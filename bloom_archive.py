import json
from pathlib import Path

REPO_DIR = Path.home() / "BLOOM"
LEDGER_FILE = REPO_DIR / "bloom_ledger.json"
ARCHIVE_FILE = REPO_DIR / "logs" / "ledger_archive.json"

def prune_and_archive_ledger(max_history=50):
    if not LEDGER_FILE.exists():
        return
    
    try:
        state = json.loads(LEDGER_FILE.read_text())
    except Exception:
        return

    history = state.get("history", [])
    if len(history) <= max_history:
        return

    keep_count = max_history // 2
    to_archive = history[:-keep_count]
    to_keep = history[-keep_count:]

    existing_archive = []
    if ARCHIVE_FILE.exists():
        try:
            existing_archive = json.loads(ARCHIVE_FILE.read_text())
        except Exception:
            existing_archive = []

    existing_archive.extend(to_archive)
    ARCHIVE_FILE.write_text(json.dumps(existing_archive, indent=2))

    state["history"] = to_keep
    LEDGER_FILE.write_text(json.dumps(state, indent=2))
    print(f"[ARCHIVER] Rotated {len(to_archive)} historical records to {ARCHIVE_FILE.name}")

if __name__ == "__main__":
    prune_and_archive_ledger()
