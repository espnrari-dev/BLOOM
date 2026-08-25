#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
cd "$REPO_DIR"

echo "=== STEP 1: INITIALIZING AUTONOMOUS TASK LEDGER ==="
python3 bloom_ledger_init.py

echo "=== STEP 2: LAUNCHING CLOSED-LOOP EXECUTION ENGINE ==="
python3 bloom_engine.py

echo "=== STEP 3: AFTER-ACTION REVIEW & STATE REPORTING ==="
python3 -c "
import json
data = json.load(open('bloom_ledger.json'))
history = data.get('history', [])
print(f'Execution Summary: {len(history)} tasks processed.')
for item in history:
    t = item['task']
    print(f'  [{item[\"status\"]}] {t[\"id\"]}: {t[\"name\"]}')
"
