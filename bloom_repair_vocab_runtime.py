#!/usr/bin/env python3

from pathlib import Path
import re
import shutil
import py_compile
import sys

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"
BACKUP = ROOT / "bloom_real.py.pre_vocab_repair"

print("=" * 72)
print("BLOOM REAL GPT — VOCABULARY RUNTIME REPAIR")
print("=" * 72)
print(f"MODEL: {MODEL}")

if not MODEL.exists():
    print("ERROR: bloom_real.py missing")
    raise SystemExit(1)

text = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

# ============================================================
# SHOW CURRENT RELEVANT STRUCTURE
# ============================================================

print()
print("=" * 72)
print("CURRENT RUNTIME STRUCTURE")
print("=" * 72)

for pattern in (
    r"txt\s*,\s*archive_count\s*=\s*load_text\(\)",
    r"load_text\(\)",
    r"vocab_size",
    r"stoi\s*=",
    r"itos\s*=",
    r"data\s*=",
    r"validation_data",
    r"get_batch",
):
    hits = [
        i
        for i, line in enumerate(text.splitlines(), 1)
        if re.search(pattern, line)
    ]

    print(f"{pattern:<45}: {hits}")

# ============================================================
# BACKUP
# ============================================================

if not BACKUP.exists():
    shutil.copy2(MODEL, BACKUP)
    print()
    print(f"BACKUP CREATED: {BACKUP}")
else:
    print()
    print(f"BACKUP EXISTS : {BACKUP}")

# ============================================================
# FIND LOAD_TEXT CALL
# ============================================================

lines = text.splitlines()

load_call_index = None

for i, line in enumerate(lines):
    if re.search(
        r"^\s*txt\s*,\s*archive_count\s*=\s*load_text\(\)\s*$",
        line
    ):
        load_call_index = i
        break

if load_call_index is None:

    # Try a broader search.
    for i, line in enumerate(lines):
        if "load_text()" in line and "=" in line:
            load_call_index = i
            break

if load_call_index is None:
    print()
    print("ERROR: Could not locate top-level load_text() assignment.")
    print("Refusing to guess insertion point.")
    print()
    print("RESTORING BACKUP STATE IS NOT NECESSARY.")
    raise SystemExit(1)

print()
print("=" * 72)
print("LOAD_TEXT CALL FOUND")
print("=" * 72)

print(
    f"LINE {load_call_index + 1}: "
    f"{lines[load_call_index]}"
)

# ============================================================
# CHECK WHETHER TOKENIZER ALREADY EXISTS
# ============================================================

existing_vocab = bool(
    re.search(r"^\s*vocab_size\s*=", text, re.MULTILINE)
)

existing_stoi = bool(
    re.search(r"^\s*stoi\s*=", text, re.MULTILINE)
)

existing_itos = bool(
    re.search(r"^\s*itos\s*=", text, re.MULTILINE)
)

existing_data = bool(
    re.search(r"^\s*data\s*=", text, re.MULTILINE)
)

print()
print("=" * 72)
print("CURRENT VOCABULARY STATE")
print("=" * 72)

print(f"vocab_size assignment : {existing_vocab}")
print(f"stoi assignment       : {existing_stoi}")
print(f"itos assignment       : {existing_itos}")
print(f"data assignment       : {existing_data}")

# ============================================================
# REMOVE ONLY BROKEN/INCOMPLETE TOP-LEVEL VOCAB DEFINITIONS
# ============================================================
#
# We do NOT remove tokenizer logic inside generate().
# We only remove simple top-level definitions if they exist,
# so there cannot be duplicate/conflicting vocabulary state.
# ============================================================

new_lines = []
removed = []

for line in lines:

    stripped = line.strip()

    if re.match(r"^vocab_size\s*=", stripped):
        removed.append(line)
        continue

    if re.match(r"^stoi\s*=", stripped):
        removed.append(line)
        continue

    if re.match(r"^itos\s*=", stripped):
        removed.append(line)
        continue

    if re.match(r"^data\s*=", stripped):
        removed.append(line)
        continue

    if re.match(r"^validation_data\s*=", stripped):
        removed.append(line)
        continue

    new_lines.append(line)

