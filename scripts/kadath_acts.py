"""Builders de los 5 actos + prólogo + finales del mundo Kadath.

Cada función recibe (N, P) helpers y devuelve una lista de nodos.
Convenciones:
- IDs con snake_case en inglés/español coherente: prologo_*, act1_*, act2_*, etc.
- 'tone' puede ser: calm | tense | horror | awe | discovery | loss | social
- Stats son deltas (+/-). Sin HP: no hay combate.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List


# ═════════════════════════════════════════════════════════════════════════════
# PRÓLOGO — El Despertar (1 nodo)
# ═════════════════════════════════════════════════════════════════════════════

def build_prologue(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    return [
        N(
            "prologo_despertar",
            zone="El Umbral del Sueño",
            act=1,
            is_start=True,
            tone="awe",
            text=(
                "Te despiertas donde no deberías estar. El cielo tiene tres colores "
                "al mismo tiempo y ninguno de ellos se parece a un cielo. "
                "Debajo de tus pies, una escalera de obsidiana desciende hacia una "
                "oscuridad que late como un corazón dormido.\n\n"
                "Con la certeza absurda de los sueños, lo sabes: la Desconocida "
                "Kadath está más allá, en algún lugar, y algo importante te espera "
                "allí. O peor: alguien."
            ),
            character_dialogue={
                "aris":     "ese cielo no tiene sentido. son tres colores y ninguno es real",
                "law":      "bro QUE es este cielo, tiene como 3 colores a la vez y ninguno tiene sentido",
                "haru":     "mano el cielo tiene como 3 colores a la vez y ninguno tiene sentido xd",
                "elyko":    "el cielo tiene 3 colores. ninguno es un cielo real. interesante.",
                "xoft":     "MANO QUE ES ESTE CIELO no tiene sentido pero es god",
                "xokram":   "Wow wow wow, esto no estaba en el contrato mano",
                "daraziel": "Mano ese cielo tiene tres capas de color y ninguna encaja. Es como un render roto.",
            },
            class_bonus={
                "CARTOGRAFO": "Reconoces la proporción áurea invertida. Esta escalera no desciende: se pliega sobre sí misma.",
                "CANTOR":     "El eco revela la profundidad: siete estratos, siete canciones distintas.",
                "LECTORA":    "En las paredes, glifos preliminares. Lo que viene se anuncia en símbolos.",
            },
            ability_hints={
                "ARIS":     "la escalera tiene 7 estratos distintos — la respuesta al primer acertijo es 'siete'.",
                "lectura":  "la escalera tiene 7 estratos distintos — la respuesta al primer acertijo es 'siete'.",
            },
            paths=[
                P("Descender con los ojos abiertos", "act1_glifos",
                  style="primary",
                  effects={"lucidez": +2}),
                P("Quedarte en el umbral, respirando", "act1_umbral_quedarse",
                  style="info",
                  effects={"memoria": +3, "voluntad": +2}),
                P("Lanzarte al vacío lateral", "act1_caida_libre",
                  style="warning",
                  effects={"voluntad": -5, "lore": +3}),
            ],
        ),
    ]


# ═════════════════════════════════════════════════════════════════════════════
# ACTO 1 — El Descenso (Ulthar, Puertas del Sueño)  [~30 nodos]
# ═════════════════════════════════════════════════════════════════════════════

def build_act1(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 1
    nodes: List[Dict[str, Any]] = []

    nodes.append(N(
        "act1_umbral_quedarse",
        act=A, zone="El Umbral — Momento de Respiro",
        tone="calm",
        text=(
            "Te quedas en el umbral. La escalera no te apura. Por un "
            "instante, recuerdas el sonido de tu propia respiración al "
            "despertar de otros sueños menos grandes. La memoria es un "
            "hilo fino — pero aferrarse a ella también te ata al mundo "
            "despierto, y ese mundo hoy está muy lejos."
        ),
        on_enter={"memoria": +4, "lucidez": +3, "lore": -3, "voluntad": -2},
        character_dialogue={
            "aris":     "no sé, se siente como cuando reinicias algo y no sabes si guardaste",
            "law":      "no me apura la escalera... necesito respirar un toque chicos",
            "haru":     "ntp, me quedo aquí un rato, no hay prisa de bajar a lo desconocido",
            "elyko":    "no hay prisa. la escalera no se mueve. yo tampoco.",
            "xoft":     "va, me quedo un toque. no me apura nadie ni una escalera cosmica",
            "xokram":   "Pues ya, si no hay prisa no me muevo gratis",
            "daraziel": "Está bien quedarse. A veces lo mejor es no moverse hasta que el encuadre se aclare.",
        },
        paths=[
            P("Descender ahora, con calma", "act1_glifos", style="primary",
              effects={"voluntad": +2}),
            P("Cerrar los ojos un instante más", "act1_vision_previa",
              style="info",
              effects={"lore": +3, "memoria": -2}),
        ],
    ))

    nodes.append(N(
        "act1_caida_libre",
        act=A, zone="El Umbral — Caída Libre",
        tone="horror",
        text=(
            "Te lanzas al costado. No hay suelo. Caes por una geometría que no "
            "permite caídas y, sin embargo, caes. Al fondo, alguien te mira como "
            "quien observa a un insecto entrar en un vaso de agua.\n\n"
            "Aterrizas de pie, sin entender cómo. Algo en ti se dobló."
        ),
        on_enter={"voluntad": -4, "lore": +5, "corrupcion": +3},
        character_dialogue={
            "aris":     "la geometría está rota. caí sin que hubiera un eje válido para caer",
            "law":      "NOOOOOOOO PORQUE ME TIRÉ BRO ALGO SE DOBLÓ EN MI no no no no",
            "haru":     "MANO COMO ATERRICÉ DE PIE??? algo se me dobló por dentro y no me gusta",
            "elyko":    "caida sin suelo. la geometria no permite esto pero pasa igual.",
            "xoft":     "DSAKJLDSAJKLDSA QUIEN ME MIRA DESDE ABAJO te voy a matar maldito",
            "xokram":   "Negreada histórica, caí sin que nadie me dijera el precio",
            "daraziel": "La geometría de esto no tiene sentido pero se ve increíble. Caí de pie y ni sé cómo.",
        },
        paths=[
            P("Seguir por donde caíste", "act1_glifos", style="primary"),
            P("Buscar a quien te miró", "act1_vision_previa",
              style="warning",
              effects={"corrupcion": +2, "lore": +3}),
        ],
    ))

    nodes.append(N(
        "act1_vision_previa",
        act=A, zone="El Umbral — Visión Prohibida",
        tone="awe",
        text=(
            "Cierras los ojos y ves. No es imaginación: es visión. Ves una "
            "montaña que no está en ningún mapa. Ves a siete viajeros "
            "descendiendo una escalera idéntica a la tuya. Ves que uno de "
            "ellos eres tú, y los otros también son tú, y todos están perdidos.\n\n"
            "Abres los ojos y sólo tú quedas en el umbral. Pero ahora sabes "
            "algo que no sabías."
        ),
        on_enter={"lore": +8, "memoria": -3, "corrupcion": +2},
        character_dialogue={
            "aris":     "son siete instancias del mismo proceso. esto no es visión, es un loop",
            "law":      "ESTOY TEMBLANDO bro me vi a mi mismo bajando y eran TODOS yo que mierda",
            "haru":     "vi a siete tipos bajando la misma escalera y uno era yo, que mierda xd",
            "elyko":    "son 7 versiones de ti bajando la misma escalera. eso no es bueno.",
            "xoft":     "mano estoy viendo siete versiones de mi y TODAS estan perdidas nmms",
            "xokram":   "Mano siete versiones de mi y todas perdidas, gg la inversión",
            "daraziel": "Siete versiones de ti bajando la misma escalera. El diseño es simétrico, es god.",
        },
        ability_hints={
            "ARIS":  "'siete viajeros' es la llave del acertijo del Consejo de Gatos.",
        },
        set_flags=["vio_vision_previa"],
        paths=[
            P("Descender ya; no quiero ver más", "act1_glifos", style="primary"),
            P("Guardar la visión para después", "act1_glifos",
              style="info", effects={"memoria": +2}),
        ],
    ))

    nodes.append(N(
        "act1_glifos",
        act=A, zone="El Descenso — Muro de Glifos",
        tone="discovery",
        text=(
            "El tercer estrato de la escalera está tallado con glifos que "
            "cambian de orientación cuando no los miras directamente. "
            "Hay tres grupos: uno que parece decir un número, otro que "
            "parece un nombre y otro que parece una advertencia.\n\n"
            "Puedes intentar leerlos, ignorarlos y seguir, o dejar que el "
            "gato que acabas de notar te guíe."
        ),
        on_enter={"lore": +3},
        character_dialogue={
            "aris":     "los glifos cambian de orientación cuando no los miras. es como un observer pattern",
            "law":      "mano los glifos se MUEVEN cuando no los miro directamente que chucha es esto",
            "haru":     "avr estos glifos se mueven cuando no los miras, eso no es normal mano",
            "elyko":    "los glifos cambian si no los miras directo. 3 grupos: numero, nombre, advertencia.",
            "xoft":     "osea los glifos se mueven solos?? esto es peak o es trampa",
            "xokram":   "Aver si estos glifos dicen algo que valga la pena leer",
            "daraziel": "Los glifos cambian de orientación cuando no los ves directo. Ese detalle es muy bueno.",
        },
        class_bonus={
            "LECTORA": "Los glifos son pre-cuneiformes de Leng. Puedes leerlos como si fuera tu lengua materna.",
            "CARTOGRAFO": "Los glifos dibujan un mapa: la puerta que buscas está tres estratos más abajo.",
        },
        ability_hints={
            "ARIS":   "los glifos dicen 'SIETE', 'BARZAI', 'NO MIRES ATRÁS'.",
            "lectura": "los glifos dicen 'SIETE', 'BARZAI', 'NO MIRES ATRÁS'.",
        },
        paths=[
            P("Leer los glifos en voz alta", "act1_glifos_leidos",
              style="primary",
              effects={"lore": +5, "lucidez": -3}),
            P("Ignorarlos y seguir bajando", "act1_escalera_media",
              style="info"),
            P("Seguir al gato que te observa", "act1_gato_sigue",
              style="success"),
        ],
    ))

    nodes.append(N(
        "act1_glifos_leidos",
        act=A, zone="El Descenso — Glifos Leídos",
        tone="awe",
        text=(
            "Pronuncias los glifos con la voz que te prestó el sueño. Los "
            "muros responden: un nombre, *Barzai el Sabio*, que descendió "
            "antes que tú y nunca volvió. Un número, *siete*. Y una "
            "advertencia: *no mires atrás*.\n\n"
            "El aire huele a ozono. Algo te marcó sin tocarte."
        ),
        on_enter={"lore": +6, "memoria": -2},
        set_flags=["leyo_glifos", "conoce_barzai"],
        give_item="fragmento_glifo",
        character_dialogue={
            "aris":     "barzai el sabio. siete. no mires atrás. ok, bastante conclusivo",
            "law":      "siete... y dice que no mire atrás. bro porque siempre me pasan estas cosas a mi",
            "haru":     "Barzai el Sabio bajó y nunca volvió, y yo aquí leyendo su nombre como pendejo",
            "elyko":    "Barzai el Sabio. siete. no mires atras. informacion clara al menos.",
            "xoft":     "Barzai el Sabio nunca volvio y yo voy igual. BUSQUENLO TODO ESTA AHI",
            "xokram":   "Barzai nunca volvió eh, pues ya sabemos que no es gratis",
            "daraziel": "Barzai, siete, no mires atrás. Es como un sistema de señalética pero para locos.",
        },
        paths=[
            P("Seguir bajando, como dijeron los glifos", "act1_escalera_media",
              style="primary"),
            P("Mirar atrás porque te dijeron que no", "act1_mirada_atras",
              style="warning",
              effects={"corrupcion": +4, "lore": +3}),
        ],
    ))

    nodes.append(N(
        "act1_mirada_atras",
        act=A, zone="El Descenso — Mirada Atrás",
        tone="horror",
        text=(
            "Miras atrás. Arriba ya no hay umbral. Hay una figura alta, de "
            "brazos demasiado largos, que te saluda con una educación que "
            "te da escalofríos. No dice nada. Sólo te saluda.\n\n"
            "Sabes, sin saber cómo, que esa figura te recordará."
        ),
        on_enter={"corrupcion": +6, "lucidez": -5, "memoria": -3},
        set_flags=["nyarlathotep_te_vio"],
        character_dialogue={
            "aris":     "no debí mirar. la figura de arriba me saludó y eso es peor que si atacara",
            "law":      "NO JODAAAAAA la figura me saludó y me dió escalofríos SAQUENME DE AQUI",
            "haru":     "mano hay una cosa con brazos largos saludándome y me dio escalofríos de verdad",
            "elyko":    "la figura de arriba te saluda. educada. eso es peor que si te gritara.",
            "xoft":     "NO MANO ESA COSA ME SALUDO con educacion eso es peor que si me gritara",
            "xokram":   "Mano esa cosa me saludó como vendedor de seguros, no me gusta",
            "daraziel": "La figura tiene las proporciones mal a propósito. Brazos largos, todo estilizado.",
        },
        paths=[
            P("Correr hacia abajo sin mirar más", "act1_escalera_media",
              style="primary",
              effects={"voluntad": +3}),
        ],
    ))

    nodes.append(N(
        "act1_gato_sigue",
        act=A, zone="El Descenso — El Gato de Ulthar",
        tone="calm",
        text=(
            "El gato te mira como si supiera cosas sobre ti. Avanza tres "
            "pasos, se detiene, te espera. En Ulthar nadie mata gatos, "
            "recuerdas haber leído alguna vez en algún libro que no existía "
            "todavía cuando lo leíste.\n\n"
            "El gato te guía por una ruta lateral que no habías visto. "
            "Aceptar su guía significa no aprender solo; los glifos se "
            "quedan sin leer."
        ),
        on_enter={"lucidez": +5, "favor": +4, "voluntad": -3, "lore": -2},
        set_flags=["gato_ulthar_aliado"],
        primary_npc="gato_ulthar",
        is_ally_npc=True,
        character_dialogue={
            "aris":     "el gato sabe más que yo de este lugar. la verdad no me sorprende",
            "law":      "el gato me mira como si supiera cosas de mi vida bro es muy lindo pero me da miedo",
            "haru":     "el gato me mira como si supiera cosas de mi que yo no se, confío en él xd",
            "elyko":    "el gato sabe mas que tu. en Ulthar nadie mata gatos. dato relevante.",
            "xoft":     "el gato sabe mas que yo y eso me da rabia pero lo sigo va",
            "xokram":   "Alchilito si, el gato sabe más que yo de rutas aquí",
            "daraziel": "El gato sabe más que nosotros. Se nota en cómo se mueve, tiene el ritmo perfecto.",
        },
        npc_trust={"gato_ulthar": +20},
        paths=[
            P("Seguir al gato por la ruta lateral", "act1_ulthar_sendero",
              style="success"),
            P("Darle las gracias y seguir solo", "act1_escalera_media",
              style="info", effects={"favor": -2}),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_sendero",
        act=A, zone="El Descenso — Sendero Felino",
        tone="discovery",
        text=(
            "El gato te lleva por un pasillo que no existía antes. Hay "
            "velas que arden sin fuego. El aire sabe a leche tibia. Al final, "
            "una puerta baja, de madera gastada, se abre sola."
        ),
        on_enter={"lucidez": +3, "favor": +3},
        give_item="bigote_gato_ulthar",
        character_dialogue={
            "aris":     "velas sin fuego. puerta que se abre sola. todo automatizado",
            "law":      "velas sin fuego y huele a leche tibia... esto es demasiado tranquilo me da miedito",
            "haru":     "velas sin fuego y el aire sabe a leche tibia, es raro pero no me quejo",
            "elyko":    "velas sin fuego. aire a leche tibia. el gato te trajo por la ruta correcta.",
            "xoft":     "velas sin fuego y olor a leche tibia?? esto es demasiado god mano",
            "xokram":   "Velas sin fuego y leche tibia, quien sabe pije esto huele a trampa",
            "daraziel": "Velas sin fuego, puerta de madera gastada. Todo el pasillo tiene una paleta muy cálida.",
        },
        paths=[
            P("Cruzar la puerta baja", "act1_ulthar_gato_consejo",
              style="primary"),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_gato_consejo",
        act=A, zone="Ulthar — Consejo de Gatos",
        tone="awe",
        text=(
            "La puerta te deja en un salón redondo donde siete gatos te "
            "están esperando como si supieran la hora exacta en que ibas "
            "a llegar. El más viejo habla con la voz de alguien que ya "
            "soñó muchas veces:\n\n"
            "— *¿Cuántos viajeros descienden, en realidad?*\n\n"
            "La pregunta tiene respuesta. La respuesta cuesta."
        ),
        on_enter={"lore": +3},
        primary_npc="consejo_gatos",
        is_ally_npc=True,
        ability_hints={
            "ARIS": "la respuesta es 'siete' — siete viajeros, siete estratos.",
        },
        paths=[
            P("Responder «siete»", "act1_ulthar_respuesta_correcta",
              style="success",
              conditions={"lore_min": 40, "lacks_flag": "respondi_consejo_gatos"},
              effects={"favor": +8, "lore": +5},
              set_flags=["respondi_consejo_gatos"]),
            P("Responder «uno; yo»", "act1_ulthar_respuesta_uno",
              style="info",
              conditions={"lacks_flag": "respondi_consejo_gatos"},
              effects={"memoria": +6, "favor": -3},
              set_flags=["respondi_consejo_gatos"]),
            P("No responder; escuchar", "act1_ulthar_respuesta_silencio",
              style="secondary",
              conditions={"lacks_flag": "respondi_consejo_gatos"},
              effects={"lucidez": +3, "lore": +2},
              set_flags=["respondi_consejo_gatos"]),
            P("Responder con la visión", "act1_ulthar_respuesta_correcta",
              style="success",
              conditions={"has_flag": "vio_vision_previa",
                          "lacks_flag": "respondi_consejo_gatos"},
              effects={"favor": +10, "lore": +6},
              set_flags=["respondi_consejo_gatos"],
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_respuesta_correcta",
        act=A, zone="Ulthar — Bendición Felina",
        tone="awe",
        text=(
            "Los gatos asienten como si les hubieras devuelto algo que "
            "habían perdido. El más viejo te da un bigote plateado y te "
            "dice, sin mover los labios:\n\n"
            "— *Los Dioses Blandos te escuchan ahora. No los llames por "
            "aburrimiento.*"
        ),
        on_enter={"favor": +12, "lucidez": +4},
        give_item="bendicion_gato",
        set_flags=["bendicion_ulthar"],
        npc_trust={"consejo_gatos": +30, "gato_ulthar": +15},
        character_dialogue={
            "aris":     "no los llames por aburrimiento. bueno, anotado",
            "law":      "MANO EL GATO ME HABLÓ SIN MOVER LOS LABIOS estoy llorando es hermoso",
            "haru":     "mano un gato me dio un bigote plateado y me dijo que no llame dioses por aburrimiento xddd",
            "elyko":    "los Dioses Blandos te escuchan. no los llames por aburrimiento. noted.",
            "xoft":     "DIOSSSSSS los gatos me dieron su bendicion. no la merezco pero la tomo",
            "xokram":   "No los llames por aburrimiento dice, la verdad suena a buen consejo",
            "daraziel": "El bigote plateado es un detalle hermoso. Obviamente los gatos saben lo que hacen.",
        },
        paths=[
            P("Agradecer y seguir bajando", "act1_escalera_media",
              style="primary"),
            P("Pedir una última pista", "act1_ulthar_pista",
              style="info",
              effects={"favor": -2, "lore": +5}),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_respuesta_uno",
        act=A, zone="Ulthar — Respuesta Solitaria",
        tone="tense",
        text=(
            "Los gatos se miran entre ellos. Uno bosteza. Otro se va por "
            "una puerta que no existía hace un momento. El viejo sonríe "
            "con una paciencia cansada:\n\n"
            "— *No es mala respuesta. Es la respuesta de un soñador joven. "
            "Todavía crees que eres uno.*"
        ),
        on_enter={"lore": +4, "memoria": +4, "favor": -2},
        set_flags=["respuesta_solitaria"],
        paths=[
            P("Aceptar el reproche y seguir", "act1_escalera_media",
              style="primary"),
            P("Argumentar", "act1_ulthar_argumento",
              style="warning",
              effects={"voluntad": +4, "favor": -4}),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_respuesta_silencio",
        act=A, zone="Ulthar — Silencio Paciente",
        tone="calm",
        text=(
            "No dices nada. Los gatos tampoco. El silencio se alarga hasta "
            "volverse música. Aprendes algo que no podrías decir en voz "
            "alta — y los gatos, que esperaban respuesta, bajan los ojos."
        ),
        on_enter={"lucidez": +5, "memoria": +3, "lore": +3, "favor": -4},
        character_dialogue={
            "aris":     "a veces no decir nada es la respuesta correcta. creo que entendieron",
            "law":      "no dije nada y los gatos tampoco... fue como música bro voy a llorar",
            "haru":     "no dije nada y los gatos tampoco, el silencio se volvió como música, está peak",
            "elyko":    "el silencio fue la respuesta correcta. los gatos lo saben.",
            "xoft":     "no dije nada y los gatos bajaron los ojos. gg me siento horrible",
            "xokram":   "Pues si no hay nada que decir no digo nada, es lo más seguro",
            "daraziel": "A veces el silencio comunica más que cualquier cosa. Eso está muy bien hecho.",
        },
        paths=[
            P("Seguir bajando", "act1_escalera_media", style="primary"),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_argumento",
        act=A, zone="Ulthar — Argumento",
        tone="tense",
        text=(
            "Discutes con los gatos. Los gatos discuten contigo. Ninguno "
            "cede. Al final, el viejo te concede: *quizás tengas razón. "
            "Quizás sólo seas tú. Pero recuerda: los otros seis también "
            "lo creen.*"
        ),
        on_enter={"voluntad": +3, "lore": +3},
        paths=[
            P("Seguir bajando, molesto", "act1_escalera_media", style="primary"),
        ],
    ))

    nodes.append(N(
        "act1_ulthar_pista",
        act=A, zone="Ulthar — Pista del Viejo",
        tone="discovery",
        text=(
            "El viejo te susurra: *en Dylath-Leen, cuida a los que llevan "
            "máscara. Los Hombres de Leng venden esclavos disfrazados de "
            "mercaderes.* La información viene con un peso: los gatos "
            "no dan consejos gratis, aunque no cobren en monedas."
        ),
        on_enter={"lore": +5, "favor": -4, "memoria": -2},
        set_flags=["sabe_leng_mercaderes"],
        paths=[
            P("Agradecer y seguir", "act1_escalera_media", style="primary"),
        ],
    ))

    nodes.append(N(
        "act1_escalera_media",
        act=A, zone="El Descenso — Estrato Medio",
        tone="calm",
        text=(
            "Los estratos centrales de la escalera están casi vacíos. "
            "Hay ecos aquí: algunos son tuyos, otros no. A la mitad, la "
            "escalera se bifurca. A la izquierda, un olor a mar salado. "
            "A la derecha, un rumor de viento frío."
        ),
        on_enter={"lucidez": +2},
        character_dialogue={
            "aris":     "los ecos que no son míos me preocupan más que los que sí",
            "law":      "huelo mar salado de un lado y viento frío del otro... no sé cual me da más miedo",
            "haru":     "a la izquierda huele a mar, a la derecha viento frío, las dos dan cosa",
            "elyko":    "bifurcacion. izquierda: mar salado. derecha: viento frio. ambas son validas.",
            "xoft":     "los ecos que no son mios me dan ñañaras pero sigo bajando va",
            "xokram":   "Mar salado o viento frío, ninguno suena a buen negocio la verdad",
            "daraziel": "Los ecos aquí tienen profundidad. Mar a la izquierda, viento a la derecha. Buen contraste.",
        },
        paths=[
            P("Bajar por la izquierda (olor a mar)", "act1_puerta_bronce",
              style="primary"),
            P("Bajar por la derecha (viento frío)", "act1_puerta_hueso",
              style="info"),
        ],
    ))

    nodes.append(N(
        "act1_puerta_bronce",
        act=A, zone="El Descenso — Puerta de Bronce",
        tone="discovery",
        text=(
            "Una puerta de bronce verde, gastada por siglos de humedad. "
            "Dos guardianes la custodian: *Nasht* y *Kaman-Thah*, "
            "sacerdotes del Umbral. Te miran sin hostilidad. Te piden un "
            "nombre o una ofrenda, a cambio del paso."
        ),
        on_enter={"lore": +3},
        primary_npc="nasht_kaman_thah",
        is_ally_npc=True,
        ability_hints={
            "ARIS": "los sacerdotes aceptan 'Barzai' como nombre; es el suyo.",
        },
        paths=[
            P("Decir «Barzai» (si lo conoces)", "act1_puerta_bronce_pasar",
              style="success",
              conditions={"has_flag": "conoce_barzai"},
              effects={"favor": +5, "lore": +3},
              show_locked=True),
            P("Ofrecer el fragmento de glifo", "act1_puerta_bronce_pasar",
              style="success",
              conditions={"has_item": "fragmento_glifo"},
              effects={"favor": +4},
              show_locked=True),
            P("Ofrecer la bendición del gato", "act1_puerta_bronce_pasar",
              style="success",
              conditions={"has_item": "bendicion_gato"},
              effects={"favor": +6, "lore": +3},
              show_locked=True),
            P("Dar tu propio nombre despierto", "act1_puerta_bronce_nombre",
              style="warning",
              effects={"memoria": -8, "favor": +3}),
            P("Rechazar y buscar otra puerta", "act1_puerta_hueso",
              style="secondary"),
        ],
    ))

    nodes.append(N(
        "act1_puerta_bronce_pasar",
        act=A, zone="El Descenso — Cruce del Umbral",
        tone="awe",
        text=(
            "Nasht y Kaman-Thah se inclinan. La puerta se abre hacia un "
            "viento salado. Al otro lado, lejísimos, se ven los techos "
            "de cobre de **Dylath-Leen**, y más allá, el mar negro que "
            "lleva a los Yermos Soñados."
        ),
        on_enter={"favor": +6, "lucidez": +4, "lore": +4},
        set_flags=["cruzo_bronce"],
        npc_trust={"nasht_kaman_thah": +25},
        character_dialogue={
            "aris":     "se ven los techos de cobre desde acá. es enorme",
            "law":      "A LA MIERDA se ven los techos de cobre y el mar negro ES GOOOOOOOOOOD",
            "haru":     "se ven los techos de cobre de una ciudad entera desde aquí, es increíble mano",
            "elyko":    "Dylath-Leen al otro lado. techos de cobre. mar negro mas alla.",
            "xoft":     "OUUUUU YEAAAAAA se ven los techos de cobre mano esto es PEAK",
            "xokram":   "Dylath-Leen pije, al menos hay comercio ahí, algo es algo",
            "daraziel": "Los techos de cobre de Dylath-Leen se ven desde acá. La composición es increíble.",
        },
        paths=[
            P("Avanzar hacia Dylath-Leen", "act2_hub_yermos", style="primary"),
        ],
    ))

    nodes.append(N(
        "act1_puerta_bronce_nombre",
        act=A, zone="El Descenso — Nombre Entregado",
        tone="tense",
        text=(
            "Das tu nombre despierto. Los sacerdotes lo reciben con cuidado, "
            "como si fuera una moneda que pesa demasiado. La puerta se abre. "
            "Pero al otro lado, algo de ti se queda. Cuando intentes "
            "recordar tu nombre más tarde, costará."
        ),
        on_enter={"memoria": -10, "favor": +5},
        set_flags=["cruzo_bronce", "dio_nombre_a_umbral"],
        paths=[
            P("Cruzar hacia Dylath-Leen", "act2_hub_yermos", style="primary"),
        ],
    ))

    nodes.append(N(
        "act1_puerta_hueso",
        act=A, zone="El Descenso — Puerta de Hueso",
        tone="tense",
        text=(
            "Una puerta tallada en hueso blanco. No tiene guardianes. "
            "Cuando te acercas, se abre sola. Al otro lado, un bosque "
            "de árboles demasiado altos para ser árboles. Hueles a moho. "
            "Y algo te observa desde las copas."
        ),
        on_enter={"corrupcion": +3, "lore": +3},
        character_dialogue={
            "aris":     "una puerta de hueso sin guardianes. eso no es buena señal",
            "law":      "una puerta de HUESO bro y se abrió sola. algo me mira desde arriba no quiero entrar",
            "haru":     "una puerta de hueso se abrió sola y hay árboles demasiado altos, huele a moho",
            "elyko":    "puerta de hueso sin guardianes. se abre sola. eso nunca es gratis.",
            "xoft":     "una puerta de hueso sin guardianes?? trampa seguro pero entro igual",
            "xokram":   "Mano una puerta de hueso sin guardia es peor que con guardia",
            "daraziel": "Puerta tallada en hueso blanco sin guardianes. El minimalismo le da más peso visual.",
        },
        paths=[
            P("Cruzar y entrar al bosque", "act2_bosque_zoog_entrada",
              style="warning"),
            P("Volver atrás al estrato medio", "act1_escalera_media",
              style="secondary"),
        ],
    ))

    return nodes


# ═════════════════════════════════════════════════════════════════════════════
# Placeholders (los demás actos se llenan en siguientes pasos)
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# ACTO 2 — Los Yermos Soñados (Dylath-Leen, Zoogs, Leng)  [~30 nodos]
# ═════════════════════════════════════════════════════════════════════════════

def build_act2(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 2
    nodes: List[Dict[str, Any]] = []

    nodes.append(N(
        "act2_hub_yermos",
        act=A, zone="Los Yermos — Encrucijada",
        tone="discovery",
        text=(
            "Los Yermos Soñados son una llanura interminable donde cada "
            "huella se convierte en un camino. Al norte, las torres de "
            "cobre de **Dylath-Leen**. Al este, el **Bosque de los Zoogs**, "
            "y más allá, **Sarkomand** en ruinas. Al sur, **Celephaïs**, "
            "que brilla como un sueño dentro del sueño.\n\n"
            "En una piedra del camino hay un hombrecillo que te saluda "
            "como si te conociera desde siempre."
        ),
        on_enter={},
        primary_npc="gab_el_primero",
        character_dialogue={
            "aris":     "cada huella se convierte en camino. es procedural esto",
            "law":      "chicos hay caminos para todos lados y cada huella se hace camino QUE HAGO",
            "haru":     "mano esto es enorme, cada huella se vuelve un camino, no se pa donde ir xd",
            "elyko":    "llanura donde cada huella se vuelve camino. 4 rutas visibles minimo.",
            "xoft":     "mano hay caminos para todos lados. yo voy al que huela a peligro",
            "xokram":   "Cuatro caminos y ninguno dice cuál te sale más barato, gg",
            "daraziel": "Cada huella se vuelve camino. Es como un mapa que se dibuja solo conforme avanzas.",
        },
        paths=[
            P("Dylath-Leen (norte) — puerto y mercaderes", "act2_dylath_entrada",
              style="primary"),
            P("Bosque de los Zoogs (este)", "act2_bosque_zoog_entrada",
              style="info"),
            P("Celephaïs (sur) — la ciudad dorada", "act2_celephais_puertas",
              style="success"),
            P("Hablar con el hombrecillo de la piedra", "act2_gab_encuentro",
              style="secondary",
              conditions={"lacks_flag": "hablo_con_gab"}),
        ],
    ))

    # NPC del servidor: Gab el Primero (usuario real gab#...)
    nodes.append(N(
        "act2_gab_encuentro",
        act=A, zone="Los Yermos — Gab el Primero",
        tone="social",
        text=(
            "— *MANO YO LLEGUÉ PRIMERO A ESTE LUGAR XDDDDDDDDD* — el "
            "hombrecillo te habla antes de que te hayas sentado. Se "
            "llama **Gab**, dice, y jura que llevaba en los Yermos "
            "«desde antes que existieran los Yermos». Sabe atajos. "
            "Y sabe rencores también."
        ),
        primary_npc="gab_el_primero",
        is_ally_npc=True,
        set_flags=["hablo_con_gab"],
        paths=[
            P("Darle la razón (te muestra un atajo)", "act2_gab_atajo",
              style="success",
              effects={"favor": -2, "lore": +4, "memoria": -3}),
            P("Discutir «yo llegué primero»", "act2_gab_duelo",
              style="warning",
              effects={"voluntad": +4, "favor": -5}),
            P("Ignorarlo y seguir", "act2_hub_yermos",
              style="secondary",
              effects={"favor": -3}),
        ],
    ))

    nodes.append(N(
        "act2_gab_atajo",
        act=A, zone="Los Yermos — Atajo de Gab",
        tone="discovery",
        text=(
            "Gab te guía por un sendero lateral que sólo él ve. Te da "
            "una **piedrita de Gab** y un resentimiento incorporado que "
            "durará más que el atajo."
        ),
        give_item="piedrita_gab",
        set_flags=["gab_debe_favor"],
        npc_trust={"gab_el_primero": +20},
        paths=[
            P("Continuar a Celephaïs por el atajo", "act2_celephais_puertas",
              style="primary"),
            P("Volver al hub", "act2_hub_yermos", style="secondary"),
        ],
    ))

    nodes.append(N(
        "act2_gab_duelo",
        act=A, zone="Los Yermos — Duelo de Primeros",
        tone="tense",
        text=(
            "Le discutes a Gab quién llegó primero. Gab llora, se ríe, "
            "vuelve a llorar, se ríe otra vez — todo en 30 segundos. "
            "Cuando se cansa, te escupe en el zapato y se va. Te deja "
            "un **papel arrugado** con una fecha que no podría ser."
        ),
        give_item="papel_de_gab",
        npc_trust={"gab_el_primero": -25},
        set_flags=["gab_enemigo"],
        paths=[
            P("Volver al hub", "act2_hub_yermos", style="primary"),
        ],
    ))

    # ── Dylath-Leen ────────────────────────────────────────────────────────
    nodes.append(N(
        "act2_dylath_entrada",
        act=A, zone="Dylath-Leen — Puertas de la Ciudad",
        tone="discovery",
        text=(
            "Las torres de cobre de Dylath-Leen huelen a sal y a humo. En "
            "la entrada, mercaderes y marineros se gritan en tres idiomas "
            "a la vez. Uno de ellos — de piel grisácea y turbante rojo — "
            "te mira con una sonrisa demasiado fija. Un gato al lado "
            "escupe al verlo."
        ),
        on_enter={"lore": +3},
        primary_npc="mercader_leng",
        character_dialogue={
            "aris":     "el de turbante rojo sonríe demasiado fijo. no me gusta",
            "law":      "huele a sal y humo y un tipo gris me sonríe demasiado fijo bro me da miedo",
            "haru":     "un tipo gris con turbante me sonríe demasiado y un gato le escupe, confío en el gato",
            "elyko":    "el mercader gris te mira fijo. el gato escupe al verlo. confia en el gato.",
            "xoft":     "ese mercader gris me mira raro. le voy a partir la cara si se acerca",
            "xokram":   "Mercaderes gritando en tres idiomas, aquí hay negocio seguro mano",
            "daraziel": "Las torres de cobre con ese olor a sal. La paleta de colores de esta ciudad es muy god.",
        },
        ability_hints={
            "ARIS": "el mercader es un Hombre de Leng disfrazado. sus pies no tocan el suelo.",
            "XOFT": "provócalo para que deje caer su acento de Leng.",
        },
        paths=[
            P("Aceptar conversar con el mercader", "act2_dylath_mercader",
              style="warning",
              conditions={"lacks_flag": "hablo_con_mercader_leng"}),
            P("Ir directo al puerto sin hacerle caso", "act2_dylath_puerto",
              style="primary"),
            P("Seguir al gato que escupió", "act2_dylath_gato_advertencia",
              style="success",
              conditions={"npc_trust": {"gato_ulthar": 10}},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act2_dylath_mercader",
        act=A, zone="Dylath-Leen — El Mercader Sospechoso",
        tone="tense",
        text=(
            "El mercader te ofrece rubíes de Leng a precio imposible. Te "
            "invita a subir a su barco negro y 'probar el vino de la luna'. "
            "Su aliento huele a algo que no es aliento."
        ),
        on_enter={"lucidez": -3},
        primary_npc="mercader_leng",
        set_flags=["hablo_con_mercader_leng"],
        character_dialogue={
            "aris":     "rubíes a precio imposible y vino gratis. la estafa es obvia",
            "law":      "NO bro su aliento huele a algo que NO es aliento ALEJATE DE MI",
            "haru":     "rubíes a precio imposible y me invita a su barco negro, esto apesta a trampa mano",
            "elyko":    "rubies de Leng a precio imposible. si es demasiado bueno no es bueno.",
            "xoft":     "rubies de Leng a precio imposible?? VENDEHUMO te huele el aliento a muerte bro",
            "xokram":   "Rubíes a precio imposible es estafa mano, shit ain't worth it",
            "daraziel": "Ese mercader tiene la sonrisa demasiado fija. Se nota que algo no encaja en su diseño.",
        },
        ability_hints={
            "XOFT": "si lo provocas, su máscara de piel cae: es un Hombre de Leng.",
            "provocacion": "si lo provocas, su máscara de piel cae: es un Hombre de Leng.",
        },
        paths=[
            P("Aceptar el vino", "act2_dylath_trampa_leng",
              style="danger",
              effects={"corrupcion": +6, "memoria": -6}),
            P("Rechazar con respeto", "act2_dylath_puerto",
              style="primary",
              effects={"voluntad": +4}),
            P("Comprar un rubí (regateando)", "act2_dylath_compra_rubi",
              style="info",
              conditions={"has_item": "moneda_onirica"},
              effects={"lore": +3, "corrupcion": +2},
              show_locked=True),
            P("Comprar un rubí (con fragmento_glifo)", "act2_dylath_compra_rubi",
              style="info",
              conditions={"has_item": "fragmento_glifo"},
              effects={"lore": +5, "corrupcion": +3},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act2_dylath_trampa_leng",
        act=A, zone="Dylath-Leen — Vino de Luna",
        tone="horror",
        text=(
            "El vino sabe a aluminio. El barco zarpa sin que hayas dicho "
            "que sí. Cuando despiertas, estás encadenado en la bodega. "
            "La luna entra por una rendija. Afuera, voces en un idioma "
            "que no debería existir discuten tu precio.\n\n"
            "Tendrás que escapar."
        ),
        on_enter={"voluntad": -6, "memoria": -4, "corrupcion": +5},
        set_flags=["capturado_por_leng"],
        character_dialogue={
            "aris":     "sabe a aluminio. el barco zarpó sin consentimiento. esto está muy mal",
            "law":      "NOOOOOOOOOO estoy encadenado y discuten mi precio SAQUENME DE AQUI LPTM",
            "haru":     "PUTAMADRE me encadenaron en la bodega, el vino sabía a aluminio, gg mi vida",
            "elyko":    "el barco zarpo sin tu permiso. estas encadenado. el vino sabia a aluminio.",
            "xoft":     "LKDSAJKLDSAJK ME ENCADENARON me drogaron con vino de aluminio mano",
            "xokram":   "Me vendieron y ni firmé nada, negreada histórica la verdad",
            "daraziel": "El vino sabe a aluminio. Mano esto se puso feo muy rápido, hay que salir de aquí.",
        },
        paths=[
            P("Romper la cadena con voluntad pura", "act2_dylath_escape_voluntad",
              style="warning",
              conditions={"voluntad_min": 45},
              effects={"voluntad": +5}),
            P("Esperar, escuchar, aprender", "act2_dylath_escape_astucia",
              style="primary",
              effects={"lore": +6, "corrupcion": +3}),
            P("Aceptar que te vendan", "act2_dylath_esclavitud",
              style="danger",
              effects={"memoria": -10, "corrupcion": +8}),
        ],
    ))

    nodes.append(N(
        "act2_dylath_escape_voluntad",
        act=A, zone="Dylath-Leen — Escape por Fuerza",
        tone="tense",
        text=(
            "Rompes la cadena. El sonido despierta a dos Hombres de Leng. "
            "Saltas por la rendija al mar negro. Nadas hasta una boya. "
            "Te suben a un bote pesquero de mañana. Estás vivo, y más "
            "enojado que antes."
        ),
        on_enter={"voluntad": +8, "corrupcion": -2},
        set_flags=["escapo_leng"],
        clear_flags=["capturado_por_leng"],
        paths=[
            P("Volver al puerto", "act2_dylath_puerto", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_escape_astucia",
        act=A, zone="Dylath-Leen — Escape por Astucia",
        tone="discovery",
        text=(
            "Escuchas. Memorizas. Aprendes el nombre del barco, el nombre "
            "del capitán, el precio en el que te tasaron. Cuando atracan "
            "en un puerto secundario, te escabulles con información que "
            "cambiará lo que sigue — y con algo de Leng pegado a la piel "
            "que no se va a lavar."
        ),
        on_enter={"lore": +6, "memoria": -4, "corrupcion": +5},
        set_flags=["escapo_leng", "sabe_precio_leng"],
        clear_flags=["capturado_por_leng"],
        give_item="nota_precio_leng",
        paths=[
            P("Volver al puerto", "act2_dylath_puerto", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_esclavitud",
        act=A, zone="Dylath-Leen — Venta al Mar",
        tone="horror",
        text=(
            "Dejas que te vendan. Los nuevos dueños tienen ojos de "
            "pescado. Te llevan al norte, a un puerto que no tiene "
            "nombre. Allí te dejan. No mueres. Pero nada de lo que "
            "hagas después te pertenecerá del todo."
        ),
        on_enter={"memoria": -15, "corrupcion": +10, "favor": -8},
        set_flags=["fue_esclavo_leng"],
        clear_flags=["capturado_por_leng"],
        paths=[
            P("Despertar, sin dueño, en un puerto sin nombre", "act2_sarkomand_ruinas",
              style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_compra_rubi",
        act=A, zone="Dylath-Leen — Rubí de Leng",
        tone="tense",
        text=(
            "El mercader te entrega el rubí. Pesa demasiado para su "
            "tamaño. Brilla con una luz interna que no proviene del "
            "sol. Lo guardas. Sabes que vas a tener que pagar por "
            "esto más tarde, de un modo u otro."
        ),
        on_enter={"corrupcion": +3, "lore": +4},
        give_item="rubi_leng",
        consume_item="moneda_onirica",
        paths=[
            P("Ir al puerto", "act2_dylath_puerto", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_gato_advertencia",
        act=A, zone="Dylath-Leen — Advertencia Felina",
        tone="discovery",
        text=(
            "El gato te guía por un callejón hasta un pequeño altar donde "
            "hay tres gatos más. Todos te miran. Uno maúlla algo que "
            "entiendes perfectamente: *ese mercader come soñadores.*\n\n"
            "Te regalan un pequeño saco que huele a hierba fresca."
        ),
        on_enter={"favor": +6, "lucidez": +4},
        give_item="hierba_ulthar",
        set_flags=["advertido_por_gatos"],
        npc_trust={"consejo_gatos": +10},
        paths=[
            P("Ir al puerto con cuidado", "act2_dylath_puerto",
              style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_puerto",
        act=A, zone="Dylath-Leen — Muelle Principal",
        tone="discovery",
        text=(
            "El muelle está lleno de barcos de todos los mundos soñados. "
            "Un capitán de barba blanca y sombrero triangular grita "
            "órdenes en alta voz. Te mira. Se ríe. Te hace una seña "
            "para que te acerques.\n\n"
            "A su lado, un hombre pequeño y sonriente te examina: "
            "**Neruson**, el chismoso del puerto."
        ),
        on_enter={"lucidez": +2},
        primary_npc="capitan_enmascarado",
        is_ally_npc=True,
        character_dialogue={
            "aris":     "hay barcos de todos los mundos. necesito procesar esto un momento",
            "law":      "el capitán se ríe y me hace seña... no sé si confiar pero se ve buena onda",
            "haru":     "el capitán se ríe y me hace señas, al menos este no huele raro xd",
            "elyko":    "capitan de barba blanca. se rie al verte. te hace seña. high-value NPC.",
            "xoft":     "HOLA CAPITAN me llevo a donde sea gratis si quiere le cuento todo",
            "xokram":   "Pues ya, si hay barcos hay oportunidad de salir de aquí",
            "daraziel": "El muelle está lleno de barcos de todos los estilos. Se ve que cada uno tiene su lore.",
        },
        paths=[
            P("Hablar con el capitán", "act2_dylath_capitan",
              style="primary",
              conditions={"lacks_flag": "hablo_con_capitan"}),
            P("Hablar con Neruson el chismoso", "act2_neruson",
              style="info",
              conditions={"lacks_flag": "hablo_con_neruson"}),
            P("Comprar un pasaje sin charla", "act2_dylath_pasaje_simple",
              style="info",
              conditions={"has_item": "moneda_onirica"},
              show_locked=True),
            P("Volver a la encrucijada", "act2_hub_yermos",
              style="secondary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_capitan",
        act=A, zone="Dylath-Leen — El Capitán de Barba Blanca",
        tone="awe",
        fallback_target="act2_dylath_puerto",
        text=(
            "— *Tú vienes del Umbral, ¿cierto? Se te ve.* — El capitán te "
            "ofrece un asiento en un barril. — *Cruzo a Sarkomand cada "
            "tres lunas. Si vas al norte, embarcas gratis si me cuentas "
            "algo que valga la pena. Si no, pagas.*"
        ),
        on_enter={"favor": +3},
        primary_npc="capitan_enmascarado",
        is_ally_npc=True,
        set_flags=["hablo_con_capitan"],
        character_dialogue={
            "aris":     "quiere una historia a cambio del pasaje. es un trato justo la verdad",
            "law":      "mano este señor me leyó al toque, dijo que se me nota que vengo del Umbral",
            "haru":     "dice que se me nota que vengo del umbral, quiere que le cuente algo bueno pa pasar gratis",
            "elyko":    "pasaje gratis si cuentas algo que valga. si no, pagas. trato justo.",
            "xoft":     "va, yo vengo del Umbral y tengo historias que valen mas que tu barco",
            "xokram":   "Pasaje gratis por una historia, eso si es un trato justo pije",
            "daraziel": "El capitán tiene buena presencia. Se nota que lleva años navegando por cómo se para.",
        },
        paths=[
            P("Contar lo que viste en el Umbral", "act2_dylath_pasaje_historia",
              style="success",
              conditions={"has_flag": "vio_vision_previa"},
              effects={"favor": +8, "lore": +4},
              show_locked=True),
            P("Cantar una canción del Despierto", "act2_dylath_pasaje_cancion",
              style="success",
              conditions={"class_in": ["CANTOR"]},
              effects={"favor": +10},
              show_locked=True),
            P("Cerrar un contrato de contrabando", "act2_dylath_contrato_capitan",
              style="success",
              conditions={"class_in": ["NEGOCIADOR"]},
              show_locked=True),
            P("Pagar con una moneda onírica", "act2_dylath_pasaje_simple",
              style="info",
              conditions={"has_item": "moneda_onirica"},
              show_locked=True),
            P("Ofrecerle el rubí de Leng", "act2_dylath_rubi_rechazado",
              style="warning",
              conditions={"has_item": "rubi_leng"},
              show_locked=True),
            P("Despedirse con cortesía y volver al muelle", "act2_dylath_puerto",
              style="secondary",
              effects={"favor": -2}),
        ],
    ))

    nodes.append(N(
        "act2_dylath_pasaje_historia",
        act=A, zone="Dylath-Leen — Pasaje por Historia",
        tone="awe",
        text=(
            "El capitán escucha sin interrumpir. Cuando terminas, asiente "
            "muy despacio. — *Eso vale más que oro. Sube. Vamos a "
            "Sarkomand. Y quizás más lejos, si te portas bien.*"
        ),
        on_enter={"favor": +6, "lore": +3},
        set_flags=["aliado_capitan"],
        npc_trust={"capitan_enmascarado": +25},
        paths=[
            P("Zarpar", "act2_mar_negro", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_pasaje_cancion",
        act=A, zone="Dylath-Leen — Pasaje por Canción",
        tone="awe",
        text=(
            "Cantas. El puerto se detiene un instante. Incluso los "
            "estibadores se quedan quietos. Cuando terminas, el capitán "
            "tiene los ojos húmedos. — *Sube, cantor. Gratis. Y me "
            "debes una canción más.*"
        ),
        on_enter={"favor": +10, "lucidez": +3, "memoria": -4},
        set_flags=["aliado_capitan", "canto_en_dylath"],
        give_item="partitura_inacabada",
        npc_trust={"capitan_enmascarado": +35},
        character_dialogue={
            "law": "canté y TODO el puerto se detuvo bro estoy llorando el capitán tiene los ojos húmedos",
        },
        paths=[
            P("Zarpar", "act2_mar_negro", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_contrato_capitan",
        act=A, zone="Dylath-Leen — Contrato de Contrabando",
        tone="discovery",
        text=(
            "— *Llévame tres cajas a Sarkomand. No preguntes qué hay "
            "dentro. Si llegan enteras, partimos ganancias.* El capitán "
            "te pasa un contrato escrito en tinta azul que huele a mar."
        ),
        on_enter={"lucidez": +2},
        set_flags=["aliado_capitan"],
        give_item="contrato_capitan",
        close_contract="contrato_capitan",
        npc_trust={"capitan_enmascarado": +20},
        paths=[
            P("Zarpar con la carga", "act2_mar_negro", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_pasaje_simple",
        act=A, zone="Dylath-Leen — Pasaje Pagado",
        tone="calm",
        text=(
            "Entregas una moneda. El capitán la muerde — costumbre vieja. "
            "Te da un gesto con la cabeza. Subes al barco."
        ),
        consume_item="moneda_onirica",
        paths=[
            P("Zarpar", "act2_mar_negro", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_dylath_rubi_rechazado",
        act=A, zone="Dylath-Leen — Rubí Rechazado",
        tone="tense",
        text=(
            "El capitán mira el rubí. Le cambia la cara. — *Eso es de "
            "Leng. No lo traigas a mi barco. No te lo compro, no te lo "
            "cuido. Y no subes con eso aquí.*\n\n"
            "Tienes que decidir qué hacer con el rubí antes de zarpar."
        ),
        on_enter={"favor": -3},
        character_dialogue={
            "xokram": "Mano el rubí es de Leng, obvio nadie lo quiere, hay que tirarlo",
        },
        paths=[
            P("Tirar el rubí al mar", "act2_dylath_capitan",
              style="primary",
              effects={"favor": +5, "corrupcion": -3},
              consume_item="rubi_leng"),
            P("Guardarlo y buscar otra forma", "act2_dylath_puerto",
              style="secondary"),
        ],
    ))

    # ── Mar Negro → Sarkomand ──────────────────────────────────────────────
    nodes.append(N(
        "act2_mar_negro",
        act=A, zone="Mar Negro — Travesía",
        tone="calm",
        text=(
            "El mar negro no tiene olas. El barco se desliza como sobre "
            "tinta. Durante la travesía aprendes tres cosas nuevas sobre "
            "ti mismo. Ninguna te gusta. Todas te sirven."
        ),
        on_enter={"lucidez": +4, "lore": +3, "memoria": -2},
        character_dialogue={
            "aris":     "el mar no tiene olas. se desliza como sobre tinta. es inquietante",
            "law":      "el mar no tiene olas... aprendí 3 cosas de mi mismo y ninguna me gustó 💔",
            "haru":     "el mar no tiene olas, es como navegar sobre tinta, aprendí cosas que no me gustan",
            "elyko":    "mar sin olas. aprendes 3 cosas de ti. ninguna te gusta. todas sirven.",
            "xoft":     "el mar no tiene olas y aprendi 3 cosas de mi. ninguna me gusta 💔",
            "xokram":   "Tres cosas nuevas de mi y ninguna me gusta, pero sirven gg",
            "daraziel": "Mar sin olas, barco sobre tinta. Es como navegar sobre un fondo plano. Muy limpio.",
        },
        paths=[
            P("Llegar a Sarkomand", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_sarkomand_ruinas",
        act=A, zone="Sarkomand — Ruinas al Norte",
        tone="discovery",
        text=(
            "Sarkomand está en ruinas desde hace más tiempo del que "
            "existe. Columnas partidas, estatuas sin cara. En el centro, "
            "un pozo que huele a frío. Aquí, dice la leyenda, se baja "
            "hacia *las Profundidades*.\n\n"
            "Sobre una losa caída, un hombre rechoncho ronca con un ojo "
            "abierto: **Papu**. Dicen que guarda esta cripta. Dicen "
            "también — más bajo — que guarda otra cosa peor."
        ),
        on_enter={},
        primary_npc="papu_el_relajado",
        is_ally_npc=False,
        character_dialogue={
            "aris":     "ruinas más viejas que el concepto de ruina. interesante",
            "law":      "estas ruinas son más viejas que todo bro y hay un pozo que huele a FRÍO como es eso",
            "haru":     "ruinas que llevan más tiempo roto de lo que existe, y un gordo roncando en medio xddd",
            "elyko":    "ruinas mas viejas que el tiempo. pozo al centro. aqui se baja.",
            "xoft":     "ruinas mas viejas que el tiempo. esto es god pero huele a frio mano",
            "xokram":   "Ruinas desde siempre y un gordo roncando, quien sabe qué vende",
            "daraziel": "Columnas partidas, estatuas sin cara. La composición de estas ruinas es peak.",
        },
        class_bonus={
            "CARTOGRAFO": "Dibujando mentalmente las columnas en sus posiciones originales, deduces: el pozo no baja. Se pliega.",
            "LECTORA": "En los muros hay inscripciones en el mismo pre-cuneiforme de Leng. Puedes leer fragmentos.",
        },
        paths=[
            P("Despertar a Papu", "act2_papu_llaves",
              style="info",
              conditions={"lacks_flag": "hablo_con_papu"},
              show_locked=False),
            P("Bajar por el pozo hacia las Profundidades", "act3_hub_profundidades",
              style="primary",
              conditions={"act_min": 2},
              effects={"voluntad": -3, "favor": -2}),
            P("Explorar las ruinas antes (cuesta lucidez)", "act2_sarkomand_explorar",
              style="info",
              effects={"lucidez": -3}),
            P("Entregar la carga del capitán (si tienes contrato)", "act2_sarkomand_entrega",
              style="success",
              conditions={"has_flag": "aliado_capitan", "has_item": "contrato_capitan"},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act2_sarkomand_explorar",
        act=A, zone="Sarkomand — Catacumbas",
        tone="awe",
        text=(
            "Bajo una losa, encuentras una biblioteca pequeña. Los libros "
            "están hechos de metal finísimo. Uno de ellos tiene tu "
            "nombre, o lo que era tu nombre antes de soñar, grabado en "
            "la portada. Lo abres — saber más de ti te cuesta no saber "
            "otras cosas."
        ),
        on_enter={"lore": +6, "memoria": -4, "lucidez": -2},
        give_item="libro_de_sarkomand",
        set_flags=["leyo_libro_sarkomand"],
        character_dialogue={
            "aris":     "un libro con mi nombre grabado. no sé si quiero abrirlo",
            "law":      "MANO encontré un libro con MI NOMBRE grabado en metal QUE ESTÁ PASANDO",
            "haru":     "encontré un libro con mi nombre grabado en metal, lo abro aunque me cueste algo",
            "elyko":    "biblioteca de metal. un libro tiene tu nombre. saber mas cuesta.",
            "xoft":     "KJDSALKJDSAJK un libro con MI NOMBRE grabado en metal me voy a matar",
            "xokram":   "Un libro con mi nombre, pues ya, saber más siempre cuesta algo",
            "daraziel": "Libros de metal con tu nombre grabado. El detalle de la tipografía es increíble.",
        },
        paths=[
            P("Leer el libro entero", "act2_sarkomand_libro_leido",
              style="success",
              effects={"lore": +10, "memoria": -4}),
            P("Guardarlo y bajar al pozo", "act3_hub_profundidades",
              style="primary",
              conditions={"act_min": 2}),
        ],
    ))

    nodes.append(N(
        "act2_sarkomand_libro_leido",
        act=A, zone="Sarkomand — Libro Leído",
        tone="awe",
        text=(
            "El libro cuenta tu vida despierta con una precisión que "
            "asusta. También cuenta que una parte de ti ya estuvo aquí, "
            "hace muchos sueños, y se quedó. El libro termina con una "
            "línea en blanco y una instrucción: *completa la última "
            "página con tu propia mano al final.*\n\n"
            "Para leerlo entero, un nombre querido se borra de tu "
            "memoria — de forma permanente."
        ),
        on_enter={"lore": +8, "memoria": -10},
        set_flags=["libro_listo_para_terminar"],
        paths=[
            P("Cerrar el libro y bajar al pozo", "act3_hub_profundidades",
              style="primary",
              conditions={"act_min": 2}),
        ],
    ))

    nodes.append(N(
        "act2_sarkomand_entrega",
        act=A, zone="Sarkomand — Entrega de la Carga",
        tone="discovery",
        text=(
            "En una cripta pequeña, tres personas con capuchas azules "
            "esperan la carga. No te preguntan tu nombre. Te entregan "
            "un sello pequeño. — *Dile al capitán que el trato está "
            "cerrado.*"
        ),
        consume_item="contrato_capitan",
        give_item="sello_contrato_sarkomand",
        close_contract="contrato_sarkomand",
        set_flags=["entrega_sarkomand_cerrada"],
        character_dialogue={
            "xokram": "Trato cerrado sin preguntas, así me gusta, limpio y directo",
        },
        paths=[
            P("Bajar al pozo", "act3_hub_profundidades",
              style="primary",
              conditions={"act_min": 2}),
        ],
    ))

    # ── Bosque de los Zoogs ────────────────────────────────────────────────
    nodes.append(N(
        "act2_bosque_zoog_entrada",
        act=A, zone="Bosque de los Zoogs",
        tone="tense",
        text=(
            "El bosque está lleno de ojos pequeños. Los zoogs — pequeños, "
            "curiosos, malintencionados — te observan desde los árboles. "
            "Uno baja, se planta frente a ti y te hace una seña: seguirlos, "
            "o abrirse paso a la fuerza."
        ),
        on_enter={"lucidez": -3, "lore": +3},
        primary_npc="zoogs",
        character_dialogue={
            "aris":     "ojos pequeños en todos los árboles. no me fío de ninguno",
            "law":      "hay ojos PEQUEÑOS por todos lados chicos no me gusta nada esto",
            "haru":     "el bosque está lleno de ojos chiquitos y un bicho me dice que lo siga, qué puede salir mal",
            "elyko":    "ojos pequeños en los arboles. zoogs. curiosos y malintencionados.",
            "xoft":     "osea estos bichos me quieren guiar o cagar?? les parto la cara igual",
            "xokram":   "Bichos chiquitos con mala cara, no vale la pena pelear gratis",
            "daraziel": "Ojos pequeños entre los árboles. La iluminación de este bosque está muy bien lograda.",
        },
        paths=[
            P("Seguir al zoog guía (pacto)", "act2_zoog_pacto",
              style="success",
              effects={"favor": +3, "lore": +4}),
            P("Abrirse paso sin pactar", "act2_zoog_ruta_forzada",
              style="warning",
              effects={"voluntad": +3, "favor": -5, "lucidez": -3}),
            P("Preguntar por el Rubí de Leng", "act2_zoog_conspiracion",
              style="info",
              conditions={"lacks_flag": "tomo_rubi"}),
        ],
    ))

    nodes.append(N(
        "act2_zoog_pacto",
        act=A, zone="Bosque — Pacto Zoog",
        tone="discovery",
        text=(
            "Los zoogs te llevan a un claro donde crece el *fruto lunar*. "
            "Te dan uno. — *Cuando llegues al Trono, recuerda a los "
            "zoogs*. Ese es el precio. Fácil, si no olvidas."
        ),
        give_item="fruto_lunar",
        set_flags=["pacto_zoog"],
        on_enter={"favor": +4, "lore": +4},
        npc_trust={"zoogs": +25},
        paths=[
            P("Agradecer y volver a la encrucijada", "act2_hub_yermos",
              style="primary"),
            P("Seguir al norte a Sarkomand", "act2_sarkomand_ruinas",
              style="info"),
        ],
    ))

    nodes.append(N(
        "act2_zoog_ruta_forzada",
        act=A, zone="Bosque — Ruta Forzada",
        tone="tense",
        text=(
            "Atraviesas el bosque a la fuerza. Los zoogs te recordarán. "
            "Pero llegas al otro lado con heridas de dignidad, no de "
            "cuerpo, y con una rabia útil."
        ),
        on_enter={"voluntad": +6, "favor": -5, "corrupcion": +2},
        set_flags=["zoogs_hostiles"],
        npc_trust={"zoogs": -30},
        paths=[
            P("Volver a la encrucijada", "act2_hub_yermos", style="primary"),
            P("Seguir al norte a Sarkomand", "act2_sarkomand_ruinas",
              style="info"),
        ],
    ))

    nodes.append(N(
        "act2_zoog_conspiracion",
        act=A, zone="Bosque — Conspiración Zoog",
        tone="discovery",
        text=(
            "El zoog guía te cuenta — en un idioma que no deberías "
            "entender pero entiendes — que los zoogs preparan una guerra "
            "contra los gatos. Te ofrece una porción de *fruto prohibido* "
            "a cambio de lealtad. Escucharlo hasta el final ya te "
            "compromete, aunque no aceptes: los gatos olerán el rastro."
        ),
        on_enter={"lore": +5, "favor": -4, "lucidez": -3},
        character_dialogue={
            "aris":     "guerra contra los gatos. escucharlo ya me comprometió. jopetas",
        },
        paths=[
            P("Aceptar el fruto (traición a los gatos)", "act2_zoog_fruto_prohibido",
              style="danger",
              effects={"corrupcion": +8, "favor": -6}),
            P("Rechazar y avisar a los gatos", "act2_zoog_delacion",
              style="success",
              conditions={"npc_trust": {"gato_ulthar": 15}},
              effects={"favor": +10, "lore": +3},
              show_locked=True),
            P("Rechazar y seguir tu camino", "act2_hub_yermos",
              style="info"),
        ],
    ))

    nodes.append(N(
        "act2_zoog_fruto_prohibido",
        act=A, zone="Bosque — Fruto Prohibido",
        tone="horror",
        text=(
            "El fruto sabe a recuerdos ajenos. Durante un segundo, sabes "
            "todo lo que los zoogs han visto en cuatro mil años. Al "
            "segundo siguiente, olvidas quién te trajo a este sueño. "
            "El pacto está hecho."
        ),
        on_enter={"lore": +12, "memoria": -10, "corrupcion": +6},
        give_item="fruto_prohibido",
        set_flags=["pacto_zoog_oscuro"],
        clear_flags=["bendicion_ulthar"],
        paths=[
            P("Salir del bosque", "act2_hub_yermos", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_zoog_delacion",
        act=A, zone="Bosque — Delación",
        tone="awe",
        text=(
            "Cuando sales del bosque, un gato de Ulthar ya te espera. "
            "Le cuentas lo que oíste. El gato te ronronea una bendición "
            "y te da un pequeño *bigote dorado*."
        ),
        on_enter={"favor": +10, "lucidez": +4},
        give_item="bigote_dorado",
        set_flags=["gatos_deben_favor"],
        npc_trust={"consejo_gatos": +30},
        paths=[
            P("Volver a la encrucijada", "act2_hub_yermos", style="primary"),
        ],
    ))

    # ── Celephaïs ──────────────────────────────────────────────────────────
    nodes.append(N(
        "act2_celephais_puertas",
        act=A, zone="Celephaïs — Puertas Doradas",
        tone="awe",
        text=(
            "Celephaïs brilla como si estuviera iluminada desde dentro. "
            "Aquí reina **Kuranes**, un soñador que llegó antes que tú y "
            "se quedó. Se dice que Kuranes ve a todo visitante nuevo, "
            "si el visitante trae algo digno."
        ),
        on_enter={"lucidez": +4, "lore": +3},
        character_dialogue={
            "aris":     "brilla como si tuviera iluminación interna. es hermosa la verdad",
            "law":      "Celephaïs brilla como si tuviera luz propia ES HERMOSISIMA bro dios",
            "haru":     "Celephaïs brilla como si estuviera iluminada desde dentro, es muy bonito mano",
            "elyko":    "Celephais brilla desde dentro. Kuranes reina aqui. llego antes que tu.",
            "xoft":     "LKDSAJKLDSAJK Celephais brilla desde adentro mano ESTO ES SO PEAK",
            "xokram":   "Celephaïs brilla como gacha de 5 estrellas, algo querrán a cambio",
            "daraziel": "Celephaïs brilla desde adentro. Es como si la ciudad tuviera luz propia, hermoso.",
        },
        paths=[
            P("Pedir audiencia con Kuranes", "act2_celephais_kuranes",
              style="primary",
              conditions={"lacks_flag": "hablo_con_kuranes"}),
            P("Recorrer la ciudad", "act2_celephais_recorrido",
              style="info",
              conditions={"lacks_flag": "recorri_celephais"}),
            P("Salir de Celephaïs", "act2_hub_yermos",
              style="secondary"),
        ],
    ))

    nodes.append(N(
        "act2_celephais_recorrido",
        act=A, zone="Celephaïs — Recorrido",
        tone="discovery",
        text=(
            "Una fuente que llora monedas. Una biblioteca donde los "
            "libros cambian de idioma mientras los lees. Un mercado "
            "donde pagan con recuerdos. Pasas una hora aquí; podrías "
            "pasar un siglo."
        ),
        on_enter={"lore": +5, "memoria": -3, "lucidez": +3},
        give_item="moneda_onirica",
        set_flags=["recorri_celephais"],
        paths=[
            P("Volver a las puertas y pedir audiencia", "act2_celephais_kuranes",
              style="primary",
              conditions={"lacks_flag": "hablo_con_kuranes"}),
            P("Volver a la encrucijada", "act2_hub_yermos",
              style="secondary"),
        ],
    ))

    nodes.append(N(
        "act2_celephais_kuranes",
        act=A, zone="Celephaïs — Audiencia con Kuranes",
        tone="awe",
        text=(
            "Kuranes te recibe en una terraza con vistas al mar. Ya no "
            "es joven. Tiene los ojos de alguien que pagó por quedarse. "
            "— *Así que vas a Kadath. Yo también fui. Volví sin el "
            "cuerpo con el que fui. ¿Sabes qué pagas, realmente?*"
        ),
        on_enter={"lore": +5},
        primary_npc="kuranes",
        is_ally_npc=True,
        set_flags=["hablo_con_kuranes"],
        character_dialogue={
            "aris":     "pagó por quedarse. tiene los ojos de alguien que sabe el costo real",
            "law":      "Kuranes tiene los ojos de alguien que pagó caro por quedarse... me da pena 💔",
            "haru":     "el tipo pagó por quedarse y se le nota en los ojos, dice que ir a Kadath cuesta caro",
            "elyko":    "Kuranes pago por quedarse. se le nota en los ojos. pregunta si sabes el costo.",
            "xoft":     "mano Kuranes pago con su cuerpo por quedarse. yo no pago nada va",
            "xokram":   "Mano Kuranes pagó con el cuerpo, eso ya es demasiado caro pije",
            "daraziel": "Kuranes tiene los ojos de alguien que pagó caro por quedarse. Se le nota en la mirada.",
        },
        paths=[
            P("«Pago lo que haya que pagar»", "act2_celephais_kuranes_respuesta_firme",
              style="success",
              effects={"voluntad": +8, "favor": +6}),
            P("«No estoy seguro»", "act2_celephais_kuranes_respuesta_humilde",
              style="info",
              effects={"memoria": +6, "lore": +4, "favor": +3}),
            P("«Dime tú, viejo»", "act2_celephais_kuranes_respuesta_ironica",
              style="warning",
              effects={"lore": +6, "favor": -3}),
        ],
    ))

    nodes.append(N(
        "act2_celephais_kuranes_respuesta_firme",
        act=A, zone="Celephaïs — Pacto de Voluntad",
        tone="awe",
        text=(
            "Kuranes asiente. — *Bien. Lleva esto: cuando llegues a las "
            "Profundidades, muéstralo a los ghouls. Te tratarán como "
            "huésped, no como presa.*"
        ),
        on_enter={"favor": +6, "voluntad": +4},
        give_item="sello_kuranes",
        set_flags=["aliado_kuranes"],
        npc_trust={"kuranes": +30},
        paths=[
            P("Agradecer y partir", "act2_hub_yermos", style="primary"),
            P("Seguir hacia Sarkomand", "act2_sarkomand_ruinas", style="info"),
        ],
    ))

    nodes.append(N(
        "act2_celephais_kuranes_respuesta_humilde",
        act=A, zone="Celephaïs — Consejo Paternal",
        tone="calm",
        text=(
            "Kuranes se ablanda. — *Entonces escucha. Kadath no te dará "
            "lo que pides. Te dará lo que eres. Si no sabes qué eres, "
            "búscalo en las Profundidades primero. Los ghouls recuerdan "
            "mejor que los dioses.*\n\n"
            "Escuchar esto te duele: saber que tu viaje puede no "
            "servir es peor que no saberlo."
        ),
        on_enter={"lore": +6, "memoria": +3, "voluntad": -4},
        give_item="consejo_kuranes",
        set_flags=["aliado_kuranes"],
        npc_trust={"kuranes": +25},
        paths=[
            P("Agradecer y partir", "act2_hub_yermos", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_celephais_kuranes_respuesta_ironica",
        act=A, zone="Celephaïs — Respuesta Espinosa",
        tone="tense",
        text=(
            "Kuranes ríe sin alegría. — *Pago mi corona. Pago mi cuerpo. "
            "Pago mi nombre despierto. Y ahora pago esta conversación "
            "contigo.* Te despide con un gesto de la mano."
        ),
        on_enter={"lore": +5, "favor": -3},
        npc_trust={"kuranes": +5},
        paths=[
            P("Salir de Celephaïs", "act2_hub_yermos", style="primary"),
        ],
    ))
    # ── NPC del servidor: Neruson el Chismoso ──────────────────────────────
    nodes.append(N(
        "act2_neruson",
        act=A, zone="Dylath-Leen — Neruson el Chismoso",
        tone="social",
        text=(
            "**Neruson** te mira como quien tasa a un caballo. — *Oye, "
            "te cuento algo: el capitán miente con la ruta. Y el mercader "
            "del turbante no es lo que dice ser. Por una moneda onírica, "
            "te doy nombres. Por una historia, te doy dos.*"
        ),
        primary_npc="neruson_el_chismoso",
        is_ally_npc=True,
        set_flags=["hablo_con_neruson"],
        paths=[
            P("Pagar una moneda onírica por el chisme", "act2_neruson_chisme",
              style="success",
              conditions={"has_item": "moneda_onirica"},
              consume_item="moneda_onirica",
              effects={"lore": +6, "memoria": -2},
              show_locked=True),
            P("Intercambiar una historia (visión del Umbral)", "act2_neruson_intercambio",
              style="info",
              conditions={"has_flag": "vio_vision_previa"},
              effects={"lore": +4, "memoria": -4},
              show_locked=True),
            P("No, gracias", "act2_dylath_puerto",
              style="secondary",
              effects={"favor": -1}),
        ],
    ))

    nodes.append(N(
        "act2_neruson_chisme",
        act=A, zone="Dylath-Leen — Chisme de Neruson",
        tone="discovery",
        text=(
            "— *El capitán te va a ofrecer pasaje por una historia. "
            "Dale la visión del Umbral si la tienes. Si no, cuéntale "
            "una mentira que suene verdadera. Y el mercader del turbante: "
            "escúpele al suelo antes de comprarle, se le cae la máscara.*"
        ),
        set_flags=["sabe_chisme_neruson"],
        give_item="nombre_verdadero_mercader",
        npc_trust={"neruson_el_chismoso": +15},
        paths=[
            P("Volver al puerto", "act2_dylath_puerto", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_neruson_intercambio",
        act=A, zone="Dylath-Leen — Intercambio con Neruson",
        tone="discovery",
        text=(
            "Le cuentas tu visión. Neruson asiente muy despacio. — *Eso "
            "vale doble. Toma: te debo dos chismes. Uno ahora, uno después.*"
        ),
        set_flags=["neruson_debe_favor"],
        close_contract="chisme_neruson",
        npc_trust={"neruson_el_chismoso": +30},
        give_item="pagare_de_neruson",
        paths=[
            P("Volver al puerto", "act2_dylath_puerto", style="primary"),
        ],
    ))


    # ── NPC del servidor: Papu el Relajado ─────────────────────────────────
    nodes.append(N(
        "act2_papu_llaves",
        act=A, zone="Sarkomand — Papu Despierta",
        tone="horror",
        text=(
            "Papu abre un solo ojo — el otro no lo abre nunca, dice él, "
            "«porque ya vi lo que hay arriba». Bosteza. El manojo de "
            "llaves del cinturón tintinea: son doce llaves pequeñas, "
            "del tamaño de jaulas pequeñas.\n\n"
            "— *ah ya mano. sisis. bienvenido a la pre-subasta. tengo "
            "producto fresco, producto viejo, producto de colección. "
            "los clientes VIP llegan en tres lunas, pero los precios de "
            "pre-venta están god. sisis.*\n\n"
            "Te ofrece algo. Un té, un vino, un pequeño vaso de algo que "
            "huele demasiado dulce."
        ),
        primary_npc="papu_el_relajado",
        is_ally_npc=False,
        character_dialogue={
            "aris":     "doce llaves del tamaño de jaulas. nunca consideré este caso",
            "law":      "PAPU ALEJATE bro tiene un ojo que no abre nunca porque ya vio lo que hay arriba",
            "haru":     "JAJAKAKAKAJA este gordo tiene 12 llaves del tamaño de jaulas, qué mierda vende",
            "elyko":    "aver, papu: 12 llaves, un ojo cerrado. dice que ya vio lo de arriba.",
            "xoft":     "PAPU MALDITO que haces con esas llaves de jaulas te voy a matar",
            "xokram":   "Doce llaves y un ojo cerrado, este mano sabe más de lo que dice",
            "daraziel": "Doce llaves del tamaño de jaulas. Ese detalle de proporción es muy bueno, mano.",
        },
        paths=[
            P("Aceptar el vaso «para cerrar negocio»",
              "act2_papu_te_duerme",
              style="danger",
              conditions={"lacks_flag": "hablo_con_papu"},
              effects={"corrupcion": +4, "memoria": -3},
              set_flags=["acepto_bebida_papu"]),
            P("Preguntarle por su «producto» sin beber",
              "act2_papu_te_duerme",
              style="warning",
              conditions={"lacks_flag": "hablo_con_papu"},
              effects={"lore": +3, "favor": -4},
              set_flags=["pregunto_producto_papu"]),
            P("Intentar huir inmediatamente",
              "act2_papu_te_duerme",
              style="warning",
              conditions={"lacks_flag": "hablo_con_papu"},
              effects={"voluntad": +3, "lucidez": -3},
              set_flags=["intento_huir_papu"]),
            P("Marcharte sin decir una sola palabra",
              "act2_sarkomand_ruinas",
              style="secondary",
              conditions={"lacks_flag": "hablo_con_papu"},
              effects={"favor": -1, "lucidez": +2},
              set_flags=["hablo_con_papu", "evito_papu"]),
        ],
    ))

    # Papu acepta el pago limpio y se guarda lo suyo
    nodes.append(N(
        "act2_papu_paso_limpio",
        act=A, zone="Sarkomand — Paso Limpio",
        tone="tense",
        text=(
            "— *waos, mano, moneda clean. mis preferidos.* Papu se "
            "guarda la moneda sin mirarla. — *ah ya, te abro la cripta "
            "del sur. de la otra mejor no preguntes. sisis. gg.*\n\n"
            "Abre una puerta baja y se vuelve a tumbar. El olor de la "
            "cripta del norte — la que no te abrió — se cuela unos "
            "segundos hasta ti. No pienses en eso."
        ),
        give_item="llaves_papu",
        set_flags=["aliado_papu", "hablo_con_papu"],
        npc_trust={"papu_el_relajado": +10},
        paths=[
            P("Explorar las catacumbas del sur", "act2_sarkomand_explorar",
              style="success"),
            P("Bajar al pozo sin mirar atrás", "act3_hub_profundidades",
              style="primary",
              effects={"memoria": -3}),
        ],
    ))

    # Papu muestra el "producto"
    nodes.append(N(
        "act2_papu_producto",
        act=A, zone="Sarkomand — El Almacén de Papu",
        tone="horror",
        text=(
            "— *ah ya, curioso el mano.* Papu se levanta por primera vez. "
            "Lo sigues a una cripta baja al norte. Dentro hay doce jaulas "
            "pequeñas, y en cada jaula una sombra del tamaño de un niño "
            "— soñadores jóvenes, piezas de dreamers aún no formados, "
            "almas oníricas sin dueño.\n\n"
            "— *estos no nacieron acá, mano. vienen del umbral, del lado "
            "donde alguien deja de soñar y yo estoy con el balde. "
            "los vendo a los de Leng, a los ghouls si pagan bien, a "
            "quien sea que lleve moneda dura. no preguntes, yo tampoco.*\n\n"
            "Una de las sombras, la más pequeña, te mira. No tiene cara. "
            "Te tiende una mano que no es una mano. Tú sabes — sin "
            "querer saberlo — que esa sombra podría haber sido tú, "
            "hace muchos sueños."
        ),
        on_enter={"corrupcion": +4, "lucidez": -6, "lore": +5},
        set_flags=["hablo_con_papu", "vio_almacen_papu"],
        character_dialogue={
            "aris":     "soñadores en jaulas. esto es tráfico. literal tráfico",
            "law":      "son soñadores JÓVENES en jaulas bro NO JODAAAAAA esto está mal está muy mal",
            "haru":     "mano tiene soñadores en jaulas, esto ya no es chistoso, es una putada de verdad",
            "elyko":    "jaulas con sombras de soñadores jovenes. esto es trafico. literal.",
            "xoft":     "SOÑADORES EN JAULAS mano Papu hijo de toda tupu esto no se perdona",
            "xokram":   "Soñadores en jaulas mano, esto ya no es negocio es negreada",
            "daraziel": "Sombras del tamaño de un niño en jaulas. Esto es horrible pero visualmente es god.",
        },
        paths=[
            P("Comprar la sombra más pequeña (ponerla a salvo)",
              "act2_papu_rescate",
              style="success",
              conditions={"has_item": "moneda_onirica"},
              consume_item="moneda_onirica",
              effects={"favor": +8, "memoria": +5, "corrupcion": -3},
              show_locked=True),
            P("Romper las jaulas (revuelta)",
              "act2_papu_revuelta",
              style="warning",
              conditions={"voluntad_min": 45},
              effects={"voluntad": +6, "favor": +6, "corrupcion": -2, "lucidez": -3},
              show_locked=True),
            P("Comprar «producto» para ti mismo (oscuro)",
              "act2_papu_compra_oscura",
              style="danger",
              conditions={"has_item": "moneda_onirica"},
              consume_item="moneda_onirica",
              effects={"corrupcion": +15, "favor": -20, "lore": +8},
              show_locked=True),
            P("Largarte del almacén sin tocar nada",
              "act2_sarkomand_ruinas",
              style="secondary",
              effects={"memoria": -5, "corrupcion": +2}),
        ],
    ))

    nodes.append(N(
        "act2_papu_rescate",
        act=A, zone="Sarkomand — Rescate Silencioso",
        tone="awe",
        text=(
            "— *ah ya mano. esa te la cobro doble — clean.* Papu suelta "
            "la jaula pequeña sin mirarte. La sombra que sacas de ahí "
            "no tiene cara pero te toma la mano sin titubear. La "
            "sueltas en el sendero al sur de Sarkomand. Se aleja. "
            "No mira atrás. Bien.\n\n"
            "Aprendes su forma de peso. La llevarás contigo hasta "
            "Kadath, aunque ya no esté en tu mano."
        ),
        give_item="sombra_rescatada",
        set_flags=["rescato_sombra_papu"],
        npc_trust={"papu_el_relajado": +5, "consejo_gatos": +20},
        paths=[
            P("Volver a Sarkomand", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_papu_revuelta",
        act=A, zone="Sarkomand — Revuelta en el Almacén",
        tone="horror",
        text=(
            "Rompes las doce jaulas. Papu grita — *«lptm mano, lptm, "
            "eras mi cliente»* — pero no se mueve: no pelea de frente, "
            "nunca, solo apunta un dedo hacia ti y murmura algo en un "
            "idioma que no era español.\n\n"
            "Las sombras salen en estampida silenciosa hacia el sur. "
            "Doce de ellas. Doce direcciones. Papu te mira con el "
            "único ojo abierto, y tú sabes que va a recordarte. "
            "Siempre."
        ),
        on_enter={"voluntad": +4, "lucidez": -4},
        set_flags=["libero_almacen_papu", "papu_enemigo_mortal"],
        npc_trust={"papu_el_relajado": -60, "consejo_gatos": +30,
                   "gato_ulthar": +20},
        paths=[
            P("Huir hacia el pozo antes de que reaccione",
              "act3_hub_profundidades",
              style="primary",
              effects={"voluntad": +3, "lucidez": -2}),
            P("Entrar a la cripta que NO abrió Papu",
              "act2_sarkomand_explorar",
              style="warning",
              effects={"lore": +8, "lucidez": -5, "corrupcion": +4}),
        ],
    ))

    nodes.append(N(
        "act2_papu_compra_oscura",
        act=A, zone="Sarkomand — La Compra que te Vuelve Otro",
        tone="horror",
        text=(
            "— *sisis mano. elegiste bien el tamaño.* Papu te entrega "
            "la jaula pequeña con una sonrisa casi tierna. La sombra "
            "dentro no tiene cara, pero tiene tu voz cuando eras niño. "
            "Cuando la tocas, se te mete en el pecho como si siempre "
            "hubiera estado ahí.\n\n"
            "— *gg mano. cliente recurrente, espero. back.*\n\n"
            "Sales del almacén sabiendo más que nunca. Y siendo menos "
            "tú que nunca. Nyarlathotep, en algún lugar, aplaude sin "
            "manos."
        ),
        on_enter={"corrupcion": +12, "memoria": -10, "lore": +8},
        give_item="sombra_propia",
        set_flags=["compro_sombra_papu", "nyarlathotep_te_aprueba"],
        npc_trust={"papu_el_relajado": +15},
        paths=[
            P("Volver a Sarkomand", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_papu_delacion_leng",
        act=A, zone="Sarkomand — Delación a Leng",
        tone="tense",
        text=(
            "Le cuentas a un Hombre de Leng que pasa por Sarkomand lo "
            "que Papu guarda. El Hombre de Leng no se sorprende — *ya lo "
            "sabíamos, soñador. Él nos vende. Pero gracias por "
            "confirmarnos que lo sabes.* Te pasa una cuchilla pequeña de "
            "hueso. — *Cuando la uses, tendrás lo que pediste.*\n\n"
            "Uno no delata a un traficante ante sus clientes sin pagar "
            "también."
        ),
        on_enter={"corrupcion": +8, "favor": -5, "lore": +4},
        give_item="cuchilla_leng",
        set_flags=["hablo_con_papu", "delato_papu_a_leng"],
        npc_trust={"papu_el_relajado": -15, "mercader_leng": +10},
        paths=[
            P("Volver a Sarkomand", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_papu_delacion_gatos",
        act=A, zone="Sarkomand — Delación a los Gatos",
        tone="discovery",
        text=(
            "Subes a Ulthar. Los gatos escuchan. El mayor asiente sin "
            "maullar. Tres gatos bajan esa misma noche a Sarkomand. "
            "Al día siguiente, las jaulas de Papu están vacías. Papu "
            "sigue sobre la losa, pero ya no ronca. Te mira cuando "
            "pasas. No te mira con odio — te mira con respeto. Eso "
            "es peor.\n\n"
            "Los gatos te dejan un bigote plateado en el camino."
        ),
        on_enter={"favor": +15, "voluntad": +5, "lucidez": +3},
        give_item="bigote_dorado",
        set_flags=["hablo_con_papu", "delato_papu_a_gatos",
                   "gatos_deben_favor"],
        npc_trust={"papu_el_relajado": -25, "consejo_gatos": +40,
                   "gato_ulthar": +25},
        paths=[
            P("Volver a Sarkomand", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_papu_robo",
        act=A, zone="Sarkomand — Colándote",
        tone="tense",
        text=(
            "Le sacas las llaves a Papu sin despertarlo. Entras por la "
            "cripta del norte — la que no te habría abierto. Adentro "
            "hay doce jaulas pequeñas. No abres las jaulas. Vuelves "
            "con las llaves y sabes algo que no podrás olvidar.\n\n"
            "Papu, aunque sea perezoso, tiene memoria. Y un ojo "
            "siempre abierto. Va a recordarte."
        ),
        on_enter={"corrupcion": +3, "lucidez": -4, "lore": +2},
        give_item="llaves_papu",
        set_flags=["traiciono_a_papu", "vio_almacen_papu",
                   "hablo_con_papu"],
        npc_trust={"papu_el_relajado": -30},
        paths=[
            P("Explorar las catacumbas del sur", "act2_sarkomand_explorar",
              style="primary"),
            P("Bajar al pozo", "act3_hub_profundidades", style="primary"),
        ],
    ))

    return nodes


def build_act3(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 3
    nodes: List[Dict[str, Any]] = []

    nodes.append(N(
        "act3_hub_profundidades",
        act=A, zone="Las Profundidades — Vestíbulo",
        tone="discovery",
        text=(
            "El pozo te dejó en una caverna inmensa donde la luz no "
            "proviene de ningún lado y, sin embargo, se ve todo. Hay "
            "tres caminos visibles: al sur, un **río subterráneo**; al "
            "norte, las **criptas ghoul**; al oeste, un **templo** "
            "sumergido hasta las rodillas en agua negra."
        ),
        on_enter={"lore": +4, "lucidez": -2},
        character_dialogue={
            "aris":     "luz sin fuente visible. tres caminos. necesito más datos antes de elegir",
            "law":      "la luz no viene de ningún lado pero se ve todo?? hay 3 caminos y todos dan miedo",
            "haru":     "una caverna inmensa con luz que no viene de ningún lado, tres caminos visibles",
            "elyko":    "caverna con luz sin origen. 3 caminos: rio, criptas ghoul, templo.",
            "xoft":     "hay luz sin fuente y tres caminos. vamos al templo que me da igual morir",
            "xokram":   "Tres caminos y todos huelen raro, la verdad ninguno es gratis",
            "daraziel": "Luz sin origen visible pero se ve todo. Tres caminos claros. Buen diseño de espacio.",
        },
        paths=[
            P("Río subterráneo (sur)", "act3_rio_entrada", style="info"),
            P("Criptas ghoul (norte)", "act3_ghouls_encuentro", style="warning",
              conditions={"lacks_flag": "visito_ghouls"}),
            P("Templo sumergido (oeste)", "act3_templo_entrada", style="primary",
              conditions={"lacks_flag": "visito_templo"}),
        ],
    ))

    # ── Río subterráneo ────────────────────────────────────────────────────
    nodes.append(N(
        "act3_rio_entrada",
        act=A, zone="Río Subterráneo — Orilla",
        tone="calm",
        text=(
            "El río es negro y silencioso. Una barca de madera vieja "
            "flota atada a un poste. Un barquero con capucha te espera "
            "sin mirarte. Cobra en recuerdos."
        ),
        on_enter={"lucidez": +3},
        primary_npc="barquero",
        paths=[
            P("Subir a la barca (pagar con un recuerdo)", "act3_rio_barca",
              style="warning", effects={"memoria": -8, "lore": +6}),
            P("Cruzar a nado (voluntad)", "act3_rio_nadar",
              style="danger",
              conditions={"voluntad_min": 45},
              effects={"voluntad": -5, "lucidez": -4}),
            P("Lanzarle la bendición del gato", "act3_rio_bendicion",
              style="success",
              conditions={"has_item": "bendicion_gato"},
              effects={"favor": +4},
              show_locked=True),
            P("Volver al vestíbulo", "act3_hub_profundidades", style="secondary"),
        ],
    ))

    nodes.append(N(
        "act3_rio_barca",
        act=A, zone="Río Subterráneo — En la Barca",
        tone="awe",
        text=(
            "El barquero rema. Le pagaste con un recuerdo de tu madre, "
            "o de alguien que quizás era tu madre. Ya no lo sabes. En "
            "la otra orilla, unas velas flotantes señalan el paso."
        ),
        set_flags=["pago_al_barquero"],
        paths=[P("Desembarcar", "act3_lago_memorias", style="primary")],
    ))

    nodes.append(N(
        "act3_rio_nadar",
        act=A, zone="Río Subterráneo — Cruzando a Nado",
        tone="tense",
        text=(
            "Cruzas el río negro a nado. El agua te cuenta cosas mientras "
            "nadas. Algunas te gustan. Otras no. Lleguas al otro lado "
            "sabiendo más de lo que sabías."
        ),
        on_enter={"voluntad": +4, "lore": +6, "lucidez": -2},
        set_flags=["cruzo_rio_a_nado"],
        paths=[P("Seguir", "act3_lago_memorias", style="primary")],
    ))

    nodes.append(N(
        "act3_rio_bendicion",
        act=A, zone="Río Subterráneo — Cruce Bendito",
        tone="awe",
        text=(
            "Muestras la bendición de Ulthar. El barquero se inclina, "
            "rema, no te cobra. Algunos favores pesan más que recuerdos."
        ),
        set_flags=["paso_rio_sin_pago"],
        paths=[P("Desembarcar", "act3_lago_memorias", style="primary")],
    ))

    nodes.append(N(
        "act3_lago_memorias",
        act=A, zone="Lago de las Memorias",
        tone="awe",
        text=(
            "Un lago inmóvil. La superficie refleja momentos que aún no "
            "han ocurrido. También refleja uno que sí, pero habías "
            "preferido olvidar. Puedes mirar, o puedes pasar sin mirar."
        ),
        on_enter={"lucidez": +3},
        character_dialogue={
            "aris":     "refleja cosas que no han pasado. y una que preferí olvidar",
            "law":      "el lago refleja cosas que NO han pasado y una que sí pero quería olvidar... no sé si mirar",
            "haru":     "el lago refleja cosas que no han pasado y una que sí pero quería olvidar, paso de largo",
            "elyko":    "lago que refleja cosas que no pasaron. y una que si pero olvidaste.",
            "xoft":     "el lago muestra cosas que no pasaron y una que si 💔 no miro mas",
            "xokram":   "Mirar el futuro gratis suena a estafa, quien sabe pije",
            "daraziel": "El lago refleja cosas que no han pasado. Es como un espejo con delay. Muy bonito.",
        },
        paths=[
            P("Mirar — aceptar lo que venga", "act3_lago_mirada",
              style="primary",
              conditions={"lacks_flag": "visite_lago"},
              effects={"lore": +8, "memoria": -4},
              set_flags=["visite_lago"]),
            P("Pasar sin mirar", "act3_convergencia_profunda",
              style="info", effects={"voluntad": +5, "memoria": +3},
              set_flags=["visite_lago"]),
            P("Mirar con el canto (cantor)", "act3_lago_cancion",
              style="success",
              conditions={"class_in": ["CANTOR"], "lacks_flag": "visite_lago"},
              effects={"favor": +8, "lore": +6},
              set_flags=["visite_lago"],
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act3_lago_mirada",
        act=A, zone="Lago — Mirada Profunda",
        tone="awe",
        text=(
            "Ves tres destinos posibles. Uno en el que te coronan. Uno "
            "en el que te olvidan. Uno en el que te ríes. No sabes cuál "
            "es real aún. Tú eliges, más tarde."
        ),
        on_enter={"lore": +8, "memoria": -2},
        set_flags=["vio_destinos"],
        paths=[P("Seguir", "act3_convergencia_profunda", style="primary")],
    ))

    nodes.append(N(
        "act3_lago_cancion",
        act=A, zone="Lago — Canción al Reflejo",
        tone="awe",
        text=(
            "Cantas sobre el lago. Los reflejos se calman y te muestran "
            "una sola escena: tú, viejo, en paz, con un instrumento que "
            "aún no existe. El lago te deja con una *partitura celeste*.\n\n"
            "La canción sabe todo de ti mientras dura — y al terminar, "
            "se lleva una parte pequeña que no vuelve."
        ),
        on_enter={"favor": +8, "lucidez": +5, "memoria": -6},
        give_item="partitura_celeste",
        set_flags=["tiene_partitura_celeste"],
        paths=[P("Seguir", "act3_convergencia_profunda", style="primary")],
    ))

    # ── Ghouls ─────────────────────────────────────────────────────────────
    nodes.append(N(
        "act3_ghouls_encuentro",
        act=A, zone="Criptas Ghoul — Encuentro",
        tone="tense",
        text=(
            "Tres ghouls te rodean. Su piel es grisácea y sus dientes "
            "largos. Huelen a tumba mojada. No te atacan: te miden. "
            "Quieren saber si eres comida, aliado o trueque."
        ),
        on_enter={"lucidez": -4},
        primary_npc="ghouls",
        set_flags=["visito_ghouls"],
        paths=[
            P("Mostrar el sello de Kuranes", "act3_ghouls_huesped",
              style="success",
              conditions={"has_item": "sello_kuranes"},
              effects={"favor": +4},
              show_locked=True),
            P("Ofrecer un pacto con ellos", "act3_ghouls_pacto",
              style="warning",
              effects={"corrupcion": +6, "favor": -3}),
            P("Ofrecer el fragmento de glifo", "act3_ghouls_trueque",
              style="info",
              conditions={"has_item": "fragmento_glifo"},
              show_locked=True),
            P("Correr hacia el templo", "act3_templo_entrada",
              style="danger",
              effects={"voluntad": -5, "lucidez": -5, "corrupcion": +3}),
        ],
    ))

    nodes.append(N(
        "act3_ghouls_huesped",
        act=A, zone="Criptas Ghoul — Huésped de Kuranes",
        tone="awe",
        text=(
            "Los ghouls se inclinan. — *Kuranes no protege a cualquiera. "
            "Come con nosotros. Escucha nuestras canciones. Cuando "
            "vayas a Kadath, recuérdanos.*\n\n"
            "Ser huésped cuesta: te ven como a uno de ellos ahora, y "
            "los Dioses Blandos lo notan."
        ),
        on_enter={"lore": +6, "favor": -3, "corrupcion": +4},
        set_flags=["huesped_ghoul"],
        npc_trust={"ghouls": +30},
        give_item="cancion_ghoul",
        paths=[
            P("Aceptar la invitación", "act3_ghouls_banquete",
              style="primary"),
            P("Seguir al templo", "act3_templo_entrada", style="info"),
        ],
    ))

    nodes.append(N(
        "act3_ghouls_banquete",
        act=A, zone="Criptas Ghoul — Banquete",
        tone="awe",
        text=(
            "Comes con los ghouls. La comida no es para ti; te dan leche "
            "de luna y pan de Leng. Cantan. Aprendes una canción que "
            "servirá más tarde — pero la leche de luna no se olvida "
            "una vez probada, y tus sueños nunca más son del todo tuyos."
        ),
        on_enter={"lucidez": +4, "favor": +3, "memoria": -8, "corrupcion": +5},
        set_flags=["banquete_ghoul"],
        give_item="sello_ghoul",
        paths=[P("Al templo", "act3_templo_entrada", style="primary")],
    ))

    nodes.append(N(
        "act3_ghouls_pacto",
        act=A, zone="Criptas Ghoul — Pacto Oscuro",
        tone="horror",
        text=(
            "Firmas con saliva propia sobre un fragmento de hueso. "
            "Desde ahora eres parte de la jauría. Te mueves con más "
            "soltura en las profundidades. Pero los Dioses Blandos ya "
            "no te escuchan igual."
        ),
        on_enter={"corrupcion": +10, "favor": -8, "voluntad": +3},
        give_item="sello_ghoul",
        set_flags=["pacto_ghoul"],
        npc_trust={"ghouls": +40},
        paths=[
            P("Partir al templo", "act3_templo_entrada", style="primary"),
            P("Conocer al *Rey Ghoul*", "act3_ghouls_rey",
              style="warning",
              conditions={"has_flag": "pacto_ghoul"},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act3_ghouls_trueque",
        act=A, zone="Criptas Ghoul — Trueque",
        tone="discovery",
        text=(
            "El fragmento de glifo les interesa: dicen que es parte del "
            "nombre verdadero de algo. Te dan a cambio una *lámpara "
            "ghoul* que ilumina lo que está oculto."
        ),
        consume_item="fragmento_glifo",
        give_item="lampara_ghoul",
        close_contract="trueque_ghoul",
        npc_trust={"ghouls": +10},
        paths=[P("Al templo", "act3_templo_entrada", style="primary")],
    ))

    nodes.append(N(
        "act3_ghouls_rey",
        act=A, zone="Criptas Ghoul — El Rey",
        tone="awe",
        text=(
            "El Rey Ghoul es enorme, viejo, paciente. No habla: rumia. "
            "Al irte, escupe un hueso a tus pies. Te lo guardas. Algún "
            "día, si llegas al Trono, este hueso abrirá una puerta que "
            "nadie más podría abrirte.\n\n"
            "Verlo sin apartar la mirada cuesta algo — la cordura no "
            "vuelve a alinearse del todo."
        ),
        on_enter={"lore": +6, "lucidez": -4, "corrupcion": +3},
        give_item="hueso_rey_ghoul",
        set_flags=["vio_rey_ghoul"],
        npc_trust={"ghouls": +20},
        paths=[P("Volver al vestíbulo", "act3_hub_profundidades", style="primary")],
    ))

    # ── Templo sumergido ───────────────────────────────────────────────────
    nodes.append(N(
        "act3_templo_entrada",
        act=A, zone="Templo Sumergido — Vestíbulo",
        tone="tense",
        text=(
            "El agua negra te llega a las rodillas. Al fondo, un altar "
            "bajo el cual se adivina una figura que no debería estar "
            "ahí. Murmullo constante, como si mil voces leyeran en voz "
            "baja al unísono."
        ),
        on_enter={"corrupcion": +3, "lore": +4, "lucidez": -3},
        set_flags=["visito_templo"],
        character_dialogue={
            "aris":     "mil voces leyendo al unísono. el murmullo no para. me da miedo",
            "law":      "el agua negra me llega a las rodillas y hay mil voces leyendo a la vez ESTOY TEMBLANDO",
            "haru":     "agua negra hasta las rodillas y mil voces leyendo al unísono, esto me da cosa de verdad",
            "elyko":    "agua negra a las rodillas. mil voces leyendo al unisono. no es bueno.",
            "xoft":     "agua negra hasta las rodillas y mil voces leyendo. me da rabia no miedo",
            "xokram":   "Mil voces murmurando no es buen ambiente para cerrar tratos mano",
            "daraziel": "Agua negra hasta las rodillas, altar al fondo. La profundidad de campo está increíble.",
        },
        paths=[
            P("Acercarse al altar", "act3_templo_altar", style="warning",
              conditions={"lacks_flag": "hablo_con_sacerdote"}),
            P("Leer las paredes (si tienes lámpara)", "act3_templo_frescos",
              style="info",
              conditions={"has_item": "lampara_ghoul"},
              show_locked=True),
            P("Retroceder", "act3_hub_profundidades", style="secondary"),
        ],
    ))

    nodes.append(N(
        "act3_templo_altar",
        act=A, zone="Templo Sumergido — Altar",
        tone="horror",
        text=(
            "En el altar, un **sacerdote sin rostro** levanta la cabeza "
            "como si te esperara. Habla sin boca: — *Soñador, te falta "
            "una máscara. Te ofrezco una. A cambio, sólo quiero tu nombre.*"
        ),
        on_enter={"lucidez": -5, "corrupcion": +5},
        primary_npc="sacerdote_sin_rostro",
        set_flags=["hablo_con_sacerdote"],
        hostile_npc="sacerdote_sin_rostro",
        paths=[
            P("Aceptar la máscara", "act3_templo_mascara_aceptada",
              style="danger",
              effects={"corrupcion": +15, "memoria": -10, "favor": -10}),
            P("Rechazar con voluntad", "act3_templo_rechazo",
              style="success",
              conditions={"voluntad_min": 45},
              effects={"voluntad": +6, "favor": +4},
              show_locked=True),
            P("Ofrecerle tu propia canción (cantor)", "act3_templo_cancion",
              style="success",
              conditions={"class_in": ["CANTOR"]},
              show_locked=True),
            P("Provocarlo para que muestre su cara", "act3_templo_provocar",
              style="warning",
              conditions={"class_in": ["PROVOCADOR"]},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act3_templo_mascara_aceptada",
        act=A, zone="Templo Sumergido — Máscara Aceptada",
        tone="horror",
        text=(
            "La máscara se te fija a la cara como si siempre hubiera "
            "estado ahí. Algo en ti se apaga y algo más se enciende. "
            "El sacerdote sonríe, aunque no tenga boca."
        ),
        on_enter={"corrupcion": +10},
        give_item="mascara_del_sacerdote",
        set_flags=["tomo_mascara_caos", "oferta_nyarlathotep"],
        paths=[P("Salir del templo", "act3_convergencia_profunda", style="primary")],
    ))

    nodes.append(N(
        "act3_templo_rechazo",
        act=A, zone="Templo Sumergido — Rechazo",
        tone="awe",
        text=(
            "— *No.* Tu voluntad empuja al sacerdote dos pasos atrás. "
            "Ríe sin boca: *Buena elección. Pero recuerda: todos los "
            "que me dijeron «no» terminaron diciéndomelo tres veces "
            "antes del final.*"
        ),
        on_enter={"voluntad": +10, "favor": +8, "lucidez": +4},
        set_flags=["rechazo_mascara", "nyarlathotep_te_respeta"],
        paths=[P("Salir del templo", "act3_convergencia_profunda", style="primary")],
    ))

    nodes.append(N(
        "act3_templo_cancion",
        act=A, zone="Templo Sumergido — Canción al Caos",
        tone="awe",
        text=(
            "Cantas algo que sólo los cantores saben. Es una canción "
            "antigua sobre despertar. El sacerdote baja la cabeza. Por "
            "primera vez, algo en él tiembla. Te deja pasar sin precio."
        ),
        on_enter={"favor": +15, "lucidez": +6, "corrupcion": -4},
        set_flags=["canto_al_sacerdote", "rechazo_mascara"],
        paths=[P("Salir del templo", "act3_convergencia_profunda", style="primary")],
    ))

    nodes.append(N(
        "act3_templo_provocar",
        act=A, zone="Templo Sumergido — Provocación",
        tone="horror",
        text=(
            "Lo provocas hasta que explota. No tiene cara, pero tiene "
            "algo peor debajo: una máscara de máscaras. Gritas más "
            "fuerte que él. Se repliega. Pero ahora te conoce."
        ),
        on_enter={"voluntad": +8, "corrupcion": +6, "lore": +8},
        set_flags=["provoco_al_caos", "nyarlathotep_te_odia"],
        paths=[P("Salir del templo", "act3_convergencia_profunda", style="primary")],
    ))

    nodes.append(N(
        "act3_templo_frescos",
        act=A, zone="Templo Sumergido — Frescos",
        tone="awe",
        text=(
            "La lámpara ilumina frescos en los muros que el agua había "
            "escondido. Cuentan, con imágenes, la verdad sobre los "
            "Dioses Blandos y sobre quien los usa como máscaras. "
            "Lo que ves cambia lo que vas a pedir en Kadath."
        ),
        on_enter={"lore": +15, "lucidez": -3},
        set_flags=["leyo_frescos"],
        give_item="plano_kadath",
        paths=[
            P("Acercarse al altar con lo que sabes", "act3_templo_altar",
              style="primary",
              conditions={"lacks_flag": "hablo_con_sacerdote"}),
            P("Salir sin enfrentar al sacerdote", "act3_convergencia_profunda",
              style="info"),
        ],
    ))

    # ── Convergencia ──────────────────────────────────────────────────────
    nodes.append(N(
        "act3_convergencia_profunda",
        act=A, zone="Profundidades — Convergencia",
        tone="calm",
        text=(
            "Todos los caminos del subsuelo se juntan aquí. Una escalera "
            "en espiral sube hacia un aire más fino. Es la ruta al "
            "**Ascenso**. Al final, está Kadath."
        ),
        on_enter={"lucidez": +3, "voluntad": +3},
        character_dialogue={
            "aris":     "todos los caminos convergen aquí. al final está kadath",
            "law":      "todos los caminos se juntan aquí... la escalera sube hacia Kadath. ya casi bro",
            "haru":     "todos los caminos se juntan aquí, una espiral sube hacia Kadath, ya casi mano",
            "elyko":    "todos los caminos convergen. escalera en espiral. arriba esta Kadath.",
            "xoft":     "todos los caminos se juntan aca. arriba esta Kadath. VAMOS MANO",
            "xokram":   "Pues ya, todos los caminos llevan arriba, algo es algo",
            "daraziel": "Escalera en espiral hacia arriba. Todos los caminos convergen aquí. Limpio y simétrico.",
        },
        paths=[
            P("Subir la espiral hacia Kadath", "act4_ascenso_inicio",
              style="primary"),
            P("Volver a revisitar algo antes de subir", "act3_hub_profundidades",
              style="secondary"),
        ],
    ))

    return nodes


def build_act4(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 4
    nodes: List[Dict[str, Any]] = []

    nodes.append(N(
        "act4_ascenso_inicio",
        act=A, zone="El Ascenso — Base del Monte",
        tone="awe",
        text=(
            "La espiral termina en la falda del **Monte Throk**, al pie "
            "de la Desconocida Kadath. El aire aquí es tan limpio que "
            "corta. Arriba, muy arriba, las torres de piedra negra "
            "coronan la cumbre. Debajo de ti, la vida entera que "
            "llevabas ya no parece real del todo."
        ),
        on_enter={},
        character_dialogue={
            "aris":     "el aire corta. arriba las torres de piedra negra. esto es real",
            "law":      "MANO el aire corta de lo limpio que es y arriba están las torres negras ES REAL",
            "haru":     "el aire corta de lo limpio, arriba las torres negras, abajo mi vida ya no parece real",
            "elyko":    "Monte Throk. aire que corta. torres negras arriba. tu vida ya no parece real.",
            "xoft":     "EL AIRE CORTA MANO. arriba estan las torres negras. ya no hay vuelta",
            "xokram":   "Kadath arriba y mi vida abajo ya no parece real, gg supongo",
            "daraziel": "Torres de piedra negra en la cumbre. El contraste con el aire limpio es muy peak.",
        },
        paths=[
            P("Subir por el Sendero Iluminado", "act4_sendero_luz",
              style="success"),
            P("Subir por el Sendero de Sombras", "act4_sendero_sombras",
              style="warning"),
            P("Subir a lomos de un Shantak", "act4_shantak_invocacion",
              style="info",
              conditions={"corrupcion_min": 35}),
            P("Buscar el Campamento del Anciano primero", "act4_campamento",
              style="secondary"),
        ],
    ))

    # ── Campamento del Anciano de Un Ojo (NPC del servidor: JC) ───────────
    nodes.append(N(
        "act4_campamento",
        act=A, zone="El Ascenso — Campamento del Anciano de Un Ojo",
        tone="calm",
        text=(
            "A mitad de camino, un hombre increíblemente viejo te invita "
            "a sentarte junto a su fogata. Le dicen **JC**. Tiene la piel "
            "de pergamino, un solo ojo abierto, y las manos le tiemblan "
            "como si cada gesto costara un invierno entero. Nadie debería "
            "haber vivido tanto en este sueño — y sin embargo, ahí está.\n\n"
            "Te ofrece té con esfuerzo visible. Siete tazas vacías frente "
            "a él, y una octava que te acerca.\n\n"
            "— *A ver, XDD, tú eres el siguiente.* La voz le raspa al "
            "salir, como metal oxidado. Señala las siete tazas. — *Siete "
            "viajeros pasan por aquí, tarde o temprano. Yo... yo he visto "
            "pasar cientos. Me quedé. El otro ojo me lo saqué yo mismo "
            "hace tantas lunas que ya no recuerdo si era mío. A ti te va "
            "a tocar decidir cuánto ver. Antes de que sea tarde. Como me "
            "pasó a mí.*"
        ),
        on_enter={},
        primary_npc="jc_anciano_un_ojo",
        is_ally_npc=True,
        character_dialogue={
            "aris":     "el viejo es literal una reliquia. tiene un solo ojo y tiembla entero",
            "law":      "este señor es el viejo más viejo que he visto y le tiembla la taza bro cuantos años tiene",
            "haru":     "mano este abuelo tiene siglos y aún sirve té, peak respect de verdad",
            "elyko":    "aver, JC: edad estimada fuera del percentil humano. high-value NPC.",
            "xoft":     "va, el abuelo respira con trabajo pero el ojo que le queda corta como cuchilla",
            "xokram":   "Este viejo vio más tratos que yo en toda mi vida, lo respeto mano",
            "daraziel": "El viejo tiene la piel de pergamino y un solo ojo. Su silueta es muy expresiva.",
        },
        ability_hints={
            "XOFT": "si lo provocas sobre el ojo perdido, te cuenta lo que vio con él — aunque le duele hablar.",
        },
        paths=[
            P("Escuchar su historia (cuesta MEMORIA real)", "act4_campamento_historia",
              style="primary",
              conditions={"lacks_flag": "jc_interaccion"},
              effects={"lore": +8, "memoria": -6, "voluntad": +2},
              set_flags=["jc_interaccion"]),
            P("Contarle tu viaje (cuesta LORE por compartir)", "act4_campamento_confesion",
              style="info",
              conditions={"lacks_flag": "jc_interaccion"},
              effects={"memoria": +6, "lore": -3, "voluntad": +4},
              set_flags=["jc_interaccion"]),
            P("Pedir un consejo concreto (cobra FAVOR)", "act4_campamento_consejo",
              style="success",
              conditions={"lacks_flag": "jc_interaccion"},
              effects={"lore": +5, "favor": -5},
              set_flags=["jc_interaccion"]),
            P("Sacarte un ojo tú también (muy crudo)", "act4_campamento_ojo_sacrificado",
              style="danger",
              conditions={"lacks_flag": "jc_interaccion"},
              effects={"voluntad": -10, "lore": +15, "corrupcion": +8},
              set_flags=["jc_interaccion"]),
            P("Volver al sendero sin hablar", "act4_ascenso_inicio",
              style="secondary",
              effects={"favor": -2}),
        ],
    ))

    nodes.append(N(
        "act4_campamento_ojo_sacrificado",
        act=A, zone="Campamento — Un Ojo Menos",
        tone="horror",
        text=(
            "Le dices a JC que quieres ver lo que él dejó de ver. El viejo "
            "te mira con su único ojo — un ojo que ha visto más lunas que "
            "cualquier ser vivo debería. Asiente con tristeza, saca un "
            "cuchillo pequeño muy limpio con manos que tiemblan tanto que "
            "no sabes cómo puede cortar algo. Te lo pasa.\n\n"
            "Lo haces tú mismo. JC cose la herida en silencio — sus dedos "
            "artríticos, milagrosamente firmes para esto y solo para esto. "
            "Cuando abres el ojo que te queda, ves TODO lo que antes estaba "
            "en el margen. Nada se olvida. Nada se desdibuja.\n\n"
            "— *No voy a decirte que lo siento* — murmura JC, y la voz le "
            "sale como de un pozo seco — *Me lo pediste. Y yo te lo di. "
            "Sube. Ya ves lo que ven pocos. Yo llevo aquí tanto que ya no "
            "sé si sigo vivo o si soy un eco. Pero tú todavía puedes subir.*"
        ),
        on_enter={},
        give_item="ojo_perdido",
        set_flags=["dio_un_ojo", "sabe_verdad_trono"],
        npc_trust={"jc_anciano_un_ojo": +40},
        character_dialogue={
            "aris":     "no. no debería haber aceptado ver eso. no debí",
            "law":      "NOOOOOOOOOO el cuchillo bro NO PUEDO VER ESTO porque siempre me pasan estas cosas",
            "haru":     "MANO LE DIJE QUE QUERÍA VER Y SACÓ UN CUCHILLO, no no no putamadre",
            "elyko":    "un ojo menos. ahora ves lo que el dejo de ver. no se si vale.",
            "xoft":     "KJDSALKJDSA SE SACO EL OJO CON UN CUCHILLO nmms yo no hago eso ni loco",
            "xokram":   "Un ojo por información, mano eso es carísimo la verdad",
            "daraziel": "Mano eso es demasiado. Pero entiendo la lógica, sacrificar algo para ver otra cosa.",
        },
        paths=[
            P("Seguir al sendero viendo todo", "act4_ascenso_inicio",
              style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_campamento_historia",
        act=A, zone="Campamento — Historia de JC",
        tone="awe",
        text=(
            "JC tose antes de hablar — un tos seca, de siglos. Le tiembla "
            "la mandíbula. Tarda en encontrar las palabras, como si las "
            "hubiera perdido entre tantas lunas.\n\n"
            "— *Yo también subí. Llegué al Trono. No me dieron lo que "
            "quería. Me dieron lo que era. Y ahora sirvo té a los que "
            "suben. Es más de lo que parece. Menos de lo que quisiera.*\n\n"
            "Se mira las manos — nudosas, manchadas, temblando. — *Llevo "
            "aquí tanto que ya no sé si soy parte del sueño o si el sueño "
            "es parte de mí. Impresionante que siga vivo, ¿no? A veces "
            "yo también me sorprendo.*"
        ),
        on_enter={},
        primary_npc="jc_anciano_un_ojo",
        is_ally_npc=True,
        set_flags=["sabe_verdad_trono", "escucho_historia_jc"],
        give_item="taza_del_anciano",
        paths=[P("Seguir al sendero", "act4_ascenso_inicio", style="primary")],
    ))

    nodes.append(N(
        "act4_campamento_confesion",
        act=A, zone="Campamento — Confesión a JC",
        tone="calm",
        text=(
            "Le cuentas todo. Él no interrumpe — quizá porque le cuesta "
            "hablar, quizá porque ha oído mil historias como la tuya. "
            "Cuando terminas, asiente con un crujido de cuello que suena "
            "a madera vieja.\n\n"
            "— *Cada uno de ustedes tiene su razón. La tuya es buena. "
            "Quizá demasiado. Ten cuidado con querer demasiado.*\n\n"
            "Se recuesta contra la roca. Cierra el ojo. Por un momento "
            "crees que se murió — pero no, respira. Apenas. Es milagroso "
            "que siga respirando."
        ),
        on_enter={},
        primary_npc="jc_anciano_un_ojo",
        is_ally_npc=True,
        set_flags=["confeso_al_anciano"],
        paths=[P("Seguir al sendero", "act4_ascenso_inicio", style="primary")],
    ))

    nodes.append(N(
        "act4_campamento_consejo",
        act=A, zone="Campamento — Consejo de JC",
        tone="discovery",
        text=(
            "JC se inclina hacia ti con esfuerzo — le crujen las rodillas, "
            "la espalda, algo dentro del pecho. Habla bajo, como si cada "
            "palabra le costara un día de vida que ya no tiene.\n\n"
            "— *En la cumbre hay dos mesas. En una están los Dioses "
            "Blandos. En la otra, alguien con forma de dios. Escucha. "
            "Los dioses no hablan primero. Nunca. Lo que hable primero "
            "no será un dios.*\n\n"
            "Se echa atrás, agotado. — *Eso es todo lo que puedo darte. "
            "Llevo tantas lunas guardando ese consejo que ya pesa más "
            "que yo.*"
        ),
        on_enter={},
        primary_npc="jc_anciano_un_ojo",
        is_ally_npc=True,
        set_flags=["sabe_test_nyarlathotep"],
        paths=[P("Seguir al sendero", "act4_ascenso_inicio", style="primary")],
    ))

    # ── Sendero Iluminado ─────────────────────────────────────────────────
    nodes.append(N(
        "act4_sendero_luz",
        act=A, zone="El Ascenso — Sendero Iluminado",
        tone="awe",
        text=(
            "El sendero de luz es el más largo pero el más seguro. Cada "
            "piedra canta un tono distinto al pisarla. Hay rezos tallados "
            "en las rocas."
        ),
        on_enter={},
        paths=[
            P("Detenerse a leer los rezos", "act4_rezos_piedra", style="info",
              effects={"lore": +6, "favor": +4}),
            P("Seguir subiendo", "act4_cima_antesala", style="primary",
              effects={"lucidez": +3}),
        ],
    ))

    nodes.append(N(
        "act4_rezos_piedra",
        act=A, zone="Sendero — Rezos en Piedra",
        tone="awe",
        text=(
            "Los rezos son viejos. Algunos son para dioses que ya no "
            "existen. Te aprendes uno. Puede que lo necesites pronto. "
            "Decirlo en voz alta aquí cuesta voz y humedad — el sendero "
            "exige algo cada vez que lo compartes."
        ),
        on_enter={"favor": +5, "lore": +3, "lucidez": -3, "memoria": -2},
        give_item="rezo_antiguo",
        set_flags=["aprendio_rezo"],
        paths=[P("Seguir subiendo", "act4_cima_antesala", style="primary")],
    ))

    # ── Sendero de Sombras ────────────────────────────────────────────────
    nodes.append(N(
        "act4_sendero_sombras",
        act=A, zone="El Ascenso — Sendero de Sombras",
        tone="tense",
        text=(
            "El sendero de sombras es más corto pero más peligroso. El "
            "aire huele a ozono. Voces en los oídos. Nadie en los ojos."
        ),
        on_enter={"lucidez": -5, "corrupcion": +5, "voluntad": +3},
        paths=[
            P("Enfrentar las voces con voluntad", "act4_voces_enfrentadas",
              style="warning",
              conditions={"voluntad_min": 40},
              effects={"voluntad": +6, "lore": +6}),
            P("Taparse los oídos y subir", "act4_cima_antesala",
              style="primary",
              effects={"lucidez": -3, "corrupcion": +3}),
            P("Escuchar con calma", "act4_voces_escuchadas",
              style="info",
              effects={"lore": +10, "corrupcion": +5}),
        ],
    ))

    nodes.append(N(
        "act4_voces_enfrentadas",
        act=A, zone="Sendero Sombrío — Voces Enfrentadas",
        tone="awe",
        text=(
            "Les gritas que se callen. Una por una, las voces se apagan. "
            "La última te dice, muy bajito, antes de irse: — *te estamos "
            "esperando arriba.*"
        ),
        on_enter={"voluntad": +10, "lore": +5, "corrupcion": -3},
        set_flags=["enfrento_voces"],
        paths=[P("Seguir", "act4_cima_antesala", style="primary")],
    ))

    nodes.append(N(
        "act4_voces_escuchadas",
        act=A, zone="Sendero Sombrío — Voces Escuchadas",
        tone="horror",
        text=(
            "Escuchas. Dicen cosas útiles entre cosas atroces. Aprendes "
            "tres nombres verdaderos y olvidas el tuyo un rato. El "
            "sendero se acorta como recompensa."
        ),
        on_enter={"lore": +12, "memoria": -8, "corrupcion": +6},
        set_flags=["escucho_voces_oscuras"],
        paths=[P("Seguir", "act4_cima_antesala", style="primary")],
    ))

    # ── Shantak ───────────────────────────────────────────────────────────
    nodes.append(N(
        "act4_shantak_invocacion",
        act=A, zone="Monte Throk — Invocación del Shantak",
        tone="horror",
        text=(
            "Invocas a un **Shantak**, una bestia alada con cabeza de "
            "caballo y ojos humanos. Te permite subir si prometes "
            "sacrificar algo en la cumbre. Tú decides qué, después. "
            "Pero lo vas a tener que decidir."
        ),
        on_enter={"corrupcion": +8, "lore": +4},
        primary_npc="shantak",
        set_flags=["invoco_shantak", "debe_sacrificio"],
        paths=[
            P("Volar con el Shantak", "act4_vuelo_shantak", style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_vuelo_shantak",
        act=A, zone="Monte Throk — Vuelo",
        tone="awe",
        text=(
            "El vuelo es rápido y terrible. La cumbre está cada vez más "
            "cerca. El Shantak te deja en una plataforma de piedra negra "
            "y te mira esperando su sacrificio."
        ),
        on_enter={"lore": +4, "corrupcion": +4},
        paths=[
            P("Sacrificar un recuerdo importante", "act4_cima_antesala",
              style="warning", effects={"memoria": -15, "favor": -4}),
            P("Sacrificar tu Lore", "act4_cima_antesala",
              style="info", effects={"lore": -15, "corrupcion": -3}),
            P("Rechazar el sacrificio (huir)", "act4_cima_antesala_huida",
              style="danger", effects={"voluntad": +5, "corrupcion": +10}),
        ],
    ))

    nodes.append(N(
        "act4_cima_antesala_huida",
        act=A, zone="Cima — Antesala (llegaste huyendo)",
        tone="horror",
        text=(
            "Llegas a la antesala de la cumbre huyendo del Shantak. Su "
            "grito te persigue. Una parte de ti sabe que la deuda no "
            "se cancela; sólo se pospone."
        ),
        on_enter={"corrupcion": +5},
        set_flags=["deuda_shantak"],
        paths=[P("Cruzar a la cumbre", "act5_cumbre_trono", style="primary")],
    ))

    # ── Antesala de la Cima ───────────────────────────────────────────────
    nodes.append(N(
        "act4_cima_antesala",
        act=A, zone="Cima — Antesala",
        tone="awe",
        text=(
            "La antesala es una plaza circular con siete puertas cerradas "
            "alrededor y una abierta en el centro, que da al trono. Una "
            "voz sin boca dice: — *Pasa sólo quien sepa por qué viene.*"
        ),
        on_enter={},
        character_dialogue={
            "aris":     "siete puertas cerradas y una abierta. pasa quien sepa por qué viene",
            "law":      "siete puertas cerradas y una voz sin boca dice que pase... dios que hago chicos",
            "haru":     "una voz sin boca dice que pase solo quien sepa por qué viene, avr déjame pensar xd",
            "elyko":    "7 puertas cerradas. 1 abierta. pasa solo quien sepa por que viene.",
            "xoft":     "pasa solo quien sepa por que viene?? YO VINE A PELEAR CON DIOS",
            "xokram":   "Pasa solo quien sepa por qué viene, pues vengo a ver qué ofrecen",
            "daraziel": "Plaza circular con siete puertas cerradas. La simetría radial es perfecta.",
        },
        paths=[
            P("«Vengo a pedir lo que soy»", "act5_cumbre_trono",
              style="success",
              conditions={"has_flag": "confeso_al_anciano"},
              effects={"voluntad": +5, "favor": +5}),
            P("«Vengo a pedir lo que quiero»", "act5_cumbre_trono",
              style="primary", effects={"corrupcion": +4}),
            P("«Vengo porque no tenía a dónde más ir»", "act5_cumbre_trono",
              style="info", effects={"memoria": +5}),
            P("«No voy a pedir nada»", "act5_cumbre_trono",
              style="warning", effects={"voluntad": +8, "favor": +4}),
        ],
    ))

    return nodes


def build_act5(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 5
    nodes: List[Dict[str, Any]] = []

    nodes.append(N(
        "act5_cumbre_trono",
        act=A, zone="La Cumbre — Sala del Trono",
        tone="awe",
        text=(
            "Entras a la sala del trono. Hay dos mesas. En una, siete "
            "figuras envueltas en niebla dorada: los **Dioses Blandos**. "
            "En la otra, una sola figura alta y delgada que sonríe "
            "demasiado: te saluda con educación que te hiela: "
            "**Nyarlathotep**, el Caos Reptante.\n\n"
            "Nadie ha hablado todavía. El silencio es palpable. "
            "Tú vas a hablar primero, o vas a esperar."
        ),
        on_enter={"lore": +6},
        primary_npc="nyarlathotep",
        character_dialogue={
            "aris":     "nyarlathotep sonríe demasiado. los dioses blandos no dicen nada. estoy helada",
            "law":      "Nyarlathotep me saluda con educación que me HIELA bro no me gusta su sonrisa LPTM",
            "haru":     "Nyarlathotep me saluda con una educación que me hiela, este tipo no es normal mano",
            "elyko":    "Dioses Blandos en una mesa. Nyarlathotep en la otra. sonrie demasiado.",
            "xoft":     "Nyarlathotep sonrie demasiado. te voy a borrar esa sonrisa maldito",
            "xokram":   "Dos mesas negociando a la vez, esto es peak oportunidad pije",
            "daraziel": "Dos mesas, niebla dorada contra una figura alta. El contraste visual es increíble.",
        },
        ability_hints={
            "ARIS":     "Nyarlathotep habla primero si le hablas. Los dioses no.",
            "ELYKO":    "Nyarlathotep habla primero si le hablas. Los dioses no.",
            "DARAZIEL": "la mesa de los dioses está un plano más alto. la otra está en el mismo nivel que tú.",
        },
        paths=[
            P("Hablar primero (tomar la iniciativa)", "act5_hablaste_primero",
              style="warning", effects={"corrupcion": +6, "voluntad": -4}),
            P("Esperar a que hablen ellos", "act5_esperas",
              style="primary",
              conditions={"has_flag": "sabe_test_nyarlathotep"},
              effects={"voluntad": +4, "favor": +6},
              show_locked=True),
            P("Esperar igualmente, intuyendo", "act5_esperas",
              style="primary", effects={"voluntad": +2}),
            P("Arrodillarte ante Nyarlathotep", "act5_sumision_caos",
              style="danger",
              conditions={"corrupcion_min": 50},
              effects={"corrupcion": +15, "favor": -15},
              show_locked=True),
            P("Cantar la canción de los ghouls", "act5_canto_ghoul",
              style="success",
              conditions={"has_item": "cancion_ghoul"},
              show_locked=True),
            P("Rezar el rezo antiguo", "act5_rezo_antiguo",
              style="success",
              conditions={"has_item": "rezo_antiguo"},
              show_locked=True),
        ],
    ))

    # ── Transiciones del trono ────────────────────────────────────────────
    nodes.append(N(
        "act5_hablaste_primero",
        act=A, zone="Cumbre — Primer Error",
        tone="horror",
        text=(
            "Hablas primero. Nyarlathotep te responde; los Dioses Blandos "
            "no se inmutan. Ya caíste en la trampa del anciano. La figura "
            "alta te rodea con palabras dulces. Cada frase te pesa un "
            "poco más."
        ),
        on_enter={"corrupcion": +10, "favor": -5, "voluntad": -3},
        set_flags=["cayo_en_trampa_nyar"],
        paths=[
            P("Arrepentirte y callar", "act5_esperas",
              style="primary", effects={"voluntad": +4}),
            P("Seguirle el juego", "act5_sumision_caos",
              style="danger", effects={"corrupcion": +10}),
            P("Cortarlo con el rezo", "act5_rezo_antiguo",
              style="success",
              conditions={"has_item": "rezo_antiguo"},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act5_esperas",
        act=A, zone="Cumbre — Silencio Victorioso",
        tone="awe",
        text=(
            "Esperas. Nyarlathotep sonríe, molesto, y habla; los Dioses "
            "Blandos no. Así sabes cuál es cuál. Cuando por fin uno de "
            "los Dioses Blandos se inclina hacia ti, te pregunta: "
            "— *¿Qué has venido a hacer con esto que sabes?*"
        ),
        on_enter={"voluntad": +8, "favor": +10, "lucidez": +4},
        set_flags=["test_nyar_pasado"],
        paths=[
            P("«Despertar en paz»", "ending_despertar_puro",
              style="success"),
            P("«Quedarme y aprender»", "ending_legado_onirico",
              style="info"),
            P("«Negociar un trato justo»", "ending_pacto_mercantil",
              style="info"),
            P("«Terminar mi libro»", "ending_biblioteca_eterna",
              style="info",
              conditions={"has_flag": "libro_listo_para_terminar"},
              show_locked=True),
            P("«Componer la última canción»", "ending_canto_final",
              style="success",
              conditions={"class_in": ["CANTOR"], "has_item": "partitura_celeste"},
              show_locked=True),
            P("«Dibujar el mapa verdadero»", "ending_arquitectura",
              style="success",
              conditions={"class_in": ["CARTOGRAFO"], "has_item": "plano_kadath"},
              show_locked=True),
            P("«Reírme de todo esto»", "ending_carcajada_cosmica",
              style="success",
              conditions={"class_in": ["TRICKSTER"], "voluntad_min": 60},
              show_locked=True),
            P("«Sentarme en el Trono Ghoul»", "ending_rey_ghouls",
              style="warning",
              conditions={"has_item": "sello_ghoul", "has_flag": "pacto_ghoul"},
              show_locked=True),
            P("«Cerrar el Gran Negocio»", "ending_gran_negocio",
              style="success",
              conditions={"class_in": ["NEGOCIADOR"], "min_contracts": 2},
              show_locked=True),
            P("«…ya no recuerdo por qué vine»", "ending_olvido",
              style="warning",
              conditions={"memoria_max": 25},
              show_locked=True),
            P("«Dejarse caer hacia el centro»", "ending_vacio",
              style="danger",
              conditions={"voluntad_max": 15},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act5_sumision_caos",
        act=A, zone="Cumbre — Sumisión al Caos",
        tone="horror",
        text=(
            "Te arrodillas ante Nyarlathotep. Su mano cae, ligera, sobre "
            "tu cabeza. Te corona. Sientes la máscara del Caos cerrarse "
            "sobre tu cara desde dentro hacia afuera. El Trono te recibe."
        ),
        on_enter={"corrupcion": +25, "favor": -25, "voluntad": -10},
        set_flags=["acepto_trono_caos"],
        paths=[
            P("Aceptar la corona", "ending_trono_caos", style="danger"),
            P("Arrepentirte en el último segundo", "ending_vacio",
              style="warning",
              conditions={"voluntad_min": 30},
              effects={"voluntad": -30},
              show_locked=True),
        ],
    ))

    nodes.append(N(
        "act5_canto_ghoul",
        act=A, zone="Cumbre — Canción Ghoul",
        tone="awe",
        text=(
            "Cantas la canción que te enseñaron los ghouls. Nyarlathotep "
            "retrocede un paso por primera vez en su existencia. Los "
            "Dioses Blandos, por un instante, parecen humanos. Uno de "
            "ellos llora."
        ),
        on_enter={"favor": +15, "lucidez": +6, "corrupcion": -6},
        set_flags=["canto_cancion_ghoul_ante_dioses"],
        paths=[P("Seguir", "act5_esperas", style="primary")],
    ))

    nodes.append(N(
        "act5_rezo_antiguo",
        act=A, zone="Cumbre — Rezo Antiguo",
        tone="awe",
        text=(
            "Rezas el rezo aprendido en el sendero. Nyarlathotep se "
            "quiebra un segundo. Los Dioses Blandos levantan la cabeza: "
            "por primera vez, alguien les reza a ellos con su nombre "
            "verdadero."
        ),
        on_enter={"favor": +15, "voluntad": +6, "corrupcion": -5},
        set_flags=["rezo_antiguo_pronunciado"],
        paths=[P("Seguir", "act5_esperas", style="primary")],
    ))

    return nodes


def build_endings(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    """12 finales — ninguno temprano, todos accesibles desde el Acto 5."""
    A = 5
    nodes: List[Dict[str, Any]] = []

    # 1. Trono del Caos — aceptaste la corona de Nyarlathotep
    nodes.append(N(
        "ending_trono_caos",
        act=A, zone="FINAL — El Trono del Caos Reptante",
        tone="horror",
        is_ending=True,
        ending_priority=95,
        ending_requires={"has_flag": "acepto_trono_caos"},
        text=(
            "Te sientan en un trono de obsidiana viva. Tus manos dejan "
            "de ser tus manos. Tu voz deja de ser tu voz. Desde ahora "
            "recorres los sueños de otros, entregando máscaras como la "
            "que aceptaste. Eres útil. Eres temible. Ya no eres tú.\n\n"
            "En algún rincón aún despierto del mundo, alguien murmura "
            "tu nombre en vano, y tú, desde el trono, lo escuchas y "
            "sonríes.\n\n"
            "**Final 1 — El Trono del Caos.**"
        ),
        character_dialogue={
            "aris":     "ya no soy yo. mis manos no son mías. esto fue un error",
            "law":      "mis manos ya no son mis manos... ya no soy yo bro NO QUIERO ESTO NOOOOOOOO",
            "haru":     "ya no soy yo, mis manos no son mías, entrego máscaras a otros soñadores, gg todo",
            "elyko":    "tus manos ya no son tuyas. tu voz tampoco. eres util. ya no eres tu.",
            "xoft":     "ya no soy yo. mis manos no son mias. lo perdimos todo 💔🥀",
            "xokram":   "Me dieron poder pero ya no soy yo, pésimo trato la verdad gg",
            "daraziel": "Obsidiana viva como trono. Tus manos dejan de ser tuyas. El diseño es oscuro pero god.",
        },
    ))

    # 2. Despertar Puro — te vas en paz con los Dioses Blandos
    nodes.append(N(
        "ending_despertar_puro",
        act=A, zone="FINAL — Despertar Puro",
        tone="awe",
        is_ending=True,
        ending_priority=80,
        ending_requires={
            "favor_min": 60,
            "corrupcion_max": 40,
            "lacks_flag": "acepto_trono_caos",
        },
        text=(
            "Uno de los Dioses Blandos te toca la frente con un dedo "
            "que no es un dedo. Abres los ojos en tu cama, o lo que "
            "haga las veces de tu cama en el mundo despierto. La luz "
            "entra por la ventana como si no hubiera pasado nada.\n\n"
            "Pero algo pasó. Lo sabes. Y una parte de ti sabe, también, "
            "que puedes volver si quieres. Y que esta vez no tienes que.\n\n"
            "**Final 2 — Despertar Puro.**"
        ),
        character_dialogue={
            "aris":     "desperté en mi cama. algo pasó. lo sé pero no puedo explicarlo",
            "law":      "abrí los ojos en mi cama y la luz entra normal pero SÉ que algo pasó... lo sé 💔",
            "haru":     "abrí los ojos en mi cama como si nada, pero algo pasó y una parte de mi lo sabe",
            "elyko":    "despiertas en tu cama. la luz entra normal. pero algo paso. lo sabes.",
            "xoft":     "abri los ojos en mi cama pero algo cambio adentro mano 💔 lo se",
            "xokram":   "Desperté y algo cambió, no sé qué pagué pero no fue gratis",
            "daraziel": "La luz entra por la ventana como si nada. Pero algo cambió en la composición de todo.",
        },
    ))

    # 3. Legado Onírico — eliges quedarte como soñador
    nodes.append(N(
        "ending_legado_onirico",
        act=A, zone="FINAL — Legado Onírico",
        tone="awe",
        is_ending=True,
        ending_priority=70,
        ending_requires={
            "lore_min": 70,
            "memoria_max": 45,
        },
        text=(
            "Decides quedarte. Tu cuerpo despierto vive sin ti, pero no "
            "se da cuenta: hace lo que hay que hacer, sonríe donde hay "
            "que sonreír. Tú, aquí, viajas de sueño en sueño, y cada "
            "soñador nuevo que baja la escalera de obsidiana encuentra, "
            "sin saberlo, tus huellas en los estratos.\n\n"
            "Eres leyenda para los gatos de Ulthar. Los zoogs te temen. "
            "Los ghouls te saludan. No es poco para alguien que no "
            "llegó a ser rey.\n\n"
            "**Final 3 — Legado Onírico.**"
        ),
        character_dialogue={
            "aris":     "me quedé. mi cuerpo despierto vive sin mí y ni se da cuenta",
            "law":      "me quedé... mi cuerpo vive sin mi pero yo viajo de sueño en sueño para siempre",
            "haru":     "me quedé, mi cuerpo vive sin mi allá afuera, yo viajo de sueño en sueño, es peak",
            "elyko":    "tu cuerpo vive sin ti. tu viajas de sueño en sueño. es un trade.",
            "xoft":     "me quedo aca. mi cuerpo alla que haga lo que quiera yo soy libre",
            "xokram":   "Me quedé, mi cuerpo allá hace lo suyo, aquí hay más que hacer",
            "daraziel": "Quedarte aquí y dejar huellas para los que vienen. Es como firmar tu obra sin nombre.",
        },
    ))

    # 4. Rey de los Ghouls — te ungen rey de la jauría
    nodes.append(N(
        "ending_rey_ghouls",
        act=A, zone="FINAL — Rey de los Ghouls",
        tone="awe",
        is_ending=True,
        ending_priority=85,
        ending_requires={
            "has_flag": "pacto_ghoul",
            "has_item": "sello_ghoul",
        },
        text=(
            "El Rey Ghoul te escupe el hueso una vez más. Esta vez cae "
            "como una corona. La jauría se inclina. Tienes una cripta, "
            "un cetro de fémur y un reino subterráneo que huele a "
            "tumba y a pan tibio.\n\n"
            "A veces, en las noches raras, subes a Ulthar y un gato "
            "muy viejo te reconoce y te deja pasar sin maullar. Es "
            "todo el respeto que un rey puede esperar.\n\n"
            "**Final 4 — Rey de los Ghouls.**"
        ),
        character_dialogue={
            "aris":     "un cetro de fémur y un reino subterráneo. bueno, peor sería nada",
            "law":      "el hueso cayó como corona y todos se inclinaron... SOY REY?? bro que acaba de pasar",
            "haru":     "tengo una corona de hueso y un reino que huele a tumba y a pan tibio xddd",
            "elyko":    "corona de hueso. reino subterraneo. huele a tumba y pan tibio. curioso.",
            "xoft":     "KSJSJAJAJAJAJ SOY REY DE LOS GHOULS con cetro de femur y todo",
            "xokram":   "Rey de un reino que huele a tumba, meh algo es algo supongo",
            "daraziel": "Un hueso como corona, un cetro de fémur. La estética es horrible y hermosa a la vez.",
        },
    ))

    # 5. Gran Negocio — XOKRAM cierra 2+ contratos con el Caos
    nodes.append(N(
        "ending_gran_negocio",
        act=A, zone="FINAL — El Gran Negocio",
        tone="awe",
        is_ending=True,
        ending_priority=88,
        ending_requires={
            "class_in": ["NEGOCIADOR"],
            "min_contracts": 2,
        },
        text=(
            "Cierras un trato con los Dioses Blandos **y** con "
            "Nyarlathotep al mismo tiempo. Nadie entiende cómo. Tú "
            "tampoco del todo. Sales del Trono con tres contratos "
            "firmados, un título honorífico y un porcentaje sobre "
            "todos los sueños que crucen Dylath-Leen.\n\n"
            "Tus hijos, si los tienes, van a ser extraordinariamente "
            "ricos.\n\n"
            "**Final 5 — El Gran Negocio.**"
        ),
        character_dialogue={
            "xokram":   "Tres contratos y un porcentaje, así se cierra mano, peak negocio",
            "aris":     "tres contratos firmados. ni yo entiendo cómo. pero funcionó",
            "law":      "COMO cerró trato con los DOS a la vez?? ni él entiende bro ES GOOOOOOOOOOD",
            "haru":     "JAJAKAKAKAJA cerré trato con los dos bandos a la vez y nadie entiende cómo, ni yo",
            "elyko":    "trato con ambas mesas a la vez. nadie entiende como. tu tampoco.",
            "xoft":     "KSJSJAJAJAJAJ cerre trato con los dos bandos ni yo entiendo como GG",
            "daraziel": "Tres contratos firmados y un porcentaje. Mano eso es tener visión de negocio onírico.",
        },
    ))

    # 6. Canto Final — LAW cierra el juego cantando
    nodes.append(N(
        "ending_canto_final",
        act=A, zone="FINAL — El Canto Final",
        tone="awe",
        is_ending=True,
        ending_priority=92,
        ending_requires={
            "class_in": ["CANTOR"],
            "favor_min": 70,
            "has_item": "partitura_celeste",
        },
        text=(
            "Cantas. Nyarlathotep se retira, por primera vez en su larga "
            "historia, sin haber convencido a nadie. Los Dioses Blandos "
            "cantan contigo la segunda estrofa. El mundo despierto y el "
            "mundo soñado se sincronizan por el tiempo exacto que dura "
            "la canción.\n\n"
            "Cuando terminas, todo vuelve a ser como era. Pero tu "
            "canción queda grabada en el aire de Kadath, y los próximos "
            "soñadores van a oírla sin saber que es tuya.\n\n"
            "**Final 6 — El Canto Final.**"
        ),
        character_dialogue={
            "law":      "canté y Nyarlathotep SE FUE bro los dioses cantan conmigo ESTOY LLORANDO",
            "aris":     "nyarlathotep se fue sin convencer a nadie. primera vez en su historia",
            "haru":     "cantaron y Nyarlathotep se fue ofendido, nunca pensé que una canción pudiera tanto",
            "elyko":    "Nyarlathotep se retira. primera vez. el canto fue mas fuerte. peak.",
            "xoft":     "Nyarlathotep se fue OFENDIDO por una cancion mano ESTO ES PEAK 🥀",
            "xokram":   "Mano la canción los espantó a todos, eso no tiene precio pije",
            "daraziel": "La canción sincroniza los dos mundos. Es como cuando la música y la animación encajan.",
        },
    ))

    # 7. Biblioteca Eterna — ARIS lee el libro final y se queda
    nodes.append(N(
        "ending_biblioteca_eterna",
        act=A, zone="FINAL — Biblioteca Eterna",
        tone="awe",
        is_ending=True,
        ending_priority=90,
        ending_requires={
            "class_in": ["LECTORA"],
            "lore_min": 80,
            "has_flag": "libro_listo_para_terminar",
        },
        text=(
            "Abres tu libro de Sarkomand. Con la pluma que siempre tuviste "
            "sin saberlo, escribes la última página. Termina: *«Y el "
            "soñador, al terminar este libro, se convierte en bibliotecario "
            "de los que vienen».*\n\n"
            "La sala del trono se desvanece. Despiertas en una biblioteca "
            "infinita donde cada libro es un soñador. Algún día le "
            "tocará a alguien escribir el último renglón sobre ti. Hasta "
            "entonces, catalogas. Lees. Esperas.\n\n"
            "**Final 7 — La Biblioteca Eterna.**"
        ),
        character_dialogue={
            "aris":     "el soñador se convierte en bibliotecario. tiene sentido",
            "law":      "escribí la última página y ahora soy bibliotecario de los que vienen... es hermoso 💔",
            "haru":     "escribí la última página y ahora soy bibliotecario de los que vienen, suena bien mano",
            "elyko":    "el soñador se convierte en bibliotecario. ciclo cerrado. es elegante.",
            "xoft":     "escribi la ultima pagina y ahora soy bibliotecario eterno. god",
            "xokram":   "Bibliotecario eterno suena a chamba sin paga, pero bueno gg",
            "daraziel": "Bibliotecario de los que vienen. Es como ser el que cuida el archivo de todo esto.",
        },
    ))

    # 8. Arquitectura Perfecta — DARAZIEL redibuja Kadath
    nodes.append(N(
        "ending_arquitectura",
        act=A, zone="FINAL — Arquitectura Perfecta",
        tone="awe",
        is_ending=True,
        ending_priority=90,
        ending_requires={
            "class_in": ["CARTOGRAFO"],
            "lore_min": 65,
            "has_item": "plano_kadath",
        },
        text=(
            "Despliegas el plano de Kadath y, con calma, lo corriges. "
            "Nyarlathotep, que lee por encima de tu hombro, frunce algo "
            "que podría llamarse el ceño. Los Dioses Blandos se inclinan "
            "y firman tu enmienda. Desde ahora la geometría del sueño es "
            "distinta. Los próximos soñadores bajarán por una escalera "
            "que tú rediseñaste.\n\n"
            "Nadie sabrá que fuiste tú. Tú sí.\n\n"
            "**Final 8 — Arquitectura Perfecta.**"
        ),
        character_dialogue={
            "daraziel": "Corregir el plano de Kadath. Obviamente la geometría del sueño necesitaba ajustes.",
            "aris":     "corrigió la geometría del sueño. los ángulos ahora son distintos",
            "law":      "corrigió el plano de Kadath y los dioses FIRMARON bro eso es poder de verdad",
            "haru":     "corrigió el plano de Kadath y los dioses firmaron, la geometría del sueño cambió",
            "elyko":    "corregiste el plano de Kadath. la geometria del sueño cambio. permanente.",
            "xoft":     "corregi la geometria del sueño y los dioses FIRMARON. osea gane",
            "xokram":   "Corrigieron la geometría del sueño, eso sí es una jugada god",
        },
    ))

    # 9. Carcajada Cósmica — HARU se ríe y el Caos se rinde
    nodes.append(N(
        "ending_carcajada_cosmica",
        act=A, zone="FINAL — La Carcajada Cósmica",
        tone="awe",
        is_ending=True,
        ending_priority=88,
        ending_requires={
            "class_in": ["TRICKSTER"],
            "voluntad_min": 55,
            "corrupcion_max": 45,
        },
        text=(
            "Miras a Nyarlathotep. Miras a los Dioses Blandos. Miras el "
            "trono. Te da risa. Una risa larga, honesta, de esas que te "
            "doblan en dos. Ríes tanto que Nyarlathotep no sabe qué hacer "
            "con esa risa: no hay discurso contra la carcajada.\n\n"
            "Se va, ofendido. Los Dioses Blandos ríen contigo, por "
            "primera vez desde hace cien mil sueños. Y cuando despiertas, "
            "te sigues riendo. En el espejo, tu cara ya no asusta.\n\n"
            "**Final 9 — La Carcajada Cósmica.**"
        ),
        character_dialogue={
            "haru":     "JAJAKAJAKAKAJAJA me dio risa y Nyarlathotep no supo qué hacer, se fue ofendido gg",
            "aris":     "se fue ofendido. no hay discurso contra una carcajada honesta",
            "law":      "JAJAJAJAJAJAJA bro se fue OFENDIDO porque nos reímos ES LO MEJOR QUE HE VISTO",
            "elyko":    "te dio risa. honesta. Nyarlathotep no supo que hacer. se fue. gg.",
            "xoft":     "KJSADLKSJADLJK ME RIO EN LA CARA DE DIOS y se fue ofendido GG",
            "xokram":   "Se fue ofendido por una risa mano, gratis y efectivo jojojo",
            "daraziel": "La risa es la mejor respuesta. No hay discurso contra una carcajada honesta, es peak.",
        },
    ))

    # 10. Pacto Mercantil — memoria alta + negociación equilibrada
    nodes.append(N(
        "ending_pacto_mercantil",
        act=A, zone="FINAL — Pacto Mercantil",
        tone="calm",
        is_ending=True,
        ending_priority=60,
        ending_requires={
            "memoria_min": 55,
            "favor_min": 40,
            "corrupcion_max": 60,
        },
        text=(
            "Negocias con las dos mesas a la vez. Un trato sensato: "
            "te dejan volver, pero te quedas con una deuda pequeña que "
            "pagarás en los años venideros sin darte cuenta. No es "
            "gratis. Pero tampoco es caro. Es un trato justo.\n\n"
            "Cuando despiertes, no vas a recordar los detalles; sólo "
            "una sensación de haber firmado algo. Con el tiempo, "
            "aprenderás a vivir con eso.\n\n"
            "**Final 10 — Pacto Mercantil.**"
        ),
        character_dialogue={
            "aris":     "un trato justo. no es gratis pero tampoco es caro. es razonable",
            "law":      "un trato justo... no es gratis pero tampoco caro. cuando despierte no voy a recordar 💔",
            "haru":     "un trato justo, no gratis pero tampoco caro, cuando despierte no recordaré nada",
            "elyko":    "deuda pequeña. no es gratis pero no es caro. trato justo en realidad.",
            "xoft":     "un trato justo con deuda chiquita. no es gratis pero tampoco caro va",
            "xokram":   "Deuda chiquita a largo plazo, la verdad es un trato decente",
            "daraziel": "Un trato justo donde nadie pierde demasiado. Está bien, es equilibrado.",
        },
    ))

    # 11. Olvido — memoria muy baja, despertar sin recuerdos
    nodes.append(N(
        "ending_olvido",
        act=A, zone="FINAL — El Gran Olvido",
        tone="horror",
        is_ending=True,
        ending_priority=75,
        ending_requires={"memoria_max": 20},
        text=(
            "No recuerdas tu nombre. No recuerdas por qué subiste. No "
            "recuerdas a quien dejaste en el mundo despierto. Los Dioses "
            "Blandos, que no son crueles, te devuelven al mundo con "
            "gentileza. Caminas por la calle como quien no entiende del "
            "todo dónde está.\n\n"
            "Con el tiempo, inventas una vida nueva sobre la que olvidaste. "
            "Es más sencilla. A veces, mirando un atardecer, lloras sin "
            "saber por qué. Y eso también es bueno.\n\n"
            "**Final 11 — El Gran Olvido.**"
        ),
        character_dialogue={
            "aris":     "no recuerdo mi nombre. no recuerdo por qué subí. esto es lo peor",
            "law":      "no recuerdo mi nombre... no recuerdo porque subí... bro porque me hicieron esto 💔",
            "haru":     "no recuerdo mi nombre ni por qué subí, camino por la calle sin entender dónde estoy",
            "elyko":    "no recuerdas tu nombre. ni por que subiste. los dioses te devuelven.",
            "xoft":     "no me acuerdo mi nombre ni porque subi. lo perdimos todo mano 💔🥀",
            "xokram":   "No recuerdo nada y camino como si nada, negreada histórica",
            "daraziel": "No recuerdas nada. Caminas sin entender dónde estás. Es como perder el archivo.",
        },
    ))

    # 12. Vacío — voluntad nula en la cumbre → caída a Azathoth
    nodes.append(N(
        "ending_vacio",
        act=A, zone="FINAL — El Vacío de Azathoth",
        tone="horror",
        is_ending=True,
        ending_priority=99,  # gana a casi todo si se cumple
        ending_requires={"voluntad_max": 10},
        text=(
            "Tu voluntad se agota. Las dos mesas se desvanecen. El "
            "trono se desvanece. La cumbre se desvanece. Caes hacia un "
            "vacío donde, al centro, un dios idiota danza al sonido de "
            "una flauta: **Azathoth**, el centro de todo y de nada.\n\n"
            "No hay aquí premio ni castigo. Sólo la danza. Te sumas a "
            "ella, porque no hay otra cosa que hacer. Lo haces bien. "
            "Nadie se da cuenta.\n\n"
            "**Final 12 — El Vacío.**"
        ),
        character_dialogue={
            "aris":     "azathoth danza al centro de todo. no hay premio ni castigo aquí. sólo ruido",
            "law":      "un dios IDIOTA danza al centro de todo y no hay premio ni castigo solo NADA lptm",
            "haru":     "caí hacia un vacío donde un dios idiota baila al son de una flauta, no hay nada aquí mano",
            "elyko":    "Azathoth al centro. dios idiota. flauta. no hay premio ni castigo aqui.",
            "xoft":     "un dios idiota bailando al centro de la nada. esto no es peak esto es horror",
            "xokram":   "Ni premio ni castigo, puro vacío, peor inversión de mi vida gg",
            "daraziel": "Un dios idiota danzando al centro de todo. El vacío tiene su propia estética, mano.",
        },
    ))

    return nodes
