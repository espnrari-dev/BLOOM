#!/usr/bin/env python3

from pathlib import Path
import hashlib
import re

ROOT = Path.home() / "BLOOM"
CORPUS = ROOT / "training_corpus.txt"

text = CORPUS.read_text(encoding="utf-8")

print("=" * 72)
print("BLOOM CORPUS AUDIT")
print("=" * 72)

print(f"File       : {CORPUS}")
print(f"Bytes      : {CORPUS.stat().st_size:,}")
print(f"Characters : {len(text):,}")
print(f"Words      : {len(text.split()):,}")
print(f"Lines      : {len(text.splitlines()):,}")
print(f"SHA256     : {hashlib.sha256(text.encode()).hexdigest()}")

sources = re.findall(r"===== SOURCE: (.*?) =====", text)

print()
print("=" * 72)
print("SOURCE AUDIT")
print("=" * 72)
print(f"Embedded sources : {len(sources)}")

for i, source in enumerate(sources, 1):
    print(f"{i:03d} | {source}")

print()
print("=" * 72)
print("CONTENT QUALITY")
print("=" * 72)

blank = len(re.findall(r"\n\s*\n", text))
ascii_chars = sum(ord(c) < 128 for c in text)
non_ascii = len(text) - ascii_chars

print(f"Blank regions    : {blank:,}")
print(f"ASCII characters : {ascii_chars:,}")
print(f"Non-ASCII        : {non_ascii:,}")

print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

if len(text) >= 1000 and len(sources) >= 2:
    print("STATUS: CORPUS_VALID")
else:
    print("STATUS: CORPUS_REQUIRES_REVIEW")

print("=" * 72)
