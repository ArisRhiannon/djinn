"""Acto 5 — ENDINGS 9-12: Carcajada Cósmica, Pacto Mercantil, Gran Olvido, Vacío de Azathoth."""
from __future__ import annotations
from typing import Any, Callable, Dict, List


def build_act5_endings_9_12(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 5
    nodes: List[Dict[str, Any]] = []

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 9: La Carcajada Cósmica
    # Los dioses nunca existieron. Todo fue una broma. No puedes parar de reír.
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_ending_carcajada", act=A, zone="Trono Vacío", tone="madness",
        is_ending=True,
        primary_npc="nyarlathotep",
        text=(
            "Llegas al trono. Los dioses no se fueron — nunca existieron. "
            "Nunca hubo nadie aquí. Nunca hubo un propósito.\n\n"
            "Todo fue una broma. El universo entero es un chiste "
            "contado por nadie para nadie.\n\n"
            "Empiezas a reír. No puedes parar. No quieres parar. "
            "La risa te consume como fuego frío. Ríes hasta que ya no "
            "eres tú quien ríe — es el vacío riendo a través de ti."
        ),
        text_variants={
            "nyar_divertido": (
                "Nyarlathotep ríe contigo. A tu lado. Para siempre.\n\n"
                "— ¿Ves? Te dije que era gracioso. Siempre fue gracioso.\n\n"
                "Dos risas en la oscuridad. Una eterna. La otra... "
                "también eterna. Ya no hay diferencia entre ustedes."
            ),
            "desafio_nyar": (
                "— Te dije que ganarías. No dije que te gustaría el premio.\n\n"
                "Nyarlathotep aplaude mientras ríes. Ganaste el desafío. "
                "El premio es saber que nada importó. Que la victoria "
                "y la derrota son el mismo chiste."
            ),
            "digno_de_kadath": (
                "La dignidad se rompe primero. Luego el orgullo. "
                "Luego la cordura. El héroe que fue digno de Kadath "
                "ríe hasta que ya no es héroe. Ríe hasta que ya no es nada.\n\n"
                "La dignidad era parte del chiste."
            ),
            "sabe_verdad_kadath": (
                "Sabías la verdad. Siempre la supiste. Pero saber que "
                "la verdad es un chiste no te prepara para el punchline.\n\n"
                "El chiste eres tú. Siempre fuiste tú. Y ahora lo entiendes "
                "y no puedes dejar de reír."
            ),
        },
        on_enter={"lucidez": -99, "corrupcion": +10},
        paths=[],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 10: Pacto Mercantil
    # Eres el nuevo Papu. Comercias sombras. Vendes sueños. Es eterno. Es vacío.
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_ending_mercantil", act=A, zone="Trono Vacío", tone="hollow",
        is_ending=True,
        primary_npc="papu",
        text=(
            "El trono no es un trono. Es un mostrador. Siempre fue un mostrador.\n\n"
            "Te sientas detrás. Las sombras vienen solas. Los sueños se apilan "
            "como mercancía. Alguien viene a comprar. Alguien siempre viene.\n\n"
            "Eres el nuevo Papu. Comercias sombras. Vendes sueños. "
            "Compras lo que queda de los que pasan. Es eterno. Es vacío. "
            "Es un negocio."
        ),
        text_variants={
            "aliado_papu": (
                "Papu está a tu lado. Sonríe con orgullo.\n\n"
                "— Bienvenido al negocio, mano. Clean.\n\n"
                "Te enseña los trucos. Cómo pesar una sombra. "
                "Cómo tasar un sueño. Cómo no sentir nada cuando "
                "alguien te paga con lo último que le queda."
            ),
            "compro_sombra_papu": (
                "Ya habías empezado. La primera sombra que compraste "
                "fue el inicio. Solo faltaba el título oficial.\n\n"
                "Ahora es tuyo. El mostrador. Las sombras. El vacío. "
                "Siempre fue tuyo. Solo no lo sabías."
            ),
            "libero_almacen_papu": (
                "Irónico. Liberaste sus sombras. Vaciaste su almacén. "
                "Y ahora vendes las tuyas.\n\n"
                "El almacén se llena de nuevo. Con tu mercancía. "
                "Con tus sombras. El ciclo no se rompe — solo cambia de dueño."
            ),
            "papu_enemigo_mortal": (
                "Papu está en una jaula detrás del mostrador. Tú lo pusiste ahí.\n\n"
                "Te mira con ojos vacíos. No con odio — con reconocimiento. "
                "Sabe que algún día alguien te pondrá a ti en esa jaula.\n\n"
                "El ciclo se repite. Siempre se repite."
            ),
        },
        on_enter={"corrupcion": +15, "voluntad": -99},
        paths=[],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 11: El Gran Olvido
    # Olvidas todo. Te sientas en el trono. Esperas. No sabes qué.
    # También accesible si voluntad=0 en el desafío del Acto 4.
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_ending_olvido", act=A, zone="Trono Vacío", tone="void",
        is_ending=True,
        primary_npc=None,
        text=(
            "Olvidas. Primero los nombres. Luego las caras. "
            "Luego por qué viniste. Luego qué es venir.\n\n"
            "Te sientas en el trono. Esperas. No sabes qué esperas. "
            "No sabes que esperas. No sabes.\n\n"
            "El trono está vacío. Tú estás vacío. No hay diferencia."
        ),
        text_variants={
            "memoria < 10": (
                "Esto ya pasó antes. Muchas veces. Llegas, olvidas, "
                "te sientas, esperas. Alguien te encuentra. Te lleva al inicio. "
                "Vuelves a empezar.\n\n"
                "Un loop eterno. No lo sabes. Nunca lo sabes. "
                "Esa es la gracia."
            ),
            "perdio_voluntad_nyar": (
                "Nyarlathotep te borró a propósito. Con cuidado. "
                "Con cariño, incluso.\n\n"
                "— Shh. Ya no duele. Ya no piensas. Ya no eres.\n\n"
                "Eres su mascota sin mente. Te acaricia la cabeza. "
                "No sientes nada. Eso es lo que él quería."
            ),
            "trauma_edyssey": (
                "Lo último que olvidas son los gritos de Edyssey. "
                "Se aferran como garras. Son lo último en irse.\n\n"
                "Luego se van. Y luego nada. Nada. Nada.\n\n"
                "Silencio perfecto."
            ),
            "edyssey_muerto + mato_edyssey": (
                "Edyssey está sentado a tu lado. También olvidó. "
                "No sabe quién eres. No sabes quién es.\n\n"
                "Dos fantasmas en un trono vacío. Esperando algo "
                "que ninguno recuerda. Para siempre."
            ),
        },
        on_enter={"memoria": -99, "voluntad": -99},
        paths=[],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 12: El Vacío de Azathoth
    # Caes al centro del universo. Caos nuclear ciego. Solo flautas eternas.
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_ending_vacio", act=A, zone="El Vacío", tone="cosmic_horror",
        is_ending=True,
        primary_npc="nyarlathotep",
        text=(
            "Caes. No hacia abajo — hacia adentro. Hacia el centro de todo.\n\n"
            "Azathoth. El caos nuclear ciego e idiota que sueña el universo. "
            "No tiene ojos. No tiene mente. No tiene nada excepto "
            "el zumbido eterno de flautas que nadie toca para nadie.\n\n"
            "Caes hacia eso. Para siempre. No hay fondo. "
            "No hay final. Solo flautas. Solo el vacío. Solo tú, "
            "disolviéndote en el sueño de algo que no sabe que sueña."
        ),
        text_variants={
            "nyar_furioso": (
                "Nyarlathotep te empujó. Lo último que ves es su rostro — "
                "furioso, hermoso, terrible.\n\n"
                "— Farewell. And beware. For I am Nyarlathotep, "
                "the Crawling Chaos.\n\n"
                "Su voz se pierde en el zumbido. Caes. Las flautas te reciben."
            ),
            "ruta_dama_activa + nyar_es_zuto": (
                "Zuto — no, Nyarlathotep — te trajo aquí a propósito. "
                "Cada paso del camino fue diseñado para esto.\n\n"
                "Eras combustible para Azathoth. Tu consciencia, "
                "tu memoria, tu dolor — todo alimenta el sueño "
                "del dios ciego. Fuiste gasolina. Nada más."
            ),
            "escapo_de_nyar": (
                "Escapaste de Nyarlathotep. Creíste que eso bastaba. "
                "Pero hay cosas peores que el Caos Reptante.\n\n"
                "Azathoth no te persiguió. No necesita perseguir. "
                "Todo cae hacia él eventualmente.\n\n"
                "Nyarlathotep ríe desde arriba. Muy, muy arriba."
            ),
            "desafio_nyar + nyar_furioso": (
                "— Me desafiaste. Nadie me desafía. NADIE.\n\n"
                "Nyarlathotep no sonríe. Por primera vez no sonríe.\n\n"
                "— Disfruta la eternidad.\n\n"
                "Te empuja. Caes. Las flautas suenan más fuerte. "
                "Más fuerte. Más fuerte. Para siempre."
            ),
        },
        on_enter={"lucidez": -99, "memoria": -99, "voluntad": -99, "corrupcion": +99},
        paths=[],
    ))

    return nodes
