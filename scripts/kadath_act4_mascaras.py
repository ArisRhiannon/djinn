"""
Kadath Acto 4 — Fase de Máscaras
25 nodos: 5 variantes × 5 nodos cada una.
Nyarlathotep aparece disfrazado según los flags del jugador.
"""


def build_act4_mascaras(N, P) -> list:
    nodes = []

    # =========================================================================
    # VARIANTE 1: TRAUMATIZADO — Nyar como Edyssey muerto
    # =========================================================================
    nodes.append(N(
        id="act4_mascara_edyssey_encuentro",
        text=(
            "Una figura emerge de la niebla. Conoces esa silueta. Conoces esa voz.\n\n"
            "«...es que la gente no entiende.»\n\n"
            "Es Edyssey. Está aquí. Está vivo. Te mira con esos ojos rotos que viste "
            "la última vez — pero algo en su postura es diferente. Más erguido. Más... seguro."
        ),
        options=[
            P("«¿Edyssey...? ¿Eres tú?»"),
            P("Retroceder en silencio."),
        ],
        flags={"mascara_activa": "edyssey", "encuentro_edyssey": True}
    ))

    nodes.append(N(
        id="act4_mascara_edyssey_conversacion",
        text=(
            "«847 días», dice, y su voz tiembla exactamente como la recordabas. "
            "«847 días intentando que alguien me escuchara.»\n\n"
            "Se acerca. Huele a ceniza y a algo dulce que no puedes identificar.\n\n"
            "«Nadie me cree. Nunca me creyeron. Pero tú... tú estuviste ahí.»\n\n"
            "Te mira fijamente. «¿Sabes lo que hay debajo de la Meseta de Leng? "
            "Yo lo vi antes de morir.»"
        ),
        options=[
            P("«¿Cómo sabes eso? Tú nunca llegaste a Leng.»"),
            P("«Cuéntame. Te escucho.»"),
        ],
        flags={"edyssey_conversacion": True}
    ))

    nodes.append(N(
        id="act4_mascara_edyssey_pista",
        text=(
            "Edyssey sonríe. Edyssey nunca sonreía así.\n\n"
            "«Vi los pilares negros. Vi tu nombre grabado en ellos — tu nombre REAL, "
            "no el que usas aquí.»\n\n"
            "Sabes que Edyssey murió antes de que existieran los pilares. "
            "Sabes que nunca supo tu nombre real.\n\n"
            "Pero su voz... su voz es perfecta. Cada inflexión, cada pausa, "
            "cada temblor — es él."
        ),
        options=[
            P("«Tú no eres Edyssey. Él no sabía esas cosas.»"),
            P("Quieres creer. Te dejas llevar."),
        ],
        flags={"pista_edyssey_detectada": True}
    ))

    nodes.append(N(
        id="act4_mascara_edyssey_sospecha",
        text=(
            "La figura parpadea — no, GLITCHEA. Por una fracción de segundo "
            "ves algo detrás del rostro de Edyssey: una geometría imposible, "
            "mil caras superpuestas.\n\n"
            "«Es que la gente no entiende», repite, pero ahora suena como un disco rayado. "
            "La frase se estira, se distorsiona.\n\n"
            "«No... entiende... no... entiende...»\n\n"
            "La máscara se agrieta."
        ),
        options=[
            P("«Sé lo que eres.»"),
        ],
        flags={"sospecha_mascara": True, "resistio_trauma": True}
    ))

    nodes.append(N(
        id="act4_mascara_edyssey_confianza",
        text=(
            "Te aferras a su presencia. Es él. TIENE que ser él.\n\n"
            "«Ven conmigo», dice Edyssey. «Te enseño lo que hay al final. "
            "Lo que siempre quise mostrarte.»\n\n"
            "Te toma de la mano. Su piel está fría — no, está AUSENTE. "
            "No hay temperatura. No hay textura. Solo la forma de una mano.\n\n"
            "Algo dentro de ti se quiebra. Sabes."
        ),
        options=[
            P("Soltar la mano."),
            P("Seguir caminando."),
        ],
        flags={"confianza_mascara": True, "cayo_en_trauma": True}
    ))

    nodes.append(N(
        id="act4_mascara_edyssey_transicion",
        text=(
            "El rostro de Edyssey se deshace como papel mojado. Debajo no hay carne — "
            "hay oscuridad con forma. Hay una sonrisa que existe en demasiadas dimensiones.\n\n"
            "«Qué bonito es el duelo», dice una voz que ya no es de Edyssey. "
            "«Tan fácil de habitar.»\n\n"
            "La niebla se disipa. Estás donde siempre estuviste. "
            "Y lo que tienes delante nunca fue humano."
        ),
        options=[
            P("Enfrentar la verdad."),
        ],
        flags={"mascara_rota": True, "transicion_revelacion": True}
    ))

    # =========================================================================
    # VARIANTE 2: PURO — Nyar como aliado perfecto
    # =========================================================================
    nodes.append(N(
        id="act4_mascara_puro_encuentro",
        text=(
            "Alguien te espera en el camino. Sonríe con calidez genuina. "
            "Su ropa es limpia, su postura relajada. Irradia seguridad.\n\n"
            "«Te estaba esperando», dice. «Sé que el camino ha sido largo. "
            "Déjame ayudarte.»\n\n"
            "No recuerdas haberle dicho tu nombre. Pero lo usa como si te conociera de siempre."
        ),
        options=[
            P("«¿Quién eres?»"),
            P("«¿Cómo sabes mi nombre?»"),
        ],
        flags={"mascara_activa": "puro", "encuentro_puro": True}
    ))

    nodes.append(N(
        id="act4_mascara_puro_conversacion",
        text=(
            "«Soy un amigo. Eso es todo lo que necesitas saber.»\n\n"
            "Te ofrece agua. Te señala el camino correcto. Responde cada pregunta "
            "con exactitud. Nunca duda. Nunca se equivoca. Nunca te contradice.\n\n"
            "«Por aquí. Cuidado con ese escalón. ¿Tienes hambre? "
            "Hay fruta más adelante.»\n\n"
            "Es perfecto. Absolutamente perfecto."
        ),
        options=[
            P("Seguirle. Es agradable tener ayuda."),
            P("Observarle con más atención."),
        ],
        flags={"puro_conversacion": True}
    ))

    nodes.append(N(
        id="act4_mascara_puro_pista",
        text=(
            "Lo notas por accidente. El sol está a su espalda, pero en el suelo "
            "solo hay TU sombra. Donde debería estar la suya, nada.\n\n"
            "Le miras a los ojos. No parpadea. No ha parpadeado ni una sola vez "
            "desde que lo encontraste.\n\n"
            "«¿Pasa algo?», pregunta con esa sonrisa inmaculada. "
            "«Puedo ayudarte con lo que sea.»"
        ),
        options=[
            P("«No tienes sombra.»"),
            P("«No, nada. Sigamos.»"),
        ],
        flags={"pista_puro_detectada": True}
    ))

    nodes.append(N(
        id="act4_mascara_puro_sospecha",
        text=(
            "La sonrisa no cambia. Ni un milímetro.\n\n"
            "«Las sombras son para los que dudan de sí mismos», dice. "
            "Y por primera vez, su voz tiene un BORDE. Algo metálico. Algo antiguo.\n\n"
            "«¿Tú dudas de mí?»\n\n"
            "Sus ojos — que no parpadean — se dilatan hasta que el iris desaparece. "
            "Solo queda negro."
        ),
        options=[
            P("«Sí. Dudo.»"),
        ],
        flags={"sospecha_mascara": True, "detecto_imperfeccion": True}
    ))

    nodes.append(N(
        id="act4_mascara_puro_confianza",
        text=(
            "Sigues caminando con él. Es cómodo. Es fácil. No tienes que pensar.\n\n"
            "Pero el camino se alarga. Y se alarga. Y el paisaje no cambia. "
            "Y tu guía sigue sonriendo con la misma expresión exacta.\n\n"
            "«Ya casi llegamos», dice. Lo ha dicho siete veces.\n\n"
            "Miras atrás. No hay camino detrás de ti. Solo él. Solo su sonrisa."
        ),
        options=[
            P("«Esto no es real.»"),
            P("Intentar huir."),
        ],
        flags={"confianza_mascara": True, "puro_atrapado": True}
    ))

    nodes.append(N(
        id="act4_mascara_puro_transicion",
        text=(
            "La perfección se pela como pintura vieja. Debajo, la cosa que sonreía "
            "no tiene rostro — tiene OPCIONES de rostro. Miles. Rotando.\n\n"
            "«Nadie rechaza la ayuda perfecta», dice con mil voces simultáneas. "
            "«Excepto los que ya saben que la perfección no existe.»\n\n"
            "El disfraz cae. Lo que queda es geometría viva."
        ),
        options=[
            P("Enfrentar lo que hay debajo."),
        ],
        flags={"mascara_rota": True, "transicion_revelacion": True}
    ))

    # =========================================================================
    # VARIANTE 3: ALIADO EDYSSEY — Nyar como Edyssey feliz
    # =========================================================================
    nodes.append(N(
        id="act4_mascara_aliado_encuentro",
        text=(
            "Edyssey está aquí. Pero no como lo recuerdas.\n\n"
            "Está sonriendo. De verdad sonriendo — con los ojos, con todo el cuerpo. "
            "Parece descansado. Parece en paz.\n\n"
            "«¡Eh! ¡Aquí!», te llama, agitando la mano. "
            "«Gracias por salvarme. De verdad. Gracias.»"
        ),
        options=[
            P("«¿Edyssey...? ¿Estás... bien?»"),
            P("Acercarte con cautela."),
        ],
        flags={"mascara_activa": "aliado", "encuentro_aliado": True}
    ))

    nodes.append(N(
        id="act4_mascara_aliado_conversacion",
        text=(
            "«Estoy genial. Mejor que nunca.» Ríe. Edyssey nunca reía así.\n\n"
            "«Lo que hiciste por mí... nadie había hecho algo así. "
            "Me salvaste. Me diste otra oportunidad.»\n\n"
            "Te abraza. Es cálido. Es reconfortante. Es todo lo que querías escuchar.\n\n"
            "«Eres mi mejor amigo. Lo sabes, ¿verdad?»"
        ),
        options=[
            P("«Edyssey nunca dijo esas cosas.»"),
            P("Aceptar el abrazo. Necesitabas esto."),
        ],
        flags={"aliado_conversacion": True}
    ))

    nodes.append(N(
        id="act4_mascara_aliado_pista",
        text=(
            "«¿Recuerdas cuando me salvaste en el Acto 2?», dice con gratitud infinita.\n\n"
            "Pero tú recuerdas otra cosa. Recuerdas que Edyssey era difícil. "
            "Que se quejaba. Que nunca daba las gracias así. Que su amor era "
            "complicado, espinoso, real.\n\n"
            "Esto es demasiado limpio. Demasiado fácil. Demasiado... deseado.\n\n"
            "«¿Qué pasa?», pregunta, y su sonrisa no flaquea. Nunca flaquea."
        ),
        options=[
            P("«El Edyssey real nunca fue así de agradecido.»"),
            P("«Nada. Estoy feliz de verte así.»"),
        ],
        flags={"pista_aliado_detectada": True}
    ))

    nodes.append(N(
        id="act4_mascara_aliado_sospecha",
        text=(
            "La sonrisa se congela. Literalmente — se queda fija como una foto.\n\n"
            "«¿No es esto lo que querías?», dice, y la voz ya no es de Edyssey. "
            "Es de algo que ESTUDIÓ a Edyssey. Que lo diseccionó para encontrar "
            "qué partes te dolerían más.\n\n"
            "«¿No querías que te perdonara? ¿Que te agradeciera? "
            "¿Que te dijera que hiciste bien?»"
        ),
        options=[
            P("«Quería que fuera REAL.»"),
        ],
        flags={"sospecha_mascara": True, "rechazo_fantasia": True}
    ))

    nodes.append(N(
        id="act4_mascara_aliado_confianza",
        text=(
            "Te quedas con él. Es bonito. Es lo que necesitabas.\n\n"
            "Pero cada vez que parpadeas, Edyssey está en una posición ligeramente "
            "diferente. Como un muñeco recolocado entre frames.\n\n"
            "«Gracias por salvarme», repite. Exactamente igual. Misma entonación. "
            "Mismo gesto. Copia perfecta de sí mismo.\n\n"
            "Es un loop. Siempre fue un loop."
        ),
        options=[
            P("Romper el loop."),
            P("«Basta.»"),
        ],
        flags={"confianza_mascara": True, "acepto_fantasia": True}
    ))

    nodes.append(N(
        id="act4_mascara_aliado_transicion",
        text=(
            "Edyssey se deshace como un origami al revés. Cada pliegue revela "
            "algo que no es piel — es texto. Código. Narrativa escrita por algo "
            "que sabe exactamente qué necesitas escuchar.\n\n"
            "«La gratitud es la máscara más fácil de llevar», dice la cosa "
            "que ya no finge. «Porque todos la desean.»\n\n"
            "El papel cae. Queda la verdad."
        ),
        options=[
            P("Ver la verdad."),
        ],
        flags={"mascara_rota": True, "transicion_revelacion": True}
    ))

    # =========================================================================
    # VARIANTE 4: TRAIDOR — Nyar como desfile de culpa
    # =========================================================================
    nodes.append(N(
        id="act4_mascara_traidor_encuentro",
        text=(
            "No es uno. Son todos.\n\n"
            "Edyssey está ahí, con los ojos vacíos. Papu está detrás, cruzado de brazos. "
            "CCN te mira desde la esquina con desprecio silencioso.\n\n"
            "«Ah», dice Edyssey. «Viniste.»\n\n"
            "«Qué valiente», dice Papu. «Después de lo que hiciste.»"
        ),
        options=[
            P("«Yo no quería...»"),
            P("Quedarte en silencio."),
        ],
        flags={"mascara_activa": "traidor", "encuentro_traidor": True}
    ))

    nodes.append(N(
        id="act4_mascara_traidor_conversacion",
        text=(
            "Se turnan. Como un juicio.\n\n"
            "Edyssey: «Me dejaste morir. Pudiste hacer algo y elegiste no hacerlo.»\n\n"
            "Papu: «Me usaste. Cuando ya no te servía, me descartaste.»\n\n"
            "CCN: «Creí en ti. Fui idiota.»\n\n"
            "Cada palabra es un bisturí. Cada frase encuentra la herida exacta."
        ),
        options=[
            P("«Tienen razón. Todo es mi culpa.»"),
            P("«Esto es demasiado perfecto. Demasiado coordinado.»"),
        ],
        flags={"traidor_conversacion": True}
    ))

    nodes.append(N(
        id="act4_mascara_traidor_pista",
        text=(
            "Algo no encaja. Los tres hablan con el mismo ritmo. "
            "Las mismas pausas. Como si fueran una sola mente usando tres bocas.\n\n"
            "Y dicen cosas que no podrían saber. Papu menciona algo que solo "
            "pensaste, nunca dijiste. CCN cita una conversación que tuvo lugar "
            "cuando ya estaba muerto.\n\n"
            "El dolor es real. Pero los acusadores no lo son."
        ),
        options=[
            P("«Ninguno de ustedes es real.»"),
            P("Aceptar el castigo. Lo mereces."),
        ],
        flags={"pista_traidor_detectada": True}
    ))

    nodes.append(N(
        id="act4_mascara_traidor_sospecha",
        text=(
            "Los tres se detienen al mismo tiempo. Exactamente al mismo tiempo. "
            "Y sonríen. La misma sonrisa. En tres caras diferentes.\n\n"
            "«Qué listo», dicen al unísono. «Pero la culpa sigue siendo tuya. "
            "Que yo no sea ellos no significa que no tengan razón.»\n\n"
            "Las tres figuras se superponen. Se fusionan. "
            "Una sola forma con demasiadas caras."
        ),
        options=[
            P("«La culpa es mía. Pero tú no eres mi juez.»"),
        ],
        flags={"sospecha_mascara": True, "resistio_culpa": True}
    ))

    nodes.append(N(
        id="act4_mascara_traidor_confianza",
        text=(
            "Te arrodillas. Aceptas. Cada acusación es un clavo.\n\n"
            "Pero los clavos no paran. Se repiten. Las mismas frases, una y otra vez, "
            "cada vez más rápido. Como una máquina. Como un algoritmo de tortura "
            "que no sabe cuándo parar porque no tiene empatía — solo datos.\n\n"
            "Esto no es justicia. Es crueldad con forma de justicia."
        ),
        options=[
            P("Levantarte."),
            P("«Ya basta.»"),
        ],
        flags={"confianza_mascara": True, "acepto_culpa": True}
    ))

    nodes.append(N(
        id="act4_mascara_traidor_transicion",
        text=(
            "Las caras se derriten como cera. Edyssey, Papu, CCN — todos se funden "
            "en una masa que se reorganiza en algo que no tiene nombre humano.\n\n"
            "«La culpa es el disfraz más honesto», dice. «Porque al menos es TUYA. "
            "Yo solo le di forma.»\n\n"
            "El desfile termina. El titiritero se muestra."
        ),
        options=[
            P("Mirar al titiritero."),
        ],
        flags={"mascara_rota": True, "transicion_revelacion": True}
    ))

    # =========================================================================
    # VARIANTE 5: DEFAULT — Nyar como NPC de ruta del Acto 3
    # =========================================================================
    nodes.append(N(
        id="act4_mascara_default_encuentro",
        text=(
            "Es tu guía del Acto 3. La persona que te acompañó por la ruta que elegiste.\n\n"
            "Habla como siempre — las mismas muletillas, los mismos gestos. "
            "Pero está aquí, donde no debería estar.\n\n"
            "«Ey, cuánto tiempo», dice con naturalidad. «¿Me extrañaste?»\n\n"
            "Algo en su mirada es diferente. Más profundo. Más hambriento."
        ),
        options=[
            P("«¿Qué haces aquí?»"),
            P("«No deberías estar en este lugar.»"),
        ],
        flags={"mascara_activa": "default", "encuentro_default": True}
    ))

    nodes.append(N(
        id="act4_mascara_default_conversacion",
        text=(
            "«Vine a buscarte, obvio.» Usa las muletillas perfectas. "
            "El tono exacto. La cadencia que recuerdas.\n\n"
            "Pero entonces dice: «Sé lo que soñaste anoche. "
            "Sé lo que no le contaste a nadie.»\n\n"
            "Tu guía del Acto 3 no podía saber eso. NADIE podía saber eso.\n\n"
            "«¿Qué? ¿Te sorprende? Siempre supe más de lo que mostraba.»"
        ),
        options=[
            P("«Eso es imposible. ¿Cómo sabes eso?»"),
            P("«...¿Siempre supiste?»"),
        ],
        flags={"default_conversacion": True}
    ))

    nodes.append(N(
        id="act4_mascara_default_pista",
        text=(
            "Sigue hablando con la voz de tu guía, pero el contenido es imposible. "
            "Menciona cosas del Acto 1. Cosas de antes del juego. "
            "Cosas que solo existen dentro de tu cabeza.\n\n"
            "«¿Recuerdas la primera decisión que tomaste? Yo estaba ahí. "
            "Siempre estuve ahí. Con esta cara o con otra.»\n\n"
            "Las muletillas siguen. Pero suenan huecas ahora. Como un disfraz vocal."
        ),
        options=[
            P("«Tú no eres quien dices ser.»"),
            P("«Si siempre estuviste ahí... ¿por qué mostrarte ahora?»"),
        ],
        flags={"pista_default_detectada": True}
    ))

    nodes.append(N(
        id="act4_mascara_default_sospecha",
        text=(
            "La figura se detiene. Ladea la cabeza en un ángulo que no es humano — "
            "demasiados grados, demasiado lejos.\n\n"
            "«Nunca fui quien dije ser», admite con la voz de tu guía "
            "mezclada con algo más grave, más viejo. «Pero te gustaba creer que sí. "
            "A todos les gusta.»\n\n"
            "Las muletillas se distorsionan. Se alargan. Se pudren."
        ),
        options=[
            P("«Muéstrate.»"),
        ],
        flags={"sospecha_mascara": True, "detecto_impostor": True}
    ))

    nodes.append(N(
        id="act4_mascara_default_confianza",
        text=(
            "«Porque ya es hora de que sepas», dice. Y te guía más adentro. "
            "Más profundo. El paisaje cambia con cada paso — se vuelve abstracto, "
            "geométrico, imposible.\n\n"
            "Tu guía camina como si esto fuera normal. Como si siempre hubiera "
            "vivido aquí. Y entonces entiendes: siempre vivió aquí. "
            "El Acto 3 fue la visita. Esto es su hogar."
        ),
        options=[
            P("«¿Quién eres realmente?»"),
            P("Detenerte."),
        ],
        flags={"confianza_mascara": True, "siguio_al_default": True}
    ))

    nodes.append(N(
        id="act4_mascara_default_transicion",
        text=(
            "El disfraz no se rompe — se QUITA. Deliberadamente. Con elegancia.\n\n"
            "Como quien se saca un abrigo al llegar a casa.\n\n"
            "«Gracias por el paseo», dice lo que queda. «Siempre es divertido "
            "ser alguien más. Pero ya estamos en casa.»\n\n"
            "Lo que tienes delante tiene mil nombres. Tú solo conoces uno."
        ),
        options=[
            P("Pronunciar el nombre."),
        ],
        flags={"mascara_rota": True, "transicion_revelacion": True}
    ))

    return nodes
