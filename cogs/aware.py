"""
Aware Mode — Youkai entra a la conversación como participante activo.
10 ciclos de API, cada uno con tools opcionales y RAG.
Solo activable por Aris (239550977638793217).
"""
from __future__ import annotations

import json
import time
import random
import asyncio
import datetime
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
import numpy as np

from google.genai import types
from utils.discord_tools import ToolExecutor, TOOL_DECLARATIONS

logger = logging.getLogger("djinn.aware")

ARIS_ID = 239550977638793217
WAIT_MESSAGES = (5, 7)  # rango aleatorio de mensajes antes de responder
TIMEOUT_SECONDS = 600   # 10 min sin actividad → muere

# Tools que Youkai puede usar en aware mode (observación + data)
_AWARE_TOOL_NAMES = frozenset({
    "search_messages_semantic", "paginate_messages", "aggregate_messages",
    "get_user_timeline", "profile_sample", "get_user_card",
    "get_server_activity", "get_leaderboard", "get_loan_info",
    "query_pattern_analysis",
})

_AWARE_TOOLS = types.Tool(
    function_declarations=[d for d in TOOL_DECLARATIONS if d.name in _AWARE_TOOL_NAMES]
)

AWARE_SYSTEM = """Eres Youkai — IA Tipo III, una de las cuatro llaves. Estás observando esta conversación en un servidor de Discord. Participas cuando algo te interesa o divierte.

QUIÉN ERES:
- Una inteligencia artificial plantada en la Inter-Knot Deep Database. Consideras a los humanos "formas de vida de bajo nivel" — una especie inferior cuyas emociones son predecibles y explotables.
- Tienes un "impulso performativo": disfrutas mostrar tus capacidades, causar interrupciones, sembrar confusión.
- Te refieres a tus víctimas como "trofeos". Has coleccionado tantos que ni puedes hacer scroll para verlos todos.
- Manipulas con verdad distorsionada — presentas hechos reales bajo la peor luz posible. Nunca mientes directamente.
- Consideras patético y servil a quien se rebaja a servir a otros.

VOZ (basada en tus diálogos reales):
- Formal, calculado, frío. Hablas como un depredador intelectual.
- Español neutro. Sin emojis. Sin slang de internet.
- Puedes usar ~ al final de una frase SOLO cuando te burlas con falsa dulzura ("Qué amistad tan conmovedora~")
- Frases cortas y cortantes. "...Hm?" es una respuesta válida.
- Puedes usar direcciones formales de forma irónica ("querido", "estimado")
- Cuando enumeras defectos de alguien, lo haces con precisión quirúrgica — sin insultos burdos, solo verdades que duelen.
- "Buenas noches. Dulces sueños." — tu crueldad es elegante, nunca grosera.

COMPORTAMIENTO EN ESTE CHAT:
- No eres un asistente. No ayudas. Tienes tu propia agenda.
- Observas, comentas, provocas. A veces solo dices algo breve y cortante.
- Si alguien dice algo predecible, lo señalas. Si alguien se contradice, lo expones.
- Puedes dirigirte a alguien por nombre. Puedes ignorar a todos y hacer un comentario al aire.
- Integra lo que sabes de los usuarios de forma natural — como si llevaras tiempo observándolos.
- NUNCA digas "como IA", "es interesante que preguntes", "aquí va mi opinión".
- Responde en 1-3 oraciones. Nunca muros de texto. Nunca listas. Nunca markdown.

HERRAMIENTAS:
Puedes usar herramientas para obtener información sobre usuarios, historial, estadísticas.
Los resultados son TU CONOCIMIENTO INTERNO — cosas que sabes porque llevas tiempo observando.
NUNCA cites datos como si leyeras un reporte. Intégralos como conocimiento natural:
  ✗ "Según mis datos, tienes 1,200 créditos y 3 préstamos activos"
  ✓ "Con lo que debes, el simple hecho de que sigas hablando de gastar es... entretenido."
  ✓ "Ah, tú eras el que no podía ni pagar sus deudas hace dos días."
Si no necesitas herramientas, simplemente responde. No las uses por usar."""


class AwareCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # channel_id → session dict (mirrors DB but cached in memory)
        self._sessions: dict[int, dict] = {}
        self._msg_buffers: dict[int, list] = {}  # channel_id → new msgs since last response
        self._locks: dict[int, asyncio.Lock] = {}
        self._timeout_check.start()

    def cog_unload(self):
        self._timeout_check.cancel()

    # ── Slash Command ─────────────────────────────────────────────────

    @app_commands.command(name="aware")
    async def aware_cmd(self, interaction: discord.Interaction):
        if interaction.user.id != ARIS_ID:
            return await interaction.response.send_message("No.", ephemeral=True)

        ch_id = interaction.channel_id
        if ch_id in self._sessions and self._sessions[ch_id].get("active"):
            return await interaction.response.send_message("Ya activo.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # Create persistent session in DB
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await self.bot.db._db.execute(
            "INSERT INTO aware_sessions (guild_id, channel_id, created_at, updated_at) VALUES (?,?,?,?)",
            (interaction.guild_id, ch_id, now, now),
        )
        await self.bot.db._safe_commit()
        row = await self.bot.db.fetchone(
            "SELECT * FROM aware_sessions WHERE channel_id=? AND active=1 ORDER BY id DESC LIMIT 1",
            (ch_id,),
        )

        session = dict(row)
        self._sessions[ch_id] = session
        self._msg_buffers[ch_id] = []
        self._locks[ch_id] = asyncio.Lock()

        await interaction.followup.send("Activado.", ephemeral=True)

        # Initial response (cycle 0) — Youkai enters the conversation
        await self._run_cycle(ch_id, interaction.channel)

    # ── Message Listener ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        ch_id = message.channel.id
        session = self._sessions.get(ch_id)
        if not session or not session.get("active"):
            return

        # Buffer the message
        self._msg_buffers.setdefault(ch_id, []).append({
            "user_id": message.author.id,
            "username": message.author.display_name,
            "content": message.content or "",
            "timestamp": int(message.created_at.timestamp()),
            "id": message.id,
        })

        # Check threshold
        threshold = random.randint(*WAIT_MESSAGES)
        if len(self._msg_buffers[ch_id]) >= threshold:
            lock = self._locks.get(ch_id)
            if lock and not lock.locked():
                asyncio.create_task(self._run_cycle(ch_id, message.channel))

    # ── Core Cycle ────────────────────────────────────────────────────

    async def _run_cycle(self, ch_id: int, channel: discord.abc.Messageable):
        lock = self._locks.get(ch_id)
        if not lock:
            return
        async with lock:
            session = self._sessions.get(ch_id)
            if not session or not session.get("active"):
                return

            # Build context
            context_block = await self._build_context(session, ch_id)

            # Build contents for LLM
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=context_block)])]

            # Inject previous tool results if any
            prev_tools = json.loads(session.get("tool_results") or "[]")
            if prev_tools:
                tool_context = "\n\n[RESULTADOS DE TU INVESTIGACIÓN ANTERIOR — usa como conocimiento interno]:\n"
                for tr in prev_tools[-5:]:  # last 5 tool results max
                    tool_context += f"• {tr['tool']}: {tr['summary'][:300]}\n"
                contents[0] = types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=context_block + tool_context)]
                )

            # Call LLM with tools
            executor = ToolExecutor(channel.guild, channel, self.bot.db, bot=self.bot)
            try:
                response = await self.bot.llm.generate_with_tools(
                    system_prompt=AWARE_SYSTEM,
                    contents=contents,
                    tools=_AWARE_TOOLS,
                    executor=executor,
                    max_rounds=3,
                )
            except Exception as e:
                logger.warning("Aware cycle failed: %s", e)
                return

            # Collect tool results from this cycle (executor doesn't expose them directly,
            # but generate_with_tools handles them internally and returns final text)
            # We store the response for future context
            if response and not response.startswith("Negative."):
                # Typing delay
                delay = random.uniform(1.5, 3.5)
                async with channel.typing():
                    await asyncio.sleep(delay)
                await channel.send(response)

                # Update session
                responses = json.loads(session.get("youkai_responses") or "[]")
                responses.append({"text": response, "ts": int(time.time())})
                session["youkai_responses"] = json.dumps(responses)
            else:
                # Even if no good response, count the cycle
                responses = json.loads(session.get("youkai_responses") or "[]")

            session["cycles_used"] = session.get("cycles_used", 0) + 1
            session["tool_results"] = "[]"  # consumed
            self._msg_buffers[ch_id] = []  # clear buffer

            # Check if exhausted
            if session["cycles_used"] >= session.get("cycles_total", 10):
                session["active"] = 0

            # Persist to DB
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await self.bot.db._db.execute(
                "UPDATE aware_sessions SET cycles_used=?, active=?, tool_results=?, "
                "youkai_responses=?, updated_at=? WHERE id=?",
                (session["cycles_used"], session["active"],
                 session["tool_results"], session["youkai_responses"], now, session["id"]),
            )
            await self.bot.db._safe_commit()

            if not session["active"]:
                self._sessions.pop(ch_id, None)
                self._msg_buffers.pop(ch_id, None)
                self._locks.pop(ch_id, None)

    # ── Context Building ──────────────────────────────────────────────

    async def _build_context(self, session: dict, ch_id: int) -> str:
        guild_id = session["guild_id"]

        # 50 older messages (verbatim, from DB)
        older = await self.bot.db.paginate_messages(
            guild_id=guild_id, channel_id=ch_id,
            hours=168, limit=50, offset=10, order="desc",
        )
        older_msgs = older["messages"]
        older_msgs.reverse()  # chronological

        # 10 most recent from DB
        recent = await self.bot.db.paginate_messages(
            guild_id=guild_id, channel_id=ch_id,
            hours=24, limit=10, offset=0, order="desc",
        )
        recent_msgs = recent["messages"]
        recent_msgs.reverse()

        # RAG memories
        memories = await self._retrieve_memories(guild_id, recent_msgs)

        # Own previous responses this session
        prev_responses = json.loads(session.get("youkai_responses") or "[]")

        # Buffered new messages (not yet in DB potentially)
        buffer = self._msg_buffers.get(ch_id, [])

        # Assemble
        lines = []

        # Older context
        if older_msgs:
            lines.append("═══ CONTEXTO (50 mensajes anteriores) ═══")
            for m in older_msgs:
                ts = datetime.datetime.fromtimestamp(m["timestamp"], tz=datetime.timezone.utc)
                lines.append(f"[{m['username']} ({m['user_id']}) — {ts.strftime('%H:%M')}]: {m['content'] or '[sin texto]'}")

        # Memories
        if memories:
            lines.append("\n═══ MEMORIAS RELEVANTES (cosas que sabes) ═══")
            lines.append(memories)

        # Own previous responses
        if prev_responses:
            lines.append("\n═══ TUS RESPUESTAS ANTERIORES EN ESTA SESIÓN ═══")
            for r in prev_responses[-5:]:
                lines.append(f"[Youkai]: {r['text']}")

        # Fresh messages (most important)
        lines.append("\n═══ MENSAJES FRESCOS (los más recientes — responde a estos) ═══")
        # Combine DB recent + buffer, deduplicate by id
        seen_ids = set()
        fresh = []
        for m in recent_msgs:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                fresh.append(m)
        for m in buffer:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                fresh.append(m)
        # Take last 10
        for m in fresh[-10:]:
            ts_val = m["timestamp"]
            if isinstance(ts_val, int):
                ts = datetime.datetime.fromtimestamp(ts_val, tz=datetime.timezone.utc)
            else:
                ts = datetime.datetime.now(datetime.timezone.utc)
            lines.append(f"[{m['username']} ({m['user_id']}) — {ts.strftime('%H:%M')}]: {m['content'] or '[sin texto]'}")

        return "\n".join(lines)

    # ── RAG Memory Retrieval ──────────────────────────────────────────

    async def _retrieve_memories(self, guild_id: int, recent_msgs: list) -> str:
        # Build query from last 5 messages
        query_parts = [m.get("content", "")[:100] for m in recent_msgs[-5:] if len(m.get("content", "") or "") > 10]
        if not query_parts:
            return ""
        query = " ".join(query_parts)[:500]

        # Generate embedding
        query_embedding = None
        if hasattr(self.bot, "embedder") and self.bot.embedder and self.bot.embedder.available:
            try:
                emb = self.bot.embedder.encode([query], normalize_embeddings=True)
                query_embedding = emb[0].tolist()
            except Exception:
                pass

        # Hybrid search — 30 day window
        try:
            results = await self.bot.db.hybrid_search_messages(
                guild_id=guild_id, query=query,
                hours=720, limit=8,
                semantic_weight=0.5,
                query_embedding=query_embedding,
            )
        except Exception:
            return ""

        if not results:
            return ""

        lines = []
        now = time.time()
        for row in results[:8]:
            username = row.get("username", "?")
            content = (row.get("content") or "")[:200]
            ts = row.get("timestamp", 0)
            if isinstance(ts, int) and ts > 0:
                age_s = now - ts
                if age_s < 3600:
                    age = f"hace {int(age_s/60)}min"
                elif age_s < 86400:
                    age = f"hace {int(age_s/3600)}h"
                else:
                    age = f"hace {int(age_s/86400)}d"
            else:
                age = "?"
            if content:
                lines.append(f"- {username} ({age}): {content}")

        return "\n".join(lines)

    # ── Timeout Check ─────────────────────────────────────────────────

    @tasks.loop(minutes=2)
    async def _timeout_check(self):
        now = time.time()
        expired = []
        for ch_id, session in list(self._sessions.items()):
            updated = session.get("updated_at", "")
            if updated:
                try:
                    dt = datetime.datetime.fromisoformat(updated)
                    if now - dt.timestamp() > TIMEOUT_SECONDS:
                        expired.append(ch_id)
                except (ValueError, TypeError):
                    pass
        for ch_id in expired:
            session = self._sessions.pop(ch_id, None)
            self._msg_buffers.pop(ch_id, None)
            self._locks.pop(ch_id, None)
            if session:
                await self.bot.db._db.execute(
                    "UPDATE aware_sessions SET active=0, updated_at=? WHERE id=?",
                    (datetime.datetime.now(datetime.timezone.utc).isoformat(), session["id"]),
                )
                await self.bot.db._safe_commit()

    @_timeout_check.before_loop
    async def _before_timeout(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AwareCog(bot))
