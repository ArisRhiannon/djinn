"""
utils/http_session.py — Cliente HTTP compartido para tools/cogs que hacen
múltiples requests.

Wave 3 (F2.1, 2026-05-15): infraestructura para migrar gradualmente los
handlers de `discord_tools.py` que crean una `aiohttp.ClientSession` por
request. No se migra ningún handler en esta wave (el ToolExecutor es
ephemeral por mensaje, así que la mejora real requiere mover el scope a
nivel `bot` — ver sección "TODO scope-bot" abajo).

Uso (cuando algún caller lo necesite):

    from utils.http_session import shared_session, close_shared_session

    async def my_handler(...):
        sess = await shared_session()
        async with sess.get(url, timeout=10) as r:
            data = await r.text()

    async def shutdown():
        await close_shared_session()

Características:
  • TCPConnector con limit=20, limit_per_host=5 (evita saturar dns/sockets).
  • User-Agent estándar del bot.
  • Timeout default 10s aplicado a la sesión.
  • Lazy init (no se crea hasta la primera llamada).
  • Thread-safe (usa asyncio.Lock).

TODO scope-bot:
  Para que la sesión sea verdaderamente compartida entre todos los
  ToolExecutor (que se crean por mensaje), el ciclo de vida ideal es a
  nivel `bot`:
    - bot.session = await shared_session()  en setup_hook()
    - await close_shared_session()          en close()
  Esta migración requiere tocar main.py y los callers — diferida.
"""

from __future__ import annotations

import asyncio
from typing import Optional

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    _AIOHTTP_AVAILABLE = False

from loguru import logger


_DEFAULT_TIMEOUT = 10.0
_USER_AGENT = "YoukaiBot/1.0 (Discord bot, youkai)"

_session: "Optional[aiohttp.ClientSession]" = None
_lock: asyncio.Lock = asyncio.Lock()


async def shared_session():
    """Devuelve la `aiohttp.ClientSession` compartida (creándola lazy).

    Raises:
        RuntimeError: si aiohttp no está instalado.
    """
    global _session
    if not _AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp no está instalado. `pip install aiohttp`.")

    if _session is not None and not _session.closed:
        return _session

    async with _lock:
        # Doble check tras adquirir el lock
        if _session is not None and not _session.closed:
            return _session

        connector = aiohttp.TCPConnector(limit=20, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=_DEFAULT_TIMEOUT)
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
        )
        logger.debug("http_session: sesión compartida creada (limit=20, per_host=5)")
        return _session


async def close_shared_session() -> None:
    """Cierra la sesión compartida si existe. Llamar en bot shutdown."""
    global _session
    async with _lock:
        if _session is not None and not _session.closed:
            try:
                await _session.close()
                logger.debug("http_session: sesión compartida cerrada")
            except Exception as exc:  # noqa: BLE001
                logger.warning("http_session: error cerrando sesión: {}", exc)
        _session = None


def is_initialized() -> bool:
    """¿Hay una sesión compartida activa? Útil para diagnóstico."""
    return _session is not None and not _session.closed
