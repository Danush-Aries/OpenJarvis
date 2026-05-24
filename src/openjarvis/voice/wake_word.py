"""Wake word listener — continuously monitors microphone for "Hey Jarvis"

Uses openWakeWord with the pre-trained hey_jarvis_v0.1.onnx model.
Runs in a background thread so the main application stays responsive.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np


logger = logging.getLogger(__name__)

# Lazy import for sounddevice — loaded only when needed
# (prevents PortAudio/ALSA native libraries from loading at import time,
#  which causes segfaults during Python interpreter shutdown)
sd = None


def _ensure_sd():
    """Lazily import sounddevice and return the module."""
    global sd
    if sd is None:
        import sounddevice as _sd  # type: ignore[import-untyped]
        sd = _sd
    return sd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000  # openWakeWord requires 16kHz
CHUNK_SIZE = 1280    # 80ms at 16kHz — matches openWakeWord frame size
_THRESHOLD = 0.5     # Detection confidence threshold
_COOLDOWN = 3.0      # Seconds to ignore after a detection (debounce)


# ---------------------------------------------------------------------------
# Wake Word Listener
# ---------------------------------------------------------------------------


class WakeWordListener:
    """Listens for "Hey Jarvis" via the microphone.

    Usage::

        def on_wake():
            print("Wake word detected!")

        listener = WakeWordListener(on_detection=on_wake)
        listener.start()
        # ... do other things ...
        listener.stop()

    The listener runs in a daemon thread so it stops automatically when
    the main program exits.

    Supports muting — when muted, detection is skipped (prevents
    the assistant from hearing its own TTS output).
    """

    def __init__(
        self,
        on_detection: Optional[Callable[[], None]] = None,
        threshold: float = _THRESHOLD,
        cooldown: float = _COOLDOWN,
        device: Optional[int] = None,
    ) -> None:
        self._on_detection = on_detection
        self._threshold = threshold
        self._cooldown = cooldown
        self._device = device

        self._model: Optional[object] = None
        self._stream: Optional[sd.InputStream] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._muted = False  # When true, detection is skipped (hearing own TTS)
        self._last_detection = 0.0
        self._available = False

        # Initialize the openWakeWord model
        self._init_model()

    # ------------------------------------------------------------------
    # Muting (prevents hearing own TTS)
    # ------------------------------------------------------------------

    @property
    def muted(self) -> bool:
        """Whether the listener is muted (skips detection)."""
        return self._muted

    @muted.setter
    def muted(self, value: bool) -> None:
        self._muted = value

    def _init_model(self) -> None:
        """Load the openWakeWord model with the hey_jarvis pre-trained model."""
        try:
            from openwakeword import Model as OWWModel
            self._model = OWWModel()
            self._available = True
            logger.info("WakeWord model loaded: hey_jarvis")
        except Exception as e:
            logger.warning("Failed to load openWakeWord model: %s", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start listening for the wake word in a background thread.

        Returns True if successfully started, False if the model isn't
        available or the mic couldn't be opened.
        """
        if self._running:
            return True
        if not self._available or not self._model:
            logger.error("Cannot start: wake word model not available")
            return False

        try:
            sd_mod = _ensure_sd()
            self._stream = sd_mod.InputStream(
                device=self._device,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.int16,
                blocksize=CHUNK_SIZE,
            )
            self._stream.start()
        except Exception as e:
            logger.error("Failed to open mic stream: %s", e)
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="wake-word-listener",
            daemon=True,
        )
        self._thread.start()
        logger.info("Wake word listener started")
        return True

    def stop(self) -> None:
        """Stop listening for the wake word."""
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Wake word listener stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        """Main loop: read audio chunks and feed them to the model."""
        if not self._model or not self._stream:
            return

        while self._running:
            try:
                # Skip detection while muted (hearing our own TTS output)
                if self._muted:
                    time.sleep(0.05)
                    continue

                chunk, _ = self._stream.read(CHUNK_SIZE)
                # openWakeWord expects 16-bit PCM int16
                chunk_int16 = (chunk * 32767).astype(np.int16) if chunk.dtype == np.float32 else chunk
                chunk_int16 = chunk_int16.flatten()

                predictions = self._model.predict(chunk_int16)
                score = predictions.get("hey_jarvis", 0.0)

                if score > self._threshold:
                    now = time.time()
                    if now - self._last_detection > self._cooldown:
                        self._last_detection = now
                        logger.info("Wake word detected (score: %.3f)", score)
                        if self._on_detection and not self._muted:
                            # Fire in a separate thread to avoid blocking audio
                            threading.Thread(
                                target=self._on_detection,
                                daemon=True,
                            ).start()

            except Exception as e:
                if self._running:
                    logger.debug("Wake word listen error: %s", e)
                    time.sleep(0.1)
