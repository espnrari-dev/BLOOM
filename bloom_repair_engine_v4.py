#!/usr/bin/env python3
"""
BLOOM AUTONOMOUS REPAIR ENGINE V4
=================================

Evidence-acquisition layer for BLOOM.

V4 does NOT modify source code.

Purpose:
    Investigate concrete runtime failures deeply enough to distinguish
    an actual defect from expected long-running / interactive behavior.

Safety rules:
    1. Never invent vocabularies.
    2. Never invent token IDs.
    3. Never invent model dimensions.
    4. Never invent checkpoints or weights.
    5. Never invent validation data.
    6. Never treat keyword occurrence as runtime proof.
    7. Never mutate source.
    8. Never classify timeout as a defect without evidence.
    9. Never learn an unvalidated repair.
   10. Never smoke-test this controller itself.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SELF_FILE = Path(__file__).resolve()

REPORT_DIR = ROOT / ".bloom_repairs"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".bloom_operator_backups",
    ".bloom_repairs",
}

TARGET = ROOT / "bloom_terminal.py"

TIMEOUT_SECONDS = 8
OBSERVATION_INTERVAL = 1.0


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    try:
        with path.open("rb") as f:
            for block in iter(
                lambda: f.read(1024 * 1024),
                b"",
            ):
                h.update(block)

        return h.hexdigest()

    except Exception:
        return ""


def safe_read(path: Path) -> str:
    try:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        return f"<READ_ERROR:{exc!r}>"


def parse_target() -> dict[str, Any]:
    if not TARGET.exists():
        return {
            "exists": False,
            "error": "TARGET_NOT_FOUND",
        }

    source = safe_read(TARGET)

    try:
        tree = ast.parse(
            source,
            filename=str(TARGET),
        )
    except Exception as exc:
        return {
            "exists": True,
            "parse_ok": False,
            "parse_error": repr(exc),
            "source_sha256": sha256_file(TARGET),
        }

    return {
        "exists": True,
        "parse_ok": True,
        "source_sha256": sha256_file(TARGET),
        "bytes": TARGET.stat().st_size,
        "lines": source.count("\n") + 1,
        "ast": tree,
        "source": source,
    }


def line_context(
    source: str,
    line: int,
    radius: int = 3,
) -> list[dict[str, Any]]:
    lines = source.splitlines()

    start = max(1, line - radius)
    end = min(len(lines), line + radius)

    result = []

    for number in range(start, end + 1):
        result.append(
            {
                "line": number,
                "text": lines[number - 1],
            }
        )

    return result


def analyze_ast(
    tree: ast.AST,
    source: str,
) -> dict[str, Any]:

    functions = []
    classes = []
    imports = []
    stdin_operations = []
    subprocess_operations = []
    network_operations = []
    sleep_operations = []
    loops = []
    file_operations = []
    environment_operations = []
    exits = []
    main_guards = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                    "async": isinstance(
                        node,
                        ast.AsyncFunctionDef,
                    ),
                }
            )

        elif isinstance(node, ast.ClassDef):
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                }
            )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append(
                    {
                        "module": node.module or "",
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.Call):

            name = ""

            if isinstance(node.func, ast.Name):
                name = node.func.id

            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr

            lower = name.lower()

            record = {
                "name": name,
                "line": node.lineno,
                "context": line_context(
                    source,
                    node.lineno,
                    2,
                ),
            }

            if lower in {
                "input",
                "readline",
                "read",
            }:
                stdin_operations.append(record)

            if lower in {
                "run",
                "popen",
                "call",
                "check_call",
                "check_output",
            }:
                subprocess_operations.append(record)

            if lower in {
                "sleep",
                "wait",
            }:
                sleep_operations.append(record)

            if lower in {
                "socket",
                "connect",
                "accept",
                "listen",
                "recv",
                "recvfrom",
                "send",
                "sendall",
            }:
                network_operations.append(record)

            if lower in {
                "open",
            }:
                file_operations.append(record)

            if lower in {
                "exit",
                "quit",
            }:
                exits.append(record)

            if lower in {
                "getenv",
                "environ",
            }:
                environment_operations.append(record)

        elif isinstance(
            node,
            (
                ast.For,
                ast.While,
                ast.AsyncFor,
            ),
        ):
            loops.append(
                {
                    "kind": type(node).__name__,
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                    "context": line_context(
                        source,
                        node.lineno,
                        3,
                    ),
                }
            )

        elif isinstance(node, ast.If):

            try:
                condition = ast.unparse(node.test)
            except Exception:
                condition = ""

            if "__name__" in condition:
                main_guards.append(
                    {
                        "line": node.lineno,
                        "condition": condition,
                    }
                )

    return {
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "stdin_operations": stdin_operations,
        "subprocess_operations": subprocess_operations,
        "network_operations": network_operations,
        "sleep_operations": sleep_operations,
        "loops": loops,
        "file_operations": file_operations,
        "environment_operations": environment_operations,
        "exits": exits,
        "main_guards": main_guards,
    }


def compile_target() -> dict[str, Any]:
    if not TARGET.exists():
        return {
            "status": "MISSING",
        }

    try:
        source = TARGET.read_text(
            encoding="utf-8",
            errors="replace",
        )

        compile(
            source,
            str(TARGET),
            "exec",
        )

        return {
            "status": "PASS",
        }

    except Exception as exc:
        return {
            "status": "FAIL",
            "error": repr(exc),
        }


def run_case(
    label: str,
    args: list[str],
    stdin_data: str | None,
    timeout: float,
) -> dict[str, Any]:

    started = time.monotonic()

    env = os.environ.copy()

    command = [
        sys.executable,
        "-u",
        str(TARGET),
        *args,
    ]

    try:

        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:

            stdout, stderr = proc.communicate(
                input=stdin_data,
                timeout=timeout,
            )

            elapsed = time.monotonic() - started

            return {
                "label": label,
                "command": command,
                "stdin": stdin_data,
                "status": (
                    "PASS"
                    if proc.returncode == 0
                    else "FAIL"
                ),
                "returncode": proc.returncode,
                "elapsed_seconds": round(
                    elapsed,
                    3,
                ),
                "stdout": stdout[-12000:],
                "stderr": stderr[-12000:],
            }

        except subprocess.TimeoutExpired:

            elapsed = time.monotonic() - started

            try:
                proc.send_signal(signal.SIGTERM)
            except Exception:
                pass

            try:
                stdout, stderr = proc.communicate(
                    timeout=2,
                )
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

                stdout, stderr = proc.communicate()

            return {
                "label": label,
                "command": command,
                "stdin": stdin_data,
                "status": "TIMEOUT",
                "returncode": None,
                "elapsed_seconds": round(
                    elapsed,
                    3,
                ),
                "stdout": stdout[-12000:],
                "stderr": stderr[-12000:],
            }

    except Exception as exc:

        return {
            "label": label,
            "command": command,
            "stdin": stdin_data,
            "status": "ERROR",
            "returncode": None,
            "elapsed_seconds": round(
                time.monotonic() - started,
                3,
            ),
            "stdout": "",
            "stderr": repr(exc),
        }


def run_process_observation(
    timeout: float,
) -> dict[str, Any]:

    started = time.monotonic()

    command = [
        sys.executable,
        "-u",
        str(TARGET),
    ]

    try:

        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )

    except Exception as exc:
        return {
            "status": "ERROR",
            "error": repr(exc),
        }

    observations = []

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        time.sleep(
            min(
                OBSERVATION_INTERVAL,
                max(
                    0.0,
                    deadline - time.monotonic(),
                ),
            )
        )

        if proc.poll() is not None:
            break

        observation = {
            "elapsed_seconds": round(
                time.monotonic() - started,
                3,
            ),
            "pid": proc.pid,
        }

        try:
            ps = subprocess.run(
                [
                    "ps",
                    "-p",
                    str(proc.pid),
                    "-o",
                    "pid,ppid,stat,etime,args",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )

            observation["ps"] = ps.stdout

        except Exception as exc:
            observation["ps_error"] = repr(exc)

        observations.append(observation)

    running = proc.poll() is None

    if running:
        try:
            proc.send_signal(signal.SIGTERM)
        except Exception:
            pass

        try:
            stdout, stderr = proc.communicate(
                timeout=2,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

            stdout, stderr = proc.communicate()

    else:
        stdout, stderr = proc.communicate()

    return {
        "status": (
            "TIMEOUT_OBSERVED"
            if running
            else "EXITED"
        ),
        "pid": proc.pid,
        "returncode": proc.returncode,
        "elapsed_seconds": round(
            time.monotonic() - started,
            3,
        ),
        "observations": observations,
        "stdout": stdout[-12000:],
        "stderr": stderr[-12000:],
    }


def classify(
    analysis: dict[str, Any],
    cases: list[dict[str, Any]],
    observation: dict[str, Any],
) -> dict[str, Any]:

    reasons = []

    has_stdin = bool(
        analysis["stdin_operations"]
    )

    has_network = bool(
        analysis["network_operations"]
    )

    has_subprocess = bool(
        analysis["subprocess_operations"]
    )

    has_loops = bool(
        analysis["loops"]
    )

    has_sleep = bool(
        analysis["sleep_operations"]
    )

    timeout_cases = [
        case
        for case in cases
        if case["status"] == "TIMEOUT"
    ]

    error_cases = [
        case
        for case in cases
        if case["status"] in {
            "FAIL",
            "ERROR",
        }
    ]

    if has_stdin:
        reasons.append(
            "stdin-related operations detected"
        )

    if has_network:
        reasons.append(
            "network-related operations detected"
        )

    if has_subprocess:
        reasons.append(
            "subprocess operations detected"
        )

    if has_loops:
        reasons.append(
            "loop constructs detected"
        )

    if has_sleep:
        reasons.append(
            "sleep/wait operations detected"
        )

    if timeout_cases:
        reasons.append(
            f"{len(timeout_cases)} controlled "
            "case(s) exceeded timeout"
        )

    if error_cases:
        reasons.append(
            f"{len(error_cases)} controlled "
            "case(s) produced an error"
        )

    classification = "UNKNOWN"

    if error_cases:
        classification = "RUNTIME_EXCEPTION"

    elif has_stdin and timeout_cases:
        classification = "WAITING_FOR_INPUT_OR_INTERACTIVE"

    elif has_network and timeout_cases:
        classification = "POSSIBLE_NETWORK_WAIT"

    elif has_subprocess and timeout_cases:
        classification = "POSSIBLE_CHILD_PROCESS_WAIT"

    elif has_loops and timeout_cases:
        classification = "POSSIBLE_LONG_RUNNING_LOOP"

    elif timeout_cases:
        classification = "POSSIBLE_HANG"

    elif observation.get("status") == "EXITED":
        classification = "NORMAL_EXIT"

    confidence = "LOW"

    if classification == "RUNTIME_EXCEPTION":
        confidence = "HIGH"
    elif classification != "UNKNOWN" and len(reasons) >= 2:
        confidence = "MEDIUM"

    return {
        "classification": classification,
        "confidence": confidence,
        "reasons": reasons,
        "automatic_repair_allowed": False,
        "explanation": (
            "V4 is evidence acquisition only. "
            "No classification produced by this "
            "version authorizes source mutation."
        ),
    }


def build_report(
    analysis: dict[str, Any],
    compile_result: dict[str, Any],
    cases: list[dict[str, Any]],
    observation: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:

    return {
        "version": 4,
        "timestamp": now(),
        "root": str(ROOT),
        "target": rel(TARGET),
        "target_sha256": sha256_file(TARGET),
        "target_exists": TARGET.exists(),
        "compile": compile_result,
        "static_analysis": {
            key: value
            for key, value in analysis.items()
        },
        "controlled_cases": cases,
        "process_observation": observation,
        "timeout_classification": classification,
        "mutation_performed": False,
        "source_changed": False,
        "repair_authorization": "NONE",
        "safety": {
            "source_mutation": False,
            "backup_required_before_future_mutation": True,
            "validation_required_before_success": True,
            "rollback_required_after_failed_validation": True,
            "learning_requires_validated_success": True,
        },
    }


def main() -> int:

    print("=" * 90)
    print("BLOOM AUTONOMOUS REPAIR ENGINE V4")
    print("EVIDENCE ACQUISITION")
    print("=" * 90)
    print(f"ROOT:   {ROOT}")
    print(f"TARGET: {TARGET}")
    print()

    if not TARGET.exists():
        print("TARGET STATUS: MISSING")
        return 2

    before_hash = sha256_file(TARGET)

    parsed = parse_target()

    if not parsed.get("parse_ok"):
        print("TARGET PARSE: FAIL")
        print(parsed.get("parse_error"))
        return 1

    source = parsed["source"]
    tree = parsed["ast"]

    analysis = analyze_ast(
        tree,
        source,
    )

    compile_result = compile_target()

    print("=" * 90)
    print("TARGET INTEGRITY")
    print("=" * 90)
    print(f"SHA256: {before_hash}")
    print(f"BYTES:  {parsed['bytes']}")
    print(f"LINES:  {parsed['lines']}")
    print(
        f"COMPILE: {compile_result['status']}"
    )
    print()

    print("=" * 90)
    print("STATIC BEHAVIORAL EVIDENCE")
    print("=" * 90)

    print(
        f"Functions:        {len(analysis['functions'])}"
    )
    print(
        f"Classes:          {len(analysis['classes'])}"
    )
    print(
        f"Imports:          {len(analysis['imports'])}"
    )
    print(
        f"stdin operations: {len(analysis['stdin_operations'])}"
    )
    print(
        f"subprocess calls: {len(analysis['subprocess_operations'])}"
    )
    print(
        f"network calls:    {len(analysis['network_operations'])}"
    )
    print(
        f"sleep/wait calls: {len(analysis['sleep_operations'])}"
    )
    print(
        f"loops:            {len(analysis['loops'])}"
    )
    print(
        f"file operations:  {len(analysis['file_operations'])}"
    )
    print(
        f"env operations:   {len(analysis['environment_operations'])}"
    )
    print()

    print("=" * 90)
    print("CONTROLLED EXECUTION")
    print("=" * 90)

    cases = []

    cases.append(
        run_case(
            "closed_stdin",
            [],
            "",
            TIMEOUT_SECONDS,
        )
    )

    cases.append(
        run_case(
            "newline_stdin",
            [],
            "\n",
            TIMEOUT_SECONDS,
        )
    )

    cases.append(
        run_case(
            "help_flag",
            ["--help"],
            "",
            TIMEOUT_SECONDS,
        )
    )

    cases.append(
        run_case(
            "version_flag",
            ["--version"],
            "",
            TIMEOUT_SECONDS,
        )
    )

    for case in cases:
        print(
            f"{case['label']:20} "
            f"{case['status']:8} "
            f"{case['elapsed_seconds']}s "
            f"rc={case['returncode']}"
        )

    print()

    print("=" * 90)
    print("PROCESS OBSERVATION")
    print("=" * 90)

    observation = run_process_observation(
        TIMEOUT_SECONDS
    )

    print(
        f"STATUS: {observation.get('status')}"
    )
    print(
        f"PID:    {observation.get('pid')}"
    )
    print(
        f"RC:     {observation.get('returncode')}"
    )
    print(
        f"TIME:   {observation.get('elapsed_seconds')}"
    )

    for item in observation.get(
        "observations",
        [],
    ):
        print()
        print(
            f"--- observation "
            f"{item['elapsed_seconds']}s ---"
        )
        print(
            item.get(
                "ps",
                "<no ps data>",
            ).rstrip()
        )

    print()

    classification = classify(
        analysis,
        cases,
        observation,
    )

    print("=" * 90)
    print("TIMEOUT CLASSIFICATION")
    print("=" * 90)
    print(
        f"CLASSIFICATION: "
        f"{classification['classification']}"
    )
    print(
        f"CONFIDENCE:     "
        f"{classification['confidence']}"
    )

    for reason in classification["reasons"]:
        print(f"  - {reason}")

    print()
    print(
        "AUTOMATIC REPAIR: FORBIDDEN IN V4"
    )

    after_hash = sha256_file(TARGET)

    report = build_report(
        analysis,
        compile_result,
        cases,
        observation,
        classification,
    )

    report["post_analysis_sha256"] = after_hash
    report["source_hash_unchanged"] = (
        before_hash == after_hash
    )

    report_path = (
        REPORT_DIR
        / f"repair_evidence_v4_"
        f"{int(time.time())}.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    evidence_path = (
        REPORT_DIR
        / "bloom_terminal_evidence_v4.txt"
    )

    with evidence_path.open(
        "w",
        encoding="utf-8",
    ) as out:

        out.write("=" * 90)
        out.write(
            "\nBLOOM TERMINAL EVIDENCE V4\n"
        )
        out.write("=" * 90)
        out.write("\n\n")

        out.write(
            f"Generated: {now()}\n"
        )
        out.write(
            f"Target: {rel(TARGET)}\n"
        )
        out.write(
            f"SHA256 before: {before_hash}\n"
        )
        out.write(
            f"SHA256 after:  {after_hash}\n"
        )
        out.write(
            f"UNCHANGED: {before_hash == after_hash}\n\n"
        )

        out.write("CLASSIFICATION\n")
        out.write(
            json.dumps(
                classification,
                indent=2,
                ensure_ascii=False,
            )
        )
        out.write("\n\n")

        out.write("STATIC ANALYSIS\n")
        out.write(
            json.dumps(
                analysis,
                indent=2,
                ensure_ascii=False,
            )
        )
        out.write("\n\n")

        out.write("CONTROLLED CASES\n")
        out.write(
            json.dumps(
                cases,
                indent=2,
                ensure_ascii=False,
            )
        )
        out.write("\n\n")

        out.write("PROCESS OBSERVATION\n")
        out.write(
            json.dumps(
                observation,
                indent=2,
                ensure_ascii=False,
            )
        )
        out.write("\n")

    print()
    print("=" * 90)
    print("ARTIFACTS")
    print("=" * 90)
    print(f"REPORT:   {report_path}")
    print(f"EVIDENCE: {evidence_path}")
    print()
    print(
        "SOURCE MUTATION: NONE"
    )
    print(
        "SOURCE HASH UNCHANGED: "
        f"{before_hash == after_hash}"
    )
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
