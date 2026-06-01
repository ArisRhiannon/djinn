"""Transformaciones heurísticas de mensajes (sin AI) para listeners.

Usado por la acción `impersonate` en `cogs/listeners.py` para construir el
contenido reemplazo a partir del mensaje original del usuario.

Dos niveles:
  1. `apply_transforms(text, ops)` — aplica una secuencia de operaciones al texto.
  2. `render_template(template, context)` — reemplaza tokens `{…}` por valores
     derivados del mensaje/autor/canal. El template puede incluir `{original}`
     (sin transformar) o `{transformed}` (después de `ops`).

Todas las operaciones son puras (sin I/O, deterministas salvo cuando tienen
parámetro de aleatoriedad), y trabajan con strings Unicode normales.
"""

from __future__ import annotations

import random
import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional

# ── Diccionarios de transformaciones ───────────────────────────────────────

_LEET_MAP = str.maketrans({
    "a": "4", "A": "4",
    "e": "3", "E": "3",
    "i": "1", "I": "1",
    "o": "0", "O": "0",
    "s": "5", "S": "5",
    "t": "7", "T": "7",
    "b": "8", "B": "8",
    "l": "1", "L": "1",
    "g": "9", "G": "9",
})

_ROT13 = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM",
)

_VOWELS = set("aeiouAEIOUáéíóúÁÉÍÓÚ")

# Zalgo combining marks (subset seguro — no quiebra Discord)
_ZALGO_UP = [
    "\u030d", "\u030e", "\u0304", "\u0305", "\u033f",
    "\u0311", "\u0306", "\u0310", "\u0352", "\u0357",
]
_ZALGO_DOWN = [
    "\u0316", "\u0317", "\u0318", "\u0319", "\u031c",
    "\u031d", "\u031e", "\u031f", "\u0320", "\u0324",
]


# ── Transformaciones individuales ─────────────────────────────────────────

def _redact(text: str, char: str = "▓", preserve: str = "spaces") -> str:
    """Reemplaza cada carácter por `char`.

    preserve:
      'spaces' (default) — mantiene espacios
      'punct'            — mantiene espacios y puntuación
      'none'             — reemplaza todo
    """
    char = (char or "▓")[0]
    if preserve == "none":
        return char * len(text)
    if preserve == "punct":
        return "".join(c if (c.isspace() or not c.isalnum()) else char for c in text)
    # default: spaces
    return "".join(c if c.isspace() else char for c in text)


def _uppercase(text: str) -> str:
    return text.upper()


def _lowercase(text: str) -> str:
    return text.lower()


def _swapcase(text: str) -> str:
    return text.swapcase()


def _reverse(text: str) -> str:
    return text[::-1]


def _reverse_words(text: str) -> str:
    return " ".join(text.split()[::-1])


def _mock(text: str) -> str:
    """aLtErNaTe CaSe (estilo SpongeBob)."""
    result = []
    toggle = False
    for c in text:
        if c.isalpha():
            result.append(c.upper() if toggle else c.lower())
            toggle = not toggle
        else:
            result.append(c)
    return "".join(result)


def _leetspeak(text: str) -> str:
    return text.translate(_LEET_MAP)


def _rot13(text: str) -> str:
    return text.translate(_ROT13)


def _shuffle_letters(text: str, seed: Optional[int] = None) -> str:
    """Typoglycemia: primera y última letra fija, el medio barajado.

    'Cambridge' → 'Cmagbirde' (aproximadamente)
    """
    rng = random.Random(seed)
    def shuffle_word(w: str) -> str:
        if len(w) <= 3:
            return w
        middle = list(w[1:-1])
        rng.shuffle(middle)
        return w[0] + "".join(middle) + w[-1]
    return re.sub(r"\S+", lambda m: shuffle_word(m.group(0)), text)


def _censor_words(text: str, words: List[str], replacement: str = "***") -> str:
    """Reemplaza palabras específicas por `replacement` (case-insensitive, word-boundary)."""
    if not words:
        return text
    pattern = r"\b(?:" + "|".join(re.escape(w) for w in words if w) + r")\b"
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)


def _replace_words(text: str, mapping: Dict[str, str]) -> str:
    """Reemplaza palabras según un diccionario {original: reemplazo}, case-insensitive, word-boundary."""
    if not mapping:
        return text
    pattern = r"\b(" + "|".join(re.escape(k) for k in mapping if k) + r")\b"
    def _sub(m: re.Match) -> str:
        key = m.group(0)
        # Buscar case-insensitive
        for k, v in mapping.items():
            if k.lower() == key.lower():
                return v
        return key
    return re.sub(pattern, _sub, text, flags=re.IGNORECASE)


