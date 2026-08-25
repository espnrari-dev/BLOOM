#!/usr/bin/env python3

from pathlib import Path
import ast
import hashlib
import re
import sys
import traceback

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"

print("=" * 80)
print("BLOOM REAL GPT — FULL EXECUTION-PATH FORENSICS")
print("=" * 80)
print("MODE: READ-ONLY")
print("MODEL MODIFICATION: NONE")

# ================================================================
# FILE INVENTORY
# ================================================================

print("\n" + "=" * 80)
print("1. FILE INVENTORY")
print("=" * 80)

for p in [MODEL, TRAIN, VALID]:
    if p.exists():
        raw = p.read_bytes()
        print(f"{p.name}")
        print(f"  exists : YES")
        print(f"  bytes  : {len(raw):,}")
        print(f"  sha256 : {hashlib.sha256(raw).hexdigest()}")
    else:
        print(f"{p.name}")
        print("  exists : NO")

if not MODEL.exists():
    print("\nFATAL: bloom_real.py does not exist.")
    raise SystemExit(1)

# ================================================================
# SOURCE PARSE
# ================================================================

source = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

print("\n" + "=" * 80)
print("2. SOURCE INTEGRITY / AST")
print("=" * 80)

try:
    tree = ast.parse(source)
    print("AST PARSE: SUCCESS")
except Exception as e:
    print("AST PARSE: FAILED")
    print(type(e).__name__, e)
    raise SystemExit(1)

# ================================================================
# TOP-LEVEL EXECUTION ORDER
# ================================================================

print("\n" + "=" * 80)
print("3. TOP-LEVEL EXECUTION ORDER")
print("=" * 80)

top_nodes = []

for node in tree.body:
    name = None

    if isinstance(node, ast.FunctionDef):
        name = f"def {node.name}()"

    elif isinstance(node, ast.ClassDef):
        name = f"class {node.name}"

    elif isinstance(node, ast.Assign):
        names = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
        name = "assign: " + ", ".join(names)

    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            name = f"assign: {node.target.id}"

    elif isinstance(node, ast.Expr):
        name = "expression"

    else:
        name = type(node).__name__

    top_nodes.append(
        (
            node.lineno,
            getattr(node, "end_lineno", node.lineno),
            name
        )
    )

for i, item in enumerate(top_nodes, 1):
    print(
        f"{i:3d}. lines {item[0]:4d}-{item[1]:4d}  {item[2]}"
    )

# ================================================================
# FUNCTION / CLASS INVENTORY
# ================================================================

print("\n" + "=" * 80)
print("4. FUNCTIONS / CLASSES")
print("=" * 80)

functions = {}
classes = {}

for node in ast.walk(tree):

    if isinstance(node, ast.FunctionDef):
        functions[node.name] = (
            node.lineno,
            getattr(node, "end_lineno", node.lineno)
        )

    elif isinstance(node, ast.ClassDef):
        classes[node.name] = (
            node.lineno,
            getattr(node, "end_lineno", node.lineno)
        )

for name, span in sorted(functions.items(), key=lambda x: x[1][0]):
    print(
        f"FUNCTION {name:<24} "
        f"lines {span[0]}-{span[1]}"
    )

for name, span in sorted(classes.items(), key=lambda x: x[1][0]):
    print(
        f"CLASS    {name:<24} "
        f"lines {span[0]}-{span[1]}"
    )

# ================================================================
# GLOBAL SYMBOL DEFINITIONS
# ================================================================

print("\n" + "=" * 80)
print("5. TOP-LEVEL SYMBOL DEFINITIONS")
print("=" * 80)

defined_globals = {}

for node in tree.body:

    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                defined_globals[target.id] = node.lineno

    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            defined_globals[node.target.id] = node.lineno

    elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        defined_globals[node.name] = node.lineno

for name, line in sorted(
    defined_globals.items(),
    key=lambda x: x[1]
):
    print(f"{line:5d}: {name}")

# ================================================================
# REQUIRED RUNTIME SYMBOLS
# ================================================================

required = [
    "load_text",
    "stoi",
    "itos",
    "vocab_size",
    "data",
    "validation_data",
    "VALIDATION_TEXT",
    "get_batch",
    "GPT",
    "model",
    "params",
    "adam_m",
    "adam_v",
    "best_loss",
    "train",
    "generate",
    "retrieve",
]

print("\n" + "=" * 80)
print("6. REQUIRED RUNTIME SYMBOL DEFINITIONS")
print("=" * 80)

for name in required:
    if name in defined_globals:
        print(
            f"{name:<22}: DEFINED "
            f"(line {defined_globals[name]})"
        )
    else:
        print(
            f"{name:<22}: NOT_TOP_LEVEL_DEFINED"
        )

