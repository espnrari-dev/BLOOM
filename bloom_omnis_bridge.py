"""BLOOM -> OMNIS bridge: garden events become OMNIS events"""
import json, time, requests
from pathlib import Path

OMNIS = "http://127.0.0.1:5000"  # change if your OMNIS is on 8050 / 8000
GARDEN = Path.home() / "BLOOM" / "garden"
GARDEN.mkdir(exist_ok=True)

def post_event(kind, payload):
    try:
        r = requests.post(f"{OMNIS}/api/event", json={
            "source": "BLOOM",
            "kind": kind,
            "payload": payload,
            "ts": time.time()
        }, timeout=2)
        print(f"-> OMNIS {kind} {r.status_code}")
    except Exception as e:
        print(f"OMNIS down? {e}")

# tail petals.jsonl
petals = GARDEN / "petals.jsonl"
dew = GARDEN / "dew.json"
seedling = GARDEN / "seedling.json"

seen = 0
if petals.exists():
    seen = len(petals.read_text().strip().splitlines())

print(f"Bridge watching {petals} (seen {seen}), posting to {OMNIS}")

while True:
    if dew.exists():
        try:
            d = json.loads(dew.read_text())
            post_event("BLOOM_DEW", d)
        except: pass
    if petals.exists():
        lines = petals.read_text().strip().splitlines()
        if len(lines) > seen:
            for line in lines[seen:]:
                try:
                    post_event("BLOOM_PETAL", json.loads(line))
                except: pass
            seen = len(lines)
    time.sleep(2)
