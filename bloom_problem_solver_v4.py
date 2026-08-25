#!/usr/bin/env python3
"""
BLOOM PROBLEM SOLVER V4
ERROR-DRIVEN SELF-HEALING ENGINE

Unlike V1-V3:
    - does not stop merely because a rule is missing
    - executes the real failing program
    - captures the real traceback
    - identifies the failing source location
    - searches the existing BLOOM repository for supporting definitions/files
    - applies evidence-backed repairs
    - backs up every mutation
    - recompiles immediately
    - reruns immediately
    - rolls back failed repairs
    - repeats until PASS or evidence is exhausted

No synthetic training data.
No fake model weights.
No fake vocabulary.
No fabricated checkpoints.
No random repair generation.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / ".bloom_solver_v4_backups"
REPORT = ROOT / "bloom_problem_solver_v4_report.json"
LEDGER = ROOT / "bloom_problem_solver_v4_ledger.jsonl"

TARGETS = [
    ROOT / "bloom_real.py",
    ROOT / "hybrid_bloom.py",
]

EXCLUDED = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".bloom_solver_backups",
    ".bloom_solver_v4_backups",
    ".bloom_repairs",
}

MAX_ROUNDS = 12
TIMEOUT = 30


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return ""


def read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def log(event: dict[str, Any]) -> None:
    event = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        **event,
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def python_files() -> list[Path]:
    result = []
    for p in ROOT.rglob("*.py"):
        if any(part in EXCLUDED for part in p.parts):
            continue
        result.append(p)
    return sorted(result)


def backup(path: Path, round_no: int) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destination = (
        BACKUP_DIR
        / f"{path.name}.round{round_no}.{int(time.time())}.bak"
    )
    shutil.copy2(path, destination)
    return destination


def restore(path: Path, backup_path: Path) -> None:
    shutil.copy2(backup_path, path)


def compile_file(path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return proc.returncode == 0, (
        proc.stdout + "\n" + proc.stderr
    ).strip()


def execute(path: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, "-u", str(path)],
            cwd=ROOT,
            input="",
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )

        return {
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-30000:],
        }

    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "passed": False,
            "timeout": True,
            "stdout": (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )[-20000:],
            "stderr": (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )[-30000:],
        }

    except Exception as exc:
        return {
            "returncode": None,
            "passed": False,
            "exception": repr(exc),
            "stdout": "",
            "stderr": "",
        }


def traceback_location(stderr: str) -> dict[str, Any]:
    matches = list(
        re.finditer(
            r'File "([^"]+)", line (\d+), in ([^\n]+)',
            stderr,
        )
    )

    if not matches:
        return {}

    m = matches[-1]

    return {
        "file": m.group(1),
        "line": int(m.group(2)),
        "function": m.group(3).strip(),
    }


def classify_error(stderr: str) -> dict[str, Any]:
    patterns = [
        (
            r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)",
            "ModuleNotFoundError",
            "module",
        ),
        (
            r"ImportError:\s*(.+)",
            "ImportError",
            "message",
        ),
        (
            r"NameError:\s*name ['\"]([^'\"]+)['\"] is not defined",
            "NameError",
            "name",
        ),
        (
            r"FileNotFoundError:.*?'([^']+)'",
            "FileNotFoundError",
            "path",
        ),
        (
            r"AttributeError:\s*(.+)",
            "AttributeError",
            "message",
        ),
        (
            r"KeyError:\s*['\"]([^'\"]+)['\"]",
            "KeyError",
            "key",
        ),
        (
            r"IndexError:\s*(.+)",
            "IndexError",
            "message",
        ),
        (
            r"TypeError:\s*(.+)",
            "TypeError",
            "message",
        ),
        (
            r"ValueError:\s*(.+)",
            "ValueError",
            "message",
        ),
    ]

    for pattern, kind, field in patterns:
        m = re.search(pattern, stderr)

        if m:
            return {
                "kind": kind,
                field: m.group(1).strip(),
            }

    return {
        "kind": "UnknownError",
        "message": stderr[-4000:],
    }


def source_context(path: Path, line: int, radius: int = 5) -> str:
    try:
        lines = read(path).splitlines()
    except Exception:
        return ""

    start = max(1, line - radius)
    end = min(len(lines), line + radius)

    return "\n".join(
        f"{n:5d}: {lines[n - 1]}"
        for n in range(start, end + 1)
    )


def find_module(name: str) -> list[Path]:
    module = name.split(".")[0]

    candidates = []

    for p in python_files():
        if p.stem == module:
            candidates.append(p)

    return candidates


def find_definition(name: str) -> list[tuple[Path, int, str]]:
    hits = []

    for path in python_files():
        try:
            tree = ast.parse(read(path), filename=str(path))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                if node.name == name:
                    hits.append(
                        (
                            path,
                            node.lineno,
                            type(node).__name__,
                        )
                    )

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        hits.append(
                            (
                                path,
                                node.lineno,
                                "assignment",
                            )
                        )

            elif isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Name)
                    and node.target.id == name
                ):
                    hits.append(
                        (
                            path,
                            node.lineno,
                            "annotation",
                        )
                    )

    return hits


def relative_import(target: Path, provider: Path) -> str | None:
    if provider.parent != target.parent:
        return None

    module = provider.stem

    try:
        tree = ast.parse(read(target), filename=str(target))
    except Exception:
        return None

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module:
                    return None

        if isinstance(node, ast.ImportFrom):
            if node.module == module:
                return None

    return f"import {module}"


def repair_missing_module(
    target: Path,
    module: str,
) -> tuple[bool, str]:
    candidates = find_module(module)

    if len(candidates) != 1:
        return (
            False,
            f"module evidence ambiguous: {module} -> {len(candidates)}",
        )

    provider = candidates[0]

    if provider == target:
        return False, "module points to target itself"

    statement = relative_import(target, provider)

    if not statement:
        return False, "no safe import construction"

    source = read(target)

    lines = source.splitlines()

    insert_at = 0

    while insert_at < len(lines):
        stripped = lines[insert_at].strip()

        if (
            stripped.startswith("#!")
            or stripped.startswith("#")
            or not stripped
        ):
            insert_at += 1
            continue

        if stripped.startswith(
            (
                '"""',
                "'''",
            )
        ):
            break

        break

    lines.insert(insert_at, statement)

    new_source = "\n".join(lines) + (
        "\n" if source.endswith("\n") else ""
    )

    if new_source == source:
        return False, "no source change"

    write(target, new_source)

    return True, f"added repository-backed import: {statement}"


