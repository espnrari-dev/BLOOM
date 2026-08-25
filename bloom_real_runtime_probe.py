#!/usr/bin/env python3

from pathlib import Path
import ast
import re

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

text = MODEL.read_text(encoding="utf-8")
lines = text.splitlines()

print("=" * 72)
print("BLOOM REAL GPT — RUNTIME DATA/PRESET PROBE")
print("=" * 72)
print(f"MODEL: {MODEL}")
print(f"LINES: {len(lines):,}")
print()

tree = ast.parse(text)

# ------------------------------------------------------------------
# 1. ALL TOP-LEVEL CONSTANTS / ASSIGNMENTS
# ------------------------------------------------------------------

print("=" * 72)
print("TOP-LEVEL CONFIGURATION")
print("=" * 72)

interesting = (
    "PRESET",
    "CONFIG",
    "CFG",
    "DATA",
    "CORPUS",
    "TRAIN",
    "VALID",
    "BLOOM_DIR",
    "CKPT_DIR",
    "LR",
    "BETA1",
    "BETA2",
    "EPS",
    "WEIGHT_DECAY",
)

for node in tree.body:
    if isinstance(node, ast.Assign):
        names = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)

        if any(
            any(key in name.upper() for key in interesting)
            for name in names
        ):
            try:
                value = ast.unparse(node.value)
            except Exception:
                value = "<?>"

            print(
                f"{', '.join(names):30} = {value}"
            )

print()

# ------------------------------------------------------------------
# 2. EXACT load_text FUNCTION
# ------------------------------------------------------------------

print("=" * 72)
print("EXACT load_text() IMPLEMENTATION")
print("=" * 72)

load_fn = None

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "load_text":
        load_fn = node
        break

if load_fn:
    start = load_fn.lineno
    end = getattr(load_fn, "end_lineno", start)

    print(f"Lines {start}-{end}")
    print("-" * 72)

    for n in range(start, end + 1):
        print(f"{n:5d}: {lines[n-1]}")
else:
    print("load_text() NOT FOUND")

print()

# ------------------------------------------------------------------
# 3. EXACT get_batch FUNCTION
# ------------------------------------------------------------------

print("=" * 72)
print("EXACT get_batch() IMPLEMENTATION")
print("=" * 72)

batch_fn = None

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "get_batch":
        batch_fn = node
        break

if batch_fn:
    start = batch_fn.lineno
    end = getattr(batch_fn, "end_lineno", start)

    print(f"Lines {start}-{end}")
    print("-" * 72)

    for n in range(start, end + 1):
        print(f"{n:5d}: {lines[n-1]}")
else:
    print("get_batch() NOT FOUND")

print()

# ------------------------------------------------------------------
# 4. MODEL CONSTRUCTION
# ------------------------------------------------------------------

print("=" * 72)
print("GPT CONSTRUCTION")
print("=" * 72)

for n, line in enumerate(lines, 1):
    if re.search(r"\bmodel\s*=\s*GPT\s*\(", line):
        start = max(1, n - 25)
        end = min(len(lines), n + 35)

        print(f"Construction around line {n}")
        print("-" * 72)

        for x in range(start, end + 1):
            print(f"{x:5d}: {lines[x-1]}")

print()

# ------------------------------------------------------------------
# 5. TRAINING LOOP
# ------------------------------------------------------------------

print("=" * 72)
print("TRAINING LOOP")
print("=" * 72)

for n, line in enumerate(lines, 1):
    if (
        "apply_grads(" in line
        or "save_ckpt(" in line
        or "loss =" in line
        or "loss," in line
        or "get_batch()" in line
    ):
        start = max(1, n - 8)
        end = min(len(lines), n + 12)

        print(f"\n--- around line {n} ---")
        for x in range(start, end + 1):
            print(f"{x:5d}: {lines[x-1]}")

print()

# ------------------------------------------------------------------
# 6. CORPUS COMPARISON
# ------------------------------------------------------------------

print("=" * 72)
print("AVAILABLE CORPORA")
print("=" * 72)

candidates = [
    "training_corpus.txt",
    "training_corpus_clean.txt",
    "training_corpus_semantic.txt",
    "training_corpus_semantic_v2.txt",
    "bloom_train.txt",
    "bloom_valid.txt",
    "bloom_train_v2.txt",
    "bloom_valid_v2.txt",
]

for name in candidates:
    p = ROOT / name

    if p.exists():
        data = p.read_text(
            encoding="utf-8",
            errors="replace"
        )

        print(
            f"{name:<35}"
            f" {len(data):>9,} chars"
            f" {len(data.split()):>8,} words"
            f" {p.stat().st_size:>9,} bytes"
        )
    else:
        print(f"{name:<35} MISSING")

print()

# ------------------------------------------------------------------
# 7. SOURCE REFERENCES INSIDE MODEL
# ------------------------------------------------------------------

print("=" * 72)
print("CORPUS/PATH REFERENCES INSIDE bloom_real.py")
print("=" * 72)

patterns = [
    r"training_corpus",
    r"bloom_train",
    r"bloom_valid",
    r"semantic",
    r"archive",
    r"\.txt",
    r"\.jsonl",
    r"Path\(",
    r"read_text",
    r"glob\(",
]

seen = set()

for pattern in patterns:
    for n, line in enumerate(lines, 1):
        if re.search(pattern, line, re.IGNORECASE):
            key = (n, line)

            if key not in seen:
                seen.add(key)
                print(f"{n:5d}: {line}")

print()

# ------------------------------------------------------------------
# 8. PRESET REFERENCES
# ------------------------------------------------------------------

print("=" * 72)
print("PRESET REFERENCES")
print("=" * 72)

for n, line in enumerate(lines, 1):
    if re.search(
        r"\bPRESET\b|\bcfg\b|\bconfig\b|\bCFG\b",
        line
    ):
        print(f"{n:5d}: {line}")

print()

# ------------------------------------------------------------------
# 9. FINAL VERDICT
# ------------------------------------------------------------------

print("=" * 72)
print("RUNTIME PROBE VERDICT")
print("=" * 72)

full_corpus = ROOT / "training_corpus.txt"
v2_train = ROOT / "bloom_train_v2.txt"
v2_valid = ROOT / "bloom_valid_v2.txt"

model_text = text.lower()

uses_full = "training_corpus.txt" in model_text
uses_v2 = (
    "bloom_train_v2.txt" in model_text
    or "bloom_valid_v2.txt" in model_text
)

has_load = load_fn is not None
has_batch = batch_fn is not None
has_model = "model = GPT(" in text
has_update = "apply_grads(" in text
has_checkpoint = "save_ckpt(" in text

print(f"load_text()          : {has_load}")
print(f"get_batch()          : {has_batch}")
print(f"GPT construction     : {has_model}")
print(f"Gradient update      : {has_update}")
print(f"Checkpointing        : {has_checkpoint}")
print(f"References full corpus: {uses_full}")
print(f"References V2 corpus  : {uses_v2}")

print()

if uses_v2:
    print("DATA PATH: V2 CORPUS REFERENCES DETECTED")
elif uses_full:
    print("DATA PATH: FULL 71K-WORD CORPUS REFERENCES DETECTED")
else:
    print("DATA PATH: NOT DETERMINED FROM SIMPLE PATH SCAN")

print()

if has_load and has_batch and has_model and has_update:
    print("STATUS: REAL_GPT_RUNTIME_PATH_CONFIRMED")
else:
    print("STATUS: RUNTIME_PATH_INCOMPLETE")

print("=" * 72)
