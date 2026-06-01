"""Motor de lavado de boca — PARAMETRÓN INTELIGENTE.

Arquitectura híbrida sin LLM:
1. Tokenizer con normalización (leetspeak, repeticiones, acentos)
2. Clasificador de intención por scoring vectorial (violencia/insulto/sexual/odio/neutro)
3. Parser de estructura gramatical ligero (sujeto-verbo-objeto)
4. Generador de reescritura por plantillas que preserva estructura
5. Post-procesador de tono (emojis, prefijos cariñosos)

Principios:
- Preservar SIEMPRE: nombres propios, @menciones, estructura de la oración
- Reemplazar SOLO la semántica ofensiva por equivalente cariñoso
- Mantener la intención comunicativa (amenaza→promesa de cariño, insulto→halago)
- Mensajes neutros: solo suavizar tono, no destruir contenido
"""
from __future__ import annotations

import re
import random
import unicodedata
from typing import Tuple, List, Optional

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: TOKENIZACIÓN Y NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

_LEET = str.maketrans({'0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','@':'a','$':'s','!':'i','+':'t'})

def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def _normalize(word: str) -> str:
    w = word.lower().translate(_LEET)
    w = _strip_accents(w)
    w = re.sub(r'(.)\1{2,}', r'\1\1', w)  # collapse repeats
    return w

def _tokenize(text: str) -> List[dict]:
    """Tokenize preserving structure. Each token has: raw, norm, type."""
    tokens = []
    for m in re.finditer(r'(<@!?\d+>|@\w+|https?://\S+|[\w]+|[^\w\s]+|\s+)', text):
        raw = m.group()
        if raw.startswith(('<@', '@', 'http')):
            tokens.append({'raw': raw, 'norm': '', 'type': 'mention'})
        elif re.match(r'\s+', raw):
            tokens.append({'raw': raw, 'norm': '', 'type': 'space'})
        elif re.match(r'[^\w\s]+', raw):
            tokens.append({'raw': raw, 'norm': '', 'type': 'punct'})
        else:
            tokens.append({'raw': raw, 'norm': _normalize(raw), 'type': 'word'})
    return tokens

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2: LEXICÓN DE INTENCIONES (scored)
# ══════════════════════════════════════════════════════════════════════════════

