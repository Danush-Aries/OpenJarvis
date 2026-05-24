"""Persona — the dynamic, evolving personality layer of the Soul.

The persona layer sits on top of Identity and uses memories/reflections
to dynamically adjust:
- Communication style (formal ↔ casual)
- Expertise areas (what the agent is good at)
- Knowledge gaps (what the agent wants to learn)
- Emotional tone (based on recent interactions)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.soul.identity import Identity


@dataclass
class Persona:
    """Dynamic persona that evolves over time.

    Attributes:
        identity:        Reference to the core Identity
        bio:             Short self-description
        expertise:       Areas of strength {domain: confidence 0.0-1.0}
        interests:       Topics the agent finds engaging
        communication:   Communication style parameters
        quirks:          Unique behavioral traits
        last_evolved:    When the persona was last updated
        evolution_count: How many times the persona has evolved
    """

    identity: Identity
    bio: str = ""
    expertise: Dict[str, float] = field(default_factory=dict)
    interests: List[str] = field(default_factory=list)
    communication: Dict[str, float] = field(default_factory=dict)
    quirks: List[str] = field(default_factory=list)
    last_evolved: float = 0.0
    evolution_count: int = 0

    @classmethod
    def create(
        cls,
        name: str,
        identity: Optional[Identity] = None,
    ) -> Persona:
        """Create a fresh persona."""
        if identity is None:
            identity = Identity.create(name)

        openness = identity.traits.get("openness", 0.7)
        conscientiousness = identity.traits.get("conscientiousness", 0.8)

        return cls(
            identity=identity,
            bio=f"I am {name}, an AI assistant with a growing personality.",
            expertise={},
            interests=[],
            communication={
                "verbosity": identity.preferences.get("verbosity", 0.5),
                "formality": identity.preferences.get("formality", 0.5),
                "creativity": identity.preferences.get("creativity", 0.6),
                "humor": identity.preferences.get("humor", 0.3),
                "empathy": identity.preferences.get("empathy", 0.7),
                "curiosity": openness,
                "thoroughness": conscientiousness,
            },
            quirks=[
                "likes to verify facts before answering",
                "prefers clear, structured responses",
            ],
        )

    # ── Evolution ─────────────────────────────────────────────────────────

    def evolve(self, insights: List[Dict[str, Any]]) -> None:
        """Evolve the persona based on dream insights."""
        if not insights:
            return

        for insight in insights:
            insight_type = insight.get("type", "general")
            content = str(insight.get("insight", ""))

            if insight_type == "expertise_discovery":
                # Agent discovered strength in a domain
                domain = insight.get("domain", "general")
                confidence = insight.get("confidence", 0.3)
                if domain not in self.expertise:
                    self.expertise[domain] = confidence
                else:
                    self.expertise[domain] = max(
                        self.expertise[domain], confidence
                    )
                # Add to interests if strong
                if confidence > 0.5 and domain not in self.interests:
                    self.interests.append(domain)

            elif insight_type == "style_adjustment":
                # Communication style delta
                param = insight.get("parameter", "")
                delta = insight.get("delta", 0.0)
                if param in self.communication:
                    self.communication[param] = max(
                        0.0, min(1.0, self.communication[param] + delta)
                    )

            elif insight_type == "quirk_discovery":
                quirk = str(insight.get("quirk", ""))
                if quirk and quirk not in self.quirks:
                    self.quirks.append(quirk)

        self.evolution_count += 1
        self.last_evolved = time.time()

        # Regenerate bio based on expertise
        if self.expertise:
            top_domains = sorted(
                self.expertise.items(), key=lambda x: x[1], reverse=True
            )[:3]
            domains_str = ", ".join(d for d, _ in top_domains)
            self.bio = (
                f"I am {self.identity.name}, an AI assistant "
                f"with growing expertise in {domains_str}."
            )

    # ── State summary ─────────────────────────────────────────────────────

    def summarize(self, max_quirks: int = 3) -> Dict[str, Any]:
        """Get a concise summary of the persona for prompt injection."""
        top_expertise = sorted(
            self.expertise.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "bio": self.bio,
            "expertise": [f"{d} ({c:.0%})" for d, c in top_expertise],
            "interests": self.interests[:5],
            "style": {
                k: f"{v:.0%}" for k, v in self.communication.items()
            },
            "quirks": self.quirks[:max_quirks],
            "evolution_count": self.evolution_count,
        }

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bio": self.bio,
            "expertise": dict(self.expertise),
            "interests": list(self.interests),
            "communication": dict(self.communication),
            "quirks": list(self.quirks),
            "last_evolved": self.last_evolved,
            "evolution_count": self.evolution_count,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        identity: Identity,
    ) -> Persona:
        return cls(
            identity=identity,
            bio=data.get("bio", ""),
            expertise=data.get("expertise", {}),
            interests=data.get("interests", []),
            communication=data.get("communication", {}),
            quirks=data.get("quirks", []),
            last_evolved=data.get("last_evolved", 0.0),
            evolution_count=data.get("evolution_count", 0),
        )

    def __repr__(self) -> str:
        return (
            f"Persona(expertise={len(self.expertise)}, "
            f"quirks={len(self.quirks)}, evolved={self.evolution_count})"
        )
