#!/usr/bin/env python3

from pathlib import Path
import re

ROOT = Path.home() / "BLOOM"
INPUT = ROOT / "training_corpus_semantic_v2.txt"

text = INPUT.read_text(encoding="utf-8")

blocks = re.split(
    r"===== SOURCE: (.*?) =====\n",
    text
)

total = 0
short = 0
accepted = 0
source_stats = {}

for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1]

    source_total = 0
    source_accepted = 0

    for line in content.splitlines():
        line = line.strip()

        if not line:
            continue

        total += 1
        source_total += 1

        words = re.findall(
            r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
            line
        )

        if len(line) < 20 or len(words) < 4:
            short += 1
            continue

        accepted += 1
        source_accepted += 1

    source_stats[source] = (
        source_total,
        source_accepted
    )

print("=" * 72)
print("BLOOM TRAINING DATA DIAGNOSTIC")
print("=" * 72)

print(f"Input characters : {len(text):,}")
print(f"Input lines      : {total:,}")
print(f"Rejected lines   : {short:,}")
print(f"Accepted lines   : {accepted:,}")
print(f"Sources          : {len(source_stats):,}")

print()
print("=" * 72)
print("SOURCE SURVIVAL")
print("=" * 72)

for source, (before, after) in sorted(
    source_stats.items(),
    key=lambda x: x[1][1],
    reverse=True
):
    print(
        f"{after:6,d} accepted | "
        f"{before:6,d} total | "
        f"{source}"
    )

print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

if accepted >= 1000:
    print("STATUS: DATASET_GENERATOR_BUG")
    print("There are enough records; preparation logic needs correction.")
elif accepted >= 100:
    print("STATUS: SMALL_BUT_USABLE")
    print("The corpus needs a less aggressive record threshold.")
else:
    print("STATUS: SEMANTIC_SOURCE_TOO_SMALL")
    print("More real semantic material is required.")

print("=" * 72)
