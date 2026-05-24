"""Storage — file-based persistence for the Soul system.

Soul data is stored as JSON in ~/.jarvis/souls/<name>/ directory.
Each soul has its own directory with:
- soul.json: Full soul state (identity, memory, persona, dreams)

Write buffering: Writes are batched in-memory and flushed to disk
periodically to reduce I/O overhead on Intel i5 / HDD systems.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.soul.errors import SoulPersistenceError

logger = logging.getLogger(__name__)

# Default base directory
# Allow override via JARVIS_SOUL_DIR env var (useful for testing)
_SOUL_DIR_OVERRIDE = os.environ.get("JARVIS_SOUL_DIR")
DEFAULT_BASE_DIR = Path(_SOUL_DIR_OVERRIDE) if _SOUL_DIR_OVERRIDE else (Path.home() / ".jarvis" / "souls")

# Write buffer defaults
WRITE_BUFFER_SECONDS = 2.0  # Max delay before flushing buffered writes
WRITE_BUFFER_MAX_OPS = 10   # Max buffered writes before forcing flush


class WriteBuffer:
    """In-memory write buffer that batches saves to reduce disk I/O.

    On an Intel i5 with 8GB RAM, every disk write is costly — especially
    for full JSON serialization. This buffer batches updates and flushes
    periodically or when the buffer is full.

    Thread-safe: Uses a lock for concurrent access (e.g., soul.remember()
    called from multiple threads).
    """

    def __init__(
        self,
        flush_fn: Callable[[Dict[str, Any]], None],
        flush_interval: float = WRITE_BUFFER_SECONDS,
        max_ops: int = WRITE_BUFFER_MAX_OPS,
    ) -> None:
        self._flush_fn = flush_fn
        self._flush_interval = flush_interval
        self._max_ops = max_ops
        self._pending: Optional[Dict[str, Any]] = None
        self._op_count = 0
        self._last_flush = 0.0
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def put(self, data: Dict[str, Any]) -> None:
        """Buffer data for batched write."""
        with self._lock:
            self._pending = data
            self._op_count += 1

            if self._op_count >= self._max_ops:
                self._flush_locked()
            elif self._timer is None:
                self._schedule_flush()

    def flush(self) -> None:
        """Force an immediate flush of buffered data."""
        with self._lock:
            self._flush_locked()

    def _schedule_flush(self) -> None:
        """Schedule a delayed flush."""
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._flush_interval, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        """Timer callback — flush if there's pending data."""
        with self._lock:
            self._timer = None
            if self._pending is not None:
                self._flush_locked()

    def _flush_locked(self) -> None:
        """Flush pending data to disk (caller must hold lock)."""
        if self._pending is None:
            return
        try:
            self._flush_fn(self._pending)
            self._pending = None
            self._op_count = 0
            self._last_flush = time.time()
        except (IOError, OSError, PermissionError) as e:
            logger.error("Write buffer flush failed (I/O): %s", e)
            # Don't clear pending — retry on next flush
        except Exception as e:
            logger.exception("Write buffer flush failed (unexpected): %s", e)
            # Don't clear pending — retry on next flush

    def close(self) -> None:
        """Flush remaining data and cancel timers."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.flush()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "pending": self._pending is not None,
                "op_count": self._op_count,
                "last_flush": self._last_flush,
                "buffer_age": time.time() - self._last_flush if self._last_flush > 0 else 0,
            }


class SoulStorage:
    """File-based persistence for a single soul.

    Stores and retrieves soul data from disk as JSON.
    Uses WriteBuffer to batch writes and reduce I/O overhead.

    On Intel i5 with limited RAM, this buffering significantly
    improves performance by avoiding a disk write on every memory store.
    """

    def __init__(
        self,
        name: str,
        base_dir: Optional[Path] = None,
        enable_buffering: bool = True,
    ) -> None:
        self.name = name
        self.base_dir = (base_dir or DEFAULT_BASE_DIR).resolve()
        self.soul_dir = self.base_dir / name
        self.soul_file = self.soul_dir / "soul.json"
        self.backup_dir = self.soul_dir / "backups"

        # Write buffer for batched persistence
        self._buffer = WriteBuffer(
            flush_fn=self._save_sync,
            flush_interval=WRITE_BUFFER_SECONDS,
            max_ops=WRITE_BUFFER_MAX_OPS,
        ) if enable_buffering else None

    # ── Path helpers ──────────────────────────────────────────────────────

    def exists(self) -> bool:
        """Check if a soul file exists on disk."""
        return self.soul_file.exists()

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.soul_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

    # ── Save / Load ───────────────────────────────────────────────────────

    def save(self, data: Dict[str, Any]) -> None:
        """Persist soul data to disk, optionally buffered."""
        if self._buffer is not None:
            self._buffer.put(data)
        else:
            self._save_sync(data)

    def _save_sync(self, data: Dict[str, Any]) -> None:
        """Synchronous write to disk."""
        self.ensure_dirs()

        # Create a backup of the previous state
        if self.soul_file.exists():
            self._backup()

        # Write atomically: write to temp file, then rename
        tmp_path = self.soul_file.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.rename(self.soul_file)
        except (IOError, OSError, PermissionError, json.JSONDecodeError) as e:
            logger.error("Failed to save soul %s: %s", self.name, e)
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
            raise SoulPersistenceError(f"Failed to save soul '{self.name}': {e}") from e

    def load(self) -> Dict[str, Any]:
        """Load soul data from disk, with corruption recovery."""
        if not self.soul_file.exists():
            raise FileNotFoundError(
                f"Soul file not found: {self.soul_file}"
            )

        # Try loading the main file
        try:
            with open(self.soul_file, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "Corrupted soul file %s: %s. Attempting backup recovery...",
                self.soul_file, e,
            )
            # Fall back to the most recent backup
            return self._recover_from_backup()

    def _recover_from_backup(self) -> Dict[str, Any]:
        """Recover soul data from the latest backup."""
        if not self.backup_dir.exists():
            raise RuntimeError(
                f"Soul file corrupted and no backups found: {self.soul_file}"
            )

        backups = sorted(self.backup_dir.glob("soul_*.json"), reverse=True)
        if not backups:
            raise RuntimeError(
                f"Soul file corrupted and no backups found: {self.soul_file}"
            )

        for backup_path in backups:
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                logger.info("Recovered soul %s from backup: %s", self.name, backup_path.name)
                # Restore the backup as the current soul file
                import shutil
                shutil.copy2(backup_path, self.soul_file)
                return data
            except (json.JSONDecodeError, ValueError, OSError):
                logger.warning("Backup also corrupted: %s", backup_path.name)
                continue

        raise RuntimeError(
            f"All backups corrupted for soul: {self.name}"
        )

    # ── Backup ────────────────────────────────────────────────────────────

    def _backup(self) -> None:
        """Create a timestamped backup of the current soul file."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"soul_{timestamp}.json"
        try:
            import shutil
            shutil.copy2(self.soul_file, backup_path)

            # Clean old backups (keep last 10)
            backups = sorted(self.backup_dir.glob("soul_*.json"))
            while len(backups) > 10:
                oldest = backups.pop(0)
                oldest.unlink()
        except (IOError, OSError, PermissionError) as e:
            logger.warning("Failed to backup soul (I/O): %s", e)
        except Exception as e:
            logger.exception("Failed to backup soul (unexpected): %s", e)

    # ── Flush / Close ─────────────────────────────────────────────────────

    def flush(self) -> None:
        """Force flush buffered writes to disk."""
        if self._buffer is not None:
            self._buffer.flush()

    def close(self) -> None:
        """Flush and release resources."""
        if self._buffer is not None:
            self._buffer.close()

    # ── Listing ───────────────────────────────────────────────────────────

    @classmethod
    def list_souls(cls, base_dir: Optional[Path] = None) -> List[str]:
        """List all available soul names."""
        base = (base_dir or DEFAULT_BASE_DIR).resolve()
        if not base.exists():
            return []
        return sorted(
            d.name for d in base.iterdir()
            if d.is_dir() and (d / "soul.json").exists()
        )

    def __repr__(self) -> str:
        return (
            f"SoulStorage(name={self.name!r}, "
            f"path={self.soul_file})"
        )
