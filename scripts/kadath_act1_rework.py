"""Acto 1 Rework — Edyssey como guía/traidor + El Payaso del Umbral.

57 nodos. Reemplaza el build_act1 original.
Secciones:
  A (1-15):  Descenso + encuentro con Edyssey
  B (16-30): Edyssey guía, payaso aparece
  C (31-45): Tensión, pistas de traición
  D (46-57): Desenlace — 3 caminos al Acto 2

INTEGRACIÓN:
  - El prólogo (prologo_despertar) debe apuntar a 'act1_descenso_inicio'
    en vez de los targets viejos (act1_glifos, act1_umbral_quedarse, act1_caida_libre).
  - Las salidas al Acto 2 se mantienen:
    act1_final_cruce_yermos → act2_hub_yermos
    act1_final_cruce_bosque → act2_bosque_zoog_entrada
  - Para usar: en generate_kadath_world.py, reemplazar la llamada a build_act1
    por build_act1_rework de este módulo.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List


def build_act1_rework(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 1
    nodes: List[Dict[str, Any]] = []

    # ═══════════════════════════════════════════════════════════════════
    # SECCIÓN A — El Descenso + Encuentro con Edyssey (nodos 1-15)
    # ═══════════════════════════════════════════════════════════════════

    nodes += _section_a(N, P, A)
    nodes += _section_b(N, P, A)
    nodes += _section_c(N, P, A)
    nodes += _section_d(N, P, A)

    return nodes


def _section_a(N: Callable, P: Callable, A: int) -> List[Dict[str, Any]]:
    """Sección A: El Descenso + Encuentro con Edyssey (15 nodos)."""
    nodes = []

    nodes.append(N(
        "act1_descenso_inicio",
        act=A, zone="El Descenso — Despertar",
        tone="awe",
        text=(
            "La escalera de obsidiana desciende en espiral. El aire huele a "
            "ozono y a recuerdos que no son tuyos. En algún lugar abajo, "
            "alguien habla solo — una voz irritada que rebota entre las paredes."
        ),
        on_enter={"lucidez": 2},
        character_dialogue={
            "aris": "hay alguien hablando abajo. no suena contento",
            "law": "bro escucho a alguien quejándose allá abajo, qué onda",
            "haru": "mano hay alguien hablando solo ahí abajo xd",
            "elyko": "voz masculina, tono irritado, eco indica 3 estratos de distancia",
            "xoft": "JAJAJA hay un wey quejándose solo allá abajo vamos a ver",
            "xokram": "alguien está hablando solo abajo, suena molesto",
            "daraziel": "hay eco de voz humana. alguien lleva rato aquí.",
        },
        paths=[
            P("Descender hacia la voz", "act1_descenso_ecos",
              style="primary", effects={"lucidez": 1}),
            P("Examinar las paredes primero", "act1_descenso_marcas",
              style="secondary", effects={"lore": 2}),
            P("Lanzarte al vacío lateral", "act1_descenso_caida",
              style="danger", effects={"voluntad": -4, "lore": 3}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_ecos",
        act=A, zone="El Descenso — Ecos",
        tone="discovery",
        text=(
            "La voz se hace más clara conforme bajas. Alguien dice: "
            "\"...es que la gente no entiende, osea yo llevo aquí más tiempo "
            "que nadie y nadie me lo reconoce...\"\n\n"
            "Los ecos distorsionan las palabras pero el tono es inconfundible: "
            "frustración pura, mezclada con algo parecido al orgullo herido."
        ),
        on_enter={"lore": 2, "lucidez": -1},
        character_dialogue={
            "aris": "ese tío suena como si llevara años quejándose de lo mismo",
            "law": "pobre tipo, suena frustrado de verdad",
            "haru": "xd ese wey suena como youtuber enojado con sus viewers",
            "elyko": "patrón de habla repetitivo. lleva mucho tiempo solo.",
            "xoft": "KSJSJ suena como cuando te quejas en el void y nadie te escucha",
            "xokram": "ese man suena como vendedor al que nadie le compra",
            "daraziel": "lleva rato en loop. eso no es sano.",
        },
        paths=[
            P("Seguir bajando hacia él", "act1_encuentro_voz",
              style="primary", effects={"voluntad": 1}),
            P("Detenerte a escuchar más", "act1_descenso_glifos",
              style="secondary", effects={"lore": 3}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_marcas",
        act=A, zone="El Descenso — Marcas",
        tone="discovery",
        text=(
            "Las paredes están llenas de marcas. No son glifos antiguos — son "
            "anotaciones recientes, hechas con algo afilado. Lees fragmentos:\n\n"
            "\"Día 847: sigo sin poder cruzar\"\n"
            "\"La puerta no se abre para mí\"\n"
            "\"Nadie documenta esto como yo\"\n"
            "\"El de la cara pintada estuvo aquí otra vez\"\n\n"
            "La última nota tiene un emoji de payaso 🤡 tachado con furia."
        ),
        on_enter={"lore": 4, "lucidez": 1},
        set_flags=["vio_marcas_edyssey"],
        character_dialogue={
            "aris": "847 días. eso es más de dos años atrapado aquí",
            "law": "el de la cara pintada... eso suena siniestro",
            "haru": "mano el emoji de payaso tachado me da mal rollo",
            "elyko": "847 iteraciones. el sujeto está obsesionado con documentar.",
            "xoft": "JAJAJA el payaso emoji tachado, qué le hizo el payaso",
            "xokram": "ese man lleva 847 días y no puede salir? uff",
            "daraziel": "las marcas son recientes. quien sea, sigue aquí.",
        },
        paths=[
            P("Seguir bajando", "act1_descenso_ecos",
              style="primary", effects={"voluntad": 1}),
            P("Buscar más marcas", "act1_descenso_glifos",
              style="secondary", effects={"lore": 2, "lucidez": -1}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_glifos",
        act=A, zone="El Descenso — Glifos Ancestrales",
        tone="discovery",
        text=(
            "Más abajo, las marcas humanas dan paso a glifos pre-humanos. "
            "Los símbolos se reordenan cuando no los miras directamente. "
            "Uno brilla con insistencia — parece un mapa, o una advertencia.\n\n"
            "Entre los glifos, alguien escribió con letra moderna: "
            "\"ya los leí todos, no sirven de nada xd\""
        ),
        on_enter={"lore": 3},
        character_dialogue={
            "aris": "glifos pre-humanos con graffiti moderno. qué combinación",
            "law": "los glifos se mueven solos... y alguien escribió 'xd' entre ellos",
            "haru": "el xd entre glifos ancestrales es arte moderno involuntario",
            "elyko": "el que escribió eso ya descifró los glifos. nos lleva ventaja.",
            "xoft": "JAJAJA 'no sirven de nada xd' entre glifos cósmicos",
            "xokram": "alguien ya pasó por aquí y dejó review negativa",
            "daraziel": "los glifos son legítimos. la nota es del mismo que las marcas.",
        },
        paths=[
            P("Leer los glifos en voz alta", "act1_descenso_glifos_leidos",
              style="primary", effects={"lore": 4}),
            P("Tocar el símbolo brillante", "act1_descenso_vision",
              style="danger", effects={"corrupcion": 3, "lore": 5}),
            P("Ignorar y seguir bajando", "act1_encuentro_voz",
              style="secondary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_glifos_leidos",
        act=A, zone="El Descenso — Glifos Leídos",
        tone="awe",
        text=(
            "Pronuncias los glifos con la voz que te prestó el sueño. Los muros "
            "responden: un zumbido grave que te dice que Kadath está al final de "
            "siete descensos, y que el Umbral tiene un guardián que no es humano.\n\n"
            "La voz de abajo se calla de golpe. Luego: \"...eh? alguien más "
            "sabe leer eso?\""
        ),
        on_enter={"lore": 6, "memoria": -2},
        give_item="fragmento_glifo",
        set_flags=["leyo_glifos"],
        paths=[
            P("Responder en voz alta", "act1_encuentro_voz",
              style="primary", effects={"voluntad": 2}),
            P("Quedarte en silencio", "act1_encuentro_edyssey",
              style="secondary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_mirada_atras",
        act=A, zone="El Descenso — Mirada Atrás",
        tone="horror",
        text=(
            "Miras atrás. Arriba ya no hay umbral. Hay una figura. Alta, "
            "delgada, con algo en la cara que podría ser pintura o podría ser "
            "una sonrisa demasiado ancha. No se mueve. Solo te observa.\n\n"
            "Cuando parpadeas, ya no está. Pero en la pared donde estaba, "
            "hay un emoji: 🤡"
        ),
        on_enter={"corrupcion": 5, "lucidez": -4, "voluntad": -3},
        set_flags=["vio_al_payaso"],
        character_dialogue={
            "aris": "eso no era humano. la sonrisa era demasiado ancha",
            "law": "no no no no eso que era eso QUE ERA ESO",
            "haru": "mano... el emoji de payaso en la pared... no me gusta",
            "elyko": "entidad no catalogada. sonrisa imposible. evitar contacto.",
            "xoft": "... ok eso sí me dio cosa no voy a mentir",
            "xokram": "nope. nope nope nope. seguimos bajando YA",
            "daraziel": "la proporción de esa sonrisa no es anatómicamente posible.",
        },
        paths=[
            P("Correr hacia abajo", "act1_encuentro_voz",
              style="danger", effects={"voluntad": -2}),
            P("Quedarte quieto, respirar", "act1_descenso_glifos",
              style="secondary", effects={"lucidez": 3}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_caida",
        act=A, zone="El Descenso — Caída Libre",
        tone="horror",
        text=(
            "Te lanzas al costado. No hay suelo. Caes por una geometría que "
            "no permite caídas y sin embargo caes. Al fondo, algo te observa — "
            "una cara pintada que sonríe mientras caes hacia ella.\n\n"
            "Aterrizas de pie. La cara ya no está. Pero escuchas una risa "
            "breve, como de alguien que acaba de ganar un juego."
        ),
        on_enter={"voluntad": -5, "lore": 5, "corrupcion": 4},
        set_flags=["vio_al_payaso"],
        character_dialogue={
            "aris": "la cara pintada. estaba esperándome abajo. esto no es random",
            "law": "LA RISA BRO escuché una risa cuando caí QUÉ",
            "haru": "ok la cara pintada esa me persigue o qué",
            "elyko": "la entidad estaba posicionada para interceptar la caída. es inteligente.",
            "xoft": "... la risa. ok. no me gustó eso",
            "xokram": "esa cosa me estaba esperando abajo. sabe lo que hago",
            "daraziel": "la geometría de la caída fue manipulada. algo controla este espacio.",
        },
        paths=[
            P("Buscar de dónde vino la risa", "act1_descenso_mirada_atras",
              style="danger", effects={"corrupcion": 2}),
            P("Ignorar y seguir", "act1_encuentro_voz",
              style="primary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_descenso_vision",
        act=A, zone="El Descenso — Visión Prohibida",
        tone="awe",
        text=(
            "Al tocar el símbolo, tu mente se fractura. Ves Kadath — una "
            "montaña de ónice perforando el cielo del sueño. Ves al Caos "
            "Reptante sonriendo. Y ves algo más: un hombre sentado en una "
            "escalera, rodeado de marcas en las paredes, hablando solo "
            "mientras una sombra con cara de payaso lo observa desde arriba."
        ),
        on_enter={"lore": 8, "memoria": -3, "corrupcion": 3},
        set_flags=["vio_vision_previa"],
        paths=[
            P("Sacudir la visión y bajar", "act1_encuentro_voz",
              style="primary", effects={"voluntad": 2}),
            P("Intentar ver más del payaso", "act1_descenso_mirada_atras",
              style="danger", effects={"corrupcion": 3, "lore": 4}),
        ],
    ))

    nodes.append(N(
        "act1_encuentro_voz",
        act=A, zone="El Descenso — La Voz",
        tone="social",
        text=(
            "Llegas a un rellano amplio. Un hombre está sentado contra la "
            "pared, rodeado de marcas talladas. Tiene ojeras profundas y "
            "una expresión de alguien que lleva demasiado tiempo solo.\n\n"
            "Te mira. \"Vaya. Otro que baja. Qué quieres que diga, bienvenido "
            "al Umbral o lo que sea. No es que importe.\""
        ),
        on_enter={"lucidez": 1},
        primary_npc="edyssey",
        paths=[
            P("\"¿Quién eres?\"", "act1_encuentro_edyssey",
              style="primary", effects={"lore": 1}),
            P("\"¿Llevas mucho aquí?\"", "act1_edyssey_historia",
              style="secondary", effects={"lore": 2}),
            P("Ignorarlo y seguir bajando", "act1_edyssey_desconfia",
              style="danger", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act1_encuentro_edyssey",
        act=A, zone="El Umbral — Edyssey",
        tone="social",
        text=(
            "\"Me llamo Edyssey. Soy... osea, soy el que más sabe de este "
            "sitio. Llevo aquí más que nadie. He documentado todo — cada "
            "pasillo, cada glifo, cada trampa. Nadie lo ha hecho como yo.\"\n\n"
            "Se levanta. Es más bajo de lo que esperabas. Sus ojos tienen "
            "esa intensidad de quien necesita que le crean.\n\n"
            "\"Es que la gente baja, cruza la puerta, y ni me mira. Como si "
            "yo no existiera. Qué quieres que diga.\""
        ),
        on_enter={"lore": 3, "lucidez": -1},
        primary_npc="edyssey",
        npc_trust={"edyssey": 5},
        set_flags=["conoce_edyssey"],
        paths=[
            P("\"¿Por qué no has cruzado tú?\"", "act1_edyssey_historia",
              style="primary", effects={"lore": 2}),
            P("\"¿Puedes guiarme?\"", "act1_edyssey_acepta",
              style="success", effects={"favor": 3}),
            P("\"No me interesa, adiós\"", "act1_edyssey_desconfia",
              style="danger", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_desconfia",
        act=A, zone="El Umbral — Desconfianza",
        tone="tense",
        text=(
            "Edyssey te mira con los ojos entrecerrados.\n\n"
            "\"Ah ya. Eres de esos. Los que pasan de largo. Los que creen "
            "que no necesitan a nadie. Pues vale, tú verás. Pero te digo "
            "una cosa — hay algo aquí abajo que no te va a dejar pasar "
            "tan fácil. A mí me persigue. Y si me ha visto contigo...\"\n\n"
            "Se calla. Mira por encima de tu hombro. Su cara cambia."
        ),
        on_enter={"voluntad": 2, "lucidez": -2},
        primary_npc="edyssey",
        npc_trust={"edyssey": -10},
        paths=[
            P("\"¿Qué te persigue?\"", "act1_edyssey_historia",
              style="primary", effects={"lore": 3}),
            P("Mirar atrás", "act1_descenso_mirada_atras",
              style="danger", effects={"corrupcion": 2}),
            P("\"Vale, guíame entonces\"", "act1_edyssey_acepta",
              style="success", effects={"favor": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_acepta",
        act=A, zone="El Umbral — Alianza",
        tone="social",
        text=(
            "Edyssey sonríe por primera vez. Es una sonrisa torcida, como "
            "de alguien que no practica mucho.\n\n"
            "\"Mira, no sé por qué pero me caes... osea no es que me caigas "
            "bien, es que al menos me escuchas. La gente normalmente pasa "
            "de mí. Vaya, pues vale. Te enseño el camino. Pero me debes una.\"\n\n"
            "Se pone en marcha sin esperar respuesta."
        ),
        on_enter={"favor": 4, "lucidez": 1},
        primary_npc="edyssey",
        npc_trust={"edyssey": 15},
        set_flags=["edyssey_guia"],
        paths=[
            P("Seguirlo", "act1_edyssey_campamento",
              style="primary", effects={"voluntad": 1}),
            P("\"¿Qué me debes una? Explica\"", "act1_edyssey_historia",
              style="secondary", effects={"lore": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_historia",
        act=A, zone="El Umbral — Historia de Edyssey",
        tone="loss",
        text=(
            "\"Es que... mira. Yo llegué aquí hace mucho. Más que nadie. "
            "Y he documentado todo — cada ruta, cada trampa, cada secreto. "
            "Nadie ha hecho lo que yo. Pero la puerta no se abre para mí. "
            "No sé por qué.\"\n\n"
            "Hace una pausa. Baja la voz.\n\n"
            "\"Y hay algo más. Hay... una cosa. Con cara de payaso. Me "
            "persigue. Siempre está ahí. Cada vez que intento cruzar, "
            "aparece. Es como si no quisiera que me fuera.\"\n\n"
            "\"Qué quieres que diga. Nadie me cree cuando lo cuento.\""
        ),
        on_enter={"lore": 5, "lucidez": -2, "memoria": 2},
        primary_npc="edyssey",
        npc_trust={"edyssey": 10},
        set_flags=["sabe_historia_edyssey"],
        paths=[
            P("\"Te creo. Yo también lo vi.\"", "act1_edyssey_acepta",
              style="success", effects={"favor": 5},
              conditions={"has_flag": "vio_al_payaso"}),
            P("\"Guíame, te ayudaré\"", "act1_edyssey_acepta",
              style="primary", effects={"favor": 3}),
            P("\"Suena a excusa para no avanzar\"", "act1_edyssey_desconfia",
              style="danger", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_campamento",
        act=A, zone="El Umbral — Campamento de Edyssey",
        tone="calm",
        text=(
            "El campamento de Edyssey es un rellano amplio con marcas por "
            "todas las paredes. Hay un mapa dibujado con obsesión enfermiza — "
            "cada pasillo del Umbral catalogado, cada trampa señalada.\n\n"
            "\"Ves? Nadie ha hecho esto. Nadie. He mapeado todo el Umbral. "
            "Es que la gente baja corriendo y no documenta nada. Yo sí.\"\n\n"
            "En una esquina hay un montón de emojis de payaso 🤡 tachados."
        ),
        on_enter={"lore": 4, "lucidez": 2, "memoria": 1},
        primary_npc="edyssey",
        give_item="mapa_edyssey",
        paths=[
            P("Estudiar el mapa", "act1_edyssey_mapa",
              style="primary", effects={"lore": 3}),
            P("Preguntar por los payasos tachados", "act1_edyssey_nervioso_camp",
              style="secondary", effects={"lore": 2}),
            P("\"Vámonos ya\"", "act1_guia_sendero",
              style="success", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_mapa",
        act=A, zone="El Umbral — El Mapa",
        tone="discovery",
        text=(
            "El mapa es impresionante en su detalle y perturbador en su "
            "obsesión. Cada pasillo tiene notas: \"aquí me persiguió\", "
            "\"aquí casi cruzo\", \"aquí la gente me ignoró\".\n\n"
            "Edyssey señala con orgullo: \"Ves la Puerta de Bronce? Está "
            "a siete estratos. Yo conozco un atajo. Pero... osea, no sé "
            "si funciona para dos. Nunca he ido con nadie.\"\n\n"
            "Algo en su tono suena calculado."
        ),
        on_enter={"lore": 5, "lucidez": -1},
        primary_npc="edyssey",
        paths=[
            P("\"Vamos por el atajo\"", "act1_guia_sendero",
              style="primary", effects={"voluntad": 1}),
            P("\"¿Por qué no funciona para dos?\"", "act1_edyssey_nervioso_camp",
              style="secondary", effects={"lucidez": 2}),
            P("Ir por la ruta normal", "act1_guia_escalera_media",
              style="secondary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_nervioso_camp",
        act=A, zone="El Umbral — Nervios",
        tone="tense",
        text=(
            "Edyssey se tensa cuando preguntas por el payaso.\n\n"
            "\"No sé qué es. Osea, es como... una cosa. Con cara pintada. "
            "Siempre sonriendo. Me sigue a todas partes. Cada vez que "
            "intento cruzar la puerta, aparece y... no sé. Me bloquea.\"\n\n"
            "Se frota los brazos.\n\n"
            "\"La gente dice que no existe. Que me lo invento. Pero yo lo "
            "veo. Siempre lo veo. Es que nadie me cree.\""
        ),
        on_enter={"lucidez": -2, "lore": 3},
        primary_npc="edyssey",
        npc_trust={"edyssey": 5},
        paths=[
            P("\"Yo te creo. Vámonos.\"", "act1_guia_sendero",
              style="success", effects={"favor": 3}),
            P("\"¿Y si el payaso eres tú?\"", "act1_edyssey_desconfia",
              style="danger", effects={"voluntad": 4, "lucidez": 2}),
        ],
    ))

    return nodes


def _section_b(N: Callable, P: Callable, A: int) -> List[Dict[str, Any]]:
    """Sección B: Edyssey guía + El Payaso aparece (15 nodos)."""
    nodes = []

    nodes.append(N(
        "act1_guia_sendero",
        act=A, zone="El Umbral — Sendero de Edyssey",
        tone="tense",
        text=(
            "Edyssey te lleva por un pasillo lateral que no aparece en "
            "ningún mapa normal. Las paredes aquí son más estrechas y "
            "el aire huele a algo dulce y podrido.\n\n"
            "\"Este es mi atajo. Lo descubrí yo. Nadie más lo conoce. "
            "Es que la gente no explora, solo quiere llegar rápido.\"\n\n"
            "Camina con la seguridad de quien ha recorrido esto mil veces."
        ),
        on_enter={"lore": 2, "lucidez": 1},
        primary_npc="edyssey",
        paths=[
            P("Seguirlo en silencio", "act1_guia_advertencia",
              style="primary", effects={"voluntad": 1}),
            P("\"¿Qué es ese olor?\"", "act1_payaso_primera_senal",
              style="secondary", effects={"lucidez": 2}),
            P("Detenerte a examinar las paredes", "act1_guia_gato",
              style="secondary", effects={"lore": 3}),
        ],
    ))

    nodes.append(N(
        "act1_guia_advertencia",
        act=A, zone="El Umbral — Advertencia",
        tone="tense",
        text=(
            "Edyssey se detiene de golpe. Levanta una mano.\n\n"
            "\"Osea, te lo digo en serio. No mires las sombras. Las de "
            "aquí se mueven solas. Y si ves algo con cara pintada... "
            "no le hables. No lo mires. No existes para él.\"\n\n"
            "Su voz tiembla un poco en la última frase.\n\n"
            "\"Es que la gente no me cree cuando digo esto. Pero yo "
            "llevo aquí 847 días. Sé de lo que hablo.\""
        ),
        on_enter={"lucidez": -2, "voluntad": -1},
        primary_npc="edyssey",
        paths=[
            P("Asentir y seguir", "act1_guia_bifurcacion",
              style="primary", effects={"voluntad": 1}),
            P("\"¿847 días? ¿Cómo sobrevives?\"", "act1_edyssey_queja",
              style="secondary", effects={"lore": 2}),
            P("Mirar las sombras deliberadamente", "act1_payaso_primera_senal",
              style="danger", effects={"corrupcion": 3, "voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act1_guia_gato",
        act=A, zone="El Umbral — El Gato",
        tone="calm",
        text=(
            "Un gato negro aparece entre las grietas de la pared. Te mira "
            "con ojos que saben demasiado. Edyssey lo ve y frunce el ceño.\n\n"
            "\"Ah, los gatos. Vaya. Estos bichos van y vienen como quieren. "
            "A mí nunca me hacen caso. Osea, yo les hablo y me ignoran. "
            "Pero a ti seguro que sí, no?\"\n\n"
            "El gato ronronea mirándote solo a ti."
        ),
        on_enter={"lucidez": 3, "favor": 2},
        primary_npc="edyssey",
        paths=[
            P("Seguir al gato", "act1_guia_gato_sigue",
              style="success", effects={"favor": 3, "lucidez": 2}),
            P("Ignorar al gato, seguir con Edyssey", "act1_guia_bifurcacion",
              style="primary", effects={"voluntad": 1}),
            P("\"¿Por qué no te hacen caso?\"", "act1_edyssey_queja",
              style="secondary", effects={"lore": 2}),
        ],
    ))

    nodes.append(N(
        "act1_guia_gato_sigue",
        act=A, zone="El Umbral — Sendero Felino",
        tone="calm",
        text=(
            "El gato te lleva por un pasillo que no existía antes. Hay "
            "velas que arden sin fuego. Edyssey te sigue a regañadientes.\n\n"
            "\"Genial. Ahora seguimos al gato. Es que siempre es así — "
            "la gente prefiere seguir a un gato que a alguien que lleva "
            "847 días mapeando esto. Qué quieres que diga.\"\n\n"
            "El gato te deja un bigote en la mano. Parece un regalo."
        ),
        on_enter={"lucidez": 4, "favor": 4},
        primary_npc="edyssey",
        give_item="bigote_gato_ulthar",
        npc_trust={"edyssey": -5},
        paths=[
            P("Seguir al gato hasta el consejo", "act1_guia_ulthar_consejo",
              style="success", effects={"favor": 2}),
            P("Volver con Edyssey", "act1_guia_bifurcacion",
              style="primary", effects={"voluntad": 1}),
        ],
    ))

    nodes.append(N(
        "act1_guia_ulthar_consejo",
        act=A, zone="Ulthar — Consejo de Gatos",
        tone="social",
        text=(
            "Siete gatos te esperan en un salón redondo. Edyssey se queda "
            "en la puerta, incómodo.\n\n"
            "\"A mí nunca me dejaron entrar aquí. 847 días y nunca. Pero "
            "tú llegas y ya te invitan. Es que es siempre así.\"\n\n"
            "El gato mayor habla sin hablar: *¿Cuántos sueños caben en "
            "una escalera?*"
        ),
        on_enter={"lore": 4},
        primary_npc="edyssey",
        paths=[
            P("\"Siete\"", "act1_guia_ulthar_respuesta",
              style="primary", effects={"favor": 8, "lucidez": 3}),
            P("\"Uno: el mío\"", "act1_guia_ulthar_respuesta",
              style="secondary", effects={"lore": 4, "favor": -2}),
            P("No responder; escuchar", "act1_guia_ulthar_respuesta",
              style="secondary", effects={"lucidez": 5, "memoria": 2}),
        ],
    ))

    nodes.append(N(
        "act1_guia_ulthar_respuesta",
        act=A, zone="Ulthar — Bendición",
        tone="calm",
        text=(
            "Los gatos asienten. El mayor te toca la frente con una pata.\n\n"
            "Sientes claridad. Como si alguien hubiera limpiado un cristal "
            "sucio detrás de tus ojos.\n\n"
            "Edyssey observa desde la puerta. \"Vaya. A mí nunca me dieron "
            "eso. 847 días. Pero bueno, qué quieres que diga.\"\n\n"
            "El gato mayor te mira una última vez. Sus ojos dicen: "
            "*cuidado con el que te guía.*"
        ),
        on_enter={"lucidez": 5, "favor": 5},
        give_item="bendicion_gato",
        set_flags=["bendicion_felina"],
        npc_trust={"edyssey": -5},
        paths=[
            P("Volver con Edyssey", "act1_guia_bifurcacion",
              style="primary", effects={"voluntad": 1}),
            P("Preguntar al gato sobre Edyssey", "act1_guia_gato_aviso",
              style="secondary", effects={"lucidez": 3}),
        ],
    ))

    nodes.append(N(
        "act1_guia_gato_aviso",
        act=A, zone="Ulthar — Aviso Felino",
        tone="tense",
        text=(
            "El gato mayor te mira fijamente. No habla con palabras pero "
            "entiendes perfectamente:\n\n"
            "*El que te guía no puede cruzar porque no quiere pagar el "
            "precio. Buscará que otro lo pague por él.*\n\n"
            "*Y la cosa que lo persigue... no lo persigue. Lo espera.*\n\n"
            "El gato se va. Edyssey te llama desde fuera: \"Eh, vienes o qué?\""
        ),
        on_enter={"lucidez": 5, "lore": 4},
        set_flags=["gato_aviso_edyssey"],
        paths=[
            P("Ir con Edyssey (sin decir nada)", "act1_guia_bifurcacion",
              style="primary", effects={"voluntad": 2}),
            P("Confrontar a Edyssey ahora", "act1_edyssey_queja",
              style="danger", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act1_payaso_primera_senal",
        act=A, zone="El Umbral — Primera Señal",
        tone="horror",
        text=(
            "Lo ves. En la pared, dibujado con algo que parece sangre seca "
            "pero huele a algodón de azúcar: 🤡\n\n"
            "No es una marca vieja. La pintura aún brilla.\n\n"
            "Edyssey lo ve y se queda blanco. \"No. No no no. Estaba aquí. "
            "Estuvo aquí hace poco. Mierda. Mierda.\"\n\n"
            "No grita. Su pánico es silencioso, contenido. Como alguien "
            "que ha tenido este miedo tantas veces que ya no le queda voz."
        ),
        on_enter={"lucidez": -3, "voluntad": -2, "corrupcion": 2},
        set_flags=["vio_al_payaso"],
        primary_npc="edyssey",
        paths=[
            P("\"Cálmate. ¿Qué hacemos?\"", "act1_edyssey_nervioso",
              style="primary", effects={"voluntad": 2}),
            P("Examinar la marca", "act1_payaso_risa",
              style="danger", effects={"corrupcion": 3, "lore": 4}),
            P("\"Vámonos de aquí YA\"", "act1_guia_bifurcacion",
              style="success", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_nervioso",
        act=A, zone="El Umbral — Pánico",
        tone="tense",
        text=(
            "Edyssey respira rápido pero controlado. Se frota la cara.\n\n"
            "\"Es que... osea, siempre es así. Cada vez que creo que puedo "
            "avanzar, aparece. Es como si supiera. Como si me vigilara.\"\n\n"
            "Te mira con ojos que calculan algo.\n\n"
            "\"Pero contigo... osea, nunca he ido con alguien. A lo mejor "
            "con dos es diferente. A lo mejor si vamos juntos, no puede "
            "pararnos a los dos. No sé.\"\n\n"
            "Hay algo en su tono que no es solo esperanza."
        ),
        on_enter={"lucidez": -1},
        primary_npc="edyssey",
        npc_trust={"edyssey": 5},
        paths=[
            P("\"Vamos juntos entonces\"", "act1_guia_bifurcacion",
              style="primary", effects={"favor": 2}),
            P("\"¿Por qué crees que conmigo es diferente?\"", "act1_edyssey_queja",
              style="secondary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_queja",
        act=A, zone="El Umbral — Quejas",
        tone="social",
        text=(
            "Edyssey se lanza a hablar como si llevara años esperando "
            "que alguien le preguntara.\n\n"
            "\"Es que mira, yo he documentado todo esto. Todo. Cada ruta, "
            "cada trampa. Nadie lo ha hecho como yo. Y la gente pasa de "
            "largo. Me ignoran. Como si no existiera. Como si mi trabajo "
            "no valiera nada.\"\n\n"
            "\"Y luego está el payaso ese. Osea, yo intento avanzar y "
            "siempre aparece. Es como si el universo no quisiera que yo "
            "progrese. Qué quieres que diga. Es injusto.\"\n\n"
            "\"Nadie me cree. Nadie quiere aprender de lo que yo sé.\""
        ),
        on_enter={"lore": 3, "lucidez": -3, "voluntad": -1},
        primary_npc="edyssey",
        paths=[
            P("Escuchar con paciencia", "act1_guia_bifurcacion",
              style="primary", effects={"favor": 3, "lucidez": -1}),
            P("\"Ya, pero hay que moverse\"", "act1_guia_bifurcacion",
              style="secondary", effects={"voluntad": 2}),
            P("\"¿Y si el problema eres tú?\"", "act1_edyssey_desconfia",
              style="danger", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act1_guia_bifurcacion",
        act=A, zone="El Umbral — Bifurcación",
        tone="discovery",
        text=(
            "El sendero se divide. A la izquierda, olor a mar y sal. "
            "A la derecha, viento frío y silencio.\n\n"
            "Edyssey señala la izquierda. \"Por ahí se llega a la Puerta "
            "de Bronce. Es la ruta... osea, la ruta oficial. Los guardianes "
            "están ahí.\"\n\n"
            "Señala la derecha. \"Por ahí hay otra puerta. De hueso. No "
            "tiene guardianes. Pero... no sé. Algo no me gusta de esa.\"\n\n"
            "\"Yo nunca he podido cruzar ninguna. Pero tú a lo mejor sí.\""
        ),
        on_enter={"lucidez": 2},
        primary_npc="edyssey",
        paths=[
            P("Izquierda — hacia la Puerta de Bronce", "act1_guia_escalera_media",
              style="primary", effects={"voluntad": 1}),
            P("Derecha — hacia la Puerta de Hueso", "act1_tension_puerta_hueso",
              style="secondary", effects={"corrupcion": 2}),
            P("\"¿Por qué no puedes cruzar?\"", "act1_edyssey_confesion",
              style="secondary", effects={"lore": 3}),
        ],
    ))

    nodes.append(N(
        "act1_guia_escalera_media",
        act=A, zone="El Descenso — Estrato Medio",
        tone="calm",
        text=(
            "Los estratos centrales están casi vacíos. Hay ecos de otros "
            "soñadores que pasaron antes — susurros que se desvanecen.\n\n"
            "Edyssey camina en silencio por primera vez. Parece pensativo.\n\n"
            "\"Sabes qué es lo peor? Que yo sé más de este sitio que "
            "cualquiera que haya cruzado. Pero la puerta no me deja. "
            "Es como si... como si necesitara algo que no tengo.\"\n\n"
            "Pausa. \"O como si necesitara a alguien.\""
        ),
        on_enter={"lucidez": 2, "lore": 1},
        primary_npc="edyssey",
        paths=[
            P("Seguir hacia la Puerta de Bronce", "act1_tension_avance",
              style="primary", effects={"voluntad": 1}),
            P("\"¿Necesitar a alguien cómo?\"", "act1_edyssey_confesion",
              style="secondary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act1_payaso_risa",
        act=A, zone="El Umbral — La Risa",
        tone="horror",
        text=(
            "Tocas la marca del payaso. Está caliente.\n\n"
            "Y entonces lo escuchas: una risa. No fuerte. No dramática. "
            "Una risa suave, como de alguien que encuentra algo gracioso "
            "de verdad. Como si TÚ fueras el chiste.\n\n"
            "Edyssey se agarra a tu brazo. \"Lo escuchaste? Lo escuchaste "
            "verdad? No me lo estoy inventando. Dime que lo escuchaste.\"\n\n"
            "La risa se apaga. El silencio que deja es peor."
        ),
        on_enter={"lucidez": -5, "voluntad": -3, "corrupcion": 4},
        set_flags=["vio_al_payaso", "escucho_risa_payaso"],
        primary_npc="edyssey",
        paths=[
            P("\"Sí, lo escuché. Vámonos.\"", "act1_guia_refugio",
              style="primary", effects={"voluntad": 2}),
            P("\"¿Qué quiere de ti?\"", "act1_edyssey_nervioso",
              style="secondary", effects={"lore": 3}),
        ],
    ))

    nodes.append(N(
        "act1_guia_refugio",
        act=A, zone="El Umbral — Refugio",
        tone="calm",
        text=(
            "Edyssey te lleva a un hueco en la pared que ha convertido en "
            "refugio. Hay marcas de conteo — cientos de rayas.\n\n"
            "\"Aquí no viene. No sé por qué. Es como... zona segura. "
            "Yo duermo aquí. Osea, si es que se puede dormir dentro de "
            "un sueño. No sé.\"\n\n"
            "Se sienta. Por primera vez parece vulnerable.\n\n"
            "\"Oye... gracias por no salir corriendo. La gente normalmente "
            "sale corriendo.\""
        ),
        on_enter={"lucidez": 4, "voluntad": 2, "memoria": 2},
        primary_npc="edyssey",
        npc_trust={"edyssey": 10},
        paths=[
            P("Descansar un momento", "act1_edyssey_confesion",
              style="primary", effects={"lucidez": 3}),
            P("\"No hay tiempo, sigamos\"", "act1_tension_avance",
              style="secondary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_edyssey_confesion",
        act=A, zone="El Umbral — Confesión",
        tone="loss",
        text=(
            "Edyssey baja la voz. Es la primera vez que no suena defensivo.\n\n"
            "\"Mira... yo antes era alguien. Afuera. Tenía... osea, tenía "
            "mi cosa. Mi contenido. La gente me veía. Algunos. No muchos "
            "pero... era algo.\"\n\n"
            "\"Y un día me dormí y aparecí aquí. Y no puedo salir. No "
            "puedo cruzar. Y cada vez que intento, el payaso aparece.\"\n\n"
            "\"Es como si este sitio me odiara. Como si yo no mereciera "
            "avanzar. Pero yo sé más que nadie de aquí. Es injusto.\"\n\n"
            "Te mira. \"Tú sí vas a poder cruzar. Lo sé. Y cuando cruces... "
            "necesito que me lleves contigo.\""
        ),
        on_enter={"lore": 5, "lucidez": -2, "memoria": 3},
        primary_npc="edyssey",
        npc_trust={"edyssey": 10},
        set_flags=["edyssey_pidio_ayuda"],
        paths=[
            P("\"Te ayudaré a cruzar\"", "act1_tension_avance",
              style="success", effects={"favor": 5}),
            P("\"No prometo nada\"", "act1_tension_avance",
              style="primary", effects={"voluntad": 3}),
            P("\"¿Por qué no puedes cruzar solo?\"", "act1_tension_edyssey_plan",
              style="secondary", effects={"lucidez": 3}),
        ],
    ))

    return nodes


def _section_c(N: Callable, P: Callable, A: int) -> List[Dict[str, Any]]:
    """Sección C: Tensión creciente, payaso acecha, pistas de traición (15 nodos)."""
    nodes = []

    nodes.append(N(
        "act1_tension_avance",
        act=A, zone="El Descenso — Avance",
        tone="tense",
        text=(
            "Siguen bajando. Edyssey camina más rápido ahora, mirando "
            "por encima del hombro cada pocos pasos.\n\n"
            "\"Estamos cerca. La puerta está a dos estratos. Pero... "
            "osea, el payaso siempre aparece cuando estoy cerca. Siempre.\"\n\n"
            "El aire se vuelve más denso. Las sombras se mueven con "
            "intención propia."
        ),
        on_enter={"voluntad": -1, "lucidez": -1},
        primary_npc="edyssey",
        paths=[
            P("Avanzar rápido", "act1_tension_payaso_cerca",
              style="primary", effects={"voluntad": 2}),
            P("Ir con cautela", "act1_tension_edyssey_plan",
              style="secondary", effects={"lucidez": 2}),
            P("\"Para. Algo no está bien.\"", "act1_tension_pista_traicion",
              style="secondary", effects={"lucidez": 3}),
        ],
    ))

    nodes.append(N(
        "act1_tension_payaso_cerca",
        act=A, zone="El Descenso — Sombra Visible",
        tone="horror",
        text=(
            "Lo ves. Al final del pasillo, una silueta alta y delgada. "
            "No se mueve. Solo está ahí, bloqueando el camino. La sonrisa "
            "pintada brilla en la oscuridad.\n\n"
            "Edyssey se congela. \"Está ahí. Está ahí otra vez. Siempre "
            "está ahí cuando estoy cerca de la puerta.\"\n\n"
            "El payaso ladea la cabeza. Como un perro curioso. "
            "Como si te estuviera evaluando."
        ),
        on_enter={"lucidez": -4, "voluntad": -3, "corrupcion": 3},
        set_flags=["vio_al_payaso"],
        primary_npc="edyssey",
        hostile_npc="payaso_umbral",
        paths=[
            P("Enfrentar al payaso", "act1_tension_payaso_cara",
              style="danger", effects={"voluntad": 5, "corrupcion": 3}),
            P("Buscar otro camino", "act1_tension_huida",
              style="primary", effects={"voluntad": 1}),
            P("Empujar a Edyssey hacia él", "act1_tension_edyssey_desesperado",
              style="danger", effects={"corrupcion": 5}),
        ],
    ))

    nodes.append(N(
        "act1_tension_edyssey_plan",
        act=A, zone="El Umbral — El Plan",
        tone="tense",
        text=(
            "Edyssey te agarra del brazo. Sus ojos brillan con algo que "
            "no es miedo — es cálculo.\n\n"
            "\"Mira, tengo un plan. He tenido mucho tiempo para pensar. "
            "La puerta necesita... osea, necesita un sacrificio. No literal. "
            "Pero alguien tiene que... quedarse atrás. Para que el otro "
            "pueda cruzar.\"\n\n"
            "\"Es que así funciona. Lo leí en los glifos. Uno cruza, "
            "otro se queda. Y yo llevo 847 días siendo el que se queda.\"\n\n"
            "Te mira fijamente. \"Esta vez no voy a ser yo.\""
        ),
        on_enter={"lucidez": 4, "voluntad": -2},
        primary_npc="edyssey",
        set_flags=["sabe_plan_edyssey"],
        paths=[
            P("\"¿Me estás diciendo que me vas a sacrificar?\"", "act1_tension_confrontar_edyssey",
              style="danger", effects={"voluntad": 5}),
            P("\"¿Y si encontramos otra forma?\"", "act1_tension_puerta_vista",
              style="primary", effects={"lucidez": 2}),
            P("Fingir que no entendiste", "act1_tension_puerta_vista",
              style="secondary", effects={"lucidez": 3}),
        ],
    ))

    nodes.append(N(
        "act1_tension_edyssey_desesperado",
        act=A, zone="El Umbral — Desesperación",
        tone="horror",
        text=(
            "Edyssey empieza a hablar más rápido. Sus manos tiemblan.\n\n"
            "\"Es que no lo entiendes. 847 días. 847. Yo merezco cruzar. "
            "Yo he hecho el trabajo. He documentado todo. He sufrido más "
            "que nadie aquí. La gente cruza sin esfuerzo y yo me quedo "
            "pudriéndome.\"\n\n"
            "\"No es justo. No es justo que tú llegues hoy y puedas "
            "cruzar y yo no. Qué quieres que diga. No es justo.\"\n\n"
            "Hay algo roto en su voz. Algo que ya no es solo frustración."
        ),
        on_enter={"lucidez": -3, "voluntad": -2, "corrupcion": 2},
        primary_npc="edyssey",
        npc_trust={"edyssey": -15},
        paths=[
            P("\"Edyssey, cálmate\"", "act1_tension_puerta_vista",
              style="primary", effects={"voluntad": 2}),
            P("\"Tienes razón, no es justo\"", "act1_tension_edyssey_ritual",
              style="secondary", effects={"favor": 3, "lucidez": -2}),
            P("Alejarte de él", "act1_tension_huida",
              style="danger", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act1_tension_payaso_cara",
        act=A, zone="El Umbral — Cara del Payaso",
        tone="horror",
        text=(
            "Te acercas al payaso. De cerca es peor. Su cara no es "
            "pintura — es su cara real. La sonrisa está cosida en su "
            "piel. Los ojos son agujeros que miran sin pupilas.\n\n"
            "No te ataca. Solo te mira. Y luego mira a Edyssey. "
            "Y la sonrisa se hace más ancha.\n\n"
            "Edyssey grita: \"NO LO MIRES A ÉL. MÍRAME A MÍ. "
            "NO DEJES QUE TE VEA.\"\n\n"
            "El payaso levanta un dedo. Señala a Edyssey. Luego a ti. "
            "Luego hace un gesto de 'elige'."
        ),
        on_enter={"lucidez": -6, "voluntad": -4, "corrupcion": 5},
        set_flags=["vio_cara_payaso"],
        primary_npc="edyssey",
        hostile_npc="payaso_umbral",
        paths=[
            P("Huir con Edyssey", "act1_tension_huida",
              style="primary", effects={"voluntad": 2}),
            P("Señalar a Edyssey", "act1_final_payaso_ataca",
              style="danger", effects={"corrupcion": 8}),
            P("Quedarte inmóvil", "act1_tension_decision",
              style="secondary", effects={"lucidez": -3}),
        ],
    ))

    nodes.append(N(
        "act1_tension_huida",
        act=A, zone="El Umbral — Huida",
        tone="tense",
        text=(
            "Corres. Edyssey corre detrás de ti. El payaso no los "
            "persigue — solo se queda ahí, sonriendo, como si supiera "
            "que no tienen a dónde ir.\n\n"
            "\"Siempre es así\" jadea Edyssey. \"Nunca persigue. Solo "
            "bloquea. Solo espera. Es que... es como si tuviera todo "
            "el tiempo del mundo.\"\n\n"
            "Llegan a otro pasillo. La Puerta de Bronce se ve a lo lejos."
        ),
        on_enter={"voluntad": 2, "lucidez": 1},
        primary_npc="edyssey",
        paths=[
            P("Ir directo a la puerta", "act1_tension_puerta_vista",
              style="primary", effects={"voluntad": 2}),
            P("\"Necesitamos un plan\"", "act1_tension_edyssey_ritual",
              style="secondary", effects={"lucidez": 2}),
            P("Buscar la Puerta de Hueso", "act1_tension_puerta_hueso",
              style="secondary", effects={"corrupcion": 2}),
        ],
    ))

    nodes.append(N(
        "act1_tension_pista_traicion",
        act=A, zone="El Umbral — Pistas",
        tone="tense",
        text=(
            "Te detienes. Algo no encaja. Edyssey dice que no puede "
            "cruzar, pero conoce cada centímetro de este lugar. Dice "
            "que el payaso lo persigue, pero el payaso nunca lo ataca.\n\n"
            "Y las marcas en las paredes... \"Día 847: sigo sin poder "
            "cruzar\". Pero también: \"Necesito a alguien. Alguien que "
            "no sepa cómo funciona.\"\n\n"
            "Esa última marca está medio borrada. Como si no quisiera "
            "que la leyeras."
        ),
        on_enter={"lucidez": 5, "lore": 4},
        set_flags=["sospecha_edyssey"],
        paths=[
            P("Confrontar a Edyssey", "act1_tension_confrontar_edyssey",
              style="danger", effects={"voluntad": 4}),
            P("No decir nada (por ahora)", "act1_tension_puerta_vista",
              style="primary", effects={"lucidez": 3}),
            P("Buscar más marcas ocultas", "act1_tension_gato_aviso",
              style="secondary", effects={"lore": 4}),
        ],
    ))

    nodes.append(N(
        "act1_tension_gato_aviso",
        act=A, zone="El Umbral — Segundo Aviso",
        tone="tense",
        text=(
            "El gato negro aparece de nuevo. Esta vez se interpone entre "
            "tú y Edyssey. Bufa hacia él.\n\n"
            "Edyssey retrocede. \"Qué le pasa a este bicho? Es que "
            "siempre me odian. Los gatos me odian.\"\n\n"
            "El gato te mira. Entiendes sin palabras: *no le des la "
            "espalda. No le des tu nombre. No le des nada que no puedas "
            "perder.*"
        ),
        on_enter={"lucidez": 4, "favor": 3},
        set_flags=["gato_aviso_edyssey"],
        npc_trust={"edyssey": -10},
        paths=[
            P("Agradecer al gato y seguir", "act1_tension_puerta_vista",
              style="primary", effects={"lucidez": 2}),
            P("Confrontar a Edyssey", "act1_tension_confrontar_edyssey",
              style="danger", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act1_tension_puerta_vista",
        act=A, zone="El Descenso — Vista de la Puerta",
        tone="awe",
        text=(
            "La Puerta de Bronce aparece al final del pasillo. Verde "
            "por la humedad de siglos. Dos figuras la custodian — "
            "Nasht y Kaman-Thah, los sacerdotes guardianes.\n\n"
            "Edyssey se detiene. Su cara es una mezcla de esperanza "
            "y terror.\n\n"
            "\"Ahí está. Ahí está. Osea... esta vez va a ser diferente. "
            "Contigo va a ser diferente. Tiene que ser.\"\n\n"
            "Mira atrás. El pasillo está vacío. Pero no por mucho."
        ),
        on_enter={"lucidez": 2, "voluntad": 1},
        primary_npc="edyssey",
        paths=[
            P("Acercarse a la puerta", "act1_tension_decision",
              style="primary", effects={"voluntad": 2}),
            P("\"Edyssey, ¿qué no me estás contando?\"", "act1_tension_confrontar_edyssey",
              style="secondary", effects={"lucidez": 3}),
            P("Esperar a ver si el payaso aparece", "act1_tension_payaso_acorrala",
              style="danger", effects={"corrupcion": 2}),
        ],
    ))

    nodes.append(N(
        "act1_tension_confrontar_edyssey",
        act=A, zone="El Umbral — Confrontación",
        tone="tense",
        text=(
            "\"Edyssey. ¿Qué es lo que no me estás diciendo?\"\n\n"
            "Se queda quieto. Por un segundo ves algo en sus ojos — "
            "culpa, o algo parecido. Pero lo tapa rápido.\n\n"
            "\"No sé de qué hablas. Es que siempre es así. La gente "
            "desconfía de mí. Yo solo quiero ayudar. Yo solo quiero "
            "cruzar. Llevo 847 días aquí. ¿Tú crees que yo elegiría "
            "estar aquí?\"\n\n"
            "\"Qué quieres que diga. Si no me crees, vete solo. "
            "A ver cuánto duras sin mi mapa.\""
        ),
        on_enter={"voluntad": 3, "lucidez": 2},
        primary_npc="edyssey",
        npc_trust={"edyssey": -10},
        paths=[
            P("\"El gato me avisó sobre ti\"", "act1_tension_edyssey_ritual",
              style="danger", effects={"voluntad": 3},
              conditions={"has_flag": "gato_aviso_edyssey"}),
            P("\"Vale, sigamos. Pero te vigilo.\"", "act1_tension_decision",
              style="primary", effects={"lucidez": 2}),
            P("Ir solo hacia la puerta", "act1_tension_puerta_hueso",
              style="secondary", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act1_tension_edyssey_ritual",
        act=A, zone="El Umbral — El Ritual",
        tone="horror",
        text=(
            "Edyssey saca algo de su bolsillo. Un trozo de obsidiana "
            "tallada con glifos que reconoces — son los mismos de las "
            "paredes, pero invertidos.\n\n"
            "\"Mira... osea, hay una forma. Los glifos dicen que la "
            "puerta se abre si alguien ofrece su... no sé cómo decirlo. "
            "Su derecho a cruzar. Si alguien renuncia a cruzar, el otro "
            "puede pasar.\"\n\n"
            "Te mira. La máscara de víctima se cae por un segundo.\n\n"
            "\"Yo no voy a ser el que renuncia otra vez.\""
        ),
        on_enter={"lucidez": 5, "voluntad": -3, "corrupcion": 3},
        primary_npc="edyssey",
        set_flags=["sabe_ritual_edyssey", "edyssey_revelo_plan"],
        paths=[
            P("\"Así que querías sacrificarme\"", "act1_tension_decision",
              style="danger", effects={"voluntad": 5}),
            P("Arrebatarle la obsidiana", "act1_tension_decision",
              style="danger", effects={"voluntad": 3, "corrupcion": 2}),
            P("\"¿Y si el payaso es el precio?\"", "act1_tension_payaso_acorrala",
              style="secondary", effects={"lore": 5}),
        ],
    ))

    nodes.append(N(
        "act1_tension_payaso_acorrala",
        act=A, zone="El Umbral — Acorralados",
        tone="horror",
        text=(
            "El payaso aparece detrás de ustedes. Sin sonido. Sin aviso. "
            "Simplemente está ahí, bloqueando la retirada.\n\n"
            "Delante: la Puerta de Bronce.\n"
            "Detrás: el payaso.\n"
            "Al lado: Edyssey, temblando.\n\n"
            "El payaso no se mueve. Solo sonríe. Espera. Como si esto "
            "fuera exactamente lo que quería.\n\n"
            "Edyssey susurra: \"Ahora. Tiene que ser ahora. Uno de los "
            "dos cruza o ninguno sale de aquí.\""
        ),
        on_enter={"lucidez": -5, "voluntad": -4, "corrupcion": 4},
        set_flags=["vio_al_payaso", "payaso_acorrala"],
        primary_npc="edyssey",
        hostile_npc="payaso_umbral",
        paths=[
            P("Correr hacia la puerta", "act1_tension_decision",
              style="primary", effects={"voluntad": 3}),
            P("Empujar a Edyssey hacia el payaso", "act1_final_payaso_ataca",
              style="danger", effects={"corrupcion": 8}),
            P("Enfrentar al payaso juntos", "act1_tension_decision",
              style="success", effects={"voluntad": 5, "favor": 3}),
        ],
    ))

    nodes.append(N(
        "act1_tension_decision",
        act=A, zone="El Umbral — Momento de Verdad",
        tone="tense",
        text=(
            "Estás frente a la Puerta de Bronce. Los guardianes te miran "
            "con ojos que han visto mil soñadores pasar.\n\n"
            "Edyssey está a tu lado. Respira agitado. El payaso está "
            "en algún lugar detrás — puedes sentir su sonrisa.\n\n"
            "\"La puerta se abre\" dice Edyssey. \"Se abre para ti. "
            "Lo sabía. Siempre lo supe.\"\n\n"
            "Su mano se mueve hacia la obsidiana tallada.\n\n"
            "\"Solo necesito que te quedes quieto un segundo.\""
        ),
        on_enter={"lucidez": 3, "voluntad": -2},
        primary_npc="edyssey",
        paths=[
            P("Dejar que Edyssey actúe", "act1_final_traicion_ritual",
              style="danger", effects={"corrupcion": 5}),
            P("Detener a Edyssey", "act1_final_traicion_lucha",
              style="primary", effects={"voluntad": 5}),
            P("Cruzar la puerta AHORA (sin él)", "act1_final_puerta_bronce",
              style="success", effects={"voluntad": 4}),
            P("\"Crucemos juntos, a la mierda el ritual\"", "act1_final_escape_juntos",
              style="success", effects={"favor": 5, "voluntad": 3},
              conditions={"favor_min": 40}),
        ],
    ))

    nodes.append(N(
        "act1_tension_puerta_hueso",
        act=A, zone="El Descenso — Puerta de Hueso",
        tone="horror",
        text=(
            "La Puerta de Hueso está en un pasillo lateral. Tallada en "
            "hueso blanco, sin guardianes. Se abre sola cuando te acercas.\n\n"
            "Edyssey no te siguió hasta aquí. O no quiso. O no pudo.\n\n"
            "Al otro lado se ve un bosque oscuro. Los árboles tienen "
            "ojos. Pero al menos no hay payasos.\n\n"
            "Detrás de ti, muy lejos, escuchas a Edyssey: \"Eh? Adónde "
            "vas? No me dejes aquí. NO ME DEJES AQUÍ.\""
        ),
        on_enter={"corrupcion": 3, "voluntad": 2},
        set_flags=["abandono_edyssey", "payaso_suelto"],
        paths=[
            P("Cruzar al bosque (abandonar a Edyssey)", "act1_final_cruce_bosque",
              style="primary", effects={"voluntad": 3, "corrupcion": 3}),
            P("Volver por Edyssey", "act1_tension_decision",
              style="success", effects={"favor": 5}),
        ],
    ))

    return nodes


def _section_d(N: Callable, P: Callable, A: int) -> List[Dict[str, Any]]:
    """Sección D: Desenlace — 3 caminos al Acto 2 (12 nodos)."""
    nodes = []

    # ─── CAMINO 1: El payaso devora a Edyssey ────────────────────────

    nodes.append(N(
        "act1_final_payaso_ataca",
        act=A, zone="El Umbral — El Payaso Ataca",
        tone="horror",
        text=(
            "El payaso se mueve. Por primera vez en 847 días, se mueve.\n\n"
            "No hacia ti. Hacia Edyssey.\n\n"
            "Es rápido. Imposiblemente rápido. Edyssey ni siquiera tiene "
            "tiempo de gritar antes de que la cosa lo agarre por los "
            "hombros con manos que son demasiado largas.\n\n"
            "Y entonces abre la boca. La sonrisa cosida se desgarra. "
            "Debajo hay más sonrisa. Y dientes. Muchos dientes."
        ),
        on_enter={"lucidez": -8, "voluntad": -5, "corrupcion": 6},
        set_flags=["vio_al_payaso", "payaso_ataco"],
        hostile_npc="payaso_umbral",
        paths=[
            P("Intentar salvar a Edyssey", "act1_final_payaso_devora",
              style="danger", effects={"voluntad": 3, "corrupcion": 3}),
            P("Correr hacia la puerta", "act1_final_puerta_bronce",
              style="primary", effects={"voluntad": -3, "corrupcion": 4}),
            P("Quedarte paralizado", "act1_final_payaso_devora",
              style="secondary", effects={"lucidez": -5}),
        ],
    ))

    nodes.append(N(
        "act1_final_payaso_devora",
        act=A, zone="El Umbral — Devorado",
        tone="horror",
        text=(
            "El payaso devora a Edyssey.\n\n"
            "No es rápido. No es limpio. Y Edyssey habla mientras pasa. "
            "Grita las cosas que siempre dijo, como un disco rayado que "
            "se niega a parar:\n\n"
            "\"ES QUE LA GENTE NO ENTIENDE — yo llevo aquí más que "
            "nadie — NADIE ME CREE — es injusto — qué quieres que "
            "diga — 847 DÍAS — la gente es estúpida — NADIE DOCUMENTA "
            "COMO YO — osea es que — es que — es que—\"\n\n"
            "La voz se corta. El payaso mastica. Sonríe.\n\n"
            "Te mira. Asiente. Como diciendo: *ahora puedes pasar.*"
        ),
        on_enter={"lucidez": -10, "voluntad": -6, "corrupcion": 8, "memoria": -5},
        set_flags=["edyssey_muerto", "edyssey_devorado_por_payaso",
                   "trauma_edyssey", "payaso_suelto"],
        hostile_npc="payaso_umbral",
        paths=[
            P("Escuchar sus últimas palabras", "act1_final_edyssey_grita",
              style="primary", effects={"lucidez": -3}),
        ],
    ))

    nodes.append(N(
        "act1_final_edyssey_grita",
        act=A, zone="El Umbral — Últimas Palabras",
        tone="horror",
        text=(
            "Las últimas palabras de Edyssey se quedan grabadas en el "
            "aire del Umbral. Como ecos que nunca se apagarán.\n\n"
            "\"...nadie me cree... es que la gente... yo solo quería "
            "cruzar... 847 días... qué quieres que diga...\"\n\n"
            "El payaso se limpia la boca. No con las manos — con la "
            "sonrisa. La sonrisa absorbe todo.\n\n"
            "Se da la vuelta y se va. Como si hubiera terminado un "
            "trabajo. Como si esto fuera lo que siempre quiso.\n\n"
            "La Puerta de Bronce se abre sola."
        ),
        on_enter={"memoria": -8, "lucidez": -5},
        set_flags=["edyssey_muerto", "edyssey_devorado_por_payaso"],
        paths=[
            P("Cruzar la puerta en silencio", "act1_final_trauma",
              style="primary", effects={"voluntad": -3}),
        ],
    ))

    nodes.append(N(
        "act1_final_trauma",
        act=A, zone="El Umbral — Trauma",
        tone="loss",
        text=(
            "Cruzas la Puerta de Bronce. Los guardianes no te miran. "
            "Saben lo que pasó. Todos lo saben.\n\n"
            "Al otro lado hay viento salado y un horizonte que promete "
            "aventura. Pero dentro de ti hay un agujero nuevo — el "
            "recuerdo de Edyssey gritando sus quejas mientras era "
            "devorado vivo.\n\n"
            "Ese recuerdo no se irá. Nunca.\n\n"
            "Y en algún lugar del Umbral, el payaso sigue sonriendo."
        ),
        on_enter={"lucidez": -3, "memoria": -5, "corrupcion": 3},
        set_flags=["trauma_edyssey", "cruzo_bronce"],
        paths=[
            P("Avanzar hacia las Tierras del Sueño", "act1_final_cruce_yermos",
              style="primary", effects={"voluntad": 2}),
        ],
    ))

    # ─── CAMINO 2: Edyssey traiciona ─────────────────────────────────

    nodes.append(N(
        "act1_final_traicion_ritual",
        act=A, zone="El Umbral — La Traición",
        tone="horror",
        text=(
            "Edyssey levanta la obsidiana. Los glifos invertidos brillan.\n\n"
            "\"Lo siento. Osea, de verdad lo siento. Pero llevo 847 días "
            "aquí y no voy a quedarme ni uno más. Necesito tu derecho a "
            "cruzar. Es que... es la única forma.\"\n\n"
            "Sientes algo tirando de ti. Como si una parte de tu ser "
            "quisiera salir por la piel. La obsidiana absorbe.\n\n"
            "\"No te va a doler. Osea, no mucho. Solo te vas a quedar "
            "aquí. Como yo. Pero tú no llevas 847 días. Tú aguantarás.\""
        ),
        on_enter={"voluntad": -8, "lucidez": -5, "corrupcion": 6},
        set_flags=["edyssey_traiciono"],
        primary_npc="edyssey",
        paths=[
            P("Luchar contra el ritual", "act1_final_traicion_lucha",
              style="danger", effects={"voluntad": 8}),
            P("Aceptar el sacrificio", "act1_final_edyssey_cruza",
              style="secondary", effects={"memoria": -10, "corrupcion": 8}),
        ],
    ))

    nodes.append(N(
        "act1_final_traicion_lucha",
        act=A, zone="El Umbral — Lucha",
        tone="tense",
        text=(
            "Le arrancas la obsidiana de las manos. Edyssey es débil — "
            "847 días sin hacer nada más que quejarse no te hacen fuerte.\n\n"
            "\"No! NO! Es mío! Yo lo encontré! Yo me lo merezco! "
            "ES QUE SIEMPRE ES ASÍ — la gente me quita todo!\"\n\n"
            "La obsidiana está en tu mano. Pulsa con energía. Podrías "
            "usarla contra él. Podrías destruirla. Podrías simplemente "
            "irte."
        ),
        on_enter={"voluntad": 5, "lucidez": 3},
        primary_npc="edyssey",
        paths=[
            P("Usar la obsidiana contra Edyssey", "act1_final_traicion_matar",
              style="danger", effects={"corrupcion": 8, "voluntad": 3}),
            P("Destruir la obsidiana", "act1_final_puerta_bronce",
              style="primary", effects={"voluntad": 5, "lore": 3}),
            P("Dejarlo y cruzar la puerta", "act1_final_puerta_bronce",
              style="success", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act1_final_traicion_matar",
        act=A, zone="El Umbral — Muerte de Edyssey",
        tone="horror",
        text=(
            "La obsidiana toca a Edyssey. Los glifos invertidos hacen "
            "su trabajo — pero al revés. Es él quien se queda.\n\n"
            "\"No... no no no. Es que no es justo. Yo llevo 847 días. "
            "YO. No tú. Yo merezco—\"\n\n"
            "Se desvanece. No muere — se disuelve en el Umbral. Se "
            "convierte en otra marca en la pared. Otra nota que nadie "
            "leerá.\n\n"
            "La Puerta de Bronce se abre.\n\n"
            "Detrás de ti, el payaso aplaude en silencio."
        ),
        on_enter={"corrupcion": 10, "voluntad": -3, "lucidez": -4},
        set_flags=["edyssey_muerto", "mato_edyssey", "payaso_suelto"],
        paths=[
            P("Cruzar la puerta", "act1_final_cruce_yermos",
              style="primary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_final_edyssey_cruza",
        act=A, zone="El Umbral — Edyssey Cruza",
        tone="loss",
        text=(
            "Dejas que pase. La obsidiana te drena algo — no sabes qué "
            "exactamente, pero algo se va.\n\n"
            "Edyssey cruza la puerta. Por primera vez en 847 días, cruza.\n\n"
            "\"Gracias. Osea... de verdad. Gracias. No sé si te lo "
            "merecías pero... qué quieres que diga.\"\n\n"
            "Y se va. Sin mirar atrás.\n\n"
            "Tú te quedas. El payaso aparece a tu lado. Te mira. "
            "Y por primera vez, no sonríe. Parece... decepcionado."
        ),
        on_enter={"memoria": -12, "voluntad": -8, "corrupcion": 5},
        set_flags=["edyssey_cruzo", "jugador_atrapado_umbral"],
        paths=[
            P("Buscar otra salida (Puerta de Hueso)", "act1_final_cruce_bosque",
              style="primary", effects={"voluntad": 5}),
        ],
    ))

    # ─── CAMINO 3: Escapar juntos ────────────────────────────────────

    nodes.append(N(
        "act1_final_escape_juntos",
        act=A, zone="El Umbral — Escape Conjunto",
        tone="awe",
        text=(
            "Agarras a Edyssey del brazo y corres hacia la puerta.\n\n"
            "\"Qué haces?! No funciona así! Los glifos dicen que—\"\n\n"
            "\"A la mierda los glifos.\"\n\n"
            "El payaso se interpone. Pero esta vez no te detienes. "
            "Corres directo hacia él. Y cuando llegas... lo atraviesas. "
            "Como si fuera humo. Como si nunca hubiera sido real.\n\n"
            "Edyssey te mira con los ojos muy abiertos. \"Qué... cómo...\"\n\n"
            "La Puerta de Bronce se abre para los dos."
        ),
        on_enter={"voluntad": 8, "lucidez": 5, "favor": 8},
        set_flags=["edyssey_aliado", "cruzo_bronce", "payaso_derrotado_temp"],
        primary_npc="edyssey",
        npc_trust={"edyssey": 30},
        paths=[
            P("Cruzar juntos", "act1_final_cruce_yermos",
              style="success", effects={"favor": 5}),
        ],
    ))

    # ─── NODOS DE SALIDA AL ACTO 2 ──────────────────────────────────

    nodes.append(N(
        "act1_final_puerta_bronce",
        act=A, zone="El Descenso — Puerta de Bronce",
        tone="awe",
        text=(
            "La Puerta de Bronce se abre. Nasht y Kaman-Thah se inclinan.\n\n"
            "Al otro lado: viento salado, un horizonte infinito, y las "
            "Tierras del Sueño extendiéndose como una promesa.\n\n"
            "Detrás de ti, el Umbral se cierra. Lo que pasó aquí — "
            "Edyssey, el payaso, las 847 marcas — se queda atrás.\n\n"
            "Pero no se olvida."
        ),
        on_enter={"lucidez": 4, "voluntad": 3, "favor": 3},
        set_flags=["cruzo_bronce"],
        paths=[
            P("Avanzar hacia Dylath-Leen", "act1_final_cruce_yermos",
              style="primary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_final_cruce_yermos",
        act=A, zone="Transición — Hacia las Tierras del Sueño",
        tone="awe",
        text=(
            "Las Tierras del Sueño se abren ante ti. El aire huele a "
            "sal y especias. A lo lejos, las torres de Dylath-Leen "
            "brillan bajo un cielo que tiene los colores correctos.\n\n"
            "El Umbral queda atrás. Pero sus lecciones no:\n"
            "Las decisiones importan. La gente miente. Y hay cosas "
            "que sonríen en la oscuridad.\n\n"
            "Tu aventura real comienza ahora."
        ),
        on_enter={"lucidez": 5, "voluntad": 3},
        paths=[
            P("Entrar a los Yermos", "act2_hub_yermos",
              style="primary", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act1_final_cruce_bosque",
        act=A, zone="Transición — Puerta de Hueso",
        tone="tense",
        text=(
            "La Puerta de Hueso te escupe al Bosque de los Zoogs. "
            "Los árboles tienen ojos y los ojos tienen hambre.\n\n"
            "No es la entrada triunfal que esperabas. Pero estás vivo. "
            "Estás fuera del Umbral. Y el payaso se quedó atrás.\n\n"
            "En algún lugar de tu memoria, Edyssey sigue hablando. "
            "Sus quejas son un eco que tardará en apagarse."
        ),
        on_enter={"corrupcion": 3, "voluntad": 2, "lucidez": 2},
        set_flags=["cruzo_hueso"],
        paths=[
            P("Adentrarse en el bosque", "act2_bosque_zoog_entrada",
              style="primary", effects={"voluntad": 1}),
        ],
    ))

    return nodes