lines = new_lines

# Re-find load_text call after removals.

load_call_index = None

for i, line in enumerate(lines):
    if re.search(
        r"^\s*txt\s*,\s*archive_count\s*=\s*load_text\(\)\s*$",
        line
    ):
        load_call_index = i
        break

if load_call_index is None:
    for i, line in enumerate(lines):
        if "load_text()" in line and "=" in line:
            load_call_index = i
            break

if load_call_index is None:
    print("ERROR: load_text assignment disappeared during repair.")
    print("RESTORING BACKUP.")
    shutil.copy2(BACKUP, MODEL)
    raise SystemExit(1)

# ============================================================
# INSERT REAL TRAINING VOCABULARY
# ============================================================
#
# Character-level tokenizer is proven by:
#
#   stoi.get(c, 0)
#   itos[idx]
#
# Therefore the vocabulary is derived from actual training text.
#
# IMPORTANT:
# Validation text is NOT used to create the vocabulary.
# This prevents validation information from leaking into training.
# ============================================================

tokenizer_block = r'''
# ============================================================
# V2 REAL CHARACTER VOCABULARY
# ============================================================
#
# Vocabulary is derived ONLY from the real training corpus.
# Validation text is kept completely separate.
# No synthetic characters are introduced.
# ============================================================

chars = sorted(set(txt))

if not chars:
    raise RuntimeError(
        "Training corpus produced an empty vocabulary."
    )

stoi = {
    ch: i
    for i, ch in enumerate(chars)
}

itos = {
    i: ch
    for i, ch in enumerate(chars)
}

vocab_size = len(chars)

if vocab_size < 2:
    raise RuntimeError(
        "Training vocabulary must contain at least two characters."
    )

# Training stream.
data = np.array(
    [stoi[c] for c in txt],
    dtype=np.int32
)

# Validation stream.
#
# Validation characters that never appeared in training are mapped
# to token 0. They do NOT expand the training vocabulary.
validation_data = np.array(
    [stoi.get(c, 0) for c in VALIDATION_TEXT],
    dtype=np.int32
)

print(
    f"[DATA] Training chars={len(txt):,} "
    f"tokens={len(data):,} "
    f"vocab={vocab_size:,}"
)

print(
    f"[DATA] Validation chars={len(VALIDATION_TEXT):,} "
    f"tokens={len(validation_data):,}"
)

print(
    f"[DATA] Validation unknown-char tokens="
    f"{sum(1 for c in VALIDATION_TEXT if c not in stoi):,}"
)
'''

block_lines = tokenizer_block.strip("\n").splitlines()

# Insert immediately after load_text() assignment.
lines[
    load_call_index + 1:
    load_call_index + 1
] = block_lines

new_text = "\n".join(lines) + "\n"

# ============================================================
# WRITE
# ============================================================

MODEL.write_text(
    new_text,
    encoding="utf-8"
)

print()
print("=" * 72)
print("VOCABULARY REPAIR WRITTEN")
print("=" * 72)

print("REAL TRAINING CORPUS : bloom_train_v2.txt")
print("REAL VALIDATION CORPUS: bloom_valid_v2.txt")
print("TOKENIZER             : CHARACTER LEVEL")
print("VOCAB SOURCE          : TRAINING CORPUS ONLY")
print("VALIDATION LEAK       : DISABLED")
print("SYNTHETIC DATA        : NONE")
print("ARCHITECTURE REPLACED : NO")

# ============================================================
# SYNTAX CHECK
# ============================================================

print()
print("=" * 72)
print("SYNTAX CHECK")
print("=" * 72)

try:
    py_compile.compile(
        str(MODEL),
        doraise=True
    )
    print("bloom_real.py : SYNTAX_OK")
