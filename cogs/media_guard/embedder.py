"""ONNX-based MobileNetV3-Small embedding extractor.

Extracts the 1280-dimensional penultimate layer (global average pooling)
from MobileNetV3-Small, L2-normalized. Operates entirely in-memory on
CPU, optimized for ARM Neoverse N1 via ONNX Runtime.

Gracefully degrades if the model file is not found — returns None
embeddings and logs warnings, allowing the cog to run without the
detection pipeline.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger("djinn.mediaguard.embedder")

# ImageNet normalization constants (MobileNetV3-Small expects these)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# MobileNetV3-Small input size
INPUT_SIZE = 224


class Embedder:
    """MobileNetV3-Small ONNX embedding extractor."""

    def __init__(self, model_path: str | None = None):
        """Initialize embedder.

        Args:
            model_path: Path to ONNX model file.
                        Defaults to MEDIAGUARD_MODEL_PATH env var
                        or 'data/mobilenetv3_small.onnx'.
        """
        self._session = None
        self._input_name: str = ""
        self._output_name: str = ""
        self._available: bool = False

        if model_path is None:
            from .thresholds import DEFAULT_MODEL_PATH, MODEL_PATH_ENV
            model_path = os.environ.get(MODEL_PATH_ENV, DEFAULT_MODEL_PATH)

        self._model_path = Path(model_path)
        self._load_model()

    @property
    def available(self) -> bool:
        """Whether the embedder is ready to generate embeddings."""
        return self._available

    def embed_image(self, image: Image.Image) -> Optional[np.ndarray]:
        """Generate a 1280-D L2-normalized embedding for a PIL Image.

        Args:
            image: RGB PIL Image (will be resized to 224x224).

        Returns:
            numpy array of shape (1280,) or None if embedder unavailable.
        """
        if not self._available:
            return None

        try:
            tensor = self._preprocess(image)
            outputs = self._session.run([self._output_name], {self._input_name: tensor})
            embedding = outputs[0][0]  # shape: (1280,)
            # L2 normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding.astype(np.float32)
        except Exception as e:
            logger.debug("Embedding extraction failed: %s", e)
            return None

    def embed_gif_frames(self, frames: list[Image.Image]) -> Optional[np.ndarray]:
        """Generate a mean embedding across GIF frames.

        Args:
            frames: List of PIL Images (RGB, 224x224 preprocessed).

        Returns:
            L2-normalized mean embedding of shape (1280,) or None.
        """
        if not frames:
            return None

        embeddings = []
        for frame in frames:
            emb = self.embed_image(frame)
            if emb is not None:
                embeddings.append(emb)

        if not embeddings:
            return None

        mean_emb = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(mean_emb)
        if norm > 0:
            mean_emb = mean_emb / norm
        return mean_emb.astype(np.float32)

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess a PIL Image to ONNX tensor.

        Steps: resize → RGB → numpy → normalize → NCHW → batch dim.
        """
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize to 224x224
        image = image.resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)

        # Convert to numpy array (HWC, 0-255)
        arr = np.asarray(image, dtype=np.float32) / 255.0

        # Normalize with ImageNet stats
        arr = (arr - IMAGENET_MEAN) / IMAGENET_STD

        # HWC → CHW → NCHW (add batch dimension)
        arr = np.transpose(arr, (2, 0, 1))  # CHW
        arr = np.expand_dims(arr, axis=0)   # NCHW (1, 3, 224, 224)

        return arr.astype(np.float32)

    def _load_model(self) -> None:
        """Load the ONNX model and discover input/output names."""
        try:
            import onnxruntime as ort
        except ImportError:
            logger.warning(
                "onnxruntime not installed. Install with: "
                "pip install onnxruntime"
            )
            self._available = False
            return

        if not self._model_path.exists():
            logger.warning(
                "ONNX model not found at %s. Run scripts/download_mobilenet_onnx.py "
                "to download and export the model.",
                self._model_path,
            )
            self._available = False
            return

        try:
            # Use CPU execution provider (optimized for ARM via ONNX Runtime)
            providers = ["CPUExecutionProvider"]
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            # Enable memory optimizations
            sess_options.enable_mem_pattern = True
            sess_options.enable_cpu_mem_arena = True

            self._session = ort.InferenceSession(
                str(self._model_path),
                sess_options=sess_options,
                providers=providers,
            )

            # Discover input/output names
            self._input_name = self._session.get_inputs()[0].name
            self._output_name = self._session.get_outputs()[0].name

            # Verify input shape
            input_shape = self._session.get_inputs()[0].shape
            expected = [1, 3, INPUT_SIZE, INPUT_SIZE]
            if input_shape != expected:
                logger.warning(
                    "Model input shape %s differs from expected %s. "
                    "Embeddings may be incorrect.",
                    input_shape, expected,
                )

            # Verify output dimension matches EMBEDDING_DIM
            from .thresholds import EMBEDDING_DIM
            output_shape = self._session.get_outputs()[0].shape
            if len(output_shape) >= 2 and output_shape[1] != EMBEDDING_DIM:
                logger.error(
                    "Model output dimension %d does not match EMBEDDING_DIM=%d. "
                    "Update thresholds.py EMBEDDING_DIM or use a different model.",
                    output_shape[1], EMBEDDING_DIM,
                )
                self._available = False
                return

            self._available = True
            logger.info(
                "Embedder loaded: %s → %s → %s  (dim=%d)",
                self._model_path.name,
                self._input_name,
                self._output_name,
                output_shape[1] if len(output_shape) >= 2 else "?",
            )

        except Exception as e:
            logger.error("Failed to load ONNX model: %s", e)
            self._available = False
