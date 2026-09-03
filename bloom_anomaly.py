#!/usr/bin/env python3
import math

def compute_anomaly(task, context=None):
    """
    task: dict for a single ledger entry
    context: optional dict with system-level info
    Returns: (score: float, flags: list[str])
    """
    score = 0.0
    flags = []

    status = task.get("status")
    kind = task.get("kind")
    duration = task.get("duration_sec", 0.0)
    exit_code = task.get("exit_code", 0)

    # 1) Hard failures
    if status not in ("COMPLETED", "REPAIRED_AND_COMPLETED"):
        score += 50.0
        flags.append("NON_COMPLETED_STATUS")

    if exit_code != 0:
        score += 40.0
        flags.append("NON_ZERO_EXIT_CODE")

    # 2) Duration anomalies (relative to recent mean, if available)
    if context and "recent_mean_duration" in context:
        mean_dur = max(context["recent_mean_duration"], 0.001)
        ratio = duration / mean_dur
        if ratio > 3.0:
            score += 25.0
            flags.append("DURATION_SPIKE")
        elif ratio < 0.3:
            score += 10.0
            flags.append("DURATION_DIP")
    else:
        # Absolute thresholds as fallback
        if duration > 30.0:
            score += 20.0
            flags.append("LONG_RUNNING_TASK")

    # 3) Kind-specific expectations
    if kind == "DRIFT_AUDIT" and status == "COMPLETED" and exit_code == 0:
        pass

    if kind == "LOG_CLEANUP" and duration > 10.0:
        score += 10.0
        flags.append("SLOW_LOG_CLEANUP")

    # 4) System pressure (queue length, recent failures)
    if context:
        qlen = context.get("queue_length", 0)
        fail_rate = context.get("recent_fail_rate", 0.0)

        if qlen > 10:
            score += 5.0
            flags.append("HIGH_QUEUE_PRESSURE")

        if fail_rate > 0.2:
            score += 15.0
            flags.append("ELEVATED_FAILURE_RATE")

    # Normalize / cap
    score = min(score, 100.0)
    return score, flags
