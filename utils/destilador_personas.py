"""
Destilador de Personalidades para la Simulación de Supervivencia.
Usa cache hash-aware para evitar re-destilar si el historial no cambió.
"""

from __future__ import annotations

import json
import hashlib
import asyncio
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from utils.genero_detector import integrar_detector_en_perfil
except ImportError:
    from genero_detector import integrar_detector_en_perfil

from loguru import logger


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

DESTILLATION_MAX_TOKENS = 6000

DESTILATION_SYSTEM = """Eres un Analista de Personalidad Forense.

Tu trabajo: examinar el historial de mensajes de UN usuario y construir
una ficha de personalidad EXTREMADAMENTE DETALLADA.

USA EXACTAMENTE la siguiente estructura JSON. No omitas ningún campo.
NO cambies los nombres de las claves. Cada campo debe tener contenido real.

FORMATO (JSON estricto):
{
 "nombre": "display_name",
 "pronombres": "él/ella/elle/they",
 "estilo_habla": {
   "descripcion_detallada": "Párrafo extenso de su huella digital de escritura.",
   "patrones": ["6-9 patrones observados con ejemplos concretos"],
   "muletillas": ["expresiones que repite mucho"],
   "vocabulario": ["palabras características"],
   "errores_intencionados": ["errores ortográficos deliberados"],
   "mayusculas": "cuándo y por qué usa mayúsculas",
   "interjecciones": ["sonidos tipo 'ajá', 'mm', 'pff', 'brr']",
   "emoji_usos": ["cómo usa los emoji"],
   "ritmo": "oraciones cortas Y largas, pauses dramáticas, etc",
   "nivel_formalidad": "0-10, informal total vs muy correcto",
   "abreviatura": ["omg, tqm, etc"],
   "voz_simulada": "Ejemplo de texto corto (30-50 palabras) escrito por este usuario. NI EL NOMBRE NI EL ROL. Solo su VOZ.",
   "guia_escritura": "3 reglas de escritura para sonar como esta persona sin perder claridad.",
   "analisis_lingüistico": "Explicación breve de por qué esta persona escribe así.",
   "como_responderia_ataque": "Cómo reaccionaría ante una provocación",
   "como_haria_solicitud": "Cómo pediría ayuda o favor",
   "como_amenazaria": "Cómo amenazaría si estuviera enojado",
   "como_pediria_alianza": "Cómo propondría una alianza"
 },
 "personalidad": {
   "arquetipo_supervivencia": "CREATIVO y ESPECÍFICO",
   "rasgos_dominantes": ["6-8 rasgos con ejemplos"],
   "descripcion_psicologica": "4-6 oraciones de análisis profundo",
   "red_flags": ["4-6 con ejemplos"],
   "green_flags": ["4-6 con ejemplos"],
   "trigger_palabras": ["4-6 temas que lo activan"],
   "dato_curioso": "detalle revelador"
 },
 "social": {
   "aliados_probables": ["nombre1#1234", "nombre2#5678"],
   "enemigos_probables": ["nombre3#9012"],
   "estilo_conflicto": "DETALLADO",
   "estilo_alianza": "DETALLADO",
   "rol_en_grupo": "líder/seguidor/provocador/etc"
 },
 "estrategia_supervivencia": "Cómo piensa sobrevivir",
 "como_moriria": "En un epitafio de 1 oración, cómo moriría esta persona",
 "system_prompt_simulacion": "Párrafo de 2-3 oraciones para el system prompt del agente en simulación. Debe capturar la ESENCIA de cómo piensa y actúa.",
 "estadisticas_juego": {
   "fuerza": 1-10,
   "agilidad": 1-10,
   "carisma": 1-10,
   "supervivencia": 1-10,
   "inteligencia": 1-10,
   "suerte": 1-10
 },
 "calidad_perfil": "alta/media/baja según cantidad de mensajes",
 "mensajes_total": número real de mensajes analizados,
 "ultima_actualizacion": "ISO timestamp",
 "estado_emocional": {
   "miedo": 1-10,
   "confianza_en_otros": 1-10,
   "desesperacion": 1-10,
   "agresividad": 1-10,
   "esperanza": 1-10
 },
 "inventario_inicial": ["2-3 ítems lógicos basados en la personalidad"],
 "zona_preferida": "zona del mapa que mejor se adapta a su estrategia"
}

IMPORTANTE:
- TODOS los campos son obligatorios
- Para "estadisticas_juego" usa números enteros del 1 al 10
- El campo "voz_simulada" debe ser un texto REAL escrito por el usuario, no una descripción
- "system_prompt_simulacion" es para que el agente de simulación sepa cómo pensar y actuar
- "calidad_perfil" indica confianza: "alta" = 500+ msgs, "media" = 250-499, "baja" = <250
"""

