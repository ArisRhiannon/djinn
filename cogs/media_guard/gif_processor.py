"""GIF frame extraction using Pillow.

Extracts N equally-spaced frames from a GIF for multi-frame
embedding generation. Handles corrupted GIFs and edge cases
(single-frame, animated without looping, etc.) gracefully.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import List

from PIL import Image, ImageSequence

from .thresholds import DEFAULT_GIF_FRAMES, MAX_GIF_FRAMES

logger = logging.getLogger("youkai.mediaguard.gif")


def is_gif(data: bytes) -> bool:
    """Check if raw bytes are a GIF by magic number."""
    return data[:6] in (b"GIF89a", b"GIF87a")


def extract_frames(data: bytes, n: int | None = None) -> List[Image.Image]:
    """Extract up to N equally-spaced frames from a GIF.

    Args:
        data: Raw GIF bytes.
        n: Number of frames to extract (default: 5 for short GIFs, 10 for long).

    Returns:
        List of PIL Image objects in RGB mode.
        Returns empty list for corrupted/non-GIF data.
    """
    try:
        img = Image.open(BytesIO(data))
    except Exception:
        logger.debug("Failed to open GIF (corrupted or non-image data)")
        return []

    # Count total frames
    try:
        num_frames = 0
        for _ in ImageSequence.Iterator(img):
            num_frames += 1
    except Exception:
        logger.debug("GIF frame enumeration failed")
        return []

    if num_frames == 0:
        return []

    # Single frame: just return it
    if num_frames == 1:
        try:
            img.seek(0)
            return [img.convert("RGB")]
        except Exception:
            return []

    # Determine frames to extract
    if n is None:
        n = DEFAULT_GIF_FRAMES if num_frames <= 50 else MAX_GIF_FRAMES
    n = min(n, num_frames)  # Can't extract more than available

    # Choose equally-spaced frame indices
    if n == 1:
        indices = [0]
    else:
        step = (num_frames - 1) / (n - 1)
        indices = [round(i * step) for i in range(n)]
        # Deduplicate in case of rounding collisions
        indices = sorted(set(indices))
        if len(indices) < n and indices[-1] < num_frames - 1:
            indices.append(num_frames - 1)

    frames: List[Image.Image] = []
    for idx in indices:
        try:
            img.seek(idx)
            frames.append(img.convert("RGB"))
        except (EOFError, OSError, ValueError) as e:
            logger.debug("GIF seek to frame %d failed: %s", idx, e)
            continue

    return frames


def extract_first_frame(data: bytes) -> Image.Image | None:
    """Extract only the first frame of a GIF (fallback)."""
    frames = extract_frames(data, n=1)
    return frames[0] if frames else None
