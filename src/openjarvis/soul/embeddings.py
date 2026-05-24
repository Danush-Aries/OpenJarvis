"""Embedding engine — lightweight CPU-based text embeddings for semantic memory search.

Uses ``fastembed`` (ONNX Runtime) instead of PyTorch/BERT so it runs efficiently
on Intel i5 with 8GB RAM. No GPU required.

Model: sentence-transformers/all-MiniLM-L6-v2 (384-dim, ~80MB)
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from openjarvis.soul.errors import SoulEmbeddingError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton embedding engine
# ---------------------------------------------------------------------------

_EMBEDDING_DIMENSION = 384


class EmbeddingEngine:
    """Lazy-loaded text embedding engine using fastembed (ONNX Runtime).

    Usage::

        engine = EmbeddingEngine.get_instance()
        vec = engine.embed("some text")
        sim = EmbeddingEngine.cosine_similarity(vec, other_vec)

    If fastembed is not installed or the model fails to load, all methods
    gracefully return None or empty lists so callers can fall back to
    keyword-based retrieval.
    """

    _instance: Optional[EmbeddingEngine] = None
    _model: object = None  # fastembed.TextEmbedding

    def __init__(self) -> None:
        self._model = None
        self._load_attempted = False

    @classmethod
    def get_instance(cls) -> EmbeddingEngine:
        """Get or create the singleton embedding engine."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Model management ──────────────────────────────────────────────────

    def _load_model(self) -> bool:
        """Lazy-load the embedding model. Returns True if successful."""
        if self._model is not None:
            return True
        if self._load_attempted:
            return False  # Don't retry failed loads every call

        self._load_attempted = True
        try:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                max_length=256,
            )
            logger.info(
                "Loaded embedding model: sentence-transformers/all-MiniLM-L6-v2 (%d-dim)",
                _EMBEDDING_DIMENSION,
            )
            return True
        except (ImportError, OSError, RuntimeError) as e:
            logger.warning("Failed to load embedding model: %s", e)
            return False

    @property
    def available(self) -> bool:
        """Check if the embedding model is loaded (or can be loaded)."""
        return self._load_model()

    # ── Embedding ─────────────────────────────────────────────────────────

    def embed(self, text: str) -> Optional[List[float]]:
        """Embed a single text string.

        Returns a list of floats (384-dim), or None if embedding fails.
        """
        if not self._load_model():
            return None
        if not text.strip():
            return None
        try:
            # fastembed.embed() returns an iterator of numpy arrays
            vec = next(iter(self._model.embed([text])), None)  # type: ignore
            if vec is None:
                return None
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        except (ValueError, TypeError, RuntimeError, SoulEmbeddingError) as e:
            logger.debug("Embedding failed: %s", e)
            return None

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in batch (more efficient than single calls)."""
        if not self._load_model():
            return []
        valid_texts = [t for t in texts if t.strip()]
        if not valid_texts:
            return []
        try:
            results: List[List[float]] = []
            for vec in self._model.embed(valid_texts):  # type: ignore
                results.append(vec.tolist() if hasattr(vec, "tolist") else list(vec))
            return results
        except (ValueError, TypeError, RuntimeError, SoulEmbeddingError) as e:
            logger.debug("Batch embedding failed: %s", e)
            return []

    @classmethod
    def dimension(cls) -> int:
        """Return the embedding dimension (384 for all-MiniLM-L6-v2)."""
        return _EMBEDDING_DIMENSION

    # ── Similarity ────────────────────────────────────────────────────────

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Cosine similarity between two embedding vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        try:
            a_arr = np.array(a, dtype=np.float64)
            b_arr = np.array(b, dtype=np.float64)
            dot = float(np.dot(a_arr, b_arr))
            norm_a = float(np.linalg.norm(a_arr))
            norm_b = float(np.linalg.norm(b_arr))
            if norm_a < 1e-10 or norm_b < 1e-10:
                return 0.0
            return max(0.0, min(1.0, dot / (norm_a * norm_b)))
        except (ValueError, TypeError, np.linalg.LinAlgError):
            return 0.0


# Module-level singleton accessor
def get_embedding(text: str) -> Optional[List[float]]:
    """Convenience: embed ``text`` using the singleton engine.

    Usage::

        vec = get_embedding("some text")
    """
    return EmbeddingEngine.get_instance().embed(text)


__all__ = [
    "EmbeddingEngine",
    "get_embedding",
]
