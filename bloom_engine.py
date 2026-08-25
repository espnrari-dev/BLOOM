import json
import time
import subprocess
from pathlib import Path
from bloom_repair import trigger_auto_repair

LEDGER_PATH = Path("bloom_ledger.json")

def init_ledger():
    if not LEDGER_PATH.exists():
        LEDGER_PATH.write_text(json.dumps({"active_task": None, "queue": [], "history": []}, indent=2))

def read_ledger():
    init_ledger()
    return json.loads(LEDGER_PATH.read_text())

def write_ledger(data):
    LEDGER_PATH.write_text(json.dumps(data, indent=2))

def run_step(command):
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def verify_audit():
    res = subprocess.run(["python3", "audit_bloom.py"], capture_output=True, text=True)
    if not Path("audit_report.json").exists():
        return False, "No audit report generated."
    report = json.loads(Path("audit_report.json").read_text())
    status = report.get("summary", {}).get("status")
    return status == "PASSED_AUDIT", f"Audit status: {status}"

def execute_autonomous_loop():
    print("=== BLOOM AUTONOMOUS EXECUTION ENGINE ONLINE ===")
    state = read_ledger()
    
    while state.get("queue"):
        task = state["queue"].pop(0)
        state["active_task"] = task
        write_ledger(state)
        
        print(f"\n[TASK] {task['id']} - {task['name']}")
        code, out, err = run_step(task["command"])
        
        audit_ok, audit_msg = verify_audit()
        
        if code == 0 and audit_ok:
            print(f"[VERIFIED] Task {task['id']} completed successfully.")
            state["history"].append({"task": task, "status": "COMPLETED"})
        else:
            error_details = f"Exit Code: {code}\nStderr: {err}\nAudit: {audit_msg}"
            print(f"[DEFECT DETECTED] {error_details}")
            
            repaired = trigger_auto_repair(error_details)
            if repaired:
                print(f"[RECOVERED] Self-repair successful for task {task['id']}.")
                state["history"].append({"task": task, "status": "REPAIRED_AND_COMPLETED"})
            else:
                print(f"[HALT] Unresolvable defect in task {task['id']}.")
                state["history"].append({"task": task, "status": "FAILED", "log": error_details})
                state["active_task"] = None
                write_ledger(state)
                break
                
        state["active_task"] = None
        write_ledger(state)

    print("\n=== BLOOM AUTONOMOUS EXECUTION COMPLETED ===")

if __name__ == "__main__":
    execute_autonomous_loop()
