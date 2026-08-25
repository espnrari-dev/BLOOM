#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "BLOOM_FULL_STATE.json"
BACKUP_DIR = ROOT / ".bloom_solver_backups"
REPORT = ROOT / "bloom_problem_solver_v3_report.json"
LEDGER = ROOT / "bloom_problem_solver_v3_ledger.jsonl"

TIMEOUT = 12
MAX_ROUNDS = 12

TARGETS = [
    ROOT / "bloom_real.py",
    ROOT / "hybrid_bloom.py",
]

IGNORE = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".bloom_repairs",
    ".bloom_solver_backups",
}


def ts():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def log(event):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def backup(path, round_no):
    BACKUP_DIR.mkdir(exist_ok=True)
    dst = BACKUP_DIR / f"{path.name}.round{round_no}.{int(time.time())}.bak"
    shutil.copy2(path, dst)
    return dst


def run(path):
    try:
        p = subprocess.run(
            [sys.executable, "-u", str(path)],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        return {
            "status": "PASS" if p.returncode == 0 else "FAIL",
            "returncode": p.returncode,
            "stdout": p.stdout[-16000:],
            "stderr": p.stderr[-16000:],
        }
    except subprocess.TimeoutExpired as e:
        return {
            "status": "TIMEOUT",
            "returncode": None,
            "stdout": (e.stdout or "")[-16000:]
            if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-16000:]
            if isinstance(e.stderr, str) else "",
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "returncode": None,
            "stdout": "",
            "stderr": repr(e),
        }


def compile_check(path):
    try:
        compile(
            path.read_text(encoding="utf-8", errors="replace"),
            str(path),
            "exec",
        )
        return True, ""
    except Exception as e:
        return False, traceback.format_exc()


def traceback_info(stderr):
    text = stderr or ""

    patterns = [
        (
            r'File "([^"]+)", line (\d+), in (.+)',
            "location",
        ),
    ]

    locations = []
    for pattern, _ in patterns:
        for m in re.finditer(pattern, text):
            locations.append({
                "file": m.group(1),
                "line": int(m.group(2)),
                "function": m.group(3),
            })

    exception = ""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if re.match(
            r"^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception|Warning)?\s*:",
            line,
        ):
            exception = line
            break

    return {
        "exception": exception,
        "locations": locations,
        "raw": text[-16000:],
    }


def source_lines(path):
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()


def write_lines(path, lines):
    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def find_line_context(path, line, radius=5):
    lines = source_lines(path)
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return [
        {"line": i, "text": lines[i - 1]}
        for i in range(start, end + 1)
    ]


def replace_line(path, line_no, new_line):
    lines = source_lines(path)
    if not 1 <= line_no <= len(lines):
        return False
    lines[line_no - 1] = new_line
    write_lines(path, lines)
    return True


def repair_missing_local_file(path, error):
    m = re.search(
        r"(?:No such file or directory|FileNotFoundError:.*)"
        r".*?[\"']([^\"']+)[\"']",
        error,
        re.I,
    )

    if not m:
        m = re.search(
            r"open\((?:.*?),?\s*[\"']([^\"']+)[\"']",
            error,
            re.I,
        )

    if not m:
        return None

    requested = m.group(1)

    if requested.startswith("/"):
        candidate = Path(requested)
    else:
        candidate = ROOT / requested

    if candidate.exists():
        return None

    # Only repair references to files that actually exist elsewhere
    # in the BLOOM tree. Never fabricate data/files.
    matches = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in IGNORE):
            continue
        if p.name == Path(requested).name:
            matches.append(p)

    if len(matches) != 1:
        return None

    actual = matches[0]

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    old_forms = [
        requested,
        str(Path(requested)),
    ]

    for old in old_forms:
        if old in source:
            new = os.path.relpath(actual, ROOT)
            path.write_text(
                source.replace(old, new),
                encoding="utf-8",
            )
            return {
                "type": "redirect_existing_file",
                "old": old,
                "new": new,
                "reason": "existing real file found in project",
            }

    return None


