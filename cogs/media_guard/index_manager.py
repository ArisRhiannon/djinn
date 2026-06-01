"""HNSW vector index manager for banned media embeddings.

Wraps hnswlib for fast approximate nearest neighbor search with
cosine distance. Persists the index to disk and maintains a JSON
metadata file for banned media entries.

Degrades gracefully if hnswlib is not installed — returns empty
results without crashing the cog.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .thresholds import (
    EMBEDDING_DIM,
    HNSW_EF_CONSTRUCTION,
    HNSW_EF_SEARCH,
    HNSW_M,
    INDEX_PATH,
    MAX_BANNED_ELEMENTS,
    META_PATH,
)

logger = logging.getLogger("djinn.mediaguard.index")


class IndexManager:
    """HNSW vector index for banned media with JSON metadata."""

    def __init__(self, index_path: str | None = None, meta_path: str | None = None):
        """Initialize the index manager.

        Args:
            index_path: Path to the hnswlib index file.
            meta_path: Path to the JSON metadata file.
        """
        self._index_path = Path(index_path or INDEX_PATH)
        self._meta_path = Path(meta_path or META_PATH)
        self._index = None
        self._id_map: Dict[int, str] = {}  # internal_id → media_uuid
        self._next_id: int = 0
        self._available: bool = False

    @property
    def available(self) -> bool:
        """Whether the index is ready for queries."""
        return self._available

    @property
    def num_banned(self) -> int:
        """Number of banned media entries."""
        if not self._available or self._index is None:
            return 0
        return self._index.element_count

    def add_media(
        self,
        embeddings: List[np.ndarray],
        media_type: str,
        added_by: int,
        source_url: str = "",
    ) -> Optional[str]:
        """Add banned media embeddings to the index.

        Args:
            embeddings: List of frame embeddings (single image = 1 embedding,
                       GIF = multiple frame embeddings).
            media_type: "image" or "gif".
            added_by: Discord user ID who added the media.
            source_url: Original URL of the media.

        Returns:
            UUID of the new entry, or None if index unavailable.
        """
        if not self._available or not self._index:
            logger.warning("Index not available, cannot add media")
            return None

        if not embeddings:
            logger.debug("No embeddings provided for add_media")
            return None

        media_uuid = str(uuid.uuid4())[:12]  # Short UUID for display

        # Assign internal IDs
        ids = []
        for i, emb in enumerate(embeddings):
            internal_id = self._next_id
            self._next_id += 1
            self._id_map[internal_id] = f"{media_uuid}_frame_{i}"
            ids.append(internal_id)

        # Insert into index
        try:
            emb_array = np.array(embeddings, dtype=np.float32)
            self._index.add_items(emb_array, np.array(ids, dtype=np.int64))
        except Exception as e:
            logger.error("hnswlib insert failed: %s", e)
            # Rollback IDs
            for iid in ids:
                self._id_map.pop(iid, None)
            self._next_id -= len(ids)
            return None

        # Save metadata
        self._save_metadata_entry(media_uuid, {
            "type": media_type,
            "added_by": added_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_url": source_url,
            "num_frames": len(embeddings),
            "internal_ids": ids,
        })

        # Persist
        self.save()

        logger.info(
            "Media banned: %s (%s, %d frames, by user %d)",
            media_uuid, media_type, len(embeddings), added_by,
        )
        return media_uuid

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 3,
    ) -> List[Tuple[str, float]]:
        """Search for nearest banned media.

        Args:
            query_embedding: L2-normalized embedding of shape (1280,).
            k: Number of nearest neighbors to return.

        Returns:
            List of (media_uuid, cosine_similarity) tuples,
            sorted by similarity descending.
        """
        if not self._available or not self._index:
            return []

        if self._index.element_count == 0:
            return []

        try:
            emb = np.array([query_embedding], dtype=np.float32)
            labels, distances = self._index.knn_query(emb, k=min(k, self._index.element_count))

            results = []
            for label, distance in zip(labels[0], distances[0]):
                if label < 0:
                    continue
                # hnswlib with 'cosine' returns cosine distance in [0, 2]
                # 0 = identical, 2 = opposite
                similarity = 1.0 - (distance / 2.0)
                # Get media UUID from the label
                full_id = self._id_map.get(int(label), f"unknown_{label}")
                # Extract base UUID (strip _frame_X suffix)
                base_uuid = full_id.rsplit("_frame_", 1)[0]
                results.append((base_uuid, float(similarity)))

            # Deduplicate (keep highest similarity per UUID)
            deduped: Dict[str, float] = {}
            for uid, sim in results:
                if uid not in deduped or sim > deduped[uid]:
                    deduped[uid] = sim

            return sorted(deduped.items(), key=lambda x: x[1], reverse=True)

        except Exception as e:
            logger.debug("hnswlib search failed: %s", e)
            return []

    def save(self) -> bool:
        """Persist index and metadata to disk."""
        if not self._available or self._index is None:
            return False

        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            self._index.save_index(str(self._index_path))
            logger.debug("Index saved: %d elements", self._index.element_count)
            return True
        except Exception as e:
            logger.error("Failed to save index: %s", e)
            return False

    def load(self) -> bool:
        """Initialize or load the index from disk."""
        try:
            import hnswlib
        except ImportError:
            logger.warning(
                "hnswlib not installed. Install with: pip install hnswlib"
            )
            self._available = False
            return False

        # Create index
        self._index = hnswlib.Index(space="cosine", dim=EMBEDDING_DIM)

        if self._index_path.exists():
            # Load existing index
            try:
                self._index.load_index(
                    str(self._index_path),
                    max_elements=MAX_BANNED_ELEMENTS,
                )
                self._index.set_ef(HNSW_EF_SEARCH)

                # Rebuild ID map from metadata
                self._rebuild_id_map()
                self._next_id = max(self._id_map.keys(), default=-1) + 1

                logger.info(
                    "Index loaded: %d elements from %s",
                    self._index.element_count,
                    self._index_path,
                )
            except Exception as e:
                logger.error("Failed to load index, creating new: %s", e)
                self._init_new_index()
        else:
            # Create new index
            self._init_new_index()

        self._available = True
        return True

    def _init_new_index(self) -> None:
        """Initialize a fresh empty index."""
        if self._index is None:
            return

        self._index.init_index(
            max_elements=MAX_BANNED_ELEMENTS,
            ef_construction=HNSW_EF_CONSTRUCTION,
            M=HNSW_M,
        )
        self._index.set_ef(HNSW_EF_SEARCH)
        self._id_map = {}
        self._next_id = 0
        logger.info("New index created (capacity: %d)", MAX_BANNED_ELEMENTS)

    def _rebuild_id_map(self) -> None:
        """Rebuild the internal ID → UUID map from metadata JSON."""
        self._id_map = {}
        if not self._meta_path.exists():
            return

        try:
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            entries = meta.get("entries", {})
            for uuid_str, entry in entries.items():
                for iid in entry.get("internal_ids", []):
                    self._id_map[iid] = f"{uuid_str}_frame_{iid}"
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Failed to read metadata: %s", e)

    def _save_metadata_entry(self, uuid_str: str, entry: dict) -> None:
        """Append or update a metadata entry."""
        meta = {}
        if self._meta_path.exists():
            try:
                meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        meta.setdefault("version", 1)
        meta.setdefault("entries", {})[uuid_str] = entry

        try:
            self._meta_path.parent.mkdir(parents=True, exist_ok=True)
            self._meta_path.write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to write metadata: %s", e)

    def get_metadata(self, uuid_str: str) -> Optional[dict]:
        """Get metadata for a specific banned media entry."""
        if not self._meta_path.exists():
            return None
        try:
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            return meta.get("entries", {}).get(uuid_str)
        except (json.JSONDecodeError, KeyError, OSError):
            return None
