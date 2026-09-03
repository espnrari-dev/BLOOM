#!/usr/bin/env python3
import json
from pathlib import Path
from bloom_anomaly import compute_anomaly

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"

def load_ledger():
    if LEDGER_FILE.exists():
        try:
            return json.loads(LEDGER_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_ledger(ledger):
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2))

def get_recent_stats(history, window=20):
    recent = history[-window:]
    if not recent:
        return {"recent_mean_duration": 0.0, "recent_fail_rate": 0.0}

    durations = [h.get("duration_sec", 0.0) for h in recent]
    failures = [1 for h in recent if h.get("status") not in ("COMPLETED", "REPAIRED_AND_COMPLETED")]
    mean_dur = sum(durations) / max(len(durations), 1)
    fail_rate = sum(failures) / max(len(recent), 1)

    return {
        "recent_mean_duration": mean_dur,
        "recent_fail_rate": fail_rate,
    }

def record_task(task_record, queue_length=0):
    ledger = load_ledger()
    history = ledger.get("history", [])

    context = get_recent_stats(history)
    context["queue_length"] = queue_length

    score, flags = compute_anomaly(task_record, context)
    task_record["anomaly_score"] = score
    task_record["anomaly_flags"] = flags

    history.append(task_record)
    ledger["history"] = history
    save_ledger(ledger)
    return task_record

if __name__ == "__main__":
    # Benchmark verification run
    sample_task = {
        "task_id": "DRIFT_AUDIT_1787669165",
        "kind": "DRIFT_AUDIT",
        "status": "COMPLETED",
        "started_at": "2026-08-25T10:40:12",
        "finished_at": "2026-08-25T10:40:13",
        "duration_sec": 1.02,
        "exit_code": 0
    }
    enriched = record_task(sample_task)
    print(f"[ANOMALY ENGINE] Enriched task {enriched['task_id']} | Score: {enriched['anomaly_score']} | Flags: {enriched['anomaly_flags']}")
