#!/usr/bin/env python3

from pathlib import Path
import re
import hashlib

ROOT = Path.home() / "BLOOM"
RAW = ROOT / "training_corpus_clean.txt"
OUT = ROOT / "training_corpus_semantic.txt"

raw = RAW.read_text(encoding="utf-8")

blocks = re.split(r"===== SOURCE: (.*?) =====\n", raw)

KEEP_EXT = {".txt", ".log"}

records = []

for i in range(1, len(blocks), 2):
    source = blocks[i]
    content = blocks[i + 1].strip()

    ext = Path(source).suffix.lower()

    if ext not in KEEP_EXT:
        continue

    if not content:
        continue

    records.append((source, content))

# Remove source headers and obvious machine-only lines while preserving
# natural-language/log evidence.
cleaned = []

for source, content in records:
    lines = []

    for line in content.splitlines():
        s = line.strip()

        if not s:
            continue

        # Skip obvious pure separators.
        if re.fullmatch(r"[-=_]{5,}", s):
            continue

        # Skip lines consisting almost entirely of punctuation/numbers.
        alnum = sum(c.isalnum() for c in s)
        if len(s) > 20 and alnum / len(s) < 0.35:
            continue

        lines.append(s)

    if lines:
        cleaned.append((source, "\n".join(lines)))

# Deduplicate identical content.
seen = set()
unique = []

for source, content in cleaned:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    if digest in seen:
        continue

    seen.add(digest)
    unique.append((source, content))

with OUT.open("w", encoding="utf-8") as f:
    for source, content in unique:
        f.write(f"===== SOURCE: {source} =====\n")
        f.write(content)
        f.write("\n\n")

text = OUT.read_text(encoding="utf-8")
words = re.findall(r"\b[A-Za-z][A-Za-z0-9_'-]*\b", text)

print("=" * 72)
print("BLOOM SEMANTIC CORPUS")
print("=" * 72)

print(f"Original corpus     : {RAW.stat().st_size:,} bytes")
print(f"Selected sources    : {len(records):,}")
print(f"Unique sources      : {len(unique):,}")
print(f"Output bytes        : {OUT.stat().st_size:,}")
print(f"Output characters   : {len(text):,}")
print(f"Output words        : {len(words):,}")
print(f"SHA256              : {hashlib.sha256(text.encode()).hexdigest()}")

print()
print("=" * 72)
print("SELECTED SOURCES")
print("=" * 72)

for source, content in unique:
    count = len(re.findall(
        r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
        content
    ))
    print(f"{count:8,d} | {source}")

print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

if len(words) >= 1000:
    print("STATUS: SEMANTIC_CORPUS_READY")
else:
    print("STATUS: SEMANTIC_CORPUS_TOO_SMALL")

print(f"OUTPUT: {OUT}")
print("=" * 72)