DESTILATION_FEW_SHOT = """
Ejemplo de salida perfecta:

HISTORIAL:
[Usuario123]: wey alv qué pedo
[Usuario123]: nadie me ayuda JAJAJAJA
[Usuario123]: esto está floppeando horrible
[Usuario123]: m6 no voy a pasar esta fase
[Usuario123]: alguien tiene idea o qué

ANÁLISIS:
{
 "nombre": "Usuario123",
 "pronombres": "él",
 "estilo_habla": {
   "descripcion_detallada": "Usuario ultra informal con escritura truncada y slang mexicano. Usa 'wey', 'alv', 'pedo' constantemente como muletillas. Sus mensajes son mayormente cortos y reactivos.",
   "patrones": ["'wey' como vocativo constante", "fin de frase con 'JAJAJAJA'", "uso de 'floppear' para fail", "'m6' como expresión de resignación"],
   "muletillas": ["wey", "alv", "pedo", "JAJAJAJA", "m6"],
   "vocabulario": ["wey", "alv", "floppear", "m6", "pasar"],
   "errores_intencionados": ["'pedo' en lugar de problemas", "escritura truncada tipo chat"],
   "mayusculas": "SÓLO para énfasis cómico como 'JAJAJAJA', nunca para gritar",
   "interjecciones": ["JAJAJAJA", "m6", "wey"],
   "emoji_usos": ["casi nunca usa emoji"],
   "ritmo": "Mensajes cortos, impulsivos, sin estructura. Responde rápido.",
   "nivel_formalidad": "1/10 - puro slang de calle",
   "abreviatura": ["m6 (me mux)", "wey", "alv"],
   "voz_simulada": "wey alv qué pedo esto está floppeando horrible, nadie me ayuda, m6",
   "guia_escritura": "Usa minúsculas siempre. Termina con risa fake. Vocabulario reducido. Oraciones cortitas.",
   "analisis_lingüistico": "Habla así porque es de entorno gamer/callejón. Su identidad está en el rechazo al sistema.",
   "como_responderia_ataque": "Respondería con burla y más slang, intentando descalificar al atacante.",
   "como_haria_solicitud": "Directo y corto: 'oye wey ayudame con X'",
   "como_amenazaria": "Amenazaría en modo chistoso: 'te voy a buscar wey'",
   "como_pediria_alianza": "Muy casual: 'vámonos wey va? somos míos'"
 },
 "personalidad": {
   "arquetipo_supervivencia": "REACTIVO - espera que otros fallen para actuar",
   "rasgos_dominantes": ["cínico", "reacciona a presión", "comunicativo cuando necesita ayuda"],
   "descripcion_psicologica": "Usuario que se maneja en modo supervivencia social. Busca espacios donde others puedan fallar primero. Le tiene miedo a la vulnerabilidad.",
   "red_flags": ["se rinde rápido (m6)", "depende de otros para pasar fases"],
   "green_flags": ["divertido en grupo", "no guarda rencor", "reconoce errores con humor"],
   "trigger_palabras": ["floppear", "basura", "bot", "títere"],
   "dato_curioso": "Dice 'm6' que es de su época ToF"
 },
 "social": {
   "aliados_probables": ["Fairy#1", "Xoft#2"],
   "enemigos_probables": [],
   "estilo_conflicto": "Evita confrontación directa, ataca por humor",
   "estilo_alianza": "Se une a quien tenga más nivel o a sus amigos",
   "rol_en_grupo": "comediante/reportero"
 },
 "estrategia_supervivencia": "Ir directo al objetivo. No perder tiempo en diálogos. Si hay que huir, huir.",
 "como_moriria": "Intentando resolver algo solo cuando ya no podía.",
 "system_prompt_simulacion": "Eres Usuario123. Cínico, informal, gamer. Escribes en minúsculas con slang mexicano. 'wey', 'm6', 'floppear'. No te rindes fácil pero reconoces cuando vas a perder. Prefieres huir a morir peleando.",
 "estadisticas_juego": {
   "fuerza": 3,
   "agilidad": 6,
   "carisma": 7,
   "supervivencia": 4,
   "inteligencia": 5,
   "suerte": 5
 },
 "calidad_perfil": "alta",
 "mensajes_total": 500,
 "ultima_actualizacion": "2025-05-03T14:22:00Z",
 "estado_emocional": {"miedo": 4, "confianza_en_otros": 3, "desesperacion": 3, "agresividad": 2, "esperanza": 5},
 "inventario_inicial": ["Pechera de cuero gastado", "Cantimplora medio vacía"],
 "zona_preferida": "bosque"
}

OTRO EJEMPLO - estilo gamer competitivo:

HISTORICO:
[ProGamer]:gg ez
[ProGamer]:este equipo estábot
[ProGamer]:reset?
[ProGamer]:no matter sigue el ranked
[ProGamer]:siuu

SALIDA:
{
 "nombre": "ProGamer",
 "pronombres": "él",
 "estilo_habla": {
   "descripcion_detallada": "Gamer competitivo hardcore. Usa inglés mezclado con español. Expresiones cortas y tajantes. Comunica en modo指令.",
   "patrones": ["gg ez cuando gana", "bot cuando hay lag", "siuu de celebración"],
   "muletillas": ["gg", "ez", "bot", "siuu", "reset"],
   "vocabulario": ["gg (good game)", "ez (easy)", "ranked", "lag"],
   "errores_intencionados": ["escribe 'no matter' sin tilde", "mezcla idiomas a propósito"],
   "mayusculas": "GG, EZ, SIUU (todo mayúsculas para expresar emoción)",
   "interjecciones": ["siuu", "gg", "bot"],
   "emoji_usos": ["gs de victoria"],
   "ritmo": "Ultra corto. 1-3 palabras por mensaje. Sin explicación.",
   "nivel_formalidad": "2/10 - gamer speak",
   "abreviatura": ["gg, ez, bot, siuu"],
   "voz_simulada": "gg ez este equipo está bot siuu",
   "guia_escritura": "Máximo 3 palabras. Mayúsculas para emoción. Mezcla español-inglés. Sin puntuación.",
   "analisis_lingüistico": "Gamer competidor de alta intensidad. Su identidad está en ganar.",
   "como_responderia_ataque": "GG EZ + mute",
   "como_haria_solicitud": "reset? o directamente hace queue sin preguntar",
   "como_amenazaria": "gg ez te voy a hacer bot",
   "como_pediria_alianza": "ranked?"
 },
 "personalidad": {
   "arquetipo_supervivencia": "COMPETITIVO - busca ventaja desde el inicio",
   "rasgos_dominantes": ["competitivo", "ego alto", "enfocado en ganar"],
   "descripcion_psicologica": "Gamer que mide todo en wins/losses. Su ego está ligado a su rendimiento.",
   "red_flags": ["se frustra fácilmente si pierde", "blamea al equipo"],
   "green_flags": ["siempre quiere improve", "entrena mucho"],
   "trigger_palabras": ["lose", "bot", "throw", "no skill"],
   "dato_curioso": "Su 'siuu' es inconfundible"
 },
 "social": {
   "aliados_probables": [],
   "enemigos_probables": [],
   "estilo_conflicto": "Compite directamente, no hace alliances",
   "estilo_alianza": "No las busca, las evita",
   "rol_en_grupo": "solo queue gamer"
 },
 "estrategia_supervivencia": "Primero el ranked..gg ez todo.",
 "como_moriria": "En un 1v1 con lag.",
 "system_prompt_simulacion": "Eres ProGamer. Competitivo, gamer speak, escribe corto y en mayúsculas para énfasis. 'gg ez siuu'. Mezclas español e inglés. odias perder. Siempre buscas la ventaja.",
 "estadisticas_juego": {
   "fuerza": 5,
   "agilidad": 8,
   "carisma": 3,
   "supervivencia": 4,
   "inteligencia": 6,
   "suerte": 4
 },
 "calidad_perfil": "media",
 "mensajes_total": 250,
 "ultima_actualizacion": "2025-05-03T14:22:00Z",
 "estado_emocional": {"miedo": 2, "confianza_en_otros": 1, "desesperacion": 2, "agresividad": 8, "esperanza": 7},
 "inventario_inicial": ["Control analógico gastado", "Energy drink"],
 "zona_preferida": "arena"
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE EXTRACCIÓN
# ─────────────────────────────────────────────────────────────────────────────

async def extraer_historial(
    user_id: int,
    guild_id: int,
    db,
    limite: int = 500,  # 30 ejemplos reales mínimo para buen análisis
) -> list:
    """
    Extrae el historial de mensajes de un usuario desde la DB.
    
    Args:
        user_id: ID del usuario en Discord
        guild_id: ID del servidor
        db: Conexión a la base de datos
        limite: Máximo de mensajes a extraer
        
    Returns:
        Lista de diccionarios con {role, content, timestamp}
    """
    try:
        mensajes = []
        
        # Usar search_messages de la Database del bot (API pública)
        try:
            rows = await db.search_messages(
                guild_id=guild_id,
                user_id=user_id,
                hours=4320,  # 180 días de historial
                limit=limite,
            )
            
            for row in rows:
                content = row.get("content", "")
                if content:
                    mensajes.append({
                        "role": "user",
                        "content": content[:2000],
                        "timestamp": row.get("timestamp", 0),
                    })
        except Exception as e:
            logger.warning(f"search_messages no disponible: {e}")
        
        # Si no hay mensajes, generar datos de ejemplo para testing
        if not mensajes:
            logger.warning(f"No hay mensajes en DB para user={user_id}, guild={guild_id}")
            return [{
                "role": "user",
                "content": "Este es un mensaje de ejemplo mientras no hay datos reales en la DB.",
                "timestamp": "2025-01-01T00:00:00Z"
            }]
        
        # Invertir para tener cronología normal (más antiguo primero)
        mensajes.reverse()
        return mensajes
    
    except Exception as e:
        logger.error(f"Error extrayendo historial para user={user_id}: {e}")
        return []


def generar_hash_historial(mensajes: list) -> str:
    """
    Genera un hash SHA-256 del contenido de los mensajes.
    Útil para cachear perfiles y evitar re-destilación.
    """
    contenido = "|".join(m["content"] for m in mensajes)
    return hashlib.sha256(contenido.encode()).hexdigest()[:16]


def _limpiar_json_response(text: str) -> str:
    """
    Limpia la respuesta JSON del modelo - extrae solo el JSON válido.
    Maneja踠s headers, markdown, y texto alrededor.
    """
    # Buscar el inicio del JSON
    json_start = text.find('{')
    if json_start == -1:
        # Intentar con array
        json_start = text.find('[')
    
    if json_start == -1:
        return text  # Devolver como está si no encuentra JSON
    
    # Buscar el final del JSON
    # Cuenta brackets para encontrar el cierre correcto
    json_text = text[json_start:]
    bracket_count = 0
    in_string = False
    escape_next = False
    
    for i, char in enumerate(json_text):
        if escape_next:
            escape_next = False
            continue
        if char in ('"', "'"):
            if not escape_next:
                in_string = not in_string
        elif not in_string:
            if char in ('{', '['):
                bracket_count += 1
            elif char in ('}', ']'):
                bracket_count -= 1
                if bracket_count == 0:
                    return json_text[:i+1]
        if char == '\\':
            escape_next = True
    
    return json_text  # Devolver lo que tenemos si no se cerró bien


# ─────────────────────────────────────────────────────────────────────────────
# DESTILACIÓN
# ─────────────────────────────────────────────────────────────────────────────

async def destilar_perfil(mensajes: list, user_name: str, bot, model_name: str) -> dict:
    """
    Destila un perfil de personalidad desde el historial de mensajes.
    """
    if not mensajes:
        return _perfil_fallback(user_name, "sin mensajes")
    
    # Contar mensajes para calidad
    mensajes_count = len(mensajes)
    
    # Construir el historial para el prompt
    historial_texto = "\n".join([
        f"[{m['role']}]: {m['content'][:300]}"
        for m in mensajes[-50:]  # Últimas 50 para contexto
    ])
    
    # Prompt completo
    prompt = f"""Analiza el siguiente historial de mensajes y genera un perfil de personalidad EXTREMO.
