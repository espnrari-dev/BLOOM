#!/usr/bin/env python3

from pathlib import Path
import ast
import re
import shutil
import py_compile

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

print("=" * 72)
print("BLOOM REAL GPT — VOCABULARY RUNTIME REPAIR")
print("=" * 72)
print(f"MODEL: {MODEL}")

if not MODEL.exists():
    raise SystemExit("ERROR: bloom_real.py not found")

text = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

lines = text.splitlines()

# ------------------------------------------------------------
# SHOW THE FAILURE REGION
# ------------------------------------------------------------

print()
print("=" * 72)
print("CURRENT MODEL CONSTRUCTION REGION")
print("=" * 72)

for n in range(max(1, 970), min(len(lines), 1010) + 1):
    print(f"{n:5d}: {lines[n-1]}")

# ------------------------------------------------------------
# DETERMINE WHETHER vocab_size IS DEFINED ANYWHERE
# ------------------------------------------------------------

print()
print("=" * 72)
print("VOCABULARY DEFINITIONS")
print("=" * 72)

assignments = []

for i, line in enumerate(lines, 1):
    if re.search(r"\bvocab_size\s*=", line):
        assignments.append((i, line))

if assignments:
    for i, line in assignments:
        print(f"{i:5d}: {line}")
else:
    print("No direct vocab_size assignment found.")

# ------------------------------------------------------------
# FIND VOCABULARY CONSTRUCTION
# ------------------------------------------------------------

vocab_candidates = []

patterns = (
    r"\bstoi\s*=",
    r"\bitos\s*=",
    r"\bvocab\s*=",
    r"\bchars\s*=",
    r"\bchars\s*=",
    r"sorted\s*\(",
    r"set\s*\(",
)

for i, line in enumerate(lines, 1):
    if any(re.search(p, line) for p in patterns):
        vocab_candidates.append((i, line))

print()
print("=" * 72)
print("VOCABULARY-RELATED SOURCE")
print("=" * 72)

for i, line in vocab_candidates:
    if i < 350:
        print(f"{i:5d}: {line}")

# ------------------------------------------------------------
# LOCATE MODEL CONSTRUCTION
# ------------------------------------------------------------

constructor_lines = []

for i, line in enumerate(lines, 1):
    if re.search(
        r"\bmodel\s*=\s*.*(?:GPT|Transformer|Model)",
        line,
        re.IGNORECASE
    ):
        constructor_lines.append((i, line))

print()
print("=" * 72)
print("MODEL CONSTRUCTION")
print("=" * 72)

for i, line in constructor_lines:
    print(f"{i:5d}: {line}")

# ------------------------------------------------------------
# SAFETY CHECK
# ------------------------------------------------------------

if assignments:
    print()
    print("A vocab_size assignment already exists.")
    print("The NameError may therefore be caused by")
    print("ordering/scope rather than a missing formula.")
    print()
    print("NO AUTOMATIC EDIT MADE.")
    print()
    print("STATUS: MANUAL_SOURCE_INSPECTION_REQUIRED")
    raise SystemExit(2)

# We need an existing tokenizer vocabulary.
# The common real-GPT architecture in this project uses
# character-level stoi/itos.
#
# Find a plausible point where stoi/itos are created.
stoi_line = None
itos_line = None

for i, line in enumerate(lines, 1):
    if re.search(r"\bstoi\s*=", line):
        stoi_line = i

    if re.search(r"\bitos\s*=", line):
        itos_line = i

print()
print("=" * 72)
print("TOKENIZER LOCATION")
print("=" * 72)
print(f"stoi assignment line: {stoi_line}")
print(f"itos assignment line: {itos_line}")

if stoi_line is None and itos_line is None:
    print()
    print("ERROR: Could not identify an existing vocabulary.")
    print("Refusing to invent one.")
    raise SystemExit(3)

# ------------------------------------------------------------
# FIND A SAFE INSERTION POINT
# ------------------------------------------------------------

# Prefer insertion immediately after the vocabulary is
# established, but before the first use of vocab_size.

