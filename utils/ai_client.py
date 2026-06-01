"""
DjinnAIClient — Singleton wrapper around google.genai.Client.

All subsystems (orchestrator, card_generator) share this single
client instance. Eliminates redundant connections and enables future context
caching across all LLM calls.
"""

from __future__ import annotations

import logging
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger("djinn.ai_client")

_instance: Optional["DjinnAIClient"] = None


class DjinnAIClient:
    """Singleton Google AI client shared across all subsystems."""

    def __init__(self, api_key: str, model_name: str) -> None:
        self._api_key = api_key
        self.model_name = model_name
        self._client: Optional[genai.Client] = None

    def load(self) -> bool:
        """Initialize the underlying genai.Client."""
        if self._client is not None:
            return True
        try:
            self._client = genai.Client(api_key=self._api_key)
            logger.info("DjinnAIClient: OK — modelo %s", self.model_name)
            return True
        except Exception:
            logger.exception("DjinnAIClient: error inicializando.")
            return False

    @property
    def ready(self) -> bool:
        return self._client is not None

    @property
    def client(self) -> Optional[genai.Client]:
        return self._client

    async def generate_content(self, *, model: Optional[str] = None, **kwargs):
        """Async generate_content passthrough."""
        if not self._client:
            raise RuntimeError("DjinnAIClient not loaded.")
        return await self._client.aio.models.generate_content(
            model=model or self.model_name, **kwargs
        )


def get_ai_client() -> Optional[DjinnAIClient]:
    """Return the global singleton (None if not initialized)."""
    return _instance


def init_ai_client(api_key: str, model_name: str) -> DjinnAIClient:
    """Initialize and return the global singleton."""
    global _instance
    if _instance is None:
        _instance = DjinnAIClient(api_key, model_name)
        _instance.load()
    return _instance
