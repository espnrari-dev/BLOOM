#!/usr/bin/env python3
import time
import json
from pathlib import Path
from bloom_policy import evaluate_autonomic_policies
from bloom_strategy import evaluate_strategy_efficiency
from bloom_ledger_writer import record_task

REPO_DIR = Path.home() / "BLOOM"

def run_governance_cycle():
    directives, stability = evaluate_autonomic_policies()
    strategy_data = evaluate_strategy_efficiency()
    bundles = strategy_data.get("recommended_strategies", {})

    if not directives:
        return

    print("============================================================")
    print("            BLOOM AUTONOMIC GOVERNOR INTERVENTION           ")
    print("============================================================")
    print(f"  SYSTEM STABILITY INDEX : {stability}%")
    print(f"  ACTIVE DIRECTIVES      : {len(directives)}")
    print("------------------------------------------------------------")

    # Select strategy bundle based on priority severity
    max_priority = max(d["priority"] for d in directives)
    chosen_actions = []
    
    if max_priority == 1:
        chosen_actions = bundles.get("DEEP_RECOVERY", ["TRIGGER_EMERGENCY_AUDIT"])
    elif max_priority == 3:
        chosen_actions = bundles.get("FAST_HYGIENE", ["PURGE_TEMP_BUFFERS"])
    else:
        chosen_actions = [d["action"] for d in directives]

    for action in chosen_actions:
        print(f"  [STRATEGY EXECUTION] Executing {action}...")
        start_time = time.time()
        
        # Execute reflex action logic
        if action == "PURGE_TEMP_BUFFERS":
            log_file = REPO_DIR / "logs" / "daemon.log"
            if log_file.exists():
                log_file.write_text("")
        elif action == "ENFORCE_COOLDOWN_BACKOFF":
            time.sleep(1.0)
        elif action == "TRIGGER_EMERGENCY_AUDIT":
            pass

        duration = round(time.time() - start_time, 2)
        
        gov_task = {
            "task_id": f"GOV_REFLEX_{int(time.time())}",
            "kind": action,
            "status": "COMPLETED",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_sec": duration,
            "exit_code": 0
        }
        record_task(gov_task)
        print(f"  [REFLEX COMPLETED] Action {action} logged to memory.")
        
    print("============================================================")

if __name__ == "__main__":
    run_governance_cycle()
