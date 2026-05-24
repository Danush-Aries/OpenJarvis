"""Soul — persistent identity, tiered memory, and evolving personality for OpenJarvis.

The Soul system gives the AI agent a persistent "self" that:
- Remembers past conversations and learns from them (episodic memory)
- Extracts and stores knowledge (semantic memory)
- Learns skills and procedures (procedural memory)
- Develops a dynamic persona that evolves with use
- Processes memories during idle time (dreaming/consolidation)
- Maintains identity across sessions
- Tracks entities, relationships, and facts (knowledge graph)
- Models emotional/affective state (VAD model)
- Summarizes sessions for cross-session context

Thread Safety:
  A module-level soul cache ensures multiple ConversationManager sessions
  sharing the same soul_name reuse the same Soul instance. The cache uses
  a threading.Lock for safe concurrent access.

Usage:
    from openjarvis.soul import Soul

    soul = Soul.load_or_create("my_agent")
    soul.remember("user said they love python")
    memory = soul.recall("what does the user like?")
    personality = soul.persona.summarize()
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.soul.identity import Identity
from openjarvis.soul.memory import (
    EpisodicMemory,
    ProceduralMemory,
    SemanticMemory,
    TieredMemory,
    MemoryEntry,
    WorkingMemory,
)
from openjarvis.soul.persona import Persona
from openjarvis.soul.dreams import DreamEngine
from openjarvis.soul.storage import SoulStorage
from openjarvis.soul.errors import SoulPersistenceError
from openjarvis.soul.reflection import SelfImprovementLoop, EnhancementSuggestion
from openjarvis.soul.knowledge import KnowledgeGraph, Entity, Fact
from openjarvis.soul.emotional import EmotionalState
from openjarvis.soul.sessions import SessionLog, Session

logger = logging.getLogger(__name__)

# ── Thread-safe soul cache ────────────────────────────────────────────────
# Prevents multiple ConversationManager sessions from creating separate
# Soul instances that all write to the same soul.json file concurrently.
_soul_cache: Dict[str, "Soul"] = {}
_soul_cache_lock = threading.Lock()


def get_soul(name: str) -> Optional["Soul"]:
    """Get a soul from the cache by name.

    Returns None if the soul hasn't been loaded yet.
    Use ``Soul.load_or_create()`` to load or create a soul.
    """
    with _soul_cache_lock:
        return _soul_cache.get(name)


def _cache_soul(soul: "Soul") -> None:
    """Store a soul in the module-level cache."""
    with _soul_cache_lock:
        _soul_cache[soul.name] = soul


def _uncache_soul(name: str) -> None:
    """Remove a soul from the cache."""
    with _soul_cache_lock:
        _soul_cache.pop(name, None)


class Soul:
    """The persistent self of an AI agent — identity, memory, persona, and dreams.

    Attributes:
        identity:    Core identity (name, traits, preferences, state)
        memory:      Tiered memory system (episodic, semantic, procedural)
        persona:     Dynamic, evolving personality
        dreams:      Background consolidation and reflection engine
        knowledge:   Entity extraction and knowledge graph
        emotion:     Emotional/affective state (VAD model)
        sessions:    Session tracking and cross-session context
        name:        Shortcut to identity.name
    """

    def __init__(
        self,
        identity: Identity,
        memory: TieredMemory,
        persona: Persona,
        dreams: DreamEngine,
    ) -> None:
        self.identity = identity
        self.memory = memory
        self.persona = persona
        self.dreams = dreams
        self.knowledge: KnowledgeGraph = KnowledgeGraph()
        self.emotion: EmotionalState = EmotionalState()
        self.sessions: SessionLog = SessionLog()
        self._storage: Optional[SoulStorage] = None
        self._improvement: Optional[SelfImprovementLoop] = None

    @property
    def name(self) -> str:
        return self.identity.name

    @property
    def improvement(self) -> SelfImprovementLoop:
        """Lazy-init self-improvement loop."""
        if self._improvement is None:
            self._improvement = SelfImprovementLoop(self)
        return self._improvement

    # ── Factory methods ───────────────────────────────────────────────────

    @classmethod
    def load_or_create(
        cls,
        name: str,
        soul_dir: Optional[Path] = None,
        traits: Optional[Dict[str, float]] = None,
    ) -> Soul:
        """Load an existing soul from disk, or create a fresh one.

        Uses an in-memory cache to ensure thread safety when multiple
        ConversationManager sessions share the same soul name.

        Args:
            name:      Agent name / identity key
            soul_dir:  Directory for soul data (default: ~/.jarvis/souls/<name>/)
            traits:    Initial personality traits {trait: intensity 0.0-1.0}
        """
        # Check cache first — prevents concurrent writes to soul.json
        cached = get_soul(name)
        if cached is not None:
            logger.debug("Returning cached soul: %s", name)
            return cached

        storage = SoulStorage(name, base_dir=soul_dir)

        if storage.exists():
            logger.info("Loading existing soul: %s", name)
            soul = cls._from_storage(storage)
        else:
            logger.info("Creating new soul: %s", name)
            identity = Identity.create(name=name, traits=traits or {})
            memory = TieredMemory.create(name)
            persona = Persona.create(name, identity=identity)
            dreams = DreamEngine(name)
            soul = cls(identity=identity, memory=memory, persona=persona, dreams=dreams)
            soul._storage = storage
            soul._persist()

        # Cache the soul instance
        _cache_soul(soul)
        return soul

    @classmethod
    def _from_storage(cls, storage: SoulStorage) -> Soul:
        """Reconstruct a Soul from persisted data."""
        data = storage.load()
        identity = Identity.from_dict(data.get("identity", {}))
        memory = TieredMemory.from_dict(name=storage.name, data=data.get("memory", {}))
        persona = Persona.from_dict(data.get("persona", {}), identity=identity)
        dreams = DreamEngine(storage.name, state=data.get("dreams", {}))
        soul = cls(identity=identity, memory=memory, persona=persona, dreams=dreams)
        soul._storage = storage

        # New v2 subsystems (graceful loading for soul files without them)
        if "knowledge" in data:
            soul.knowledge = KnowledgeGraph.from_dict(data["knowledge"])
        if "emotion" in data:
            soul.emotion = EmotionalState.from_dict(data["emotion"])
        if "sessions" in data:
            soul.sessions = SessionLog.from_dict(data["sessions"])

        return soul

    @classmethod
    def invalidate_cache(cls, name: Optional[str] = None) -> None:
        """Invalidate cached soul instance(s).

        Use this if you need to force a fresh load from disk.
        Args:
            name: If provided, invalidate only this soul. Otherwise, clear all.
        """
        if name is not None:
            _uncache_soul(name)
        else:
            with _soul_cache_lock:
                _soul_cache.clear()

    # ── Core Memory API ──────────────────────────────────────────────────

    def remember(
        self,
        content: str,
        memory_type: str = "episodic",
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store something in memory.

        Also triggers:
        - Knowledge graph extraction (entities, facts)
        - Emotional state update
        - Session recording

        Args:
            content:     The experience, fact, or procedure to remember
            memory_type: "episodic" (default), "semantic", or "procedural"
            importance:  0.0 (trivial) - 1.0 (critical), None = auto-computed
            metadata:    Optional tags, timestamps, emotional valence, etc.

        Returns:
            The memory entry ID for future reference (e.g., for pinning).
        """
        # Store in memory
        self.memory.store(content, memory_type=memory_type, importance=importance or None,
                         metadata=metadata)

        # Extract knowledge (entities and facts from content)
        facts = self.knowledge.add_memory(content)
        if facts:
            # Store extracted facts as semantic memories too
            for fact in facts:
                fact_text = f"{fact.subject} {fact.predicate} {fact.object}"
                self.memory.store(fact_text, memory_type="semantic",
                                  importance=0.7, metadata={"source": "knowledge_graph"})

        # Update emotional state from interaction sentiment
        self.emotion.update_from_interaction(content)

        # Record in session log
        entity_names = [e.name for e in self.knowledge.search_entities(content, limit=5)]
        self.sessions.record_interaction(
            user_text=content,
            entity_names=entity_names,
        )

        # Update identity stats
        self.identity.record_memory_stored()
        self._persist()
        return "stored"

    def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 5,
        use_mmr: bool = False,
        include_working: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories.

        Supports enhanced retrieval with MMR diversity re-ranking
        and working memory inclusion.

        Args:
            query:           Search query or context
            memory_type:     Filter by type (None = all types)
            limit:           Max results
            use_mmr:         Apply MMR diversity re-ranking
            include_working: Include pinned/sticky working memory items

        Returns:
            List of memory dicts with keys: content, type, timestamp, metadata, score
        """
        return self.memory.retrieve(
            query, memory_type=memory_type, limit=limit,
            use_mmr=use_mmr, include_working=include_working,
        )

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
            query: Forget memories whose content matches query text (substring, case-insensitive)

        Returns:
            Number of memories removed.

        Note:
            Only one filter is applied at a time, with priority:
            memory_id > memory_type > query.
        """
        removed = self.memory.forget(
            memory_id=memory_id,
            memory_type=memory_type,
            query=query,
        )
        # Also clean up knowledge graph
        if memory_id:
            self.knowledge.remove_memory(memory_id)
        if removed:
            self._persist()
        return removed

    # ── Knowledge Graph API ─────────────────────────────────────────────

    def query_entity(self, name: str) -> Optional[Entity]:
        """Look up an entity by name."""
        return self.knowledge.query_entity(name)

    def query_facts(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        limit: int = 20,
    ) -> List[Fact]:
        """Query knowledge graph facts."""
        return self.knowledge.query_facts(subject=subject, predicate=predicate, limit=limit)

    def search_entities(self, query: str) -> List[Entity]:
        """Search for entities by name."""
        return self.knowledge.search_entities(query)

    def query_related_entities(self, entity_name: str) -> List[tuple]:
        """Find entities related to a given entity."""
        return self.knowledge.query_related_entities(entity_name)

    # ── Emotional State API ─────────────────────────────────────────────

    def get_emotional_context(self) -> Dict[str, Any]:
        """Get current emotional state for prompt injection."""
        return self.emotion.get_emotional_context()

    def emotional_trend(self) -> str:
        """Analyze recent emotional trend."""
        return self.emotion.get_recent_trend()

    # ── Working Memory API ──────────────────────────────────────────────

    def pin_memory(self, memory_id: str) -> None:
        """Pin a memory to working memory (always included in recall)."""
        self.memory.working.pin(memory_id)
        self._persist()

    def unpin_memory(self, memory_id: str) -> None:
        """Remove a memory from working memory."""
        self.memory.working.unpin(memory_id)
        self._persist()

    def get_working_memory(self) -> List[str]:
        """Get IDs of entries currently in working memory."""
        return self.memory.working.get_ids()

    # ── Session API ─────────────────────────────────────────────────────

    def start_session(self) -> Session:
        """Start a new interaction session."""
        return self.sessions.start_session()

    def end_session(self) -> Optional[Session]:
        """End the current session and generate summary."""
        active = self.sessions.get_active_session()
        if active is None:
            return None
        # Collect recent memories for summary
        recent = self.memory.retrieve("", memory_type="episodic", limit=20)
        session = self.sessions.end_session(memories=recent)
        # Store the session summary as a semantic memory
        summary = session.summaries.get("normal", "")
        if summary and len(summary) > 20:
            self.memory.store(
                f"[Session] {summary}",
                memory_type="semantic",
                importance=0.6,
                metadata={"source": "session_summary", "session_id": session.id},
            )
        self._persist()
        return session

    def get_cross_session_context(self) -> str:
        """Get a summary of recent sessions for context injection."""
        return self.sessions.get_cross_session_summary()

    # ── Deduplication ───────────────────────────────────────────────────

    def deduplicate_memories(self, threshold: float = 0.92) -> int:
        """Deduplicate near-duplicate memory entries.

        Args:
            threshold: Cosine similarity threshold [0.0-1.0]

        Returns:
            Number of duplicates removed.
        """
        removed = self.memory.deduplicate(threshold)
        removed += self.knowledge.deduplicate_facts()
        if removed:
            self._persist()
        return removed

    # ── Reflection ──────────────────────────────────────────────────────

    def reflect(self) -> Dict[str, Any]:
        """Run a reflection/dream cycle — consolidates memories, updates persona.

        Now also:
        - Processes knowledge graph for entity patterns
        - Considers emotional state in persona evolution

        Returns:
            Dict with reflection insights
        """
        recent = self.memory.retrieve("", memory_type="episodic", limit=20)
        if not recent:
            return {"reflection": "no_memories", "insights": []}

        # Merge knowledge graph domain signals into the reflection
        knowledge_domains = self.knowledge.get_domains_from_entities()
        emotional_context = self.emotion.get_emotional_context()

        insights = self.dreams.dream(
            recent, self.persona,
            knowledge_domains=knowledge_domains,
            emotional_context=emotional_context,
        )
        if insights:
            for insight in insights:
                self.memory.store(
                    str(insight.get("insight", "")),
                    memory_type="semantic",
                    importance=0.7,
                    metadata={"source": "dream", **insight},
                )
            self.persona.evolve(insights)
            # Also feed insights into emotional state (successful reflection is positive)
            self.emotion.update_from_interaction(
                f"Completed reflection with {len(insights)} insights",
                explicit_sentiment="positive",
            )
            self._persist()

        return {"reflection": "completed", "insights": insights or []}

    def suggest_enhancements(self) -> List[EnhancementSuggestion]:
        """Run the self-improvement loop and get enhancement suggestions."""
        return self.improvement.analyze()

    def apply_enhancement(self, suggestion: EnhancementSuggestion) -> bool:
        """Apply a specific enhancement suggestion."""
        return self.improvement.apply(suggestion)

    # ── State Summary ───────────────────────────────────────────────────

    def state_summary(self) -> Dict[str, Any]:
        """Get a full snapshot of the soul's current state."""
        return {
            "name": self.identity.name,
            "identity": self.identity.to_dict(),
            "persona": self.persona.to_dict(),
            "memory_stats": self.memory.stats(),
            "dreams": self.dreams.state_summary(),
            "knowledge": self.knowledge.stats(),
            "emotion": self.emotion.get_emotional_context(),
            "sessions": self.sessions.stats(),
            "working_memory": self.memory.working.get_ids(),
        }

    def _persist(self) -> None:
        """Write current state to disk with error resilience."""
        if self._storage is None:
            return
        try:
            data = {
                "identity": self.identity.to_dict(),
                "memory": self.memory.to_dict(),
                "persona": self.persona.to_dict(),
                "dreams": self.dreams.to_dict(),
                "knowledge": self.knowledge.to_dict(),
                "emotion": self.emotion.to_dict(),
                "sessions": self.sessions.to_dict(),
            }
            self._storage.save(data)
        except (IOError, OSError, PermissionError, SoulPersistenceError) as e:
            logger.error("Failed to persist soul '%s': %s", self.name, e)

    @classmethod
    def list_souls(cls, base_dir: Optional[Path] = None) -> List[str]:
        """List all available soul names."""
        return SoulStorage.list_souls(base_dir=base_dir)

    def close(self) -> None:
        """Flush buffered writes and release resources."""
        if self._storage is not None:
            self._storage.close()
        _uncache_soul(self.name)

    @classmethod
    def close_all(cls) -> None:
        """Close every soul that is currently cached.

        Flushes all WriteBuffers and removes entries from the cache.
        Safe to call during server shutdown.
        """
        with _soul_cache_lock:
            names = list(_soul_cache.keys())
            souls = list(_soul_cache.values())
        for soul in souls:
            try:
                if soul._storage is not None:
                    soul._storage.close()
            except (IOError, OSError, PermissionError, SoulPersistenceError) as e:
                logger.debug("Error closing soul '%s': %s", soul.name, e)
        with _soul_cache_lock:
            for name in names:
                _soul_cache.pop(name, None)


__all__ = [
    "Soul",
    "Identity",
    "TieredMemory",
    "Persona",
    "DreamEngine",
    "SelfImprovementLoop",
    "EnhancementSuggestion",
    "KnowledgeGraph",
    "EmotionalState",
    "SessionLog",
    "WorkingMemory",
    "Entity",
    "Fact",
    "Session",
    "get_soul",
]
