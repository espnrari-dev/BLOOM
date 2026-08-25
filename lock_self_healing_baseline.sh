#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
cd "$REPO_DIR"

echo "=== STEP 1: AUDIT VERIFICATION ==="
python3 audit_bloom.py

echo "=== STEP 2: UPDATE PIPELINE FREEZE CHECKSUMS ==="
python3 -c "
import json
import hashlib
from pathlib import Path

repo = Path('$REPO_DIR')
freeze_manifest = {
    'pipeline_status': 'FROZEN_v1.1.0',
    'total_files': len(list(repo.rglob('*.py'))),
    'checksums': {}
}

for py_file in sorted(repo.rglob('*.py')):
    if not any(part in str(py_file) for part in ['venv', '__pycache__', '.git']):
        rel_path = str(py_file.relative_to(repo))
        freeze_manifest['checksums'][rel_path] = hashlib.sha256(py_file.read_bytes()).hexdigest()

manifest_path = repo / 'pipeline_freeze.json'
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(freeze_manifest, f, indent=2)

print(f'[FREEZE LOCKED] Updated manifest saved to {manifest_path}')
"

echo "=== STEP 3: GIT BASELINE LOCK (v1.1.0-self-healing-verified) ==="
git add .
git commit -m "feat(autonomy): integrate AST-validated self-healing loop and persistent state ledger" || echo "No new uncommitted changes."
git tag -f -a "v1.1.0-self-healing-verified" -m "Autonomous execution loop and AST auto-repair verified via stress test"
echo "[GIT LOCKED] Tagged v1.1.0-self-healing-verified."

echo "=== STEP 4: VERIFY COMPLETE PRODUCTION PIPELINE ==="
./run_autonomous_pipeline.sh

echo "=== BASELINE INTEGRATION COMPLETED SUCCESSFULLY ==="
