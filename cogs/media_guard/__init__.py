"""Cog: MediaGuard — Near-duplicate media detection for Discord.

Uses MobileNetV3-Small ONNX embeddings + hnswlib approximate search
to detect banned images/GIFs and auto-delete them with conservative
thresholds that guarantee zero false positives.

Architecture:
  on_message  → media_resolver (bytes) → gif_processor (frames)
              → embedder (1280-D vectors) → index_manager (hnswlib search)
              → match? auto-delete + log
  /prohibir   → same pipeline → add to index + persist
"""

from __future__ import annotations

import logging

from .cog import MediaGuardCog

logger = logging.getLogger("youkai.mediaguard")


async def setup(bot) -> None:
    """Register the MediaGuard cog."""
    cog = MediaGuardCog(bot)
    try:
        await cog.initialize()
    except Exception as exc:
        logger.warning("MediaGuard initialization failed: %s", exc)
        # Still add the cog — it degrades gracefully with empty index
    await bot.add_cog(cog)
    logger.info("MediaGuard cog loaded")
