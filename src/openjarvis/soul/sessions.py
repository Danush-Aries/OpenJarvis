"""Sessions — session tracking, summarization, and cross-session context for the Soul.

Tracks interaction sessions and distills them into higher-level abstractions
that enrich the memory system. Inspired by Mem0's session scope and Letta's
core memory paging.

Each session captures:
- Start/end timestamps and duration
- Interaction count and token estimate
- Summary of key topics discussed
- Emotional trend across the session
- Entities and facts discovered

Session summaries are themselves stored as semantic memories, enabling
cross-session context retrieval.

Usage:
    session_log = SessionLog()
    session = session_log.start_session()
    # ... interactions happen ...
    session.record_interaction("user said...", "agent said...")
    session_log.end_session(session)  # auto-generates summary
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """A single interaction session.

    Sessions are bounded periods of interaction that get summarized
    upon completion. The summary is stored as a semantic memory for
    cross-session context.

    Attributes:
        id:               Unique session ID
        start_time:       When the session started
        end_time:         When the session ended (0.0 = active)
        interaction_count: Number of turns in this session
        token_estimate:   Approximate tokens used
        summaries:        Dict of {scale: summary_text}
                         scales: "brief" (1 line), "normal" (paragraph), "detailed"
        key_topics:       Topics discussed in this session
        entities_seen:    Entity names mentioned during the session
        dominant_mood:    Prevailing emotional tone of the session
        metadata:         Arbitrary metadata
    """

    id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    interaction_count: int = 0
    token_estimate: int = 0
    summaries: Dict[str, str] = field(default_factory=dict)
    key_topics: List[str] = field(default_factory=list)
    entities_seen: List[str] = field(default_factory=list)
    dominant_mood: str = "neutral"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls) -> Session:
        return cls(
            id=str(uuid.uuid4())[:12],
            start_time=time.time(),
        )

    @property
    def duration(self) -> float:
        """Session duration in seconds (0 if still active)."""
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def is_active(self) -> bool:
        return self.end_time == 0.0

    def record_interaction(self, user_text: str = "", agent_text: str = "") -> None:
        """Record a single interaction turn."""
        self.interaction_count += 1
        # Rough token estimate: ~4 chars per token
        self.token_estimate += (len(user_text) + len(agent_text)) // 4

    def generate_summary(
        self,
        memories: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate a summary of the session.

        Uses a simple heuristic-based approach: extracts key topics
        from memory content, detects most frequent entities, and
        constructs a structured summary.

        In production, this would use an LLM call. For the local-only
        path, we use a lightweight keyword-frequency approach.

        Args:
            memories: Optional list of memory dicts from this session

        Returns:
            Summary text
        """
        # Extract topics from memories
        topics: Dict[str, int] = {}
        all_content = []
        if memories:
            for mem in memories:
                content = str(mem.get("content", ""))
                all_content.append(content)
                words = content.lower().split()
                for word in words:
                    if len(word) > 5:
                        topics[word] = topics.get(word, 0) + 1

        # Top topics by frequency
        sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
        if sorted_topics:
            self.key_topics = [t for t, _ in sorted_topics[:5]]

        # Generate brief summary
        topic_str = ", ".join(self.key_topics[:3]) if self.key_topics else "general conversation"
        self.summaries["brief"] = (
            f"Session with {self.interaction_count} turns about {topic_str}."
        )

        # Generate normal summary
        mood_str = f" Mood: {self.dominant_mood}." if self.dominant_mood != "neutral" else ""
        entity_str = f" Entities: {', '.join(self.entities_seen[:5])}." if self.entities_seen else ""
        duration_m = self.duration / 60
        self.summaries["normal"] = (
            f"A {duration_m:.0f}-min session ({self.interaction_count} turns, "
            f"~{self.token_estimate} tokens) discussing {topic_str}."
            f"{mood_str}{entity_str}"
        )

        return self.summaries.get("normal", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "interaction_count": self.interaction_count,
            "token_estimate": self.token_estimate,
            "summaries": dict(self.summaries),
            "key_topics": list(self.key_topics),
            "entities_seen": list(self.entities_seen),
            "dominant_mood": self.dominant_mood,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Session:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Session Log
# ---------------------------------------------------------------------------


class SessionLog:
    """Manages interaction sessions and generates cross-session context.

    Maintains a history of completed sessions and their summaries,
    enabling the soul to recall what happened in previous sessions
    without replaying all the memory entries.
    """

    def __init__(self, max_history: int = 50) -> None:
        self._active_session: Optional[Session] = None
        self._completed: List[Session] = []
        self._max_history = max_history

    # ── Session lifecycle ───────────────────────────────────────────────

    def start_session(self) -> Session:
        """Start a new session (ends any active session first)."""
        if self._active_session is not None:
            self.end_session(self._active_session)

        self._active_session = Session.create()
        logger.debug("Session started: %s", self._active_session.id)
        return self._active_session

    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session, if any."""
        return self._active_session

    def end_session(
        self,
        session: Optional[Session] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
    ) -> Session:
        """End a session, generate summary, and archive it.

        Args:
            session:  Session to end (defaults to active session)
            memories: Memories from this session for summary generation

        Returns:
            The completed session with summary.
        """
        target = session or self._active_session
        if target is None:
            logger.warning("No active session to end")
            # Return a minimal session
            return Session(id="noop", start_time=0, end_time=0)

        target.end_time = time.time()
        target.generate_summary(memories=memories)
        self._completed.append(target)

        # Prune if over limit
        if len(self._completed) > self._max_history:
            self._completed = self._completed[-self._max_history:]

        if target is self._active_session:
            self._active_session = None

        logger.debug(
            "Session ended: %s (%d turns, %.1fm)",
            target.id, target.interaction_count, target.duration / 60,
        )
        return target

    def record_interaction(
        self,
        user_text: str = "",
        agent_text: str = "",
        entity_names: Optional[List[str]] = None,
    ) -> None:
        """Record an interaction in the active session."""
        if self._active_session is None:
            self._active_session = Session.create()

        self._active_session.record_interaction(user_text, agent_text)

        if entity_names:
            for name in entity_names:
                if name not in self._active_session.entities_seen:
                    self._active_session.entities_seen.append(name)

    # ── Cross-session context ──────────────────────────────────────────

    def get_recent_sessions(self, n: int = 5) -> List[Session]:
        """Get the N most recent completed sessions."""
        return self._completed[-n:]

    def get_cross_session_summary(self, max_sessions: int = 5) -> str:
        """Generate a cross-session context summary.

        Combines summaries from recent sessions into a cohesive
        overview of what the agent has been doing.

        Args:
            max_sessions: Number of recent sessions to include

        Returns:
            Multi-line summary text.
        """
        recent = self._completed[-max_sessions:]
        if not recent:
            return "No previous sessions."

        lines = ["Recent sessions:"]
        for i, s in enumerate(recent, 1):
            summary = s.summaries.get("brief", s.summaries.get("normal", ""))
            time_str = time.strftime("%b %d %H:%M", time.localtime(s.start_time))
            lines.append(f"  {i}. [{time_str}] {summary}")

        return "\n".join(lines)

    def get_topics_across_sessions(self) -> Dict[str, int]:
        """Aggregate key topics across all completed sessions."""
        topics: Dict[str, int] = {}
        for session in self._completed:
            for topic in session.key_topics:
                topics[topic] = topics.get(topic, 0) + 1
        return dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)[:20])

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self._active_session.to_dict() if self._active_session else None,
            "completed": [s.to_dict() for s in self._completed],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionLog:
        log = cls()
        active = data.get("active")
        if active:
            log._active_session = Session.from_dict(active)
        log._completed = [Session.from_dict(s) for s in data.get("completed", [])]
        return log

    def stats(self) -> Dict[str, Any]:
        """Get statistics about session history."""
        if not self._completed:
            return {"total_sessions": 0, "total_interactions": 0}

        total_int = sum(s.interaction_count for s in self._completed)
        total_tokens = sum(s.token_estimate for s in self._completed)
        avg_duration = sum(s.duration for s in self._completed) / len(self._completed)

        return {
            "total_sessions": len(self._completed),
            "total_interactions": total_int,
            "total_tokens": total_tokens,
            "avg_duration_m": round(avg_duration / 60, 1),
            "is_active": self._active_session is not None,
        }

    def __repr__(self) -> str:
        return (
            f"SessionLog(active={self._active_session is not None}, "
            f"completed={len(self._completed)})"
        )


__all__ = [
    "Session",
    "SessionLog",
]
