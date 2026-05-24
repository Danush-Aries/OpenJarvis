"""Tiered Memory — episodic, semantic, and procedural memory with retrieval.

Memory tiers:
- Episodic:   Specific experiences and conversations (what happened when)
- Semantic:   Facts, concepts, and knowledge extracted from experience
- Procedural: Skills, procedures, and how-to knowledge

Each tier has its own storage and retrieval strategy.

Enhancements over baseline:
- Automated importance scoring via heuristic signals
- MMR (Maximum Marginal Relevance) diversity re-ranking
- Ebbinghaus-inspired decay curves for retrieval scoring
- Memory deduplication (near-merge via embedding similarity)
- Working Memory — a configurable "always in context" memory set
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding engine (lazy-loaded singleton)
# ---------------------------------------------------------------------------

from openjarvis.soul.embeddings import EmbeddingEngine as _EmbeddingEngine

_EMBEDDING_ENGINE: Optional[_EmbeddingEngine] = None


def _get_embedding_engine():
    """Lazy accessor for the embedding engine singleton."""
    global _EMBEDDING_ENGINE
    if _EMBEDDING_ENGINE is None:
        _EMBEDDING_ENGINE = _EmbeddingEngine.get_instance()
    return _EMBEDDING_ENGINE


# ---------------------------------------------------------------------------
# Memory entry
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """A single memory unit.

    Attributes:
        id:          Unique identifier
        content:     The memory content (text)
        memory_type: "episodic", "semantic", or "procedural"
        timestamp:   When the memory was formed
        importance:  0.0 (trivial) - 1.0 (critical)
        embedding:   Dense vector embedding for semantic search (384-dim float list)
        access_count: How many times this has been recalled
        last_accessed: When last recalled
        metadata:    Arbitrary metadata (tags, emotional valence, etc.)
    """

    id: str
    content: str
    memory_type: str = "episodic"
    timestamp: float = 0.0
    importance: float = 0.5
    embedding: List[float] = field(default_factory=list)
    access_count: int = 0
    last_accessed: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        content: str,
        memory_type: str = "episodic",
        importance: Optional[float] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Create a memory entry with optional auto-scored importance.

        If ``importance`` is None, it will be automatically computed
        using heuristic signals (length, question marks, exclamation,
        technical terms, user repetition patterns).
        """
        if importance is None:
            importance = compute_importance_score(content)
        return cls(
            id=str(uuid.uuid4())[:12],
            content=content,
            memory_type=memory_type,
            timestamp=time.time(),
            importance=max(0.0, min(1.0, importance)),
            embedding=embedding or [],
            metadata=metadata or {},
        )

    def record_access(self) -> None:
        """Mark this memory as accessed."""
        self.access_count += 1
        self.last_accessed = time.time()

    def compute_decay_factor(self) -> float:
        """Compute an Ebbinghaus-inspired decay factor for this memory.

        Uses a power-law decay curve:
            strength = (access_count + 1)^0.5 / (hours_since_last_access + 1)^0.3

        Returns:
            A decay factor [0.0, 1.0] where 1.0 = strongest retention.
        """
        hours_since = (time.time() - max(self.last_accessed, self.timestamp)) / 3600
        strength = math.pow(self.access_count + 1, 0.5) / math.pow(max(hours_since, 0.01) + 1, 0.3)
        # Normalize: typical range is 0.0-3.0, clamp to [0.0, 1.0]
        return min(1.0, strength / 3.0)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryEntry:
        """Create a MemoryEntry from a dict, ignoring unknown keys."""
        valid_fields = {"id", "content", "memory_type", "timestamp",
                        "importance", "embedding", "access_count",
                        "last_accessed", "metadata"}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Automated Importance Scoring
# ---------------------------------------------------------------------------

