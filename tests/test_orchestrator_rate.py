"""A3 (review): rate limit por usuario — ventana deslizante."""

from utils.orchestrator import Orchestrator


def _orch():
    # __init__ solo asigna atributos; no llama métodos del bot/llm.
    return Orchestrator(object(), object())


def test_rate_limit_blocks_after_max():
    o = _orch()
    o._RATE_MAX = 3
    o._RATE_WINDOW = 100.0  # amplio: nada expira durante el test
    assert o._check_user_rate(1) is True
    assert o._check_user_rate(1) is True
    assert o._check_user_rate(1) is True
    assert o._check_user_rate(1) is False   # 4ª excede el límite
    assert o._check_user_rate(2) is True    # otro usuario no afectado


def test_rate_limit_disabled_when_max_zero():
    o = _orch()
    o._RATE_MAX = 0                          # 0 = desactivado (respeta el opt-out)
    for _ in range(100):
        assert o._check_user_rate(1) is True