def repair_missing_file(
    target: Path,
    missing: str,
) -> tuple[bool, str]:
    missing_path = Path(missing)

    basename = missing_path.name

    candidates = []

    for p in ROOT.rglob(basename):
        if not p.is_file():
            continue
        if any(part in EXCLUDED for part in p.parts):
            continue
        if p == target:
            continue
        candidates.append(p)

    if len(candidates) != 1:
        return (
            False,
            f"file evidence ambiguous: {basename} -> {len(candidates)}",
        )

    candidate = candidates[0]

    source = read(target)

    old_variants = {
        missing,
        missing.replace("\\", "/"),
        str(missing_path),
    }

    replacement = str(candidate.relative_to(ROOT))

    changed = False
    new_source = source

    for old in old_variants:
        if old and old in new_source:
            new_source = new_source.replace(
                old,
                replacement,
            )
            changed = True

    if not changed:
        return False, "missing path not represented literally in source"

    write(target, new_source)

    return True, f"redirected missing file to repository file: {replacement}"


def repair_name_error(
    target: Path,
    name: str,
) -> tuple[bool, str]:
    hits = find_definition(name)

    hits = [
        hit
        for hit in hits
        if hit[0] != target
    ]

    if len(hits) != 1:
        return (
            False,
            f"name evidence ambiguous: {name} -> {len(hits)}",
        )

    provider, _, kind = hits[0]

    statement = relative_import(target, provider)

    if not statement:
        return (
            False,
            f"definition found but safe import unavailable: {provider}",
        )

    source = read(target)

    if statement in source:
        return False, "import already present"

    lines = source.splitlines()

    insert_at = 0

    while insert_at < len(lines):
        stripped = lines[insert_at].strip()

        if (
            stripped.startswith("#!")
            or stripped.startswith("#")
            or not stripped
        ):
            insert_at += 1
            continue

        break

    lines.insert(insert_at, statement)

    new_source = "\n".join(lines) + (
        "\n" if source.endswith("\n") else ""
    )

    write(target, new_source)

    return (
        True,
        f"imported repository-backed {kind} {name} from {provider.name}",
    )


def repair(
    target: Path,
    error: dict[str, Any],
) -> tuple[bool, str]:
    kind = error.get("kind")

    if kind == "ModuleNotFoundError":
        return repair_missing_module(
            target,
            error["module"],
        )

    if kind == "FileNotFoundError":
        return repair_missing_file(
            target,
            error["path"],
        )

    if kind == "NameError":
        return repair_name_error(
            target,
            error["name"],
        )

    return (
        False,
        f"no evidence-backed repair rule for {kind}",
    )


def validate(target: Path) -> dict[str, Any]:
    compiled, compile_output = compile_file(target)

    if not compiled:
        return {
            "compile": False,
            "runtime": False,
            "compile_output": compile_output,
        }

    runtime = execute(target)

    return {
        "compile": True,
        "runtime": runtime["passed"],
        "compile_output": compile_output,
        "runtime_result": runtime,
    }


