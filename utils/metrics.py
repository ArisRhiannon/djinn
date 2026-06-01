"""
utils/metrics.py — Contadores de métricas en memoria, thread-safe.

Wave 9 (F5.3, 2026-05-15): observabilidad estructurada simple. No depende de
Prometheus — solo dict de contadores con timestamps y snapshot serializable
para el endpoint `/api/v1/metrics_x` del API server.

API:
    counter("messages_processed").inc()
    counter("tools_executed", tool="ban_user").inc()
    counter("llm_failures", provider="google-genai").inc(by=2)
    timer("llm_latency_ms").observe(354)

    snapshot()  -> dict con todos los contadores y timers en formato JSON.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Iterable


_LOCK = RLock()
_COUNTERS: dict[tuple, "_Counter"] = {}
_TIMERS: dict[str, "_Timer"] = {}
_STARTED_AT = time.time()


def _key(name: str, **labels) -> tuple:
    return (name,) + tuple(sorted(labels.items()))


@dataclass
class _Counter:
    name: str
    labels: dict
    value: int = 0
    last_inc_at: float = 0.0

    def inc(self, by: int = 1) -> int:
        with _LOCK:
            self.value += by
            self.last_inc_at = time.time()
            return self.value


@dataclass
class _Timer:
    name: str
    samples: deque = field(default_factory=lambda: deque(maxlen=500))
    sum_ms: float = 0.0
    count: int = 0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    def observe(self, ms: float) -> None:
        with _LOCK:
            self.samples.append(ms)
            self.sum_ms += ms
            self.count += 1
            if ms < self.min_ms:
                self.min_ms = ms
            if ms > self.max_ms:
                self.max_ms = ms

    def snapshot(self) -> dict:
        with _LOCK:
            if self.count == 0:
                return {"name": self.name, "count": 0}
            avg = self.sum_ms / self.count
            sorted_s = sorted(self.samples)
            n = len(sorted_s)
            p50 = sorted_s[n // 2]
            p95 = sorted_s[int(n * 0.95)] if n >= 20 else sorted_s[-1]
            p99 = sorted_s[int(n * 0.99)] if n >= 100 else sorted_s[-1]
            return {
                "name": self.name,
                "count": self.count,
                "avg_ms": round(avg, 2),
                "min_ms": round(self.min_ms, 2),
                "max_ms": round(self.max_ms, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
            }


def counter(name: str, **labels) -> _Counter:
    """Devuelve (creando si no existe) un contador con labels opcionales."""
    k = _key(name, **labels)
    with _LOCK:
        c = _COUNTERS.get(k)
        if c is None:
            c = _Counter(name=name, labels=labels)
            _COUNTERS[k] = c
        return c


def timer(name: str) -> _Timer:
    """Devuelve (creando si no existe) un timer."""
    with _LOCK:
        t = _TIMERS.get(name)
        if t is None:
            t = _Timer(name=name)
            _TIMERS[name] = t
        return t


def snapshot() -> dict:
    """Snapshot serializable de todos los contadores + timers + breakers."""
    # Import diferido para evitar ciclo si circuit_breaker importa metrics en el futuro.
    try:
        from utils.circuit_breaker import all_breakers_snapshot
        breakers = all_breakers_snapshot()
    except Exception:
        breakers = []

    with _LOCK:
        counters_out: list[dict] = []
        # Agrupar por nombre para una salida más legible
        by_name: dict[str, list[dict]] = defaultdict(list)
        for c in _COUNTERS.values():
            by_name[c.name].append({
                "labels": c.labels,
                "value": c.value,
                "last_inc_at": c.last_inc_at,
            })
        for n, entries in by_name.items():
            counters_out.append({"name": n, "entries": entries})

        timers_out = [t.snapshot() for t in _TIMERS.values()]

        return {
            "started_at": _STARTED_AT,
            "uptime_s": time.time() - _STARTED_AT,
            "counters": counters_out,
            "timers": timers_out,
            "circuit_breakers": breakers,
        }


def reset_all() -> None:
    """Reset completo (para tests / admin)."""
    with _LOCK:
        _COUNTERS.clear()
        _TIMERS.clear()
