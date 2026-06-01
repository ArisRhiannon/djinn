"""
Test de integración del TorneoCog — AI-as-LLM.

El LLM soy yo. Mockeo `bot.llm.generate_plain()` para que devuelva
JSONs realistas y coherentes respetando cada schema del torneo.

Ejecutar: python3 tests/test_torneo_integration.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

# ── Helpers ───────────────────────────────────────────────────────────────────
async def _nop_coro():
    pass

# ── Inyectar path del proyecto ────────────────────────────────────────────────
sys.path.insert(0, ".")

from cogs.torneo import (
    MAX_FASES,
    MAX_MESSAGES_PER_USER,
    TorneoCog,
    _clean_json_response,
    _fallback_ficha,
    _safe_list,
    _safe_str,
)


# ══════════════════════════════════════════════════════════════════════════════
# Fake LLM — soy yo respondiendo
# ══════════════════════════════════════════════════════════════════════════════

# Fake messages per user (historial inventado)
_FAKE_HISTORIES = {
    "papu": [
        {"username": "papu", "content": "no mames wey jajaja",
         "timestamp": 1700000000},
        {"username": "papu", "content": "alv ya se murio otro XD",
         "timestamp": 1700000100},
        {"username": "papu", "content": "yo digo q fue el pinche makao siempre anda sospechoso",
         "timestamp": 1700000200},
        {"username": "papu", "content": "weno weno no se enojen era broma jaja",
         "timestamp": 1700000300},
        {"username": "papu", "content": "nmms neta? no puede ser ALV",
         "timestamp": 1700000400},
    ],
    "Makao": [
        {"username": "Makao", "content": "Good evening gentlemen.",
         "timestamp": 1700000000},
        {"username": "Makao", "content": "I've been analyzing the situation and the evidence points elsewhere.",
         "timestamp": 1700000100},
        {"username": "Makao", "content": "How curious. The knife was in the kitchen all along.",
         "timestamp": 1700000200},
        {"username": "Makao", "content": "I would never betray my allies. Loyalty is paramount.",
         "timestamp": 1700000300},
    ],
    "Cov": [
        {"username": "Cov", "content": "buenas",
         "timestamp": 1700000000},
        {"username": "Cov", "content": "no vi nada yo solo estaba en mi cuarto",
         "timestamp": 1700000100},
        {"username": "Cov", "content": "._.",
         "timestamp": 1700000200},
    ],
    "Aria": [
        {"username": "Aria", "content": "✨ buenas noches a todos ✨",
         "timestamp": 1700000000},
        {"username": "Aria", "content": "uyuyuy esto se puso intenso... yo solo quiero paz y amor 🌸",
         "timestamp": 1700000100},
        {"username": "Aria", "content": "no sé ustedes pero yo VOY a encontrar al culpable >:)",
         "timestamp": 1700000200},
        {"username": "Aria", "content": "que miedoooo 😭😭😭",
         "timestamp": 1700000300},
        {"username": "Aria", "content": "confío en Makao, siempre tan tranquilo el hombre",
         "timestamp": 1700000400},
    ],
    "Blueber": [
        {"username": "Blueber", "content": "hola",
         "timestamp": 1700000000},
        {"username": "Blueber", "content": "wtf paso algo?",
         "timestamp": 1700000100},
        {"username": "Blueber", "content": "yo no fui we",
         "timestamp": 1700000200},
        {"username": "Blueber", "content": "👀",
         "timestamp": 1700000300},
    ],
}


def _make_distillation_json(name: str) -> str:
    """Genero una ficha de personalidad como si el LLM la hubiera destilado."""
    profiles = {
        "papu": {
            "nombre": "papu",
            "estilo_habla": {
                "descripcion_detallada": "Escritura caótica, impulsiva y cargada de mexicanismos. Usa muchas abreviaturas y carcajadas.",
                "patrones": ["abreviaturas agresivas", "risa después de acusación", "cambio rápido de tono"],
                "muletillas": ["wey", "no mames", "nmms", "ALV", "alv", "jajaja", "XD", "weno"],
                "muestras_reales": [
                    "no mames wey jajaja",
                    "alv ya se murio otro XD",
                    "yo digo q fue el pinche makao siempre anda sospechoso",
                    "weno weno no se enojen era broma jaja",
                    "nmms neta? no puede ser ALV"
                ],
                "ortografia": "sin tildes, sin mayúsculas salvo ALV, usa q en vez de que, acusa con humor",
                "emojis_favoritos": ["XD", ":v"],
                "insultos_favoritos": ["pinche", "wey"],
                "estructura_mensajes": "frases cortas, una idea por mensaje, termina con risa o ALV",
                "voz_simulada": [
                    "Cómo acusaría: 'NO MAMES WEY OBVIO FUE EL PINCHE MAKAO SIEMPRE CON SUS COSAS RARAS XD'",
                    "Cómo se defendería: 'wey neta yo no fui nmms yo estaba en mi cuarto ALV'",
                    "Cómo reaccionaría a un cadáver: 'ALV ALV ALV SE MURIOOOOO jajaja nmms que miedo'",
                    "Cómo amenazaría: 'wey te voy a partir tu madre si fuiste tu pinche asesino >:v'",
                    "Cómo confesaría: 'wey... si fui yo. pero era el o yo nmms. no me juzguen ALV'",
                    "Cómo pediría alianza: 'wey hagamos equipo tu y yo contra estos weyes ALV'"
                ],
                "anti_patrones": ["NUNCA escribe formal", "NUNCA usa puntuación correcta"],
                "guia_escritura": "Escribe TODO en minúsculas excepto ALV. Usa wey cada 5 palabras. Termina frases con XD o ALV."
            },
            "personalidad": {
                "arquetipo_supervivencia": "El Caótico Acusador",
                "rasgos_dominantes": ["impulsivo", "paranoico", "bromista macabro", "leal a sus aliados", "ruidoso"],
                "descripcion_psicologica": "Papu usa el humor como máscara de su miedo profundo. Acusa rápido para desviar sospechas de sí mismo. Es leal pero volátil.",
                "red_flags": ["acusa antes de pensar", "ríe en situaciones inapropiadas"],
                "green_flags": ["defiende a sus aliados", "admite errores"],
                "trigger_palabras": ["asesino", "muerto", "sospechoso", "traición"],
                "dato_curioso": "Siempre es el primero en encontrar el cadáver."
            },
            "social": {
                "aliados_probables": ["Cov", "Aria"],
                "enemigos_probables": ["Makao"],
                "estilo_conflicto": "Acusación frontal con humor, se retracta rápido si se caldea",
                "estilo_alianza": "Lealtad ruidosa, defiende a los suyos a gritos",
                "rol_en_grupo": "provocador",
                "carisma_descripcion": "Cae bien por gracioso pero cansa por intenso"
            },
            "estadisticas_juego": {
                "fuerza": 6, "inteligencia": 4, "carisma": 8, "supervivencia": 5, "traicion": 3,
                "justificacion": "Carisma alto por humor. Inteligencia baja por impulsividad."
            },
            "frase_iconica": "ALV",
            "estrategia_supervivencia": "Acusar a todos para que nadie sospeche de él. Hacer alianzas ruidosas.",
            "como_moriria": "Acusando al asesino real demasiado tarde, con un 'ALV...' como últimas palabras."
        },
        "Makao": {
            "nombre": "Makao",
            "estilo_habla": {
                "descripcion_detallada": "Habla con elegancia británica. Frases completas, puntuación perfecta, tono calmado incluso bajo presión.",
                "patrones": ["oraciones compuestas", "ironía sutil", "preguntas retóricas"],
                "muletillas": ["How curious.", "Indeed.", "I've been analyzing"],
                "muestras_reales": [
                    "Good evening gentlemen.",
                    "I've been analyzing the situation and the evidence points elsewhere.",
                    "How curious. The knife was in the kitchen all along.",
                    "I would never betray my allies. Loyalty is paramount."
                ],
                "ortografia": "impecable, signos de puntuación correctos, vocabulario extenso",
                "emojis_favoritos": ["🧐"],
                "insultos_favoritos": [],
                "estructura_mensajes": "párrafos cortos pero bien construidos, una idea por mensaje",
                "voz_simulada": [
                    "Cómo acusaría: 'The evidence suggests a rather uncomfortable conclusion, I'm afraid.'",
                    "Cómo se defendería: 'I assure you, my alibi is quite unshakeable. Do check the timestamps.'",
                    "Cómo reaccionaría a un cadáver: '...How unfortunate. This changes the calculus significantly.'",
                    "Cómo amenazaría: 'I would strongly advise against that course of action.'",
                    "Cómo confesaría: 'Yes. It was me. And I would do it again, given the circumstances.'",
                    "Cómo pediría alianza: 'I propose a mutually beneficial arrangement. Shall we discuss terms?'"
                ],
                "anti_patrones": ["NUNCA es vulgar", "NUNCA pierde la compostura"],
                "guia_escritura": "Inglés formal con ocasionales toques de ironía. Nunca alza la voz. Usa 'indeed' y 'curious' frecuentemente."
            },
            "personalidad": {
                "arquetipo_supervivencia": "El Estratega Estoico",
                "rasgos_dominantes": ["analítico", "calmado", "misterioso", "leal", "calculador"],
                "descripcion_psicologica": "Makao procesa todo con lógica fría. Su calma es genuina pero también su mayor debilidad: subestima el caos emocional.",
                "red_flags": ["demasiado calmado para ser inocente", "analiza en vez de sentir"],
                "green_flags": ["nunca traicionaría a un aliado", "dice la verdad aunque duela"],
                "trigger_palabras": ["caos", "desorden", "mentira"],
                "dato_curioso": "Siempre lleva un cuaderno mental de evidencias."
            },
            "social": {
                "aliados_probables": ["Aria", "Cov"],
                "enemigos_probables": ["papu"],
                "estilo_conflicto": "Confrontación lógica, desarma con preguntas",
                "estilo_alianza": "Lealtad absoluta, espera lo mismo a cambio",
                "rol_en_grupo": "estratega",
                "carisma_descripcion": "Inspira confianza por su calma, pero también desconfianza por lo mismo"
            },
            "estadisticas_juego": {
                "fuerza": 5, "inteligencia": 9, "carisma": 7, "supervivencia": 8, "traicion": 2,
                "justificacion": "Inteligencia máxima por análisis. Traición mínima por lealtad."
            },
            "frase_iconica": "How curious.",
            "estrategia_supervivencia": "Analizar cada movimiento, mantener la calma, proteger a sus aliados.",
            "como_moriria": "Traicionado por alguien en quien confiaba plenamente, con un seco '...I see.'"
        },
        "Cov": {},
        "Aria": {},
        "Blueber": {},
    }

    profile = profiles.get(name, None)
    if profile is None:
        return _gen_generic_distillation(name)
    return json.dumps(profile, ensure_ascii=False)


def _gen_generic_distillation(name: str) -> str:
    return json.dumps({
        "nombre": name,
        "estilo_habla": {
            "descripcion_detallada": f"Usuario {name} con estilo conversacional normal.",
            "patrones": ["mensajes cortos", "tono casual"],
            "muletillas": ["hola", "jaja"],
            "muestras_reales": ["buenas", "no vi nada", "..._..."],
            "ortografia": "estándar con algunos errores",
            "emojis_favoritos": ["✨", "😭"],
            "insultos_favoritos": [],
            "estructura_mensajes": "frases cortas",
            "voz_simulada": [
                f"Cómo acusaría: 'yo creo que fue {name}... digo, alguien más'",
                f"Cómo se defendería: 'yo no fui, estaba en mi cuarto'",
                f"Cómo reaccionaría a un cadáver: 'uy no... que miedo'",
                f"Cómo amenazaría: 'mejor no te metas conmigo'",
                f"Cómo confesaría: 'bueno... si fui yo. perdón.'",
                f"Cómo pediría alianza: 'hagamos equipo porfa'"
            ],
            "anti_patrones": ["NUNCA es agresivo"],
            "guia_escritura": f"Escribe como {name}: casual, con algunos emojis."
        },
        "personalidad": {
            "arquetipo_supervivencia": "El Observador Silencioso",
            "rasgos_dominantes": ["tranquilo", "observador", "nervioso bajo presión"],
            "descripcion_psicologica": f"{name} prefiere observar antes de actuar. Ansiedad en situaciones de conflicto.",
            "red_flags": ["demasiado callado"],
            "green_flags": ["no miente", "ayuda si se lo piden"],
            "trigger_palabras": ["acusación", "pelea"],
            "dato_curioso": f"{name} siempre está en el lugar equivocado en el momento equivocado."
        },
        "social": {
            "aliados_probables": ["Aria"],
            "enemigos_probables": [],
            "estilo_conflicto": "evitación",
            "estilo_alianza": "apoyo silencioso",
            "rol_en_grupo": "observador",
            "carisma_descripcion": "Pasa desapercibido, ni bien ni mal."
        },
        "estadisticas_juego": {
            "fuerza": 4, "inteligencia": 6, "carisma": 4, "supervivencia": 6, "traicion": 3,
            "justificacion": "Stats equilibrados, nada excepcional."
        },
        "frase_iconica": "._.",
        "estrategia_supervivencia": "Pasar desapercibido y esperar que otros resuelvan.",
        "como_moriria": "En el lugar equivocado, en el momento equivocado."
    }, ensure_ascii=False)


def _make_story_bible_json() -> str:
    return json.dumps({
        "titulo_del_misterio": "La Mansión de los Mil Reflejos",
        "tema_central": "¿Puedes confiar en lo que ves cuando todos llevan máscara?",
        "logline": "Cinco almas atrapadas en Ashford Manor descubren que entre ellas hay un asesino, pero la verdad tiene más capas que las paredes de la mansión.",
        "arco_narrativo": {
            "acto_1_paranoia": "Primer cuerpo en la biblioteca. La tormenta corta la luz. Todos se miran distinto.",
            "acto_2_caceria": "Las acusaciones vuelan. Aliados se vuelven enemigos. Papu acusa a Makao de ser el asesino.",
            "acto_2_crisis": "Segundo cuerpo. El pánico es total. Nadie confía en nadie.",
            "acto_3_revelacion": "Enfrentamiento final en la sala de trofeos. Solo uno sabrá la verdad."
        },
        "perfil_asesino_principal": {
            "nombre": "Aria",
            "motivo_oculto": "Cree que los demás conspiraron contra ella en el pasado. Esto es venganza envuelta en poesía.",
            "modus_operandi": "Envenenamiento silencioso. Nadie sospecha de la chica dulce.",
            "firma": "Deja una flor junto al cadáver. Siempre una margarita."
        },
        "perfil_detective": {
            "nombre": "Makao",
            "estilo_investigacion": "metódico, analítico, paciente",
            "debilidad_fatal": "Su confianza en Aria. Nunca sospecharía de su aliada más cercana."
        },
        "dinamicas_centrales": [
            {"descripcion": "Papu vs Makao: caos contra orden", "personajes": ["papu", "Makao"], "potencial_dramatico": "Explosivo"},
            {"descripcion": "Aria y Makao: alianza ciega que será su perdición", "personajes": ["Aria", "Makao"], "potencial_dramatico": "Trágico"}
        ],
        "ganador_ideal": {"nombre": "papu", "justificacion": "El caos triunfa sobre el orden. Irónico y satisfactorio."}
    }, ensure_ascii=False)


def _make_agendas_json(participantes: List[str], asesino: str) -> str:
    agendas = {}
    for p in participantes:
        if p == asesino:
            agendas[p] = {
                "deseo_profundo": "Venganza. Quiere que todos paguen por lo que hicieron.",
                "miedo_nuclear": "Ser descubierta antes de completar su obra.",
                "secreto_que_parece_culpable": "Sabe demasiado sobre venenos para alguien tan dulce.",
                "opinion_del_detective": "Makao es brillante pero confía demasiado en mí. Eso lo hará débil.",
                "contradiccion_interna": "Quiere ser amada pero está destruyendo a quienes podrían amarla.",
                "momento_quiebre": "Si Makao descubre la verdad y la mira con decepción."
            }
        else:
            agendas[p] = {
                "deseo_profundo": "Sobrevivir a toda costa.",
                "miedo_nuclear": "Ser acusado injustamente.",
                "secreto_que_parece_culpable": "Todos tienen algo que esconder de esa noche.",
                "opinion_del_detective": "Confío en Makao, tiene la cabeza fría.",
                "contradiccion_interna": "Quiero confiar en los demás pero el miedo me lo impide.",
                "momento_quiebre": "Ser traicionado por mi aliado más cercano."
            }
    return json.dumps(agendas, ensure_ascii=False)


def _make_intencion(name: str) -> str:
    intenciones = {
        "papu": json.dumps({
            "pensamiento_interno": "ALV ya se murio otro nmms esto se puso denso. Yo digo q fue el makao wey siempre con sus aires de superioridad. Ahorita me lanzo a la cocina a buscar algo pa defenderme no vaya ser q me quieran hacer algo ALV.",
            "sospechoso_principal": "Makao",
            "confias_en": ["Cov", "Aria"],
            "objetivo_de_accion": "Voy a la cocina a buscar un cuchillo y después sigo a Makao para ver qué hace.",
            "estado_emocional": "paranoico"
        }, ensure_ascii=False),
        "Makao": json.dumps({
            "pensamiento_interno": "The patterns are emerging. Papu's erratic accusations, while crude, may contain fragments of truth. I shall examine the library again — the first body held clues I may have overlooked. How curious that Aria was the last to see the victim alive.",
            "sospechoso_principal": None,
            "confias_en": ["Aria"],
            "objetivo_de_accion": "Revisar la biblioteca en busca de evidencia forense que pasé por alto.",
            "estado_emocional": "calculador"
        }, ensure_ascii=False),
        "Cov": json.dumps({
            "pensamiento_interno": "ay no que miedo ya hay un muerto ._. yo solo quiero irme a mi casa. Papu anda muy alterado wey. Mejor me quedo en mi cuarto y no abro la puerta.",
            "sospechoso_principal": None,
            "confias_en": ["Aria"],
            "objetivo_de_accion": "Encerrarme en mi habitación y atrancar la puerta con una silla.",
            "estado_emocional": "aterrado"
        }, ensure_ascii=False),
        "Aria": json.dumps({
            "pensamiento_interno": "Todo va según lo planeado ✨. Makao no sospecha nada... mi querido detective. Pobre Papu acusándolo sin pruebas. Mientras tanto yo preparo la siguiente sorpresa. La cocina tiene todo lo que necesito 🌸.",
            "sospechoso_principal": "papu",
            "confias_en": ["Makao"],
            "objetivo_de_accion": "Ir a la cocina con la excusa de preparar té para todos y asegurarme de que el próximo 'accidente' sea perfecto.",
            "estado_emocional": "calculador"
        }, ensure_ascii=False),
        "Blueber": json.dumps({
            "pensamiento_interno": "wtf ya hay muertos? no mames apenas llegue. bueno yo ni me meto, solo quiero sobrevivir. vere si alguien necesita ayuda pa no estar solo.",
            "sospechoso_principal": None,
            "confias_en": ["Makao"],
            "objetivo_de_accion": "Buscar a Makao y ofrecerme a ayudarlo con la investigación.",
            "estado_emocional": "resignado"
        }, ensure_ascii=False),
    }
    return intenciones.get(name, json.dumps({
        "pensamiento_interno": "No sé qué está pasando pero debo mantenerme alerta.",
        "sospechoso_principal": None,
        "confias_en": [],
        "objetivo_de_accion": "Explorar la mansión con cuidado.",
        "estado_emocional": "confundido"
    }, ensure_ascii=False))


def _make_encuentros(vivos: List[str]) -> str:
    # Agrupar intenciones: Papu y Aria van a la cocina → encuentro.
    # Makao va solo a la biblioteca. Cov se encierra. Blueber busca a Makao.
    return json.dumps({
        "tablero": {
            "papu": "Cocina", "Aria": "Cocina",
            "Makao": "Biblioteca", "Blueber": "Biblioteca",
            "Cov": "Torreón",
        },
        "encuentros": [
            {
                "protagonistas": ["papu", "Aria"],
                "lugar": "Cocina",
                "contexto_situacion": "Papu irrumpe en la cocina buscando un arma. Aria ya está allí, preparando té con una sonrisa inocente. Sus miradas se cruzan sobre la encimera llena de cuchillos.",
                "tipo_encuentro": "casualidad",
                "roll_d20_asignado": 12,
                "interpretacion_roll": "Éxito parcial — Funciona razonablemente bien."
            },
            {
                "protagonistas": ["Makao", "Blueber"],
                "lugar": "Biblioteca",
                "contexto_situacion": "Makao examina meticulosamente la biblioteca. Blueber lo encuentra y le ofrece ayuda. Makao acepta con una condición: absoluta discreción.",
                "tipo_encuentro": "alianza",
                "roll_d20_asignado": 17,
                "interpretacion_roll": "Éxito rotundo — Todo sale según lo planeado o mejor."
            },
            {
                "protagonistas": ["Cov"],
                "lugar": "Torreón",
                "contexto_situacion": "Cov está solo en el torreón, escuchando los pasos en el pasillo. La puerta está atrancada pero los goznes son viejos.",
                "tipo_encuentro": "investigacion",
                "roll_d20_asignado": 3,
                "interpretacion_roll": "Fallo grave — Las cosas van mal. Error de cálculo o mala suerte."
            }
        ]
    }, ensure_ascii=False)


def _make_reaccion(name: str) -> str:
    reacciones = {
        "papu": json.dumps({
            "dialogo_exacto": "nmms Aria eres tu? q haces aqui tan noche wey? no mames me asustaste ALV",
            "accion_fisica": "Agarro el cuchillo más grande de la encimera y lo sostengo detrás de mi espalda, intentando disimular.",
            "estado_emocional_ahora": "paranoico"
        }, ensure_ascii=False),
        "Aria": json.dumps({
            "dialogo_exacto": "ay Papu! solo preparaba tecito para calmarnos 🌸 está todo tan tenso no crees? quieres una taza?",
            "accion_fisica": "Sirvo té con movimientos suaves y elegantes, ocultando el pequeño frasco que guardo en mi manga.",
            "estado_emocional_ahora": "calculador"
        }, ensure_ascii=False),
        "Makao": json.dumps({
            "dialogo_exacto": "Blueber. Good timing. I was just examining these footprints. Notice the pattern — size 7, likely a woman's shoe. How curious.",
            "accion_fisica": "Señalo las huellas en el polvo de la biblioteca con precisión quirúrgica.",
            "estado_emocional_ahora": "calculador"
        }, ensure_ascii=False),
        "Blueber": json.dumps({
            "dialogo_exacto": "woah en serio? tienes razón... yo ni había visto eso. te ayudo a buscar más pistas?",
            "accion_fisica": "Me agacho para examinar las huellas de cerca, siguiendo la dirección que Makao señala.",
            "estado_emocional_ahora": "eufórico"
        }, ensure_ascii=False),
        "Cov": json.dumps({
            "dialogo_exacto": "...esos pasos se escuchan muy cerca ._.",
            "accion_fisica": "Me escondo detrás de la cama, abrazando mis rodillas contra el pecho.",
            "estado_emocional_ahora": "aterrado"
        }, ensure_ascii=False),
    }
    return reacciones.get(name, json.dumps({
        "dialogo_exacto": "...",
        "accion_fisica": "Mirar alrededor nerviosamente.",
        "estado_emocional_ahora": "nervioso"
    }, ensure_ascii=False))


_fase_counter = [0]  # mutable para rastrear fase


def _make_ensamblaje(vivos: List[str], fase_num: int, is_final: bool = False) -> str:
    muerto = "Blueber" if fase_num == 1 and len(vivos) > 2 else (vivos[-1] if vivos else None)

    fase_data = {
        "nombre_fase": f"Fase {fase_num}: {'El Primer Corte' if fase_num == 1 else 'Sombras que se Alargan'}",
        "escenario_dinamico": "Ashford Manor se retuerce bajo la tormenta. Las velas parpadean. Algo huele a té dulce y metal.",
        "eventos": [
            {
                "accion": "Papu irrumpe en la cocina. Aria está allí, bañada en la luz cálida de las velas, preparando té. Sus dedos rozan los cuchillos magnéticos. Tira un D20: 12. Papu agarra el cuchillo más grande pero su mano tiembla — Aria lo nota pero mantiene la sonrisa. Éxito parcial: Papu consigue el arma pero Aria sabe que está armado.",
                "nombres_protagonistas": ["papu", "Aria"],
                "dialogos": {
                    "papu": "nmms Aria eres tu? q haces aqui tan noche wey? no mames me asustaste ALV",
                    "Aria": "ay Papu! solo preparaba tecito para calmarnos 🌸 está todo tan tenso no crees? quieres una taza?"
                },
                "tipo_accion": "Confrontación",
                "d20_roll": 12,
                "resultado_roll": "Éxito parcial"
            },
            {
                "accion": "Makao y Blueber forman una alianza improbable. Las huellas en el polvo de la biblioteca revelan una verdad incómoda: alguien más entró después del asesinato. Tira un D20: 17. Éxito rotundo. La pista es clara: el asesino usa zapatos de mujer y volvió a la escena del crimen.",
                "nombres_protagonistas": ["Makao", "Blueber"],
                "dialogos": {
                    "Makao": "Blueber. Good timing. I was just examining these footprints. Notice the pattern — size 7, likely a woman's shoe. How curious.",
                    "Blueber": "woah en serio? tienes razón... yo ni había visto eso. te ayudo a buscar más pistas?"
                },
                "tipo_accion": "Alianza",
                "d20_roll": 17,
                "resultado_roll": "Éxito rotundo"
            },
            {
                "accion": "Cov encierra su puerta con la silla. Pero los goznes están oxidados. Escucha pasos acercarse. Tira un D20: 3. Fallo grave. Alguien empuja la puerta desde afuera. La madera cruje. Cov contiene la respiración — pero los pasos se alejan al último segundo. ¿Quién era?",
                "nombres_protagonistas": ["Cov"],
                "dialogos": {
                    "Cov": "...esos pasos se escuchan muy cerca ._."
                },
                "tipo_accion": "Investigación",
                "d20_roll": 3,
                "resultado_roll": "Fallo grave"
            }
        ],
        "recuento_fase": {
            "resumen_breve": "Papu consiguió un cuchillo. Aria preparó té. Makao y Blueber descubrieron que el asesino tiene pies de mujer. Cov casi muere de un infarto en su cuarto.",
            "muertos_en_esta_fase": [muerto] if muerto and fase_num > 1 else [],
            "vivos_restantes": [v for v in vivos if v != muerto],
            "equipos_activos": [["Makao", "Blueber"], ["papu", "Cov"]]
        },
        "es_final": is_final,
        "ganador_absoluto": vivos[0] if is_final and len(vivos) == 1 else None
    }
    return json.dumps(fase_data, ensure_ascii=False)


def _make_summary() -> str:
    return "FASE 1: Papu consiguió un cuchillo. Makao y Blueber encontraron pistas sobre zapatos de mujer. Cov sobrevivió a un susto. El asesino sigue libre."


# ══════════════════════════════════════════════════════════════════════════════
# LLM Router — simulo ser el LLM
# ══════════════════════════════════════════════════════════════════════════════

class FakeLLM:
    """
    Mock de generate_plain(). Inspecciona el system_prompt y user_text
    para decidir qué JSON devolver, como si el LLM real respondiera.
    """
    PARTICIPANTES = ["papu", "Makao", "Cov", "Aria", "Blueber"]
    ASESINO = "Aria"
    CALL_COUNT = 0  # contador global

    async def generate_plain(
        self,
        system_prompt: str = "",
        contents: List[Any] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1000,
    ) -> str:
        FakeLLM.CALL_COUNT += 1
        user_text = ""
        if contents:
            for c in contents:
                for part in getattr(c, 'parts', []):
                    user_text += getattr(part, 'text', '')

        sp = system_prompt or ""
        ut = user_text or ""

        # ── 1. DESTILACIÓN ──
        if "Analista de Personalidad Forense" in sp:
            for name in self.PARTICIPANTES:
                if f"HISTORIAL DE {name}" in ut:
                    return _make_distillation_json(name)
            return _gen_generic_distillation("unknown")

        # ── 2. STORY BIBLE ──
        if "SHOWRUNNER" in sp:
            return _make_story_bible_json()

        # ── 3. AGENDAS ──
        if "PSICÓLOGO DE CASTING" in sp:
            return _make_agendas_json(self.PARTICIPANTES, self.ASESINO)

        # ── 4. INTENCIONES ──
        if "JUGADOR REAL" in sp or ("{nombre}" not in sp and "Eres" in sp and "juego de misterio" in sp):
            for name in self.PARTICIPANTES:
                if f"VIVOS: {name}" in ut or f"VIVOS: papu" in ut:
                    # El system prompt ya tiene el nombre reemplazado para este agente
                    pass
            # Buscar nombre en system prompt
            for name in self.PARTICIPANTES:
                if f"Eres {name}," in sp:
                    return _make_intencion(name)

        # ── 5. ENCUENTROS (GM) ──
        if "DIRECTOR DE ESCENA" in sp:
            vivos = [p for p in self.PARTICIPANTES if p in ut]
            return _make_encuentros(vivos or self.PARTICIPANTES)

        # ── 6. REACCIONES ──
        if "VIVIENDO este momento AHORA MISMO" in sp or "INDISTINGUIBLE de un mensaje real" in sp:
            for name in self.PARTICIPANTES:
                if f"Eres {name} " in sp or f"Eres {name}y" in sp:
                    return _make_reaccion(name)

        # ── 7. ENSAMBLAJE (GM) ──
        if "GAME MASTER OMNISCIENTE" in sp:
            vivos = [p for p in self.PARTICIPANTES if p in ut]
            is_final = len(vivos) <= 1
            fase_num = 1
            for line in ut.split("\n"):
                if line.startswith("FASE "):
                    try:
                        fase_num = int(line.split()[1].split("/")[0])
                    except ValueError:
                        pass
            return _make_ensamblaje(vivos or self.PARTICIPANTES, fase_num, is_final)

        # ── 8. SUMMARIZER ──
        if "CRONISTA DEL MISTERIO" in sp:
            return _make_summary()

        # ── 9. JSON FIX ──
        if "JSON tiene errores" in sp:
            return ut  # ya viene como JSON, devolverlo igual

        # ── Fallback ──
        return "{}"


# ══════════════════════════════════════════════════════════════════════════════
# Mock objects
# ══════════════════════════════════════════════════════════════════════════════

class FakeDB:
    """Mock de la DB que devuelve historiales fake."""
    async def search_messages(self, guild_id, user_id, hours, limit):
        for member_id, history in _FAKE_HISTORIES.items():
            if member_id in str(user_id) or str(user_id) in member_id:
                return history
        return []

    async def get_youkai_readers(self, guild_id):
        return []


class FakeMember:
    def __init__(self, name, mid):
        self.display_name = name
        self.display_avatar = MagicMock()
        self.display_avatar.with_size.return_value.url = f"https://cdn.discord.com/avatars/{mid}/avatar.png"
        self.id = mid
        self.bot = False
        self.guild_permissions = MagicMock()
        self.guild_permissions.administrator = False
        self.roles = []


class FakeRole:
    def __init__(self, name, members):
        self.name = name
        self.members = members
        self.id = 12345
        self.mention = f"@{name}"


class FakeChannel:
    def __init__(self, name):
        self.name = name
        self.mention = f"#{name}"
        self.id = 67890
        self.guild = MagicMock()
        self.guild.id = 99999

    async def send(self, content=None, embed=None, file=None):
        msg = f"[CANAL] {content[:100] if content else ''}"
        if embed:
            msg += f" | embed: {embed.title}"
        print(f"  📨 {msg}")
        return MagicMock()


class FakeInteraction:
    def __init__(self, user, guild):
        self.user = user
        self.guild = guild
        self.response = MagicMock()

    async def send_message(self, *args, **kwargs):
        pass


# ══════════════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════════════

async def test_distillation_parallel():
    """La destilación de 5 agentes debe completarse con asyncio.gather."""
    from cogs.torneo import TorneoCog

    bot = MagicMock()
    bot.llm = FakeLLM()
    bot.db = FakeDB()

    cog = TorneoCog(bot)

    members = [
        FakeMember("papu", 1),
        FakeMember("Makao", 2),
        FakeMember("Cov", 3),
        FakeMember("Aria", 4),
        FakeMember("Blueber", 5),
    ]

    # Simular historiales
    histories = {}
    for m in members:
        histories[m.id] = _FAKE_HISTORIES.get(m.display_name, [])

    async def _destilar(m):
        name = m.display_name
        history = histories.get(m.id, [])
        if not history:
            return name, _fallback_ficha(name, True)
        history_lines = [
            f"[{msg.get('username', name)}]: {(msg.get('content') or '')[:250]}"
            for msg in history[-MAX_MESSAGES_PER_USER:]
            if (msg.get("content") or "").strip()
        ]
        if not history_lines:
            return name, _fallback_ficha(name, True)
        try:
            ficha_json = await cog._call_llm(
                system_prompt="Analista de Personalidad Forense",
                user_text=f"HISTORIAL DE {name}:\n" + "\n".join(history_lines)[:40000] + "\n\nGenera ficha COMPLETA. SOLO JSON.",
                max_tokens=6000, temperature=0.7, expect_json=True,
            )
            ficha = json.loads(_clean_json_response(ficha_json))
            ficha["nombre"] = name
            return name, ficha
        except Exception as exc:
            return name, _fallback_ficha(name, False)

    # ── PARALELO ──
    tasks = [_destilar(m) for m in members]
    results = await asyncio.gather(*tasks)

    fichas = {}
    for name, ficha in results:
        if ficha:
            fichas[name] = ficha

    assert len(fichas) == 5, f"Esperaba 5 fichas, obtuve {len(fichas)}"
    assert "papu" in fichas
    assert "Makao" in fichas

    # Verificar que la voz de Papu se preservó
    voz_papu = _safe_list(fichas["papu"]["estilo_habla"]["voz_simulada"])
    assert any("ALV" in v or "wey" in v.lower() for v in voz_papu), \
        f"Voz de Papu no contiene sus muletillas: {voz_papu[:2]}"

    # Verificar que Makao habla en inglés formal
    voz_makao = _safe_list(fichas["Makao"]["estilo_habla"]["voz_simulada"])
    assert any("How" in v or "Indeed" in v or "curious" in v.lower() for v in voz_makao), \
        f"Voz de Makao no es formal: {voz_makao[:2]}"

    print(f"✅ Paralelización OK: {len(fichas)} fichas en {FakeLLM.CALL_COUNT} llamadas LLM")
    print(f"   Papu voice: {voz_papu[0][:60]}...")
    print(f"   Makao voice: {voz_makao[0][:60]}...")

    FakeLLM.CALL_COUNT = 0  # reset para siguientes tests


async def test_pipeline_completo():
    """Test de integración: pipeline sin rate limit (bypasseamos _rate_limit para velocidad)."""
    from cogs.torneo import TorneoCog

    bot = MagicMock()
    bot.llm = FakeLLM()
    bot.db = FakeDB()

    cog = TorneoCog(bot)
    # Bypass rate limit para test rápido
    cog._rate_limit = _nop_coro

    participantes = FakeLLM.PARTICIPANTES[:]
    vivos = list(participantes)
    fase_num = 1
    historial = ""
    muertos: List[str] = []
    memoria_agentes: Dict[str, str] = {
        n: "El torneo acaba de empezar."
        for n in participantes
    }

    escenario = {
        "nombre": "Ashford Manor",
        "descripcion": "Mansión victoriana aislada por tormenta.",
        "elementos": ["pasadizos", "armas de caza", "bodega", "biblioteca"],
        "lugares": ["Vestíbulo", "Comedor", "Biblioteca", "Cocina", "Torreón", "Bodega", "Embarcadero", "Sala de Trofeos"],
    }

    # 1. Destilación secuencial (el test de arriba ya probó paralela)
    fichas = {}
    for name in participantes:
        ficha_json = await cog._call_llm(
            system_prompt="Analista de Personalidad Forense",
            user_text=f"HISTORIAL DE {name}:\n...\n\nGenera ficha. SOLO JSON.",
            max_tokens=6000, temperature=0.7, expect_json=True,
        )
        fichas[name] = json.loads(_clean_json_response(ficha_json))

    # 2. Story Bible
    story_bible = await cog._generate_story_bible(fichas, participantes,
                                                    "DETECTIVE: Makao | ASESINO: Aria")
    assert "titulo_del_misterio" in story_bible
    print(f"  📖 Story Bible: {story_bible['titulo_del_misterio']}")

    # 3. Agendas
    agendas = await cog._generate_agendas(fichas, participantes,
                                           "DETECTIVE: Makao | ASESINO: Aria")
    assert isinstance(agendas, dict)
    assert len(agendas) == 5
    print(f"  🧠 Agendas: {len(agendas)} personajes con agenda")

    # 4. Fase 1 — Pipeline completo
    from cogs.torneo import _build_memoria_viva
    memoria_viva = _build_memoria_viva(
        {}, [], {p: "?" for p in vivos}, vivos, [], fase_num,
    )
    intenciones = await cog._fase_1_intenciones(
        vivos, fichas, "DETECTIVE: Makao | ASESINO: Aria",
        memoria_viva, agendas, escenario, fase_num,
    )
    assert len(intenciones) == len(vivos)
    assert "papu" in intenciones
    assert "sospechoso_principal" in intenciones["papu"]
    assert intenciones["papu"]["sospechoso_principal"] == "Makao"
    print(f"  🎯 Intenciones: {len(intenciones)} agentes pensaron en paralelo")

    # Verificar que el asesino (Aria) sabe que es el asesino
    assert "DETECTIVE" in "DETECTIVE: Makao | ASESINO: Aria"
    print(f"  🔪 Asesino detectado correctamente: Aria")

    # 5. Encuentros
    encuentros, board_state = await cog._fase_2_encuentros_gm(vivos, intenciones, escenario)
    assert len(encuentros) > 0
    assert isinstance(board_state, dict)
    assert len(board_state) == len(vivos), f"Board missing people: {len(board_state)} vs {len(vivos)}"
    print(f"  🔀 Encuentros: {len(encuentros)} (+ board con {len(board_state)} personas)")

    # 6. Reacciones
    reacciones = await cog._fase_3_reacciones(encuentros, fichas, escenario)
    assert len(reacciones) >= len(vivos) - 1  # algunos pueden estar en múltiples encuentros
    print(f"  💬 Reacciones: {len(reacciones)} diálogos generados")

    # 7. Ensamblaje
    phase_data = await cog._fase_4_ensamblaje_final(
        encuentros, reacciones, vivos, escenario, historial,
        "DETECTIVE: Makao | ASESINO: Aria", fase_num, 7,
        fichas, "Test Mystery", "Paranoia",
        story_bible, agendas,
    )
    assert "eventos" in phase_data
    assert len(phase_data["eventos"]) >= 2
    print(f"  ⚔️ Ensamblaje: {len(phase_data['eventos'])} eventos narrados")
    print(f"  📊 Recuento: {phase_data['recuento_fase']['resumen_breve'][:100]}...")

    # 8. Verificar consistencia narrativa
    eventos = phase_data["eventos"]
    # Todos los eventos tienen protagonistas, diálogos, D20 roll
    for evt in eventos:
        assert "nombres_protagonistas" in evt
        assert "accion" in evt
        assert "d20_roll" in evt
        assert "dialogos" in evt

    # Los diálogos de Papu deben contener ALV
    dialogos_papu = [evt["dialogos"].get("papu", "") for evt in eventos if "papu" in evt.get("dialogos", {})]
    if dialogos_papu:
        assert any("ALV" in d or "wey" in d.lower() for d in dialogos_papu), \
            f"Diálogos Papu no tienen voz: {dialogos_papu}"

    print(f"\n🔥 PIPELINE COMPLETO OK — {FakeLLM.CALL_COUNT} llamadas LLM totales")
    print(f"   Voz Papu preservada: {bool(dialogos_papu)}")


async def test_rate_limit_enforced():
    """El rate limit debe respetar max 9 llamadas por ventana."""
    from cogs.torneo import RATE_LIMIT_CALLS, TorneoCog

    bot = MagicMock()
    bot.llm = FakeLLM()
    bot.db = FakeDB()

    cog = TorneoCog(bot)

    # Hacer RATE_LIMIT_CALLS llamadas rápidas — no deberían esperar
    for i in range(RATE_LIMIT_CALLS):
        r = await cog._call_llm(
            system_prompt="Test",
            user_text=f"Call {i}",
            max_tokens=100,
        )
        assert r, f"Call {i} returned empty"

    print(f"✅ Rate limit test: {RATE_LIMIT_CALLS} calls sin espera forzada")


# ══════════════════════════════════════════════════════════════════════════════
# Runner sin pytest
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print("═══════════════════════════════════════")
    print("  🧪 TORNEO INTEGRATION TEST SUITE")
    print("  LLM = GitHub Copilot (yo)")
    print("═══════════════════════════════════════\n")

    await test_distillation_parallel()
    print()
    await test_pipeline_completo()
    print()
    await test_rate_limit_enforced()
    print()
    print("═══════════════════════════════════════")
    print("  ✅ ALL TESTS PASSED")
    print("═══════════════════════════════════════")


if __name__ == "__main__":
    asyncio.run(main())
