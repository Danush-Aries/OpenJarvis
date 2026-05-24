"""TTSEngine — macOS-native text-to-speech engine for J.A.R.V.I.S.

Uses the built-in macOS `say` command with the Daniel voice for offline,
zero-latency speech synthesis. Falls back gracefully on non-macOS systems.

The `speak()` method returns raw bytes (WAV) so callers can play them
or apply barge-in logic. `speak_and_play()` is a fire-and-forget helper
that plays audio synchronously inline.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Preferred macOS voice — Daniel is the classic British JARVIS voice
_MACOS_VOICE = "Daniel"
_DEFAULT_CONTENT_TYPE = "audio/wav"


class TTSEngine:
    """Offline text-to-speech engine backed by macOS `say`.

    Interface matches what ``VoiceAssistant`` and ``router_chat.py`` expect:
        - ``speak(text) -> Optional[bytes]``       — synthesize and return WAV bytes
        - ``speak_and_play(text)``                  — synthesize and play inline
        - ``is_available() -> bool``                — health check
        - ``get_last_content_type() -> str``        — audio MIME type of last output
    """

    def __init__(self) -> None:
        self._last_content_type: str = _DEFAULT_CONTENT_TYPE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the `say` command is reachable."""
        try:
            result = subprocess.run(
                ["say", "--version"],
                capture_output=True,
                timeout=2,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_last_content_type(self) -> str:
        return self._last_content_type

    def speak(self, text: str) -> Optional[bytes]:
        """Synthesize *text* and return raw audio bytes (AIFF on macOS).

        Returns ``None`` on failure so callers can check before playing.
        """
        clean = self._clean(text)
        if not clean:
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
                tmp_path = tmp.name

            subprocess.run(
                ["say", "-v", _MACOS_VOICE, "-o", tmp_path, clean],
                check=True,
                capture_output=True,
                timeout=30,
            )
            self._last_content_type = "audio/aiff"

            with open(tmp_path, "rb") as f:
                data = f.read()

            return data
        except Exception as e:
            logger.error("TTS synthesis failed: %s", e)
            return None
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

    def speak_and_play(self, text: str) -> None:
        """Synthesize and play *text* immediately (blocking)."""
        clean = self._clean(text)
        if not clean:
            return
        try:
            subprocess.run(
                ["say", "-v", _MACOS_VOICE, clean],
                check=False,
                timeout=60,
            )
        except Exception as e:
            logger.error("TTS speak_and_play failed: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """Strip markdown artefacts that produce awkward speech output."""
        return (
            text.replace("*", "")
                .replace("_", " ")
                .replace("`", "")
                .replace("#", "")
                .strip()
        )
