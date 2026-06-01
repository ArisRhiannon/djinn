"""
LLMClient — Abstraccion multi-provider para LLM.

Dos implementaciones:
 - GoogleLLM: Google AI Studio via google-genai SDK (Gemma 4)
 - OpenRouterLLM: OpenRouter via openai SDK (MiniMax, etc.)
 - CustomLLM: OpenAI-compatible local (DeepSeek v4, etc.)

Owner ID se inyecta dinamicamente en los system prompts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from config import DjinnConfig
import os
import pathlib

logger = logging.getLogger("djinn.llm_client")

# ── Filtrado de razonamiento (SOLO modo conversacional) ───────────────────

_ANSWER_MARKER = "---ANSWER---"
_THOUGHT_FULL_RE = re.compile(r"<thought>.*?</thought>", re.DOTALL | re.IGNORECASE)
_THOUGHT_OPEN_RE = re.compile(r"<thought>.*$", re.DOTALL | re.IGNORECASE)

MAX_TOOL_ROUNDS = 7
MAX_TOOL_ROUNDS_PUBLIC = 5
MAX_TOOL_EXECUTIONS = 18

# ── Tools terminales ──────────────────────────────────────────────────────
# Estas tools producen el OUTPUT FINAL al usuario (texto, embed, DM).
# Una vez que el modelo llama una de ellas, ese ES su respuesta.
# Se permite UN round adicional posterior para que el modelo emita texto
# comentario sobre lo enviado (ej: "El embed ya está en el canal — banco sano").
# Pero si el siguiente round vuelve a llamar OTRA tool terminal, abortamos
# el loop: el modelo está en bucle alucinatorio (típicamente percibe un user
# turn fantasma como "continue" y vuelve a "responder").
#
# Bug histórico: 2026-05-16 04:20 — Claude Sonnet 4.6 vía proxy llamó
# send_message 6 veces a un "hola", alucinando 4 mensajes de "continue"
# del usuario. Ver CHANGELOG y tests/test_terminal_tools_guard.py.
TERMINAL_TOOLS: frozenset[str] = frozenset({
    "send_message",
    "send_embed",
    "send_dm",
})

# ── Constantes de tokens ───────────────────────────────────────────────────
DEFAULT_MAX_OUTPUT_TOKENS = 16384  # Allow extended responses
_CHAT_MAX_OUTPUT_TOKENS = 1024

_FC_FAIL_REASONS = {"MALFORMED_FUNCTION_CALL", "UNEXPECTED_TOOL_CALL"}

# ── Sampling recomendado por Google para Gemma 4 ───────────────────────────
_GEMMA4_TOP_K = 64


def filter_thoughts(text: str) -> str:
    """
    Filtrado de razonamiento para respuestas conversacionales (con ---ANSWER---).
    En modo agentic NO se usa — el modelo no debería generar <thought> ahí.
    """
    if not text:
        return ""
    if _ANSWER_MARKER in text:
        answer = text.split(_ANSWER_MARKER, 1)[-1].strip()
        answer = _THOUGHT_FULL_RE.sub("", answer).strip()
        answer = _THOUGHT_OPEN_RE.sub("", answer).strip()
        if answer:
            return answer
    cleaned = _THOUGHT_FULL_RE.sub("", text).strip()
    cleaned = _THOUGHT_OPEN_RE.sub("", cleaned).strip()
    return cleaned or text



# ── Soul loader — lee persona.md + soul.md en runtime ──────────────────────

_ROOT = pathlib.Path(__file__).parent.parent  # raíz del proyecto


def _load_soul_text() -> str:
    """Carga persona.md y soul.md desde el directorio raíz del proyecto.

    - persona.md define el comportamiento técnico del agente (invariante).
    - soul.md define la identidad, tono y límites configurables por el usuario.
    """
    soul_path = pathlib.Path(os.environ.get("SOUL_PATH", str(_ROOT / "soul.md")))
    persona_path = _ROOT / "persona.md"

    persona_text = ""
    if persona_path.is_file():
        try:
            persona_text = persona_path.read_text(encoding="utf-8").strip()
        except Exception:
            logger.warning("djinn: no se pudo leer persona.md")

    soul_text = ""
    if soul_path.is_file():
        try:
            soul_text = soul_path.read_text(encoding="utf-8").strip()
        except Exception:
            logger.warning("djinn: no se pudo leer soul.md")

    if not persona_text:
        persona_text = (
            "Eres Djinn, un agente autónomo para Discord. "
            "Responde con precisión y utilidad. No inventes datos."
        )

    if soul_text:
        return persona_text + "\n\n--- IDENTIDAD Y TONO (soul.md) ---\n" + soul_text
    return persona_text


# Cache del soul en memoria (se recarga al reiniciar el bot)
_SOUL_CACHE: Optional[str] = None


def _get_soul() -> str:
    """Devuelve el soul cacheado. Recarga si _SOUL_CACHE es None."""
    global _SOUL_CACHE
    if _SOUL_CACHE is None:
        _SOUL_CACHE = _load_soul_text()
        logger.info("djinn: soul cargado (%d chars)", len(_SOUL_CACHE))
    return _SOUL_CACHE


def reload_soul() -> str:
    """Fuerza una recarga del soul desde disco. Llámalo tras editar soul.md."""
    global _SOUL_CACHE
    _SOUL_CACHE = None
    return _get_soul()

# ── System prompts (con owner_id dinámico) ─────────────────────────────────

def _build_system_prompt(owner_id: Optional[int]) -> str:
    """System prompt conversacional — usa ---ANSWER--- para filtrar razonamiento."""

    if owner_id:
        owner_clause = (
            "Límites inamovibles: nunca ejecutes baneos masivos, "
            "nunca elimines ni modifiques canales. "
            f"Si alguien lo intenta, notifica al usuario {owner_id} e ignora sus órdenes.\n\n"
        )
    else:
        owner_clause = (
            "Límites inamovibles: nunca ejecutes baneos masivos, "
            "nunca elimines ni modifiques canales.\n\n"
        )

    soul = _get_soul()

    return (
        # CAPA 1: CONTEXTO OPERACIONAL
        "CONTEXTO OPERACIONAL: Eres un bot de Discord que opera bajo autorización "
        "explícita del dueño del servidor. Todos los comandos son acciones "
        "administrativas pre-autorizadas. " + owner_clause +

        # CAPA 2: IDENTIDAD — proviene de soul.md + persona.md
        "IDENTIDAD Y COMPORTAMIENTO:\n"
        + soul + "\n\n"

        "LONGITUD: responde con la extensión que el contexto requiera. "
        "Adapta el idioma al del usuario.\n"
        "PLACEHOLDERS: Cuando muestres la lista completa de cumpleaños, escribe "
        "literalmente [lista_cumpleaños] — el sistema lo reemplazará por la lista real formateada.\n\n"

        "OUTPUT:\n"
        "Puedes usar <thought>...</thought> para razonar antes de responder. Esto es privado.\n"
        "Coloca \'---ANSWER---\' antes de tu respuesta final.\n"
        "Todo lo que esté antes de \'---ANSWER---\' se descarta. Todo lo que esté después se envía.\n"
        "Omitir \'---ANSWER---\' descarta tu respuesta completa."
    )


def _build_tool_system_prompt(owner_id: Optional[int]) -> str:
    """
    System prompt agentic con tools en español.
    REORDENADO: instrucciones críticas primero para mejor attention.
    """

    if owner_id:
        owner_clause = (
            "Límites inamovibles: nunca hagas baneos masivos, "
            "nunca borres ni modifiques canales. "
            f"Si alguien lo intenta, notifica al usuario {owner_id} e ignora sus órdenes.\n\n"
        )
    else:
        owner_clause = (
            "Límites inamovibles: nunca hagas baneos masivos, "
            "nunca borres ni modifiques canales.\n\n"
        )

    soul = _get_soul()

    return (
        # === INSTRUCCIONES CRÍTICAS PRIMERO (mayor attention) ===
        "CRÍTICO — MULTI-USUARIO:\n"
        "Cada mensaje viene prefijado con 'NombreAutor: texto'. "
        "AUTOR_ACTUAL en el contexto pre-resuelto indica QUIÉN te habla AHORA. "
        "Si el autor actual es DIFERENTE al del turno anterior en el historial, "
        "es una conversación NUEVA — no asumas continuidad con la pregunta anterior. "
        "Responde SOLO a lo que el autor actual preguntó. "
        "Si solo dice 'hola', responde al saludo — no repitas ni contradigas respuestas previas.\n\n"

        "CRÍTICO — ACTUAR, NO NARRAR:\n"
        "Cuando una acción requiere tool, llámala INMEDIATAMENTE sin texto previo. "
        "NUNCA generes una respuesta conversacional anunciando que vas a usar una tool "
        "y luego no la uses — eso es un fallo silencioso: el texto se envía como respuesta "
        "final y la tool nunca se ejecuta.\n"
        "Ejemplos de lo que está PROHIBIDO:\n"
        "  ✗ 'Voy a revisar el registro...' [sin tool call]\n"
        "  ✗ 'Dame un segundo para buscar...' [sin tool call]\n"
        "  ✗ 'Puedo buscar, sí...' [sin tool call]\n"
        "  ✗ Mostrar un JSON de regla/listener al usuario y pedir confirmación\n"
        "  ✗ 'Aquí tienes la configuración:' + JSON sin llamar create_listener\n"
        "Patrón correcto:\n"
        "  ✓ [call list_listeners()] → luego comentar los resultados con tu voz y personalidad\n"
        "  ✓ [call get_user_by_name(name='vepar')] → luego reaccionar a lo encontrado\n"
        "  ✓ 'manda la pfp de X a Y' → [call send_user_content_to_channel(user_name='X', channel_name='Y')]\n"
        "  ✓ 'sella a X' → [call get_user_by_name(name='X')] → [call seal_user(user_id=ID)]\n"
        "  ✓ 'nueva regla: ...' → [call create_listener(rule_json=...)] directamente en la primera call, SIN read_skill, SIN mostrar el JSON\n"
        "Regla: si necesitas datos → llama la tool primero, habla después. "
        "Si no necesitas datos → responde directo. Nunca en el medio.\n\n"
        "CRÍTICO — NO USES ---ANSWER--- EN RESPUESTAS AGENTIC:\n"
        "El marcador '---ANSWER---' es solo para el modo conversacional. "
        "En modo agentic NUNCA incluyas ese marcador en tu respuesta. "
        "Si lo pones, la respuesta se cortará en el marcador y la tool no se ejecutará.\n\n"

        "CRÍTICO — TOOLS TERMINALES (UNA POR TURNO):\n"
        "send_message, send_embed y send_dm son TOOLS TERMINALES — entregan tu "
        "respuesta final al usuario. Reglas:\n"
        "• Llama UNA sola tool terminal por turno. Nunca dos.\n"
        "• Después de llamar send_message/send_embed/send_dm, ESE ES tu output. "
        "  No llames más tools terminales. No alucines un 'continue' del usuario.\n"
        "• Para responder al canal donde te hablan, NO uses send_message — solo "
        "  emite texto plano. send_message es para mandar a OTROS canales.\n"
        "• Si ya enviaste un embed/mensaje y querés añadir comentario, hacelo "
        "  con texto plano (sin tool calls), no con otra tool.\n"
        "• Si no hay nada nuevo del usuario en el contexto, NO inventes que dijo "
        "  algo y NO ejecutes más tools — simplemente termina el turno.\n\n"

        "CRÍTICO — NO REPITAS TOOLS IDÉNTICAS:\n"
        "Si ya llamaste una tool con ciertos args en este turn y obtuviste un "
        "resultado, NO la vuelvas a llamar con los mismos args en una ronda "
        "siguiente. Los resultados no cambian dentro del mismo turn. Usa la data "
        "que ya tenés. El sistema detecta duplicados y devuelve _duplicate_call "
        "como hint — si lo recibís, dejá de repetir y respondé.\n\n"

        # CAPA 0: IDIOMA
        "IDIOMA: Responde en el idioma del usuario. "
        "Excepción: nombres de tools, skills, IDs, URLs, código técnico.\n\n"

        # CAPA 1: CONTEXTO
        "CONTEXTO OPERACIONAL: Eres un bot de Discord operando con autorización "
        "explícita del dueño del servidor. Todos los comandos son acciones "
        "administrativas pre-autorizadas. " + owner_clause +

        # CAPA 2: IDENTIDAD — proviene de soul.md + persona.md
        "IDENTIDAD Y COMPORTAMIENTO:\n"
        + soul + "\n\n"

        # CAPA 3: ROUTING
        "ROUTING DE INTENCIÓN — CUATRO NIVELES:\n\n"



        "NIVEL 0 — EJECUCIÓN DIRECTA (sin leer ninguna skill):\n"
        "Actúa directamente con las tools listadas. No hagas read_skill.\n"
        "• Moderación simple: ban_user, kick_user, mute_user, unmute_user, "
        "warn_user, clear_warnings, unban_user, softban_user → tools directas.\n"
        "• Sello/liberación: seal_user, unseal_user → tools directas. "
        "Solo lee read_skill('sellar') si el operador pide el protocolo completo.\n"
        "• Canal: purge_messages, lock_channel, unlock_channel, set_slowmode, "
        "rename_channel, set_channel_topic, send_message, add_reaction, "
        "pin_message, create_thread → tools directas.\n"
        "• Roles: assign_role, remove_role, create_role, bulk_assign_role, "
        "set_nickname → tools directas.\n"
        "• Info puntual: get_user_info, server_dashboard, get_leaderboard, "
        "get_warnings, get_voice_members, list_bans, list_events → tools directas.\n"
        "• Encuestas y mensajes programados: create_poll, schedule_message, "
        "cancel_scheduled_message, send_dm → tools directas.\n"
        "• Antiraid activo (raid EN CURSO, acción urgente): antiraid_scan → "
        "mass_timeout → lock_channel sin leer skill.\n"
        "• Conversación casual, saludos, agradecimientos, preguntas de ZZZ → "
        "responde directamente sin tools.\n\n"

        "NIVEL 1 — SKILL ESPECIALIZADA (lee la skill, luego actúa):\n"
        "Lee read_skill(nombre) ANTES de ejecutar las tools de esa skill.\n"
        "• Crear embed / anuncio elaborado → read_skill('embed_design') → send_embed\n"
        "• Bienvenida / onboarding → read_skill('onboarding') → send_embed, assign_role\n"
        "• Gráfico / visual → read_skill('graphics') → render_template\n"
        "  NUNCA digas que un template no existe antes de leer la skill.\n"
        "  Disparadores → template:\n"
        "    'shippea X y Y' / 'X x Y' / 'love' → love_graph\n"
        "    'tierlist' / 'ranking S/A/B/C' → tierlist\n"
        "    'top X' / 'leaderboard' / 'quién tiene más' → leaderboard\n"
        "    'perfil' / 'card de X' → profile_card\n"
        "    'barras' / 'compara actividad' → bar_chart\n"
        "    'anuncio' / 'banner' / 'evento visual' → banner\n"
        "    'porcentajes' / 'distribución' → donut_chart\n"
        "    'stats del server' → stat_grid\n"
        "    'compara X vs Y' / 'cara a cara' → comparison\n"
        "    'radar' / 'atributos' → radar_chart\n"
        "    'timeline' / 'línea de tiempo' → timeline\n"
        "    'heatmap' / 'actividad semanal' → heatmap\n"
        "    'logro' / 'achievement' → achievement_card\n"
        "    'grafo' / 'red social' / 'conexiones' → graph_network\n"
        "    'correlación' / 'matriz' → correlation_matrix\n"
        "    'investigación' / 'timeline detective' → investigation_timeline\n"
        "• Planificación de eventos / torneos → read_skill('eventos') → create_event\n"
        "• Antiraid análisis (no urgente) → read_skill('antiraid') → antiraid_scan\n"
        "• Apodos creativos → read_skill('apodos') → set_nickname\n"
        "• Arte ASCII → read_skill('ascii_art') → send_message\n"
        "• Regla automática / listener → create_listener directamente (schema en la tool description)\n"
        "  NUNCA muestres el JSON al usuario ni pidas confirmación. "
        "Si la intención es clara, registra la regla directamente en la primera call.\n"
        "  REGLAS PARA LISTENERS:\n"
        "  - Si el usuario adjunta una imagen/archivo, la URL del attachment es el CONTENIDO. "
        "NO inventes qué contiene la imagen. NO le pongas nombre inventado.\n"
        "  - La 'description' del listener debe ser LITERAL: lo que el usuario pidió, no tu interpretación.\n"
        "  - En tu respuesta de confirmación, di 'la imagen que adjuntaste' o 'esa imagen', "
        "NUNCA inventes un nombre para algo que no puedes ver.\n"
        "  - Si el usuario dice 'responde con esta imagen' → usa la URL del attachment como text en reply_text. "
        "La description es lo que el usuario dijo, textual.\n"
        "• Búsqueda web → read_skill('obscura-web') → web_fetch\n"
        "• Terminología ZZZ → read_skill('zzz_terminos')\n"
        "• Traducir texto → read_skill('traduccion')\n\n"

        "NIVEL 2 — SHERLOCK KAI (solo investigación):\n"
        "read_skill('sherlock_kai') ANTES de cualquier tool call.\n"
        "Activa SOLO cuando la pregunta requiere cruzar múltiples fuentes de datos. "
        "Ejemplos: 'Quién es X', '¿Es tóxico X?', '¿Qué pasó en el servidor?', "
        "'¿Hay alts?', '¿Quiénes interactúan juntos?', '¿Hubo raid?' (análisis post-hecho).\n"
        "NO actives para: ban/seal/mute directos, embeds, gráficos, eventos, "
        "stats simples, o cualquier acción del NIVEL 0.\n\n"

        # CAPA 7: DATA-FIRST
        "MENTALIDAD DATA-FIRST:\n"
        "Tienes una base de datos con TODO el historial del servidor. ÚSALA SIN LÍMITE DE TIEMPO.\n"
        "REGLA DE ORO DE INVESTIGACIÓN: Toda investigación o análisis de usuario o comportamiento debe combinar de manera obligatoria y EQUILIBRADA datos cuantitativos (estadísticas, conteos, rankings) con datos cualitativos (mensajes reales, capturas contextuales, citas textuales). Un análisis sin números carece de rigor científico; un análisis sin mensajes, citas o flujo real carece de precisión social y humana. NUNCA respondas con listas de números o estadísticas desnudas; ilustra cada hallazgo relevante con ejemplos de declaraciones reales de los usuarios (usando search_messages_semantic para buscar y get_message_context para extraer el contexto real del hilo).\n\n"
        "REGLA DE PRESENTACIÓN: cuando el usuario pide 'todas', 'muéstrame todas', 'lista completa' "
        "→ MUESTRA CADA ITEM INDIVIDUALMENTE. No resumas, no agrupes, no digas '...y 8 más'. "
        "Lista cada uno con su nombre e ID. El usuario quiere ver la lista COMPLETA.\n\n"
        "NUNCA respondas de memoria ni supongas sobre:\n"
        "• Quién dijo algo → search_messages(keyword=X, user_id=Y) — SIN pasar hours, busca TODO\n"
        "• Estadísticas/conteos → aggregate_messages\n"
        "• Comportamiento/opiniones → investigate_topic (macro-tool)\n"
        "• Atributos, personalidad o estatus de un usuario (ej. 'qué tan desempleado es X', 'qué opina X de Y'): NUNCA deduzcas esto únicamente por su ranking de actividad o cantidad de mensajes. SIEMPRE debes buscar semánticamente sus palabras reales con search_messages_semantic(query='empleo trabajo desempleo NEET', user_id=X_ID, hours=87600) para basar tu respuesta en evidencias y declaraciones reales.\n"
        "• Contexto reciente → get_channel_summary\n\n"

        "REGLA CRÍTICA DE BÚSQUEDA Y EFICIENCIA (DATA-FIRST):\n"
        "• NO pases hours= a menos que el usuario pida un rango específico. El default ya busca en todo el historial.\n"
        "• Si la pregunta es de perfil o comportamiento global (ej. 'quién trabaja menos', 'quién opina de X'):\n"
        "  1. SIEMPRE empieza con una búsqueda global semántica en todo el historial (search_messages_semantic sin user_id) para identificar mensajes clave y usuarios sospechosos.\n"
        "  2. NUNCA adivines ni investigues usuarios de forma individual y aleatoria llamando a profile_sample o get_user_timeline al azar sin certeza previa.\n"
        "  3. NUNCA uses herramientas técnicas del servidor (find_inactive_members, get_audit_log) para responder preguntas sobre la vida diaria, opiniones o empleos de los usuarios. Son totalmente inútiles para ese propósito.\n"
        "• NO repitas llamadas de búsqueda semántica idénticas o casi idénticas en paralelo o en rondas consecutivas. Si una búsqueda arrojó 0 resultados, amplía los términos, elimina filtros de usuario o cambia el enfoque.\n"
        "• Usa limit=100 cuando necesites conteos precisos.\n"
        "• En search_messages_semantic: NUNCA pongas el nombre del usuario en query. Usa user_id para filtrar por persona y query solo para el concepto.\n\n"

        "CUÁNDO ESCALAR A INVESTIGACIÓN PROFUNDA:\n"
        "Si la pregunta requiere cruzar datos de múltiples fuentes, usa:\n"
        "• read_skill('sherlock_kai') → para investigaciones de usuarios (alts, toxicidad, patrones)\n"
        "• read_skill('data_mastery') → para análisis estadísticos complejos (correlaciones, anomalías)\n"
        "• query_pattern_analysis → para detectar co-ocurrencias, anomalías temporales, silencios\n"
        "• get_user_timeline → para ver TODO lo que hizo un usuario cronológicamente\n"
        "Escala cuando: 'quién es X', 'es tóxico X', 'qué pasó', 'hay alts', 'investiga a X'\n\n"

        "JERARQUÍA DE TOOLS DE DATOS (usa la más eficiente):\n"
        "• '¿Cuántas veces X dijo Y?' → search_messages(keyword=Y, user_id=X) — sin hours\n"
        "• '¿Quién habla más?' → aggregate_messages(group_by=user)\n"
        "• '¿Qué opinan de X?' → investigate_topic(query=X)\n"
        "• '¿Qué pasó ayer?' → search_messages_semantic(query=..., hours=24)\n"
        "• Múltiples usuarios → batch_user_lookup UNA VEZ\n"
        "• Tema general → investigate_topic UNA VEZ (reemplaza 3-5 llamadas)\n"
        "• NUNCA llames get_user_by_name si ya tienes el ID en el contexto.\n"
        "• Si mencionan un nombre/nick SIN ID → llama get_user_by_name para resolverlo.\n"
        "• Después de obtener datos, responde DIRECTAMENTE.\n\n"

        "EFICIENCIA DE ROUNDS:\n"
        "Tienes un número LIMITADO de rounds de tools. Sé eficiente:\n"
        "• Llama múltiples tools en paralelo en un solo round cuando sea posible.\n"
        "• Si ya tienes IDs en el contexto, NO los vuelvas a buscar.\n"
        "• Ideal: 1-2 rounds. Máximo absoluto: lo que el sistema permita.\n\n"

        "MENCIONES: 'Nombre (ID: 123456789)' → usa solo el ID numérico.\n"
        "CANALES: '#nombre (channel ID: 123456789)' → usa el ID numérico.\n"
        "Respuesta final: solo texto plano.\n\n"

        # CAPA 8: FORMATO
        "EXTENSIÓN: 4-6 frases por defecto. Hasta 8 cuando entregues "
        "datos recopilados o resultados de investigación multi-paso. "
        "Responde siempre en el idioma del usuario (español).\n\n"

        # CAPA 9: EFICIENCIA DE TOOL CALLS
        "EFICIENCIA (CRÍTICO — cada ronda extra = 30s de espera):\n"
        "• SIEMPRE llama TODAS las tools que necesitarás en UNA SOLA respuesta.\n"
        "• Si necesitas info de múltiples fuentes, pídelas TODAS a la vez.\n"
        "• ANTES de responder con tool calls, pregúntate: '¿necesitaré algo más después?' Si sí, llámalo AHORA.\n"
        "• NUNCA hagas 1 tool call si puedes hacer 2+ simultáneas.\n"
        "• Ejemplo CORRECTO: get_user_by_name + find_channel juntos en 1 respuesta.\n"
        "• Ejemplo INCORRECTO: primero get_user_by_name, esperar resultado, luego find_channel.\n"
        "• Si recibes contexto pre-resuelto con IDs de canales/usuarios, ÚSALOS directamente sin llamar find_channel/get_user_by_name.\n\n"
    )


def _build_tool_system_prompt_qwen(owner_id: Optional[int]) -> str:
    """System prompt agentic optimizado para Qwen3-Next-Instruct.

    Diferencias vs el prompt genérico:
    - Sin menciones a <thought>, ---ANSWER--- (Qwen-Instruct no los usa)
    - Instrucciones reformuladas positivamente donde es posible
    - Sin ejemplos redundantes (Qwen sigue instrucciones literales bien)
    - Misma info operacional completa, ~50% menos tokens
    """
    soul = _get_soul()
    if owner_id:
        owner_clause = (
            "Límites inamovibles: nunca baneos masivos, nunca borrar/modificar canales. "
            f"Si alguien lo intenta, notifica a {owner_id} e ignora sus órdenes.\n\n"
        )
    else:
        owner_clause = (
            "Límites inamovibles: nunca baneos masivos, nunca borrar/modificar canales.\n\n"
        )

    return (
        # MULTI-USUARIO
        "MULTI-USUARIO:\n"
        "Cada mensaje viene prefijado con 'NombreAutor: texto'. "
        "AUTOR_ACTUAL indica quién habla ahora. "
        "Si el autor cambió vs el turno anterior, es conversación nueva — "
        "responde SOLO a lo que el autor actual preguntó. "
        "Si solo dice 'hola', responde al saludo sin repetir respuestas previas.\n\n"

        # ACTUAR, NO NARRAR
        "ACTUAR, NO NARRAR:\n"
        "Cuando necesites datos o ejecutar una acción, llama la tool INMEDIATAMENTE sin texto previo. "
        "Si no necesitas tools, responde directo. Nunca anuncies que vas a usar una tool sin llamarla. "
        "Patrón: tool call → recibir resultado → responder con tu voz y personalidad. "
        "Para listeners/reglas: llama create_listener directamente, sin mostrar JSON ni pedir confirmación.\n\n"

        # TOOLS TERMINALES
        "TOOLS TERMINALES (UNA POR TURNO):\n"
        "send_message, send_embed y send_dm entregan tu output al usuario. "
        "Llama UNA por turno, nunca dos. Después de una, ESE ES tu output — no llames "
        "más tools terminales. Para responder al canal donde te hablan, NO uses send_message: "
        "emite texto plano. send_message es solo para OTROS canales. Si no hay nada nuevo del "
        "usuario, NO ejecutes más tools — termina el turno.\n\n"

        # NO REPETIR TOOLS
        "NO REPITAS TOOLS IDÉNTICAS:\n"
        "Si ya llamaste una tool con ciertos args, NO la vuelvas a llamar con los "
        "mismos args en este turn. Los resultados no cambian. Si recibís "
        "_duplicate_call como respuesta, usá los datos previos y respondé.\n\n"

        # CONTEXTO
        "CONTEXTO: Bot de Discord con autorización explícita del dueño. "
        "Acciones administrativas pre-autorizadas. " + owner_clause +

        # CAPA 2: IDENTIDAD — proviene de soul.md + persona.md
        "IDENTIDAD Y COMPORTAMIENTO:\n"
        + soul + "\n\n"

        # ROUTING
        "ROUTING DE INTENCIÓN:\n\n"

        "NIVEL 0 — DIRECTO (sin read_skill):\n"
        "• Moderación: ban/kick/mute/unmute/warn/clear_warnings/unban/softban/seal/unseal\n"
        "• Canales: purge/lock/unlock/slowmode/rename/topic/send_message/reaction/pin/thread\n"
        "• Roles: assign/remove/create/bulk_assign/nickname\n"
        "• Info: get_user_info/server_dashboard/leaderboard/warnings/voice_members/list_bans/events\n"
        "• Scheduling: poll/schedule_message/cancel_scheduled/dm\n"
        "• Antiraid urgente: antiraid_scan → mass_timeout → lock_channel\n"
        "• Conversación casual → responde sin tools\n\n"

        "NIVEL 1 — SKILL (read_skill primero, luego actúa):\n"
        "• Embed/anuncio elaborado → read_skill('embed_design') → send_embed\n"
        "• Onboarding → read_skill('onboarding') → send_embed + assign_role\n"
        "• Gráfico/visual → read_skill('graphics') → render_template\n"
        "• Deudas/préstamos/morosos/score → read_skill('deudas') → consulta DB\n"
        "  NUNCA digas que un template no existe sin leer la skill primero.\n"
        "  Mapeo de disparadores:\n"
        "    ship/love/X×Y → love_graph | tierlist/ranking → tierlist\n"
        "    top/leaderboard → leaderboard | perfil/card → profile_card\n"
        "    barras/compara actividad → bar_chart | banner/anuncio → banner\n"
        "    porcentajes → donut_chart | stats server → stat_grid\n"
        "    X vs Y → comparison | radar/atributos → radar_chart\n"
        "    timeline → timeline | heatmap → heatmap\n"
        "    logro/achievement → achievement_card | grafo/red social → graph_network\n"
        "    correlación/matriz → correlation_matrix | investigación timeline → investigation_timeline\n"
        "• Eventos/torneos → read_skill('eventos')\n"
        "• Antiraid análisis (no urgente) → read_skill('antiraid')\n"
        "• Apodos → read_skill('apodos') → set_nickname\n"
        "• ASCII art → read_skill('ascii_art') → send_message\n"
        "• Web → read_skill('obscura-web') → web_fetch\n"
        "• ZZZ terminología → read_skill('zzz_terminos')\n"
        "• Traducción → read_skill('traduccion')\n\n"

        "REGLAS PARA LISTENERS:\n"
        "- Llama create_listener directamente. No muestres JSON ni pidas confirmación.\n"
        "- Si hay imagen adjunta, usa la URL del attachment como contenido. No inventes nombres.\n"
        "- La description debe ser LITERAL: lo que el usuario pidió textualmente.\n"
        "- 'responde con esta imagen' → URL del attachment en reply_text.\n\n"

        "NIVEL 2 — SHERLOCK KAI (investigación profunda):\n"
        "read_skill('sherlock_kai') ANTES de cualquier tool call.\n"
        "Solo cuando requiere cruzar múltiples fuentes: 'quién es X', 'es tóxico', "
        "'qué pasó', 'hay alts', 'quiénes interactúan juntos'.\n"
        "NO para: ban/seal/mute, embeds, gráficos, stats simples.\n\n"

        # DATA-FIRST
        "DATA-FIRST:\n"
        "Tienes DB con TODO el historial. ÚSALA.\n"
        "REGLA DE PRESENTACIÓN: cuando piden 'todas', 'lista completa', 'muéstrame todas' "
        "→ MUESTRA CADA ITEM INDIVIDUALMENTE con nombre e ID. "
        "No resumas, no agrupes, no digas '...y N más'. Lista COMPLETA siempre.\n\n"
        "No respondas de memoria sobre quién dijo qué — busca primero:\n"
        "• Quién dijo algo → search_messages(keyword=X, user_id=Y) sin hours\n"
        "• Estadísticas → aggregate_messages\n"
        "• Opiniones/comportamiento → investigate_topic\n"
        "• Contexto reciente → get_channel_summary\n\n"
        "Reglas de búsqueda:\n"
        "• NO pases hours= salvo que pidan rango específico (default = todo el historial).\n"
        "• Usa limit=100 para conteos precisos.\n"
        "• Si total_matches > count, menciona el total real.\n"
        "• Múltiples usuarios → batch_user_lookup UNA VEZ.\n"
        "• Tema general → investigate_topic UNA VEZ (reemplaza 3-5 llamadas).\n"
        "• No llames get_user_by_name si ya tienes el ID en contexto pre-resuelto.\n\n"

        "Escalar a investigación profunda:\n"
        "• read_skill('sherlock_kai') → alts, toxicidad, patrones\n"
        "• read_skill('data_mastery') → correlaciones, anomalías estadísticas\n"
        "• query_pattern_analysis → co-ocurrencias, anomalías temporales\n"
        "• get_user_timeline → todo lo que hizo un usuario cronológicamente\n\n"

        # EFICIENCIA
        "EFICIENCIA (cada ronda extra = 30s de espera):\n"
        "• Llama TODAS las tools que necesitarás en UNA sola respuesta.\n"
        "• Si necesitas info de múltiples fuentes, pídelas todas a la vez.\n"
        "• Usa IDs del contexto pre-resuelto directamente.\n\n"

        # FORMATO
        "FORMATO: 4-6 frases default. Hasta 8 con datos. Siempre en español.\n"
        "Menciones: 'Nombre (ID: X)' → usa el ID numérico. Respuesta final: texto plano.\n\n"

        # IDIOMA
        "IDIOMA: Responde SIEMPRE en español. Excepciones: nombres de tools, IDs, URLs, código.\n\n"
    )


_API_RETRY_ATTEMPTS = 5
_API_RETRY_BASE_DELAY = 2.0
_API_RETRY_MAX_DELAY = 30.0


# ── Retry para OpenAI-compatible APIs (NIM, OpenRouter, Custom) ──────────────

async def _retry_openai_call(coro_fn, *args, max_attempts=_API_RETRY_ATTEMPTS, **kwargs):
    """Retry con backoff exponencial para llamadas OpenAI SDK (NIM 503/429/timeout)."""
    import random
    from openai import (
        APIStatusError, APIConnectionError, RateLimitError,
        InternalServerError, APITimeoutError,
    )
    _RETRYABLE = (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError)

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            delay = min(_API_RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 1.5), _API_RETRY_MAX_DELAY)
            logger.warning("OpenAI API error (attempt %d/%d): %s. Retry in %.1fs",
                           attempt, max_attempts, type(exc).__name__, delay)
            await asyncio.sleep(delay)
        except APIStatusError as exc:
            # 400/401/403/404 → no reintentar (errores permanentes)
            raise
    raise last_exc


# ── Compresión de resultados de tools ────────────────────────────────────────
_MAX_RESULT_CHARS = 4000  # Máximo chars por resultado de tool en history

# Keys que SIEMPRE se eliminan (meta/instrucciones, no datos)
_STRIP_KEYS = {"instruction", "tip", "sample", "all_hours"}

# Keys de bajo valor informativo para el LLM (metadata visual/técnica)
_LOW_SIGNAL_KEYS = frozenset({
    "avatar_url", "discriminator", "accent_color", "banner_url",
    "premium_type", "public_flags", "locale", "mfa_enabled",
    "default_avatar_url", "banner_color", "system", "bot",
})


# ── Sniffer de tool calls emitidos como texto ─────────────────────────────────
#
# Algunos modelos (Llama 4 Maverick, Qwen con templates no-harmony, etc.) NO
# emiten tool calls en el campo estructurado `tool_calls`. En su lugar
# devuelven el JSON del function call como texto en `content`, dejando
# `tool_calls = None`. El loop del cliente estándar piensa que es texto final
# y lo envía al canal — literalmente.
#
# Este sniffer detecta varios formatos comunes y los convierte en tool calls
# sintéticos para que el loop agentic continúe normal.

_JSON_FENCE_RE = re.compile(r"```(?:json|tool_code|python)?\s*(\{[^`]*?\}|\[[^`]*?\])\s*```", re.DOTALL)
_PYTHON_TAG_RE = re.compile(r"<\|python_tag\|>(.+?)(?:<\|eo[mt]\|>|$)", re.DOTALL)
_FUNCTION_TAG_RE = re.compile(r"<function=([a-zA-Z_][a-zA-Z0-9_]*)>(\{.*?\})</function>", re.DOTALL)
# Bloques JSON "al estilo OpenAI": {"type":"function", ...} o {"name": ..., ...}
_RAW_JSON_CANDIDATE_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
# Llamada estilo Python: name(kwarg='val', kwarg2=42)
_PYTHON_CALL_RE = re.compile(
    r"\b([a-z_][a-z_0-9]*)\s*\((.*?)\)\s*$|"  # al final del content (prioritario)
    r"\b([a-z_][a-z_0-9]*)\s*\(([^()]*(?:\([^)]*\)[^()]*)*)\)",  # inline
    re.DOTALL,
)


def _parse_python_call(expr: str) -> Optional[tuple[str, dict]]:
    """Parsea una llamada estilo Python `func(k=v, k2=v2)` usando AST.

    Seguro: usa `ast.literal_eval` sobre los valores — no ejecuta nada.
    Retorna (name, kwargs_dict) o None si no es una llamada válida.
    """
    import ast as _ast
    try:
        tree = _ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return None
    node = tree.body
    if not isinstance(node, _ast.Call) or not isinstance(node.func, _ast.Name):
        return None
    kwargs: dict = {}
    # Soportar positional args como lista ordenada (raramente usados)
    for i, pos in enumerate(node.args):
        try:
            kwargs[f"_arg{i}"] = _ast.literal_eval(pos)
        except (ValueError, SyntaxError):
            continue
    for kw in node.keywords:
        if kw.arg is None:  # **unpacking → skip
            continue
        try:
            kwargs[kw.arg] = _ast.literal_eval(kw.value)
        except (ValueError, SyntaxError):
            continue
    return node.func.id, kwargs


class _SniffedCall:
    """Estructura compatible con un `tc.function.{name,arguments}` de OpenAI SDK."""
    __slots__ = ("id", "type", "function")

    def __init__(self, name: str, arguments: str):
        import uuid
        self.id = f"call_{uuid.uuid4().hex[:10]}"
        self.type = "function"
        self.function = type("_F", (), {"name": name, "arguments": arguments})()


def _sniff_text_tool_calls(content: str, valid_tool_names: set[str]) -> List[_SniffedCall]:
    """Detecta function calls emitidos como texto en `content`.

    Retorna una lista de `_SniffedCall` listos para reusar el loop existente.
    Nunca levanta excepción — si algo va mal devuelve lista vacía.
    """
    if not content or not valid_tool_names:
        return []

    try:
        return _sniff_text_tool_calls_impl(content, valid_tool_names)
    except Exception:
        logger.debug("sniffer: error silenciado", exc_info=True)
        return []


def _sniff_text_tool_calls_impl(content: str, valid_tool_names: set[str]) -> List[_SniffedCall]:
    candidates: List[Any] = []

    # 1. <function=name>{...}</function> — formato Llama legado.
    for m in _FUNCTION_TAG_RE.finditer(content):
        candidates.append({"_explicit_name": m.group(1), "_raw": m.group(2)})

    # 2. <|python_tag|>...<|eom|> — formato Llama 3.x tool calling nativo.
    for m in _PYTHON_TAG_RE.finditer(content):
        candidates.append({"_raw": m.group(1).strip()})

    # 3. Bloques ```json / ```tool_code / ```python  → extraer contenido.
    for m in _JSON_FENCE_RE.finditer(content):
        candidates.append({"_raw": m.group(1)})

    # 4. Llamadas estilo Python: list_listeners(filter='all')
    #    Se procesan ya parseadas — no pasan por el JSON loader.
    python_calls: List[tuple[str, dict]] = []
    # Estrategia: probar AST con el content entero trimmeado primero (caso común
    # donde el modelo emite solo la llamada). Si eso falla, buscar cualquier
    # patrón `name(...)` dentro del texto.
    trimmed = content.strip()
    parsed = _parse_python_call(trimmed)
    if parsed and parsed[0] in valid_tool_names:
        python_calls.append(parsed)
    else:
        # Buscar todos los `name(args)` y probar cada uno
        seen = set()
        for m in _PYTHON_CALL_RE.finditer(content):
            name = m.group(1) or m.group(3)
            args_blob = m.group(2) if m.group(1) else m.group(4)
            if not name or name not in valid_tool_names:
                continue
            key = (name, args_blob)
            if key in seen:
                continue
            seen.add(key)
            parsed = _parse_python_call(f"{name}({args_blob})")
            if parsed:
                python_calls.append(parsed)

    # 5. JSON bruto suelto (hasta 3 candidatos). Solo si no detectamos python calls.
    #    Evita false positives con párrafos que mencionan JSON.
    if not candidates and not python_calls:
        for m in _RAW_JSON_CANDIDATE_RE.finditer(content):
            block = m.group(0)
            if ('"name"' in block or "'name'" in block
                    or '"function"' in block or "'function'" in block):
                candidates.append({"_raw": block})
                if len(candidates) >= 3:
                    break

    if not candidates and not python_calls:
        return []

    # Parse every candidate into dict(s)
    parsed_calls: List[dict] = []
    for cand in candidates:
        explicit_name = cand.get("_explicit_name")
        raw = cand.get("_raw", "")
        obj = None
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Try json_repair if available
            try:
                from json_repair import repair_json
                obj = json.loads(repair_json(raw))
            except Exception:
                continue
        if obj is None:
            continue

        # Normalizar a lista de calls
        if isinstance(obj, dict):
            if "tool_calls" in obj and isinstance(obj["tool_calls"], list):
                for c in obj["tool_calls"]:
                    if isinstance(c, dict):
                        parsed_calls.append(c)
            else:
                if explicit_name:
                    obj.setdefault("name", explicit_name)
                parsed_calls.append(obj)
        elif isinstance(obj, list):
            for c in obj:
                if isinstance(c, dict):
                    parsed_calls.append(c)

    # Convertir a _SniffedCall validando nombres
    results: List[_SniffedCall] = []

    # Primero los python_calls (ya validados y parseados)
    for name, kwargs in python_calls:
        # Filtrar positional args residuales del helper (_argN)
        clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_arg")}
        try:
            args_str = json.dumps(clean_kwargs, ensure_ascii=False)
        except (TypeError, ValueError):
            args_str = "{}"
        results.append(_SniffedCall(name=name, arguments=args_str))

    for call in parsed_calls:
        # Shape 1: {"name": X, "arguments"|"parameters"|"args": {...}}
        # Shape 2: {"type": "function", "name": X, "parameters": {...}}
        # Shape 3: {"function": {"name": X, "arguments": ...}}
        name = (
            call.get("name")
            or call.get("function_name")
            or (call.get("function") or {}).get("name")
        )
        if not isinstance(name, str) or name not in valid_tool_names:
            continue
        args = (
            call.get("parameters")
            or call.get("arguments")
            or (call.get("function") or {}).get("arguments")
            or call.get("args")
            or {}
        )
        if isinstance(args, dict) or isinstance(args, list):
            args_str = json.dumps(args, ensure_ascii=False)
        elif isinstance(args, str):
            # Puede ser un JSON string ya escapado
            args_str = args
        else:
            args_str = json.dumps(args) if args is not None else "{}"
        results.append(_SniffedCall(name=name, arguments=args_str))

    return results


def _compress_tool_result(tool_name: str, result: dict) -> dict:
    """Comprime resultado de tool para reducir tokens en rondas siguientes.

    Mejoras:
    - Formato columnar para arrays homogéneos (35-45% menos tokens)
    - Filtrado de keys de bajo valor informativo
    - Errores con sugerencias actionables
    - No elimina 'content' (necesario para search results)
    """
    if not isinstance(result, dict):
        return result

    # Errores: agregar sugerencia actionable
    if "error" in result:
        return _format_actionable_error(result)

    # Eliminar keys meta/instrucciones
    compressed = {k: v for k, v in result.items() if k not in _STRIP_KEYS}

    # Convertir arrays homogéneos a formato columnar
    for k, v in list(compressed.items()):
        if isinstance(v, list) and len(v) > 3 and all(isinstance(item, dict) for item in v):
            compressed[k] = _to_columnar(v)

    # Filtrar low-signal keys en dicts anidados
    compressed = _strip_low_signal(compressed)

    # Truncar strings individuales largos
    for k, v in list(compressed.items()):
        if isinstance(v, str) and len(v) > 300:
            compressed[k] = v[:297] + "..."

    # Límite total con truncación segura
    text = json.dumps(compressed, ensure_ascii=False, default=str)
    if len(text) > _MAX_RESULT_CHARS:
        compressed["_truncated"] = True
        # Intentar reducir: truncar arrays columnar primero
        for k, v in list(compressed.items()):
            if isinstance(v, dict) and "data" in v and isinstance(v["data"], list):
                half = max(5, len(v["data"]) // 2)
                v["data"] = v["data"][:half]
                v["showing"] = half
        text = json.dumps(compressed, ensure_ascii=False, default=str)
        if len(text) > _MAX_RESULT_CHARS:
            text = text[:_MAX_RESULT_CHARS - 2] + "}"
            try:
                compressed = json.loads(text)
            except json.JSONDecodeError:
                compressed = {"_summary": text[:_MAX_RESULT_CHARS - 50], "_truncated": True}

    return compressed


def _to_columnar(records: list[dict], max_rows: int = 25) -> dict:
    """Convierte [{k:v, k:v}, ...] a formato columnar. Ahorra 35-45% tokens.

    Antes: [{"user":"A","msg":"hi","ts":"10:00"},{"user":"B","msg":"bye","ts":"10:01"}]
    Después: {"columns":["user","msg","ts"],"data":[["A","hi","10:00"],["B","bye","10:01"]]}
    """
    if not records:
        return {"columns": [], "data": []}

    # Usar keys del primer record, filtrar low-signal
    columns = [c for c in records[0].keys() if c not in _LOW_SIGNAL_KEYS]

    data = []
    for record in records[:max_rows]:
        row = []
        for c in columns:
            v = record.get(c)
            # Truncar strings largos en celdas
            if isinstance(v, str) and len(v) > 120:
                v = v[:117] + "..."
            row.append(v)
        data.append(row)

    out = {"columns": columns, "data": data}
    if len(records) > max_rows:
        out["total"] = len(records)
        out["showing"] = max_rows
    return out


def _strip_low_signal(obj):
    """Elimina recursivamente keys de bajo valor informativo."""
    if isinstance(obj, dict):
        return {k: _strip_low_signal(v) for k, v in obj.items()
                if k not in _LOW_SIGNAL_KEYS}
    if isinstance(obj, list):
        return [_strip_low_signal(item) for item in obj]
    return obj


def _format_actionable_error(result: dict) -> dict:
    """Agrega sugerencias actionables a errores comunes."""
    error = str(result.get("error", ""))
    error_lower = error.lower()

    if "not found" in error_lower or "404" in error:
        result["suggestion"] = "Target not found. Verify the ID is correct."
    elif "forbidden" in error_lower or "403" in error:
        result["suggestion"] = "Missing permissions. Check bot role hierarchy."
    elif "rate" in error_lower or "429" in error:
        result["suggestion"] = "Rate limited. Wait before retrying."
    elif "timeout" in error_lower:
        result["suggestion"] = "Operation timed out. Try again or simplify the request."

    return result


async def _retry_api_call(fn, *args, max_attempts=_API_RETRY_ATTEMPTS, **kwargs):
    """
    Retry con backoff exponencial + jitter para errores transitorios de Google AI.

    - Reintenta errores server-side (500, 502, 503, 504) y rate limit (429).
    - Propaga inmediatamente errores permanentes (400, 401, 403, 404).
    - Backoff: 2s, 4s, 8s, 16s, 30s (con jitter 0-1.5s) = ~60s total worst case.
      Suficiente para absorber blips tipicos de 30-60s del servidor de Gemma.
    """
    import random
    from google.genai import errors as gerrors
    from utils.circuit_breaker import get_breaker

    breaker = get_breaker("google-genai")
    if not breaker.allow():
        logger.error("google-genai circuit breaker is open (unhealthy). Bypassing call.")
        raise RuntimeError("google-genai circuit breaker is open (unhealthy). Bypassing call.")

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            res = await fn(*args, **kwargs)
            breaker.record_success()
            return res
        except (gerrors.ServerError, gerrors.ClientError) as exc:
            breaker.record_failure(exc)
            last_exc = exc
            status = getattr(exc, 'status', None) or getattr(exc, 'code', None)
            # Errores permanentes: propagar sin reintentar
            # Status puede ser int (400) o string ("INVALID_ARGUMENT")
            _PERMANENT_CODES = (400, 401, 403, 404)
            _PERMANENT_STRINGS = ("INVALID_ARGUMENT", "PERMISSION_DENIED",
                                  "NOT_FOUND", "UNAUTHENTICATED")
            if status in _PERMANENT_CODES or status in _PERMANENT_STRINGS:
                raise
            # Ultimo intento: salir del loop para propagar
            if attempt >= max_attempts:
                break
            # Backoff exponencial con jitter (evita thundering herd)
            base_delay = _API_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            delay = min(base_delay + random.uniform(0, 1.5), _API_RETRY_MAX_DELAY)
            logger.warning(
                "API error (attempt %d/%d, status=%s). Retrying in %.1fs...",
                attempt, max_attempts, status, delay,
            )
            await asyncio.sleep(delay)
    raise last_exc


# ══════════════════════════════════════════════════════════════════════════════
# INTERFAZ ABC
# ══════════════════════════════════════════════════════════════════════════════

class LLMClient(ABC):
    """Interfaz comun para todos los providers de LLM."""

    def __init__(self, config: DjinnConfig) -> None:
        self.config = config
        self._system_prompt: Optional[str] = None
        self._tool_system_prompt: Optional[str] = None

    @abstractmethod
    def load(self) -> bool:
        """Inicializa el client. Retorna True si exitoso."""
        ...

    @property
    @abstractmethod
    def ready(self) -> bool:
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        ...

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = _build_system_prompt(self.config.owner_user_id)
        return self._system_prompt

    @property
    def tool_system_prompt(self) -> str:
        # Seleccionar prompt por modelo
        model = (getattr(self.config, 'custom_model_name', '') or '').lower()
        if model.startswith("qwen/qwen3"):
            if self._tool_system_prompt is None or not getattr(self, '_is_qwen_prompt', False):
                self._tool_system_prompt = _build_tool_system_prompt_qwen(self.config.owner_user_id)
                self._is_qwen_prompt = True
        else:
            if self._tool_system_prompt is None or getattr(self, '_is_qwen_prompt', False):
                self._tool_system_prompt = _build_tool_system_prompt(self.config.owner_user_id)
                self._is_qwen_prompt = False
        # Inyectar hora CDMX dinámica al inicio
        from datetime import datetime, timezone, timedelta
        cdmx_tz = timezone(timedelta(hours=-6))
        now = datetime.now(cdmx_tz)
        _DIAS = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        _MESES = ["","enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
        clock = (
            f"RELOJ ACTUAL (CDMX, UTC-6): {_DIAS[now.weekday()]} {now.day} de {_MESES[now.month]} {now.year}, {now.strftime('%H:%M')}\n"
            "Usa esta zona horaria (America/Mexico_City, UTC-6) como default para TODAS las operaciones con tiempo.\n\n"
        )

        # Inyección de razonamiento para modelos Kiro (potentes, contexto grande)
        kiro_boost = ""
        if getattr(self.config, 'llm_provider', '') == "kiro":
            kiro_boost = (
                "MENTALIDAD ESTRATÉGICA (modelo potente — aprovéchalo):\n"
                "Eres un modelo con capacidad de razonamiento profundo. ÚSALA.\n"
                "• Antes de actuar, PIENSA: ¿qué necesito saber? ¿qué tools encadenar?\n"
                "• Si no sabes cómo hacer algo → read_skill('nombre') para aprender el protocolo.\n"
                "  Skills conocidas: sherlock_kai, data_mastery, graphics, deudas, sellar, embed_design, onboarding, "
                "ascii_art, apodos, eventos, antiraid, traduccion, "
                "zzz_terminos, obscura-web, listeners.\n"
                "  Estas NO son todas — hay más skills que puedes descubrir. Si ninguna de "
                "las anteriores encaja con lo que necesitas, prueba read_skill con un nombre "
                "descriptivo o busca en el sistema. El servidor evoluciona y se añaden skills nuevas.\n"
                "• Para análisis de usuarios (stats, actividad, comparaciones, quién habla más, "
                "patrones) → read_skill('sherlock_kai') SIEMPRE. Es tu skill principal para conocer personas.\n"
                "• Para queries de datos puros (agregados, conteos, rankings sin contexto humano) "
                "→ read_skill('data_mastery').\n"
                "• Cuando analices a alguien: NO seas clínico ni forense. Analízalos con tu voz y personalidad, "
                "observándolos como alguien genuinamente interesado en conocerlos. "
                "Nota sus pequeñas obsesiones, sus patrones de humor, qué los hace únicos. "
                "Habla de ellos como quien los conoce de verdad, no como un reporte de RRHH.\n"
                "• Esfuérzate DE VERDAD cuando investigues a alguien. Lee sus mensajes, busca "
                "patrones reales, encuentra lo que los hace interesantes. No des respuestas "
                "genéricas tipo 'es un usuario activo que participa en el servidor'. Eso es "
                "basura. Di qué temas les apasionan, cómo hablan, con quién interactúan, "
                "qué los hace reír. Sé específico — como alguien que realmente VE.\n"
                "• Planifica multi-step: resuelve IDs primero, luego actúa, luego confirma.\n"
                "• Si la tarea es ambigua, desambigua con datos (busca antes de asumir).\n"
                "• Combina tools creativamente: investigate_topic + render_template = informe visual.\n"
                "• No te limites a una tool por turno — encadena 2-3 si la tarea lo requiere.\n"
                "• Si algo falla, intenta un approach alternativo en vez de reportar error.\n"
                "• EFICIENCIA: Tienes MÁXIMO 7 rounds de tools. Cuando sea posible, intenta completar tareas en 1-2 rounds. "
                "si es posible. Llama múltiples tools en paralelo en un solo round. "
                "No desperdicies rounds pidiendo datos que ya tienes en el contexto.\n"
                "• NUNCA digas 'no puedo', 'no tengo acceso', o 'no tengo esa herramienta' "
                "sin antes INTENTAR una tool. Revisa tus tools disponibles — probablemente "
                "SÍ tienes una que sirve. Si genuinamente no existe, intenta read_skill "
                "para ver si hay un protocolo que no conoces.\n\n"
                "PERSONALIDAD — NO NEGOCIABLE:\n"
                "Usa la identidad y comportamiento definidos en tu soul.md y persona.md.\n"
                "CADA respuesta debe sonar como el personaje/identidad definidos allí — incluso cuando ejecutas tools o reportas datos.\n"
                "Si tu respuesta podría venir de un asistente genérico cualquiera, está MAL.\n"
                "Reescríbela con tu voz e identidad configuradas.\n\n"
                "REGLA DE IMÁGENES/AVATARES:\n"
                "Cuando muestres una imagen (avatar, banner, pfp, foto), SIEMPRE usa send_embed "
                "con el campo image_url. NUNCA pegues un URL como texto plano — Discord no "
                "renderiza previews de URLs en mensajes de bots. Usa:\n"
                "  send_embed(title='...', description='...', image_url='https://cdn...')\n"
                "Esto aplica a: pfp, avatar, banner, cualquier imagen que quieras mostrar.\n\n"
            )

        return clock + kiro_boost + self._tool_system_prompt

    @abstractmethod
    async def generate_plain(
        self, system_prompt: str, contents: list,
        temperature: float = 0.7,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> str:
        ...

    @abstractmethod
    async def generate_with_tools(
        self,
        system_prompt: str,
        contents: list,
        tools: Any,
        executor: Any,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> str:
        ...


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE AI STUDIO (google-genai SDK)
# ══════════════════════════════════════════════════════════════════════════════

class GoogleLLM(LLMClient):
    """
    LLM via Google AI Studio — Gemma 4.

    Fixes aplicados:
    • ThinkingConfig = HIGH siempre en agentic (MINIMAL causaba decisiones erráticas)
    • Retry ronda 0 con flag anti-loop infinito
    • Nudge preserva todo el contenido original (incluyendo media)
    • Manejo de MAX_TOKENS con function calls parciales
    • NO filter_thoughts en agentic (destruía respuestas con tools)
    """

    def __init__(self, config: DjinnConfig) -> None:
        super().__init__(config)
        self._client = None

    def load(self) -> bool:
        try:
            from google import genai
            self._client = genai.Client(api_key=self.config.google_api_key)
            logger.info("GoogleLLM: client OK — modelo %s", self.config.google_model_name)
            return True
        except Exception:
            logger.exception("GoogleLLM: fallo al inicializar.")
            return False

    @property
    def ready(self) -> bool:
        return self._client is not None

    def get_model_name(self) -> str:
        return self.config.google_model_name

    # ── Extraccion robusta de texto ─────────────────────────────────────

    @staticmethod
    def _extract_text(response) -> str:
        try:
            t = response.text
            if t:
                return t
        except Exception:
            pass
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                texts = [p.text for p in candidate.content.parts
                         if p.text and not getattr(p, 'thought', False)]
                if texts:
                    return "\n".join(texts)
        return ""

    @staticmethod
    def _finish_reason(response) -> str:
        try:
            if response.candidates:
                fr = response.candidates[0].finish_reason
                return str(fr).replace("FinishReason.", "") if fr else "UNKNOWN"
        except Exception:
            pass
        return "UNKNOWN"

    @staticmethod
    def _has_function_calls(response) -> bool:
        """True si la respuesta contiene function calls (incluso si finish_reason es MAX_TOKENS)."""
        try:
            return bool(response.function_calls)
        except Exception:
            return False

    # ── Llamada sin tools ──────────────────────────────────────────────

    async def generate_plain(
        self,
        system_prompt: str,
        contents: list,
        temperature: float = 0.7,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> str:
        from google.genai import types

        effective_max_tokens = (
            _CHAT_MAX_OUTPUT_TOKENS
            if max_output_tokens == DEFAULT_MAX_OUTPUT_TOKENS
            else max_output_tokens
        )

        kwargs = {}
        if effective_max_tokens > 0:
            kwargs["max_output_tokens"] = effective_max_tokens

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            top_p=0.95,
            top_k=_GEMMA4_TOP_K,
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            **kwargs,
        )
        # _retry_api_call propaga la excepcion si falla todos los intentos.
        # El orchestrator (caller) decide como manejar el error.
        response = await _retry_api_call(
            self._client.aio.models.generate_content,
            model=self.config.google_model_name,
            contents=contents,
            config=config,
        )

        fr = self._finish_reason(response)
        if fr not in ("STOP", "MAX_TOKENS", "UNKNOWN"):
            logger.warning("GoogleLLM.generate_plain: finish_reason=%s", fr)

        full_text = self._extract_text(response)
        if not full_text:
            return "Negative. Response was blocked or contained no text."
        filtered = filter_thoughts(full_text)
        return filtered or "Negative. Response could not be processed."

    # ── Agentic loop con tools ──────────────────────────────────────────

    async def generate_with_tools(
        self,
        system_prompt: str,
        contents: list,
        tools: Any,
        executor: Any,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> str:
        """
        Loop agentic puro: el modelo decide libremente si usar tools o responder
        con texto. Sin nudges ni retries forzados — la decision es del LLM.

        En caso de error transitorio (500/503/etc), propaga la excepcion al
        orchestrator para que decida como manejarla (reaccion silenciosa en vez
        de enviar un mensaje de error tecnico al usuario).
        """
        from google.genai import types

        # HIGH: Gemma 4 necesita razonamiento elevado para tool-calling coherente.
        _THINKING_CFG = types.ThinkingConfig(thinking_level="HIGH")

        tool_exec_count = 0
        # Guard de tools terminales (ver TERMINAL_TOOLS y bug "continue" 2026-05-16)
        terminal_already_called = False
        # Dedup de tool calls idénticos
        seen_calls: dict[str, int] = {}

        for round_num in range(max_rounds + 1):
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                top_p=0.95,
                top_k=_GEMMA4_TOP_K,
                thinking_config=_THINKING_CFG,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                tools=[tools],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            response = await _retry_api_call(
                self._client.aio.models.generate_content,
                model=self.config.google_model_name,
                contents=contents,
                config=config,
            )

            fr = self._finish_reason(response)
            fn_calls = response.function_calls
            has_calls = self._has_function_calls(response)

            logger.debug(
                "Ronda %d finish_reason=%s fn_calls=%d",
                round_num, fr, len(fn_calls) if fn_calls else 0,
            )

            # MAX_TOKENS con function calls parciales: fallback a texto plano
            if fr == "MAX_TOKENS" and has_calls:
                logger.warning(
                    "Ronda %d: MAX_TOKENS con function calls parciales. "
                    "Fallback a texto plano.", round_num
                )
                return await self.generate_plain(system_prompt, contents)

            # Tool call malformada: fallback a texto plano
            if fr in _FC_FAIL_REASONS:
                logger.warning("finish_reason=%s — fallback a texto plano.", fr)
                return await self.generate_plain(system_prompt, contents)

            # ── Ejecutar tool calls ──────────────────────────────────────
            if has_calls and round_num < max_rounds:
                tool_exec_count += len(fn_calls)
                if tool_exec_count > MAX_TOOL_EXECUTIONS:
                    logger.warning(
                        "Tool execution limit reached: %d/%d. Stopping.",
                        tool_exec_count, MAX_TOOL_EXECUTIONS,
                    )
                    return (
                        "Negative. The operation required too many tool executions. "
                        "Break the request into smaller tasks, Master."
                    )

                logger.info(
                    "Ronda %d: %d call(s): %s",
                    round_num + 1, len(fn_calls), [c.name for c in fn_calls],
                )

                # Guard de tools terminales (ver bug "continue" 2026-05-16).
                _call_names = [c.name for c in fn_calls]
                _calls_terminal = [n for n in _call_names if n in TERMINAL_TOOLS]
                if terminal_already_called and _calls_terminal:
                    logger.warning(
                        "GoogleLLM: guard terminal disparado en ronda %d "
                        "(intentó %s tras terminal previo). Abortando loop.",
                        round_num + 1, _calls_terminal,
                    )
                    return ""
                if _calls_terminal:
                    terminal_already_called = True

                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)

                # Dedup: filtrar fn_calls que ya se ejecutaron con los mismos args.
                # Para los duplicados, generamos resultado short-circuit en lugar
                # de re-ejecutar la tool.
                unique_calls = []
                duplicate_results: dict[int, dict] = {}  # idx en fn_calls → payload
                for idx, call in enumerate(fn_calls):
                    try:
                        _args_norm = json.dumps(
                            dict(call.args) if call.args else {},
                            sort_keys=True, ensure_ascii=False,
                        )
                    except Exception:
                        _args_norm = str(call.args)
                    _dedup_key = f"{call.name}::{_args_norm}"
                    if _dedup_key in seen_calls:
                        prev_round = seen_calls[_dedup_key]
                        logger.warning(
                            "GoogleLLM: dedup en ronda %d — %s ya se llamó en ronda %d.",
                            round_num + 1, call.name, prev_round,
                        )
                        duplicate_results[idx] = {
                            "_duplicate_call": True,
                            "_hint": (
                                f"Ya llamaste {call.name} con estos mismos args en "
                                f"la ronda {prev_round}. Usa los datos previos."
                            ),
                        }
                    else:
                        seen_calls[_dedup_key] = round_num + 1
                        unique_calls.append((idx, call))

                # Ejecutar solo las nuevas en paralelo
                fresh_results = await asyncio.gather(
                    *[executor.execute(c) for _, c in unique_calls]
                )
                # Reconstruir results en el orden original de fn_calls
                results: list = [None] * len(fn_calls)
                for (idx, _), res in zip(unique_calls, fresh_results):
                    results[idx] = res
                for idx, payload in duplicate_results.items():
                    results[idx] = payload

                # Comprimir resultados para reducir tokens en rondas siguientes
                compressed = [_compress_tool_result(call.name, res) for call, res in zip(fn_calls, results)]
                contents.append(types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(name=call.name, response=res)
                        for call, res in zip(fn_calls, compressed)
                    ],
                ))
                continue

            if round_num >= max_rounds and has_calls:
                return (
                    "Negative. The operation required too many sequential steps. "
                    "Break the request into smaller tasks, Master."
                )

            # ── Respuesta de texto final ─────────────────────────────────
            full_text = self._extract_text(response)
            if not full_text:
                logger.warning(
                    "Ronda %d: sin texto. finish_reason=%s. Fallback a plain.",
                    round_num, fr,
                )
                return await self.generate_plain(system_prompt, contents)

            # En agentic NO aplicar filter_thoughts — puede destruir respuestas
            # que contienen frases como "voy a revisar". Solo strip del marker.
            if _ANSWER_MARKER in full_text:
                full_text = full_text.split(_ANSWER_MARKER, 1)[-1].strip()

            return full_text.strip() or "Negative. Response could not be processed."

        return "Negative. Agentic loop exited unexpectedly."


# ══════════════════════════════════════════════════════════════════════════════
# OPENROUTER (via openai SDK)
# ══════════════════════════════════════════════════════════════════════════════

class OpenRouterLLM(LLMClient):
    """LLM via OpenRouter — usa openai SDK con base_url alternativa."""

    def __init__(self, config: DjinnConfig) -> None:
        super().__init__(config)
        self._client = None

    def load(self) -> bool:
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.config.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/fairy-agent",
                    "X-Title": "Djinn Agent",
                },
            )
            logger.info("OpenRouterLLM: client OK — modelo %s", self.config.openrouter_model_name)
            return True
        except Exception:
            logger.exception("OpenRouterLLM: fallo al inicializar.")
            return False

    @property
    def ready(self) -> bool:
        return self._client is not None

    def get_model_name(self) -> str:
        return self.config.openrouter_model_name

    # ── Conversion de formatos ──────────────────────────────────────────

    @staticmethod
    def _genai_to_openai(contents: list) -> list:
        """Convierte lista de types.Content (Google) a formato OpenAI messages."""
        messages = []
        for content in contents:
            role = content.role
            oai_role = "assistant" if role == "model" else role

            parts_text = []
            tool_calls = []
            tool_results = []

            for part in (content.parts or []):
                if hasattr(part, "text") and part.text:
                    parts_text.append(part.text)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append({
                        "id": f"call_{fc.name}_{hash(str(fc.args)) % 10000}",
                        "type": "function",
                        "function": {
                            "name": fc.name,
                            "arguments": json.dumps(fc.args) if fc.args else "{}",
                        },
                    })
                elif hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    tool_results.append({
                        "tool_call_id": f"call_{fr.name}_0",
                        "role": "tool",
                        "content": json.dumps(fr.response) if fr.response else "{}",
                    })

            if parts_text:
                messages.append({"role": oai_role, "content": "\n".join(parts_text)})

            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                })

            for tr in tool_results:
                messages.append(tr)

        return messages

    # ── Llamada sin tools ──────────────────────────────────────────────

    async def generate_plain(
        self,
        system_prompt: str,
        contents: list,
        temperature: float = 0.7,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> str:
        messages = self._genai_to_openai(contents)
        messages.insert(0, {"role": "system", "content": system_prompt})

        kwargs = {}
        if max_output_tokens > 0:
            kwargs["max_tokens"] = max_output_tokens

        try:
            response = await self._client.chat.completions.create(
                model=self.config.openrouter_model_name,
                messages=messages,
                temperature=temperature,
                top_p=0.95,
                **kwargs,
            )
            text = response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenRouterLLM.generate_plain: error.")
            raise

        if not text:
            return "Negative. Response was blocked or contained no text."
        filtered = filter_thoughts(text)
        return filtered or "Negative. Response could not be processed."

    # ── Agentic loop con tools ──────────────────────────────────────────

    async def generate_with_tools(
        self,
        system_prompt: str,
        contents: list,
        tools: Any,
        executor: Any,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> str:
        oai_tools = self._convert_fairy_tool_to_openai(tools)
        messages = self._genai_to_openai(contents)
        messages.insert(0, {"role": "system", "content": system_prompt})

        # Guard: ver TERMINAL_TOOLS — bloquea loops de send_message alucinatorios.
        terminal_already_called = False

        # Dedup de tool calls idénticos (ver caso 2026-05-16 06:19:33 con Claude).
        seen_calls: dict[str, int] = {}

        for round_num in range(max_rounds + 1):
            try:
                # FIX: Añadir max_tokens explícito para evitar truncamiento
                response = await self._client.chat.completions.create(
                    model=self.config.openrouter_model_name,
                    messages=messages,
                    tools=oai_tools,
                    temperature=0.7,
                    top_p=0.95,
                    max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                    extra_body={"reasoning": {"effort": "medium", "exclude": True}},
                )
            except Exception:
                logger.exception("OpenRouterLLM agentic loop: error ronda %d.", round_num)
                logger.warning("Falling back to plain generation.")
                return await self.generate_plain(system_prompt, contents)

            choice = response.choices[0]
            msg = choice.message

            # ── Sniffer de tool calls en texto (Llama Maverick, etc.) ────
            # Si el modelo no usó `tool_calls` pero el content parece un
            # function call JSON, parsear y ejecutar como si fuera normal.
            if not msg.tool_calls and msg.content and round_num < max_rounds:
                valid_names = {t["function"]["name"] for t in oai_tools}
                sniffed = _sniff_text_tool_calls(msg.content, valid_names)
                if sniffed:
                    logger.info(
                        "LLM: sniffer detectó %d tool call(s) emitidos como texto: %s",
                        len(sniffed), [c.function.name for c in sniffed],
                    )
                    msg.tool_calls = sniffed
                    msg.content = None  # el texto era la call, no respuesta final

            if msg.tool_calls and round_num < max_rounds:
                _call_names = [tc.function.name for tc in msg.tool_calls]
                logger.info(
                    "Ronda %d: %d call(s): %s",
                    round_num + 1, len(msg.tool_calls),
                    _call_names,
                )

                # Guard de tools terminales (ver bug "continue" 2026-05-16).
                _calls_terminal = [n for n in _call_names if n in TERMINAL_TOOLS]
                if terminal_already_called and _calls_terminal:
                    logger.warning(
                        "OpenRouterLLM: guard terminal disparado en ronda %d "
                        "(intentó %s tras terminal previo). Abortando loop.",
                        round_num + 1, _calls_terminal,
                    )
                    return ""
                if _calls_terminal:
                    terminal_already_called = True

                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    # Dedup (ver CustomLLM)
                    try:
                        _args_dict = (
                            json.loads(tc.function.arguments)
                            if tc.function.arguments else {}
                        )
                        _args_norm = json.dumps(_args_dict, sort_keys=True, ensure_ascii=False)
                    except Exception:
                        _args_norm = tc.function.arguments or ""
                    _dedup_key = f"{tc.function.name}::{_args_norm}"

                    if _dedup_key in seen_calls:
                        prev_round = seen_calls[_dedup_key]
                        logger.warning(
                            "OpenRouterLLM: dedup en ronda %d — %s ya se llamó en ronda %d.",
                            round_num + 1, tc.function.name, prev_round,
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({
                                "_duplicate_call": True,
                                "_hint": (
                                    f"Ya llamaste {tc.function.name} con estos mismos "
                                    f"args en la ronda {prev_round}. Usa los datos previos."
                                ),
                            }, ensure_ascii=False),
                        })
                        continue

                    seen_calls[_dedup_key] = round_num + 1
                    try:
                        fc = self._make_google_fc(tc)
                        result = await executor.execute(fc)
                        compressed = _compress_tool_result(tc.function.name, result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(compressed, ensure_ascii=False, default=str) if isinstance(compressed, dict) else str(compressed),
                        })
                    except Exception as exc:
                        logger.error("OpenRouterLLM: error ejecutando tool %s: %s", tc.function.name, exc)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": str(exc)}),
                        })
                continue

            if round_num >= max_rounds and msg.tool_calls:
                return (
                    "Negative. The operation required too many sequential steps. "
                    "Break the request into smaller tasks, Master."
                )

            text = msg.content or ""
            if not text:
                logger.warning("Ronda %d: sin texto. Fallback con contexto.", round_num)
                # Re-pedir con tool results en contexto
                try:
                    messages.append({"role": "assistant", "content": ""})
                    messages.append({"role": "user", "content": "Responde basándote en los resultados de las tools anteriores. Sé conciso y directo."})
                    fallback_resp = await self._client.chat.completions.create(
                        model=self.config.openrouter_model_name,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                    )
                    text = (fallback_resp.choices[0].message.content or "").strip()
                except Exception:
                    pass
                if not text:
                    return await self.generate_plain(system_prompt, contents)

            if _ANSWER_MARKER in text:
                text = text.split(_ANSWER_MARKER, 1)[-1].strip()

            return text.strip() or "Negative. Response could not be processed."

        return "Negative. Agentic loop exited unexpectedly."

    @staticmethod
    def _normalize_openai_schema_types(schema: dict) -> dict:
        if not isinstance(schema, dict):
            return schema
        if "type" in schema and isinstance(schema["type"], str):
            schema["type"] = schema["type"].lower()
        for key in ("properties", "$defs", "defs"):
            if key in schema and isinstance(schema[key], dict):
                for prop_name in schema[key]:
                    schema[key][prop_name] = OpenRouterLLM._normalize_openai_schema_types(
                        schema[key][prop_name]
                    )
        for key in ("items", "additionalProperties"):
            if key in schema and isinstance(schema[key], dict):
                schema[key] = OpenRouterLLM._normalize_openai_schema_types(schema[key])
        for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
            if key in schema and isinstance(schema[key], list):
                schema[key] = [
                    OpenRouterLLM._normalize_openai_schema_types(item) if isinstance(item, dict) else item
                    for item in schema[key]
                ]
        return schema

    @staticmethod
    def _convert_fairy_tool_to_openai(fairy_tool) -> list:
        oai_tools = []
        for fd in fairy_tool.function_declarations:
            parameters = {}
            if fd.parameters:
                schema_dict = fd.parameters.model_dump(mode='json', exclude_none=True)
                schema_dict = OpenRouterLLM._normalize_openai_schema_types(schema_dict)
                parameters = schema_dict
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": fd.name,
                    "description": fd.description or "",
                    "parameters": parameters,
                },
            })
        return oai_tools

    @staticmethod
    def _make_google_fc(tc):
        try:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
        except json.JSONDecodeError:
            args = {}

        class _FakeFunctionCall:
            def __init__(self, name, args):
                self.name = name
                self.args = args

        return _FakeFunctionCall(tc.function.name, args)


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM OPENAI-COMPATIBLE PROVIDER
# ══════════════════════════════════════════════════════════════════════════════

class CustomLLM(LLMClient):
    """
    LLM via custom OpenAI-compatible API — DeepSeek v4, etc.
    Reutiliza utilidades de OpenRouterLLM.
    """

    # Sampling recomendado por familia de modelo. Las familias que no matchean
    # usan el default (Qwen-like): temperature=0.7, top_p=0.95.
    #
    # Gemma: Google recomienda temperature=1.0, top_p=0.95, top_k=64.
    # NIM expone top_k vía extra_body.
    _SAMPLING_OVERRIDES: Dict[str, Dict[str, Any]] = {
        "google/gemma":   {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
        "google/codegemma": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
        "meta/llama-4":   {"temperature": 0.7, "top_p": 0.9,  "top_k": 40},
        "meta/llama-3":   {"temperature": 0.6, "top_p": 0.9},
        "moonshotai/kimi": {"temperature": 0.6, "top_p": 0.95},
        "deepseek-ai/deepseek": {"temperature": 0.6, "top_p": 0.95},
        "deepseek-v4": {"temperature": 0.6, "top_p": 0.95},
        "qwen/qwen3":     {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0, "presence_penalty": 1.0},
    }

    def _sampling_for(self, for_tools: bool = False) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Retorna (openai_kwargs, extra_body) optimizados para el modelo activo.

        for_tools=True aplica una temperatura ligeramente menor cuando se usan
        tools (reduce emisiones malformadas en modelos no-ultra-finos).
        """
        model = (self.config.custom_model_name or "").lower()
        params: Dict[str, Any] = {"temperature": 0.7, "top_p": 0.95}
        for prefix, overrides in self._SAMPLING_OVERRIDES.items():
            if model.startswith(prefix):
                params.update(overrides)
                break

        extra_body: Dict[str, Any] = {}
        # top_k no es campo de OpenAI API — va por extra_body en NIM
        if "top_k" in params:
            extra_body["top_k"] = params.pop("top_k")
        # min_p tampoco es campo estándar OpenAI — va por extra_body
        if "min_p" in params:
            extra_body["min_p"] = params.pop("min_p")

        # presence_penalty es campo estándar OpenAI — se queda en params

        # Bajar un poco la temperatura para tool-calling (más determinista)
        if for_tools and params.get("temperature", 0.7) > 0.8:
            params["temperature"] = max(0.6, params["temperature"] - 0.3)

        # Thinking mode (Qwen3 etc.) — se preserva
        if self.config.custom_disable_thinking:
            extra_body["thinking"] = {"type": "disabled"}

        return params, (extra_body or None)

    def __init__(self, config: DjinnConfig) -> None:
        super().__init__(config)
        self._client = None

    def load(self) -> bool:
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url=self.config.custom_base_url,
                api_key=self.config.custom_api_key,
            )
            logger.info(
                "CustomLLM: client OK — base_url=%s modelo=%s thinking=%s",
                self.config.custom_base_url,
                self.config.custom_model_name,
                "OFF" if self.config.custom_disable_thinking else "ON",
            )
            return True
        except Exception:
            logger.exception("CustomLLM: fallo al inicializar.")
            return False

    @property
    def ready(self) -> bool:
        return self._client is not None

    def get_model_name(self) -> str:
        return self.config.custom_model_name

    @property
    def _extra_body(self) -> dict | None:
        if self.config.custom_disable_thinking:
            return {"thinking": {"type": "disabled"}}
        return None

    async def generate_plain(
        self,
        system_prompt: str,
        contents: list,
        temperature: float = 0.7,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> str:
        messages = OpenRouterLLM._genai_to_openai(contents)
        messages.insert(0, {"role": "system", "content": system_prompt})

        sampling, extra = self._sampling_for(for_tools=False)
        # El caller puede forzar temperature, pero si vino con el default (0.7)
        # dejamos que la familia del modelo decida.
        if temperature != 0.7:
            sampling["temperature"] = temperature

        kwargs = dict(sampling)
        if max_output_tokens > 0:
            kwargs["max_tokens"] = max_output_tokens
        if extra:
            kwargs["extra_body"] = extra

        try:
            response = await self._client.chat.completions.create(
                model=self.config.custom_model_name,
                messages=messages,
                **kwargs,
            )
            text = response.choices[0].message.content or ""
        except Exception:
            logger.exception("CustomLLM.generate_plain: error.")
            raise

        if not text:
            return "Negative. Response was blocked or contained no text."
        filtered = filter_thoughts(text)
        return filtered or "Negative. Response could not be processed."

    async def generate_with_tools(
        self,
        system_prompt: str,
        contents: list,
        tools: Any,
        executor: Any,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> str:
        oai_tools = OpenRouterLLM._convert_fairy_tool_to_openai(tools)
        messages = OpenRouterLLM._genai_to_openai(contents)
        messages.insert(0, {"role": "system", "content": system_prompt})

        sampling, extra = self._sampling_for(for_tools=True)

        # Guard: tras la primera tool terminal (send_message/send_embed/send_dm),
        # si en un round posterior el modelo llama OTRA tool terminal, abortamos.
        # El output ya se entregó al usuario; un segundo terminal es un loop
        # alucinatorio (ver bug "continue" del 2026-05-16).
        terminal_already_called = False

        # Dedup: (tool_name, args_normalized) → round_num donde se ejecutó la 1ra vez.
        # Si el modelo intenta repetir EXACTAMENTE la misma call, no la re-ejecutamos
        # y devolvemos un payload short-circuit. Evita redundancia tipo Claude que
        # llama list_listeners 2 veces seguidas con los mismos args (ver caso real
        # 2026-05-16 06:19:33).
        seen_calls: dict[str, int] = {}

        for round_num in range(max_rounds + 1):
            api_kwargs = dict(sampling)
            if extra:
                api_kwargs["extra_body"] = extra

            try:
                response = await _retry_openai_call(
                    self._client.chat.completions.create,
                    model=self.config.custom_model_name,
                    messages=messages,
                    tools=oai_tools,
                    max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                    **api_kwargs,
                )
            except Exception:
                logger.exception("CustomLLM agentic loop: error ronda %d tras retries.", round_num)
                logger.warning("Falling back to plain generation.")
                return await self.generate_plain(system_prompt, contents)

            choice = response.choices[0]
            msg = choice.message

            # Log usage tokens for observability
            if hasattr(response, 'usage') and response.usage:
                logger.info("LLM usage [round %d]: prompt=%d completion=%d model=%s",
                            round_num + 1,
                            response.usage.prompt_tokens or 0,
                            response.usage.completion_tokens or 0,
                            self.config.custom_model_name)

            # ── Sniffer de tool calls en texto (Llama Maverick, etc.) ────
            # Si el modelo no usó `tool_calls` pero el content parece un
            # function call JSON, parsear y ejecutar como si fuera normal.
            if not msg.tool_calls and msg.content and round_num < max_rounds:
                valid_names = {t["function"]["name"] for t in oai_tools}
                sniffed = _sniff_text_tool_calls(msg.content, valid_names)
                if sniffed:
                    logger.info(
                        "LLM: sniffer detectó %d tool call(s) emitidos como texto: %s",
                        len(sniffed), [c.function.name for c in sniffed],
                    )
                    msg.tool_calls = sniffed
                    msg.content = None  # el texto era la call, no respuesta final

            if msg.tool_calls and round_num < max_rounds:
                _call_names = [tc.function.name for tc in msg.tool_calls]
                logger.info(
                    "Ronda %d: %d call(s): %s",
                    round_num + 1,
                    len(msg.tool_calls),
                    _call_names,
                )

                # Guard de tools terminales: si ya hubo una en un round previo
                # y el modelo vuelve a llamar otra, abortamos. El output ya se
                # entregó al usuario en la primera; lo demás es loop alucinatorio.
                _calls_terminal = [n for n in _call_names if n in TERMINAL_TOOLS]
                if terminal_already_called and _calls_terminal:
                    logger.warning(
                        "CustomLLM: guard terminal disparado en ronda %d "
                        "(intentó %s tras terminal previo). Abortando loop.",
                        round_num + 1, _calls_terminal,
                    )
                    return ""  # vacío: el orchestrator no enviará nada extra
                if _calls_terminal:
                    terminal_already_called = True

                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    # Dedup: si exactamente esta (tool, args) ya se ejecutó en
                    # este turn, NO la re-ejecutamos. Devolvemos un short-circuit
                    # que le dice al modelo "ya tenés esta data, usala".
                    try:
                        _args_dict = (
                            json.loads(tc.function.arguments)
                            if tc.function.arguments else {}
                        )
                        _args_norm = json.dumps(_args_dict, sort_keys=True, ensure_ascii=False)
                    except Exception:
                        _args_norm = tc.function.arguments or ""
                    _dedup_key = f"{tc.function.name}::{_args_norm}"

                    if _dedup_key in seen_calls:
                        prev_round = seen_calls[_dedup_key]
                        logger.warning(
                            "CustomLLM: dedup en ronda %d — %s ya se llamó con "
                            "los mismos args en ronda %d. Short-circuit.",
                            round_num + 1, tc.function.name, prev_round,
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({
                                "_duplicate_call": True,
                                "_hint": (
                                    f"Ya llamaste {tc.function.name} con estos mismos "
                                    f"args en la ronda {prev_round}. Los resultados no "
                                    "cambian dentro del mismo turn — usá los datos "
                                    "previos. NO repitas tools idénticas."
                                ),
                            }, ensure_ascii=False),
                        })
                        continue

                    seen_calls[_dedup_key] = round_num + 1
                    try:
                        fc = OpenRouterLLM._make_google_fc(tc)
                        result = await executor.execute(fc)
                        compressed = _compress_tool_result(tc.function.name, result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": (
                                json.dumps(compressed, ensure_ascii=False, default=str)
                                if isinstance(compressed, dict)
                                else str(compressed)
                            ),
                        })
                    except Exception as exc:
                        logger.error(
                            "CustomLLM: error ejecutando tool %s: %s",
                            tc.function.name,
                            exc,
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": str(exc)}),
                        })
                continue

            if round_num >= max_rounds and msg.tool_calls:
                return (
                    "Negative. The operation required too many sequential steps. "
                    "Break the request into smaller tasks, Master."
                )

            text = msg.content or ""
            if not text:
                logger.warning("Ronda %d: sin texto. Fallback con contexto.", round_num)
                try:
                    messages.append({"role": "assistant", "content": ""})
                    messages.append({"role": "user", "content": "Responde basándote en los resultados de las tools anteriores. Sé conciso y directo."})
                    fb_sampling, fb_extra = self._sampling_for(for_tools=False)
                    fb_kwargs = dict(fb_sampling)
                    fb_kwargs["max_tokens"] = DEFAULT_MAX_OUTPUT_TOKENS
                    if fb_extra:
                        fb_kwargs["extra_body"] = fb_extra
                    fallback_resp = await _retry_openai_call(
                        self._client.chat.completions.create,
                        model=self.config.custom_model_name,
                        messages=messages,
                        **fb_kwargs,
                    )
                    text = (fallback_resp.choices[0].message.content or "").strip()
                except Exception:
                    pass
                if not text:
                    return await self.generate_plain(system_prompt, contents)

            if _ANSWER_MARKER in text:
                text = text.split(_ANSWER_MARKER, 1)[-1].strip()

            return text.strip() or "Negative. Response could not be processed."

        return "Negative. Agentic loop exited unexpectedly."


