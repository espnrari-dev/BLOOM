#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/BLOOM"
cd "$REPO_DIR"

echo "=== STEP 1: AUDIT VERIFICATION ==="
python3 audit_bloom.py

echo "=== STEP 2: UPDATE FREEZE CHECKSUMS ==="
python3 -c "
import json, hashlib
from pathlib import Path

repo = Path('$REPO_DIR')
freeze_manifest = {
    'pipeline_status': 'FROZEN_v1.2.0',
    'total_files': len(list(repo.rglob('*.py'))),
    'checksums': {}
}

for py_file in sorted(repo.rglob('*.py')):
    if not any(part in str(py_file) for part in ['venv', '__pycache__', '.git']):
        rel_path = str(py_file.relative_to(repo))
        freeze_manifest['checksums'][rel_path] = hashlib.sha256(py_file.read_bytes()).hexdigest()

manifest_path = repo / 'pipeline_freeze.json'
manifest_path.write_text(json.dumps(freeze_manifest, indent=2))
print(f'[FREEZE LOCKED] Updated manifest saved to {manifest_path}')
"

echo "=== STEP 3: GIT COMMIT AND TAG (v1.2.0-dynamic-daemon-verified) ==="
git add .
git commit -m "feat(autonomy): add dynamic task producer, live telemetry dashboard, and ledger archiver" || echo "No changes to commit."
git tag -f -a "v1.2.0-dynamic-daemon-verified" -m "Dynamic producer, live telemetry, and log archiver operational"
echo "[GIT LOCKED] Tagged v1.2.0-dynamic-daemon-verified."

echo "=== STEP 4: VERIFY SYSTEM TELEMETRY ==="
python3 "$REPO_DIR/bloom_telemetry.py"
