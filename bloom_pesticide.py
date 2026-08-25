"""
BLOOM PESTICIDE - protects all gardens from code bugs
- quarantines corrupted jsonl
- kills runaway petals with NaN/inf
- antivirus same as terminal but for all gardens
"""
import json, shutil
from pathlib import Path

GARDENS = ["garden", "garden_noble", "garden_merged", "garden_hybrid", "garden_term", "garden_live", "garden_noble"]
MALICIOUS = ["rm -rf", ":(){:|:&};:", "mkfs", "dd if=", "shred", "> /dev/sda", "chmod -R 777 /"]

def spray():
    for gname in GARDENS:
        g = Path(gname)
        if not g.exists(): continue
        q = g / "quarantine"
        q.mkdir(exist_ok=True)
        print(f"[PESTICIDE] checking {gname}")
        for f in g.glob("*.json*"):
            try:
                txt = f.read_text()
                # bug 1: malicious
                for pat in MALICIOUS:
                    if pat in txt:
                        print(f"  BUG {pat} in {f.name} -> quarantine")
                        shutil.move(str(f), str(q / f.name))
                        raise StopIteration
                # bug 2: corrupted jsonl / NaN / inf
                if f.suffix == ".jsonl" or "petals" in f.name or "lineage" in f.name:
                    for i, line in enumerate(txt.splitlines()):
                        if not line.strip(): continue
                        obj = json.loads(line)
                        # check NaN inf in any value
                        s = json.dumps(obj)
                        if "NaN" in s or "Infinity" in s or "inf" in s.lower():
                            print(f"  BUG NaN in {f.name}:{i} -> quarantine line")
                            # rewrite without bad line
                            good = [l for l in txt.splitlines() if "NaN" not in l and "Infinity" not in l]
                            f.write_text("\n".join(good))
            except StopIteration:
                continue
            except Exception as e:
                if "quarantine" not in str(e):
                    print(f"  CORRUPT {f.name}: {e} -> quarantine")
                    try: shutil.move(str(f), str(q / f.name))
                    except: pass
    print("[PESTICIDE] clean - bloom protected")

if __name__ == "__main__":
    spray()
