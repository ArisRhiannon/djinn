#!/usr/bin/env python3
"""Pre-descarga de los modelos OPUS-MT usados por la Maldición.

La feature de `curse_translator` necesita 5 modelos MarianMT (español → X)
desde HuggingFace. `from_pretrained(...)` los descarga en `~/.cache/huggingface/`
en el primer uso, lo que bloquea el arranque del bot y consume ~1.5 GB de
tráfico en `on_ready` la primera vez (a veces con fallos por rate-limit).

Este script los baja una sola vez, antes de arrancar. Es seguro correrlo
varias veces: detecta los que ya están en caché y los salta.

Uso:
    python scripts/download_opusmt.py

Se ejecuta automáticamente desde install.sh.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Desactivar barras de progreso ruidosas en CI
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

# Modelos usados por utils/curse_translator.py (mantener sincronizado con SUPPORTED_LANGS).
MODELS: list[tuple[str, str]] = [
    ("islandés",   "Helsinki-NLP/opus-mt-es-is"),
    ("maltés",     "Helsinki-NLP/opus-mt-es-mt"),
    ("xhosa",      "Helsinki-NLP/opus-mt-es-xh"),
    ("papiamento", "Helsinki-NLP/opus-mt-es-pap"),
    ("esperanto",  "Helsinki-NLP/opus-mt-es-eo"),
]


def main() -> int:
    try:
        from transformers import MarianMTModel, MarianTokenizer
    except ImportError:
        print("ERROR: transformers no instalado. Ejecutá primero:", file=sys.stderr)
        print("  pip install -r requirements.txt", file=sys.stderr)
        return 1

    # Requerido por MarianTokenizer
    try:
        import sentencepiece  # noqa: F401
    except ImportError:
        print("ERROR: sentencepiece no instalado (requerido por MarianTokenizer).",
              file=sys.stderr)
        print("  pip install sentencepiece", file=sys.stderr)
        return 1

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not hf_token:
        print("⚠ Sin HF_TOKEN en el entorno — posible rate-limit. "
              "Configurá uno en .env para descargas más rápidas.\n")

    print(f"Descargando {len(MODELS)} modelos OPUS-MT "
          f"(~1.2 GB total, se cachean en ~/.cache/huggingface/)\n")

    failed: list[str] = []
    for idx, (name, model_id) in enumerate(MODELS, 1):
        print(f"[{idx}/{len(MODELS)}] {name:<12} ({model_id}) …", end=" ", flush=True)
        try:
            MarianTokenizer.from_pretrained(model_id, token=hf_token)
            MarianMTModel.from_pretrained(model_id, token=hf_token)
            print("✓")
        except Exception as exc:
            print(f"✗  ({type(exc).__name__}: {exc})")
            failed.append(model_id)

    print()
    if failed:
        print(f"⚠ {len(failed)} modelo(s) fallaron: {', '.join(failed)}")
        print("  CurseTranslator seguirá funcionando con los que sí cargaron.")
        return 2
    print(f"✅ Todos los modelos listos en: {Path.home() / '.cache/huggingface/hub'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
