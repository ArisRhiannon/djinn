"""
Cog: Message Logger — registra mensajes y perfiles de usuario en la DB.
Buffering en memoria con flush por lotes para evitar bloqueos de SQLite.
Embedding worker de fondo para busqueda semantica (sqlite-vec + BLOB).
"""
from __future__ import annotations

import asyncio
import struct
import time

import discord
from discord.ext import commands
from loguru import logger

MIN_EMBED_LENGTH = 20  # Mensajes cortos no son utiles para busqueda semantica
EMBED_BATCH_SIZE = 20  # Tamano del lote de encoding


class MessageLoggerCog(commands.Cog, name="Logger"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.queue: asyncio.Queue = asyncio.Queue()
        self.embed_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._flush_task = None
        self._embed_task = None
        # Agregador de log para embeddings: cada 6 flushes loguea mini,
        # cada 66 muestra heartbeat con stats (procesados totales, latencia).
        self._emb_flushes = 0
        self._emb_total_msgs = 0
        self._emb_total_time_ms = 0.0
        self._emb_pending_msgs = 0  # acumulador entre flushes

    async def cog_load(self) -> None:
        """Inicia los workers de flush y embedding cuando el bot esta listo."""
        self._flush_task = asyncio.create_task(self._flush_worker())
        self._embed_task = asyncio.create_task(self._embedding_worker())

    def cog_unload(self) -> None:
        for t in (self._flush_task, self._embed_task):
            if t:
                t.cancel()

    # -- Flush worker: inserta mensajes en la DB -------------------------

    async def _flush_worker(self) -> None:
        """Procesa la cola de mensajes en lotes para optimizar escrituras."""
        while True:
            try:
                item = await self.queue.get()
                batch = [item]
                while not self.queue.empty() and len(batch) < 50:
                    batch.append(self.queue.get_nowait())

                # Usar metodo publico del Database para batch insert + profile upsert
                await self.bot.db.batch_insert_messages(batch)

                # -- Obtener message_ids y alimentar cola de embeddings ----
                # SELECTs van FUERA del write_lock: con WAL los reads
                # no bloquean writes y viceversa.
                for m in batch:
                    content = m.get("content") or ""
                    if len(content) < MIN_EMBED_LENGTH:
                        continue
                    alpha_count = sum(1 for c in content if c.isalpha())
                    if alpha_count / max(len(content), 1) < 0.4:
                        continue
                    try:
                        msg_id = await self.bot.db.find_message_id(
                            m["user_id"], m["channel_id"], m["timestamp"]
                        )
                        if msg_id:
                            m["message_id"] = msg_id
                            try:
                                self.embed_queue.put_nowait(m)
                            except asyncio.QueueFull:
                                logger.warning("logger: embed_queue llena, mensaje {} sin embedding", msg_id)
                    except Exception as exc:
                        logger.debug("logger: embed queue error: {}", exc)

                for _ in batch:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Logger Worker: error escribiendo lote: {exc}")
                await asyncio.sleep(1)

    # -- Embedding worker: genera embeddings en fondo --------------------

    async def _embedding_worker(self) -> None:
        """Codifica mensajes en lotes y los almacena como BLOBs + KNN.
        Acumula por 10s antes de procesar para reducir batches pequeños."""
        while True:
            try:
                # Esperar al menos un item, luego acumular por 10s
                item = await self.embed_queue.get()
                batch = [item]
                deadline = asyncio.get_event_loop().time() + 10.0
                while len(batch) < EMBED_BATCH_SIZE:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    try:
                        next_item = await asyncio.wait_for(
                            self.embed_queue.get(), timeout=remaining
                        )
                        batch.append(next_item)
                    except asyncio.TimeoutError:
                        break

                texts = [m["content"] for m in batch]

                # Encode en thread pool (CPU-bound, no bloquea event loop)
                loop = asyncio.get_event_loop()
                _t0 = loop.time()
                embeddings = await loop.run_in_executor(
                    None, self.bot.embedder.encode, texts
                )
                _elapsed_ms = (loop.time() - _t0) * 1000.0

                # Empaquetar para ChromaDB
                items = []
                for i, m in enumerate(batch):
                    emb = embeddings[i]
                    items.append({
                        "message_id": m["message_id"],
                        "content": m["content"],
                        "embedding": emb.tolist(),
                        "guild_id": m["guild_id"],
                        "channel_id": m["channel_id"],
                        "user_id": m["user_id"],
                        "username": m.get("username") or "",
                        "timestamp": m["timestamp"]
                    })

                await self.bot.db.store_embeddings(items)

                # ── Log agregado: 1 mini cada 6 flushes, 1 heartbeat cada 66 ──
                self._emb_flushes += 1
                self._emb_total_msgs += len(batch)
                self._emb_pending_msgs += len(batch)
                self._emb_total_time_ms += _elapsed_ms

                if self._emb_flushes % 66 == 0:
                    avg_ms = self._emb_total_time_ms / self._emb_flushes if self._emb_flushes else 0.0
                    logger.info(
                        "embeddings · {} batches OK · {} mensajes totales · avg {:.0f}ms/batch",
                        self._emb_flushes, self._emb_total_msgs, avg_ms,
                    )
                    self._emb_pending_msgs = 0
                elif self._emb_flushes % 6 == 0:
                    logger.debug(
                        "embeddings · {}+ msgs procesados (batch #{}, +{:.0f}ms)",
                        self._emb_pending_msgs, self._emb_flushes, _elapsed_ms,
                    )
                    self._emb_pending_msgs = 0

                for _ in batch:
                    self.embed_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Embedding Worker: {exc}")
                await asyncio.sleep(1)

    # -- Event listeners -------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (message.author.bot and message.author.id != self.bot.user.id) or not message.guild:
            return

        attachments = " ".join(a.url for a in message.attachments) if message.attachments else None

        await self.queue.put({
            "guild_id": message.guild.id,
            "channel_id": message.channel.id,
            "user_id": message.author.id,
            "username": message.author.name,
            "display_name": message.author.display_name,
            "content": message.content,
            "attachments": attachments,
            "reply_to_id": (
                message.reference.message_id if message.reference else None
            ),
            "timestamp": int(message.created_at.timestamp()),
        })


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageLoggerCog(bot))
