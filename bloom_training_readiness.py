#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import re
import math

ROOT = Path.home() / "BLOOM"
CORPUS = ROOT / "training_corpus_semantic_v2.txt"

text = CORPUS.read_text(encoding="utf-8")

words = re.findall(
    r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
    text.lower()
)

counts = Counter(words)
total = len(words)

sources = re.findall(
    r"===== SOURCE: (.*?) =====",
    text
)

source_counts = Counter()

blocks = re.split(
    r"===== SOURCE: (.*?) =====\n",
    text
)

for i in range(1, len(blocks), 2):
    source = blocks[i]
    body = blocks[i + 1]
    n = len(re.findall(
        r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
        body
    ))
    source_counts[source] += n

entropy = 0.0

if total:
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)

top20 = sum(c for _, c in counts.most_common(20))

print("=" * 72)
print("BLOOM TRAINING READINESS AUDIT")
print("=" * 72)

print(f"Corpus words        : {total:,}")
print(f"Unique vocabulary   : {len(counts):,}")
print(f"Vocabulary ratio    : {len(counts)/max(total,1):.6f}")
print(f"Sources             : {len(set(sources)):,}")
print(f"Lexical entropy     : {entropy:.6f}")
print(f"Top-20 token share  : {top20/max(total,1):.2%}")

print()
print("=" * 72)
print("TOP TOKENS")
print("=" * 72)

for word, count in counts.most_common(30):
    print(f"{count:7,d} | {word}")

print()
print("=" * 72)
print("SOURCE BALANCE")
print("=" * 72)

for source, count in source_counts.most_common():
    share = count / max(total, 1)
    print(f"{count:7,d} | {share:7.2%} | {source}")

largest = max(source_counts.values()) if source_counts else 0
largest_share = largest / max(total, 1)

print()
print("=" * 72)
print("READINESS")
print("=" * 72)

if total < 1000:
    verdict = "INSUFFICIENT"
elif len(counts) < 1000:
    verdict = "LOW_VOCABULARY"
elif largest_share > 0.50:
    verdict = "SOURCE_DOMINATED"
elif top20 / max(total,1) > 0.60:
    verdict = "HIGH_REPETITION"
elif len(set(sources)) < 10:
    verdict = "LOW_SOURCE_DIVERSITY"
else:
    verdict = "TRAINING_READY"

print(f"STATUS: {verdict}")

print()
print("Recommended minimum:")
print("  words >= 1,000")
print("  vocabulary >= 1,000")
print("  sources >= 10")
print("  largest source < 50%")
print("  top-20 token share < 60%")

print("=" * 72)
