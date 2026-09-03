#!/usr/bin/env python3
import json
from pathlib import Path

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"

def compute_stability_index():
    if not LEDGER_FILE.exists():
        return 100.0

    try:
        ledger = json.loads(LEDGER_FILE.read_text())
    except Exception:
        return 0.0

    history = ledger.get("history", [])
    if not history:
        return 100.0

    recent = history[-20:]
    total = len(recent)
    
    # Weight factors
    failures = sum(1 for t in recent if t.get("status") not in ("COMPLETED", "REPAIRED_AND_COMPLETED"))
    high_anomalies = sum(1 for t in recent if t.get("anomaly_score", 0.0) >= 70.0)
    moderate_anomalies = sum(1 for t in recent if 30.0 <= t.get("anomaly_score", 0.0) < 70.0)
    
    # Penalties
    failure_penalty = (failures / total) * 50.0
    high_anomaly_penalty = (high_anomalies / total) * 35.0
    mod_anomaly_penalty = (moderate_anomalies / total) * 15.0

    stability = max(0.0, 100.0 - (failure_penalty + high_anomaly_penalty + mod_anomaly_penalty))
    return round(stability, 2)

if __name__ == "__main__":
    score = compute_stability_index()
    print(f"[STABILITY ENGINE] Computed System Stability Index: {score}%")
