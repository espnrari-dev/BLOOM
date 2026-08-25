import json
from pathlib import Path

LEDGER_FILE = Path("bloom_ledger.json")

INITIAL_TASKS = [
    {
        "id": "TASK_001",
        "name": "Audit System Environment and Core Dependencies",
        "command": "python3 audit_bloom.py"
    },
    {
        "id": "TASK_002",
        "name": "Verify Tensor Forward/Backward Pass Integrity",
        "command": "python3 bloom_real.py"
    },
    {
        "id": "TASK_003",
        "name": "Execute Model Checkpoint Archive",
        "command": "tar -czf logs/checkpoint_$(date +%Y%m%d_%H%M%S).tar.gz audit_report.json"
    },
    {
        "id": "TASK_004",
        "name": "Final Forensic Audit Verification Gate",
        "command": "python3 audit_bloom.py"
    }
]

def initialize_queue():
    payload = {
        "active_task": None,
        "queue": INITIAL_TASKS,
        "history": []
    }
    LEDGER_FILE.write_text(json.dumps(payload, indent=2))
    print(f"[LEDGER INITIALIZED] Seeded {len(INITIAL_TASKS)} operational tasks into bloom_ledger.json")

if __name__ == "__main__":
    initialize_queue()
