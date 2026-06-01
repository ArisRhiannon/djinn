"""
Server Operational Memory — Datos reales del server con búsqueda fuzzy.

Indexa usuarios, canales, roles como chunks BM25.
Matching inteligente: normalización Unicode + BM25 (no exact match).
Capa 2: ring buffer de acciones de mod en tiempo real.
"""

from __future__ import annotations

import logging
import math
import re
import time
import unicodedata
from collections import Counter, deque
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("youkai.server_memory")

# ── BM25 minimal (misma impl que zzz_rag) ─────────────────────────────

def _normalize(text: str) -> str:
    """Normaliza Unicode + lowercase para fuzzy matching."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c)[0] in ("L", "N", "Z", "P"))
    return text.lower()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", _normalize(text))


class _BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.corpus: list[list[str]] = []
        self.doc_freqs: list[Counter] = []
        self.idf: dict[str, float] = {}
        self.avgdl: float = 0
        self.docs: list[str] = []

    def index(self, documents: list[str]) -> None:
        self.docs = documents
        self.corpus = [_tokenize(d) for d in documents]
        self.doc_freqs = [Counter(doc) for doc in self.corpus]
        n = len(self.corpus)
        self.avgdl = sum(len(d) for d in self.corpus) / max(n, 1)
        df: Counter = Counter()
        for doc in self.corpus:
            df.update(set(doc))
        self.idf = {
            word: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for word, freq in df.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        tokens = _tokenize(query)
        scores = []
        for i, doc_freq in enumerate(self.doc_freqs):
            score = 0.0
            dl = len(self.corpus[i])
            for t in tokens:
                if t not in doc_freq:
                    continue
                tf = doc_freq[t]
                idf = self.idf.get(t, 0)
                num = tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * num / den
            if score > 0:
                scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ── Estado global ──────────────────────────────────────────────────────
_bm25 = _BM25()
_ready = False
_last_rebuild: float = 0
_REBUILD_TTL = 1800  # 30 min

# Capa 2: hechos operacionales
_MAX_FACTS = 25
_operational_facts: deque[str] = deque(maxlen=_MAX_FACTS)

_MOD_KEYWORDS = frozenset([
    "ban", "kick", "mute", "warn", "timeout", "unmute", "unban",
    "spam", "raid", "infrac", "castigo", "sancion", "sanción",
    "modera", "reporte", "report", "problemat", "toxic",
    "reinciden", "historial", "warns", "bans",
])


def record_fact(fact: str) -> None:
    """Registra un hecho operacional."""
    _operational_facts.append(fact)


def _rebuild(guild: discord.Guild) -> int:
    """Reconstruye el índice BM25 con datos reales del server."""
    global _ready, _last_rebuild
    chunks: list[str] = []

    # ── Usuarios (miembros del server) ─────────────────────────────
    for member in guild.members:
        if member.bot:
            continue
        roles = [r.name for r in member.roles if not r.is_default()]
        role_str = f" | Roles: {', '.join(roles[:5])}" if roles else ""
        nick = f" aka {member.nick}" if member.nick and member.nick != member.name else ""
        joined = member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "?"
        chunk = f"[USUARIO] {member.display_name}{nick} | @{member.name} | ID:{member.id} | Joined:{joined}{role_str}"
        chunks.append(chunk)

    # ── Canales ────────────────────────────────────────────────────
    for ch in guild.text_channels:
        cat = ch.category.name if ch.category else "Sin categoría"
        topic = f" | Topic: {ch.topic[:80]}" if ch.topic else ""
        chunk = f"[CANAL] #{ch.name} | ID:{ch.id} | Categoría: {cat}{topic}"
        chunks.append(chunk)

    for ch in guild.voice_channels:
        cat = ch.category.name if ch.category else "Sin categoría"
        chunk = f"[CANAL VOZ] {ch.name} | ID:{ch.id} | Categoría: {cat}"
        chunks.append(chunk)

    # ── Roles ──────────────────────────────────────────────────────
    for role in guild.roles:
        if role.is_default() or role.is_bot_managed():
            continue
        members = [m.display_name for m in role.members[:8]]
        perms = []
        if role.permissions.administrator:
            perms.append("Admin")
        if role.permissions.ban_members:
            perms.append("Ban")
        if role.permissions.kick_members:
            perms.append("Kick")
        if role.permissions.manage_messages:
            perms.append("ManageMsg")
        perm_str = f" | Perms: {','.join(perms)}" if perms else ""
        member_str = f" | Miembros: {', '.join(members)}" if members else ""
        chunk = f"[ROL] @{role.name} | ID:{role.id} | Color:{role.color}{perm_str}{member_str}"
        chunks.append(chunk)

    # ── Server info ────────────────────────────────────────────────
    owner = guild.owner
    chunks.append(f"[SERVER] {guild.name} | Owner: {owner.display_name if owner else '?'} (ID:{guild.owner_id}) | Miembros: {guild.member_count}")

    # Indexar
    if chunks:
        _bm25.index(chunks)
        _ready = True
        _last_rebuild = time.time()
        logger.info("ServerMemory: indexados %d chunks (%d users, %d channels, %d roles)",
                    len(chunks),
                    sum(1 for c in chunks if c.startswith("[USUARIO]")),
                    sum(1 for c in chunks if c.startswith("[CANAL")),
                    sum(1 for c in chunks if c.startswith("[ROL]")))
    return len(chunks)


def _ensure_fresh(guild: discord.Guild) -> None:
    """Rebuild si el cache expiró."""
    if not _ready or (time.time() - _last_rebuild) > _REBUILD_TTL:
        _rebuild(guild)


def server_query(guild: discord.Guild, text: str, top_k: int = 5) -> list[str]:
    """Busca en la KB del server. Retorna chunks relevantes."""
    _ensure_fresh(guild)
    if not _ready:
        return []
    results = _bm25.search(text, top_k=top_k)
    return [_bm25.docs[i] for i, _ in results]


def get_server_context(guild: discord.Guild, text: str) -> str:
    """Genera contexto del server para inyectar en el LLM."""
    _ensure_fresh(guild)
    parts = []

    # Capa 1: búsqueda relevante al mensaje (top 5 chunks más relevantes)
    if _ready:
        results = _bm25.search(text, top_k=5)
        if results:
            relevant = [_bm25.docs[i] for i, score in results if score > 0.1]
            if relevant:
                parts.append("SERVER CONTEXT (datos relevantes):\n" + "\n".join(relevant))

    # Capa 2: hechos operacionales (solo si es sobre mod)
    text_lower = text.lower()
    if any(kw in text_lower for kw in _MOD_KEYWORDS):
        if _operational_facts:
            parts.append("ACCIONES RECIENTES:\n" + "\n".join(f"  • {f}" for f in _operational_facts))

    return "\n".join(parts) if parts else ""


# ── Cog ────────────────────────────────────────────────────────────────

class ServerMemory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            _rebuild(guild)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        record_fact(f"BAN: {user.display_name} (ID:{user.id})")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        record_fact(f"UNBAN: {user.display_name} (ID:{user.id})")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until and not before.timed_out_until:
                record_fact(f"MUTE: {after.display_name} (ID:{after.id})")
            elif before.timed_out_until and not after.timed_out_until:
                record_fact(f"UNMUTE: {after.display_name} (ID:{after.id})")

    memory_group = app_commands.Group(name="memory", description="Server operational memory")

    @memory_group.command(name="update", description="Reconstruir la memoria del server")
    @app_commands.checks.has_permissions(administrator=True)
    async def memory_update(self, interaction: discord.Interaction):
        count = _rebuild(interaction.guild)
        await interaction.response.send_message(
            f"✅ Server memory: **{count}** chunks indexados. {len(_operational_facts)} hechos en buffer.",
            ephemeral=True,
        )

    @memory_group.command(name="search", description="Buscar en la memoria del server (debug)")
    @app_commands.describe(query="Término de búsqueda")
    async def memory_search(self, interaction: discord.Interaction, query: str):
        results = server_query(interaction.guild, query, top_k=5)
        if not results:
            await interaction.response.send_message("Sin resultados.", ephemeral=True)
            return
        text = "\n".join(results)
        await interaction.response.send_message(f"```\n{text[:1900]}\n```", ephemeral=True)

    @memory_group.command(name="status", description="Ver estado de la memoria")
    async def memory_status(self, interaction: discord.Interaction):
        n = len(_bm25.docs) if _ready else 0
        age = int(time.time() - _last_rebuild) if _last_rebuild else -1
        await interaction.response.send_message(
            f"Server Memory: {'🟢' if _ready else '🔴'} | {n} chunks | age {age}s | {len(_operational_facts)} hechos",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerMemory(bot))
