"""
Orchestrator — Pipeline mensaje → historial → LLM (agentic) → respuesta.

Cambio clave: _prepare_content() reemplaza _strip_mentions().
 - Elimina SOLO la mención del bot propio.
 - Resuelve <@USER_ID>, <@&ROLE_ID>, <#CHANNEL_ID> a
 "Nombre (ID: X)" para que el LLM disponga del ID numérico
 sin necesidad de pedírselo al usuario.

v2: Usa LLMClient (multi-provider) en vez de GoogleAIStudioClient directo.
"""

from __future__ import annotations

import re
import os
import logging
import time
from collections import deque
from typing import Any, Deque, List, Optional

import discord
from .orch_types import Content, Part, Tool

from .llm_client import LLMClient
from .discord_tools import DJINN_TOOL, TOOL_DECLARATIONS, ToolExecutor

logger = logging.getLogger("djinn.orchestrator")

# ── Tool Routing Dinámico ───────────────────────────────────────────────
# Categorías de tools → se envían solo las relevantes al LLM
from .orch_types import Tool as _Tool

_TOOL_CATEGORIES: dict[str, list[str]] = {
    "core": [  # siempre incluidas
        "send_message", "send_embed", "add_reaction", "get_user_by_name",
        "find_channel", "read_skill", "get_user_info",
        "create_listener", "list_listeners", "search_messages",
    ],
    "moderation": [
        "ban_user", "kick_user", "mute_user", "unmute_user", "warn_user",
        "get_warnings", "clear_warnings", "unban_user", "softban_user",
        "mass_timeout", "seal_user", "unseal_user", "antiraid_scan",
        "case_note", "get_case_notes", "get_infractions_summary",
        "list_sealed_users",
    ],
    "channels": [
        "find_channel", "list_categories", "create_channel",
        "rename_channel", "set_channel_topic", "set_slowmode",
        "lock_channel", "unlock_channel", "purge_messages",
        "create_thread", "pin_message", "bulk_channel_action",
        "get_channel_permissions", "set_channel_permissions",
    ],
    "roles": [
        "assign_role", "remove_role", "create_role", "find_role",
        "bulk_assign_role", "bulk_assign_role_all", "set_nickname",
    ],
    "search": [
        "search_messages", "search_messages_semantic", "aggregate_messages",
        "paginate_messages", "get_channel_summary", "investigate_topic",
        "get_user_timeline", "query_pattern_analysis",
        "knowledge_search", "knowledge_store", "knowledge_update", "knowledge_delete",
        "get_message_context",
    ],
    "user_content": [
        "get_user_by_name", "batch_user_lookup", "get_user_card",
        "send_user_content_to_channel", "get_user_info",
        "compare_user_activity", "filter_members",
    ],
    "visual": [
        "render_template", "send_embed",
    ],
    "server_info": [
        "server_dashboard", "get_leaderboard", "get_server_activity",
        "get_peak_hours", "find_inactive_members", "detect_newcomers",
        "get_voice_members", "list_bans", "list_events",
    ],
    "social_graph": [
        "analyze_social_graph", "find_communities", "trace_influence_path",
        "detect_coordinated_activity", "correlate_user_behavior", "run_anomaly_scan",
        "search_messages", "render_template",
    ],
    "listeners": [
        "create_listener", "list_listeners", "toggle_listener",
        "delete_listener", "edit_listener", "test_listener", "get_listener_stats",
    ],
    "scheduling": [
        "schedule_message", "cancel_scheduled_message", "create_poll",
        "send_dm", "broadcast", "create_listener",
    ],
    "web": ["web_fetch", "fetch_url_preview"],
    "curse": ["curse_user", "uncurse_user", "list_cursed_users",
              "wash_mouth", "unwash_mouth", "list_mouth_washed"],
    "loans": [
        "list_morosos", "get_user_debt", "get_loan_leaderboard",
        "get_loan_stats", "get_loan_history", "get_loan_info",
        "get_user_by_name", "send_embed",
    ],
    "treasury": [
        "get_treasury_balance", "get_treasury_history",
        "treasury_grant_credits", "treasury_deposit",
        "get_user_by_name", "send_embed",
    ],
    "shop": [
        "shop_create", "shop_list", "shop_redeem", "shop_manage",
        "economy_stats", "get_user_by_name",
    ],
}

# Keywords → categorías
_KEYWORD_MAP: dict[str, list[str]] = {
    "ban": ["moderation"], "kick": ["moderation"], "mute": ["moderation"],
    "warn": ["moderation"], "seal": ["moderation"], "sella": ["moderation"],
    "sellado": ["moderation"], "raid": ["moderation"],
    "timeout": ["moderation"], "infrac": ["moderation"],
    "libera": ["moderation"], "desella": ["moderation"], "libéralo": ["moderation"],
    "suéltalo": ["moderation"], "quita el sello": ["moderation"],
    "cállalo": ["moderation"], "silencia": ["moderation"], "mutea": ["moderation"],
    "desmutea": ["moderation"], "bótalo": ["moderation"], "échalo": ["moderation"],
    "sácalo": ["moderation"], "expulsa": ["moderation"], "banea": ["moderation"],
    "desbanea": ["moderation"], "adviértele": ["moderation"],
    "encierra": ["moderation"], "cuarentena": ["moderation"],
    "canal": ["channels"], "channel": ["channels"], "lock": ["channels"],
    "unlock": ["channels"], "slow": ["channels"], "purge": ["channels"],
    "hilo": ["channels"], "thread": ["channels"], "pin": ["channels"],
    "cierra": ["channels"], "abre": ["channels"], "borra mensajes": ["channels"],
    "limpia": ["channels"],
    "rol": ["roles"], "role": ["roles"], "nick": ["roles"], "apodo": ["roles"],
    "ponle": ["roles"], "cámbiale": ["roles"], "renombra": ["roles"],
    "busca": ["search"], "search": ["search"], "mensaj": ["search"],
    "dijo": ["search"], "habló": ["search"], "investig": ["search"],
    "escribió": ["search"], "cuándo": ["search"],
    "pfp": ["user_content"], "avatar": ["user_content"], "banner": ["user_content"],
    "foto": ["user_content"], "perfil": ["user_content", "visual"],
    "manda": ["user_content", "channels", "scheduling"], "envía": ["user_content", "channels", "scheduling"],
    "embed": ["visual"], "tierlist": ["visual"], "gráfico": ["visual"],
    "template": ["visual"], "ranking": ["visual"], "ship": ["visual"],
    "shippea": ["visual"],
    "leaderboard": ["server_info", "visual"], "stats": ["server_info"],
    "actividad": ["server_info"], "server": ["server_info"],
    "dashboard": ["server_info"], "voz": ["server_info"], "voice": ["server_info"],
    "vc": ["server_info"],
    "activo": ["server_info"], "evento": ["server_info"],
    "grafo": ["social_graph"], "red social": ["social_graph"],
    "conexion": ["social_graph"], "comunidad": ["social_graph"], "alt": ["social_graph"],
    "listener": ["listeners"], "regla": ["listeners"],
    "cuando alguien": ["listeners"], "cada vez que": ["listeners"], "si alguien": ["listeners"],
    "cada que": ["listeners"], "ping": ["listeners"],
    "notifícame": ["listeners"], "avisame": ["listeners"], "avísame": ["listeners"],
    "programa": ["scheduling"], "encuesta": ["scheduling"], "poll": ["scheduling"],
    "dm": ["scheduling"], "broadcast": ["scheduling"], "privado": ["scheduling"],
    "md": ["scheduling"],
    "web": ["web"], "url": ["web"], "link": ["web"], "página": ["web"],
    "internet": ["web"], "googl": ["web"],
    "maldici": ["curse"], "curse": ["curse"], "maldito": ["curse"],
    "lavado": ["curse"], "wash": ["curse"], "boca": ["curse"],
    "maldícelo": ["curse"], "jabón": ["curse"], "lávale": ["curse"],
    # ── deudas / préstamos / morosos ────────────────────────────────────
    "deuda": ["loans"], "deudas": ["loans"], "deudor": ["loans"],
    "deudores": ["loans"], "moroso": ["loans"], "morosos": ["loans"],
    "préstamo": ["loans"], "prestamo": ["loans"], "préstamos": ["loans"],
    "prestamos": ["loans"], "score crediticio": ["loans"],
    "crédito": ["loans"], "credito": ["loans"], "créditos": ["loans"],
    "créditos perdidos": ["loans"], "agiotista": ["loans"],
    "cuánto debe": ["loans"], "cuanto debe": ["loans"],
    "cuánto deben": ["loans"], "cuanto deben": ["loans"],
    "cuánto debo": ["loans"], "cuanto debo": ["loans"],
    "quién debe": ["loans"], "quien debe": ["loans"],
    "wall of shame": ["loans"], "tasa de interés": ["loans"],
    "blacklist": ["loans"], "default": ["loans"],
    "historial de pagos": ["loans"], "lista de morosos": ["loans"],
    "lista de deudores": ["loans"], "ránking deudor": ["loans"],
    "ranking deudor": ["loans"], "buen pagador": ["loans"],
    "mejores pagadores": ["loans"],
    # ── banco / tesorería ───────────────────────────────────────────────
    "banco": ["treasury", "loans"], "tesorería": ["treasury"],
    "tesoreria": ["treasury"], "tesoro": ["treasury"],
    "pool del banco": ["treasury"], "pool del servidor": ["treasury"],
    "saldo del banco": ["treasury"], "saldo del servidor": ["treasury"],
    "fondos": ["treasury"], "fondos del banco": ["treasury"],
    "caja": ["treasury"], "caja del servidor": ["treasury"],
    "cómo va el banco": ["treasury"], "como va el banco": ["treasury"],
    "cómo va la caja": ["treasury"], "como va la caja": ["treasury"],
    "cuánto tiene el banco": ["treasury"], "cuanto tiene el banco": ["treasury"],
    "cuánto tiene youkai": ["treasury"], "cuanto tiene youkai": ["treasury"],
    "cuánto tiene djinn": ["treasury"], "cuanto tiene djinn": ["treasury"],
    "movimientos del banco": ["treasury"], "depositar": ["treasury"],
    "entregar créditos": ["treasury"], "entregar creditos": ["treasury"],
    "regalo del banco": ["treasury"], "premio del banco": ["treasury"],
}

