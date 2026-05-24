"""Chat router — /v1/chat endpoints for conversational AI.

Provides:
- POST /v1/chat — send a message, get a response (with optional TTS audio)
- GET  /v1/chat/history — get conversation history
- POST /v1/chat/clear — clear conversation history
- GET  /v1/chat/status — service status and tool listing
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from openjarvis.agents.conversation import ConversationManager
from openjarvis.engine.chat import ChatMessage, ChatEngine
from openjarvis.engine.tts import TTSEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])

# Active sessions — simple in-memory store
_sessions: Dict[str, ConversationManager] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's message")
    session_id: Optional[str] = Field(None, description="Existing session ID (omit for new session)")
    voice: bool = Field(False, description="Generate TTS audio for the response")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    model: str = ""
    tool_calls: List[Dict[str, Any]] = []
    audio: Optional[str] = None
    elapsed: float = 0.0
    history_length: int = 0


class StatusResponse(BaseModel):
    session_id: str
    message_count: int
    duration_seconds: float
    services: Dict[str, bool]
    tools: List[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _get_or_create_session(session_id: Optional[str], system_prompt: Optional[str] = None) -> tuple[str, ConversationManager]:
    """Get an existing session or create a new one."""
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]

    new_id = session_id or uuid4().hex[:12]
    mgr = ConversationManager(session_id=new_id, system_prompt=system_prompt)
    _sessions[new_id] = mgr
    logger.info("Created conversation session: %s", new_id)
    return new_id, mgr


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to Jarvis and get a response.

    Creates a new conversation session if no session_id is provided.
    Set voice=true to get base64-encoded TTS audio in the response.
    """
    session_id, mgr = _get_or_create_session(req.session_id)
    result = mgr.send_message(message=req.message, voice=req.voice)

    return ChatResponse(
        response=result.get("response", ""),
        session_id=session_id,
        model=result.get("model", ""),
        tool_calls=result.get("tool_calls", []),
        audio=result.get("audio"),
        elapsed=result.get("elapsed", 0.0),
        history_length=result.get("history_length", 0),
    )


@router.get("/history")
async def get_history(session_id: str, limit: int = 50):
    """Get conversation history for a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"session_id": session_id, "messages": _sessions[session_id].get_history(limit=limit)}


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat endpoint via SSE.

    Returns a text/event-stream with events:
      - `{"type": "token", "content": "..."}` — Streamed LLM tokens
      - `{"type": "audio", "data": "..."}` — Base64-encoded TTS audio (if voice=true)
      - `{"type": "done", "session_id": "...", "content": "...", "model": "...", "elapsed": 0.0}` — Final event

    Notes:
      - For simple chat (no tool calling), tokens stream immediately for low latency.
      - If the LLM decides to call a tool, the streaming endpoint will:
        1. Stream the initial response
        2. Detect tool_calls, execute them
        3. Stream the final response
      - Falls back gracefully on errors.
    """
    session_id, mgr = _get_or_create_session(req.session_id)
    start_time = time.time()

    async def event_stream():
        nonlocal session_id
        nonlocal start_time

        # Add user message to history
        user_msg = ChatMessage(role="user", content=req.message)
        mgr._history.append(user_msg)

        # Store user message in soul memory
        soul = getattr(mgr, '_soul', None)
        if soul is not None:
            try:
                soul.remember(
                    f"User asked: {req.message[:500]}",
                    memory_type="episodic",
                    importance=0.6,
                    metadata={"session": session_id, "role": "user", "streaming": True},
                )
            except Exception as e:
                logger.debug("Failed to store streaming user msg in soul: %s", e)

        # Build messages with soul-injected system prompt
        stream_messages = [ChatMessage(role="system", content=mgr._system_prompt)] + mgr._history

        chat = ChatEngine()
        full_content = ""

        # ── Phase 1: Stream LLM tokens ──
        try:
            async for token in chat.chat_stream(messages=stream_messages):
                full_content += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            logger.error("Stream error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Stream error: {str(e)}'})}\n\n"
            return

        # ── Add to history ──
        if full_content:
            mgr._history.append(ChatMessage(role="assistant", content=full_content))
            mgr.store_to_memory(req.message, full_content)

            # Store assistant reply in soul memory
            if soul is not None:
                try:
                    soul.remember(
                        f"I responded: {full_content[:500]}",
                        memory_type="episodic",
                        importance=0.5,
                        metadata={"session": session_id, "role": "assistant", "streaming": True},
                    )
                    # Auto-reflection every 5 interactions
                    mgr._interaction_count += 1
                    if mgr._interaction_count % 5 == 0:
                        insights = soul.reflect()
                        if insights.get("insights"):
                            logger.info("Streaming auto-reflection: %d insights", len(insights["insights"]))
                except Exception as e:
                    logger.debug("Failed to store streaming reply in soul: %s", e)

        # ── Generate TTS audio (parallel with text display) ──
        audio_b64 = None
        if req.voice and full_content:
            tts = TTSEngine()
            try:
                import base64
                audio_bytes = tts.speak(full_content[:400])
                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    yield f"data: {json.dumps({'type': 'audio', 'data': audio_b64})}\n\n"
            except Exception as e:
                logger.warning("TTS stream failed: %s", e)

        # ── Final event ──
        elapsed = round(time.time() - start_time, 2)
        done_event = {
            'type': 'done',
            'session_id': session_id,
            'content': full_content,
            'model': chat._model,
            'elapsed': elapsed,
        }
        yield f"data: {json.dumps(done_event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/clear")
async def clear_history(session_id: str):
    """Clear a session's conversation history."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    _sessions[session_id].clear_history()
    return {"status": "ok", "session_id": session_id, "action": "history_cleared"}


@router.get("/status", response_model=StatusResponse)
async def chat_status(session_id: Optional[str] = None):
    """Get service status for a session or the default status."""
    _, mgr = _get_or_create_session(session_id)
    status = mgr.get_status()
    return StatusResponse(
        session_id=status.get("session_id", ""),
        message_count=status.get("message_count", 0),
        duration_seconds=status.get("duration_seconds", 0.0),
        services=status.get("services", {}),
        tools=status.get("tools", []),
    )


@router.post("/reset")
async def reset_session(session_id: str):
    """Reset a conversation session entirely."""
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info("Conversation session reset: %s", session_id)
    return {"status": "ok", "session_id": session_id, "action": "session_reset"}
