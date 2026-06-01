"""Tests for utils/circuit_breaker.py."""

from __future__ import annotations

import time

import pytest

from utils.circuit_breaker import CircuitBreaker, get_breaker, all_breakers_snapshot


class TestCircuitBreaker:

    def test_starts_closed(self, env_clean):
        b = CircuitBreaker(name="t1", failure_threshold=3, window_s=60, cooldown_s=10)
        assert b.state == "closed"
        assert b.allow() is True

    def test_opens_after_threshold(self, env_clean):
        b = CircuitBreaker(name="t2", failure_threshold=3, window_s=60, cooldown_s=10)
        for _ in range(3):
            b.record_failure(Exception("sim"))
        assert b.state == "open"
        assert b.allow() is False

    def test_partial_failures_dont_open(self, env_clean):
        b = CircuitBreaker(name="t3", failure_threshold=5, window_s=60, cooldown_s=10)
        for _ in range(4):
            b.record_failure()
        assert b.state == "closed"
        assert b.allow() is True

    def test_success_resets_after_open(self, env_clean):
        b = CircuitBreaker(name="t4", failure_threshold=2, window_s=60, cooldown_s=10)
        for _ in range(2):
            b.record_failure()
        assert b.state == "open"
        # Forzamos half_open simulando paso de tiempo (cooldown=0 para test)
        b.cooldown_s = 0  # type: ignore[assignment]
        assert b.allow() is True   # promueve a half_open
        b.record_success()
        assert b.state == "closed"
        assert b.allow() is True

    def test_half_open_failure_returns_open(self, env_clean):
        b = CircuitBreaker(name="t5", failure_threshold=2, window_s=60, cooldown_s=0)
        b.record_failure()
        b.record_failure()
        assert b.state == "open"
        assert b.allow() is True   # cooldown=0 → pasa a half_open inmediatamente
        b.record_failure(Exception("probe-failed"))
        assert b.state == "open"

    def test_disable_via_env(self, monkeypatch):
        monkeypatch.setenv("FAIRY_CIRCUIT_BREAKER_DISABLED", "1")
        b = CircuitBreaker(name="t6", failure_threshold=1, window_s=60, cooldown_s=60)
        b.record_failure()
        # A pesar del fallo, allow() devuelve True por la flag
        assert b.allow() is True

    def test_reset(self, env_clean):
        b = CircuitBreaker(name="t7", failure_threshold=2, window_s=60, cooldown_s=60)
        b.record_failure()
        b.record_failure()
        assert b.state == "open"
        b.reset()
        assert b.state == "closed"
        assert b.allow() is True

    def test_window_expires_old_failures(self, env_clean):
        b = CircuitBreaker(name="t8", failure_threshold=3, window_s=0.05, cooldown_s=60)
        b.record_failure()
        b.record_failure()
        time.sleep(0.1)  # esperar a que la ventana expire
        b.record_failure()  # esto purga las viejas
        assert b.state == "closed", "fallos antiguos deberían haber expirado"

    def test_snapshot_structure(self, env_clean):
        b = CircuitBreaker(name="t9", failure_threshold=3, window_s=60, cooldown_s=10)
        s = b.snapshot()
        assert s["name"] == "t9"
        assert s["state"] == "closed"
        assert s["failure_threshold"] == 3
        assert "disabled" in s


class TestRegistry:

    def test_get_breaker_returns_singleton(self, env_clean):
        a = get_breaker("singleton-test", failure_threshold=5)
        b = get_breaker("singleton-test", failure_threshold=99)  # mismo name
        assert a is b
        # parámetros del primero ganan
        assert a.failure_threshold == 5

    def test_all_breakers_includes_registered(self, env_clean):
        get_breaker("registry-test-1")
        get_breaker("registry-test-2")
        names = {s["name"] for s in all_breakers_snapshot()}
        assert "registry-test-1" in names
        assert "registry-test-2" in names
