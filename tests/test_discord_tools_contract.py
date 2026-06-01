"""Regression test: el refactor del 2026-05-16 movió las declarations a un
módulo separado. Este test asegura que el contrato público del módulo
``utils.discord_tools`` no cambie sin que pasemos por aquí.

Si añadís una tool nueva o borrás una, actualizá los conteos esperados.
Si cambiás la firma de un método de ``ToolExecutor`` (por ejemplo, renombrar
un kwarg), actualizá la firma esperada o documentá el cambio.

Si querés ver un diff entre lo que cambió, mirá ``deprecated/utils_old/
discord_tools_monolith.py`` que es la versión pre-refactor congelada.
"""
from __future__ import annotations

import inspect

import pytest


def test_module_imports_clean():
    """Los símbolos públicos siguen disponibles desde el path histórico."""
    from utils.discord_tools import (
        ToolExecutor, TOOL_DECLARATIONS, YOUKAI_TOOL, FORBIDDEN,
    )
    # También deben estar disponibles los helpers del módulo separado
    from utils.tools._declarations import _str, _int, _bool, _decl
    assert callable(_str) and callable(_int) and callable(_bool)
    assert callable(_decl)
    assert ToolExecutor is not None
    assert TOOL_DECLARATIONS is not None
    assert YOUKAI_TOOL is not None
    assert FORBIDDEN is not None


def test_tool_declarations_count():
    """Conteo congelado. Si añadís tools, actualizá este número."""
    from utils.discord_tools import TOOL_DECLARATIONS
    # 128 originales + 5 loans + 4 treasury + 4 knowledge + 2 birthdays + 5 shop + 6 utilidades = 158
    assert len(TOOL_DECLARATIONS) == 158, (
        f"TOOL_DECLARATIONS tiene {len(TOOL_DECLARATIONS)} entries, "
        "esperaba 158. Si añadiste/borraste tools, actualizá este test."
    )


def test_youkai_tool_matches_declarations():
    """YOUKAI_TOOL envuelve TOOL_DECLARATIONS — los nombres y la cantidad
    deben coincidir exactamente (la lib de Google copia la lista internamente,
    así que `is` no aplica; pero los contenidos sí deben matchear)."""
    from utils.discord_tools import YOUKAI_TOOL, TOOL_DECLARATIONS
    assert len(YOUKAI_TOOL.function_declarations) == len(TOOL_DECLARATIONS)
    yt_names = [d.name for d in YOUKAI_TOOL.function_declarations]
    td_names = [d.name for d in TOOL_DECLARATIONS]
    assert yt_names == td_names


def test_decl_names_unique():
    """Cada tool debe tener un nombre único — sin duplicados."""
    from utils.discord_tools import TOOL_DECLARATIONS
    names = [d.name for d in TOOL_DECLARATIONS]
    assert len(names) == len(set(names)), (
        f"Hay tools duplicadas: {[n for n in names if names.count(n) > 1]}"
    )


def test_decl_names_match_handlers():
    """Cada declaration debe tener un handler _do_<name> en ToolExecutor, y viceversa.

    Esto previene declarar una tool sin implementarla, o tener handlers muertos sin declarar.
    """
    from utils.discord_tools import TOOL_DECLARATIONS, ToolExecutor
    decl_names = {d.name for d in TOOL_DECLARATIONS}
    handler_names = {
        m[4:] for m in dir(ToolExecutor)
        if m.startswith('_do_') and callable(getattr(ToolExecutor, m, None))
    }
    missing_handlers = decl_names - handler_names
    assert not missing_handlers, (
        f"Tools declaradas SIN handler _do_<name>(): {sorted(missing_handlers)}"
    )
    missing_decls = handler_names - decl_names
    assert not missing_decls, (
        f"Handlers _do_<name>() implementados SIN estar declarados (código muerto): {sorted(missing_decls)}"
    )


