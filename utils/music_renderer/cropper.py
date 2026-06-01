"""Smart square cropper: face detection (Haar) → smartcrop fallback → center."""
from __future__ import annotations

import io
import logging
from typing import Optional

import cv2
import numpy as np
import smartcrop
from PIL import Image

logger = logging.getLogger("youkai.music_renderer.cropper")

# Load Haar cascade once (frontal face)
_FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def _detect_faces(img_array: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Return list of (x, y, w, h) face bounding boxes."""
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
    )
    return [tuple(f) for f in faces]


def smart_square_crop(image_bytes: bytes, size: int = 320) -> bytes:
    """
    Smart crop to a square:
    1. Detect faces — if found, center on the largest face
    2. Otherwise use smartcrop saliency
    3. Always returns size×size PNG bytes
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        logger.warning("Could not open image: %s", e)
        return image_bytes

    w, h = img.size
    crop_size = min(w, h)

    # Try face detection
    arr = np.array(img)
    faces = _detect_faces(arr)
    cx = cy = None

    if faces:
        # Pick the largest face
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        cx = fx + fw // 2
        cy = fy + fh // 2 - fh // 4  # bias slightly up to include head better
    else:
        # Smartcrop fallback
        try:
            sc = smartcrop.SmartCrop()
            result = sc.crop(img, crop_size, crop_size)
            top_crop = result["top_crop"]
            cx = top_crop["x"] + top_crop["width"] // 2
            cy = top_crop["y"] + top_crop["height"] // 2
        except Exception as e:
            logger.debug("smartcrop failed: %s", e)
            cx, cy = w // 2, h // 2

    # Compute crop box centered on (cx, cy), clamped to image bounds
    half = crop_size // 2
    x0 = max(0, min(cx - half, w - crop_size))
    y0 = max(0, min(cy - half, h - crop_size))
    cropped = img.crop((x0, y0, x0 + crop_size, y0 + crop_size))

    # Resize to target size
    cropped = cropped.resize((size, size), Image.LANCZOS)

    out = io.BytesIO()
    cropped.save(out, format="PNG", optimize=True)
    return out.getvalue()
