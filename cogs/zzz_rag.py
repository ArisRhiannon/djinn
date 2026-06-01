"""
ZZZ RAG — Knowledge base de Zenless Zone Zero.

Scraper directo a static.nanoka.cc (API estática JSON).
BM25 en memoria para retrieval (~0 costo computacional).
Auto-inyección en orchestrator cuando detecta keywords ZZZ.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("djinn.zzz_rag")

# ── BM25 minimal (inline, sin dependencia externa) ─────────────────────
import math
from collections import Counter


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class BM25:
    """BM25 Okapi — implementación mínima en memoria."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.corpus: list[list[str]] = []
        self.doc_freqs: list[Counter] = []
        self.idf: dict[str, float] = {}
        self.avgdl: float = 0
        self.docs: list[str] = []  # texto original de cada chunk

    def index(self, documents: list[str]) -> None:
        self.docs = documents
        self.corpus = [_tokenize(d) for d in documents]
        self.doc_freqs = [Counter(doc) for doc in self.corpus]
        n = len(self.corpus)
        self.avgdl = sum(len(d) for d in self.corpus) / max(n, 1)

        # IDF
        df: Counter = Counter()
        for doc in self.corpus:
            df.update(set(doc))
        self.idf = {
            word: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for word, freq in df.items()
        }

    def search(self, query: str, top_k: int = 3) -> list[tuple[int, float]]:
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


# ── Singleton global para acceso desde orchestrator ─────────────────────
_zzz_bm25 = BM25()
_zzz_name_index: dict[str, int] = {}  # nombre_lower → doc index
_zzz_ready = False

# Keywords que activan la inyección
_ZZZ_KEYWORDS = frozenset([
    "zzz", "zenless", "zone zero", "agente", "agent", "w-engine", "wengine",
    "bangboo", "drive disc", "disco", "anomaly", "anomalía",
    # Facciones
    "cunning hares", "section 6", "belobog", "victoria housekeeping",
    "obol", "calydon", "sons of calydon", "hollow",
    # Atributos
    "physical", "fire", "ice", "electric", "ether",
    # Specialties
    "stun", "attack", "support", "defense", "anomaly", "rupture",
])

# Nombres de agentes conocidos (se actualiza dinámicamente al indexar)
_zzz_agent_names: set[str] = set()

BASE_URL = "https://static.nanoka.cc"


def zzz_query(text: str, top_k: int = 3) -> list[str]:
    """Busca en la KB de ZZZ. Retorna chunks relevantes o []."""
    if not _zzz_ready:
        return []
    text_lower = text.lower()

    # Paso 1: exact match por nombre de agente/arma
    for name, idx in _zzz_name_index.items():
        if name in text_lower:
            results = [_zzz_bm25.docs[idx]]
            # También buscar BM25 para complementar
            bm25_results = _zzz_bm25.search(text, top_k=2)
            for i, _ in bm25_results:
                if i != idx:
                    results.append(_zzz_bm25.docs[i])
            return results[:top_k]

    # Paso 2: BM25 puro
    results = _zzz_bm25.search(text, top_k=top_k)
    return [_zzz_bm25.docs[i] for i, _ in results]


def zzz_should_inject(text: str) -> bool:
    """Detecta si el mensaje es sobre ZZZ."""
    text_lower = text.lower()
    # Check keywords
    for kw in _ZZZ_KEYWORDS:
        if kw in text_lower:
            return True
    # Check agent names
    for name in _zzz_agent_names:
        if name in text_lower:
            return True
    return False


# ── Scraper ─────────────────────────────────────────────────────────────

async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
        if r.status == 200:
            return await r.json()
        logger.warning("ZZZ RAG: HTTP %d para %s", r.status, url)
        return None


def _clean_desc(text: str) -> str:
    """Limpia tags de formato del juego."""
    text = re.sub(r"<color=[^>]*>", "", text)
    text = text.replace("</color>", "")
    text = re.sub(r"<IconMap:[^>]*>", "", text)
    return text.strip()


