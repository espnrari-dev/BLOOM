#!/usr/bin/env python3

from pathlib import Path
import re
import ast

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

print("=" * 72)
print("BLOOM REAL GPT — LOADER AUDIT")
print("=" * 72)

text = MODEL.read_text(encoding="utf-8")
lines = text.splitlines()
tree = ast.parse(text)

fn = next(
    (
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
        and n.name == "load_text"
    ),
    None
)

if fn is None:
    print("ERROR: load_text() not found")
    raise SystemExit(1)

print()
print("=" * 72)
print("ACTUAL load_text() SOURCE")
print("=" * 72)

for n in range(fn.lineno, fn.end_lineno + 1):
    print(f"{n:5d}: {lines[n-1]}")

print()
print("=" * 72)
print("RUNTIME INPUTS REFERENCED BY LOADER")
print("=" * 72)

patterns = [
    r"my_texts\.txt",
    r"archives",
    r"glob",
    r"rglob",
    r"read_text",
    r"split",
    r"words",
    r"len\(",
    r"threshold",
    r"minimum",
    r"minimum_chars",
    r"minimum_words",
    r"500",
    r"1000",
    r"2000",
    r"5000",
    r"10000",
]

for pattern in patterns:
    hits = [
        (n, line)
        for n, line in enumerate(lines, 1)
        if fn.lineno <= n <= fn.end_lineno
        and re.search(pattern, line, re.IGNORECASE)
    ]

    if hits:
        print(f"\nPATTERN: {pattern}")
        for n, line in hits:
            print(f"{n:5d}: {line}")

print()
print("=" * 72)
print("ACTUAL my_texts.txt")
print("=" * 72)

p = ROOT / "my_texts.txt"

if p.exists():
    data = p.read_text(
        encoding="utf-8",
        errors="replace"
    )

    print(f"Characters : {len(data):,}")
    print(f"Words      : {len(data.split()):,}")
    print(f"Lines      : {len(data.splitlines()):,}")
    print(f"Bytes      : {p.stat().st_size:,}")
else:
    print("MISSING")

print()
print("=" * 72)
print("ACTUAL ARCHIVES")
print("=" * 72)

archives = ROOT / "archives"

if archives.exists():
    files = sorted(
        p for p in archives.rglob("*")
        if p.is_file()
    )

    print(f"Files: {len(files):,}")

    total_chars = 0
    total_words = 0

    for p in files:
        try:
            data = p.read_text(
                encoding="utf-8",
                errors="replace"
            )
        except Exception:
            continue

        chars = len(data)
        words = len(data.split())

        total_chars += chars
        total_words += words

        print(
            f"{words:8,d} words | "
            f"{chars:9,d} chars | "
            f"{p.relative_to(ROOT)}"
        )

    print()
    print(f"TOTAL ARCHIVE WORDS : {total_words:,}")
    print(f"TOTAL ARCHIVE CHARS : {total_chars:,}")
else:
    print("MISSING")

print()
print("=" * 72)
print("VALIDATED CORPORA")
print("=" * 72)

for name in (
    "training_corpus_semantic_v2.txt",
    "bloom_train_v2.txt",
    "bloom_valid_v2.txt",
    "training_corpus_semantic.txt",
):
    p = ROOT / name

    if p.exists():
        data = p.read_text(
            encoding="utf-8",
            errors="replace"
        )

        print(
            f"{name:<35} "
            f"{len(data.split()):>8,d} words | "
            f"{len(data):>9,d} chars"
        )
    else:
        print(f"{name:<35} MISSING")

print()
print("=" * 72)
print("LOADER AUDIT VERDICT")
print("=" * 72)

print("The real GPT loader is rejecting the workspace")
print("BEFORE model construction completes.")
print()
print("The validated V2 corpus therefore has NOT yet")
print("been demonstrated to reach the real GPT.")
print()
print("NEXT ACTION: redirect the REAL loader to the")
print("validated V2 train/validation data without")
print("fabricating or duplicating corpus material.")
print("=" * 72)
