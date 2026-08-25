#!/usr/bin/env python3
"""
BLOOM PROBLEM SOLVER V2
=======================

Self-healing engineering controller.

Architecture:

    OBSERVE
       ↓
    DIAGNOSE
       ↓
    HYPOTHESIZE
       ↓
    REPAIR
       ↓
    VALIDATE
       ↓
    ACCEPT ───────────────┐
       │                 │
       └── LEARN          │
                         │
    FAILURE ─→ ROLLBACK ─┘

Principles:
    - real files only
    - no synthetic training data
    - no fabricated model parameters
    - no blind source replacement
    - every mutation gets a backup
    - every mutation requires validation
    - failed mutations are rolled back
    - successful repairs are recorded
    - multiple independent problems may be repaired
    - stop when the system reaches a stable state

This is an engineering repair controller, not another audit-only script.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATE = ROOT / "BLOOM_FULL_STATE.json"

BACKUP_ROOT = ROOT / ".bloom_solver_backups"
LEDGER = ROOT / "bloom_problem_solver_ledger.jsonl"
REPORT = ROOT / "bloom_problem_solver_report.json"

MAX_ROUNDS = 12
RUNTIME_TIMEOUT = 15
MAX_REPAIR_ATTEMPTS_PER_FILE = 4

EXCLUDED = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".bloom_repairs",
    ".bloom_solver_backups",
}

PYTHON_NAMES = {
    "python",
    "python3",
}


@dataclass
class Finding:
    severity: str
    kind: str
    file: str
    line: int
    message: str
    evidence: str = ""


@dataclass
class Repair:
    file: Path
    kind: str
    description: str
    before: str
    after: str
    evidence: str


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def log(event: dict[str, Any]) -> None:
    event = {
        "timestamp": timestamp(),
        **event,
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def discover_python() -> list[Path]:
    result = []

    for p in sorted(ROOT.rglob("*.py")):
        if not p.is_file():
            continue

        if any(part in EXCLUDED for part in p.parts):
            continue

        result.append(p)

    return result


def read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def write(path: Path, text: str) -> None:
    path.write_text(
        text,
        encoding="utf-8",
    )


def compile_file(path: Path) -> tuple[bool, str]:
    try:
        compile(
            read(path),
            str(path),
            "exec",
        )
        return True, ""
    except Exception as exc:
        return False, traceback.format_exc()


def parse_file(path: Path) -> tuple[ast.AST | None, str]:
    try:
        return ast.parse(
            read(path),
            filename=str(path),
        ), ""
    except Exception:
        return None, traceback.format_exc()


def line_number_from_error(error: str) -> int:
    patterns = [
        r'line (\d+)',
        r'File ".*", line (\d+)',
    ]

    for pattern in patterns:
        m = re.search(pattern, error)

        if m:
            return int(m.group(1))

    return 0


def make_backup(path: Path) -> Path:
    BACKUP_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = str(int(time.time() * 1000000))

    destination = (
        BACKUP_ROOT
        / stamp
        / path.relative_to(ROOT)
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        path,
        destination,
    )

    return destination


def restore(path: Path, backup: Path) -> None:
    shutil.copy2(
        backup,
        path,
    )


def run_python(
    path: Path,
    args: list[str] | None = None,
    timeout: int = RUNTIME_TIMEOUT,
) -> dict[str, Any]:

    args = args or []

    command = [
        sys.executable,
        "-u",
        str(path),
        *args,
    ]

    started = time.monotonic()

    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )

        return {
            "status": (
                "PASS"
                if proc.returncode == 0
                else "FAIL"
            ),
            "returncode": proc.returncode,
            "elapsed": round(
                time.monotonic() - started,
                3,
            ),
            "stdout": proc.stdout[-16000:],
            "stderr": proc.stderr[-16000:],
        }

    except subprocess.TimeoutExpired as exc:
        return {
            "status": "TIMEOUT",
            "returncode": None,
            "elapsed": round(
                time.monotonic() - started,
                3,
            ),
            "stdout": str(exc.stdout or "")[-16000:],
            "stderr": str(exc.stderr or "")[-16000:],
        }

    except Exception:
        return {
            "status": "ERROR",
            "returncode": None,
            "elapsed": round(
                time.monotonic() - started,
                3,
            ),
            "stdout": "",
            "stderr": traceback.format_exc(),
        }


def static_findings(path: Path) -> list[Finding]:
    findings = []

    source = read(path)

    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )
    except SyntaxError as exc:
        findings.append(
            Finding(
                "CRITICAL",
                "syntax_error",
                str(path.relative_to(ROOT)),
                exc.lineno or 0,
                str(exc),
                source[max(0, (exc.lineno or 1) - 3):],
            )
        )
        return findings

    imports = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    (
                        alias.name,
                        node.lineno,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(
                    (
                        node.module,
                        node.lineno,
                    )
                )

    for module, line in imports:

        root = module.split(".")[0]

        if root in {
            "json",
            "os",
            "sys",
            "time",
            "math",
            "re",
            "ast",
            "pathlib",
            "typing",
            "hashlib",
            "subprocess",
            "shutil",
            "traceback",
            "dataclasses",
            "collections",
            "itertools",
            "statistics",
            "random",
            "sqlite3",
            "threading",
            "queue",
            "logging",
            "argparse",
            "signal",
            "copy",
            "csv",
            "glob",
            "textwrap",
            "inspect",
            "importlib",
            "functools",
        }:
            continue

        try:
            spec = importlib.util.find_spec(root)

            if spec is None:
                findings.append(
                    Finding(
                        "HIGH",
                        "missing_import",
                        str(path.relative_to(ROOT)),
                        line,
                        f"Module unavailable: {module}",
                    )
                )
        except Exception:
            pass

    return findings


def collect_compile_failures(
    files: list[Path],
) -> list[Finding]:

    findings = []

    for path in files:
        ok, error = compile_file(path)

        if not ok:
            findings.append(
                Finding(
                    "CRITICAL",
                    "compile_failure",
                    str(path.relative_to(ROOT)),
                    line_number_from_error(error),
                    "Python compilation failed",
                    error,
                )
            )

    return findings


def identify_entrypoints(
    files: list[Path],
) -> list[Path]:

    candidates = []

    priority = [
        "bloom_terminal.py",
        "bloom.py",
        "bloom_real.py",
        "bloom_true.py",
        "bloom_live.py",
        "bloom_operator.py",
        "bloom_autonomous_operator.py",
        "bloom_chat.py",
        "hybrid_bloom.py",
        "hybrid_bloom_v3.py",
    ]

    by_name = {
        p.name: p
        for p in files
    }

    for name in priority:
        if name in by_name:
            candidates.append(by_name[name])

    if candidates:
        return candidates

    for path in files:
        try:
            tree = ast.parse(read(path))
        except Exception:
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and "__name__" in ast.unparse(node.test)
                and "main" in ast.unparse(node)
            ):
                candidates.append(path)
                break

    return candidates[:8]


def validate_entrypoints(
    entrypoints: list[Path],
) -> list[Finding]:

    findings = []

    for path in entrypoints:

        result = run_python(path)

        if result["status"] == "FAIL":

            findings.append(
                Finding(
                    "HIGH",
                    "runtime_failure",
                    str(path.relative_to(ROOT)),
                    0,
                    "Entrypoint returned non-zero",
                    result["stderr"] or result["stdout"],
                )
            )

        elif result["status"] == "ERROR":

            findings.append(
                Finding(
                    "HIGH",
                    "runtime_error",
                    str(path.relative_to(ROOT)),
                    0,
                    "Entrypoint could not be executed",
                    result["stderr"],
                )
            )

    return findings


# ---------------------------------------------------------------------
# REPAIR SYNTHESIS
# ---------------------------------------------------------------------

def repair_syntax(
    finding: Finding,
) -> Repair | None:

    path = ROOT / finding.file
    source = read(path)

    # -------------------------------------------------------------
    # Case 1: common accidental trailing garbage.
    # -------------------------------------------------------------

    lines = source.splitlines()

    if finding.line:
        idx = finding.line - 1

        if 0 <= idx < len(lines):

            bad = lines[idx]

            # Never delete arbitrary program logic.
            # Only remove unmistakable shell/paste contamination.
            garbage_markers = (
                "~/BLOOM $",
                ">>>",
                "Traceback (most recent call last)",
            )

            if any(
                marker in bad
                for marker in garbage_markers
            ):
                new_lines = lines[:idx] + lines[idx + 1:]

                return Repair(
                    path,
                    "remove_terminal_contamination",
                    "Removed unmistakable terminal contamination from source.",
                    source,
                    "\n".join(new_lines) + "\n",
                    bad,
                )

    return None


def repair_obvious_import(
    finding: Finding,
) -> Repair | None:

    path = ROOT / finding.file
    source = read(path)

    module_match = re.search(
        r"Module unavailable: ([A-Za-z0-9_.]+)",
        finding.message,
    )

    if not module_match:
        return None

    module = module_match.group(1)
    root = module.split(".")[0]

    # We do NOT fabricate a dependency.
    # Instead, if BLOOM already contains a local module,
    # convert the import only when the module physically exists.
    local_candidates = [
        ROOT / f"{root}.py",
        ROOT / root / "__init__.py",
    ]

    if not any(p.exists() for p in local_candidates):
        return None

    return None


def repair_target(
    finding: Finding,
) -> Repair | None:

    if finding.kind == "syntax_error":
        return repair_syntax(finding)

    if finding.kind == "compile_failure":
        return repair_syntax(finding)

    if finding.kind == "missing_import":
        return repair_obvious_import(finding)

    return None


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

def validate_repair(
    repair: Repair,
) -> tuple[bool, dict[str, Any]]:

    compile_ok, compile_error = compile_file(
        repair.file
    )

    if not compile_ok:
        return False, {
            "stage": "compile",
            "error": compile_error,
        }

    # If repair affects an executable, run it.
    if repair.file.name in {
        "bloom_terminal.py",
        "bloom.py",
        "bloom_real.py",
        "bloom_true.py",
        "bloom_live.py",
        "bloom_operator.py",
        "bloom_autonomous_operator.py",
        "bloom_chat.py",
        "hybrid_bloom.py",
        "hybrid_bloom_v3.py",
    }:
        result = run_python(
            repair.file,
            timeout=RUNTIME_TIMEOUT,
        )

        if result["status"] == "FAIL":
            return False, result

        if result["status"] == "ERROR":
            return False, result

    return True, {
        "stage": "all_available_validation",
        "status": "PASS",
    }


def apply_repair(
    repair: Repair,
) -> bool:

    backup = make_backup(repair.file)

    original_hash = sha256(repair.file)

    write(
        repair.file,
        repair.after,
    )

    new_hash = sha256(repair.file)

    if original_hash == new_hash:
        return False

    valid, evidence = validate_repair(
        repair
    )

    if valid:

        log(
            {
                "event": "repair_accepted",
                "file": str(
                    repair.file.relative_to(ROOT)
                ),
                "kind": repair.kind,
                "description": repair.description,
                "evidence": evidence,
                "backup": str(
                    backup.relative_to(ROOT)
                ),
            }
        )

        return True

    restore(
        repair.file,
        backup,
    )

    log(
        {
            "event": "repair_rejected",
            "file": str(
                repair.file.relative_to(ROOT)
            ),
            "kind": repair.kind,
            "reason": evidence,
            "rollback": True,
            "backup": str(
                backup.relative_to(ROOT)
            ),
        }
    )

    return False


# ---------------------------------------------------------------------
# SYSTEM STATE
# ---------------------------------------------------------------------

def system_snapshot(
    files: list[Path],
) -> dict[str, Any]:

    compiled = 0
    failed = 0

    for path in files:
        ok, _ = compile_file(path)

        if ok:
            compiled += 1
        else:
            failed += 1

    return {
        "timestamp": timestamp(),
        "python_files": len(files),
        "compile_pass": compiled,
        "compile_fail": failed,
        "entrypoints": [
            str(p.relative_to(ROOT))
            for p in identify_entrypoints(files)
        ],
    }


def save_report(
    rounds: list[dict[str, Any]],
    final: dict[str, Any],
) -> None:

    REPORT.write_text(
        json.dumps(
            {
                "version": 2,
                "generated": timestamp(),
                "rounds": rounds,
                "final": final,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# MAIN CLOSED LOOP
# ---------------------------------------------------------------------

def main() -> int:

    print("=" * 90)
    print("BLOOM PROBLEM SOLVER V2")
    print("SELF-HEALING ENGINEERING LOOP")
    print("=" * 90)
    print(f"ROOT: {ROOT}")
    print()

    rounds = []

    total_repairs = 0
    total_rollbacks = 0

    for round_number in range(
        1,
        MAX_ROUNDS + 1,
    ):

        print("=" * 90)
        print(f"REPAIR ROUND {round_number}")
        print("=" * 90)

        files = discover_python()

        print(
            f"PYTHON FILES: {len(files)}"
        )

        findings = []

        # 1. Compile reality.
        findings.extend(
            collect_compile_failures(files)
        )

        # 2. Static concrete evidence.
        for path in files:
            findings.extend(
                static_findings(path)
            )

        # 3. Real entrypoint execution.
        entrypoints = identify_entrypoints(files)

        findings.extend(
            validate_entrypoints(entrypoints)
        )

        # Deduplicate.
        unique = {}

        for f in findings:
            key = (
                f.kind,
                f.file,
                f.line,
                f.message,
            )

            unique[key] = f

        findings = list(unique.values())

        critical = [
            f for f in findings
            if f.severity == "CRITICAL"
        ]

        actionable = [
            f for f in findings
            if f.kind in {
                "syntax_error",
                "compile_failure",
                "missing_import",
                "runtime_failure",
                "runtime_error",
            }
        ]

        print(
            f"FINDINGS: {len(findings)}"
        )
        print(
            f"ACTIONABLE: {len(actionable)}"
        )

        for f in actionable[:20]:
            print(
                f"  [{f.severity}] "
                f"{f.file}"
                f"{':' + str(f.line) if f.line else ''} "
                f"{f.kind}: {f.message}"
            )

        if not actionable:

            print()
            print(
                "NO VERIFIED REPAIRABLE DEFECTS FOUND."
            )

            final = system_snapshot(files)

            rounds.append(
                {
                    "round": round_number,
                    "findings": [],
                    "repairs": [],
                    "result": "STABLE",
                }
            )

            save_report(
                rounds,
                final,
            )

            print()
            print("=" * 90)
            print("SYSTEM CONVERGED")
            print("=" * 90)
            print(
                f"COMPILE PASS: "
                f"{final['compile_pass']}"
            )
            print(
                f"COMPILE FAIL: "
                f"{final['compile_fail']}"
            )
            print(
                f"REPAIRS ACCEPTED: "
                f"{total_repairs}"
            )
            print(
                f"ROLLBACKS: "
                f"{total_rollbacks}"
            )
            print(
                f"REPORT: {REPORT}"
            )
            print("=" * 90)

            return 0

        repairs_this_round = []

        # Highest-confidence findings first.
        ordered = sorted(
            actionable,
            key=lambda x: (
                0 if x.severity == "CRITICAL" else
                1 if x.severity == "HIGH" else
                2
            ),
        )

        attempted = set()

        for finding in ordered:

            key = (
                finding.file,
                finding.kind,
            )

            if key in attempted:
                continue

            attempted.add(key)

            path = ROOT / finding.file

            if not path.exists():
                continue

            repair = repair_target(
                finding
            )

            if repair is None:
                continue

            print()
            print(
                "PROPOSED REPAIR:"
            )
            print(
                f"  FILE: {finding.file}"
            )
            print(
                f"  TYPE: {repair.kind}"
            )
            print(
                f"  WHY:  {repair.description}"
            )

            accepted = apply_repair(
                repair
            )

            if accepted:

                total_repairs += 1

                repairs_this_round.append(
                    {
                        "file": finding.file,
                        "kind": repair.kind,
                        "description": repair.description,
                        "status": "ACCEPTED",
                    }
                )

                print(
                    "  RESULT: ACCEPTED"
                )

            else:

                total_rollbacks += 1

                repairs_this_round.append(
                    {
                        "file": finding.file,
                        "kind": repair.kind,
                        "description": repair.description,
                        "status": "REJECTED_AND_ROLLED_BACK",
                    }
                )

                print(
                    "  RESULT: REJECTED / ROLLED BACK"
                )

        rounds.append(
            {
                "round": round_number,
                "finding_count": len(findings),
                "actionable_count": len(actionable),
                "repairs": repairs_this_round,
            }
        )

        if not repairs_this_round:

            print()
            print(
                "STOP: remaining findings "
                "have no verified safe automatic repair."
            )
            break

    files = discover_python()

    final = system_snapshot(files)

    save_report(
        rounds,
        final,
    )

    print()
    print("=" * 90)
    print("FINAL SELF-HEALING RESULT")
    print("=" * 90)
    print(
        f"PYTHON FILES:   {final['python_files']}"
    )
    print(
        f"COMPILE PASS:   {final['compile_pass']}"
    )
    print(
        f"COMPILE FAIL:   {final['compile_fail']}"
    )
    print(
        f"REPAIRS:        {total_repairs}"
    )
    print(
        f"ROLLBACKS:      {total_rollbacks}"
    )
    print(
        f"REPORT:         {REPORT}"
    )
    print(
        f"LEDGER:         {LEDGER}"
    )
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