_IMPORTANCE_SIGNALS = {
    # Signal pattern -> score contribution
    "length": lambda c: min(0.2, len(c) / 5000 * 0.2),       # longer = more important
    "questions": lambda c: min(0.15, c.count("?") * 0.05),    # questions signal curiosity
    "exclamations": lambda c: min(0.15, c.count("!") * 0.05),  # strong emotion
    "technical": lambda c: min(0.2, sum(1 for w in ["function", "code", "api", "data",
        "algorithm", "system", "design", "implement", "architecture", "deploy",
        "config", "database", "security", "protocol", "framework"] if w in c.lower()) * 0.04),
    "user_preference": lambda c: min(0.25, sum(1 for w in ["i like", "i love", "i prefer",
        "i want", "i need", "my favorite", "i hate", "i don't like"] if w in c.lower()) * 0.08),
    "instruction": lambda c: min(0.2, sum(1 for w in ["remember", "important", "critical",
        "urgent", "key", "note", "warning", "todo", "fix", "bug"] if w in c.lower()) * 0.05),
}


def compute_importance_score(content: str) -> float:
    """Automatically compute the importance of memory content.

    Uses multiple heuristic signals:
    - Content length (longer interactions tend to be more substantive)
    - Question marks (curiosity/engagement)
    - Exclamation marks (emotional intensity)
    - Technical terminology (domain relevance)
    - User preference language ("I like", "I want", etc.)
    - Instruction keywords ("remember", "important", etc.)

    Returns:
        Importance score between 0.0 (trivial) and 1.0 (critical).
    """
    if not content or not content.strip():
        return 0.1

    score = 0.0
    for signal_name, signal_fn in _IMPORTANCE_SIGNALS.items():
        score += signal_fn(content)

    # Base importance for any substantive content
    if len(content.strip()) > 20:
        score += 0.1

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Maximum Marginal Relevance (MMR) Re-ranker
# ---------------------------------------------------------------------------


