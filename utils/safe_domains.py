"""
utils/safe_domains.py — Loader lazy para la lista de dominios seguros.

Wave 6 (F4.1, 2026-05-15): la lista de ~10,000 dominios estaba en
`cogs/safe_domains.py` (166 KB de literales Python que nadie importaba).
Movida a `data/safe_domains.json` y este módulo provee acceso O(1).

API pública:
    is_safe_domain(domain) -> bool
    safe_domains() -> frozenset[str]
    reload_safe_domains() -> int   # devuelve count tras recargar
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from loguru import logger

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "safe_domains.json"


def _load_from_disk() -> frozenset[str]:
    if not _DATA_PATH.exists():
        logger.warning("safe_domains: {} no existe — devolviendo set vacío", _DATA_PATH)
        return frozenset()
    try:
        with _DATA_PATH.open(encoding="utf-8") as fp:
            payload = json.load(fp)
        domains = payload.get("domains") or []
        return frozenset(str(d).lower().strip() for d in domains if d)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.error("safe_domains: error cargando {}: {}", _DATA_PATH, exc)
        return frozenset()


@lru_cache(maxsize=1)
def safe_domains() -> frozenset[str]:
    """Devuelve el frozenset de dominios seguros (cacheado tras la primera llamada)."""
    s = _load_from_disk()
    logger.debug("safe_domains: cargados {} dominios desde disco", len(s))
    return s


def is_safe_domain(domain: str) -> bool:
    """¿Está ``domain`` (host normalizado) en la lista de dominios seguros?"""
    if not domain:
        return False
    d = domain.lower().strip().rstrip(".")
    if not d:
        return False
    s = safe_domains()
    if d in s:
        return True
    # Compatibilidad: cubrir subdominios (e.g. "cdn.example.com" matchea "example.com")
    parts = d.split(".")
    for i in range(1, len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in s:
            return True
    return False


def reload_safe_domains() -> int:
    """Limpia el caché y fuerza recarga desde disco. Devuelve el count actualizado."""
    safe_domains.cache_clear()
    return len(safe_domains())