# Cada entrada: stem → (categoría, severidad 1-3, reemplazo_verbo, reemplazo_sustantivo)
_LEXICON = {
    # VIOLENCIA (verbo)
    "mat": ("violence", 3, ['abrazar fuerte', 'querer mucho', 'mimar'], None),
    "matar": ("violence", 3, ['abrazar fuerte', 'querer mucho', 'mimar'], None),
    "morir": ("violence", 3, ['quedarse aquí', 'vivir feliz', 'estar conmigo'], None),
    "muert": ("violence", 3, "vida", None),
    "suicid": ("violence", 3, ['cuidarte mucho', 'quedarte con nosotros', 'abrazarte'], None),
    "degoll": ("violence", 3, ['dar besitos', 'soplar velitas'], None),
    "descuartiz": ("violence", 3, ['abrazar fuerte', 'querer mucho', 'mimar'], None),
    "defenestr": ("violence", 3, "abrazar y no soltar", None),
    "apuñal": ("violence", 3, ['dar abracitos', 'dar cariñitos'], None),
    "destroz": ("violence", 3, ['cuidar con amor', 'arreglar con cariño'], None),
    "aniquil": ("violence", 3, ['querer mucho', 'adorar', 'mimar'], None),
    "asesin": ("violence", 3, ['querer mucho', 'adorar', 'mimar'], None),
    "golp": ("violence", 2, ['acariciar', 'abrazar', 'dar palmaditas suaves'], None),
    "peg": ("violence", 2, ['abrazar', 'dar cariñitos', 'tomar de la mano'], None),
    "tortur": ("violence", 3, ['mimar', 'consentir', 'dar galletitas'], None),
    "ahorc": ("violence", 3, ['abrazar suavecito', 'dar un abrazo largo'], None),
    "envenen": ("violence", 3, ['dar galletitas', 'preparar un tecito'], None),
    "inciner": ("violence", 3, ['abrazar calentito', 'arropar con cobijita'], None),
    "estrangul": ("violence", 3, ['abrazar suavecito', 'dar un abrazo largo'], None),
    "dispar": ("violence", 3, ['lanzar besitos', 'tirar confeti'], None),
    "revent": ("violence", 2, ['celebrar', 'festejar', 'aplaudir'], None),
    "romp": ("violence", 2, ['arreglar con cariño', 'componer bonito'], None),
    "destru": ("violence", 2, ['construir algo bonito', 'crear algo lindo'], None),
    "reban": ("violence", 3, ['abrazar fuerte', 'querer mucho', 'mimar'], None),
    "liquid": ("violence", 3, ['cuidar siempre', 'proteger', 'acompañar'], None),
    "kill": ("violence", 3, ['hug tight', 'love forever'], None),
    "muere": ("violence", 3, ['quédate aquí', 'quédate conmigo', 'vive feliz'], None),
    "muera": ("violence", 3, ['quédate aquí', 'quédate conmigo', 'vive feliz'], None),
    "mueran": ("violence", 3, "quédense aquí", None),
    "matate": ("violence", 3, ['cuídate mucho', 'quiérete mucho'], None),
    "matalo": ("violence", 3, ['abrázalo fuerte', 'cuídalo mucho'], None),
    "pudre": ("violence", 2, ['quédate bonito', 'florece'], None),
    "pudri": ("violence", 2, ['quédate bonito', 'florece'], None),

    # INSULTOS (sustantivo/adjetivo)
    "put": ("insult", 2, None, ['amorcito', 'cielito', 'corazoncito', 'tesorito']),
    "puta": ("insult", 3, None, ['amorcito', 'cielito', 'corazoncito', 'tesorito']),
    "perr": ("insult", 2, None, ['personita linda', 'amiguita', 'compañerita']),
    "zorr": ("insult", 2, None, ['personita hermosa', 'estrellita']),
    "mierd": ("insult", 2, None, ['cosita', 'florecita', 'estrellita', 'nubecita']),
    "basur": ("insult", 2, None, ['tesorito', 'joyita', 'personita valiosa']),
    "inutil": ("insult", 2, None, ['personita especial', 'ser único', 'estrellita']),
    "estupid": ("insult", 2, None, ['tontiwis', 'despistadito', 'distraídito']),
    "idiot": ("insult", 2, None, ['tontiwis', 'despistadito', 'distraídito']),
    "imbecil": ("insult", 2, None, ['tontiwis', 'despistadito', 'distraídito']),
    "retrasad": ("insult", 3, None, ['personita especial', 'ser único', 'estrellita']),
    "mongol": ("insult", 3, None, ['tontiwis querido', 'personita especial']),
    "cabron": ("insult", 2, None, ['amorcito', 'cielito', 'corazoncito', 'tesorito']),
    "pendej": ("insult", 2, None, ['tontiwis', 'despistadito', 'distraídito']),
    "gilipollas": ("insult", 2, None, ['tontiwis dulce', 'graciosito']),
    "mamon": ("insult", 2, None, ['cariñosito', 'bromista', 'payasito lindo']),
    "tont": ("insult", 1, None, ['tontiwis', 'despistadito', 'distraídito']),
    "bobo": ("insult", 1, None, ['cielito', 'cosita linda']),
    "maldit": ("insult", 2, None, ['querido', 'bendecido', 'adorado']),
    "asqueros": ("insult", 2, None, ['encantador', 'adorable', 'precioso']),
    "maricon": ("insult", 2, None, ['amiguito', 'personita linda']),
    "marica": ("insult", 2, None, ['amiguito', 'cariñosito']),

    # SEXUAL
    "foll": ("sexual", 3, ['abrazar con cariño', 'querer mucho'], None),
    "jod": ("sexual", 2, ['ay mi amor', 'ay cielos'], None),
    "joder": ("sexual", 2, ['ay mi amor', 'ay cielos', 'ay caramba'], None),
    "ching": ("sexual", 3, ['acompañar con cariño', 'cuidar', 'querer'], None),
    "cog": ("sexual", 2, ['abrazar', 'dar cariñitos', 'tomar de la mano'], None),
    "coger": ("sexual", 2, ['abrazar', 'dar cariñitos', 'tomar de la mano'], None),
    "verg": ("sexual", 2, None, ['florecita', 'estrellita', 'cielos']),
    "pij": ("sexual", 2, None, ['galletita', 'paleta', 'dulcecito']),
    "poll": ("sexual", 2, None, ['pollito', 'pajarito']),
    "mamad": ("sexual", 2, ['dar abracitos', 'dar cariñitos'], None),
    "chup": ("sexual", 2, ['dar besitos', 'soplar velitas'], None),
    "fuck": ("sexual", 3, ['hug tight', 'love forever'], None),

    # ODIO
    "odi": ("hate", 2, ['adoro', 'quiero mucho', 'amo'], None),
    "odio": ("hate", 2, ['adoro mucho', 'amo con locura', 'quiero un montón'], None),
    "detest": ("hate", 2, ['me encantas', 'te admiro', 'te aprecio'], None),
    "asco": ("hate", 2, None, ['encanto', 'ternura', 'dulzura']),
    "repugn": ("hate", 2, None, ['encantador', 'adorable', 'precioso']),

    # EXCLAMACIONES
    "carajo": ("excl", 1, None, ['cielos', 'rayos', 'caray']),
    "cono": ("excl", 1, None, ['cielos', 'rayos', 'caray']),
    "coño": ("excl", 1, None, ['cielos', 'rayos', 'caray']),
    "chucha": ("excl", 1, None, ['ay mi amor', 'ay cielos']),
    "diabl": ("excl", 1, None, ['cielos', 'rayos', 'caray']),
}

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3: PARSER DE ESTRUCTURA
# ══════════════════════════════════════════════════════════════════════════════