def test_critical_tools_present():
    """Sanity: las tools críticas que el bot usa frecuentemente están vivas."""
    from utils.discord_tools import TOOL_DECLARATIONS
    names = {d.name for d in TOOL_DECLARATIONS}
    must_have = {
        # core
        "send_message", "send_embed", "get_user_by_name", "find_channel",
        "read_skill",
        # moderación (Wave 1+ críticas)
        "ban_user", "kick_user", "mute_user", "warn_user",
        # SEC-01: execute_code DEBE estar AUSENTE
        # loans (cd15e1a)
        "list_morosos", "get_user_debt", "get_loan_leaderboard",
        "get_loan_stats", "get_loan_history",
        # treasury (528dd3c)
        "get_treasury_balance", "get_treasury_history",
        "treasury_grant_credits", "treasury_deposit",
    }
    missing = must_have - names
    assert not missing, f"Tools críticas faltantes: {sorted(missing)}"


def test_execute_code_removed():
    """SEC-01 (Wave 1, 2026-05-15): execute_code fue eliminado por RCE.

    No debe volver a aparecer ni en TOOL_DECLARATIONS ni como handler.
    """
    from utils.discord_tools import TOOL_DECLARATIONS, ToolExecutor, FORBIDDEN
    decl_names = {d.name for d in TOOL_DECLARATIONS}
    assert "execute_code" not in decl_names, (
        "execute_code reintrodujo en TOOL_DECLARATIONS. "
        "Esta tool permite RCE — NO LA RESTAURES."
    )
    # FORBIDDEN debe seguir incluyéndola como defensa en profundidad
    assert "execute_code" in FORBIDDEN, (
        "execute_code debe estar en FORBIDDEN aunque ya no esté declarada"
    )
    # No debe haber handler tampoco
    assert not hasattr(ToolExecutor, "_do_execute_code")


def test_forbidden_includes_destructive():
    """FORBIDDEN bloquea tools destructivas que no queremos que el LLM use."""
    from utils.discord_tools import FORBIDDEN
    # Sample: estas son destructivas y no las queremos como tools llamables
    must_be_forbidden = {
        "delete_channel", "mass_ban", "nuke_server",
        "delete_all_channels", "delete_all_roles",
    }
    missing = must_be_forbidden - FORBIDDEN
    assert not missing, f"Tools destructivas no están en FORBIDDEN: {missing}"


def test_tool_executor_class_signature():
    """ToolExecutor sigue siendo una clase con __init__ que acepta los kwargs
    históricos. Si rompés esto, los cogs que la instancian se caen.
    """
    from utils.discord_tools import ToolExecutor
    sig = inspect.signature(ToolExecutor.__init__)
    params = set(sig.parameters)
    must_accept = {"self", "guild", "channel", "db"}
    missing = must_accept - params
    assert not missing, f"__init__ de ToolExecutor perdió params: {missing}"


def test_no_circular_import_with_orchestrator():
    """orchestrator.py importa TOOL_DECLARATIONS y YOUKAI_TOOL — debe seguir
    funcionando tras separar las declarations.
    """
    # Si el import circular volviera, este import explota
    from utils import orchestrator  # noqa: F401
    from utils.orchestrator import _route_tools  # noqa: F401


@pytest.mark.parametrize("category", [
    "loans", "treasury", "moderation", "channels", "roles",
])
def test_routing_categories_have_valid_tools(category):
    """Las categorías del routing referencian tools que existen en TOOL_DECLARATIONS."""
    from utils.orchestrator import _TOOL_CATEGORIES
    from utils.discord_tools import TOOL_DECLARATIONS
    valid_names = {d.name for d in TOOL_DECLARATIONS}
    cat_tools = set(_TOOL_CATEGORIES.get(category, []))
    invalid = cat_tools - valid_names
    assert not invalid, (
        f"Categoría {category!r} referencia tools inexistentes: {invalid}"
    )


# ── Runtime smoke tests para los helpers (detectan refactors que rompan sin
# que los snapshots se enteren — ej: dejar constantes huérfanas en otro módulo).
def test_helper_safe_int_runtime():
    from utils.discord_tools import _safe_int
    assert _safe_int("123") == 123
    assert _safe_int(456) == 456
    assert _safe_int(None) is None
    assert _safe_int("abc") is None


