"""ConversationManager — persistent multi-turn conversation session.

Manages chat history, routes messages through the active InferenceEngine
(via ChatEngine), optionally generates TTS audio, and provides a simple
in-memory knowledge store for short-term memory across turns.

This is the central orchestration layer used by:
  - VoiceAssistant (src/openjarvis/voice/voice_assistant.py)
  - Chat API router (src/openjarvis/server/router_chat.py)

Soul Integration:
  — Each session auto-loads a Soul for persistent identity/memory
  — Soul persona context is injected into the system prompt
  — Each interaction is stored in soul memory
  - After N interactions, a dream/reflection cycle auto-runs
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openjarvis.engine.chat import ChatEngine, ChatMessage

logger = logging.getLogger(__name__)

# ── J.A.R.V.I.S. persona system prompt ────────────────────────────────────────
_DEFAULT_SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), "
    "Tony Stark's personal AI assistant. "
    "You are polite, precise, and slightly dry with your wit. "
    "You address the user as 'sir' or 'Dhanush'. "
    "Respond concisely — never ramble. "
    "You have access to web browsing, file operations, and code execution tools. "
    "Efficiency Guidelines:\n"
    "- To search for information, answer questions about the web, or read web content, ALWAYS prefer the high-speed and credit-saving 'web_search' API tool.\n"
    "- If the user asks you to open a website, URL, file, or application, ALWAYS use the 'launch_app' tool (passing the URL/path to the 'url' parameter) to safely, natively, and instantly open it directly on their desktop using Python webbrowser, which consumes ZERO credits and runs entirely locally. Avoid 'browser_navigate' for simply opening a website for the user."
)

# Auto-reflect every N interactions to consolidate memories
_SOUL_AUTO_REFLECT_INTERVAL = 5


class ConversationManager:
    """Stateful, session-scoped conversation manager with Soul integration.

    Args:
        session_id:    Unique session identifier. Auto-generated if not provided.
        system_prompt: Override the default J.A.R.V.I.S. system prompt.
        soul_name:     Name of the soul to load/create for this session.
                       If None, uses "default" for all sessions.

    Attributes:
        _history: List of ``ChatMessage`` objects representing the conversation.
        _soul:    Optional Soul instance for persistent identity and memory.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        soul_name: Optional[str] = None,
    ) -> None:
        self.session_id: str = session_id or uuid4().hex[:12]
        self._system_prompt_base: str = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self._history: List[ChatMessage] = []
        self._memory: List[Dict[str, str]] = []  # lightweight short-term memory
        self._created_at: float = time.time()
        self._interaction_count: int = 0

        # ── Resolve Model from config ───────────────────────────────────
        import os
        from openjarvis.core.config import load_config
        try:
            cfg = load_config()
            configured_model = cfg.intelligence.default_model or "meta/llama-3.1-8b-instruct"
        except Exception:
            configured_model = "meta/llama-3.1-8b-instruct"

        from openjarvis.nvidia_config import NVIDIA_API_KEY
        if not os.environ.get("NVIDIA_API_KEY"):
            os.environ["NVIDIA_API_KEY"] = NVIDIA_API_KEY

        self._chat: ChatEngine = ChatEngine(model=configured_model)
        self._last_model: str = configured_model

        # ── Initialize Soul ─────────────────────────────────────────────
        self._soul = None
        self._soul_name = soul_name or "default"
        self._init_soul()

        logger.info(
            "ConversationManager session created: %s (model: %s, soul: %s)",
            self.session_id, configured_model, self._soul_name,
        )

    def _init_soul(self) -> None:
        """Load or create the soul for this session.

        If loading fails (e.g., corrupted file), gracefully degrades
        to operating without a soul rather than crashing.

        Also starts a soul session for tracking cross-interaction context.
        """
        try:
            from openjarvis.soul import Soul
            self._soul = Soul.load_or_create(self._soul_name)
            # Start a session for this conversation
            self._soul.start_session()
            logger.info(
                "Soul '%s' loaded, session started for %s",
                self._soul_name, self.session_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to load soul '%s': %s. Running without soul.",
                self._soul_name, e,
            )
            self._soul = None

    @property
    def _system_prompt(self) -> str:
        """Build the system prompt dynamically, injecting soul context.

        Injects (in order):
          1. Base personality prompt
          2. Evolved persona from soul
          3. Current emotional state
          4. Cross-session context from previous conversations
          5. Known entities from the knowledge graph

        All sections are wrapped in [System Note] blocks so the model
        can distinguish them from core instructions.
        """
        prompt = self._system_prompt_base

        if self._soul is None:
            return prompt

        try:
            # ── 1. Evolved Persona ──────────────────────────────────
            persona = self._soul.persona.summarize()
            parts = []

            if persona.get("bio"):
                parts.append(f"Your evolving identity: {persona['bio']}")

            if persona.get("expertise"):
                expertise_str = ", ".join(persona["expertise"][:5])
                parts.append(f"Your demonstrated expertise: {expertise_str}")

            if persona.get("quirks"):
                quirks_str = ", ".join(persona["quirks"][:3])
                parts.append(f"Your behavioral traits: {quirks_str}")

            if persona.get("style"):
                style = persona["style"]
                style_desc = []
                if float(style.get("formality", "50%").rstrip("%")) > 60:
                    style_desc.append("formal")
                elif float(style.get("formality", "50%").rstrip("%")) < 30:
                    style_desc.append("casual")
                if float(style.get("verbosity", "50%").rstrip("%")) > 60:
                    style_desc.append("verbose")
                elif float(style.get("verbosity", "50%").rstrip("%")) < 30:
                    style_desc.append("concise")
                if style_desc:
                    parts.append(f"Your natural communication style: {', '.join(style_desc)}")

            if parts:
                prompt += "\n\n[System Note — Your Evolved Persona]\n"
                prompt += "\n".join(f"• {p}" for p in parts)
                prompt += "\n[/System Note]"

            # ── 2. Emotional State ──────────────────────────────────
            emotion = self._soul.get_emotional_context()
            if emotion.get("self_awareness"):
                lines = ["[System Note — Your Current State]"]
                sa = emotion["self_awareness"]
                if sa.get("mood"):
                    lines.append(f"• Your current mood: {sa['mood']}")
                if sa.get("frustration_level"):
                    lines.append(f"• Frustration level: {sa['frustration_level']}")
                if sa.get("communication_style"):
                    lines.append(f"• Recommended communication: {sa['communication_style']}")
                lines.append("[/System Note]")
                prompt += "\n\n" + "\n".join(lines)

            # ── 3. Cross-Session Context ────────────────────────────
            session_context = self._soul.get_cross_session_context()
            if session_context and len(session_context) > 20:
                prompt += (
                    f"\n\n[System Note — Recent Session Context]\n"
                    f"{session_context[:500]}\n"
                    f"[/System Note]"
                )

            # ── 4. Knowledge Graph Entities ─────────────────────────
            entities = self._soul.search_entities("")
            if entities:
                entity_names = [e.name for e in entities[:8]]
                prompt += (
                    f"\n\n[System Note — Known Entities]\n"
                    f"You are aware of these topics: {', '.join(entity_names)}.\n"
                    f"[/System Note]"
                )

        except Exception as e:
            logger.debug("Failed to inject soul context: %s", e)

        return prompt

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """End the soul session and flush resources.

        Call this when the conversation ends (e.g., voice assistant stops,
        server shuts down) so the soul persists session summaries and
        releases the cache entry.
        """
        if self._soul is not None:
            try:
                self._soul.end_session()
                self._soul.close()
                logger.info(
                    "Soul '%s' session ended, resources released",
                    self._soul_name,
                )
            except Exception as e:
                logger.debug("Error closing soul session: %s", e)
            finally:
                self._soul = None

    # ------------------------------------------------------------------
    # Core message handling
    # ------------------------------------------------------------------

    def send_message(self, message: str, voice: bool = False) -> Dict[str, Any]:
        """Send a user message, get a reply, optionally generate TTS audio.

        Integrates with the Soul system:
        1. Stores user message in soul memory
        2. Injects soul persona context into system prompt
        3. Stores assistant reply in soul memory
        4. Auto-runs dream/reflection every N interactions

        Args:
            message: Raw user text input.
            voice:   If True, generates base64-encoded TTS audio in response.

        Returns:
            Dict with keys: response, model, tool_calls, audio, elapsed,
            history_length.
        """
        t0 = time.time()
        self._history.append(ChatMessage(role="user", content=message))
        self._interaction_count += 1

        # Store in soul memory with source tag
        if self._soul is not None:
            try:
                source = "voice" if voice else "chat"
                self._soul.remember(
                    f"User asked: {message[:500]}",
                    memory_type="episodic",
                    importance=0.6,
                    metadata={
                        "session": self.session_id,
                        "role": "user",
                        "source": source,
                    },
                )
            except Exception as e:
                logger.debug("Failed to store user message in soul: %s", e)

        # Build full messages list: dynamically-built system prompt + history
        messages = [ChatMessage(role="system", content=self._system_prompt)] + self._history

        try:
            reply_msg = self._chat.chat(messages)
        except Exception as e:
            logger.error("ConversationManager.send_message error: %s", e)
            reply_msg = ChatMessage(role="assistant", content="I'm sorry, sir. I encountered an error processing your request.")

        self._history.append(reply_msg)
        self._last_model = self._chat._model or "meta/llama-3.1-8b-instruct"

        # Store reply in soul memory with source tag
        if self._soul is not None:
            try:
                source = "voice" if voice else "chat"
                self._soul.remember(
                    f"I responded: {reply_msg.content[:500]}",
                    memory_type="episodic",
                    importance=0.5,
                    metadata={
                        "session": self.session_id,
                        "role": "assistant",
                        "source": source,
                    },
                )
            except Exception as e:
                logger.debug("Failed to store assistant reply in soul: %s", e)

        # Auto-reflection every N interactions
        if (
            self._soul is not None
            and self._interaction_count % _SOUL_AUTO_REFLECT_INTERVAL == 0
        ):
            try:
                insights = self._soul.reflect()
                if insights.get("insights"):
                    logger.info(
                        "Auto-reflection: %d insights from soul '%s'",
                        len(insights["insights"]), self._soul_name,
                    )
            except Exception as e:
                logger.debug("Auto-reflection failed: %s", e)

        # Optional TTS audio generation
        audio_b64: Optional[str] = None
        if voice and reply_msg.content:
            audio_b64 = self._generate_audio(reply_msg.content)

        elapsed = round(time.time() - t0, 2)
        return {
            "response": reply_msg.content,
            "model": self._last_model,
            "tool_calls": [],
            "audio": audio_b64,
            "elapsed": elapsed,
            "history_length": len(self._history),
        }

    def store_to_memory(self, user_text: str, assistant_reply: str) -> None:
        """Store a (user, assistant) pair in short-term memory."""
        self._memory.append({"user": user_text, "assistant": assistant_reply})
        # Keep only the last 20 pairs to prevent unbounded growth
        if len(self._memory) > 20:
            self._memory = self._memory[-20:]

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 50) -> List[Dict[str, str]]:
        """Return recent history as a list of dicts for API responses."""
        recent = self._history[-limit:]
        return [{"role": m.role, "content": m.content} for m in recent]

    def clear_history(self) -> None:
        """Clear conversation history (keeps memory intact)."""
        self._history.clear()
        logger.info("Conversation history cleared for session: %s", self.session_id)

    # ------------------------------------------------------------------
    # Status & health
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a status dict for the /v1/chat/status endpoint."""
        # Check service availability
        tts_ok = False
        try:
            from openjarvis.engine.tts import TTSEngine
            tts_ok = TTSEngine().is_available()
        except Exception:
            pass

        return {
            "session_id": self.session_id,
            "message_count": len(self._history),
            "duration_seconds": round(time.time() - self._created_at, 1),
            "services": {
                "chat_engine": True,
                "tts": tts_ok,
                "memory": True,
            },
            "tools": [
                "browser_navigate",
                "browser_click",
                "browser_type",
                "browser_screenshot",
                "web_search",
                "shell_exec",
                "file_read",
                "code_interpreter",
                "launch_app",
                "list_apps",
            ],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_audio(self, text: str) -> Optional[str]:
        """Synthesize TTS audio and return base64-encoded bytes, or None."""
        try:
            from openjarvis.engine.tts import TTSEngine
            tts = TTSEngine()
            audio_bytes = tts.speak(text[:400])  # cap to avoid very long TTS
            if audio_bytes:
                return base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            logger.warning("TTS audio generation failed: %s", e)
        return None
