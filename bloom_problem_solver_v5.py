#!/usr/bin/env python3

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKUP = ROOT / ".bloom_solver_v5_backups"
REPORT = ROOT / "bloom_problem_solver_v5_report.json"
LEDGER = ROOT / "bloom_problem_solver_v5_ledger.jsonl"

TARGETS = [
    ROOT / "bloom_real.py",
    ROOT / "hybrid_bloom.py",
]

TIMEOUT = 45
MAX_ROUNDS = 15


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def log(obj):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    **obj,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def backup(path, tag):
    BACKUP.mkdir(parents=True, exist_ok=True)
    out = BACKUP / f"{path.name}.{tag}.{int(time.time())}.bak"
    shutil.copy2(path, out)
    return out


def restore(path, backup):
    shutil.copy2(backup, path)


def compile_file(path):
    p = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return p.returncode == 0, p.stdout + p.stderr


def run_file(path):
    try:
        p = subprocess.run(
            [sys.executable, "-u", str(path)],
            cwd=ROOT,
            input="",
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )

        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-30000:],
        }

    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "returncode": None,
            "timeout": True,
            "stdout": (
                e.stdout.decode(errors="replace")
                if isinstance(e.stdout, bytes)
                else (e.stdout or "")
            )[-20000:],
            "stderr": (
                e.stderr.decode(errors="replace")
                if isinstance(e.stderr, bytes)
                else (e.stderr or "")
            )[-30000:],
        }


def traceback_location(stderr):
    hits = list(
        re.finditer(
            r'File "([^"]+)", line (\d+), in ([^\n]+)',
            stderr,
        )
    )

    if not hits:
        return None

    m = hits[-1]

    return {
        "file": m.group(1),
        "line": int(m.group(2)),
        "function": m.group(3).strip(),
    }


def patch_bloom_best_llm():
    """
    Concrete repair for the observed failure:

        h[t] @ Whh

    h has width 128 while Whh expects width 256.

    The actual recurrent matrix defines the state width.
    Therefore the initial hidden state must be constructed
    using Whh.shape[0], not the stale global 'hidden'.
    """

    path = ROOT / "bloom_best_llm.py"
    source = path.read_text(encoding="utf-8")

    old = "np.zeros((batch,hidden))"
    new = "np.zeros((batch,Whh.shape[0]))"

    if old not in source:
        return False, "target expression not present"

    if new in source:
        return False, "repair already present"

    backup_path = backup(path, "hidden_dim")

    patched = source.replace(old, new)

    path.write_text(patched, encoding="utf-8")

    ok, err = compile_file(path)

    if not ok:
        restore(path, backup_path)
        return False, "rollback: bloom_best_llm compile failure"

    return (
        True,
        "fixed recurrent initial-state width using Whh.shape[0]",
    )


def patch_hybrid_market_guard():
    """
    Concrete repair for observed:

        ZeroDivisionError

    at market_signal() because MARKET is true while
    closes/volumes contain no observations.

    No synthetic market data is created.

    If no real market dataset exists, MARKET is disabled so
    the program does not manufacture a market condition.
    """

    path = ROOT / "hybrid_bloom.py"
    source = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except Exception as e:
        return False, f"hybrid AST failure: {e}"

    closes_name = "closes"
    volumes_name = "volumes"

    market_assignments = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in {"MARKET", "closes", "volumes"}:
                        market_assignments.append(node)

    marker = "# BLOOM_V5_REAL_DATA_GUARD"

    if marker in source:
        return False, "market data guard already present"

    guard = (
        "\n"
        f"{marker}\n"
        "if MARKET and (not closes or not volumes):\n"
        "    MARKET = False\n"
        "\n"
    )

    # Insert immediately before the first market_signal definition.
    match = re.search(
        r"(?m)^def\s+market_signal\s*\(",
        source,
    )

    if not match:
        return False, "market_signal definition not found"

    backup_path = backup(path, "market_guard")

    patched = source[:match.start()] + guard + source[match.start():]

    path.write_text(patched, encoding="utf-8")

    ok, err = compile_file(path)

    if not ok:
        restore(path, backup_path)
        return False, "rollback: hybrid compile failure"

    return (
        True,
        "disabled MARKET only when real closes/volumes are empty; no synthetic data created",
    )


def apply_known_repairs(target):
    repairs = []

    if target.name == "bloom_real.py":
        changed, msg = patch_bloom_best_llm()

        if changed:
            repairs.append(msg)

    if target.name == "hybrid_bloom.py":
        changed, msg = patch_hybrid_market_guard()

        if changed:
            repairs.append(msg)

    return repairs


