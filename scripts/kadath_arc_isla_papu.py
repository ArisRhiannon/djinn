"""Arco de la Isla de Papu — EXPANDIDO (74 nodos)."""

from __future__ import annotations
from typing import Any, Callable, Dict, List


def build_arc_isla_papu(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 2
    nodes: List[Dict[str, Any]] = []

    nodes.append(N(
        "act2_papu_te_duerme",
        act=A, zone="Sarkomand — Te Duerme",
        tone="horror",
        text=(
            "No pasa como pensabas. Papu no te agarra, no te grita, no te"
            "apunta con nada. Sólo sonríe — esa sonrisa ancha que no debería"
            "dar tanto miedo — y sigue hablando. Su voz se vuelve más suave,"
            "más rítmica. Tú empiezas a sentir el mundo más denso, los oídos"
            "llenos de algodón tibio. El aire huele a algo dulce — orgánico,"
            "como fruta demasiado madura pudriéndose en plata.  — *ah ya mano,"
            "sisis. tranqui, te llevo al showroom. allá vas a ver el catálogo"
            "entero. waos, xd, no te resistas que igual llegas.*  Las piernas"
            "dejan de responder. El suelo sube. El sonido se apaga como una"
            "radio perdiendo señal. Piensas: no. Pero el pensamiento se"
            "disuelve antes de terminar.  Lo último que sientes antes de caer"
            "es la mano rechoncha de Papu guiándote la cabeza para que no te"
            "golpees. Casi gentil. Casi humano."
        ),
        on_enter={"voluntad": -8, "lucidez": -10, "memoria": -8, "corrupcion": 5},
        set_flags=["hablo_con_papu", "capturado_por_papu", "estuvo_en_isla_papu"],
        primary_npc="papu_el_relajado",
        character_dialogue={
            "aris": "me está durmiendo sin que pueda evitarlo. el mundo se pone denso",
            "law": "bro me está durmiendo SIN TOCARME no puedo moverme PAPU ALEJATE NO",
            "haru": "no mano me está durmiendo con la voz, putamadre no puedo ni moverme ya",
            "elyko": "te durmio hablando. ni te diste cuenta. el mundo se puso denso.",
            "xoft": "LKDSAJKLDSAJK ME DURMIO HABLANDO el gordo ni me di cuenta mano",
            "xokram": "Mano me durmió sin que me diera cuenta, eso no es justo pije",
            "daraziel": "El mundo se pone denso y los oídos se llenan de algodón. Mano esto no se ve bien.",
        },
        paths=[
            P("...", "act2_isla_despertar", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_despertar",
        act=A, zone="Isla de Papu — Jaula Estrecha",
        tone="horror",
        text=(
            "Despiertas en una jaula de latón apenas más alta que tú. El metal"
            "está frío — un frío húmedo que se te mete en los huesos cuando lo"
            "tocas. El techo es bajo, la madera huele a mar viejo y a moho, a"
            "sal acumulada durante lunas y lunas. El aire es pegajoso, denso,"
            "difícil de respirar.  A tu lado, una hilera de jaulas con sombras"
            "pequeñas adentro — soñadores jóvenes, entidades oníricas sin"
            "dueño. Algunas se mueven. Otras no. El sonido de cadenas"
            "tintineando llena el espacio como una música enferma, metálica,"
            "sin ritmo.  Afuera, un salón enorme con alfombras rojas que"
            "absorben la luz de las lámparas de aceite verde. Todo tiene un"
            "tono enfermizo, submarino. Papu camina entre las jaulas saludando"
            "a visitantes encapuchados, su voz lejana rebotando en las paredes"
            "altas.  Piensas: ¿cuánto tiempo? ¿Cuánto tiempo llevas aquí? El"
            "entumecimiento en las piernas dice: demasiado."
        ),
        on_enter={"voluntad": -3, "lucidez": -5, "memoria": -3},
        character_dialogue={
            "aris": "estoy en una jaula. literal soy mercancía ahora",
            "law": "MANO ESTOY EN UNA JAULA bro dónde estoy QUÉ PASÓ",
            "haru": "nmms desperté en una jaula con sombras al lado, qué pedo",
            "elyko": "jaula de latón. hilera de jaulas. salón con alfombras rojas. entendido.",
            "xoft": "mano estoy en una JAULA. literal me enjaularon como animal",
            "xokram": "Desperté enjaulado mano, esto es lo peor que me ha pasado",
            "daraziel": "Jaula estrecha, techo bajo. El espacio está diseñado para oprimir.",
        },
        paths=[
            P("Escuchar a la sombra de al lado", "act2_isla_sombra_vecina", style="info", effects={"lucidez": 2}),
            P("Examinar tu jaula en detalle", "act2_isla_examinar_jaula", style="primary", effects={"lore": 2}),
            P("Gritar pidiendo ayuda", "act2_isla_gritar", style="danger", effects={"voluntad": 3, "lucidez": -4}),
            P("Quedarte quieto y observar", "act2_isla_observar_salon", style="secondary", effects={"lucidez": 3, "lore": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_sombra_vecina",
        act=A, zone="Isla de Papu — Sombra Vecina",
        tone="tense",
        text=(
            "La sombra de al lado no tiene cara definida — un borrón oscuro"
            "que respira. Pero susurra con claridad, su voz fría como metal: —"
            "*Llevas dos lunas dormido. Eres el lote catorce. La subasta es"
            "esta noche. Los que no se venden... se disuelven.*  El aire entre"
            "las jaulas huele a sal vieja y a algo dulce-podrido. Las lámparas"
            "de aceite verde proyectan sombras que se mueven solas. En algún"
            "lugar, cadenas se arrastran contra piedra.  Te dice que hay siete"
            "sombras conscientes como ella. Que llevan lunas planeando algo."
            "Que necesitan a alguien con manos sólidas — alguien como tú."
            "Piensas: mi mejor aliado es humo con voz."
        ),
        on_enter={"lore": 5, "memoria": 3},
        set_flags=["sombras_confian_en_ti"],
        character_dialogue={
            "aris": "lote catorce. dos lunas dormido. los que no se venden se disuelven",
            "law": "LOTE CATORCE?? me van a VENDER bro no no no no",
            "haru": "soy el lote 14 y si no me venden me disuelvo, peak situación xd",
            "elyko": "lote 14. subasta esta noche. los no vendidos se disuelven. noted.",
            "xoft": "me catalogaron como LOTE CATORCE. mano me van a subastar",
            "xokram": "Lote 14, subasta esta noche. necesito salir antes de eso",
            "daraziel": "Lote catorce. La numeración implica al menos trece antes que yo.",
        },
        paths=[
            P("Aceptar ayudar a las sombras", "act2_isla_plan_sombras", style="success", effects={"voluntad": 4, "favor": 3}),
            P("Pedirle más información sobre la subasta", "act2_isla_info_subasta", style="info", effects={"lore": 4, "lucidez": -2}),
            P("Ignorarla y buscar tu propia salida", "act2_isla_examinar_jaula", style="warning", effects={"favor": -3, "voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_examinar_jaula",
        act=A, zone="Isla de Papu — Examinando la Jaula",
        tone="tense",
        text=(
            "La jaula tiene barrotes de latón oxidado — el metal está frío y"
            "áspero bajo tus dedos, con una textura granulada que te recuerda"
            "a hueso viejo. Donde lo tocas, te queda un residuo verdoso en la"
            "piel. El techo no está soldado — está atornillado con tornillos"
            "viejos, corroídos por la sal del aire. Con suficiente fuerza o"
            "algo puntiagudo, podrías aflojarlos. Los examinas uno por uno:"
            "cuatro tornillos, cuatro oportunidades.  En el suelo de la jaula"
            "hay una marca grabada — quemada en la madera con algo caliente:"
            "«LOTE 14 — SOÑADOR SÓLIDO — RESERVA: 8 MONEDAS». Debajo, en letra"
            "más pequeña, casi ilegible bajo la mugre: «Cliente preferente: La"
            "Dama de Porcelana».  El nombre te produce un escalofrío que no"
            "tiene explicación racional. Las cadenas de las jaulas vecinas"
            "tintinean suavemente — un sonido metálico, constante, como un"
            "reloj que cuenta algo que no es tiempo. Piensas: ya tengo dueña."
            "Antes de que empiece la subasta, ya tengo dueña."
        ),
        on_enter={"lore": 4},
        set_flags=["sabe_precio_propio"],
        character_dialogue={
            "aris": "tornillos viejos en el techo. y ya tengo compradora preferente",
            "law": "RESERVA 8 MONEDAS?? tengo PRECIO bro. y una Dama de Porcelana me quiere",
            "haru": "tengo precio de reserva y una clienta VIP, nmms qué asco",
            "elyko": "techo atornillado, no soldado. punto débil. y ya hay compradora.",
            "xoft": "me pusieron PRECIO. 8 monedas. y una tipa ya me reservó. mano.",
            "xokram": "8 monedas de reserva, eso es bajo. y ya hay clienta preferente",
            "daraziel": "Tornillos viejos, no soldadura. El techo es el punto débil estructural.",
        },
        paths=[
            P("Intentar aflojar los tornillos con las uñas", "act2_isla_forzar_techo", style="warning", effects={"voluntad": -3, "lucidez": -2}),
            P("Buscar algo puntiagudo en el suelo", "act2_isla_buscar_herramienta", style="primary", effects={"lore": 2}),
            P("Esperar a que alguien abra la jaula", "act2_isla_esperar_apertura", style="secondary", effects={"lucidez": 2, "memoria": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_gritar",
        act=A, zone="Isla de Papu — Grito",
        tone="horror",
        text=(
            "Gritas. El sonido rebota en las paredes del salón — un eco húmedo"
            "que vuelve distorsionado, como si las paredes lo masticaran antes"
            "de devolverlo. Todas las sombras de las jaulas vecinas se"
            "encogen; algunas emiten un quejido fino, como porcelana"
            "frotándose contra porcelana. El aire se espesa con olor a"
            "incienso quemado y sal vieja.  Un guardia — un Hombre de Leng con"
            "la piel mal cosida, los puntos supurando algo amarillento — se"
            "acerca y golpea tu jaula con un bastón de hueso. El impacto"
            "resuena en tus dientes. El metal frío vibra contra tu espalda.  —"
            "*Silencio, lote catorce. Los que gritan se venden con descuento.*"
            "*Mierda. Mierda. Piensa.* El pecho te aprieta. Las lámparas de"
            "aceite verde tiñen todo de un color enfermo.  Papu aparece"
            "detrás, con ese olor dulzón que siempre lo precede: — *mano,"
            "sisis, tranqui. no grites que me bajas el precio. waos. te"
            "conviene estar calladito.*"
        ),
        on_enter={"voluntad": -4, "lucidez": -3, "favor": -2},
        set_flags=["grito_en_jaula"],
        character_dialogue={
            "aris": "grité y me bajaron el precio. no debí hacer eso",
            "law": "ME GOLPEARON LA JAULA bro y Papu me dijo que me calle NO",
            "haru": "grité y un guardia me pegó la jaula, Papu dice que me baja el precio xd",
            "elyko": "gritar = descuento. error táctico. ahora saben que estoy despierto.",
            "xoft": "me golpearon la jaula por gritar. Papu dice que me baja el precio. mano.",
            "xokram": "Grité y me bajaron el precio, pésima jugada mano",
            "daraziel": "El guardia tiene la piel mal cosida. Hombre de Leng. No debí gritar.",
        },
        paths=[
            P("Callarte y observar", "act2_isla_observar_salon", style="secondary", effects={"lucidez": 3}),
            P("Escupirle al guardia", "act2_isla_escupir_guardia", style="danger", effects={"voluntad": 5, "lucidez": -5}),
        ],
    ))

    nodes.append(N(
        "act2_isla_observar_salon",
        act=A, zone="Isla de Papu — Observando el Salón",
        tone="tense",
        text=(
            "Finges dormir. Cierras los ojos casi del todo — apenas una"
            "rendija. Observas. El salón tiene forma de anfiteatro con un"
            "escenario central elevado, iluminado por lámparas de aceite verde"
            "que tiñen todo de un color submarino, enfermo. El olor a incienso"
            "y a cuerpos que no son del todo cuerpos te llena la nariz."
            "Cuentas: dieciocho jaulas en semicírculo, dos guardias por puerta"
            "(cuatro puertas), un pasillo lateral sin vigilancia, y una"
            "escalera que sube al piso de Papu.  Los clientes llegan de a"
            "poco. Sus pasos suenan distintos — algunos húmedos, otros huecos."
            "Capuchas de distintos colores: verde (Hombres de Leng), negra"
            "(sacerdotes sin rostro), blanca (uno solo — la Dama de"
            "Porcelana). Cada uno examina jaulas distintas. El aire se enfría"
            "cuando la Dama pasa. Se detiene frente a la tuya. *No te muevas."
            "No respires fuerte.* El pecho te aprieta."
        ),
        on_enter={"lore": 6, "lucidez": 3},
        set_flags=["mapeo_la_mansion"],
        character_dialogue={
            "aris": "18 jaulas, 4 puertas, 2 guardias cada una. pasillo sin vigilancia",
            "law": "la Dama de Porcelana se paró frente a MI jaula bro NO",
            "haru": "la de blanco se paró frente a mi jaula, qué asco mano",
            "elyko": "4 puertas, 8 guardias, 1 pasillo ciego, 1 escalera. la dama me mira.",
            "xoft": "la Dama de Porcelana me está mirando. mano. me está evaluando.",
            "xokram": "Pasillo sin vigilancia, escalera arriba. y la Dama ya me fichó",
            "daraziel": "Anfiteatro semicircular. 18 jaulas. La Dama de blanco se detuvo aquí.",
        },
        paths=[
            P("Sostenerle la mirada a la Dama", "act2_isla_mirada_dama", style="danger", effects={"voluntad": 4, "corrupcion": 3}),
            P("Memorizar las salidas y esperar", "act2_isla_esperar_apertura", style="primary", effects={"lore": 3, "lucidez": 2}),
            P("Hablar con la sombra vecina ahora", "act2_isla_sombra_vecina", style="info", effects={"lucidez": 2}, conditions={"lacks_flag": "sombras_confian_en_ti"}),
        ],
    ))

    nodes.append(N(
        "act2_isla_plan_sombras",
        act=A, zone="Isla de Papu — Plan de las Sombras",
        tone="discovery",
        text=(
            "Las siete sombras conscientes te explican el plan en susurros"
            "coordinados — cada una dice una frase y la siguiente continúa."
            "Sus voces son como olas rompiendo en secuencia, una tras otra, y"
            "huelen a sal marina y a tinta disuelta. El aire entre las jaulas"
            "se enfría mientras hablan:  — *Cuando Papu abra tu jaula para el"
            "escenario...* — *...tú muerdes. Fuerte. En la mano de las"
            "llaves...* — *...nosotras empujamos desde adentro...* — *...las"
            "jaulas no aguantan siete a la vez...* — *...el caos es nuestra"
            "salida...* — *...tú corres al pasillo ciego...* — *...nosotras al"
            "mar.*  Silencio. Las cadenas tintinean suavemente. *Puede"
            "funcionar. Tiene que funcionar.* Sientes el latido en las sienes,"
            "el sabor metálico del miedo en la lengua."
        ),
        on_enter={"lore": 5, "voluntad": 4, "favor": 5},
        set_flags=["plan_sombras_completo"],
        character_dialogue={
            "aris": "plan coordinado entre siete. cada una dice una frase. eficiente",
            "law": "las sombras tienen un PLAN y hablan en CADENA bro esto es peak",
            "haru": "las sombras hablan en cadena como un plan de película, god",
            "elyko": "7 sombras, plan sincronizado. muerdo, empujan, caos, pasillo, mar.",
            "xoft": "las sombras tienen un plan COORDINADO. muerdo a Papu. ellas empujan.",
            "xokram": "Plan de 7 pasos. yo muerdo, ellas empujan, caos, cada quien corre",
            "daraziel": "Siete voces en secuencia. El plan tiene ritmo. Está bien diseñado.",
        },
        paths=[
            P("Aceptar el plan completo", "act2_isla_esperar_apertura", style="success", effects={"voluntad": 3, "favor": 3}, set_flags=["acepto_plan_sombras"]),
            P("Proponer una variante (escapar juntos)", "act2_isla_variante_plan", style="info", effects={"voluntad": 2, "lore": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_info_subasta",
        act=A, zone="Isla de Papu — Información de la Subasta",
        tone="tense",
        text=(
            "La sombra te cuenta lo que sabe. Su voz es un susurro que huele a"
            "sal marina y a tinta vieja — cada palabra te llega como si la"
            "escucharas dentro del cráneo:  — *Hay tres compradores"
            "principales. El Hombre de Leng compra sombras para disolver y"
            "usar como tinta ritual — las hierve vivas, dicen. El Sacerdote"
            "Sin Rostro compra para alimentar algo que tiene debajo del"
            "templo. Algo que zumba. Algo que siempre tiene hambre. Y la Dama"
            "de Porcelana... nadie sabe qué hace con lo que compra. Pero nunca"
            "devuelve nada. Nunca.*  El silencio después pesa. Las cadenas de"
            "las jaulas vecinas tintinean con una brisa que no debería existir"
            "aquí adentro.  — *Tú eres sólido. Eso te hace raro. Los tres van"
            "a pujar fuerte por ti.* — La sombra se encoge, como si decirlo en"
            "voz alta lo hiciera más real. *Mierda. Soy carne en un mercado.*"
        ),
        on_enter={"lore": 8, "lucidez": -3, "memoria": -2},
        set_flags=["sabe_compradores"],
        character_dialogue={
            "aris": "tres compradores. tinta ritual, alimento, y la dama que no devuelve nada",
            "law": "uno me disuelve, otro me come, y la Dama no devuelve NADA bro",
            "haru": "uno me hace tinta, otro me come, la dama no se sabe. todos malos xd",
            "elyko": "3 compradores: tinta ritual, alimento subterráneo, dama = desconocido.",
            "xoft": "me disuelven, me comen, o la Dama me desaparece. ninguno es bueno.",
            "xokram": "Tres compradores, tres destinos malos. soy mercancía premium",
            "daraziel": "Tinta, alimento, desaparición. Tres destinos. Ninguno tiene retorno.",
        },
        paths=[
            P("Preguntar cómo escapar", "act2_isla_plan_sombras", style="success", effects={"voluntad": 2}, conditions={"lacks_flag": "plan_sombras_completo"}),
            P("Volver a examinar tu jaula", "act2_isla_examinar_jaula", style="primary", effects={"lore": 2}, conditions={"lacks_flag": "jaula_abierta"}),
            P("Esperar la subasta", "act2_isla_esperar_apertura", style="secondary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_forzar_techo",
        act=A, zone="Isla de Papu — Forzando el Techo",
        tone="tense",
        text=(
            "Trabajas los tornillos en silencio. El clavo oxidado encaja"
            "apenas en la ranura — tienes que girar con los dedos, presionando"
            "hasta que las yemas se ponen blancas. El metal chirría contra"
            "metal: un sonido diminuto que en este silencio suena enorme. Uno"
            "cede. Dos. El tercero está más apretado — te sangran los dedos,"
            "la sangre hace el clavo resbaladizo, caliente contra el frío del"
            "latón. Pero el cuarto sale y el panel del techo se levanta apenas"
            "un centímetro.  Aire fresco — bueno, menos viciado — entra por la"
            "rendija. Puedes oler el pasillo: aceite de las lámparas verdes,"
            "piedra húmeda, libertad.  Podrías salir ahora — pero los guardias"
            "están haciendo ronda. Escuchas sus pasos pesados, el golpe"
            "rítmico de los bastones contra el suelo. Si esperas a que empiece"
            "la subasta, estarán distraídos. Si sales ahora, te arriesgas."
            "Las manos te tiemblan. No de miedo — de posibilidad."
        ),
        on_enter={"voluntad": 4, "lucidez": -2},
        set_flags=["jaula_abierta"],
        character_dialogue={
            "aris": "cuatro tornillos fuera. puedo salir. pero los guardias están cerca",
            "law": "ABRÍ LA JAULA bro pero los guardias están ahí ESPERO O SALGO",
            "haru": "abrí el techo de la jaula, pero hay guardias. espero o me arriesgo",
            "elyko": "techo abierto. guardias en ronda. timing: esperar a la subasta.",
            "xoft": "abrí la jaula. los guardias están cerca. salgo o espero. mano.",
            "xokram": "Jaula abierta pero guardias cerca. mejor esperar a la distracción",
            "daraziel": "Panel levantado. Un centímetro de libertad. Los guardias hacen ronda.",
        },
        paths=[
            P("Salir ahora (arriesgado)", "act2_isla_escape_temprano", style="danger", effects={"voluntad": 5, "lucidez": -5}),
            P("Esperar a que empiece la subasta", "act2_isla_pre_subasta", style="primary", effects={"lucidez": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_buscar_herramienta",
        act=A, zone="Isla de Papu — Buscando en el Suelo",
        tone="tense",
        text=(
            "Palpas el suelo de la jaula en la oscuridad. La paja está húmeda,"
            "pegajosa, huele a sudor ajeno y a algo dulce que preferirías no"
            "identificar. Tus dedos encuentran las grietas entre las tablas,"
            "la mugre acumulada de quién sabe cuántos lotes anteriores."
            "Debajo de una capa de paja sucia encuentras: un clavo oxidado —"
            "frío, áspero, con bordes que te cortan la yema del pulgar —, un"
            "trozo de espejo roto que refleja la luz verde de las lámparas de"
            "aceite en fragmentos enfermizos, y algo que parece un diente"
            "humano muy grande. Demasiado grande. Liso como porcelana al"
            "tacto.  El clavo serviría para los tornillos. El espejo para"
            "señales. El diente... no sabes para qué sirve un diente de ese"
            "tamaño. Pero el hecho de que esté aquí — de que alguien lo dejó o"
            "lo perdió — te aprieta el pecho con un frío que no tiene que ver"
            "con la temperatura."
        ),
        on_enter={"lore": 3},
        character_dialogue={
            "aris": "clavo oxidado, espejo roto, diente enorme. el clavo sirve para los tornillos",
            "law": "encontré un clavo y un espejo roto y un DIENTE ENORME qué es esto",
            "haru": "hay un clavo, un espejo y un diente gigante en el suelo, xd",
            "elyko": "clavo = tornillos. espejo = señales. diente = desconocido.",
            "xoft": "clavo, espejo roto, diente enorme. el clavo me sirve mano",
            "xokram": "Clavo para los tornillos, espejo para señales. el diente no sé",
            "daraziel": "Tres objetos. El clavo es funcional. El espejo refleja. El diente inquieta.",
        },
        paths=[
            P("Tomar el clavo y atacar los tornillos", "act2_isla_forzar_techo", style="success", effects={"voluntad": 2}, give_item="clavo_oxidado"),
            P("Tomar el espejo (para después)", "act2_isla_esperar_apertura", style="info", effects={"lore": 2}, set_flags=["tiene_espejo"], give_item="espejo_roto"),
            P("Tomar el diente (instinto)", "act2_isla_esperar_apertura", style="warning", effects={"corrupcion": 3, "lore": 4}, set_flags=["tiene_diente"], give_item="diente_enorme"),
        ],
    ))

    nodes.append(N(
        "act2_isla_esperar_apertura",
        act=A, zone="Isla de Papu — Esperando",
        tone="tense",
        text=(
            "Las horas pasan. El salón se llena despacio — capuchas que entran"
            "por las cuatro puertas, pasos que no suenan como pasos humanos,"
            "el roce de telas que no son tela. Los murmullos crecen: un"
            "zumbido grave, constante, como abejas dentro de una pared. El"
            "olor a incienso se espesa hasta que casi puedes masticarlo. Las"
            "lámparas de aceite verde parpadean al ritmo de algo que no es"
            "viento.  Papu sube al escenario central y prueba un micrófono de"
            "hueso que amplifica su voz por todo el anfiteatro. El sonido de"
            "feedback es un chillido agudo que hace que todas las sombras en"
            "las jaulas se encojan.  — *sisis, mano, bienvenidos a la subasta"
            "número cuarenta y tres. hoy tenemos dieciocho lotes, tres"
            "premium. el catálogo está en sus asientos. empezamos en cinco"
            "minutos. waos.*  Cinco minutos. El corazón se te acelera. Las"
            "manos te sudan. Lo que hagas ahora determina cómo llegas al"
            "escenario — o si llegas."
        ),
        on_enter={"lucidez": -3, "voluntad": -2},
        character_dialogue={
            "aris": "subasta 43. dieciocho lotes. tres premium. cinco minutos",
            "law": "CINCO MINUTOS para que me subasten bro CINCO MINUTOS",
            "haru": "subasta 43, 18 lotes, 5 minutos. Papu con micrófono de hueso xd",
            "elyko": "subasta #43. 18 lotes. 3 premium. 5 minutos. soy premium.",
            "xoft": "cinco minutos para que me subasten. Papu con micrófono de hueso. mano.",
            "xokram": "Subasta 43, soy lote premium. cinco minutos para actuar",
            "daraziel": "Micrófono de hueso. Anfiteatro lleno. Cinco minutos. El diseño es teatral.",
        },
        paths=[
            P("Escapar ahora por el techo (si lo abriste)", "act2_isla_escape_temprano", style="success", effects={"voluntad": 5}, conditions={"has_flag": "jaula_abierta"}),
            P("Ejecutar el plan de las sombras (morder a Papu)", "act2_isla_morder_papu", style="warning", effects={"voluntad": 6}, conditions={"has_flag": "acepto_plan_sombras"}),
            P("Dejarte llevar al escenario", "act2_isla_pre_subasta", style="secondary", effects={"lucidez": -2, "memoria": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_escupir_guardia",
        act=A, zone="Isla de Papu — Escupitajo",
        tone="horror",
        text=(
            "Le escupes al Hombre de Leng. El escupitajo le cae en la piel mal"
            "cosida del cuello — donde los puntos de sutura negros se tensan"
            "sobre carne verdosa. No reacciona como un humano — se queda"
            "quieto, ladea la cabeza con un crujido de vértebras que suena a"
            "madera seca, y luego mete el bastón entre los barrotes y te"
            "golpea en las costillas.  Duele. Un dolor seco, profundo, que te"
            "roba el aire. Sientes el hueso del bastón frío incluso a través"
            "de la ropa. Pero lo peor es lo que dice después, con una voz que"
            "suena a cuero mojado arrastrándose sobre piedra:  — *Lote"
            "catorce. Marca de rebeldía. Precio sube. Los clientes pagan más"
            "por los que se resisten.*  Se aleja. El olor que deja — agrio,"
            "orgánico, como carne curada mal — se queda flotando entre los"
            "barrotes. Piensas: hasta mi rabia tiene precio aquí. Hasta eso me"
            "lo compran."
        ),
        on_enter={"voluntad": 4, "lucidez": -5, "memoria": -3},
        set_flags=["marca_rebeldia"],
        character_dialogue={
            "aris": "me golpeó y dijo que los rebeldes valen más. contraproducente",
            "law": "ME PEGÓ CON EL BASTÓN y dijo que ahora valgo MÁS por rebelde NO",
            "haru": "le escupí y me pegó, dice que los rebeldes valen más, nmms",
            "elyko": "escupí. me golpeó. marca de rebeldía = precio sube. error.",
            "xoft": "le escupí y me marcó como rebelde. dice que valgo MÁS ahora. mano.",
            "xokram": "Me marcaron como rebelde y subió mi precio. todo al revés",
            "daraziel": "El guardia tiene piel cosida. No reacciona como humano. Me marcó.",
        },
        paths=[
            P("Aguantar el dolor y esperar", "act2_isla_esperar_apertura", style="secondary", effects={"voluntad": 2}),
            P("Intentar quitarle el bastón", "act2_isla_forcejeo_guardia", style="danger", effects={"voluntad": 6, "lucidez": -4}, conditions={"voluntad_min": 40}),
        ],
    ))

    nodes.append(N(
        "act2_isla_mirada_dama",
        act=A, zone="Isla de Papu — La Dama Te Mira",
        tone="horror",
        text=(
            "Le sostienes la mirada. La máscara de porcelana no tiene ojos —"
            "sólo dos agujeros vacíos donde debería haber algo. Oscuridad pura"
            "detrás, sin fondo. Pero te ve. Lo sabes porque inclina la cabeza,"
            "como un pájaro examinando un insecto. Un clic suave de porcelana"
            "contra porcelana.  Se acerca. El aire se enfría tres grados."
            "Huele a flores secas y a algo debajo — algo que tu cuerpo"
            "reconoce como peligro antes que tu mente. Pone un dedo enguantado"
            "en el barrote de tu jaula. El metal se calienta donde lo toca —"
            "un calor que no es natural, que sube por el latón hasta tus"
            "manos.  — *Interesante. Sólido. Consciente. Esto vale más de"
            "ocho.*  *No me mires. No me mires.* Pero no puedes apartar los"
            "ojos de esos agujeros vacíos. Se aleja. El frío se va con ella."
            "Papu la sigue con la mirada, nervioso, frotándose las manos como"
            "si también las sintiera calientes."
        ),
        on_enter={"corrupcion": 5, "lore": 4, "lucidez": -3},
        set_flags=["dama_te_noto", "dama_interesada"],
        character_dialogue={
            "aris": "no tiene ojos detrás de la máscara. pero me ve. y dijo que valgo más",
            "law": "NO TIENE OJOS bro y me dijo que valgo más de ocho NOOOO",
            "haru": "la tipa no tiene ojos y dijo que valgo más, peak incómodo",
            "elyko": "sin ojos. me evaluó. dijo que valgo más de 8. papu se puso nervioso.",
            "xoft": "me miró SIN OJOS y dijo que valgo más. Papu se cagó. mano.",
            "xokram": "Dijo que valgo más de 8. Papu se puso nervioso. ella manda aquí",
            "daraziel": "La máscara no tiene ojos pero ve. El metal se calentó donde tocó.",
        },
        paths=[
            P("Hablarle directamente", "act2_isla_hablar_dama", style="danger", effects={"voluntad": 5, "corrupcion": 5}),
            P("Apartarte del barrote", "act2_isla_esperar_apertura", style="secondary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_variante_plan",
        act=A, zone="Isla de Papu — Variante del Plan",
        tone="discovery",
        text=(
            "Les propones escapar juntos — no separarse. Las sombras dudan. El"
            "susurro colectivo se apaga — silencio entre las jaulas, sólo el"
            "crujido del latón oxidado y el murmullo lejano de los clientes."
            "El olor a sal y aceite verde flota entre ustedes.  Una dice, su"
            "voz como metal frío: — *Somos humo. Tú eres sólido. Si nos"
            "llevas, te ralentizamos. Si nos dejas, llegamos al mar solas.*"
            "Otra añade — suena más vieja, más cansada: — *Pero si nos"
            "llevas... te debemos. Y una deuda de siete sombras pesa en los"
            "Yermos. Pesa como cadenas que no se rompen.*"
        ),
        on_enter={"lore": 4, "favor": 3},
        character_dialogue={
            "aris": "si las llevo me ralentizan pero me deben. deuda de siete sombras",
            "law": "si las llevo me deben una deuda de SIETE SOMBRAS bro eso suena fuerte",
            "haru": "me ralentizan pero me deben, una deuda de 7 sombras suena god",
            "elyko": "tradeoff: velocidad vs deuda de 7 sombras. la deuda pesa en los yermos.",
            "xoft": "si las llevo me deben. deuda de siete sombras. eso vale mano.",
            "xokram": "Deuda de 7 sombras a mi favor. eso es capital onírico serio",
            "daraziel": "Humo vs sólido. Si las llevo, deuda. Si no, llegan solas al mar.",
        },
        paths=[
            P("Llevarlas contigo (más lento, deuda a favor)", "act2_isla_esperar_apertura", style="success", effects={"favor": 8, "voluntad": -3}, set_flags=["acepto_plan_sombras", "lleva_sombras"]),
            P("Dejarlas ir solas al mar", "act2_isla_esperar_apertura", style="warning", effects={"favor": -2, "voluntad": 3}, set_flags=["acepto_plan_sombras", "abandono_sombras"]),
        ],
    ))

    nodes.append(N(
        "act2_isla_escape_temprano",
        act=A, zone="Isla de Papu — Escape Temprano",
        tone="tense",
        text=(
            "Sales por el techo de la jaula y caes al suelo del pasillo"
            "lateral. El impacto te sube por las rodillas — piedra fría,"
            "húmeda, resbaladiza. El aire aquí huele distinto: menos cuerpos,"
            "más sal, más moho. Los guardias están mirando hacia el escenario"
            "— Papu está haciendo su discurso de apertura, su voz amplificada"
            "por el micrófono de hueso rebotando en las paredes del"
            "anfiteatro. Tienes segundos antes de que alguien mire hacia aquí."
            "Las lámparas de aceite verde proyectan sombras largas que se"
            "mueven solas. El corazón te late en la garganta. Las manos te"
            "tiemblan — adrenalina pura, metálica, con sabor a sangre en la"
            "lengua.  El pasillo tiene tres direcciones: hacia la escalera de"
            "arriba (estudio de Papu), donde el aire es más cálido; hacia una"
            "ventana alta donde se ve el mar negro y se oye el golpe distante"
            "de las olas; o hacia la puerta trasera del salón, donde los"
            "murmullos de los clientes zumban como un enjambre."
        ),
        on_enter={"voluntad": 5, "lucidez": 3},
        set_flags=["escapo_antes_subasta"],
        character_dialogue={
            "aris": "fuera de la jaula. guardias distraídos. tres direcciones",
            "law": "SALÍ DE LA JAULA bro los guardias no me vieron VAMOS",
            "haru": "salí mientras Papu hablaba, los guardias mirando al escenario xd",
            "elyko": "fuera. guardias distraídos. 3 rutas: escalera, ventana, puerta trasera.",
            "xoft": "SALÍ. los guardias no me vieron. tengo segundos. mano.",
            "xokram": "Fuera de la jaula, guardias distraídos. tres opciones",
            "daraziel": "Caí al pasillo. Tres direcciones. Los guardias miran al escenario.",
        },
        paths=[
            P("Subir al estudio de Papu", "act2_isla_estudio_papu", style="info", effects={"lore": 3, "lucidez": -2}),
            P("Ir a la ventana alta (mar)", "act2_isla_ventana_mar", style="success", effects={"voluntad": 3}),
            P("Volver al salón por la puerta trasera (espiar)", "act2_isla_espiar_subasta", style="warning", effects={"lore": 5, "lucidez": -3}),
            P("Liberar otras jaulas antes de irte", "act2_isla_liberar_jaulas", style="danger", effects={"voluntad": 6, "favor": 8, "lucidez": -4}, conditions={"has_flag": "sombras_confian_en_ti"}),
        ],
    ))

    nodes.append(N(
        "act2_isla_pre_subasta",
        act=A, zone="Isla de Papu — Preparación para el Escenario",
        tone="horror",
        text=(
            "Dos guardias abren tu jaula. El chirrido del metal te eriza la"
            "piel. Te sacan sin violencia — con la eficiencia de quien mueve"
            "cajas. Manos frías, piel mal cosida que se te pega un instante al"
            "brazo. Te ponen de pie. Te limpian la cara con un trapo húmedo"
            "que huele a vinagre y a algo floral. Te peinan con dedos que no"
            "son del todo dedos.  Papu se acerca con un cartel que dice «LOTE"
            "14 — SOÑADOR SÓLIDO — CONSCIENTE — RESERVA 8». Te lo cuelga del"
            "cuello con un alambre que te raspa la nuca. El peso del cartel"
            "tira hacia abajo.  — *mano, sisis, te ves bien. los clientes van"
            "a pelear por ti. waos. no te muevas mucho en el escenario que se"
            "ve feo.* — Te guiña un ojo. Como si esto fuera normal. Como si"
            "fueras un producto y eso estuviera bien. *Esto no está bien. Nada"
            "de esto está bien.*"
        ),
        on_enter={"voluntad": -6, "lucidez": -4, "memoria": -3},
        set_flags=["en_escenario"],
        character_dialogue={
            "aris": "me limpiaron, me peinaron, me colgaron un cartel con mi precio",
            "law": "me PEINARON y me pusieron un CARTEL CON MI PRECIO bro soy mercancía",
            "haru": "me limpiaron y me colgaron un cartel con mi precio, nmms soy un producto",
            "elyko": "limpieza, peinado, cartel con precio. soy mercancía presentable.",
            "xoft": "me colgaron un CARTEL con mi PRECIO del cuello. mano. soy producto.",
            "xokram": "Me pusieron precio en el cuello. literal soy mercancía ahora",
            "daraziel": "Me prepararon como se prepara un objeto para exhibición. Cartel con precio.",
        },
        paths=[
            P("Resistirte en el último momento", "act2_isla_resistir_escenario", style="warning", effects={"voluntad": 5, "lucidez": -3}),
            P("Ir al escenario sin resistir", "act2_isla_escenario", style="secondary", effects={"lucidez": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_morder_papu",
        act=A, zone="Isla de Papu — Morder a Papu",
        tone="horror",
        text=(
            "Papu abre tu jaula con su manojo de llaves. El tintineo del metal"
            "resuena en tu pecho como una campana. — *sisis mano, lote"
            "catorce, tu turno. sal bonito que hay clientas VIP viéndote.*  Le"
            "muerdes la mano. Fuerte. Los dientes se hunden en carne que cede"
            "demasiado fácil. Sientes el sabor a sal y a algo que no es sangre"
            "— es más espeso, más dulce, empalagoso, te cubre la lengua como"
            "miel podrida. *No es humano. No es humano.* Papu GRITA: — *¡LPTM!"
            "¡LPTM MANO! ¡ME MORDIÓ! ¡WAOS!*  Las siete sombras empujan sus"
            "jaulas al unísono. El estruendo de metal llena el salón — un coro"
            "de cadenas y latón retorcido que ahoga los murmullos de los"
            "clientes. Las lámparas verdes oscilan. Caos."
        ),
        on_enter={"voluntad": 10, "lucidez": -5, "favor": 8},
        set_flags=["mordio_a_papu", "rebelion_isla_papu"],
        character_dialogue={
            "aris": "le mordí la mano. no es sangre lo que tiene. las sombras empujaron",
            "law": "LE MORDÍ LA MANO A PAPU y gritó LPTM y las sombras EXPLOTARON TODO",
            "haru": "le mordí la mano a Papu y gritó lptm, las sombras reventaron las jaulas",
            "elyko": "mordida ejecutada. no es sangre. las 7 sombras empujaron. caos.",
            "xoft": "LE MORDÍ LA MANO. no es sangre. LPTM gritó. las sombras explotaron.",
            "xokram": "Le mordí y las sombras empujaron. caos total. ahora a correr",
            "daraziel": "Le mordí. Lo que tiene no es sangre. Las jaulas estallan. Caos total.",
        },
        paths=[
            P("Correr al pasillo ciego en el caos", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}),
            P("Quedarte a liberar más jaulas", "act2_isla_liberar_jaulas", style="warning", effects={"favor": 10, "lucidez": -5}),
            P("Enfrentar a los guardias directamente", "act2_isla_enfrentar_guardias", style="danger", effects={"voluntad": 8, "lucidez": -6}),
        ],
    ))

    nodes.append(N(
        "act2_isla_forcejeo_guardia",
        act=A, zone="Isla de Papu — Forcejeo",
        tone="horror",
        text=(
            "Agarras el bastón entre los barrotes. El hueso es liso, frío, con"
            "una textura que se siente demasiado parecida a hueso humano. El"
            "Hombre de Leng tira. Tú tiras. Es más fuerte — mucho más fuerte,"
            "sientes los músculos del hombro gritar — pero tú estás"
            "desesperado. La desesperación pesa más que la fuerza.  El bastón"
            "se parte en dos con un crack seco que resuena en el salón. Te"
            "quedas con un trozo puntiagudo de hueso — afilado donde se"
            "rompió, con astillas que te pinchan la palma. Sangre tibia en la"
            "mano. Tu sangre.  El guardia te mira. No grita. No llama a nadie."
            "Sólo asiente, como si esto ya hubiera pasado antes — como si"
            "fuera parte del guión —, y se aleja a buscar otro bastón. Sus"
            "pasos son pesados, lentos, indiferentes. El olor agrio que deja"
            "se queda flotando.  Piensas: tengo un arma. Un hueso roto. Es lo"
            "mejor que he tenido en mucho tiempo."
        ),
        on_enter={"voluntad": 5, "lucidez": -3},
        set_flags=["tiene_hueso_puntiagudo"],
        give_item="hueso_puntiagudo",
        character_dialogue={
            "aris": "tengo un trozo de hueso puntiagudo. el guardia no llamó a nadie",
            "law": "TENGO UN HUESO PUNTIAGUDO bro el guardia se fue como si nada",
            "haru": "le partí el bastón y me quedé con un trozo, el guardia ni se inmutó xd",
            "elyko": "hueso puntiagudo obtenido. el guardia no alertó. esto ya pasó antes.",
            "xoft": "le partí el bastón. tengo un hueso. el guardia se fue tranquilo. raro.",
            "xokram": "Tengo un hueso puntiagudo. el guardia no alertó. sospechoso",
            "daraziel": "El bastón se partió. Hueso puntiagudo. El guardia se fue sin alertar.",
        },
        paths=[
            P("Usar el hueso para aflojar los tornillos", "act2_isla_forzar_techo", style="success", effects={"voluntad": 3}),
            P("Esconder el hueso y esperar", "act2_isla_esperar_apertura", style="primary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_hablar_dama",
        act=A, zone="Isla de Papu — Hablando con la Dama",
        tone="horror",
        text=(
            "— *¿Qué quieres de mí?* — le preguntas. Tu voz suena más pequeña"
            "de lo que esperabas. El aire entre ustedes huele a algo floral y"
            "podrido a la vez — como flores dejadas en agua estancada"
            "demasiado tiempo.  La Dama ladea la cabeza. Un clic suave —"
            "porcelana contra porcelana. La voz que sale no viene de la"
            "máscara — viene de todas partes a la vez, resuena en los"
            "barrotes, en el suelo, dentro de tu cráneo:  — *Tu sustancia. Tu"
            "sueño tiene textura. Los otros son humo; tú eres arcilla. Puedo"
            "hacer cosas con arcilla.*  Sientes náusea. Un frío que no es"
            "temperatura — es algo más profundo, como si tu cuerpo reconociera"
            "un peligro que tu mente todavía no procesa. *No debí hablarle. No"
            "debí hablarle.*  Papu se acerca corriendo, sus zapatos resbalando"
            "en el suelo húmedo: — *mano mano mano, no le hables a la clienta"
            "VIP, lptm. ella paga triple pero se enoja fácil. sisis. no la"
            "provoques.*"
        ),
        on_enter={"lore": 6, "corrupcion": 4, "voluntad": 3},
        set_flags=["hablo_con_dama"],
        character_dialogue={
            "aris": "mi sueño tiene textura. los otros son humo, yo soy arcilla. eso es malo",
            "law": "dijo que soy ARCILLA y que puede hacer cosas conmigo bro NO",
            "haru": "dice que soy arcilla y los demás humo, Papu corrió a callarme xd",
            "elyko": "sustancia = textura onírica sólida. ella quiere materia prima. no bueno.",
            "xoft": "dice que soy ARCILLA y puede hacer cosas conmigo. Papu se cagó.",
            "xokram": "Paga triple pero se enoja fácil. Papu le tiene miedo a ella",
            "daraziel": "La voz viene de todas partes. No es una persona. Es algo más.",
        },
        paths=[
            P("Decirle que no estás en venta", "act2_isla_desafiar_dama", style="danger", effects={"voluntad": 8, "corrupcion": 6}),
            P("Callarte y dejar que Papu maneje", "act2_isla_esperar_apertura", style="secondary", effects={"lucidez": 2, "favor": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_estudio_papu",
        act=A, zone="Isla de Papu — Estudio Privado",
        tone="discovery",
        text=(
            "El estudio es sorprendentemente acogedor — un contraste obsceno"
            "con todo lo de abajo. Sillón gastado de cuero marrón, una taza de"
            "café tibio que todavía humea (el olor es real, terrestre, casi"
            "reconfortante), un monitor con una partida congelada de un MOBA."
            "La luz aquí es cálida — una lámpara normal, amarilla, sin aceite"
            "verde. Junto al teclado, carpetas clasificadas por cliente,"
            "apiladas con un orden que no esperabas de Papu.  En el"
            "escritorio: una libreta de contabilidad con números en tinta"
            "roja, un contrato firmado con tinta roja dirigido a «Nyarlathotep"
            "Mensajero» — el papel vibra cuando lo tocas, un zumbido bajo que"
            "sientes en las yemas de los dedos —, y una ventana que da a la"
            "terraza donde está el Shantak. Puedes oír a la bestia respirar"
            "desde aquí: un resoplido húmedo, rítmico, animal.  Piensas: Papu"
            "vive aquí. Juega videojuegos. Toma café. Y abajo vende personas."
            "La normalidad de este cuarto es lo más perturbador que has visto"
            "en toda la noche."
        ),
        on_enter={"lore": 6, "lucidez": -2},
        set_flags=["vio_estudio_papu"],
        character_dialogue={
            "aris": "estudio con MOBA congelado. carpetas de clientes. contrato con nyarlathotep",
            "law": "tiene un MOBA CONGELADO en el monitor bro y un contrato con NYARLATHOTEP",
            "haru": "tiene un moba congelado y un contrato con nyarlathotep, peak cultista gamer",
            "elyko": "moba congelado. carpetas. contrato con nyarlathotep. ventana → shantak.",
            "xoft": "MOBA congelado. contrato con Nyarlathotep. este tipo es un gamer cultista.",
            "xokram": "Carpetas de clientes, contrato con Nyarlathotep. y un moba congelado xd",
            "daraziel": "Estudio acogedor. MOBA congelado. Contrato con Nyarlathotep. Ventana al Shantak.",
        },
        paths=[
            P("Tomar el contrato (evidencia)", "act2_isla_tomar_contrato", style="info", effects={"lore": 5, "corrupcion": 3}, give_item="contrato_papu_nyar"),
            P("Ir a la ventana (Shantak)", "act2_isla_ventana_mar", style="success", effects={"voluntad": 3}),
            P("Revisar las carpetas de clientes", "act2_isla_carpetas", style="warning", effects={"lore": 8, "lucidez": -4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_ventana_mar",
        act=A, zone="Isla de Papu — Terraza del Shantak",
        tone="awe",
        text=(
            "La terraza da al mar negro. El viento golpea — frío, salado, con"
            "un filo que corta. Amarrado a un pilar de piedra erosionada, un"
            "Shantak — bestia alada con cabeza de caballo y ojos demasiado"
            "humanos que te siguen cuando te mueves. Huele a animal y a algo"
            "más antiguo. En el anca tiene el sello de Papu — un símbolo que"
            "brilla tenue.  Es el transporte personal del cultista. Diez"
            "minutos a Sarkomand. Las cadenas que lo atan tintinean con el"
            "viento. Pero si lo montas, Papu lo sabe. Y la Dama también."
        ),
        on_enter={"lucidez": 4, "voluntad": 3},
        set_flags=["vio_shantak_papu"],
        character_dialogue={
            "aris": "shantak amarrado. diez minutos a sarkomand. pero papu y la dama lo sabrán",
            "law": "un SHANTAK bro diez minutos a Sarkomand pero Papu y la Dama lo sabrán",
            "haru": "shantak amarrado, 10 min a sarkomand, pero lo van a saber",
            "elyko": "shantak. 10 min a sarkomand. riesgo: papu y dama lo saben.",
            "xoft": "Shantak. 10 minutos. pero Papu y la Dama lo sabrán. me da igual. MONTO.",
            "xokram": "Shantak, 10 min. Papu y la Dama lo saben. pero ya qué",
            "daraziel": "Shantak amarrado. Diez minutos. El sello de Papu en el anca. Lo sabrán.",
        },
        paths=[
            P("Montar el Shantak y huir", "act2_isla_montar_shantak", style="success", effects={"voluntad": 5, "corrupcion": 2}),
            P("Soltar al Shantak sin montarlo", "act2_isla_soltar_shantak", style="info", effects={"favor": 6, "voluntad": 3}),
            P("Volver abajo (otra ruta)", "act2_isla_pasillo_caos", style="secondary", effects={"lucidez": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_espiar_subasta",
        act=A, zone="Isla de Papu — Espiando la Subasta",
        tone="horror",
        text=(
            "Te cuelas por la puerta trasera del salón. El aire aquí es más"
            "frío — huele a piedra húmeda y a incienso viejo. Desde aquí ves"
            "el escenario sin que te vean, oculto entre las sombras del marco"
            "de la puerta. La luz verde de las antorchas no llega hasta este"
            "rincón.  Hay otro lote ahí — una sombra pequeña, temblando bajo"
            "la luz enferma. Casi transparente. La puja va rápido — números"
            "que se lanzan como cuchillos, voces inhumanas que compiten sin"
            "emoción.  El Hombre de Leng la compra por seis monedas. La sombra"
            "no grita — ya no puede. Ya no tiene con qué. La llevan a la sala"
            "de preparación — dos guardias la cargan como quien carga un saco"
            "vacío. La misma sala donde estuviste tú. El mismo olor a blanco."
            "La misma mesa.  Sientes la bilis subir. Piensas: eso era yo. Eso"
            "iba a ser yo."
        ),
        on_enter={"lore": 6, "lucidez": -5, "corrupcion": 4},
        set_flags=["vio_subasta_papu"],
        character_dialogue={
            "aris": "otro lote. sombra pequeña. seis monedas. la llevan a preparación",
            "law": "hay OTRA sombra en el escenario temblando y la COMPRARON por seis bro",
            "haru": "otra sombra temblando, la compraron por 6, la llevan a preparación",
            "elyko": "otro lote. sombra pequeña. 6 monedas. misma sala de preparación.",
            "xoft": "otra sombra temblando. la compraron. la llevan a la misma sala. mano.",
            "xokram": "Otro lote vendido por 6. la llevan a preparación. esto sigue sin mí",
            "daraziel": "Otro lote. Sombra pequeña. Seis monedas. Misma sala. El ciclo continúa.",
        },
        paths=[
            P("Volver al pasillo y escapar", "act2_isla_pasillo_caos", style="primary", effects={"voluntad": 2}),
            P("Intentar salvar a esa sombra", "act2_isla_salvar_sombra", style="warning", effects={"favor": 8, "voluntad": 5, "lucidez": -4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_liberar_jaulas",
        act=A, zone="Isla de Papu — Liberando Jaulas",
        tone="awe",
        text=(
            "Vuelves al salón en el caos. Las lámparas de aceite verde"
            "oscilan, proyectando sombras que se mueven solas. Usas las llaves"
            "— una jaula, dos, cinco, diez. El metal frío de cada cerradura"
            "cede con un chasquido satisfactorio. Las sombras salen corriendo,"
            "volando, arrastrándose. Algunas te miran con gratitud — ojos que"
            "brillan un instante antes de desvanecerse. Otras ni siquiera"
            "saben qué eres.  El aire se llena de un olor a ozono y sal. El"
            "sonido de cadenas cayendo al suelo es casi musical. Los guardias"
            "intentan detenerte pero son pocos contra el torrente de sombras"
            "liberadas. El salón se vacía. Los clientes huyen — hasta el"
            "Sacerdote Sin Rostro se aleja flotando, su zumbido perdiéndose en"
            "la distancia como una nota grave que se apaga.  *Esto es lo"
            "correcto. Esto es lo único correcto que ha pasado aquí.*"
        ),
        on_enter={"favor": 15, "voluntad": 8, "lucidez": -5},
        set_flags=["libero_sombras_isla", "rebelion_isla_papu"],
        character_dialogue={
            "aris": "abrí diez jaulas. las sombras salen. los guardias no pueden. el salón se vacía",
            "law": "ABRÍ TODAS LAS JAULAS y las sombras SALEN y los guardias no pueden VAMOS",
            "haru": "abrí todas las jaulas, las sombras salen corriendo, los guardias no dan abasto",
            "elyko": "10+ jaulas abiertas. torrente de sombras. guardias superados. salón vacío.",
            "xoft": "abrí TODAS las jaulas. las sombras salen. los guardias no pueden. BIEN.",
            "xokram": "Abrí todo. las sombras salen. los clientes huyen. el negocio se acabó",
            "daraziel": "Diez jaulas abiertas. Torrente de sombras. El salón se vacía. Los clientes huyen.",
        },
        paths=[
            P("Escapar en el caos al pasillo", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}, conditions={"lacks_flag": "en_pasillo_papu"}),
            P("Ir al muelle con las sombras", "act2_isla_muelle", style="primary", effects={"favor": 5}),
            P("Subir al Shantak", "act2_isla_ventana_mar", style="info", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_resistir_escenario",
        act=A, zone="Isla de Papu — Resistencia",
        tone="horror",
        text=(
            "Te plantas. Los pies descalzos contra la piedra fría — te aferras"
            "a esa textura. Los guardias tiran de ti, sus manos de piel mal"
            "cosida ásperas contra tus brazos. Tú no te mueves. El público"
            "murmura — algunos con interés, otros con impaciencia. El sonido"
            "es un oleaje bajo, inhumano.  Papu se acerca. Huele a sudor"
            "dulce:  — *mano, sisis, no hagas esto. te van a comprar igual. si"
            "te resistes sólo sube el precio. los clientes pagan más por los"
            "que pelean. es como... oferta y demanda, xd.*  Tiene razón. Lo"
            "sabes. Los murmullos se vuelven más intensos. La Dama de"
            "Porcelana se inclina hacia adelante con un clic suave de"
            "porcelana. Piensas: estoy alimentando exactamente lo que quiero"
            "destruir."
        ),
        on_enter={"voluntad": 4, "lucidez": -3, "corrupcion": 2},
        set_flags=["resistio_escenario"],
        character_dialogue={
            "aris": "me resistí y subió mi precio. oferta y demanda. tiene razón",
            "law": "me resistí y Papu dice que SUBE MI PRECIO por eso NO PUEDE SER",
            "haru": "me resistí y dice que sube el precio, oferta y demanda dice, nmms",
            "elyko": "resistencia = precio sube. la dama se inclinó. contraproducente.",
            "xoft": "me resistí y subió mi precio. la Dama se inclinó. mano.",
            "xokram": "Resistirme subió mi precio. la Dama se interesó más. mal negocio",
            "daraziel": "La resistencia es parte del espectáculo. La Dama se inclinó.",
        },
        paths=[
            P("Ir al escenario (inevitable)", "act2_isla_escenario", style="primary", effects={"voluntad": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_escenario",
        act=A, zone="Isla de Papu — El Escenario",
        tone="horror",
        text=(
            "Estás en el centro del anfiteatro. Luz de antorchas verdes desde"
            "arriba — una luz enferma que te hace parecer cadáver, que"
            "convierte tu piel en algo submarino. El calor de las llamas no"
            "llega hasta abajo; aquí sólo hay frío. Catorce figuras"
            "encapuchadas te rodean en semicírculo. Puedes ver sus manos —"
            "algunas no son manos. Garras. Tentáculos. Cosas con demasiados"
            "nudillos.  El olor es una mezcla de incienso, sal y algo"
            "dulce-podrido que te revuelve el estómago. El silencio de las"
            "figuras es peor que cualquier ruido — un silencio que te examina,"
            "que te pesa, que te pone precio.  Papu toma el micrófono de"
            "hueso. El sonido de sus dedos contra el material es un click seco"
            "que rebota en todo el anfiteatro:  — *sisis, mano, lote catorce."
            "soñador sólido. consciente. textura premium. reserva en ocho"
            "monedas oníricas. empezamos. ¿quién abre?*  Sientes las miradas."
            "Todas. Como agujas frías en la piel."
        ),
        on_enter={"voluntad": -5, "lucidez": -5, "corrupcion": 3},
        character_dialogue={
            "aris": "estoy en el escenario. catorce compradores. algunas manos no son manos",
            "law": "estoy en el CENTRO y hay 14 encapuchados mirándome bro AYUDA",
            "haru": "14 encapuchados mirándome, algunas manos no son manos, qué asco",
            "elyko": "escenario central. 14 compradores. manos no humanas. reserva 8.",
            "xoft": "14 encapuchados me miran. algunas manos no son manos. mano.",
            "xokram": "Reserva en 8. 14 compradores. estoy en exhibición",
            "daraziel": "Luz verde desde arriba. 14 figuras en semicírculo. Manos no humanas.",
        },
        paths=[
            P("Observar quién puja primero", "act2_isla_primera_puja", style="primary", effects={"lore": 3}),
            P("Intentar hablar al público", "act2_isla_hablar_publico", style="warning", effects={"voluntad": 5, "lucidez": -3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_pasillo_caos",
        act=A, zone="Isla de Papu — Pasillo en Caos",
        tone="tense",
        text=(
            "El pasillo lateral. Lámparas de aceite verde que chisporrotean y"
            "proyectan sombras largas en las paredes de piedra húmeda. El aire"
            "es denso, pegajoso, huele a sal y a humo. Gritos lejanos del"
            "salón — la subasta se interrumpió o tú ya no estás para verla. El"
            "eco de cadenas arrastrándose. Tu respiración demasiado fuerte en"
            "el silencio.  *Piensa. Rápido.* Tres direcciones:  Escalera"
            "arriba → estudio de Papu y ventana al mar. Recto → muelle"
            "trasero. Abajo → sótano y túnel. De abajo sube un zumbido grave"
            "que sientes en el estómago."
        ),
        on_enter={"voluntad": 3, "lucidez": 2},
        set_flags=["en_pasillo_papu"],
        character_dialogue={
            "aris": "pasillo. tres direcciones. arriba, recto, abajo. hay que elegir",
            "law": "PASILLO tres direcciones ARRIBA RECTO ABAJO cuál cuál cuál",
            "haru": "pasillo con tres rutas, gritos atrás, hay que elegir rápido",
            "elyko": "3 rutas: escalera (estudio+ventana), recto (muelle), abajo (túnel).",
            "xoft": "tres rutas. arriba, recto, abajo. gritos atrás. MUÉVETE.",
            "xokram": "Tres rutas. arriba rápido, recto medio, abajo peligroso. a elegir",
            "daraziel": "Pasillo con tres ejes. Lámparas verdes. Gritos lejanos. Elegir.",
        },
        paths=[
            P("Subir al estudio de Papu", "act2_isla_estudio_papu", style="info", effects={"lore": 3, "lucidez": -2}),
            P("Ir recto al muelle", "act2_isla_muelle", style="primary", effects={"voluntad": 2}),
            P("Bajar al sótano/túnel", "act2_isla_tunel_sotano", style="warning", effects={"lore": 3, "lucidez": -3}),
            P("Liberar jaulas antes de irte", "act2_isla_liberar_jaulas", style="danger", effects={"favor": 10, "lucidez": -4}, conditions={"has_item": "llaves_papu", "lacks_flag": "libero_todas_sombras"}),
        ],
    ))

    nodes.append(N(
        "act2_isla_enfrentar_guardias",
        act=A, zone="Isla de Papu — Contra los Guardias",
        tone="horror",
        text=(
            "Dos Hombres de Leng te bloquean el paso. Tienen bastones de hueso"
            "— amarillentos, con marcas de dientes en los extremos — y piel"
            "que se les despega del cuello en tiras húmedas. El olor es agrio,"
            "como cuero mojado pudriéndose al sol. No son rápidos — pero son"
            "duros. Sus ojos no parpadean. Nunca parpadean.  Las sombras"
            "liberadas pasan a tu lado como un río de humo frío, rozándote la"
            "piel con dedos que casi no existen. Los guardias tienen que"
            "elegir: tú o las sombras. Se miran entre ellos — un gesto lento,"
            "reptiliano — y eligen las sombras. Valen más en conjunto.  Te"
            "dejan pasar. Uno de ellos te roza el hombro al girarse y el"
            "contacto con su piel te deja un frío que tarda en irse. Piensas:"
            "no me vieron como amenaza. No sé si eso es bueno o humillante."
        ),
        on_enter={"voluntad": 6, "lucidez": -3},
        character_dialogue={
            "aris": "los guardias eligieron perseguir sombras. valgo menos que el grupo. me dejaron",
            "law": "los guardias eligieron las SOMBRAS porque valen más en grupo ME DEJARON PASAR",
            "haru": "los guardias eligieron las sombras, valgo menos que el grupo, me dejaron xd",
            "elyko": "guardias eligieron sombras. valor grupal > individual. me dejaron pasar.",
            "xoft": "los guardias eligieron las sombras. valgo menos que el grupo. me dejaron.",
            "xokram": "Eligieron las sombras, valen más en grupo. me dejaron pasar. bien",
            "daraziel": "Eligieron las sombras. Valor grupal mayor. Me dejaron pasar.",
        },
        paths=[
            P("Correr al pasillo", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_desafiar_dama",
        act=A, zone="Isla de Papu — Desafío",
        tone="horror",
        text=(
            "— *No estoy en venta.*  Tu propia voz te sorprende — más firme de"
            "lo que esperabas. El salón se queda en silencio. Un silencio"
            "pesado, húmedo, que huele a sal y a miedo ajeno. Todos los"
            "encapuchados te miran — o lo que sea que hacen con los agujeros"
            "que tienen donde deberían estar los ojos. La Dama no se mueve."
            "Las lámparas de aceite verde parpadean una vez, como si el aire"
            "se hubiera espesado.  Luego, muy despacio, se ríe. No es una risa"
            "humana — es el sonido de porcelana rompiéndose en cámara lenta."
            "Crack. Crack. Crack. Te recorre la columna como dedos fríos. El"
            "estómago se te contrae.  — *Todos están en venta. La pregunta es"
            "el precio.*  Se aleja. El click de sus pasos sobre el suelo de"
            "piedra es lo único que se oye. Papu te mira con los ojos muy"
            "abiertos, sudando: — *mano. mano. acabas de subir tu precio."
            "waos. eso no te conviene.*  Piensas: tiene razón. Pero al menos"
            "todavía puedo decir que no. Todavía."
        ),
        on_enter={"voluntad": 6, "corrupcion": 4, "lucidez": -4},
        set_flags=["desafio_dama"],
        character_dialogue={
            "aris": "le dije que no estoy en venta. se rió. dijo que todos lo están",
            "law": "le dije NO ESTOY EN VENTA y se RIÓ como porcelana rompiéndose MANO",
            "haru": "le dije que no y se rió como platos cayéndose, Papu dice que subí mi precio",
            "elyko": "la desafié. se rió. dijo que todos están en venta. subí mi precio.",
            "xoft": "le dije que NO y se rió como porcelana rota. subí mi precio. GG.",
            "xokram": "Subí mi propio precio desafiándola. pésimo movimiento comercial",
            "daraziel": "La risa suena a porcelana rompiéndose. No es humana. Subí mi precio.",
        },
        paths=[
            P("Esperar la subasta con dignidad", "act2_isla_esperar_apertura", style="primary", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_tomar_contrato",
        act=A, zone="Isla de Papu — Contrato",
        tone="discovery",
        text=(
            "El contrato dice: «Yo, Papu, cedo el 70% de mis ganancias al"
            "Mensajero a cambio de protección, clientela, y no disolución."
            "Firmado en tinta de sombra procesada.»  El papel es frío al tacto"
            "— un frío que sube por los dedos. La tinta roja huele a sangre"
            "dulce. Debajo, una firma que no es una firma — es un símbolo que"
            "se mueve cuando lo miras. Se retuerce. Cambia. Nunca es el mismo"
            "dos veces. Nyarlathotep.  La Dama trabaja para él. Papu trabaja"
            "para ella. La cadena llega hasta arriba. Piensas: todo esto es"
            "una franquicia. Un negocio. Y el dueño es algo que no debería"
            "tener nombre."
        ),
        on_enter={"lore": 8, "corrupcion": 4, "lucidez": -3},
        set_flags=["sabe_cadena_mando"],
        character_dialogue={
            "aris": "papu cede 70% a nyarlathotep. la dama trabaja para él. cadena completa",
            "law": "Papu le da el 70% a NYARLATHOTEP y la Dama trabaja para él TODO CONECTA",
            "haru": "papu da 70% a nyarlathotep, la dama es su empleada, cadena alimenticia",
            "elyko": "70% a nyarlathotep. dama = intermediaria. papu = operador. cadena clara.",
            "xoft": "70% a Nyarlathotep. la Dama trabaja para él. Papu es el eslabón bajo.",
            "xokram": "70% a Nyarlathotep. la Dama es intermediaria. Papu es el operador",
            "daraziel": "Cadena: Nyarlathotep → Dama → Papu → producto. Estructura piramidal.",
        },
        paths=[
            P("Ir a la ventana (Shantak)", "act2_isla_ventana_mar", style="success", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_carpetas",
        act=A, zone="Isla de Papu — Carpetas de Clientes",
        tone="horror",
        text=(
            "Las carpetas tienen nombres. No nombres humanos — títulos: «El"
            "Que Disuelve», «La Sin Rostro del Templo», «La Dama de"
            "Porcelana», «El Coleccionista de Celephaïs», «Los Siete"
            "Hambrientos». El papel es grueso, amarillento, y huele a incienso"
            "y a tinta vieja. Cada carpeta está atada con un cordel negro que"
            "se siente aceitoso al tacto.  Cada carpeta tiene un historial de"
            "compras. Números, fechas lunares, descripciones de lotes. La Dama"
            "ha comprado cuarenta y tres lotes en los últimos dos años."
            "Ninguno fue devuelto. Ninguno fue visto de nuevo. Cuarenta y"
            "tres. El número se te queda pegado en la cabeza como un zumbido."
            "En los márgenes de su carpeta, Papu ha escrito notas con letra"
            "temblorosa: «no preguntar», «paga siempre de más», «no mirarla a"
            "los ojos (¿tiene ojos?)». La última nota dice simplemente:"
            "«mano... xd»."
        ),
        on_enter={"lore": 10, "lucidez": -5, "corrupcion": 4, "memoria": -3},
        set_flags=["leyo_carpetas"],
        give_item="lista_clientes_papu",
        character_dialogue={
            "aris": "43 lotes comprados por la dama. ninguno devuelto. ninguno visto de nuevo",
            "law": "la Dama compró CUARENTA Y TRES y NINGUNO fue visto de nuevo bro",
            "haru": "la dama compró 43 y ninguno volvió. ninguno. eso es mucho mano",
            "elyko": "dama: 43 compras, 0 devoluciones, 0 avistamientos. tasa de retorno: 0%.",
            "xoft": "43 compras. NINGUNO vuelve. ninguno. la Dama los desaparece a todos.",
            "xokram": "43 compras, 0 devoluciones. la Dama es el cliente más peligroso",
            "daraziel": "43 lotes. Ninguno devuelto. Ninguno visto. La Dama es un agujero negro.",
        },
        paths=[
            P("Ir a la ventana (Shantak)", "act2_isla_ventana_mar", style="success", effects={"voluntad": 3}),
            P("Tomar la carpeta de la Dama", "act2_isla_ventana_mar", style="info", effects={"lore": 4, "corrupcion": 2}, give_item="carpeta_dama"),
        ],
    ))

    nodes.append(N(
        "act2_isla_montar_shantak",
        act=A, zone="Isla de Papu — Montando el Shantak",
        tone="awe",
        text=(
            "Desatas al Shantak. La cuerda está húmeda de salitre y se deshace"
            "entre tus dedos. Te mira con esos ojos demasiado humanos — hay"
            "algo detrás, algo que entiende — y te deja subir. Su piel es"
            "áspera, caliente, huele a animal y a tormenta. Abre las alas. El"
            "viento del mar negro te golpea la cara como una bofetada salada."
            "*Vuela. Vuela. No mires abajo.* Pero miras.  Abajo, en la"
            "terraza, ves una figura blanca — la Dama de Porcelana, mirando"
            "hacia arriba. Inmóvil como una estatua. No corre. No grita. Sólo"
            "mira. Y sabes — con la certeza fría de quien sueña — que te va a"
            "recordar. Que la distancia no significa nada para ella."
        ),
        on_enter={"voluntad": 8, "lucidez": 4},
        set_flags=["escapo_en_shantak"],
        character_dialogue={
            "aris": "monté el shantak. la dama me mira desde abajo. me va a recordar",
            "law": "MONTÉ EL SHANTAK y la Dama me mira desde abajo bro me va a recordar",
            "haru": "monté el shantak, la dama me mira desde abajo, me va a recordar",
            "elyko": "shantak montado. la dama mira desde abajo. me recordará. no importa.",
            "xoft": "monté el Shantak. la Dama me mira. me va a recordar. que me recuerde.",
            "xokram": "Monté el shantak. la Dama me mira. me va a recordar. ya qué",
            "daraziel": "Shantak montado. La Dama mira desde abajo. Me recordará. No importa.",
        },
        paths=[
            P("Volar a Sarkomand", "act2_isla_escape", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_soltar_shantak",
        act=A, zone="Isla de Papu — Soltando al Shantak",
        tone="calm",
        text=(
            "Desatas al Shantak pero no te subes. El viento del mar negro te"
            "golpea — sal, frío, distancia infinita. Le quitas el sello de"
            "Papu del anca — se despega como una costra vieja, con un sonido"
            "húmedo. La bestia te mira con esos ojos demasiado humanos — hay"
            "algo ahí, algo que reconoce lo que haces. Abre las alas — el"
            "sonido es enorme, como una vela desplegándose — y se va sola"
            "hacia el mar.  Libre. Como las sombras. Como tú quieres ser."
            "Ahora tienes que bajar al muelle y nadar. O encontrar otra forma."
            "El viento te enfría el sudor en la espalda."
        ),
        on_enter={"favor": 8, "voluntad": 4, "lucidez": 2},
        set_flags=["libero_shantak"],
        character_dialogue={
            "aris": "lo solté. se fue libre. ahora tengo que nadar o buscar otra ruta",
            "law": "lo solté y se fue LIBRE bro ahora tengo que nadar o buscar otra forma",
            "haru": "lo solté, se fue libre, ahora me toca nadar o buscar otra ruta",
            "elyko": "shantak liberado. ahora: muelle o túnel. sin transporte aéreo.",
            "xoft": "lo solté. se fue libre. ahora me toca a mí. muelle o túnel.",
            "xokram": "Lo solté. se fue. ahora tengo que buscar otra salida",
            "daraziel": "Lo solté. Se fue al mar. Libre. Ahora me toca encontrar mi ruta.",
        },
        paths=[
            P("Bajar al muelle", "act2_isla_muelle", style="primary", effects={"voluntad": 2}),
            P("Bajar al túnel del sótano", "act2_isla_tunel_sotano", style="warning", effects={"lore": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_salvar_sombra",
        act=A, zone="Isla de Papu — Salvando una Sombra",
        tone="tense",
        text=(
            "Interceptas al guardia que lleva a la sombra. El Hombre de Leng"
            "te mira — ojos sin párpados, piel despegándose del cuello. Le"
            "quitas la sombra de las manos — es liviana, casi no pesa. Como"
            "sostener humo tibio con forma de niño. El guardia te mira,"
            "confundido. No esperaba resistencia de un producto ya vendido."
            "La sombra se agarra a ti como un niño asustado. Sus dedos se"
            "hunden apenas en tu ropa, fríos, casi imperceptibles. No habla."
            "Pero tiembla menos. Huele a nada — a ausencia donde debería haber"
            "algo."
        ),
        on_enter={"favor": 10, "voluntad": 5, "lucidez": -3},
        set_flags=["salvo_sombra_individual"],
        character_dialogue={
            "aris": "la tomé. es liviana. se agarra a mí. el guardia no esperaba esto",
            "law": "la TOMÉ y se agarra a mí como un niño asustado bro la salvo",
            "haru": "la agarré, es liviana, se agarra a mí temblando, el guardia no sabe qué hacer",
            "elyko": "sombra rescatada. liviana. se agarra. guardia confundido. no esperaba esto.",
            "xoft": "la tomé. se agarra a mí. tiembla menos. el guardia no sabe qué hacer.",
            "xokram": "La tomé. es liviana. el guardia no esperaba que un producto se rebele",
            "daraziel": "La tomé. Casi no pesa. Se agarra. El guardia no esperaba resistencia.",
        },
        paths=[
            P("Correr con ella al pasillo", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 3, "favor": 5}),
        ],
    ))

    nodes.append(N(
        "act2_isla_muelle",
        act=A, zone="Isla de Papu — Muelle Trasero",
        tone="tense",
        text=(
            "El muelle es de madera podrida — cruje bajo cada paso, húmeda y"
            "blanda como carne vieja. El olor a sal y a algas en"
            "descomposición te llena los pulmones. Hay un bote pequeño"
            "amarrado con una soga que se deshace — sin remos, sin vela. El"
            "mar negro se extiende hasta donde no alcanza la vista, liso como"
            "aceite.  Sarkomand está en algún lugar al norte. Sin remos, el"
            "bote iría a la deriva. Pero hay corriente — la sientes en cómo el"
            "agua tira de los pilares del muelle — y la corriente va hacia el"
            "norte. *Es un plan terrible. Pero es un plan.*"
        ),
        on_enter={"lucidez": 3, "voluntad": 2},
        character_dialogue={
            "aris": "bote sin remos. corriente al norte. sarkomand al norte. funciona",
            "law": "hay un bote SIN REMOS pero la corriente va al norte VAMOS",
            "haru": "bote sin remos pero la corriente va al norte, funciona",
            "elyko": "bote sin remos. corriente norte. sarkomand norte. viable.",
            "xoft": "bote sin remos. corriente al norte. me subo. mano.",
            "xokram": "Bote sin remos pero corriente al norte. es la salida",
            "daraziel": "Bote sin remos. Corriente norte. Sarkomand norte. La física ayuda.",
        },
        paths=[
            P("Subirse al bote y dejarse llevar", "act2_isla_bote_mar", style="success", effects={"voluntad": 3, "lucidez": 2}),
            P("Nadar directamente (más rápido)", "act2_isla_nadar", style="warning", effects={"voluntad": 5, "lucidez": -4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_primera_puja",
        act=A, zone="Isla de Papu — Primera Puja",
        tone="horror",
        text=(
            "Un Hombre de Leng levanta tres dedos verdes — la piel se le"
            "despega entre los nudillos: — *Nueve.*  El Sacerdote Sin Rostro"
            "inclina lo que debería ser su cabeza. El zumbido que emite cambia"
            "de tono: — *Diez.*  El número flota en el aire como algo sólido."
            "Puedes oler la tensión — incienso, sudor ácido, algo metálico."
            "Papu sonríe, el micrófono de hueso amplificando su voz con un eco"
            "húmedo: — *sisis, diez, tengo diez. ¿once? mano, ¿once alguien?*"
            "La Dama de Porcelana no se mueve. Espera. Inmóvil como una"
            "estatua en su asiento blanco. Los otros dos se miran entre sí — o"
            "lo que sea que hacen cuando no tienen ojos. *Me están comprando."
            "Como un mueble. Como carne.* El pecho te aprieta."
        ),
        on_enter={"lucidez": -3, "corrupcion": 2},
        character_dialogue={
            "aris": "nueve, diez. están pujando por mí. la dama espera",
            "law": "están PUJANDO POR MÍ bro nueve diez la Dama no se mueve",
            "haru": "están pujando por mí como si fuera un item raro, la dama espera",
            "elyko": "9, 10. dos pujadores activos. la dama espera. estrategia de cierre.",
            "xoft": "están pujando por mí. nueve. diez. la Dama espera su momento.",
            "xokram": "9, 10. la Dama espera a que suban para cerrar. clásico",
            "daraziel": "Nueve. Diez. La Dama no se mueve. Espera el momento exacto.",
        },
        paths=[
            P("Quedarte quieto y escuchar", "act2_isla_puja_sube", style="secondary", effects={"lucidez": -2}),
            P("Gritar que no vales nada (sabotear)", "act2_isla_sabotear_puja", style="info", effects={"voluntad": 4, "favor": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_hablar_publico",
        act=A, zone="Isla de Papu — Dirigiéndote al Público",
        tone="horror",
        text=(
            "— *¿Quiénes son ustedes?* — preguntas al semicírculo. Tu voz se"
            "pierde en el espacio del anfiteatro como una piedra cayendo en un"
            "pozo.  Nadie responde. El silencio tiene peso — huele a incienso"
            "rancio y a algo metálico, como sangre vieja. La Dama de Porcelana"
            "ladea la cabeza con ese clic de bisagra rota. El Hombre de Leng"
            "se rasca la piel del cuello (se le despega un poco — debajo hay"
            "algo gris y húmedo). El Sacerdote Sin Rostro emite un zumbido"
            "bajo que sientes en los huesos del pecho.  *No son personas."
            "Ninguno es una persona.* El pensamiento te llega con claridad"
            "helada.  Papu te agarra del hombro — su mano está tibia y"
            "pegajosa: — *mano, sisis, no les hables. no les gusta. la última"
            "vez que un lote les habló... bueno. ya no hay lote.*"
        ),
        on_enter={"voluntad": 4, "lore": 5, "lucidez": -4},
        character_dialogue={
            "aris": "les pregunté quiénes son. no respondieron. papu dice que el último que habló desapareció",
            "law": "les hablé y NADIE respondió y Papu dice que el último que habló DESAPARECIÓ",
            "haru": "les hablé y nadie respondió, el último que habló ya no existe dice Papu",
            "elyko": "pregunté. sin respuesta. el último que habló desapareció. noted.",
            "xoft": "les hablé. nadie respondió. el último que habló desapareció. mano.",
            "xokram": "Les hablé y nada. el último que habló desapareció. mejor callarme",
            "daraziel": "Nadie respondió. El Leng se rascó y se le despegó piel. No son humanos.",
        },
        paths=[
            P("Callarte y dejar que siga la puja", "act2_isla_primera_puja", style="secondary", effects={"lucidez": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_tunel_sotano",
        act=A, zone="Isla de Papu — Túnel del Sótano",
        tone="horror",
        text=(
            "El sótano huele a humedad antigua — siglos de agua filtrándose"
            "por piedra. El aire es frío y pegajoso contra la piel. No hay luz"
            "— avanzas a tientas, las manos contra paredes mojadas que se"
            "sienten orgánicas.  El túnel es estrecho — tienes que agacharte."
            "Las paredes tienen marcas de uñas. Muchas marcas. De muchas"
            "manos. Algunas profundas, desesperadas. Otras superficiales, como"
            "si quien las hizo ya no tuviera fuerza.  El túnel baja, gira, y"
            "se bifurca: un camino sube hacia lo que huele a aire libre, a"
            "sal. El otro baja más, hacia un zumbido grave que vibra en los"
            "huesos — el templo del Sacerdote Sin Rostro."
        ),
        on_enter={"lore": 4, "lucidez": -4},
        character_dialogue={
            "aris": "marcas de uñas en las paredes. muchas. bifurcación: arriba o abajo",
            "law": "hay MARCAS DE UÑAS en las paredes bro MUCHAS y el túnel se bifurca",
            "haru": "marcas de uñas en las paredes, muchas manos, el túnel se bifurca",
            "elyko": "marcas de uñas. múltiples. bifurcación: arriba (aire) o abajo (templo).",
            "xoft": "marcas de uñas. muchas. muchas manos. el túnel se bifurca. mano.",
            "xokram": "Marcas de uñas en las paredes. bifurcación: arriba seguro, abajo peligroso",
            "daraziel": "Marcas de uñas. Muchas manos. Bifurcación. Arriba = aire. Abajo = templo.",
        },
        paths=[
            P("Subir hacia el aire libre", "act2_isla_tunel_salida", style="success", effects={"voluntad": 3, "lucidez": 2}),
            P("Bajar al templo del Sacerdote", "act2_isla_templo_sacerdote", style="danger", effects={"lore": 8, "lucidez": -6, "corrupcion": 5}),
        ],
    ))

    nodes.append(N(
        "act2_isla_escape",
        act=A, zone="Regreso a Sarkomand",
        tone="calm",
        text=(
            "El mar negro te deja en la orilla de Sarkomand. La arena es gris,"
            "fría, y cruje bajo tus pies como huesos molidos. Las ruinas están"
            "como las dejaste — piedra antigua, silencio pesado, el olor a"
            "polvo y a tiempo muerto. La losa donde dormía Papu está vacía. Su"
            "manojo de llaves sigue en el suelo, oxidándose, las doce llaves"
            "pequeñas abriéndose como una flor de metal muerto.  El aire aquí"
            "es distinto. Más limpio. Más frío. Respiras hondo y te duele —"
            "los pulmones se acostumbraron al aire espeso de la isla.  Tienes"
            "lo que viste. Tienes lo que pagaste por verlo. Y en algún lugar,"
            "lejos — más allá del mar negro, más allá de las lámparas de"
            "aceite verde —, la Dama de Porcelana sabe tu nombre. Lo sientes"
            "como un anzuelo diminuto en el centro del pecho. Frío. Quieto."
            "Esperando."
        ),
        on_enter={"lucidez": 5, "voluntad": 4, "memoria": 3},
        set_flags=["escapo_isla_papu"],
        character_dialogue={
            "aris": "llegué a sarkomand. la dama sabe mi nombre. pero estoy fuera",
            "law": "llegué a Sarkomand bro estoy FUERA pero la Dama sabe mi nombre",
            "haru": "llegué a sarkomand, estoy fuera, pero la dama sabe mi nombre",
            "elyko": "sarkomand. fuera. la dama sabe mi nombre. pero estoy libre.",
            "xoft": "llegué. estoy fuera. la Dama sabe mi nombre. pero estoy libre.",
            "xokram": "Llegué a Sarkomand. estoy fuera. la Dama sabe mi nombre. ya qué",
            "daraziel": "Sarkomand. Fuera. La Dama sabe mi nombre. Las ruinas están igual.",
        },
        paths=[
            P("Volver a las ruinas", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_bote_mar",
        act=A, zone="Mar Negro — En el Bote",
        tone="calm",
        text=(
            "El bote se aleja de la isla. La madera cruje bajo tu peso —"
            "podrida, blanda, con olor a sal vieja y algas muertas. La"
            "corriente te lleva sin que hagas nada, como si el mar te quisiera"
            "lejos de aquí tanto como tú.  Detrás, la mansión de Papu se hace"
            "pequeña — una mancha de luz verde en la oscuridad, las lámparas"
            "de aceite brillando como ojos enfermos. El aire huele a sal y a"
            "algo metálico que no puedes identificar. No hay viento. No hay"
            "olas. El agua se mueve desde abajo, empujándote.  El mar está"
            "quieto. Demasiado quieto. El silencio es tan denso que escuchas"
            "tu propia sangre en los oídos, el latido húmedo de tu corazón."
            "Pero te aleja. Cada segundo te aleja más. Te aferras al borde del"
            "bote — la madera está fría y resbaladiza bajo tus dedos — y no"
            "miras atrás otra vez."
        ),
        on_enter={"lucidez": 4, "voluntad": 3, "memoria": 2},
        set_flags=["escape_en_bote"],
        character_dialogue={
            "aris": "el bote se aleja. la isla se hace pequeña. el mar está quieto",
            "law": "me alejo de la isla bro el mar está quieto y me alejo cada segundo",
            "haru": "el bote se aleja, la isla se hace chiquita, el mar está quieto",
            "elyko": "alejándose. isla = mancha verde. mar quieto. corriente funciona.",
            "xoft": "me alejo. la isla se hace pequeña. cada segundo más lejos. bien.",
            "xokram": "Me alejo. la isla se hace chiquita. la corriente funciona",
            "daraziel": "La isla se reduce. Mancha verde en la oscuridad. El mar está quieto.",
        },
        paths=[
            P("Llegar a Sarkomand", "act2_isla_escape", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_nadar",
        act=A, zone="Mar Negro — Nadando",
        tone="tense",
        text=(
            "Nadas. El agua es espesa — más que agua normal. Como nadar en"
            "miel negra. Fría. Te entumece los brazos en minutos. Pero"
            "avanzas. La isla se aleja, su luz verde haciéndose más pequeña"
            "con cada brazada.  Algo te roza la pierna bajo el agua. Algo liso"
            "y frío, como piel de anguila pero del tamaño de un brazo. No"
            "miras. Sigues nadando. El corazón te martillea en los oídos. Te"
            "roza otra vez — más arriba, en el muslo. Sigues. No miras. *Si"
            "miras es real. Si no miras no es real.* Sigues nadando."
        ),
        on_enter={"voluntad": 5, "lucidez": -5, "memoria": -3},
        set_flags=["escape_nadando"],
        character_dialogue={
            "aris": "el agua es espesa. algo me roza la pierna. no miro. sigo nadando",
            "law": "algo me ROZÓ LA PIERNA bajo el agua NO MIRO SIGO NADANDO",
            "haru": "algo me rozó la pierna, no miro, sigo nadando, el agua es espesa",
            "elyko": "agua espesa. contacto bajo el agua. no mirar. seguir. avanzar.",
            "xoft": "algo me rozó la pierna. NO MIRO. sigo nadando. mano.",
            "xokram": "Algo me rozó. no miro. sigo. el agua es espesa pero avanzo",
            "daraziel": "Agua espesa como miel. Algo roza. No miro. Sigo. La isla se aleja.",
        },
        paths=[
            P("Seguir hasta llegar", "act2_isla_escape", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_puja_sube",
        act=A, zone="Isla de Papu — La Puja Sube",
        tone="horror",
        text=(
            "— *Once* — dice el Hombre de Leng. Su voz suena a cuero húmedo. —"
            "*Trece* — el Sacerdote salta dos. El zumbido que emite vibra en"
            "los dientes. — *Quince* — el Leng aprieta los dientes verdes. Se"
            "oye el chirrido, como porcelana contra porcelana. — *Dieciocho* —"
            "el Sacerdote. Final.  Papu está sudando — un sudor espeso que"
            "huele dulce: — *waos mano, dieciocho, tengo dieciocho."
            "¿diecinueve? ¿alguien?*  El Hombre de Leng se sienta. Se rindió."
            "El Sacerdote espera. El silencio pesa en el pecho. Y entonces la"
            "Dama de Porcelana levanta un solo dedo enguantado."
        ),
        on_enter={"lucidez": -4, "corrupcion": 3, "memoria": -2},
        character_dialogue={
            "aris": "once, trece, quince, dieciocho. la dama levantó un dedo",
            "law": "DIECIOCHO MONEDAS POR MÍ y la Dama levantó UN DEDO bro",
            "haru": "subió a 18 y la dama levantó un solo dedo, eso es mucho más",
            "elyko": "escalada: 11, 13, 15, 18. leng se rindió. la dama entra.",
            "xoft": "18 monedas y la Dama levantó UN dedo. eso es más. mucho más.",
            "xokram": "18 y la Dama entra con un dedo. eso es oferta de cierre",
            "daraziel": "Escalada hasta 18. El Leng se rindió. La Dama levantó un dedo.",
        },
        paths=[
            P("Ver qué significa ese dedo", "act2_isla_dama_cierra", style="primary", effects={"lore": 4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_sabotear_puja",
        act=A, zone="Isla de Papu — Sabotaje",
        tone="tense",
        text=(
            "— *¡NO VALGO NADA!* — gritas. Tu voz rebota en las paredes del"
            "anfiteatro. — *¡SOY HUMO! ¡ME VOY A DISOLVER EN DOS LUNAS! ¡NO"
            "COMPREN!*  Silencio. Las antorchas verdes crepitan. Puedes oír tu"
            "propia respiración. Luego risas — risas que no suenan humanas. El"
            "Hombre de Leng se ríe con un sonido húmedo, como carne"
            "despegándose de hueso. El Sacerdote emite un zumbido que sube de"
            "tono y vibra en el pecho.  Papu te mira con lástima, los ojos"
            "brillando bajo la luz verde: — *mano... eso no funciona aquí."
            "ellos saben lo que eres. sisis. de hecho acabas de subir tu"
            "precio. los que gritan son los más frescos.*"
        ),
        on_enter={"voluntad": 3, "lucidez": -4, "corrupcion": 2},
        character_dialogue={
            "aris": "grité que no valgo nada. se rieron. subí mi precio. no funciona",
            "law": "grité que no valgo nada y SE RIERON y subió mi precio NO",
            "haru": "grité que no valgo y se rieron, dice que subí mi precio xd fail",
            "elyko": "sabotaje fallido. gritar = frescura = precio sube. contraproducente.",
            "xoft": "grité que no valgo y se RIERON. subí mi precio. mano.",
            "xokram": "Intenté sabotear y subí mi precio. aquí todo funciona al revés",
            "daraziel": "Grité. Se rieron. El mercado funciona al revés aquí.",
        },
        paths=[
            P("Resignarte y ver la puja", "act2_isla_puja_sube", style="secondary", effects={"voluntad": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_tunel_salida",
        act=A, zone="Isla de Papu — Salida del Túnel",
        tone="calm",
        text=(
            "El túnel sube y se abre a un acantilado. El viento te golpea —"
            "frío, salado, real. Después del aire estancado del sótano, es"
            "como respirar por primera vez. El mar negro abajo, moviéndose con"
            "una calma que no tranquiliza. Sarkomand es una línea de luces"
            "lejanas al norte, parpadeantes como velas a punto de apagarse."
            "Hay un sendero que baja al agua — tallado en la roca, resbaladizo"
            "de sal y musgo. El sonido de las olas es rítmico, hipnótico."
            "Desde aquí, nadar o dejarte llevar por la corriente."
        ),
        on_enter={"lucidez": 4, "voluntad": 3},
        character_dialogue={
            "aris": "salí del túnel. acantilado. sarkomand al norte. sendero al agua",
            "law": "SALÍ del túnel bro Sarkomand está al norte puedo verlo",
            "haru": "salí del túnel, sarkomand al norte, sendero al agua, gg",
            "elyko": "salida. acantilado. sarkomand visible al norte. sendero al agua.",
            "xoft": "salí. Sarkomand al norte. sendero al agua. casi libre. mano.",
            "xokram": "Salí del túnel. Sarkomand al norte. sendero al agua. casi",
            "daraziel": "Acantilado. Mar negro. Sarkomand al norte. Sendero descendente al agua.",
        },
        paths=[
            P("Bajar al agua y nadar a Sarkomand", "act2_isla_escape", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_templo_sacerdote",
        act=A, zone="Isla de Papu — Templo Subterráneo",
        tone="horror",
        text=(
            "El zumbido se hace más fuerte — ya no es sonido, es presión."
            "Vibra en el pecho, en los dientes. El túnel se abre a una cámara"
            "circular con paredes de piedra mojada. En el centro, un pozo. El"
            "pozo no tiene fondo visible — sólo oscuridad que se mueve, que"
            "respira, que sube y baja como marea.  El olor es abrumador:"
            "incienso quemado, sangre vieja, algo orgánico y antiguo. El aire"
            "es espeso, pegajoso. Hace calor húmedo, de cosa viva.  El"
            "Sacerdote Sin Rostro está aquí. De espaldas. Alimenta algo en el"
            "pozo — vierte un frasco de líquido brillante. Una sombra"
            "procesada. La oscuridad la absorbe con un sonido húmedo — como"
            "una boca tragando.  No te ha visto. Todavía."
        ),
        on_enter={"lore": 12, "lucidez": -8, "corrupcion": 6, "memoria": -4},
        set_flags=["vio_templo_sacerdote"],
        character_dialogue={
            "aris": "el sacerdote alimenta algo en un pozo con sombras procesadas. no me vio",
            "law": "el Sacerdote está ALIMENTANDO ALGO en un pozo con sombras bro NO ME VIO",
            "haru": "el sacerdote alimenta un pozo con sombras procesadas, no me vio todavía",
            "elyko": "cámara circular. pozo sin fondo. sacerdote alimenta con sombras. no detectado.",
            "xoft": "el Sacerdote alimenta ALGO en un pozo con sombras. no me vio. mano.",
            "xokram": "El sacerdote alimenta algo con sombras procesadas. no me vio. salir ya",
            "daraziel": "Cámara circular. Pozo sin fondo. El Sacerdote alimenta algo. No me vio.",
        },
        paths=[
            P("Retroceder en silencio", "act2_isla_tunel_salida", style="success", effects={"voluntad": 2}),
            P("Empujar al Sacerdote al pozo", "act2_isla_empujar_sacerdote", style="danger", effects={"voluntad": 10, "corrupcion": 8, "lucidez": -6}),
            P("Robar un frasco del estante", "act2_isla_robar_frasco", style="warning", effects={"lore": 5, "corrupcion": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_dama_cierra",
        act=A, zone="Isla de Papu — La Dama Cierra",
        tone="horror",
        text=(
            "— *Treinta* — dice la Dama. Una sola palabra. El sonido no sale"
            "de su boca — sale del aire mismo, como si la realidad la"
            "obedeciera. El salón se queda en silencio absoluto. Hasta las"
            "lámparas de aceite verde dejan de parpadear. El Sacerdote Sin"
            "Rostro se levanta y se va sin decir nada — su túnica"
            "arrastrándose por el suelo con un susurro seco. El Hombre de Leng"
            "ni siquiera mira atrás.  Papu tartamudea: — *t-treinta... mano..."
            "treinta monedas oníricas... vendido... vendido al lote... a la"
            "clienta de la máscara... waos...*  Le tiemblan las manos. El"
            "micrófono de hueso amplifica el temblor de su voz por todo el"
            "anfiteatro.  La Dama se levanta. Camina hacia ti. Cada paso suena"
            "como porcelana contra mármol — click, click, click — un sonido"
            "limpio y terrible que te recorre la columna. El olor a incienso"
            "se intensifica con cada paso que da. El aire se vuelve más denso,"
            "más difícil de respirar. Sientes el pecho apretarse como si"
            "alguien te pusiera una mano invisible sobre el esternón."
            "Piensas: treinta. Valgo treinta. No sé si eso es mucho o poco y"
            "no sé cuál opción es peor."
        ),
        on_enter={"lucidez": -6, "corrupcion": 5, "voluntad": -4},
        set_flags=["vendido_a_dama", "vio_subasta_papu"],
        character_dialogue={
            "aris": "treinta. todos se fueron. me vendieron a la dama. treinta monedas",
            "law": "TREINTA MONEDAS. todos se fueron. me VENDIERON a la Dama. no.",
            "haru": "dijo treinta y todos se callaron. me vendieron. a la dama. gg",
            "elyko": "30 monedas. cierre instantáneo. los otros se fueron. vendido.",
            "xoft": "TREINTA. todos se callaron. me vendieron a la Dama. mano. no.",
            "xokram": "30 monedas. los otros ni pujaron. ella cerró el mercado",
            "daraziel": "Treinta. Silencio absoluto. Los otros se fueron. Cada paso suena a porcelana.",
        },
        paths=[
            P("Intentar correr antes de que te alcance", "act2_isla_huir_escenario", style="warning", effects={"voluntad": 6, "lucidez": -3}),
            P("Quedarte inmóvil mientras se acerca", "act2_isla_dama_te_toca", style="secondary", effects={"lucidez": -3, "corrupcion": 3}),
            P("Hablarle antes de que llegue", "act2_isla_negociar_dama", style="info", effects={"voluntad": 3, "lore": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_empujar_sacerdote",
        act=A, zone="Isla de Papu — El Sacerdote Cae",
        tone="horror",
        text=(
            "Lo empujas. No pesa casi nada — como empujar una túnica vacía,"
            "como empujar aire con forma. Cae al pozo sin gritar (no tiene"
            "boca). La oscuridad lo absorbe con el mismo sonido húmedo que usó"
            "con las sombras — un trago largo, satisfecho, orgánico.  El olor"
            "que sube del pozo es indescriptible. Rot y algo más. Algo vivo."
            "El pozo se queda quieto. Las paredes de la cámara dejan de"
            "vibrar. Luego, desde abajo, un sonido — no un grito, un..."
            "agradecimiento. Grave, profundo, que sientes en el pecho más que"
            "en los oídos. Lo que sea que vive ahí abajo está satisfecho."
            "Alimentado.  La lámpara de aceite verde en la pared parpadea una"
            "vez. El silencio que sigue es total. Piensas: acabo de matar"
            "algo. O acabo de alimentar algo peor. No sé cuál."
        ),
        on_enter={"voluntad": 8, "corrupcion": 10, "lucidez": -6, "favor": 5},
        set_flags=["mato_sacerdote"],
        character_dialogue={
            "aris": "lo empujé. no pesa. cayó sin gritar. el pozo agradeció. eso es peor",
            "law": "lo EMPUJÉ y cayó sin gritar y el pozo AGRADECIÓ bro QUÉ",
            "haru": "lo empujé, no pesa nada, cayó, el pozo agradeció. qué asco mano",
            "elyko": "empujado. sin peso. sin grito. el pozo agradeció. alimenté algo.",
            "xoft": "lo empujé. cayó. el pozo AGRADECIÓ. alimenté algo sin querer. mano.",
            "xokram": "Lo empujé. el pozo agradeció. alimenté algo. eso no era el plan",
            "daraziel": "No pesa. Cayó. El pozo agradeció. Alimenté lo que él alimentaba.",
        },
        paths=[
            P("Salir del templo inmediatamente", "act2_isla_tunel_salida", style="success", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_robar_frasco",
        act=A, zone="Isla de Papu — Frasco Robado",
        tone="tense",
        text=(
            "Tomas un frasco del estante sin hacer ruido. El vidrio está frío"
            "— un frío que no debería tener. Adentro, una sombra pequeña se"
            "mueve — todavía consciente, todavía formada. Te mira desde el"
            "vidrio con algo que podría ser esperanza.  El zumbido del pozo"
            "vibra en los huesos. Huele a sal y a algo orgánico. El Sacerdote"
            "sigue de espaldas, vertiendo otro frasco en la oscuridad. El"
            "sonido húmedo de absorción te revuelve el estómago.  Sales"
            "despacio, con el frasco contra el pecho. La sombra adentro se"
            "aquieta — como si supiera."
        ),
        on_enter={"lore": 5, "corrupcion": 3, "favor": 3},
        set_flags=["tiene_frasco_sombra"],
        give_item="frasco_sombra_viva",
        character_dialogue={
            "aris": "tomé un frasco. hay una sombra viva adentro. me mira. salí sin que me vea",
            "law": "tomé un frasco con una sombra VIVA adentro que me MIRA bro salí sin que me vea",
            "haru": "tomé un frasco con una sombra viva, me mira desde el vidrio, salí sin ruido",
            "elyko": "frasco con sombra viva. consciente. me mira. sacerdote no detectó. salí.",
            "xoft": "tomé un frasco. sombra viva adentro. me mira. salí sin que me vea.",
            "xokram": "Tomé un frasco con sombra viva. el sacerdote no me vio. salí",
            "daraziel": "Frasco con sombra viva. Me mira desde el vidrio. Salí sin ruido.",
        },
        paths=[
            P("Subir al túnel de salida", "act2_isla_tunel_salida", style="success", effects={"voluntad": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_huir_escenario",
        act=A, zone="Isla de Papu — Huida del Escenario",
        tone="tense",
        text=(
            "Corres. El cartel con tu precio rebota contra tu pecho — el"
            "alambre te corta la piel del cuello con cada paso. Los guardias"
            "reaccionan — pero tarde. Tus pies descalzos golpean la piedra"
            "fría y húmeda. Llegas al borde del escenario y saltas hacia el"
            "pasillo lateral. El impacto en las rodillas te sube hasta los"
            "dientes.  El aire del pasillo huele distinto — a sal, a mar, a"
            "posibilidad. *Corre. Corre. No mires atrás.*  Detrás de ti, Papu"
            "grita: — *¡MANO! ¡LOTE CATORCE SE ESCAPA! ¡LPTM! ¡AGARRENLO!*"
            "Pero la Dama de Porcelana levanta una mano y los guardias se"
            "detienen como marionetas a las que les cortaron los hilos. —"
            "*Déjenlo. Es más divertido así.* — Su voz suena como si"
            "disfrutara. Como porcelana acariciando porcelana. El sonido te"
            "persigue por el pasillo más que cualquier guardia."
        ),
        on_enter={"voluntad": 8, "lucidez": -3},
        set_flags=["huyo_escenario"],
        character_dialogue={
            "aris": "corrí. la dama detuvo a los guardias. dijo que es más divertido así",
            "law": "CORRÍ y la Dama DETUVO a los guardias y dijo que es más DIVERTIDO así NO",
            "haru": "corrí y la dama detuvo a los guardias, dice que es más divertido así xd",
            "elyko": "huí. la dama detuvo guardias. 'más divertido así'. me está cazando.",
            "xoft": "corrí y la Dama detuvo a los guardias. dice que es DIVERTIDO. mano.",
            "xokram": "Corrí y la Dama detuvo a los guardias. me está dejando correr. trampa",
            "daraziel": "Corrí. La Dama detuvo a los guardias. Esto es una cacería, no una fuga.",
        },
        paths=[
            P("Correr al pasillo ciego", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}),
            P("Subir la escalera al estudio", "act2_isla_estudio_papu", style="info", effects={"lore": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_dama_te_toca",
        act=A, zone="Isla de Papu — La Dama Te Reclama",
        tone="horror",
        text=(
            "La Dama llega hasta ti. No habla. No avisa. El aire a su"
            "alrededor huele a incienso quemado y a algo más — algo mineral,"
            "antiguo, como piedra mojada en una tumba abierta. Pone una mano"
            "enguantada en tu pecho — y el sello se graba al instante. No es"
            "un proceso. No es un ritual. Es un hecho. Como sellar una carta."
            "Como cerrar una puerta.  Tres símbolos se hunden en tu piel antes"
            "de que puedas respirar. El dolor dura un segundo — blanco, total,"
            "como si te arrancaran algo que no sabías que tenías. Después,"
            "nada. Sólo la certeza absoluta de que ya no eres tuyo. Un vacío"
            "frío donde antes había voluntad. Entumecimiento.  — *Mío.*  La"
            "palabra resuena dentro de ti como una campana. Se quita la"
            "máscara. El sonido de la porcelana despegándose de la piel es"
            "húmedo, íntimo, obsceno. Debajo hay una cara joven, hermosa,"
            "completamente vacía de empatía. Como mirar un mueble. Como mirar"
            "una pared. Ojos que te ven sin verte.  — *Mi nombre es Zuto."
            "Camina.*  Y tus piernas obedecen antes de que tu cerebro decida"
            "nada."
        ),
        on_enter={"corrupcion": 15, "lucidez": -10, "voluntad": -15, "memoria": -8},
        set_flags=["dama_te_reclamo", "propiedad_dama", "conoce_zuto", "ruta_dama_activa", "sello_dama_completo", "zuto_acompana"],
        character_dialogue={
            "aris": "un segundo. tres símbolos. ya no soy mío. se llama zuto. camina",
            "law": "UN SEGUNDO y ya no soy mío. se quitó la máscara. Zuto. CAMINA dijo.",
            "haru": "un segundo y ya soy suyo, se quitó la máscara, se llama zuto, dijo camina",
            "elyko": "1 segundo. 3 símbolos. sello instantáneo. zuto. propiedad confirmada.",
            "xoft": "un segundo. ya no soy mío. Zuto. me dijo camina. mano.",
            "xokram": "Un segundo. tres símbolos. ya soy propiedad. Zuto. dijo camina",
            "daraziel": "Un segundo. Tres símbolos. Instantáneo. Zuto. Cara vacía. Camina.",
        },
        paths=[
            P("...", "act2_isla_primera_orden", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_negociar_dama",
        act=A, zone="Isla de Papu — Negociando",
        tone="horror",
        text=(
            "— *¿Qué vas a hacer conmigo?* — le preguntas antes de que llegue."
            "La voz te sale ronca. El aire entre ustedes huele a flores"
            "muertas y a algo metálico — como monedas viejas en la lengua.  Se"
            "detiene. Ladea la cabeza. Ese clic de porcelana. — *Moldear. Tu"
            "sustancia es arcilla. Voy a hacer algo con ella. Algo que no"
            "existe todavía. Algo que necesito.* — Cada palabra cae como una"
            "gota fría en tu nuca.  — *¿Y si me niego?*  El silencio dura tres"
            "latidos. Puedes oír las olas lejanas contra la isla. Puedes oír"
            "tu propia sangre.  — *Ya pagué. No hay negociación después del"
            "pago. Pero si cooperas... te dejo recordar quién eras. Si no..."
            "te borro.* — Lo dice como quien describe el clima. Sin crueldad."
            "Sin nada."
        ),
        on_enter={"lore": 8, "corrupcion": 4, "lucidez": -3},
        set_flags=["sabe_plan_dama"],
        character_dialogue={
            "aris": "va a moldearme. si coopero recuerdo. si no, me borra. esas son las opciones",
            "law": "dice que me va a MOLDEAR y si no coopero me BORRA bro",
            "haru": "dice que me moldea, si coopero recuerdo quién soy, si no me borra",
            "elyko": "moldear = transformar sustancia. cooperar = memoria. no cooperar = borrado.",
            "xoft": "me moldea. si coopero recuerdo. si no, me borra. esas son las opciones.",
            "xokram": "Cooperar = recuerdo. No cooperar = borrado. mal trato pero hay opciones",
            "daraziel": "Moldear. Arcilla. Si coopero, memoria. Si no, borrado. Dos caminos.",
        },
        paths=[
            P("Ir con ella (cooperar por ahora)", "act2_isla_sala_preparacion", style="secondary", effects={"lucidez": 2, "corrupcion": 3}),
            P("Negarte rotundamente", "act2_isla_zafarse_dama", style="danger", effects={"voluntad": 8, "lucidez": -5}),
        ],
    ))

    nodes.append(N(
        "act2_isla_primera_orden",
        act=A, zone="Isla de Papu — Primera Orden",
        tone="horror",
        text=(
            "Zuto te mira como se mira una silla que está en el lugar"
            "equivocado. Sus ojos son claros, vacíos de todo excepto función."
            "El aire a su alrededor huele a nada — una ausencia de olor que es"
            "peor que cualquier hedor. La luz parece más blanca donde ella"
            "está, más fría, sin fuente.  — *Arrodíllate.*  No es una"
            "petición. Es una instrucción — como decirle a un objeto «quédate"
            "ahí». El sello en tu pecho pulsa. Un tirón frío, mecánico, que"
            "baja por las piernas. Tus rodillas quieren doblarse solas. Los"
            "músculos se aflojan sin tu permiso. *No. No. Soy una persona. Soy"
            "una persona.*"
        ),
        on_enter={"voluntad": -5, "lucidez": -3},
        character_dialogue={
            "aris": "me dijo arrodíllate como quien mueve un mueble. el sello pulsa",
            "law": "me dijo ARRODÍLLATE como si fuera un MUEBLE y mis rodillas quieren ceder",
            "haru": "me dijo arrodíllate como quien mueve una silla, el sello pulsa",
            "elyko": "orden: arrodíllate. tono: instrucción a objeto. sello pulsa.",
            "xoft": "me dijo arrodíllate como quien mueve un mueble. el sello pulsa. mano.",
            "xokram": "Me ordenó como quien mueve un mueble. el sello pulsa",
            "daraziel": "Instrucción a objeto. No amenaza. El sello pulsa. Las rodillas ceden.",
        },
        paths=[
            P("Resistir (cuesta mucho)", "act2_isla_resistir_orden", style="danger", effects={"voluntad": 8, "lucidez": -6, "corrupcion": 4}, conditions={"voluntad_min": 35}),
            P("Obedecer", "act2_isla_obedecer_orden", style="secondary", effects={"voluntad": -5, "corrupcion": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_sala_preparacion",
        act=A, zone="Isla de Papu — Sala de Preparación",
        tone="horror",
        text=(
            "La sala es blanca. Demasiado blanca. Una blancura sin fuente —"
            "las paredes mismas emiten luz fría que te hace sentir expuesto."
            "Hay una mesa de piedra en el centro, pulida como mármol de"
            "morgue, correas de cuero en los bordes, y estantes con frascos"
            "llenos de líquidos que brillan con luz propia.  El aire huele a"
            "desinfectante y a algo debajo — dulce, orgánico, como flores"
            "pudriéndose en agua estancada.  Papu entra detrás de ti con un"
            "delantal limpio: — *sisis mano, ahora te preparo para la clienta."
            "tranqui, no duele... mucho. es como un empaque, xd. te envuelvo"
            "bonito para que ella te lleve.*  Señala la mesa. La piedra tiene"
            "manchas que la blancura no logra ocultar."
        ),
        on_enter={"voluntad": -5, "lucidez": -4, "corrupcion": 4},
        character_dialogue={
            "aris": "sala blanca. mesa con correas. frascos. papu dice que me va a empacar",
            "law": "hay una MESA CON CORREAS y Papu dice que me va a EMPACAR bro NO",
            "haru": "mesa con correas, frascos brillantes, Papu con delantal dice que me empaca xd",
            "elyko": "mesa, correas, frascos. papu dice 'empacar'. esto es procesamiento.",
            "xoft": "mesa con CORREAS. frascos. Papu dice que me empaca. mano. NO.",
            "xokram": "Mesa con correas y frascos. me van a procesar como mercancía",
            "daraziel": "Sala blanca. Mesa de piedra. Correas. Frascos luminosos. Diseño clínico.",
        },
        paths=[
            P("Subirse a la mesa (cooperar)", "act2_isla_mesa_cooperar", style="secondary", effects={"corrupcion": 5, "lucidez": -3}),
            P("Negarte rotundamente", "act2_isla_mesa_negar", style="warning", effects={"voluntad": 6, "lucidez": -2}),
            P("Atacar a Papu con lo que tengas", "act2_isla_atacar_papu", style="danger", effects={"voluntad": 8, "lucidez": -4}, conditions={"has_item": "hueso_puntiagudo"}),
            P("Tirar los frascos al suelo (caos)", "act2_isla_tirar_frascos", style="danger", effects={"voluntad": 5, "corrupcion": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_zafarse_dama",
        act=A, zone="Isla de Papu — Zafándote",
        tone="horror",
        text=(
            "Te arrancas de su agarre. El hombro donde te tocó arde — un ardor"
            "profundo, como si la marca se hundiera en el hueso. El olor a"
            "incienso frío se intensifica. La Dama no te persigue — se queda"
            "quieta, mirándote con esos agujeros vacíos. La máscara brilla"
            "bajo la luz verde.  — *Corres. Bien. Corre. Te encontraré."
            "Siempre encuentro lo que compré.* — La voz viene de todas partes"
            "— del techo, del suelo, de dentro de tu pecho. No es una amenaza."
            "Es un hecho.  Papu, detrás de ella, te hace señas desesperadas"
            "hacia el pasillo lateral — manos agitándose, ojos abiertos, sudor"
            "dulce brillándole en la frente. Piensas: corro. Piensas: ¿hasta"
            "dónde?"
        ),
        on_enter={"voluntad": 8, "lucidez": -4, "corrupcion": 2},
        set_flags=["escapo_de_dama"],
        character_dialogue={
            "aris": "me zafé. no me persigue. dice que siempre encuentra lo que compró",
            "law": "me ZAFÉ y dice que me va a ENCONTRAR siempre bro CORRO",
            "haru": "me zafé y dice que siempre encuentra lo que compró, Papu me dice que corra",
            "elyko": "me zafé. no persigue. 'siempre encuentro lo que compré'. papu señala salida.",
            "xoft": "me zafé. dice que me encontrará. Papu me dice que corra. CORRO.",
            "xokram": "Me zafé. dice que siempre encuentra lo que compró. Papu dice que corra",
            "daraziel": "Me zafé. No persigue. Dice que siempre encuentra. Papu señala el pasillo.",
        },
        paths=[
            P("Correr al pasillo que señala Papu", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}),
            P("Subir la escalera al estudio", "act2_isla_estudio_papu", style="info", effects={"lore": 3, "lucidez": -2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_resistir_orden",
        act=A, zone="Isla de Papu — Resistencia Inútil",
        tone="horror",
        text=(
            "No te arrodillas. El sello arde — un dolor profundo, como un"
            "gancho de metal frío en el esternón tirando hacia abajo. Duele"
            "como si te arrancaran algo de adentro. Las piernas tiemblan. Pero"
            "te quedas de pie.  Zuto ladea la cabeza. Clic, clic. No se enoja"
            "— eso sería reconocerte como persona. Sólo dice:  — *Un mueble"
            "con opinión. No importa. Los muebles con opinión siguen siendo"
            "muebles.*  La luz aquí es demasiado blanca, sin fuente visible."
            "Se levanta — el movimiento fluido, inhumano. — *Camina. Vamos a"
            "Sarkomand. Tengo cosas que hacer y tú vienes conmigo.*"
        ),
        on_enter={"voluntad": 5, "lucidez": -4, "corrupcion": 3},
        character_dialogue={
            "aris": "no me arrodillé. dijo 'mueble con opinión'. no le importa. sigo siendo suyo",
            "law": "NO me arrodillé y dijo MUEBLE CON OPINIÓN y no le importó SIGO SIENDO SUYO",
            "haru": "no me arrodillé, dijo mueble con opinión, no le importa, sigo siendo suyo",
            "elyko": "resistí. 'mueble con opinión'. sin cambio de estatus. irrelevante para ella.",
            "xoft": "no me arrodillé. dijo mueble con opinión. no le importa. sigo siendo suyo.",
            "xokram": "Resistí. dijo mueble con opinión. no cambió nada. sigo siendo propiedad",
            "daraziel": "Resistí. 'Mueble con opinión.' Sin cambio. Sigo siendo objeto.",
        },
        paths=[
            P("Ir con ella a Sarkomand", "act2_isla_escape_con_dama", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_obedecer_orden",
        act=A, zone="Isla de Papu — Obediencia",
        tone="horror",
        text=(
            "Te arrodillas. Las rodillas golpean la piedra fría — el impacto"
            "sube por los muslos. El sello deja de doler al instante, como una"
            "mano que suelta. El alivio es casi peor que el dolor. *Así de"
            "fácil. Así de fácil te rompieron.*  Zuto asiente — no con"
            "aprobación, con la satisfacción de quien pone un libro en el"
            "estante correcto. Sus ojos no te miran como a una persona. Te"
            "miran como a una cosa que funciona.  — *Bien. Levántate. Camina."
            "No hables a menos que te pregunte algo.* — Su voz es plana, sin"
            "temperatura. Como instrucciones impresas en un manual."
        ),
        on_enter={"voluntad": -8, "corrupcion": 5, "lucidez": -2},
        character_dialogue={
            "aris": "me arrodillé. el sello dejó de doler. asintió como quien guarda un libro",
            "law": "me arrodillé y el sello dejó de doler y asintió como quien guarda un LIBRO",
            "haru": "me arrodillé, el sello dejó de doler, asintió como quien guarda un libro",
            "elyko": "obedecí. sello sin dolor. satisfacción de organizar objetos.",
            "xoft": "me arrodillé. el sello dejó de doler. me ve como un libro en un estante.",
            "xokram": "Obedecí. el sello dejó de doler. me ve como un objeto bien colocado",
            "daraziel": "Obedecí. Sello sin dolor. Asintió como quien coloca un objeto.",
        },
        paths=[
            P("Ir con ella a Sarkomand", "act2_isla_escape_con_dama", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_mesa_cooperar",
        act=A, zone="Isla de Papu — En la Mesa",
        tone="horror",
        text=(
            "Te subes a la mesa. La piedra está fría — un frío que te cala"
            "hasta los huesos a través de la ropa. Papu te ata las correas con"
            "manos practicadas — muñecas, tobillos, pecho. El cuero huele a"
            "sudor viejo y a algo dulce. No aprieta demasiado. — *sisis mano,"
            "tranqui. ahora te pongo el sello de la clienta y listo. es como"
            "un tatuaje pero por dentro.*  Saca un frasco con líquido negro"
            "que no refleja la luz — la absorbe. Y un pincel de hueso,"
            "amarillento, con cerdas que parecen pelo humano. Empieza a pintar"
            "símbolos en tu pecho. Cada trazo se hunde en la piel como si la"
            "tinta tuviera peso propio. Sientes frío donde toca — un frío que"
            "baja, que se mete entre las costillas. El olor a incienso y"
            "sangre dulce te llena la nariz. *No debí subirme. No debí"
            "subirme.*"
        ),
        on_enter={"corrupcion": 8, "lucidez": -5, "voluntad": -6, "memoria": -4},
        set_flags=["sello_dama_parcial"],
        character_dialogue={
            "aris": "me ató. pinta símbolos con tinta negra. se hunden en la piel",
            "law": "me ATÓ y está PINTANDO SÍMBOLOS que se HUNDEN EN MI PIEL no no no",
            "haru": "me ató y pinta símbolos que se hunden en la piel, nmms qué es esto",
            "elyko": "atado. tinta negra. símbolos que se hunden. sello de propiedad.",
            "xoft": "me ató y pinta símbolos que se HUNDEN en mi piel. mano. no.",
            "xokram": "Me está marcando como propiedad. tinta que se hunde. esto es malo",
            "daraziel": "Tinta negra con peso propio. Los símbolos se hunden. Marca de propiedad.",
        },
        paths=[
            P("Intentar romper las correas", "act2_isla_romper_correas", style="warning", effects={"voluntad": 6, "lucidez": -3}),
            P("Dejar que termine (ganar tiempo)", "act2_isla_sello_completo", style="secondary", effects={"corrupcion": 6, "memoria": -5}),
        ],
    ))

    nodes.append(N(
        "act2_isla_mesa_negar",
        act=A, zone="Isla de Papu — Negativa",
        tone="tense",
        text=(
            "— *No me subo a eso.*  La mesa de piedra brilla bajo la luz"
            "blanca — demasiado blanca, sin fuente visible. Las correas de"
            "cuero cuelgan como lenguas muertas. El olor a desinfectante y a"
            "algo orgánico debajo te revuelve el estómago.  Papu suspira. Se"
            "frota las manos — están manchadas de tinta negra que no se va: —"
            "*mano... la clienta pagó treinta. si no te preparo, ella viene a"
            "prepararte ella misma. y mano, sisis, créeme que es peor. yo al"
            "menos soy... gentil. xd.*  Te mira con algo que podría ser"
            "lástima genuina. Sus ojos están húmedos. — *te doy un minuto para"
            "decidir. después llamo a la Dama.* — El silencio que sigue pesa"
            "como piedra mojada."
        ),
        on_enter={"voluntad": 4, "lucidez": 2},
        character_dialogue={
            "aris": "me negué. papu dice que si no me prepara él, viene la dama. un minuto",
            "law": "me negué y Papu dice que si no me prepara ÉL viene la DAMA bro",
            "haru": "me negué, Papu dice que si no lo hace él viene la dama, un minuto",
            "elyko": "negativa. papu da 1 minuto. alternativa: la dama prepara. peor.",
            "xoft": "me negué. Papu dice que viene la Dama si no. un minuto. mano.",
            "xokram": "Me negué. un minuto antes de que venga la Dama. hay que actuar",
            "daraziel": "Me negué. Un minuto. Papu dice que la alternativa es peor.",
        },
        paths=[
            P("Usar el minuto para buscar salida", "act2_isla_buscar_salida_prep", style="success", effects={"voluntad": 3, "lucidez": 2}),
            P("Aceptar que Papu te prepare (mal menor)", "act2_isla_mesa_cooperar", style="secondary", effects={"voluntad": -3, "corrupcion": 3}),
            P("Esperar a la Dama (enfrentarla)", "act2_isla_dama_prepara", style="danger", effects={"voluntad": 5, "corrupcion": 6}),
        ],
    ))

    nodes.append(N(
        "act2_isla_atacar_papu",
        act=A, zone="Isla de Papu — Atacando a Papu",
        tone="horror",
        text=(
            "Sacas el hueso puntiagudo y lo clavas en el brazo de Papu. La"
            "resistencia de la carne es menor de lo que esperabas — como"
            "hundir un cuchillo en fruta madura. Él grita — *¡LPTM MANO! ¡OTRA"
            "VEZ! ¡WAOS!* — y suelta el pincel, que cae al suelo con un"
            "chasquido húmedo. Lo que sale de su brazo no es sangre: es un"
            "líquido espeso y dulce, del color del ámbar oscuro, y el olor te"
            "golpea — blood-sweet, empalagoso, el mismo que oliste cuando te"
            "drogó. Te revuelve el estómago.  Papu cae de rodillas,"
            "agarrándose el brazo. El líquido le escurre entre los dedos y"
            "gotea en las baldosas blancas con un sonido suave, rítmico. Te"
            "mira con los ojos muy abiertos — no con odio, con sorpresa. La"
            "luz demasiado blanca de la sala le hace parecer más pálido de lo"
            "que debería ser posible.  — *mano... nadie me había... waos. gg."
            "gg mi brazo.*  Piensas: no es humano. Nunca lo fue. Y aun así"
            "sientes algo parecido a la culpa raspándote la garganta."
        ),
        on_enter={"voluntad": 10, "lucidez": -3, "favor": -5},
        set_flags=["ataco_a_papu"],
        character_dialogue={
            "aris": "lo apuñalé. no tiene sangre. tiene el líquido dulce. no es humano",
            "law": "LE CLAVÉ EL HUESO y no tiene SANGRE tiene líquido DULCE bro QUÉ ES",
            "haru": "le clavé el hueso y no sangra normal, tiene líquido dulce, no es humano",
            "elyko": "apuñalado. no sangre. líquido espeso dulce. el mismo de la droga. no humano.",
            "xoft": "le clavé el hueso. no tiene sangre. tiene el líquido dulce. NO ES HUMANO.",
            "xokram": "Lo apuñalé y no sangra normal. tiene el líquido de la droga. no es humano",
            "daraziel": "No sangra. Líquido espeso y dulce. El mismo de la droga. No es humano.",
        },
        paths=[
            P("Tomar sus llaves y correr", "act2_isla_llaves_papu", style="success", effects={"voluntad": 4}, give_item="llaves_papu"),
            P("Preguntarle qué es él", "act2_isla_que_es_papu", style="info", effects={"lore": 8, "lucidez": -4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_tirar_frascos",
        act=A, zone="Isla de Papu — Frascos Rotos",
        tone="horror",
        text=(
            "Barres los estantes con el brazo. Veinte frascos caen y estallan"
            "contra la piedra. El estruendo es enorme en la sala blanca. Los"
            "líquidos se mezclan en el suelo — y empiezan a moverse solos."
            "Formas. Caras. Manos pequeñas que se estiran hacia arriba y se"
            "disuelven con un suspiro colectivo.  Eran sombras. Sombras ya"
            "procesadas. Ya empacadas. Disueltas en frascos esperando entrega."
            "El olor que sube es dulce y podrido — fruta fermentada con"
            "incienso. El aire se llena de susurros diminutos.  Papu grita: —"
            "*¡MANO! ¡LPTM! ¡ESO ERA MERCANCÍA PAGADA! ¡ME VAS A ARRUINAR!* —"
            "Está de rodillas entre vidrios rotos, el líquido dulce de su"
            "sangre mezclándose con los restos."
        ),
        on_enter={"lore": 10, "corrupcion": 5, "lucidez": -6, "voluntad": 4},
        set_flags=["rompio_frascos", "vio_sombras_procesadas"],
        character_dialogue={
            "aris": "los frascos tenían sombras procesadas. disueltas. empacadas. eran personas",
            "law": "los frascos tenían SOMBRAS DISUELTAS con CARAS y MANOS bro eran personas",
            "haru": "los frascos tenían sombras procesadas, se ven caras y manos, qué asco mano",
            "elyko": "frascos = sombras procesadas. caras, manos. mercancía pagada. ya entregada.",
            "xoft": "los frascos tenían SOMBRAS PROCESADAS. caras. manos. eran PERSONAS.",
            "xokram": "Los frascos eran mercancía pagada. sombras procesadas. esto es peor de lo que pensé",
            "daraziel": "Los líquidos forman caras y manos. Sombras procesadas. Empacadas en frascos.",
        },
        paths=[
            P("Correr mientras Papu llora su mercancía", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 5}),
            P("Romper más frascos (liberar todo)", "act2_isla_liberar_frascos", style="warning", effects={"favor": 10, "lucidez": -5, "corrupcion": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_escape_con_dama",
        act=A, zone="Regreso a Sarkomand — Con Zuto",
        tone="tense",
        text=(
            "Zuto camina. Sus pasos suenan como porcelana contra piedra —"
            "click, click, click — rítmicos, inhumanos, perfectos. Tú caminas"
            "detrás. No te ata, no te empuja — no necesita. El sello te"
            "mantiene a tres pasos de ella, siempre. Como un perro con correa"
            "invisible. El tirón en el pecho es constante, frío, un"
            "recordatorio que no necesitas.  Llegan a Sarkomand. Las ruinas se"
            "ven distintas con ella al lado — más pequeñas. Más"
            "insignificantes. Como tú. El aire huele a polvo y a incienso — su"
            "incienso, que la sigue como una sombra perfumada. Las piedras"
            "antiguas parecen encogerse a su paso.  — *Sigue tu camino. Haz lo"
            "que hacías. Pero cuando te llame, vienes. Cuando te ordene,"
            "obedeces. No siempre estaré visible. Pero siempre estaré.*  Se"
            "aleja. El sonido de sus pasos se desvanece. Pero el frío en el"
            "pecho no. Piensas: soy un mueble que camina. Un mueble con"
            "memoria."
        ),
        on_enter={"lucidez": 2, "voluntad": -3, "memoria": 2},
        set_flags=["escapo_isla_papu"],
        character_dialogue={
            "aris": "camino detrás. el sello me mantiene cerca. siempre estará. siempre",
            "law": "camino detrás y el sello me mantiene cerca SIEMPRE ESTARÁ dijo",
            "haru": "camino detrás, el sello me mantiene a 3 pasos, siempre estará",
            "elyko": "3 pasos detrás. sello = correa invisible. 'siempre estaré'. permanente.",
            "xoft": "camino detrás. el sello me mantiene. siempre estará. mano.",
            "xokram": "Camino detrás. el sello me mantiene. siempre estará. permanente",
            "daraziel": "Tres pasos detrás. Sello como correa. Siempre estará. Permanente.",
        },
        paths=[
            P("Continuar tu viaje (con ella)", "act2_sarkomand_ruinas", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_romper_correas",
        act=A, zone="Isla de Papu — Rompiendo Correas",
        tone="tense",
        text=(
            "Tiras de las correas con todo. El cuero es viejo — huele a sudor"
            "ajeno y a miedo acumulado. Una se rompe con un chasquido seco."
            "Luego otra. Papu retrocede con el pincel en alto, goteando tinta"
            "negra que se mueve sola en el suelo: — *mano mano mano, tranqui,"
            "no hagas eso—*  Te levantas de la mesa. Los símbolos a medio"
            "pintar en tu pecho arden, incompletos — chispas errantes bajo la"
            "piel. La luz blanca te ciega un segundo. Papu está entre tú y la"
            "puerta. No es un guerrero. Nunca lo fue. Piensas: puedo pasar."
        ),
        on_enter={"voluntad": 8, "lucidez": -2, "corrupcion": 2},
        set_flags=["rompio_correas"],
        character_dialogue={
            "aris": "rompí las correas. los símbolos arden incompletos. papu entre yo y la puerta",
            "law": "ROMPÍ LAS CORREAS y me levanté y Papu está entre yo y la puerta",
            "haru": "rompí las correas, los símbolos arden, Papu entre yo y la puerta",
            "elyko": "correas rotas. símbolos incompletos = inestables. papu bloquea puerta.",
            "xoft": "rompí las correas. me levanté. Papu entre yo y la puerta. MUÉVETE.",
            "xokram": "Correas rotas, símbolos incompletos. Papu bloquea la salida",
            "daraziel": "Correas rotas. Símbolos incompletos arden. Papu bloquea la puerta.",
        },
        paths=[
            P("Empujar a Papu y salir", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4, "favor": -3}),
            P("Atacarlo con lo que tengas", "act2_isla_atacar_papu", style="danger", effects={"voluntad": 6}, conditions={"has_item": "hueso_puntiagudo"}),
            P("Pedirle que se quite", "act2_isla_oferta_papu", style="info", effects={"lore": 2}),
        ],
    ))

    nodes.append(N(
        "act2_isla_sello_completo",
        act=A, zone="Isla de Papu — Sello Completo",
        tone="horror",
        text=(
            "Papu termina de pintar. El último trazo se hunde con un sonido —"
            "no externo, dentro de ti, como una puerta cerrándose. Los"
            "símbolos se hunden completamente — ya no están en tu piel, están"
            "debajo. Sientes algo frío moverse dentro, como un parásito de"
            "tinta deslizándose entre las costillas.  El aire sabe a metal."
            "Náusea.  — *listo mano. sisis. ahora eres oficialmente propiedad"
            "de la Dama. cuando ella te llame, vas a sentir un tirón aquí.* —"
            "Se toca el pecho. — *no te resistas al tirón. duele más si te"
            "resistes.*  Te desata. El mundo se siente más estrecho. — *la"
            "Dama viene en una hora. tienes ese rato.* — No te mira a los"
            "ojos."
        ),
        on_enter={"corrupcion": 10, "lucidez": -6, "voluntad": -5, "memoria": -5},
        set_flags=["sello_dama_completo"],
        character_dialogue={
            "aris": "sello completo. algo frío se mueve dentro. soy propiedad. una hora",
            "law": "los símbolos están DENTRO DE MÍ y soy PROPIEDAD y tengo UNA HORA",
            "haru": "el sello está dentro, soy propiedad oficial, tengo una hora para escapar",
            "elyko": "sello interno. parásito de tinta. propiedad oficial. 1 hora. tirón si llama.",
            "xoft": "el sello está DENTRO. soy propiedad. una hora. mano. CORRO.",
            "xokram": "Sello completo, soy propiedad. una hora antes de que venga. a moverse",
            "daraziel": "Sello interno. Parásito de tinta. Una hora. El tirón viene si ella llama.",
        },
        paths=[
            P("Correr al pasillo inmediatamente", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 5}),
            P("Buscar cómo romper el sello", "act2_isla_romper_sello", style="info", effects={"lore": 5, "lucidez": -3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_buscar_salida_prep",
        act=A, zone="Isla de Papu — Buscando Salida",
        tone="tense",
        text=(
            "Tienes un minuto. El corazón te late en la garganta. Miras"
            "alrededor: la puerta por donde entraste — el salón de subastas al"
            "otro lado, murmullos y pasos —, una ventana alta con barrotes de"
            "hierro negro donde se condensa la humedad, y un desagüe en el"
            "suelo lo bastante grande para una persona. Una rejilla oxidada lo"
            "cubre apenas.  El desagüe huele a mar y a algo podrido — carne"
            "vieja, sal, descomposición orgánica que te sube por la nariz y se"
            "instala detrás de los ojos. La ventana da al pasillo lateral; a"
            "través de los barrotes ves la luz verde de las lámparas de aceite"
            "parpadeando. La puerta lleva de vuelta al salón de subastas,"
            "donde el ruido de cadenas y voces inhumanas sigue creciendo."
            "Piensas: un minuto. Sesenta latidos. Elige."
        ),
        on_enter={"lucidez": 3, "lore": 2},
        character_dialogue={
            "aris": "puerta, ventana con barrotes, desagüe al mar. un minuto",
            "law": "puerta ventana desagüe UN MINUTO para elegir bro",
            "haru": "puerta, ventana, desagüe. un minuto. el desagüe huele a mar",
            "elyko": "3 salidas: puerta (salón), ventana (pasillo), desagüe (mar). 1 minuto.",
            "xoft": "puerta, ventana, desagüe. un minuto. el desagüe huele a mar y podrido.",
            "xokram": "Tres salidas, un minuto. desagüe al mar es la más directa",
            "daraziel": "Tres salidas. Desagüe al mar. Ventana al pasillo. Puerta al salón.",
        },
        paths=[
            P("Meterte por el desagüe", "act2_isla_desague", style="warning", effects={"voluntad": 3, "lucidez": -3}),
            P("Salir por la ventana al pasillo", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 2}),
            P("Volver al salón (arriesgado)", "act2_isla_espiar_subasta", style="danger", effects={"lore": 4, "lucidez": -4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_dama_prepara",
        act=A, zone="Isla de Papu — La Dama Prepara",
        tone="horror",
        text=(
            "La Dama entra a la sala. El olor a incienso la precede — dulce,"
            "espeso, con un fondo metálico que te hace lagrimear. La luz"
            "demasiado blanca parpadea una vez cuando cruza el umbral, como si"
            "la electricidad le tuviera miedo. Papu se pega a la pared con un"
            "sonido ahogado, las manos contra la piedra fría.  Ella no usa"
            "pincel — usa las manos. Se quita los guantes despacio. Debajo,"
            "los dedos son blancos como hueso, sin uñas, sin líneas, sin"
            "imperfecciones. Cada dedo deja una marca negra donde toca — como"
            "si tu piel fuera papel y ella escribiera con fuego frío. No"
            "necesita correas: donde te toca, no puedes moverte. La parálisis"
            "es instantánea, total, sin dolor. Peor que dolor.  — *Quieto."
            "Esto es más rápido si no te mueves. Más lento si te resistes."
            "Pero termina igual.*  Su voz suena como porcelana deslizándose"
            "sobre porcelana. Pinta tres símbolos. Cada uno se hunde en tu"
            "piel con un frío que te llega hasta los huesos. Sientes tu"
            "voluntad comprimirse — hacerse más pequeña, más densa, más fácil"
            "de guardar en un cajón."
        ),
        on_enter={"corrupcion": 12, "voluntad": -10, "lucidez": -6, "memoria": -5},
        set_flags=["dama_te_sello", "sello_dama_completo"],
        character_dialogue={
            "aris": "la dama no usa pincel. usa las manos. donde toca no me muevo",
            "law": "la Dama me toca y NO PUEDO MOVERME donde toca se CONGELA todo",
            "haru": "la dama usa las manos, donde toca no me muevo, tres símbolos adentro",
            "elyko": "sin pincel. manos directas. parálisis al contacto. 3 símbolos. voluntad comprimida.",
            "xoft": "la Dama usa las MANOS. donde toca no me muevo. tres símbolos. mano.",
            "xokram": "La Dama no necesita herramientas. donde toca paraliza. tres sellos",
            "daraziel": "Sin pincel. Manos directas. Parálisis al contacto. Tres símbolos hundidos.",
        },
        paths=[
            P("Resistir con todo (voluntad pura)", "act2_isla_resistir_dama", style="danger", effects={"voluntad": 12, "lucidez": -8}, conditions={"voluntad_min": 45}),
            P("Ceder y buscar oportunidad después", "act2_isla_post_sello_dama", style="secondary", effects={"lucidez": 2, "corrupcion": 4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_llaves_papu",
        act=A, zone="Isla de Papu — Con las Llaves",
        tone="tense",
        text=(
            "Tienes el manojo de llaves de Papu. Doce llaves pequeñas de latón"
            "frío — cada una abre una jaula. Y una llave grande, más pesada,"
            "oxidada en los dientes, que abre las puertas principales. El"
            "metal te enfría la palma. Huelen a sal y al líquido dulce de"
            "Papu.  Papu no te persigue. Está en el suelo, agarrándose el"
            "brazo, mirando al techo con ojos que ya no enfocan. El líquido"
            "espeso le empapa la manga. Tienes segundos antes de que los"
            "guardias noten que algo va mal. El corazón te late en la"
            "garganta. *Muévete. Ahora.*"
        ),
        on_enter={"voluntad": 4, "lucidez": 2},
        character_dialogue={
            "aris": "12 llaves de jaulas, 1 llave grande. papu no me persigue. segundos",
            "law": "tengo las LLAVES bro 12 de jaulas y 1 grande VAMOS",
            "haru": "tengo las llaves, 12 de jaulas y una grande, Papu no se mueve",
            "elyko": "12 llaves jaulas + 1 grande puertas. papu en el suelo. segundos.",
            "xoft": "tengo las llaves. 12 jaulas. 1 grande. Papu no se mueve. VAMOS.",
            "xokram": "12 llaves de jaulas y una grande. Papu no persigue. a moverse",
            "daraziel": "Doce llaves pequeñas, una grande. Papu en el suelo. Tiempo limitado.",
        },
        paths=[
            P("Liberar las jaulas del salón", "act2_isla_liberar_jaulas", style="warning", effects={"favor": 10, "lucidez": -4}),
            P("Ir directo al pasillo de escape", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_que_es_papu",
        act=A, zone="Isla de Papu — ¿Qué Eres?",
        tone="discovery",
        text=(
            "— *¿Qué eres?* — le preguntas mientras se agarra el brazo. El"
            "olor dulce del líquido que le sale llena la sala, empalagoso,"
            "revolviendo el estómago.  Papu te mira. Por primera vez no"
            "sonríe. La luz blanca le marca cada arruga, cada costura que no"
            "habías notado — tiene costuras, como los Hombres de Leng, pero"
            "más finas. — *mano... yo era como tú. sisis. hace muchas lunas."
            "me compraron. me procesaron. pero no me disolvieron — me..."
            "reciclaron. me hicieron esto. ahora vendo a otros para no ser"
            "vendido yo. xd. es como... la cadena alimenticia, mano.*  Se mira"
            "el brazo donde el líquido dulce ya dejó de salir. La herida se"
            "sella sola, como cera tapando un frasco. — *si dejas de vender,"
            "te disuelven. así funciona.*"
        ),
        on_enter={"lore": 12, "corrupcion": 4, "lucidez": -4, "memoria": -3},
        set_flags=["sabe_origen_papu"],
        character_dialogue={
            "aris": "papu era como yo. lo compraron, lo reciclaron. vende para no ser vendido",
            "law": "Papu ERA COMO YO y lo RECICLARON y ahora vende para no ser vendido bro",
            "haru": "papu era como nosotros, lo reciclaron, vende para no ser vendido. peak lore",
            "elyko": "papu = ex-producto reciclado. vende para no ser disuelto. cadena alimenticia.",
            "xoft": "Papu era como yo. lo reciclaron. vende para no ser vendido. mano.",
            "xokram": "Era producto, lo reciclaron, ahora vende. si deja de vender lo disuelven",
            "daraziel": "Era como yo. Lo reciclaron. Vende para no ser vendido. Ciclo cerrado.",
        },
        paths=[
            P("Tomar sus llaves y correr", "act2_isla_llaves_papu", style="success", effects={"voluntad": 3}, give_item="llaves_papu"),
            P("Ofrecerle escapar juntos", "act2_isla_oferta_papu", style="info", effects={"favor": 5, "lore": 3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_liberar_frascos",
        act=A, zone="Isla de Papu — Liberando Frascos",
        tone="awe",
        text=(
            "Rompes todo. Cada frasco. Cada estante. El vidrio estalla y te"
            "corta las manos — no te importa. Los líquidos se mezclan en el"
            "suelo, brillando con luz propia, y empiezan a moverse solos. Las"
            "sombras procesadas se elevan como humo con forma — docenas de"
            "ellas, subiendo hacia el techo, atravesando la piedra, yéndose."
            "El olor es abrumador: dulce como sangre, salado como mar, amargo"
            "como incienso quemado todo a la vez.  Algunas te miran antes de"
            "irse. Una te toca la mejilla con una mano que ya casi no existe —"
            "el contacto es frío, eléctrico, y huele a lluvia. Gratitud sin"
            "palabras. *Eran personas. Todas eran personas.*  El salón queda"
            "en silencio excepto por el goteo del vidrio roto. Papu está en el"
            "suelo, llorando, el líquido dulce de su brazo mezclándose con las"
            "sombras derramadas: — *mano... mi inventario... lunas de"
            "trabajo... lptm...*"
        ),
        on_enter={"favor": 15, "voluntad": 8, "lucidez": -4, "corrupcion": -5},
        set_flags=["libero_todas_sombras"],
        character_dialogue={
            "aris": "las liberé todas. docenas. suben como humo. una me tocó la mejilla",
            "law": "las liberé TODAS y suben como humo y una me TOCÓ la mejilla bro",
            "haru": "rompí todo, las sombras suben y se van, una me tocó la mejilla, god",
            "elyko": "docenas liberadas. suben. una tocó mi mejilla. papu llora. inventario perdido.",
            "xoft": "las liberé TODAS. suben. una me tocó la mejilla. Papu llora. BIEN.",
            "xokram": "Liberé todo su inventario. Papu llora. las sombras se fueron agradecidas",
            "daraziel": "Docenas suben como humo con forma. Una me toca. Gratitud sin palabras.",
        },
        paths=[
            P("Salir mientras Papu llora", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_oferta_papu",
        act=A, zone="Isla de Papu — Oferta",
        tone="calm",
        text=(
            "— *Ven conmigo. Escapamos los dos.*  Papu te mira. El líquido"
            "dulce ya dejó de salir de su brazo — se coaguló en algo que"
            "parece ámbar. Algo cambia en su cara — algo viejo, algo que"
            "recuerda haber sido. Un parpadeo. Una sombra de quien fue antes"
            "de que lo reciclaran. Luego niega con la cabeza.  — *no mano."
            "sisis. yo ya no puedo salir. estoy hecho de esto. si salgo de la"
            "isla me disuelvo. como los frascos. como las sombras. pero... te"
            "doy las llaves. y te digo por dónde salir. es lo que puedo.*  Te"
            "entrega el manojo de llaves. Doce llaves pequeñas. El metal está"
            "tibio — calor de su mano. Huele a ese líquido dulce. *Era como"
            "yo. Era exactamente como yo.*"
        ),
        on_enter={"favor": 8, "lore": 4, "voluntad": 3},
        set_flags=["papu_te_ayuda"],
        give_item="llaves_papu",
        character_dialogue={
            "aris": "le ofrecí escapar. no puede. está hecho de esto. me dio las llaves",
            "law": "le ofrecí escapar y dijo que NO PUEDE que se disuelve si sale bro me dio las llaves",
            "haru": "le ofrecí escapar pero dice que se disuelve si sale, me dio las llaves",
            "elyko": "no puede salir. se disuelve fuera. me dio las llaves. 12 llaves.",
            "xoft": "no puede salir. se disuelve. me dio las llaves. mano. esto es triste.",
            "xokram": "No puede salir, se disuelve. me dio las llaves. es lo que puede dar",
            "daraziel": "No puede salir. Está hecho de la isla. Me dio las llaves. Doce.",
        },
        paths=[
            P("Tomar las llaves e ir al pasillo", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}),
            P("Preguntarle la mejor ruta", "act2_isla_ruta_papu", style="info", effects={"lore": 5}),
        ],
    ))

    nodes.append(N(
        "act2_isla_romper_sello",
        act=A, zone="Isla de Papu — Rompiendo el Sello",
        tone="discovery",
        text=(
            "Buscas en los estantes que quedan. Las manos te tiemblan — el"
            "frío del sello pulsa bajo la piel. Un frasco etiquetado"
            "«DISOLVENTE — NO USAR EN PRODUCTO SELLADO» te llama la atención."
            "Si el sello es tinta... el disolvente debería funcionar.  Te lo"
            "echas en el pecho. ARDE. Como ácido sobre carne viva. El olor es"
            "químico, metálico, mezclado con algo dulce-podrido. Los símbolos"
            "se retuercen bajo la piel, intentando quedarse — puedes verlos"
            "moverse como gusanos negros. Pero ceden. Uno a uno salen a la"
            "superficie y se evaporan con un siseo fino.  Cuando termina,"
            "tienes el pecho en carne viva. Hipersensible al aire frío. Pero"
            "eres libre del sello. La ausencia del tirón es lo más hermoso que"
            "has sentido en lunas."
        ),
        on_enter={"voluntad": 8, "lucidez": -5, "corrupcion": -8, "memoria": 3},
        set_flags=["sello_roto"],
        character_dialogue={
            "aris": "encontré disolvente. arde como ácido. el sello salió. soy libre del sello",
            "law": "me eché DISOLVENTE y ARDE pero el sello SALIÓ soy libre bro",
            "haru": "me eché disolvente, ardió como ácido pero el sello salió, gg",
            "elyko": "disolvente aplicado. arde. símbolos salen. sello roto. pecho en carne viva.",
            "xoft": "me eché disolvente. ARDE. pero el sello salió. soy libre. mano.",
            "xokram": "Disolvente. arde. pero el sello salió. ya no soy propiedad",
            "daraziel": "Disolvente contra tinta. Arde. Los símbolos salen. Sello roto. Libre.",
        },
        paths=[
            P("Correr al pasillo", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_desague",
        act=A, zone="Isla de Papu — Desagüe al Mar",
        tone="tense",
        text=(
            "Te metes por el desagüe. La rejilla cede con un chirrido oxidado"
            "que te hace apretar los dientes. Es estrecho — los hombros rozan"
            "las paredes de piedra húmeda, resbaladiza, cubierta de algo"
            "viscoso que no quieres identificar. Huele a sal y a algo orgánico"
            "— putrefacción marina, tripas de pez, vida descomponiéndose."
            "Avanzas a gatas. El sonido de tus manos contra la piedra mojada"
            "rebota en el tubo como un eco enfermo.  El tubo baja en ángulo —"
            "cada vez más rápido. Pierdes tracción. Resbalas. El aire se"
            "vuelve más frío, más salado, más real.  De pronto el tubo termina"
            "y caes al mar negro. El agua te recibe fría — un golpe total,"
            "eléctrico, que te roba el aire de los pulmones. La sal te arde en"
            "los cortes de los dedos. La isla está arriba, en el acantilado,"
            "las luces verdes diminutas como ojos de insecto. Estás fuera."
            "Piensas: fuera. Fuera. El pecho se te afloja por primera vez en"
            "horas."
        ),
        on_enter={"voluntad": 4, "lucidez": -3},
        set_flags=["escape_desague"],
        character_dialogue={
            "aris": "desagüe estrecho. caí al mar. estoy fuera de la isla",
            "law": "me metí por el desagüe y CAÍ AL MAR bro estoy FUERA",
            "haru": "me metí por el desagüe, caí al mar, estoy fuera de la isla",
            "elyko": "desagüe → caída → mar. fuera de la isla. funcional.",
            "xoft": "desagüe. caí al mar. estoy fuera. mano. LIBRE.",
            "xokram": "Desagüe al mar. caí. estoy fuera. funciona",
            "daraziel": "Desagüe en ángulo. Caída al mar. Fuera de la isla. Funcional.",
        },
        paths=[
            P("Nadar a Sarkomand", "act2_isla_escape", style="primary"),
        ],
    ))

    nodes.append(N(
        "act2_isla_resistir_dama",
        act=A, zone="Isla de Papu — Resistencia Pura",
        tone="horror",
        text=(
            "Empujas. Con todo. No con el cuerpo — con algo más profundo. Tu"
            "sueño empuja contra el suyo. Es como meter las manos en agua"
            "helada y apretar. Los símbolos que pintó se agrietan con un"
            "sonido fino de porcelana rompiéndose. La Dama retrocede un paso —"
            "el primer paso atrás que da en toda la noche.  El aire huele a"
            "incienso quemado y a metal. Sientes náusea, presión en el pecho."
            "— *Interesante* — dice. Y por primera vez suena... sorprendida. —"
            "*Nadie había hecho eso. Nadie.*  Los símbolos se rompen. Caen"
            "como ceniza negra sobre la piedra mojada. Eres libre del sello."
            "El alivio es físico. Pero ella sigue ahí."
        ),
        on_enter={"voluntad": 10, "corrupcion": -6, "lucidez": -5},
        set_flags=["resistio_dama", "sello_roto"],
        character_dialogue={
            "aris": "empujé con el sueño. los símbolos se agrietaron. retrocedió. nadie había hecho eso",
            "law": "EMPUJÉ CON TODO y los símbolos se ROMPIERON y ella RETROCEDIÓ bro",
            "haru": "empujé con el sueño y los símbolos se rompieron, ella retrocedió, peak",
            "elyko": "resistencia onírica. símbolos rotos. ella retrocedió. primera vez. notable.",
            "xoft": "empujé y los símbolos se ROMPIERON. ella retrocedió. NADIE había hecho eso.",
            "xokram": "Empujé con todo y los símbolos se rompieron. ella retrocedió. primera vez",
            "daraziel": "Empujé con el sueño. Símbolos agrietados. Ella retrocedió. Sin precedentes.",
        },
        paths=[
            P("Correr mientras está sorprendida", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 5}),
            P("Enfrentarla cara a cara", "act2_isla_cara_a_cara_dama", style="danger", effects={"voluntad": 8, "corrupcion": 8}),
        ],
    ))

    nodes.append(N(
        "act2_isla_post_sello_dama",
        act=A, zone="Isla de Papu — Después del Sello",
        tone="horror",
        text=(
            "La Dama termina. Te suelta. Puedes moverte otra vez — pero"
            "sientes el sello dentro, como un anzuelo clavado entre las"
            "costillas. Frío. Vivo. Moviéndose apenas cuando respiras. El olor"
            "a flores muertas se queda en tu piel donde ella tocó. Ella se"
            "aleja hacia la puerta — cada paso un clic de porcelana contra"
            "piedra.  — *Vendré por ti en una hora. No corras. El sello te"
            "trae de vuelta.*  Se va. El aire se calienta dos grados. Papu se"
            "despega de la pared, temblando, con sudor en la frente que huele"
            "a ese líquido dulce: — *mano... tienes una hora. el sello te trae"
            "de vuelta si ella llama. pero si sales de la isla antes... no"
            "llega.* — Te mira con urgencia. — *una hora, mano. corre.*"
        ),
        on_enter={"lucidez": 3, "voluntad": 2},
        set_flags=["sabe_limite_sello"],
        character_dialogue={
            "aris": "una hora. el sello me trae de vuelta si llama. pero si salgo de la isla no llega",
            "law": "UNA HORA y el sello me trae de vuelta PERO si salgo de la isla no llega CORRO",
            "haru": "una hora, el sello me jala si llama, pero si salgo de la isla no llega",
            "elyko": "1 hora. sello = recall si llama. fuera de la isla = sin efecto. salir ya.",
            "xoft": "una hora. el sello me jala. pero si salgo de la isla no llega. CORRO.",
            "xokram": "Una hora. fuera de la isla el sello no funciona. hay que salir ya",
            "daraziel": "Una hora. El sello tiene rango limitado a la isla. Salir = libre.",
        },
        paths=[
            P("Correr al pasillo inmediatamente", "act2_isla_pasillo_caos", style="success", effects={"voluntad": 5}),
            P("Pedirle a Papu la mejor ruta", "act2_isla_ruta_papu", style="info", effects={"lore": 4}),
        ],
    ))

    nodes.append(N(
        "act2_isla_ruta_papu",
        act=A, zone="Isla de Papu — Ruta de Papu",
        tone="calm",
        text=(
            "— *mano, sisis. hay tres formas de salir.* — Papu habla rápido,"
            "mirando hacia la puerta. El sudor dulce le baja por la frente. —"
            "*la ventana de arriba tiene un Shantak amarrado — es mi"
            "transporte. si lo montas, llegas a Sarkomand en diez minutos. la"
            "puerta del muelle lleva al mar — dos lunas nadando. y el sótano"
            "tiene un túnel que sale a las ruinas... pero pasa por debajo del"
            "templo del Sacerdote. no recomiendo esa.*  Se oyen cadenas"
            "arrastrándose en algún lugar del edificio. El aire huele a aceite"
            "verde quemado.  — *ah, y mano. la Dama te va a buscar. siempre"
            "encuentra lo que compra. corre rápido.* — Te mira con"
            "reconocimiento. Como si se viera a sí mismo, muchas lunas atrás."
        ),
        on_enter={"lore": 8, "lucidez": 3},
        set_flags=["sabe_rutas_isla"],
        character_dialogue={
            "aris": "tres rutas: shantak arriba, mar por muelle, túnel por sótano. la dama me busca",
            "law": "tres rutas: Shantak, mar, o túnel bajo el templo. la Dama me busca. CORRO",
            "haru": "shantak arriba, mar por muelle, túnel por sótano. la dama me busca",
            "elyko": "3 rutas: shantak (10min), muelle (2 lunas), túnel (peligroso). dama persigue.",
            "xoft": "tres rutas. shantak, mar, túnel. la Dama me busca. siempre encuentra.",
            "xokram": "Shantak rápido, mar lento, túnel peligroso. la Dama persigue",
            "daraziel": "Tres rutas con distintos riesgos. La Dama persigue. Shantak es la más rápida.",
        },
        paths=[
            P("Ir al Shantak (ventana arriba)", "act2_isla_ventana_mar", style="success", effects={"voluntad": 3}),
            P("Ir al muelle (mar)", "act2_isla_muelle", style="info", effects={"lucidez": 2}),
            P("Ir al túnel del sótano", "act2_isla_tunel_sotano", style="warning", effects={"lore": 3, "lucidez": -3}),
        ],
    ))

    nodes.append(N(
        "act2_isla_cara_a_cara_dama",
        act=A, zone="Isla de Papu — Cara a Cara",
        tone="horror",
        text=(
            "La enfrentas. El aire entre ustedes se espesa — huele a incienso"
            "quemado y a algo mineral, antiguo. La Dama de Porcelana se queda"
            "quieta. La máscara se agrieta — una línea fina que baja desde la"
            "frente con un sonido diminuto, como uña contra cristal. Detrás no"
            "hay cara. Hay más máscaras. Infinitas. Capas y capas de porcelana"
            "blanca, cada una con agujeros vacíos donde deberían estar los"
            "ojos.  Sientes el estómago contraerse. Náusea pura.  — *Soñador."
            "Nadie me enfrenta. Nadie.* — La voz viene de todas partes — del"
            "techo, del suelo, de dentro de tu propio cráneo. — *Si quieres"
            "irte, te dejo. Pero me debes. Y cobro.*  Te tiende una mano que"
            "no es una mano. Los dedos son demasiado largos, demasiado"
            "articulados, y el guante blanco se mueve como si debajo hubiera"
            "más dedos de los que deberían caber. El aire alrededor de su"
            "palma extendida vibra con un calor que no debería existir en este"
            "lugar frío.  Piensas: si la toco, no vuelvo. Lo sabes como sabes"
            "que estás soñando."
        ),
        on_enter={"lore": 12, "corrupcion": 8, "lucidez": -8, "memoria": -5},
        set_flags=["nyar_te_reconoce"],
        character_dialogue={
            "aris": "la máscara se agrieta. más máscaras debajo. infinitas. me ofrece un trato",
            "law": "la máscara se AGRIETA y hay MÁS MÁSCARAS debajo INFINITAS y me ofrece un trato",
            "haru": "máscaras infinitas debajo, no tiene cara, me ofrece un trato",
            "elyko": "máscara agrietada. más máscaras. infinitas. ofrece trato: libertad por deuda.",
            "xoft": "máscaras infinitas. no tiene cara. me ofrece un trato. mano.",
            "xokram": "Máscaras infinitas. me ofrece libertad por deuda. mal trato",
            "daraziel": "Máscaras infinitas. Sin cara. Ofrece trato. Libertad por deuda.",
        },
        paths=[
            P("Aceptar su mano (deuda con Nyarlathotep)", "act2_isla_escape", style="danger", effects={"corrupcion": 15, "favor": -15, "lucidez": -5}, set_flags=["acepto_mano_nyar", "nyarlathotep_te_debe_favor_oscuro"]),
            P("Rechazar y correr", "act2_isla_escape", style="success", effects={"voluntad": 12, "favor": 8, "corrupcion": -5}, conditions={"voluntad_min": 50}, set_flags=["rechazo_mano_nyar"]),
            P("Quedarte callado y retroceder", "act2_isla_pasillo_caos", style="secondary", effects={"memoria": -4, "lucidez": -3}),
        ],
    ))

    return nodes