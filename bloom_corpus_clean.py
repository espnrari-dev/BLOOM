#!/usr/bin/env python3

from pathlib import Path
import re
import hashlib

ROOT = Path.home() / "BLOOM"
RAW = ROOT / "training_corpus.txt"
CLEAN = ROOT / "training_corpus_clean.txt"

raw = RAW.read_text(encoding="utf-8")

blocks = re.split(
    r"\n\n===== SOURCE: (.*?) =====\n\n",
    raw,
)

records = []

for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1].strip()

    if not content:
        continue

    records.append((source, content))

def normalize(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

seen = set()
accepted = []

for source, content in records:
    content = normalize(content)

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    if digest in seen:
        continue

    seen.add(digest)
    accepted.append((source, content))

with CLEAN.open("w", encoding="utf-8") as f:
    for source, content in accepted:
        f.write(f"===== SOURCE: {source} =====\n")
        f.write(content)
        f.write("\n\n")

text = CLEAN.read_text(encoding="utf-8")

words = re.findall(
    r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
    text
)

print("=" * 72)
print("BLOOM CLEAN CORPUS")
print("=" * 72)
print(f"Raw sources       : {len(records):,}")
print(f"Unique sources    : {len(accepted):,}")
print(f"Characters        : {len(text):,}")
print(f"Words             : {len(words):,}")
print(f"Bytes             : {CLEAN.stat().st_size:,}")
print(f"SHA256            : {hashlib.sha256(text.encode()).hexdigest()}")

print()
print("=" * 72)
print("STATUS")
print("=" * 72)

if len(words) >= 10000:
    print("CORPUS_STATUS: STRONG")
elif len(words) >= 1000:
    print("CORPUS_STATUS: USABLE")
else:
    print("CORPUS_STATUS: SMALL")

print(f"OUTPUT: {CLEAN}")
print("=" * 72)