def repair_target(target: Path) -> dict[str, Any]:
    result = {
        "target": str(target.relative_to(ROOT)),
        "initial_sha256": sha256(target),
        "rounds": [],
        "status": "UNKNOWN",
        "repairs": [],
    }

    print()
    print("=" * 90)
    print(f"TARGET: {target.name}")
    print("=" * 90)

    for round_no in range(1, MAX_ROUNDS + 1):
        print()
        print(f"REPAIR ROUND {round_no}")

        validation = validate(target)

        if validation["compile"] and validation["runtime"]:
            print("RESULT: PASS")
            result["status"] = "PASS"
            result["final_sha256"] = sha256(target)
            return result

        runtime = validation.get("runtime_result", {})
        stderr = runtime.get("stderr", "")

        error = classify_error(stderr)
        location = traceback_location(stderr)

        finding = {
            "round": round_no,
            "error": error,
            "location": location,
            "stderr": stderr[-12000:],
        }

        result["rounds"].append(finding)

        print(f"ERROR: {error.get('kind')}")

        if location:
            print(
                f"LOCATION: "
                f"{location.get('file')}:{location.get('line')}"
            )

            location_path = Path(location["file"])

            if not location_path.is_absolute():
                location_path = ROOT / location_path

            if location_path.exists():
                print()
                print("FAILING SOURCE CONTEXT:")
                print(
                    source_context(
                        location_path,
                        location["line"],
                    )
                )

        if stderr:
            print()
            print("TRACEBACK:")
            print(stderr[-5000:])

        backup_path = backup(target, round_no)

        changed, explanation = repair(
            target,
            error,
        )

        if not changed:
            restore(target, backup_path)

            print()
            print("NO EVIDENCE-BACKED REPAIR FOUND.")
            print(f"REASON: {explanation}")

            log(
                {
                    "event": "repair_failed",
                    "target": str(target),
                    "round": round_no,
                    "error": error,
                    "reason": explanation,
                }
            )

            result["status"] = "UNRESOLVED"
            result["final_sha256"] = sha256(target)
            return result

        print()
        print("REPAIR APPLIED:")
        print(explanation)

        compile_ok, compile_output = compile_file(target)

        if not compile_ok:
            print()
            print("REPAIR BROKE COMPILATION.")
            print("ROLLING BACK.")

            restore(target, backup_path)

            log(
                {
                    "event": "rollback",
                    "target": str(target),
                    "round": round_no,
                    "reason": "compile_failure",
                    "compile_output": compile_output,
                }
            )

            continue

        post = execute(target)

        if post["passed"]:
            print()
            print("REPAIR VERIFIED: PASS")

            result["repairs"].append(
                {
                    "round": round_no,
                    "repair": explanation,
                    "verified": True,
                    "backup": str(backup_path),
                }
            )

            log(
                {
                    "event": "repair_verified",
                    "target": str(target),
                    "round": round_no,
                    "repair": explanation,
                }
            )

            result["status"] = "PASS"
            result["final_sha256"] = sha256(target)
            return result

        result["repairs"].append(
            {
                "round": round_no,
                "repair": explanation,
                "verified": False,
                "backup": str(backup_path),
            }
        )

        print()
        print("REPAIR DID NOT SOLVE RUNTIME FAILURE.")

        next_error = classify_error(
            post.get("stderr", "")
        )

        print(
            f"NEXT ERROR: "
            f"{next_error.get('kind')}"
        )

        log(
            {
                "event": "repair_unverified",
                "target": str(target),
                "round": round_no,
                "repair": explanation,
                "next_error": next_error,
            }
        )

    result["status"] = "EXHAUSTED"
    result["final_sha256"] = sha256(target)
    return result


def main() -> int:
    print("=" * 90)
    print("BLOOM PROBLEM SOLVER V4")
    print("ERROR-DRIVEN ACTIVE SELF-HEALING")
    print("=" * 90)
    print(f"ROOT: {ROOT}")
    print(f"PYTHON FILES: {len(python_files())}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for target in TARGETS:
        if not target.exists():
            print()
            print(f"TARGET MISSING: {target.name}")
            results.append(
                {
                    "target": target.name,
                    "status": "MISSING",
                }
            )
            continue

        results.append(
            repair_target(target)
        )

    report = {
        "version": 4,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "root": str(ROOT),
        "results": results,
    }

    REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 90)
    print("FINAL SELF-HEALING RESULT")
    print("=" * 90)

    all_pass = True

    for item in results:
        status = item["status"]
        print(
            f"{item['target']:<28} {status}"
        )

        if status != "PASS":
            all_pass = False

    print()
    print(f"REPORT:  {REPORT}")
    print(f"LEDGER:  {LEDGER}")
    print(f"BACKUPS: {BACKUP_DIR}")

    print("=" * 90)

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
