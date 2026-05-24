#!/usr/bin/env python3
"""Jarvis Voice Assistant — always-on wake word + clap detection.

Usage:
    .venv/bin/python scripts/voice_assistant.py          # Start and listen
    .venv/bin/python scripts/voice_assistant.py --no-clap # Disable clap detection

Say "Hey Jarvis" or clap your hands to activate!
Jarvis will listen, respond, and speak back.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        stream=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis Voice Assistant")
    parser.add_argument(
        "--no-clap",
        action="store_true",
        help="Disable clap detection (only respond to 'Hey Jarvis')",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--wake-threshold",
        type=float,
        default=0.5,
        help="Wake word detection threshold (0.0-1.0, default: 0.5)",
    )
    parser.add_argument(
        "--no-greet",
        action="store_true",
        help="Skip startup greeting",
    )
    args = parser.parse_args()

    setup_logging(args.debug)

    # Ensure src is on path
    sys.path.insert(0, "src")

    from openjarvis.agents.conversation import ConversationManager
    from openjarvis.voice.voice_assistant import VoiceAssistant

    logger = logging.getLogger("voice_assistant")

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║        Jarvis Voice Assistant      ║")
    print("  ║                                          ║")
    print("  ║  Say \"Hey Jarvis\" to activate      ║")
    if not args.no_clap:
        print("  ║  Or clap your hands!                     ║")
    print("  ║                                          ║")
    print("  ║  Press Ctrl+C to stop                    ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    # Create a conversation session with soul integration
    # so voice interactions benefit from persistent memory, persona evolution,
    # and auto-reflection like chat interactions do.
    conversation = ConversationManager(soul_name="default")

    assistant = VoiceAssistant(
        conversation=conversation,
        enable_clap=not args.no_clap,
        wake_threshold=args.wake_threshold,
    )

    if not assistant.tts_available:
        print("  ⚠ WARNING: No TTS engine available!")
        print("    Jarvis won't be able to speak back.")
        print("    Install: .venv/bin/pip install gtts")
        print()

    # Handle graceful shutdown
    shutdown = False

    def _on_signal(sig: int, frame: object) -> None:
        nonlocal shutdown
        if shutdown:
            return
        shutdown = True
        print("\n  Stopping Jarvis voice assistant...")
        assistant.stop()
        print("  Goodbye, sir.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # Start the assistant (the __init__ already loads models)
    success = assistant.start(listen_for_wake=True)
    if not success:
        print("  ✗ Failed to start voice assistant!")
        print("    Check microphone and model availability.")
        sys.exit(1)

    print(f"  ✓ Wake word: {'AVAILABLE' if assistant.wake_available else 'UNAVAILABLE'}")
    print(f"  ✓ Clap detection: {'AVAILABLE' if assistant.clap_available else 'UNAVAILABLE'}")
    print(f"  ✓ TTS engine: {'AVAILABLE' if assistant.tts_available else 'UNAVAILABLE'}")
    print()

    # Keep alive until Ctrl+C
    try:
        while not shutdown:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if not shutdown:
            print("\n  Stopping Jarvis voice assistant...")
            assistant.stop()
            print("  Goodbye, sir.")


if __name__ == "__main__":
    main()
