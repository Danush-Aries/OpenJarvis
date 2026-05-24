"""Voice assistant — always-on wake word + clap detection with full voice loop.

Orchestrates:
  1. "Hey Jarvis" (or clap) triggers listening
  2. Mutes wake detection while Jarvis speaks (prevents self-triggering)
  3. Records speech from microphone
  4. Transcribes via local Whisper STT (free, offline)
  5. Sends to ConversationManager (tools, memory, context)
  6. Speaks response aloud via Piper TTS (JARVIS voice)
  7. Barge-in: "Hey Jarvis" while speaking interrupts and starts fresh
  8. Returns to listening mode

Designed to run as a background daemon.
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from typing import Optional

import numpy as np

from openjarvis.agents.conversation import ConversationManager
from openjarvis.engine.chat import ChatEngine, ChatMessage
from openjarvis.engine.tts import TTSEngine
from openjarvis.voice.local_stt import LocalSTT
from openjarvis.voice.wake_word import WakeWordListener
from openjarvis.voice.clap_detector import ClapDetector
from openjarvis.voice.speech_style import preprocess_for_speech, adjust_for_emotion


# Module-level singleton so the Whisper model is loaded once, not per voice cycle
_STT: LocalSTT | None = None


def _get_stt() -> LocalSTT:
    global _STT
    if _STT is None:
        _STT = LocalSTT()
    _STT.ensure_model()
    return _STT


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LISTEN_SAMPLE_RATE = 16000
_LISTEN_CHANNELS = 1
_LISTEN_DTYPE = np.int16
_MAX_RECORD_SECONDS = 15        # Max recording length per query
_LISTEN_TIMEOUT_SILENCE = 2.5   # Seconds of silence before auto-stopping
_SILENCE_RMS_THRESHOLD = 0.005  # RMS below this = silence (lowered for quiet mics)

# Wake responses — spoken acknowledgment before listening
# Neutral ack phrases — used when mood is calm/neutral
_ACK_PHRASES = [
    "Listening, sir.",
    "Yes, sir?",
    "At your service.",
    "Go ahead.",
    "I'm listening.",
]

# Warmer ack phrases — used when mood is positive
_ACK_PHRASES_WARM = [
    "Right away, sir.",
    "At your service.",
    "Yes, sir. Ready when you are.",
    "Listening intently.",
    "Go ahead, sir.",
]

# Direct ack phrases — used when frustration is high
_ACK_PHRASES_DIRECT = [
    "Yes.",
    "Go ahead.",
    "I'm listening.",
    "Proceed.",
]

# Barge-in cooldown — prevent rapid re-triggering during interruption
_BARGE_IN_COOLDOWN = 0.5


# ---------------------------------------------------------------------------
# Voice Assistant
# ---------------------------------------------------------------------------


class VoiceAssistant:
    """Always-on voice assistant that responds to "Hey Jarvis" and claps.

    Usage::

        assistant = VoiceAssistant()
        assistant.start()  # Background thread, non-blocking
        # ...
        assistant.stop()

    Key features:
    - Wake word / clap detection
    - Mutes detection while speaking (prevents echo loop)
    - Barge-in: say "Hey Jarvis" while speaking to cancel and re-listen
    - Startup chime sequence
    - ConversationManager integration for tools, memory, and context
    """

    def __init__(
        self,
        conversation: Optional[ConversationManager] = None,
        chat_engine: Optional[ChatEngine] = None,
        tts_engine: Optional[TTSEngine] = None,
        enable_clap: bool = True,
        wake_threshold: float = 0.5,
        device: Optional[int] = None,
    ) -> None:
        # Use ConversationManager (handles tools, memory, TTS) or fall back to raw ChatEngine
        self._conversation = conversation
        self._chat = chat_engine or ChatEngine()
        self._tts = tts_engine or TTSEngine()
        self._device = device

        self._audio_queue: queue.Queue = queue.Queue()

        # State
        self._running = False
        self._is_speaking = False
        self._is_listening = threading.Event()
        self._barge_in_requested = threading.Event()

        # Track when assistant was last active (to debounce wake triggers
        # while TTS is playing)
        self._last_turn_end = 0.0
        self._wake_cooldown = 2.0

        # Build wake word listener — pass a mute-aware reference
        self._wake = WakeWordListener(
            on_detection=self._on_wake_detected,
            threshold=wake_threshold,
            device=device,
        )

        # Build clap detector (optional)
        self._clap: Optional[ClapDetector] = None
        if enable_clap:
            self._clap = ClapDetector(
                on_clap=self._on_clap_detected,
                device=device,
            )

        # Thread for processing the voice loop (separate from mic capture)
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def wake_available(self) -> bool:
        return self._wake.is_available

    @property
    def clap_available(self) -> bool:
        return bool(self._clap and self._clap.is_available)

    @property
    def tts_available(self) -> bool:
        return self._tts.is_available()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, listen_for_wake: bool = True) -> bool:
        """Start the voice assistant.

        Args:
            listen_for_wake: If True, starts background wake word + clap
                             detection immediately. If False, you must call
                             trigger() manually.

        Returns:
            True if at least the assistant loop started.
        """
        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(
            target=self._assistant_loop,
            name="voice-assistant",
            daemon=True,
        )
        self._thread.start()

        if listen_for_wake:
            self._wake.start()
            if self._clap:
                self._clap.start()

        logger.info(
            "Voice assistant started (wake: %s, clap: %s, tts: %s)",
            self._wake.is_available,
            self.clap_available,
            self.tts_available,
        )

        # Play startup chime sequence
        self._play_startup_chime()
        return True

    def stop(self) -> None:
        """Stop the voice assistant and all listeners.

        Also closes the conversation session so the soul persists
        session summaries and emotional state.
        """
        self._running = False

        # Unmute wake word so it can be stopped cleanly
        self._wake.muted = False
        self._wake.stop()

        if self._clap:
            self._clap.stop()

        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        # Close conversation session (ends soul session, persists data)
        if self._conversation is not None:
            try:
                self._conversation.close()
            except Exception as e:
                logger.warning("Failed to close conversation: %s", e)

        logger.info("Voice assistant stopped")

    # ------------------------------------------------------------------
    # Startup Chime
    # ------------------------------------------------------------------

    def _play_startup_chime(self) -> None:
        """Play a startup chime sequence — arc reactor power-on sound.

        Three ascending tones: Jarvis initializing, loading systems,
        and coming online. Uses Piper TTS with short synthesized tones.
        """
        def _play_tone(text: str, delay: float = 0.5) -> None:
            """Play a short TTS tone after a delay."""
            time.sleep(delay)
            try:
                self._tts.speak_and_play(text)
            except Exception:
                pass

        # Spawn the chime sequence in a background thread so startup
        # returns immediately
        def _chime_sequence() -> None:
            try:
                # Phase 1: System initialization (short click/chirp)
                self._wake.muted = True  # Don't hear our own startup
                self._is_speaking = True

                # Short power-on tones using TTS with very short phrases
                # This creates a natural "system powering up" feel
                _play_tone("Initializing.", 0.3)

                # Phase 2: Loading systems
                _play_tone("Systems loading.", 0.6)

                # Phase 3: Online — "Jarvis online"
                _play_tone("Jarvis online and listening.", 0.8)

                logger.info("Startup chime sequence complete")
            except Exception as e:
                logger.debug("Startup chime skipped: %s", e)
            finally:
                self._is_speaking = False
                self._wake.muted = False

        threading.Thread(target=_chime_sequence, name="startup-chime", daemon=True).start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger(self) -> None:
        """Manually trigger the assistant (e.g., from a keybind or button)."""
        self._start_listen_cycle()

    def wake_on(self) -> None:
        """Enable wake word detection."""
        self._wake.start()
        if self._clap:
            self._clap.start()
        logger.info("Wake word + clap detection enabled")

    def wake_off(self) -> None:
        """Disable wake word detection (still works via manual trigger)."""
        self._wake.stop()
        if self._clap:
            self._clap.stop()
        logger.info("Wake word + clap detection disabled")

    def set_volume(self, volume: float) -> None:
        """Set TTS volume (0.0 to 1.0). Depends on playback backend support."""
        pass

    # ------------------------------------------------------------------
    # Callbacks (from wake word / clap detectors)
    # ------------------------------------------------------------------

    def _on_wake_detected(self) -> None:
        """Called when "Hey Jarvis" is heard.

        If Jarvis is currently speaking, this triggers barge-in:
        the current speech is interrupted and a fresh listen cycle starts.
        """
        if self._is_speaking:
            # Barge-in! Interrupt current speech and start fresh
            logger.info("Wake word detected while speaking — barge-in!")
            self._barge_in_requested.set()
            return

        logger.info("Wake word detected — starting listen cycle")
        self._start_listen_cycle()

    def _on_clap_detected(self) -> None:
        """Called when a hand clap is heard."""
        if self._is_speaking:
            # Barge-in for claps too
            logger.info("Clap detected while speaking — barge-in!")
            self._barge_in_requested.set()
            return

        logger.info("Clap detected — starting listen cycle")
        self._start_listen_cycle()

    # ------------------------------------------------------------------
    # Listen → Transcribe → LLM → TTS cycle
    # ------------------------------------------------------------------

    def _start_listen_cycle(self) -> None:
        """Start a full voice interaction cycle.

        Runs in a separate thread to avoid blocking the audio listener.
        Handles barge-in by canceling any in-progress cycle.
        """
        if self._barge_in_requested.is_set():
            # Already barge-in requested, ignore duplicate
            return

        now = time.time()
        if now - self._last_turn_end < self._wake_cooldown and not self._is_speaking:
            # Still in cooldown (e.g., TTS just finished)
            return

        self._is_listening.set()
        threading.Thread(
            target=self._run_cycle,
            name="voice-cycle",
            daemon=True,
        ).start()

    def _run_cycle(self) -> None:
        """Execute one full voice interaction cycle.

        Handles:
        1. Mute wake detection while speaking
        2. Barge-in interruption
        3. Transcription → LLM → TTS pipeline
        4. Conversation memory persistence
        """
        # Get emotional context for mood-aware adaptation
        emotional_context = None
        if self._conversation is not None and self._conversation._soul is not None:
            try:
                emotional_context = self._conversation._soul.get_emotional_context()
            except Exception:
                pass

        try:
            # Mute wake detection so we don't hear our own voice
            self._wake.muted = True

            # 1. Play acknowledgement — mood-aware phrasing
            ack = self._select_ack_phrase(emotional_context)
            self._is_speaking = True
            threading.Thread(
                target=self._speak,
                args=(ack,),
                kwargs={"allow_interrupt": True},
                name="ack-phrase",
                daemon=True,
            ).start()
            # Brief pause so the ack tone has started playing before we listen
            time.sleep(0.15)

            # Check for barge-in after ack
            if self._barge_in_requested.is_set():
                self._barge_in_requested.clear()
                logger.debug("Barge-in after ack, returning to idle")
                return

            # 2. Listen for speech (mic is open while ack is still playing)
            audio_data = self._record_audio()
            if audio_data is None or len(audio_data) == 0:
                logger.info("No audio recorded (mic issue or all silence), returning to idle")
                return

            # Check for barge-in during recording
            if self._barge_in_requested.is_set():
                self._barge_in_requested.clear()
                return

            # 3. Transcribe
            text = self._transcribe(audio_data)
            if not text or not text.strip():
                logger.info("Empty transcription (VAD filtered all audio or silence) — returning to idle")
                # Still speak a small prompt so the user knows Jarvis heard them
                self._speak("I didn't catch that. Could you repeat?", allow_interrupt=False)
                return

            logger.info("User said: %s", text)

            # 4. Send to LLM with tools via ConversationManager
            if self._conversation:
                result = self._conversation.send_message(text, voice=False)
                reply = result.get("response", "") or "I'm sorry, I couldn't process that."

                # Store conversation to memory (knowledge graph)
                self._conversation.store_to_memory(text, reply)

                # Refresh emotional context after interaction
                if self._conversation._soul is not None:
                    try:
                        emotional_context = self._conversation._soul.get_emotional_context()
                    except Exception:
                        pass
            elif self._chat:
                response = self._chat.chat(
                    messages=[ChatMessage(role="user", content=text)]
                )
                reply = response.content or "I'm sorry, I couldn't process that."
            else:
                reply = "I'm sorry, I couldn't process that."

            logger.info("Jarvis responds: %s", reply[:80])

            # 5. Preprocess reply for speech with emotional context
            reply = preprocess_for_speech(reply)
            reply = adjust_for_emotion(reply, emotional_context)

            # Check for barge-in before speaking
            if self._barge_in_requested.is_set():
                self._barge_in_requested.clear()
                return

            # 6. Speak response (with allow_interrupt for ongoing barge-in)
            self._speak(reply, allow_interrupt=True)

            # Final barge-in check after speaking
            if self._barge_in_requested.is_set():
                self._barge_in_requested.clear()

        except Exception as e:
            logger.error("Voice cycle error: %s", e)
            self._speak("I encountered an error. Please try again.")
        finally:
            self._is_listening.clear()
            self._last_turn_end = time.time()
            self._wake.muted = False  # Re-enable wake detection

    # ------------------------------------------------------------------
    # Audio recording + STT
    # ------------------------------------------------------------------

    def _record_audio(self) -> Optional[np.ndarray]:
        """Record audio from mic until silence or timeout.

        Returns numpy array of int16 audio data, or None on error.
        Checks for barge-in periodically during recording.
        """
        try:
            import sounddevice as sd_rec  # fmt: skip

            audio_chunks: list[np.ndarray] = []
            silence_frames = 0
            silence_limit = int(_LISTEN_TIMEOUT_SILENCE * _LISTEN_SAMPLE_RATE / 1024)
            max_frames = int(_MAX_RECORD_SECONDS * _LISTEN_SAMPLE_RATE / 1024)
            frames = 0

            # Give a moment for the acknowledgement sound to finish
            time.sleep(0.3)

            with sd_rec.InputStream(
                device=self._device,
                samplerate=_LISTEN_SAMPLE_RATE,
                channels=_LISTEN_CHANNELS,
                dtype=np.float32,
                blocksize=1024,
            ) as stream:
                while frames < max_frames:
                    # Check for barge-in periodically
                    if self._barge_in_requested.is_set():
                        return None

                    chunk, _ = stream.read(1024)
                    frames += 1

                    # Calculate RMS
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    audio_chunks.append((chunk * 32767).astype(np.int16))

                    if rms < _SILENCE_RMS_THRESHOLD:
                        silence_frames += 1
                    else:
                        silence_frames = 0

                    if silence_frames >= silence_limit and len(audio_chunks) > silence_limit:
                        break

            if not audio_chunks:
                return None

            return np.concatenate(audio_chunks)

        except Exception as e:
            logger.error("Recording failed: %s", e)
            return None

    def _transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe audio to text using local Whisper STT (free, no API key).

        Uses faster-whisper locally for private, offline speech recognition.
        Falls back to Google Speech Recognition if Whisper is not installed.
        """
        stt = _get_stt()
        text = stt.transcribe_audio(audio_data)
        if text:
            logger.debug("Whisper STT: %s", text[:60])
            return text

        logger.debug("Whisper STT returned empty, falling back to Google STT")

        # Fallback to Google Speech Recognition
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            import io
            import wave

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(_LISTEN_SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())
            buf.seek(0)

            with sr.AudioFile(buf) as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio)
                return text

        except ImportError:
            logger.warning("SpeechRecognition not installed, no STT available")
            return ""
        except sr.UnknownValueError:
            logger.debug("Speech not understood")
            return ""
        except sr.RequestError as e:
            logger.warning("Google STT request failed: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Mood-aware helpers
    # ------------------------------------------------------------------

    def _select_ack_phrase(self, emotional_context=None) -> str:
        """Select an acknowledgment phrase based on emotional state.

        - High frustration: direct, clipped acknowledgments
        - Positive mood: warm, enthusiastic phrases
        - Default: neutral professional phrases
        """
        if emotional_context:
            frustration = emotional_context.get("frustration", 0.0)
            mood = emotional_context.get("mood", "neutral")

            if frustration > 0.5:
                return random.choice(_ACK_PHRASES_DIRECT)
            if mood in ("happy", "excited"):
                return random.choice(_ACK_PHRASES_WARM)

        return random.choice(_ACK_PHRASES)

    # ------------------------------------------------------------------
    # TTS helpers
    # ------------------------------------------------------------------

    def _speak(self, text: str, allow_interrupt: bool = False) -> None:
        """Speak text via TTS.

        Args:
            text: Text to speak.
            allow_interrupt: If True, checks for barge-in requests during
                             playback and cancels early if interrupted.
        """
        self._is_speaking = True
        try:
            if allow_interrupt:
                self._speak_with_interrupt(text)
            else:
                self._tts.speak_and_play(text)
        except Exception as e:
            logger.error("TTS playback failed: %s", e)
        finally:
            self._is_speaking = False

    def _speak_with_interrupt(self, text: str) -> None:
        """Speak text but allow barge-in interruption.

        Plays audio via TTS, but checks for barge-in flag.
        If interrupted, stops playback early.
        """
        audio = self._tts.speak(text)
        if audio is None:
            return

        try:
            import subprocess
            import os
            import tempfile

            # Use the correct suffix based on the actual audio format
            content_type = self._tts.get_last_content_type()
            suffix = ".wav" if content_type == "audio/wav" else ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(audio)
            tmp_path = tmp.name
            tmp.close()

            try:
                # Build player candidates in priority order based on format
                if content_type == "audio/mpeg":
                    # MP3 — ffplay handles it best; paplay expects WAV/PCM
                    player_candidates: list[list[str]] = [
                        ["ffplay", "-nodisp", "-autoexit", tmp_path],
                        ["paplay", tmp_path],
                        ["aplay", tmp_path],
                    ]
                else:
                    # WAV — paplay is the native PulseAudio player
                    player_candidates = [
                        ["paplay", tmp_path],
                        ["ffplay", "-nodisp", "-autoexit", tmp_path],
                        ["aplay", tmp_path],
                    ]

                played = False
                for player in player_candidates:
                    try:
                        proc = subprocess.Popen(player, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                        # Wait while playing, checking for barge-in
                        while proc.poll() is None:
                            if self._barge_in_requested.is_set():
                                proc.terminate()
                                try:
                                    proc.wait(timeout=1.0)
                                except subprocess.TimeoutExpired:
                                    proc.kill()
                                logger.debug("TTS interrupted by barge-in")
                                return
                            time.sleep(0.05)

                        # Playback completed. Check if it succeeded
                        if proc.returncode == 0:
                            played = True
                            break
                        else:
                            logger.warning("Player %s failed with exit code %d", player[0], proc.returncode)
                    except FileNotFoundError:
                        continue

                if not played:
                    logger.warning(
                        "No audio player available to play TTS output "
                        "(tried paplay, ffplay, aplay)"
                    )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            logger.error("Interruptible playback failed: %s", e)

    # ------------------------------------------------------------------
    # Background assistant loop (health check)
    # ------------------------------------------------------------------

    def _assistant_loop(self) -> None:
        """Background loop that keeps the assistant alive."""
        while self._running:
            time.sleep(5.0)
            # Could add periodic health checks, reconnection logic, etc.
