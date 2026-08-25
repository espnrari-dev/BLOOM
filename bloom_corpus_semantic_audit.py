#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import re
import math

ROOT = Path.home() / "BLOOM"
CORPUS = ROOT / "training_corpus_clean.txt"

text = CORPUS.read_text(encoding="utf-8")

blocks = re.split(
    r"===== SOURCE: (.*?) =====\n",
    text
)

records = []

for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1].strip()
    records.append((source, content))

def words(text):
    return re.findall(
        r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
        text.lower()
    )

all_words = words(text)
counts = Counter(all_words)

print("=" * 72)
print("BLOOM SEMANTIC CORPUS AUDIT")
print("=" * 72)

print(f"Sources              : {len(records):,}")
print(f"Words                : {len(all_words):,}")
print(f"Unique vocabulary    : {len(counts):,}")
print(f"Vocabulary ratio     : {len(counts)/len(all_words):.6f}")

print()
print("=" * 72)
print("SOURCE DISTRIBUTION")
print("=" * 72)

sizes = []

for source, content in records:
    n = len(words(content))
    sizes.append(n)
    print(f"{n:8,d} | {source}")

print()
print("=" * 72)
print("DISTRIBUTION STATS")
print("=" * 72)

mean = sum(sizes) / len(sizes)
variance = sum((x - mean) ** 2 for x in sizes) / len(sizes)
std = math.sqrt(variance)

print(f"Mean words/source    : {mean:,.2f}")
print(f"Std deviation        : {std:,.2f}")
print(f"Smallest source      : {min(sizes):,}")
print(f"Largest source       : {max(sizes):,}")

print()
print("=" * 72)
print("VOCABULARY")
print("=" * 72)

for word, count in counts.most_common(40):
    print(f"{count:7,d} | {word}")

print()
print("=" * 72)
print("REPETITION")
print("=" * 72)

hapax = sum(1 for c in counts.values() if c == 1)
twice = sum(1 for c in counts.values() if c == 2)

print(f"Hapax vocabulary     : {hapax:,}")
print(f"Appearing twice      : {twice:,}")
print(f"Repeated >=3         : {sum(1 for c in counts.values() if c >= 3):,}")

print()
print("=" * 72)
print("CORPUS VERDICT")
print("=" * 72)

if len(all_words) >= 50000 and len(counts) >= 2000 and len(records) >= 20:
    print("STATUS: SEMANTICALLY_SIZED_CORPUS")
else:
    print("STATUS: REQUIRES_EXPANSION")

print("=" * 72)
