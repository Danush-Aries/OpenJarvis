"""Emotion — affective state tracking for the Soul.

Implements emotional/affective computing for the AI agent:
- Valence-arousal-dominance (VAD) emotional state model
- Sentiment analysis of interaction content
- Mood curves over time (track emotional trends)
- Frustration detection (repeated negative sentiment + repetition)
- Emotional state influences persona communication style

No external NLP dependencies — uses keyword-based sentiment heuristics
designed for CPU efficiency.

Usage:
    emotion = EmotionalState()
    emotion.update_from_interaction("I love this!", "positive")
    valence = emotion.valence
    mood_label = emotion.current_mood
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentiment lexicon (simplified, CPU-friendly)
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: set = {
    "love", "great", "amazing", "awesome", "fantastic", "excellent", "wonderful",
    "happy", "glad", "pleased", "delighted", "grateful", "thankful", "joy",
    "beautiful", "brilliant", "perfect", "fun", "exciting", "incredible",
    "good", "nice", "cool", "sweet", "welcome", "yes", "absolutely",
    "helpful", "useful", "thanks", "thank", "appreciate", "perfect",
    "best", "love", "loved", "loving", "favorite", "amazing",
}

_NEGATIVE_WORDS: set = {
    "hate", "terrible", "awful", "horrible", "bad", "worst", "wrong",
    "angry", "frustrated", "annoying", "annoyed", "upset", "sad",
    "disappointed", "disappointing", "useless", "stupid", "broken",
    "fails", "failed", "failure", "error", "bug", "crash", "slow",
    "ugly", "garbage", "terrible", "hate", "hated", "hating",
    "no", "never", "nothing", "none", "can't", "won't", "doesn't",
    "problem", "issue", "difficult", "hard", "confused", "confusing",
}

_HIGH_AROUSAL_WORDS: set = {
    "amazing", "incredible", "terrible", "horrible", "urgent", "critical",
    "excited", "excited", "furious", "panic", "emergency", "immediately",
    "!",
}

_LOW_AROUSAL_WORDS: set = {
    "calm", "relaxed", "peaceful", "serene", "tranquil", "gentle",
    "slow", "quiet", "boring", "dull", "sleepy", "tired",
}

_DOMINANT_WORDS: set = {
    "must", "will", "need", "demand", "require", "insist", "command",
    "always", "never", "certainly", "definitely", "absolutely",
}

_SUBMISSIVE_WORDS: set = {
    "maybe", "perhaps", "possibly", "might", "could", "would",
    "sorry", "apologize", "please", "if possible", "whenever",
    "suggest", "recommend", "optionally",
}


# ---------------------------------------------------------------------------
# Emotional State
# ---------------------------------------------------------------------------


@dataclass
class EmotionalState:
    """Affective state of the AI agent.

    Uses the VAD (Valence-Arousal-Dominance) emotional model:

    - **Valence** (-1.0 to 1.0): Pleasure/displeasure
        - Negative = sad, angry, frustrated
        - Positive = happy, content, excited
    - **Arousal** (0.0 to 1.0): Calm/excited
        - Low = calm, bored, tired
        - High = excited, alert, anxious
    - **Dominance** (0.0 to 1.0): In control / submissive
        - Low = submissive, unsure
        - High = dominant, confident

    The state decays toward neutral over time and is updated by
    interactions.

    Attributes:
        valence:         Current valence (-1.0 to 1.0)
        arousal:         Current arousal (0.0 to 1.0)
        dominance:       Current dominance (0.0 to 1.0)
        mood:            Current mood label
        mood_history:    Time-stamped mood snapshots (for trend analysis)
        frustration_level: Accumulated frustration (0.0 to 1.0)
        last_update:     When the state was last updated
        decay_rate:      How fast emotions decay toward neutral (per hour)
    """

    valence: float = 0.0
    arousal: float = 0.5
    dominance: float = 0.5
    mood: str = "neutral"
    mood_history: List[Dict[str, Any]] = field(default_factory=list)
    frustration_level: float = 0.0
    last_update: float = 0.0
    decay_rate: float = 0.1  # per hour toward neutral

    # ── Update ──────────────────────────────────────────────────────────

    def update_from_interaction(
        self,
        text: str,
        explicit_sentiment: Optional[str] = None,
    ) -> None:
        """Update emotional state based on interaction content.

        Args:
            text:               The interaction text to analyze
            explicit_sentiment: Optional override ("positive", "negative", "neutral")
        """
        now = time.time()
        self._apply_decay(now)

        if explicit_sentiment:
            sentiment = explicit_sentiment
        else:
            sentiment = self._analyze_sentiment(text)

        # Compute deltas based on sentiment
        valence_delta, arousal_delta, dominance_delta = self._compute_deltas(
            text, sentiment
        )

        self.valence = max(-1.0, min(1.0, self.valence + valence_delta))
        self.arousal = max(0.0, min(1.0, self.arousal + arousal_delta))
        self.dominance = max(0.0, min(1.0, self.dominance + dominance_delta))

        # Track frustration (accumulates with negative sentiment)
        if sentiment == "negative":
            self.frustration_level = min(1.0, self.frustration_level + 0.1)
        else:
            self.frustration_level = max(0.0, self.frustration_level - 0.05)

        # Update mood label
        self.mood = self._compute_mood()
        self.last_update = now

        # Record in history (sample every 10th update or significant changes)
        self.mood_history.append({
            "timestamp": now,
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "mood": self.mood,
            "frustration": self.frustration_level,
        })
        # Keep last 100 entries
        if len(self.mood_history) > 100:
            self.mood_history = self.mood_history[-100:]

    def _apply_decay(self, now: float) -> None:
        """Decay emotional state toward neutral over time.

        Uses exponential decay toward zero for valence and toward
        0.5 for arousal/dominance.
        """
        if self.last_update == 0:
            self.last_update = now
            return

        elapsed_hours = (now - self.last_update) / 3600
        if elapsed_hours <= 0:
            return

        decay_factor = self.decay_rate * elapsed_hours
        decay_factor = min(1.0, decay_factor)

        # Decay toward neutral
        self.valence = self.valence * (1.0 - decay_factor)
        self.arousal = 0.5 + (self.arousal - 0.5) * (1.0 - decay_factor)
        self.dominance = 0.5 + (self.dominance - 0.5) * (1.0 - decay_factor)
        self.frustration_level *= (1.0 - decay_factor * 0.5)

    # ── Sentiment Analysis (lightweight) ────────────────────────────────

    @staticmethod
    def _analyze_sentiment(text: str) -> str:
        """Analyze sentiment of text using keyword heuristics.

        Returns "positive", "negative", or "neutral".
        """
        if not text:
            return "neutral"

        words = set(text.lower().split())
        pos_count = len(words & _POSITIVE_WORDS)
        neg_count = len(words & _NEGATIVE_WORDS)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        else:
            return "neutral"

    @staticmethod
    def _compute_deltas(text: str, sentiment: str) -> Tuple[float, float, float]:
        """Compute VAD deltas based on sentiment and text content."""
        valence_delta = 0.0
        arousal_delta = 0.0
        dominance_delta = 0.0

        if sentiment == "positive":
            valence_delta = 0.1
        elif sentiment == "negative":
            valence_delta = -0.15
            arousal_delta = 0.05  # negative emotion often increases arousal

        # Arousal from text features
        text_lower = text.lower()
        if any(w in text_lower for w in _HIGH_AROUSAL_WORDS):
            arousal_delta += 0.1
        if any(w in text_lower for w in _LOW_AROUSAL_WORDS):
            arousal_delta -= 0.05

        # Dominance from text features
        if any(w in text_lower for w in _DOMINANT_WORDS):
            dominance_delta += 0.08
        if any(w in text_lower for w in _SUBMISSIVE_WORDS):
            dominance_delta -= 0.05

        # Exclamation marks increase arousal
        if "!" in text:
            arousal_delta += 0.05

        # Question marks decrease dominance slightly
        if "?" in text:
            dominance_delta -= 0.03

        return valence_delta, arousal_delta, dominance_delta

    # ── Mood Classification ─────────────────────────────────────────────

    def _compute_mood(self) -> str:
        """Map VAD values to a mood label.

        Based on the circumplex model of affect:
        - High valence + high arousal = excited
        - High valence + low arousal = calm
        - Low valence + high arousal = tense/angry
        - Low valence + low arousal = sad/depressed
        """
        v = self.valence
        a = self.arousal
        f = self.frustration_level

        if f > 0.7:
            return "frustrated"
        if v > 0.3:
            if a > 0.6:
                return "excited"
            elif a < 0.4:
                return "calm"
            return "happy"
        elif v < -0.3:
            if a > 0.6:
                return "tense"
            elif a < 0.4:
                return "sad"
            return "unhappy"
        else:
            if a > 0.7:
                return "alert"
            elif a < 0.3:
                return "tired"
            return "neutral"

    # ── Queries ─────────────────────────────────────────────────────────

    def get_emotional_context(self) -> Dict[str, Any]:
        """Get a summary of emotional state for prompt injection."""
        return {
            "mood": self.mood,
            "valence": round(self.valence, 2),
            "arousal": round(self.arousal, 2),
            "dominance": round(self.dominance, 2),
            "frustration": round(self.frustration_level, 2),
        }

    def get_recent_trend(self, window: int = 10) -> str:
        """Analyze recent mood trend.

        Args:
            window: Number of recent history entries to analyze

        Returns:
            Trend description: "improving", "declining", "stable", or "volatile"
        """
        if len(self.mood_history) < 3:
            return "stable"

        recent = self.mood_history[-window:]
        valences = [e["valence"] for e in recent]

        if len(valences) < 2:
            return "stable"

        # Simple linear trend
        first_half = sum(valences[:len(valences)//2]) / max(len(valences)//2, 1)
        second_half = sum(valences[len(valences)//2:]) / max(len(valences) - len(valences)//2, 1)

        delta = second_half - first_half
        if delta > 0.2:
            return "improving"
        elif delta < -0.2:
            return "declining"

        # Check volatility
        variance = sum((v - sum(valences)/len(valences))**2 for v in valences) / len(valences)
        if variance > 0.1:
            return "volatile"

        return "stable"

    # ── Communication Style Influence ───────────────────────────────────

    def communication_adjustments(self) -> Dict[str, float]:
        """Get communication style adjustments based on emotional state.

        These deltas can be applied to the persona's communication parameters.

        Returns:
            Dict of {parameter: delta} adjustments.
        """
        adjustments: Dict[str, float] = {}

        if self.frustration_level > 0.5:
            # User is frustrated — be more concise and empathetic
            adjustments["verbosity"] = -0.1
            adjustments["empathy"] = 0.1

        if self.valence < -0.3:
            # Negative valence — be more supportive
            adjustments["empathy"] = 0.05

        if self.arousal > 0.7:
            # High arousal — be more calming
            adjustments["verbosity"] = -0.05
            adjustments["creativity"] = -0.05

        if self.dominance < 0.3:
            # Low confidence — be more deferential
            adjustments["formality"] = 0.03

        return adjustments

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "mood": self.mood,
            "mood_history": list(self.mood_history),
            "frustration_level": self.frustration_level,
            "last_update": self.last_update,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EmotionalState:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return (
            f"EmotionalState(mood={self.mood}, "
            f"V={self.valence:.2f}, A={self.arousal:.2f}, D={self.dominance:.2f})"
        )


__all__ = [
    "EmotionalState",
]
