#!/usr/bin/env python3

from pathlib import Path
import sys
import traceback

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

print("=" * 72)
print("BLOOM REAL GPT — DATA SOURCE TRUTH TEST")
print("=" * 72)
print(f"ROOT : {ROOT}")
print(f"MODEL: {MODEL}")
print()

# Import the actual model module.
# This executes definitions but does NOT enter training unless
# bloom_real.py has unsafe top-level training code.
print("=" * 72)
print("IMPORTING ACTUAL bloom_real MODULE")
print("=" * 72)

try:
    sys.path.insert(0, str(ROOT))
    import bloom_real
    print("IMPORT: SUCCESS")
except Exception as e:
    print("IMPORT: FAILED")
    print(f"{type(e).__name__}: {e}")
    traceback.print_exc()
    raise SystemExit(1)

print()

# ------------------------------------------------------------------
# SHOW RUNTIME GLOBALS THAT MAY CONTROL DATA
# ------------------------------------------------------------------

print("=" * 72)
print("RUNTIME DATA-RELATED GLOBALS")
print("=" * 72)

names = sorted(
    name
    for name in vars(bloom_real)
    if any(
        key in name.lower()
        for key in (
            "data",
            "text",
            "corpus",
            "archive",
            "train",
            "valid",
            "vocab",
            "preset",
            "config",
            "cfg",
            "path",
        )
    )
)

for name in names:
    try:
        value = getattr(bloom_real, name)

        if callable(value):
            print(f"{name:<30} <callable>")
        else:
            representation = repr(value)

            if len(representation) > 500:
                representation = (
                    representation[:500]
                    + "...<truncated>"
                )

            print(
                f"{name:<30} "
                f"{type(value).__name__}: "
                f"{representation}"
            )
    except Exception as e:
        print(
            f"{name:<30} "
            f"<ERROR: {e}>"
        )

print()

# ------------------------------------------------------------------
# ACTUAL load_text()
# ------------------------------------------------------------------

print("=" * 72)
print("EXECUTING ACTUAL load_text()")
print("=" * 72)

if not hasattr(bloom_real, "load_text"):
    print("ERROR: load_text() unavailable")
    raise SystemExit(1)

try:
    result = bloom_real.load_text()
except Exception as e:
    print("load_text(): FAILED")
    print(f"{type(e).__name__}: {e}")
    traceback.print_exc()
    raise SystemExit(1)

print("load_text(): SUCCESS")
print(f"Return type: {type(result).__name__}")

if isinstance(result, tuple):
    print(f"Tuple length: {len(result)}")
    for i, item in enumerate(result):
        print(
            f"  [{i}] type={type(item).__name__} "
            f"size={len(item) if hasattr(item, '__len__') else 'n/a'}"
        )
else:
    print(
        f"Result size: "
        f"{len(result) if hasattr(result, '__len__') else 'n/a'}"
    )

print()

# ------------------------------------------------------------------
# IDENTIFY RETURN VALUES
# ------------------------------------------------------------------

text = None
archive_count = None

if isinstance(result, tuple):
    for item in result:
        if isinstance(item, str):
            text = item
        elif isinstance(item, int):
            archive_count = item
elif isinstance(result, str):
    text = result

if text is None:
    print("=" * 72)
    print("COULD NOT IDENTIFY TEXT RETURN VALUE")
    print("=" * 72)
    raise SystemExit(1)

print("=" * 72)
print("ACTUAL LOADED CORPUS")
print("=" * 72)

print(f"Characters       : {len(text):,}")
print(f"Words            : {len(text.split()):,}")
print(f"Bytes UTF-8      : {len(text.encode('utf-8')):,}")
print(f"Lines            : {len(text.splitlines()):,}")

if archive_count is not None:
    print(f"Archive count    : {archive_count}")

print()

# ------------------------------------------------------------------
# TOKENIZATION / VOCAB
# ------------------------------------------------------------------

print("=" * 72)
print("ACTUAL MODEL TOKENIZATION")
print("=" * 72)

stoi = getattr(bloom_real, "stoi", None)
itos = getattr(bloom_real, "itos", None)

if isinstance(stoi, dict):
    print(f"Runtime stoi size: {len(stoi):,}")

if isinstance(itos, dict):
    print(f"Runtime itos size: {len(itos):,}")

elif isinstance(itos, (list, tuple)):
    print(f"Runtime itos size: {len(itos):,}")

# Try the model's own encoding mechanism if available.
encoded = None

for name in ("encode", "tokenize"):
    fn = getattr(bloom_real, name, None)

    if callable(fn):
        try:
            encoded = fn(text)
            print(
                f"Runtime {name}() succeeded: "
                f"{len(encoded):,} tokens"
            )
            break
        except Exception as e:
            print(
                f"Runtime {name}() failed: "
                f"{type(e).__name__}: {e}"
            )

if encoded is None and isinstance(stoi, dict):
    ids = []

    for ch in text:
        if ch in stoi:
            ids.append(stoi[ch])

    encoded = ids

    print(
        f"Character stoi reconstruction: "
        f"{len(encoded):,} tokens"
    )

print()

# ------------------------------------------------------------------
# COMPARE AGAINST ALL AVAILABLE CORPORA
# ------------------------------------------------------------------

print("=" * 72)
print("CORPUS IDENTITY COMPARISON")
print("=" * 72)

import hashlib

actual_hash = hashlib.sha256(
    text.encode("utf-8")
).hexdigest()

print(f"ACTUAL SHA256: {actual_hash}")
print()

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

matches = []

for name in candidates:
    path = ROOT / name

    if not path.exists():
        print(f"{name:<35} MISSING")
        continue

    data = path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    digest = hashlib.sha256(
        data.encode("utf-8")
    ).hexdigest()

    exact = digest == actual_hash

    if exact:
        matches.append(name)

    print(
        f"{name:<35} "
        f"{len(data):>9,} chars | "
        f"{len(data.split()):>8,} words | "
        f"SHA match={exact}"
    )

print()

# ------------------------------------------------------------------
# SAMPLE
# ------------------------------------------------------------------

print("=" * 72)
print("ACTUAL CORPUS SAMPLE")
print("=" * 72)

sample = text[:2000]

print(sample)

print()
print("=" * 72)
print("FINAL DATA TRUTH")
print("=" * 72)

if matches:
    print("EXACT MATCH:")
    for name in matches:
        print(f"  {name}")
else:
    print("EXACT MATCH: NONE OF THE CURRENT CANDIDATE FILES")

print()
print(f"Actual characters : {len(text):,}")
print(f"Actual words      : {len(text.split()):,}")
print(f"Actual SHA256     : {actual_hash}")

print()
print("STATUS: RUNTIME_DATA_SOURCE_IDENTIFIED")
print("=" * 72)
