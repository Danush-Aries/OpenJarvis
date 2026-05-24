"""Local speech-to-text using faster-whisper — free, private, no API key.

Transcribes audio from microphone or WAV bytes using OpenAI's Whisper
model running locally via the faster-whisper (CTranslate2) backend.

Model is downloaded automatically on first use and cached (~1.5GB for
large-v3, ~500MB for base).

Usage:
    stt = LocalSTT(model_size="base")
    text = stt.transcribe_file("/tmp/recording.wav")
    # or with an AudioData object from speech_recognition
    text = stt.transcribe_audio(audio_data)
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default model — "base" is fast and accurate enough for voice commands.
# Use "small" or "medium" for better accuracy (slower).
# Use "large-v3" for best accuracy (needs GPU).
_DEFAULT_MODEL = "base"
_CACHE_DIR = Path.home() / ".cache" / "jarvis" / "whisper"


class LocalSTT:
    """Local speech recognition via faster-whisper.

    Downloads the Whisper model on first use (cached in ~/.cache/jarvis/whisper/).
    Runs entirely on CPU by default — set device="cuda" if you have an NVIDIA GPU.

    Usage:
        stt = LocalSTT(model_size="base")
        text = stt.transcribe_file("speech.wav")
        print(f"Recognized: {text}")
    """

    def __init__(
        self,
        model_size: str = _DEFAULT_MODEL,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None
        self._model_loaded = False

        # Auto-detect device
        if device == "auto":
            try:
                import torch
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"

        # Auto-detect compute type
        if compute_type == "auto":
            self._compute_type = "float16" if self._device == "cuda" else "int8"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Whether faster-whisper is installed."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def model_loaded(self) -> bool:
        return self._model_loaded

    @property
    def model_size(self) -> str:
        return self._model_size

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def ensure_model(self) -> bool:
        """Load the Whisper model if not already loaded.

        Downloads on first use (~500MB for base, ~1.5GB for large-v3).
        Returns True if model is ready.
        """
        if self._model_loaded:
            return True

        if not self.available:
            logger.warning("faster-whisper not installed. Run: pip install faster-whisper")
            return False

        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading Whisper model '%s' (device=%s, compute=%s)...",
                self._model_size, self._device, self._compute_type,
            )
            start = time.time()

            os.makedirs(_CACHE_DIR, exist_ok=True)
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=str(_CACHE_DIR),
            )

            elapsed = time.time() - start
            logger.info("Whisper model loaded in %.1fs", elapsed)
            self._model_loaded = True
            return True

        except Exception as e:
            logger.error("Failed to load Whisper model: %s", e)
            return False

    def unload_model(self) -> None:
        """Unload the model to free memory."""
        self._model = None
        self._model_loaded = False
        import gc
        gc.collect()

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe_file(self, wav_path: str, language: Optional[str] = None) -> str:
        """Transcribe a WAV file to text.

        Args:
            wav_path: Path to a WAV file (16-bit PCM, any sample rate).
            language: Optional language code (e.g., "en"). Auto-detected if None.

        Returns:
            Transcribed text string, or empty string on failure.
        """
        if not self.ensure_model():
            return ""
        if self._model is None:
            return ""

        try:
            start = time.time()
            segments, info = self._model.transcribe(
                wav_path,
                language=language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.3,               # default 0.5 — lower = more sensitive
                    min_silence_duration_ms=300, # default 2000 — cut silence faster
                    speech_pad_ms=200,           # padding around speech
                    min_speech_duration_ms=100,  # catch short words
                ),
            )

            text = " ".join(seg.text for seg in segments)
            elapsed = time.time() - start

            logger.debug(
                "Transcribed %.1fs audio in %.2fs: %s",
                info.duration if hasattr(info, 'duration') else 0,
                elapsed,
                text[:60],
            )
            return text.strip()

        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return ""

    def transcribe_audio(self, audio_data: "AnyAudioData") -> str:
        """Transcribe audio data to text.

        Accepts:
            - numpy int16 array (16kHz expected)
            - numpy float32 array (values in [-1, 1], 16kHz expected)
            - bytes (raw PCM int16, 16kHz expected)

        Args:
            audio_data: Audio samples as numpy array or raw bytes.
                       Must be at 16kHz sample rate (faster-whisper's native rate).

        Returns:
            Transcribed text string, or empty string on failure.
        """
        if not self.ensure_model():
            return ""
        if self._model is None:
            return ""

        try:
            import numpy as np

            # Convert to float32 if needed
            if isinstance(audio_data, bytes):
                samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            elif isinstance(audio_data, np.ndarray):
                if audio_data.dtype == np.int16:
                    samples = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.float32:
                    samples = audio_data
                else:
                    samples = audio_data.astype(np.float32)
            else:
                logger.warning("Unsupported audio data type: %s", type(audio_data).__name__)
                return ""

            # Ensure 1D array
            if samples.ndim > 1:
                samples = samples.mean(axis=1)

            start = time.time()
            segments, info = self._model.transcribe(
                samples,
                beam_size=5,
                language="en",       # force English — avoids mis-detection
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.3,               # lower = more sensitive to quiet voice
                    min_silence_duration_ms=300,
                    speech_pad_ms=200,
                    min_speech_duration_ms=100,  # catch short words like "hey"
                ),
            )

            text = " ".join(seg.text for seg in segments)
            elapsed = time.time() - start

            logger.debug("Transcribed in %.2fs: %s", elapsed, text[:60])
            return text.strip()

        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return ""

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        """Transcribe WAV file bytes to text.

        Resamples audio to 16kHz if needed (faster-whisper's native rate).
        Requires scipy for non-16kHz sample rates; passes raw 16kHz PCM
        directly for the common case.

        Args:
            wav_bytes: Complete WAV file bytes (header + data).

        Returns:
            Transcribed text string, or empty string on failure.
        """
        frames: bytes = b""
        try:
            import wave
            import io
            import numpy as np

            with wave.open(io.BytesIO(wav_bytes)) as wf:
                sample_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            # Resample to 16kHz if needed
            if sample_rate != 16000:
                try:
                    import scipy.signal
                    samples = scipy.signal.resample(
                        samples,
                        int(len(samples) * 16000 / sample_rate),
                    )
                except ImportError:
                    # Without scipy, pass the raw PCM bytes at original sample rate.
                    # The model may handle it, though accuracy may suffer.
                    return self.transcribe_audio(frames)

            return self.transcribe_audio(samples)

        except Exception as e:
            logger.error("WAV bytes transcription failed: %s", e)
            return ""


# Type alias for accepted audio data formats
AnyAudioData = object  # numpy.ndarray | bytes
