#!/usr/bin/env python3

import hashlib
from pathlib import Path

ROOT = Path.home() / "BLOOM"
OUTPUT = ROOT / "training_corpus.txt"
MIN_CHARS = 1000

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}

EXCLUDE_FILES = {
    OUTPUT.name,
    "bloom_corpus.py",
    "training_corpus.txt",
}

EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".text",
    ".log",
    ".csv",
    ".json",
    ".jsonl",
    ".py",
    ".sh",
    ".yaml",
    ".yml",
}

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def discover():
    found = []

    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue

        if p.name in EXCLUDE_FILES:
            continue

        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue

        if p.suffix.lower() not in EXTENSIONS:
            continue

        try:
            data = p.read_bytes()
            text = data.decode("utf-8", errors="strict")
        except Exception:
            continue

        if not text.strip():
            continue

        found.append((p, data, text))

    return found

def main():
    print("=" * 72)
    print("BLOOM CORPUS ENGINE")
    print("=" * 72)

    sources = discover()

    seen = set()
    accepted = []
    duplicates = 0

    for path, data, text in sources:
        digest = sha256(data)

        if digest in seen:
            duplicates += 1
            continue

        seen.add(digest)
        accepted.append((path, data, text))

        print(
            f"{str(path.relative_to(ROOT)):<45} "
            f"bytes={len(data):<8} "
            f"chars={len(text):<8} "
            f"words={len(text.split()):<8} "
            f"sha256={digest[:16]}"
        )

    total_bytes = sum(len(x[1]) for x in accepted)
    total_chars = sum(len(x[2]) for x in accepted)
    total_words = sum(len(x[2].split()) for x in accepted)

    print()
    print("=" * 72)
    print("CORPUS ACCOUNTING")
    print("=" * 72)
    print(f"Unique sources : {len(accepted)}")
    print(f"Duplicate files: {duplicates}")
    print(f"Bytes          : {total_bytes}")
    print(f"Characters     : {total_chars}")
    print(f"Words          : {total_words}")

    if total_chars < MIN_CHARS:
        print()
        print("[STATUS] INSUFFICIENT_REAL_CORPUS")
        print(f"[REQUIRED] >= {MIN_CHARS:,} characters")
        print(f"[ACTUAL]   {total_chars:,} characters")
        print()
        print("No training corpus will be produced.")
        return 1

    with OUTPUT.open("w", encoding="utf-8") as out:
        for path, _, text in accepted:
            out.write(f"\n\n===== SOURCE: {path.relative_to(ROOT)} =====\n\n")
            out.write(text.rstrip())
            out.write("\n")

    print()
    print("[STATUS] CORPUS_READY")
    print(f"[OUTPUT] {OUTPUT}")
    print(f"[CHARS]  {total_chars:,}")
    print(f"[WORDS]  {total_words:,}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