# ================================================================
# CALL GRAPH / CALL SITES
# ================================================================

print("\n" + "=" * 80)
print("7. IMPORTANT CALL SITES")
print("=" * 80)

interesting_calls = [
    "load_text",
    "get_batch",
    "forward",
    "backward",
    "generate",
    "evaluate",
    "save_ckpt",
    "collect_params",
    "model",
    "GPT",
]

for node in ast.walk(tree):

    if isinstance(node, ast.Call):

        fn = None

        if isinstance(node.func, ast.Name):
            fn = node.func.id

        elif isinstance(node.func, ast.Attribute):
            fn = node.func.attr

        if fn in interesting_calls:
            print(
                f"line {node.lineno:4d}: {fn}()"
            )

# ================================================================
# DATA PIPELINE STATIC ANALYSIS
# ================================================================

print("\n" + "=" * 80)
print("8. DATA PIPELINE")
print("=" * 80)

data_patterns = [
    r"my_texts\.txt",
    r"bloom_train_v2\.txt",
    r"bloom_valid_v2\.txt",
    r"archives",
    r"read_text",
    r"load_text",
    r"stoi",
    r"itos",
    r"vocab_size",
    r"np\.array",
    r"np\.asarray",
    r"data\s*=",
    r"validation_data",
    r"get_batch",
]

lines = source.splitlines()

for pattern in data_patterns:
    hits = [
        i
        for i, line in enumerate(lines, 1)
        if re.search(pattern, line, re.IGNORECASE)
    ]

    print(
        f"{pattern:<28}: "
        f"{hits if hits else 'NONE'}"
    )

# ================================================================
# GET_BATCH DEPENDENCIES
# ================================================================

print("\n" + "=" * 80)
print("9. get_batch() DEPENDENCY ANALYSIS")
print("=" * 80)

if "get_batch" in functions:

    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
        and n.name == "get_batch"
    )

    segment = ast.get_source_segment(source, node) or ""

    print(segment)

    names_loaded = sorted({
        n.id
        for n in ast.walk(node)
        if isinstance(n, ast.Name)
        and isinstance(n.ctx, ast.Load)
    })

    print("\nREADS GLOBALS / EXTERNAL NAMES:")

    for name in names_loaded:
        if name not in {
            "np",
            "range",
            "len",
        }:
            print(
                f"  {name:<24} "
                f"{'TOP_LEVEL_DEFINED' if name in defined_globals else 'UNRESOLVED_STATIC'}"
            )

# ================================================================
# GPT CONSTRUCTOR DEPENDENCIES
# ================================================================

print("\n" + "=" * 80)
print("10. GPT CONSTRUCTOR")
print("=" * 80)

if "GPT" in classes:

    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
        and n.name == "GPT"
    )

    print(
        ast.get_source_segment(source, node) or ""
    )

# ================================================================
# FORWARD / BACKWARD
# ================================================================

print("\n" + "=" * 80)
print("11. FORWARD / BACKWARD / LOSS")
print("=" * 80)

for name in [
    "forward",
    "backward",
]:
    if name in functions:

        node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == name
        )

        print(
            f"\n--- {name}() ---"
        )

        segment = (
            ast.get_source_segment(source, node)
            or ""
        )

        print(segment)

# ================================================================
# TRAINING LOOP
# ================================================================

print("\n" + "=" * 80)
print("12. TRAINING LOOP")
print("=" * 80)

for keyword in [
    "MAX_ITERS",
    "EVAL_EVERY",
    "best_loss",
    "adam_m",
    "adam_v",
    "save_ckpt",
    "for step",
    "range(MAX_ITERS)",
]:
    hits = [
        (i, line)
        for i, line in enumerate(lines, 1)
        if keyword.lower() in line.lower()
    ]

    print(f"\n[{keyword}]")

    if hits:
        for i, line in hits:
            print(f"{i:5d}: {line}")
    else:
        print("  NONE")

# ================================================================
# CHECKPOINTING
# ================================================================

print("\n" + "=" * 80)
print("13. CHECKPOINTING")
print("=" * 80)

if "save_ckpt" in functions:

    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
        and n.name == "save_ckpt"
    )

    print(
        ast.get_source_segment(source, node)
        or ""
    )

# ================================================================
# EVALUATION
# ================================================================

print("\n" + "=" * 80)
print("14. EVALUATION / VALIDATION")
print("=" * 80)

evaluation_terms = [
    "validation",
    "validation_data",
    "test_x",
    "test_y",
    "test_loss",
    "eval",
    "evaluate",
]

for term in evaluation_terms:

    hits = [
        (i, line)
        for i, line in enumerate(lines, 1)
        if term.lower() in line.lower()
    ]

    print(f"\n[{term}]")

    for i, line in hits:
        print(f"{i:5d}: {line}")

