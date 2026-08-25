#!/usr/bin/env python3

from pathlib import Path
import ast
import re

ROOT = Path.home() / "BLOOM"

files = sorted(
    p for p in ROOT.glob("*.py")
    if p.name != "bloom_architecture_probe.py"
)

print("=" * 72)
print("BLOOM ARCHITECTURE PROBE")
print("=" * 72)

for path in files:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except Exception as e:
        print(f"\n{path.name}: PARSE_ERROR: {e}")
        continue

    classes = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]

    functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    imports = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(
                alias.name
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    interesting = [
        x for x in functions
        if any(
            k in x.lower()
            for k in (
                "train",
                "fit",
                "learn",
                "model",
                "generate",
                "predict",
                "forward",
                "loss",
            )
        )
    ]

    print()
    print("-" * 72)
    print(path.name)
    print("-" * 72)

    print(f"Lines      : {len(text.splitlines()):,}")
    print(f"Classes    : {', '.join(classes) if classes else 'none'}")
    print(
        "Functions  : "
        + (", ".join(functions) if functions else "none")
    )

    if interesting:
        print(
            "ML-related : "
            + ", ".join(interesting)
        )

    if imports:
        print(
            "Imports    : "
            + ", ".join(sorted(set(imports)))
        )

print()
print("=" * 72)
print("TARGET FILE SCAN")
print("=" * 72)

patterns = [
    r"torch",
    r"tensorflow",
    r"transformers",
    r"numpy",
    r"embedding",
    r"token",
    r"loss",
    r"optimizer",
    r"backprop",
    r"gradient",
    r"attention",
    r"forward",
    r"generate",
    r"predict",
]

for path in files:
    try:
        text = path.read_text(
            encoding="utf-8"
        ).lower()
    except Exception:
        continue

    hits = [
        pattern
        for pattern in patterns
        if re.search(pattern, text)
    ]

    if hits:
        print(
            f"{path.name:<35} "
            + ", ".join(hits)
        )

print()
print("=" * 72)
print("PROBE COMPLETE")
print("=" * 72)
print("Use the output to identify BLOOM's actual training path.")
print("=" * 72)
