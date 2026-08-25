#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import re
import math

ROOT = Path.home() / "BLOOM"
CORPUS = ROOT / "training_corpus.txt"

text = CORPUS.read_text(encoding="utf-8")

sources = re.findall(r"===== SOURCE: (.*?) =====", text)

body_parts = re.split(r"===== SOURCE: .*? =====", text)
body = "\n".join(body_parts)

words = re.findall(r"\b[A-Za-z][A-Za-z0-9_'-]*\b", body)
lower = [w.lower() for w in words]

counts = Counter(lower)

print("=" * 72)
print("BLOOM CORPUS PROFILE")
print("=" * 72)

print(f"Characters       : {len(text):,}")
print(f"Words            : {len(words):,}")
print(f"Sources          : {len(sources):,}")
print(f"Unique words     : {len(counts):,}")
print(f"Vocabulary ratio : {len(counts)/max(1,len(words)):.6f}")

print()
print("=" * 72)
print("TOP VOCABULARY")
print("=" * 72)

for word, count in counts.most_common(50):
    print(f"{count:7d} | {word}")

print()
print("=" * 72)
print("SOURCE TYPES")
print("=" * 72)

types = Counter()

for source in sources:
    suffix = Path(source).suffix.lower() or "[none]"
    types[suffix] += 1

for suffix, count in types.most_common():
    print(f"{suffix:10s} | {count}")

print()
print("=" * 72)
print("DIVERSITY")
print("=" * 72)

total = len(words)

if total:
    entropy = -sum(
        (c / total) * math.log2(c / total)
        for c in counts.values()
    )
else:
    entropy = 0.0

print(f"Lexical entropy : {entropy:.6f} bits")
print(f"Hapax words     : {sum(1 for c in counts.values() if c == 1):,}")
print(f"Repeated words  : {sum(1 for c in counts.values() if c > 1):,}")

print()
print("=" * 72)
print("BLOOM CORPUS PROFILE COMPLETE")
print("=" * 72)