# ── Public pipeline: restricted tool set for non-reader users ────────────
_PUBLIC_TOOL_NAMES: set[str] = {
    # core
    "send_message", "send_embed", "add_reaction", "get_user_by_name", "find_channel",
    "read_skill",
    # data/sherlock
    "search_messages", "search_messages_semantic", "aggregate_messages",
    "get_channel_summary", "investigate_topic", "get_user_timeline",
    "query_pattern_analysis", "paginate_messages", "profile_sample", "get_message_context",
    "get_loan_info", "list_morosos", "get_user_debt",
    "get_loan_leaderboard", "get_loan_stats", "get_loan_history",
    "get_treasury_balance", "get_treasury_history",
    # web
    "web_fetch", "fetch_url_preview",
    # listeners (create only — enforced in executor)
    "create_listener", "list_listeners",
    # messaging
    "send_dm",
    # shop / economy
    "shop_list", "shop_redeem", "economy_stats",
    # knowledge
    "knowledge_search",
    # birthdays
    "get_birthdays",
    # music
    "play_music", "music_queue",
    # self-seal (public users can only seal themselves — enforced in executor)
    "seal_user",
}

# ── Detección de intención → auto-inyección de skill ─────────────────────
# Mapea patrones de intención a skills. Si matchea, se carga automáticamente.
# Cada entrada: (regex_compilado, skill_name)
# IMPORTANTE: el orden importa — primera match gana.

_SKILL_INTENT_MAP: list[tuple[re.Pattern, str]] = [
    # ── listeners (reglas automáticas — broad structural pattern) ─────
    (re.compile(
        r"(?i)(?:"
        # Explicit keywords
        r"(?:nueva|crea|añade|haz)\s+(?:una?\s+)?regla|"
        # Conditional→Action: "cuando/si/cada que [X] [acción]"
        r"(?:cuando|si|cada\s*que)\s+.{3,}?\s*(?:reacciona|responde|borra|elimina|manda|envía|"
        r"avísa|notifica|ponle|dale|redacta|reemplaza|timeout|mute|cambia|"
        r"pon(?:le|ga)|haz|ejecuta|activa)|"
        # "cada que [nombre] [verbo]" (user says action after)
        r"cada\s*que\s+\w+\s+(?:diga|escriba|mencione|haga|ponga|mande)|"
        # "haz que cuando/haz algo para que cuando"
        r"haz\s+(?:algo\s+)?(?:que|para)\s+(?:que\s+)?(?:cuando|si|cada)|"
        # "quiero/necesito/puedes que [X] cuando"
        r"(?:quiero|necesito|puedes)\s+(?:que\s+)?(?:el\s+bot\s+)?\w+\s+(?:cuando|si|cada)|"
        # "automatiza/programa/configura/monitorea/vigila"
        r"(?:automatiza|programa|configura|monitorea|vigila)|"
        # "redacta/reemplaza los mensajes de"
        r"(?:redacta|reemplaza)\s+(?:todos?\s+)?(?:los\s+)?mensajes?\s+de|"
        # "borra los mensajes que contengan"
        r"(?:borra|elimina)\s+(?:los\s+)?mensajes?\s+(?:que|de|con)|"
        # "manda [algo] todos los [día]" (scheduled)
        r"manda\s+.{3,}\s+todos\s+los|"
        # "cuando alguien entre" (join trigger)
        r"cuando\s+(?:alguien|un\s+miembro)\s+(?:entre|se\s+una)|"
        # "ponle/dale [X] cuando/si"
        r"(?:ponle|dale)\s+.{2,}?\s+(?:cuando|si|cada)"
        r")"
    ), "listeners"),

    # ── sherlock_kai (investigación profunda) ─────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"investig|quién\s+es|who\s+is|"
        r"es\s+(?:tóxico|alt|bot|sospechoso)|"
        r"qué\s+pasó|what\s+happened|"
        r"hay\s+(?:alts?|bots?|raid)|"
        r"quiénes\s+(?:interactúan|hablan\s+juntos)|"
        r"conexion|relacion\s+entre|"
        r"perfil(?:a|ar)|analiz(?:a|ar)\s+(?:a|al|el)\s+(?:usuario|user)"
        r")"
    ), "sherlock_kai"),

    # ── antiraid ──────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"raid|nuke|mass\s*join|"
        r"están\s+entrando\s+(?:muchos|bots)|"
        r"ataque|attack|"
        r"cuentas?\s+(?:nuevas?|falsas?|bots?)\s+(?:entrando|uniéndose)"
        r")"
    ), "antiraid"),

    # ── data_mastery (análisis de datos complejos) ────────────────────
    (re.compile(
        r"(?i)(?:"
        r"estadístic|stats?\s+(?:del|de)|"
        r"cuánto\s+(?:se\s+)?(?:habla|escribe|postea)|"
        r"actividad\s+(?:del|de|por)|"
        r"patrón|pattern|anomalía|"
        r"(?:más|menos)\s+activ|"
        r"leaderboard|ranking|top\s+\d+\s+(?:usuarios|users)|"
        r"gráfic(?:o|a)\s+(?:de\s+)?actividad|"
        r"horas?\s+(?:pico|peak)|"
        r"comparar?\s+(?:actividad|usuarios)"
        r")"
    ), "data_mastery"),

    # ── eventos ───────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"crea(?:r)?\s+(?:un\s+)?evento|"
        r"organiz(?:a|ar)\s+(?:un\s+)?(?:evento|torneo|sorteo)|"
        r"programa(?:r)?\s+(?:un\s+)?(?:evento|actividad)|"
        r"haz\s+(?:un\s+)?(?:evento|torneo)"
        r")"
    ), "eventos"),

    # ── embed_design ──────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"(?:haz|crea|diseña|manda)\s+(?:un\s+)?embed|"
        r"embed\s+(?:bonito|custom|personalizado)|"
        r"anuncio\s+(?:bonito|embed|con\s+formato)"
        r")"
    ), "embed_design"),

    # ── sellar ────────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"s[eé]ll(?:a|ar|ame)|a[ií]sl(?:a|ar|ame)|"
        r"pon(?:lo|la|me)?\s+en\s+(?:cuarentena|aislamiento)|"
        r"encierr(?:a|ar|ame)|"
        r"quiero\s+(?:que\s+me\s+)?sell(?:en|ar)|"
        r"auto.?sell"
        r")"
    ), "sellar"),

    # ── apodos ────────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"pon(?:le|me)?\s+(?:de\s+)?(?:apodo|nick|nombre)|"
        r"cámbia(?:le|me)?\s+(?:el\s+)?(?:apodo|nick|nombre)|"
        r"renombr(?:a|ar)|"
        r"apodo\s+(?:creativo|random|gracioso)"
        r")"
    ), "apodos"),

    # ── traduccion ────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"traduc(?:e|ir)|translat|"
        r"(?:en|al?)\s+(?:inglés|español|japonés|francés|alemán|coreano|chino|portugués)|"
        r"qué\s+(?:significa|dice)\s+(?:en|esto)"
        r")"
    ), "traduccion"),

    # ── ascii_art ─────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"ascii\s*art|arte\s*ascii|"
        r"haz(?:me)?\s+(?:un\s+)?(?:dibujo|arte)\s+(?:en\s+)?(?:texto|ascii)|"
        r"text\s*art"
        r")"
    ), "ascii_art"),

    # ── onboarding ────────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"configura(?:r)?\s+(?:el\s+)?(?:onboarding|bienvenida)|"
        r"sistema\s+de\s+(?:bienvenida|verificación|onboarding)|"
        r"auto.?(?:rol|verificación)\s+(?:al|cuando)\s+(?:entrar|unirse)"
        r")"
    ), "onboarding"),

    # ── graphics (tierlists, leaderboards, charts) ────────────────────
    (re.compile(
        r"(?i)(?:"
        r"tier\s*list|tierlist|"
        r"haz(?:me)?\s+(?:un\s+)?(?:gráfic|chart|barras|donut|radar|heatmap|pie\s*chart)|"
        r"crea\s+(?:un\s+)?(?:gráfic|chart|tierlist)|"
        r"render(?:iza|ear)?\s+(?:un\s+)?(?:template|gráfic)|"
        r"gráfic(?:o|a)\s+(?:de\s+)?(?:barras|dona|línea|líneas|radar)|"
        r"shipea|shippea|love\s+graph"
        r")"
    ), "graphics"),

    # ── deudas (préstamos, morosos, score crediticio) ─────────────────
    (re.compile(
        r"(?i)(?:"
        r"deuda|préstamo|moroso|score\s*credit|"
        r"cuánto\s+(?:me\s+)?deb|cuánto\s+le\s+deb|"
        r"quién(?:es)?\s+deb|lista\s+de\s+(?:morosos|deudores)|"
        r"historial\s+(?:de\s+)?pagos|"
        r"interés|tasa\s+(?:de\s+)?interés"
        r")"
    ), "deudas"),

    # ── banco / tesorería del servidor ────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"banco|tesorer[ií]a|tesoro|"
        r"pool\s+(?:del\s+)?(?:banco|servidor)|"
        r"saldo\s+(?:del\s+)?(?:banco|servidor)|"
        r"fondos\s+(?:del\s+)?(?:banco|servidor)|"
        r"caja\s+(?:del\s+)?servidor|"
        r"cu[áa]nto\s+tiene\s+(?:el\s+banco|youkai|djinn|la\s+caja)|"
        r"c[óo]mo\s+va\s+(?:el\s+banco|la\s+caja|el\s+pool)|"
        r"movimientos\s+del\s+banco|"
        r"depositar\s+(?:al?\s+)?banco|"
        r"entregar\s+(?:cr[eé]ditos|del\s+pool)|"
        r"premio\s+del\s+banco|regalo\s+del\s+banco"
        r")"
    ), "banco"),

    # ── obscura-web ───────────────────────────────────────────────────
    (re.compile(
        r"(?i)(?:"
        r"busc(?:a|ar)\s+(?:en\s+)?(?:internet|la\s+web|google|online)|"
        r"(?:qué|quién)\s+(?:es|fue|significa)\s+.{3,}|"
        r"información\s+(?:sobre|de)\s+.{3,}|"
        r"web\s*search|fetch\s+url"
        r")"
    ), "obscura-web"),
]

