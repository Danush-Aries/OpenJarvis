"""Tests for the embedding engine and semantic memory search layer.

Covers:
- EmbeddingEngine singleton and lazy-loading
- Cosine similarity math
- Graceful fallback when model is unavailable
- Semantic + keyword hybrid retrieval in all 3 memory tiers
- MemoryEntry embedding field persistence
- Integration: embedding computed on store, used on retrieve
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Set soul directory to temp before any imports
TEST_DIR = Path(tempfile.mkdtemp(prefix="emb_test_"))
os.environ["JARVIS_SOUL_DIR"] = str(TEST_DIR)

from openjarvis.soul import memory as soul_memory
from openjarvis.soul.embeddings import EmbeddingEngine, get_embedding
from openjarvis.soul.memory import MemoryEntry, EpisodicMemory, SemanticMemory, ProceduralMemory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset the EmbeddingEngine singleton and all module-level caches before each test."""
    old_instance = EmbeddingEngine._instance
    old_memory_cache = soul_memory._EMBEDDING_ENGINE
    EmbeddingEngine._instance = None
    soul_memory._EMBEDDING_ENGINE = None
    yield
    EmbeddingEngine._instance = old_instance
    soul_memory._EMBEDDING_ENGINE = old_memory_cache


# ---------------------------------------------------------------------------
# EmbeddingEngine
# ---------------------------------------------------------------------------


class TestEmbeddingEngine:
    def test_singleton(self):
        e1 = EmbeddingEngine.get_instance()
        e2 = EmbeddingEngine.get_instance()
        assert e1 is e2

    def test_dimension(self):
        assert EmbeddingEngine.dimension() == 384

    def test_not_loaded_on_init(self):
        """Engine should not load the model until first embed call."""
        engine = EmbeddingEngine.get_instance()
        assert engine._model is None
        assert engine._load_attempted is False


class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 0.0, 0.0]
        assert EmbeddingEngine.cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert EmbeddingEngine.cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        # Cosine similarity returns 0..1 (clamped), so opposite returns 0
        assert EmbeddingEngine.cosine_similarity(a, b) == pytest.approx(0.0)

    def test_partial_match(self):
        a = [1.0, 1.0, 1.0]
        b = [1.0, 0.0, 0.0]
        sim = EmbeddingEngine.cosine_similarity(a, b)
        assert 0.5 < sim < 1.0

    def test_empty_vectors(self):
        assert EmbeddingEngine.cosine_similarity([], []) == 0.0

    def test_mismatched_dimensions(self):
        assert EmbeddingEngine.cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert EmbeddingEngine.cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# MemoryEntry with embeddings
# ---------------------------------------------------------------------------


class TestMemoryEntryEmbedding:
    def test_create_with_embedding(self):
        emb = [0.1] * 384
        entry = MemoryEntry.create("test", embedding=emb)
        assert len(entry.embedding) == 384
        assert entry.embedding[:3] == [0.1, 0.1, 0.1]

    def test_create_without_embedding(self):
        entry = MemoryEntry.create("test")
        assert entry.embedding == []

    def test_embedding_in_to_dict(self):
        emb = [0.5] * 384
        entry = MemoryEntry.create("test", embedding=emb)
        d = entry.to_dict()
        assert "embedding" in d
        assert len(d["embedding"]) == 384

    def test_embedding_in_from_dict(self):
        emb = [0.25] * 384
        entry = MemoryEntry.create("test", embedding=emb)
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert len(restored.embedding) == 384
        assert restored.embedding[0] == 0.25

    def test_from_dict_missing_embedding(self):
        d = {
            "id": "abc123",
            "content": "test",
            "memory_type": "episodic",
            "timestamp": 1000.0,
            "importance": 0.5,
            "access_count": 0,
            "last_accessed": 0.0,
            "metadata": {},
        }
        entry = MemoryEntry.from_dict(d)
        assert entry.embedding == []


# ---------------------------------------------------------------------------
# Hybrid retrieval (without real model — test the scoring logic)
# ---------------------------------------------------------------------------


