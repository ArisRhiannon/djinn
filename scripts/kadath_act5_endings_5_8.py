"""Kadath Acto 5 — Endings 5-8 (El Gran Negocio, El Canto Final, Biblioteca Eterna, Arquitectura Perfecta)."""
from __future__ import annotations
from typing import Any, Callable, Dict, List


def build_act5_endings_5_8(N: Callable, P: Callable) -> List[Dict[str, Any]]:
    A = 5
    nodes: List[Dict[str, Any]] = []

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 5 — EL GRAN NEGOCIO
    # ═══════════════════════════════════════════════════════════════════
    Z5 = "El Gran Negocio"

    nodes.append(N(
        "act5_ending_negocio",
        act=A, zone=Z5, tone="vacío",
        text=(
            "El trato se cobra. No hay trueno, no hay drama — solo un vacío "
            "que se abre donde antes había algo.\n\n"
            "Eres libre. Nyarlathotep cumplió su palabra. Pero lo que vendiste "
            "no vuelve. Caminas por las Dreamlands como un fantasma que olvidó "
            "por qué camina."
        ),
        on_enter={"corrupcion": +3},
        set_flags=["ending_gran_negocio"],
        paths=[
            P("Seguir caminando (destruiste la bendición)", "act5_negocio_bendicion",
              style="danger", conditions={"has_flag": "destruyo_bendicion"}),
            P("Seguir caminando (traicionaste a tu aliado)", "act5_negocio_traicion",
              style="danger", conditions={"has_flag": "traiciono_aliado_act3"}),
            P("Seguir caminando (cediste tu voluntad)", "act5_negocio_voluntad",
              style="danger", conditions={"has_flag": "perdio_voluntad_nyar"}),
            P("Seguir caminando (ya eras de Nyar)", "act5_negocio_corrupto",
              style="danger", conditions={"has_flag": "trato_con_nyar", "corrupcion_min": 50}),
            P("Seguir caminando", "act5_negocio_default", style="primary"),
        ],
    ))

    # --- Variante: destruyó la bendición felina ---
    nodes.append(N(
        "act5_negocio_bendicion",
        act=A, zone=Z5, tone="desolación",
        text=(
            "Un gato cruza tu camino. Te mira. Sus ojos dicen: te conozco.\n\n"
            "Luego te da la espalda. Otro gato hace lo mismo. Y otro. "
            "Todos los gatos de las Dreamlands saben lo que hiciste. "
            "Ninguno te mirará de nuevo. Para siempre.\n\n"
            "Caminas solo. El silencio de los gatos es peor que cualquier condena."
        ),
        on_enter={"favor": -10},
        set_flags=["gatos_rechazo_eterno"],
        paths=[
            P("Caminar hacia ningún lugar", "act5_negocio_epilogo", style="primary"),
        ],
    ))

    # --- Variante: traicionó aliado ---
    nodes.append(N(
        "act5_negocio_traicion",
        act=A, zone=Z5, tone="paranoia",
        text=(
            "Pasos detrás de ti. Los reconoces — son los pasos de quien "
            "llamabas aliado.\n\n"
            "No viene a hablar. No viene a perdonar. Viene a cobrarse "
            "lo que le hiciste. Y tiene todo el tiempo del mundo.\n\n"
            "Corres. Pero en las Dreamlands, los fantasmas no se cansan."
        ),
        on_enter={"voluntad": -3},
        set_flags=["aliado_venganza"],
        paths=[
            P("Correr sin destino", "act5_negocio_epilogo", style="danger"),
        ],
    ))

    # --- Variante: perdió voluntad ---
    nodes.append(N(
        "act5_negocio_voluntad",
        act=A, zone=Z5, tone="vacío",
        text=(
            "Caminas. ¿Por qué? No lo sabes. ¿Hacia dónde? No importa.\n\n"
            "Sin voluntad no hay dirección. Sin dirección no hay propósito. "
            "Tus piernas se mueven porque eso es lo que hacen las piernas. "
            "Tu mente está en blanco. Siempre estará en blanco.\n\n"
            "Eres un cuerpo que camina. Nada más."
        ),
        on_enter={"voluntad": -5},
        set_flags=["caminante_vacio"],
        paths=[
            P("...", "act5_negocio_epilogo", style="primary"),
        ],
    ))

    # --- Variante: trato + alta corrupción ---
    nodes.append(N(
        "act5_negocio_corrupto",
        act=A, zone=Z5, tone="oscuro",
        text=(
            "Eres libre. Eres vacío. Eres perfecto.\n\n"
            "Nyarlathotep no necesitó quedarse contigo. Ya eres exactamente "
            "lo que él quería: un recipiente vacío que camina, que respira, "
            "que existe sin existir. Perfecto para cuando te necesite de nuevo.\n\n"
            "Y te necesitará. Siempre te necesitará."
        ),
        on_enter={"corrupcion": +5},
        set_flags=["recipiente_nyar"],
        paths=[
            P("Esperar", "act5_negocio_epilogo", style="danger"),
        ],
    ))

    # --- Variante default ---
    nodes.append(N(
        "act5_negocio_default",
        act=A, zone=Z5, tone="melancolía",
        text=(
            "Lo que vendiste — ¿qué era? Ya no recuerdas. Solo sabes que "
            "falta algo. Un hueco en el pecho que el viento atraviesa.\n\n"
            "Las Dreamlands se extienden ante ti, infinitas y vacías. "
            "Tienes toda la eternidad para caminar. No tienes razón para hacerlo."
        ),
        on_enter={"memoria": -3},
        paths=[
            P("Caminar", "act5_negocio_epilogo", style="primary"),
        ],
    ))

    # --- Epílogo + Cameo Neruson ---
    nodes.append(N(
        "act5_negocio_epilogo",
        act=A, zone=Z5, tone="amargo",
        text=(
            "A lo lejos, una figura pequeña y chismosa observa tu silueta "
            "alejarse.\n\n"
            "Neruson se gira hacia nadie en particular.\n\n"
            "—Yo sabía que iba a pasar. Se lo dije. Bueno, no se lo dije "
            "a nadie, pero lo pensé. Eso cuenta.\n\n"
            "Nadie responde. Neruson asiente satisfecho de todos modos.\n\n"
            "█ FIN — EL GRAN NEGOCIO █"
        ),
        primary_npc="neruson",
        set_flags=["ending_complete_gran_negocio"],
        paths=[],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 6 — EL CANTO FINAL
    # ═══════════════════════════════════════════════════════════════════
    Z6 = "El Canto Final"

    nodes.append(N(
        "act5_ending_canto",
        act=A, zone=Z6, tone="sublime",
        text=(
            "La escuchas. La música que sostiene las Dreamlands — la melodía "
            "que existía antes que los dioses, antes que los sueños.\n\n"
            "Es hermosa. Es insoportable. No puedes dejar de escuchar. "
            "Tu cuerpo se detiene. Tus pies echan raíces. La piedra sube "
            "por tus piernas como una marea lenta."
        ),
        on_enter={"lucidez": +5},
        set_flags=["ending_canto_final"],
        paths=[
            P("Escuchar con Index", "act5_canto_index",
              style="primary", conditions={"has_flag": "ruta_index"}),
            P("Intentar entender la música", "act5_canto_lore",
              style="warning", conditions={"lore_min": 50}),
            P("Los gatos cantan contigo", "act5_canto_gatos",
              style="primary", conditions={"has_flag": "bendicion_felina"}),
            P("Escuchar", "act5_canto_default", style="primary"),
        ],
    ))

    # --- Variante: ruta Index ---
    nodes.append(N(
        "act5_canto_index",
        act=A, zone=Z6, tone="sublime",
        text=(
            "Index está ahí. A tu lado. También escucha. La piedra sube "
            "por sus piernas también.\n\n"
            "Te mira. Sus ojos ya son de mármol pero todavía brillan.\n\n"
            "—Mano... es god.\n\n"
            "Son sus últimas palabras. Las tuyas también se petrifican "
            "en tu garganta. Dos estatuas escuchando la música eterna."
        ),
        on_enter={"lucidez": +3},
        primary_npc="index",
        set_flags=["index_petrificado"],
        paths=[
            P("...", "act5_canto_epilogo", style="primary"),
        ],
    ))

    # --- Variante: alta lore ---
    nodes.append(N(
        "act5_canto_lore",
        act=A, zone=Z6, tone="horror_sublime",
        text=(
            "Entiendes la música. Cada nota es un universo muriendo. "
            "Cada silencio es un universo naciendo. El ciclo es infinito "
            "y tú lo comprendes TODO.\n\n"
            "Eso no ayuda. Entender no te salva. Solo hace que la "
            "petrificación sea consciente. Sabes exactamente lo que "
            "cada nota significa mientras la piedra te consume.\n\n"
            "El conocimiento es la peor prisión."
        ),
        on_enter={"lore": +10, "lucidez": +5},
        set_flags=["comprende_musica"],
        paths=[
            P("Comprender hasta el final", "act5_canto_epilogo", style="primary"),
        ],
    ))

    # --- Variante: bendición felina ---
    nodes.append(N(
        "act5_canto_gatos",
        act=A, zone=Z6, tone="belleza_terrible",
        text=(
            "Los gatos aparecen. Docenas. Cientos. Se sientan a tu alrededor "
            "y empiezan a cantar contigo. Su ronroneo se une a la melodía "
            "cósmica.\n\n"
            "No ayuda. No te salva. Solo hace la petrificación más bella. "
            "Eres una estatua rodeada de gatos cantores. Es hermoso. "
            "Es eterno. Es terrible."
        ),
        on_enter={"favor": +3},
        set_flags=["petrificacion_bella"],
        paths=[
            P("Ser hermoso para siempre", "act5_canto_epilogo", style="primary"),
        ],
    ))

    # --- Variante default ---
    nodes.append(N(
        "act5_canto_default",
        act=A, zone=Z6, tone="sublime",
        text=(
            "Escuchas. No entiendes. No necesitas entender. La música "
            "te llena como agua llenando un vaso.\n\n"
            "La piedra sube. Tus manos se endurecen. Tu rostro se fija "
            "en una expresión de asombro eterno. Es lo último que sientes: "
            "asombro."
        ),
        on_enter={"lucidez": +2},
        paths=[
            P("...", "act5_canto_epilogo", style="primary"),
        ],
    ))

    # --- Epílogo + Cameo Heku ---
    nodes.append(N(
        "act5_canto_epilogo",
        act=A, zone=Z6, tone="etéreo",
        text=(
            "La melodía continúa. Continuará siempre.\n\n"
            "Y en algún lugar entre las notas, Heku aparece. No como "
            "cuerpo — ya no tiene cuerpo. Es la melodía misma. Es el "
            "espacio entre las notas. Es el silencio que hace que la "
            "música exista.\n\n"
            "Sin cuerpo. Solo sonido. Solo siempre.\n\n"
            "█ FIN — EL CANTO FINAL █"
        ),
        primary_npc="heku",
        set_flags=["ending_complete_canto_final"],
        paths=[],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 7 — BIBLIOTECA ETERNA
    # ═══════════════════════════════════════════════════════════════════
    Z7 = "Biblioteca Eterna"

    nodes.append(N(
        "act5_ending_biblioteca",
        act=A, zone=Z7, tone="melancólico",
        text=(
            "Los textos te llaman. Las páginas se abren solas a tu paso. "
            "Las palabras se reordenan para contarte — para contenerte.\n\n"
            "Tu piel se vuelve pergamino. Tus venas, tinta. Tus recuerdos "
            "se escriben solos en páginas que no existían hace un segundo.\n\n"
            "Eres un libro. Contiene todo lo que viviste."
        ),
        on_enter={"lore": +5},
        set_flags=["ending_biblioteca_eterna"],
        paths=[
            P("Ser leído por Rotundus", "act5_biblio_rotundus",
              style="primary", conditions={"has_flag": "rotundus_aliado"}),
            P("Ser el texto más completo", "act5_biblio_descifro",
              style="primary", conditions={"has_flag": "descifro_textos"}),
            P("Contener la verdad", "act5_biblio_verdad",
              style="warning", conditions={"has_flag": "sabe_verdad_kadath"}),
            P("Ser un libro más", "act5_biblio_default", style="primary"),
        ],
    ))

    # --- Variante: Rotundus aliado ---
    nodes.append(N(
        "act5_biblio_rotundus",
        act=A, zone=Z7, tone="agridulce",
        text=(
            "Rotundus te encuentra. Te saca del estante con cuidado. "
            "Abre tus páginas con reverencia académica.\n\n"
            "—Es que este texto es fascinante. La estructura narrativa... "
            "los arcos de personaje... magistral.\n\n"
            "No te reconoce. Lee tu vida como si fuera ficción. "
            "Toma notas en los márgenes. Te cita en sus papers. "
            "Nunca sabrá que eras tú."
        ),
        primary_npc="rotundus",
        set_flags=["rotundus_te_lee"],
        paths=[
            P("Ser leído para siempre", "act5_biblio_epilogo", style="primary"),
        ],
    ))

    # --- Variante: descifró textos ---
    nodes.append(N(
        "act5_biblio_descifro",
        act=A, zone=Z7, tone="orgullo_vacío",
        text=(
            "Eres el texto más completo jamás escrito. Cada glifo que "
            "descifraste, cada secreto que arrancaste a las piedras — "
            "todo está aquí. En ti.\n\n"
            "Generaciones de soñadores te estudiarán. Escribirán tesis "
            "sobre ti. Discutirán tus significados. Nunca se pondrán "
            "de acuerdo.\n\n"
            "Eres inmortal. Eres incomprendido. Eres perfecto."
        ),
        on_enter={"lore": +10},
        set_flags=["texto_completo"],
        paths=[
            P("Ser estudiado por la eternidad", "act5_biblio_epilogo", style="primary"),
        ],
    ))

    # --- Variante: sabe la verdad ---
    nodes.append(N(
        "act5_biblio_verdad",
        act=A, zone=Z7, tone="horror_quieto",
        text=(
            "El libro contiene la verdad. LA verdad. Sobre Kadath, sobre "
            "los dioses, sobre el trono vacío, sobre todo.\n\n"
            "Nadie lo abrirá jamás.\n\n"
            "No porque esté prohibido. No porque esté escondido. "
            "Simplemente... nadie querrá. La verdad repele. La verdad "
            "pesa. Los que se acercan sienten náuseas y se van.\n\n"
            "Sabes todo. Nadie sabrá que sabes."
        ),
        on_enter={"lore": +15},
        set_flags=["verdad_sellada"],
        paths=[
            P("Esperar un lector que nunca vendrá", "act5_biblio_epilogo", style="primary"),
        ],
    ))

    # --- Variante default ---
    nodes.append(N(
        "act5_biblio_default",
        act=A, zone=Z7, tone="quieto",
        text=(
            "Eres un libro más en una biblioteca infinita. Tu lomo no "
            "tiene título. Tus páginas amarillean con el tiempo que no "
            "pasa.\n\n"
            "Alguien te leerá algún día. No sabrán que fuiste una persona. "
            "Pensarán que eres ficción. Quizás siempre lo fuiste."
        ),
        paths=[
            P("Esperar en el estante", "act5_biblio_epilogo", style="primary"),
        ],
    ))

    # --- Epílogo + Cameo Phosperono ---
    nodes.append(N(
        "act5_biblio_epilogo",
        act=A, zone=Z7, tone="irónico",
        text=(
            "Pasan los eones. La biblioteca persiste.\n\n"
            "Phosperono pasa por el pasillo. Se detiene frente a tu estante. "
            "Te mira — o mira a través de ti.\n\n"
            "—Nadie quiere leer — dice, con un suspiro que huele a "
            "resignación cósmica.\n\n"
            "Se va. No vuelve.\n\n"
            "█ FIN — BIBLIOTECA ETERNA █"
        ),
        primary_npc="phosperono",
        set_flags=["ending_complete_biblioteca"],
        paths=[],
    ))

    # ═══════════════════════════════════════════════════════════════════
    # ENDING 8 — ARQUITECTURA PERFECTA
    # ═══════════════════════════════════════════════════════════════════
    Z8 = "Arquitectura Perfecta"

    nodes.append(N(
        "act5_ending_arquitectura",
        act=A, zone=Z8, tone="geométrico",
        text=(
            "La montaña te reclama. No con violencia — con precisión.\n\n"
            "Tus huesos se alinean. Tus ángulos se perfeccionan. Tu carne "
            "se endurece en mármol imposible. Te conviertes en parte de "
            "Kadath. Un pilar. Un arco. Una escalera que nadie subirá.\n\n"
            "Perfecto. Eterno. Muerto."
        ),
        on_enter={"lucidez": +3},
        set_flags=["ending_arquitectura"],
        paths=[
            P("Ser estudiado por Rotundus", "act5_arq_rotundus",
              style="primary", conditions={"has_flag": "ruta_rotundus"}),
            P("Ser reclamado por el templo", "act5_arq_templo",
              style="danger", conditions={"has_flag": "templo_activado"}),
            P("Saber que eres arquitectura", "act5_arq_consciencia",
              style="warning", conditions={"has_flag": "sabe_verdad_kadath"}),
            P("Ser piedra", "act5_arq_default", style="primary"),
        ],
    ))

    # --- Variante: ruta Rotundus ---
    nodes.append(N(
        "act5_arq_rotundus",
        act=A, zone=Z8, tone="académico",
        text=(
            "Rotundus te encuentra. Saca su cuaderno. Empieza a medir.\n\n"
            "—La proporción es perfecta. Áurea, pero no exactamente — "
            "es algo más. Algo que no tiene nombre en ningún idioma "
            "humano.\n\n"
            "Toma notas durante horas. Días. Semanas. Nunca se cansa "
            "de estudiarte. Nunca te reconoce. Eres su obra maestra "
            "favorita. Eres su mejor paper."
        ),
        primary_npc="rotundus",
        set_flags=["rotundus_te_estudia"],
        paths=[
            P("Ser medido para siempre", "act5_arq_epilogo", style="primary"),
        ],
    ))

    # --- Variante: templo activado ---
    nodes.append(N(
        "act5_arq_templo",
        act=A, zone=Z8, tone="revelación",
        text=(
            "El templo te reclamó. Siempre fuiste parte de su diseño.\n\n"
            "Los planos que viste en las paredes — esos glifos que no "
            "podías descifrar — eran TÚ. Tu forma. Tu posición exacta. "
            "Estabas dibujado en la piedra miles de años antes de nacer.\n\n"
            "No viniste a Kadath. Kadath te trajo de vuelta."
        ),
        on_enter={"lore": +5},
        set_flags=["siempre_fue_diseño"],
        paths=[
            P("Encajar en tu lugar", "act5_arq_epilogo", style="primary"),
        ],
    ))

    # --- Variante: sabe la verdad ---
    nodes.append(N(
        "act5_arq_consciencia",
        act=A, zone=Z8, tone="horror_eterno",
        text=(
            "Sabes que eres arquitectura. La consciencia persiste.\n\n"
            "No puedes moverte. No puedes hablar. No puedes cerrar los "
            "ojos porque ya no tienes párpados. Pero piensas. Sientes. "
            "Recuerdas.\n\n"
            "Para siempre.\n\n"
            "Cada segundo es una eternidad. Cada eternidad es un segundo. "
            "Y no hay final. Nunca habrá final."
        ),
        on_enter={"voluntad": -10},
        set_flags=["consciencia_eterna"],
        paths=[
            P("Para siempre", "act5_arq_epilogo", style="danger"),
        ],
    ))

    # --- Variante default ---
    nodes.append(N(
        "act5_arq_default",
        act=A, zone=Z8, tone="quieto",
        text=(
            "Eres piedra. No piensas. No sientes. No recuerdas.\n\n"
            "El viento pasa a través de tus arcos. La lluvia te erosiona "
            "en escalas de milenios. Eres perfecto y no lo sabes. "
            "Quizás eso es misericordia."
        ),
        paths=[
            P("...", "act5_arq_epilogo", style="primary"),
        ],
    ))

    # --- Epílogo + Cameo Kaidps ---
    nodes.append(N(
        "act5_arq_epilogo",
        act=A, zone=Z8, tone="silencio",
        text=(
            "El tiempo pasa. Kadath persiste. Tú persistes.\n\n"
            "Kaidps pasa. Se detiene. Te mira.\n\n"
            "No dice nada.\n\n"
            "Se va.\n\n"
            "(Eso es peor.)\n\n"
            "█ FIN — ARQUITECTURA PERFECTA █"
        ),
        primary_npc="kaidps",
        set_flags=["ending_complete_arquitectura"],
        paths=[],
    ))

    return nodes
