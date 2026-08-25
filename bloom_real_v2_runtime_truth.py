#!/usr/bin/env python3

from pathlib import Path
import ast
import hashlib
import re
import sys

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"

print("=" * 72)
print("BLOOM REAL GPT — V2 RUNTIME TRUTH AUDIT")
print("=" * 72)

# ----------------------------------------------------------------------
# FILE HASHES
# ----------------------------------------------------------------------

def digest(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()

train = TRAIN.read_text(
    encoding="utf-8",
    errors="replace"
)

valid = VALID.read_text(
    encoding="utf-8",
    errors="replace"
)

print()
print("=" * 72)
print("CORPUS IDENTITY")
print("=" * 72)

print(f"TRAIN : {TRAIN}")
print(f"  chars : {len(train):,}")
print(f"  words : {len(train.split()):,}")
print(f"  sha256: {digest(TRAIN)}")

print()

print(f"VALID : {VALID}")
print(f"  chars : {len(valid):,}")
print(f"  words : {len(valid.split()):,}")
print(f"  sha256: {digest(VALID)}")

print()
print(
    "Exact train/valid text match :",
    train == valid
)

# ----------------------------------------------------------------------
# SOURCE ANALYSIS
# ----------------------------------------------------------------------

text = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

lines = text.splitlines()

print()
print("=" * 72)
print("DATA REFERENCES IN bloom_real.py")
print("=" * 72)

patterns = [
    r"bloom_train_v2",
    r"bloom_valid_v2",
    r"VALIDATION_TEXT",
    r"load_text",
    r"get_batch",
    r"test_x",
    r"test_y",
    r"train",
    r"valid",
    r"validation",
]

for pattern in patterns:
    hits = [
        i
        for i, line in enumerate(lines, 1)
        if re.search(pattern, line, re.IGNORECASE)
    ]

    if hits:
        print(
            f"{pattern:<24} lines: {hits}"
        )

# ----------------------------------------------------------------------
# PRINT DATA-RELEVANT SOURCE
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("DATA / EVALUATION SOURCE CODE")
print("=" * 72)

interesting = (
    "load_text",
    "get_batch",
    "VALIDATION_TEXT",
    "test_x",
    "test_y",
    "train_x",
    "train_y",
    "validation",
    "valid",
    "evaluate",
    "loss",
)

for i, line in enumerate(lines, 1):
    low = line.lower()

    if any(token.lower() in low for token in interesting):
        print(f"{i:5d}: {line}")

# ----------------------------------------------------------------------
# AST: FUNCTIONS USING DATA
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("FUNCTION STRUCTURE")
print("=" * 72)

try:
    tree = ast.parse(text)
except Exception as e:
    print("AST PARSE ERROR:", e)
    raise SystemExit(1)

for node in ast.walk(tree):

    if not isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        continue

    source = ast.get_source_segment(
        text,
        node
    ) or ""

    low = source.lower()

    if any(
        token.lower() in low
        for token in (
            "load_text",
            "get_batch",
            "validation",
            "valid",
            "test_x",
            "test_y",
            "loss",
        )
    ):
        print()
        print(f"FUNCTION: {node.name}")
        print(
            f"LINES: {node.lineno}-{getattr(node, 'end_lineno', node.lineno)}"
        )

        for i, line in enumerate(
            source.splitlines(),
            node.lineno
        ):
            if any(
                token.lower() in line.lower()
                for token in (
                    "load_text",
                    "get_batch",
                    "VALIDATION_TEXT",
                    "test_x",
                    "test_y",
                    "train",
                    "valid",
                    "loss",
                )
            ):
                print(f"{i:5d}: {line}")

# ----------------------------------------------------------------------
# IMPORT WITHOUT TRAINING
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("RUNTIME IMPORT TEST")
print("=" * 72)

sys.path.insert(0, str(ROOT))

try:
    import bloom_real
    print("IMPORT : SUCCESS")
except Exception as e:
    print("IMPORT : FAILED")
    print(f"{type(e).__name__}: {e}")
    raise SystemExit(1)

# ----------------------------------------------------------------------
# RUNTIME GLOBALS
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("RUNTIME DATA STATE")
print("=" * 72)

for name in (
    "TEXT_FILE",
    "ARCH_DIR",
    "VALIDATION_TEXT",
    "stoi",
    "itos",
    "VOCAB",
    "VOCAB_SIZE",
    "T",
    "BATCH",
    "N_LAYER",
    "N_HEAD",
    "N_EMBD",
):

    if hasattr(bloom_real, name):
        value = getattr(
            bloom_real,
            name
        )

        if isinstance(value, str):
            if len(value) > 300:
                value = value[:300] + "...<truncated>"

        elif hasattr(value, "__len__"):
            try:
                value = (
                    f"<{type(value).__name__}, "
                    f"len={len(value):,}>"
                )
            except Exception:
                pass

        print(
            f"{name:<20}: {value!r}"
        )

# ----------------------------------------------------------------------
# ACTUAL load_text()
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("ACTUAL load_text() RUNTIME")
print("=" * 72)

try:
    result = bloom_real.load_text()
except Exception as e:
    print("load_text() FAILED")
    print(f"{type(e).__name__}: {e}")
    raise SystemExit(1)

print(
    "Return type:",
    type(result).__name__
)

if isinstance(result, tuple):
    for i, item in enumerate(result):
        print(
            f"[{i}] "
            f"type={type(item).__name__} "
            f"size={len(item) if hasattr(item, '__len__') else 'n/a'}"
        )

# ----------------------------------------------------------------------
# VERIFY TRAIN TEXT RETURN
# ----------------------------------------------------------------------

runtime_train = None

if isinstance(result, tuple):
    for item in result:
        if isinstance(item, str):
            runtime_train = item
            break
elif isinstance(result, str):
    runtime_train = result

print()

if runtime_train is None:
    print("RUNTIME TRAIN TEXT: NOT FOUND")
else:
    runtime_hash = hashlib.sha256(
        runtime_train.encode("utf-8")
    ).hexdigest()

    print("RUNTIME TRAIN TEXT")
    print(
        "  chars:",
        f"{len(runtime_train):,}"
    )
    print(
        "  words:",
        f"{len(runtime_train.split()):,}"
    )
    print(
        "  sha256:",
        runtime_hash
    )
    print(
        "  exact V2 train match:",
        runtime_train == train
    )

# ----------------------------------------------------------------------
# VERIFY VALIDATION GLOBAL
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("RUNTIME VALIDATION TEXT")
print("=" * 72)

runtime_valid = getattr(
    bloom_real,
    "VALIDATION_TEXT",
    None
)

if runtime_valid is None:
    print("VALIDATION_TEXT : NOT PRESENT")
    print()
    print(
        "IMPORTANT: the model currently has no demonstrated"
    )
    print(
        "runtime validation stream."
    )
else:
    valid_hash = hashlib.sha256(
        runtime_valid.encode("utf-8")
    ).hexdigest()

    print(
        "chars:",
        f"{len(runtime_valid):,}"
    )
    print(
        "words:",
        f"{len(runtime_valid.split()):,}"
    )
    print(
        "sha256:",
        valid_hash
    )
    print(
        "exact V2 valid match:",
        runtime_valid == valid
    )
    print(
        "equals training stream:",
        runtime_valid == runtime_train
    )

# ----------------------------------------------------------------------
# FINAL VERDICT
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("V2 RUNTIME TRUTH VERDICT")
print("=" * 72)

train_ok = (
    runtime_train is not None
    and runtime_train == train
)

valid_ok = (
    runtime_valid is not None
    and runtime_valid == valid
)

separated = (
    train_ok
    and valid_ok
    and runtime_train != runtime_valid
)

print(
    "TRAINING SOURCE REACHED GPT :",
    train_ok
)

print(
    "VALIDATION SOURCE REACHED GPT:",
    valid_ok
)

print(
    "TRAIN/VALIDATION SEPARATED   :",
    separated
)

if separated:
    print()
    print("STATUS: V2_DATA_PATH_VERIFIED")
    print()
    print("NEXT STEP:")
    print("RUN ONE REAL GPT TRAINING EXPERIMENT")
    print("WITH BEFORE/AFTER LOSS + PARAMETER CHANGE")
else:
    print()
    print("STATUS: VALIDATION_PATH_NOT_YET_VERIFIED")
    print()
    print("DO NOT CLAIM GENERALIZATION YET.")
    print("The training source is bridged, but validation")
    print("must be independently demonstrated.")

print("=" * 72)
