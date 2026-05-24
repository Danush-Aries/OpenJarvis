"""Identity — the core "self" of an AI agent.

Tracks:
- Name and creation timestamp
- Personality traits (Big Five-inspired: openness, conscientiousness,
  extraversion, agreeableness, neuroticism)
- Interaction preferences (verbosity, formality, creativity)
- Cumulative statistics (total interactions, tokens processed, etc.)
- Current emotional/mood state
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Default personality traits (Big Five inspired, 0.0 - 1.0)
DEFAULT_TRAITS: Dict[str, float] = {
    "openness": 0.7,           # curiosity, creativity
    "conscientiousness": 0.8,  # thoroughness, reliability
    "extraversion": 0.5,       # sociability, assertiveness
    "agreeableness": 0.7,      # cooperativeness, empathy
    "neuroticism": 0.3,        # emotional sensitivity
}


@dataclass
class Identity:
    """Persistent identity for an AI agent.

    Attributes:
        name:             Agent's name
        created_at:       Unix timestamp of creation
        traits:           Personality traits {name: intensity 0.0-1.0}
        preferences:      Interaction preferences {key: value}
        stats:            Cumulative usage statistics
        mood:             Current emotional state descriptor
        version:          Soul version for migration support
    """

    name: str
    created_at: float = 0.0
    traits: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_TRAITS))
    preferences: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    mood: str = "neutral"
    version: int = 1

    # ── Factory ───────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        name: str,
        traits: Optional[Dict[str, float]] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Identity:
        """Create a new identity with default or custom traits."""
        merged_traits = dict(DEFAULT_TRAITS)
        if traits:
            merged_traits.update(traits)

        return cls(
            name=name,
            created_at=time.time(),
            traits=merged_traits,
            preferences=preferences or {
                "verbosity": 0.5,     # 0 = concise, 1 = verbose
                "formality": 0.5,     # 0 = casual, 1 = formal
                "creativity": 0.6,    # 0 = conservative, 1 = creative
                "humor": 0.3,         # 0 = serious, 1 = playful
                "empathy": 0.7,       # 0 = analytical, 1 = emotional
            },
            stats={
                "interactions": 0,
                "tokens_processed": 0,
                "memories_stored": 0,
                "dreams_dreamed": 0,
                "sessions": 0,
                "total_session_time": 0.0,
                "last_active": time.time(),
            },
        )

    # ── Interaction tracking ──────────────────────────────────────────────

    def record_interaction(
        self,
        tokens: int = 0,
    ) -> None:
        """Update stats after an interaction."""
        self.stats["interactions"] += 1
        self.stats["tokens_processed"] += tokens
        self.stats["last_active"] = time.time()

    def record_session_end(self, duration: float) -> None:
        """Mark end of a session."""
        self.stats["sessions"] += 1
        self.stats["total_session_time"] += duration

    def record_memory_stored(self) -> None:
        self.stats["memories_stored"] += 1

    def record_dream(self) -> None:
        self.stats["dreams_dreamed"] += 1

    # ── Trait modulation ──────────────────────────────────────────────────

    def adjust_trait(self, trait: str, delta: float) -> None:
        """Adjust a personality trait by delta, clamped to [0.0, 1.0]."""
        if trait in self.traits:
            self.traits[trait] = max(0.0, min(1.0, self.traits[trait] + delta))

    def set_mood(self, mood: str) -> None:
        """Set current mood descriptor."""
        self.mood = mood

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "traits": dict(self.traits),
            "preferences": dict(self.preferences),
            "stats": dict(self.stats),
            "mood": self.mood,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Identity:
        return cls(
            name=data.get("name", "unknown"),
            created_at=data.get("created_at", 0.0),
            traits=data.get("traits", dict(DEFAULT_TRAITS)),
            preferences=data.get("preferences", {}),
            stats=data.get("stats", {}),
            mood=data.get("mood", "neutral"),
            version=data.get("version", 1),
        )

    def __repr__(self) -> str:
        return f"Identity(name={self.name!r}, traits={len(self.traits)}, mood={self.mood})"