def repair_bloom_real_import(target):
    """
    If bloom_real reaches a NameError for vocab_size again,
    derive it from the actual vocabulary object in bloom_best_llm
    rather than copying an unrelated scalar.
    """

    source = target.read_text(encoding="utf-8")

    if "vocab_size," not in source:
        return False, "vocab_size call site not present"

    # Already fixed if an explicit local definition exists.
    if re.search(r"(?m)^\s*vocab_size\s*=", source):
        return False, "vocab_size already defined"

    if "import bloom_best_llm" not in source:
        return False, "bloom_best_llm import absent"

    # Use the real model vocabulary size if available.
    insertion = (
        "\n"
        "# BLOOM_V5_REAL_VOCAB_SIZE\n"
        "vocab_size = int(getattr(bloom_best_llm, 'vocab_size'))\n"
        "\n"
    )

    # Put after import bloom_best_llm.
    pos = source.find("import bloom_best_llm")

    if pos < 0:
        return False, "import location not found"

    line_end = source.find("\n", pos)

    if line_end < 0:
        line_end = len(source)

    backup_path = backup(target, "vocab_size")

    patched = (
        source[:line_end + 1]
        + insertion
        + source[line_end + 1:]
    )

    target.write_text(patched, encoding="utf-8")

    ok, _ = compile_file(target)

    if not ok:
        restore(target, backup_path)
        return False, "rollback: vocab_size compile failure"

    return True, "derived vocab_size from bloom_best_llm"


def execute_repair_loop(target):
    result = {
        "target": target.name,
        "rounds": [],
        "repairs": [],
        "status": "UNRESOLVED",
        "initial_sha256": sha256(target),
    }

    print()
    print("=" * 90)
    print(f"ACTIVE TARGET: {target.name}")
    print("=" * 90)

    # First apply the two known concrete repairs.
    known = apply_known_repairs(target)

    for repair in known:
        print(f"[KNOWN REPAIR] {repair}")
        result["repairs"].append(repair)

    for round_no in range(1, MAX_ROUNDS + 1):
        print()
        print(f"EXECUTION ROUND {round_no}")

        compiled, compile_output = compile_file(target)

        if not compiled:
            print("COMPILE FAILURE")
            print(compile_output[-5000:])
            result["status"] = "COMPILE_FAILURE"
            break

        run = run_file(target)

        if run["ok"]:
            print("RUNTIME: PASS")
            result["status"] = "PASS"
            break

        stderr = run.get("stderr", "")

        location = traceback_location(stderr)

        print(
            f"RUNTIME: FAIL"
            f"  rc={run.get('returncode')}"
        )

        if location:
            print(
                f"FAILURE: {location['file']}:{location['line']}"
            )

        # bloom_real.py -> vocab_size
        if (
            target.name == "bloom_real.py"
            and "NameError: name 'vocab_size' is not defined" in stderr
        ):
            changed, msg = repair_bloom_real_import(target)

            if changed:
                print(f"[REPAIR] {msg}")
                result["repairs"].append(msg)
                log(
                    {
                        "event": "verified_structural_repair",
                        "target": target.name,
                        "repair": msg,
                    }
                )
                continue

        # Dimension mismatch that can be structurally resolved
        # by using the recurrent matrix width.
        if (
            "ValueError: matmul" in stderr
            and "mismatch in its core dimension" in stderr
            and target.name == "bloom_real.py"
        ):
            changed, msg = patch_bloom_best_llm()

            if changed:
                print(f"[REPAIR] {msg}")
                result["repairs"].append(msg)
                continue

        # Empty market data.
        if (
            target.name == "hybrid_bloom.py"
            and "ZeroDivisionError" in stderr
            and "market_signal" in stderr
        ):
            changed, msg = patch_hybrid_market_guard(target)

            if changed:
                print(f"[REPAIR] {msg}")
                result["repairs"].append(msg)
                continue

        result["rounds"].append(
            {
                "round": round_no,
                "stderr": stderr[-12000:],
                "location": location,
            }
        )

        print()
        print("NO VERIFIED STRUCTURAL REPAIR AVAILABLE FOR THIS FAILURE.")
        result["status"] = "UNRESOLVED"
        break

    result["final_sha256"] = sha256(target)
    return result


def main():
    print("=" * 90)
    print("BLOOM PROBLEM SOLVER V5")
    print("DIRECT ACTIVE REPAIR")
    print("=" * 90)

    BACKUP.mkdir(parents=True, exist_ok=True)

    results = []

    for target in TARGETS:
        if target.exists():
            results.append(
                execute_repair_loop(target)
            )
        else:
            results.append(
                {
                    "target": target.name,
                    "status": "MISSING",
                }
            )

    report = {
        "version": 5,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
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
    print("FINAL RESULT")
    print("=" * 90)

    success = True

    for result in results:
        print(
            f"{result['target']:<28}"
            f"{result['status']}"
        )

        if result["status"] != "PASS":
            success = False

    print()
    print(f"REPORT:  {REPORT}")
    print(f"BACKUPS: {BACKUP}")

    print("=" * 90)

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
