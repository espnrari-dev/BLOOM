#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
cd "$REPO_DIR"

echo "=== STEP 1: INJECTING SYNTHETIC FAULT INTO TASK LEDGER ==="
python3 bloom_stress_test.py

echo "=== STEP 2: RUNNING ENGINE SELF-HEALING RECOVERY LOOP ==="
python3 bloom_engine.py

echo "=== STEP 3: STRESS TEST AFTER-ACTION REVIEW ==="
python3 -c "
import json
data = json.load(open('bloom_ledger.json'))
history = data.get('history', [])
print(f'Stress Test Summary: {len(history)} tasks processed.')
for item in history:
    t = item['task']
    print(f'  [{item[\"status\"]}] {t[\"id\"]}: {t[\"name\"]}')
"
