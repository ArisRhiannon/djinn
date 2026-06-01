"""Acto 4 — Fase de Revelación: Nyarlathotep se revela (25 nodos)."""
from __future__ import annotations
from typing import Any, Callable, Dict, List


def build_act4_revelacion(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 4
    Z = "La Revelación"
    NPC = "nyarlathotep"
    nodes: List[Dict[str, Any]] = []

    # ═══════════════════════════════════════════════════════════════════
    # ENTRADAS (4 nodos)
    # ═══════════════════════════════════════════════════════════════════

    # Entrada 1: desde máscaras — el jugador descubrió o Nyar se aburrió
    nodes.append(N(
        "act4_revelacion_inicio",
        act=A, zone=Z, tone="horror",
        text=(
            "Las máscaras caen. Todas a la vez, como hojas muertas. "
            "El aire se congela y la figura frente a ti deja de fingir.\n\n"
            "—Bueno... ya estuvo, ¿no? Me aburrí de este jueguito."
        ),
        on_enter={"lucidez": +5, "corrupcion": +2},
        set_flags=["nyar_revelado"],
        primary_npc=NPC,
        paths=[
            P("Observar en silencio", "act4_rev_mascara_cae", style="primary"),
        ],
    ))

    # Entrada 2: el Iluminado — ya sabe, Nyar está impresionado
    nodes.append(N(
        "act4_nyar_iluminado",
        act=A, zone=Z, tone="awe",
        text=(
            "—Vaya, vaya. Lo supiste antes de que yo quisiera mostrarlo. "
            "Eso no pasa seguido. Me impresionas, mortal.\n\n"
            "La figura aplaude lentamente. Cada palmada suena como un trueno lejano."
        ),
        on_enter={"lucidez": +8, "voluntad": +3},
        set_flags=["nyar_revelado", "iluminado_path"],
        primary_npc=NPC,
        paths=[
            P("Sostener la mirada", "act4_rev_mascara_cae", style="primary", effects={"voluntad": +2}),
        ],
    ))

    # Entrada 3: Herramienta de Zuto — Zuto se transforma en Nyar
    nodes.append(N(
        "act4_nyar_zuto",
        act=A, zone=Z, tone="horror",
        text=(
            "Zuto se detiene a mitad de frase. Su cuerpo se estira, se retuerce. "
            "Los huesos crujen como ramas secas. Su rostro se derrite y debajo... "
            "debajo hay algo que siempre estuvo ahí.\n\n"
            "—Sorpresa. 🎭"
        ),
        on_enter={"corrupcion": +5, "memoria": +3},
        set_flags=["nyar_revelado", "zuto_era_nyar"],
        primary_npc=NPC,
        paths=[
            P("Retroceder horrorizado", "act4_rev_mascara_cae", style="danger", effects={"voluntad": -2}),
            P("Reírte", "act4_rev_mascara_cae", style="warning", effects={"corrupcion": +2}),
        ],
    ))

    # Entrada 4: el Corrupto — Nyar lo felicita
    nodes.append(N(
        "act4_nyar_corrupto",
        act=A, zone=Z, tone="horror",
        text=(
            "—Mira nada más lo que hiciste. Mira en lo que te convertiste. "
            "Estoy... orgulloso. De verdad.\n\n"
            "La sombra que te ha seguido todo este tiempo da un paso adelante "
            "y por primera vez tiene rostro."
        ),
        on_enter={"corrupcion": +8},
        set_flags=["nyar_revelado", "corrupto_path"],
        primary_npc=NPC,
        paths=[
            P("Aceptar el halago", "act4_rev_mascara_cae", style="danger", effects={"corrupcion": +3}),
            P("Escupirle", "act4_rev_mascara_cae", style="warning", effects={"voluntad": +3}),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # LA MÁSCARA CAE (nodo convergente)
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_mascara_cae",
        act=A, zone=Z, tone="horror",
        text=(
            "Se lleva las manos a la cara. Los dedos se hunden en la piel "
            "como si fuera arcilla. Tira. La máscara se desprende con un "
            "sonido húmedo, orgánico, imposible.\n\n"
            "Debajo no hay una cara. Hay TODAS las caras."
        ),
        on_enter={"lucidez": +3},
        primary_npc=NPC,
        paths=[
            P("Ver la primera cara", "act4_rev_cara_edyssey", style="primary"),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # LAS CARAS CAMBIANTES (5 nodos)
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_cara_edyssey",
        act=A, zone=Z, tone="horror",
        text=(
            "La primera cara es Edyssey. Sus ojos vacíos, su sonrisa rota. "
            "Te mira como te miró la última vez que lo viste.\n\n"
            "—¿Me reconoces? Claro que sí. Fui tu amigo. Tu guía. Tu error."
        ),
        on_enter={"memoria": +5},
        primary_npc=NPC,
        paths=[
            P("Seguir mirando", "act4_rev_cara_papu", style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_rev_cara_papu",
        act=A, zone=Z, tone="horror",
        text=(
            "La cara se retuerce. Ahora es Papu. La barba, los ojos cansados, "
            "esa expresión de quien ha visto demasiado.\n\n"
            "—También fui él. El viejo sabio. El mentor. Qué cliché tan útil."
        ),
        on_enter={"memoria": +3},
        primary_npc=NPC,
        paths=[
            P("Seguir mirando", "act4_rev_cara_zuto", style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_rev_cara_zuto",
        act=A, zone=Z, tone="horror",
        text=(
            "Zuto. La cara de Zuto aparece con esa sonrisa torcida, "
            "los sellos brillando en su piel.\n\n"
            "—El rebelde. El traidor. El que te hizo dudar. "
            "¿Cuántas veces caíste en esta?"
        ),
        on_enter={"memoria": +3},
        primary_npc=NPC,
        paths=[
            P("Seguir mirando", "act4_rev_cara_payaso", style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_rev_cara_payaso",
        act=A, zone=Z, tone="horror",
        text=(
            "El Payaso. La pintura corrida, la sonrisa demasiado ancha, "
            "los dientes que no son dientes.\n\n"
            "—🤡 Este es mi favorito. A todos les da miedo el payaso. "
            "Nadie sospecha del payaso."
        ),
        on_enter={"corrupcion": +3},
        primary_npc=NPC,
        paths=[
            P("Seguir mirando", "act4_rev_cara_jugador", style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_rev_cara_jugador",
        act=A, zone=Z, tone="horror",
        text=(
            "La última cara eres tú. TU cara. Perfecta, exacta, hasta "
            "la última imperfección. Te sonríe con tu propia boca.\n\n"
            "—Y este... este es el que más me divierte."
        ),
        on_enter={"lucidez": +5, "corrupcion": +3},
        primary_npc=NPC,
        paths=[
            P("Exigir respuestas", "act4_rev_identidad", style="primary", effects={"voluntad": +3}),
            P("Quedarte en shock", "act4_rev_identidad", style="info", effects={"voluntad": -2}),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # IDENTIDAD REVELADA
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_identidad",
        act=A, zone=Z, tone="awe",
        text=(
            "La cara se estabiliza. Ya no cambia. Es algo que no es humano "
            "y nunca lo fue. Ojos como agujeros negros. Una sonrisa que "
            "contiene geometrías imposibles.\n\n"
            "—Soy Nyarlathotep. El Caos Reptante. El Mensajero de los Dioses Exteriores. "
            "Y tú... tú eres mi entretenimiento favorito."
        ),
        on_enter={"lucidez": +5},
        primary_npc=NPC,
        paths=[
            P("¿Por qué?", "act4_rev_dialogo_flags", style="primary"),
            P("¿Qué quieres de mí?", "act4_rev_dialogo_flags", style="info"),
            P("(Quedarse en silencio)", "act4_rev_silencio", style="info", effects={"voluntad": -2}),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # DIÁLOGOS CONDICIONALES POR FLAGS (6 nodos)
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_dialogo_flags",
        act=A, zone=Z, tone="horror",
        text=(
            "Nyarlathotep ladea la cabeza. Su sonrisa se ensancha.\n\n"
            "—¿Quieres saber qué fuiste para mí? Déjame recordarte..."
        ),
        primary_npc=NPC,
        paths=[
            P("El payaso soy yo. Siempre fui yo. 🤡",
              "act4_rev_payaso_conf", style="danger",
              conditions={"flag": "edyssey_devorado_por_payaso"}),
            P("Zuto es una de mis formas favoritas. El sello es MÍO.",
              "act4_rev_zuto_conf", style="danger",
              conditions={"flag": "ruta_dama_activa"}),
            P("Lo mataste tú. Pero yo puse la obsidiana en sus manos.",
              "act4_rev_obsidiana_conf", style="danger",
              conditions={"flag": "mato_edyssey"}),
            P("Escucho sus gritos cada noche. Son mi canción de cuna.",
              "act4_rev_trauma_conf", style="danger",
              conditions={"flag": "trauma_edyssey"}),
            P("El héroe. Qué aburrido. Vamos a ver cuánto duras.",
              "act4_rev_heroe_conf", style="warning",
              conditions={"flag": "digno_de_kadath"}),
            P("Bienvenido a casa. Siempre fuiste de los míos.",
              "act4_rev_aprobado_conf", style="danger",
              conditions={"flag": "nyarlathotep_te_aprueba"}),
            P("(Ninguna flag activa) Continuar", "act4_rev_proposito",
              style="primary",
              conditions={"flag_none": ["edyssey_devorado_por_payaso", "ruta_dama_activa",
                                        "mato_edyssey", "trauma_edyssey",
                                        "digno_de_kadath", "nyarlathotep_te_aprueba"]}),
        ],
    ))

    # Nodos de confirmación para cada flag
    nodes.append(N(
        "act4_rev_payaso_conf",
        act=A, zone=Z, tone="horror",
        text=(
            "—El payaso soy yo. Siempre fui yo. 🤡\n\n"
            "Se ríe. La risa suena como cristal rompiéndose dentro de tu cráneo.\n\n"
            "—Edyssey nunca tuvo oportunidad. El payaso lo devoró porque YO "
            "lo devoré. Cada vez que le tuviste miedo al payaso... me tenías miedo a mí."
        ),
        on_enter={"corrupcion": +5, "memoria": +5},
        primary_npc=NPC,
        paths=[P("Continuar", "act4_rev_proposito", style="primary")],
    ))

    nodes.append(N(
        "act4_rev_zuto_conf",
        act=A, zone=Z, tone="horror",
        text=(
            "—Zuto es una de mis formas favoritas. El sello es MÍO.\n\n"
            "Pasa un dedo por el aire y un sello aparece, brillando con luz negra.\n\n"
            "—La Dama pensó que controlaba algo. Zuto pensó que era libre. "
            "Pero el sello siempre fue mío. Cada pacto que hiciste... lo firmaste conmigo."
        ),
        on_enter={"corrupcion": +5, "memoria": +3},
        primary_npc=NPC,
        paths=[P("Continuar", "act4_rev_proposito", style="primary")],
    ))

    nodes.append(N(
        "act4_rev_obsidiana_conf",
        act=A, zone=Z, tone="horror",
        text=(
            "—Lo mataste tú. Pero yo puse la obsidiana en sus manos.\n\n"
            "Extiende las manos. En ellas, un fragmento de obsidiana idéntico "
            "al que usaste.\n\n"
            "—Cada arma que encontraste. Cada oportunidad que tuviste. "
            "Yo las puse ahí. Tú solo... apretaste."
        ),
        on_enter={"corrupcion": +8, "memoria": +5},
        primary_npc=NPC,
        paths=[P("Continuar", "act4_rev_proposito", style="primary")],
    ))

    nodes.append(N(
        "act4_rev_trauma_conf",
        act=A, zone=Z, tone="horror",
        text=(
            "—Escucho sus gritos cada noche. Son mi canción de cuna.\n\n"
            "Cierra los ojos como si saboreara algo exquisito.\n\n"
            "—El trauma de Edyssey fue mi obra maestra. Cada grito, cada "
            "pesadilla, cada vez que se despertó sudando... yo estaba ahí, "
            "escuchando. Alimentándome."
        ),
        on_enter={"corrupcion": +5, "memoria": +8},
        primary_npc=NPC,
        paths=[P("Continuar", "act4_rev_proposito", style="primary")],
    ))

    nodes.append(N(
        "act4_rev_heroe_conf",
        act=A, zone=Z, tone="tense",
        text=(
            "—El héroe. Qué aburrido. Vamos a ver cuánto duras.\n\n"
            "Bosteza teatralmente.\n\n"
            "—Hiciste todo bien. Salvaste a todos. Qué lindo. "
            "Pero los héroes son los que más se rompen cuando descubren "
            "que el villano nunca estuvo en peligro."
        ),
        on_enter={"voluntad": +5},
        primary_npc=NPC,
        paths=[P("Continuar", "act4_rev_risa_cosmica", style="primary")],
    ))

    nodes.append(N(
        "act4_rev_aprobado_conf",
        act=A, zone=Z, tone="horror",
        text=(
            "—Bienvenido a casa. Siempre fuiste de los míos.\n\n"
            "Extiende los brazos como un padre recibiendo a un hijo pródigo.\n\n"
            "—Cada decisión oscura. Cada momento en que elegiste el poder "
            "sobre la piedad. No te corrompí. Te LIBERÉ."
        ),
        on_enter={"corrupcion": +10},
        primary_npc=NPC,
        paths=[P("Continuar", "act4_rev_proposito", style="primary")],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # REACCIÓN DEL JUGADOR
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_silencio",
        act=A, zone=Z, tone="horror",
        text=(
            "El silencio después de sus palabras pesa como plomo líquido. "
            "Nyarlathotep te observa con curiosidad genuina, como un niño "
            "mirando un insecto que aún se mueve.\n\n"
            "—¿Nada? ¿Ni un grito? ¿Ni una lágrima? Interesante."
        ),
        primary_npc=NPC,
        paths=[
            P("¿Todo fue mentira?", "act4_rev_verdad_mentira", style="primary"),
            P("¿Qué quieres de mí?", "act4_rev_proposito", style="info"),
        ],
    ))

    nodes.append(N(
        "act4_rev_verdad_mentira",
        act=A, zone=Z, tone="tense",
        text=(
            "—¿Mentira? No, no. Todo fue REAL. Ese es el chiste.\n\n"
            "Se acerca tanto que puedes ver galaxias morir en sus pupilas.\n\n"
            "—Cada emoción que sentiste fue genuina. Cada amigo que hiciste "
            "existió de verdad. Yo solo... puse el escenario. Escribí el guión. "
            "Pero las lágrimas fueron tuyas."
        ),
        on_enter={"memoria": +5, "lucidez": +3},
        primary_npc=NPC,
        paths=[
            P("Eso es peor", "act4_rev_proposito", style="primary", effects={"voluntad": +2}),
        ],
    ))

    nodes.append(N(
        "act4_rev_risa_cosmica",
        act=A, zone=Z, tone="horror",
        text=(
            "Nyarlathotep se ríe. No es una risa humana. Es el sonido de "
            "estrellas colapsando, de civilizaciones olvidándose a sí mismas, "
            "de un universo que nunca tuvo sentido y lo encuentra gracioso.\n\n"
            "—¿Sabes cuántos como tú han llegado hasta aquí? Cientos. Miles. "
            "Pero tú... tú eres DIVERTIDO."
        ),
        on_enter={"lucidez": +3, "corrupcion": +2},
        primary_npc=NPC,
        paths=[
            P("No soy tu juguete", "act4_rev_proposito", style="warning", effects={"voluntad": +3}),
            P("¿Qué me hace diferente?", "act4_rev_proposito", style="primary"),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # PROPÓSITO Y OFERTA
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_proposito",
        act=A, zone=Z, tone="tense",
        text=(
            "Nyarlathotep se sienta en el aire. Literalmente. Como si hubiera "
            "una silla invisible hecha de vacío.\n\n"
            "—Kadath no es un lugar. Es un JUEGO. Mi juego. "
            "Y tú llegaste más lejos que la mayoría. Eso merece... una oferta."
        ),
        primary_npc=NPC,
        paths=[
            P("¿Qué clase de oferta?", "act4_rev_reglas", style="primary"),
            P("No quiero nada de ti", "act4_rev_rechazo_inicial", style="warning", effects={"voluntad": +3}),
        ],
    ))

    nodes.append(N(
        "act4_rev_rechazo_inicial",
        act=A, zone=Z, tone="tense",
        text=(
            "—Jajaja. Qué tierno. Crees que tienes opción.\n\n"
            "Chasquea los dedos. El mundo a tu alrededor se pliega como origami. "
            "Estás exactamente donde él quiere que estés.\n\n"
            "—No es una oferta que puedas rechazar. Es una oferta que puedes "
            "ELEGIR cómo aceptar. Hay una diferencia."
        ),
        on_enter={"voluntad": -2},
        primary_npc=NPC,
        paths=[
            P("Escuchar las reglas", "act4_rev_reglas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act4_rev_reglas",
        act=A, zone=Z, tone="tense",
        text=(
            "—Las reglas son simples. Kadath tiene un corazón. "
            "Quien lo toque, define la realidad. Yo quiero que TÚ lo toques. "
            "Pero cómo llegas ahí... eso depende de ti.\n\n"
            "Levanta tres dedos.\n\n"
            "—Tres caminos. Tres formas de jugar MI juego."
        ),
        primary_npc=NPC,
        paths=[
            P("¿Cuáles son?", "act4_rev_opciones", style="primary"),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # EL JUEGO — LAS 3 OPCIONES
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_rev_opciones",
        act=A, zone=Z, tone="tense",
        text=(
            "Nyarlathotep despliega tres puertas en el aire. Cada una pulsa "
            "con una energía distinta.\n\n"
            "—UNO: Aceptas mi trato. Te doy poder, te doy el camino directo. "
            "A cambio... bueno, ya verás.\n\n"
            "—DOS: Me desafías. Intentas llegar al corazón SIN mi ayuda, "
            "CONTRA mí. Divertido. Doloroso. Pero divertido.\n\n"
            "—TRES: Te largas. Huyes. Corres. A ver si puedes salir de un "
            "laberinto que YO diseñé.\n\n"
            "—Elige."
        ),
        on_enter={"lucidez": +3},
        primary_npc=NPC,
        character_dialogue={
            "aris": "tres puertas. tres caminos. ninguno es seguro. pero tengo que elegir",
            "law": "bro tres opciones y todas suenan a que me van a partir la madre",
            "haru": "mano ninguna de las tres opciones suena bien pero hay que elegir",
            "elyko": "tres opciones. trato, desafío, huida. analiza antes de elegir.",
            "xoft": "TRES PUERTAS MANO y todas dan miedo pero hay que elegir una",
            "xokram": "Tres caminos y todos huelen a trampa, gg",
            "daraziel": "Tres opciones. Ninguna es segura. Pero la inacción no es opción.",
        },
        paths=[
            P("Acepto tu trato", "act4_juego_trato",
              style="danger", effects={"corrupcion": +5}),
            P("Te desafío", "act4_juego_desafio",
              style="warning", effects={"voluntad": +5}),
            P("Me largo de aquí", "act4_juego_huida",
              style="info", effects={"lucidez": +3}),
        ],
    ))

    assert len(nodes) == 25, f"Expected 25 nodes, got {len(nodes)}"
    return nodes