class TestEpisodicHybridRetrieval:
    def test_keyword_fallback_without_embeddings(self):
        """When MemoryEntries have no embeddings, fall back to keyword matching."""
        mem = EpisodicMemory()
        mem.store("python programming tutorial")
        mem.store("machine learning models")
        mem.store("data science with python")

        results = mem.retrieve("python", limit=5)
        assert len(results) >= 2  # Two entries mention python
        assert any("python" in r["content"] for r in results)

    def test_semantic_boost_with_embeddings(self, monkeypatch):
        """Simulate embeddings to verify the scoring blend works."""
        mem = EpisodicMemory()
        emb_small = [0.1] * 384
        emb_big = [0.9] * 384

        mem.store("small similar memory", embedding=emb_small)
        mem.store("very relevant memory", embedding=emb_big)

        # Force embedding engine to be "available" and return a mock embedding
        class MockEngine:
            available = True
            def embed(self, text: str) -> List[float]:
                # Return an embedding close to emb_big
                return [0.85] * 384

        import openjarvis.soul.memory as mem_module
        monkeypatch.setattr(mem_module, "_get_embedding_engine", lambda: MockEngine())

        # Seed entries with their mock-friendly query embedding
        mem._entries[0].embedding = emb_small
        mem._entries[1].embedding = emb_big

        results = mem.retrieve("highly relevant content", limit=5)
        assert len(results) >= 2
        # The entry with embedding closer to query should score higher
        scores = [r["score"] for r in results if r["content"] == "very relevant memory"]
        scores_small = [r["score"] for r in results if r["content"] == "small similar memory"]
        assert scores and scores_small, "Both entries should appear in results"
        assert scores[0] >= scores_small[0], "Semantically closer entry should rank higher"


class TestSemanticHybridRetrieval:
    def test_term_overlap_scoring(self):
        """Semantic memory uses term overlap — verify it still works without embeddings."""
        mem = SemanticMemory()
        mem.store("Python is a high-level programming language")
        mem.store("Jarvis is an AI assistant")
        mem.store("The weather is nice today")

        results = mem.retrieve("Python programming language", limit=5)
        assert len(results) >= 1
        # The python entry should score higher
        top = results[0]
        assert "python" in top["content"].lower()


class TestProceduralHybridRetrieval:
    def test_word_level_match(self):
        """Procedural memory uses word-level matching — verify fallback."""
        mem = ProceduralMemory()
        mem.store("To deploy: build the project, run tests, then release")
        mem.store("To debug: check logs, reproduce, isolate, fix")

        results = mem.retrieve("deployment", limit=5)
        assert len(results) >= 1
        assert "deploy" in results[0]["content"].lower() or any(
            "deploy" in r["content"].lower() for r in results
        )


# ---------------------------------------------------------------------------
# Integration: store computes embedding, retrieve uses it
# ---------------------------------------------------------------------------


class TestTieredMemoryEmbeddingIntegration:
    def test_store_computes_embedding(self):
        """When storing via TieredMemory, an embedding should be computed."""
        from openjarvis.soul.memory import TieredMemory, _get_embedding_engine

        mem = TieredMemory.create("embed_test")
        engine = _get_embedding_engine()

        # Store a memory — this triggers embedding computation
        mem.store("Python is great for data science", memory_type="semantic")

        # Check that the stored entry has an embedding (if engine is available)
        if engine.available:
            entries = mem.semantic._entries
            assert len(entries) == 1
            assert len(entries[0].embedding) == 384
        else:
            # Graceful fallback — no embedding, but memory is still stored
            entries = mem.semantic._entries
            assert len(entries) == 1
            assert entries[0].embedding == []

    def test_retrieve_does_not_crash_without_engine(self, monkeypatch):
        """Even without an embedding engine, retrieve should work via keywords."""
        from openjarvis.soul.memory import TieredMemory

        # Patch to return a broken engine
        class BrokenEngine:
            available = False
            def embed(self, text: str) -> None:
                return None

        import openjarvis.soul.memory as mem_module
        monkeypatch.setattr(mem_module, "_get_embedding_engine", lambda: BrokenEngine())

        mem = TieredMemory.create("fallback_test")
        mem.store("python coding tips", memory_type="episodic")
        mem.store("data analysis", memory_type="semantic")

        results = mem.retrieve("python")
        assert len(results) >= 1
        assert "python" in results[0]["content"]


# ---------------------------------------------------------------------------
# Convenience helper get_embedding()
# ---------------------------------------------------------------------------


class TestGetEmbeddingHelper:
    def test_get_embedding_function_exists(self):
        """get_embedding helper should return None without crashing."""
        result = get_embedding("test")
        # May be None if model not loaded, but shouldn't crash
        assert result is None or len(result) == 384