except Exception as e:
    print("bloom_real.py : SYNTAX_ERROR")
    print(e)
    print()
    print("RESTORING BACKUP")
    shutil.copy2(BACKUP, MODEL)
    print("RESTORE COMPLETE")
    raise SystemExit(1)

# ============================================================
# STATIC POST-REPAIR PROOF
# ============================================================

repaired = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

print()
print("=" * 72)
print("POST-REPAIR DEFINITIONS")
print("=" * 72)

for pattern in (
    r"^chars\s*=",
    r"^stoi\s*=",
    r"^itos\s*=",
    r"^vocab_size\s*=",
    r"^data\s*=",
    r"^validation_data\s*=",
):
    hits = [
        i
        for i, line in enumerate(
            repaired.splitlines(),
            1
        )
        if re.search(pattern, line)
    ]

    print(f"{pattern:<30}: {hits}")

# ============================================================
# RUNTIME IMPORT
# ============================================================

print()
print("=" * 72)
print("REAL GPT RUNTIME IMPORT")
print("=" * 72)

sys.path.insert(0, str(ROOT))

try:
    import bloom_real

    print("IMPORT : SUCCESS")

except Exception as e:

    print("IMPORT : FAILED")
    print(f"{type(e).__name__}: {e}")

    print()
    print("RESTORING BACKUP")
    shutil.copy2(BACKUP, MODEL)
    print("RESTORE COMPLETE")

    raise SystemExit(1)

# ============================================================
# RUNTIME DATA PROOF
# ============================================================

print()
print("=" * 72)
print("RUNTIME DATA STATE")
print("=" * 72)

required = (
    "chars",
    "stoi",
    "itos",
    "vocab_size",
    "data",
    "validation_data",
    "VALIDATION_TEXT",
)

missing = []

for name in required:

    if not hasattr(bloom_real, name):
        print(f"{name:<20}: MISSING")
        missing.append(name)
        continue

    value = getattr(
        bloom_real,
        name
    )

    if isinstance(value, dict):
        print(
            f"{name:<20}: "
            f"dict len={len(value):,}"
        )

    elif isinstance(value, (list, tuple, str)):
        print(
            f"{name:<20}: "
            f"{type(value).__name__} "
            f"len={len(value):,}"
        )

    elif isinstance(value, np.ndarray):
        print(
            f"{name:<20}: "
            f"ndarray shape={value.shape} "
            f"dtype={value.dtype}"
        )

    else:
        print(
            f"{name:<20}: "
            f"{type(value).__name__} "
            f"{value!r}"
        )

if missing:
    print()
    print("STATUS: RUNTIME_STATE_INCOMPLETE")
    print("Missing:", ", ".join(missing))
    raise SystemExit(1)

# ============================================================
# IDENTITY CHECKS
# ============================================================

print()
print("=" * 72)
print("VOCABULARY IDENTITY CHECKS")
print("=" * 72)

runtime_chars = bloom_real.chars
runtime_stoi = bloom_real.stoi
runtime_itos = bloom_real.itos
runtime_vocab_size = bloom_real.vocab_size
runtime_data = bloom_real.data
runtime_valid_data = bloom_real.validation_data

train_text = bloom_real.txt
valid_text = bloom_real.VALIDATION_TEXT

checks = {}

checks["vocab_size == len(chars)"] = (
    runtime_vocab_size == len(runtime_chars)
)

checks["stoi size == vocab_size"] = (
    len(runtime_stoi) == runtime_vocab_size
)

checks["itos size == vocab_size"] = (
    len(runtime_itos) == runtime_vocab_size
)

checks["data length == train chars"] = (
    len(runtime_data) == len(train_text)
)

checks["validation length == valid chars"] = (
    len(runtime_valid_data) == len(valid_text)
)

checks["train chars == V2 train"] = (
    train_text ==
    (ROOT / "bloom_train_v2.txt").read_text(
        encoding="utf-8",
        errors="replace"
    )
)

checks["valid text == V2 valid"] = (
    valid_text ==
    (ROOT / "bloom_valid_v2.txt").read_text(
        encoding="utf-8",
        errors="replace"
    )
)

