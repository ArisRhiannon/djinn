"""Kadath Acto 5 — TRONCO PRINCIPAL: El Trono Vacío, La Tentación, La Elección Final."""


def build_act5_core(N, P):
    nodes = []

    # ═══════════════════════════════════════════════════════════════
    # FASE 1 — EL TRONO VACÍO (10 nodos)
    # ═══════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_cumbre_trono", act=5, zone="kadath_cumbre",
        text=(
            "La escalera termina. No hay más peldaños. "
            "Ante ti se abre la meseta final de Kadath — un disco de ónice negro "
            "pulido por eones, rodeado de un vacío que no es cielo ni espacio, "
            "sino la ausencia misma de narrativa. El viento no sopla: tiembla."
        ),
        on_enter=["stat:memoria+1"],
        paths=[P("Avanzar hacia el trono", "act5_meseta_silencio", style="bold")],
        set_flags=["llegaste_a_kadath"],
        character_dialogue={
            "narrator": "Has llegado. Nadie más lo ha hecho en esta era.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_meseta_silencio", act=5, zone="kadath_cumbre",
        text=(
            "El silencio aquí tiene peso. Cada paso resuena como un latido "
            "en una catedral vacía. Las estrellas sobre Kadath no titilan — "
            "observan. Reconoces constelaciones que no existen en ningún atlas."
        ),
        on_enter=["stat:lucidez+1"],
        paths=[P("Buscar a los dioses", "act5_tronos_vacios", style="careful")],
        set_flags=[],
        character_dialogue={
            "narrator": "El aire sabe a eternidad estancada.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_tronos_vacios", act=5, zone="kadath_cumbre",
        text=(
            "Hay tronos menores dispuestos en semicírculo — docenas de ellos, "
            "tallados en basalto y jade onírico. Todos vacíos. Polvo de siglos "
            "cubre los reposabrazos. Los Grandes Dioses de la Tierra se fueron "
            "hace mucho. O nunca estuvieron."
        ),
        on_enter=[],
        paths=[P("Examinar el trono central", "act5_trono_onice", style="bold")],
        set_flags=["vio_tronos_vacios"],
        character_dialogue={
            "narrator": "Abandonados. Como juguetes de niños que crecieron.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_trono_onice", act=5, zone="kadath_cumbre",
        text=(
            "El Trono de Ónice se alza al centro exacto de la meseta. "
            "Es más grande que cualquier silla mortal — un monolito esculpido "
            "en roca que absorbe la luz. Su superficie muestra relieves que "
            "cambian cuando no los miras directamente: ciudades, rostros, mapas "
            "de lugares que aún no existen."
        ),
        on_enter=["stat:lore+2"],
        paths=[P("Tocarlo", "act5_contacto_trono", style="risky")],
        set_flags=[],
        character_dialogue={
            "narrator": "El trono te reconoce. Lo sientes en los huesos del sueño.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_contacto_trono", act=5, zone="kadath_cumbre",
        text=(
            "Al rozar el ónice, una descarga recorre tu brazo. No es dolor — "
            "es información. Ves fragmentos: tu llegada vista desde arriba, "
            "el camino entero que recorriste comprimido en un instante. "
            "El trono sabe quién eres. Siempre lo supo."
        ),
        on_enter=["stat:memoria+2"],
        paths=[P("Mirar alrededor", "act5_eco_viaje", style="careful")],
        set_flags=["toco_trono"],
        character_dialogue={
            "narrator": "La piedra recuerda mejor que tú.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_eco_viaje", act=5, zone="kadath_cumbre",
        text=(
            "El trono reacciona a tu presencia. En su superficie aparecen "
            "escenas de tu viaje — fragmentos: la primera vez que cruzaste "
            "la Puerta del Sueño Profundo, los gatos de Ulthar, las torres "
            "de Celephais. Todo lo que viviste, grabado en ónice."
        ),
        on_enter=["stat:memoria+1"],
        paths=[P("Seguir observando", "act5_panorama_kadath", style="careful")],
        set_flags=["trono_mostro_viaje"],
        character_dialogue={
            "narrator": "El trono es un espejo que refleja el camino, no el rostro.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_panorama_kadath", act=5, zone="kadath_cumbre",
        text=(
            "Desde la cima ves todo: el desierto frío que cruzaste, las montañas "
            "que escalaste, y más allá — las Dreamlands enteras desplegadas como "
            "un tapiz infinito. Ulthar brilla al sur. Celephais centellea al oeste. "
            "Y debajo, muy debajo, los túneles ghoul pulsan como venas oscuras."
        ),
        on_enter=[],
        paths=[P("¿Hay alguien más aquí?", "act5_presencia_check", style="careful")],
        set_flags=[],
        character_dialogue={
            "narrator": "Todo lo que soñaste, visible desde un solo punto.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_presencia_check", act=5, zone="kadath_cumbre",
        text=(
            "Sientes una presencia. No la ves — la intuyes. Como una sombra "
            "que existe solo en tu visión periférica. El aire se espesa con "
            "algo que podría ser una risa contenida o el preludio de un aplauso."
        ),
        on_enter=[],
        paths=[
            P("Llamar a Nyarlathotep", "act5_nyar_aparece",
              style="risky", conditions=["flag:nyarlathotep_conocido"]),
            P("Esperar en silencio", "act5_nyar_aparece_igual", style="careful")
        ],
        set_flags=[],
        character_dialogue={
            "narrator": "No estás solo. Nunca lo estuviste en Kadath.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_nyar_aparece", act=5, zone="kadath_cumbre",
        text=(
            "—Ah, me llamaste por mi nombre. Qué íntimo.\n\n"
            "Nyarlathotep se materializa desde las sombras del trono. "
            "Su forma es la del hombre alto y elegante — piel oscura, "
            "sonrisa que conoce todos tus secretos. Lleva un traje que "
            "parece hecho de noche líquida."
        ),
        on_enter=["stat:corrupcion+1"],
        paths=[P("Escucharlo", "act5_nyar_discurso", style="bold")],
        set_flags=["nyar_invocado"],
        character_dialogue={
            "narrator": "",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Llegaste. Sabía que lo harías. Siempre lo supe."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_nyar_aparece_igual", act=5, zone="kadath_cumbre",
        text=(
            "El silencio se rompe solo. Una figura emerge del propio trono "
            "como si la piedra lo pariera. Nyarlathotep — o algo que usa su forma — "
            "te observa con ojos que contienen galaxias muertas.\n\n"
            "—No hacía falta que llamaras. Ya estaba aquí antes que tú."
        ),
        on_enter=["stat:corrupcion+1"],
        paths=[P("Escucharlo", "act5_nyar_discurso", style="careful")],
        set_flags=[],
        character_dialogue={
            "narrator": "",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "La paciencia es mi único lujo. Tengo toda la eternidad."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_nyar_discurso", act=5, zone="kadath_cumbre",
        text=(
            "—Los dioses se fueron, sí. Se aburrieron de este lugar hace eones. "
            "Pero el trono... el trono necesita a alguien. La estructura de las "
            "Dreamlands exige un ocupante. Sin uno, todo esto — Ulthar, Celephais, "
            "los mares, los gatos, todo — se deshilacha.\n\n"
            "Hace una pausa teatral.\n\n"
            "—Y tú llegaste justo a tiempo."
        ),
        on_enter=["stat:lore+1"],
        paths=[P("¿Qué me estás ofreciendo?", "act5_tentacion_inicio", style="bold")],
        set_flags=["nyar_ofrecio_trono"],
        character_dialogue={
            "narrator": "",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "No ofrezco. Presento hechos. La oferta la haces tú mismo."
        },
        primary_npc="nyarlathotep"
    ))

    # ═══════════════════════════════════════════════════════════════
    # FASE 2 — LA TENTACIÓN (15 nodos)
    # ═══════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_tentacion_inicio", act=5, zone="kadath_trono",
        text=(
            "Nyarlathotep chasquea los dedos. El trono de ónice se ilumina "
            "desde dentro — venas de luz dorada recorren sus relieves. "
            "Y en su superficie, como en un espejo imposible, comienzas a ver algo."
        ),
        on_enter=["stat:lucidez+1"],
        paths=[
            P("Mirar lo que muestra", "act5_vision_ciudad",
              style="bold", conditions=["flag:digno_de_kadath"]),
            P("Mirar lo que muestra", "act5_vision_poder",
              style="bold", conditions=["flag:nyarlathotep_te_aprueba"]),
            P("Mirar lo que muestra", "act5_vision_edyssey",
              style="bold", conditions=["flag:trauma_edyssey"]),
            P("Mirar lo que muestra", "act5_vision_libertad",
              style="bold", conditions=["flag:ruta_dama_activa"]),
            P("Mirar lo que muestra", "act5_vision_subterraneo",
              style="bold", conditions=["flag:pacto_ghoul"]),
            P("Mirar lo que muestra", "act5_vision_hogar", style="bold")
        ],
        set_flags=["tentacion_iniciada"],
        character_dialogue={
            "narrator": "El trono te muestra lo que más deseas.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Mira. Solo mira. No te pido nada más... por ahora."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_vision_ciudad", act=5, zone="kadath_trono",
        text=(
            "La ciudad del atardecer. La ves perfecta — sus minaretes dorados, "
            "sus terrazas de mármol rosado, el sol perpetuo hundiéndose sin "
            "terminar de caer. Es la ciudad que buscaste desde el primer sueño. "
            "Existe. Siempre existió. Y el trono es la llave."
        ),
        on_enter=["stat:memoria+2"],
        paths=[P("Extender la mano hacia la visión", "act5_tentacion_profunda", style="bold")],
        set_flags=["vision_ciudad_atardecer"],
        character_dialogue={
            "narrator": "Como Carter antes que tú, la ciudad te llama.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Hermosa, ¿verdad? Y puede ser tuya. Para siempre."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_vision_poder", act=5, zone="kadath_trono",
        text=(
            "Poder. Infinito y sin forma. Ves las Dreamlands como un tablero "
            "y tú eres la mano que mueve las piezas. Cada sueño de cada soñador "
            "sería tuyo para moldear. Serías más que un dios — serías el sueño mismo."
        ),
        on_enter=["stat:corrupcion+2"],
        paths=[P("Extender la mano hacia la visión", "act5_tentacion_profunda", style="risky")],
        set_flags=["vision_poder"],
        character_dialogue={
            "narrator": "El poder absoluto. La tentación más antigua.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Mereces esto. Lo ganaste. Cada prueba te preparó."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_vision_edyssey", act=5, zone="kadath_trono",
        text=(
            "Edyssey. Vivo. Sonriendo. No como fantasma ni eco — real, "
            "con peso y calor y esa risa que reconocerías entre mil. "
            "Está en un jardín que no existe, esperándote. "
            "El trono puede traerlo de vuelta. El trono puede arreglar lo que se rompió."
        ),
        on_enter=["stat:memoria+3"],
        paths=[P("Extender la mano hacia la visión", "act5_tentacion_profunda", style="bold")],
        set_flags=["vision_edyssey"],
        character_dialogue={
            "narrator": "El dolor más profundo convertido en promesa.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "Estoy aquí. Siempre estuve aquí. Solo tenías que llegar.",
            "dama": "",
            "nyarlathotep": ""
        },
        primary_npc="edyssey"
    ))

    nodes.append(N(
        "act5_vision_libertad", act=5, zone="kadath_trono",
        text=(
            "El sello se rompe. La Dama camina libre — sin cadenas de ónice, "
            "sin pactos que la aten. La ves reír por primera vez, y su risa "
            "suena como campanas de un templo que nunca fue profanado. "
            "El trono tiene el poder de liberarla."
        ),
        on_enter=["stat:favor+2"],
        paths=[P("Extender la mano hacia la visión", "act5_tentacion_profunda", style="bold")],
        set_flags=["vision_libertad_dama"],
        character_dialogue={
            "narrator": "Libertad para quien nunca la tuvo.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "",
            "dama": "¿Harías eso... por mí?",
            "nyarlathotep": ""
        },
        primary_npc="dama"
    ))

    nodes.append(N(
        "act5_vision_subterraneo", act=5, zone="kadath_trono",
        text=(
            "Un reino bajo la tierra. Túneles infinitos iluminados por hongos "
            "fosforescentes, catedrales de hueso donde los ghouls reinan sin miedo. "
            "Y tú — transformado, aceptado, parte de algo más antiguo que los dioses. "
            "Un hogar que no juzga. Que no exige."
        ),
        on_enter=["stat:corrupcion+1"],
        paths=[P("Extender la mano hacia la visión", "act5_tentacion_profunda", style="bold")],
        set_flags=["vision_reino_ghoul"],
        character_dialogue={
            "narrator": "Pertenecer. El deseo más humano, en su forma menos humana.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Ellos te aceptaron cuando nadie más lo hizo."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_vision_hogar", act=5, zone="kadath_trono",
        text=(
            "Tu hogar. Tu vida antes del sueño. La habitación donde dormías, "
            "la luz de la mañana entrando por la ventana, el olor a café, "
            "la normalidad perfecta de un día sin monstruos ni dioses ni tronos. "
            "Simple. Cálido. Perdido."
        ),
        on_enter=["stat:memoria+2"],
        paths=[P("Extender la mano hacia la visión", "act5_tentacion_profunda", style="bold")],
        set_flags=["vision_hogar"],
        character_dialogue={
            "narrator": "Lo más difícil de dejar siempre fue lo más simple.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Puedes volver. Como si nada hubiera pasado."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_tentacion_profunda", act=5, zone="kadath_trono",
        text=(
            "La visión se intensifica. Sientes que podrías entrar en ella — "
            "solo un paso más. Nyarlathotep observa con esa sonrisa que no "
            "revela si es aliado o verdugo. El trono pulsa como un corazón."
        ),
        on_enter=["stat:voluntad-1"],
        paths=[P("Dejarte llevar", "act5_vision_se_quiebra", style="risky")],
        set_flags=[],
        character_dialogue={
            "narrator": "",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Un paso más. Solo uno. ¿Qué podrías perder que no hayas perdido ya?"
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_vision_se_quiebra", act=5, zone="kadath_trono",
        text=(
            "La visión tiembla. Por un instante ves grietas en la imagen perfecta — "
            "como una pantalla que falla. Detrás de la promesa hay... ¿nada? "
            "¿O algo peor que nada? El trono sigue pulsando, indiferente a tu duda."
        ),
        on_enter=["stat:lucidez+1"],
        paths=[P("Resistir el encanto", "act5_resistencia_tentacion", style="careful")],
        set_flags=["vio_grietas_vision"],
        character_dialogue={
            "narrator": "Toda ilusión tiene costuras. Si sabes dónde mirar.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "No mires ahí. Mira lo que te ofrezco, no lo que hay detrás."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_resistencia_tentacion", act=5, zone="kadath_trono",
        text=(
            "Algo en ti se aferra — voluntad, memoria, terquedad pura. "
            "La visión no desaparece pero pierde su tirón hipnótico. "
            "Puedes pensar de nuevo. Y entonces, desde los bordes de la realidad, "
            "llegan los ecos de quienes conociste."
        ),
        on_enter=["stat:voluntad+1"],
        paths=[P("Atender a los ecos", "act5_cameo_deivid", style="careful")],
        set_flags=["resistio_tentacion"],
        character_dialogue={
            "narrator": "La voluntad es el último músculo que se rinde.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Hmm. Resistente. Eso lo hace más divertido."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_cameo_deivid", act=5, zone="kadath_trono",
        text=(
            "Una risa corta rompe el hechizo — familiar, burlona, imposible aquí.\n\n"
            "Un eco de Deivid resuena desde ninguna parte: la silueta de una mano "
            "haciendo un gesto que reconoces. 'Mano así es el meme', dice la voz, "
            "y se desvanece como humo de cigarro. Pero bastó para que parpadearas."
        ),
        on_enter=["stat:lucidez+1"],
        paths=[P("Sacudir la cabeza", "act5_cameo_heku", style="careful")],
        set_flags=["cameo_deivid_final"],
        character_dialogue={
            "narrator": "",
            "deivid": "Mano así es el meme. No te sientes en esa vaina loco.",
            "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="deivid"
    ))

    nodes.append(N(
        "act5_cameo_heku", act=5, zone="kadath_trono",
        text=(
            "Una melodía. Sin instrumento, sin cuerpo que la produzca — solo "
            "notas flotando en el aire de Kadath como pétalos de un árbol invisible. "
            "Reconoces la tonada: es de Heku. Una canción que escuchaste hace "
            "vidas, en otro acto de este sueño. Te ancla."
        ),
        on_enter=["stat:memoria+1"],
        paths=[P("Escuchar hasta que termine", "act5_cameo_blueber", style="careful")],
        set_flags=["cameo_heku_final"],
        character_dialogue={
            "narrator": "La música persiste donde la carne no puede.",
            "deivid": "",
            "heku": "♪ ...ni el olvido borra lo que el sueño escribió... ♪",
            "blueber": "", "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="heku"
    ))

    nodes.append(N(
        "act5_cameo_blueber", act=5, zone="kadath_trono",
        text=(
            "Una sombra azul parpadea al borde de tu visión. Blueber — o lo que "
            "queda de Blueber en las Dreamlands — aparece y desaparece como "
            "interferencia en una señal. Cada vez que aparece, está en una pose "
            "diferente. Señalando el trono. Señalando el vacío. Señalándote a ti."
        ),
        on_enter=[],
        paths=[P("Volver al momento presente", "act5_nyar_presiona", style="careful")],
        set_flags=["cameo_blueber_final"],
        character_dialogue={
            "narrator": "Presente y ausente. Como todo en los sueños.",
            "deivid": "", "heku": "",
            "blueber": "...[estática]... elige... [estática]... bien...",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="blueber"
    ))

    nodes.append(N(
        "act5_nyar_presiona", act=5, zone="kadath_trono",
        text=(
            "—Basta de fantasmas —dice Nyarlathotep, y su voz tiene filo—. "
            "El trono no esperará eternamente. Las Dreamlands se deshilachan "
            "mientras dudas. Cada segundo sin ocupante es un sueño que muere "
            "en algún lugar. ¿Eso quieres? ¿Ser responsable de la nada?"
        ),
        on_enter=["stat:voluntad-1", "stat:corrupcion+1"],
        paths=[P("Enfrentar la decisión", "act5_momento_verdad", style="bold")],
        set_flags=[],
        character_dialogue={
            "narrator": "",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Decide. O decidiré por ti. Y no te gustará mi elección."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_momento_verdad", act=5, zone="kadath_trono",
        text=(
            "El trono de ónice. El vacío alrededor. Nyarlathotep esperando. "
            "Los ecos de todos los que conociste resonando en tu memoria. "
            "Este es el momento. No hay más camino hacia adelante — solo la elección.\n\n"
            "¿Qué haces?"
        ),
        on_enter=["stat:lucidez+1"],
        paths=[P("Tomar tu decisión", "act5_eleccion_final", style="bold")],
        set_flags=["momento_verdad_alcanzado"],
        character_dialogue={
            "narrator": "Todo te trajo aquí. Cada paso, cada pérdida, cada alianza.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "..."
        },
        primary_npc="narrator"
    ))

    # ═══════════════════════════════════════════════════════════════
    # FASE 3 — LA ELECCIÓN FINAL (20 nodos)
    # ═══════════════════════════════════════════════════════════════

    nodes.append(N(
        "act5_eleccion_final", act=5, zone="kadath_trono",
        text=(
            "Seis caminos se abren ante ti — no como puertas físicas, "
            "sino como certezas. Sabes, con la claridad absoluta del sueño, "
            "que cada una es real. Que cada una tiene consecuencias. "
            "Que no hay vuelta atrás."
        ),
        on_enter=[],
        paths=[
            P("Sentarse en el trono", "act5_path_trono", style="risky"),
            P("Intentar despertar", "act5_path_despertar", style="careful"),
            P("Quedarse en las Dreamlands", "act5_path_quedarse", style="bold"),
            P("Aceptar la transformación", "act5_path_transformacion", style="risky"),
            P("Hacer un último trato", "act5_path_trato", style="risky"),
            P("Caer al vacío", "act5_path_vacio", style="risky")
        ],
        set_flags=["eleccion_final_presentada"],
        character_dialogue={
            "narrator": "Seis destinos. Una vida. Elige.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Al fin. Muéstrame quién eres realmente."
        },
        primary_npc="narrator"
    ))

    # --- PATH 1: SENTARSE EN EL TRONO ---
    nodes.append(N(
        "act5_path_trono", act=5, zone="kadath_trono",
        text=(
            "Te acercas al trono. El ónice vibra bajo tus pies. "
            "Nyarlathotep se aparta — ¿con reverencia o con satisfacción? "
            "Imposible saberlo. Te das la vuelta y te sientas."
        ),
        on_enter=["stat:corrupcion+2", "stat:voluntad+1"],
        paths=[
            P("Reclamar el poder con dignidad", "act5_trono_digno",
              style="bold", conditions=["flag:digno_de_kadath", "stat:voluntad>=7"]),
            P("Sentir cómo el trono te consume", "act5_trono_consumido", style="risky")
        ],
        set_flags=["eligio_trono"],
        character_dialogue={
            "narrator": "El peso de eones cae sobre tus hombros.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Sí... SÍ."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_trono_digno", act=5, zone="kadath_trono",
        text=(
            "El trono te acepta — no como amo, sino como guardián. "
            "Sientes las Dreamlands fluir a través de ti: cada sueño, "
            "cada pesadilla, cada deseo nocturno. Y los sostienes. "
            "Nyarlathotep inclina la cabeza. Por primera vez, parece... sorprendido."
        ),
        on_enter=["stat:lore+3"],
        paths=[P("Asumir el rol", "act5_ending_trono", style="bold")],
        set_flags=["trono_aceptado_digno"],
        character_dialogue={
            "narrator": "Un nuevo guardián para un trono antiguo.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "...No esperaba esto. Interesante."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_trono_consumido", act=5, zone="kadath_trono",
        text=(
            "El trono te devora. No con dientes — con información. "
            "Tu identidad se disuelve en el ónice como sal en agua. "
            "Lo último que escuchas es la carcajada de Nyarlathotep, "
            "larga y genuina, resonando por toda Kadath."
        ),
        on_enter=["stat:corrupcion+5", "stat:lucidez-3"],
        paths=[P("Perderte", "act5_ending_carcajada", style="risky")],
        set_flags=["trono_consumido"],
        character_dialogue={
            "narrator": "Otro peón. Otro juguete. Otra broma cósmica.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "JAJAJAJA. Cada vez caen. CADA VEZ."
        },
        primary_npc="nyarlathotep"
    ))

    # --- PATH 2: INTENTAR DESPERTAR ---
    nodes.append(N(
        "act5_path_despertar", act=5, zone="kadath_trono",
        text=(
            "Cierras los ojos. No al trono — al sueño entero. "
            "Buscas dentro de ti el hilo que te conecta al mundo de vigilia. "
            "Está ahí, tenue, casi roto por el viaje. Pero está."
        ),
        on_enter=["stat:voluntad+2"],
        paths=[
            P("Tirar del hilo con fuerza", "act5_despertar_lucido",
              style="bold", conditions=["stat:lucidez>=8", "stat:memoria>=6"]),
            P("Tirar del hilo con fuerza", "act5_despertar_olvido", style="careful")
        ],
        set_flags=["eligio_despertar"],
        character_dialogue={
            "narrator": "El camino de vuelta siempre existió.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "¿Huir? ¿Después de todo esto? ...Qué desperdicio."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_despertar_lucido", act=5, zone="kadath_trono",
        text=(
            "El hilo responde. Las Dreamlands se pliegan a tu alrededor "
            "como un libro que se cierra. Pero no olvidas — llevas todo contigo. "
            "Cada lección, cada nombre, cada rostro. Despiertas completo."
        ),
        on_enter=["stat:memoria+3"],
        paths=[P("Abrir los ojos", "act5_ending_despertar", style="bold")],
        set_flags=["despertar_lucido"],
        character_dialogue={
            "narrator": "Recordar es la forma más valiente de despertar.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_despertar_olvido", act=5, zone="kadath_trono",
        text=(
            "El hilo se rompe al tirarlo. Despiertas — pero vacío. "
            "Las Dreamlands se borran de tu mente como tinta bajo la lluvia. "
            "Nombres, rostros, el trono, Kadath... todo se vuelve un sueño "
            "que no puedes recordar. Solo queda una melancolía sin nombre."
        ),
        on_enter=["stat:memoria-5"],
        paths=[P("Olvidar", "act5_ending_olvido", style="careful")],
        set_flags=["despertar_con_olvido"],
        character_dialogue={
            "narrator": "Algunos despertares son pequeñas muertes.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Ni siquiera recordarás que perdiste. Eso es... misericordia."
        },
        primary_npc="nyarlathotep"
    ))

    # --- PATH 3: QUEDARSE EN LAS DREAMLANDS ---
    nodes.append(N(
        "act5_path_quedarse", act=5, zone="kadath_trono",
        text=(
            "No el trono. No el despertar. Las Dreamlands mismas — "
            "como habitante, como leyenda, como parte del tejido onírico. "
            "Rechazas el poder y eliges el mundo."
        ),
        on_enter=["stat:voluntad+1", "stat:favor+1"],
        paths=[
            P("Caminar hacia las Dreamlands como héroe", "act5_quedarse_legado",
              style="bold", conditions=["stat:favor>=7", "stat:lore>=6"]),
            P("Disolverse en el sueño colectivo", "act5_quedarse_canto", style="careful")
        ],
        set_flags=["eligio_quedarse"],
        character_dialogue={
            "narrator": "No gobernar el sueño. Ser parte de él.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "¿Rechazas el trono para ser... nadie? Fascinante."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_quedarse_legado", act=5, zone="kadath_trono",
        text=(
            "Bajas de Kadath no como rey, sino como caminante. "
            "Pero las Dreamlands te recuerdan — en Ulthar cuentan tu historia, "
            "en Celephais cantan tu nombre, los gatos te saludan al pasar. "
            "Eres leyenda viva. Eres legado."
        ),
        on_enter=["stat:favor+3"],
        paths=[P("Vivir la leyenda", "act5_ending_legado", style="bold")],
        set_flags=["quedarse_como_legado"],
        character_dialogue={
            "narrator": "Hay formas de inmortalidad más amables que un trono.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_quedarse_canto", act=5, zone="kadath_trono",
        text=(
            "Tu forma se adelgaza. Te vuelves parte del sueño — no una persona, "
            "sino una canción que los soñadores escuchan sin saber de dónde viene. "
            "Pierdes el cuerpo pero ganas eternidad. Eres el canto de las Dreamlands."
        ),
        on_enter=["stat:lucidez-2", "stat:memoria+2"],
        paths=[P("Convertirse en canción", "act5_ending_canto", style="careful")],
        set_flags=["quedarse_como_canto"],
        character_dialogue={
            "narrator": "No todos los finales tienen forma humana.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    # --- PATH 4: ACEPTAR LA TRANSFORMACIÓN ---
    nodes.append(N(
        "act5_path_transformacion", act=5, zone="kadath_trono",
        text=(
            "No el trono de los dioses — el trono de abajo. "
            "Aceptas lo que los túneles te ofrecieron. La transformación "
            "que comenzó en las profundidades puede completarse aquí, "
            "en la cima, donde la frontera entre formas es más delgada."
        ),
        on_enter=["stat:corrupcion+2"],
        paths=[
            P("Transformarse con propósito", "act5_transform_arquitecto",
              style="bold", conditions=["flag:pacto_ghoul", "stat:lore>=7"]),
            P("Dejarse transformar", "act5_transform_ghoul", style="risky")
        ],
        set_flags=["eligio_transformacion"],
        character_dialogue={
            "narrator": "La carne es solo un borrador. Siempre lo fue.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Ah, la opción que menos esperaba. Delicioso."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_transform_arquitecto", act=5, zone="kadath_trono",
        text=(
            "La transformación no te consume — la diriges. "
            "Te conviertes en algo nuevo: ni ghoul ni humano ni dios. "
            "Un arquitecto de los espacios entre sueños. "
            "Construirás nuevas Dreamlands donde nadie soñó antes."
        ),
        on_enter=["stat:lore+3", "stat:corrupcion+1"],
        paths=[P("Construir", "act5_ending_arquitectura", style="bold")],
        set_flags=["transformacion_arquitecto"],
        character_dialogue={
            "narrator": "Ni arriba ni abajo. Entre. Siempre entre.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_transform_ghoul", act=5, zone="kadath_trono",
        text=(
            "La transformación te toma entero. Huesos se reconfiguran, "
            "piel se endurece, los ojos aprenden a ver en la oscuridad total. "
            "Olvidas tu nombre humano. Pero ganas otro — uno que los ghouls "
            "cantarán en sus festines por siglos."
        ),
        on_enter=["stat:corrupcion+4", "stat:memoria-2"],
        paths=[P("Descender", "act5_ending_ghouls", style="risky")],
        set_flags=["transformacion_ghoul_completa"],
        character_dialogue={
            "narrator": "Hay hogares que exigen que dejes de ser quien eras.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Bienvenido a la familia más antigua del sueño."
        },
        primary_npc="nyarlathotep"
    ))

    # --- PATH 5: HACER UN ÚLTIMO TRATO ---
    nodes.append(N(
        "act5_path_trato", act=5, zone="kadath_trono",
        text=(
            "—Espera —dices—. No acepto ni rechazo. Negociemos.\n\n"
            "Nyarlathotep arquea una ceja. Por un instante, parece genuinamente "
            "interesado. —¿Negociar? ¿Conmigo? ¿Aquí? ...Tienes agallas."
        ),
        on_enter=["stat:voluntad+1"],
        paths=[
            P("Proponer un intercambio justo", "act5_trato_justo",
              style="bold", conditions=["stat:voluntad>=8", "flag:nyarlathotep_conocido"]),
            P("Intentar engañarlo", "act5_trato_mercantil", style="risky")
        ],
        set_flags=["eligio_trato"],
        character_dialogue={
            "narrator": "Negociar con el Caos Reptante. Pocos lo intentaron. Menos sobrevivieron.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Habla. Pero elige bien tus palabras."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_trato_justo", act=5, zone="kadath_trono",
        text=(
            "Le ofreces algo que no esperaba: tu historia. No tu alma, "
            "no tu cuerpo — tu narrativa. El derecho a contar lo que pasó aquí. "
            "A Nyarlathotep, coleccionista de historias cósmicas, "
            "esto le resulta... irresistible."
        ),
        on_enter=["stat:favor+2", "stat:lore+1"],
        paths=[P("Cerrar el trato", "act5_ending_negocio", style="bold")],
        set_flags=["trato_narrativo"],
        character_dialogue={
            "narrator": "Un trato entre iguales. O la ilusión perfecta de uno.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "...Aceptado. Eres más interesante de lo que pensé."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_trato_mercantil", act=5, zone="kadath_trono",
        text=(
            "Intentas engañar al Caos Reptante. Él lo sabe — por supuesto que lo sabe. "
            "Pero le divierte. Te deja creer que ganaste. El trato se cierra "
            "con una sonrisa que tiene demasiados dientes. "
            "Obtienes lo que pediste. Pero el precio... el precio vendrá después."
        ),
        on_enter=["stat:corrupcion+3"],
        paths=[P("Aceptar las consecuencias", "act5_ending_mercantil", style="risky")],
        set_flags=["trato_mercantil"],
        character_dialogue={
            "narrator": "Nadie engaña al mensajero de los Dioses Exteriores. Nadie.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "Trato hecho. Placer hacer negocios contigo. Je."
        },
        primary_npc="nyarlathotep"
    ))

    # --- PATH 6: CAER AL VACÍO ---
    nodes.append(N(
        "act5_path_vacio", act=5, zone="kadath_trono",
        text=(
            "Ni trono ni despertar ni trato. Te acercas al borde de la meseta "
            "y miras el vacío que rodea Kadath — ese abismo que no es espacio "
            "sino posibilidad pura. Y saltas."
        ),
        on_enter=["stat:voluntad+2", "stat:lucidez-1"],
        paths=[
            P("Caer con los ojos abiertos", "act5_vacio_biblioteca",
              style="bold", conditions=["stat:lore>=8"]),
            P("Caer sin resistencia", "act5_vacio_puro", style="risky")
        ],
        set_flags=["eligio_vacio"],
        character_dialogue={
            "narrator": "El acto más libre. O el más cobarde. O ambos.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "¡NO! ...Espera. ...Hmm. No. Déjalo. Que caiga."
        },
        primary_npc="nyarlathotep"
    ))

    nodes.append(N(
        "act5_vacio_biblioteca", act=5, zone="kadath_trono",
        text=(
            "Caes — pero el vacío no es vacío. Es una biblioteca. "
            "Infinita, imposible, hecha de todos los sueños que nunca se soñaron. "
            "Aterrizas entre estantes que contienen libros escritos en idiomas "
            "que aún no existen. Y comprendes: este era el verdadero tesoro de Kadath."
        ),
        on_enter=["stat:lore+5"],
        paths=[P("Leer eternamente", "act5_ending_biblioteca", style="bold")],
        set_flags=["encontro_biblioteca"],
        character_dialogue={
            "narrator": "Debajo del poder, debajo del trono: conocimiento.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "", "nyarlathotep": ""
        },
        primary_npc="narrator"
    ))

    nodes.append(N(
        "act5_vacio_puro", act=5, zone="kadath_trono",
        text=(
            "Caes y no dejas de caer. No hay fondo. No hay biblioteca, "
            "no hay revelación, no hay premio oculto. Solo el vacío — "
            "puro, absoluto, eterno. Y en ese vacío, lentamente, "
            "dejas de ser. No mueres. Simplemente... ya no estás."
        ),
        on_enter=["stat:lucidez-3", "stat:memoria-3"],
        paths=[P("Desvanecerse", "act5_ending_vacio", style="risky")],
        set_flags=["cayo_al_vacio_puro"],
        character_dialogue={
            "narrator": "Algunos abismos no tienen fondo. Ni lección. Ni sentido.",
            "deivid": "", "heku": "", "blueber": "",
            "edyssey": "", "dama": "",
            "nyarlathotep": "...Qué desperdicio."
        },
        primary_npc="nyarlathotep"
    ))

    return nodes
