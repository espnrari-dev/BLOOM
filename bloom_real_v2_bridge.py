#!/usr/bin/env python3

from pathlib import Path
import shutil
import re
import sys

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"

print("=" * 72)
print("BLOOM REAL GPT — V2 CORPUS BRIDGE")
print("=" * 72)

# ----------------------------------------------------------------------
# REQUIREMENTS
# ----------------------------------------------------------------------

for path in (MODEL, TRAIN, VALID):
    if not path.exists():
        print(f"ERROR: missing {path}")
        raise SystemExit(1)

train_text = TRAIN.read_text(
    encoding="utf-8",
    errors="replace"
)

valid_text = VALID.read_text(
    encoding="utf-8",
    errors="replace"
)

if not train_text.strip():
    print("ERROR: V2 training corpus is empty")
    raise SystemExit(1)

if not valid_text.strip():
    print("ERROR: V2 validation corpus is empty")
    raise SystemExit(1)

print(f"Training source : {TRAIN}")
print(f"Training chars  : {len(train_text):,}")
print(f"Training words  : {len(train_text.split()):,}")
print()
print(f"Validation source : {VALID}")
print(f"Validation chars  : {len(valid_text):,}")
print(f"Validation words  : {len(valid_text.split()):,}")

# ----------------------------------------------------------------------
# BACKUP
# ----------------------------------------------------------------------

backup = MODEL.with_suffix(".py.pre_v2_bridge")

if not backup.exists():
    shutil.copy2(MODEL, backup)
    print()
    print(f"BACKUP CREATED : {backup}")
else:
    print()
    print(f"BACKUP EXISTS  : {backup}")

# ----------------------------------------------------------------------
# READ MODEL
# ----------------------------------------------------------------------

text = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

# ----------------------------------------------------------------------
# FIND load_text()
# ----------------------------------------------------------------------

match = re.search(
    r"(?ms)^def load_text\(\):.*?(?=^def |\Z)",
    text
)

if not match:
    print("ERROR: could not locate load_text()")
    raise SystemExit(1)

old_loader = match.group(0)

# ----------------------------------------------------------------------
# NEW VALIDATED V2 LOADER
#
# Important:
#   - training corpus is kept separate
#   - validation corpus is kept separate
#   - no archive discovery
#   - no synthetic/fabricated content
#   - no corpus multiplication here
#
# The return remains compatible with the existing:
#
#     txt, archive_count = load_text()
#
# ----------------------------------------------------------------------

new_loader = r'''def load_text():
    """
    BLOOM V2 REAL DATA LOADER

    Training:
        bloom_train_v2.txt

    Validation:
        bloom_valid_v2.txt

    The validated V2 corpora are loaded directly.
    No fabricated text is introduced.
    No archive material is silently mixed into training.
    """

    train_path = BLOOM_DIR / "bloom_train_v2.txt"
    valid_path = BLOOM_DIR / "bloom_valid_v2.txt"

    if not train_path.exists():
        raise RuntimeError(
            f"Missing validated V2 training corpus: {train_path}"
        )

    if not valid_path.exists():
        raise RuntimeError(
            f"Missing validated V2 validation corpus: {valid_path}"
        )

    train_text = train_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    valid_text = valid_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    if len(train_text.strip()) < 100:
        raise RuntimeError(
            "Validated V2 training corpus is too small."
        )

    if len(valid_text.strip()) < 20:
        raise RuntimeError(
            "Validated V2 validation corpus is too small."
        )

    # Keep validation available to the runtime without contaminating
    # the training stream.
    global VALIDATION_TEXT
    VALIDATION_TEXT = valid_text

    # The existing GPT runtime expects load_text() to return the
    # training text and an archive count.
    #
    # archive_count is retained for compatibility.
    archive_count = 0

    return train_text, archive_count
'''

text = text[:match.start()] + new_loader + text[match.end():]

# ----------------------------------------------------------------------
# ADD VALIDATION GLOBAL AFTER LOADER
# ----------------------------------------------------------------------

if "VALIDATION_TEXT = None" not in text:
    marker = "def load_text():"

    text = text.replace(
        marker,
        "VALIDATION_TEXT = None\n\n\n" + marker,
        1
    )

# ----------------------------------------------------------------------
# WRITE
# ----------------------------------------------------------------------

MODEL.write_text(
    text,
    encoding="utf-8"
)

print()
print("=" * 72)
print("PATCH COMPLETE")
print("=" * 72)
print("REAL GPT LOADER NOW TARGETS:")
print(f"  TRAIN : {TRAIN}")
print(f"  VALID : {VALID}")
print()
print("Archives are no longer mixed into the training stream.")
print("The GPT architecture itself was not replaced.")
print("No synthetic corpus was created.")
print("=" * 72)

# ----------------------------------------------------------------------
# SYNTAX CHECK
# ----------------------------------------------------------------------

print()
print("=" * 72)
print("SYNTAX CHECK")
print("=" * 72)

import py_compile

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
    shutil.copy2(backup, MODEL)
    print("RESTORE COMPLETE")
    raise SystemExit(1)

print()
print("=" * 72)
print("V2 BRIDGE STATUS")
print("=" * 72)
print("STATUS: REAL_GPT_LOADER_REDIRECTED")
print("TRAINING_SOURCE: bloom_train_v2.txt")
print("VALIDATION_SOURCE: bloom_valid_v2.txt")
print("SYNTHETIC_DATA: NONE")
print("ARCHIVE_MIXING: DISABLED")
print("ARCHITECTURE_REPLACED: NO")
print("=" * 72)