El historial es de UNA persona real. El perfil debe capturar su VOZ ÚNICA.

{historial_texto}

Genera el perfil JSON ahora. Sé MUY específico en la voz_simulada y los patrones."""

    try:
        # Llamar al modelo usando generate_plain del bot
        from google.genai import types as genai_types
        contents = [genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt)])]
        response = await bot.llm.generate_plain(
            system_prompt=DESTILATION_SYSTEM,
            contents=contents,
            temperature=0.7,
            max_output_tokens=DESTILLATION_MAX_TOKENS,
        )
        
        # Extraer el texto de la respuesta (generate_plain retorna str directamente)
        response_text = response if isinstance(response, str) else str(response)
        
        # Limpiar y parsear JSON
        json_text = _limpiar_json_response(response_text)
        
        try:
            perfil = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, intentando corregir...")
            # Último intento: buscar en el texto
        for line in response_text.split('\n'):
            if line.strip().startswith('{') and line.strip().endswith('}'):
                try:
                    perfil = json.loads(line.strip())
                    break
                except json.JSONDecodeError:
                    continue
        else:
            return _perfil_fallback(user_name, f"json_error: {e}")
        
        # Agregar metadata
        perfil["_hash"] = generar_hash_historial(mensajes)
        
        # Agregar system_prompt_simulacion si no existe
        if "system_prompt_simulacion" not in perfil:
            perfil["system_prompt_simulacion"] = _generar_system_prompt(perfil, user_name)
        
        # Agregar calidad del perfil
        if mensajes_count >= 500:
            perfil["calidad_perfil"] = "alta"
        elif mensajes_count >= 250:
            perfil["calidad_perfil"] = "media"
        else:
            perfil["calidad_perfil"] = "baja"
        
        perfil["mensajes_total"] = mensajes_count
        perfil["ultima_actualizacion"] = "2025-05-03T14:22:00Z"  # Se actualiza en runtime
        
        return perfil
        
    except Exception as e:
        logger.error(f"Error destilando perfil para {user_name}: {e}")
        return _perfil_fallback(user_name, str(e))


def _generar_system_prompt(perfil: dict, user_name: str) -> str:
    """Genera el system_prompt_simulacion desde el perfil."""
    estilo = perfil.get("estilo_habla", {})
    personalidad = perfil.get("personalidad", {})
    estrategia = perfil.get("estrategia_supervivencia", "")
    
    # Usar la voz simulada como base
    voz = estilo.get("voz_simulada", "")[:100]
    
    # Agregar estrategia de supervivencia
    estrategia_text = estrategia[:80] if estrategia else "Sobrevive como pueda."
    
    return f"Eres {user_name}. {voz} Estrategia: {estrategia_text}"


def _perfil_fallback(name: str, reason: str) -> dict:
    """Perfil por defecto cuando falla la destilación."""
    return {
        "nombre": name,
        "pronombres": "él/ella",
        "estilo_habla": {
            "descripcion_detallada": "Perfil de fallback",
            "patrones": ["texto genérico"],
            "voz_simulada": f"Soy {name} y esto es un perfil de respaldo",
            "guia_escritura": "Sé genérico"
        },
        "personalidad": {"arquetipo_supervivencia": "NEUTRAL"},
        "social": {"aliados_probables": [], "enemigos_probables": []},
        "estadisticas_juego": {
            "fuerza": 5, "agilidad": 5, "carisma": 5,
            "supervivencia": 5, "inteligencia": 5, "suerte": 5
        },
        "estrategia_supervivencia": "Sobrevivir un día más",
        "como_moriria": "Por mala suerte",
        "system_prompt_simulacion": f"Eres {name}. Sé básico.",
        "calidad_perfil": "baja",
        "mensajes_total": 0,
        "ultima_actualizacion": "2025-05-03T14:22:00Z",
        "estado_emocional": {"miedo": 5, "confianza_en_otros": 5, "desesperacion": 5, "agresividad": 5, "esperanza": 5},
        "inventario_inicial": ["Objeto genérico"],
        "zona_preferida": "bosque",
        "_fallback_reason": reason
    }


def guardar_en_disk(user_id: str, perfil: dict, mensajes: list = None, data_dir: str = "data/personas", nombre_autoritativo: str = None) -> None:
    """
    Guarda el perfil en disco como archivos .md y .json.

    Args:
        user_id: ID del usuario
        perfil: Perfil destilado
        mensajes: Lista de mensajes original (para contar calidad)
        data_dir: Directorio base para guardar
        nombre_autoritativo: Nombre real del usuario en Discord (OBLIGATORIO para evitar carpetas "Anonymous User")
    """
    try:
        # Usar SIEMPRE el nombre autoritativo de Discord, NO el extraído por LLM
        user_name = nombre_autoritativo or perfil.get("nombre", user_id)
        base = Path(data_dir) / f"{user_id} - {user_name}"
        base.mkdir(parents=True, exist_ok=True)
        
        # Calidad del perfil basada en mensajes
        mensajes_count = len(mensajes) if mensajes else 500
        if mensajes_count >= 500:
            calidad = "alta"
        elif mensajes_count >= 250:
            calidad = "media"
        else:
            calidad = "baja"
        
        # 1. perfil_completo.md (lectura humana)
        perfil_md = f"""# Perfil de {user_name}