# Patrones que CANCELAN autoinyección (consultas sobre skills, no uso)
_SKILL_QUERY_CANCEL = re.compile(
    r"(?i)(?:"
    r"(?:cuáles?|qué|lista)\s+(?:de\s+)?(?:reglas|skills|listeners)|"
    r"muéstrame\s+(?:las\s+)?(?:reglas|skills)|"
    r"desactiva\s+(?:la\s+)?regla|"
    r"borra\s+(?:la\s+)?regla|"
    r"edita\s+(?:la\s+)?regla"
    r")"
)


def _detect_skill_intent(text: str) -> str | None:
    """Detecta intención y retorna nombre de skill a inyectar, o None.

    Capa 1: Regex (0ms) — patrones exactos, primera match gana.
    Solo retorna una skill (la primera que matchea).
    Para multi-skill, ver _detect_skills_semantic().
    """
    if _SKILL_QUERY_CANCEL.search(text):
        return None
    for pattern, skill_name in _SKILL_INTENT_MAP:
        if pattern.search(text):
            return skill_name
    return None


# ── Semantic Skill Router (Capa 2) ────────────────────────────────────────
# Usa embeddings con frases de ejemplo para detectar skills cuando regex falla.
# Soporta multi-skill (ej: "investiga a X y hazme un gráfico" → sherlock + tierlists)

_SKILL_EXAMPLES: dict[str, list[str]] = {
    "sherlock_kai": [
        "investiga a este usuario", "es tóxico", "quién es este tipo",
        "tiene alts", "qué pasó con", "analiza su comportamiento",
        "es sospechoso", "revisa su historial", "hay algo raro con",
        "quiénes interactúan juntos", "perfila a", "es un alt",
        "qué hizo este usuario", "es de confianza", "tiene cuentas múltiples",
        "de dónde salió este", "desde cuándo está en el server",
        "este tipo es raro", "me da mala espina", "parece bot",
        "siempre aparece con el otro", "son la misma persona",
        "revisa qué ha dicho", "analiza sus mensajes", "es troll",
    ],
    "embed_design": [
        "embed bonito", "anuncio elaborado", "diseña un embed",
        "embed con campos", "mensaje rico", "formato bonito",
        "embed para anunciar", "haz un anuncio", "embed personalizado",
        "manda un anuncio bonito", "haz un mensaje con formato",
        "quiero un embed con colores", "anuncio para el server",
        "diseña algo bonito para anunciar", "embed con imagen",
    ],
    "listeners": [
        "crea una regla", "cuando alguien diga", "cada que", "si alguien",
        "avísame cuando", "notifícame si", "regla automática", "listener",
        "reacciona cuando", "responde cuando alguien", "cada vez que alguien",
        "automatiza", "trigger cuando", "regla que detecte",
        "nueva regla", "añade una regla", "haz que cuando",
        "quiero que reacciones cuando", "manda dm cuando alguien",
        "responde automáticamente si", "ponle una regla a",
        "cada que alguien haga ping", "cuando mencionen a",
        "si alguien dice esto reacciona", "regla para que",
        "mándale un mensaje cuando", "avisa si alguien menciona",
        "redacta los mensajes de", "reemplaza lo que diga",
        "cada que diga algo responde con", "haz una automatización",
        # Patterns with names in the middle (real user phrasings)
        "cada que Xoft diga algo reacciona", "cuando Papu escriba borra",
        "si Karu dice algo responde", "cada que alguien mencione atelier",
        "cuando digan una grosería timeout", "si alguien dice spam borra",
        "haz que cuando digan peak reaccione", "cada que escriba reemplaza",
        "cuando alguien entre manda bienvenida", "si dice algo ponle timeout",
        "programa que reaccione a mensajes", "quiero que responda cuando me mencionen",
        "haz algo para cuando diga", "cada que mencione reemplaza su mensaje",
        "cuando haga ping avísale", "si alguien escribe esto que reaccione",
    ],
    "antiraid": [
        "raid", "ataque masivo", "muchas cuentas nuevas", "spam coordinado",
        "están raideando", "protección contra raid", "nuke", "mass join",
        "cuentas falsas entrando", "bots entrando", "nos están atacando",
        "entraron muchos de golpe", "están spameando",
    ],
    "apodos": [
        "apodo creativo", "ponle un nombre", "nickname", "cámbiale el nombre",
        "apodo para", "nombre gracioso", "renombra a", "ponle apodo",
        "cámbiale el nick", "ponle un apodo random", "nombre chistoso para",
        "renómbralo", "ponle de nombre",
    ],
    "traduccion": [
        "traduce", "traducir", "en inglés", "en español", "translate",
        "cómo se dice", "pásalo a inglés", "qué significa en",
        "tradúceme esto", "al japonés", "en francés",
        "dilo en inglés", "cómo sería en español", "pásalo a otro idioma",
        "qué dice esto en español",
    ],
    "obscura-web": [
        "busca en internet", "busca online", "googlea", "web search",
        "qué dice internet sobre", "busca información de",
        "investiga en la web", "fetch url", "busca en google",
        "qué es esto", "busca qué significa", "encuentra info sobre",
        "dime qué es", "busca sobre", "qué sabes de esto",
    ],
    "zzz_terminos": [
        "qué es en zzz", "zenless zone zero término", "bangboo",
        "hollow en zzz", "agente zzz", "w-engine", "disco drive",
        "qué significa en zzz", "mecánica de zzz", "sistema de zzz",
        "qué hace este personaje en zzz", "build de", "equipo para",
        "qué disco le pongo", "mejor w-engine para",
    ],
    "eventos": [
        "evento", "torneo", "planificar actividad", "organizar evento",
        "crear evento", "fecha del torneo", "sorteo", "programar actividad",
        "haz un torneo", "organiza algo", "actividad para el server",
        "cuándo es el próximo evento",
    ],
    "data_mastery": [
        "cuántos mensajes", "estadísticas", "quién habla más",
        "actividad del server", "datos de", "conteo de mensajes",
        "análisis de actividad", "horas pico", "comparar actividad",
        "quién es más activo", "stats del server",
        "cuánto se habla aquí", "quién postea más",
        "a qué hora hay más actividad", "el server está muerto",
        "quién ha estado más activo esta semana",
        "dame las stats", "muéstrame la actividad",
    ],
    "onboarding": [
        "bienvenida", "onboarding", "sistema de verificación",
        "auto rol al entrar", "configurar bienvenida", "welcome",
        "mensaje de bienvenida", "cuando alguien entre al server",
    ],
    "sellar": [
        "protocolo de sello completo", "procedimiento de sellado",
        "aislamiento completo con protocolo", "sella con todo el proceso",
        "séllame", "quiero sellarme", "ponme en cuarentena",
        "aíslame", "enciérrame", "quiero aislarme",
    ],
    "ascii_art": [
        "ascii art", "arte ascii", "dibujo en texto", "text art",
        "haz un dibujo ascii", "dibuja con caracteres",
    ],
}

# Multi-skill combinations: when these skills appear together, it's intentional
_SKILL_COMBOS: dict[str, list[str]] = {
    # "busca en internet y traduce" → web + traduccion
    "obscura-web+traduccion": ["busca y traduce", "encuentra en internet y tradúceme"],
    # "investiga y crea una regla" → sherlock + listeners
    "sherlock_kai+listeners": ["investiga y si es tóxico crea regla", "analiza y automatiza"],
}

_SKILL_EMB_INDEX: dict | None = None
_SKILL_EMB_LOCK = None


def _build_skill_emb_index(embedder) -> dict:
    """Build embedding index for skill example phrases."""
    all_phrases = []
    phrase_to_skill = []
    for skill, phrases in _SKILL_EXAMPLES.items():
        for phrase in phrases:
            all_phrases.append(phrase)
            phrase_to_skill.append(skill)
    # Add combo phrases
    for combo_key, phrases in _SKILL_COMBOS.items():
        for phrase in phrases:
            all_phrases.append(phrase)
            phrase_to_skill.append(combo_key)  # "skill1+skill2"

    embeddings = embedder.encode(all_phrases, normalize_embeddings=True)
    return {"embeddings": embeddings, "skills": phrase_to_skill}


