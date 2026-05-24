"""Voice package — wake word detection, clap detection, and voice assistant."""

from openjarvis.voice.wake_word import WakeWordListener
from openjarvis.voice.clap_detector import ClapDetector
from openjarvis.voice.voice_assistant import VoiceAssistant

__all__ = [
    "WakeWordListener",
    "ClapDetector",
    "VoiceAssistant",
]
