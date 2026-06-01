"""Parche de profundización: inyecta text_variants a nodos clave tras el build.

Se aplica al final de build_world(). Mantiene los builders de cada acto
limpios mientras añadimos capas narrativas condicionadas por estado.
"""

from __future__ import annotations

from typing import Any, Dict, List


TEXT_VARIANTS: Dict[str, List[Dict[str, Any]]] = {
    # ═════════════════ ACTO 1 ═════════════════
    "prologo_despertar": [
        {
            "conditions": {"has_flag": "insight_III_espejo"},
            "text": (
                "No te despiertas. Nunca te despertaste. Vuelves a mirar la "
                "escalera de obsidiana como quien mira un error de indexado: "
                "ya estuviste aquí, y sigues aquí, y no sabes cuál de las dos "
                "cosas es más cierta.\n\n"
                "Más abajo, alguien con educación excesiva te espera. Lo "
                "reconocerás cuando llegues."
            ),
        },
        {
            "conditions": {"has_flag": "nyarlathotep_te_vio"},
            "text": (
                "La escalera de obsidiana desciende igual que antes. Pero "
                "ahora sabes que, a mitad de ella, hay alguien que te saluda "
                "con demasiada educación. Sabes que te recuerda.\n\n"
                "El aire huele a ozono y a recuerdos prestados."
            ),
        },
    ],

    "act1_glifos": [
        {
            "conditions": {"has_flag": "insight_II_susurros"},
            "text": (
                "Los glifos del tercer estrato ya no te resultan extraños: los "
                "oíste la noche pasada, aunque no hayas leído un libro en días. "
                "Se leen a sí mismos en tu oído interno. Dicen lo mismo. "
                "Dicen 'SIETE'. Dicen 'BARZAI'. Dicen 'NO MIRES ATRÁS'. Y "
                "dicen también un cuarto nombre, que es el tuyo, y que "
                "prefieres no pronunciar.\n\n"
                "El gato, si lo había, ya no está."
            ),
        },
    ],

    "act1_ulthar_gato_consejo": [
        {
            "conditions": {"has_flag": "taint_I_marcado"},
            "text": (
                "Los siete gatos están en el salón, pero algo en ellos te "
                "rehúye. El mayor no te mira a los ojos; mira un poco a la "
                "izquierda de ti, como si hubiera alguien más ahí, alguien "
                "peor.\n\n"
                "La pregunta, sin embargo, es la misma:\n\n"
                "— *¿Cuántos viajeros descienden, en realidad?*"
            ),
        },
        {
            "conditions": {"has_flag": "pacto_ghoul"},
            "text": (
                "Los gatos bufan cuando entras. Ninguno se retira, pero el "
                "silencio es una forma de expulsión. El mayor, al fin, "
                "pregunta — sin mirarte:\n\n"
                "— *¿Cuántos viajeros descienden, en realidad?*\n\n"
                "Y agrega, con una paciencia que podría ser piedad o desprecio:\n"
                "— *No esperamos tu respuesta. No la queremos.*"
            ),
        },
    ],

    # ═════════════════ ACTO 2 ═════════════════
    "act2_hub_yermos": [
        {
            "conditions": {"has_flag": "insight_III_espejo"},
            "text": (
                "Los Yermos Soñados ya no son una llanura: son cuatro "
                "llanuras superpuestas, y caminas por las cuatro al mismo "
                "tiempo. Cada camino lleva a su ciudad — y también a una "
                "versión distorsionada de ella.\n\n"
                "Gab sigue sentado en su piedra. Saludándote. Pero es otro "
                "Gab. Hay muchos."
            ),
        },
        {
            "conditions": {"has_flag": "taint_II_abandonado"},
            "text": (
                "La encrucijada parece más pequeña que antes. Los caminos "
                "hacia Celephaïs y Ulthar se ven borrosos, como si estuvieran "
                "cerrándose. El camino al bosque zoog y a Dylath-Leen, en "
                "cambio, se ven más nítidos que nunca.\n\n"
                "Gab te saluda desde su piedra con una sonrisa que sabe "
                "demasiado."
            ),
        },
    ],

    "act2_dylath_entrada": [
        {
            "conditions": {"has_flag": "sabe_chisme_neruson"},
            "text": (
                "Ahora que sabes lo que Neruson te contó, ves al mercader "
                "del turbante rojo como lo que es: un Hombre de Leng con la "
                "piel mal puesta. Sus pies no tocan el suelo. Su sonrisa es "
                "una línea pintada.\n\n"
                "El gato de Ulthar, a su lado, te observa con atención "
                "redoblada."
            ),
        },
    ],

    "act2_sarkomand_ruinas": [
        {
            "conditions": {"has_flag": "insight_II_susurros"},
            "text": (
                "Las estatuas sin cara tienen ahora las tuyas — o versiones "
                "tuyas, distintos viajeros sin rostro. Sarkomand no olvida "
                "a los que bajan. Los conserva en piedra.\n\n"
                "Papu sigue roncando sobre una de ellas. Sobre ti, en "
                "realidad."
            ),
        },
    ],

    # ═════════════════ ACTO 3 ═════════════════
    "act3_hub_profundidades": [
        {
            "conditions": {"has_flag": "pacto_ghoul"},
            "text": (
                "Las Profundidades te saludan como a un regresado. El aire "
                "huele a leche de luna. Los túneles que antes parecían "
                "amenazantes ahora se ven como pasillos de una casa que fue "
                "tuya.\n\n"
                "Al sur, el río subterráneo. Al norte, las criptas de los "
                "tuyos. Al oeste, el templo donde alguien te sigue esperando."
            ),
        },
        {
            "conditions": {"has_flag": "insight_III_espejo"},
            "text": (
                "La caverna ya no es una caverna. Es un pulmón. Cada "
                "respiración suya es un sueño tuyo hecho ambiente. Los tres "
                "caminos visibles ya no son tres: son los mismos tres, pero "
                "vistos desde tres ángulos mentales distintos.\n\n"
                "No sabes cuál de ti elige."
            ),
        },
    ],

    "act3_templo_entrada": [
        {
            "conditions": {"has_flag": "provoco_al_caos"},
            "text": (
                "El agua negra te reconoce cuando entras. El altar al fondo "
                "está vacío — el sacerdote no te espera con el rostro que le "
                "recuerdas. Te espera con otro. Uno que se parece a ti, "
                "aunque deformado.\n\n"
                "El murmullo ya no es de mil voces. Es de una sola voz que "
                "dice tu nombre mil veces."
            ),
        },
    ],

    "act3_lago_memorias": [
        {
            "conditions": {"has_flag": "leyo_libro_sarkomand"},
            "text": (
                "El lago refleja ahora algo que ya leíste: tu vida despierta, "
                "capítulo por capítulo, con las últimas páginas en blanco. "
                "Mirar el agua es releer. Y lo que ves cambiará según dónde "
                "mires.\n\n"
                "Mira, o no mires. Ya no es gratis ninguna opción."
            ),
        },
    ],

    # ═════════════════ ACTO 4 ═════════════════
    "act4_campamento": [
        {
            "conditions": {"has_flag": "dio_un_ojo"},
            "text": (
                "JC te espera con una sola taza en la mano, no con siete. "
                "La octava — la tuya — la dejó aparte, en una roca más alta. "
                "Te saluda sin el único ojo que le queda, usando el otro, "
                "que tú le diste.\n\n"
                "— *Bien. Eres de los que vuelven.*"
            ),
        },
        {
            "conditions": {"has_flag": "insight_III_espejo"},
            "text": (
                "JC te recibe con la sonrisa de alguien que ya sabe lo que "
                "vas a preguntar. Las siete tazas frente a él son la "
                "tuya, repetida siete veces — y todas las tuyas son al mismo "
                "tiempo.\n\n"
                "— *A ver, XDD, siempre es ahora.*"
            ),
        },
    ],

    "act4_ascenso_inicio": [
        {
            "conditions": {"has_flag": "taint_III_corteja"},
            "text": (
                "La espiral termina en la falda del Monte Throk. El aire es "
                "tan limpio que duele. Nyarlathotep te llama por tu nombre "
                "despierto desde arriba — no te apura, solo te saluda.\n\n"
                "Las torres negras de Kadath parecen reclinarse ligeramente "
                "para saludarte también. Como si te reconocieran."
            ),
        },
        {
            "conditions": {"has_flag": "insight_IV_desanclado"},
            "text": (
                "La espiral termina donde siempre termina. El Monte Throk "
                "existe solo porque tú lo estás subiendo. Arriba, dos "
                "mesas — no tres, no cuatro, siempre dos. Ya ves más allá "
                "de la subida.\n\n"
                "Lo que sigue es menos importante que lo que ya elegiste."
            ),
        },
    ],

    # ═════════════════ ACTO 5 ═════════════════
    "act5_cumbre_trono": [
        {
            "conditions": {"has_flag": "insight_IV_desanclado"},
            "text": (
                "Ya no hay dos mesas. Nunca hubo dos mesas. Hay una, y "
                "alguien sentado al frente de ella, que es Nyarlathotep con "
                "siete caras o siete Dioses Blandos con una cara.\n\n"
                "Nadie ha hablado porque nadie puede hablar. Tú ya no "
                "eres tú del todo. Lo que digas saldrá de la boca que "
                "ellos elijan."
            ),
        },
        {
            "conditions": {"has_flag": "dio_un_ojo"},
            "text": (
                "Entras a la sala y ves las dos mesas con el ojo que te "
                "queda. Con el otro — el perdido, el que JC te guarda — "
                "ves además una tercera mesa, pequeña, al fondo, en la que "
                "tú ya estás sentado.\n\n"
                "Esperas a que alguien hable. Nadie lo hace. JC tenía razón: "
                "los dioses no hablan primero."
            ),
        },
    ],

    # ═════════════════ NERUSON EXPANDIDO ═════════════════
    "act2_isla_primera_puja": [
        {
            "conditions": {"has_flag": "hablo_con_neruson"},
            "append_text": (
                "\n\nEntre los encapuchados, reconoces una figura "
                "pequeña sin capucha — **Neruson**. Está sentado en "
                "la tercera fila, comiendo algo, mirándote con una "
                "sonrisa enorme.\n\n"
                "— *Oye mano, no te pongas así. Yo vine a ver nomás. "
                "Bueno... y a pujar un poquito. Pero tranqui, no "
                "tengo tanto presupuesto. Sólo quería ver tu cara "
                "cuando te pusieran precio.*"
            ),
        },
        {
            "conditions": {"has_flag": "neruson_debe_favor"},
            "append_text": (
                "\n\nNeruson está en la tercera fila. Te saluda con "
                "la mano como si estuvieras en un café.\n\n"
                "— *Mano, ¿te acuerdas que me diste info en el puerto? "
                "Bueno, ahora yo sé tu precio. Estamos a mano, pije. "
                "No te creas, no voy a pujar en serio... creo.*"
            ),
        },
    ],
    "act2_isla_puja_sube": [
        {
            "conditions": {"has_flag": "hablo_con_neruson"},
            "append_text": (
                "\n\nNeruson levanta la mano: — *¡Catorce!* — Todos "
                "lo miran. Él se encoge de hombros: — *¿Qué? Quiero "
                "ver hasta dónde llega. Además me debe un chisme.*\n\n"
                "El Hombre de Leng lo fulmina. Neruson baja la mano, "
                "riendo."
            ),
        },
    ],
    "act2_isla_escenario": [
        {
            "conditions": {"has_flag": "hablo_con_neruson"},
            "append_text": (
                "\n\nDesde la tercera fila, Neruson te hace un gesto "
                "con el pulgar hacia arriba. Luego se señala los ojos "
                "y después a ti — «te estoy viendo». No sabes si es "
                "amenaza o apoyo."
            ),
        },
    ],
    "act2_isla_dama_cierra": [
        {
            "conditions": {"has_flag": "jc_interaccion"},
            "append_text": (
                "\n\nAntes de que la Dama hable, una voz vieja y "
                "rasposa desde el fondo: — *Veinte.* — Es **JC**. "
                "El anciano de un ojo, aquí, en la subasta. Temblando "
                "pero de pie. Pujando por ti.\n\n"
                "La Dama lo mira. JC no baja la mirada. — *Treinta* "
                "— dice ella. JC cierra su único ojo. Se sienta. "
                "No puede competir.\n\n"
                "Cuando pasa a tu lado murmura: — *Lo intenté, "
                "muchacho. Lo intenté.*"
            ),
        },
    ],
    "act3_rio_entrada": [
        {
            "conditions": {"has_flag": "hablo_con_neruson"},
            "append_text": (
                "\n\nUna voz familiar desde una esquina oscura: "
                "— *Oye, mano. Sí, soy yo. Neruson. ¿Qué hago aquí? "
                "Pues lo mismo que tú pero llegué antes. Ya sé lo que "
                "hay abajo. ¿Quieres que te cuente o prefieres la "
                "sorpresa?*\n\n"
                "Sonríe. Siempre sonríe."
            ),
        },
    ],
    "act3_ghouls_encuentro": [
        {
            "conditions": {"has_flag": "hablo_con_neruson", "lacks_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nNeruson está aquí también — sentado entre los "
                "ghouls como si fueran viejos amigos. — *Mano, estos "
                "compas son buena onda si les caes bien. Yo les "
                "cuento chismes del puerto y ellos me dan huesos "
                "interesantes. Win-win.*"
            ),
        },
    ],
    "act5_esperas": [
        {
            "conditions": {"has_flag": "hablo_con_neruson", "lacks_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nUna nota en el suelo, con la caligrafía de "
                "Neruson: «Mano, si llegaste hasta aquí, felicidades. "
                "Yo no subí. Me quedé abajo. Pero te cuento un "
                "chisme gratis: lo que hable primero no es un dios. "
                "De nada. — N.»"
            ),
        },
    ],

    # ═════════════════ RUTA ZUTO (propiedad_dama) ═════════════════
    "act3_hub_profundidades": [
        {
            "conditions": {"has_flag": "hablo_con_neruson", "lacks_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nUna voz familiar desde una esquina oscura: "
                "— *Oye, mano. Sí, soy yo. Neruson. ¿Qué hago aquí? "
                "Pues lo mismo que tú pero llegué antes. Ya sé lo que "
                "hay abajo. ¿Quieres que te cuente o prefieres la "
                "sorpresa?*\n\n"
                "Sonríe. Siempre sonríe."
            ),
        },
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\n— *No te detengas* — dice Zuto desde algún lugar "
                "detrás de ti. No la ves. Pero la sientes. Siempre la "
                "sientes. — *Baja. Quiero ver qué hay abajo.*"
            ),
        },
    ],
    "act3_lago_memorias": [
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nZuto aparece a tu lado. Mira el lago con "
                "desinterés. — *Tus memorias. Qué aburridas. Mira las "
                "mías.* — Toca el agua. El lago se vuelve negro un "
                "segundo. Luego vuelve. No te dice qué vio."
            ),
        },
    ],
    "act3_ghouls_encuentro": [
        {
            "conditions": {"has_flag": "hablo_con_neruson", "lacks_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nNeruson está aquí también — sentado entre los "
                "ghouls como si fueran viejos amigos. — *Mano, estos "
                "compas son buena onda si les caes bien. Yo les "
                "cuento chismes del puerto y ellos me dan huesos "
                "interesantes. Win-win.*"
            ),
        },
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nLos ghouls te miran. Luego miran detrás de ti — "
                "donde Zuto está, invisible para ti pero no para ellos. "
                "Retroceden. — *Ah* — dice uno — *vienes con dueña. "
                "No tocamos lo que tiene marca.*"
            ),
        },
    ],
    "act3_templo_altar": [
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\n— *Arrodíllate* — dice Zuto. No ante el altar. "
                "Ante ella. Aquí, en el templo, su voz suena más "
                "fuerte. El sello pulsa. — *Este lugar es mío también. "
                "Todo lo que ves es mío. Incluido tú.*"
            ),
        },
    ],
    "act4_campamento": [
        {
            "conditions": {"has_flag": "hablo_con_neruson", "lacks_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nNeruson está sentado al otro lado de la fogata, "
                "con una taza vacía. — *Oye, ya llegaste. JC me "
                "contó que venías. Yo le conté lo que hiciste en "
                "Sarkomand. Él me contó lo del ojo. Estamos al día.*\n\n"
                "JC suspira: — *Neruson sabe todo. Es agotador.*"
            ),
        },
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nJC te mira con su único ojo. Luego mira detrás "
                "de ti. Palidece. — *Vienes... acompañado. Eso que "
                "llevas encima... no se quita, muchacho. Lo siento.*"
            ),
        },
    ],
    "act4_ascenso_inicio": [
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\n— *Sube* — ordena Zuto. — *Quiero ver la cumbre "
                "desde tus ojos. Los míos ya la vieron. Pero los tuyos "
                "son nuevos. Sube, mueble.*"
            ),
        },
    ],
    "act5_cumbre_trono": [
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nZuto se materializa a tu lado. Se sienta en el "
                "trono como si fuera suyo. Quizá lo es. — *¿Creías "
                "que ibas a llegar aquí y ser libre? Llegaste aquí "
                "porque yo te traje. Eres mi mueble favorito. El que "
                "camina solo.*\n\n"
                "Nyarlathotep — el verdadero, el del trono — la mira. "
                "Asiente. Son lo mismo. Siempre fueron lo mismo."
            ),
        },
    ],
    "act5_esperas": [
        {
            "conditions": {"has_flag": "hablo_con_neruson", "lacks_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\nUna nota en el suelo, con la caligrafía de "
                "Neruson: «Mano, si llegaste hasta aquí, felicidades. "
                "Yo no subí. Me quedé abajo. Pero te cuento un "
                "chisme gratis: lo que hable primero no es un dios. "
                "De nada. — N.»"
            ),
        },
        {
            "conditions": {"has_flag": "ruta_dama_activa"},
            "append_text": (
                "\n\n— *Casi* — dice Zuto. — *Casi llegas. Bien. "
                "Los muebles que llegan lejos son los más valiosos. "
                "No te emociones. Sigues siendo una silla.*"
            ),
        },
    ],
}


def apply_text_variants(world: Dict[str, Dict[str, Any]]) -> int:
    """Añade text_variants a los nodos listados. Devuelve cantidad inyectada."""
    count = 0
    for node_id, variants in TEXT_VARIANTS.items():
        if node_id not in world:
            continue
        node = world[node_id]
        existing = node.get("text_variants") or []
        # Combina sin duplicar
        node["text_variants"] = variants + existing
        count += len(variants)
    return count