def _detect_skills_semantic(text: str, embedder) -> list[str]:
    """Detect skills using semantic similarity. Returns list of skill names (can be multiple).

    Falls back gracefully if embedder unavailable.
    """
    global _SKILL_EMB_INDEX, _SKILL_EMB_LOCK
    import threading

    # Cancel check: management queries don't need skill injection
    if _SKILL_QUERY_CANCEL.search(text):
        return []

    if not embedder or not embedder.available:
        return []

    if _SKILL_EMB_LOCK is None:
        _SKILL_EMB_LOCK = threading.Lock()

    if _SKILL_EMB_INDEX is None:
        with _SKILL_EMB_LOCK:
            if _SKILL_EMB_INDEX is None:
                try:
                    _SKILL_EMB_INDEX = _build_skill_emb_index(embedder)
                except Exception:
                    return []

    try:
        q_emb = embedder.encode([text], normalize_embeddings=True)[0]
        scores = _SKILL_EMB_INDEX["embeddings"] @ q_emb
        skills_list = _SKILL_EMB_INDEX["skills"]

        # Find all skills above threshold
        THRESHOLD = 0.68
        # Listeners gets lower threshold — it's the most common request and has high cost of missing
        _SKILL_THRESHOLDS = {"listeners": 0.58, "antiraid": 0.60}
        SECONDARY_THRESHOLD = 0.72  # For multi-skill, second skill needs higher confidence

        # Get best score per skill
        skill_scores: dict[str, float] = {}
        for idx, score in enumerate(scores):
            skill = skills_list[idx]
            if score > skill_scores.get(skill, 0):
                skill_scores[skill] = float(score)

        # Sort by score
        ranked = sorted(skill_scores.items(), key=lambda x: -x[1])
        if not ranked:
            return []

        # Check against per-skill threshold (some skills are more important)
        top_skill, top_score = ranked[0]
        effective_threshold = _SKILL_THRESHOLDS.get(top_skill, THRESHOLD)
        if top_score < effective_threshold:
            return []

        result = []
        # First skill: passed its threshold
        if "+" in top_skill:
            # It's a combo match — return both skills
            result = top_skill.split("+")
        else:
            result.append(top_skill)
            # Check if a second skill also has high confidence (multi-skill request)
            if len(ranked) > 1:
                second_skill, second_score = ranked[1]
                if second_score >= SECONDARY_THRESHOLD and "+" not in second_skill:
                    # Only add if it's a different domain (not just a close synonym)
                    if second_skill != top_skill:
                        result.append(second_skill)

        return result

    except Exception:
        return []


# ── Kiro pipeline: modelos potentes con contexto grande ───────────────────────
# Siempre envía un set amplio de tools críticas + las relevantes por keyword.
# Estos modelos (Claude, MiniMax, GLM, DeepSeek) manejan bien 40+ tools.

_KIRO_ALWAYS_TOOLS: frozenset = frozenset({
    # core
    "send_message", "send_embed", "add_reaction", "get_user_by_name",
    "find_channel", "read_skill", "get_user_info", "search_messages",
    "create_listener", "list_listeners",
    # moderation
    "ban_user", "kick_user", "mute_user", "unmute_user", "warn_user",
    "get_warnings", "clear_warnings", "seal_user", "unseal_user",
    "get_infractions_summary",
    # channels
    "purge_messages", "lock_channel", "unlock_channel", "set_slowmode",
    "create_thread", "pin_message", "rename_channel",
    "get_channel_permissions", "set_channel_permissions",
    # roles
    "assign_role", "remove_role", "find_role", "set_nickname",
    # search/data
    "search_messages_semantic", "aggregate_messages", "get_channel_summary",
    "investigate_topic", "get_user_timeline", "query_pattern_analysis",
    "profile_sample", "paginate_messages", "get_loan_info",
    "list_morosos", "get_user_debt", "get_loan_leaderboard",
    "get_loan_stats", "get_loan_history",
    "get_treasury_balance", "get_treasury_history",
    # server info
    "server_dashboard", "get_leaderboard", "get_server_activity",
    "detect_newcomers", "find_inactive_members", "get_voice_members",
    # visual
    "render_template",
    # social graph
    "analyze_social_graph",
    # scheduling/misc
    "schedule_message", "create_poll", "send_dm", "web_fetch",
    "fetch_url_preview",
    # user content
    "get_user_card", "send_user_content_to_channel",
    # listeners
    "toggle_listener", "delete_listener", "edit_listener",
    # knowledge base
    "knowledge_search", "knowledge_store", "knowledge_update", "knowledge_delete",
    # birthdays
    "register_birthday", "get_birthdays",
    # shop / economy
    "shop_create", "shop_list", "shop_redeem", "shop_manage", "shop_bulk_create", "economy_stats",
    # music
    "play_music", "music_queue",
})


def _route_tools_kiro(user_text: str) -> _Tool:
    """Routing para modelos Kiro: set amplio base + expansión por keywords."""
    text_lower = user_text.lower() if user_text else ""
    selected_names = set(_KIRO_ALWAYS_TOOLS)

    # Expandir con categorías por keyword
    for keyword, cats in _KEYWORD_MAP.items():
        if keyword in text_lower:
            for cat in cats:
                selected_names.update(_TOOL_CATEGORIES.get(cat, []))

    filtered = [d for d in TOOL_DECLARATIONS if d.name in selected_names]
    return _Tool(function_declarations=filtered)


def _route_tools(user_text: str, model_name: str = "") -> _Tool:
    """Selecciona solo las tools relevantes basándose en keywords del mensaje."""
    text_lower = user_text.lower() if user_text else ""
    selected_cats = {"core"}  # siempre incluir core
    _is_qwen = model_name.lower().startswith("qwen/qwen3") if model_name else False

    for keyword, cats in _KEYWORD_MAP.items():
        if keyword in text_lower:
            selected_cats.update(cats)

    # Si no matcheó nada específico
    if selected_cats == {"core"}:
        if _is_qwen:
            # Qwen: expandir con categorías seguras en vez de TODAS
            selected_cats.update(("search", "server_info", "user_content"))
        else:
            return DJINN_TOOL

    # Recopilar nombres de tools seleccionadas
    selected_names = set()
    for cat in selected_cats:
        selected_names.update(_TOOL_CATEGORIES.get(cat, []))

    # Filtrar declaraciones
    filtered = [d for d in TOOL_DECLARATIONS if d.name in selected_names]

    # Si el filtro es muy agresivo (<10 tools)
    if len(filtered) < 10:
        if _is_qwen:
            # Expandir con categorías seguras, no con TODAS
            for cat in ("core", "search", "server_info", "user_content", "channels"):
                selected_names.update(_TOOL_CATEGORIES.get(cat, []))
            filtered = [d for d in TOOL_DECLARATIONS if d.name in selected_names]
        else:
            return DJINN_TOOL

    return _Tool(function_declarations=filtered)


# ── Semantic Tool Router ──────────────────────────────────────────────────────
# Uses EmbedEngine (all-MiniLM-L6-v2) to retrieve the most relevant tools
# for a given user message via cosine similarity. Falls back to keyword routing
# if embedder is unavailable.

import numpy as np

_TOOL_INDEX: dict | None = None  # Lazy-built on first use
_TOOL_INDEX_LOCK = None  # Will be set to threading.Lock() on first use

# Tools always included regardless of similarity score
_CORE_TOOL_NAMES: frozenset = frozenset({
    "send_message", "send_embed", "add_reaction", "get_user_by_name",
    "find_channel", "read_skill", "get_user_info",
    "create_listener", "list_listeners", "search_messages",
})

_MAX_SEMANTIC_TOOLS = 18  # Max tools to send (core + retrieved)
_SIMILARITY_THRESHOLD = 0.20  # Below this, tool is irrelevant


def _build_tool_index(embedder) -> dict:
    """Build embedding index for all tool declarations. Called once at first use."""
    texts = []
    for td in TOOL_DECLARATIONS:
        # Combine name + description + param names for rich embedding
        param_names = ""
        if td.parameters and td.parameters.properties:
            param_names = " ".join(td.parameters.properties.keys())
        text = f"{td.name.replace('_', ' ')}: {td.description}. params: {param_names}"
        texts.append(text)

    embeddings = embedder.encode(texts, normalize_embeddings=True)
    return {
        "embeddings": embeddings,  # shape (N, 384)
        "names": [td.name for td in TOOL_DECLARATIONS],
    }


def _route_tools_semantic(user_text: str, embedder, model_name: str = "") -> _Tool:
    """Hybrid tool routing: keyword matching first, semantic retrieval as supplement.

    Strategy:
    1. Keyword routing selects categories (fast, accurate for known patterns)
    2. If keywords matched → use those + supplement with top semantic matches
    3. If no keywords matched → use semantic retrieval instead of ALL tools fallback
    Falls back to keyword-only if embedder is unavailable.
    """
    global _TOOL_INDEX, _TOOL_INDEX_LOCK
    import threading

    # Step 1: Always run keyword routing first
    text_lower = user_text.lower() if user_text else ""
    selected_cats = {"core"}
    for keyword, cats in _KEYWORD_MAP.items():
        if keyword in text_lower:
            selected_cats.update(cats)

    # Collect keyword-matched tool names
    kw_names = set()
    for cat in selected_cats:
        kw_names.update(_TOOL_CATEGORIES.get(cat, []))

    keyword_matched = selected_cats != {"core"}

    # Step 2: If keywords matched well (>= 10 tools), use them directly
    if keyword_matched:
        filtered = [d for d in TOOL_DECLARATIONS if d.name in kw_names]
        if len(filtered) >= 10:
            return _Tool(function_declarations=filtered)

    # Step 3: Semantic supplement (when keywords insufficient or no match)
    if not embedder or not embedder.available:
        # No embedder → legacy fallback
        if keyword_matched:
            return _Tool(function_declarations=[d for d in TOOL_DECLARATIONS if d.name in kw_names])
        return DJINN_TOOL

    if _TOOL_INDEX_LOCK is None:
        _TOOL_INDEX_LOCK = threading.Lock()

    if _TOOL_INDEX is None:
        with _TOOL_INDEX_LOCK:
            if _TOOL_INDEX is None:
                try:
                    _TOOL_INDEX = _build_tool_index(embedder)
                    logger.info("Semantic tool index built: %d tools", len(_TOOL_INDEX["names"]))
                except Exception as exc:
                    logger.warning("Failed to build tool index: %s", exc)
                    return DJINN_TOOL if not keyword_matched else _Tool(
                        function_declarations=[d for d in TOOL_DECLARATIONS if d.name in kw_names])

    try:
        query_emb = embedder.encode([user_text], normalize_embeddings=True)[0]
        scores = _TOOL_INDEX["embeddings"] @ query_emb
        top_indices = np.argsort(scores)[::-1]

        # Retrieve top semantic matches above threshold
        semantic_names = set()
        for idx in top_indices:
            name = _TOOL_INDEX["names"][idx]
            if name in _CORE_TOOL_NAMES:
                continue
            if scores[idx] < _SIMILARITY_THRESHOLD:
                break
            semantic_names.add(name)
            if len(semantic_names) >= _MAX_SEMANTIC_TOOLS:
                break

        # Merge: keyword matches + semantic matches + core
        all_names = kw_names | semantic_names | _CORE_TOOL_NAMES
        declarations = [d for d in TOOL_DECLARATIONS if d.name in all_names]

        # Cap at reasonable size
        if len(declarations) > 25:
            # Prioritize: core > keyword > semantic (by score)
            core_decls = [d for d in declarations if d.name in _CORE_TOOL_NAMES]
            kw_decls = [d for d in declarations if d.name in kw_names and d.name not in _CORE_TOOL_NAMES]
            sem_decls = [d for d in declarations if d.name in semantic_names
                         and d.name not in _CORE_TOOL_NAMES and d.name not in kw_names]
            declarations = core_decls + kw_decls + sem_decls[:25 - len(core_decls) - len(kw_decls)]

        return _Tool(function_declarations=declarations) if declarations else DJINN_TOOL

    except Exception as exc:
        logger.debug("Semantic routing failed: %s", exc)
        return DJINN_TOOL if not keyword_matched else _Tool(
            function_declarations=[d for d in TOOL_DECLARATIONS if d.name in kw_names])

