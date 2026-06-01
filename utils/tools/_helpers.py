"""Helpers internos del ToolExecutor.

Funciones top-level que son llamadas como tales desde dentro de la clase
``ToolExecutor`` y de algún _do_<name>() handler. Extraídas del monolito
utils/discord_tools.py el 2026-05-16 (fase 2 del refactor).

Estas funciones son privadas (prefijadas con ``_``) y no deben importarse
desde otros módulos. Si alguien las necesita, está usando la API mal —
exponer un wrapper público en su lugar.
"""
from __future__ import annotations

import datetime
import re
from typing import Any, Optional

import discord


# Constantes usadas por _parse_duration (movidas de discord_tools.py
# en fase 2 del refactor, junto con la función que las consume).
_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_DURATION_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_MAX_TIMEOUT_SECONDS = 28 * 86_400  # Discord cap: 28 días


def _parse_hex_color(color_str: str, default: int = 0xA855F7) -> int:
    if not color_str:
        return default
    try:
        return int(color_str.strip().lstrip("#"), 16)
    except (ValueError, AttributeError):
        return default

def _member_avatar_url(member: discord.Member | discord.User | None) -> str | None:
    if member is None:
        return None
    asset = member.display_avatar
    return str(asset.url) if asset else None

def _safe_perm_name(name: str) -> bool:
    return name.strip() in discord.Permissions.VALID_FLAGS

def _parse_duration(duration: str) -> datetime.timedelta:
    m = _DURATION_RE.match(str(duration).strip())
    if not m:
        raise ValueError(f"Formato de duración inválido: '{duration}'. Usa ej: 10m, 2h, 1d")
    secs = min(int(m.group(1)) * _DURATION_SECONDS[m.group(2).lower()], _MAX_TIMEOUT_SECONDS)
    return datetime.timedelta(seconds=secs)

def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def _ts_to_date(ts: int | str) -> str:
    """Unix timestamp (int) o ISO string → 'YYYY-MM-DD'."""
    if isinstance(ts, str):
        return ts[:10]
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


# ── ToolExecutor ──────────────────────────────────────────────────────────────