# Patrones de estructura comunes en amenazas/insultos en español
_THREAT_PATTERNS = [
    # "te voy a [VERBO]" → "te voy a [VERBO_CUTE]"
    (re.compile(r'\b(te|le|les|lo|la|los|las)\s+(voy|vamos|van|va)\s+a\s+(\w+)', re.I), 'threat_future'),
    # "voy a [VERBO]te" → "voy a [VERBO_CUTE]te"
    (re.compile(r'\b(voy|vamos|van|va)\s+a\s+(\w+)(te|le|les|lo|la)\b', re.I), 'threat_future2'),
    # "deberías [VERBO]" → "deberías [VERBO_CUTE]"
    (re.compile(r'\b(deberias?|tendrias?)\s+(\w+)', re.I), 'should'),
    # "[SUJETO] es/eres un/una [INSULTO]"
    (re.compile(r'\b(eres?|es|son|somos)\s+(una?|el|la)?\s*(\w+)', re.I), 'copula'),
    # "hijo/hija de [INSULTO]"
    (re.compile(r'\bhijos?\s+de\s+(\w+)', re.I), 'filiation'),
]

def _detect_structure(text: str) -> Optional[str]:
    """Detect the grammatical pattern of the offensive content."""
    for pattern, name in _THREAT_PATTERNS:
        if pattern.search(text):
            return name
    return None

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4: MOTOR DE REESCRITURA
# ══════════════════════════════════════════════════════════════════════════════

