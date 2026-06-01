"""
Kadath Acto 5 — Endings 1-4
Nodos de ending con buildup y text_variants.
"""


def build_act5_endings_1_4(N, P) -> list:
    nodes = []

    # =========================================================================
    # ENDING 1: El Trono del Caos Reptante
    # =========================================================================

    # Buildup 1 - Aproximación
    nodes.append(N('act5_trono_approach_1',
        act=5,
        zone='trono_caos',
        text=(
            'El suelo bajo tus pies deja de ser suelo. Es carne. Es piedra viva que late '
            'con un ritmo que reconoces — es TU pulso. Cada paso que diste desde el inicio '
            'del viaje resuena aquí, amplificado, devuelto como un eco que siempre estuvo '
            'esperándote. Las paredes del corredor final están hechas de tus decisiones '
            'cristalizadas. Puedes ver cada encrucijada, cada elección, brillando como '
            'vértebras en una columna infinita.'
        ),
        on_enter={'set_flag': 'approaching_throne'},
        paths=[P('Avanzar hacia el latido', 'act5_trono_approach_2')]
    ))

    # Buildup 2
    nodes.append(N('act5_trono_approach_2',
        act=5,
        zone='trono_caos',
        text=(
            'Nyarlathotep está aquí. No como lo viste antes — no como el hombre de mil '
            'máscaras, no como la sombra sonriente. Está aquí como GEOMETRÍA. Como la '
            'forma que adopta el universo cuando nadie lo observa. Y en el centro de esa '
            'geometría hay un trono. No. No es un trono. Es una AUSENCIA con forma de '
            'trono. Un hueco en la realidad que tiene exactamente tu forma.\n\n'
            '"¿Lo ves?" dice una voz que es todas las voces. "Siempre fue tuyo."\n\n'
            'Walre grita "FUCK" desde algún lugar lejano. El sonido se distorsiona, '
            'se estira, se convierte en parte de la arquitectura del lugar.'
        ),
        on_enter={'set_flag': 'throne_revealed'},
        paths=[P('Sentarte en el trono', 'act5_ending_trono')]
    ))

    # ENDING NODE
    nodes.append(N('act5_ending_trono',
        act=5,
        zone='trono_caos',
        text=(
            'Te sientas. Y el universo EXHALA.\n\n'
            'No hay dolor. No hay transformación. No hay momento dramático de cambio. '
            'Simplemente... encajas. Como una llave en una cerradura que llevaba eones '
            'esperando. TÚ eres el trono. Tu viaje fue el ritual. Cada paso, cada '
            'decisión, cada momento de duda — todo fue parte del diseño.\n\n'
            'Nyarlathotep te usó desde el principio. Desde antes del principio. Desde '
            'antes de que supieras que estabas soñando.\n\n'
            'El Caos Reptante tiene un nuevo asiento. Y ese asiento eres tú.\n\n'
            'Walre sigue gritando "FUCK" en algún lugar que ya no existe del todo. '
            'Su voz se pliega con la realidad, se convierte en estática, en ruido '
            'blanco, en el sonido de fondo del nuevo orden.\n\n'
            'Reinas. No porque lo eligieras. Porque fuiste DISEÑADO para esto.'
        ),
        on_enter={'set_flag': 'ending_trono_caos', 'add_stat': {'endings_achieved': 1}},
        is_ending=True,
        text_variants=[
            {
                'conditions': {'has_flag': 'trato_con_nyar'},
                'text_append': (
                    '\n\nAceptaste esto. Lo sabías. En el fondo siempre lo supiste. '
                    'El trato que hiciste no fue un trato — fue un RECONOCIMIENTO. '
                    'Firmaste tu propia coronación sin saberlo. O sabiéndolo. Ya no '
                    'importa la diferencia. El trono acepta tu peso con la familiaridad '
                    'de algo que siempre te perteneció.'
                )
            },
            {
                'conditions': {'has_flag': 'desafio_nyar'},
                'text_append': (
                    '\n\nGanaste el desafío. El premio era ESTO. Felicidades. '
                    '¿Creíste que vencer a un dios no tendría consecuencias? ¿Que '
                    'demostrar ser más listo que el Caos Reptante no te convertiría '
                    'en parte de él? Cada victoria fue un eslabón. Cada triunfo, un '
                    'paso más hacia este trono que ahora es tu cárcel y tu corona.'
                )
            },
            {
                'conditions': {'has_flag': 'nyarlathotep_te_aprueba'},
                'text_append': (
                    '\n\n"Siempre supe que serías perfecto para el trono," dice '
                    'Nyarlathotep, y su voz suena como un padre orgulloso. Como un '
                    'escultor admirando su obra terminada. Te moldeó con paciencia '
                    'infinita. Cada prueba fue un cincelazo. Y ahora, por fin, la '
                    'escultura está completa.'
                )
            },
            {
                'conditions': {'has_flag': 'ruta_dama_activa'},
                'text_append': (
                    '\n\nZuto te preparó. El sello era la llave. Bienvenido a casa. '
                    'La Dama del Sello no era tu protectora — era tu PREPARADORA. '
                    'Cada glifo que grabó en tu alma era una instrucción de montaje. '
                    'Ahora todas las piezas encajan y el sello brilla con luz propia, '
                    'fundiéndose con el trono hasta que no puedes distinguir dónde '
                    'terminas tú y dónde empieza el Caos.'
                )
            }
        ]
    ))

    # =========================================================================
    # ENDING 2: Despertar Puro
    # =========================================================================

    # Buildup 1
    nodes.append(N('act5_despertar_approach_1',
        act=5,
        zone='despertar',
        text=(
            'Algo se agrieta. No el mundo — tu PERCEPCIÓN del mundo. Como cuando '
            'estás en un sueño y de pronto notas que las proporciones están mal. '
            'Que las puertas no llevan a ningún lado. Que la gente repite frases. '
            'Kadath tiembla a tu alrededor y por primera vez ves las COSTURAS. '
            'Los bordes donde la realidad onírica fue pegada con descuido.'
        ),
        on_enter={'set_flag': 'lucidity_rising'},
        paths=[P('Tirar del hilo', 'act5_despertar_approach_2')]
    ))

    # Buildup 2
    nodes.append(N('act5_despertar_approach_2',
        act=5,
        zone='despertar',
        text=(
            'El mundo se pela como pintura vieja. Debajo no hay nada — solo la '
            'sensación de sábanas, de un colchón, de un cuerpo que lleva demasiado '
            'tiempo inmóvil. Tus manos oníricas se vuelven transparentes. Kadath '
            'grita. Las Tierras del Sueño no quieren dejarte ir.\n\n'
            'Cisart aparece en el borde de tu visión, fumando algo que no debería '
            'existir en ningún plano. "Si estamos si," dice, exhalando humo que '
            'tiene forma de signos de interrogación. No ayuda en absoluto.'
        ),
        on_enter={'set_flag': 'waking_imminent'},
        paths=[P('Abrir los ojos', 'act5_ending_despertar')]
    ))

    # ENDING NODE
    nodes.append(N('act5_ending_despertar',
        act=5,
        zone='despertar',
        text=(
            'Despiertas.\n\n'
            'Es tan simple y tan devastador como eso. Un momento estás en Kadath, '
            'en las Tierras del Sueño, en un mundo de imposibilidades y maravillas '
            'terribles. Al siguiente estás en una cama. Tu cama. Con el techo de '
            'siempre mirándote desde arriba.\n\n'
            'Recuerdas que sueñas. Recuerdas TODO. Durante exactamente once segundos '
            'recuerdas cada detalle con claridad perfecta — los ghouls, las torres, '
            'los dioses, las escaleras que no terminan. Y luego se va. Como agua '
            'entre los dedos. Como humo.\n\n'
            'Intentas volver a dormir esa noche. Y la siguiente. Y la siguiente.\n\n'
            'Nunca vuelves a soñar. Nunca. El precio del despertar es el sueño mismo. '
            'Kadath te dejó ir, pero se llevó la puerta consigo.\n\n'
            'Cisart sigue en algún lugar de tu memoria, fumando, diciendo cosas que '
            'no significan nada. O que significan todo. Ya no puedes verificarlo.'
        ),
        on_enter={'set_flag': 'ending_despertar_puro', 'add_stat': {'endings_achieved': 1}},
        is_ending=True,
        text_variants=[
            {
                'conditions': {'has_flag': 'digno_de_kadath'},
                'text_append': (
                    '\n\nDespiertas con un fragmento de belleza que se desvanece en '
                    'segundos. Un color que no existe en el mundo despierto. Una nota '
                    'musical que ningún instrumento puede producir. Lo sientes en el '
                    'pecho durante once latidos y luego se va para siempre. Kadath te '
                    'dio un regalo de despedida. El último. El único que podía cruzar '
                    'la frontera. Y ni siquiera eso sobrevive.'
                )
            },
            {
                'conditions': {'has_flag': 'trauma_edyssey'},
                'text_append': (
                    '\n\nDespiertas gritando. "847 días... 847 DÍAS..." Las palabras '
                    'salen de tu boca antes de que puedas controlarlas. Tu voz suena '
                    'rota, oxidada, como si no la hubieras usado en años. Nadie te '
                    'cree. Nadie te va a creer nunca. ¿Cómo explicas 847 días en un '
                    'lugar que no existe? ¿Cómo explicas las cicatrices que no están '
                    'en tu cuerpo pero sí en tu alma?'
                )
            },
            {
                'conditions': {'stat_less_than': {'memoria': 10}},
                'text_append': (
                    '\n\nDespiertas sin recordar tu nombre. Sin recordar NADA. El '
                    'sueño se llevó más de lo que trajo. Miras tus manos y no las '
                    'reconoces. Miras el techo y no sabes dónde estás. Alguien '
                    'vendrá. Alguien te dirá quién eres. Pero tú sabrás, en algún '
                    'lugar profundo y roto, que esa persona que te describan no eres '
                    'tú. Tú te quedaste en Kadath. Lo que despertó es solo el envase.'
                )
            },
            {
                'conditions': {'has_flag': 'edyssey_aliado'},
                'text_append': (
                    '\n\nEdyssey despierta contigo. Lo sabes porque sientes el eco — '
                    'otro par de ojos abriéndose en algún lugar del mundo. Otro '
                    'cuerpo recordando que tiene peso. Se encontrarán algún día, '
                    'quizás. En un café, en una calle, en un hospital. Se mirarán. '
                    'Y no se reconocerán. Dos extraños con el mismo agujero en el '
                    'pecho donde solía estar Kadath.'
                )
            }
        ]
    ))

    # =========================================================================
    # ENDING 3: Legado Onírico
    # =========================================================================

    # Buildup 1
    nodes.append(N('act5_legado_approach_1',
        act=5,
        zone='legado_onirico',
        text=(
            'Tu cuerpo se vuelve translúcido. No es una metáfora — puedes ver a '
            'través de tus propias manos. El paisaje de Kadath brilla a través de '
            'tu carne como luz a través de un vitral. Estás dejando de ser una '
            'persona y empezando a ser un LUGAR. Una parte del terreno. Un accidente '
            'geográfico del mundo onírico.'
        ),
        on_enter={'set_flag': 'dissolving_begins'},
        paths=[P('Dejarte ir', 'act5_legado_approach_2')]
    ))

    # Buildup 2
    nodes.append(N('act5_legado_approach_2',
        act=5,
        zone='legado_onirico',
        text=(
            'Tus pies se funden con la escalera que pisas. Tus dedos se ramifican '
            'en glifos que se inscriben solos en las paredes. Tu voz se convierte '
            'en el eco que otros soñadores escucharán dentro de mil años.\n\n'
            'Meltbrine está aquí. Observando. Con esa libreta que siempre lleva. '
            'Toma notas con una caligrafía precisa y desapasionada. No interviene. '
            'No intenta salvarte. Solo DOCUMENTA.'
        ),
        on_enter={'set_flag': 'becoming_landscape'},
        paths=[P('Completar la disolución', 'act5_ending_legado')]
    ))

    # ENDING NODE
    nodes.append(N('act5_ending_legado',
        act=5,
        zone='legado_onirico',
        text=(
            'Te disuelves en el paisaje. Y es hermoso.\n\n'
            'No mueres. No desapareces. Te TRANSFORMAS. Eres una escalera que '
            'conecta dos niveles del sueño que antes no se tocaban. Eres un glifo '
            'en una pared que futuros soñadores descifrarán sin saber que fue una '
            'persona. Eres un eco que resuena en las cámaras vacías de Kadath, '
            'repitiendo fragmentos de conversaciones que tuviste.\n\n'
            'Tu consciencia no se apaga. Se EXPANDE. Se diluye hasta ser tan fina '
            'que cubre todo el paisaje onírico como una capa de rocío. Estás en '
            'todas partes y en ninguna. Eres todo y nada.\n\n'
            'Meltbrine cierra su libreta. Escribe una última nota en la portada: '
            '"Sujeto integrado. Proceso completo. Irreversible." Se va sin mirar '
            'atrás. Tiene otros sujetos que observar.\n\n'
            'Eres el legado. Eres Kadath. Kadath eres tú.'
        ),
        on_enter={'set_flag': 'ending_legado_onirico', 'add_stat': {'endings_achieved': 1}},
        is_ending=True,
        text_variants=[
            {
                'conditions': {'has_flag': 'edyssey_aliado'},
                'text_append': (
                    '\n\nEdyssey se queda contigo. No tenía que hacerlo — podía irse, '
                    'despertar, elegir otro camino. Pero se queda. Se disuelve a tu '
                    'lado. Dos ecos donde antes había uno. Dos escaleras entrelazadas. '
                    'Dos glifos que juntos forman una palabra que ningún idioma humano '
                    'puede pronunciar pero que significa algo parecido a "compañía". '
                    'No están solos. Nunca estarán solos. Eso es algo.'
                )
            },
            {
                'conditions': {'has_flag': 'sabe_verdad_kadath'},
                'text_append': (
                    '\n\nSabes lo que te pasa. Eso lo hace peor. Infinitamente peor. '
                    'Porque no es un proceso misterioso ni una transformación mágica — '
                    'es DIGESTIÓN. Kadath te está digiriendo. Absorbiendo. Y tú lo '
                    'sabes con la claridad horrible de quien ve venir el tren y no '
                    'puede moverse de las vías. Cada segundo de la disolución es '
                    'consciente. Cada átomo que pierdes lo sientes irse.'
                )
            },
            {
                'conditions': {'stat_greater_than': {'memoria': 40}},
                'text_append': (
                    '\n\nRecuerdas todo mientras te disuelves. Cada recuerdo duele. '
                    'No como un dolor físico — como la nostalgia multiplicada por mil. '
                    'Recuerdas tu primer día. Tu nombre. Las caras de personas que '
                    'amaste. El sabor del café. La sensación de la lluvia. Y cada uno '
                    'de esos recuerdos se convierte en parte del paisaje. Tu primer '
                    'beso es ahora una fuente. Tu infancia es un jardín. Tu dolor es '
                    'una grieta en una pared. Todo lo que fuiste, preservado para '
                    'siempre en un lugar al que nadie que te conoció podrá llegar.'
                )
            }
        ]
    ))

    # =========================================================================
    # ENDING 4: Rey de los Ghouls
    # =========================================================================

    # Buildup 1
    nodes.append(N('act5_ghouls_approach_1',
        act=5,
        zone='reino_ghoul',
        text=(
            'Los huesos crujen. Los TUYOS. No de dolor — de CAMBIO. Tu mandíbula '
            'se alarga. Tus uñas se endurecen y oscurecen. La piel de tus manos '
            'se vuelve correosa, gris, resistente. Los ghouls a tu alrededor te '
            'observan con algo que podría ser reverencia. O hambre. Con los ghouls '
            'nunca se sabe. Quizás es lo mismo.'
        ),
        on_enter={'set_flag': 'ghoul_transformation_starting'},
        paths=[P('Aceptar el cambio', 'act5_ghouls_approach_2')]
    ))

    # Buildup 2
    nodes.append(N('act5_ghouls_approach_2',
        act=5,
        zone='reino_ghoul',
        text=(
            'El olor. Dios, el OLOR. Lo que antes te daba náuseas ahora huele a... '
            '¿hogar? Los túneles de hueso y tierra compactada se sienten cómodos. '
            'Correctos. El ghoul más viejo — el que llaman el Rey Anterior — te '
            'mira con sus ojos sin párpados y asiente lentamente.\n\n'
            'Gab está aquí. En una esquina. Llorando. "Yo quería salvarte," dice '
            'entre sollozos. "Yo quería... yo pensé que podía..." No pudo. Nadie '
            'podía. Esto no es algo de lo que se salva a alguien.'
        ),
        on_enter={'set_flag': 'ghoul_transformation_advanced'},
        paths=[P('Completar la transformación', 'act5_ending_ghouls')]
    ))

    # ENDING NODE
    nodes.append(N('act5_ending_ghouls',
        act=5,
        zone='reino_ghoul',
        text=(
            'La transformación se completa. Ya no eres humano.\n\n'
            'No es una tragedia. No es un triunfo. Es simplemente lo que eres ahora. '
            'Tu cuerpo es fuerte, resistente, hecho para los túneles y la oscuridad. '
            'Tus sentidos son diferentes — ves en la penumbra como otros ven al '
            'mediodía. Hueles la muerte a kilómetros. Y la muerte huele BIEN.\n\n'
            'Comes lo que ellos comen. No te da asco. No te da nada. Es comida. '
            'Es sustento. Es lo que tu cuerpo necesita ahora.\n\n'
            'El Rey Anterior se inclina. Los demás ghouls golpean el suelo con sus '
            'garras en un ritmo que significa coronación. Eres el nuevo Rey. El más '
            'fuerte. El que recuerda haber sido humano y eligió esto de todas formas.\n\n'
            'Gab sigue llorando en su esquina. Se irá eventualmente. Todos se van. '
            'Pero los ghouls se quedan. Los ghouls son para siempre.'
        ),
        on_enter={'set_flag': 'ending_rey_ghouls', 'add_stat': {'endings_achieved': 1}},
        is_ending=True,
        text_variants=[
            {
                'conditions': {'has_flag': 'pacto_ghoul', 'has_flag_2': 'comio_con_ghouls'},
                'text_append': (
                    '\n\nTransformación voluntaria y completa. No hay ni un gramo de '
                    'resistencia en tu cuerpo. Hiciste el pacto con los ojos abiertos. '
                    'Comiste con ellos sabiendo lo que comías. Cada bocado fue una '
                    'elección. Cada elección te trajo aquí. No eres una víctima — eres '
                    'un CONVERSO. Y los conversos siempre son los más devotos. Tu '
                    'transformación es perfecta, sin las imperfecciones que deja la '
                    'resistencia. Eres el ghoul más puro que ha existido.'
                )
            },
            {
                'conditions': {'has_flag': 'ccn_aliado'},
                'text_append': (
                    '\n\nCCN emerge de las sombras. También cambió — pero menos. '
                    'Conserva algo de su sonrisa humana, algo de ese brillo en los '
                    'ojos que dice "esto es una locura pero aquí estamos". Se '
                    'arrodilla con una teatralidad que no ha perdido. "Wey," dice, '
                    'y su voz suena como grava arrastrándose, "bienvenido al club. '
                    'Yo soy tu segundo al mando. ¿Primer decreto del rey?" Se ríe. '
                    'Suena horrible. Suena perfecto.'
                )
            },
            {
                'conditions': {'has_flag': 'comio_todo_ghoul'},
                'text_append': (
                    '\n\nEres el ghoul más poderoso que ha existido. No por magia, '
                    'no por destino — por APETITO. Comiste todo lo que te pusieron '
                    'enfrente. Cada cosa prohibida, cada tabú, cada línea que otros '
                    'no cruzarían. Y cada bocado te hizo más fuerte. El Rey Anterior '
                    'no solo se inclina — se POSTRA. Reconoce en ti algo que él '
                    'nunca tuvo: hambre sin límite. Voluntad sin freno. Eres lo que '
                    'los ghouls siempre quisieron ser.'
                )
            }
        ]
    ))

    return nodes
