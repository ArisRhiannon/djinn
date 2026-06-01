"""Tests de la lógica nueva de list_listeners (search/limit/offset/verbose).

Bug histórico (2026-05-16 06:09): el LLM llamó list_listeners 2 veces
seguidas porque la primera devolvió data truncada por _MAX_RESULT_CHARS=4000
con 23 reglas. El modelo no encontró "Atelier" y borró la regla equivocada
("rule_jopetix"). Fix: paginación + búsqueda + modo light por default.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_rule(rule_id: str, name: str, enabled: bool = True,
               trigger_type: str = "on_message") -> dict:
    return {
        "id": rule_id,
        "name": name,
        "enabled": enabled,
        "trigger": {"type": trigger_type},
        "condition": {"type": "contains_text"},
        "actions": [{"type": "react"}],
        "trigger_count": 0,
        "last_triggered": None,
    }


def _make_executor_with_rules(rules: list[dict]):
    """ToolExecutor con DB mockeado que devuelve `rules`."""
    from utils.discord_tools import ToolExecutor

    db = MagicMock()
    db.get_listeners = AsyncMock(return_value=rules)

    guild = MagicMock()
    guild.id = 12345
    channel = MagicMock()

    return ToolExecutor(guild=guild, channel=channel, db=db, bot=None)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: modo light por default (sin verbose) — solo campos esenciales
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_default_is_light_mode():
    rules = [_make_rule(f"rule_{i}", f"Regla {i}") for i in range(5)]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners()

    assert result["total"] == 5
    assert result["showing"] == 5
    # Modo light: solo rule_id + name + enabled + trigger_type
    rule = result["rules"][0]
    assert set(rule.keys()) == {"rule_id", "name", "enabled", "trigger_type"}
    # No debe tener los campos verbose
    assert "condition_type" not in rule
    assert "actions" not in rule
    assert "trigger_count" not in rule


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: verbose=True devuelve campos completos
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_verbose_returns_all_fields():
    rules = [_make_rule(f"rule_{i}", f"Regla {i}") for i in range(3)]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners(verbose=True)

    rule = result["rules"][0]
    assert "trigger" in rule
    assert "condition_type" in rule
    assert "actions" in rule
    assert "trigger_count" in rule


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: search reproduce el caso de "borra la regla de Atelier"
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_search_finds_specific_rule():
    rules = [
        _make_rule("rule_jopetix", "Jopetix · ping"),
        _make_rule("rule_xoft_cat", "Xoft · Gato"),
        _make_rule("rule_atelier_god", "Atelier es god"),  # ← lo que el user quería
        _make_rule("rule_other", "Otra cosa"),
    ]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners(search="atelier")

    # Búsqueda devuelve verbose y SIN paginar
    assert result["total"] == 1
    assert result["showing"] == 1
    assert result["rules"][0]["rule_id"] == "rule_atelier_god"
    assert result["rules"][0]["name"] == "Atelier es god"
    # Verbose: tiene los campos completos
    assert "actions" in result["rules"][0]
    # No hay 'more_available' porque devolvió todo
    assert "more_available" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: search es case-insensitive
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_search_case_insensitive():
    rules = [_make_rule("rule_xyz", "ATELIER GOD MODE")]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners(search="atelier")
    assert result["showing"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: search también encuentra por rule_id parcial
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_search_matches_rule_id():
    rules = [
        _make_rule("rule_jopetix_ping", "Cualquier nombre"),
        _make_rule("rule_other", "Atelier nombre"),
    ]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners(search="jopetix")
    assert result["showing"] == 1
    assert result["rules"][0]["rule_id"] == "rule_jopetix_ping"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: paginación con limit/offset funciona correctamente
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_pagination():
    rules = [_make_rule(f"rule_{i}", f"Regla {i}") for i in range(30)]
    executor = _make_executor_with_rules(rules)

    # Primera página: 10 reglas
    page1 = await executor._do_list_listeners(limit=10, offset=0)
    assert page1["total"] == 30
    assert page1["showing"] == 10
    assert page1["more_available"] is True
    assert "hint" in page1
    assert page1["rules"][0]["rule_id"] == "rule_0"

    # Segunda página
    page2 = await executor._do_list_listeners(limit=10, offset=10)
    assert page2["showing"] == 10
    assert page2["rules"][0]["rule_id"] == "rule_10"

    # Última página (parcial)
    page3 = await executor._do_list_listeners(limit=10, offset=20)
    assert page3["showing"] == 10
    assert page3["rules"][-1]["rule_id"] == "rule_29"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: filter='active' funciona junto con paginación
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_filter_active_with_pagination():
    rules = [
        _make_rule("rule_a", "A", enabled=True),
        _make_rule("rule_b", "B", enabled=False),
        _make_rule("rule_c", "C", enabled=True),
    ]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners(filter="active")
    assert result["total"] == 2
    assert all(r["enabled"] for r in result["rules"])


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: regresión — bug original. 25+ reglas en modo light caben sin truncar
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_listeners_light_mode_fits_in_4000_chars():
    """El modo light debe poder devolver 25 reglas sin pasar _MAX_RESULT_CHARS."""
    import json
    rules = [
        _make_rule(f"rule_xoft_cat_gif_{i:02d}", f"Xoft · Gato 🐱 v{i}", enabled=True)
        for i in range(25)
    ]
    executor = _make_executor_with_rules(rules)

    result = await executor._do_list_listeners()  # default: light, 25
    serialized = json.dumps(result, ensure_ascii=False)

    # Debería caber holgado en 4000 chars (modo light es ~80 chars/regla)
    assert len(serialized) < 4000, (
        f"Modo light pasó {len(serialized)} chars con 25 reglas — "
        f"_MAX_RESULT_CHARS=4000 lo va a truncar."
    )
    assert result["showing"] == 25
