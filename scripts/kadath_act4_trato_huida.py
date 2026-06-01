"""Kadath Acto 4 — Rutas TRATO y HUIDA (20 nodos: 10+10)."""


def build_act4_trato_huida(N, P) -> list:
    nodes = []
    A = 4
    Z_T = "Trono de Nyarlathotep — El Trato"
    Z_H = "Trono de Nyarlathotep — La Huida"
    NPC = "nyarlathotep"

    # ═══════════════════════════════════════════════════════════════════
    # RUTA A — EL TRATO (10 nodos)
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_juego_trato",
        act=A, zone=Z_T, tone="ominoso",
        text=(
            "Nyarlathotep se inclina hacia ti. Su rostro cambia — ahora es "
            "amable, casi paternal.\n\n"
            "—No tienes que sufrir más. Puedo llevarte a Kadath ahora mismo. "
            "Solo necesito... algo tuyo. Algo pequeño. Algo que no vas a extrañar."
        ),
        on_enter={"corrupcion": +2},
        primary_npc=NPC,
        hostile_npc=NPC,
        paths=[
            P("Escuchar su oferta (tienes la bendición felina)", "act4_trato_bendicion",
              style="warning", conditions={"has_flag": "bendicion_felina"}),
            P("Escuchar su oferta (tienes un aliado)", "act4_trato_aliado",
              style="warning", conditions={"has_flag": "index_aliado"}),
            P("Escuchar su oferta (tienes un aliado)", "act4_trato_aliado",
              style="warning", conditions={"has_flag": "ccn_aliado"}),
            P("Escuchar su oferta (tienes un aliado)", "act4_trato_aliado",
              style="warning", conditions={"has_flag": "rotundus_aliado"}),
            P("Escuchar su oferta (voluntad fuerte)", "act4_trato_voluntad",
              style="warning", conditions={"voluntad_min": 50}),
            P("Escuchar su oferta (ya eres suyo)", "act4_trato_corrupto",
              style="danger", conditions={"corrupcion_min": 50}),
            P("Escuchar su oferta", "act4_trato_memoria", style="primary"),
            P("Rechazar de inmediato", "act4_juego_huida", style="success",
              effects={"voluntad": +3}),
        ],
    ))

    # --- Rama: pide la bendición felina ---
    nodes.append(N(
        "act4_trato_bendicion",
        act=A, zone=Z_T, tone="ominoso",
        text=(
            "Los ojos de Nyarlathotep se fijan en tu pecho, donde la "
            "bendición felina pulsa como un segundo corazón.\n\n"
            "—Eso. Esa cosita que te dieron los gatos. Dámela y te llevo. "
            "Es un trato justo, ¿no? Ellos te la dieron gratis. Yo te doy Kadath."
        ),
        on_enter={"corrupcion": +1},
        primary_npc=NPC,
        paths=[
            P("Entregar la bendición felina", "act4_trato_acepta_bendicion",
              style="danger", consume_item="bendicion_felina",
              effects={"corrupcion": +5}),
            P("Negarte", "act4_trato_rechazo", style="success",
              effects={"voluntad": +4}),
        ],
    ))

    nodes.append(N(
        "act4_trato_acepta_bendicion",
        act=A, zone=Z_T, tone="oscuro",
        text=(
            "Arrancas la bendición de tu pecho. Duele — como arrancar un "
            "recuerdo feliz. Nyarlathotep la toma entre sus dedos y la "
            "aplasta. Polvo dorado cae al suelo.\n\n"
            "—Buen chico. Ahora ven. Kadath te espera."
        ),
        on_enter={"corrupcion": +5, "lucidez": -3},
        set_flags=["trato_nyar_aceptado", "perdio_bendicion_felina"],
        primary_npc=NPC,
        paths=[
            P("Seguirlo a Kadath", "act4_trato_consecuencia", style="danger"),
        ],
    ))

    # --- Rama: pide traicionar aliado ---
    nodes.append(N(
        "act4_trato_aliado",
        act=A, zone=Z_T, tone="ominoso",
        text=(
            "Nyarlathotep sonríe con demasiados dientes.\n\n"
            "—Tienes amigos. Qué tierno. Mira, no te pido mucho: solo "
            "dime dónde están. Dime su nombre real. Eso es todo. "
            "Un nombre a cambio de Kadath. ¿No es generoso?"
        ),
        on_enter={"corrupcion": +2},
        primary_npc=NPC,
        paths=[
            P("Traicionar a tu aliado", "act4_trato_acepta_aliado",
              style="danger", effects={"corrupcion": +8, "favor": -10}),
            P("Negarte", "act4_trato_rechazo", style="success",
              effects={"voluntad": +5, "favor": +3}),
        ],
    ))

    nodes.append(N(
        "act4_trato_acepta_aliado",
        act=A, zone=Z_T, tone="oscuro",
        text=(
            "Dices el nombre. Lo sientes salir de tu boca como veneno. "
            "Nyarlathotep cierra los ojos, saboreándolo.\n\n"
            "—Perfecto. Ya no son tu problema. Ven — Kadath te espera."
        ),
        on_enter={"corrupcion": +5, "favor": -5},
        set_flags=["trato_nyar_aceptado", "traiciono_aliado_act3"],
        primary_npc=NPC,
        paths=[
            P("Seguirlo a Kadath", "act4_trato_consecuencia", style="danger"),
        ],
    ))

    # --- Rama: pide voluntad ---
    nodes.append(N(
        "act4_trato_voluntad",
        act=A, zone=Z_T, tone="ominoso",
        text=(
            "Nyarlathotep te mira con algo parecido al respeto.\n\n"
            "—Tienes voluntad fuerte. Eso me gusta. Dame un pedazo. "
            "Solo un pedazo — no lo vas a notar. Bueno, quizás un poco. "
            "Pero tendrás Kadath. ¿No es lo que querías?"
        ),
        on_enter={"corrupcion": +1},
        primary_npc=NPC,
        paths=[
            P("Ceder parte de tu voluntad", "act4_trato_consecuencia",
              style="danger", effects={"voluntad": -20, "corrupcion": +4},
              set_flags=["trato_nyar_aceptado", "voluntad_cedida"]),
            P("Negarte", "act4_trato_rechazo", style="success",
              effects={"voluntad": +3}),
        ],
    ))

    # --- Rama: ya corrupto ---
    nodes.append(N(
        "act4_trato_corrupto",
        act=A, zone=Z_T, tone="oscuro",
        text=(
            "Nyarlathotep no pide nada. Solo te mira — y sonríe.\n\n"
            "—¿Sabes qué? No necesito pedirte nada. Ya eres mío. "
            "Lo has sido desde hace rato. Ven, vamos a casa."
        ),
        on_enter={"corrupcion": +3},
        set_flags=["trato_nyar_aceptado", "nyar_posesion_total"],
        primary_npc=NPC,
        paths=[
            P("Seguirlo (no tienes opción)", "act4_trato_consecuencia",
              style="danger"),
        ],
    ))

    # --- Rama: pide memoria (default) ---
    nodes.append(N(
        "act4_trato_memoria",
        act=A, zone=Z_T, tone="ominoso",
        text=(
            "Nyarlathotep ladea la cabeza, pensativo.\n\n"
            "—No tienes mucho que ofrecer, ¿verdad? Pero tienes recuerdos. "
            "Dame algunos. Los que te hacen humano. No los necesitas en Kadath."
        ),
        on_enter={"corrupcion": +2},
        primary_npc=NPC,
        paths=[
            P("Entregar tus recuerdos", "act4_trato_consecuencia",
              style="danger", effects={"memoria": -15, "corrupcion": +4},
              set_flags=["trato_nyar_aceptado", "memoria_cedida"]),
            P("Negarte", "act4_trato_rechazo", style="success",
              effects={"voluntad": +3}),
        ],
    ))

    # --- Rechazo → manda a huida ---
    nodes.append(N(
        "act4_trato_rechazo",
        act=A, zone=Z_T, tone="tenso",
        text=(
            "Nyarlathotep suspira — teatralmente.\n\n"
            "—Qué lástima. Bueno, corre entonces. Corre todo lo que quieras. "
            "Todos los caminos llevan a mí.\n\n"
            "Te das la vuelta y corres."
        ),
        on_enter={"voluntad": +2},
        set_flags=["rechazo_trato_nyar"],
        primary_npc=NPC,
        paths=[
            P("Correr", "act4_juego_huida", style="primary",
              effects={"voluntad": +2}),
        ],
    ))

    # --- Consecuencia del trato aceptado ---
    nodes.append(N(
        "act4_trato_consecuencia",
        act=A, zone=Z_T, tone="oscuro",
        text=(
            "El mundo se pliega. Nyarlathotep te toma del hombro y el "
            "espacio se desgarra como papel mojado. Ves Kadath — la ciudad "
            "imposible — materializarse ante ti.\n\n"
            "Pero algo falta. Algo que eras antes de este momento ya no está."
        ),
        on_enter={"lucidez": -2, "corrupcion": +2},
        set_flags=["llego_por_trato"],
        primary_npc=NPC,
        paths=[
            P("Entrar a Kadath", "act4_paso_kadath", style="danger"),
        ],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # RUTA C — LA HUIDA (10 nodos)
    # ═══════════════════════════════════════════════════════════════════

    nodes.append(N(
        "act4_juego_huida",
        act=A, zone=Z_H, tone="tenso",
        text=(
            "Corres. El trono de Nyarlathotep queda atrás — o eso crees. "
            "Los pasillos se tuercen, las paredes respiran. Cada puerta "
            "que abres da a otro corredor idéntico.\n\n"
            "Primer intento de escape."
        ),
        on_enter={"voluntad": +1},
        set_flags=["huida_loop_1"],
        paths=[
            P("Los gatos abren una grieta", "act4_huida_gatos",
              style="success", conditions={"has_flag": "bendicion_felina"}),
            P("Los gatos abren una grieta", "act4_huida_gatos",
              style="success", conditions={"has_flag": "bendicion_gato"}),
            P("La grieta del sello roto", "act4_huida_sello",
              style="success", conditions={"has_flag": "sello_roto"}),
            P("Los ghouls te sacan por abajo", "act4_huida_ghouls",
              style="success", conditions={"has_flag": "pacto_ghoul"}),
            P("Seguir corriendo", "act4_huida_loop2", style="primary"),
        ],
    ))

    # --- Loop 2 ---
    nodes.append(N(
        "act4_huida_loop2",
        act=A, zone=Z_H, tone="opresivo",
        text=(
            "Otro corredor. Otra puerta. La abres y — ahí está. "
            "Nyarlathotep, sentado exactamente igual. Te saluda con la mano.\n\n"
            "—¿Ya? ¿Tan rápido volviste?\n\n"
            "Te das la vuelta. Segundo intento."
        ),
        on_enter={"lucidez": -2, "corrupcion": +1},
        set_flags=["huida_loop_2"],
        primary_npc=NPC,
        paths=[
            P("Los gatos abren una grieta", "act4_huida_gatos",
              style="success", conditions={"has_flag": "bendicion_felina"}),
            P("Los gatos abren una grieta", "act4_huida_gatos",
              style="success", conditions={"has_flag": "bendicion_gato"}),
            P("La grieta del sello roto", "act4_huida_sello",
              style="success", conditions={"has_flag": "sello_roto"}),
            P("Los ghouls te sacan por abajo", "act4_huida_ghouls",
              style="success", conditions={"has_flag": "pacto_ghoul"}),
            P("Seguir corriendo", "act4_huida_loop3", style="primary"),
        ],
    ))

    # --- Loop 3 ---
    nodes.append(N(
        "act4_huida_loop3",
        act=A, zone=Z_H, tone="desesperado",
        text=(
            "Tercer corredor. Tercer intento. Las paredes ya ni se molestan "
            "en parecer diferentes. Nyarlathotep está al final, bostezando.\n\n"
            "—Mira, esto ya me aburrió. ¿Quieres seguir jugando o...?"
        ),
        on_enter={"lucidez": -3, "corrupcion": +2},
        set_flags=["huida_loop_3"],
        primary_npc=NPC,
        paths=[
            P("Los gatos abren una grieta", "act4_huida_gatos",
              style="success", conditions={"has_flag": "bendicion_felina"}),
            P("Los gatos abren una grieta", "act4_huida_gatos",
              style="success", conditions={"has_flag": "bendicion_gato"}),
            P("La grieta del sello roto", "act4_huida_sello",
              style="success", conditions={"has_flag": "sello_roto"}),
            P("Los ghouls te sacan por abajo", "act4_huida_ghouls",
              style="success", conditions={"has_flag": "pacto_ghoul"}),
            P("Aceptar que no puedes escapar", "act4_huida_aburrimiento",
              style="warning"),
        ],
    ))

    # --- Escape: gatos ---
    nodes.append(N(
        "act4_huida_gatos",
        act=A, zone=Z_H, tone="esperanza",
        text=(
            "Un maullido. Luego cien. Los gatos de Ulthar aparecen de "
            "todas partes — de las grietas, de las sombras, de los rincones "
            "imposibles. Arañan la realidad hasta que se abre una fisura "
            "brillante.\n\n"
            "Nyarlathotep frunce el ceño por primera vez.\n\n"
            "—Malditos gatos."
        ),
        on_enter={"lucidez": +5, "voluntad": +3},
        set_flags=["escapo_por_gatos"],
        primary_npc=NPC,
        paths=[
            P("Saltar por la grieta", "act4_huida_libre", style="success"),
        ],
    ))

    # --- Escape: sello roto ---
    nodes.append(N(
        "act4_huida_sello",
        act=A, zone=Z_H, tone="misterioso",
        text=(
            "Lo ves — una grieta en la pared que no debería estar ahí. "
            "El sello que rompiste en el templo de Zuto dejó una herida "
            "en la realidad que ni Nyarlathotep puede cerrar.\n\n"
            "—Ah. Eso. Debí haberlo previsto."
        ),
        on_enter={"lucidez": +4, "lore": +3},
        set_flags=["escapo_por_sello"],
        primary_npc=NPC,
        paths=[
            P("Cruzar la grieta", "act4_huida_libre", style="success"),
        ],
    ))

    # --- Escape: ghouls ---
    nodes.append(N(
        "act4_huida_ghouls",
        act=A, zone=Z_H, tone="grotesco",
        text=(
            "El suelo se abre. Garras pálidas emergen desde abajo — los "
            "ghouls. Cumplen su pacto. Te jalan hacia las profundidades "
            "antes de que Nyarlathotep pueda reaccionar.\n\n"
            "—Interesante. Los muertos te prefieren a mí."
        ),
        on_enter={"lucidez": +3, "corrupcion": +1},
        set_flags=["escapo_por_ghouls"],
        primary_npc=NPC,
        paths=[
            P("Dejarte llevar por los ghouls", "act4_huida_libre",
              style="success"),
        ],
    ))

    # --- Default: Nyar se aburre ---
    nodes.append(N(
        "act4_huida_aburrimiento",
        act=A, zone=Z_H, tone="oscuro",
        text=(
            "Nyarlathotep se levanta, se estira, y bosteza con una boca "
            "que tiene demasiadas filas de dientes.\n\n"
            "—Sabes qué, ya me cansé de esto. No eres divertido. "
            "Voy a dejarte ir — pero no gratis."
        ),
        on_enter={"corrupcion": +3, "lucidez": -2},
        set_flags=["nyar_aburrido"],
        primary_npc=NPC,
        paths=[
            P("¿Qué vas a hacerme?", "act4_huida_marca", style="warning"),
        ],
    ))

    # --- Nyar te marca ---
    nodes.append(N(
        "act4_huida_marca",
        act=A, zone=Z_H, tone="oscuro",
        text=(
            "Nyarlathotep chasquea los dedos. Sientes algo frío grabarse "
            "en tu nuca — un símbolo que no puedes ver pero que pesa.\n\n"
            "—Listo. Ahora vete. Una puerta aparece — real, abierta. "
            "Donde vayas, una parte de ti me pertenece."
        ),
        on_enter={"corrupcion": +3},
        set_flags=["marca_nyarlathotep", "escapo_por_aburrimiento"],
        primary_npc=NPC,
        paths=[
            P("Cruzar la puerta", "act4_huida_marcado", style="warning"),
        ],
    ))

    # --- Nodo marcado (default sin flags) ---
    nodes.append(N(
        "act4_huida_marcado",
        act=A, zone=Z_H, tone="oscuro",
        text=(
            "Cruzas la puerta. Sientes algo frío en la nuca — como un "
            "tatuaje que se graba solo. La marca de Nyarlathotep.\n\n"
            "Estás libre. Pero no estás limpio."
        ),
        on_enter={"corrupcion": +2},
        set_flags=["marcado_por_nyar"],
        paths=[
            P("Continuar hacia Kadath", "act4_paso_kadath", style="primary"),
        ],
    ))

    # --- Nodo libre (escape exitoso) ---
    nodes.append(N(
        "act4_huida_libre",
        act=A, zone=Z_H, tone="esperanza",
        text=(
            "Sales. El aire cambia — ya no huele a azufre y mentiras. "
            "Nyarlathotep quedó atrás, y por primera vez en mucho tiempo "
            "sientes que el camino es tuyo.\n\n"
            "Kadath está adelante. Llegarás por tu cuenta."
        ),
        on_enter={"voluntad": +5, "lucidez": +3},
        set_flags=["escapo_de_nyar"],
        paths=[
            P("Avanzar hacia Kadath", "act4_paso_kadath", style="success",
              effects={"voluntad": +2}),
        ],
    ))

    return nodes
