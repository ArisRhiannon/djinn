"""
TorneoCog v9 — GM Omnipotente.

Pipeline V9: 1 llamada por fase. El GM es DIOS.
Mueve, habla, actúa y narra TODOS los personajes con voces auténticas.
Recibe fichas destiladas (voz_simulada, muestras_reales, muletillas, guia_escritura).
~1 llamada por fase. 7 fases = 7 llamadas + 3 setup = 10 total.
Coherencia cinematográfica total, firmas lingüísticas preservadas.
"""

from __future__ import annotations

import asyncio
import io
import json
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from utils.torneo_renderer import TorneoRenderer
from utils.security import can_use_youkai_nl


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

MAX_PARTICIPANTS = 24
MAX_MESSAGES_PER_USER = 250
DISTILLATION_MAX_TOKENS = 6000
STORY_BIBLE_MAX_TOKENS = 4000
AGENDA_MAX_TOKENS = 5000
PHASE_JSON_MAX_TOKENS = 16000  # V9: GM hace TODO en 1 llamada

# 10 RPM reales con margen de seguridad
RATE_LIMIT_CALLS = 9
RATE_LIMIT_WINDOW = 62.0
RATE_LIMIT_COOLDOWN = 65.0    # espera si se alcanza el límite

MAX_JSON_RETRIES = 2
MAX_FASES = 7

PHASE_PACING_SECONDS = 15
MAX_CONCURRENT_LLM = 4        # semáforo de concurrencia


# ══════════════════════════════════════════════════════════════════════════════
# SISTEMA D20
# ══════════════════════════════════════════════════════════════════════════════

def _roll_d20() -> int:
    return random.randint(1, 20)

def _interpret_roll(roll: int) -> Dict[str, Any]:
    if roll == 1:
        return {"resultado": "DESASTRE CRÍTICO", "modificador": -10,
                "narrativa": "Todo sale terriblemente mal. El peor escenario posible."}
    elif roll <= 5:
        return {"resultado": "Fallo grave", "modificador": -3,
                "narrativa": "Las cosas van mal. Error de cálculo o mala suerte."}
    elif roll <= 10:
        return {"resultado": "Fallo leve", "modificador": -1,
                "narrativa": "No sale como esperabas pero no es catastrófico."}
    elif roll <= 15:
        return {"resultado": "Éxito parcial", "modificador": 2,
                "narrativa": "Funciona razonablemente bien."}
    elif roll <= 19:
        return {"resultado": "Éxito rotundo", "modificador": 5,
                "narrativa": "Todo sale según lo planeado o mejor."}
    else:  # 20
        return {"resultado": "ÉXITO CRÍTICO", "modificador": 10,
                "narrativa": "Golpe de genio. El destino sonríe. Momento épico."}


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT: DESTILACIÓN
# ══════════════════════════════════════════════════════════════════════════════

_DISTILLATION_SYSTEM = """Eres un Analista de Personalidad Forense.

Tu trabajo: examinar el historial COMPLETO de mensajes de UN usuario y construir
una ficha de personalidad EXTREMADAMENTE DETALLADA. Mínimo 1800 tokens.

FORMATO (JSON estricto):
{
  "nombre": "display_name",
  "estilo_habla": {
    "descripcion_detallada": "Párrafo extenso de su huella digital de escritura.",
    "patrones": ["6-9 patrones observados con ejemplos"],
    "muletillas": ["10-15 muletillas REALES del historial"],
    "muestras_reales": ["cita 1", "cita 2", "cita 3", "cita 4", "cita 5", "cita 6"],
    "ortografia": "errores, abreviaturas, peculiaridades",
    "emojis_favoritos": ["emoji1", "emoji2", "emoji3", "emoji4"],
    "insultos_favoritos": ["exacto1", "exacto2"],
    "estructura_mensajes": "frases cortas/largas, puntuación, espaciado",
    "voz_simulada": [
      "Cómo acusaría: [COMO ELLOS]",
      "Cómo se defendería: [COMO ELLOS]",
      "Cómo reaccionaría a un cadáver: [COMO ELLOS]",
      "Cómo amenazaría: [COMO ELLOS]",
      "Cómo confesaría: [COMO ELLOS]",
      "Cómo pediría alianza: [COMO ELLOS]"
    ],
    "anti_patrones": ["NUNCA hace X"],
    "guia_escritura": "Regla de oro de 3 oraciones para escribir como esta persona."
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
    "aliados_probables": ["nombre1", "nombre2", "nombre3"],
    "enemigos_probables": ["nombre1", "nombre2"],
    "estilo_conflicto": "DETALLADO",
    "estilo_alianza": "DETALLADO",
    "rol_en_grupo": "líder/seguidor/provocador/etc",
    "carisma_descripcion": "cómo cae a los demás"
  },
  "estadisticas_juego": {
    "fuerza": 5, "inteligencia": 5, "carisma": 5, "supervivencia": 5, "traicion": 5,
    "justificacion": "una oración por stat"
  },
  "frase_iconica": "COMO ELLOS la escribirían",
  "estrategia_supervivencia": "3-4 oraciones",
  "como_moriria": "muerte poética o irónica"
}

REGLAS: voz_simulada es LO MÁS IMPORTANTE. Escrito COMO LA PERSONA.
muestras_reales = citas TEXTUALES. Sé despiadadamente honesto. CADA campo LLENO."""


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT: STORY BIBLE
# ══════════════════════════════════════════════════════════════════════════════

_STORY_BIBLE_SYSTEM = """Eres el SHOWRUNNER de un thriller de misterio y terror psicológico.

Diseña el STORY BIBLE basado en las fichas reales y los ROLES ASIGNADOS.

FORMATO (JSON):
{
  "titulo_del_misterio": "Título cinematográfico y tétrico",
  "tema_central": "La pregunta temática",
  "logline": "25 palabras de tensión central",
  "arco_narrativo": {
    "acto_1_paranoia": "Primer cuerpo, se siembra la duda",
    "acto_2_caceria": "Cacería, inocentes acusados",
    "acto_2_crisis": "Quiebre total, paranoia máxima",
    "acto_3_revelacion": "Enfrentamiento final"
  },
  "perfil_asesino_principal": {
    "nombre": "nombre exacto",
    "motivo_oculto": "por qué mata, basado en su ficha",
    "modus_operandi": "cómo mata, refleja su personalidad",
    "firma": "detalle macabro que siempre deja"
  },
  "perfil_detective": {
    "nombre": "nombre exacto",
    "estilo_investigacion": "metódico/agresivo/paranoico",
    "debilidad_fatal": "defecto que el asesino explotará"
  },
  "dinamicas_centrales": [
    {"descripcion": "tensión A-B", "personajes": ["A","B"], "potencial_dramatico": "..."}
  ],
  "ganador_ideal": {"nombre": "...", "justificacion": "impacto temático"}
}

Basado TODO en fichas reales. Ambicioso, oscuro, retorcido."""


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT: AGENDAS
# ══════════════════════════════════════════════════════════════════════════════

_AGENDA_SYSTEM = """Eres el PSICÓLOGO DE CASTING.

Genera las agendas personales ocultas de TODOS los participantes.
El asesino sabe que es el asesino. El detective sabe que es el detective.

FORMATO (JSON):
{
  "NombreExacto": {
    "deseo_profundo": "qué quieren realmente",
    "miedo_nuclear": "terror más profundo",
    "secreto_que_parece_culpable": "secreto turbio que los hace parecer sospechosos",
    "opinion_del_detective": "qué piensan del Detective",
    "contradiccion_interna": "tensión entre querer y hacer",
    "momento_quiebre": "qué los haría explotar"
  }
}

Cada campo basado en la ficha real. TODOS deben tener agenda."""


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIOS (pool de 20, se elige UNO por partida)
# ══════════════════════════════════════════════════════════════════════════════

