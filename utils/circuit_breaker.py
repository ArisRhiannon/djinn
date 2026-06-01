"""
utils/circuit_breaker.py — Circuit breaker simple para providers LLM y otros
servicios externos.

Wave 9 (F1.3, 2026-05-15): cuando un provider LLM falla N veces seguidas en
una ventana de tiempo, lo marcamos `unhealthy` durante un cooldown. Tras el
cooldown se reabre en estado `half_open`: la próxima llamada decide si
volvemos a `closed` (todo bien) o a `open` (sigue caído).

Uso (sin tocar llm_client.py):

    from utils.circuit_breaker import get_breaker

    breaker = get_breaker("google-genai", failure_threshold=5, window_s=300, cooldown_s=600)
    if not breaker.allow():
        # provider está abierto, hacer fallback
        ...
    try:
        result = await call_provider(...)
        breaker.record_success()
    except Exception as exc:
        breaker.record_failure(exc)
        raise

Variable de entorno:
    FAIRY_CIRCUIT_BREAKER_DISABLED=1   → todos los breakers permiten siempre.
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Optional

from loguru import logger


_BREAKERS: dict[str, "CircuitBreaker"] = {}
_REGISTRY_LOCK = RLock()


@dataclass
class CircuitBreaker:
    """Circuit breaker thread-safe en memoria."""

    name: str
    failure_threshold: int = 5
    window_s: float = 300.0      # ventana para contar fallos
    cooldown_s: float = 600.0    # cuánto tiempo permanece OPEN antes de half-open
    _failures: deque = field(default_factory=lambda: deque(maxlen=256))
    _state: str = "closed"        # "closed" | "open" | "half_open"
    _opened_at: Optional[float] = None
    _half_open_inflight: bool = False
    _lock: RLock = field(default_factory=RLock)

    @property
    def state(self) -> str:
        return self._state

    def _disabled(self) -> bool:
        return os.environ.get("FAIRY_CIRCUIT_BREAKER_DISABLED", "0") == "1"

    def allow(self) -> bool:
        """¿Se permite hacer la llamada al servicio? Llamar antes de cada request."""
        if self._disabled():
            return True
        with self._lock:
            now = time.monotonic()
            if self._state == "closed":
                return True
            if self._state == "open":
                if self._opened_at is not None and now - self._opened_at >= self.cooldown_s:
                    # transición a half-open
                    self._state = "half_open"
                    self._half_open_inflight = False
                    logger.info("circuit_breaker[{}]: open → half_open (cooldown agotado)", self.name)
                else:
                    return False
            if self._state == "half_open":
                if self._half_open_inflight:
                    return False  # ya hay una llamada de prueba en vuelo
                self._half_open_inflight = True
                return True
            return True

    def record_success(self) -> None:
        if self._disabled():
            return
        with self._lock:
            if self._state in ("half_open", "open"):
                logger.info("circuit_breaker[{}]: {} → closed (success)", self.name, self._state)
                self._state = "closed"
                self._opened_at = None
            self._half_open_inflight = False
            self._failures.clear()

    def record_failure(self, exc: BaseException | None = None) -> None:
        if self._disabled():
            return
        with self._lock:
            now = time.monotonic()
            self._failures.append(now)
            self._half_open_inflight = False

            # Eliminar fallos fuera de la ventana
            cutoff = now - self.window_s
            while self._failures and self._failures[0] < cutoff:
                self._failures.popleft()

            if self._state == "half_open":
                # Falló el probe → volver a open con nuevo cooldown
                self._opened_at = now
                self._state = "open"
                logger.warning(
                    "circuit_breaker[{}]: half_open → open (probe falló: {})",
                    self.name, exc and str(exc)[:120],
                )
                return

            if len(self._failures) >= self.failure_threshold and self._state == "closed":
                self._state = "open"
                self._opened_at = now
                logger.warning(
                    "circuit_breaker[{}]: closed → open ({} fallos en {}s, último: {})",
                    self.name, len(self._failures), int(self.window_s),
                    exc and str(exc)[:120],
                )

    def snapshot(self) -> dict:
        """Estado serializable para métricas."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failure_count_window": len(self._failures),
                "failure_threshold": self.failure_threshold,
                "window_s": self.window_s,
                "cooldown_s": self.cooldown_s,
                "opened_at_monotonic": self._opened_at,
                "disabled": self._disabled(),
            }

    def reset(self) -> None:
        """Forzar reset manual (uso desde admin commands o tests)."""
        with self._lock:
            self._state = "closed"
            self._opened_at = None
            self._half_open_inflight = False
            self._failures.clear()
            logger.info("circuit_breaker[{}]: reset manual → closed", self.name)


def get_breaker(name: str, *,
                failure_threshold: int = 5,
                window_s: float = 300.0,
                cooldown_s: float = 600.0) -> CircuitBreaker:
    """Devuelve (creando si no existe) el breaker singleton para `name`."""
    with _REGISTRY_LOCK:
        b = _BREAKERS.get(name)
        if b is None:
            b = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                window_s=window_s,
                cooldown_s=cooldown_s,
            )
            _BREAKERS[name] = b
        return b


def all_breakers_snapshot() -> list[dict]:
    """Snapshot de todos los breakers registrados (para métricas)."""
    with _REGISTRY_LOCK:
        return [b.snapshot() for b in _BREAKERS.values()]