async def _refresh_kb() -> int:
    """Descarga datos de nanoka.cc y reconstruye el índice BM25."""
    global _zzz_ready
    chunks: list[str] = []
    name_idx: dict[str, int] = {}
    agent_names: set[str] = set()

    async with aiohttp.ClientSession() as session:
        # Obtener versión actual
        manifest = await _fetch_json(session, f"{BASE_URL}/manifest.json")
        if not manifest:
            logger.warning("ZZZ RAG: no se pudo obtener manifest.json")
            return 0
        zzz_manifest = manifest.get("zzz", {})
        version = zzz_manifest.get("live", "")
        if not version:
            logger.warning("ZZZ RAG: no se encontró versión live en manifest")
            return 0
        logger.info("ZZZ RAG: usando versión %s", version)

        # ── AGENTES ────────────────────────────────────────────────────
        chars = await _fetch_json(session, f"{BASE_URL}/zzz/{version}/character.json")
        if chars:
            for cid, data in chars.items():
                if cid in ("2011", "2021"):
                    continue
                name_en = data.get("en", "???")

                detail = await _fetch_json(
                    session, f"{BASE_URL}/zzz/{version}/en/character/{cid}.json"
                )
                if not detail:
                    continue

                rarity = detail.get("rarity", 0)
                rank_str = "S" if rarity >= 4 else "A" if rarity == 3 else "B"
                elem_dict = detail.get("element_type", {})
                element = list(elem_dict.values())[0] if elem_dict else "?"
                wtype_dict = detail.get("weapon_type", {})
                specialty = list(wtype_dict.values())[0] if wtype_dict else "?"
                hit_dict = detail.get("hit_type", {})
                hit_type = list(hit_dict.values())[0] if hit_dict else "?"
                camp_dict = detail.get("camp", {})
                faction = list(camp_dict.values())[0] if camp_dict else "?"

                lines = [f"[AGENTE] {name_en} | {rank_str}-Rank | {element} | {specialty} | {hit_type} | Facción: {faction}"]

                # Skills completos
                skills = detail.get("skill", {})
                for cat, sk_data in skills.items():
                    if not isinstance(sk_data, dict):
                        continue
                    descs = sk_data.get("description", [])
                    for desc in descs:
                        sname = desc.get("name", "")
                        sdesc = _clean_desc(desc.get("desc", ""))
                        if sname:
                            lines.append(f"  {cat.upper()}: {sname} — {sdesc[:250]}")

                # Talents (core passives / mindscape cinema)
                talent = detail.get("talent", {})
                if talent:
                    lines.append("  TALENTOS:")
                    for tid, tdata in talent.items():
                        if isinstance(tdata, dict):
                            tname = tdata.get("name", "")
                            tdesc = _clean_desc(tdata.get("desc", ""))
                            if tname:
                                lines.append(f"    {tname}: {tdesc[:200]}")

                chunk = "\n".join(lines)
                idx = len(chunks)
                chunks.append(chunk)
                name_lower = name_en.lower()
                name_idx[name_lower] = idx
                agent_names.add(name_lower)
                no_space = name_lower.replace(" ", "")
                if no_space != name_lower:
                    name_idx[no_space] = idx

        # ── W-ENGINES ──────────────────────────────────────────────────
        weapons = await _fetch_json(session, f"{BASE_URL}/zzz/{version}/weapon.json")
        if weapons:
            for wid, data in weapons.items():
                name_en = data.get("en", "???")
                rarity = data.get("rank", 0)
                rank_str = "S" if rarity >= 4 else "A" if rarity == 3 else "B"
                atk = data.get("atk", "?")
                sub = data.get("sub", "")
                desc = _clean_desc(data.get("desc", ""))
                chunk = f"[W-ENGINE] {name_en} | {rank_str}-Rank | ATK: {atk} | Sub: {sub}\nEfecto: {desc[:400]}"
                idx = len(chunks)
                chunks.append(chunk)
                name_idx[name_en.lower()] = idx

        # ── BANGBOOS ───────────────────────────────────────────────────
        bangboos = await _fetch_json(session, f"{BASE_URL}/zzz/{version}/bangboo.json")
        if bangboos:
            for bid, data in bangboos.items():
                name_en = data.get("en", "???")
                rarity = data.get("rank", 0)
                rank_str = "S" if rarity >= 4 else "A" if rarity == 3 else "B"
                # Detalle del bangboo
                detail = await _fetch_json(
                    session, f"{BASE_URL}/zzz/{version}/en/bangboo/{bid}.json"
                )
                lines = [f"[BANGBOO] {name_en} | {rank_str}-Rank"]
                if detail:
                    skills = detail.get("skill", [])
                    if isinstance(skills, list):
                        for sk in skills:
                            if isinstance(sk, dict):
                                sname = sk.get("name", "")
                                sdesc = _clean_desc(sk.get("desc", ""))
                                if sname:
                                    lines.append(f"  {sname}: {sdesc[:200]}")
                    elif isinstance(skills, dict):
                        for sk_id, sk in skills.items():
                            if isinstance(sk, dict):
                                sname = sk.get("name", "")
                                sdesc = _clean_desc(sk.get("desc", ""))
                                if sname:
                                    lines.append(f"  {sname}: {sdesc[:200]}")
                chunk = "\n".join(lines)
                idx = len(chunks)
                chunks.append(chunk)
                name_idx[name_en.lower()] = idx

        # ── DRIVE DISCS ────────────────────────────────────────────────
        discs = await _fetch_json(session, f"{BASE_URL}/zzz/{version}/equipment.json")
        if discs:
            for did, data in discs.items():
                detail = await _fetch_json(
                    session, f"{BASE_URL}/zzz/{version}/en/equipment/{did}.json"
                )
                if not detail:
                    continue
                name_en = detail.get("name", "???")
                lines = [f"[DRIVE DISC] {name_en}"]
                # Set effects
                effects = detail.get("effect", {})
                if isinstance(effects, dict):
                    for pc, eff in effects.items():
                        if eff:
                            lines.append(f"  {pc}-Piece: {_clean_desc(str(eff))[:200]}")
                # Substats info
                suit_type = detail.get("suit_type", "")
                if suit_type:
                    lines.append(f"  Tipo: {suit_type}")
                chunk = "\n".join(lines)
                idx = len(chunks)
                chunks.append(chunk)
                name_idx[name_en.lower()] = idx

    # Indexar
    if chunks:
        global _zzz_name_index, _zzz_agent_names, _zzz_ready
        _zzz_bm25.index(chunks)
        _zzz_name_index = name_idx
        _zzz_agent_names = agent_names
        _zzz_ready = True
        logger.info("ZZZ RAG: indexados %d chunks (v%s)", len(chunks), version)

    return len(chunks)


