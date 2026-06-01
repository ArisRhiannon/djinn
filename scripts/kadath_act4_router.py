"""
Kadath Acto 4 - Router de Arquetipos
15 nodos que bifurcan según flags del jugador.
"""


def build_act4_router(N, P) -> list:
    nodes = []

    # ═══════════════════════════════════════════════════════════════
    # NODO 1: ENTRADA PRINCIPAL - Router por arquetipo
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_ascenso_inicio',
        paths=[
            P('Nyar Iluminado', 'act4_nyar_iluminado',
              conditions={'has_flag': 'sabe_verdad_kadath'}),
            P('Nyar Zuto', 'act4_nyar_zuto',
              conditions={'has_flag': 'ruta_dama_activa'}),
            P('Nyar Corrupto', 'act4_nyar_corrupto',
              conditions={'has_flag': 'nyarlathotep_te_aprueba'}),
            P('Mascara Edyssey', 'act4_mascara_edyssey',
              conditions={'has_flag': 'edyssey_devorado_por_payaso'}),
            P('Mascara Puro', 'act4_mascara_puro',
              conditions={'has_flag': 'digno_de_kadath'}),
            P('Mascara Aliado', 'act4_mascara_aliado',
              conditions={'has_flag': 'edyssey_aliado'}),
            P('Mascara Traidor', 'act4_mascara_traidor',
              conditions={'has_flag': 'mato_edyssey'}),
            P('Mascara Default', 'act4_mascara_default'),
        ]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODOS 2-4: ARQUETIPOS DIRECTOS (saltan Fase 1)
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_nyar_iluminado'
             "'Ya lo sabes. ¿Para qué fingir?' La revelación directa te golpea como un maremoto.",
        paths=[P('Revelacion Final', 'act4_revelacion_final')]
    ))

    nodes.append(N(
        'act4_nyar_zuto'
             "'Siempre fui yo', dice con una voz que no es suya. Zuto era el disfraz.",
        paths=[P('Revelacion Final', 'act4_revelacion_final')]
    ))

    nodes.append(N(
        'act4_nyar_corrupto'
             "Cada decisión tuya fue exactamente lo que necesitaba.' Te felicita. Genuinamente.",
        paths=[P('Revelacion Final', 'act4_revelacion_final')]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODOS 5-8: MÁSCARAS (Fase 1 - engaño activo)
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_mascara_edyssey'
             "Pero sus ojos... sus ojos no parpadean.",
        paths=[
            P('Algo Mal', 'act4_algo_mal'),
            P('Revelacion Final', 'act4_revelacion_final'),
        ]
    ))

    nodes.append(N(
        'act4_mascara_puro'
             "Todo es perfecto. Demasiado perfecto. La luz no proyecta sombras.",
        paths=[
            P('Algo Mal', 'act4_algo_mal'),
            P('Revelacion Final', 'act4_revelacion_final'),
        ]
    ))

    nodes.append(N(
        'act4_mascara_aliado'
             "Pero repite exactamente las mismas palabras que dijo al conocerte. Exactamente.",
        paths=[
            P('Algo Mal', 'act4_algo_mal'),
            P('Revelacion Final', 'act4_revelacion_final'),
        ]
    ))

    nodes.append(N(
        'act4_mascara_traidor'
             "No te acusan. Sonríen. 'Gracias', dicen al unísono. Eso es peor.",
        paths=[
            P('Algo Mal', 'act4_algo_mal'),
            P('Revelacion Final', 'act4_revelacion_final'),
        ]
    ))

    nodes.append(N(
        'act4_mascara_default'
             "'Te estaba esperando aquí arriba.' Pero no debería estar aquí. No tiene sentido.",
        paths=[
            P('Algo Mal', 'act4_algo_mal'),
            P('Revelacion Final', 'act4_revelacion_final'),
        ]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODO 9: ALGO ESTÁ MAL (para los que no saltan Fase 1)
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_algo_mal'
             "Quien sea que está frente a ti... titubea. Como un actor que olvidó su línea.",
        paths=[
            P('Campamento Jc', 'act4_campamento_jc'),
            P('Revelacion Final', 'act4_revelacion_final'),
        ]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODOS 10-11: TRANSICIONES POR RUTA DEL ACTO 3
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_sendero_iluminado'
             "brillan en las paredes de roca. El camino asciende bañado en una luz que no calienta.",
        paths=[
            P('Ascenso Inicio', 'act4_ascenso_inicio',
              conditions={'has_flag': 'ruta_index'}),
        ]
    ))

    nodes.append(N(
        'act4_sendero_sombras'
             "los ecos suenan antes que las voces. Subes entre tinieblas familiares.",
        paths=[
            P('Ascenso Inicio', 'act4_ascenso_inicio',
              conditions={'has_flag': 'ruta_ccn'}),
        ]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODO 12: CAMPAMENTO DE JC
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_campamento_jc'
             "'Muchacho. Lo que te espera arriba no es lo que parece. Nada aquí lo es.' "
             "Su ojo bueno te perfora. 'Nyarlathotep usa lo que más quieres como disfraz.'",
        npc='jc_anciano_un_ojo',
        paths=[
            P('Ascenso Inicio', 'act4_ascenso_inicio'),
            P('Algo Mal', 'act4_algo_mal'),
        ]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODO 13: ALGO ESTÁ MUY MAL (segundo nivel de sospecha)
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_algo_muy_mal'
             "Capas infinitas de mentira. El aire huele a ozono y a algo antiguo. "
             "Nyarlathotep se está divirtiendo con tu resistencia.",
        paths=[P('Revelacion Final', 'act4_revelacion_final')]
    ))

    # ═══════════════════════════════════════════════════════════════
    # NODO 14-15: REVELACIÓN FINAL (convergencia)
    # ═══════════════════════════════════════════════════════════════
    nodes.append(N(
        'act4_revelacion_final'
             "El Caos Reptante te mira con algo parecido al respeto. O al hambre. "
             "'Bienvenido a Kadath, soñador.'",
        paths=[P('Decision Final', 'act4_decision_final')]
    ))

    nodes.append(N(
        'act4_decision_final'
             "Nyarlathotep espera tu respuesta. Todo el viaje te trajo aquí.",
        paths=[]
    ))

    return nodes