def _replace_regex(text: str, pattern: str, replacement: str = "", flags: str = "i") -> str:
    """Reemplazo por regex. `flags` es string tipo 'is' (i=IGNORECASE, s=DOTALL, m=MULTILINE)."""
    f = 0
    for ch in (flags or "").lower():
        if ch == "i": f |= re.IGNORECASE
        elif ch == "s": f |= re.DOTALL
        elif ch == "m": f |= re.MULTILINE
    try:
        return re.sub(pattern, replacement, text, flags=f)
    except re.error:
        return text


def _prefix(text: str, value: str) -> str:
    return f"{value}{text}"


def _suffix(text: str, value: str) -> str:
    return f"{text}{value}"


def _repeat_letters(text: str, times: int = 2, letters: Optional[str] = None) -> str:
    """Repite las letras indicadas (default: vocales) N veces. 'hola' → 'hoooola' con times=3."""
    letters_set = set(letters) if letters else _VOWELS
    times = max(1, min(10, int(times)))
    return "".join(c * times if c in letters_set else c for c in text)


def _stretch_vowels(text: str, min_n: int = 2, max_n: int = 5, seed: Optional[int] = None) -> str:
    """Estira vocales aleatoriamente entre [min_n, max_n] repeticiones."""
    rng = random.Random(seed)
    min_n = max(1, int(min_n))
    max_n = max(min_n, int(max_n))
    return "".join(c * rng.randint(min_n, max_n) if c in _VOWELS else c for c in text)


def _zalgo(text: str, intensity: int = 2, seed: Optional[int] = None) -> str:
    """Agrega combining marks aleatorios. intensity 1-5."""
    rng = random.Random(seed)
    intensity = max(1, min(5, int(intensity)))
    result = []
    for c in text:
        result.append(c)
        if c.isalpha():
            for _ in range(rng.randint(0, intensity)):
                result.append(rng.choice(_ZALGO_UP + _ZALGO_DOWN))
    return "".join(result)


def _emoji_sprinkle(text: str, emojis: List[str], every: int = 3, seed: Optional[int] = None) -> str:
    """Inserta un emoji cada `every` palabras (con un poco de variabilidad)."""
    if not emojis:
        return text
    rng = random.Random(seed)
    words = text.split(" ")
    every = max(1, int(every))
    result = []
    for i, w in enumerate(words):
        result.append(w)
        if (i + 1) % every == 0 and i < len(words) - 1:
            result.append(rng.choice(emojis))
    return " ".join(result)


def _truncate(text: str, length: int = 50, ellipsis: str = "…") -> str:
    length = max(1, int(length))
    if len(text) <= length:
        return text
    return text[: length - len(ellipsis)] + ellipsis


def _remove_vowels(text: str) -> str:
    return "".join(c for c in text if c not in _VOWELS)


def _keep_initials(text: str, sep: str = "") -> str:
    """Solo la primera letra de cada palabra: 'hola mundo' → 'hm'."""
    return sep.join(w[0] for w in text.split() if w)


def _emphasize(text: str, marker: str = "**", prob: float = 0.25, seed: Optional[int] = None) -> str:
    """Envuelve palabras aleatorias en markdown (ej. **negrita**)."""
    rng = random.Random(seed)
    prob = max(0.0, min(1.0, float(prob)))
    def _maybe(w: str) -> str:
        if len(w) > 2 and w.isalpha() and rng.random() < prob:
            return f"{marker}{w}{marker}"
        return w
    return " ".join(_maybe(w) for w in text.split(" "))


def _wrap(text: str, left: str, right: Optional[str] = None) -> str:
    return f"{left}{text}{right if right is not None else left}"


def _pig_latin(text: str) -> str:
    """Pig latin de libro: consonante-cluster → final + 'ay', vocal → + 'way'."""
    def _one(w: str) -> str:
        if not w or not w.isalpha():
            return w
        lw = w.lower()
        if lw[0] in "aeiou":
            res = lw + "way"
        else:
            i = 0
            while i < len(lw) and lw[i] not in "aeiou":
                i += 1
            res = lw[i:] + lw[:i] + "ay"
        return res.capitalize() if w[0].isupper() else res
    return re.sub(r"\w+", lambda m: _one(m.group(0)), text)


