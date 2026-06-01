"""
Motor de embeddings — all-MiniLM-L6-v2.

Dos funciones principales:
  1. Recuperación de respuestas tipo "Fairy": dado un contexto de acción,
     encuentra la plantilla de respuesta más apropiada del banco de respuestas.
  2. Pre-clasificación de intención: ¿es esto un comando de moderación,
     una pregunta, o conversación? (para decidir si pasar a Gemma o no).

¿Tiene sentido usar MiniLM para respuestas? SÍ.
  - Velocidad: inferencia en ~10ms vs ~500ms de Gemma
  - Consistencia: las respuestas pre-escritas mantienen la personalidad de Fairy
  - Sin generación: no hay riesgo de respuestas "out of character"
  - El modelo solo se usa para similitud semántica, no generación
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger


class IntentType(Enum):
    MODERATION = auto()      # ban, kick, mute, warn, purge, etc.
    QUERY = auto()           # preguntar sobre un usuario, el servidor, etc.
    CONFIG = auto()          # configurar algo del servidor
    CHAT = auto()            # conversación general / no comando
    UNKNOWN = auto()


@dataclass
class ResponseMatch:
    template: str
    context_key: str
    score: float


class EmbedEngine:
    """Recuperación semántica de respuestas y clasificación de intención."""

    # Ejemplos de cada intención para el clasificador de zero-shot
    _INTENT_EXAMPLES: Dict[IntentType, List[str]] = {
        IntentType.MODERATION: [
            "banea a ese usuario", "silencia a @usuario por 10 minutos",
            "expulsa al spammer", "pon slowmode", "bloquea el canal",
            "borra esos mensajes", "advierte a ese usuario", "quita el mute",
        ],
        IntentType.QUERY: [
            "cuántos miembros tiene el servidor", "qué roles tiene @usuario",
            "muéstrame la info del servidor", "cuántas advertencias tiene",
            "información de ese usuario",
        ],
        IntentType.CONFIG: [
            "crea un canal de texto", "asigna el rol a @usuario",
            "edita ese rol", "cambia el apodo", "crea una encuesta",
            "haz un anuncio en ese canal",
        ],
        IntentType.CHAT: [
            "hola", "cómo estás", "gracias", "buen trabajo",
            "qué opinas", "me alegra que estés aquí", "fairy eres genial",
        ],
    }

    def __init__(self, config):
        self.config = config
        self._model = None
        self._responses: List[Dict] = []
        self._response_embeddings: Optional[np.ndarray] = None
        self._intent_embeddings: Dict[IntentType, np.ndarray] = {}

    def load(self):
        """Carga el modelo y pre-computa embeddings. Llamar en executor."""
        try:
            # Suppress tqdm progress bars from sentence-transformers internals
            os.environ.setdefault("TQDM_DISABLE", "1")
            from sentence_transformers import SentenceTransformer
            t0 = time.time()
            self._model = SentenceTransformer(
                self.config.embed_model,
                cache_folder=self.config.embed_cache_dir,
                device="cpu",
            )
            elapsed = time.time() - t0
            logger.info("MiniLM cargado en {:.1f}s", elapsed)

            self._load_responses()
            self._precompute_intent_embeddings()
            logger.info(
                "EmbedEngine listo: {} respuestas | {} clases de intención",
                len(self._responses), len(self._intent_embeddings),
            )
        except ImportError:
            logger.warning("sentence-transformers no instalado: pip install sentence-transformers")
        except Exception as e:
            logger.exception("Error cargando EmbedEngine: {}", e)

    @property
    def available(self) -> bool:
        return self._model is not None

    def encode(self, texts: List[str], normalize_embeddings: bool = True) -> np.ndarray:
        """Encode texts to embeddings. Shared with Listeners cog to avoid duplicate models."""
        if not self.available:
            raise RuntimeError("EmbedEngine model not loaded")
        return np.array(self._model.encode(texts, normalize_embeddings=normalize_embeddings, show_progress_bar=False))

    def get_response(self, context_description: str, **template_vars) -> str:
        """
        Encuentra la respuesta más apropiada para un contexto dado y
        rellena las variables del template.

        Ejemplo:
          context = "ban ejecutado exitosamente"
          template_vars = {"user": "@SpamBot99", "reason": "spam"}
          → "Procesado. @SpamBot99 ha sido baneado. Razón: spam."
        """
        if not self.available or not self._responses:
            return self._fallback_response(context_description, **template_vars)

        try:
            ctx_emb = self._embed([context_description])[0]
            similarities = np.dot(self._response_embeddings, ctx_emb)
            best_idx = int(np.argmax(similarities))
            best = self._responses[best_idx]
            template = best["template"]

            # Rellenar variables del template
            for key, val in template_vars.items():
                template = template.replace(f"{{{key}}}", str(val))

            return template
        except Exception as e:
            logger.debug("Error en recuperación de respuesta: {}", e)
            return self._fallback_response(context_description, **template_vars)

    def classify_intent(self, text: str) -> Tuple[IntentType, float]:
        """
        Clasifica el intento del mensaje. Retorna (IntentType, confidence).
        Rápido (~10ms) — se usa antes de decidir si invocar Gemma.
        """
        if not self.available or not self._intent_embeddings:
            return IntentType.UNKNOWN, 0.0

        try:
            text_emb = self._embed([text])[0]
            best_intent = IntentType.UNKNOWN
            best_score = -1.0

            for intent, embs in self._intent_embeddings.items():
                # Similitud media con todos los ejemplos de la clase
                scores = np.dot(embs, text_emb)
                score = float(np.mean(scores))
                if score > best_score:
                    best_score = score
                    best_intent = intent

            return best_intent, best_score
        except Exception as e:
            logger.debug("Error clasificando intención: {}", e)
            return IntentType.UNKNOWN, 0.0

    # ── Privado ────────────────────────────────────────────────────────────

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Wrapper de encode con normalización L2."""
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(embeddings)

    def _load_responses(self):
        """Carga el banco de respuestas y pre-computa sus embeddings."""
        path = Path(self.config.responses_path)
        if not path.exists():
            logger.warning("Banco de respuestas no encontrado en {}", path)
            return

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self._responses = data.get("responses", [])
        if not self._responses:
            return

        contexts = [r["context"] for r in self._responses]
        self._response_embeddings = self._embed(contexts)
        logger.debug(f"{len(self._responses)} respuestas cargadas y embebidas")

    def _precompute_intent_embeddings(self):
        """Pre-computa embeddings de los ejemplos de intención."""
        for intent, examples in self._INTENT_EXAMPLES.items():
            self._intent_embeddings[intent] = self._embed(examples)

    @staticmethod
    def _fallback_response(context: str, **kwargs) -> str:
        """Respuesta de emergencia si el sistema de recuperación falla."""
        user = kwargs.get("user", "el usuario")
        if "ban" in context:
            return f"Procesado. {user} ha sido baneado."
        if "mute" in context or "silenc" in context:
            dur = kwargs.get("duration", "")
            return f"Listo. He silenciado a {user}{' por ' + dur if dur else ''}."
        if "kick" in context:
            return f"Expulsado. {user} ha salido del servidor."
        if "warn" in context:
            return f"Advertencia registrada para {user}."
        return "Procesado."
