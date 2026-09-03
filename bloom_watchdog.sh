#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
LOG_FILE="$REPO_DIR/logs/watchdog.log"
mkdir -p "$REPO_DIR/logs"

if ! pgrep -f "bloom_daemon.sh" > /dev/null; then
    echo "[WATCHDOG RECOVERY] Daemon process missing. Relaunching at $(date)" >> "$LOG_FILE"
    nohup "$REPO_DIR/bloom_daemon.sh" > /dev/null 2>&1 &
    echo "[WATCHDOG RECOVERY] Daemon restarted with PID $!" >> "$LOG_FILE"
else
    echo "[WATCHDOG NOMINAL] Daemon verified active at $(date)" >> "$LOG_FILE"
fi
