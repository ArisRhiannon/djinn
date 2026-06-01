"""Constantes y utilidades puras del ToolExecutor.

Movidas del monolito utils/discord_tools.py el 2026-05-16 (fase 3 del refactor).
Contiene constantes de configuración (timeouts, límites, sets) y una función
pura (_fix_json) que se importan desde discord_tools.py para preservar el
namespace original.

NO mover aquí cosas que tengan side-effects o estado mutable global. Las
funciones _dashboard_record(), _memory_record() y la variable
_TEMPLATE_ENGINE_CACHE quedan en discord_tools.py porque su semántica
depende de su scope original (lazy import, global statement, etc.).
"""
from __future__ import annotations

import os
from typing import Dict


# ── SKILLS_DIR ──────────────────────────────────────────────────
SKILLS_DIR: str = os.environ.get("FAIRY_SKILLS_DIR", "./skills")

# ── _PERM_CONCURRENCY ───────────────────────────────────────────
_PERM_CONCURRENCY = 10

# ── _DEFAULT_TOOL_TIMEOUT ───────────────────────────────────────
_DEFAULT_TOOL_TIMEOUT = 60

# ── _TOOL_TIMEOUTS ──────────────────────────────────────────────
_TOOL_TIMEOUTS: Dict[str, int] = {
    "web_fetch": 45, "analyze_social_graph": 90, "find_communities": 90,
    "investigate_topic": 60, "bulk_assign_role_all": 300, "backup_server": 120,
    "broadcast": 120, "render_template": 30,
    "detect_coordinated_activity": 90,
}

# ── _fix_json ───────────────────────────────────────────────────
def _fix_json(raw: str) -> str:
    """
    Repara JSON malformado generado por LLMs usando json_repair.
    Maneja: trailing commas, comillas simples, comentarios, markdown fences,
    strings truncados, keys sin comillas, brackets desbalanceados,
    Python literals (True/False/None), doble comas, y más.
    """
    from json_repair import repair_json
    return repair_json(raw)


# ── _DB_REQUIRED_TOOLS ──────────────────────────────────────────
_DB_REQUIRED_TOOLS: frozenset[str] = frozenset({
    "warn_user", "get_warnings", "clear_warnings", "get_infractions_summary",
    "watch_user", "unwatch_user", "list_watched_users", "case_note", "get_case_notes",
    "antiraid_scan", "search_messages", "get_server_activity", "get_user_card",
    "get_channel_summary", "get_leaderboard", "find_inactive_members",
    "compare_user_activity", "get_peak_hours", "get_user_by_name", "batch_user_lookup",
    "search_messages_semantic", "aggregate_messages", "paginate_messages",
    "get_user_timeline", "query_pattern_analysis", "investigate_topic",
    "analyze_social_graph", "find_communities", "trace_influence_path",
    "detect_coordinated_activity", "correlate_user_behavior", "run_anomaly_scan",
    "server_dashboard", "filter_members", "detect_newcomers",
    "create_listener", "list_listeners", "toggle_listener", "delete_listener",
    "edit_listener", "test_listener", "get_listener_stats",
    "seal_user", "unseal_user", "create_reaction_role",
})

# ── _MOD_TOOLS ──────────────────────────────────────────────────
_MOD_TOOLS = frozenset(["ban_user", "kick_user", "mute_user", "unmute_user", "warn_user", "unban_user", "mass_timeout"])

