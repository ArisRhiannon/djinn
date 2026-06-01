"""Tests for utils/metrics.py."""

from __future__ import annotations

import pytest

from utils import metrics


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset_all()
    yield
    metrics.reset_all()


class TestCounters:

    def test_inc_default(self):
        metrics.counter("foo").inc()
        c = metrics.counter("foo")
        assert c.value == 1

    def test_inc_by(self):
        metrics.counter("bar").inc(by=5)
        metrics.counter("bar").inc(by=3)
        assert metrics.counter("bar").value == 8

    def test_labels_create_separate_counters(self):
        metrics.counter("calls", endpoint="/a").inc()
        metrics.counter("calls", endpoint="/a").inc()
        metrics.counter("calls", endpoint="/b").inc()
        a = metrics.counter("calls", endpoint="/a")
        b = metrics.counter("calls", endpoint="/b")
        assert a.value == 2
        assert b.value == 1

    def test_singleton_per_label_set(self):
        c1 = metrics.counter("xyz", k="v")
        c2 = metrics.counter("xyz", k="v")
        assert c1 is c2


class TestTimer:

    def test_observes_samples(self):
        metrics.timer("lat").observe(100.0)
        metrics.timer("lat").observe(200.0)
        snap = metrics.timer("lat").snapshot()
        assert snap["count"] == 2
        assert snap["min_ms"] == 100.0
        assert snap["max_ms"] == 200.0
        assert snap["avg_ms"] == 150.0

    def test_percentiles_with_few_samples(self):
        metrics.timer("p").observe(50)
        snap = metrics.timer("p").snapshot()
        assert snap["count"] == 1
        assert snap["p50_ms"] == 50

    def test_percentiles_with_many_samples(self):
        for v in range(1, 201):
            metrics.timer("range").observe(float(v))
        snap = metrics.timer("range").snapshot()
        assert snap["count"] == 200
        # p50 debería estar cerca de 100, p95 cerca de 190, p99 cerca de 198
        assert 90 <= snap["p50_ms"] <= 110
        assert 180 <= snap["p95_ms"] <= 200
        assert 195 <= snap["p99_ms"] <= 200


class TestSnapshot:

    def test_snapshot_structure(self):
        metrics.counter("a").inc()
        metrics.counter("b", x="y").inc()
        metrics.timer("t").observe(50)
        snap = metrics.snapshot()
        assert "started_at" in snap
        assert "uptime_s" in snap
        assert isinstance(snap["counters"], list)
        assert isinstance(snap["timers"], list)
        assert isinstance(snap["circuit_breakers"], list)
        names = {c["name"] for c in snap["counters"]}
        assert {"a", "b"}.issubset(names)
