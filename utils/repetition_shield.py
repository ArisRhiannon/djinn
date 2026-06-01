"""
Repetition Shield — detección local de respuestas LLM en loop/spam.

5 heurísticas O(n) sin IA:
1. N-gram overlap (frases repetidas)
2. Entropía de Shannon (texto predecible)
3. Ratio de líneas duplicadas
4. Bloque repetido más largo
5. Longitud extrema

Uso:
    result = RepetitionShield.check(text)
    if not result.clean:
        text = result.trimmed_text  # recortado al último punto bueno
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Set


# ── Umbrales (tuneables) ──────────────────────────────────────────────────

NGRAM_SIZE: int = 5             # palabras por n-grama
NGRAM_OVERLAP_THRESHOLD: float = 0.30  # 30%+ de n-gramas duplicados → spam
ENTROPY_THRESHOLD: float = 2.0  # entropía < 2.0 → texto repetitivo
LINE_DUP_THRESHOLD: float = 0.40  # 40%+ de líneas duplicadas → loop
MIN_REPEAT_BLOCK_RATIO: float = 0.50  # bloque repetido ocupa >50% del texto
MIN_REPEAT_COUNT: int = 3       # un bloque debe repetirse 3+ veces
SHIELD_MIN_TEXT_LEN: int = 100  # no analizar textos < 100 chars
MAX_RESPONSE_CHARS: int = 8000  # techo de chars (≈4 mensajes Discord)
MIN_TRIM_LEN: int = 50         # si tras recortar queda < 50 chars, descartar


@dataclass
class ShieldResult:
    clean: bool = True
    reason: str = ""
    score: float = 0.0        # 0.0-1.0, cuán repetitivo
    trimmed_text: str = ""


class RepetitionShield:
    """Analiza texto de respuesta LLM para detectar loops de repetición."""

    @staticmethod
    def check(text: str) -> ShieldResult:
        """Pasa el texto por las 5 heurísticas y devuelve resultado."""
        if not text or len(text) < SHIELD_MIN_TEXT_LEN:
            return ShieldResult(clean=True, trimmed_text=text)

        reasons: List[str] = []
        scores: List[float] = []

        # ── Capa 1: N-gram overlap ───────────────────────────────────
        ngram_score = RepetitionShield._ngram_overlap(text)
        if ngram_score >= NGRAM_OVERLAP_THRESHOLD:
            reasons.append("ngram_overlap")
            scores.append(ngram_score)

        # ── Capa 2: Entropía de Shannon ──────────────────────────────
        entropy = RepetitionShield._shannon_entropy(text)
        if entropy < ENTROPY_THRESHOLD:
            # Normalizar score: entropía 0 = score 1.0, entropía = threshold = score 0.5
            ent_score = max(0.0, 1.0 - (entropy / ENTROPY_THRESHOLD))
            reasons.append("low_entropy")
            scores.append(ent_score)

        # ── Capa 3: Líneas duplicadas ────────────────────────────────
        line_score = RepetitionShield._line_duplication_ratio(text)
        if line_score >= LINE_DUP_THRESHOLD:
            reasons.append("line_duplication")
            scores.append(line_score)

        # ── Capa 4: Bloque repetido más largo ────────────────────────
        block_score = RepetitionShield._longest_repeated_block(text)
        if block_score >= MIN_REPEAT_BLOCK_RATIO:
            reasons.append("repeated_block")
            scores.append(block_score)

        # ── Capa 5: Longitud extrema ─────────────────────────────────
        if len(text) > MAX_RESPONSE_CHARS:
            reasons.append("excessive_length")
            scores.append(min(len(text) / MAX_RESPONSE_CHARS - 1.0, 1.0))

        # ── Veredicto ─────────────────────────────────────────────────
        # Se requiere al menos 1 heurística positiva O longitud extrema
        is_spam = len(reasons) >= 1
        avg_score = sum(scores) / len(scores) if scores else 0.0

        if not is_spam:
            return ShieldResult(clean=True, trimmed_text=text)

        # ── Recortar al último punto bueno ────────────────────────────
        trimmed = RepetitionShield._find_last_good_text(text)

        return ShieldResult(
            clean=False,
            reason="|".join(reasons),
            score=round(avg_score, 3),
            trimmed_text=trimmed,
        )

    # ── Heurísticas ───────────────────────────────────────────────────

    @staticmethod
    def _ngram_overlap(text: str) -> float:
        """Ratio de n-gramas (5 palabras) que aparecen más de una vez."""
        words = text.lower().split()
        if len(words) < NGRAM_SIZE:
            return 0.0
        ngrams = [
            " ".join(words[i : i + NGRAM_SIZE])
            for i in range(len(words) - NGRAM_SIZE + 1)
        ]
        if not ngrams:
            return 0.0
        counts = Counter(ngrams)
        dupes = sum(1 for ng, c in counts.items() if c > 1)
        return dupes / len(counts)

    @staticmethod
    def _shannon_entropy(text: str) -> float:
        """Entropía de Shannon por carácter. Baja = repetitivo."""
        if not text:
            return 0.0
        counts = Counter(text)
        length = len(text)
        entropy = 0.0
        for count in counts.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def _line_duplication_ratio(text: str) -> float:
        """Ratio de líneas no vacías que son duplicados de otra línea."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 2:
            return 0.0
        seen: Set[str] = set()
        dupes = 0
        for line in lines:
            norm = line.lower().rstrip(".,;:!?…—–- ")
            if norm in seen:
                dupes += 1
            else:
                seen.add(norm)
        return dupes / len(lines)

    @staticmethod
    def _longest_repeated_block(text: str) -> float:
        """Ratio del bloque más largo que se repite 3+ veces."""
        # Buscar substrings que se repiten usando ventanas de tamaño decreciente
        text_len = len(text)
        if text_len < 30:
            return 0.0

        # Probar bloques de 20+ chars
        max_ratio = 0.0
        for block_len in range(min(text_len // MIN_REPEAT_COUNT, 500), 19, -20):
            blocks: Counter = Counter()
            for i in range(0, text_len - block_len + 1, max(block_len // 2, 10)):
                block = text[i : i + block_len]
                blocks[block] += 1
            for block, count in blocks.items():
                if count >= MIN_REPEAT_COUNT:
                    ratio = (len(block) * count) / text_len
                    max_ratio = max(max_ratio, ratio)
            if max_ratio >= MIN_REPEAT_BLOCK_RATIO:
                break  # ya encontramos, no seguir buscando

        return min(max_ratio, 1.0)

    # ── Recorte inteligente ────────────────────────────────────────────

    @staticmethod
    def _find_last_good_text(text: str) -> str:
        """Encuentra el punto donde la repetición empieza y recorta ahí.

        Estrategia: recorrer el texto por párrafos/oraciones y encontrar
        el punto donde la entropía cae o la repetición de n-gramas sube.
        Si no se encuentra un punto claro, truncar a MAX_RESPONSE_CHARS.
        """
        if len(text) <= MAX_RESPONSE_CHARS:
            # El texto no es excesivamente largo pero es repetitivo —
            # buscar el último párrafo "bueno"
            return RepetitionShield._trim_at_repetition_start(text)

        # Longitud extrema: truncar a MAX_RESPONSE_CHARS respetando párrafos
        truncated = text[:MAX_RESPONSE_CHARS]
        # Buscar el último salto de párrafo completo
        for sep in ["\n\n", "\n", ". "]:
            idx = truncated.rfind(sep)
            if idx > len(truncated) // 2:
                truncated = truncated[: idx + len(sep)]
                break

        # Verificar si la parte truncada también es repetitiva
        partial = RepetitionShield._trim_at_repetition_start(truncated)
        if len(partial) >= MIN_TRIM_LEN:
            return partial
        return truncated

    @staticmethod
    def _trim_at_repetition_start(text: str) -> str:
        """Recorta en el punto donde la repetición comienza.

        Divide el texto en segmentos de ~500 chars y calcula la entropía
        de cada uno. Corta donde la entropía cae abruptamente o donde
        el n-gram overlap sube.
        """
        SEGMENT_SIZE = 500
        segments = []
        for i in range(0, len(text), SEGMENT_SIZE):
            seg = text[i : i + SEGMENT_SIZE]
            if seg.strip():
                segments.append((i, seg))

        if len(segments) <= 1:
            return text[:MIN_TRIM_LEN] if len(text) >= MIN_TRIM_LEN else ""

        # Calcular entropía y overlap por segmento
        good_up_to = len(text)
        for idx, (start, seg) in enumerate(segments):
            if idx < 1:
                continue
            ent = RepetitionShield._shannon_entropy(seg)
            overlap = RepetitionShield._ngram_overlap(seg)

            # Si entropía baja Y overlap alto → aquí empieza la repetición
            if ent < ENTROPY_THRESHOLD * 0.7 and overlap > NGRAM_OVERLAP_THRESHOLD:
                good_up_to = start
                break
            # Si overlap extremo (>50%) → corte seguro
            if overlap > 0.50:
                good_up_to = start
                break

        trimmed = text[:good_up_to].rstrip()

        # Último recurso: si quedó muy corto, tomar al menos el primer segmento
        if len(trimmed) < MIN_TRIM_LEN and len(segments) > 0:
            first_end = segments[0][0] + len(segments[0][1])
            trimmed = text[:first_end].rstrip()

        return trimmed


def smart_chunk(text: str, max_chunk: int = 1900, max_chunks: int = 5) -> List[str]:
    """Divide texto en chunks respetando word/sentence boundaries.

    Prioridad de corte: párrafo → oración → palabra.
    Nunca corta a mitad de palabra o markdown.
    """
    if len(text) <= max_chunk:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining and len(chunks) < max_chunks:
        if len(remaining) <= max_chunk:
            chunks.append(remaining)
            break

        # Buscar punto de corte dentro del rango [max_chunk*0.7, max_chunk]
        window = remaining[: max_chunk + 200]

        # 1. Cortar en párrafo (\n\n)
        best_cut = -1
        for sep in ["\n\n", "\n"]:
            idx = window.rfind(sep, max_chunk * 7 // 10, max_chunk)
            if idx > best_cut:
                best_cut = idx + len(sep)

        # 2. Cortar en oración (. ! ? seguido de espacio o newline)
        if best_cut <= 0:
            sentence_end = re.compile(r'[.!?]\s')
            for match in sentence_end.finditer(window, max_chunk * 7 // 10, max_chunk):
                best_cut = match.end()

        # 3. Cortar en palabra (último espacio)
        if best_cut <= 0:
            idx = window.rfind(" ", max_chunk * 7 // 10, max_chunk)
            if idx > 0:
                best_cut = idx + 1

        # 4. Fallback: cortar en max_chunk
        if best_cut <= 0:
            best_cut = max_chunk

        chunk = remaining[:best_cut].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[best_cut:].lstrip("\n")

    # Truncation notice si quedó texto pendiente
    if remaining and len(chunks) == max_chunks:
        chunks[-1] = chunks[-1].rstrip() + "\n\n*[...respuesta truncada]*"

    return chunks
