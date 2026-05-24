"""Soul router — /v1/soul endpoints for inspecting and managing the AI's persistent identity.

Provides:
- GET  /v1/soul              — List all souls
- GET  /v1/soul/{name}       — Soul state summary (identity, memory stats, persona)
- POST /v1/soul/{name}/reflect — Trigger a dream/reflection cycle
- POST /v1/soul/{name}/recall  — Search soul memories
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openjarvis.soul import Soul
from openjarvis.soul.storage import DEFAULT_BASE_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/soul", tags=["soul"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    memory_type: Optional[str] = Field(None, description="Filter by type (episodic, semantic, procedural)")    limit: int = Field(10, ge=1, le=100, description="Max results")


class ReflectResponse(BaseModel):
    reflection: str
    insights: List[Dict[str, Any]] = []


class SoulStatus(BaseModel):
    name: str
    exists: bool
    identity: Dict[str, Any] = {}
    memory_stats: Dict[str, int] = {}
    persona: Dict[str, Any] = {}
    dreams: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_soul(name: str) -> Soul:
    """Load a soul, raising 404 if it doesn't exist."""
    soul_dir = DEFAULT_BASE_DIR / name / "soul.json"
    if not soul_dir.exists():
        raise HTTPException(status_code=404, detail=f"Soul '{name}' not found. Create one with `jarvis soul init {name}`.")
    try:
        return Soul.load_or_create(name)
    except Exception as e:
        logger.exception("Failed to load soul '%s'", name)
        raise HTTPException(status_code=500, detail=f"Failed to load soul '{name}': {e}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_souls() -> Dict[str, Any]:
    """List all available souls."""
    soul_names = Soul.list_souls()
    return {"souls": soul_names, "count": len(soul_names), "dir": str(DEFAULT_BASE_DIR)}


@router.get("/{name}", response_model=SoulStatus)
async def soul_status(name: str) -> Dict[str, Any]:
    """Get a soul's full status summary."""
    soul_dir = DEFAULT_BASE_DIR / name / "soul.json"
    if not soul_dir.exists():
        return SoulStatus(name=name, exists=False).model_dump()

    soul = _load_soul(name)
    summary = soul.state_summary()

    return SoulStatus(
        name=name,
        exists=True,
        identity=summary.get("identity", {}),
        memory_stats=summary.get("memory_stats", {}),
        persona=summary.get("persona", {}),
        dreams=summary.get("dreams", {}),
    ).model_dump()


@router.post("/{name}/reflect", response_model=ReflectResponse)
async def soul_reflect(name: str) -> Dict[str, Any]:
    """Trigger a dream/reflection cycle to consolidate memories and evolve persona."""
    soul = _load_soul(name)
    try:
        result = soul.reflect()
        return ReflectResponse(
            reflection=result.get("reflection", "completed"),
            insights=result.get("insights", []),
        ).model_dump()
    except Exception as e:
        logger.exception("Reflection failed for soul '%s'", name)
        raise HTTPException(status_code=500, detail=f"Reflection failed: {e}")


@router.post("/{name}/recall")
async def soul_recall(name: str, req: RecallRequest) -> Dict[str, Any]:
    """Search soul memories with semantic + keyword retrieval."""
    soul = _load_soul(name)
    try:
        results = soul.recall(query=req.query, memory_type=req.memory_type, limit=req.limit)
        return {
            "query": req.query,
            "memory_type": req.memory_type,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.exception("Recall failed for soul '%s'", name)
        raise HTTPException(status_code=500, detail=f"Recall failed: {e}")


__all__ = ["router"]
