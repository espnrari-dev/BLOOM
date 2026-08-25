import json
from pathlib import Path

LEDGER_FILE = Path("bloom_ledger.json")

STRESS_TASKS = [
    {
        "id": "STRESS_001",
        "name": "Execute Self-Healing Synthetic Fault Injection Test",
        "command": "python3 -c 'import sys; print(\"[FAULT INJECTED] Simulating runtime error\"); sys.exit(1)'"
    },
    {
        "id": "STRESS_002",
        "name": "Post-Repair State Audit Verification Gate",
        "command": "python3 audit_bloom.py"
    }
]

def inject_stress_queue():
    payload = {
        "active_task": None,
        "queue": STRESS_TASKS,
        "history": []
    }
    LEDGER_FILE.write_text(json.dumps(payload, indent=2))
    print("[STRESS TEST INITIALIZED] Seeded synthetic fault task into bloom_ledger.json")

if __name__ == "__main__":
    inject_stress_queue()
