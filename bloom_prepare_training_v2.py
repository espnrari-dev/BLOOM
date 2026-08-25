#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict
import re
import random
import hashlib

ROOT = Path.home() / "BLOOM"
INPUT = ROOT / "training_corpus_semantic_v2.txt"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"
META = ROOT / "bloom_training_manifest_v2.txt"

SEED = 1337
VALID_RATIO = 0.15
MAX_PER_SOURCE = 300

random.seed(SEED)

text = INPUT.read_text(encoding="utf-8")

blocks = re.split(
    r"===== SOURCE: (.*?) =====\n",
    text
)

by_source = defaultdict(list)

for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1].strip()

    if not content:
        continue

    # Split on sentence-like boundaries AND existing log/code lines.
    chunks = re.split(
        r"(?<=[.!?])\s+|\n+|(?<=:)\s+(?=[A-Z])",
        content
    )

    for chunk in chunks:
        chunk = re.sub(r"\s+", " ", chunk).strip()

        if not chunk:
            continue

        tokens = re.findall(
            r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
            chunk
        )

        # Keep real information-bearing fragments.
        if len(tokens) < 4:
            continue

        if len(chunk) < 20:
            continue

        # Avoid enormous fragments.
        if len(chunk) > 1000:
            words = chunk.split()
            for start in range(0, len(words), 100):
                piece = " ".join(words[start:start + 100])
                if len(piece.split()) >= 4:
                    by_source[source].append(piece)
        else:
            by_source[source].append(chunk)

# Deduplicate within each source.
for source in list(by_source):
    seen = set()
    clean = []

    for chunk in by_source[source]:
        key = hashlib.sha256(
            chunk.lower().encode("utf-8")
        ).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        clean.append(chunk)

    random.shuffle(clean)

    if len(clean) > MAX_PER_SOURCE:
        clean = clean[:MAX_PER_SOURCE]

    by_source[source] = clean

records = []

for source, chunks in by_source.items():
    for chunk in chunks:
        records.append((source, chunk))

# Global deduplication.
seen = set()
unique = []

for source, chunk in records:
    key = hashlib.sha256(
        chunk.lower().encode("utf-8")
    ).hexdigest()

    if key in seen:
        continue

    seen.add(key)
    unique.append((source, chunk))

random.shuffle(unique)

# Split by RECORD, not by source, so every real source can contribute
# to both training and validation.
split = int(len(unique) * (1.0 - VALID_RATIO))

train_records = unique[:split]
valid_records = unique[split:]

with TRAIN.open("w", encoding="utf-8") as f:
    for _, chunk in train_records:
        f.write(chunk + "\n")

with VALID.open("w", encoding="utf-8") as f:
    for _, chunk in valid_records:
        f.write(chunk + "\n")

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

source_counts = defaultdict(int)

for source, _ in unique:
    source_counts[source] += 1

with META.open("w", encoding="utf-8") as f:
    f.write("BLOOM TRAINING MANIFEST V2\n")
    f.write("=" * 72 + "\n")
    f.write(f"seed={SEED}\n")
    f.write(f"valid_ratio={VALID_RATIO}\n")
    f.write(f"max_per_source={MAX_PER_SOURCE}\n")
    f.write(f"input={INPUT}\n")
    f.write(f"sources={len(source_counts)}\n")
    f.write(f"records={len(unique)}\n")
    f.write(f"train_records={len(train_records)}\n")
    f.write(f"valid_records={len(valid_records)}\n")
    f.write(f"train_words={len(train_words)}\n")
    f.write(f"valid_words={len(valid_words)}\n")
    f.write(
        "train_sha256="
        + hashlib.sha256(train_text.encode()).hexdigest()
        + "\n"
    )
    f.write(
        "valid_sha256="
        + hashlib.sha256(valid_text.encode()).hexdigest()
        + "\n"
    )

print("=" * 72)
print("BLOOM TRAINING DATA PREPARATION V2")
print("=" * 72)

print(f"Sources discovered   : {len(source_counts):,}")
print(f"Unique records       : {len(unique):,}")
print(f"Training records     : {len(train_records):,}")
print(f"Validation records   : {len(valid_records):,}")
print(f"Training words       : {len(train_words):,}")
print(f"Validation words     : {len(valid_words):,}")

print()
print("=" * 72)
print("SOURCE CONTRIBUTIONS")
print("=" * 72)

for source, count in sorted(
    source_counts.items(),
    key=lambda x: x[1],
    reverse=True
):
    print(f"{count:6,d} | {source}")

print()
print("=" * 72)
print("STATUS")
print("=" * 72)

if len(train_records) >= 200 and len(valid_records) >= 30:
    print("TRAINING_DATA_READY")
else:
    print("TRAINING_DATA_SMALL")

print()
print(f"TRAIN : {TRAIN}")
print(f"VALID : {VALID}")
print(f"META  : {META}")
print("=" * 72)