def _normalize_nfkd(text: str) -> str:
    """Quita acentos y decomposiciones (ascii-fold)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ── Registry de ops ────────────────────────────────────────────────────────
#
# Cada op es (fn, allowed_kwargs). Las kwargs se toman del dict de la op
# menos "op" y se pasan por nombre a fn.

_OPS: Dict[str, tuple[Callable[..., str], tuple[str, ...]]] = {
    "redact":          (_redact,          ("char", "preserve")),
    "uppercase":       (_uppercase,       ()),
    "lowercase":       (_lowercase,       ()),
    "swapcase":        (_swapcase,        ()),
    "reverse":         (_reverse,         ()),
    "reverse_words":   (_reverse_words,   ()),
    "mock":            (_mock,            ()),
    "leetspeak":       (_leetspeak,       ()),
    "rot13":           (_rot13,           ()),
    "shuffle_letters": (_shuffle_letters, ("seed",)),
    "censor_words":    (_censor_words,    ("words", "replacement")),
    "replace_words":   (_replace_words,   ("mapping",)),
    "replace_regex":   (_replace_regex,   ("pattern", "replacement", "flags")),
    "prefix":          (_prefix,          ("value",)),
    "suffix":          (_suffix,          ("value",)),
    "repeat_letters":  (_repeat_letters,  ("times", "letters")),
    "stretch_vowels":  (_stretch_vowels,  ("min_n", "max_n", "seed")),
    "zalgo":           (_zalgo,           ("intensity", "seed")),
    "emoji_sprinkle":  (_emoji_sprinkle,  ("emojis", "every", "seed")),
    "truncate":        (_truncate,        ("length", "ellipsis")),
    "remove_vowels":   (_remove_vowels,   ()),
    "keep_initials":   (_keep_initials,   ("sep",)),
    "emphasize":       (_emphasize,       ("marker", "prob", "seed")),
    "wrap":            (_wrap,            ("left", "right")),
    "pig_latin":       (_pig_latin,       ()),
    "normalize_nfkd":  (_normalize_nfkd,  ()),
}


AVAILABLE_OPS: List[str] = sorted(_OPS.keys())


# ── API pública ────────────────────────────────────────────────────────────

def apply_transforms(text: str, ops: List[Dict[str, Any]]) -> str:
    """Aplica una secuencia de operaciones al texto.

    Cada op es un dict con key `op` (nombre de la transformación) y kwargs
    adicionales según la operación. Ops desconocidas o kwargs inválidas se
    ignoran silenciosamente (no queremos que una regla inválida haga crash).

    Ejemplo:
        apply_transforms("Hola mundo", [
            {"op": "uppercase"},
            {"op": "suffix", "value": " 🌸"},
        ])
        → "HOLA MUNDO 🌸"
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    if not ops:
        return text
    result = text
    for entry in ops:
        if not isinstance(entry, dict):
            continue
        name = entry.get("op")
        if not name or name not in _OPS:
            continue
        fn, allowed = _OPS[name]
        kwargs = {k: v for k, v in entry.items() if k != "op" and k in allowed}
        try:
            result = fn(result, **kwargs)
        except Exception:
            # Nunca romper el listener por una transformación rota
            continue
    return result


# ── Template rendering ─────────────────────────────────────────────────────

# Tokens soportados en el template. Se construyen a partir del mensaje original
# + el texto ya transformado. Un formato {name} se reemplaza por str(value).

_TOKEN_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def build_context(
    *,
    original: str,
    transformed: str,
    author_name: str = "",
    author_id: str = "",
    channel_name: str = "",
    channel_id: str = "",
) -> Dict[str, str]:
    """Construye el diccionario de tokens disponibles en el template."""
    words = original.split() if original else []
    return {
        "original":     original or "",
        "transformed":  transformed or "",
        "upper":        (original or "").upper(),
        "lower":        (original or "").lower(),
        "reverse":      (original or "")[::-1],
        "first_word":   words[0] if words else "",
        "last_word":    words[-1] if words else "",
        "word_count":   str(len(words)),
        "char_count":   str(len(original or "")),
        "author":       author_name or "",
        "author_id":    author_id or "",
        "channel":      channel_name or "",
        "channel_id":   channel_id or "",
    }


def render_template(template: str, context: Dict[str, str]) -> str:
    """Sustituye tokens `{name}` en `template` por el valor en `context`.

    Tokens desconocidos se dejan literales. Ideal para construir el contenido
    de `impersonate` a partir del mensaje original.
    """
    if not template:
        return context.get("transformed", "")

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))

    return _TOKEN_RE.sub(_sub, template)


def compose(
    *,
    original: str,
    template: Optional[str],
    transforms: Optional[List[Dict[str, Any]]],
    author_name: str = "",
    author_id: str = "",
    channel_name: str = "",
    channel_id: str = "",
) -> str:
    """Pipeline completo: aplica transforms al original, arma contexto, renderiza template.

    Si no hay template → devuelve el texto transformado directamente.
    Si no hay transforms → `transformed` == `original`.
    """
    transformed = apply_transforms(original or "", transforms or [])
    ctx = build_context(
        original=original,
        transformed=transformed,
        author_name=author_name,
        author_id=author_id,
        channel_name=channel_name,
        channel_id=channel_id,
    )
    if template:
        return render_template(template, ctx)
    return transformed
