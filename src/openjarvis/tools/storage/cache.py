"""LRU cache for retrieval results with similarity-based matching."""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.tools.storage._stubs import RetrievalResult


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_saved_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Percentage of cache hits."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def avg_saved_time_ms(self) -> float:
        """Average time saved per hit."""
        return self.total_saved_time_ms / self.hits if self.hits > 0 else 0.0


@dataclass
class CachedQuery:
    """A cached query and its results."""

    query_hash: str
    query: str
    results: List[RetrievalResult]
    top_k: int
    timestamp: float
    query_time_ms: float = 0.0

    @property
    def age_seconds(self) -> float:
        """How old is this cache entry (in seconds)?"""
        return time.time() - self.timestamp


class RetrievalCache:
    """LRU cache for retrieval results with configurable TTL and similarity matching.

    Features:
    - LRU eviction when capacity exceeded
    - Optional TTL per entry
    - Query similarity matching (exact match + edit distance)
    - Performance tracking
    """

    def __init__(
        self,
        max_size: int = 256,
        ttl_seconds: Optional[int] = 3600,
        similarity_threshold: float = 0.85,
    ):
        """Initialize the retrieval cache.

        Args:
            max_size: Maximum number of cached queries
            ttl_seconds: Time-to-live for cache entries (None = no expiry)
            similarity_threshold: Min similarity (0-1) to consider a match
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.cache: OrderedDict[str, CachedQuery] = OrderedDict()
        self.stats = CacheStats()

    def _compute_query_hash(self, query: str) -> str:
        """Compute a hash of the query for fast comparison."""
        return hashlib.sha256(query.lower().encode()).hexdigest()[:16]

    def _similarity_score(self, q1: str, q2: str) -> float:
        """Compute similarity between two queries (0-1 scale).

        Uses a simple approach:
        - Exact match = 1.0
        - Token overlap = 0.5-0.9
        - No overlap = 0.0
        """
        q1_tokens = set(q1.lower().split())
        q2_tokens = set(q2.lower().split())

        if q1 == q2:
            return 1.0

        if not q1_tokens or not q2_tokens:
            return 0.0

        intersection = len(q1_tokens & q2_tokens)
        union = len(q1_tokens | q2_tokens)

        return intersection / union if union > 0 else 0.0

    def get(
        self, query: str, top_k: int = 5
    ) -> Optional[List[RetrievalResult]]:
        """Retrieve cached results if available and valid.

        Returns None if no valid cache entry found.
        Updates stats for hit/miss tracking.
        """
        query_hash = self._compute_query_hash(query)

        # Try exact match first
        if query_hash in self.cache:
            entry = self.cache[query_hash]

            # Check TTL
            if self.ttl_seconds and entry.age_seconds > self.ttl_seconds:
                del self.cache[query_hash]
                self.stats.misses += 1
                return None

            # Check top_k compatibility
            if entry.top_k >= top_k:
                # Move to end (most recently used)
                self.cache.move_to_end(query_hash)
                self.stats.hits += 1
                return entry.results[:top_k]

        # Try similarity match
        best_match = None
        best_score = 0.0

        for hash_key, entry in self.cache.items():
            # Skip if TTL expired
            if self.ttl_seconds and entry.age_seconds > self.ttl_seconds:
                continue

            # Skip if top_k too small
            if entry.top_k < top_k:
                continue

            score = self._similarity_score(query, entry.query)
            if score > best_score:
                best_score = score
                best_match = hash_key

        if best_match and best_score >= self.similarity_threshold:
            entry = self.cache[best_match]
            self.cache.move_to_end(best_match)
            self.stats.hits += 1
            return entry.results[:top_k]

        self.stats.misses += 1
        return None

    def put(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 5,
        query_time_ms: float = 0.0,
    ) -> None:
        """Cache the results of a retrieval query.

        Args:
            query: The search query
            results: The retrieval results
            top_k: The value of top_k used
            query_time_ms: Time taken to execute the query (for stats)
        """
        query_hash = self._compute_query_hash(query)

        # If exists, update and move to end
        if query_hash in self.cache:
            self.cache[query_hash] = CachedQuery(
                query_hash=query_hash,
                query=query,
                results=results,
                top_k=top_k,
                timestamp=time.time(),
                query_time_ms=query_time_ms,
            )
            self.cache.move_to_end(query_hash)
            return

        # Check if we need to evict
        while len(self.cache) >= self.max_size:
            evicted_key, _ = self.cache.popitem(last=False)  # Remove oldest (first)
            self.stats.evictions += 1

        # Add new entry
        self.cache[query_hash] = CachedQuery(
            query_hash=query_hash,
            query=query,
            results=results,
            top_k=top_k,
            timestamp=time.time(),
            query_time_ms=query_time_ms,
        )
        self.stats.total_saved_time_ms += query_time_ms

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        return self.stats

    def __len__(self) -> int:
        """Number of cached entries."""
        return len(self.cache)


__all__ = ["RetrievalCache", "CachedQuery", "CacheStats"]
