#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
BACKUP_DIR="$HOME/.bloom_backups/v1.0.0_baseline"
LOG_DIR="$REPO_DIR/logs"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"
cd "$REPO_DIR"

echo "=== STEP 1: PRE-FLIGHT AUDIT AUTOMATION ==="
python3 audit_bloom.py

AUDIT_STATUS=$(python3 -c "import json; print(json.load(open('audit_report.json'))['summary']['status'])")
if [ "$AUDIT_STATUS" != "PASSED_AUDIT" ]; then
    echo "[CRITICAL ABORT] Pre-flight audit status: $AUDIT_STATUS. Operational block active."
    exit 1
fi
echo "[VALIDATED] Pre-flight audit passed. Proceeding to state backup."

echo "=== STEP 2: BASELINE CHECKPOINT BACKUP ==="
cp -f pipeline_freeze.json "$BACKUP_DIR/"
cp -f audit_report.json "$BACKUP_DIR/"
tar -czf "$BACKUP_DIR/git_baseline_$(date +%Y%m%d_%H%M%S).tar.gz" .git/
echo "[BACKUP COMPLETE] Freeze manifest and repository state archived to $BACKUP_DIR."

echo "=== STEP 3: CORE MODEL TRAINING LAUNCH ==="
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TRAIN_LOG="$LOG_DIR/training_$TIMESTAMP.log"

echo "[TRAINING STARTED] Execution output stream logging to $TRAIN_LOG"
python3 bloom_real.py 2>&1 | tee "$TRAIN_LOG"

echo "=== OPERATIONAL PIPELINE COMPLETED ==="
