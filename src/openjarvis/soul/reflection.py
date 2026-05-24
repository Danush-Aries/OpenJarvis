"""Reflection — Self-improvement loop for the Soul.

The self-improvement loop meta-cognitively analyzes:
1. Memory health (too many/few memories, stale data, consolidation needed)
2. Persona development (stagnant traits, unexplored expertise)
3. Dream quality (insight diversity, pattern richness)
4. Storage hygiene (backup age, disk usage)
5. General enhancement suggestions

This enables the agent to continuously evolve and improve itself.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enhancement Suggestion
# ---------------------------------------------------------------------------


@dataclass
class EnhancementSuggestion:
    """A suggestion for how to improve the soul system.

    Attributes:
        category:    Area of improvement (memory, persona, dreams, storage, general)
        title:       Short title
        description: Detailed description of the issue and solution
        priority:    1 (critical) - 5 (nice to have)
        actionable:  Whether this can be auto-applied
        apply_fn:    Callable to apply the enhancement (set after creation)
    """

    category: str
    title: str
    description: str
    priority: int = 3
    actionable: bool = False
    apply_fn: Optional[Callable[[], Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "actionable": self.actionable,
        }


# ---------------------------------------------------------------------------
# Self-Improvement Loop
# ---------------------------------------------------------------------------


class SelfImprovementLoop:
    """Meta-cognitive analysis engine for the Soul.

    Analyzes memory, persona, dreams, and storage to suggest improvements.
    """

    def __init__(self, soul: Any) -> None:  # Soul type, avoid circular
        self.soul = soul
        self._suggestions: List[EnhancementSuggestion] = []
        self._applied_count = 0
        self._last_analysis = 0.0

    # ── Main analysis ────────────────────────────────────────────────────

    def analyze(self) -> List[EnhancementSuggestion]:
        """Run full analysis and return enhancement suggestions."""
        self._suggestions = []

        self._check_memory_health()
        self._check_persona_development()
        self._check_dream_quality()
        self._check_storage_hygiene()
        self._check_knowledge_health()
        self._check_emotional_health()
        self._check_working_memory_health()
        self._check_general_health()

        self._suggestions.sort(key=lambda s: s.priority)
        self._last_analysis = time.time()

        if self._suggestions:
            logger.info(
                "Self-improvement analysis: %d suggestions found",
                len(self._suggestions),
            )
        else:
            logger.info("Self-improvement analysis: system looks healthy!")

        return list(self._suggestions)

    # ── Specialized checks ────────────────────────────────────────────────

    def _check_memory_health(self) -> None:
        """Analyze memory health and suggest improvements."""
        stats = self.soul.memory.stats()
        total = stats.get("total", 0)

        # Too few memories
        if total == 0:
            self._add_suggestion(
                category="memory",
                title="No memories stored",
                description="The soul has no memories yet. Consider seeding initial "
                            "knowledge or enabling memory capture during interactions.",
                priority=2,
            )
        elif total < 5:
            self._add_suggestion(
                category="memory",
                title="Very few memories",
                description=f"Only {total} memories. The soul's recall will be limited. "
                            "Enable more frequent memory storage during interactions.",
                priority=3,
            )

        # Imbalanced memory types
        episodic = stats.get("episodic", 0)
        semantic = stats.get("semantic", 0)
        procedural = stats.get("procedural", 0)

        if episodic > 20 and semantic < 3:
            self._add_suggestion(
                category="memory",
                title="Run memory consolidation",
                description=f"Episodic memories ({episodic}) far outnumber semantic ({semantic}). "
                            "Running a dream cycle will extract patterns and consolidate knowledge.",
                priority=2,
                actionable=True,
                apply_fn=lambda: self.soul.reflect(),
            )

        if total > 100:
            self._add_suggestion(
                category="memory",
                title="Memory consolidation recommended",
                description=f"The soul has {total} memories. Consider running consolidation "
                            "to prune old, low-importance entries.",
                priority=3,
            )

        # Check for stale memories (not accessed recently)
        if total > 10:
            stale_count = self._count_stale_memories()
            if stale_count > total * 0.5:
                self._add_suggestion(
                    category="memory",
                    title="Many stale memories",
                    description=f"{stale_count}/{total} memories haven't been accessed recently. "
                                "Consider consolidation to improve retrieval quality.",
                    priority=4,
                )

    def _check_persona_development(self) -> None:
        """Analyze persona health and suggest improvements."""
        persona = self.soul.persona

        # No expertise developed
        if not persona.expertise:
            self._add_suggestion(
                category="persona",
                title="No expertise areas",
                description="The persona hasn't developed any expertise yet. "
                            "Interact with more diverse topics to build knowledge domains.",
                priority=3,
            )

        # Stagnant evolution
        if persona.evolution_count == 0:
            self._add_suggestion(
                category="persona",
                title="Persona hasn't evolved yet",
                description="Run a dream cycle to discover patterns and evolve the persona "
                            "based on interaction history.",
                priority=2,
                actionable=True,
                apply_fn=lambda: self.soul.reflect(),
            )

        # Check for trait imbalance
        traits = self.soul.identity.traits
        extreme_traits = [
            t for t, v in traits.items()
            if v > 0.95 or v < 0.05
        ]
        if extreme_traits:
            self._add_suggestion(
                category="persona",
                title=f"Extreme traits detected: {', '.join(extreme_traits)}",
                description=f"Traits {', '.join(extreme_traits)} are at extreme values. "
                            "Consider adjusting for more balanced behavior.",
                priority=4,
            )

    def _check_dream_quality(self) -> None:
        """Analyze dream health and suggest improvements."""
        dreams = self.soul.dreams

        if dreams.dreams_count == 0:
            self._add_suggestion(
                category="dreams",
                title="No dream cycles run",
                description="The dream engine hasn't processed any memories yet. "
                            "Run a dream cycle to extract insights and consolidate knowledge.",
                priority=1,
                actionable=True,
                apply_fn=lambda: self.soul.reflect(),
            )

        # Low insight diversity
        if dreams.dreams_count > 3 and len(dreams.insights) < 2:
            self._add_suggestion(
                category="dreams",
                title="Low insight diversity",
                description=f"After {dreams.dreams_count} dream cycles, only "
                            f"{len(dreams.insights)} insights were generated. "
                            "Consider more diverse interactions.",
                priority=4,
            )

        # Very active dreaming (adjust cadence)
        if dreams.dreams_count > 50 and len(dreams.insights) < 10:
            self._add_suggestion(
                category="dreams",
                title="Inefficient dreaming",
                description=f"{dreams.dreams_count} dream cycles produced only "
                            f"{len(dreams.insights)} insights. Consider increasing the "
                            "minimum memory threshold for dreaming.",
                priority=4,
            )

    def _check_storage_hygiene(self) -> None:
        """Analyze storage health and suggest improvements."""
        soul_dir = None
        try:
            from openjarvis.soul.storage import DEFAULT_BASE_DIR
            name = self.soul.name
            base_dir = DEFAULT_BASE_DIR
            soul_dir = base_dir / name
        except Exception:
            return

        if soul_dir and soul_dir.exists():
            # Check file size
            soul_file = soul_dir / "soul.json"
            if soul_file.exists():
                size_kb = soul_file.stat().st_size / 1024
                if size_kb > 1024:  # > 1MB
                    self._add_suggestion(
                        category="storage",
                        title="Large soul file",
                        description=f"Soul file is {size_kb:.0f}KB. Consider running "
                                    "consolidation to reduce memory footprint.",
                        priority=3,
                    )

            # Check backups
            backup_dir = soul_dir / "backups"
            if backup_dir.exists():
                backup_count = len(list(backup_dir.glob("soul_*.json")))
                if backup_count > 20:
                    self._add_suggestion(
                        category="storage",
                        title="Many backups",
                        description=f"{backup_count} backups exist. Consider cleaning up "
                                    "old backups to save disk space.",
                        priority=5,
                    )

    def _check_knowledge_health(self) -> None:
        """Analyze knowledge graph health."""
        try:
            kg = self.soul.knowledge
        except AttributeError:
            return

        stats = kg.stats()

        if stats["entities"] == 0:
            self._add_suggestion(
                category="knowledge",
                title="No entities in knowledge graph",
                description="The knowledge graph hasn't extracted any entities yet. "
                            "Entities are extracted automatically during memory storage.",
                priority=3,
            )
        elif stats["entities"] < 5:
            self._add_suggestion(
                category="knowledge",
                title="Very few entities",
                description=f"Only {stats['entities']} entities in the knowledge graph. "
                            "More diverse interactions will help build entity awareness.",
                priority=4,
            )

        if stats["facts"] > 0 and stats["valid_facts"] < stats["facts"] * 0.5:
            self._add_suggestion(
                category="knowledge",
                title="Many expired facts",
                description=f"{stats['facts'] - stats['valid_facts']} of {stats['facts']} facts "
                            "have been superseded by contradictory information. "
                            "Consider running fact consolidation.",
                priority=4,
            )

    def _check_emotional_health(self) -> None:
        """Analyze emotional state health."""
        try:
            emotion = self.soul.emotion
        except AttributeError:
            return

        ctx = emotion.get_emotional_context()

        if ctx.get("frustration", 0) > 0.7:
            self._add_suggestion(
                category="emotion",
                title="High frustration level detected",
                description=f"Frustration level is at {ctx['frustration']:.0%}. "
                            "The user may be experiencing issues. Consider being more "
                            "helpful and direct in responses.",
                priority=2,
            )
        elif ctx.get("frustration", 0) > 0.4:
            self._add_suggestion(
                category="emotion",
                title="Elevated frustration",
                description=f"Frustration level is at {ctx['frustration']:.0%}. "
                            "Monitor for patterns in what's causing frustration.",
                priority=3,
            )

        trend = emotion.get_recent_trend()
        if trend == "declining":
            self._add_suggestion(
                category="emotion",
                title="Declining emotional trend",
                description="The emotional valence has been trending downward. "
                            "Consider adjusting communication style to be more empathetic.",
                priority=3,
            )

    def _check_working_memory_health(self) -> None:
        """Analyze working memory usage."""
        try:
            working = self.soul.memory.working
            total = self.soul.memory.stats().get("total", 0)
        except AttributeError:
            return

        wm_ids = working.get_ids()

        if total > 10 and not wm_ids:
            self._add_suggestion(
                category="memory",
                title="Working memory is empty",
                description=f"With {total} memories in storage, working memory has no entries. "
                            "Consider pinning important memories for faster recall.",
                priority=4,
            )

        if working.is_pinned("") if len(wm_ids) == 0 else False:
            pass

        # Check if pinned entries still exist in memory
        pinned = [pid for pid in wm_ids if pid in working._pinned_ids]
        if pinned:
            # Verify they still exist in any tier
            all_ids = set()
            for tier_name in ("episodic", "semantic", "procedural"):
                tier = getattr(self.soul.memory, tier_name, None)
                if tier:
                    all_ids.update(e.id for e in tier._entries)
            missing = [pid for pid in pinned if pid not in all_ids]
            if missing:
                self._add_suggestion(
                    category="memory",
                    title="Orphaned pinned memories",
                    description=f"{len(missing)} pinned memories no longer exist. "
                                "Run unpin to clean up working memory.",
                    priority=4,
                )

    def _check_general_health(self) -> None:
        """General system health checks."""
        identity = self.soul.identity

        # Low interaction count
        if identity.stats.get("interactions", 0) == 0:
            self._add_suggestion(
                category="general",
                title="No interactions yet",
                description="The soul hasn't had any interactions. Start a conversation "
                            "to begin building memory and personality.",
                priority=2,
            )

        # Check for session tracking
        if identity.stats.get("sessions", 0) == 0 and identity.stats.get("interactions", 0) > 0:
            self._add_suggestion(
                category="general",
                title="Session tracking not active",
                description="Interactions are happening but session boundaries aren't "
                            "being tracked. Consider wrapping interactions in sessions.",
                priority=4,
            )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _add_suggestion(
        self,
        category: str,
        title: str,
        description: str,
        priority: int = 3,
        actionable: bool = False,
        apply_fn: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Add a suggestion to the list."""
        suggestion = EnhancementSuggestion(
            category=category,
            title=title,
            description=description,
            priority=priority,
            actionable=actionable,
        )
        if actionable and apply_fn is not None:
            suggestion.apply_fn = apply_fn
        self._suggestions.append(suggestion)

    def _count_stale_memories(self) -> int:
        """Count memories not accessed in the last 7 days."""
        cutoff = time.time() - (7 * 86400)
        stale = 0
        for memory_type in ("episodic", "semantic", "procedural"):
            tier = getattr(self.soul.memory, memory_type, None)
            if tier:
                stale += sum(
                    1 for e in tier._entries
                    if e.last_accessed < cutoff
                )
        return stale

    def apply(self, suggestion: EnhancementSuggestion) -> bool:
        """Apply an enhancement suggestion.

        Args:
            suggestion: The suggestion to apply

        Returns:
            True if applied successfully
        """
        if not suggestion.actionable or suggestion.apply_fn is None:
            logger.warning("Suggestion '%s' is not auto-applicable", suggestion.title)
            return False

        try:
            suggestion.apply_fn()
            self._applied_count += 1
            logger.info("Applied enhancement: %s", suggestion.title)
            return True
        except Exception as e:
            logger.error("Failed to apply enhancement '%s': %s", suggestion.title, e)
            return False

    def suggestion_summary(self) -> Dict[str, Any]:
        """Get a summary of analysis results."""
        return {
            "total_suggestions": len(self._suggestions),
            "by_category": {
                cat: [s.to_dict() for s in self._suggestions if s.category == cat]
                for cat in set(s.category for s in self._suggestions)
            },
            "applied_count": self._applied_count,
            "last_analysis": self._last_analysis,
        }

    def __repr__(self) -> str:
        return (
            f"SelfImprovementLoop(suggestions={len(self._suggestions)}, "
            f"applied={self._applied_count})"
        )