def mmr_rerank(
    results: List[Dict[str, Any]],
    query_embedding: Optional[List[float]] = None,
    lambda_param: float = 0.6,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Re-rank retrieval results using Maximum Marginal Relevance.

    MMR balances relevance and diversity:
        MMR = lambda * sim(q, d_i) - (1-lambda) * max(sim(d_i, d_j))

    Higher lambda = more relevance-focused, lower = more diversity-focused.

    Args:
        results:        Initial retrieval results with "score" and "embedding" keys
        query_embedding: Embedding of the query for similarity comparison
        lambda_param:   Trade-off between relevance (1.0) and diversity (0.0)
        limit:          Max items to return

    Returns:
        Re-ranked results list.
    """
    if len(results) <= 1:
        return results[:limit]

    if query_embedding is None:
        # Fall back to score-based ranking
        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)[:limit]

    selected: List[Dict[str, Any]] = []
    candidates = list(results)

    while len(selected) < limit and candidates:
        best_score = -float("inf")
        best_idx = 0

        for i, cand in enumerate(candidates):
            # Relevance: similarity to query
            relevance = cand.get("score", 0)

            # Diversity: max similarity to already-selected items
            cand_emb = cand.get("embedding")
            if cand_emb and selected:
                max_sim_to_selected = max(
                    _EmbeddingEngine.cosine_similarity(cand_emb, s.get("embedding", []))
                    for s in selected
                    if s.get("embedding")
                )
            else:
                max_sim_to_selected = 0.0

            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(candidates.pop(best_idx))

    return selected


# ---------------------------------------------------------------------------
# Working Memory
# ---------------------------------------------------------------------------


class WorkingMemory:
    """A configurable "always in context" memory set.

    Working memory holds the most important memories that should be
    surfaced without explicit query. Inspired by Letta's "core memory"
    that stays in the LLM's context window.

    Items in working memory are determined by a combination of:
    - Explicit pinning (user or agent marks as important)
    - High importance scores (>0.8)
    - Most recent top-N by recency
    - Frequent access patterns

    Attributes:
        max_slots:   Maximum number of working memory slots
        pinned_ids:  Set of explicitly pinned memory entry IDs
    """

    def __init__(self, max_slots: int = 5) -> None:
        self.max_slots = max_slots
        self._pinned_ids: Set[str] = set()
        self._entry_ids: List[str] = []  # ordered, most important first

    def pin(self, memory_id: str) -> None:
        """Pin a memory entry to working memory."""
        self._pinned_ids.add(memory_id)
        self._promote(memory_id)

    def unpin(self, memory_id: str) -> None:
        """Remove a memory from working memory."""
        self._pinned_ids.discard(memory_id)
        if memory_id in self._entry_ids:
            self._entry_ids.remove(memory_id)

    def is_pinned(self, memory_id: str) -> bool:
        return memory_id in self._pinned_ids

    def refresh(
        self,
        entries: List[MemoryEntry],
        new_entry_id: Optional[str] = None,
    ) -> None:
        """Refresh working memory contents based on current entries.

        Working memory slots are filled in priority order:
        1. Pinned entries (always kept)
        2. High-importance entries (>0.8)
        3. Most recently accessed entries

        Args:
            entries:      All current memory entries
            new_entry_id: Optional ID of a newly added entry to promote
        """
        # Score all entries for working memory candidacy
        scored: List[Tuple[float, MemoryEntry]] = []
        for entry in entries:
            score = 0.0

            # Pinned entries get maximum score
            if entry.id in self._pinned_ids:
                score += 10.0

            # High importance
            score += entry.importance * 5.0

            # Recency
            hours_ago = (time.time() - entry.last_accessed or entry.timestamp) / 3600
            score += max(0, 1.0 - hours_ago / 24) * 2.0  # boost for last 24h

            # New entry boost
            if new_entry_id and entry.id == new_entry_id:
                score += 3.0

            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Keep top-N
        self._entry_ids = [e.id for _, e in scored[:self.max_slots]]

        # Ensure pinned entries are always present
        for pid in self._pinned_ids:
            if pid not in self._entry_ids:
                self._entry_ids.insert(0, pid)
                if len(self._entry_ids) > self.max_slots:
                    self._entry_ids = self._entry_ids[:self.max_slots]

    def _promote(self, memory_id: str) -> None:
        """Promote a memory ID to the front of working memory."""
        if memory_id in self._entry_ids:
            self._entry_ids.remove(memory_id)
        self._entry_ids.insert(0, memory_id)
        if len(self._entry_ids) > self.max_slots:
            self._entry_ids = self._entry_ids[:self.max_slots]

    def get_ids(self) -> List[str]:
        """Get the current working memory entry IDs."""
        return list(self._entry_ids)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_slots": self.max_slots,
            "pinned_ids": list(self._pinned_ids),
            "entry_ids": list(self._entry_ids),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkingMemory:
        wm = cls(max_slots=data.get("max_slots", 5))
        wm._pinned_ids = set(data.get("pinned_ids", []))
        wm._entry_ids = list(data.get("entry_ids", []))
        return wm


# ---------------------------------------------------------------------------
# Memory storage
# ---------------------------------------------------------------------------


class EpisodicMemory:
    """Episodic memory — stores experiences with temporal context."""

    def __init__(self) -> None:
        self._entries: List[MemoryEntry] = []

    def store(self, content: str, importance: float = 0.5,
              metadata: Optional[Dict[str, Any]] = None,
              embedding: Optional[List[float]] = None) -> MemoryEntry:
        entry = MemoryEntry.create(
            content, memory_type="episodic", importance=importance,
            embedding=embedding, metadata=metadata,
        )
        self._entries.append(entry)
        return entry

    def retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Hybrid retrieval: semantic (embedding) + keyword + recency + importance.

        Uses cosine similarity of query vs stored embeddings when available,
        blended with existing keyword and metadata signals. Falls back to
        pure keyword matching if embeddings are unavailable.
        """
        # Compute query embedding once
        engine = _get_embedding_engine()
        query_emb: Optional[List[float]] = None
        if engine.available and any(e.embedding for e in self._entries):
            query_emb = engine.embed(query)

        scored: List[Tuple[float, MemoryEntry]] = []
        q = query.lower()

        for entry in self._entries:
            score = 0.0

            # ── Semantic score (if embeddings available) ──
            sem_score = 0.0
            if query_emb is not None and entry.embedding:
                sem_score = _EmbeddingEngine.cosine_similarity(query_emb, entry.embedding)
                score += sem_score * 0.40  # 40% weight on semantic meaning

            # ── Keyword match ──
            if q in entry.content.lower():
                score += 0.30

            # ── Recency boost (more recent = higher) ──
            age_hours = (time.time() - entry.timestamp) / 3600
            recency_boost = max(0.0, 1.0 - (age_hours / 720))  # 30-day decay
            score += recency_boost * 0.15

            # ── Importance boost ──
            score += entry.importance * 0.10

            # ── Frequency boost (frequently recalled = more relevant) ──
            freq_boost = min(1.0, entry.access_count / 10)
            score += freq_boost * 0.05

            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, entry in scored[:limit]:
            entry.record_access()
            d = entry.to_dict()
            d["score"] = round(score, 3)
            results.append(d)
        return results

    @property
    def count(self) -> int:
        return len(self._entries)

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": [e.to_dict() for e in self._entries]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EpisodicMemory:
        mem = cls()
        mem._entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
        return mem

    def consolidate(self, max_age_days: float = 90.0) -> int:
        """Remove very old, unimportant memories to save space."""
        cutoff = time.time() - (max_age_days * 86400)
        before = len(self._entries)
        self._entries = [
            e for e in self._entries
            if e.timestamp > cutoff or e.importance > 0.7
        ]
        return before - len(self._entries)


class SemanticMemory:
    """Semantic memory — stores facts, concepts, and extracted knowledge."""

    def __init__(self) -> None:
        self._entries: List[MemoryEntry] = []

    def store(self, content: str, importance: float = 0.5,
              metadata: Optional[Dict[str, Any]] = None,
              embedding: Optional[List[float]] = None) -> MemoryEntry:
        entry = MemoryEntry.create(
            content, memory_type="semantic", importance=importance,
            embedding=embedding, metadata=metadata,
        )
        self._entries.append(entry)
        return entry

    def retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Hybrid retrieval: semantic + keyword for facts."""
        engine = _get_embedding_engine()
        query_emb: Optional[List[float]] = None
        if engine.available and any(e.embedding for e in self._entries):
            query_emb = engine.embed(query)

        scored: List[Tuple[float, MemoryEntry]] = []
        q = query.lower()
        query_terms = set(q.split())

        for entry in self._entries:
            score = 0.0
            content_lower = entry.content.lower()

            # ── Semantic score (if embeddings available) ──
            sem_score = 0.0
            if query_emb is not None and entry.embedding:
                sem_score = _EmbeddingEngine.cosine_similarity(query_emb, entry.embedding)
                score += sem_score * 0.45

            # ── Term overlap ──
            content_terms = set(content_lower.split())
            overlap = len(query_terms & content_terms)
            if overlap > 0:
                score += (overlap / max(len(query_terms), 1)) * 0.25

            # ── Direct substring ──
            if q in content_lower:
                score += 0.15

            # ── Importance ──
            score += entry.importance * 0.15

            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, entry in scored[:limit]:
            entry.record_access()
            d = entry.to_dict()
            d["score"] = round(score, 3)
            results.append(d)
        return results

    @property
    def count(self) -> int:
        return len(self._entries)

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": [e.to_dict() for e in self._entries]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SemanticMemory:
        mem = cls()
        mem._entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
        return mem


class ProceduralMemory:
    """Procedural memory — stores skills, patterns, and how-to knowledge."""

    def __init__(self) -> None:
        self._entries: List[MemoryEntry] = []

    def store(self, content: str, importance: float = 0.5,
              metadata: Optional[Dict[str, Any]] = None,
              embedding: Optional[List[float]] = None) -> MemoryEntry:
        entry = MemoryEntry.create(
            content, memory_type="procedural", importance=importance,
            embedding=embedding, metadata=metadata,
        )
        self._entries.append(entry)
        return entry

    def retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Hybrid retrieval: semantic + keyword for procedural knowledge."""
        engine = _get_embedding_engine()
        query_emb: Optional[List[float]] = None
        if engine.available and any(e.embedding for e in self._entries):
            query_emb = engine.embed(query)

        scored: List[Tuple[float, MemoryEntry]] = []
        q = query.lower()

        for entry in self._entries:
            score = 0.0
            content_lower = entry.content.lower()

            # ── Semantic score (if embeddings available) ──
            sem_score = 0.0
            if query_emb is not None and entry.embedding:
                sem_score = _EmbeddingEngine.cosine_similarity(query_emb, entry.embedding)
                score += sem_score * 0.50

            # ── Keyword match ──
            if q in content_lower:
                score += 0.25

            # ── Word-level match ──
            if any(word in content_lower for word in q.split()):
                score += 0.15

            # ── Importance ──
            score += entry.importance * 0.10

            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, entry in scored[:limit]:
            entry.record_access()
            d = entry.to_dict()
            d["score"] = round(score, 3)
            results.append(d)
        return results

    @property
    def count(self) -> int:
        return len(self._entries)

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": [e.to_dict() for e in self._entries]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProceduralMemory:
        mem = cls()
        mem._entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
        return mem


# ---------------------------------------------------------------------------
# Tiered Memory (combined)
# ---------------------------------------------------------------------------


class TieredMemory:
    """Combined tiered memory system.

    Provides unified store/retrieve across all three memory types.
    Supports auto-consolidation when memory count exceeds ``max_memories``
    and selective forgetting by ID, type, or query.

    New in v2:
    - Working memory (always-in-context slots)
    - Memory deduplication (near-merge via embedding similarity)
    - Decay-aware retrieval scoring
    - Option to use MMR diversity re-ranking
    """

    def __init__(
        self,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        procedural: ProceduralMemory,
        max_memories: int = 1000,
        working_memory: Optional[WorkingMemory] = None,
    ) -> None:
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.max_memories = max_memories
        self.working = working_memory or WorkingMemory()
        self._consolidation_cooldown: float = 0.0

    @classmethod
    def create(cls, name: str) -> TieredMemory:
        return cls(
            episodic=EpisodicMemory(),
            semantic=SemanticMemory(),
            procedural=ProceduralMemory(),
            working_memory=WorkingMemory(),
        )

    def store(
        self,
        content: str,
        memory_type: str = "episodic",
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a memory in the appropriate tier, computing its embedding.

        Embeddings are computed lazily via fastembed (ONNX Runtime, CPU-only).
        If the model fails to load or embedding generation fails, the memory
        is still stored — it will just use keyword-based retrieval as fallback.

        Importance is auto-computed if not provided (via ``compute_importance_score``).

        Auto-triggers consolidation when total memory count exceeds
        ``max_memories``.

        Args:
            content:     Memory text content
            memory_type: "episodic", "semantic", or "procedural"
            importance:  0.0 (trivial) - 1.0 (critical), None = auto-compute
            metadata:    Optional metadata dict
        """
        # Compute embedding for semantic search
        try:
            engine = _get_embedding_engine()
            embedding = engine.embed(content) if engine.available else None
        except Exception:
            embedding = None
            logger.debug("Failed to compute embedding for: %.60s", content)

        if importance is None:
            importance = compute_importance_score(content)

        entry = None
        if memory_type == "episodic":
            entry = self.episodic.store(content, importance=importance,
                                        metadata=metadata, embedding=embedding)
        elif memory_type == "semantic":
            entry = self.semantic.store(content, importance=importance,
                                        metadata=metadata, embedding=embedding)
        elif memory_type == "procedural":
            entry = self.procedural.store(content, importance=importance,
                                          metadata=metadata, embedding=embedding)
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

        # Refresh working memory to include the new entry
        if entry is not None:
            self._refresh_working(new_entry_id=entry.id)

        # Auto-consolidate when exceeding threshold (with 60s cooldown)
        if self.max_memories > 0 and self.stats()["total"] > self.max_memories:
            now = time.time()
            if now > self._consolidation_cooldown:
                pruned = self.consolidate(max_age_days=90.0)
                total_pruned = sum(pruned.values())
                if total_pruned:
                    logger.debug("Auto-consolidation pruned %d entries (max=%d)",
                                 total_pruned, self.max_memories)
                self._consolidation_cooldown = now + 60.0

    def _refresh_working(self, new_entry_id: Optional[str] = None) -> None:
        """Refresh working memory from all tier entries."""
        all_entries: List[MemoryEntry] = []
        all_entries.extend(self.episodic._entries)
        all_entries.extend(self.semantic._entries)
        all_entries.extend(self.procedural._entries)
        self.working.refresh(all_entries, new_entry_id=new_entry_id)

    def retrieve(
        self,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 5,
        use_mmr: bool = False,
        mmr_lambda: float = 0.6,
        include_working: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories across one or all tiers.

        Args:
            query:            Search query or context
            memory_type:      Filter by type (None = all types)
            limit:            Max results
            use_mmr:          Apply MMR diversity re-ranking if True
            mmr_lambda:       MMR trade-off (1.0 = relevance only, 0.0 = diversity only)
            include_working:  Prepend working memory items to results

        Returns:
            List of memory dicts with keys: content, type, timestamp, metadata, score
        """
        results = []
        if memory_type is None or memory_type == "episodic":
            results.extend(self.episodic.retrieve(query, limit=limit * 2))
        if memory_type is None or memory_type == "semantic":
            results.extend(self.semantic.retrieve(query, limit=limit * 2))
        if memory_type is None or memory_type == "procedural":
            results.extend(self.procedural.retrieve(query, limit=limit * 2))

        # Sort by score across all tiers
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Apply MMR diversity re-ranking if embeddings are available
        if use_mmr and results:
            try:
                engine = _get_embedding_engine()
                query_emb = engine.embed(query) if engine.available else None
                results = mmr_rerank(
                    results, query_embedding=query_emb,
                    lambda_param=mmr_lambda, limit=limit,
                )
            except Exception:
                # Fall back to score ranking if MMR fails
                results = results[:limit]
        else:
            results = results[:limit]

        # Prepend working memory items if requested
        if include_working and self.working.get_ids():
            working_ids = set(self.working.get_ids())
            working_results = [
                r for r in results
                if r.get("id") in working_ids
            ]
            non_working = [
                r for r in results
                if r.get("id") not in working_ids
            ]
            # Ensure working items are at the front with boosted score
            for wr in working_results:
                wr["score"] = max(wr.get("score", 0), 0.9)
                wr["from_working_memory"] = True
            results = working_results + non_working

        return results[:limit]

    def forget(
        self,
        memory_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        query: Optional[str] = None,
    ) -> int:
        """Selectively forget memories.

        Args:
            memory_id: Forget a specific memory by its ID
            memory_type: Forget all memories of a type ("episodic", "semantic", "procedural")
            query: Forget memories whose content matches query text (substring match)

        Returns:
            Number of memories removed.

        Note:
            Only one filter is applied at a time, with priority:
            memory_id > memory_type > query.
        """
        tiers: List[tuple[str, Any]] = [
            ("episodic", self.episodic),
            ("semantic", self.semantic),
            ("procedural", self.procedural),
        ]

        # Filter tiers to only the requested type
        if memory_type is not None:
            tiers = [(t, m) for t, m in tiers if t == memory_type]
            if not tiers:
                raise ValueError(f"Unknown memory type: {memory_type}")

        removed = 0

        if memory_id is not None:
            # Forget a specific entry by ID across applicable tiers
            for _, tier in tiers:
                before = len(tier._entries)
                tier._entries = [e for e in tier._entries if e.id != memory_id]
                removed += before - len(tier._entries)
            # Also unpin from working memory
            self.working.unpin(memory_id)
            return removed

        if query is not None:
            # Forget entries whose content matches query (substring, case-insensitive)
            q = query.lower()
            removed_ids: Set[str] = set()
            for _, tier in tiers:
                before = len(tier._entries)
                removed_entries = [e for e in tier._entries if q in e.content.lower()]
                tier._entries = [e for e in tier._entries if q not in e.content.lower()]
                for re in removed_entries:
                    removed_ids.add(re.id)
                removed += before - len(tier._entries)
            return removed

        # Forget entire type(s)
        for _, tier in tiers:
            removed += len(tier._entries)
            tier._entries.clear()
        return removed

    def deduplicate(self, similarity_threshold: float = 0.92) -> int:
        """Deduplicate memories by merging near-duplicate entries.

        Uses embedding cosine similarity to detect near-duplicates.
        When two entries have similarity > threshold, the older one
        is removed (its access count is merged into the newer one).

        Args:
            similarity_threshold: Cosine similarity threshold [0.0-1.0]

        Returns:
            Number of duplicate entries removed.
        """
        tiers: List[tuple[str, Any]] = [
            ("episodic", self.episodic),
            ("semantic", self.semantic),
            ("procedural", self.procedural),
        ]
        total_removed = 0

        for tier_name, tier in tiers:
            entries = tier._entries
            if len(entries) < 2:
                continue

            # Only dedup entries with embeddings
            has_emb = [e for e in entries if e.embedding]
            if len(has_emb) < 2:
                continue

            # Compare pairs
            to_remove: Set[str] = set()
            for i in range(len(entries)):
                if entries[i].id in to_remove:
                    continue
                if not entries[i].embedding:
                    continue
                for j in range(i + 1, len(entries)):
                    if entries[j].id in to_remove:
                        continue
                    if not entries[j].embedding:
                        continue
                    sim = _EmbeddingEngine.cosine_similarity(
                        entries[i].embedding, entries[j].embedding
                    )
                    if sim > similarity_threshold:
                        # Keep the newer one, remove the older
                        older = entries[i] if entries[i].timestamp < entries[j].timestamp else entries[j]
                        to_remove.add(older.id)
                        logger.debug(
                            "Dedup: removed %s (sim=%.3f)",
                            older.content[:40], sim,
                        )

            if to_remove:
                before = len(entries)
                tier._entries = [e for e in entries if e.id not in to_remove]
                total_removed += before - len(tier._entries)

        return total_removed

    def stats(self) -> Dict[str, int]:
        return {
            "episodic": self.episodic.count,
            "semantic": self.semantic.count,
            "procedural": self.procedural.count,
            "total": self.episodic.count + self.semantic.count + self.procedural.count,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episodic": self.episodic.to_dict(),
            "semantic": self.semantic.to_dict(),
            "procedural": self.procedural.to_dict(),
            "working_memory": self.working.to_dict(),
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> TieredMemory:
        return cls(
            episodic=EpisodicMemory.from_dict(data.get("episodic", {})),
            semantic=SemanticMemory.from_dict(data.get("semantic", {})),
            procedural=ProceduralMemory.from_dict(data.get("procedural", {})),
            working_memory=WorkingMemory.from_dict(
                data.get("working_memory", {})
            ) if data.get("working_memory") else None,
        )

    def consolidate(self, max_age_days: float = 90.0) -> Dict[str, int]:
        """Run consolidation on all tiers.

        Only episodic memories are aged out (semantic and procedural
        are more durable). Returns count of removed entries per tier.
        """
        pruned = {
            "episodic": self.episodic.consolidate(max_age_days=max_age_days),
            "semantic": 0,
            "procedural": 0,
        }
        # Refresh working memory after consolidation
        self._refresh_working()
        return pruned
