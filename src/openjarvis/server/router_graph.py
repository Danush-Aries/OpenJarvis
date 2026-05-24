"""FastAPI routes for knowledge graph entity listing and extraction."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

graph_router = APIRouter(prefix="/v1/graph", tags=["graph"])


def _get_kg():
    """Lazy import for KnowledgeGraphMemory."""
    from openjarvis.tools.storage.knowledge_graph import KnowledgeGraphMemory
    return KnowledgeGraphMemory()


@graph_router.get("/entities")
async def list_entities(
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    max_results: int = 100,
):
    """List entities from the knowledge graph, optionally filtered by type or name search."""
    kg = _get_kg()
    try:
        entities = kg.search_entities(
            entity_type=entity_type or None,
            name=search or None,
            max_results=max_results,
        )
    except Exception as e:
        logger.warning("Graph query failed: %s", e)
        # Return empty result on error — graph may not be initialized
        entities = []

    nodes = []
    links = []
    seen_ids = set()

    for ent in entities:
        if ent.entity_id not in seen_ids:
            seen_ids.add(ent.entity_id)
            nodes.append({
                "id": ent.entity_id,
                "name": ent.name,
                "type": ent.entity_type or "entity",
            })

    # Also fetch recent relations for the link data
    try:
        for ent in entities[:20]:  # limit relations to first 20 entities
            relations_out = kg.query_pattern(source_id=ent.entity_id, max_results=5)
            for rel in relations_out:
                links.append({
                    "source": rel.source_id,
                    "target": rel.target_id,
                    "type": rel.relation_type,
                })
    except Exception:
        pass

    return {"nodes": nodes, "links": links}


@graph_router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get a single entity with its relations."""
    kg = _get_kg()
    try:
        entities = kg.search_entities(entity_id=entity_id, max_results=1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not entities:
        raise HTTPException(status_code=404, detail="Entity not found")

    ent = entities[0]
    relations_in = []
    relations_out = []

    try:
        relations_in = kg.query_pattern(target_id=entity_id, max_results=20)
        relations_out = kg.query_pattern(source_id=entity_id, max_results=20)
    except Exception:
        pass

    return {
        "entity": {
            "id": ent.entity_id,
            "name": ent.name,
            "type": ent.entity_type,
            "metadata": getattr(ent, "metadata", {}),
        },
        "incoming_relations": [str(r) for r in relations_in],
        "outgoing_relations": [str(r) for r in relations_out],
    }
