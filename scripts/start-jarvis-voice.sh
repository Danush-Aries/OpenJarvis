#!/usr/bin/env bash
#
# start-jarvis-voice.sh — Jarvis Voice Assistant Daemon
#
# Wrapper script that runs the voice assistant in the background with:
#   - Proper PYTHONPATH for the src/ directory
#   - Automatic restart on crash (up to 5 retries, then exponential backoff)
#   - Logging to both stdout and a persistent log file
#   - Graceful shutdown via SIGTERM/SIGINT
#
# Usage:
#   ./scripts/start-jarvis-voice.sh              # Foreground (for testing)
#   ./scripts/start-jarvis-voice.sh --daemon     # Background daemon
#   ./scripts/start-jarvis-voice.sh --stop       # Stop the daemon
#
set -euo pipefail

APP_NAME="jarvis-voice"
PID_FILE="/tmp/${APP_NAME}.pid"
LOG_DIR="${HOME}/OpenJarvis/logs"
LOG_FILE="${LOG_DIR}/voice-assistant.log"
RESTART_MAX=5
RESTART_DELAY=2       # seconds, doubles each retry (2, 4, 8, 16, 32)

# ── Resolve project root (handle symlinks, relative paths) ─────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Ensure log directory exists ───────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Python environment ────────────────────────────────────────────
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "❌ Python not found at ${PYTHON}"
    echo "   Run: uv sync"
    exit 1
fi

export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

# ── Helpers ───────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
    echo "$*"
}

# ── PID cleanup (only used in daemon mode) ───────────────────────
cleanup() {
    if [ -f "$PID_FILE" ]; then
        local old_pid
        old_pid=$(cat "$PID_FILE")
        if kill -0 "$old_pid" 2>/dev/null; then
            log "Stopping ${APP_NAME} (PID ${old_pid})..."
            kill "$old_pid" 2>/dev/null || true
            # Wait for graceful shutdown
            for i in $(seq 1 5); do
                if ! kill -0 "$old_pid" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            # Force kill if still alive
            kill -9 "$old_pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi
    log "${APP_NAME} stopped."
}

# ── Stop ──────────────────────────────────────────────────────────
if [ "${1:-}" = "--stop" ]; then
    cleanup
    exit 0
fi

# ── Daemon mode ───────────────────────────────────────────────────
if [ "${1:-}" = "--daemon" ]; then
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        local old_pid
        old_pid=$(cat "$PID_FILE")
        if kill -0 "$old_pid" 2>/dev/null; then
            log "⚠  ${APP_NAME} is already running (PID ${old_pid}). Use --stop first."
            exit 1
        fi
        rm -f "$PID_FILE"
    fi

    # Fork into background
    nohup "$0" --_daemonized >> "$LOG_FILE" 2>&1 &
    local daemon_pid=$!
    echo "$daemon_pid" > "$PID_FILE"
    log "✅ ${APP_NAME} started in background (PID ${daemon_pid})"
    log "   Logs: ${LOG_FILE}"
    log "   Monitor: journalctl --user -u jarvis-voice -f"
    exit 0
fi

# ── Inner daemon loop (called internally) ─────────────────────────
if [ "${1:-}" = "--_daemonized" ]; then
    # Write PID
    echo $$ > "$PID_FILE"

    RESTART_COUNT=0
    CURRENT_DELAY=$RESTART_DELAY

    while true; do
        log "Starting Jarvis Voice Assistant..."
        log "  Python: ${PYTHON}"
        log "  PYTHONPATH: ${PYTHONPATH}"
        log "  Args: ${*:2}"

        # Run the voice assistant (captures stderr separately)
        if "${PYTHON}" "${PROJECT_ROOT}/scripts/voice_assistant.py" \
            --no-greet \
            "${@:2}" 2>> "$LOG_FILE"; then
            # Clean exit (restart normally)
            RESTART_COUNT=0
            CURRENT_DELAY=$RESTART_DELAY
            log "Voice assistant exited cleanly. Restarting..."
        else
            # Crash exit
            RESTART_COUNT=$((RESTART_COUNT + 1))
            if [ "$RESTART_COUNT" -gt "$RESTART_MAX" ]; then
                log "❌ Voice assistant crashed ${RESTART_MAX} times. Giving up."
                log "   Restart manually: ${PROJECT_ROOT}/scripts/start-jarvis-voice.sh"
                exit 1
            fi
            log "⚠  Voice assistant crashed (attempt ${RESTART_COUNT}/${RESTART_MAX})."
            log "   Restarting in ${CURRENT_DELAY}s..."
            sleep "$CURRENT_DELAY"
            CURRENT_DELAY=$((CURRENT_DELAY * 2))
        fi
    done
fi

# ── Foreground mode (default — used by systemd) ────────────────
#
# No PID file or cleanup trap needed here — systemd manages the
# process group lifecycle. The voice assistant handles SIGTERM/
# SIGINT gracefully via its own signal handlers.
#
log "🚀 Jarvis Voice Assistant — Foreground Mode"
log "   Press Ctrl+C to stop"

# Run voice assistant directly
"${PYTHON}" "${PROJECT_ROOT}/scripts/voice_assistant.py" \
    --no-greet \
    "$@"
