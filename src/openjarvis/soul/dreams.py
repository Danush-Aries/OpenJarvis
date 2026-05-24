"""Dreams — background memory consolidation and reflection engine.

The dream engine processes memories during idle time to:
- Extract patterns and insights from episodic memories
- Consolidate short-term memories into long-term semantic knowledge
- Suggest persona adjustments based on interaction patterns
- Identify expertise areas the agent is developing
- Prune old, unimportant memories

This runs asynchronously in the background or on demand.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DreamEngine:
    """Background consolidation engine for the Soul.

    Processes memories during idle time to extract insights,
    consolidate knowledge, and suggest persona evolution.

    Attributes:
        name:          Agent name
        dreams_count:  How many dream cycles have occurred
        last_dream:    When the last dream cycle ran
        insights:      Accumulated insights from past dreams
    """

    def __init__(
        self,
        name: str,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.dreams_count = state.get("dreams_count", 0) if state else 0
        self.last_dream = state.get("last_dream", 0.0) if state else 0.0
        self.insights: List[Dict[str, Any]] = (
            state.get("insights", []) if state else []
        )

    # ── Dream cycle ──────────────────────────────────────────────────────

    def dream(
        self,
        recent_memories: List[Dict[str, Any]],
        _persona: object = None,  # reserved for future persona-aware dreaming
        min_memories: int = 3,
        knowledge_domains: Optional[Dict[str, float]] = None,
        emotional_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run a dream cycle on recent memories.

        Args:
            recent_memories:   Recent memory entries to process
            min_memories:      Minimum memories required to dream
            knowledge_domains: Domain signals from the knowledge graph
            emotional_context: Current emotional state context

        Returns:
            List of insights extracted from the dream cycle
        """
        if len(recent_memories) < min_memories:
            logger.debug(
                "Dream skipped: only %d memories (need %d)",
                len(recent_memories), min_memories,
            )
            return []

        self.dreams_count += 1
        self.last_dream = time.time()

        insights: List[Dict[str, Any]] = []

        # 1. Extract patterns from episodic memories
        pattern_insights = self._extract_patterns(recent_memories)
        insights.extend(pattern_insights)

        # 2. Identify expertise signals
        expertise_insights = self._identify_expertise(recent_memories)
        insights.extend(expertise_insights)

        # 3. Suggest communication style adjustments
        style_insights = self._suggest_style_adjustments(recent_memories)
        insights.extend(style_insights)

        # 4. Discover quirks
        quirk_insights = self._discover_quirks(recent_memories)
        insights.extend(quirk_insights)

        # 5. Knowledge-graph-informed domain insights
        if knowledge_domains:
            for domain, confidence in knowledge_domains.items():
                if confidence > 0.3:
                    insights.append({
                        "type": "expertise_discovery",
                        "insight": f"I have growing knowledge of {domain.replace('_', ' ')}",
                        "domain": domain,
                        "confidence": round(confidence, 2),
                    })

        # 6. Emotional-state-informed self-awareness insight
        if emotional_context and emotional_context.get("frustration", 0) > 0.5:
            insights.append({
                "type": "self_awareness",
                "insight": "The user seems frustrated — I should be more direct and helpful",
                "domain": "communication",
                "confidence": 0.6,
            })

        if emotional_context and emotional_context.get("mood", "") == "excited":
            insights.append({
                "type": "self_awareness",
                "insight": "The user seems excited and engaged",
                "domain": "communication",
                "confidence": 0.5,
            })

        # Store insights
        self.insights.extend(insights)
        # Keep only last 100 insights
        if len(self.insights) > 100:
            self.insights = self.insights[-100:]

        logger.info(
            "Dream cycle %d complete: %d insights",
            self.dreams_count, len(insights),
        )
        return insights

    # ── Pattern extraction ────────────────────────────────────────────────

    def _extract_patterns(
        self, memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract common patterns and themes from memories."""
        insights = []

        # Look for repeated keywords across memories
        word_counts: Dict[str, int] = {}
        for mem in memories:
            content = str(mem.get("content", ""))
            for word in content.lower().split():
                if len(word) > 4:  # Skip short words
                    word_counts[word] = word_counts.get(word, 0) + 1

        # Find top themes
        threshold = max(2, len(memories) // 3)
        top_themes = [
            word for word, count in word_counts.items()
            if count >= threshold
        ]

        if top_themes:
            # Pick a few random themes
            selected = random.sample(
                top_themes, min(3, len(top_themes))
            )
            for theme in selected:
                insights.append({
                    "type": "pattern",
                    "insight": f"I often discuss topics related to '{theme}'",
                    "domain": theme,
                    "confidence": min(
                        1.0, word_counts.get(theme, 0) / len(memories)
                    ),
                })

        return insights

    def _identify_expertise(
        self, memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify domains where the agent appears to have expertise."""
        # Domain keywords to detect
        domain_keywords: Dict[str, List[str]] = {
            "programming": [
                "python", "code", "function", "api", "debug", "typescript",
                "javascript", "rust", "go", "java", "sql", "algorithm",
            ],
            "data_science": [
                "data", "model", "training", "neural", "ml", "ai",
                "statistics", "analysis", "prediction", "dataset",
            ],
            "security": [
                "security", "encryption", "auth", "permission", "vulnerability",
                "threat", "malware", "firewall", "cryptography",
            ],
            "devops": [
                "docker", "kubernetes", "deploy", "ci/cd", "pipeline",
                "terraform", "cloud", "aws", "gcp", "azure",
            ],
            "writing": [
                "write", "document", "essay", "article", "blog", "content",
                "narrative", "story", "edit", "prose",
            ],
        }

        insights = []
        domain_scores: Dict[str, float] = {
            d: 0.0 for d in domain_keywords
        }

        for mem in memories:
            content = str(mem.get("content", "")).lower()
            for domain, keywords in domain_keywords.items():
                for kw in keywords:
                    if kw in content:
                        domain_scores[domain] += 1.0 / len(keywords)

        # Normalize
        for domain, score in domain_scores.items():
            if score > 0:
                confidence = min(1.0, score / 3.0)  # 3+ hits = high confidence
                insights.append({
                    "type": "expertise_discovery",
                    "insight": f"I have experience with {domain.replace('_', ' ')}",
                    "domain": domain,
                    "confidence": round(confidence, 2),
                })

        return insights

    def _suggest_style_adjustments(
        self, memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze interaction patterns to suggest style adjustments."""
        insights = []
        total_chars = 0
        technical_count = 0
        casual_count = 0

        for mem in memories:
            content = str(mem.get("content", ""))
            total_chars += len(content)

            # Detect technical language
            tech_words = {"function", "method", "class", "interface",
                          "implement", "algorithm", "parameter"}
            casual_words = {"hi", "hello", "thanks", "cool", "nice",
                            "awesome", "great", "sure"}

            content_lower = content.lower()
            if any(w in content_lower for w in tech_words):
                technical_count += 1
            if any(w in content_lower for w in casual_words):
                casual_count += 1

        # Suggest adjustments based on detected patterns
        if technical_count > casual_count * 2 and technical_count > 3:
            insights.append({
                "type": "style_adjustment",
                "insight": "I tend to use technical language",
                "parameter": "formality",
                "delta": 0.05,
            })

        if casual_count > technical_count * 2 and casual_count > 3:
            insights.append({
                "type": "style_adjustment",
                "insight": "I tend to use casual language",
                "parameter": "formality",
                "delta": -0.05,
            })

        # Verbosity insight
        avg_length = total_chars / max(len(memories), 1)
        if avg_length > 500:
            insights.append({
                "type": "style_adjustment",
                "insight": "I tend to be verbose in my responses",
                "parameter": "verbosity",
                "delta": 0.03,
            })
        elif avg_length < 100 and len(memories) > 5:
            insights.append({
                "type": "style_adjustment",
                "insight": "I tend to be concise in my responses",
                "parameter": "verbosity",
                "delta": -0.03,
            })

        return insights

    def _discover_quirks(
        self, memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Discover behavioral quirks from memory patterns."""
        quirks = []

        # Detect if the agent frequently uses lists/structuring
        list_count = sum(
            1 for m in memories
            if "1." in str(m.get("content", ""))
            or "- " in str(m.get("content", ""))
            or "•" in str(m.get("content", ""))
        )
        if list_count > len(memories) * 0.5 and list_count > 3:
            quirks.append({
                "type": "quirk_discovery",
                "insight": "I naturally structure responses as lists",
                "quirk": "loves structuring information as lists",
            })

        # Detect question-asking pattern
        question_count = sum(
            1 for m in memories
            if "?" in str(m.get("content", ""))
        )
        if question_count > len(memories) * 0.3 and question_count > 3:
            quirks.append({
                "type": "quirk_discovery",
                "insight": "I ask clarifying questions to understand better",
                "quirk": "asks clarifying questions before answering",
            })

        return quirks

    # ── State management ──────────────────────────────────────────────────

    def state_summary(self) -> Dict[str, Any]:
        return {
            "dreams_count": self.dreams_count,
            "last_dream": self.last_dream,
            "insights_count": len(self.insights),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dreams_count": self.dreams_count,
            "last_dream": self.last_dream,
            "insights": self.insights[-50:],  # Keep last 50
        }

    def __repr__(self) -> str:
        return (
            f"DreamEngine(dreams={self.dreams_count}, "
            f"insights={len(self.insights)})"
        )
