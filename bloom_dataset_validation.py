#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import hashlib
import re
import math

ROOT = Path.home() / "BLOOM"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"

train = TRAIN.read_text(encoding="utf-8")
valid = VALID.read_text(encoding="utf-8")

def tokenize(text):
    return re.findall(
        r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
        text.lower()
    )

train_words = tokenize(train)
valid_words = tokenize(valid)

train_set = set(train_words)
valid_set = set(valid_words)

overlap = train_set & valid_set
novel_valid = valid_set - train_set

train_counts = Counter(train_words)

entropy = 0.0
if train_words:
    total = len(train_words)
    for count in train_counts.values():
        p = count / total
        entropy -= p * math.log2(p)

train_lines = [
    x.strip()
    for x in train.splitlines()
    if x.strip()
]

valid_lines = [
    x.strip()
    for x in valid.splitlines()
    if x.strip()
]

train_hashes = {
    hashlib.sha256(
        x.lower().encode("utf-8")
    ).hexdigest()
    for x in train_lines
}

valid_hashes = {
    hashlib.sha256(
        x.lower().encode("utf-8")
    ).hexdigest()
    for x in valid_lines
}

exact_overlap = train_hashes & valid_hashes

print("=" * 72)
print("BLOOM DATASET VALIDATION")
print("=" * 72)

print(f"Train words             : {len(train_words):,}")
print(f"Validation words        : {len(valid_words):,}")
print(f"Train vocabulary        : {len(train_set):,}")
print(f"Validation vocabulary   : {len(valid_set):,}")
print(f"Shared vocabulary       : {len(overlap):,}")
print(f"Novel validation words  : {len(novel_valid):,}")
print(f"Train lexical entropy   : {entropy:.6f}")

print()
print("=" * 72)
print("MEMORIZATION CHECK")
print("=" * 72)

print(f"Train records           : {len(train_lines):,}")
print(f"Validation records      : {len(valid_lines):,}")
print(f"Exact duplicate records : {len(exact_overlap):,}")

if valid_set:
    print(
        f"Vocabulary overlap      : "
        f"{len(overlap)/len(valid_set):.2%}"
    )

print()
print("=" * 72)
print("TOP TRAIN TOKENS")
print("=" * 72)

for word, count in train_counts.most_common(30):
    print(f"{count:7,d} | {word}")

print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

if exact_overlap:
    print("STATUS: DATA_LEAKAGE")
elif len(train_set) < 500:
    print("STATUS: LOW_VOCABULARY")
elif len(valid_lines) < 30:
    print("STATUS: VALIDATION_TOO_SMALL")
elif len(novel_valid) == 0:
    print("STATUS: NO_NOVEL_VOCABULARY")
else:
    print("STATUS: CLEAN_TRAIN_VALID_SPLIT")

print("=" * 72)