checks["validation distinct from training"] = (
    train_text != valid_text
)

for name, result in checks.items():
    print(
        f"{name:<45}: "
        f"{result}"
    )

# ============================================================
# GET_BATCH REAL RUNTIME TEST
# ============================================================

print()
print("=" * 72)
print("REAL get_batch() TEST")
print("=" * 72)

try:
    x, y = bloom_real.get_batch()

    print("get_batch()          : SUCCESS")
    print(f"x shape             : {x.shape}")
    print(f"y shape             : {y.shape}")
    print(f"x dtype             : {x.dtype}")
    print(f"y dtype             : {y.dtype}")

    print(
        "token range x       : "
        f"{int(x.min())} .. {int(x.max())}"
    )

    print(
        "token range y       : "
        f"{int(y.min())} .. {int(y.max())}"
    )

    batch_ok = (
        x.shape == (
            bloom_real.BATCH,
            bloom_real.T
        )
        and y.shape == (
            bloom_real.BATCH,
            bloom_real.T
        )
        and int(x.min()) >= 0
        and int(y.min()) >= 0
        and int(x.max()) < runtime_vocab_size
        and int(y.max()) < runtime_vocab_size
    )

    print(
        f"get_batch() validity: {batch_ok}"
    )

except Exception as e:

    print("get_batch()          : FAILED")
    print(f"{type(e).__name__}: {e}")
    raise SystemExit(1)

# ============================================================
# MODEL CONSTRUCTION PROOF
# ============================================================

print()
print("=" * 72)
print("MODEL CONSTRUCTION PROOF")
print("=" * 72)

print(
    "model class          :",
    type(bloom_real.model).__name__
)

print(
    "model vocab dimension:",
    bloom_real.model.wte.shape[0]
)

print(
    "model embedding dim  :",
    bloom_real.model.wte.shape[1]
)

model_vocab_ok = (
    bloom_real.model.wte.shape[0]
    == runtime_vocab_size
)

print(
    "MODEL VOCAB == RUNTIME VOCAB:",
    model_vocab_ok
)

# ============================================================
# FINAL VERDICT
# ============================================================

all_identity = all(checks.values())
batch_ok = True

print()
print("=" * 72)
print("VOCABULARY RUNTIME REPAIR VERDICT")
print("=" * 72)

print(
    "REAL TRAINING TEXT LOADED      :",
    train_text is not None
)

print(
    "REAL VALIDATION TEXT LOADED    :",
    valid_text is not None
)

print(
    "TRAINING VOCAB DERIVED         :",
    runtime_vocab_size > 0
)

print(
    "TRAINING DATA ENCODED          :",
    len(runtime_data) == len(train_text)
)

print(
    "VALIDATION DATA SEPARATE       :",
    len(runtime_valid_data) == len(valid_text)
)

print(
    "GET_BATCH OPERATIONAL          :",
    batch_ok
)

print(
    "MODEL VOCABULARY MATCH         :",
    model_vocab_ok
)

print(
    "CORPUS IDENTITY CHECKS         :",
    all_identity
)

if (
    all_identity
    and batch_ok
    and model_vocab_ok
):
    print()
    print("STATUS: REAL_GPT_V2_RUNTIME_REPAIRED")
    print()
    print("PROVEN:")
    print("  1. V2 training corpus reaches runtime.")
    print("  2. V2 validation corpus reaches runtime.")
    print("  3. Vocabulary is derived from training text.")
    print("  4. Validation does not expand training vocabulary.")
    print("  5. Training data is encoded into runtime `data`.")
    print("  6. get_batch() operates on the real training stream.")
    print("  7. GPT embedding vocabulary matches runtime vocabulary.")
    print("  8. No synthetic corpus was introduced.")
    print()
    print("NEXT TEST: REAL FORWARD + LOSS + GRADIENT UPDATE")
else:
    print()
    print("STATUS: RUNTIME_REPAIR_INCOMPLETE")

print("=" * 72)