first_vocab_use = None

for i, line in enumerate(lines, 1):
    if re.search(r"\bvocab_size\b", line):
        if not re.search(r"\bvocab_size\s*=", line):
            first_vocab_use = i
            break

print()
print("=" * 72)
print("VOCAB_SIZE FIRST USE")
print("=" * 72)
print(f"First non-assignment use: {first_vocab_use}")

if first_vocab_use is None:
    print("No vocab_size use found.")
    raise SystemExit(4)

# Determine which existing vocabulary object is authoritative.
#
# Prefer stoi because character-level GPT implementations generally
# derive vocabulary size directly from the encoding dictionary.
if stoi_line is not None:
    vocab_expr = "len(stoi)"
elif itos_line is not None:
    vocab_expr = "len(itos)"
else:
    raise SystemExit("No usable vocabulary object found.")

# Insert immediately before the first use, but only if this does
# not occur before the vocabulary itself exists.
vocab_definition_line = stoi_line or itos_line

if first_vocab_use <= vocab_definition_line:
    print()
    print("ERROR: vocab_size is used before vocabulary construction.")
    print(f"Vocabulary line : {vocab_definition_line}")
    print(f"First use       : {first_vocab_use}")
    print()
    print("Refusing unsafe automatic rewrite.")
    raise SystemExit(5)

# ------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------

backup = MODEL.with_suffix(".py.pre_vocab_runtime_fix")

if not backup.exists():
    shutil.copy2(MODEL, backup)
    print()
    print(f"BACKUP CREATED: {backup}")
else:
    print()
    print(f"BACKUP EXISTS : {backup}")

# ------------------------------------------------------------
# INSERT ONLY THE MISSING DERIVED VALUE
# ------------------------------------------------------------

new_lines = []
inserted = False

for i, line in enumerate(lines, 1):

    if i == first_vocab_use and not inserted:
        new_lines.append("")
        new_lines.append("# ------------------------------------------------")
        new_lines.append("# RUNTIME VOCABULARY SIZE")
        new_lines.append("# Derived from the existing tokenizer vocabulary.")
        new_lines.append("# No corpus or model architecture is changed.")
        new_lines.append("# ------------------------------------------------")
        new_lines.append(f"vocab_size = {vocab_expr}")
        new_lines.append("")
        inserted = True

    new_lines.append(line)

if not inserted:
    print("ERROR: insertion point was not reached.")
    raise SystemExit(6)

patched = "\n".join(new_lines) + "\n"

MODEL.write_text(
    patched,
    encoding="utf-8"
)

# ------------------------------------------------------------
# SYNTAX CHECK
# ------------------------------------------------------------

print()
print("=" * 72)
print("SYNTAX CHECK")
print("=" * 72)

try:
    py_compile.compile(
        str(MODEL),
        doraise=True
    )
except Exception as e:
    print("SYNTAX ERROR")
    print(e)

    print()
    print("RESTORING BACKUP")
    shutil.copy2(backup, MODEL)
    print("RESTORE COMPLETE")

    raise SystemExit(7)

print("bloom_real.py : SYNTAX_OK")

# ------------------------------------------------------------
# VERIFY THE INSERTION
# ------------------------------------------------------------

check = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

hits = [
    i
    for i, line in enumerate(
        check.splitlines(),
        1
    )
    if re.search(r"\bvocab_size\s*=", line)
]

print()
print("=" * 72)
print("REPAIR RESULT")
print("=" * 72)

print("vocab_size assignments:")
for i in hits:
    print(f"  line {i}: {check.splitlines()[i-1]}")

print()
print("VOCABULARY SOURCE:", vocab_expr)
print("CORPUS MODIFIED: NO")
print("TRAINING CORPUS MODIFIED: NO")
print("VALIDATION CORPUS MODIFIED: NO")
print("ARCHIVES RE-ENABLED: NO")
print("GPT ARCHITECTURE REPLACED: NO")
print()
print("STATUS: VOCAB_SIZE_RUNTIME_REPAIRED")
print("=" * 72)
