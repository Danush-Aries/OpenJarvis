"""Retrieval tool — search memory backends for relevant context."""

from __future__ import annotations

import time
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec
from openjarvis.tools.storage._stubs import MemoryBackend
from openjarvis.tools.storage.cache import RetrievalCache
from openjarvis.tools.storage.context import format_context


@ToolRegistry.register("retrieval")
class RetrievalTool(BaseTool):
    """Search the memory backend and return formatted context."""

    tool_id = "retrieval"

    def __init__(
        self,
        backend: Optional[MemoryBackend] = None,
        *,
        top_k: int = 5,
        enable_cache: bool = True,
        cache_max_size: int = 256,
        cache_ttl_seconds: Optional[int] = 3600,
    ) -> None:
        self._backend = backend
        self._top_k = top_k
        self._enable_cache = enable_cache
        self._cache: Optional[RetrievalCache] = None
        if enable_cache:
            self._cache = RetrievalCache(
                max_size=cache_max_size,
                ttl_seconds=cache_ttl_seconds,
            )

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="retrieval",
            description=(
                "Search the knowledge base for relevant"
                " information. Returns context with sources."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant information.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5).",
                    },
                },
                "required": ["query"],
            },
            category="memory",
        )

    def execute(self, **params: Any) -> ToolResult:
        if self._backend is None:
            return ToolResult(
                tool_name="retrieval",
                content="No memory backend configured.",
                success=False,
            )
        query = params.get("query", "")
        if not query:
            return ToolResult(
                tool_name="retrieval",
                content="No query provided.",
                success=False,
            )
        top_k = params.get("top_k", self._top_k)

        # Check cache first
        if self._cache:
            cached_results = self._cache.get(query, top_k)
            if cached_results is not None:
                formatted = format_context(cached_results)
                return ToolResult(
                    tool_name="retrieval",
                    content=formatted,
                    success=True,
                    metadata={
                        "num_results": len(cached_results),
                        "cache_hit": True,
                    },
                )

        # Execute retrieval
        try:
            start_time = time.time()
            results = self._backend.retrieve(query, top_k=top_k)
            query_time_ms = (time.time() - start_time) * 1000

            # Cache results
            if self._cache:
                self._cache.put(query, results, top_k, query_time_ms)
        except Exception as exc:
            return ToolResult(
                tool_name="retrieval",
                content=f"Retrieval error: {exc}",
                success=False,
            )
        if not results:
            return ToolResult(
                tool_name="retrieval",
                content="No relevant results found.",
                success=True,
            )
        formatted = format_context(results)
        return ToolResult(
            tool_name="retrieval",
            content=formatted,
            success=True,
            metadata={
                "num_results": len(results),
                "cache_hit": False,
                "query_time_ms": query_time_ms,
            },
        )

    def get_cache_stats(self) -> Optional[dict]:
        """Get cache performance statistics."""
        if not self._cache:
            return None
        stats = self._cache.get_stats()
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._cache.max_size,
            "cache_hits": stats.hits,
            "cache_misses": stats.misses,
            "cache_evictions": stats.evictions,
            "cache_hit_rate_percent": stats.hit_rate,
            "avg_saved_time_ms": stats.avg_saved_time_ms,
            "total_saved_time_ms": stats.total_saved_time_ms,
        }


__all__ = ["RetrievalTool"]