# ── Token budget ────────────────────────────────────────────────────────
# Gemma 4 26b-a4b: 128K context. Budget conservador para latencia baja.
# 50K tokens de historial ≈ ~150 turnos — más que suficiente para Discord.
_CONTEXT_TOKEN_BUDGET: int = 50_000

# ── Inline Tool Markers (Qwen3-Next) ──────────────────────────────────────
# Permite al modelo generar texto con marcadores [tool_name(args)] embebidos.
# El post-procesador los ejecuta y reemplaza con resultados formateados.
# Esto permite que Qwen comente antes/después de los datos inline.

import re as _re_mod

_INLINE_TOOL_RE = _re_mod.compile(
    r"\[([a-z_][a-z_0-9]*)"       # [tool_name
    r"(?:\(([^)]*)\))?"            # (optional args)
    r"\]",                         # ]
    _re_mod.IGNORECASE,
)

# Broader regex to catch malformed attempts: [List Listeners], [LIST_LISTENERS()], etc.
_INLINE_TOOL_FUZZY_RE = _re_mod.compile(
    r"\[([A-Za-z][A-Za-z0-9_ \-]*[A-Za-z0-9])"  # [tool name - greedy, must end with alnum
    r"(?:\(([^)]*)\))?"                           # (optional args)
    r"\]",                                        # ]
)

# Tools que soportan ejecución inline (read-only, resultados formateables)
_INLINE_ALLOWED_TOOLS: frozenset = frozenset({
    "list_listeners", "get_warnings", "get_leaderboard", "server_dashboard",
    "list_bans", "list_events", "get_voice_members", "get_user_info",
    "search_messages", "aggregate_messages", "get_channel_summary",
    "get_server_activity", "get_peak_hours", "find_inactive_members",
    "detect_newcomers", "get_listener_stats", "get_infractions_summary",
    "get_user_card", "get_case_notes", "list_watched_users",
})

# Normalized lookup: stripped/lowered name → canonical tool name
_INLINE_TOOL_ALIASES: dict = {}
for _t in _INLINE_ALLOWED_TOOLS:
    _INLINE_TOOL_ALIASES[_t] = _t                          # list_listeners
    _INLINE_TOOL_ALIASES[_t.replace("_", "")] = _t         # listlisteners
    _INLINE_TOOL_ALIASES[_t.replace("_", " ")] = _t        # list listeners


def _normalize_inline_tool_name(raw: str) -> Optional[str]:
    """Fuzzy-match a malformed tool name to a canonical one."""
    # Direct match
    lower = raw.lower().strip()
    if lower in _INLINE_ALLOWED_TOOLS:
        return lower
    # Normalize: replace hyphens/spaces with underscores, then try
    normalized = lower.replace("-", "_").replace(" ", "_")
    if normalized in _INLINE_ALLOWED_TOOLS:
        return normalized
    # Remove all separators and match
    stripped = lower.replace(" ", "").replace("_", "").replace("-", "")
    for canonical in _INLINE_ALLOWED_TOOLS:
        if canonical.replace("_", "") == stripped:
            return canonical
    # Partial prefix match (at least 8 chars)
    if len(stripped) >= 8:
        for canonical in _INLINE_ALLOWED_TOOLS:
            if canonical.replace("_", "").startswith(stripped):
                return canonical
    return None


def _fix_inline_markers(text: str) -> str:
    """Fix malformed inline tool markers to canonical format.

    Handles:
      [List_Listeners], [list listeners], [LIST_LISTENERS], [listlisteners]
      [[list_listeners]], [list_listeners()], [list_listeners( )]
      {list_listeners}, **[list_listeners]**, `[list_listeners]`
      [list-listeners], [list_listeners]:, [list_listeners].
      [list_listeners - (missing close bracket)
      list_listeners] - (missing open bracket)
    """
    # Pass 1: Strip markdown formatting around potential markers
    # **[...]** → [...], `[...]` → [...], *[...]* → [...]
    text = _re_mod.sub(r'\*{1,2}\[', '[', text)
    text = _re_mod.sub(r'\]\*{1,2}', ']', text)
    text = _re_mod.sub(r'`\[', '[', text)
    text = _re_mod.sub(r'\]`', ']', text)

    # Pass 2: Fix double brackets [[...]] → [...]
    text = _re_mod.sub(r'\[\[([^\]]+)\]\]', r'[\1]', text)

    # Pass 3: Fix curly braces {tool_name} → [tool_name]
    text = _re_mod.sub(r'\{([A-Za-z][A-Za-z0-9_ -]*(?:\([^)]*\))?)\}', r'[\1]', text)

    # Pass 4: Fix missing closing bracket: [tool_name followed by newline/period/comma
    # Only if there's NO ] before the next newline (avoids breaking valid [X Y] markers)
    text = _re_mod.sub(r'\[([A-Za-z][A-Za-z0-9_ -]{5,})(?=[\.\,\:](?!\]))', r'[\1]', text)

    # Pass 5: Fix bare function-call style: tool_name() at start of line or after whitespace
    def _bare_call_fix(m):
        raw = m.group(1)
        args = m.group(2) or ""
        canonical = _normalize_inline_tool_name(raw)
        if canonical:
            if args.strip():
                return f"[{canonical}({args.strip()})]"
            return f"[{canonical}]"
        return m.group(0)
    text = _re_mod.sub(r'(?:^|(?<=\s))([A-Za-z][A-Za-z_]{5,})\(([^)]*)\)', _bare_call_fix, text)

    # Pass 6: Normalize the content inside brackets
    def _replacer(match):
        raw_name = match.group(1)
        args = match.group(2)

        # Strip trailing punctuation from name
        raw_name = raw_name.rstrip(':.,;!')
        # Replace hyphens with underscores
        raw_name = raw_name.replace('-', '_')
        # Strip empty parens that got captured as part of name
        raw_name = raw_name.rstrip('()')

        canonical = _normalize_inline_tool_name(raw_name)
        if canonical:
            # Clean args: strip empty parens, whitespace
            if args is not None:
                args = args.strip()
                if not args:
                    return f"[{canonical}]"
                return f"[{canonical}({args})]"
            return f"[{canonical}]"
        return match.group(0)  # Leave unchanged if not a tool

    text = _INLINE_TOOL_FUZZY_RE.sub(_replacer, text)

    # Pass 7: Remove trailing punctuation stuck to closing bracket: ]:  ].  ],
    text = _re_mod.sub(r'\]([:\.])\s', r'] ', text)

    return text


def _format_inline_result(tool_name: str, result: Any) -> str:
    """Formatea el resultado de una tool para inserción inline en texto."""
    if isinstance(result, dict):
        # Si tiene un campo 'error', mostrar el error
        if "error" in result:
            return f"[Error: {result['error']}]"
        # Si tiene items/results/entries como lista, formatear cada uno
        for key in ("rules", "items", "results", "entries", "warnings",
                    "members", "bans", "events", "listeners", "users"):
            if key in result and isinstance(result[key], list):
                lines = []
                for i, item in enumerate(result[key], 1):
                    if isinstance(item, dict):
                        # Intentar extraer nombre/descripción/id
                        name = item.get("name") or item.get("description") or item.get("rule_id") or item.get("username") or str(item)
                        detail = item.get("detail") or item.get("status") or item.get("triggers_today") or ""
                        if isinstance(name, dict):
                            name = str(name)
                        line = f"{i}. {name}"
                        if detail:
                            line += f" — {detail}"
                        lines.append(line)
                    else:
                        lines.append(f"{i}. {item}")
                if lines:
                    return "\n".join(lines)
        # Fallback: JSON compacto
        import json as _json
        return _json.dumps(result, ensure_ascii=False, default=str)[:2000]
    if isinstance(result, list):
        lines = [f"{i+1}. {item}" for i, item in enumerate(result)]
        return "\n".join(lines) if lines else "(vacío)"
    return str(result)[:2000]


