#!/usr/bin/env python3
"""
J.A.R.V.I.S. Background Clap Detector.
Listens for a physical clap to wake up the voice assistant, utilizing
ambient noise level calibration and cooldown periods to prevent self-echoing.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class ClapDetector:
    """Always-on physical clap detector utilizing rolling ambient noise calibration."""

    def __init__(
        self,
        on_clap: Callable[[], None],
        device: Optional[int] = None,
    ) -> None:
        self.on_clap = on_clap
        self.device = device
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Configuration parameters
        self.SAMPLE_RATE = 16000
        self.BLOCK_SIZE = 1024
        self.THRESHOLD_RATIO = 8.0
        self.COOLDOWN_SECONDS = 3.0

        # State coordinates
        self.ambient_energy = 0.05
        self.last_trigger_time = 0.0
        self.is_warming_up = True

    @property
    def is_available(self) -> bool:
        """Check if audio input hardware is available and accessible."""
        try:
            sd.query_devices(self.device, "input")
            return True
        except Exception:
            return False

    def start(self) -> None:
        """Start the clap detector background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="clap-detector",
            daemon=True,
        )
        self._thread.start()
        logger.info("Clap detector thread started successfully.")

    def stop(self) -> None:
        """Stop the clap detector."""
        self._running = False
        logger.info("Clap detector thread stopped.")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: int) -> None:
        """Processes each incoming audio buffer chunk from the microphone stream."""
        if status:
            logger.debug("Audio callback status warning: %s", status)

        # Calculate root-mean-square energy of the chunk
        energy = np.sqrt(np.mean(indata**2))

        # Smoothly update rolling ambient noise level (leak integration)
        self.ambient_energy = 0.98 * self.ambient_energy + 0.02 * max(energy, 0.001)

        if self.is_warming_up:
            return

        current_time = time.time()

        # Check if peak energy is a sharp spike compared to rolling ambient noise
        if energy > self.THRESHOLD_RATIO * self.ambient_energy:
            if current_time - self.last_trigger_time > self.COOLDOWN_SECONDS:
                self.last_trigger_time = current_time
                logger.info("Physical clap spike detected! Triggering callback...")
                if self.on_clap:
                    try:
                        self.on_clap()
                    except Exception as e:
                        logger.error("Error running clap callback: %s", e)

    def _run(self) -> None:
        """Inner loop for the background audio monitoring session."""
        try:
            self.is_warming_up = True
            with sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=self.SAMPLE_RATE,
                blocksize=self.BLOCK_SIZE,
                callback=self._audio_callback,
            ):
                # Sleep briefly to calibrate ambient noise levels & avoid echo feedback
                time.sleep(1.5)
                self.is_warming_up = False

                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            logger.warning("Clap detection stream encountered background warning: %s", e)