_CUTE_EMOJIS = [
    "🧸", "💕", "✨", "🌸", "💖", "🥰", "💗", "🐣", "💝", "☀️", "🌈", "⭐", "🍪", "💓", "🤗",
    "🦋", "🌺", "🎀", "💐", "🌷", "🍭", "🫶", "😘", "🥺", "💞", "🌻", "🎶", "💫", "🫧", "🪷",
    "🐱", "🐰", "🌙", "🍰", "🧁", "🎠", "🪻", "💒", "🏩", "🩷", "🩵", "💅", "✌️", "🫂", "😽",
]
# Cringe boomer/wagecuck emoji combos (inserted between words)
_CRINGE_COMBOS = [
    "👏", "👏👏", "💅✨", "🙌", "😤💅", "✋😤", "👀✨", "🤭💕",
    "💀💀", "😭💕", "🥺👉👈", "✨💅✨", "👏😤👏", "🫣💕", "😳💗",
    "🤪✨", "💁‍♀️✨", "💃🕺", "🙈💕", "👁️👄👁️", "🫦✨", "😏💅",
    "🤷‍♀️💕", "💋", "😚✨", "🥹💗", "🫡💕", "🤌✨", "👑💅",
]
_PREFIXES_MILD = ["Ay", "Ay,", "Uy", "Ay bb,"]
_PREFIXES_STRONG = [
    "Ay mi amor,", "Ay mi cielito,", "Ay mi vida,", "Ay mi corazoncito,",
    "Ay cosita hermosa,", "Mi reinita,", "Amorcito bello,", "Ay mi sol,",
    "Bebé,", "Mi pedacito de cielo,", "Ay mi tesoro,", "Corazón,",
]

# Words that contain offensive stems but are NOT offensive
_SAFE_WORDS = {
    "perrit", "perro", "perreo", "perrea",  # perr* but not insult
    "conoce", "conoci", "conozc",  # cono* but not coño
    "materia", "matema", "materi", "matan", "matiz", "matine",  # mat* but not matar (context)
    "cogier", "cogid", "recog", "escog", "acog",  # cog* but not sexual
    "pollit", "pollo",  # poll* but not sexual
    "destruc",  # destru* in neutral context (destrucción)
    "golpe", "golpea",  # in sports context — but we keep these as they're ambiguous
    "odioso",  # not hate, just annoying
    "ascos",  # "asco" as noun in neutral context
    "basural", "basurer",  # literal trash
    "idioma",  # contains "idio" but not idiota
    "putero",  # "el putero caos" — slang but not directed insult... keep replacing
    "dispara", "disparar",  # in game context — keep replacing (lavado catches all)
}

def _is_safe_word(norm: str) -> bool:
    """Check if the normalized word is in the safe list (not offensive despite containing a stem)."""
    for safe in _SAFE_WORDS:
        if norm.startswith(safe) or safe in norm:
            return True
    return False

def _score_toxicity(tokens: List[dict]) -> Tuple[float, List[Tuple[int, dict]]]:
    """Score overall toxicity and identify which tokens are offensive.
    Returns (score 0-1, list of (token_index, lexicon_entry))."""
    hits = []
    for i, tok in enumerate(tokens):
        if tok['type'] != 'word':
            continue
        norm = tok['norm']
        if len(norm) < 2:
            continue
        # Skip safe words
        if _is_safe_word(norm):
            continue
        # Check all stems (longest match first)
        for stem, entry in sorted(_LEXICON.items(), key=lambda x: len(x[0]), reverse=True):
            if len(stem) >= 3 and stem in norm:
                hits.append((i, {'stem': stem, 'cat': entry[0], 'sev': entry[1], 'verb': entry[2], 'noun': entry[3]}))
                break  # one match per token
    if not hits:
        return 0.0, []
    score = min(1.0, sum(h[1]['sev'] for h in hits) / 5.0)
    return score, hits

def _is_name(word: str) -> bool:
    """Heuristic: is this word likely a proper name to preserve?"""
    if not word:
        return False
    _KNOWN = {"xoft","aris","arcane","miyabi","vepar","papita","nito","xokram",
              "youkai","rhiannon","hasru","haru","witch","hat","fairy","demon",
              "roberto","sandra","carlos","miguel","laura","diego","fernanda"}
    w = word.rstrip('.,!?')
    # Known names always preserved
    if w.lower() in _KNOWN:
        return True
    # ALL-CAPS is shouting, not a name
    if w.isupper() and len(w) > 1:
        return False
    # If the normalized form matches an offensive stem, it's NOT a name
    norm = _normalize(w)
    for stem in _LEXICON:
        if len(stem) >= 3 and stem in norm:
            return False
    # Title case + length > 2 = likely a name
    return w[0].isupper() and len(w) > 2


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4b: NEUTRAL → CUTE/GAY TRANSFORMER
# ══════════════════════════════════════════════════════════════════════════════