def repair_missing_module(path, error):
    m = re.search(
        r"No module named ['\"]([^'\"]+)['\"]",
        error,
    )
    if not m:
        return None

    module = m.group(1).split(".")[0]

    # First determine whether this is actually a local module.
    local_py = ROOT / f"{module}.py"
    if not local_py.exists():
        return None

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    # A local module should be importable from ROOT.
    # Add project root deterministically rather than changing
    # the module semantics.
    marker = "# BLOOM_SOLVER_LOCAL_PATH"
    if marker in source:
        return None

    lines = source.splitlines()

    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("#!")
        or lines[insert_at].startswith("#")
    ):
        insert_at += 1

    block = [
        marker,
        "import sys as _bloom_solver_sys",
        "from pathlib import Path as _bloom_solver_Path",
        "_bloom_solver_root = _bloom_solver_Path(__file__).resolve().parent",
        "if str(_bloom_solver_root) not in _bloom_solver_sys.path:",
        "    _bloom_solver_sys.path.insert(0, str(_bloom_solver_root))",
    ]

    lines[insert_at:insert_at] = block
    write_lines(path, lines)

    return {
        "type": "local_module_path_repair",
        "module": module,
    }


def repair_attribute_error(path, error):
    m = re.search(
        r"AttributeError: .*? object has no attribute ['\"]([^'\"]+)",
        error,
    )
    if not m:
        return None

    attr = m.group(1)

    # Do not invent behavior for arbitrary attributes.
    # Only repair a known Python compatibility spelling.
    replacements = {
        "iteritems": "items",
        "iterkeys": "keys",
        "itervalues": "values",
    }

    if attr not in replacements:
        return None

    old = attr
    new = replacements[attr]

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if old not in source:
        return None

    path.write_text(
        source.replace(f".{old}(", f".{new}("),
        encoding="utf-8",
    )

    return {
        "type": "python_compatibility_repair",
        "old": old,
        "new": new,
    }


def repair_import_error(path, error):
    m = re.search(
        r"ImportError: cannot import name ['\"]([^'\"]+)['\"] "
        r"from ['\"]([^'\"]+)['\"]",
        error,
    )
    if not m:
        return None

    symbol = m.group(1)
    module = m.group(2)

    local = ROOT / (module.replace(".", "/") + ".py")

    if not local.exists():
        return None

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    # Check whether symbol actually exists in the local module.
    mod_source = local.read_text(
        encoding="utf-8",
        errors="replace",
    )

    try:
        tree = ast.parse(mod_source)
    except Exception:
        return None

    defined = set()

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            defined.add(node.name)

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)

    if symbol in defined:
        return None

    return None


def repair_runtime(path, result):
    error = (
        (result.get("stderr") or "")
        + "\n"
        + (result.get("stdout") or "")
    )

    repairs = [
        repair_missing_local_file,
        repair_missing_module,
        repair_attribute_error,
        repair_import_error,
    ]

    for fn in repairs:
        try:
            change = fn(path, error)
        except Exception:
            change = None

        if change:
            return change

    return None


def validate_all():
    results = {}

    for path in TARGETS:
        if not path.exists():
            continue

        ok, err = compile_check(path)

        if not ok:
            results[path.name] = {
                "compile": False,
                "runtime": None,
                "compile_error": err,
            }
            continue

        results[path.name] = {
            "compile": True,
            "runtime": run(path),
        }

    return results


def score_result(result):
    if not result:
        return -100

    if result["compile"] is False:
        return -100

    runtime = result["runtime"]

    if runtime["status"] == "PASS":
        return 100

    if runtime["status"] == "TIMEOUT":
        return 10

    if runtime["status"] == "FAIL":
        return -20

    return -30


