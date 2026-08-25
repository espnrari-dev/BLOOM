import json
import time
from pathlib import Path

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"

def generate_cycle_tasks():
    ts = int(time.time())
    return [
        {
            "id": f"DRIFT_AUDIT_{ts}",
            "name": "Automated AST Drift and Code Base Integrity Check",
            "command": "python3 audit_bloom.py"
        },
        {
            "id": f"LOG_CLEANUP_{ts}",
            "name": "Purge Pycache Artifacts and Temporary Buffers",
            "command": "find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
        }
    ]

def inject_tasks():
    if not LEDGER_FILE.exists():
        state = {"active_task": None, "queue": [], "history": []}
    else:
        try:
            state = json.loads(LEDGER_FILE.read_text())
        except Exception:
            state = {"active_task": None, "queue": [], "history": []}
            
    # Avoid overloading queue if tasks are already pending
    if len(state.get("queue", [])) == 0:
        new_tasks = generate_cycle_tasks()
        state["queue"].extend(new_tasks)
        LEDGER_FILE.write_text(json.dumps(state, indent=2))
        print(f"[PRODUCER] Injected {len(new_tasks)} dynamic operational tasks into queue.")
    else:
        print("[PRODUCER] Queue active. Skipping task injection.")

if __name__ == "__main__":
    inject_tasks()