## Información General
- **Nombre**: {user_name}
- **Pronombres**: {perfil.get('pronombres', 'él/ella')}
- **Calidad**: {calidad} ({mensajes_count} mensajes)
- **Última actualización**: {perfil.get('ultima_actualizacion', 'desconocida')}

## Estadísticas de Juego
{json.dumps(perfil.get('estadisticas_juego', {}), indent=2)}

## Estrategia de Supervivencia
{perfil.get('estrategia_supervivencia', 'No definida')}

## Estado Emocional Inicial
{json.dumps(perfil.get('estado_emocional', {}), indent=2)}

## Inventario Inicial
{json.dumps(perfil.get('inventario_inicial', []), indent=2)}

## Zona Preferida
{perfil.get('zona_preferida', 'bosque')}

## Estilo de Habla
### Descripción
{perfil.get('estilo_habla', {}).get('descripcion_detallada', '')}

### Patrones
{chr(10).join(f'- {p}' for p in perfil.get('estilo_habla', {}).get('patrones', []))}

### Muletillas
{chr(10).join(f'- {m}' for m in perfil.get('estilo_habla', {}).get('muletillas', []))}

### Voz Simulada
{perfil.get('estilo_habla', {}).get('voz_simulada', '')}

### Guía de Escritura
{perfil.get('estilo_habla', {}).get('guia_escritura', '')}

