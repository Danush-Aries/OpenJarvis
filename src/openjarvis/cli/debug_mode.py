"""Debug mode utilities for OpenJarvis CLI."""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional


class DebugContext:
    """Context for managing debug mode settings."""

    _instance: Optional[DebugContext] = None
    _enabled: bool = False

    def __new__(cls) -> DebugContext:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, debug: bool = False) -> None:
        """Initialize debug mode from CLI flag or environment variable.

        Args:
            debug: Whether debug mode is explicitly enabled via CLI flag
        """
        # Check environment variable first
        env_debug = os.environ.get("OPENJARVIS_DEBUG", "").lower()
        debug_enabled = debug or env_debug in ("1", "true", "yes", "on")

        cls._enabled = debug_enabled

        if debug_enabled:
            # Enable all debug logging
            logging.getLogger("openjarvis").setLevel(logging.DEBUG)

            # Show debug messages on startup
            import openjarvis

            print(
                f"🔧 Debug mode enabled (OpenJarvis {openjarvis.__version__})",
                file=sys.stderr,
            )

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if debug mode is currently enabled."""
        return cls._enabled

    @classmethod
    def get_debug_info(cls) -> dict:
        """Return diagnostic information for debugging."""
        import platform

        info = {
            "debug_enabled": cls._enabled,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "env_debug": os.environ.get("OPENJARVIS_DEBUG", "not set"),
        }
        return info


def debug_print(message: str, prefix: str = "DEBUG") -> None:
    """Print a debug message to stderr if debug mode is enabled.

    Args:
        message: The message to print
        prefix: The prefix for the message (default: "DEBUG")
    """
    if DebugContext.is_enabled():
        print(f"[{prefix}] {message}", file=sys.stderr)


def debug_log(logger: logging.Logger, message: str, **kwargs) -> None:
    """Log a debug message using the provided logger.

    Args:
        logger: The logger to use
        message: The message to log
        **kwargs: Additional arguments passed to logger.debug()
    """
    if DebugContext.is_enabled():
        logger.debug(message, **kwargs)


__all__ = ["DebugContext", "debug_print", "debug_log"]