# ── Cog ─────────────────────────────────────────────────────────────────

class ZZZRag(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Indexar al arrancar el bot."""
        try:
            count = await _refresh_kb()
            logger.info("ZZZ RAG: cargado con %d chunks al inicio.", count)
        except Exception:
            logger.exception("ZZZ RAG: error en carga inicial.")

    zzz_group = app_commands.Group(name="zzz", description="Zenless Zone Zero knowledge base")

    @zzz_group.command(name="update", description="Actualizar la KB de ZZZ desde nanoka.cc")
    @app_commands.checks.has_permissions(administrator=True)
    async def zzz_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            count = await _refresh_kb()
            await interaction.followup.send(f"✅ ZZZ KB actualizada: **{count}** chunks indexados.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @zzz_group.command(name="search", description="Buscar en la KB de ZZZ (debug)")
    @app_commands.describe(query="Término de búsqueda")
    async def zzz_search(self, interaction: discord.Interaction, query: str):
        results = zzz_query(query, top_k=3)
        if not results:
            await interaction.response.send_message("Sin resultados.", ephemeral=True)
            return
        text = "\n\n".join(f"```\n{r[:500]}\n```" for r in results)
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @zzz_group.command(name="status", description="Ver estado de la KB de ZZZ")
    async def zzz_status(self, interaction: discord.Interaction):
        n = len(_zzz_bm25.docs) if _zzz_ready else 0
        agents = len(_zzz_agent_names)
        await interaction.response.send_message(
            f"ZZZ RAG: {'🟢 activo' if _zzz_ready else '🔴 no cargado'} | {n} chunks | {agents} agentes",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ZZZRag(bot))