# ================================================================
# GENERATION
# ================================================================

print("\n" + "=" * 80)
print("15. GENERATION")
print("=" * 80)

if "generate" in functions:

    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
        and n.name == "generate"
    )

    print(
        ast.get_source_segment(source, node)
        or ""
    )

# ================================================================
# STATIC UNRESOLVED-NAME ANALYSIS
# ================================================================

print("\n" + "=" * 80)
print("16. STATIC UNRESOLVED NAME ANALYSIS")
print("=" * 80)

# This is deliberately conservative.
# It reports names read in top-level executable code that are not:
#   - defined globally
#   - imported
#   - obvious Python/NumPy builtins
#
# It does NOT claim these are runtime failures.

imports = set()

for node in ast.walk(tree):

    if isinstance(node, ast.Import):

        for alias in node.names:
            imports.add(
                alias.asname or alias.name.split(".")[0]
            )

    elif isinstance(node, ast.ImportFrom):

        for alias in node.names:
            imports.add(
                alias.asname or alias.name
            )

builtin_names = set(dir(__builtins__))

obvious = {
    "np",
    "math",
    "random",
    "time",
    "sys",
    "pathlib",
    "glob",
    "pickle",
    "True",
    "False",
    "None",
}

unresolved = {}

for node in tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.ClassDef,
            ast.Import,
            ast.ImportFrom,
        )
    ):
        continue

    for child in ast.walk(node):

        if isinstance(child, ast.Name):
            if isinstance(child.ctx, ast.Load):

                name = child.id

                if (
                    name not in defined_globals
                    and name not in imports
                    and name not in builtin_names
                    and name not in obvious
                ):
                    unresolved.setdefault(
                        name,
                        child.lineno
                    )

if unresolved:

    for name, line in sorted(
        unresolved.items(),
        key=lambda x: x[1]
    ):
        print(
            f"{line:5d}: {name}"
        )
else:
    print("NONE")

# ================================================================
# ACTUAL IMPORT TEST
# ================================================================
#
# This is the first point where execution is allowed.
#
# IMPORTANT:
# bloom_real.py currently performs top-level model construction.
# Therefore this test is observational only. We do NOT alter sys.modules,
# source, environment, or globals to make it pass.
#
# ================================================================

print("\n" + "=" * 80)
print("17. ACTUAL IMPORT TEST")
print("=" * 80)

sys.path.insert(0, str(ROOT))

try:

    import bloom_real

    print("IMPORT: SUCCESS")

except Exception as e:

    print("IMPORT: FAILED")
    print(
        f"EXCEPTION: {type(e).__name__}: {e}"
    )

    print("\nTRACEBACK:")
    traceback.print_exc()

    print("\nIMPORTANT:")
    print(
        "This is an OBSERVED runtime failure at the exact "
        "execution point shown above."
    )

    bloom_real = None

# ================================================================
# RUNTIME STATE IF IMPORT SUCCEEDS
# ================================================================

if bloom_real is not None:

    print("\n" + "=" * 80)
    print("18. RUNTIME SYMBOL STATE")
    print("=" * 80)

    runtime_names = [
        "TRAIN_TEXT",
        "VALIDATION_TEXT",
        "stoi",
        "itos",
        "vocab_size",
        "data",
        "validation_data",
        "model",
        "params",
        "adam_m",
        "adam_v",
        "best_loss",
    ]

    for name in runtime_names:

        if hasattr(bloom_real, name):

            value = getattr(
                bloom_real,
                name
            )

            if isinstance(value, str):
                desc = (
                    f"str chars={len(value):,}"
                )

            elif hasattr(value, "shape"):
                desc = (
                    f"{type(value).__name__} "
                    f"shape={value.shape} "
                    f"dtype={getattr(value, 'dtype', None)}"
                )

            elif hasattr(value, "__len__"):
                try:
                    desc = (
                        f"{type(value).__name__} "
                        f"len={len(value):,}"
                    )
                except Exception:
                    desc = type(value).__name__

            else:
                desc = repr(value)

            print(
                f"{name:<22}: PRESENT | {desc}"
            )

        else:

            print(
                f"{name:<22}: ABSENT"
            )

# ================================================================
# FINAL CLASSIFICATION
# ================================================================

print("\n" + "=" * 80)
print("19. FORENSIC CLASSIFICATION")
print("=" * 80)

print("""
OBSERVED:
  Facts directly established by source inspection or actual execution.

INFERRED:
  Conclusions supported by source structure but not executed.

UNKNOWN:
  Behavior that cannot honestly be established yet.

This report intentionally does NOT call any single observed exception
the "final blocker." It identifies the execution boundary actually
reached and maps what remains unverified.
""")

print("=" * 80)
print("END OF READ-ONLY FORENSICS")
print("=" * 80)