def test_helper_parse_duration_runtime():
    """Bug detectado en fase 2 del refactor: si las constantes se quedan
    en otro módulo, esta función falla con NameError en runtime aunque
    los snapshots de firmas sean idénticos."""
    from utils.discord_tools import _parse_duration
    import datetime
    assert _parse_duration("5m") == datetime.timedelta(minutes=5)
    assert _parse_duration("1h") == datetime.timedelta(hours=1)
    assert _parse_duration("30s") == datetime.timedelta(seconds=30)


def test_helper_parse_hex_color_runtime():
    from utils.discord_tools import _parse_hex_color
    assert _parse_hex_color("#FF0000") == 0xFF0000
    assert _parse_hex_color("00ff00") == 0x00FF00
    # Default fallback en input inválido
    assert _parse_hex_color("not-a-color", default=0xABCDEF) == 0xABCDEF


def test_helper_safe_perm_name_runtime():
    from utils.discord_tools import _safe_perm_name
    assert _safe_perm_name("ban_members") is True
    # Algo que claramente no es perm name
    assert _safe_perm_name("--rm -rf /") is False


# ── Constantes movidas en fase 3 ──────────────────────────────────────────


def test_constants_runtime_values():
    """Las constantes movidas mantienen sus valores semánticos.

    Si alguien edita _constants.py y modifica el valor, este test salta —
    obligando a documentar el cambio en el commit.
    """
    from utils.discord_tools import (
        _PERM_CONCURRENCY, _DEFAULT_TOOL_TIMEOUT,
        _DB_REQUIRED_TOOLS, _MOD_TOOLS, SKILLS_DIR,
    )
    assert _PERM_CONCURRENCY == 10
    assert _DEFAULT_TOOL_TIMEOUT == 60
    assert isinstance(_DB_REQUIRED_TOOLS, frozenset)
    assert len(_DB_REQUIRED_TOOLS) >= 40, "_DB_REQUIRED_TOOLS encogió sospechosamente"
    assert isinstance(_MOD_TOOLS, frozenset)
    assert _MOD_TOOLS == frozenset({
        "ban_user", "kick_user", "mute_user", "unmute_user",
        "warn_user", "unban_user", "mass_timeout",
    })
    assert SKILLS_DIR  # path no vacío


def test_tool_timeouts_runtime():
    """_TOOL_TIMEOUTS contiene timeouts especiales para tools costosas."""
    from utils.discord_tools import _TOOL_TIMEOUTS
    # Tools que conocemos que tienen timeout custom
    for tool in ("web_fetch", "analyze_social_graph"):
        assert tool in _TOOL_TIMEOUTS, f"_TOOL_TIMEOUTS perdió {tool}"
        assert _TOOL_TIMEOUTS[tool] > 0


def test_fix_json_runtime():
    """_fix_json repara JSON malformado típico de LLMs."""
    from utils.discord_tools import _fix_json
    # Trailing comma
    out = _fix_json('{"a": 1,}')
    assert '"a"' in out
    # Single quotes → double
    out = _fix_json("{'name': 'Karu'}")
    assert '"name"' in out


def test_dashboard_record_no_op_safe():
    """_dashboard_record no se movió — es un wrapper con lazy import.
    Debe seguir siendo no-op si dashboard no está cargado.
    """
    from utils.discord_tools import _dashboard_record
    # No debe lanzar excepción aunque el cog dashboard no esté cargado
    _dashboard_record("test_tool", 0.5, "ok", "summary")


def test_memory_record_filters_to_mod_tools():
    """_memory_record solo registra si la tool está en _MOD_TOOLS.

    No movido — sigue en discord_tools.py — pero usa _MOD_TOOLS desde
    el namespace re-importado, así que validamos que esa cadena funciona.
    """
    from utils.discord_tools import _memory_record
    # No debe lanzar excepción para tool no-mod (early return)
    _memory_record("send_message", {}, {})
    # No debe lanzar para tool mod (intenta cargar server_memory cog,
    # que puede no estar en este contexto, pero está envuelto en try/except)
    _memory_record("ban_user", {"user_id": 123}, {"success": True})
