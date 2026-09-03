#!/usr/bin/env python3
import subprocess
import os
from pathlib import Path

def get_host_telemetry():
    """
    Senses hardware resource pressure directly from the host operating system.
    """
    ram_pct = 0.0
    disk_pct = 0.0

    # 1. Sense RAM Usage
    try:
        res = subprocess.run(["free", "-m"], capture_output=True, text=True)
        lines = res.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            total = float(parts[1])
            used = float(parts[2])
            ram_pct = round((used / total) * 100.0, 2)
    except Exception:
        pass

    # 2. Sense Disk Storage Usage
    try:
        home_path = str(Path.home())
        res = subprocess.run(["df", "-P", home_path], capture_output=True, text=True)
        lines = res.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            disk_pct = float(parts[4].replace('%', ''))
    except Exception:
        pass

    return {
        "ram_usage_pct": ram_pct,
        "disk_usage_pct": disk_pct
    }

if __name__ == "__main__":
    t = get_host_telemetry()
    print("============================================================")
    print("           BLOOM HOST SENSORY ARRAY TELEMETRY               ")
    print("============================================================")
    print(f"  HOST RAM USAGE   : {t['ram_usage_pct']}%")
    print(f"  HOST DISK USAGE  : {t['disk_usage_pct']}%")
    print("============================================================")
