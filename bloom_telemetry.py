import json
import os
import subprocess
from pathlib import Path

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"
LOG_FILE = REPO_DIR / "logs" / "daemon.log"

def get_daemon_pids():
    try:
        res = subprocess.run(["pgrep", "-f", "bloom_daemon.sh"], capture_output=True, text=True)
        pids = [p.strip() for p in res.stdout.strip().split("\n") if p.strip()]
        return pids
    except Exception:
        return []

def load_ledger():
    if not LEDGER_FILE.exists():
        return {"active_task": None, "queue": [], "history": []}
    try:
        return json.loads(LEDGER_FILE.read_text())
    except Exception:
        return {"active_task": None, "queue": [], "history": []}

def render_dashboard():
    ledger = load_ledger()
    pids = get_daemon_pids()
    daemon_str = f"ONLINE (PID: {', '.join(pids)})" if pids else "OFFLINE"
    
    queue = ledger.get("queue", [])
    history = ledger.get("history", [])
    active = ledger.get("active_task")
    
    total = len(history)
    successes = sum(1 for item in history if item.get("status") in ["COMPLETED", "REPAIRED_AND_COMPLETED"])
    failed = sum(1 for item in history if item.get("status") == "FAILED")
    rate = (successes / total * 100) if total > 0 else 100.0

    print("============================================================")
    print("                BLOOM LIVE TELEMETRY DASHBOARD              ")
    print("============================================================")
    print(f"  DAEMON STATUS  : {daemon_str}")
    print(f"  QUEUE LENGTH   : {len(queue)} pending task(s)")
    print(f"  CURRENT STATE  : {'IDLE' if not active else active.get('id')}")
    print(f"  TOTAL PROCESSED: {total}")
    print(f"  SUCCESS RATE   : {rate:.1f}% (Passed: {successes} | Failed: {failed})")
    print("------------------------------------------------------------")
    print("  RECENT TASK HISTORY (LAST 5):")
    if not history:
        print("    [No historical execution records found]")
    else:
        for item in history[-5:]:
            t = item.get("task", {})
            status = item.get("status", "UNKNOWN")
            print(f"    [{status}] {t.get('id', 'N/A')}: {t.get('name', 'N/A')}")
    print("============================================================")

if __name__ == "__main__":
    render_dashboard()