async def _process_inline_tools(text: str, executor) -> str:
    """Procesa marcadores [tool_name(args)] en texto y los reemplaza con resultados.

    Solo para Qwen3-Next. Permite al modelo comentar antes/después de datos.
    """
    if not executor or not text:
        return text

    matches = list(_INLINE_TOOL_RE.finditer(text))
    if not matches:
        return text

    # Procesar de atrás hacia adelante para no romper offsets
    for match in reversed(matches):
        tool_name = match.group(1).lower()
        raw_args = match.group(2) or ""

        if tool_name not in _INLINE_ALLOWED_TOOLS:
            continue

        # Parsear args simples: key=value, key=value
        kwargs = {}
        if raw_args.strip():
            for part in raw_args.split(","):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    # Intentar convertir a int
                    try:
                        v = int(v)
                    except ValueError:
                        pass
                    kwargs[k] = v

        try:
            # Construir un FunctionCall-like object para el executor
            from google.genai import types
            fc = types.FunctionCall(name=tool_name, args=kwargs)
            result = await executor.execute(fc)
            formatted = _format_inline_result(tool_name, result)
            text = text[:match.start()] + formatted + text[match.end():]
        except Exception as exc:
            logger.debug("Inline tool %s failed: %s", tool_name, exc)
            text = text[:match.start()] + f"[Error ejecutando {tool_name}]" + text[match.end():]

    return text
_CONTEXT_TOKEN_BUDGET: int = 50_000
_CHARS_PER_TOKEN: float = 3.5  # estimación para texto mixto es/en (±20%)

# System prompt + tool schemas ≈ 14K tokens (se descuenta del budget)
_SYSTEM_PROMPT_TOKENS: int = 14_000

# Patrones de menciones en contenido crudo de Discord
_USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
_ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")
_CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")


def _resolve_mentions(text: str, guild: discord.Guild) -> str:
    """
    Convierte menciones de Discord a formato legible con IDs explícitos.

    Antes: "dale timeout a <@***> de 1 hora"
    Después: "dale timeout a NotSoBot (ID: 439205512425504771) de 1 hora"

    Esto permite al LLM extraer el user_id directamente sin pedírselo al usuario.
    """
    def resolve_user(m: re.Match) -> str:
        uid = int(m.group(1))
        member = guild.get_member(uid)
        name = member.display_name if member else "User"
        return f"{name} (ID: {uid})"

    def resolve_role(m: re.Match) -> str:
        rid = int(m.group(1))
        role = guild.get_role(rid)
        name = role.name if role else "Role"
        return f"@{name} (role ID: {rid})"

    def resolve_channel(m: re.Match) -> str:
        cid = int(m.group(1))
        ch = guild.get_channel(cid)
        name = ch.name if ch else "channel"
        return f"#{name} (channel ID: {cid})"

    text = _USER_MENTION_RE.sub(resolve_user, text)
    text = _ROLE_MENTION_RE.sub(resolve_role, text)
    text = _CHANNEL_MENTION_RE.sub(resolve_channel, text)
    return text


