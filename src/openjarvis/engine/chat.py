"""ChatEngine — a simple stateless chat wrapper around the active InferenceEngine.

Provides a high-level interface for single-turn and streaming chat
without requiring callers to manage raw Message objects directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional

from openjarvis.core.types import Message, Role

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Lightweight single-message container compatible with ConversationManager history."""

    role: str
    content: str

    def to_message(self) -> Message:
        """Convert to the canonical ``Message`` type expected by InferenceEngine."""
        return Message(role=Role(self.role), content=self.content)


class ChatEngine:
    """Thin stateless wrapper around the default OpenJarvis InferenceEngine.

    Lazily resolves the active engine on first call so the process
    does not need a running engine at import time.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._model: str = model or ""
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from openjarvis.engine._discovery import get_engine
                self._engine = get_engine()
                if self._model:
                    # If engine supports model override, apply it
                    if hasattr(self._engine, "_model"):
                        self._engine._model = self._model
                elif hasattr(self._engine, "_model"):
                    self._model = self._engine._model or "ollama"
            except Exception as e:
                logger.error("Engine discovery failed: %s", e)
                raise RuntimeError(f"No inference engine available: {e}") from e
        return self._engine

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        """Send a list of messages and return the assistant reply as a ChatMessage."""
        engine = self._get_engine()
        core_msgs = [m.to_message() for m in messages]
        try:
            result = engine.generate(core_msgs)
            content = result.content if hasattr(result, "content") else str(result)
            return ChatMessage(role="assistant", content=content)
        except Exception as e:
            logger.error("ChatEngine.chat failed: %s", e)
            return ChatMessage(role="assistant", content="I'm sorry, I encountered an error.")

    async def chat_stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        """Async generator that streams tokens from the engine."""
        engine = self._get_engine()
        core_msgs = [m.to_message() for m in messages]
        try:
            if hasattr(engine, "stream"):
                for token in engine.stream(core_msgs):
                    content = token.content if hasattr(token, "content") else str(token)
                    if content:
                        yield content
            else:
                # Fallback: yield entire response as single chunk
                result = engine.generate(core_msgs)
                content = result.content if hasattr(result, "content") else str(result)
                yield content
        except Exception as e:
            logger.error("ChatEngine.chat_stream failed: %s", e)
            yield "I'm sorry, I encountered an error."
