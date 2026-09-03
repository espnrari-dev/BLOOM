#!/usr/bin/env python3
import json
from pathlib import Path
from bloom_stability import compute_stability_index
from bloom_adaptive import get_adaptive_baselines
import bloom_host

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"

def evaluate_autonomic_policies():
    """
    Evaluates internal execution telemetry + host hardware pressure dynamically.
    """
    directives = []
    stability = compute_stability_index()
    baselines = get_adaptive_baselines()
    host = bloom_host.get_host_telemetry()
    
    ledger = {}
    if LEDGER_FILE.exists():
        try:
            ledger = json.loads(LEDGER_FILE.read_text())
        except Exception:
            pass

    history = ledger.get("history", [])
    recent_task = history[-1] if history else {}
    
    anomaly_trigger = baselines["dynamic_anomaly_threshold"]
    stability_trigger = baselines["dynamic_stability_threshold"]
    
    # Reflex 1: Anomaly Spike Reaction
    if recent_task.get("anomaly_score", 0.0) >= anomaly_trigger:
        directives.append({
            "action": "TRIGGER_EMERGENCY_AUDIT",
            "reason": f"Anomaly score ({recent_task.get('anomaly_score')}) breached dynamic threshold ({anomaly_trigger})",
            "priority": 1
        })

    # Reflex 2: System Stability Recovery
    if stability < stability_trigger:
        directives.append({
            "action": "ENFORCE_COOLDOWN_BACKOFF",
            "reason": f"System stability ({stability}%) fell below target ({stability_trigger}%)",
            "priority": 2
        })

    # Reflex 3: Host RAM Pressure Backoff
    if host.get("ram_usage_pct", 0.0) > 85.0:
        directives.append({
            "action": "ENFORCE_COOLDOWN_BACKOFF",
            "reason": f"Host RAM pressure elevated at {host['ram_usage_pct']}%",
            "priority": 1
        })

    # Reflex 4: Storage Hygiene
    if host.get("disk_usage_pct", 0.0) > 90.0:
        directives.append({
            "action": "PURGE_TEMP_BUFFERS",
            "reason": f"Host storage capacity low ({host['disk_usage_pct']}% utilized)",
            "priority": 2
        })

    return directives, stability

if __name__ == "__main__":
    policies, stability = evaluate_autonomic_policies()
    print(f"[HOST-AWARE POLICY ENGINE] System Stability: {stability}% | Active Directives: {len(policies)}")
    for p in policies:
        print(f"  -> [{p['action']}] (Priority {p['priority']}): {p['reason']}")