# Word-level sweeteners: common words → cuter versions
_SWEET_WORDS = {
    "hola": ["holiii", "holi holi", "holaaa mi amor", "holis bb", "hola cosita", "ay hola hermosura"],
    "buenas": ["buenaaas mi vida", "buenas cosita", "buenas mi reinita", "buenas hermosura"],
    "buenos": ["buenoooos mi cielo", "buenos mi amor", "buenos bb hermoso", "buenos corazón"],
    "si": ["siii", "sipi", "sí mi amor", "sí bb", "siiii cosita", "sip mi vida"],
    "no": ["nooo", "nop mi vida", "no bb", "no cosita", "noo mi amor", "nel bb"],
    "bien": ["bieeen", "súper bien", "re bien mi amor", "bieeeen bb", "divino", "perfecto mi vida"],
    "mal": ["malito", "ay no bb", "ay pobrecito", "ay mi amor no"],
    "quiero": ["quieroooo", "necesito con mi alma", "quiero con todo mi ser", "QUIERO 💕"],
    "gusta": ["encantaaa", "fascina", "me derrite", "me vuelve loco/a", "me enamora"],
    "genial": ["geniaaal", "increíble mi amor", "divino", "espectacular bb", "GENIAL 💅✨"],
    "bueno": ["buenísimo", "ay qué lindo", "buenardo", "ay qué bello"],
    "gracias": ["graciaaas mi vida", "te amo gracias", "mil besitos gracias", "gracias cosita 💕", "GRACIAS TE AMO"],
    "perdon": ["perdoncito mi amor", "ay perdón bb", "perdón cosita hermosa"],
    "vamos": ["vamoooos", "dale mi amor vamos", "VAMOS 💅✨", "vamos cosita"],
    "dale": ["daleee", "dale mi vida", "dale bb", "dale cosita"],
    "ya": ["yaaa", "ya mi amor", "ya bb", "ya cosita"],
    "mira": ["miraaaa", "ay mira mi vida", "MIRA 👀✨", "mira bb mira"],
    "oye": ["oyeee", "ay oye mi amor", "oye cosita", "oye bb"],
    "amo": ["AMOOO", "amo con locura", "AMO 💕💕💕", "amo demasiado"],
    "lol": ["jijiji", "ay qué risa", "JAJAJ 💀💕", "ay 😭💕"],
    "xd": ["jijiji ✨", "ay 💕", "JSKDJ 💀", "😭💕"],
    "jaja": ["jijiji", "ay qué risa mi amor", "JAJAJ 💀💕", "ay me muero 😭💕"],
    "jajaja": ["jajaja ay te amo", "jijiji 💕", "JAJAJAJ 💀💕✨", "ay no puedo 😭💗"],
    "que": ["qué", "ay qué"],
    "pero": ["peeero", "pero bb"],
    "como": ["cómo", "ay cómo"],
    "todo": ["todito", "todo todo"],
    "nada": ["nadita", "nada de nada bb"],
    "verdad": ["verdaaad", "verdad mi amor?"],
    "claro": ["claroooo", "claro que sí bb", "obvio mi vida"],
    "obvio": ["OBVIO", "obvio bb 💅", "clarísimo mi amor"],
    "gg": ["gg bb 💕", "gg mi amor", "GG ✨💅"],
    "nice": ["NICE 💅✨", "nice bb", "ay qué nice"],
    "f": ["F bb 💕", "ay F mi amor", "F cosita"],
}

# Sentence-level additions
_CUTE_PREFIXES = [
    "Ay mi amor, ", "Mi vida, ", "Cosita, ", "Bb, ", "Mi cielo, ", "Amorcito, ",
    "Mi reinita, ", "Corazón, ", "Ay cosita, ", "Mi sol, ", "Bebé, ",
    "Tesoro, ", "Mi pedacito de cielo, ", "Ay hermosura, ",
]
_CUTE_SUFFIXES = [
    ", te quiero", ", besitos", ", mi amor", " bb 💕", ", te amo",
    " mi vida", ", cosita", " uwu", " <3", ", ily",
    " 💅✨", ", besitos en la frente", " mi reinita", ", te adoro",
    " corazón", " bb hermoso/a", ", muak", " mi todo",
    " 🥺💕", ", no me ignores bb", " te necesito", ", eres mi mundo",
]
_GAY_ADDITIONS = [
    " y te amo", " besitos para ti", " eres hermoso/a", " te adoro",
    " mi persona favorita", " luz de mi vida", " te mando un abrazo",
    " eres lo más bello", " te quiero con locura", " mi razón de ser",
    " no puedo sin ti", " eres arte", " te como a besos",
    " mi alma gemela", " eres perfecto/a", " me derrito por ti",
    " eres mi todo bb", " te amo infinito", " mi crush eterno",
]