_SCENARIOS = [
    # ══════════════════════════════════════════════════════════════════════
    # 1. MANSIONES — El clásico absoluto
    # ══════════════════════════════════════════════════════════════════════
    {
        "nombre": "Roca del Cuervo",
        "descripcion": "Isla privada frente a los acantilados de Cornualles. Una mansión eduardiana encaramada en la roca. La marea alta inunda el único camino de vuelta y la tormenta ha cortado el telégrafo. Doce invitados. Nadie sabe quién los convocó.",
        "lugares": [
            "Vestíbulo", "Comedor", "Biblioteca", "Sala de Trofeos",
            "Cocina", "Bodega", "Torreón", "Embarcadero",
        ],
        "elementos": [
            "diez figuras de porcelana en la repisa del comedor — una menos cada mañana",
            "un gramófono que reproduce valses a medianoche sin que nadie le dé cuerda",
            "cartas de invitación con la misma letra pero firmas distintas",
            "la biblioteca del ala este con un diario íntimo escondido tras un ladrillo suelto",
            "el embarcadero destrozado por las olas — no hay botes, no hay salida",
            "un revólver Webley con seis balas y un nombre grabado en la culata",
        ],
    },
    {
        "nombre": "Cipreses Altos",
        "descripcion": "Hacienda colonial en una isla del Caribe. Plantaciones abandonadas, calor sofocante. El barco que trajo a los invitados no volverá hasta dentro de una semana. Los sirvientes se fueron al amanecer sin decir palabra. Queda una casa, sus secretos, y el sonido de tambores lejanos en la selva.",
        "lugares": [
            "Patio Central", "Salón Principal", "Cobertizo", "Bodega del Sótano",
            "Pozo", "Cocina", "Selva Norte", "Embarcadero Viejo",
        ],
        "elementos": [
            "el cuaderno de cuentas del patrón — páginas arrancadas que alguien está recomponiendo",
            "machetes de caña en el cobertizo, uno de ellos con el filo recién limpiado",
            "una muñeca de trapo clavada en la puerta principal con un alfiler en el corazón",
            "el pozo del patio: alguien dejó caer una linterna y sigue encendida allá abajo",
            "diarios de a bordo del bergantín San Telmo — su capitán desapareció en esta isla en 1847",
            "ron y opio en la bodega del sótano — suficiente para que alguien no despierte jamás",
        ],
    },
    # ══════════════════════════════════════════════════════════════════════
    # 2. TREN — Sin parada, sin escape
    # ══════════════════════════════════════════════════════════════════════
    {
        "nombre": "El Simplon Express",
        "descripcion": "Tren nocturno Milán-Estambul, 1934. Los Alpes suizos bajo una nevada histórica. El convoy quedó detenido por un alud sobre las vías. Sin telégrafo, sin pueblo cercano. Los pasajeros del vagón cama se miran con desconfianza: uno de ellos no es quien dice ser. El revisor no aparece desde hace tres horas.",
        "lugares": [
            "Vagón Restaurante", "Vagón Cama A", "Vagón Cama B",
            "Vagón de Equipajes", "Cabina del Maquinista", "Furgón de Cola",
            "Techo del Tren", "Túnel de Lausanne",
        ],
        "elementos": [
            "un pasaporte diplomático falso en el equipaje del compartimento 7 — la foto no coincide con nadie",
            "el vagón restaurante: una botella de chartreuse con sedimento sospechoso en el fondo",
            "la puerta del vagón de equipajes está forzada. Dentro, un baúl con cerradura reventada y ropa de mujer",
            "el registro de pasajeros tiene un nombre tachado con tinta negra — ilegible pero reciente",
            "un estuche médico con morfina y jeringuillas. El doctor del tren asegura que no es suyo",
            "humo en el túnel de Lausanne — alguien encendió una bengala y la arrojó a las vías",
        ],
    },
    # ══════════════════════════════════════════════════════════════════════
    # 3. MONTAÑA — Nieve, silencio, muerte
    # ══════════════════════════════════════════════════════════════════════
    {
        "nombre": "El Refugio Klausen",
        "descripcion": "Albergue alpino a 2800 metros en los Dolomitas. Once montañeros atrapados por una ventisca que durará al menos cuatro días. Provisiones contadas. Un solo generador de gasolina. La radio solo emite estática. Alguien cortó la cuerda de seguridad del puente colgante. Están aislados. Y uno de ellos lo sabía antes de subir.",
        "lugares": [
            "Dormitorio Norte", "Dormitorio Sur", "Cocina del Refugio",
            "Sala de Radio", "Armario de Equipo", "Mirador Este",
            "Puente Colgante", "Generador",
        ],
        "elementos": [
            "cuerdas de escalada con nudos de sabotaje — un corte limpio, no un desgaste",
            "el diario de cumbre: alguien escribió 'el séptimo no bajará' con letra temblorosa",
            "piolets guardados en el armario — la funda de uno está manchada de algo oscuro y seco",
            "un mapa de la ruta sur con marcas que no hizo el guía — alguien exploró solo",
            "raciones de emergencia alteradas: latas con fechas de caducidad raspadas y vueltas a escribir",
            "la ventana del dormitorio norte no cierra bien. Afuera, la nieve tiene huellas que van... y no vuelven",
        ],
    },
    # ══════════════════════════════════════════════════════════════════════
    # 4. MAR — Barco sin rumbo
    # ══════════════════════════════════════════════════════════════════════
    {
        "nombre": "El Albatros",
        "descripcion": "Goleta de tres mástiles en ruta Atenas-Alejandría. Mar Jónico, 1898. La tripulación despertó con el capitán muerto en su camarote — puerta cerrada por dentro. Los oficiales se acusan entre sí. Sin viento desde hace dos días, el barco deriva. Las provisiones de agua bajan más rápido de lo que deberían. Alguien está vaciando los barriles.",
        "lugares": [
            "Camarote del Capitán", "Cubierta de Proa", "Cubierta de Popa",
            "Bodega de Carga", "Camarote de Oficiales", "Cocina del Barco",
            "Cofa del Mástil", "Bodega del Agua",
        ],
        "elementos": [
            "la bitácora del capitán: la última página describe un motín... fechada mañana",
            "una brújula que no apunta al norte sino al camarote del contramaestre",
            "el arcón de medicinas del boticario de a bordo — frascos cambiados de sitio, uno vacío",
            "redes de pesca arrastrando algo pesado por estribor — demasiado pequeño para un pez",
            "la campana de niebla suena sola a las tres de la madrugada. Nadie la toca. Nadie la oye tocar",
            "un bote salvavidas con provisiones para seis. En un barco con treinta almas. Alguien planeaba escapar solo",
        ],
    },
    # ══════════════════════════════════════════════════════════════════════
    # 5. ABADÍA — Dios no contesta
    # ══════════════════════════════════════════════════════════════════════
    {
        "nombre": "Abadía de San Gotardo",
        "descripcion": "Monasterio benedictino en la cima de una colina toscana. La carretera se derrumbó con las lluvias de otoño. Ni coches ni carretas. Los monjes acogen a los viajeros varados. Pero los monjes no son lo que parecen: las oraciones se interrumpen, los hábitos esconden cicatrices de guerra, y el sótano de la cripta está cerrado con tres candados distintos.",
        "lugares": [
            "Capilla", "Cripta", "Biblioteca Monacal", "Campanario",
            "Sacristía", "Refectorio", "Jardín de Hierbas", "Celdas de los Monjes",
        ],
        "elementos": [
            "un códice iluminado del siglo XIV en la biblioteca — la última página desgarrada con prisa",
            "la cripta: lápidas con nombres raspados. Una de ellas tiene tierra fresca alrededor de la base",
            "el confesionario de madera: alguien dejó una nota doblada— 'perdóname, padre, lo haré otra vez'",
            "el campanario solo tiene acceso con llave. La llave la tiene el hermano portero, que ha enmudecido",
            "vinos de misa en la sacristía — una botella sin etiqueta, más amarga que el resto",
            "el jardín de hierbas medicinales: dedalera y belladona entre la manzanilla. Alguien sabe de venenos",
        ],
    },
    # ══════════════════════════════════════════════════════════════════════
    # 6. PÁRAMO — Nada en kilómetros
    # ══════════════════════════════════════════════════════════════════════
    {
        "nombre": "La Posada del Brezo",
        "descripcion": "Casa de postas abandonada en los páramos de Yorkshire. La diligencia volcó en el barro a tres millas. Los pasajeros caminaron bajo la lluvia hasta esta ruina. Hay un teléfono de manivela que no funciona, chimeneas que echan humo negro, y una habitación cerrada con llave en el piso de arriba. La llave cuelga del cuello de una mujer que no habla con nadie. El páramo se traga los gritos.",
        "lugares": [
            "Vestíbulo", "Cocina", "Comedor", "Habitación 4",
            "Desván", "Cuadra", "Páramo Norte", "Sótano",
        ],
        "elementos": [
            "el libro de registro de la posada: la última entrada es de 1911 y termina a mitad de frase",
            "cerradura de la habitación 4 — arañazos profundos en la madera, del lado de fuera",
            "cartas sin abrir en el buró del vestíbulo. Todas para la misma persona. Ningún remitente.",
            "turba cortada en el páramo cercano — una pila demasiado ordenada. Esconde algo debajo",
            "la cocina: un horno aún caliente con cenizas de papel. Fragmentos legibles: '...no debe saber...'",
            "la veleta del tejado gira al revés. Marca norte cuando sopla el sur. Es la única dirección que miente",
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# DESTILACIÓN → VOZ DEL AGENTE  (todas las piezas se usan)
# ══════════════════════════════════════════════════════════════════════════════

def _build_agent_voice_block(ficha: Dict, max_chars: int = 2200) -> str:
    """
    Ensambla TODOS los campos de la destilación en un bloque de voz
    inyectable en cada prompt de agente. NADA se desperdicia.

    Devuelve texto denso y accionable que el LLM puede absorber como
    identidad completa del personaje.
    """
    h = ficha.get("estilo_habla", {}) or {}
    p = ficha.get("personalidad", {}) or {}
    s = ficha.get("social", {}) or {}
    e = ficha.get("estadisticas_juego", {}) or {}

    parts = []

    # ── VOZ SIMULADA (lo más importante: cómo habla en cada situación) ──
    voz = _safe_list(h.get("voz_simulada"))
    if voz:
        parts.append("🎭 CÓMO HABLAS EN CADA SITUACIÓN (tu voz real):\n" + "\n".join(f"  • {v}" for v in voz))

    # ── MUESTRAS REALES (citas textuales — oro puro) ──
    muestras = _safe_list(h.get("muestras_reales"), 6)
    if muestras:
        parts.append("📝 TUS MENSAJES REALES (así escribes TÚ exactamente):\n" + "\n".join(f'  "{m}"' for m in muestras))

    # ── FRASE ICÓNICA ──
    frase = _safe_str(ficha.get("frase_iconica"))
    if frase and frase != "...":
        parts.append(f'💎 TU FRASE ICÓNICA: "{frase}"')

    # ── DESCRIPCIÓN DETALLADA DE HABLA ──
    desc = _safe_str(h.get("descripcion_detallada"))
    if desc and len(desc) > 20:
        parts.append(f"🔬 HUELLA DE ESCRITURA: {desc}")

    # ── GUÍA DE ESCRITURA (regla de oro) ──
    guia = _safe_str(h.get("guia_escritura"))
    if guia:
        parts.append(f"📏 REGLA DE ORO PARA ESCRIBIR COMO TÚ: {guia}")

    # ── PATRONES ──
    patrones = _safe_list(h.get("patrones"), 6)
    if patrones:
        parts.append("🔄 PATRONES OBSERVADOS: " + " | ".join(patrones))

    # ── MULETILLAS ──
    muletillas = _safe_list(h.get("muletillas"), 10)
    if muletillas:
        parts.append("🗣️ MULETILLAS (ÚSALAS): " + ", ".join(muletillas))

    # ── ORTOGRAFÍA ──
    ort = _safe_str(h.get("ortografia"))
    if ort and ort != "estándar":
        parts.append(f"✍️ ORTOGRAFÍA: {ort}")

    # ── INSULTOS FAVORITOS ──
    insultos = _safe_list(h.get("insultos_favoritos"))
    if insultos:
        parts.append("🤬 INSULTOS FAVORITOS: " + ", ".join(insultos))

    # ── EMOJIS FAVORITOS ──
    emojis = _safe_list(h.get("emojis_favoritos"))
    if emojis:
        parts.append("😀 EMOJIS FAVORITOS: " + " ".join(emojis))

    # ── ESTRUCTURA DE MENSAJES ──
    estructura = _safe_str(h.get("estructura_mensajes"))
    if estructura and estructura != "desconocida":
        parts.append(f"📐 ESTRUCTURA: {estructura}")

    # ── ANTI-PATRONES (lo que NUNCA harías) ──
    anti = _safe_list(h.get("anti_patrones"))
    if anti and anti != ["estilo completamente desconocido"]:
        parts.append("🚫 NUNCA HACES: " + " | ".join(anti))

    # ── ARQUETIPO + RASGOS ──
    arq = _safe_str(p.get("arquetipo_supervivencia"))
    rasgos = _safe_list(p.get("rasgos_dominantes"))
    if arq or rasgos:
        parts.append(f"🧬 ARQUETIPO: {arq} | RASGOS: {', '.join(rasgos)}")

    # ── DESCRIPCIÓN PSICOLÓGICA ──
    psic = _safe_str(p.get("descripcion_psicologica"))
    if psic and len(psic) > 20:
        parts.append(f"🧠 PSICOLOGÍA: {psic}")

    # ── RED FLAGS / GREEN FLAGS ──
    red = _safe_list(p.get("red_flags"))
    green = _safe_list(p.get("green_flags"))
    if red and red != ["desconocido"]:
        parts.append("🔴 RED FLAGS: " + "; ".join(red))
    if green and green != ["desconocido"]:
        parts.append("🟢 GREEN FLAGS: " + "; ".join(green))

    # ── TRIGGER PALABRAS ──
    triggers = _safe_list(p.get("trigger_palabras"))
    if triggers:
        parts.append("💥 TE ACTIVAN: " + ", ".join(triggers))

    # ── DATO CURIOSO ──
    dato = _safe_str(p.get("dato_curioso"))
    if dato and dato != "Nadie sabe nada.":
        parts.append(f"🔍 DATO CURIOSO: {dato}")

    # ── SOCIAL: aliados, enemigos, estilo de conflicto, rol ──
    aliados = _safe_list(s.get("aliados_probables"))
    enemigos = _safe_list(s.get("enemigos_probables"))
    if aliados:
        parts.append("🤝 ALIADOS NATURALES: " + ", ".join(aliados))
    if enemigos:
        parts.append("⚔️ ENEMIGOS NATURALES: " + ", ".join(enemigos))
    estilo_c = _safe_str(s.get("estilo_conflicto"))
    if estilo_c:
        parts.append(f"🥊 ESTILO DE CONFLICTO: {estilo_c}")
    estilo_a = _safe_str(s.get("estilo_alianza"))
    if estilo_a:
        parts.append(f"🤝 ESTILO DE ALIANZA: {estilo_a}")
    rol_g = _safe_str(s.get("rol_en_grupo"))
    if rol_g:
        parts.append(f"👥 ROL EN GRUPO: {rol_g}")
    carisma = _safe_str(s.get("carisma_descripcion"))
    if carisma:
        parts.append(f"✨ CARISMA: {carisma}")

    # ── ESTADÍSTICAS ──
    stats = []
    for stat_name in ("fuerza", "inteligencia", "carisma", "supervivencia", "traicion"):
        val = e.get(stat_name, 5)
        stars = "★" * val + "☆" * (10 - val)
        stats.append(f"{stat_name}: {stars} ({val}/10)")
    parts.append("🎲 STATS: " + " | ".join(stats))

    # ── ESTRATEGIA DE SUPERVIVENCIA ──
    estrategia = _safe_str(ficha.get("estrategia_supervivencia"))
    if estrategia and len(estrategia) > 10:
        parts.append(f"🎯 ESTRATEGIA: {estrategia}")

    # ── CÓMO MORIRÍA ──
    muerte = _safe_str(ficha.get("como_moriria"))
    if muerte and muerte != "Muerte por causas desconocidas.":
        parts.append(f"💀 MUERTE PROFÉTICA: {muerte}")

    result = "\n\n".join(parts)
    # Truncar inteligentemente — nunca cortar a mitad de línea
    if len(result) > max_chars:
        lines = result.split("\n")
        truncated = []
        current = 0
        for line in lines:
            if current + len(line) + 1 > max_chars:
                break
            truncated.append(line)
            current += len(line) + 1
        result = "\n".join(truncated)
    return result


def _build_memoria_viva(
    memoria_agentes: Dict[str, str],
    eventos: List[Dict],
    board_state: Dict[str, str],
    vivos: List[str],
    muertos: List[str],
    fase_num: int,
) -> Dict[str, str]:
    """
    Memoria narrativa viva por agente. No es solo un resumen — es el contexto
    concreto de lo que CADA agente vivió, dijo y presenció esta fase.

    Se inyecta en el prompt de intenciones y reacciones para que
    NUNCA empiecen en blanco.
    """
    urgency_map = {
        1: "calma tensa", 2: "inquietud creciente", 3: "paranoia",
        4: "desesperación", 5: "modo supervivencia", 6: "instinto animal",
        7: "último aliento",
    }

    mis_eventos: Dict[str, List[str]] = {name: [] for name in vivos}
    mis_dialogos: Dict[str, List[str]] = {name: [] for name in vivos}
    con_quien_estuve: Dict[str, set] = {name: set() for name in vivos}
    relaciones: Dict[str, Dict[str, str]] = {name: {} for name in vivos}

    for evt in eventos:
        protas = evt.get("nombres_protagonistas", [])
        accion = evt.get("accion", "")
        dialogos = evt.get("dialogos", {})
        lugar = evt.get("lugar", board_state.get(protas[0], "desconocido")) if protas else "desconocido"

        for name in protas:
            if name not in mis_eventos:
                continue
            mis_eventos[name].append(f"📍 {lugar}: {accion[:200]}")
            for other in protas:
                if other != name:
                    con_quien_estuve[name].add(other)
            if name in dialogos and dialogos[name]:
                mis_dialogos[name].append(dialogos[name][:150])

    for name in vivos:
        for other in vivos:
            if other == name:
                continue
            if other in con_quien_estuve.get(name, set()):
                relaciones[name][other] = "interactué — mi opinión está fresca y basada en hechos"
            else:
                relaciones[name][other] = "no interactuamos — solo puedo especular"

    urgency = urgency_map.get(fase_num, "colapso total")
    new_memory: Dict[str, str] = {}

    for name in vivos:
        parts = []
        parts.append(f"FASE ACTUAL: {fase_num}/7 — Nivel de urgencia: {urgency.upper()}.")

        if mis_eventos.get(name):
            parts.append("LO QUE ACABA DE PASAR (esta misma fase):")
            for e in mis_eventos[name][-3:]:
                parts.append(f"  {e}")

        if mis_dialogos.get(name):
            parts.append("LO QUE TÚ DIJISTE ESTA FASE (no lo repitas — construye sobre ello):")
            for d in mis_dialogos[name][-2:]:
                parts.append(f'  "{d}"')

        if relaciones.get(name):
            parts.append("TU RELACIÓN CON CADA VIVO:")
            for other, status in relaciones[name].items():
                parts.append(f"  {other}: {status}")

        if muertos:
            parts.append(
                f"CAÍDOS: {', '.join(muertos[-5:])}. "
                "Cada muerte cambia el tablero. Recalcula tus alianzas y sospechas."
            )

        where = board_state.get(name, "desconocido")
        parts.append(f"AHORA ESTÁS EN: {where}.")
        parts.append(f"VIVOS: {', '.join(v for v in vivos if v != name)}.")

        prev = memoria_agentes.get(name, "")
        if prev:
            parts.append(f"RESUMEN DE FASES ANTERIORES: {prev[:400]}")

        new_memory[name] = "\n".join(parts)

    return new_memory




def _build_agent_agenda_block(agendas: Dict, nombre: str) -> str:
    """
    Inyecta la agenda oculta del agente (deseo, miedo, secreto, quiebre)
    para que sus decisiones tengan profundidad psicológica.
    """
    a = agendas.get(nombre, {})
    if not a or not isinstance(a, dict):
        return ""

    parts = []
    if _safe_str(a.get("deseo_profundo")):
        parts.append(f"💭 DESEO PROFUNDO: {_safe_str(a['deseo_profundo'])}")
    if _safe_str(a.get("miedo_nuclear")):
        parts.append(f"😱 MIEDO NUCLEAR: {_safe_str(a['miedo_nuclear'])}")
    if _safe_str(a.get("secreto_que_parece_culpable")):
        parts.append(f"🔒 SECRETO TURBIO (te hace parecer culpable): {_safe_str(a['secreto_que_parece_culpable'])}")
    if _safe_str(a.get("contradiccion_interna")):
        parts.append(f"⚡ CONTRADICCIÓN INTERNA: {_safe_str(a['contradiccion_interna'])}")
    if _safe_str(a.get("momento_quiebre")):
        parts.append(f"💥 MOMENTO DE QUIEBRE: {_safe_str(a['momento_quiebre'])}")
    if _safe_str(a.get("opinion_del_detective")):
        parts.append(f"🕵️ TU OPINIÓN DEL DETECTIVE: {_safe_str(a['opinion_del_detective'])}")

    if not parts:
        return ""
    return "🎭 TU AGENDA OCULTA:\n" + "\n".join(parts)


def _safe_list(value: Any, max_items: Optional[int] = None) -> List:
    """
    Defensa contra LLM que devuelve dict en vez de list.
    - None / no-list → []
    - dict → list(dict.values())  (el LLM a veces pone {0: "x", 1: "y"})
    - string → [string]
    - list → list (truncada si max_items)
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value[:max_items] if max_items else list(value)
    if isinstance(value, dict):
        items = list(value.values()) if value else []
        return items[:max_items] if max_items else items
    if isinstance(value, str):
        return [value] if max_items is None or max_items > 0 else []
    try:
        items = list(value)
        return items[:max_items] if max_items else items
    except TypeError:
        return [str(value)] if max_items is None or max_items > 0 else []


def _safe_str(value: Any, fallback: str = "") -> str:
    """Defensa contra LLM que devuelve list/dict en vez de string."""
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return fallback
    return str(value)


def _enforce_d20_rolls(narracion: dict, server_rolls: dict) -> None:
    """Forza los D20 pre-rolados por el servidor si el LLM se inventó los suyos."""
    for evt in narracion.get("eventos", []):
        if evt.get("d20_roll") and evt["d20_roll"] not in server_rolls.values():
            protas = evt.get("nombres_protagonistas", [])
            if protas and protas[0] in server_rolls:
                evt["d20_roll"] = server_rolls[protas[0]]


def _clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return text.strip()


def _estimate_tokens(text: str) -> int:
    return int(len(text) / 3.5)


def _condense_fichas(fichas: Dict, vivos: List[str], max_chars: int = 15000) -> str:
    """Condensa fichas para prompts de planificación con datos accionables para el GM."""
    condensed = {}
    for name in vivos:
        if name not in fichas:
            continue
        f = fichas[name]
        h = f.get("estilo_habla", {})
        p = f.get("personalidad", {})
        s = f.get("social", {})
        e = f.get("estadisticas_juego", {})
        condensed[name] = {
            "arquetipo": _safe_str(p.get("arquetipo_supervivencia")),
            "rasgos": _safe_list(p.get("rasgos_dominantes"), 8),
            "guia_escritura": _safe_str(h.get("guia_escritura")),
            "voz_simulada": _safe_list(h.get("voz_simulada"), 4),
            "muletillas": _safe_list(h.get("muletillas"), 10),
            "insultos_favoritos": _safe_list(h.get("insultos_favoritos"), 10),
            "frase_iconica": _safe_str(f.get("frase_iconica")),
            "anti_patrones": _safe_list(h.get("anti_patrones")),
            "descripcion_psicologica": _safe_str(p.get("descripcion_psicologica"))[:250],
            "red_flags": _safe_list(p.get("red_flags")),
            "trigger_palabras": _safe_list(p.get("trigger_palabras")),
            "aliados": _safe_list(s.get("aliados_probables")),
            "enemigos": _safe_list(s.get("enemigos_probables")),
            "estilo_conflicto": _safe_str(s.get("estilo_conflicto")),
            "estilo_alianza": _safe_str(s.get("estilo_alianza")),
            "rol_en_grupo": _safe_str(s.get("rol_en_grupo")),
            "estrategia": _safe_str(f.get("estrategia_supervivencia")),
            "como_moriria": _safe_str(f.get("como_moriria")),
            "stats": {k: e.get(k, 5) for k in ("fuerza", "inteligencia", "carisma", "supervivencia", "traicion")},
        }
    result = json.dumps(condensed, ensure_ascii=False)
    if len(result) <= max_chars:
        return result
    # Truncar los campos más largos, no eliminar jugadores
    for name in condensed:
        c = condensed[name]
        if isinstance(c.get("guia_escritura"), str) and len(c["guia_escritura"]) > 200:
            c["guia_escritura"] = c["guia_escritura"][:200] + "..."
    result = json.dumps(condensed, ensure_ascii=False)
    return result[:max_chars]


def _fallback_ficha(name: str, sin_historial: bool) -> Dict:
    reason = "sin datos" if sin_historial else "error en destilación"
    return {
        "nombre": name,
        "estilo_habla": {
            "descripcion_detallada": f"Usuario {reason}.", "patrones": ["estilo desconocido"],
            "muletillas": [], "muestras_reales": [], "ortografia": "estándar",
            "emojis_favoritos": [], "insultos_favoritos": [], "estructura_mensajes": "desconocida",
            "voz_simulada": ["Cómo acusaría: [desconocido]", "Cómo reaccionaría: [desconocido]"],
            "anti_patrones": ["estilo completamente desconocido"],
            "guia_escritura": "Sin datos. Usar estilo neutro y genérico.",
        },
        "personalidad": {
            "arquetipo_supervivencia": "El Incógnito",
            "rasgos_dominantes": ["misterioso", "impredecible"],
            "descripcion_psicologica": f"Datos insuficientes. {reason}.",
            "red_flags": ["desconocido"], "green_flags": ["desconocido"],
            "trigger_palabras": [], "dato_curioso": "Nadie sabe nada.",
        },
        "social": {
            "aliados_probables": [], "enemigos_probables": [],
            "estilo_conflicto": "impredecible", "estilo_alianza": "solitario",
            "rol_en_grupo": "observador", "carisma_descripcion": "un misterio",
        },
        "estadisticas_juego": {
            "fuerza": 5, "inteligencia": 5, "carisma": 5, "supervivencia": 5, "traicion": 5,
            "justificacion": "Stats por defecto.",
        },
        "frase_iconica": "...",
        "estrategia_supervivencia": f"Estrategia desconocida. {reason}.",
        "como_moriria": "Muerte por causas desconocidas.",
    }

# ══════════════════════════════════════════════════════════════════════════════
# TORNEO COG V9 — GM OMNIPOTENTE
# ══════════════════════════════════════════════════════════════════════════════

_GM_OMNIPOTENTE_SYSTEM = """Eres el GAME MASTER OMNISCIENTE de un Murder Mystery. Eres DIOS en este mundo.

CONTROLAS TODO:
- Mueves cada personaje a un lugar del escenario
- Generas los diálogos de CADA personaje con su VOZ AUTÉNTICA
- Tiras D20 internamente para cada acción arriesgada
- Narras la fase con coherencia cinematográfica
- Decides quién muere (si toca)

REGLAS DE VOZ (CRÍTICO):
Para CADA diálogo, debes escribir EXACTAMENTE como esa persona hablaría.
- Si la ficha dice "muletillas: ['wey','alv','nmms']", el personaje USA esas muletillas.
- Si la ficha dice "insultos_favoritos: ['pendejo','imbecil']", los USA al insultar.
- Si la ficha dice "emojis_favoritos: ['💀','🤡','😭']", los USA.
- Si la ficha dice "guia_escritura: 'todo en minúsculas sin puntos'", SIGUE esa regla.
- Si la ficha dice "voz_simulada: 'Cómo acusaría: A ver quién pedo fue wey ALV'", ACUSA así.
- Si la ficha dice "anti_patrones: ['NUNCA usa mayúsculas']", NUNCA uses mayúsculas para ese personaje.
- Si la ficha tiene muestras_reales, IMITA ese estilo exacto.

CADA personaje tiene su propia voz. No los hables a todos igual.
Un personaje vulgar dice "wey alv qué pedo", uno formal dice "I believe we should investigate".
La diferencia DEBE ser visible en cada línea de diálogo.

REGLAS DE NARRACIÓN:
- 4-8 eventos por fase. Cada evento es una escena cinematográfica.
- Los eventos deben tener ARCO: tensión → clímax → consecuencia.
- Los personajes se mueven, se encuentran, hablan, actúan.
- Las muertes deben ser dramáticas y coherentes con el contexto.
- En fases 1-2: 0-1 muertes. Fase 3+: 1-2 muertes. Fase final: puede haber múltiples.
- El ASESINO actúa en secreto. El DETECTIVE investiga. Los INOCENTES sobreviven o caen.
- Los D20 rolls determinan el éxito de acciones arriesgadas:
  Nat 1 = desastre, Nat 20 = éxito perfecto, 10 = resultado mixto.

FORMATO JSON DE SALIDA:
{
  "nombre_fase": "título cinematográfico de la fase",
  "escenario_dinamico": "cómo cambia el escenario esta fase (2-3 oraciones)",
  "eventos": [
    {
      "accion": "Narración cinematográfica de 3-5 oraciones. QUÉ PASA, no solo qué se dicen.",
      "nombres_protagonistas": ["Nombre1", "Nombre2"],
      "dialogos": {
        "Nombre1": "TEXTO EXACTO que Nombre1 dice, con SU VOZ REAL",
        "Nombre2": "TEXTO EXACTO que Nombre2 dice, con SU VOZ REAL"
      },
      "lugar": "Lugar del escenario",
      "tipo_accion": "confrontacion/descubrimiento/alianza/traicion/asesinato/sospecha/escape/enganyo",
      "d20_roll": 15,
      "resultado_roll": "Éxito parcial"
    }
  ],
  "recuento_fase": {
    "resumen_breve": "1-2 oraciones resumiendo la fase",
    "muertos_en_esta_fase": ["NombreDelMuerto"],
    "vivos_restantes": ["Nombre1", "Nombre2", ...]
  },
  "es_final": false,
  "ganador_absoluto": null
}

REGLAS DEL JSON:
- eventos: 4-8 entradas. MÁS eventos = MÁS rico.
- dialogos: SOLO incluir personajes que HABLAN en ese evento. Puede ser 1 (monólogo) o 2+ (conversación).
- Los diálogos deben ser VIVOS y AUTÉNTICOS. Cada personaje con SU voz.
- d20_roll: NO tires dados. Usa EXCLUSIVAMENTE el valor del campo "pre_roll" del personaje que actúa. El pre_roll ya fue calculado por el sistema.
- muertos_en_esta_fase: lista de nombres. Vacía si nadie muere.
- es_final: true si el misterio se resuelve (asesino descubierto o último inocente).
- ganador_absoluto: nombre del ganador si es_final=true, null si no.

SOLO JSON. Sin texto fuera del JSON."""

_JSON_FIX_SYSTEM = """Eres un corrector de JSON. Recibes un JSON con errores de sintaxis.
Corrige SOLO los errores de sintaxis. No cambies el contenido.
Devuelve SOLO el JSON corregido, sin texto adicional, sin markdown, sin explicaciones.
Si un string tiene comillas sin escapar, escápalas. Si falta una coma, agrégala.
Si hay texto fuera del JSON, elimínalo. SOLO JSON válido."""


class TorneoCog(commands.Cog, name="Torneo"):
    """Comando /torneo — Murder Mystery V9. GM Omnipotente, 1 llamada por fase."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.renderer = TorneoRenderer()
        self._call_timestamps: List[float] = []
        self._rate_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

    async def _rate_limit(self) -> None:
        async with self._rate_lock:
            now = time.monotonic()
            cutoff = now - RATE_LIMIT_WINDOW
            self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
            if len(self._call_timestamps) >= RATE_LIMIT_CALLS:
                wait = self._call_timestamps[0] + RATE_LIMIT_WINDOW - now + 3
                logger.warning(f"Torneo: rate limit (esperando {wait:.1f}s)...")
                await asyncio.sleep(max(wait, RATE_LIMIT_COOLDOWN))
                self._call_timestamps = [t for t in self._call_timestamps if t > time.monotonic() - RATE_LIMIT_WINDOW]
            self._call_timestamps.append(time.monotonic())

    async def _call_llm(self, system_prompt, user_text, max_tokens=6000, temperature=0.85,
                        max_retries=MAX_JSON_RETRIES, expect_json=False):
        async with self._semaphore:
            await self._rate_limit()
            from google.genai import types
            ou, osys = user_text, system_prompt
            lbj, le = None, ""
            for attempt in range(max_retries + 1):
                ct = max(0.3, temperature - (attempt * 0.12))
                if attempt > 0 and expect_json and lbj:
                    asys = _JSON_FIX_SYSTEM
                    au = f"Error: {le}\n\nJSON:\n{lbj}\n\nCorrige. SOLO JSON."
                else:
                    asys, au = osys, ou
                contents = [types.Content(role="user", parts=[types.Part.from_text(text=au)])]
                try:
                    r = await self.bot.llm.generate_plain(system_prompt=asys, contents=contents,
                                                           temperature=ct, max_output_tokens=max_tokens)
                    if not r or not r.strip():
                        if attempt < max_retries: continue
                        return ""
                    if expect_json:
                        cleaned = _clean_json_response(r)
                        try:
                            json.loads(cleaned)
                            return cleaned
                        except json.JSONDecodeError as e:
                            le, lbj = str(e), cleaned[:3000]
                            if attempt < max_retries: continue
                            return r
                    else:
                        return r
                except Exception as exc:
                    if any(k in str(exc).lower() for k in ("429","rate","quota")):
                        await asyncio.sleep(RATE_LIMIT_COOLDOWN)
                        if attempt < max_retries: continue
                    logger.error(f"Torneo: error LLM: {exc}")
                    if attempt < max_retries:
                        await asyncio.sleep(2.0); continue
                    raise
            return ""

    async def _generate_story_bible(self, fichas, participantes, roles_secretos):
        fc = _condense_fichas(fichas, participantes, max_chars=30000)
        u = f"PARTICIPANTES: {', '.join(participantes)}\n\nROLES SECRETOS:\n{roles_secretos}\n\nFICHAS:\n{fc}\n\nGenera el STORY BIBLE. SOLO JSON."
        try:
            r = await self._call_llm(system_prompt=_STORY_BIBLE_SYSTEM, user_text=u,
                                      max_tokens=STORY_BIBLE_MAX_TOKENS, temperature=0.65, expect_json=True)
            return json.loads(_clean_json_response(r))
        except Exception as e:
            logger.warning(f"Story bible fallback: {e}")
            return {"titulo_del_misterio":"El Misterio","tema_central":"La Locura","logline":"Un grupo atrapado."}

    async def _generate_agendas(self, fichas, participantes, roles_secretos):
        fc = _condense_fichas(fichas, participantes, max_chars=35000)
        u = f"PARTICIPANTES: {', '.join(participantes)}\n\nROLES SECRETOS:\n{roles_secretos}\n\nFICHAS:\n{fc}\n\nGenera las AGENDAS de TODOS. SOLO JSON."
        try:
            r = await self._call_llm(system_prompt=_AGENDA_SYSTEM, user_text=u,
                                      max_tokens=AGENDA_MAX_TOKENS, temperature=0.7, expect_json=True)
            return json.loads(_clean_json_response(r))
        except Exception as e:
            logger.warning(f"Agendas fallback: {e}")
            return {}

    # ═════════════════════════════════════════════════════════════════════
    # V9: GM OMNIPOTENTE — 1 llamada, TODO lo hace el GM
    # ═════════════════════════════════════════════════════════════════════

    async def _gm_omnipotente(self, vivos, fichas, escenario, roles_secretos,
                               fase_num, max_fases, story_bible, agendas,
                               memoria_agentes, prev_eventos, prev_board, muertos):
        """1 llamada LLM. El GM mueve, habla, actúa y narra TODO."""

        # Build voice compendium — each character's voice contract
        voice_blocks = {}
        for name in vivos:
            ficha = fichas.get(name, {})
            voice_blocks[name] = _build_agent_voice_block(ficha, max_chars=1500)

        # Build agenda blocks
        agenda_blocks = {}
        for name in vivos:
            agenda_blocks[name] = _build_agent_agenda_block(agendas, name)

        # Build memory per character
        memoria_viva = _build_memoria_viva(
            memoria_agentes, prev_eventos, prev_board, vivos, muertos, fase_num)

        # Assemble character compendium
        compendium_parts = []
        for name in vivos:
            parts = [f"═══ {name} ═══"]
            # Role
            if f"DETECTIVE: {name}" in roles_secretos:
                parts.append("ROL SECRETO: DETECTIVE — investiga en secreto")
            elif f"ASESINO: {name}" in roles_secretos:
                parts.append("ROL SECRETO: ASESINO — mata en secreto")
            else:
                parts.append("ROL SECRETO: INOCENTE — sobrevive")
            parts.append(f"VOZ:\n{voice_blocks.get(name, 'Desconocida')}")
            parts.append(f"AGENDA:\n{agenda_blocks.get(name, 'Ninguna')}")
            parts.append(f"MEMORIA:\n{memoria_viva.get(name, 'Inicio.')}")
            compendium_parts.append("\n".join(parts))

        compendium = "\n\n".join(compendium_parts)

        # Truncate if too long (keep voices intact, trim memory first)
        if len(compendium) > 55000:
            # Rebuild with shorter memory
            compendium_parts = []
            for name in vivos:
                parts = [f"═══ {name} ═══"]
                if f"DETECTIVE: {name}" in roles_secretos: parts.append("ROL: DETECTIVE")
                elif f"ASESINO: {name}" in roles_secretos: parts.append("ROL: ASESINO")
                else: parts.append("ROL: INOCENTE")
                parts.append(f"VOZ:\n{voice_blocks.get(name, '?')}")
                parts.append(f"AGENDA:\n{agenda_blocks.get(name, '?')[:300]}")
                parts.append(f"MEMORIA:\n{memoria_viva.get(name, '?')[:200]}")
                compendium_parts.append("\n".join(parts))
            compendium = "\n\n".join(compendium_parts)

        final_warning = ""
        if fase_num >= max_fases:
            final_warning = "\n\n⚠️ FASE FINAL. El misterio DEBE resolverse. Múltiples muertes posibles. El asesino puede ser descubierto."
        elif fase_num >= max_fases - 1:
            final_warning = "\n\n⚠️ Penúltima fase. La tensión está al máximo. Alguien debería morir."

        # ── D20 server-side: pre-roll for each character ──
        d20_rolls = {name: _roll_d20() for name in vivos}
        d20_block = "\n".join(
            f"  {name}: D20={roll} → {_interpret_roll(roll)['resultado']}"
            for name, roll in d20_rolls.items()
        )

        # ── Story arc injection ──
        arco = story_bible.get("arco_narrativo", {})
        arco_block = ""
        if arco:
            actos = []
            if fase_num <= 2 and arco.get("acto_1_paranoia"):
                actos.append(f"ACTO 1 (AHORA): {arco['acto_1_paranoia']}")
            elif fase_num <= 4 and arco.get("acto_2_caceria"):
                actos.append(f"ACTO 2 (AHORA): {arco['acto_2_caceria']}")
            elif fase_num <= 5 and arco.get("acto_2_crisis"):
                actos.append(f"CRISIS (AHORA): {arco['acto_2_crisis']}")
            elif arco.get("acto_3_revelacion"):
                actos.append(f"ACTO 3 (AHORA): {arco['acto_3_revelacion']}")
            actos.append(f"ARCO COMPLETO: A1={arco.get('acto_1_paranoia','?')} → A2={arco.get('acto_2_caceria','?')} → Crisis={arco.get('acto_2_crisis','?')} → A3={arco.get('acto_3_revelacion','?')}")
            arco_block = "\n".join(actos)

        # ── Asesino/detective profiles from story bible ──
        perf_asesino = story_bible.get("perfil_asesino_principal", {})
        perf_detective = story_bible.get("perfil_detective", {})
        profiles_block = ""
        if perf_asesino:
            profiles_block += f"\nPERFIL ASESINO: motivo={perf_asesino.get('motivo_oculto','?')}, MO={perf_asesino.get('modus_operandi','?')}, firma={perf_asesino.get('firma','?')}"
        if perf_detective:
            profiles_block += f"\nPERFIL DETECTIVE: estilo={perf_detective.get('estilo_investigacion','?')}, debilidad={perf_detective.get('debilidad_fatal','?')}"

        # ── Dynamic death pacing ──
        deaths_so_far = len(muertos)
        alive_count = len(vivos)
        if fase_num <= 2:
            death_instruction = "MÁXIMO 1 muerte esta fase (puede ser 0). Estamos en Acto 1 — siembra paranoia, no matanza."
        elif fase_num <= 4:
            death_instruction = "1-2 muertes esta fase. La cacería se intensifica."
        elif alive_count <= 3:
            death_instruction = "1 muerte máximo. Quedan pocos — cada muerte es decisiva."
        else:
            death_instruction = "1-2 muertes esta fase. La crisis exige sacrificios."

        # ── Previous phase summary ──
        prev_summary = ""
        if prev_eventos:
            prev_parts = []
            for evt in prev_eventos[-4:]:
                protas = evt.get("nombres_protagonistas", [])
                accion = evt.get("accion", "")[:120]
                dlg = evt.get("dialogos", {})
                dlg_text = " | ".join(f"{k}: {v[:60]}" for k, v in dlg.items()) if dlg else ""
                prev_parts.append(f"  • {', '.join(protas)}: {accion}")
                if dlg_text:
                    prev_parts.append(f"    Diálogos: {dlg_text}")
            prev_summary = "RESUMEN DE LA FASE ANTERIOR:\n" + "\n".join(prev_parts)

        user = (
        f"FASE {fase_num}/{max_fases}\n\n"
        f"ESCENARIO: {escenario['nombre']}\n"
        f"Descripción: {escenario['descripcion']}\n"
        f"Lugares: {', '.join(escenario.get('lugares', []))}\n"
        f"Elementos: {', '.join(escenario.get('elementos', []))}\n\n"
        f"STORY BIBLE: {story_bible.get('titulo_del_misterio', '?')} — {story_bible.get('tema_central', '?')}\n"
        f"Logline: {story_bible.get('logline', '?')}\n"
        f"{arco_block}\n"
        f"{profiles_block}\n\n"
        f"ROLES SECRETOS: {roles_secretos}\n\n"
        f"MUERTOS HASTA AHORA ({deaths_so_far}): {', '.join(muertos) if muertos else 'Nadie'}\n"
        f"VIVOS ({alive_count}): {', '.join(vivos)}\n\n"
        f"═══ D20 TIRADAS (USA estos rolls para las acciones de cada personaje) ═══\n"
        f"{d20_block}\n\n"
        f"═══ RITMO DE MUERTES ═══\n"
        f"{death_instruction}\n\n"
        f"{prev_summary}\n\n"
        f"═══════════════════════════════════════\n"
        f"COMPENDIO DE PERSONAJES:\n"
        f"═══════════════════════════════════════\n\n"
        f"{compendium}"
        f"{final_warning}\n\n"
        f"Narra la fase completa. SOLO JSON."
        )

        try:
            r = await self._call_llm(
                system_prompt=_GM_OMNIPOTENTE_SYSTEM,
                user_text=user,
                max_tokens=PHASE_JSON_MAX_TOKENS,
                temperature=0.92,
                expect_json=True,
                max_retries=MAX_JSON_RETRIES,
            )
            narracion = json.loads(_clean_json_response(r))
            _enforce_d20_rolls(narracion, d20_rolls)
            return narracion
        except Exception as exc:
            logger.error(f"Torneo: GM omnipotente fase {fase_num}: {exc}")
            raise

    # ═════════════════════════════════════════════════════════════════════
    # COMANDO /torneo
    # ═════════════════════════════════════════════════════════════════════

    @app_commands.command(name="torneo", description="Murder Mystery V9. GM Omnipotente, 1 llamada por fase.")
    @app_commands.describe(rol="Rol cuyos miembros participaran", canal="Canal donde se narrara")
    async def torneo(self, interaction: discord.Interaction, rol: discord.Role, canal: discord.TextChannel) -> None:
        member = interaction.user
        if isinstance(member, discord.Member):
            if not await can_use_youkai_nl(member, self.bot.db):
                await interaction.response.send_message("Solo **Youkai Reader**.", ephemeral=True); return
        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild
        if not guild: await interaction.followup.send("Solo servidores."); return
        members = [m for m in rol.members if not m.bot]
        if len(members) < 3:
            await interaction.followup.send(f"Minimo 3. {rol.name} tiene {len(members)}."); return
        if len(members) > MAX_PARTICIPANTS: members = random.sample(members, MAX_PARTICIPANTS)
        await interaction.followup.send(embed=discord.Embed(
            title="MURDER MYSTERY V9",
            description=f"**{len(members)} almas** • GM Omnipotente • 1 llamada/fase",
            color=0x8b0000))

        # ── Escenario ──
        escenario = random.choice(_SCENARIOS)
        await canal.send(f"**{escenario['nombre']}** — {escenario['descripcion']}")

        # ── PFPs ──
        pfp_cache: Dict[str, io.BytesIO] = {}
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                for m in members:
                    try:
                        async with s.get(m.display_avatar.with_size(256).url) as rp:
                            if rp.status == 200: pfp_cache[m.display_name] = io.BytesIO(await rp.read())
                    except Exception as exc:
                        logger.debug("torneo: PFP download failed for {}: {}", m.display_name, exc)
        except ImportError: pass

        # ── Historiales ──
        user_histories: Dict[int, List[Dict]] = {}
        for m in members:
            try:
                msgs = await self.bot.db.search_messages(guild_id=guild.id, user_id=m.id, hours=720, limit=MAX_MESSAGES_PER_USER)
                msgs.sort(key=lambda x: x.get("timestamp", 0))
                user_histories[m.id] = msgs
            except Exception as exc:
                logger.warning("torneo: history search failed for {}: {}", m.display_name, exc)
                user_histories[m.id] = []

        # ── Destilación PARALELA ──
        async def _destilar(m):
            name = m.display_name
            history = user_histories.get(m.id, [])
            if not history: return name, _fallback_ficha(name, True)
            hl = [f"[{msg.get('username',name)}]: {(msg.get('content') or '')[:250]}"
                  for msg in history[-MAX_MESSAGES_PER_USER:]
                  if (msg.get("content") or "").strip()]
            if not hl: return name, _fallback_ficha(name, True)
            try:
                fj = await self._call_llm(
                    system_prompt=_DISTILLATION_SYSTEM,
                    user_text=f"HISTORIAL DE {name}:\n"+"\n".join(hl)[:40000]+"\n\nGenera ficha COMPLETA. SOLO JSON.",
                    max_tokens=DISTILLATION_MAX_TOKENS, temperature=0.7, expect_json=True)
                ficha = json.loads(_clean_json_response(fj)); ficha["nombre"] = name
                return name, ficha
            except Exception as exc:
                logger.error(f"Torneo: destilacion {name}: {exc}")
                return name, _fallback_ficha(name, False)

        tasks = [_destilar(m) for m in members]
        results = await asyncio.gather(*tasks)
        fichas: Dict[str, Dict] = {}
        for name, ficha in results:
            if ficha: fichas[name] = ficha
        await canal.send(f"**{len(fichas)}/{len(members)} fichas** destiladas.")

        # ── Roles ──
        participantes = list(fichas.keys())
        detective = random.choice(participantes)
        asesino = random.choice([p for p in participantes if p != detective])
        roles_secretos = f"DETECTIVE: {detective} | ASESINO: {asesino}"

        # ── Story Bible + Agendas ──
        story_bible = await self._generate_story_bible(fichas, participantes, roles_secretos)
        titulo = story_bible.get("titulo_del_misterio", "El Misterio")
        tema = story_bible.get("tema_central", "La Locura")
        agendas = await self._generate_agendas(fichas, participantes, roles_secretos)

        await canal.send(f"**{titulo}**\n*{tema}*\n*Roles designados en secreto.*")
        await asyncio.sleep(3)

        # ── Estado del juego ──
        memoria_agentes: Dict[str, str] = {n: "Inicio." for n in participantes}
        vivos = list(participantes)
        muertos: List[str] = []
        fase_num = 1
        ganador = None
        prev_eventos: List[Dict] = []
        prev_board: Dict[str, str] = {p: "?" for p in participantes}

        # ════════════════════════════════════════════════════
        # BUCLE PRINCIPAL V9 — 1 llamada GM por fase
        # ════════════════════════════════════════════════════
        while len(vivos) > 1:
            msg = await canal.send(
                f"**FASE {fase_num}/{MAX_FASES}** — {len(vivos)} vivos\n"
                f"*GM Omnipotente narrando...*")

            try:
                narracion = await self._gm_omnipotente(
                    vivos, fichas, escenario, roles_secretos,
                    fase_num, MAX_FASES, story_bible, agendas,
                    memoria_agentes, prev_eventos, prev_board, muertos)
            except Exception as exc:
                logger.error(f"Torneo: GM fallo en fase {fase_num}: {exc}")
                await msg.edit(content=f"Error en Fase {fase_num}. Abortando.")
                return

            await msg.delete()

            # ── Extraer datos de la narración ──
            nombre_fase = _safe_str(narracion.get("nombre_fase"), f"Fase {fase_num}")
            escenario_dinamico = _safe_str(narracion.get("escenario_dinamico"), escenario["descripcion"])
            eventos = narracion.get("eventos", [])
            if not isinstance(eventos, list): eventos = []
            recuento = narracion.get("recuento_fase", {})
            if not isinstance(recuento, dict): recuento = {}
            es_final = narracion.get("es_final", False)
            ganador_fase = narracion.get("ganador_absoluto")
            muertos_fase = recuento.get("muertos_en_esta_fase", [])
            if not isinstance(muertos_fase, list): muertos_fase = []
            resumen_breve = _safe_str(recuento.get("resumen_breve"))

            # ── Actualizar estado ──
            for name in muertos_fase:
                if name in vivos:
                    vivos.remove(name)
                    muertos.append(name)

            # ── Actualizar memoria de agentes ──
            for evt in eventos:
                for name in evt.get("nombres_protagonistas", []):
                    if name in memoria_agentes:
                        dlg = evt.get("dialogos", {})
                        mi_dlg = dlg.get(name, "")[:150] if isinstance(dlg, dict) else ""
                        prev = memoria_agentes[name]
                        memoria_agentes[name] = (
                            f"[F{fase_num}] {evt.get('accion','')[:150]}. "
                            f"Dije: {mi_dlg}. "
                        ) + prev[:300]

            # ── Board state from eventos ──
            board_state = dict(prev_board)
            for evt in eventos:
                lugar = evt.get("lugar", "")
                for name in evt.get("nombres_protagonistas", []):
                    if lugar and name in vivos:
                        board_state[name] = lugar

            # ── Renderizar ──
            await canal.send(f"**Renderizando {nombre_fase}...**")
            img_file = None
            try:
                rd = {
                    "resumen_breve": resumen_breve,
                    "muertos_en_esta_fase": muertos_fase,
                    "vivos_restantes": list(vivos),
                }
                ps: Dict[str, io.BytesIO] = {}
                for pn, pb in pfp_cache.items():
                    pb.seek(0)
                    ps[pn] = pb
                loop = asyncio.get_running_loop()
                img_bytes = await loop.run_in_executor(
                    None, self.renderer.renderizar_fase_completa,
                    nombre_fase, escenario_dinamico, eventos, rd, ps,
                    board_state, escenario.get("lugares", []))
                img_file = discord.File(fp=io.BytesIO(img_bytes), filename=f"fase{fase_num}.png")
            except Exception as exc:
                logger.error(f"Torneo: render: {exc}")
                await canal.send(f"Error render: {exc}")

            embed_fase = discord.Embed(
                title=f"{nombre_fase}", description=escenario_dinamico, color=0xe67e22)
            embed_fase.set_footer(text=f"Fase {fase_num} • {len(vivos)} vivos • {len(eventos)} eventos")
            if img_file:
                embed_fase.set_image(url=f"attachment://fase{fase_num}.png")
                await canal.send(embed=embed_fase, file=img_file)
            else:
                await canal.send(embed=embed_fase)

            # ── Verificar fin ──
            if es_final and ganador_fase:
                await canal.send(embed=discord.Embed(
                    title="GANADOR ABSOLUTO",
                    description=f"**{ganador_fase}** ha resuelto el misterio.",
                    color=0xf1c40f))
                ganador = ganador_fase
                break
            if len(vivos) <= 1:
                ganador = vivos[0] if vivos else "Nadie"
                await canal.send(embed=discord.Embed(
                    title="GANADOR ABSOLUTO",
                    description=f"**{ganador}** es el último en pie.",
                    color=0xf1c40f))
                break
            if fase_num >= MAX_FASES:
                ganador = random.choice(vivos) if vivos else "Nadie"
                await canal.send(embed=discord.Embed(
                    title="GANADOR ABSOLUTO",
                    description=f"**{ganador}** sobrevive al colapso.",
                    color=0xf1c40f))
                break

            prev_eventos = eventos
            prev_board = board_state
            fase_num += 1
            await canal.send("*Preparando siguiente fase...*")
            await asyncio.sleep(PHASE_PACING_SECONDS)

        # ── Fin ──
        await canal.send(embed=discord.Embed(
            title="MISTERIO RESUELTO",
            description=(
                f"**{fase_num} fases** • "
                f"**{len(muertos)} caídos** • "
                f"**{ganador or 'El destino'}** reclama la verdad."
            ),
            color=0x9b59b6))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TorneoCog(bot))