## Personalidad
### Arquetipo
{perfil.get('personalidad', {}).get('arquetipo_supervivencia', '')}

### Descripción Psicológica
{perfil.get('personalidad', {}).get('descripcion_psicologica', '')}

### Trigger Palabras
{chr(10).join(f'- {t}' for t in perfil.get('personalidad', {}).get('trigger_palabras', []))}

## Social
### Aliados Probables
{chr(10).join(f'- {a}' for a in perfil.get('social', {}).get('aliados_probables', []))}

### Enemigos Probables
{chr(10).join(f'- {e}' for e in perfil.get('social', {}).get('enemigos_probables', []))}

### Estilo de Conflicto
{perfil.get('social', {}).get('estilo_conflicto', '')}

## Cómo Moriría
{perfil.get('como_moriria', '')}
"""
        (base / "perfil_completo.md").write_text(perfil_md, encoding="utf-8")
        
        # 2. agente_core.json (para carga rápida en simulación)
        stats = perfil.get("estadisticas_juego", {})
        estilo = perfil.get("estilo_habla", {})
        personalidad = perfil.get("personalidad", {})
        
        # Zona basada en preferencia
        zonas_validas = ["bosque", "bunker", "arena", "cueva", "playa", "ciudad"]
        zona_preferida = perfil.get("zona_preferida", "bosque")
        if zona_preferida not in zonas_validas:
            zona_preferida = random.choice(zonas_validas)
        
        agente_core = {
            "hash_historial": perfil.get("_hash", ""),
            "nombre": perfil.get("nombre", user_name),
            "pronombres": perfil.get("pronombres", "él/ella"),
            "stats": {
                "fuerza": stats.get("fuerza", 5),
                "agilidad": stats.get("agilidad", 5),
                "carisma": stats.get("carisma", 5),
                "supervivencia": stats.get("supervivencia", 5),
                "inteligencia": stats.get("inteligencia", 5),
                "suerte": stats.get("suerte", 5),
            },
            "zona_actual": zona_preferida,
            "hp": 100,
            "inventario": perfil.get("inventario_inicial", []),
            "perfil_completo": perfil,  # Guardar perfil completo también
            "system_prompt_simulacion": perfil.get("system_prompt_simulacion", ""),
            "trigger_palabras": personalidad.get("trigger_palabras", []),
            "como_moriria": perfil.get("como_moriria", ""),
            "estado_emocional": perfil.get("estado_emocional", {"miedo": 5, "confianza_en_otros": 5, "desesperacion": 5, "agresividad": 5, "esperanza": 5}),
        }
        (base / "agente_core.json").write_text(json.dumps(agente_core, indent=2, ensure_ascii=False), encoding="utf-8")
        
        logger.info(f"Perfil guardado en {base}")
        
    except Exception as e:
        logger.error(f"Error guardando perfil en disco: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

async def cargar_o_destilar(
    user_id: int,
    guild_id: int,
    user_name: str,
    db,
    bot,
    model_name: str = "gemma-4-26b-a4b-it",
) -> dict:
    """
    Carga un perfil desde disco si existe y es válido,
    o lo destila desde cero si no existe o el hash cambió.
    
    Returns:
        dict con todos los campos del perfil
    """
    data_dir = Path("data/personas")
    cache_file = data_dir / f"{user_id} - {user_name}" / "agente_core.json"
    
    # Intentar cargar desde caché
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                agente_core = json.load(f)

            # Verificar que tiene los campos necesarios (nuevos campos)
            # Y que NO es un perfil fallback (necesita re-destilarse con datos reales)
            if (agente_core.get("stats", {}).get("inteligencia") is not None
                    and agente_core.get("pronombres")
                    and agente_core.get("system_prompt_simulacion")
                    and not agente_core.get("perfil_completo", {}).get("_fallback_reason")):
                logger.debug(f"Perfil cacheado válido para {user_name}")
                return agente_core
        except (json.JSONDecodeError, IOError):
            pass

    # Destilar nuevo perfil
    logger.info(f"Destilando perfil para {user_name} ({user_id})...")
    mensajes = await extraer_historial(user_id, guild_id, db, limite=500)
    
    if not mensajes:
        logger.warning(f"No hay mensajes para {user_name}, usando fallback")
        return _perfil_fallback(user_name, "sin mensajes")
    
    perfil = await destilar_perfil(mensajes, user_name, bot, model_name)
    
    # Integrar detector de género y pronombres
    perfil = integrar_detector_en_perfil(perfil, mensajes)
    
    # Actualizar timestamp con hora real
    perfil["ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
    
    # Guardar a disco
    guardar_en_disk(str(user_id), perfil, mensajes, nombre_autoritativo=user_name)
    
    # Retornar en formato agente_core
    agente_core = {
        "hash_historial": perfil.get("_hash", ""),
        "nombre": user_name,
        "pronombres": perfil.get("pronombres", "él/ella"),
        "stats": perfil.get("estadisticas_juego", {
            "fuerza": 5, "agilidad": 5, "carisma": 5,
            "supervivencia": 5, "inteligencia": 5, "suerte": 5
        }),
        "zona_actual": perfil.get("zona_preferida", "bosque"),
        "hp": 100,
        "inventario": perfil.get("inventario_inicial", []),
        "perfil_completo": perfil,
        "system_prompt_simulacion": perfil.get("system_prompt_simulacion", ""),
        "trigger_palabras": perfil.get("personalidad", {}).get("trigger_palabras", []),
        "como_moriria": perfil.get("como_moriria", ""),
        "estado_emocional": perfil.get("estado_emocional", {"miedo": 5, "agresividad": 5, "desesperacion": 5, "esperanza": 5, "confianza_en_otros": 5}),
    }
    
    return agente_core
