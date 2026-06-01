"""
Kadath — motor de aventura determinista.

Filosofía:
- El LLM (u otro autor) construye el mundo durante la creación (data/kadath_world.json
  + plantillas de voz en este archivo).
- En runtime el motor es puro: lee el JSON, valida condiciones, aplica efectos, avanza
  nodos. No hay HP de combate, no hay muerte por tiempo, no hay eventos aleatorios que
  castiguen al jugador por explorar.
- La "muerte" o finales oscuros sólo ocurren por decisiones explícitas del jugador al
  llegar a nodos finales con los prerequisitos adecuados.

Stats (0-100):
- VOLUNTAD   — resistencia al sueño que te quiere disolver.
- LUCIDEZ    — claridad mental, capacidad de razonar en el sueño.
- FAVOR      — estima de los Dioses Blandos (Nodens, los Otros).
- CORRUPCION — influencia de Nyarlathotep, el Caos Reptante.
- LORE       — conocimiento arcano acumulado.
- MEMORIA    — conexión con tu yo despierto.

Arquetipos (ver CHARACTER_DATA más abajo). Cada uno trae:
- Stats iniciales distintos (no hay "clase mejor", son tradeoffs narrativos).
- Una habilidad única NO de combate, útil en rutas específicas.
- Voz: plantillas de reacción + frases específicas en nodos críticos.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Arquetipos ──────────────────────────────────────────────────────────────

CHARACTER_DATA: Dict[str, Dict[str, Any]] = {
    "ARIS": {
        "class": "LECTORA",
        "title": "La Lectora de Glifos",
        "description": (
            "Ojo frío. Lee los símbolos como si fueran código. "
            "No cree en milagros; cree en patrones."
        ),
        "base_stats": {
            "voluntad": 55, "lucidez": 60, "favor": 40,
            "corrupcion": 25, "lore": 55, "memoria": 55,
        },
        "item_slots": 6,
        "tagged_bonuses": {"glifo", "arcano", "patron", "observar"},
    },
    "LAW": {
        "class": "CANTOR",
        "title": "El Cantor del Umbral",
        "description": (
            "Saca la música de cualquier parte. Cuando los horrores se acercan, "
            "él tararea algo y, por un segundo, todo tiene sentido otra vez."
        ),
        "base_stats": {
            "voluntad": 50, "lucidez": 65, "favor": 55,
            "corrupcion": 20, "lore": 45, "memoria": 60,
        },
        "item_slots": 5,
        "tagged_bonuses": {"cancion", "cantar", "social", "calmar"},
    },
    "HARU": {
        "class": "TRICKSTER",
        "title": "El que se Ríe del Abismo",
        "description": (
            "No se asusta. Se ríe. No es valentía: es que ya vio demasiadas "
            "pendejadas como para que el fin del mundo le afecte."
        ),
        "base_stats": {
            "voluntad": 60, "lucidez": 50, "favor": 45,
            "corrupcion": 35, "lore": 45, "memoria": 55,
        },
        "item_slots": 6,
        "tagged_bonuses": {"reir", "caos", "evadir", "absurdo"},
    },
    "ELYKO": {
        "class": "OBSERVADOR",
        "title": "El Observador Técnico",
        "description": (
            "Habla poco, calcula mucho. Cuando por fin abre la boca, suelta la "
            "observación que nadie vio venir y que te reordena la cabeza."
        ),
        "base_stats": {
            "voluntad": 55, "lucidez": 55, "favor": 40,
            "corrupcion": 30, "lore": 60, "memoria": 55,
        },
        "item_slots": 5,
        "tagged_bonuses": {"calcular", "patron", "trampa", "leer"},
    },
    "XOFT": {
        "class": "PROVOCADOR",
        "title": "El que Rompe Máscaras",
        "description": (
            "No tiene freno. Pincha a los dioses a ver si contestan. "
            "Curiosamente, a veces contestan."
        ),
        "base_stats": {
            "voluntad": 65, "lucidez": 45, "favor": 45,
            "corrupcion": 40, "lore": 40, "memoria": 55,
        },
        "item_slots": 6,
        "tagged_bonuses": {"provocar", "romper", "directa", "gritar"},
    },
    "XOKRAM": {
        "class": "NEGOCIADOR",
        "title": "El Contrabandista de Sueños",
        "description": (
            "Habla con todo el mundo — con humanos, con ghouls, con dioses. "
            "Siempre encuentra el ángulo. Siempre hay un ángulo."
        ),
        "base_stats": {
            "voluntad": 55, "lucidez": 50, "favor": 50,
            "corrupcion": 40, "lore": 40, "memoria": 60,
        },
        "item_slots": 8,
        "tagged_bonuses": {"negociar", "mercado", "pacto", "intercambio"},
    },
    "DARAZIEL": {
        "class": "CARTOGRAFO",
        "title": "El Cartógrafo del Sueño",
        "description": (
            "Dibuja mapas de lugares que aún no han sido soñados. "
            "La geometría le habla en voz baja, y él escucha."
        ),
        "base_stats": {
            "voluntad": 55, "lucidez": 60, "favor": 45,
            "corrupcion": 25, "lore": 60, "memoria": 55,
        },
        "item_slots": 5,
        "tagged_bonuses": {"mapa", "geometria", "arquitectura", "diseñar"},
    },
}


# ─── Plantillas de voz por arquetipo ─────────────────────────────────────────
# Estas plantillas son las frases de "relleno" que aparecen cuando un nodo no
# tiene diálogo específico para ese personaje. Son auténticas (basadas en los
# perfiles destilados en data/personas/*) y se eligen de forma determinista por
# hash(node_id, character_id) — mismo nodo, misma frase siempre, pero con
# variedad garantizada a lo largo del juego.
#
# Convenciones:
# - {tag}: placeholder de contexto (calm/tense/horror/awe/discovery/loss).
# - Cada tag apunta a una lista de frases; se elige una por hash.

VOICE_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "ARIS": {
        "calm":    [
            "ok.",
            "sí, esto tiene sentido. lo dudo, pero tiene sentido.",
            "jopetas, otra sala.",
            "esto es como un boot sequence orgánico, la verdad.",
            "nada que no hayamos visto en un gacha game.",
        ],
        "tense":   [
            "ok no me gusta esto.",
            "lo dudo, la verdad, pero ya estamos acá.",
            "baiteo cósmico detectado.",
            "si esto me droppea, me droppea. jopetas.",
        ],
        "horror":  [
            "ok esto ya no es divertido.",
            "familia perrito >>>> esta vaina.",
            "me voy a matar jajaja pero literal.",
            "me estoy mareando con tanto lore sin contexto.",
        ],
        "awe":     [
            "jopetas.",
            "ok, esto sí es peak.",
            "esto es god, no voy a mentir.",
            "…sí, ok, esto sí me pegó.",
        ],
        "discovery": [
            "ah. interesante.",
            "ok, patrón detectado.",
            "esto lo saqué del log, no de ustedes.",
            "pfp material, honestamente.",
        ],
        "loss":    [
            "gg.",
            "ok, droppeamos eso.",
            "la verdad, me da mayormente igual. pero duele.",
        ],
        "social":  [
            "ok, tú haz lo que quieras, yo veo desde acá.",
            "lo dudo. pero dale.",
            "ok, explícamelo como si tuviera 5.",
        ],
    },
    "LAW": {
        "calm":    [
            "oye oye, qué bonito esto.",
            "mano, esto suena bien.",
            "me gusta, me gusta, sigamos.",
            "ASKJDHSJKDS qué paz, no mames.",
        ],
        "tense":   [
            "oye oye oye, momento.",
            "MANO espera, esto pinta raro.",
            "jakshdjska, no me gusta el ambiente.",
            "MÁNDASELO AL DM esto porfa, no lo quiero acá.",
        ],
        "horror":  [
            "MANO MANO MANO no.",
            "ASKJDHSJKDS QUÉ ES ESO.",
            "oye oye oye OYE.",
            "ok yo me salgo, les confío el resto.",
        ],
        "awe":     [
            "MANO POR FIN, era esto.",
            "oye, OYE, esto es god.",
            "<a:FrierenShiver:1403015493312315433> esto me pegó.",
            "termino este cap y me voy, dice uno, pero no, sigamos.",
        ],
        "discovery": [
            "oye, entendí todo lo q necesitaba.",
            "mano, hay plugins más refinados que esto.",
            "ASKJDHSJKDS miren esto.",
        ],
        "loss":    [
            "mano, los caps que quedan. ya qué.",
            "oye, les confío a ustedes.",
            "sería pelear con nadie igual.",
        ],
        "social":  [
            "oye oye, hagan algo con esto.",
            "MÁNDASELO al que esté a cargo, yo no sé.",
            "mano, yo acompaño, pero tú decides.",
        ],
    },
    "HARU": {
        "calm":    [
            "mano qué tranqui esto xd.",
            "aver, pije, no está mal.",
            "mano este lugar es god.",
            "xdxd ni el buggy dura menos que esto.",
        ],
        "tense":   [
            "mano esto es una pendejada xdd.",
            "coño marico ya me cansé.",
            "aver aver, no me chaqueteen.",
            "mano este ambiente es salado.",
        ],
        "horror":  [
            "MANO esto ya es mucho xddd.",
            "coño qué pendejada es esta.",
            "ja ja ja no voy a morir aquí por una tontería.",
            "mano ya dejen esta pendejada.",
        ],
        "awe":     [
            "MANO ESO SÍ ES GOD.",
            "pije, esto spawneó bonito.",
            "xd ok sí, esto vale la pena.",
            "mano esto es peak, ja ja.",
        ],
        "discovery": [
            "aver, pije, qué tenemos acá.",
            "xddd mira esto, marico.",
            "mano esto es una goddddd, vamos.",
            "ja ja ja me llegó la respuesta antes que el problema.",
        ],
        "loss":    [
            "xd gg, ni modo.",
            "mano, a la próxima la sacamos.",
            "coño ya qué, seguimos.",
        ],
        "social":  [
            "mano ya dejen de pelear por pendejadas.",
            "aver, chaquetéense tranquilos, yo observo xdd.",
            "mano, todos se lo toman muy personal.",
        ],
    },
    "ELYKO": {
        "calm":    [
            "mano, esto está normal. por ahora.",
            "aver, déjame mapear las variables.",
            "JAJAJAJA pareciera tranquilo, pero nunca lo es.",
            "está muy goddddd. sospechosamente god.",
        ],
        "tense":   [
            "MANO esto no cuadra.",
            "no generas punchline con esto, esto es real.",
            "JAJAJAJA PARECIERA QUE todo va bien, pero no.",
            "MUY BIEN AMOR, a pensar.",
        ],
        "horror":  [
            "CUAL DE TODOS es el que nos quiere matar.",
            "MANO esto es pocket dimension cringe.",
            "JAJAJAJA pareciera, pero no es nada divertido.",
            "ASLKDJALSKDJ eso no debería existir.",
        ],
        "awe":     [
            "está muy god mano.",
            "JAJAJAJA esto es lore puro.",
            "MUY BIEN AMOR, eso sí valió la ruta.",
            "roxy cara de seed, pero esto es distinto.",
        ],
        "discovery": [
            "aver, patrón detectado.",
            "mano esto tiene cara de ser importante.",
            "JAJAJAJA sí, esto encaja con la teoría.",
            "me puedo jubilar a los 20 con este lore.",
        ],
        "loss":    [
            "CUAL DE TODOS, ni siquiera me enteré.",
            "gg, eso salió mal.",
            "mano, literal no fue nuestro fault.",
        ],
        "social":  [
            "mano esta gente no entiende.",
            "JAJAJAJA PARECIERA QUE son aliados.",
            "tienen cara de traicionarnos, aver.",
        ],
    },
    "XOFT": {
        "calm":    [
            "va, estamos tranqui.",
            "KSJSKAJAJAJAJ ok, esto es manejable.",
            "mano, peak setting fr.",
            "ya se, ya se, sigamos.",
        ],
        "tense":   [
            "va, aquí empieza el drama.",
            "KSJSKAJAJAJAJ no me digas que nos van a dropear.",
            "peak karma incoming 💔.",
            "Mano, esto huele a traición, ya se.",
        ],
        "horror":  [
            "KSJSKAJAJAJAJ NO LLEGA A LA MÉDULA esto, literal.",
            "va, yo soy el que muere primero 🥀.",
            "mano esto es karma por algo que hicimos.",
            "okei, nos vamos, gg.",
        ],
        "awe":     [
            "KSJSKAJAJAJAJ ESTO ES PEAK.",
            "va, god, GOD, no voy a mentir.",
            "KAJAJAJAJJAJAJA ya decía yo que estaba god.",
            "Mano esto es más god que cualquier dropeada.",
        ],
        "discovery": [
            "va, tenemos algo acá.",
            "KSJSKAJAJAJAJ miren lo que encontré.",
            "mano, este lore es peak.",
            "CON RAZÓN MANO, ya decía yo.",
        ],
        "loss":    [
            "GG, era el karma.",
            "KSJSKAJAJAJAJ así es la vida 💔🥀.",
            "va, es el karma por traicionarme antes.",
        ],
        "social":  [
            "va, dropeen lo que quieran, yo me adapto.",
            "KSJSKAJAJAJAJ este drama es peak.",
            "ami me da igual, pero lo dices feo mano.",
        ],
    },
    "XOKRAM": {
        "calm":    [
            "mano, todo en orden. sisis.",
            "ah ya, aquí se puede negociar.",
            "waos, ambiente tranqui.",
            "aver, qué tenemos pa' intercambiar.",
        ],
        "tense":   [
            "mano xd esto se puso feo.",
            "sisis, pero con cuidado.",
            "lptm, esto no me lo esperaba.",
            "aver, respiremos y negociamos.",
        ],
        "horror":  [
            "LPTM mano esto está salvaje.",
            "waos, aquí se muere alguien.",
            "xd ni para negociar da tiempo.",
            "ah ya, el pacto salió caro.",
        ],
        "awe":     [
            "mano esto se ve metaplayer.",
            "waos, ¡qué buen trato!.",
            "sisis, esto lo cambio por lo que sea.",
            "ah ya, aquí vale la pena pullear.",
        ],
        "discovery": [
            "aver, cuánto pide por esto.",
            "mano, este objeto tiene valor.",
            "sisis, esto lo guardo para después.",
            "waos, contrato cerrado.",
        ],
        "loss":    [
            "gg, el contrato se rompió.",
            "lptm, perdimos margen.",
            "ah ya, fue mala inversión.",
        ],
        "social":  [
            "mano, hablemos de negocios.",
            "sisis, todo se puede negociar.",
            "aver, qué ofrecen y qué quieren.",
        ],
    },
    "DARAZIEL": {
        "calm":    [
            "mano, este lugar tiene buen diseño.",
            "es que, obviamente, aquí hay un patrón.",
            "observen la simetría, es pije.",
            "pero fíjense en los ángulos, son god.",
        ],
        "tense":   [
            "mano, la geometría está rota, eso no es bueno.",
            "es que, esto no cuadra con lo anterior.",
            "obviamente alguien movió las piedras.",
            "pero esto es imposible, y sin embargo.",
        ],
        "horror":  [
            "mano esto rompe las reglas del espacio.",
            "obviamente no deberíamos estar aquí.",
            "pero el ángulo no existe en 3D mano.",
            "es que, slay, pero hay que salir.",
        ],
        "awe":     [
            "mano, esto es arquitectura god.",
            "es que, obviamente, esto lo diseñó alguien.",
            "pero miren las proporciones, es divino.",
            "slay total, yo me quedo viendo esto.",
        ],
        "discovery": [
            "mano, hay un patrón en todo esto.",
            "es que, obviamente, esto conecta con aquello.",
            "pero miren, la ruta oculta estaba acá.",
            "dibujé un mapa mental y ya tiene sentido.",
        ],
        "loss":    [
            "mano, perdí el plano por esto.",
            "es que, obviamente, iba a salir mal.",
            "slay, pero duele.",
        ],
        "social":  [
            "mano ustedes no ven el mapa completo.",
            "es que, obviamente, hay que coordinar.",
            "pero si me oyeran, estaríamos mejor.",
        ],
    },
}


# Frases que el personaje dice al USAR su habilidad (UI feedback).
# ─── Sistema de pasivas ──────────────────────────────────────────────────────
# Las pasivas NO son botones. Modifican la experiencia en cada transición y
# cada render: revelan información, reducen pérdidas, abren opciones ocultas.

PASSIVE_META: Dict[str, Dict[str, Any]] = {
    "ARIS": {
        "name": "Ojo del Patrón",
        "short": "Lees lo que no debería leerse. Cada lectura te marca.",
        "effects": [
            "Ves las pistas ocultas (ability_hints) de cada nodo.",
            "COSTO: cada nodo nuevo con una pista leída suma +1 CORRUPCIÓN — entender es mancharse.",
            "No puedes 'no ver'. Lo que lees se queda.",
        ],
    },
    "LAW": {
        "name": "Oído Interior",
        "short": "Escuchas lo que los nodos cantan. Cantar devuelve cosas, pero se lleva otras.",
        "effects": [
            "En nodos con NPC hostil o texto de música/canto: +3 LUCIDEZ al entrar.",
            "COSTO: cada nodo donde el oído se 'activa' te cuesta −1 MEMORIA — la canción saca algo de ti.",
            "Las canciones viejas, al sonar, borran otras.",
        ],
    },
    "HARU": {
        "name": "Risa Absurda",
        "short": "El horror te hace reír. Los finales limpios se te cierran.",
        "effects": [
            "En nodos de tono 'horror': +2 LORE al entrar — entiendes el chiste cósmico.",
            "COSTO: no puedes usar rutas de estilo 'success' en nodos 'horror'. La risa te aleja del camino noble.",
            "La risa es, en el fondo, su propia forma de corrupción.",
        ],
    },
    "ELYKO": {
        "name": "Cálculo Perpetuo",
        "short": "Memorizas lo que viste. No funcionas sin datos previos.",
        "effects": [
            "Al pisar un nodo por 2ª vez: ves exactamente qué efectos tuvieron tus últimas elecciones.",
            "COSTO: primer visita a cualquier nodo no te da información; solo memoria (−1 MEMORIA).",
            "Sin memoria previa, estás ciego.",
        ],
    },
    "XOFT": {
        "name": "Boca Rota",
        "short": "Las máscaras se caen cuando te oyen entrar.",
        "effects": [
            "En nodos con NPC: aparece '🩸 Provocar a {npc}' como opción.",
            "La máscara del NPC revela su intención (ability_hints.XOFT).",
            "Trust ±2 según sea aliado u hostil. Provocar aliados duele más tarde.",
        ],
    },
    "XOKRAM": {
        "name": "Ojo del Mercader",
        "short": "Todo tiene precio. Todo lo que cargas cuenta.",
        "effects": [
            "+2 slots de inventario adicionales.",
            "Auto-trade: si entras a un nodo con 'trade' y tienes el item 'wants', se ejecuta solo.",
            "El ojo del mercader nunca deja de tasar — incluso a los dioses.",
        ],
    },
    "DARAZIEL": {
        "name": "Mapa Interior",
        "short": "Ves los planos que otros no ven. Mirarlos duele.",
        "effects": [
            "Todas las hidden_paths son visibles siempre.",
            "COSTO: al entrar a un nodo con rutas ocultas, −2 LUCIDEZ (ver el plano entero cuesta).",
            "+2 LORE cada nodo nuevo, pero −1 MEMORIA (memorizar la geometría desplaza otras memorias).",
        ],
    },
}


# ─── Constantes de motor ─────────────────────────────────────────────────────

STATS: Tuple[str, ...] = ("voluntad", "lucidez", "favor", "corrupcion", "lore", "memoria")
STAT_EMOJI: Dict[str, str] = {
    "voluntad":   "🛡️",
    "lucidez":    "🧠",
    "favor":      "🌟",
    "corrupcion": "👁️",
    "lore":       "📜",
    "memoria":    "🪞",
}
STAT_NAMES_ES: Dict[str, str] = {
    "voluntad":   "Voluntad",
    "lucidez":    "Lucidez",
    "favor":      "Favor",
    "corrupcion": "Corrupción",
    "lore":       "Lore",
    "memoria":    "Memoria",
}


# ─── GameState ───────────────────────────────────────────────────────────────

@dataclass
class GameState:
    # Identidad
    user_id: int
    character_id: str

    # Navegación
    current_node: str = "prologo_despertar"
    zone: str = "El Umbral del Sueño"
    act: int = 1

    # Stats (0-100)
    voluntad: int = 50
    lucidez: int = 50
    favor: int = 40
    corrupcion: int = 25
    lore: int = 40
    memoria: int = 60

    # Inventario
    inventory: List[str] = field(default_factory=list)
    item_slots: int = 6

    # Progresión
    visited: List[str] = field(default_factory=list)
    visit_counts: Dict[str, int] = field(default_factory=dict)
    applied_on_enter: Set[str] = field(default_factory=set)  # anti-farm: solo primera visita
    flags: Set[str] = field(default_factory=set)
    turns_played: int = 0

    # Relaciones NPC
    npc_trust: Dict[str, int] = field(default_factory=dict)

    # Contratos (específicos de XOKRAM para ending_gran_negocio)
    contracts_closed: List[str] = field(default_factory=list)

    # Arquetipo destilado del jugador real (lovecraftian_survivor). Si no hay
    # perfil disponible, se deja como None y las condiciones player_archetype
    # siempre fallan. Es un campo estático por partida (no cambia).
    player_archetype: Optional[str] = None

    # ─── Factory ─────────────────────────────────────────────────────────

    @classmethod
    def create(cls, user_id: int, character_id: str) -> "GameState":
        cid = character_id.upper()
        if cid not in CHARACTER_DATA:
            raise ValueError(
                f"Arquetipo desconocido: {character_id}. "
                f"Elige entre: {list(CHARACTER_DATA.keys())}"
            )
        data = CHARACTER_DATA[cid]
        bs = data["base_stats"]
        # XOKRAM: pasiva +2 slots
        slots = data["item_slots"] + (2 if cid == "XOKRAM" else 0)
        return cls(
            user_id=user_id,
            character_id=cid,
            voluntad=bs["voluntad"],
            lucidez=bs["lucidez"],
            favor=bs["favor"],
            corrupcion=bs["corrupcion"],
            lore=bs["lore"],
            memoria=bs["memoria"],
            item_slots=slots,
        )

    # ─── Serialización ───────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "character_id": self.character_id,
            "current_node": self.current_node,
            "zone": self.zone,
            "act": self.act,
            "voluntad": self.voluntad,
            "lucidez": self.lucidez,
            "favor": self.favor,
            "corrupcion": self.corrupcion,
            "lore": self.lore,
            "memoria": self.memoria,
            "inventory": self.inventory,
            "item_slots": self.item_slots,
            "visited": self.visited,
            "visit_counts": self.visit_counts,
            "applied_on_enter": sorted(self.applied_on_enter),
            "flags": sorted(self.flags),
            "turns_played": self.turns_played,
            "npc_trust": self.npc_trust,
            "contracts_closed": self.contracts_closed,
            "player_archetype": self.player_archetype,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameState":
        return cls(
            user_id=int(d["user_id"]),
            character_id=d.get("character_id", "ARIS"),
            current_node=d.get("current_node", "prologo_despertar"),
            zone=d.get("zone", "El Umbral del Sueño"),
            act=int(d.get("act", 1)),
            voluntad=int(d.get("voluntad", 50)),
            lucidez=int(d.get("lucidez", 50)),
            favor=int(d.get("favor", 40)),
            corrupcion=int(d.get("corrupcion", 25)),
            lore=int(d.get("lore", 40)),
            memoria=int(d.get("memoria", 60)),
            inventory=list(d.get("inventory", [])),
            item_slots=int(d.get("item_slots", 6)),
            visited=list(d.get("visited", [])),
            visit_counts=dict(d.get("visit_counts", {})),
            applied_on_enter=set(d.get("applied_on_enter", [])),
            flags=set(d.get("flags", [])),
            turns_played=int(d.get("turns_played", 0)),
            npc_trust=dict(d.get("npc_trust", {})),
            contracts_closed=list(d.get("contracts_closed", [])),
            player_archetype=d.get("player_archetype"),
        )

    # ─── Stat helpers ────────────────────────────────────────────────────

    def apply_effects(self, effects: Dict[str, int]) -> Dict[str, int]:
        """Aplica deltas a stats (clamped 0-100) y devuelve los deltas efectivos.

        Las pasivas NO reducen pérdidas — son profundidad narrativa, no modo fácil.
        El único modificador aquí es el '_style' que se descarta; los costos y
        bonificaciones por pasiva se aplican en apply_passives_on_node.
        """
        applied: Dict[str, int] = {}
        for stat in STATS:
            delta = int(effects.get(stat, 0))
            if delta == 0:
                continue
            before = getattr(self, stat)
            after = max(0, min(100, before + delta))
            setattr(self, stat, after)
            applied[stat] = after - before
        return applied

    def apply_on_enter_once(self, node_id: str, on_enter: Dict[str, int],
                            style: Optional[str] = None) -> Dict[str, int]:
        """Aplica on_enter SOLO si es la primera vez en el nodo. Devuelve deltas efectivos."""
        if node_id in self.applied_on_enter:
            return {}
        self.applied_on_enter.add(node_id)
        if not on_enter:
            return {}
        eff = dict(on_enter)
        if style:
            eff["_style"] = style
        return self.apply_effects(eff)

    def apply_passives_on_node(self, node: Dict[str, Any]) -> Dict[str, int]:
        """Aplica pasivas del personaje al ENTRAR al nodo (solo primera visita).

        Las pasivas son TRADE-OFFS narrativos: cada una abre algo y cobra algo.
        No reducen pérdidas ni hacen el juego más fácil — profundizan la historia.
        """
        nid = node.get("id") or node.get("_id") or self.current_node
        passive_tag = f"passive:{nid}"
        if passive_tag in self.flags:
            return {}
        self.flags.add(passive_tag)

        cid = self.character_id
        text = (node.get("text") or "").lower()
        deltas: Dict[str, int] = {}

        if cid == "ARIS":
            # Leer pistas ocultas mancha. Cada nodo con ability_hints suma +1 CORRUPCION
            # porque entender lo que no deberías entender tiene precio.
            hints = node.get("ability_hints", {}) or {}
            if hints.get("ARIS") or hints.get("lectura"):
                deltas = self.apply_effects({"corrupcion": +1})

        elif cid == "LAW":
            # La música protege, pero cantar saca algo de ti.
            has_music = any(kw in text for kw in (
                "cant", "melodía", "melodia", "música", "musica",
                "himno", "aria", "coro"))
            hostile = node.get("hostile_npc")
            if has_music or hostile:
                deltas = self.apply_effects({"lucidez": +3, "memoria": -1})

        elif cid == "HARU":
            # El horror te hace reír = entiendes el chiste cósmico = +LORE.
            # Pero la risa cierra las rutas 'success' en horror (eso se resuelve
            # en el cog al filtrar paths).
            if node.get("tone") == "horror":
                deltas = self.apply_effects({"lore": +2})

        elif cid == "ELYKO":
            # Primera visita: memorizas, pero no sabes nada aún. Costo: -1 MEMORIA.
            # Segunda visita en adelante: ves el resultado de la vez pasada
            # (se renderiza en el cog usando visit_counts).
            visits = self.visit_counts.get(nid, 0)
            if visits <= 1:  # primera visita efectiva
                deltas = self.apply_effects({"memoria": -1})

        elif cid == "XOKRAM":
            # Auto-trade sigue como está: ejecuta si tienes el 'wants'
            trade = node.get("trade") or {}
            wants = trade.get("wants")
            gives = trade.get("gives")
            if wants and gives and wants in self.inventory:
                self.take_item(wants)
                self.give_item(gives)

        elif cid == "DARAZIEL":
            # Ver la geometría duele. Si el nodo tiene hidden_paths, -2 LUCIDEZ.
            # En cada nodo nuevo: +2 LORE -1 MEMORIA (memorizar desplaza memorias).
            eff = {"lore": +2, "memoria": -1}
            if node.get("hidden_paths"):
                eff["lucidez"] = -2
            deltas = self.apply_effects(eff)

        # XOFT no tiene pasiva on-enter; su pasiva es la opción de Provocar en el cog.
        return deltas

    def has_lore_discount(self) -> int:
        """Ya no hay descuento: era modo fácil. Devuelve 0 siempre (legado)."""
        return 0

    def can_take_success_in_horror(self, node: Dict[str, Any]) -> bool:
        """HARU: no puede elegir rutas 'success' en nodos de tono 'horror'.
        La risa le aleja del camino noble. Otros personajes pueden siempre."""
        if self.character_id != "HARU":
            return True
        return node.get("tone") != "horror"

    def add_flag(self, flag: str) -> None:
        """Añade un flag. Si está en EXCLUSIVE_FLAGS, limpia los incompatibles."""
        self.flags.add(flag)
        # Exclusión mutua: comprometerse con uno cierra las puertas de los otros
        for excluded in EXCLUSIVE_FLAGS.get(flag, []):
            self.flags.discard(excluded)

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags

    def is_ending_locked(self, ending_id: str) -> bool:
        """True si el ending fue bloqueado por algún flag de ENDING_LOCKS."""
        for blocker in ENDING_LOCKS.get(ending_id, []):
            if blocker in self.flags:
                return True
        return False

    def process_thresholds(self) -> List[Dict[str, Any]]:
        """Chequea umbrales de insight (LORE) y corrupción. Aplica costos y
        devuelve lista de eventos narrativos nuevos (uno por cada umbral cruzado
        en esta transición).

        Nota: solo se dispara UNA VEZ por umbral (lo marca con flag). No drena
        por tiempo.
        """
        events: List[Dict[str, Any]] = []

        # Insight (LORE)
        for th in INSIGHT_THRESHOLDS:
            if self.lore >= th["lore"] and th["flag"] not in self.flags:
                self.flags.add(th["flag"])
                self.apply_effects(th["cost"])
                events.append({
                    "type": "insight",
                    "threshold": th["lore"],
                    "title": th["title"],
                    "narrative": th["narrative"],
                    "cost": th["cost"],
                })

        # Corrupción
        for th in CORRUPTION_THRESHOLDS:
            if self.corrupcion >= th["corrupcion"] and th["flag"] not in self.flags:
                self.flags.add(th["flag"])
                self.apply_effects(th["cost"])
                for npc, delta in (th.get("npc_trust_shifts") or {}).items():
                    self.modify_npc_trust(npc, int(delta))
                events.append({
                    "type": "corruption",
                    "threshold": th["corrupcion"],
                    "title": th["title"],
                    "narrative": th["narrative"],
                    "cost": th["cost"],
                })

        return events

    def give_item(self, item: str) -> bool:
        if not item or item in self.inventory:
            return False
        if len(self.inventory) >= self.item_slots:
            return False
        self.inventory.append(item)
        return True

    def take_item(self, item: str) -> bool:
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False

    def modify_npc_trust(self, npc: str, delta: int) -> int:
        cur = self.npc_trust.get(npc, 0)
        new_val = max(-100, min(100, cur + delta))
        self.npc_trust[npc] = new_val
        return new_val

    def add_contract(self, contract: str) -> None:
        if contract and contract not in self.contracts_closed:
            self.contracts_closed.append(contract)

    # ─── Condiciones de rutas ────────────────────────────────────────────

    def meets_conditions(self, conditions: Optional[Dict[str, Any]]) -> bool:
        """Evalúa condiciones de visibilidad/habilitación de una ruta.

        Tipos soportados:
        - {stat}_min / {stat}_max para cada stat en STATS
        - has_item: str | List[str]           → requiere tener todos
        - lacks_item: str | List[str]         → requiere no tener ninguno
        - has_flag: str | List[str]           → requiere tener todas
        - lacks_flag: str | List[str]         → requiere no tener ninguna
        - npc_trust: {npc_id: min_trust}      → requiere confianza mínima
        - character_in: List[str]             → requiere personaje actual
        - class_in: List[str]                 → requiere clase actual
        - act_min / act_max                   → gating por acto
        - min_contracts: int                  → para XOKRAM
        """
        if not conditions:
            return True

        def _as_list(v: Any) -> List[str]:
            if v is None:
                return []
            if isinstance(v, str):
                return [v]
            return list(v)

        for stat in STATS:
            mn = conditions.get(f"{stat}_min")
            mx = conditions.get(f"{stat}_max")
            cur = getattr(self, stat)
            # ARIS: descuento de 10 en umbrales de lore
            if stat == "lore" and mn is not None:
                mn = max(0, int(mn) - self.has_lore_discount())
            if mn is not None and cur < int(mn):
                return False
            if mx is not None and cur > int(mx):
                return False

        act_min = conditions.get("act_min")
        act_max = conditions.get("act_max")
        if act_min is not None and self.act < int(act_min):
            return False
        if act_max is not None and self.act > int(act_max):
            return False

        for it in _as_list(conditions.get("has_item")):
            if it not in self.inventory:
                return False
        for it in _as_list(conditions.get("lacks_item")):
            if it in self.inventory:
                return False
        for fl in _as_list(conditions.get("has_flag")):
            if fl not in self.flags:
                return False
        for fl in _as_list(conditions.get("lacks_flag")):
            if fl in self.flags:
                return False

        trust = conditions.get("npc_trust") or {}
        if isinstance(trust, dict):
            for npc, min_t in trust.items():
                if self.npc_trust.get(npc, 0) < int(min_t):
                    return False

        char_in = conditions.get("character_in")
        if char_in and self.character_id not in [c.upper() for c in char_in]:
            return False

        class_in = conditions.get("class_in")
        if class_in:
            my_class = CHARACTER_DATA[self.character_id]["class"]
            if my_class not in [c.upper() for c in class_in]:
                return False

        min_contracts = conditions.get("min_contracts")
        if min_contracts is not None and len(self.contracts_closed) < int(min_contracts):
            return False

        # Arquetipo destilado del jugador real (sin tildes, upper). Puede ser:
        # - string único: "PROVOCADOR"  (match si contiene)
        # - lista:        ["PROVOCADOR", "CAOTICO"]  (match si alguno contiene)
        pa = conditions.get("player_archetype")
        if pa:
            if not self.player_archetype:
                return False
            targets = [pa] if isinstance(pa, str) else list(pa)
            hay = self.player_archetype.upper()
            # Normalizar sin tildes
            hay = (hay.replace("Á","A").replace("É","E").replace("Í","I")
                      .replace("Ó","O").replace("Ú","U"))
            if not any(t.upper() in hay for t in targets):
                return False

        return True

    # ─── Habilidad ───────────────────────────────────────────────────────

    # ─── Turno ───────────────────────────────────────────────────────────

    def advance_turn(self, node_id: str) -> None:
        self.turns_played += 1
        self.current_node = node_id
        if node_id not in self.visited:
            self.visited.append(node_id)
        self.visit_counts[node_id] = self.visit_counts.get(node_id, 0) + 1

    # ─── Evaluación de finales ───────────────────────────────────────────

    def ending_priority_list(self, world: Dict[str, Any]) -> List[str]:
        """Devuelve los endings cuyos prerequisitos cumple el jugador Y que no
        estén bloqueados por ENDING_LOCKS, en orden de prioridad."""
        candidates = []
        for nid, node in world.items():
            if not node.get("is_ending"):
                continue
            if self.is_ending_locked(nid):
                continue
            reqs = node.get("ending_requires") or {}
            if self.meets_conditions(reqs):
                priority = node.get("ending_priority", 50)
                candidates.append((priority, nid))
        candidates.sort(reverse=True)
        return [nid for _, nid in candidates]


# ─── Selección determinista de frase de voz ──────────────────────────────────

def pick_voice_line(character_id: str, node_id: str, tag: str = "calm") -> str:
    """Devuelve una frase de voz para `character_id` en `node_id` usando el tag.

    Es determinista: el mismo (node_id, character_id, tag) produce siempre
    la misma frase, pero el hash garantiza variedad entre nodos.
    """
    templates = VOICE_TEMPLATES.get(character_id.upper(), {})
    bank = templates.get(tag) or templates.get("calm") or ["..."]
    if not bank:
        return "..."
    seed = f"{character_id}|{node_id}|{tag}".encode("utf-8")
    idx = int(hashlib.md5(seed).hexdigest(), 16) % len(bank)
    return bank[idx]

# ─── Pequeño helper: narrador determinista del estado emocional ──────────────

def state_tag(state: GameState) -> str:
    """Devuelve un tag emocional en función del estado actual del jugador.

    No es combate: solo modula el tono de las frases de voz del personaje
    (calm/tense/horror/awe/loss/discovery).
    """
    if state.voluntad <= 20 or state.lucidez <= 20:
        return "horror"
    if state.corrupcion >= 70:
        return "horror"
    if state.lucidez <= 40 or state.voluntad <= 40:
        return "tense"
    if state.favor >= 70 or state.lore >= 75:
        return "awe"
    return "calm"


# ─── Umbrales de Insight (LORE) y Corrupción ─────────────────────────────────
# Al cruzar cada umbral, se aplica un costo PERMANENTE + se setea un flag. Es un
# evento narrativo único (no se repite ni drena por tiempo). El objetivo es que
# el conocimiento cósmico pese: saber más duele, corromperte más te aísla.

INSIGHT_THRESHOLDS: List[Dict[str, Any]] = [
    {
        "lore": 30, "flag": "insight_I_velos",
        "title": "🌑 Primer Velo Descorrido",
        "narrative": (
            "Empiezas a notar cosas raras en los márgenes de la visión. "
            "Las sombras de la gente no siempre coinciden con sus cuerpos."
        ),
        "cost": {"lucidez": -6, "favor": -3},
    },
    {
        "lore": 50, "flag": "insight_II_susurros",
        "title": "🗣️ Susurros en la Vigilia",
        "narrative": (
            "Oyes murmullos cuando no hay nadie. A veces contestan a lo que "
            "estás pensando. La MEMORIA se hace frágil — tu mente se ajusta "
            "al horror y pierde plasticidad."
        ),
        "cost": {"memoria": -10, "favor": -5, "corrupcion": +4},
    },
    {
        "lore": 70, "flag": "insight_III_espejo",
        "title": "🪞 En Cada Espejo, No Estás Solo",
        "narrative": (
            "En todo reflejo hay una figura que te saluda con educación. "
            "Nyarlathotep te ha notado."
        ),
        "cost": {"memoria": -10, "corrupcion": +10, "voluntad": -3},
    },
    {
        "lore": 85, "flag": "insight_IV_desanclado",
        "title": "🕳️ Desanclado",
        "narrative": (
            "Ya no distingues bien si sigues soñando o si alguien está "
            "soñándote. La MEMORIA se desprende de ti como una piel seca."
        ),
        "cost": {"memoria": -15, "corrupcion": +8, "favor": -8},
    },
]

CORRUPTION_THRESHOLDS: List[Dict[str, Any]] = [
    {
        "corrupcion": 50, "flag": "taint_I_marcado",
        "title": "👁️ Marcado por el Caos",
        "narrative": (
            "Los gatos de Ulthar dejan de saludarte con cariño. Los ghouls, "
            "en cambio, asienten al verte pasar."
        ),
        "cost": {"favor": -8},
        "npc_trust_shifts": {"gato_ulthar": -15, "consejo_gatos": -15, "ghouls": +10},
    },
    {
        "corrupcion": 70, "flag": "taint_II_abandonado",
        "title": "🌑 Abandonado por los Blandos",
        "narrative": (
            "Los Dioses Blandos ya no escuchan tus rezos. Pero hay otras "
            "cosas que sí, y están más cerca de lo que crees."
        ),
        "cost": {"favor": -15, "memoria": -5},
        "npc_trust_shifts": {"kuranes": -20, "nasht_kaman_thah": -25},
    },
    {
        "corrupcion": 85, "flag": "taint_III_corteja",
        "title": "💀 El Caos te Corteja",
        "narrative": (
            "Nyarlathotep te llama por tu nombre despierto. Saber que lo "
            "sabe duele más que nada que hayas sentido."
        ),
        "cost": {"favor": -10, "voluntad": -5, "lucidez": -8},
    },
]


# ─── Flags exclusivos: comprometerse con uno cierra los otros ────────────────
# Clave: flag que se activa. Valor: lista de flags incompatibles que se LIMPIAN.
# Esto modela los "thought commitments": cuando te comprometes con algo, ciertas
# otras opciones quedan literalmente cerradas en tu save.

EXCLUSIVE_FLAGS: Dict[str, List[str]] = {
    # Pacto con ghouls cierra todas las líneas de "amistad Ulthar"
    "pacto_ghoul": [
        "bendicion_ulthar", "gato_ulthar_aliado", "gatos_deben_favor",
        "advertido_por_gatos",
    ],
    # Fruto prohibido de los zoogs quema los puentes con los gatos
    "pacto_zoog_oscuro": [
        "bendicion_ulthar", "gato_ulthar_aliado", "gatos_deben_favor",
    ],
    # Aceptar la máscara del sacerdote cierra el test del anciano
    "tomo_mascara_caos": [
        "rechazo_mascara", "nyarlathotep_te_respeta", "canto_al_sacerdote",
    ],
    # Rechazar la máscara cierra la sumisión al Caos
    "rechazo_mascara": [
        "tomo_mascara_caos", "acepto_trono_caos", "nyarlathotep_te_odia",
    ],
    # Aceptar trono del caos cierra todo lo puro
    "acepto_trono_caos": [
        "test_nyar_pasado", "aliado_kuranes", "bendicion_ulthar",
    ],
    # Esclavitud Leng te deja sin Dioses Blandos
    "fue_esclavo_leng": [
        "aliado_kuranes", "bendicion_ulthar",
    ],
    # Dar nombre al umbral te roba memoria de aliados
    "dio_nombre_a_umbral": [
        "gatos_deben_favor",
    ],
}


# ─── Endings bloqueables por flags ───────────────────────────────────────────
# Si el jugador tiene CUALQUIERA de estos flags, el ending correspondiente se
# considera no alcanzable (se filtrará del priority_list).

ENDING_LOCKS: Dict[str, List[str]] = {
    "ending_despertar_puro":      ["pacto_ghoul", "pacto_zoog_oscuro", "tomo_mascara_caos",
                                    "acepto_trono_caos", "fue_esclavo_leng"],
    "ending_carcajada_cosmica":   ["acepto_trono_caos", "tomo_mascara_caos",
                                    "taint_II_abandonado"],
    "ending_canto_final":         ["acepto_trono_caos", "tomo_mascara_caos",
                                    "pacto_zoog_oscuro"],
    "ending_biblioteca_eterna":   ["acepto_trono_caos", "pacto_zoog_oscuro"],
    "ending_arquitectura":        ["acepto_trono_caos"],
    "ending_legado_onirico":      [],  # cualquier jugador puede quedarse
    "ending_pacto_mercantil":     ["acepto_trono_caos"],
    "ending_rey_ghouls":          ["rechazo_mascara"],  # si rechazaste, los ghouls no te ungirán
    "ending_gran_negocio":        [],
    "ending_trono_caos":          [],  # siempre accesible si cumples prereqs
    "ending_olvido":              [],
    "ending_vacio":               [],
}


# ─── Directorio de personas destiladas del servidor ──────────────────────────
# Cada entrada describe un usuario real del server con su perfil-resumen. El
# motor lo usa para:
# - inyectar reacciones de NPCs basadas en el perfil del jugador real
# - aparecer como NPCs dentro del mundo (JC, Aria, Papu, etc.)

# ID → meta. Los folders de data/personas usan nombres mixtos (con caracteres),
# así que mantenemos una tabla canon para lookup rápido.
# Los datos completos se cargan lazy desde data/personas/<id> - <nombre>/agente_core.json.

PERSONA_DIR_MAP: Dict[int, str] = {
    239550977638793217:  "239550977638793217 - Aris",
    747920937260679269:  "747920937260679269 - Xoft Piece",
    1465595293792993402: "1465595293792993402 - Xokram",
    743759722141974559:  "743759722141974559 - Daraziel",
    666446833220059156:  "666446833220059156 - Karu (Tupu)",
    1329862951552815265: "1329862951552815265 - Papu",
    793224582147342336:  "793224582147342336 - gab",
    903443370477776956:  "903443370477776956 - jcmaster27",
}


# NPCs del servidor — tienen presencia narrativa dentro del mundo. Estos son
# sus "arquetipos de sueño" (cómo aparecen al jugador, no su yo despierto).
SERVER_NPCS: Dict[str, Dict[str, Any]] = {
    "jc_anciano_un_ojo": {
        "id": "jc_anciano_un_ojo",
        "real_user_id": 903443370477776956,
        "real_name": "jcmaster27",
        "dream_title": "El Anciano de Un Ojo",
        "description": (
            "Un ermitaño de un solo ojo que vive en una choza a mitad del "
            "Monte Throk. El otro ojo, dicen, se lo sacó él mismo para "
            "dejar de ver lo que no se debe ver."
        ),
        "voice_samples": [
            "A ver, XDD, deja ver esta vaina con el ojo bueno.",
            "Simon, lo que buscas está arriba. Pero te va a doler.",
            "Está muy goddddd el problema tuyo, pero tiene solución.",
        ],
    },
    "aria_tejedora": {
        "id": "aria_tejedora",
        "real_user_id": 948469943677104138,
        "real_name": "aria",
        "dream_title": "La Tejedora de Celephaïs",
        "description": (
            "Una mujer joven que teje sueños en un telar hecho de hilos que "
            "nunca estuvieron. Si te teje un paño, no lo pierdas."
        ),
        "voice_samples": [
            "Quédate un momento. No tienes que hablar.",
            "Llevé un hilo de tu vida despierta al telar. Espero que no te moleste.",
        ],
    },
    "neruson_el_chismoso": {
        "id": "neruson_el_chismoso",
        "real_user_id": 923305311954157608,
        "real_name": "neruson",
        "dream_title": "Neruson el Chismoso del Puerto",
        "description": (
            "Un hombre pequeño y sonriente que sabe todo lo que pasa en los "
            "muelles de Dylath-Leen porque su trabajo es saberlo. Se entera "
            "incluso antes de que pase."
        ),
        "voice_samples": [
            "Oye, te cuento algo: el capitán miente con la ruta. Anda con cuidado.",
            "Ya sé lo que vienes a preguntar. Vale una moneda onírica.",
        ],
    },
    "papu_el_relajado": {
        "id": "papu_el_relajado",
        "real_user_id": 1329862951552815265,
        "real_name": "Papu",
        "dream_title": "Papu — Subastador de la Élite Cultista",
        "description": (
            "Un hombre rechoncho que ronca sobre una losa de Sarkomand y "
            "solo abre un ojo cuando se acerca un cliente. Detrás de esa "
            "fachada perezosa hay una de las figuras más podridas del "
            "círculo cultista: miembro de la Élite, socio de los Hombres "
            "de Leng, anfitrión de una mansión privada en una isla que "
            "no está en ningún mapa. Ahí subasta soñadores jóvenes — "
            "sombras oníricas aún no formadas — a clientes cuyo nombre "
            "no deberías pronunciar. Sus rituales personales se cuentan "
            "en voz baja. Firmó pacto directo con alguien que sueña a "
            "Azathoth. Cobra en gifs, en monedas oníricas y en cosas peores."
        ),
        "voice_samples": [
            "mano, sisis, pasa. tengo producto. no preguntes de dónde.",
            "ah ya, me pides un tamañito especial. dame 10 y prendo la inspección, xd.",
            "waos, lptm, ese lote salió caro. pero pagas y no haces preguntas, sisis.",
            "gg mano, esa carga no iba a aguantar tres lunas. back al carro.",
            "ah ya, cliente VIP. los de la élite pagan doble. sisis.",
            "mano, la subasta de esta luna va a estar peak. metaplayer total.",
        ],
    },
    "gab_el_primero": {
        "id": "gab_el_primero",
        "real_user_id": 793224582147342336,
        "real_name": "gab",
        "dream_title": "Gab el Primero en Llegar",
        "description": (
            "Un soñador eterno que jura que llegó a los Yermos ANTES que "
            "tú. Se ofende fácil. Pero sabe atajos."
        ),
        "voice_samples": [
            "MANO YO LLEGUÉ PRIMERO A ESTE LUGAR XDDDDDDDDDDDD.",
            "oe, lpm, tú ni siquiera estabas aquí cuando yo ya vivía acá, jajaja.",
        ],
    },
    "xokram_sombra": {
        "id": "xokram_sombra",
        "real_user_id": 1465595293792993402,
        "real_name": "xokram",
        "dream_title": "La Sombra Contrabandista",
        "description": (
            "Un vendedor ambulante que puede ser tú mismo en otro sueño, "
            "o puede ser Xokram, que también sueña. Aparece en los "
            "márgenes de las ciudades oníricas."
        ),
        "voice_samples": [
            "sisis, contrato? trae algo de valor.",
            "waos mano, te veo caminando como si supieras. lo dudo.",
        ],
    },
}


def get_server_npc(npc_id: str) -> Optional[Dict[str, Any]]:
    return SERVER_NPCS.get(npc_id)


# ═════════════════════════════════════════════════════════════════════════════
# PROFUNDIZACIÓN — Capas narrativas sobre los sistemas existentes
# ═════════════════════════════════════════════════════════════════════════════

# ─── ITEM_LORE: cada objeto tiene microhistoria ──────────────────────────────
# Lección Bloodborne: los items cuentan lore. Se muestran al ver /aventura estado.

ITEM_LORE: Dict[str, Dict[str, str]] = {
    "fragmento_glifo": {
        "name": "Fragmento de Glifo",
        "short": "Pesa menos de lo que parece.",
        "lore": "Trozo de inscripción pre-cuneiforme. Si lo miras desde el ángulo correcto, la palabra cambia — dicen que es 'SIETE', o 'BARZAI', o un tercer nombre que no deberías saber aún.",
    },
    "bigote_gato_ulthar": {
        "name": "Bigote del Gato de Ulthar",
        "short": "Aún huele a leche tibia.",
        "lore": "Ese gato tenía un nombre. Lo sabía cuando te lo dio. Tú no. Los gatos de Ulthar solo regalan bigotes a los que reconocen de otras vidas.",
    },
    "bendicion_gato": {
        "name": "Bendición Felina",
        "short": "Un ronroneo que no termina.",
        "lore": "Los Dioses Blandos escuchan a quien carga esta bendición. Pero también Nyarlathotep — y él escucha más atentamente a los que los dioses oyen.",
    },
    "bigote_dorado": {
        "name": "Bigote Dorado del Gato Mayor",
        "short": "Pesa como una promesa antigua.",
        "lore": "Solo se dan a los que salvaron a los gatos de una traición. En Ulthar, es tratado como reliquia. En el resto del sueño, como arma.",
    },
    "fruto_lunar": {
        "name": "Fruto Lunar",
        "short": "Cambia de sabor según quién lo sostiene.",
        "lore": "Los zoogs lo dan solo a aquellos que prometen recordarlos en el Trono. Comerlo olvida. No comerlo pero guardarlo, recuerda — aunque no sepas por qué.",
    },
    "fruto_prohibido": {
        "name": "Fruto Prohibido",
        "short": "Pesa más cada vez que lo tocas.",
        "lore": "Quien lo come olvida tres veces lo que quiso olvidar una, y recuerda mil veces lo que quiso recordar una. Los gatos saben quién te lo dio. Siempre saben.",
    },
    "moneda_onirica": {
        "name": "Moneda Onírica",
        "short": "No pesa, pero ocupa espacio real.",
        "lore": "En Celephaïs pagan con recuerdos. Esta es un recuerdo que alguien tasó en cantidad redonda — tuyo, ajeno, ya no importa.",
    },
    "rubi_leng": {
        "name": "Rubí de Leng",
        "short": "Brilla con luz que no viene del sol.",
        "lore": "Los Hombres de Leng los fabrican con la angustia de los esclavos soñados. Cada rubí es un grito comprimido hasta ser bello.",
    },
    "hierba_ulthar": {
        "name": "Hierba de Ulthar",
        "short": "Huele a jardín imposible.",
        "lore": "Crece sola donde los gatos duermen en grupo. Los Hombres de Leng no pueden tocarla; les quema la piel gris.",
    },
    "nota_precio_leng": {
        "name": "Nota de Precio",
        "short": "Tu nombre despierto y una cifra.",
        "lore": "Cuanto te tasaron en el mercado oculto del barco negro. La cifra es humillantemente pequeña o alarmantemente grande, según quién la lea.",
    },
    "sello_kuranes": {
        "name": "Sello de Kuranes",
        "short": "Cera azul con forma de ola.",
        "lore": "Kuranes no lo da a cualquiera. Él también fue soñador; él también pagó. Llevar su sello es un pasaporte y una deuda.",
    },
    "consejo_kuranes": {
        "name": "Consejo de Kuranes",
        "short": "Una frase repetida en la memoria.",
        "lore": "«Kadath no te dará lo que pides. Te dará lo que eres.» Lo sabes sin quererlo, y duele.",
    },
    "partitura_inacabada": {
        "name": "Partitura Inacabada",
        "short": "Notas que aún no existen.",
        "lore": "El capitán de Dylath-Leen la guarda décadas antes de cederla al cantor adecuado. La última estrofa la tienes que escribir tú. En Kadath.",
    },
    "partitura_celeste": {
        "name": "Partitura Celeste",
        "short": "Canta sola cuando la abres.",
        "lore": "El lago de las memorias la dejó caer sobre ti como si la hubieras olvidado. Algún día la cantarás ante los Dioses Blandos, y despertarás mundos.",
    },
    "libro_de_sarkomand": {
        "name": "Libro de Sarkomand",
        "short": "Tu nombre en la portada. O el que era tu nombre.",
        "lore": "Cuenta tu vida despierta con precisión imposible. La última página está en blanco y pide que la completes tú — al final. Si la terminas en Kadath, abres un ending. Si la terminas antes, se cierra uno.",
    },
    "cancion_ghoul": {
        "name": "Canción Ghoul",
        "short": "Melodía rota que no deja de crecer.",
        "lore": "Aprendida en el banquete de las criptas. Los ghouls no cantan para los vivos; cantaron para ti porque, de alguna manera, ya no eres del todo uno. Si la cantas ante los Dioses Blandos, Nyarlathotep retrocede.",
    },
    "sello_ghoul": {
        "name": "Sello Ghoul",
        "short": "Hueso tallado con tres dientes.",
        "lore": "Te reconoce el Rey. En las Profundidades te tratan de igual a igual. En la superficie, te tratan como ya muerto.",
    },
    "hueso_rey_ghoul": {
        "name": "Hueso del Rey Ghoul",
        "short": "Húmedo. Tibio. No deberías haberlo tocado.",
        "lore": "En Kadath, este hueso abre una puerta que nadie más puede abrirte. Pero cada día que pasa, pesa un poco más.",
    },
    "lampara_ghoul": {
        "name": "Lámpara Ghoul",
        "short": "Ilumina sin calor.",
        "lore": "Muestra lo que los sueños esconden en los muros. Los frescos del templo sumergido. Los glifos bajo el polvo. Los rostros de los dioses antes de que tuvieran máscara.",
    },
    "mascara_del_sacerdote": {
        "name": "Máscara del Sacerdote Sin Rostro",
        "short": "Encaja demasiado bien.",
        "lore": "Aceptarla fue aceptar mucho más. Nyarlathotep te mira desde adentro cuando te la pones — y tus propios ojos te miran desde afuera. Ya no sabes cuál de los dos eres.",
    },
    "plano_kadath": {
        "name": "Plano de Kadath",
        "short": "Dibujado con tinta que no existe en tu mundo.",
        "lore": "Cada vez que lo miras, hay una línea más que antes. Si lo tiras al fuego, se quedaría. Si lo completas, Kadath se rediseña contigo.",
    },
    "rezo_antiguo": {
        "name": "Rezo Antiguo",
        "short": "Palabras para dioses que ya no existen.",
        "lore": "O que existieron. O que existirán. Decirlo en voz alta obliga a alguien a escuchar — no siempre al que querías.",
    },
    "taza_del_anciano": {
        "name": "Taza de JC",
        "short": "Vacía, pero con el olor de lo que bebió él.",
        "lore": "JC — el que perdió un ojo — te la regaló sin decirlo. Siete tazas esperan siete viajeros. La tuya ya no está en la mesa del campamento.",
    },
    "ojo_perdido": {
        "name": "Ojo Perdido",
        "short": "El tuyo. En una bolsita limpia.",
        "lore": "Te lo sacaste tú mismo. JC te lo guarda, dice que algún día lo devolverás a su sitio. Mientras tanto, ves TODO lo que antes estaba en el margen. Nada se olvida. Nada se desdibuja.",
    },
    "piedrita_gab": {
        "name": "Piedrita de Gab",
        "short": "Gab jura que es sagrada.",
        "lore": "No es sagrada. Pero Gab insiste tanto que uno empieza a dudar. Uno empieza.",
    },
    "papel_de_gab": {
        "name": "Papel Arrugado de Gab",
        "short": "Una fecha imposible.",
        "lore": "La fecha es anterior a cualquier cosa. Gab la escribió con saña. Si se la muestras al anciano JC, JC asentirá muy despacio: también la ha visto.",
    },
    "pagare_de_neruson": {
        "name": "Pagaré de Neruson",
        "short": "«Te debo dos chismes.»",
        "lore": "Neruson firma pocos pagarés. Los firmados siempre se cumplen, aunque tarden. Se cumplen mal, a veces.",
    },
    "llaves_papu": {
        "name": "Llaves de Papu",
        "short": "Pesadas, oxidadas, cálidas.",
        "lore": "Papu te las dio o se las robaste. No es lo mismo. Las llaves, de todos modos, saben quién las está usando.",
    },
    "sombra_rescatada": {
        "name": "Sombra Rescatada",
        "short": "Pesa como un recuerdo ajeno.",
        "lore": "Sacaste a una sombra joven de la jaula de Papu. La soltaste en el sendero. Ya no está contigo, pero tu mano todavía recuerda su forma. Los gatos de Ulthar te deberán un favor por esto mucho después de Kadath.",
    },
    "sombra_propia": {
        "name": "Tu Sombra Joven",
        "short": "Tiene tu voz de niño.",
        "lore": "La compraste. La metiste dentro de ti porque Papu te dijo que era tuya desde antes. Ahora ya no sabes si eres tú o la sombra quien piensa. En Kadath, tampoco importa.",
    },
    "cuchilla_leng": {
        "name": "Cuchilla de Hueso de Leng",
        "short": "Pide ser usada.",
        "lore": "Los Hombres de Leng no dan cuchillas sin motivo. Cuando la uses, lo que pediste llegará — y algo más, que no pediste, llegará también.",
    },
    "taza_del_anciano_ROJA": {
        "name": "Octava Taza",
        "short": "Esta no estaba en la mesa.",
        "lore": "JC miente cuando dice que son siete viajeros. Siempre son ocho. La octava eres tú, siempre.",
    },
}

def get_item_lore(item_id: str) -> Optional[Dict[str, str]]:
    return ITEM_LORE.get(item_id)


# ─── ENDING_MEMORIES: epílogos dinámicos por flag ────────────────────────────
# Lección Anchorhead: cada final integra los momentos clave del run.

ENDING_MEMORIES: List[Dict[str, str]] = [
    {"flag": "gato_ulthar_aliado",       "line": "El gato de la escalera sigue esperando tu vuelta. No vuelves. Espera igual."},
    {"flag": "bendicion_ulthar",         "line": "Los gatos de Ulthar cantaron tu nombre al amanecer — una sola vez, y nunca más."},
    {"flag": "gatos_deben_favor",        "line": "Un gato mayor acude a tu lecho la noche en que despiertas. Se va sin que lo veas."},
    {"flag": "leyo_glifos",              "line": "En los muros del Descenso, tu voz pronunciando 'SIETE' y 'BARZAI' aún retumba."},
    {"flag": "nyarlathotep_te_vio",      "line": "Aquella figura alta del umbral te seguirá recordando. Eso es lo peor de todo."},
    {"flag": "canto_en_dylath",          "line": "En el puerto de Dylath-Leen, una canción sin autor conocido flota entre las grúas. Te acordarás de ella a veces, sin saber por qué."},
    {"flag": "aliado_capitan",           "line": "El capitán de barba blanca te levantó una copa en su última travesía. No supiste nunca."},
    {"flag": "fue_esclavo_leng",         "line": "Algo de Leng quedó adentro. Los ojos del espejo no siempre son los tuyos."},
    {"flag": "leyo_libro_sarkomand",     "line": "El libro de Sarkomand se cerró por sí solo cuando terminaste. La última página — la que escribirías tú — quedó en blanco."},
    {"flag": "libro_listo_para_terminar","line": "Una página en blanco te espera en algún rincón del sueño. Algún día la terminarás."},
    {"flag": "pacto_zoog",               "line": "Los zoogs te recuerdan. Dicen tu nombre a sus crías antes de dormirlas."},
    {"flag": "pacto_zoog_oscuro",        "line": "El fruto prohibido aún te sabe a aluminio cuando piensas en tu madre. Y ya no sabes si es tu madre."},
    {"flag": "gatos_deben_favor",        "line": "Tres gatos de Ulthar vienen a verte al mundo despierto. Tu puerta, de alguna manera, se abrió para ellos."},
    {"flag": "aliado_kuranes",           "line": "Kuranes te menciona alguna vez. Cuando sueña, sueña también contigo."},
    {"flag": "pacto_ghoul",              "line": "Los ghouls cantarán tu nombre cuando otro alguien baje. Tú les enseñaste una canción nueva."},
    {"flag": "huesped_ghoul",            "line": "En las Profundidades hay un sitio reservado para ti. Siempre frío, siempre limpio."},
    {"flag": "rechazo_mascara",          "line": "El sacerdote sin rostro aún te recuerda como el único que dijo 'no' tres veces seguidas."},
    {"flag": "tomo_mascara_caos",        "line": "La máscara que aceptaste ya no está en tu cara. Pero aún está. Siempre."},
    {"flag": "canto_al_sacerdote",       "line": "La canción que le cantaste al sacerdote aún lo hace callar cuando él quiere hablar."},
    {"flag": "dio_un_ojo",               "line": "JC cuida tu ojo en una caja limpia. Cuando despiertas, ves demasiado por el que te queda."},
    {"flag": "sabe_verdad_trono",        "line": "Entiendes lo que JC vio con el ojo que perdió. No se lo cuentas a nadie."},
    {"flag": "confeso_al_anciano",       "line": "La octava taza del campamento tiene tu huella. JC la dejará ahí, por si acaso."},
    {"flag": "engañó_a_papu",            "line": "Papu se despertó después y te miró sin ojos durante mucho tiempo."},
    {"flag": "traiciono_a_papu",         "line": "Papu sigue durmiendo, pero ahora con un ojo abierto — el tuyo, el que perdiste con JC, si lo perdiste."},
    {"flag": "rescato_sombra_papu",      "line": "Una sombra joven que liberaste de la cripta de Papu camina por algún rincón del sueño. Tu mano aún recuerda su forma."},
    {"flag": "libero_almacen_papu",      "line": "Doce sombras salieron corriendo de Sarkomand aquella noche. Doce direcciones. Algún día, alguna de ellas va a agradecerte. Ninguna va a llegar a tiempo."},
    {"flag": "compro_sombra_papu",       "line": "Tu sombra joven vive dentro de ti desde que la compraste. A veces grita. A veces canta. A veces eres tú."},
    {"flag": "delato_papu_a_gatos",      "line": "Los gatos de Ulthar bajaron a Sarkomand esa noche. Al amanecer las jaulas estaban vacías. Papu sigue allí, pero ya no ronca."},
    {"flag": "delato_papu_a_leng",       "line": "Los Hombres de Leng te dieron una cuchilla y luego se llevaron todo. Tu delación no salvó a nadie — solo cambió de dueño a Papu."},
    {"flag": "papu_enemigo_mortal",      "line": "Papu te recuerda. Va a recordarte siempre. El único ojo abierto sigue abierto en alguna parte, mirándote."},
    {"flag": "neruson_debe_favor",       "line": "Neruson te debía dos chismes. Un día, sin avisar, te despiertas con uno de ellos en la cabeza."},
    {"flag": "gab_debe_favor",           "line": "Gab sigue jurando que llegó primero al lugar donde despertaste. Ahora quizá sea verdad."},
    {"flag": "gab_enemigo",              "line": "El papel arrugado con la fecha imposible está en tu bolsillo cuando despiertas. Lo tiras. Vuelve."},
    {"flag": "vio_rey_ghoul",            "line": "El Rey Ghoul te escupió un hueso. Aún lo tienes. Aún pesa."},
    {"flag": "invoco_shantak",           "line": "La bestia voladora te exigió sacrificio. Lo pagaste o lo debes. No olvidas cuál."},
    {"flag": "acepto_trono_caos",        "line": "Ya no sueñas. Tú eres el sueño de otros ahora."},
    {"flag": "enfrento_voces",           "line": "Las voces que acallaste en el sendero aún se dan cita cuando duermes. Ya no gritas."},
    {"flag": "test_nyar_pasado",         "line": "Los Dioses Blandos te llamaron por tu nombre — no el despierto, el otro. Aún lo recuerdas. Casi."},
]

def collect_ending_memories(state: "GameState", limit: int = 5) -> List[str]:
    """Devuelve hasta `limit` líneas de memoria aplicables al estado final."""
    lines = []
    seen_flags = set()
    for entry in ENDING_MEMORIES:
        flag = entry["flag"]
        if flag in state.flags and flag not in seen_flags:
            seen_flags.add(flag)
            lines.append(entry["line"])
        if len(lines) >= limit:
            break
    return lines


# ─── NPC_MEMORY_LINES: los NPCs recuerdan lo que hiciste ─────────────────────
# Lección Anchorhead/Fallen London: los NPCs reaccionan a tus flags específicos.

NPC_MEMORY_LINES: Dict[str, List[Dict[str, Any]]] = {
    "consejo_gatos": [
        {"flags": ["pacto_ghoul"],         "line": "*El mayor te mira sin parpadear.* «Ya no somos los mismos. Ya no eres el mismo.»"},
        {"flags": ["pacto_zoog_oscuro"],   "line": "*Los siete gatos te dan la espalda al mismo tiempo.* Uno bufa al viento."},
        {"flags": ["gatos_deben_favor"],   "line": "*El mayor se levanta.* «Te debemos un favor. Úsalo cuando no tengas otra opción. Aún no es ese momento.»"},
        {"flags": ["traiciono_a_papu"],    "line": "*Los gatos hablan entre sí en un idioma que casi entiendes.* «Ah. Eres tú.»"},
    ],
    "capitan_enmascarado": [
        {"flags": ["canto_en_dylath"],     "line": "*El capitán te hace una reverencia pequeña.* «Cantor. Te guardé esta canción desde el puerto.»"},
        {"flags": ["escapo_leng"],         "line": "*Te estudia con el ceño fruncido.* «Alguien que olió a Leng y volvió. Cuéntame cómo.»"},
        {"flags": ["fue_esclavo_leng"],    "line": "*Baja la vista.* «Lo siento, muchacho. No siempre llegamos a tiempo.»"},
    ],
    "kuranes": [
        {"flags": ["pacto_ghoul"],         "line": "*Kuranes aparta la mirada.* «Los ghouls también son reyes, a su modo. Pero no todos los reinos vuelven.»"},
        {"flags": ["leyo_libro_sarkomand"],"line": "*Asiente despacio.* «Entonces ya sabes quién fuiste. Y quién puedes no ser.»"},
    ],
    "jc_anciano_un_ojo": [
        {"flags": ["pacto_ghoul"],         "line": "*JC te sirve té sin decir nada. La taza está más limpia que las otras.* «A este paso, no vas a necesitar mi consejo.»"},
        {"flags": ["dio_un_ojo"],          "line": "*Ríe en voz baja.* «Ahora somos dos tuertos. Bienvenido al club. No se habla mucho aquí dentro.»"},
        {"flags": ["tomo_mascara_caos"],   "line": "*JC deja caer la taza.* «...Vete. Ya no puedo ayudarte.»"},
        {"flags": ["leyo_libro_sarkomand"],"line": "*Se inclina.* «Leíste el libro. Yo también. La mía decía que iba a perder un ojo. Tenía razón.»"},
    ],
    "sacerdote_sin_rostro": [
        {"flags": ["provoco_al_caos"],     "line": "*Se gira sin máscara debajo de la máscara.* «Te recuerdo. Vas a decir «no» otras dos veces más antes del final.»"},
        {"flags": ["canto_al_sacerdote"],  "line": "*Tiembla ligeramente.* «Tu canción. Aún duele. Sigue, si quieres.»"},
    ],
    "ghouls": [
        {"flags": ["huesped_ghoul"],       "line": "*Los ghouls bajan la cabeza al pasar.* «Hermano. La mesa está puesta.»"},
        {"flags": ["vio_rey_ghoul"],       "line": "*Un ghoul joven te señala con respeto temeroso.* «Ese. Ese vio al Rey.»"},
    ],
    "gab_el_primero": [
        {"flags": ["gab_debe_favor"],      "line": "*Gab sonríe de lado.* «Ya sé que eres tú. Tengo memoria, mano. A veces.»"},
        {"flags": ["gab_enemigo"],         "line": "*Gab te escupe al suelo y grita.* «¡YO LLEGUÉ PRIMERO!»"},
    ],
    "papu_el_relajado": [
        {"flags": ["libero_almacen_papu"],    "line": "*Papu no abre ninguno de los dos ojos cuando pasas. Su dedo apunta hacia ti y tiembla ligeramente.* «lptm. lptm. lptm.»"},
        {"flags": ["compro_sombra_papu"],     "line": "*Papu te sonríe con media cara.* «sisis mano, cliente repetido, el mejor.» *Se toca el pecho, como si reconociera algo ahí dentro tuyo.*"},
        {"flags": ["rescato_sombra_papu"],    "line": "*Papu te mira como a un competidor.* «ah ya. el que saca producto y lo suelta. pierdes plata, mano. gg.»"},
        {"flags": ["delato_papu_a_gatos"],    "line": "*Papu está sobre la losa pero ya no ronca. Un ojo abierto te sigue cuando pasas. No dice nada. Respira.*"},
        {"flags": ["delato_papu_a_leng"],     "line": "*Papu ya no tiene jaulas. Tiene una cicatriz nueva en la frente.* «sisis mano. me cobraron. seguimos.»"},
        {"flags": ["traiciono_a_papu"],       "line": "*Papu abre el único ojo.* «oye. tú eres el de las llaves. no te acuerdas, pero yo sí. sisis.»"},
        {"flags": ["hablo_con_papu"],         "line": "*Papu asiente lento.* «ah ya, el cliente. ¿algo más hoy? producto fresco llegó ayer.»"},
    ],
    "neruson_el_chismoso": [
        {"flags": ["neruson_debe_favor"],  "line": "*Neruson te guiña.* «Aún te debo un chisme. El primero te lo doy ya: JC te está esperando arriba.»"},
    ],
}


def pick_npc_memory_line(npc_id: str, state: "GameState") -> Optional[str]:
    """Devuelve una línea específica del NPC según flags del jugador, o None.

    Elige la primera entrada cuyos TODOS los flags estén presentes. Si varias
    cumplen, elige la primera declarada (orden de especificidad decidida por
    el autor).
    """
    entries = NPC_MEMORY_LINES.get(npc_id)
    if not entries:
        return None
    for e in entries:
        required = e.get("flags") or []
        if all(f in state.flags for f in required):
            return e["line"]
    return None


# ─── Narrador no confiable (Eternal Darkness) ────────────────────────────────
# Cuando el jugador cruza el 4º umbral de insight, el texto de los nodos se
# distorsiona. Sustituciones deterministas que preservan legibilidad.

_UNRELIABLE_SUBS: List[Tuple[str, str]] = [
    ("los gatos",     "~~los gatos~~ *los testigos*"),
    ("el capitán",    "el capitán (o lo que usa su cara)"),
    ("los dioses",    "~~los dioses~~ las máscaras"),
    ("despiertas",    "~~despiertas~~ *crees despertar*"),
    ("recuerdas",     "~~recuerdas~~ *te convencen de que recuerdas*"),
    ("el mar",        "el mar (que no es mar)"),
    ("tu nombre",     "tu ~~nombre~~ *alias operacional*"),
    ("la escalera",   "la escalera (que ya no baja)"),
    ("la puerta",     "la puerta (que no siempre estuvo ahí)"),
    ("la voz",        "~~la voz~~ *una de las voces*"),
]


def untrustworthy_filter(text: str, state: "GameState") -> str:
    """Distorsiona el texto si el jugador cruzó insight_IV_desanclado.

    Las sustituciones son deterministas — mismo texto → misma versión rota.
    Solo sustituye primera ocurrencia de cada patrón para no saturar.
    """
    if not text or "insight_IV_desanclado" not in state.flags:
        return text
    out = text
    for old, new in _UNRELIABLE_SUBS:
        if old in out:
            out = out.replace(old, new, 1)
    return out


# ─── resolve_node_text: devuelve el texto que corresponde al estado actual ───
# Eje 1. Cada nodo puede declarar text_variants ordenados por especificidad.

def resolve_node_text(state: "GameState", node: Dict[str, Any]) -> str:
    """Devuelve el texto del nodo, escogiendo el primer text_variant cuyas
    condiciones cumpla el jugador. Si ninguno aplica, devuelve node['text'].
    Soporta 'text' (reemplazo total) y 'append_text' (añade al base)."""
    base = node.get("text") or "*El silencio del sueño te envuelve.*"
    variants = node.get("text_variants") or []
    for v in variants:
        conds = v.get("conditions") or {}
        if state.meets_conditions(conds):
            if "text" in v:
                return v["text"]
            if "append_text" in v:
                return base + v["append_text"]
    return base


# ─── Cargador de persona del jugador ─────────────────────────────────────────
# Lee data/personas/<id> - <nombre>/agente_core.json si existe. El cog lo usa
# para inyectar reacciones de NPCs basadas en el perfil REAL del jugador.

def load_player_persona(user_id: int, project_root: Any) -> Optional[Dict[str, Any]]:
    """Carga el perfil destilado del jugador, si existe.

    Devuelve un dict con los campos relevantes (muletillas, trigger_palabras,
    estado_emocional, arquetipo_supervivencia, red_flags, green_flags,
    como_moriria) o None si no hay perfil.
    """
    import json
    from pathlib import Path
    root = Path(project_root) / "data" / "personas"
    if not root.exists():
        return None

    folder_name = PERSONA_DIR_MAP.get(int(user_id))
    candidate_paths = []
    if folder_name:
        candidate_paths.append(root / folder_name / "agente_core.json")
    # Fallback: busca cualquier folder que empiece con el user_id
    for child in root.iterdir():
        if child.is_dir() and child.name.startswith(f"{user_id} "):
            candidate_paths.append(child / "agente_core.json")

    for path in candidate_paths:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                perfil = data.get("perfil_completo") or data
                estilo = perfil.get("estilo_habla") or {}
                personalidad = perfil.get("personalidad") or {}
                social = perfil.get("social") or {}
                return {
                    "user_id": int(user_id),
                    "muletillas": estilo.get("muletillas", [])[:6],
                    "vocabulario": estilo.get("vocabulario", [])[:6],
                    "voz_simulada": estilo.get("voz_simulada", "")[:280],
                    "arquetipo": personalidad.get("arquetipo_supervivencia", ""),
                    "red_flags": personalidad.get("red_flags", []),
                    "green_flags": personalidad.get("green_flags", []),
                    "rasgos": personalidad.get("rasgos_dominantes", []),
                    "trigger_palabras": data.get("trigger_palabras",
                        personalidad.get("trigger_palabras", [])),
                    "como_moriria": data.get("como_moriria",
                        perfil.get("como_moriria", "")),
                    "estado_emocional": data.get("estado_emocional",
                        perfil.get("estado_emocional", {})),
                    # Campos sociales expandidos
                    "aliados_probables": social.get("aliados_probables", []),
                    "enemigos_probables": social.get("enemigos_probables", []),
                    "estilo_conflicto": social.get("estilo_conflicto", ""),
                    "estilo_alianza": social.get("estilo_alianza", ""),
                    "rol_en_grupo": social.get("rol_en_grupo", ""),
                    "estrategia_supervivencia": perfil.get("estrategia_supervivencia", ""),
                    "dato_curioso": personalidad.get("dato_curioso", ""),
                    "descripcion_psicologica": personalidad.get("descripcion_psicologica", ""),
                }
            except (json.JSONDecodeError, OSError):
                continue
    return None


def pick_npc_reaction_to_player(
    npc_id: str,
    player_persona: Optional[Dict[str, Any]],
    node_id: str,
) -> Optional[str]:
    """Genera una línea de reacción del NPC al jugador, basada en su perfil.

    Determinista: mismo (npc, node_id, perfil) → misma línea. Si no hay perfil,
    devuelve None (el NPC habla de forma genérica).

    Usa datos ricos del perfil destilado:
    - arquetipo_supervivencia
    - estado_emocional (miedo, agresividad, desesperacion, etc.)
    - rol_en_grupo, estilo_conflicto
    - red_flags / green_flags
    - rasgos_dominantes
    - trigger_palabras (si aparecen en el id del nodo)
    """
    if not player_persona:
        return None
    npc = SERVER_NPCS.get(npc_id)
    if not npc:
        return None

    title = npc["dream_title"]
    arche = (player_persona.get("arquetipo") or "").upper()
    rasgos_txt = " ".join(player_persona.get("rasgos", [])).upper()
    rol = (player_persona.get("rol_en_grupo") or "").upper()
    conflicto = (player_persona.get("estilo_conflicto") or "").upper()
    emo = player_persona.get("estado_emocional") or {}
    miedo = int(emo.get("miedo", 0))
    agresividad = int(emo.get("agresividad", 0))
    desesperacion = int(emo.get("desesperacion", 0))
    confianza = int(emo.get("confianza_en_otros", 5))
    red_flags = [f.upper() for f in player_persona.get("red_flags", [])]
    green_flags = [f.upper() for f in player_persona.get("green_flags", [])]
    triggers = [t.upper() for t in player_persona.get("trigger_palabras", [])]

    templates: List[str] = []

    # Por arquetipo + estado emocional combinado
    if ("PROVOCADOR" in arche or "IMPULSIVO" in rasgos_txt) and agresividad >= 4:
        templates.append(
            f"— *{title} da un paso atrás sin darse cuenta.* «Ya veo. Tú "
            "eres de los que empujan hasta que algo empuja de vuelta. Bien. "
            "Aquí tengo poco que perder.»"
        )
    elif "OBSERVADOR" in arche and miedo <= 2:
        templates.append(
            f"— *{title} asiente despacio.* «Tú miras primero. Bien. "
            "Los que miran antes de hablar llegan más lejos en Kadath.»"
        )
    elif ("CAÓTICO" in arche or "CAOTICO" in arche) and confianza >= 5:
        templates.append(
            f"— *{title} ríe con los hombros.* «Me caes bien. La mayoría "
            "de los que bajan se toman este sueño demasiado en serio.»"
        )
    elif ("RELAJADO" in arche or "INTEGRADO" in arche or "RECLUTA" in arche):
        templates.append(
            f"— *{title} se encoge de hombros.* «Tú fluyes. Aquí abajo "
            "eso a veces salva, a veces te ahoga.»"
        )
    elif "REACCIONARIO" in arche or "DRAMA" in rol:
        templates.append(
            f"— *{title} inclina la cabeza.* «Tú reaccionas primero, piensas "
            "después. Kadath premia y castiga eso en partes iguales.»"
        )

    # Por estado emocional dominante
    if miedo >= 4 and desesperacion >= 3:
        templates.append(
            f"— *{title} baja la voz.* «Tienes miedo. Lo huelo. No te "
            "voy a mentir: aquí eso atrae cosas. Trata de dormir con un gato cerca.»"
        )
    if confianza <= 2:
        templates.append(
            f"— *{title} no te mira.* «No te fías de nadie. Bien. Aquí "
            "es casi una virtud. Pero la soledad también tiene precio.»"
        )
    if agresividad >= 5:
        templates.append(
            f"— *{title} se tensa un poco.* «Ándate con cuidado con quién "
            "te metes. Lo que intimides aquí te recordará cuando despiertes.»"
        )

    # Por estilo de conflicto
    if "PASIVO" in conflicto or "EVITATIVO" in conflicto:
        templates.append(
            f"— *{title} nota algo en tu postura.* «Tú no peleas de frente. "
            "Vale. Aquí hay muchas maneras de salir sin levantar la voz.»"
        )
    elif "AGRESIVO" in conflicto or "DIRECTO" in conflicto:
        templates.append(
            f"— *{title} te mide.* «Tú peleas de frente. En los sueños, "
            "lo de frente no siempre es lo de verdad.»"
        )

    # Red flags / Green flags (citando rasgos concretos)
    for rf in red_flags:
        if "DESHUMANIZ" in rf or "BURLA" in rf or "SUPERFICIAL" in rf:
            templates.append(
                f"— *{title} te estudia.* «Sabes reírte de cosas que otros "
                "no soportan ver. Útil. Hasta el momento en que deja de serlo.»"
            )
            break
    for gf in green_flags:
        if "HONESTIDAD" in gf or "LEALTAD" in gf or "HUMOR" in gf:
            templates.append(
                f"— *{title} asiente.* «Tu forma de hablar es directa. "
                "Se agradece. Aquí abajo la franqueza es rara.»"
            )
            break

    # Triggers: si una palabra-gatillo del jugador aparece en el nodo
    if triggers and any(t.replace(" ", "_") in node_id.upper() for t in triggers):
        templates.append(
            f"— *{title} se detiene.* «Veo que ciertos temas te siguen "
            "incluso hasta aquí. Nada es casualidad en Kadath.»"
        )

    # Fallback si nada aplicó
    if not templates:
        templates.append(f"— *{title} te estudia un momento, sin decir nada.*")

    idx = int(
        hashlib.md5(
            f"{npc_id}|{node_id}|{player_persona.get('user_id', 0)}".encode()
        ).hexdigest(), 16
    ) % len(templates)
    return templates[idx]


def initial_npc_trust_from_persona(
    player_persona: Optional[Dict[str, Any]],
) -> Dict[str, int]:
    """Al crear partida, aplica trust inicial a NPCs basado en aliados/enemigos
    probables del perfil del jugador. Devuelve dict npc_id→delta inicial."""
    if not player_persona:
        return {}

    aliados = player_persona.get("aliados_probables") or []
    enemigos = player_persona.get("enemigos_probables") or []
    trust: Dict[str, int] = {}

    # Match laxo: buscar en aliases del nombre
    def normalize(s: str) -> str:
        return s.lower().split("#")[0].strip()

    aliados_norm = [normalize(a) for a in aliados]
    enemigos_norm = [normalize(e) for e in enemigos]

    for npc_id, meta in SERVER_NPCS.items():
        real_name = normalize(meta.get("real_name", ""))
        dream_title = normalize(meta.get("dream_title", ""))
        matched_as = None
        for a in aliados_norm:
            if a and (a in real_name or a in dream_title
                      or real_name in a or (npc_id.lower() in a)):
                matched_as = "aliado"; break
        if not matched_as:
            for e in enemigos_norm:
                if e and (e in real_name or e in dream_title
                          or real_name in e or (npc_id.lower() in e)):
                    matched_as = "enemigo"; break

        if matched_as == "aliado":
            trust[npc_id] = +15
        elif matched_as == "enemigo":
            trust[npc_id] = -15

    return trust


__all__ = [
    "CHARACTER_DATA",
    "VOICE_TEMPLATES",
    "PASSIVE_META",
    "STATS",
    "STAT_EMOJI",
    "STAT_NAMES_ES",
    "INSIGHT_THRESHOLDS",
    "CORRUPTION_THRESHOLDS",
    "EXCLUSIVE_FLAGS",
    "ENDING_LOCKS",
    "SERVER_NPCS",
    "PERSONA_DIR_MAP",
    "ITEM_LORE",
    "ENDING_MEMORIES",
    "NPC_MEMORY_LINES",
    "GameState",
    "pick_voice_line",
    "state_tag",
    "load_player_persona",
    "pick_npc_reaction_to_player",
    "initial_npc_trust_from_persona",
    "get_server_npc",
    "get_item_lore",
    "collect_ending_memories",
    "pick_npc_memory_line",
    "resolve_node_text",
    "untrustworthy_filter",
]
