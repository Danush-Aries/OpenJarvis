"""Knowledge — entity extraction, fact tracking, and knowledge graph for the Soul.

Implements a lightweight in-memory knowledge graph that:
- Extracts named entities from memory content using heuristic patterns
- Tracks facts as (subject, predicate, object) triples with confidence
- Detects and resolves contradictory facts (same subject+predicate, different object)
- Tracks temporal validity of facts (bi-temporal model inspired by Zep)
- Enables entity-relationship queries for richer memory recall

No external dependencies — uses regex and heuristic NLP patterns designed to
run efficiently on CPU (Intel i5, 8GB RAM).

Usage:
    kg = KnowledgeGraph()
    kg.add_memory("User Sarah loves programming in Python")
    entities = kg.query_entity("Sarah")
    facts = kg.query_facts(subject="Sarah")
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """A named entity discovered in memory.

    Attributes:
        name:         Canonical entity name (lowercased, normalized)
        entity_type:  Category (person, technology, place, organization, concept, etc.)
        confidence:   How certain we are this is a real entity (0.0-1.0)
        first_seen:   Timestamp of first occurrence
        last_seen:    Timestamp of most recent occurrence
        occurrence_count: How many times this entity has been mentioned
        aliases:      Alternative names for the same entity
    """

    name: str
    entity_type: str = "concept"
    confidence: float = 0.5
    first_seen: float = 0.0
    last_seen: float = 0.0
    occurrence_count: int = 1
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "occurrence_count": self.occurrence_count,
            "aliases": list(self.aliases),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Entity:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Fact
# ---------------------------------------------------------------------------


@dataclass
class Fact:
    """A structured fact extracted from memory.

    Uses a bi-temporal model (inspired by Zep/Graphiti):
    - ``timestamp``: When the fact was first known
    - ``valid_until``: When the fact became invalid (None = currently valid)

    This allows the system to handle changing information over time,
    e.g., "User works at Acme Corp (2023-2024)" → "User works at BigCorp (2024-)".
    Old facts are not deleted, just marked as invalid.

    Attributes:
        subject:         Entity the fact is about (e.g., "sarah")
        predicate:       Relation/attribute (e.g., "likes", "works_at", "knows")
        object:          Value or related entity (e.g., "python", "acme_corp")
        confidence:      How certain this fact is (0.0-1.0)
        source_memory_id: ID of the memory this was extracted from
        timestamp:       When this fact was first recorded
        valid_until:     When this fact became invalid (None = currently valid)
        is_inferred:     Whether this fact was inferred (vs directly extracted)
    """

    subject: str
    predicate: str
    object: str
    confidence: float = 0.5
    source_memory_id: str = ""
    timestamp: float = 0.0
    valid_until: Optional[float] = None
    is_inferred: bool = False

    @property
    def is_valid(self) -> bool:
        """Check if this fact is currently valid."""
        return self.valid_until is None or self.valid_until > time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source_memory_id": self.source_memory_id,
            "timestamp": self.timestamp,
            "valid_until": self.valid_until,
            "is_inferred": self.is_inferred,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Fact:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        valid = "valid" if self.is_valid else f"expired({self.valid_until})"
        return f"Fact({self.subject} —[{self.predicate}]→ {self.object}, {valid})"


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------

# Patterns for entity type detection
_ENTITY_TYPE_PATTERNS: List[Tuple[str, str]] = [
    (r"^[A-Z][a-z]+ [A-Z][a-z]+$", "person"),        # "John Smith"
    (r"^(Python|JavaScript|TypeScript|Rust|Go|Java|Kotlin|Swift"
     r"|React|Vue|Angular|Django|Flask|FastAPI|PyTorch|TensorFlow"
     r"|Docker|Kubernetes|AWS|GCP|Azure|Linux|MacOS|Windows)$", "technology"),
    (r"^(https?://|www\.)\S+$", "url"),
    (r"^@\w+$", "handle"),
    (r"^#\w+$", "hashtag"),
    (r"^(San Francisco|New York|London|Tokyo|Berlin|Paris|Sydney"
     r"|Seattle|Austin|Bangalore|Singapore)$", "place"),
]

# Common predicates to extract
_PREDICATE_PATTERNS: List[Tuple[str, str, str]] = [
    # "X likes Y", "X loves Y", "X enjoys Y"
    (r"(?:likes|loves|enjoys|prefers|adores?)\s+(\w+)", "likes", "likes"),
    # "X works at Y", "X works for Y"
    (r"works\s+(?:at|for)\s+(\w+(?:\s+\w+)?)", "works_at", "works_at"),
    # "X knows Y", "X understands Y"
    (r"(?:knows|understands?|is familiar with)\s+(\w+)", "knows", "knows"),
    # "X uses Y", "X uses" 
    (r"uses?\s+(\w+)", "uses", "uses"),
    # "X is a Y", "X is an Y"
    (r"is\s+(?:a|an)\s+(\w+)", "is_a", "is_a"),
    # "X has Y", "X owns Y"
    (r"(?:has|owns?|possesses?)\s+(\w+)", "has", "has"),
    # "X created Y", "X wrote Y", "X built Y"
    (r"(?:created|wrote|built|developed|made|designed)\s+(\w+)", "created", "created"),
]


class KnowledgeGraph:
    """Lightweight in-memory knowledge graph for entity and fact extraction.

    Extracts knowledge from memory content during ``add_memory()`` and stores
    it in structured form for richer retrieval and persona development.
    """

    def __init__(self) -> None:
        self._entities: Dict[str, Entity] = {}       # name -> Entity
        self._facts: List[Fact] = []                   # all facts
        self._entity_refs: Dict[str, Set[str]] = {}    # entity -> set of memory IDs

    # ── Core API ────────────────────────────────────────────────────────

    def add_memory(self, content: str, memory_id: str = "", timestamp: Optional[float] = None) -> List[Fact]:
        """Process a memory and extract entities + facts.

        Args:
            content:  The memory text content
            memory_id: ID of the memory entry this came from
            timestamp: When the memory was created (default: now)

        Returns:
            List of facts extracted from this memory
        """
        ts = timestamp or time.time()
        new_facts: List[Fact] = []

        # 1. Extract entities
        entities = self._extract_entities(content)
        for entity_name, entity_type, confidence in entities:
            self._upsert_entity(entity_name, entity_type, confidence, ts)
            if memory_id:
                self._entity_refs.setdefault(entity_name, set()).add(memory_id)

        # 2. Extract facts
        facts = self._extract_facts(content, memory_id, ts)
        for fact in facts:
            # Check for contradictions with existing facts
            self._resolve_contradiction_on_add(fact)
            self._facts.append(fact)
            new_facts.append(fact)
            if memory_id:
                self._entity_refs.setdefault(fact.subject, set()).add(memory_id)
                self._entity_refs.setdefault(fact.object, set()).add(memory_id)

        if new_facts:
            logger.debug("KnowledgeGraph: %d facts extracted from memory", len(new_facts))

        return new_facts

    def remove_memory(self, memory_id: str) -> int:
        """Remove all facts associated with a memory ID.

        Returns:
            Number of facts removed.
        """
        before = len(self._facts)
        self._facts = [f for f in self._facts if f.source_memory_id != memory_id]
        return before - len(self._facts)

    def query_entity(self, name: str) -> Optional[Entity]:
        """Get entity info by name (case-insensitive)."""
        key = name.lower().strip()
        return self._entities.get(key)

    def query_facts(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        valid_only: bool = True,
        limit: int = 20,
    ) -> List[Fact]:
        """Query facts by subject and/or predicate.

        Args:
            subject:     Filter by subject entity (case-insensitive)
            predicate:   Filter by predicate type
            valid_only:  Only return currently valid facts
            limit:       Max results

        Returns:
            List of matching facts, sorted by confidence (descending).
        """
        results = []
        for fact in self._facts:
            if valid_only and not fact.is_valid:
                continue
            if subject and fact.subject != subject.lower().strip():
                continue
            if predicate and fact.predicate != predicate:
                continue
            results.append(fact)

        results.sort(key=lambda f: f.confidence, reverse=True)
        return results[:limit]

    def query_related_entities(self, entity_name: str, max_depth: int = 1) -> List[Tuple[str, str, float]]:
        """Find entities related to the given entity via shared facts.

        Args:
            entity_name: Starting entity
            max_depth:   Relationship traversal depth (1 = direct only)

        Returns:
            List of (related_entity, relationship_type, confidence) tuples.
        """
        key = entity_name.lower().strip()
        related: Set[Tuple[str, str, float]] = set()

        for fact in self._facts:
            if not fact.is_valid:
                continue
            if fact.subject == key:
                related.add((fact.object, fact.predicate, fact.confidence))
            elif fact.object == key:
                # Reverse relationship
                related.add((fact.subject, f"~{fact.predicate}", fact.confidence))

        return sorted(related, key=lambda x: x[2], reverse=True)

    def query_memories_for_entity(self, entity_name: str) -> Set[str]:
        """Get memory IDs associated with an entity."""
        key = entity_name.lower().strip()
        return set(self._entity_refs.get(key, set()))

    def search_entities(self, query: str, limit: int = 10) -> List[Entity]:
        """Search entities by name (substring, case-insensitive)."""
        q = query.lower()
        results = [
            e for e in self._entities.values()
            if q in e.name or any(q in a for a in e.aliases)
        ]
        results.sort(key=lambda e: e.occurrence_count, reverse=True)
        return results[:limit]

    def get_domains_from_entities(self) -> Dict[str, float]:
        """Derive domain expertise signals from entity types.

        Returns:
            Dict of domain -> confidence based on entity presence.
        """
        domains: Dict[str, float] = {}
        tech_count = sum(
            1 for e in self._entities.values()
            if e.entity_type == "technology"
        )
        if tech_count > 0:
            domains["technology"] = min(1.0, tech_count / 5.0)
        return domains

    # ── Entity Extraction (Heuristic) ───────────────────────────────────

    def _extract_entities(self, text: str) -> List[Tuple[str, str, float]]:
        """Extract entities from text using heuristic patterns.

        Returns list of (entity_name, entity_type, confidence).
        """
        entities: List[Tuple[str, str, float]] = []

        # 1. Check capitalized multi-word names (potential people/organizations)
        # Match: "John Smith", "Acme Corporation"  
        for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
            name = match.group(1).lower()
            # Determine type
            etype = "person" if " " in name else "organization"
            entities.append((name, etype, 0.6))

        # 2. Check capitalized single words (potential proper nouns)
        for match in re.finditer(r'\b([A-Z][a-z]{2,})\b', text):
            word = match.group(1)
            name = word.lower()
            # Skip if at start of sentence (likely just capitalization)
            pos = match.start()
            if pos == 0 or text[pos - 1] in '.!?\n':
                continue

            # Check against known type patterns
            etype = "concept"
            confidence = 0.3
            for pattern, entity_type in _ENTITY_TYPE_PATTERNS[:5]:  # skip URL/handle patterns
                if re.match(pattern, word):
                    etype = entity_type
                    confidence = 0.7
                    break

            entities.append((name, etype, confidence))

        # 3. Extract URLs
        for match in re.finditer(r'(https?://[^\s]+)', text):
            entities.append((match.group(1).lower(), "url", 0.9))

        # 4. Extract handles and hashtags
        for match in re.finditer(r'@(\w+)', text):
            entities.append((match.group(1).lower(), "handle", 0.8))
        for match in re.finditer(r'#(\w+)', text):
            entities.append((match.group(1).lower(), "hashtag", 0.7))

        return entities

    def _extract_facts(self, content: str, memory_id: str, timestamp: float) -> List[Fact]:
        """Extract subject-predicate-object facts from content.

        Uses the subject entity from the content (first person/technology entity found)
        or falls back to the first capitalized word.
        """
        facts: List[Fact] = []
        content_lower = content.lower()

        # Find the primary subject entity in this content
        subject = self._find_primary_subject(content)
        if not subject:
            return facts

        # Try each predicate pattern
        for pattern, pred_key, _ in _PREDICATE_PATTERNS:
            for match in re.finditer(pattern, content_lower):
                obj = match.group(1).strip().lower()
                if not obj or obj in {"the", "a", "an", "this", "that", "it"}:
                    continue
                facts.append(Fact(
                    subject=subject,
                    predicate=pred_key,
                    object=obj,
                    confidence=0.5,
                    source_memory_id=memory_id,
                    timestamp=timestamp,
                ))

        return facts

    def _find_primary_subject(self, content: str) -> Optional[str]:
        """Find the primary subject entity in content.

        Priority:
        1. First person entity (e.g., "John")
        2. First technology entity (e.g., "Python")
        3. First capitalized word (potential entity)
        """
        # Check for "User", "user" as subject
        if re.search(r'\b(?:the\s+)?user\b', content.lower()):
            return "user"

        # Look for known entities in the content
        content_lower = content.lower()
        for name, entity in self._entities.items():
            if name in content_lower:
                return name

        # Look for capitalized words as potential subjects
        for match in re.finditer(r'\b([A-Z][a-z]{2,})\b', content):
            pos = match.start()
            if pos > 0 and content[pos - 1] not in '.!?\n':
                return match.group(1).lower()

        # Last resort: use first word as generic subject
        words = content_lower.split()
        if words and len(words[0]) > 2:
            return words[0]

        return None

    def _upsert_entity(
        self, name: str, entity_type: str, confidence: float, timestamp: float
    ) -> None:
        """Create or update an entity in the graph."""
        key = name.lower().strip()
        if key in self._entities:
            entity = self._entities[key]
            entity.last_seen = timestamp
            entity.occurrence_count += 1
            entity.confidence = max(entity.confidence, confidence)
            if entity_type != "concept" and entity.entity_type == "concept":
                entity.entity_type = entity_type
        else:
            self._entities[key] = Entity(
                name=key,
                entity_type=entity_type,
                confidence=confidence,
                first_seen=timestamp,
                last_seen=timestamp,
            )

    # ── Contradiction Resolution ─────────────────────────────────────────

    def _resolve_contradiction_on_add(self, new_fact: Fact) -> None:
        """When adding a fact, check for contradictions with existing facts.

        If the same subject+predicate exists with a *different* object,
        mark the old fact as expired (valid_until = now) so the new
        fact takes precedence. This is the bi-temporal approach — old
        facts are preserved for history but marked invalid.
        """
        for existing in self._facts:
            if not existing.is_valid:
                continue
            if (existing.subject == new_fact.subject
                    and existing.predicate == new_fact.predicate
                    and existing.object != new_fact.object
                    and existing.confidence <= new_fact.confidence):
                # The new fact contradicts and has >= confidence — expire the old one
                existing.valid_until = new_fact.timestamp
                logger.debug(
                    "Contradiction: '%s' → '%s' supersedes '%s'",
                    existing, new_fact, existing.object,
                )

    def resolve_all_contradictions(self) -> int:
        """Run contradiction resolution across all facts.

        Returns:
            Number of facts expired.
        """
        expired = 0
        # Group by subject+predicate
        groups: Dict[Tuple[str, str], List[Fact]] = {}
        for fact in self._facts:
            key = (fact.subject, fact.predicate)
            groups.setdefault(key, []).append(fact)

        for key, group in groups.items():
            if len(group) < 2:
                continue
            # Sort by timestamp (newest first)
            group.sort(key=lambda f: f.timestamp, reverse=True)
            # Keep the newest valid one, expire the rest
            for fact in group[1:]:
                if fact.is_valid:
                    fact.valid_until = group[0].timestamp
                    expired += 1

        return expired

    # ── Deduplication ────────────────────────────────────────────────────

    def deduplicate_facts(self) -> int:
        """Remove exact duplicate facts (same subject+predicate+object).

        Returns:
            Number of duplicates removed.
        """
        seen: Set[Tuple[str, str, str]] = set()
        unique: List[Fact] = []
        removed = 0
        for fact in self._facts:
            key = (fact.subject, fact.predicate, fact.object)
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            unique.append(fact)
        self._facts = unique
        return removed

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self._entities.values()],
            "facts": [f.to_dict() for f in self._facts],
            "entity_refs": {k: list(v) for k, v in self._entity_refs.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KnowledgeGraph:
        kg = cls()
        for e_data in data.get("entities", []):
            entity = Entity.from_dict(e_data)
            kg._entities[entity.name] = entity
        for f_data in data.get("facts", []):
            kg._facts.append(Fact.from_dict(f_data))
        for name, refs in data.get("entity_refs", {}).items():
            kg._entity_refs[name] = set(refs)
        return kg

    def stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        type_counts: Dict[str, int] = {}
        for e in self._entities.values():
            type_counts[e.entity_type] = type_counts.get(e.entity_type, 0) + 1
        valid_facts = sum(1 for f in self._facts if f.is_valid)
        return {
            "entities": len(self._entities),
            "facts": len(self._facts),
            "valid_facts": valid_facts,
            "types": type_counts,
        }

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraph(entities={len(self._entities)}, "
            f"facts={len(self._facts)})"
        )


__all__ = [
    "Entity",
    "Fact",
    "KnowledgeGraph",
]
