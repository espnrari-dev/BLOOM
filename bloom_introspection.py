#!/usr/bin/env python3

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"
STATE = ROOT / "bloom_introspection.json"


REQUIRED = [
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
    "generate",
    "retrieve",
]


def source_hash(path):
    raw = path.read_bytes()

    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def symbol_name(node):

    if isinstance(node, ast.FunctionDef):
        return node.name

    if isinstance(node, ast.AsyncFunctionDef):
        return node.name

    if isinstance(node, ast.ClassDef):
        return node.name

    if isinstance(node, ast.Assign):

        names = []

        for target in node.targets:

            if isinstance(target, ast.Name):
                names.append(target.id)

        return ", ".join(names)

    if isinstance(node, ast.AnnAssign):

        if isinstance(node.target, ast.Name):
            return node.target.id

    return type(node).__name__


def inspect_source():

    if not MODEL.exists():

        return {
            "exists": False,
            "error": "bloom_real.py does not exist",
        }

    source = MODEL.read_text(
        encoding="utf-8",
        errors="replace",
    )

    result = {
        "exists": True,
        "source": source_hash(MODEL),
        "parse": None,
        "top_level": [],
        "functions": {},
        "classes": {},
        "definitions": {},
        "references": {},
        "required_symbols": {},
    }

    try:
        tree = ast.parse(source)
        result["parse"] = {
            "success": True,
        }

    except Exception as e:

        result["parse"] = {
            "success": False,
            "exception": type(e).__name__,
            "message": str(e),
        }

        return result

    for node in tree.body:

        result["top_level"].append({
            "line": node.lineno,
            "end_line": getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
            "type": type(node).__name__,
            "name": symbol_name(node),
        })

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            result["functions"][node.name] = {
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
            }

        elif isinstance(node, ast.ClassDef):

            result["classes"][node.name] = {
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
            }

    for node in tree.body:

        if isinstance(node, ast.Assign):

            for target in node.targets:

                if isinstance(target, ast.Name):

                    result["definitions"][
                        target.id
                    ] = node.lineno

        elif isinstance(node, ast.AnnAssign):

            if isinstance(node.target, ast.Name):

                result["definitions"][
                    node.target.id
                ] = node.lineno

        elif isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):

            result["definitions"][
                node.name
            ] = node.lineno

    references = {}

    for node in ast.walk(tree):

        if not isinstance(node, ast.Name):
            continue

        if not isinstance(node.ctx, ast.Load):
            continue

        references.setdefault(
            node.id,
            [],
        ).append(node.lineno)

    result["references"] = references

    for name in REQUIRED:

        result["required_symbols"][name] = {
            "defined": name in result["definitions"],
            "definition_line":
                result["definitions"].get(name),
            "references":
                result["references"].get(
                    name,
                    [],
                ),
        }

    return result


def run_import_probe():

    probe = """
import sys
sys.path.insert(0, r'%s')

try:
    import bloom_real

    print("IMPORT_SUCCESS")

    names = [
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

    for name in names:

        if hasattr(bloom_real, name):

            value = getattr(
                bloom_real,
                name,
            )

            try:
                size = len(value)
            except Exception:
                size = None

            shape = getattr(
                value,
                "shape",
                None,
            )

            print(
                "STATE",
                name,
                type(value).__name__,
                size,
                shape,
            )

        else:

            print(
                "MISSING",
                name,
            )

except Exception as e:

    print(
        "IMPORT_FAILURE",
        type(e).__name__,
        str(e),
    )
""" % str(ROOT)

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            probe,
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )

    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def build_state():

    started = time.time()

    state = {
        "timestamp": time.time(),
        "root": str(ROOT),
        "model": inspect_source(),
        "import_probe": run_import_probe(),
    }

    state["duration"] = time.time() - started

    STATE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return state


if __name__ == "__main__":

    state = build_state()

    print("=" * 80)
    print("BLOOM INTROSPECTION")
    print("=" * 80)

    model = state["model"]

    print(
        "MODEL:",
        MODEL,
    )

    print(
        "SHA256:",
        model.get(
            "source",
            {},
        ).get(
            "sha256"
        ),
    )

    parse = model.get(
        "parse",
        {},
    )

    print(
        "PARSE:",
        "SUCCESS"
        if parse.get("success")
        else "FAILED",
    )

    print()
    print("REQUIRED SYMBOLS")

    for name, info in model.get(
        "required_symbols",
        {},
    ).items():

        print(
            f"{name:<22}",
            f"defined={info['defined']}",
            f"line={info['definition_line']}",
            f"refs={info['references']}",
        )

    print()
    print("IMPORT PROBE")

    probe = state["import_probe"]

    print(probe["stdout"])

    if probe["stderr"]:
        print(
            "--- STDERR ---"
        )
        print(probe["stderr"])

    print(
        "STATE WRITTEN:",
        STATE,
    )
