#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import re
import math

ROOT = Path.home() / "BLOOM"
CORPUS = ROOT / "training_corpus_clean.txt"

text = CORPUS.read_text(encoding="utf-8")

blocks = re.split(r"===== SOURCE: (.*?) =====\n", text)

records = []
for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1].strip()
    records.append((source, content))

def tokenize(s):
    return re.findall(r"\b[A-Za-z][A-Za-z0-9_'-]*\b", s.lower())

code_ext = {".py", ".sh", ".json", ".jsonl"}
prose_ext = {".txt", ".log"}

total_words = 0
code_words = 0
prose_words = 0
source_stats = []

for source, content in records:
    w = tokenize(content)
    n = len(w)
    total_words += n

    ext = Path(source).suffix.lower()

    if ext in code_ext:
        code_words += n
        kind = "CODE/DATA"
    else:
        prose_words += n
        kind = "TEXT/LOG"

    source_stats.append((source, n, kind))

print("=" * 72)
print("BLOOM CORPUS INTEGRITY AUDIT")
print("=" * 72)

print(f"Total words       : {total_words:,}")
print(f"Code/data words   : {code_words:,}")
print(f"Text/log words    : {prose_words:,}")
print(f"Code/data share   : {code_words/total_words:.2%}")
print(f"Text/log share    : {prose_words/total_words:.2%}")

print()
print("=" * 72)
print("LARGEST SOURCES")
print("=" * 72)

for source, n, kind in sorted(source_stats, key=lambda x: x[1], reverse=True)[:20]:
    print(f"{n:8,d} | {kind:10s} | {source}")

print()
print("=" * 72)
print("SEMANTIC SIGNAL")
print("=" * 72)

# Technical/semantic terms expected to carry meaning beyond syntax.
semantic_terms = {
    "reason","because","therefore","however","although",
    "goal","purpose","cause","effect","decision","evidence",
    "learn","learning","knowledge","memory","context",
    "future","risk","market","capital","power","honor",
    "truth","false","real","novel","pattern","rule",
    "prediction","result","outcome","strategy","reasoning",
    "state","change","behavior","system","model"
}

counts = Counter(tokenize(text))

semantic_hits = sum(counts[x] for x in semantic_terms)

print(f"Semantic anchor hits : {semantic_hits:,}")
print(f"Anchor density       : {semantic_hits/total_words:.4%}")

print()
print("=" * 72)
print("REPETITION PRESSURE")
print("=" * 72)

top = counts.most_common(20)
top20_words = sum(c for _, c in top)

print(f"Top 20 token volume  : {top20_words:,}")
print(f"Top 20 share         : {top20_words/total_words:.2%}")

entropy = 0.0
for c in counts.values():
    p = c / total_words
    entropy -= p * math.log2(p)

print(f"Lexical entropy      : {entropy:.6f}")

print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

if code_words / total_words > 0.70:
    print("STATUS: CODE_HEAVY")
    print("WARNING: Corpus is dominated by code/data.")
elif semantic_hits / total_words < 0.01:
    print("STATUS: LOW_SEMANTIC_DENSITY")
else:
    print("STATUS: SEMANTICALLY_USEFUL")

print("=" * 72)
