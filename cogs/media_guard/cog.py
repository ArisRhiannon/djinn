"""MediaGuard main cog — slash commands and on_message listener.

Architecture:
  /prohibir  → resolves media → embedder → index.add → persist
  on_message → media_resolver → embedder → index.search
             → match? auto-delete + notify
             → gray zone? send to review channel
"""

from __future__ import annotations

import asyncio
import logging
import os
from io import BytesIO
from typing import Optional, Set

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from .embedder import Embedder
from .gif_processor import extract_frames, is_gif
from .index_manager import IndexManager
from .media_resolver import (
    MediaSource,
    download_media,
    extract_media_sources,
)
from .thresholds import (
    GIF_FRAME_SIMILARITY_THRESHOLD,
    GIF_MIN_MATCHING_FRAMES,
    GIF_MULTI_FRAME_THRESHOLD,
    GRAY_ZONE_HIGH,
    GRAY_ZONE_LOW,
    IMAGE_SIMILARITY_THRESHOLD,
    REVIEW_CHANNEL_ENV,
)

logger = logging.getLogger("youkai.mediaguard.cog")


class MediaGuardCog(commands.Cog):
    """Near-duplicate media detection using CNN embeddings + HNSW.

    Degrades gracefully: if the ONNX model or hnswlib is missing,
    detection is simply disabled without crashing the bot.
    """

    def __init__(self, bot) -> None:
        self.bot = bot
        self.embedder = Embedder()
        self.index = IndexManager()
        self._bg_tasks: Set[asyncio.Task] = set()
        self._review_channel_id: Optional[int] = self._parse_review_channel()
        self._message_cache: Set[str] = set()  # Processed message IDs

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Async init: load index from disk in thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.index.load)
        if self.index.available and self.embedder.available:
            logger.info(
                "MediaGuard ready: %d banned entries, model OK",
                self.index.num_banned,
            )
        elif self.index.available:
            logger.warning(
                "MediaGuard index OK but NO MODEL — detection disabled. "
                "Run scripts/download_mobilenet_onnx.py"
            )
        elif self.embedder.available:
            logger.warning(
                "MediaGuard model OK but NO INDEX — detection disabled. "
                "Add media with /prohibir"
            )
        else:
            logger.warning(
                "MediaGuard: neither model nor index available — "
                "detection disabled. Install onnxruntime + hnswlib "
                "and run scripts/download_mobilenet_onnx.py"
            )

    def cog_unload(self) -> None:
        """Persist index and cancel pending tasks on unload."""
        for task in self._bg_tasks:
            task.cancel()
        self._bg_tasks.clear()
        try:
            self.index.save()
        except Exception as e:
            logger.debug("Index save on unload failed: %s", e)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _parse_review_channel(self) -> Optional[int]:
        raw = os.environ.get(REVIEW_CHANNEL_ENV, "").strip()
        if raw:
            try:
                return int(raw)
            except ValueError:
                logger.warning("Invalid %s=%r", REVIEW_CHANNEL_ENV, raw)
        return None

    @property
    def _ready(self) -> bool:
        """True if both embedder and index are available."""
        return self.embedder.available and self.index.available

    # ── /prohibir ────────────────────────────────────────────────────────

    @app_commands.command(
        name="prohibir",
        description="🔒 Añade una imagen/GIF a la lista de media prohibida (admin)",
    )
    @app_commands.describe(
        media_url="Link directo a la imagen/GIF (opcional si adjuntas archivo)",
        file="Archivo de imagen o GIF adjunto (opcional si usas link)",
    )
    @app_commands.default_permissions(administrator=True)
    async def prohibir(
        self,
        interaction: discord.Interaction,
        media_url: Optional[str] = None,
        file: Optional[discord.Attachment] = None,
    ) -> None:
        """Add banned media to the detection index."""
        # Double-check admin (belt and suspenders)
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "⛔ Solo los administradores pueden usar este comando.",
                ephemeral=True,
            )
            return

        if not self._ready:
            await interaction.response.send_message(
                "⚠️ MediaGuard no está listo.\n"
                "Asegúrate de que `onnxruntime`, `hnswlib` estén instalados y "
                "el modelo ONNX esté en `data/mobilenetv3_small.onnx`.\n"
                "Ejecuta: `python scripts/download_mobilenet_onnx.py`",
                ephemeral=True,
            )
            return

        # ── Resolve media bytes ─────────────────────────────────────
        bytes_data: Optional[bytes] = None
        source_type = "image"

        if file is not None:
            try:
                bytes_data = await file.read()
                ct = file.content_type or ""
                source_type = "gif" if "gif" in ct else "image"
            except (discord.HTTPException, discord.NotFound) as e:
                logger.debug("Attachment read failed: %s", e)

        if bytes_data is None and media_url:
            import aiohttp

            try:
                timeout = aiohttp.ClientTimeout(total=15)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    source = MediaSource(media_url, "direct_link")
                    bytes_data = await download_media(source, session)
                    if bytes_data:
                        source_type = "gif" if is_gif(bytes_data) else "image"
            except Exception as e:
                logger.debug("URL download failed for /prohibir: %s", e)

        if bytes_data is None:
            await interaction.response.send_message(
                "❌ No se encontró media válida. Adjunta una imagen/GIF "
                "o proporciona un link directo.",
                ephemeral=True,
            )
            return

        # Defer now that we have data
        await interaction.response.defer(ephemeral=True)

        # ── Generate embeddings ─────────────────────────────────────
        gif_flag = is_gif(bytes_data)
        media_type = "gif" if gif_flag else "image"

        embeddings = await asyncio.to_thread(
            self._generate_embeddings, bytes_data, gif_flag
        )

        if not embeddings:
            await interaction.followup.send(
                "❌ No se pudieron generar embeddings. ¿El archivo está corrupto?"
            )
            return

        # ── Add to index ────────────────────────────────────────────
        media_id = self.index.add_media(
            embeddings,
            media_type=media_type,
            added_by=interaction.user.id,
            source_url=media_url or file.url if file else "",
        )

        if media_id:
            await interaction.followup.send(
                f"✅ **Media prohibida añadida**\n"
                f"🆔 `{media_id}`\n"
                f"📁 {media_type} · {len(embeddings)} embedding(s)\n"
                f"👤 {interaction.user.mention}"
            )
        else:
            await interaction.followup.send(
                "❌ Error interno al guardar en el índice. Revisa los logs."
            )

    def _generate_embeddings(
        self, data: bytes, is_gif_flag: bool
    ) -> list:
        """Generate embeddings from raw bytes (sync, runs in thread pool)."""
        if is_gif_flag:
            frames = extract_frames(data)
            if not frames:
                return []
            embeddings = []
            for frame in frames:
                emb = self.embedder.embed_image(frame)
                if emb is not None:
                    embeddings.append(emb)
            return embeddings
        else:
            try:
                image = Image.open(BytesIO(data))
                emb = self.embedder.embed_image(image)
                return [emb] if emb is not None else []
            except Exception:
                logger.debug("Failed to open image for /prohibir", exc_info=True)
                return []

    # ── on_message listener ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Scan every message for banned media."""
        if message.author.bot:
            return
        if not self._ready:
            return
        if not message.guild:  # DM — skip for now
            return

        # Deduplicate message IDs
        msg_key = str(message.id)
        if msg_key in self._message_cache:
            return
        self._message_cache.add(msg_key)
        if len(self._message_cache) > 2000:
            self._message_cache.clear()

        sources = extract_media_sources(message)
        if not sources:
            return

        # Fire-and-forget with task tracking (prevents GC)
        task = asyncio.create_task(self._process_media(message, sources))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _process_media(
        self,
        message: discord.Message,
        sources: list[MediaSource],
    ) -> None:
        """Download, embed, search, and act on media sources."""
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for source in sources:
                    data = await download_media(source, session)
                    if data is None:
                        continue

                    gif_flag = is_gif(data)
                    similarity = 0.0
                    matched_id: Optional[str] = None

                    # ── Generate embeddings and search ───────────
                    if gif_flag:
                        frames = extract_frames(data)
                        if not frames:
                            continue
                        frame_embs = []
                        for frm in frames:
                            emb = self.embedder.embed_image(frm)
                            if emb is not None:
                                frame_embs.append(emb)
                        if not frame_embs:
                            continue

                        high_matches = 0
                        for emb in frame_embs:
                            results = self.index.search(emb, k=1)
                            if results:
                                uid, sim = results[0]
                                if sim > similarity:
                                    similarity = sim
                                    matched_id = uid
                                if sim >= GIF_MULTI_FRAME_THRESHOLD:
                                    high_matches += 1

                        # Multi-frame consensus for GIFs
                        if high_matches < GIF_MIN_MATCHING_FRAMES:
                            if similarity >= GRAY_ZONE_LOW:
                                await self._send_to_review(
                                    message, matched_id or "?",
                                    similarity, source.url,
                                )
                            continue
                    else:
                        try:
                            image = Image.open(BytesIO(data))
                            emb = self.embedder.embed_image(image)
                        except Exception:
                            continue
                        if emb is None:
                            continue
                        results = self.index.search(emb, k=1)
                        if results:
                            matched_id, similarity = results[0]

                    # ── Decision ────────────────────────────────
                    threshold = (
                        GIF_FRAME_SIMILARITY_THRESHOLD
                        if gif_flag
                        else IMAGE_SIMILARITY_THRESHOLD
                    )

                    if similarity >= threshold:
                        await self._auto_delete(message, matched_id, similarity)
                        return  # One hit is enough — don't spam deletions

                    elif similarity >= GRAY_ZONE_LOW:
                        await self._send_to_review(
                            message, matched_id or "?",
                            similarity, source.url,
                        )

        except Exception:
            logger.exception("MediaGuard _process_media error")

    # ── Actions ─────────────────────────────────────────────────────────

    async def _auto_delete(
        self,
        message: discord.Message,
        matched_id: Optional[str],
        similarity: float,
    ) -> None:
        """Delete the message and post a brief notification."""
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            # Message already deleted or we lack permissions
            pass

        logger.info(
            "MediaGuard DELETED: msg %s from %s (%d) — match %s (%.1f%%)",
            message.id, message.author, message.author.id,
            matched_id, similarity * 100,
        )

        meta = self.index.get_metadata(matched_id or "")
        added_by = meta.get("added_by", "?") if meta else "?"
        banned_on = meta.get("timestamp", "???")[:10] if meta else "???"

        try:
            await message.channel.send(
                f"🛡️ **Media prohibida detectada** — mensaje eliminado.\n"
                f"📊 Similitud: **{similarity:.0%}**  ·  "
                f"🆔 `{matched_id}`  ·  añadida por <@{added_by}> ({banned_on})",
                delete_after=8,
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _send_to_review(
        self,
        message: discord.Message,
        matched_id: str,
        similarity: float,
        source_url: str,
    ) -> None:
        """Escalate gray-zone matches to the review channel."""
        logger.info(
            "MediaGuard GRAY: msg %s (%.1f%%) → %s",
            message.id, similarity * 100, matched_id,
        )

        if not self._review_channel_id:
            return

        channel = self.bot.get_channel(self._review_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="🟡 MediaGuard — Zona Gris",
            description=(
                f"**Similitud:** {similarity:.0%}\n"
                f"**Match:** `{matched_id}`\n"
                f"**Usuario:** {message.author.mention} (`{message.author.id}`)\n"
                f"**Canal:** {message.channel.mention}\n"
                f"**URL:** {source_url[:300]}"
            ),
            color=0xF1C40F,
        )
        embed.add_field(
            name="🔗 Mensaje original",
            value=f"[Ir al mensaje]({message.jump_url})",
            inline=False,
        )
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.debug("Review channel send failed: %s", exc)
