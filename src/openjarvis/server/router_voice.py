"""Voice router — /v1/voice endpoints for text-to-speech.

Provides:
- POST /v1/voice/speak — convert text to speech audio
- GET  /v1/voice/voices — list available TTS voices
- GET  /v1/voice/status — TTS service status
"""

from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openjarvis.engine.tts import TTSEngine
from openjarvis.core.credentials import get_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/voice", tags=["voice"])

# Singleton TTS engine
_tts: Optional[TTSEngine] = None


def _get_tts() -> TTSEngine:
    global _tts
    if _tts is None:
        _tts = TTSEngine()
    return _tts


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Text to speak")
    voice_id: Optional[str] = Field(None, description="Optional voice ID")
    format: str = Field("base64", description="Response format: 'base64', 'wav', or 'url'")


class SpeakResponse(BaseModel):
    status: str
    audio: Optional[str] = None
    format: str = ""
    content_type: str = ""
    chars: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/speak", response_model=SpeakResponse)
async def speak(req: SpeakRequest):
    """Convert text to speech audio.

    Returns base64-encoded WAV audio by default. The TTS engine uses
    Cartesia AI if configured, or returns a simulated response.
    """
    tts = _get_tts()

    if not tts.is_available():
        return SpeakResponse(
            status="unavailable",
            audio=None,
            format="",
            chars=len(req.text),
            message="TTS not available. Install gtts or set CARTESIA_API_KEY.",
        )

    try:
        audio_bytes = tts.speak(req.text, voice_id=req.voice_id)
        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            return SpeakResponse(
                status="ok",
                audio=audio_b64,
                format=req.format,
                content_type=tts.get_last_content_type(),
                chars=len(req.text),
                message="Speech synthesized successfully",
            )
        else:
            return SpeakResponse(
                status="error",
                audio=None,
                format="",
                content_type="",
                chars=len(req.text),
                message="TTS synthesis returned no audio",
            )
    except Exception as e:
        logger.error("TTS speak failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")


@router.get("/voices")
async def list_voices():
    """List available TTS voices."""
    tts = _get_tts()
    return {"voices": tts.list_voices()}


@router.get("/status")
async def voice_status():
    """Get TTS service status."""
    tts = _get_tts()
    creds = get_credentials()

    if creds.tts_available:
        engine = "Cartesia AI (premium)"
        msg = "Ready — premium TTS active"
    elif tts.is_available():
        engine = "gTTS (free)"
        msg = "Ready — free TTS active (gTTS)"
    else:
        engine = "none"
        msg = "Not available. Install gtts or set CARTESIA_API_KEY"

    return {
        "configured": tts.is_available(),
        "engine": engine,
        "message": msg,
    }