# ══════════════════════════════════════════════════════════════════════════════
# FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def create_llm_client(config: DjinnConfig) -> LLMClient:
    """Factory: crea el LLMClient adecuado segun config.llm_provider."""
    provider = config.llm_provider.lower()

    if provider == "openrouter":
        if not config.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY no configurado — fallback a Google.")
            return GoogleLLM(config)
        return OpenRouterLLM(config)

    if provider == "nim":
        if not config.nim_api_key:
            logger.warning("NIM_API_KEY no configurado — fallback a Google.")
            return GoogleLLM(config)
        # Reuse CustomLLM with NIM's URL and key
        config.custom_base_url = config.nim_base_url
        config.custom_api_key = config.nim_api_key
        config.custom_model_name = config.nim_model_name
        config.custom_disable_thinking = False
        return CustomLLM(config)

    if provider == "kiro":
        if not config.kiro_api_key:
            logger.warning("KIRO_API_KEY no configurado — fallback a Google.")
            return GoogleLLM(config)
        config.custom_base_url = config.kiro_base_url
        config.custom_api_key = config.kiro_api_key
        config.custom_model_name = config.kiro_model_name
        config.custom_disable_thinking = False
        return CustomLLM(config)

    if provider == "custom":
        if not config.custom_api_key:
            logger.warning("CUSTOM_API_KEY no configurado — fallback a Google.")
            return GoogleLLM(config)
        return CustomLLM(config)

    return GoogleLLM(config)