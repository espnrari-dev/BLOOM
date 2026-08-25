#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import re
import math

ROOT = Path.home() / "BLOOM"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"

def tokenize(text):
    return re.findall(
        r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
        text.lower()
    )

train = tokenize(TRAIN.read_text(encoding="utf-8"))
valid = tokenize(VALID.read_text(encoding="utf-8"))

counts = Counter(train)
total = len(train)

# Laplace-smoothed unigram model.
vocab = set(train)
V = len(vocab)

log_loss = 0.0
known = 0
unknown = 0

for word in valid:
    probability = (counts[word] + 1) / (total + V + 1)

    log_loss -= math.log(probability)

    if word in vocab:
        known += 1
    else:
        unknown += 1

cross_entropy = log_loss / max(1, len(valid))
perplexity = math.exp(cross_entropy)

# Most common validation token prediction baseline.
majority = counts.most_common(1)[0][0]

majority_hits = sum(
    1 for word in valid
    if word == majority
)

majority_accuracy = majority_hits / max(1, len(valid))

print("=" * 72)
print("BLOOM BASELINE LANGUAGE MODEL")
print("=" * 72)

print(f"Training tokens       : {len(train):,}")
print(f"Validation tokens     : {len(valid):,}")
print(f"Vocabulary            : {V:,}")
print(f"Known validation      : {known:,}")
print(f"Unknown validation    : {unknown:,}")
print(f"Known-token ratio     : {known/max(1,len(valid)):.2%}")

print()
print("=" * 72)
print("UNIGRAM BASELINE")
print("=" * 72)

print(f"Cross entropy         : {cross_entropy:.6f}")
print(f"Perplexity            : {perplexity:.6f}")
print(f"Majority token        : {majority}")
print(f"Majority accuracy     : {majority_accuracy:.4%}")

print()
print("=" * 72)
print("TOP LEARNED TOKENS")
print("=" * 72)

for word, count in counts.most_common(40):
    probability = count / total
    print(
        f"{count:6,d} | "
        f"{probability:8.4%} | "
        f"{word}"
    )

print()
print("=" * 72)
print("BASELINE STATUS")
print("=" * 72)

if len(valid) >= 300 and unknown / len(valid) < 0.70:
    print("STATUS: BASELINE_ESTABLISHED")
else:
    print("STATUS: BASELINE_DATA_LIMITED")

print("=" * 72)