def repair_target(path, history):
    before = run(path)

    if before["status"] == "PASS":
        return {
            "status": "already_passes",
            "before": before,
        }

    for round_no in range(1, MAX_ROUNDS + 1):

        ok, compile_error = compile_check(path)

        if not ok:
            return {
                "status": "compile_failure",
                "round": round_no,
                "compile_error": compile_error,
            }

        current = run(path)

        if current["status"] == "PASS":
            return {
                "status": "fixed",
                "round": round_no,
                "result": current,
            }

        evidence = traceback_info(
            current.get("stderr", "")
        )

        context = None

        if evidence["locations"]:
            loc = evidence["locations"][-1]

            try:
                context = find_line_context(
                    path,
                    loc["line"],
                )
            except Exception:
                context = None

        event = {
            "time": ts(),
            "target": path.name,
            "round": round_no,
            "status": current["status"],
            "exception": evidence["exception"],
            "locations": evidence["locations"],
            "context": context,
        }

        history.append(event)
        log(event)

        before_hash = sha(path)
        backup_path = backup(path, round_no)

        change = repair_runtime(
            path,
            current,
        )

        if not change:
            shutil.copy2(backup_path, path)

            return {
                "status": "unrepairable_with_verified_rules",
                "round": round_no,
                "runtime": current,
                "exception": evidence["exception"],
                "locations": evidence["locations"],
            }

        ok, compile_error = compile_check(path)

        if not ok:
            shutil.copy2(backup_path, path)

            rollback = {
                "time": ts(),
                "target": path.name,
                "round": round_no,
                "action": "rollback_compile_failure",
                "repair": change,
            }

            log(rollback)

            return {
                "status": "rollback_compile_failure",
                "round": round_no,
                "repair": change,
            }

        after = run(path)

        if score_result({
            "compile": True,
            "runtime": after,
        }) > score_result({
            "compile": True,
            "runtime": current,
        }):
            event = {
                "time": ts(),
                "target": path.name,
                "round": round_no,
                "action": "repair_kept",
                "repair": change,
                "before": current,
                "after": after,
                "hash_before": before_hash,
                "hash_after": sha(path),
            }
            log(event)

            if after["status"] == "PASS":
                return {
                    "status": "fixed",
                    "round": round_no,
                    "repair": change,
                    "before": current,
                    "after": after,
                }

            continue

        shutil.copy2(backup_path, path)

        rollback = {
            "time": ts(),
            "target": path.name,
            "round": round_no,
            "action": "rollback_no_improvement",
            "repair": change,
            "before": current,
            "after": after,
        }

        log(rollback)

        return {
            "status": "rollback_no_improvement",
            "round": round_no,
            "repair": change,
            "before": current,
            "after": after,
        }

    return {
        "status": "round_limit",
    }


def main():
    print("=" * 90)
    print("BLOOM PROBLEM SOLVER V3")
    print("ACTIVE SELF-HEALING ENGINE")
    print("=" * 90)
    print(f"ROOT: {ROOT}")
    print()

    BACKUP_DIR.mkdir(exist_ok=True)

    history = []
    results = {}

    for target in TARGETS:
        if not target.exists():
            continue

        print("=" * 90)
        print(f"TARGET: {target.name}")
        print("=" * 90)

        result = repair_target(
            target,
            history,
        )

        results[target.name] = result

        print(f"RESULT: {result['status']}")

        if result.get("repair"):
            print(
                "REPAIR:",
                json.dumps(
                    result["repair"],
                    ensure_ascii=False,
                ),
            )

        print()

    final = validate_all()

    report = {
        "version": 3,
        "time": ts(),
        "root": str(ROOT),
        "targets": [str(x) for x in TARGETS],
        "results": results,
        "final_validation": final,
        "history": history,
    }

    REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 90)
    print("FINAL VALIDATION")
    print("=" * 90)

    for name, result in final.items():
        print(
            f"{name:24} "
            f"compile={result['compile']} "
            f"runtime={result.get('runtime', {}).get('status')}"
        )

    passed = all(
        r["compile"]
        and r["runtime"]["status"] == "PASS"
        for r in final.values()
    )

    print()
    print("=" * 90)

    if passed:
        print("BLOOM SELF-HEALING RESULT: PASS")
    else:
        print("BLOOM SELF-HEALING RESULT: INCOMPLETE")
        print("The engine stopped only where a verified repair rule did not exist.")

    print("=" * 90)
    print(f"REPORT: {REPORT}")
    print(f"LEDGER: {LEDGER}")
    print(f"BACKUPS: {BACKUP_DIR}")

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