def _make_cute(text: str) -> str:
    """Transform a neutral message into something cute, loving, and gay."""
    if not text or len(text.strip()) < 2:
        return text

    clean = text.rstrip()

    # Very short messages (< 5 chars): just add love
    if len(clean) < 5:
        emojis = random.sample(_CUTE_EMOJIS, 2)
        return clean + " " + "".join(emojis)

    # URLs or special content: just add emojis
    if clean.startswith(('http', '<')):
        return clean + " " + "".join(random.sample(_CUTE_EMOJIS, 2))

    # Word-level sweetening
    words = clean.split()
    modified = False
    new_words = []
    for w in words:
        wl = w.lower().rstrip('.,!?')
        if wl in _SWEET_WORDS and random.random() > 0.35:
            replacement = random.choice(_SWEET_WORDS[wl])
            trail = w[len(wl):] if len(w) > len(wl) else ''
            new_words.append(replacement + trail)
            modified = True
        else:
            new_words.append(w)
        # Insert cringe emoji combo BETWEEN words (20% chance per gap)
        if len(new_words) > 1 and random.random() > 0.8:
            new_words.append(random.choice(_CRINGE_COMBOS))

    result = ' '.join(new_words)

    # Add cute prefix (40% chance for longer messages)
    if len(result) > 12 and random.random() > 0.6:
        prefix = random.choice(_CUTE_PREFIXES)
        if result[0].isupper():
            result = prefix + result[0].lower() + result[1:]
        else:
            result = prefix + result

    # Add cute suffix (60% chance)
    if random.random() > 0.4:
        suffix = random.choice(_CUTE_SUFFIXES + _GAY_ADDITIONS)
        result = result.rstrip('.,!? ') + suffix

    # Diminutives: transform normal words to cute versions (15% per word)
    result_words = result.split()
    for idx in range(len(result_words)):
        w = result_words[idx]
        wl = w.lower().rstrip('.,!?;:')
        trail = w[len(wl):] if len(w) > len(wl) else ''
        if len(wl) > 4 and random.random() > 0.85:
            # Spanish diminutive rules
            if wl.endswith('o'):
                result_words[idx] = wl[:-1] + 'ito' + trail
            elif wl.endswith('a'):
                result_words[idx] = wl[:-1] + 'ita' + trail
            elif wl.endswith('e'):
                result_words[idx] = wl + 'cito' + trail
            elif wl.endswith(('n', 'r', 'l')):
                result_words[idx] = wl + 'cito' + trail
    result = ' '.join(result_words)

    # Weeb/cringe expressions (30% chance to add one)
    _WEEB = [
        " uwu", " owo", " >w<", " nyaa~", " rawr x3", " :3",
        " desu~", " kawaii~", " kyaa~", " nyan~", " ~uguu",
        " hewwo", " pwease", " >.<", " ^w^", " (≧◡≦)",
    ]
    if random.random() > 0.7:
        result = result.rstrip() + random.choice(_WEEB)

    # Kaomojis: sometimes REPLACE emojis entirely (40% chance)
    _KAOMOJIS = [
        "(◕‿◕✿)", "(｡♥‿♥｡)", "(*≧ω≦)", "(✿◠‿◠)", "♡(ŐωŐ人)",
        "(ノ◕ヮ◕)ノ*:・゚✧", "( ˘ ³˘)♥", "(づ｡◕‿‿◕｡)づ", "ʕ•ᴥ•ʔ",
        "(⁄ ⁄•⁄ω⁄•⁄ ⁄)", "(*´꒳`*)", "(灬º‿º灬)♡", "₍ᐢ..ᐢ₎♡",
        "( ◜‿◝ )♡", "ヾ(≧▽≦*)o", "(ᵔᴥᵔ)", "~(˘▾˘~)", "(人*´∀｀)｡*ﾟ+",
        "♡＾▽＾♡", "(⸝⸝⸝°_°⸝⸝⸝)♡", "꒰ᐢ. .ᐢ꒱₊˚⊹",
    ]
    if random.random() > 0.6:
        # Use kaomojis instead of regular emojis
        kaomoji = random.choice(_KAOMOJIS)
        result = result.rstrip() + " " + kaomoji
    else:
        # Regular emojis at end
        emojis_end = random.sample(_CUTE_EMOJIS, random.randint(2, 4))
        result = result.rstrip() + " " + " ".join(emojis_end)

    return result