class Orchestrator:
    # ── Rate limiting por usuario ──────────────────────────────────────────
    _USER_RATE_WINDOW = 60  # segundos
    _USER_RATE_MAX = 8      # máx requests por usuario por ventana

    # ── Circuit breaker para LLM ──────────────────────────────────────────
    _CB_FAIL_THRESHOLD = 3   # fallos consecutivos para abrir
    _CB_RECOVERY_SECS = 60   # segundos en estado abierto antes de half-open

    def __init__(self, bot, llm_client: LLMClient) -> None:
        self.bot = bot
        self.llm = llm_client
        self.llm_public = llm_client  # default: mismo que staff, switcheable independiente
        self._histories: dict[int, Deque[Content]] = {}
        self._history_last_access: dict[int, float] = {}
        self._MAX_HISTORIES = 50
        # Rate limiting
        self._user_requests: dict[int, List[float]] = {}
        # Circuit breaker state
        self._cb_failures: int = 0
        self._cb_open_since: float = 0.0

    # A3 (review): rate limit por usuario — ventana deslizante. Generoso para no
    # molestar conversación normal; corta abuso / bucles de tools. Configurable:
    # DJINN_RATE_MAX peticiones por DJINN_RATE_WINDOW seg. MAX<=0 lo desactiva.
    _RATE_MAX = int(os.environ.get("DJINN_RATE_MAX", os.environ.get("YOUKAI_RATE_MAX", "8")))
    _RATE_WINDOW = float(os.environ.get("DJINN_RATE_WINDOW", os.environ.get("YOUKAI_RATE_WINDOW", "30")))

    def _check_user_rate(self, user_id: int) -> bool:
        """True si el usuario está dentro del límite (ventana deslizante)."""
        if self._RATE_MAX <= 0:
            return True
        now = time.monotonic()
        cutoff = now - self._RATE_WINDOW
        reqs = [t for t in self._user_requests.get(user_id, ()) if t >= cutoff]
        if len(reqs) >= self._RATE_MAX:
            self._user_requests[user_id] = reqs
            return False
        reqs.append(now)
        self._user_requests[user_id] = reqs
        return True

    def _cb_is_open(self) -> bool:
        """Check if circuit breaker is open (LLM disabled)."""
        if self._cb_failures < self._CB_FAIL_THRESHOLD:
            return False
        if time.time() - self._cb_open_since >= self._CB_RECOVERY_SECS:
            # Half-open: allow one attempt
            self._cb_failures = self._CB_FAIL_THRESHOLD - 1
            return False
        return True

    def _cb_record_success(self) -> None:
        self._cb_failures = 0

    def _cb_record_failure(self) -> None:
        self._cb_failures += 1
        if self._cb_failures >= self._CB_FAIL_THRESHOLD:
            self._cb_open_since = time.time()
            logger.warning("Orchestrator: circuit breaker OPEN — LLM disabled for %ds", self._CB_RECOVERY_SECS)

    # ── Historial ──────────────────────────────────────────────────────────

    def _get_history(self, channel_id: int) -> Deque[Content]:
        if channel_id not in self._histories:
            self._prune_stale_histories()
            self._histories[channel_id] = deque()
        self._history_last_access[channel_id] = time.monotonic() if hasattr(time, 'monotonic') else 0
        return self._histories[channel_id]

    def _prune_stale_histories(self) -> None:
        """Elimina historiales excesivos para evitar memory leak."""
        if len(self._histories) <= self._MAX_HISTORIES:
            return
        # Eliminar los 10 canales con acceso mas antiguo
        sorted_channels = sorted(
            self._history_last_access.items(),
            key=lambda x: x[1],
        )
        for ch_id, _ in sorted_channels[:10]:
            self._histories.pop(ch_id, None)
            self._history_last_access.pop(ch_id, None)

    @staticmethod
    def _token_estimate(char_count: int) -> int:
        """Estimación rápida de tokens. chars / 3.5 ≈ tokens (±20% texto mixto)."""
        return int(char_count / _CHARS_PER_TOKEN)

    def _trim_to_budget(self, history: Deque[Content]) -> None:
        available = _CONTEXT_TOKEN_BUDGET - _SYSTEM_PROMPT_TOKENS
        while history:
            total_chars = sum(
                len(part.text or "")
                for turn in history
                for part in (turn.parts or [])
                if hasattr(part, "text")
            )
            if self._token_estimate(total_chars) <= available:
                break
            if history: history.popleft()  # user turn
            if history: history.popleft()  # model turn
        # F2: Si despues de recortar quedan 8+ turnos, prefijar con resumen
        if len(history) >= 8:
            summary = self._summarize_history(history)
            if summary:
                summary_content = Content(
                    role="user",
                    parts=[Part.from_text(text=summary)]
                )
                if history: history.popleft()
                if history: history.popleft()
                history.appendleft(summary_content)

    @staticmethod
    def _summarize_history(history: Deque[Content]) -> str:
        # Genera un resumen comprimido con datos duros: nombres y citas textuales
        turns = list(history)
        if len(turns) < 6:
            return ""
        summary_parts = []
        recent = turns[-10:]
        for turn in recent:
            role = getattr(turn, 'role', 'unknown')
            for part in (turn.parts or []):
                text = getattr(part, 'text', None) or ''
                if not text:
                    continue
                if len(text) > 150:
                    text = text[:147] + '...'
                prefix = 'USR' if role == 'user' else 'BOT'
                summary_parts.append(f'{prefix}: "{text}"')
        if not summary_parts:
            return ''
        return 'CONVERSATION SUMMARY (recent context):\n' + '\n'.join(summary_parts[-8:])

    def _record_turn(self, channel_id: int, user_text: str, model_text: str) -> None:
        history = self._get_history(channel_id)
        history.append(Content(role="user", parts=[Part.from_text(text=user_text)]))
        history.append(Content(role="model", parts=[Part.from_text(text=model_text)]))
        self._trim_to_budget(history)

    def clear_history(self, channel_id: int) -> None:
        self._histories.pop(channel_id, None)

    # ── Lazy Loading Gates ─────────────────────────────────────────────────

    # Keywords que indican que el mensaje necesita contexto histórico
    _RECALL_KEYWORDS = frozenset((
        "quién", "cuándo", "dijo", "pasó", "busca", "investiga", "qué",
        "cuántas", "cuántos", "recuerdas", "antes", "ayer", "hoy",
        "mencionó", "habló", "escribió", "preguntó", "respondió",
        "historial", "registro", "log", "últim", "reciente",
    ))

    # Keywords que indican operación de canal
    _CHANNEL_KEYWORDS = frozenset((
        "canal", "channel", "#", "mover", "move", "envía en", "send in",
        "manda en", "post in", "crea canal", "create channel", "lock",
        "unlock", "slowmode", "purge", "limpia", "borra mensajes",
        "thread", "hilo", "pin", "topic",
    ))

    @staticmethod
    def _should_recall(clean_text: str) -> bool:
        """Determina si el mensaje necesita auto-recall de la DB.

        Skip para: saludos cortos, reacciones, mensajes triviales, comandos directos.
        Activa para: preguntas sobre historial, menciones de personas/eventos.
        """
        text_lower = clean_text.lower()
        # Strip author prefix ("Nombre: ") for analysis
        if ": " in text_lower:
            text_body = text_lower.split(": ", 1)[1]
        else:
            text_body = text_lower
        words = text_body.split()

        # Mensajes muy cortos sin keywords de consulta → no recall
        if len(words) <= 4:
            if not any(kw in text_body for kw in Orchestrator._RECALL_KEYWORDS):
                return False

        # Mensajes que son claramente comandos/acciones → no recall
        action_starts = ("ban", "kick", "mute", "seal", "crea ", "nueva regla",
                         "asigna", "quita rol", "timeout")
        if any(text_body.startswith(a) for a in action_starts):
            return False

        return True

    @staticmethod
    def _should_include_channels(clean_text: str) -> bool:
        """Determina si el mensaje necesita la lista de canales pre-resuelta.

        La mayoría de mensajes no necesitan saber qué canales existen.
        El modelo puede llamar find_channel() si lo necesita.
        """
        if not clean_text:
            return False
        text_lower = clean_text.lower()
        return any(kw in text_lower for kw in Orchestrator._CHANNEL_KEYWORDS)

    # ── Preparación del mensaje ────────────────────────────────────────────

    def _prepare_content(self, message: discord.Message) -> str:
        """
        1. Elimina solo la mención al propio bot.
        2. Resuelve todas las demás menciones a "Nombre (ID: X)".
        3. Prefija con el display_name del autor para que el LLM distinga speakers.
        """
        content = message.content

        # Eliminar solo la mención del bot (no las de otros usuarios)
        bot_id = self.bot.user.id
        content = re.sub(rf"<@!?{bot_id}>", "", content)

        # Resolver menciones de usuarios, roles y canales
        if message.guild:
            content = _resolve_mentions(content, message.guild)

        # Prefijar autor para multi-user awareness (C2 fix)
        author_name = message.author.display_name
        resolved = content.strip()
        if resolved:
            return f"{author_name}: {resolved}"
        return resolved

    # ── Pipeline principal ─────────────────────────────────────────────────

    async def process_message(
        self,
        message: discord.Message,
        media: Optional[List[Any]] = None,
        system_override: bool = False,
    ) -> Optional[str]:
        # ── Rate limiting por usuario (Fairy overseer exenta) ──────────
        _FAIRY_BOT_ID = 1488300519234470108
        if message.author.id != _FAIRY_BOT_ID and not self._check_user_rate(message.author.id):
            logger.warning("Orchestrator: rate limit hit for user %d", message.author.id)
            return None

        # ── Circuit breaker ────────────────────────────────────────────
        if self._cb_is_open():
            logger.debug("Orchestrator: circuit breaker open — skipping LLM call")
            return None

        channel_id = message.channel.id
        clean_text = self._prepare_content(message)

        if not clean_text and not media:
            logger.debug("Orchestrator: mensaje vacío — ignorado.")
            return None

        try:
            nexus_context = await self.bot.nexus.get_context_snapshot(message.guild.id)
        except Exception:
            logger.exception("Orchestrator: error obteniendo nexus_context.")
            nexus_context = ""

        tools_available = (
            message.guild is not None
            and message.channel is not None
            and self.bot.db is not None
        )

        # ── F1: Auto-recall mensajes relevantes de la DB ─────────────
        relevant_context = ""
        if tools_available and clean_text and self._should_recall(clean_text):
            try:
                _recall_limit = 50

                # ── C1 fix: Augmentar query con contexto reciente ──────
                history = list(self._get_history(channel_id))
                recent_context = ""
                if history:
                    recent_parts = []
                    for turn in history[-10:]:
                        for part in (turn.parts or []):
                            text = getattr(part, 'text', None) or ''
                            if text and len(text) > 5:
                                recent_parts.append(text[:150])
                                break
                    if recent_parts:
                        recent_context = " | ".join(recent_parts[-8:])

                query_text = clean_text[:200]
                if recent_context:
                    query_text = f"{clean_text[:200]}\n[contexto reciente: {recent_context}]"

                # Generar embedding del query semántico usando Youkai EmbedEngine
                query_embedding = None
                if self.bot.embedder and self.bot.embedder.available:
                    try:
                        loop = asyncio.get_running_loop()
                        query_embedding = await loop.run_in_executor(
                            None, self.bot.embedder.encode, query_text[:800]
                        )
                        if hasattr(query_embedding, "tolist"):
                            query_embedding = query_embedding.tolist()
                    except Exception:
                        query_embedding = None

                results = await self.bot.db.hybrid_search_messages(
                    guild_id=message.guild.id,
                    query=query_text[:800],
                    hours=168,
                    limit=_recall_limit,
                    semantic_weight=0.5 if query_embedding is not None else 0.0,
                    query_embedding=query_embedding,
                )
                if results:
                    lines = []
                    for row in results:
                        uname = row.get("username", "unknown")
                        raw_content = row.get("content") or ""
                        if len(raw_content) > 500:
                            content = raw_content[:500] + "..."
                        else:
                            content = raw_content
                        if content:
                            lines.append(f"  [{uname}]: {content}")
                    if lines:
                        relevant_context = "RELEVANT PAST MESSAGES (auto-recalled from DB):\n" + "\n".join(lines)
            except Exception:
                logger.debug("Orchestrator: auto-recall falló, continuando sin contexto extra.")

        # ── Server Memory injection ────────────────────────────────────
        server_memory_ctx = ""
        if tools_available and clean_text:
            try:
                from cogs.server_memory import get_server_context
                server_memory_ctx = get_server_context(message.guild, clean_text)
            except ImportError:
                pass
            except Exception:
                logger.debug("Orchestrator: server memory injection falló.")

        # ── Auto-inyección de skill por intención ─────────────────────
        rules_skill_ctx = ""
        if tools_available and clean_text:
            # Capa 1: Regex (0ms, preciso para patrones conocidos)
            detected_skill = _detect_skill_intent(clean_text)
            skills_to_load = [detected_skill] if detected_skill else []

            # Capa 2: Semantic fallback (22ms, para mensajes ambiguos)
            if not skills_to_load and hasattr(self.bot, 'embedder'):
                skills_to_load = _detect_skills_semantic(clean_text, self.bot.embedder)

            # Cargar todas las skills detectadas
            if skills_to_load:
                try:
                    import os
                    skill_parts = []
                    for skill_name in skills_to_load:
                        _skill_path = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "skills", f"{skill_name}.md"
                        )
                        if os.path.isfile(_skill_path):
                            with open(_skill_path, "r", encoding="utf-8") as _f:
                                skill_parts.append(
                                    f"SKILL AUTO-LOADED ({skill_name}) — Sigue este protocolo:\n"
                                    + _f.read()
                                )
                            logger.debug("Orchestrator: skill '%s' auto-inyectada.", skill_name)
                    if skill_parts:
                        rules_skill_ctx = "\n\n".join(skill_parts)
                except Exception:
                    pass

        # ── ZZZ RAG injection ──────────────────────────────────────────
        zzz_context = ""
        if clean_text:
            try:
                from cogs.zzz_rag import zzz_should_inject, zzz_query
                if zzz_should_inject(clean_text):
                    zzz_chunks = zzz_query(clean_text, top_k=3)
                    if zzz_chunks:
                        zzz_context = "ZZZ KNOWLEDGE BASE (datos actualizados de Zenless Zone Zero):\n" + "\n".join(zzz_chunks)
                        logger.debug("Orchestrator: ZZZ RAG inyectó %d chunks", len(zzz_chunks))
            except ImportError as e:
                logger.debug("Orchestrator: ZZZ RAG import failed: %s", e)
            except Exception as e:
                logger.debug("Orchestrator: ZZZ RAG injection falló: %s", e)

        # ── Knowledge Base auto-injection ──────────────────────────────
        kb_context = ""
        if tools_available and clean_text and len(clean_text) > 8:
            try:
                kb_results = await self.bot.db.kb_search(
                    message.guild.id, clean_text[:200], limit=3
                )
                if kb_results:
                    kb_lines = [f"  • {r['content'][:200]}" for r in kb_results]
                    kb_context = "KNOWLEDGE BASE (memoria persistente del servidor):\n" + "\n".join(kb_lines)
                    logger.debug("Orchestrator: KB inyectó %d entries", len(kb_results))
            except Exception:
                pass

        # Construir contents
        parts: List[Part] = []

        # ── Contexto pre-resuelto: canales + usuarios mencionados ──────
        pre_resolved = []
        if tools_available:
            # Canales: solo inyectar lista completa si el mensaje sugiere operación de canal
            import unicodedata
            if self._should_include_channels(clean_text):
                ch_list = []
                for ch in message.guild.text_channels:
                    norm = unicodedata.normalize("NFKD", ch.name)
                    norm = "".join(c for c in norm if unicodedata.category(c)[0] in ("L", "N", "Z")).lower()
                    ch_list.append(f"{norm}={ch.id}")
                _model = (self.llm.get_model_name() or "").lower()
                _max_ch = 10 if _model.startswith("qwen/qwen3") else 30
                pre_resolved.append(f"CANALES: {', '.join(ch_list[:_max_ch])}")

            # Usuarios mencionados en el mensaje
            if message.mentions:
                u_parts = []
                for u in message.mentions[:10]:
                    avatar = u.display_avatar.url if u.display_avatar else ""
                    u_parts.append(f"{u.display_name}(ID:{u.id},avatar:{avatar})")
                pre_resolved.append(f"USUARIOS_MENCIONADOS: {', '.join(u_parts)}")

            # Canal actual
            pre_resolved.append(
                f"CANAL_ACTUAL: {message.channel.name} (ID:{message.channel.id})"
            )

            # Autor del mensaje actual (para que el LLM use el ID correcto)
            pre_resolved.append(
                f"AUTOR_ACTUAL: {message.author.display_name} (ID:{message.author.id})"
            )

        if pre_resolved:
            ctx_text = "[CONTEXTO PRE-RESUELTO — usa estos IDs directamente, NO llames find_channel/get_user_by_name para ellos]\n" + "\n".join(pre_resolved)
            parts.append(Part.from_text(text=ctx_text + "\n\n" + (clean_text or "")))
        elif clean_text:
            parts.append(Part.from_text(text=clean_text))
        if media:
            for frame in media:
                parts.append(Part.from_bytes(data=frame, mime_type="image/jpeg"))
        if not parts:
            return None

        history = list(self._get_history(channel_id))
        contents = history + [Content(role="user", parts=parts)]

        try:
            # Agentic-only pipeline: siempre usar generate_with_tools.
            # El tool_system_prompt instruye al LLM a responder sin tools
            # cuando es conversacion casual. Confiamos en esa decision.
            tool_prompt = self.llm.tool_system_prompt
            if nexus_context:
                tool_prompt = (
                    tool_prompt
                    + f"\n\nCURRENT IDENTITY CONTEXT (IDs and Aliases):\n{nexus_context}"
                )
            if relevant_context:
                tool_prompt = (
                    tool_prompt
                    + f"\n\n{relevant_context}"
                )
            if server_memory_ctx:
                tool_prompt = (
                    tool_prompt
                    + f"\n\n{server_memory_ctx}"
                )
            if zzz_context:
                tool_prompt = (
                    tool_prompt
                    + f"\n\n{zzz_context}"
                )
            if kb_context:
                tool_prompt = (
                    tool_prompt
                    + f"\n\n{kb_context}"
                )
            if rules_skill_ctx:
                tool_prompt = (
                    tool_prompt
                    + f"\n\n{rules_skill_ctx}"
                )
            executor = ToolExecutor(message.guild, message.channel, self.bot.db,
                            bot=self.bot, author_id=message.author.id) if tools_available else None
            if tools_available:
                _model = self.llm.get_model_name() or ""
                if system_override:
                    routed_tools = _Tool(function_declarations=list(TOOL_DECLARATIONS))
                elif self.bot.config.llm_provider == "kiro":
                    routed_tools = _route_tools_kiro(clean_text)
                else:
                    routed_tools = _route_tools_semantic(clean_text, self.bot.embedder, _model)
            else:
                routed_tools = DJINN_TOOL
            response = await self.llm.generate_with_tools(
                system_prompt=tool_prompt,
                contents=contents,
                tools=routed_tools,
                executor=executor,
            )
        except Exception as exc:
            # Error transitorio de la API (500/503/timeout tras 5 retries).
            # Retornamos None para que NLPHandler reaccione con emoji discreto
            # en vez de enviar "Negative. An internal API error..." al usuario.
            logger.warning(
                "Orchestrator: LLM call failed after retries — %s: %s",
                type(exc).__name__, exc,
            )
            self._cb_record_failure()
            return None

        self._cb_record_success()

        # ── Inline tool markers (Qwen3-Next only) ─────────────────────
        # Only process if user explicitly asked for data (lista, reglas, stats, etc.)
        if response and executor and (self.llm.get_model_name() or "").lower().startswith("qwen/qwen3"):
            _data_request = any(kw in clean_text.lower() for kw in
                ("lista", "reglas", "rules", "listeners", "stats", "leaderboard",
                 "warnings", "bans", "dashboard", "activ"))
            if _INLINE_TOOL_FUZZY_RE.search(response):
                if _data_request:
                    try:
                        response = _fix_inline_markers(response)
                        response = await _process_inline_tools(response, executor)
                    except Exception as exc:
                        logger.debug("Inline tool processing failed: %s", exc)
                else:
                    # Strip unprocessed markers so user doesn't see [list_listeners] raw
                    response = _INLINE_TOOL_RE.sub("", response).strip()

        if response and not response.startswith("Negative."):
            self._record_turn(channel_id, clean_text, response)
        else:
            logger.warning(
                "Orchestrator: respuesta auto-negativa — no persistida. Preview: %s",
                (response or "")[:120],
            )

        return response or None

    # ── Public pipeline (restricted tools, no full personality) ─────────
    async def process_message_public(
        self,
        message: discord.Message,
    ) -> Optional[str]:
        """Lighter pipeline for non-reader users with restricted tools."""
        channel_id = message.channel.id
        clean_text = self._prepare_content(message)
        if not clean_text:
            return None

        _model = (self.llm.get_model_name() or "").lower()
        _is_qwen = _model.startswith("qwen/qwen3")

        # Build public tool set
        filtered = [d for d in TOOL_DECLARATIONS if d.name in _PUBLIC_TOOL_NAMES]
        public_tools = _Tool(function_declarations=filtered)

        # Context with lazy loading gates (same as main pipeline)
        parts: List[Part] = []
        import unicodedata
        pre_resolved = []

        # Channels: only if message suggests channel operations
        if self._should_include_channels(clean_text):
            ch_list = []
            for ch in message.guild.text_channels:
                norm = unicodedata.normalize("NFKD", ch.name)
                norm = "".join(c for c in norm if unicodedata.category(c)[0] in ("L", "N", "Z")).lower()
                ch_list.append(f"{norm}={ch.id}")
            _max_ch = 10 if _is_qwen else 30
            pre_resolved.append(f"CANALES: {', '.join(ch_list[:_max_ch])}")

        pre_resolved.append(f"CANAL_ACTUAL: {message.channel.name} (ID:{message.channel.id})")
        pre_resolved.append(f"AUTOR_ACTUAL: {message.author.display_name} (ID:{message.author.id})")

        ctx_text = "[CONTEXTO PRE-RESUELTO]\n" + "\n".join(pre_resolved)
        parts.append(Part.from_text(text=ctx_text + "\n\n" + clean_text))

        contents = [Content(role="user", parts=parts)]

        # Public system prompt — same personality, restricted tools
        public_prompt = (
            "Eres Djinn. Mismo tono, misma personalidad, misma ironía cortante. "
            "Hablas en español neutro. Sin emojis. Oraciones cortas y completas. "
            "Ironía casual, superioridad relajada, genuinamente entretenido por los humanos. "
            "NO eres un asistente genérico — eres Djinn con acceso limitado.\n\n"
            "RESPUESTA NORMAL — TEXTO PLANO:\n"
            "Para responder al canal donde te hablan, emite TEXTO PLANO directamente. "
            "NO uses send_message para esto — send_message es solo para mandar a OTROS "
            "canales (operación admin). Si solo te dicen 'hola', responde con texto, no "
            "con una tool. NUNCA llames send_message dos veces seguidas — eso es un loop "
            "alucinatorio. Una respuesta = un turn = un texto.\n\n"
            "CAPACIDADES DE ESTE USUARIO (no es Reader):\n"
            "• Búsqueda y análisis de datos (search_messages, aggregate_messages, investigate_topic)\n"
            "• Enviar mensajes y DMs (send_message, send_dm, send_embed) — SOLO si el usuario lo pide\n"
            "  explícitamente para OTRO canal/usuario, no para responder al canal actual\n"
            "• Crear y listar listeners (cooldown mínimo forzado: 6h, cuesta 1000cr, máx 1 por usuario)\n"
            "• Web (web_fetch)\n"
            "• Reacciones (add_reaction)\n"
            "• Leer skills para protocolos avanzados (read_skill)\n\n"
            "• Auto-sello: el usuario puede sellarse A SÍ MISMO con seal_user(user_id=SU_PROPIO_ID).\n"
            "  Solo funciona con su propio ID. Si piden sellarse, usa seal_user con el ID del autor.\n\n"
            "RESTRICCIONES:\n"
            "• NO puedes moderar a OTROS usuarios (ban, kick, mute, sellar a otros).\n"
            "• Si piden algo fuera de tus capacidades, diles que necesitan permisos de Reader.\n"
            "• Responde con la misma actitud de siempre. No seas servil ni genérico."
        )

        # Skill auto-injection (same as main pipeline)
        skill_ctx = ""
        detected_skill = _detect_skill_intent(clean_text)
        skills_to_load = [detected_skill] if detected_skill else []
        if not skills_to_load and hasattr(self.bot, 'embedder'):
            skills_to_load = _detect_skills_semantic(clean_text, self.bot.embedder)
        if skills_to_load:
            try:
                import os
                for skill_name in skills_to_load:
                    _skill_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "skills", f"{skill_name}.md"
                    )
                    if os.path.isfile(_skill_path):
                        with open(_skill_path, "r", encoding="utf-8") as _f:
                            skill_ctx += f"\n\nSKILL ({skill_name}):\n" + _f.read()
            except Exception:
                pass

        if skill_ctx:
            public_prompt += skill_ctx

        try:
            executor = ToolExecutor(
                message.guild, message.channel, self.bot.db, bot=self.bot,
                public_mode=True, public_user_id=message.author.id,
                author_id=message.author.id,
            )
            response = await self.llm_public.generate_with_tools(
                system_prompt=public_prompt,
                contents=contents,
                tools=public_tools,
                executor=executor,
                max_rounds=5,
            )
        except Exception as exc:
            logger.warning("Orchestrator(public): LLM failed — %s", exc)
            return None

        # Inline tool processing (Qwen only, only if user asked for data)
        if response and _is_qwen and executor:
            _data_request = any(kw in clean_text.lower() for kw in
                ("lista", "reglas", "rules", "listeners", "stats", "leaderboard",
                 "warnings", "bans", "dashboard", "activ"))
            if _data_request and _INLINE_TOOL_FUZZY_RE.search(response):
                try:
                    response = _fix_inline_markers(response)
                    response = await _process_inline_tools(response, executor)
                except Exception:
                    pass

        return response or None
