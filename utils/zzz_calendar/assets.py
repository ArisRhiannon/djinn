"""
ZZZ Calendar — caché de assets.

Tipos:
  agent portrait   : /images/{name}.png             (~283x307)
  agent splash     : /images/builds/{name}.png      (1656x2700, full body)
  agent icon       : /images/Iconos/{name}.png      (200x200)
  wengine          : /images/wengine/{name}.png
  element icon     : /images/elementos/{el}.png     (Hielo/Fuego/etereo/...)
  type icon        : /images/elementos/{type}.png   (Anomalo/Atacante/...)
  faction          : /images/faccion/{f}.png
  rank S/A         : /images/rangos/S.png | A.png
  agent meta       : /api/agentes/{name}/detalle    {elemento, tipo, faccion, rango}
"""
from __future__ import annotations

import asyncio
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import aiohttp

logger = logging.getLogger("youkai.zzz_calendar.assets")

API_BASE = "http://140.84.187.50:8000"
CACHE_DIR = Path("data/zzz_calendar_cache")
AGENTS_DIR = CACHE_DIR / "agents"
SPLASH_DIR = CACHE_DIR / "splash"
WENGINES_DIR = CACHE_DIR / "wengines"
META_DIR = CACHE_DIR / "meta"

for d in (AGENTS_DIR, SPLASH_DIR, WENGINES_DIR, META_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _normalize(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


# Manual aliases: user-facing → API name
_AGENT_ALIASES = {
    "ellen joe": "Ellen",
    "billy kid": "Billy",
    "starlight - billy kid": "Starlight - Billy Kid",
    "anton": "Anton",
    "ben bigger": "Ben",
    "nicole demara": "Nicole",
    "zhu yuan": "Zhu Yuan",
    "soldier 11": "Soldier 11",
    "qingyi": "Qingyi",
    "miyabi": "Miyabi",
    "hoshimi miyabi": "Miyabi",
    "promeia": "Promeia",
    "lucia elowen": "Lucia",
    "lucia": "Lucia",
    "orphie magnusson & magus": "Orphie & Magus",
    "orphie & magus": "Orphie & Magus",
    "ju fufu": "Ju Fufu",
    "nangong yu": "Nangong Yu",
    "ye shunguang": "Ye Shunguang",
    "soldier 0 - anby": "Soldier 0 - Anby",
    "astra yao": "Astra Yao",
}

_ELEMENT_FILES = {
    "hielo": "hielo", "ice": "hielo", "frost": "frost",
    "fuego": "fuego", "fire": "fuego",
    "electrico": "electrico", "electric": "electrico", "lightning": "electrico",
    "etereo": "etereo", "ether": "etereo", "ethereal": "etereo",
    "fisico": "fisico", "physical": "fisico",
    "tinta aurica": "tinta aurica", "auric ink": "tinta aurica",
}

_TYPE_FILES = {
    "atacante": "atacante", "attacker": "atacante", "attack": "atacante",
    "anomalo": "anomalo", "anomaly": "anomalo",
    "soporte": "soporte", "support": "soporte",
    "defensor": "defensor", "defense": "defensor", "defender": "defensor",
    "aturdidor": "aturdidor", "stun": "aturdidor", "stunner": "aturdidor",
    "ruptura": "ruptura", "rupture": "ruptura",
}


# ── HTTP ──────────────────────────────────────────────────────────────────

async def _get(url: str, timeout: float = 12.0) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 200:
                    return await r.read()
        return None
    except Exception as e:
        logger.debug("GET %s failed: %s", url, e)
        return None


async def _get_json(url: str, timeout: float = 10.0) -> Optional[dict]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 200:
                    return await r.json()
        return None
    except Exception:
        return None


# ── Image fetchers (return URLs for HTML, but cache to disk too) ─────────

def _to_data_url(path: Path) -> str:
    """Convierte path local a data: URL para embebido en HTML."""
    import base64, mimetypes
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


async def fetch_agent_portrait(name: str) -> Optional[Path]:
    key = _AGENT_ALIASES.get(name.lower(), name)
    safe = re.sub(r"[^\w\s&-]", "", key).strip()
    local = AGENTS_DIR / f"{safe}.png"
    if local.exists() and local.stat().st_size > 1000:
        return local
    encoded = quote(safe)
    for url in [
        f"{API_BASE}/images/{encoded}.png",
        f"{API_BASE}/images/Iconos/{encoded}.png",
    ]:
        data = await _get(url)
        if data and len(data) > 1000:
            local.write_bytes(data)
            return local
    return None


async def fetch_agent_splash(name: str) -> Optional[Path]:
    key = _AGENT_ALIASES.get(name.lower(), name)
    safe = re.sub(r"[^\w\s&-]", "", key).strip()
    local = SPLASH_DIR / f"{safe}.png"
    if local.exists() and local.stat().st_size > 5000:
        return local
    data = await _get(f"{API_BASE}/images/builds/{quote(safe)}.png", timeout=20)
    if data and len(data) > 5000:
        local.write_bytes(data)
        return local
    return None


async def fetch_wengine_image(name: str) -> Optional[Path]:
    safe = re.sub(r"[^\w\s()&-]", "", name).strip()
    local = WENGINES_DIR / f"{safe}.png"
    if local.exists() and local.stat().st_size > 1000:
        return local
    encoded = quote(safe)
    for url in [
        f"{API_BASE}/images/wengine/{encoded}.png",
        f"{API_BASE}/images/{encoded}.png",
    ]:
        data = await _get(url)
        if data and len(data) > 1000:
            local.write_bytes(data)
            return local
    listing = await _get_json(f"{API_BASE}/images/list")
    if listing:
        norm = _normalize(name)
        for f in listing.get("archivos", []):
            if f.startswith("wengine/") and norm in _normalize(f):
                data = await _get(f"{API_BASE}/images/{quote(f)}")
                if data:
                    local.write_bytes(data)
                    return local
    return None


async def fetch_element_icon(element: str) -> Optional[Path]:
    if not element:
        return None
    key = _ELEMENT_FILES.get(element.lower().strip(), element.lower().strip())
    local = META_DIR / f"el_{_normalize(key)}.png"
    if local.exists() and local.stat().st_size > 200:
        return local
    data = await _get(f"{API_BASE}/images/elementos/{quote(key)}.png")
    if data:
        local.write_bytes(data)
        return local
    return None


async def fetch_type_icon(agent_type: str) -> Optional[Path]:
    if not agent_type:
        return None
    key = _TYPE_FILES.get(agent_type.lower().strip(), agent_type.lower().strip())
    local = META_DIR / f"ty_{_normalize(key)}.png"
    if local.exists() and local.stat().st_size > 200:
        return local
    data = await _get(f"{API_BASE}/images/elementos/{quote(key)}.png")
    if data:
        local.write_bytes(data)
        return local
    return None


async def fetch_faction_icon(faction: str) -> Optional[Path]:
    if not faction:
        return None
    safe = faction.lower().strip()
    local = META_DIR / f"fac_{_normalize(safe)}.png"
    if local.exists() and local.stat().st_size > 200:
        return local
    data = await _get(f"{API_BASE}/images/faccion/{quote(safe)}.png")
    if data:
        local.write_bytes(data)
        return local
    return None


async def fetch_rank_badge(rank: str) -> Optional[Path]:
    rank = (rank or "S").upper()
    if rank not in ("S", "A"):
        return None
    local = META_DIR / f"rank_{rank}.png"
    if local.exists() and local.stat().st_size > 200:
        return local
    data = await _get(f"{API_BASE}/images/rangos/{rank}.png")
    if data:
        local.write_bytes(data)
        return local
    return None


async def fetch_agent_meta(name: str) -> dict:
    """Devuelve {element, type, faction, rank}."""
    key = _AGENT_ALIASES.get(name.lower(), name)
    data = await _get_json(f"{API_BASE}/api/agentes/{quote(key)}/detalle")
    if not data:
        return {}
    return {
        "element": data.get("elemento", ""),
        "type": data.get("tipo", ""),
        "faction": data.get("faccion", ""),
        "rank": data.get("rango", "S"),
    }


# ── Bulk prefetch — returns dict of asset_key → data_url for HTML ────────

async def prefetch_calendar_assets(calendar) -> tuple[dict[str, str], dict[str, dict]]:
    """
    Pre-descarga TODO. Devuelve:
      data_urls: dict[str, str]   — keys: "agent:Name", "splash:Name",
                                          "wengine:Name", "element:Name",
                                          "type:Name", "faction:Name",
                                          "rank:S", "rank:A"
                                    values: data:image/png;base64,...
      meta:      dict[str, dict]  — "Name" → {element, type, faction, rank}
    """
    data_urls: dict[str, str] = {}
    meta: dict[str, dict] = {}
    paths: dict[str, Path] = {}
    sem = asyncio.Semaphore(8)

    main_agents: set[str] = set()
    side_agents: set[str] = set()
    wengines: set[str] = set()

    for b in calendar.exclusive_channels:
        main_agents.add(b.main)
        side_agents.update(b.side)
    for b in calendar.wengine_channels:
        wengines.add(b.main)
        wengines.update(b.side)
    all_agents = main_agents | side_agents

    # Phase 1: meta de los principales
    async def _meta(name: str) -> None:
        async with sem:
            m = await fetch_agent_meta(name)
            if m:
                meta[name] = m

    await asyncio.gather(*(_meta(n) for n in main_agents),
                         return_exceptions=True)

    # Phase 2: imágenes
    async def _portrait(name: str) -> None:
        async with sem:
            p = await fetch_agent_portrait(name)
            if p: paths[f"agent:{name}"] = p

    async def _splash(name: str) -> None:
        async with sem:
            p = await fetch_agent_splash(name)
            if p: paths[f"splash:{name}"] = p

    async def _wengine(name: str) -> None:
        async with sem:
            p = await fetch_wengine_image(name)
            if p: paths[f"wengine:{name}"] = p

    async def _meta_imgs(name: str) -> None:
        m = meta.get(name)
        if not m: return
        async with sem:
            ep = await fetch_element_icon(m.get("element", ""))
            if ep: paths[f"element:{name}"] = ep
            tp = await fetch_type_icon(m.get("type", ""))
            if tp: paths[f"type:{name}"] = tp
            fp = await fetch_faction_icon(m.get("faction", ""))
            if fp: paths[f"faction:{name}"] = fp

    async def _rank(r: str) -> None:
        async with sem:
            p = await fetch_rank_badge(r)
            if p: paths[f"rank:{r}"] = p

    tasks = []
    tasks += [_portrait(n) for n in all_agents]
    tasks += [_splash(n) for n in main_agents]
    tasks += [_wengine(n) for n in wengines]
    tasks += [_meta_imgs(n) for n in main_agents]
    tasks += [_rank(r) for r in ("S", "A")]

    await asyncio.gather(*tasks, return_exceptions=True)

    # Add UI assets (logo, background) — these are local files
    from pathlib import Path as _Path
    ui_dir = _Path("data/zzz_calendar_cache/ui")
    for name in ["zzz_logo.png", "splash_v28.png"]:
        p = ui_dir / name
        if p.exists() and p.stat().st_size > 500:
            key = f"ui:{name.replace('.png', '')}"
            paths[key] = p

    # Convert to data URLs for HTML embedding
    for k, p in paths.items():
        if p and p.exists():
            data_urls[k] = _to_data_url(p)

    logger.info(
        "ZZZ assets: %d agents, %d wengines, %d total → %d data URLs",
        len(all_agents), len(wengines), len(paths), len(data_urls),
    )
    return data_urls, meta


__all__ = [
    "fetch_agent_portrait", "fetch_agent_splash",
    "fetch_wengine_image", "fetch_element_icon", "fetch_type_icon",
    "fetch_faction_icon", "fetch_rank_badge", "fetch_agent_meta",
    "prefetch_calendar_assets", "_to_data_url",
]
