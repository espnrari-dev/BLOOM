#!/usr/bin/env python3

from pathlib import Path
import re
import random
import hashlib

ROOT = Path.home() / "BLOOM"
INPUT = ROOT / "training_corpus_semantic_v2.txt"
TRAIN = ROOT / "bloom_train.txt"
VALID = ROOT / "bloom_valid.txt"
META = ROOT / "bloom_training_manifest.txt"

SEED = 1337
VALID_RATIO = 0.15
MAX_PER_SOURCE = 500

random.seed(SEED)

text = INPUT.read_text(encoding="utf-8")

blocks = re.split(
    r"===== SOURCE: (.*?) =====\n",
    text
)

records = []

for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1].strip()

    if not content:
        continue

    # Split into usable semantic lines.
    lines = []

    for line in content.splitlines():
        line = line.strip()

        if len(line) < 20:
            continue

        words = re.findall(
            r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
            line
        )

        if len(words) < 4:
            continue

        lines.append(line)

    # Remove duplicate lines within each source.
    seen = set()
    unique_lines = []

    for line in lines:
        key = hashlib.sha256(
            line.lower().encode("utf-8")
        ).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        unique_lines.append(line)

    # Balance large sources.
    if len(unique_lines) > MAX_PER_SOURCE:
        random.shuffle(unique_lines)
        unique_lines = unique_lines[:MAX_PER_SOURCE]

    for line in unique_lines:
        records.append((source, line))

# Global deduplication.
seen = set()
unique = []

for source, line in records:
    key = hashlib.sha256(
        line.lower().encode("utf-8")
    ).hexdigest()

    if key in seen:
        continue

    seen.add(key)
    unique.append((source, line))

random.shuffle(unique)

split = int(len(unique) * (1.0 - VALID_RATIO))

train_records = unique[:split]
valid_records = unique[split:]

with TRAIN.open("w", encoding="utf-8") as f:
    for source, line in train_records:
        f.write(line + "\n")

with VALID.open("w", encoding="utf-8") as f:
    for source, line in valid_records:
        f.write(line + "\n")

train_text = TRAIN.read_text(encoding="utf-8")
valid_text = VALID.read_text(encoding="utf-8")

train_words = re.findall(
    r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
    train_text
)

valid_words = re.findall(
    r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
    valid_text
)

sources = sorted(set(source for source, _ in unique))

with META.open("w", encoding="utf-8") as f:
    f.write("BLOOM TRAINING MANIFEST\n")
    f.write("=" * 72 + "\n")
    f.write(f"seed={SEED}\n")
    f.write(f"valid_ratio={VALID_RATIO}\n")
    f.write(f"max_per_source={MAX_PER_SOURCE}\n")
    f.write(f"input={INPUT}\n")
    f.write(f"sources={len(sources)}\n")
    f.write(f"records={len(unique)}\n")
    f.write(f"train_records={len(train_records)}\n")
    f.write(f"valid_records={len(valid_records)}\n")
    f.write(f"train_words={len(train_words)}\n")
    f.write(f"valid_words={len(valid_words)}\n")
    f.write(f"train_sha256={hashlib.sha256(train_text.encode()).hexdigest()}\n")
    f.write(f"valid_sha256={hashlib.sha256(valid_text.encode()).hexdigest()}\n")

print("=" * 72)
print("BLOOM TRAINING DATA PREPARATION")
print("=" * 72)

print(f"Input records       : {len(records):,}")
print(f"Unique records      : {len(unique):,}")
print(f"Sources             : {len(sources):,}")
print(f"Train records       : {len(train_records):,}")
print(f"Validation records  : {len(valid_records):,}")
print(f"Train words         : {len(train_words):,}")
print(f"Validation words    : {len(valid_words):,}")

print()
print("=" * 72)
print("OUTPUT")
print("=" * 72)

print(f"TRAIN : {TRAIN}")
print(f"VALID : {VALID}")
print(f"META  : {META}")

print()
print("=" * 72)

if len(train_records) >= 1000 and len(valid_records) >= 100:
    print("STATUS: TRAINING_DATA_READY")
else:
    print("STATUS: INSUFFICIENT_TRAINING_DATA")

print("=" * 72)