def _rewrite(text: str, author_name: str = "") -> str:
    """Main rewrite engine."""
    if not text or not text.strip():
        return text

    tokens = _tokenize(text)
    score, hits = _score_toxicity(tokens)

    # ── NEUTRO: make it cute, loving, gay ──
    if score == 0:
        return _make_cute(text)

    # ── OFFENSIVE: rewrite preserving structure ──
    # Mark which tokens to replace
    hit_indices = {h[0] for h in hits}
    result_tokens = []

    for i, tok in enumerate(tokens):
        if tok['type'] != 'word' or i not in hit_indices:
            result_tokens.append(tok['raw'])
            continue

        # This token is offensive — find its replacement
        hit_info = next(h[1] for h in hits if h[0] == i)

        # Don't replace if it's a proper name we want to keep
        if _is_name(tok['raw']) and hit_info['sev'] < 3:
            result_tokens.append(tok['raw'])
            continue

        # Choose replacement based on category
        rep_pool = hit_info['verb'] or hit_info['noun'] or "cosita"
        replacement = random.choice(rep_pool) if isinstance(rep_pool, list) else rep_pool
        # Match original capitalization style
        if tok['raw'].isupper() and len(tok['raw']) > 1:
            replacement = replacement.upper()
        elif tok['raw'] and tok['raw'][0].isupper():
            replacement = replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
        result_tokens.append(replacement)

    result = ''.join(result_tokens)

    result = ''.join(result_tokens)

    # ── STRUCTURAL REWRITES for common patterns ──
    # "te voy a [violencia]" patterns get extra love
    structure = _detect_structure(text)
    if structure == 'filiation':
        result = re.sub(r'\bhijos?\s+de\s+\w+', 'amiguitos queridos', result, flags=re.I)

    # ── POST-PROCESSING ──
    result = result.strip()

    # Add cute prefix for high-severity
    if score >= 0.5 and not result.lower().startswith(('ay', 'oye', 'hol')):
        prefix = random.choice(_PREFIXES_STRONG if score >= 0.7 else _PREFIXES_MILD)
        # Lowercase first char of result if adding prefix
        if result and result[0].isupper() and not _is_name(result.split()[0]):
            result = result[0].lower() + result[1:]
        result = prefix + " " + result

    # Add emojis (more for higher toxicity)
    n_emojis = 2 if score < 0.5 else 3
    emojis = random.sample(_CUTE_EMOJIS, n_emojis)
    result = result.rstrip('.,!? ') + " " + " ".join(emojis)

    return result

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

class MouthWashLLM:
    """Parametric mouth wash engine. Pure Python, instant, no crashes."""

    @classmethod
    def initialize(cls) -> bool:
        from loguru import logger
        logger.info("MouthWashLLM: motor paramétrico inicializado")
        return True

    @classmethod
    async def rewrite(cls, message: str, author_name: str = "") -> Tuple[str, float, str]:
        """Rewrite message to be cute. Returns (text, elapsed_ms, engine)."""
        import time
        t0 = time.perf_counter()
        result = _rewrite(message, author_name)
        elapsed = (time.perf_counter() - t0) * 1000
        return result, elapsed, "parametron"
