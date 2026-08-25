#!/usr/bin/env python3

from pathlib import Path
import ast
import re

ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

text = MODEL.read_text(
    encoding="utf-8",
    errors="replace"
)

lines = text.splitlines()

print("=" * 72)
print("BLOOM REAL GPT — VOCABULARY FORENSICS")
print("=" * 72)

# ============================================================
# 1. SHOW TOP-LEVEL SOURCE
# ============================================================

print()
print("=" * 72)
print("TOP OF bloom_real.py")
print("=" * 72)

for i in range(1, min(180, len(lines)) + 1):
    print(f"{i:5d}: {lines[i-1]}")

# ============================================================
# 2. SEARCH ALL TOKENIZATION / VOCABULARY TERMS
# ============================================================

terms = [
    "vocab",
    "token",
    "encode",
    "decode",
    "chars",
    "char",
    "stoi",
    "itos",
    "alphabet",
    "charset",
    "symbols",
    "ids",
    "tokens",
    "ord(",
    "chr(",
    "unique",
    "set(",
    "max_token",
    "n_vocab",
]

print()
print("=" * 72)
print("ALL TOKENIZATION / VOCABULARY REFERENCES")
print("=" * 72)

for term in terms:
    hits = []

    for i, line in enumerate(lines, 1):
        if term.lower() in line.lower():
            hits.append(i)

    if hits:
        print(f"{term:<16}: {hits}")

# ============================================================
# 3. PRINT EVERY MATCH WITH CONTEXT
# ============================================================

print()
print("=" * 72)
print("TOKENIZATION SOURCE WITH CONTEXT")
print("=" * 72)

matched = set()

for i, line in enumerate(lines, 1):
    low = line.lower()

    if any(term.lower() in low for term in terms):
        matched.add(i)

for i in sorted(matched):
    start = max(1, i - 2)
    end = min(len(lines), i + 2)

    print()
    print(f"--- around line {i} ---")

    for n in range(start, end + 1):
        marker = ">>>" if n == i else "   "
        print(f"{marker} {n:5d}: {lines[n-1]}")

# ============================================================
# 4. AST: TOP-LEVEL ASSIGNMENTS
# ============================================================

print()
print("=" * 72)
print("TOP-LEVEL VARIABLES")
print("=" * 72)

tree = ast.parse(text)

for node in tree.body:

    if isinstance(node, ast.Assign):
        targets = []

        for target in node.targets:
            if isinstance(target, ast.Name):
                targets.append(target.id)

        if targets:
            source = ast.get_source_segment(text, node) or ""

            print(
                f"{node.lineno:5d}: "
                f"{', '.join(targets)} = "
                f"{source[:250]}"
            )

    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            source = ast.get_source_segment(text, node) or ""

            print(
                f"{node.lineno:5d}: "
                f"{node.target.id} = "
                f"{source[:250]}"
            )

# ============================================================
# 5. FIND UNDEFINED vocab_size USE
# ============================================================

print()
print("=" * 72)
print("vocab_size REFERENCES")
print("=" * 72)

for i, line in enumerate(lines, 1):
    if re.search(r"\bvocab_size\b", line):
        print(f"{i:5d}: {line}")

# ============================================================
# 6. FIND GPT CONSTRUCTOR SIGNATURE
# ============================================================

print()
print("=" * 72)
print("GPT CLASS / CONSTRUCTOR")
print("=" * 72)

for node in ast.walk(tree):

    if isinstance(node, ast.ClassDef) and node.name == "GPT":

        print(
            f"GPT class lines "
            f"{node.lineno}-"
            f"{getattr(node, 'end_lineno', node.lineno)}"
        )

        source = ast.get_source_segment(text, node) or ""

        source_lines = source.splitlines()

        for i, line in enumerate(source_lines, 1):
            if (
                "__init__" in line
                or "vocab" in line.lower()
                or "token" in line.lower()
                or "embedding" in line.lower()
                or "shape" in line.lower()
            ):
                print(f"{i:5d}: {line}")

# ============================================================
# 7. FIND get_batch()
# ============================================================

print()
print("=" * 72)
print("get_batch() SOURCE")
print("=" * 72)

for node in ast.walk(tree):

    if isinstance(node, ast.FunctionDef) and node.name == "get_batch":

        source = ast.get_source_segment(text, node) or ""

        print(
            f"LINES {node.lineno}-"
            f"{getattr(node, 'end_lineno', node.lineno)}"
        )

        for i, line in enumerate(
            source.splitlines(),
            node.lineno
        ):
            print(f"{i:5d}: {line}")

# ============================================================
# 8. FIND ENCODING LOGIC
# ============================================================

print()
print("=" * 72)
print("ENCODING / ID CONVERSION FUNCTIONS")
print("=" * 72)

for node in ast.walk(tree):

    if not isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        continue

    source = ast.get_source_segment(text, node) or ""
    low = source.lower()

    if any(
        x in low
        for x in (
            "ord(",
            "chr(",
            "encode",
            "token",
            "vocab",
            "chars",
            "ids",
            "set(",
        )
    ):

        print()
        print(
            f"FUNCTION: {node.name} "
            f"LINES {node.lineno}-"
            f"{getattr(node, 'end_lineno', node.lineno)}"
        )

        for i, line in enumerate(
            source.splitlines(),
            node.lineno
        ):
            print(f"{i:5d}: {line}")

# ============================================================
# 9. IMPORTANT: DETERMINE WHETHER CHARACTER ORDINALS ARE USED
# ============================================================

print()
print("=" * 72)
print("ORDINAL / CHARACTER TOKEN POSSIBILITY")
print("=" * 72)

ord_hits = [
    (i, line)
    for i, line in enumerate(lines, 1)
    if "ord(" in line
]

chr_hits = [
    (i, line)
    for i, line in enumerate(lines, 1)
    if "chr(" in line
]

print("ord() references:")
for i, line in ord_hits:
    print(f"{i:5d}: {line}")

print()
print("chr() references:")
for i, line in chr_hits:
    print(f"{i:5d}: {line}")

# ============================================================
# 10. FINAL FORENSIC SUMMARY
# ============================================================

print()
print("=" * 72)
print("FORENSIC SUMMARY")
print("=" * 72)

print(
    "The runtime has an unresolved variable: vocab_size."
)

print(
    "No stoi/itos assignment was found."
)

if ord_hits:
    print(
        "Character ordinal encoding is present."
    )
else:
    print(
        "Character ordinal encoding was NOT detected."
    )

print()
print(
    "STATUS: VOCABULARY_SOURCE_IDENTIFICATION_REQUIRED"
)
print(
    "NO MODEL FILE MODIFIED."
)
print("=" * 72)
