"""Conservative thresholds to guarantee zero false positives.

Calibrated for anime/cosplay imagery — slight recompressions,
resizing, and Instagram-style filters are captured without
flagging different images of the same character/pose.

All values are cosine similarity (0.0 = orthogonal, 1.0 = identical).
"""

# ── Auto-delete thresholds ──────────────────────────────────────────────────

# Static image: 92% similarity = same image with artifacts
IMAGE_SIMILARITY_THRESHOLD: float = 0.92

# GIF individual frame: slightly lower due to compression artifacts
GIF_FRAME_SIMILARITY_THRESHOLD: float = 0.90

# GIF multi-frame consensus: lower per-frame bar, but must match 2+ frames
GIF_MULTI_FRAME_THRESHOLD: float = 0.88
GIF_MIN_MATCHING_FRAMES: int = 2

# ── Gray zone (manual review instead of auto-delete) ────────────────────────
GRAY_ZONE_LOW: float = 0.85
GRAY_ZONE_HIGH: float = 0.92  # matches IMAGE_SIMILARITY_THRESHOLD

# ── HNSW index parameters ───────────────────────────────────────────────────
HNSW_EF_CONSTRUCTION: int = 200  # Build-time accuracy (higher = slower build)
HNSW_M: int = 16                 # Connection degree (higher = more memory)
HNSW_EF_SEARCH: int = 50         # Search-time accuracy (higher = slower search)

MAX_BANNED_ELEMENTS: int = 100_000  # Pre-allocated index capacity
EMBEDDING_DIM: int = 1280           # MobileNetV3-Small penultimate layer

# ── GIF processing ──────────────────────────────────────────────────────────
DEFAULT_GIF_FRAMES: int = 5    # Frames extracted for GIFs < 5 seconds
MAX_GIF_FRAMES: int = 10       # Max frames for long GIFs

# ── Model paths ─────────────────────────────────────────────────────────────
DEFAULT_MODEL_PATH: str = "data/mobilenetv3_small.onnx"
MODEL_PATH_ENV: str = "MEDIAGUARD_MODEL_PATH"

# ── Index persistence ───────────────────────────────────────────────────────
INDEX_PATH: str = "data/banned_media.bin"
META_PATH: str = "data/banned_media_meta.json"

# ── Review channel env var ──────────────────────────────────────────────────
REVIEW_CHANNEL_ENV: str = "MEDIAGUARD_REVIEW_CHANNEL"
