#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
LOG_FILE="$REPO_DIR/logs/daemon.log"
mkdir -p "$REPO_DIR/logs"

echo "[DAEMON INITIALIZED] Starting BLOOM autonomous operational loop at $(date)" >> "$LOG_FILE"

while true; do
    echo "=== DAEMON CYCLE RUN AT $(date) ===" >> "$LOG_FILE"
    # Auto-generate tasks if queue is clear
    python3 "$REPO_DIR/bloom_producer.py" >> "$LOG_FILE" 2>&1 || true
    # Execute pending queue
    python3 "$REPO_DIR/bloom_engine.py" >> "$LOG_FILE" 2>&1 || true
    sleep 30
done
