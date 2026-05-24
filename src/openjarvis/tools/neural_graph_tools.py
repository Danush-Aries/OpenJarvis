"""Tools for neural knowledge graph operations — entity extraction, graph querying, and associative reasoning."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline registry — no dependency on the full ToolRegistry system
# ---------------------------------------------------------------------------
_TOOLS: Dict[str, Any] = {}


def register(cls: Any) -> Any:
    _TOOLS[cls.__name__] = cls
    return cls


def get_tools() -> List[Any]:
    return list(_TOOLS.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_knowledge_graph():
    """Lazy import & singleton for the KnowledgeGraphMemory backend.

    Returns None if the storage backend is not installed.
    """
    try:
        from openjarvis.tools.storage.knowledge_graph import KnowledgeGraphMemory
        return KnowledgeGraphMemory()
    except ImportError:
        logger.warning("Knowledge graph storage backend not available")
        return None


# ---------------------------------------------------------------------------
# Auto Entity Extraction Tool
# ---------------------------------------------------------------------------


@register
class AutoEntityExtractTool:
    """Automatically extract entities and relations from text and store them in the knowledge graph."""

    tool_id = "kg_auto_extract"
    name = "Auto-Extract Entities"
    description = "Parse text to extract named entities (people, places, concepts, tools) and their relationships, then store them in the knowledge graph."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to extract entities from",
                },
                "source": {
                    "type": "string",
                    "description": "Optional source label for provenance tracking",
                },
            },
            "required": ["text"],
        }

    def execute(self, text: str, source: str = "") -> Dict[str, Any]:
        kg = _get_knowledge_graph()
        if kg is None:
            return {
                "status": "unavailable",
                "message": "Knowledge graph storage is not available. The storage module is not installed.",
                "entities_added": 0,
                "relations_added": 0,
            }
        extracted = self._extract_entities(text, source)
        results = {"entities": [], "relations": []}

        for ent in extracted.get("entities", []):
            try:
                kg.add_entity(ent)
                results["entities"].append(ent.entity_id)
            except Exception as e:
                logger.warning("Failed to add entity %s: %s", ent.entity_id, e)

        for rel in extracted.get("relations", []):
            try:
                kg.add_relation(rel)
                results["relations"].append(f"{rel.source_id} -> {rel.target_id}")
            except Exception as e:
                logger.warning("Failed to add relation: %s", e)

        return {
            "status": "ok",
            "entities_added": len(results["entities"]),
            "relations_added": len(results["relations"]),
            "details": results,
        }

    def _extract_entities(self, text: str, source: str) -> Dict[str, Any]:
        from openjarvis.tools.storage.knowledge_graph import Entity, Relation

        entities: List[Entity] = []
        relations: List[Relation] = []

        # ---- regex-based extraction for common patterns ----
        patterns = {
            "person": r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
            "concept": r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b",
            "tool": r"\b([A-Z][a-z]+API|[A-Z][a-z]+SDK|Open[A-Z][a-z]+|React|Vue|Angular|Django|Flask|FastAPI|PyTorch|TensorFlow)\b",
        }

        seen_entities: Dict[str, str] = {}
        for etype, pat in patterns.items():
            for match in re.finditer(pat, text):
                name = match.group(1)
                eid = name.lower().replace(" ", "_")
                if eid not in seen_entities:
                    seen_entities[eid] = etype
                    entities.append(Entity(
                        entity_id=eid,
                        entity_type=etype,
                        name=name,
                        metadata={"source": source} if source else {},
                    ))

        # ---- relation extraction via proximity ----
        words = re.findall(r"\b\w+\b", text.lower())
        for i, w in enumerate(words):
            if w in seen_entities:
                for j in range(i + 1, min(i + 10, len(words))):
                    if words[j] in seen_entities and words[j] != w:
                        rel_type = "related_to"
                        between = " ".join(words[i + 1:j])
                        if any(v in between for v in ("uses", "built", "created", "developed")):
                            rel_type = "uses"
                        elif any(v in between for v in ("part of", "belongs to", "in")):
                            rel_type = "part_of"
                        elif any(v in between for v in ("said", "told", "spoke")):
                            rel_type = "communicated_with"

                        relations.append(Relation(
                            source_id=w,
                            target_id=words[j],
                            relation_type=rel_type,
                            metadata={"source_text": between[:100]} if source else {},
                        ))

        return {"entities": entities, "relations": relations}


@register
class GraphQueryTool:
    """Query the knowledge graph by entity ID, type, or pattern."""

    tool_id = "kg_query"
    name = "Query Knowledge Graph"
    description = "Search the knowledge graph for entities matching a query, or find neighbors/patterns around a specific entity."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["entity", "neighbors", "type", "search"],
                    "description": "Type of query: 'entity' by ID, 'neighbors' around an entity, 'type' by entity type, 'search' by name substring",
                },
                "value": {
                    "type": "string",
                    "description": "Entity ID, entity type, or search term depending on query_type",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 20,
                },
            },
            "required": ["query_type", "value"],
        }

    def execute(self, query_type: str, value: str, max_results: int = 20) -> Dict[str, Any]:
        kg = _get_knowledge_graph()
        if kg is None:
            return {
                "status": "unavailable",
                "message": "Knowledge graph storage is not available. The storage module is not installed.",
            }

        if query_type == "entity":
            # search_entities can filter by entity_id
            entities = kg.search_entities(entity_id=value, max_results=max_results)
            if not entities:
                return {"status": "not_found", "query": value}
            entity = entities[0]
            relations_in = kg.query_pattern(target_id=value, max_results=max_results)
            relations_out = kg.query_pattern(source_id=value, max_results=max_results)
            return {
                "status": "ok",
                "entity": {
                    "id": entity.entity_id,
                    "name": entity.name,
                    "type": entity.entity_type,
                    "metadata": getattr(entity, "metadata", {}),
                },
                "incoming_relations": [str(r) for r in relations_in],
                "outgoing_relations": [str(r) for r in relations_out],
            }

        elif query_type == "neighbors":
            neighbors = kg.neighbors(value, max_results=max_results)
            return {
                "status": "ok",
                "entity_id": value,
                "neighbors": [str(n) for n in neighbors],
            }

        elif query_type == "type":
            entities = kg.search_entities(entity_type=value, max_results=max_results)
            return {
                "status": "ok",
                "entity_type": value,
                "entities": [
                    {"id": e.entity_id, "name": e.name, "type": e.entity_type}
                    for e in entities
                ],
                "count": len(entities),
            }

        elif query_type == "search":
            entities = kg.search_entities(name=value, max_results=max_results)
            return {
                "status": "ok",
                "search": value,
                "entities": [
                    {"id": e.entity_id, "name": e.name, "type": e.entity_type}
                    for e in entities
                ],
                "count": len(entities),
            }

        return {"status": "error", "message": f"Unknown query_type: {query_type}"}
