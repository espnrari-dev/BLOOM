#!/usr/bin/env python3
import json
import statistics
from pathlib import Path

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"

def get_adaptive_baselines(window=50):
    """
    Computes dynamic anomaly thresholds using standard deviation offsets
    from historical execution records.
    """
    default_baselines = {
        "anomaly_mean": 0.0,
        "anomaly_stdev": 0.0,
        "dynamic_anomaly_threshold": 70.0,
        "dynamic_stability_threshold": 70.0,
        "sample_size": 0
    }

    if not LEDGER_FILE.exists():
        return default_baselines

    try:
        ledger = json.loads(LEDGER_FILE.read_text())
    except Exception:
        return default_baselines

    history = ledger.get("history", [])
    if len(history) < 5:
        return default_baselines

    scores = [t.get("anomaly_score", 0.0) for t in history[-window:]]
    mean_score = statistics.mean(scores)
    stdev_score = statistics.stdev(scores) if len(scores) > 1 else 0.0

    # Dynamic Anomaly Trigger: Mean + 2 Standard Deviations (bounded between 40.0 and 85.0)
    dynamic_high = min(max(mean_score + (2 * stdev_score), 40.0), 85.0)
    
    # Dynamic Stability Threshold: Clamped to standard 70.0 baseline or 1.5x mean anomaly offset
    dynamic_stability = max(50.0, 100.0 - (mean_score * 2.5))

    return {
        "anomaly_mean": round(mean_score, 2),
        "anomaly_stdev": round(stdev_score, 2),
        "dynamic_anomaly_threshold": round(dynamic_high, 2),
        "dynamic_stability_threshold": round(dynamic_stability, 2),
        "sample_size": len(scores)
    }

if __name__ == "__main__":
    b = get_adaptive_baselines()
    print("============================================================")
    print("            BLOOM ADAPTIVE BASELINE TELEMETRY               ")
    print("============================================================")
    print(f"  SAMPLES ANALYZED           : {b['sample_size']}")
    print(f"  HISTORICAL ANOMALY MEAN    : {b['anomaly_mean']}")
    print(f"  HISTORICAL ANOMALY STDEV   : {b['anomaly_stdev']}")
    print(f"  DYNAMIC ANOMALY THRESHOLD  : > {b['dynamic_anomaly_threshold']} (μ + 2σ)")
    print(f"  DYNAMIC STABILITY TARGET   : >= {b['dynamic_stability_threshold']}%")
    print("============================================================")
