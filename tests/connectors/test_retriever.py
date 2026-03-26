"""Tests for TwoStageRetriever — BM25 recall + optional semantic reranking."""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from openjarvis.connectors.retriever import Reranker, TwoStageRetriever
from openjarvis.connectors.store import KnowledgeStore
from openjarvis.tools.storage._stubs import RetrievalResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> KnowledgeStore:
    """KnowledgeStore pre-populated with 4 items across different sources/authors."""
    ks = KnowledgeStore(db_path=tmp_path / "test_retriever.db")

    ks.store(
        content="AI research on neural networks and deep learning advances.",
        source="gmail",
        doc_type="email",
        author="alice@example.com",
    )
    ks.store(
        content="AI research on distributed systems and cloud infrastructure.",
        source="obsidian",
        doc_type="note",
        author="bob@example.com",
    )
    ks.store(
        content="AI research on natural language processing and transformers.",
        source="gmail",
        doc_type="email",
        author="alice@example.com",
    )
    ks.store(
        content="AI research on reinforcement learning for robotics.",
        source="slack",
        doc_type="message",
        author="carol@example.com",
    )

    return ks


@pytest.fixture()
def retriever(store: KnowledgeStore) -> TwoStageRetriever:
    return TwoStageRetriever(store)


# ---------------------------------------------------------------------------
# Test 1: retrieve_returns_results — basic search works
# ---------------------------------------------------------------------------


def test_retrieve_returns_results(retriever: TwoStageRetriever) -> None:
    """A matching query returns at least one result."""
    results = retriever.retrieve("AI research")
    assert isinstance(results, list)
    assert len(results) >= 1
    assert all(isinstance(r, RetrievalResult) for r in results)


# ---------------------------------------------------------------------------
# Test 2: retrieve_respects_top_k — limits results
# ---------------------------------------------------------------------------


def test_retrieve_respects_top_k(retriever: TwoStageRetriever) -> None:
    """retrieve() returns at most top_k results."""
    results = retriever.retrieve("AI research", top_k=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Test 3: retrieve_with_source_filter — filters pass through to store
# ---------------------------------------------------------------------------


def test_retrieve_with_source_filter(
    store: KnowledgeStore,
) -> None:
    """source= filter is forwarded to the KnowledgeStore."""
    ret = TwoStageRetriever(store)
    results = ret.retrieve("AI research", source="gmail")
    assert len(results) >= 1
    for r in results:
        assert r.metadata.get("source") == "gmail"


# ---------------------------------------------------------------------------
# Test 4: retrieve_with_author_filter — filters pass through
# ---------------------------------------------------------------------------


def test_retrieve_with_author_filter(
    store: KnowledgeStore,
) -> None:
    """author= filter is forwarded to the KnowledgeStore."""
    ret = TwoStageRetriever(store)
    results = ret.retrieve("AI research", author="alice@example.com")
    assert len(results) >= 1
    for r in results:
        assert r.metadata.get("author") == "alice@example.com"


# ---------------------------------------------------------------------------
# Test 5: retrieve_bm25_only_when_no_colbert — works without reranker
# ---------------------------------------------------------------------------


def test_retrieve_bm25_only_when_no_reranker(
    store: KnowledgeStore,
) -> None:
    """Without a reranker the retriever returns BM25 results directly."""
    ret = TwoStageRetriever(store, reranker=None)
    results = ret.retrieve("AI research", top_k=3)
    assert isinstance(results, list)
    assert len(results) <= 3


# ---------------------------------------------------------------------------
# Test 6: retrieve_with_colbert_reranking — mock reranker is called
# ---------------------------------------------------------------------------


def test_retrieve_with_colbert_reranking(
    store: KnowledgeStore,
) -> None:
    """When a reranker is provided it is called to reorder candidates."""
    mock_reranker = MagicMock(spec=Reranker)
    # The mock reranker returns a pair of results to distinguish from BM25 output
    reranked = [
        RetrievalResult(
            content="Reranked result A",
            score=0.99,
            source="gmail",
            metadata={"reranked": True},
        ),
        RetrievalResult(
            content="Reranked result B",
            score=0.95,
            source="slack",
            metadata={"reranked": True},
        ),
    ]
    mock_reranker.rerank.return_value = reranked

    # recall_k=4 fetches all 4 docs; top_k=2 so len(candidates)=4 > top_k=2
    ret = TwoStageRetriever(store, reranker=mock_reranker, recall_k=4)
    results = ret.retrieve("AI research", top_k=2)

    # The reranker must have been called with top_k=2
    mock_reranker.rerank.assert_called_once()
    call_args = mock_reranker.rerank.call_args
    assert call_args[1].get("top_k") == 2

    # Results come from the reranker
    assert results == reranked


# ---------------------------------------------------------------------------
# Test 7: retrieve_no_results — empty for nonexistent query
# ---------------------------------------------------------------------------


def test_retrieve_no_results(retriever: TwoStageRetriever) -> None:
    """A query matching nothing returns an empty list."""
    results = retriever.retrieve("xyzzy_nonexistent_zqjwkm")
    assert results == []


# ---------------------------------------------------------------------------
# Test 8: retrieve_recall_k_larger_than_top_k — BM25 fetches more than final k
# ---------------------------------------------------------------------------


def test_retrieve_recall_k_larger_than_top_k(
    store: KnowledgeStore,
) -> None:
    """Stage-1 recall fetches max(recall_k, top_k*3) candidates."""
    call_log: List[int] = []

    class SpyStore(KnowledgeStore):
        def retrieve(self, query, *, top_k=5, **kwargs):  # type: ignore[override]
            call_log.append(top_k)
            return super().retrieve(query, top_k=top_k, **kwargs)

    spy = SpyStore(db_path=":memory:")
    spy.store(
        content="Deep learning research in computer vision tasks.",
        source="gmail",
        doc_type="email",
        author="alice@example.com",
    )

    ret = TwoStageRetriever(spy, recall_k=50)
    ret.retrieve("deep learning research", top_k=2)

    # Stage-1 must have requested more candidates than the final top_k
    assert len(call_log) == 1
    # recall_k=50 vs top_k*3=6 → should use 50
    assert call_log[0] == 50
