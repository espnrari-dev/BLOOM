#!/usr/bin/env python3
"""
BLOOM AUTONOMOUS REPAIR ENGINE V3
=================================

Evidence-driven autonomous diagnosis and conservative repair controller.

DESIGN RULES
------------
1. Never invent vocabularies.
2. Never invent token IDs.
3. Never invent model dimensions.
4. Never invent checkpoints or weights.
5. Never invent validation data.
6. Never convert keyword occurrence into proof of a runtime contract.
7. Never mutate source without a backup.
8. Never call a repair successful unless validation proves it.
9. Never learn a repair pattern from an unsuccessful validation.
10. Never smoke-test this controller itself.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

STATE_FILE = ROOT / "bloom_autonomous_state.json"
LEDGER_FILE = ROOT / "bloom_autonomous_ledger.jsonl"
BACKUP_DIR = ROOT / ".bloom_operator_backups"
REPORT_DIR = ROOT / ".bloom_repairs"
LEARNED_FILE = ROOT / "bloom_learned_repairs.json"

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
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


# The controller itself must not become evidence for a BLOOM
# vocabulary/model/runtime/learning contract.
SELF_FILE = Path(__file__).resolve()


CONTRACTS = {
    "vocabulary": {
        "names": {
            "vocab",
            "vocabulary",
            "tokenizer",
            "token_id",
            "token_ids",
            "token2id",
            "id2token",
            "itos",
            "stoi",
            "vocab_size",
        },
        "consumer_calls": {
            "encode",
            "decode",
            "retrieve",
        },
    },
    "model": {
        "names": {
            "model",
            "model_dim",
            "hidden_dim",
            "hidden_size",
            "embedding",
            "embed_dim",
            "n_embd",
            "num_embeddings",
        },
        "consumer_calls": {
            "forward",
            "predict",
            "generate",
            "load_state_dict",
        },
    },
    "runtime": {
        "names": {
            "checkpoint",
            "checkpoint_path",
            "state_dict",
            "weights",
        },
        "consumer_calls": {
            "load_state_dict",
            "load",
        },
    },
    "learning": {
        "names": {
            "learn",
            "learning",
            "repair",
            "self_repair",
            "self_heal",
            "reflection",
            "feedback",
            "ledger",
        },
        "consumer_calls": {
            "learn",
            "repair",
            "validate",
        },
    },
}


@dataclass
class Symbol:
    file: str
    kind: str
    name: str
    line: int
    end_line: int
    qualified: str


@dataclass
class Reference:
    file: str
    kind: str
    name: str
    line: int
    context: str


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
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)

        return h.hexdigest()

    except Exception:
        return ""


def append_ledger(event: str, data: dict[str, Any]) -> None:
    record = {
        "timestamp": now(),
        "event": event,
        "data": data,
    }

    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


def default_state() -> dict[str, Any]:
    return {
        "version": 3,
        "mode": "AUTONOMOUS_DIAGNOSIS",
        "runs": 0,
        "repairs_attempted": 0,
        "repairs_successful": 0,
        "repairs_failed": 0,
        "repairs_rolled_back": 0,
        "learned_repairs": {},
        "failure_history": [],
        "last_run": None,
        "last_report": None,
        "last_evidence_bundle": None,
    }


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )

    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(
        path.suffix + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tmp.replace(path)


def load_state() -> dict[str, Any]:
    state = load_json(
        STATE_FILE,
        default_state(),
    )

    if not isinstance(state, dict):
        return default_state()

    base = default_state()
    base.update(state)

    return base


def save_state(state: dict[str, Any]) -> None:
    """
    Persist controller state atomically.

    This function was missing in V2 and caused the final
    NameError after the diagnostic cycle completed.
    """
    save_json(
        STATE_FILE,
        state,
    )


def load_learned() -> dict[str, Any]:
    data = load_json(
        LEARNED_FILE,
        {
            "version": 1,
            "patterns": {},
        },
    )

    if not isinstance(data, dict):
        return {
            "version": 1,
            "patterns": {},
        }

    data.setdefault("version", 1)
    data.setdefault("patterns", {})

    return data


def save_learned(data: dict[str, Any]) -> None:
    save_json(
        LEARNED_FILE,
        data,
    )


def python_files() -> list[Path]:
    result = []

    for path in ROOT.rglob("*.py"):
        if any(
            part in EXCLUDE_DIRS
            for part in path.parts
        ):
            continue

        result.append(path)

    return sorted(result)


def auxiliary_files() -> list[Path]:
    result = []

    patterns = (
        "*.sh",
        "*.json",
        "*.jsonl",
        "*.yaml",
        "*.yml",
        "*.toml",
        "*.txt",
        "*.cfg",
        "*.ini",
    )

    for pattern in patterns:
        for path in ROOT.rglob(pattern):
            if any(
                part in EXCLUDE_DIRS
                for part in path.parts
            ):
                continue

            result.append(path)

    return sorted(set(result))


def parse_python(
    path: Path,
) -> tuple[str, ast.AST | None, str | None]:

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        tree = ast.parse(
            text,
            filename=str(path),
        )

        return text, tree, None

    except Exception as exc:
        return "", None, repr(exc)


def build_symbol_graph() -> dict[str, Any]:

    symbols: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []

    for path in python_files():

        text, tree, error = parse_python(path)

        if tree is None:
            parse_errors.append(
                {
                    "file": rel(path),
                    "error": error,
                }
            )
            continue

        lines = text.splitlines()

        def context(line_no: int) -> str:
            if 1 <= line_no <= len(lines):
                return lines[line_no - 1][:500]
            return ""

        module = path.stem

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                symbols.append(
                    asdict(
                        Symbol(
                            file=rel(path),
                            kind="function",
                            name=node.name,
                            line=node.lineno,
                            end_line=getattr(
                                node,
                                "end_lineno",
                                node.lineno,
                            ),
                            qualified=f"{module}.{node.name}",
                        )
                    )
                )

            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    asdict(
                        Symbol(
                            file=rel(path),
                            kind="class",
                            name=node.name,
                            line=node.lineno,
                            end_line=getattr(
                                node,
                                "end_lineno",
                                node.lineno,
                            ),
                            qualified=f"{module}.{node.name}",
                        )
                    )
                )

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        {
                            "file": rel(path),
                            "line": node.lineno,
                            "module": alias.name,
                            "alias": alias.asname,
                        }
                    )

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append(
                        {
                            "file": rel(path),
                            "line": node.lineno,
                            "module": node.module or "",
                            "name": alias.name,
                            "alias": alias.asname,
                        }
                    )

            # IMPORTANT:
            # Only calls and attribute access are treated as meaningful
            # consumer evidence. Ordinary variable mentions are not.
            elif isinstance(node, ast.Call):

                if isinstance(node.func, ast.Name):
                    name = node.func.id

                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr

                else:
                    name = "<unknown>"

                references.append(
                    asdict(
                        Reference(
                            file=rel(path),
                            kind="call",
                            name=name,
                            line=node.lineno,
                            context=context(node.lineno),
                        )
                    )
                )

            elif isinstance(node, ast.Attribute):
                references.append(
                    asdict(
                        Reference(
                            file=rel(path),
                            kind="attribute",
                            name=node.attr,
                            line=node.lineno,
                            context=context(node.lineno),
                        )
                    )
                )

    return {
        "symbols": symbols,
        "references": references,
        "imports": imports,
        "parse_errors": parse_errors,
    }


def definitions_by_name(
    graph: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:

    result: dict[str, list[dict[str, Any]]] = {}

    for symbol in graph["symbols"]:
        result.setdefault(
            symbol["name"],
            [],
        ).append(symbol)

    return result


def contract_analysis(
    graph: dict[str, Any],
) -> dict[str, Any]:

    definitions = definitions_by_name(graph)

    output = {}

    for category, spec in CONTRACTS.items():

        evidence = {
            "producer_definitions": [],
            "consumer_references": [],
            "unresolved_names": [],
        }

        names = {
            x.lower()
            for x in spec["names"]
        }

        calls = {
            x.lower()
            for x in spec["consumer_calls"]
        }

        for symbol in graph["symbols"]:

            name = symbol["name"].lower()

            if name in names:
                evidence[
                    "producer_definitions"
                ].append(symbol)

        for ref in graph["references"]:

            name = ref["name"].lower()

            if (
                name in names
                or name in calls
            ):
                evidence[
                    "consumer_references"
                ].append(ref)

        for ref in evidence[
            "consumer_references"
        ]:

            name = ref["name"]

            if name not in definitions:

                evidence[
                    "unresolved_names"
                ].append(
                    {
                        "name": name,
                        "file": ref["file"],
                        "line": ref["line"],
                        "context": ref["context"],
                    }
                )

        producer_count = len(
            evidence[
                "producer_definitions"
            ]
        )

        consumer_count = len(
            evidence[
                "consumer_references"
            ]
        )

        unresolved_count = len(
            evidence[
                "unresolved_names"
            ]
        )

        if (
            consumer_count > 0
            and producer_count == 0
        ):
            status = "MISSING_PRODUCER_EVIDENCE"

        elif (
            unresolved_count > 0
        ):
            status = "UNRESOLVED_REFERENCE"

        elif (
            producer_count > 0
            and consumer_count > 0
        ):
            status = "EVIDENCE_PRESENT"

        else:
            status = "NO_STRONG_EVIDENCE"

        output[category] = {
            "status": status,
            "producer_count": producer_count,
            "consumer_count": consumer_count,
            "unresolved_count": unresolved_count,
            "evidence": evidence,
        }

    return output


def compile_all() -> dict[str, Any]:

    results = []

    for path in python_files():

        try:
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            compile(
                source,
                str(path),
                "exec",
            )

            results.append(
                {
                    "file": rel(path),
                    "status": "PASS",
                }
            )

        except Exception as exc:

            results.append(
                {
                    "file": rel(path),
                    "status": "FAIL",
                    "error": repr(exc),
                }
            )

    failures = [
        x
        for x in results
        if x["status"] == "FAIL"
    ]

    return {
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "results": results,
    }


def find_entrypoints() -> list[dict[str, Any]]:

    candidates = []

    priority_names = {
        "main.py",
        "app.py",
        "run.py",
        "train.py",
        "serve.py",
        "runtime.py",
        "bloom.py",
        "model.py",
        "inference.py",
        "cli.py",
    }

    for path in python_files():

        # Never classify the repair controller as an application
        # entrypoint for its own smoke test.
        if path.resolve() == SELF_FILE:
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        score = 0
        reasons = []

        if path.name in priority_names:
            score += 5
            reasons.append(
                "priority_filename"
            )

        if "__main__" in text:
            score += 5
            reasons.append(
                "main_guard"
            )

        if re.search(
            r"\bdef\s+main\s*\(",
            text,
        ):
            score += 3
            reasons.append(
                "main_function"
            )

        if re.search(
            r"argparse|sys\.argv",
            text,
        ):
            score += 2
            reasons.append(
                "cli"
            )

        if score:
            candidates.append(
                {
                    "file": rel(path),
                    "score": score,
                    "reasons": reasons,
                }
            )

    return sorted(
        candidates,
        key=lambda x: (
            -x["score"],
            x["file"],
        ),
    )


def runtime_smoke_test(
    entrypoints: list[dict[str, Any]],
    timeout: int = 8,
) -> list[dict[str, Any]]:

    results = []

    for item in entrypoints[:8]:

        path = ROOT / item["file"]

        command = [
            sys.executable,
            "-u",
            str(path),
        ]

        try:

            proc = subprocess.run(
                command,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy(),
            )

            output = (
                proc.stdout
                + "\n"
                + proc.stderr
            )

            results.append(
                {
                    "file": item["file"],
                    "returncode": proc.returncode,
                    "status": (
                        "PASS"
                        if proc.returncode == 0
                        else "FAIL"
                    ),
                    "output": output[-12000:],
                }
            )

        except subprocess.TimeoutExpired as exc:

            results.append(
                {
                    "file": item["file"],
                    "returncode": None,
                    "status": "TIMEOUT",
                    "output": str(exc)[-12000:],
                }
            )

        except Exception as exc:

            results.append(
                {
                    "file": item["file"],
                    "returncode": None,
                    "status": "ERROR",
                    "output": repr(exc),
                }
            )

    return results


def extract_runtime_failures(
    smoke: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    failures = []

    patterns = [
        (
            "missing_module",
            r"No module named ['\"]([^'\"]+)"
        ),
        (
            "missing_name",
            r"NameError: name ['\"]([^'\"]+)['\"]"
        ),
        (
            "missing_attribute",
            r"AttributeError: .*['\"]([^'\"]+)['\"]"
        ),
        (
            "missing_file",
            r"FileNotFoundError: .*['\"]([^'\"]+)['\"]"
        ),
        (
            "key_error",
            r"KeyError: ['\"]([^'\"]+)['\"]"
        ),
        (
            "value_error",
            r"ValueError: (.*)"
        ),
        (
            "runtime_error",
            r"RuntimeError: (.*)"
        ),
        (
            "type_error",
            r"TypeError: (.*)"
        ),
        (
            "assertion_error",
            r"AssertionError: (.*)"
        ),
    ]

    for result in smoke:

        if result["status"] == "PASS":
            continue

        output = result.get(
            "output",
            "",
        )

        detected = False

        for kind, pattern in patterns:

            match = re.search(
                pattern,
                output,
                re.IGNORECASE,
            )

            if match:

                failures.append(
                    {
                        "file": result["file"],
                        "kind": kind,
                        "detail": (
                            match.group(1)
                            if match.lastindex
                            else match.group(0)
                        ),
                        "output": output[-6000:],
                    }
                )

                detected = True
                break

        if not detected:

            failures.append(
                {
                    "file": result["file"],
                    "kind": (
                        "timeout"
                        if result["status"] == "TIMEOUT"
                        else "unclassified_runtime_failure"
                    ),
                    "detail": (
                        "Process timeout."
                        if result["status"] == "TIMEOUT"
                        else "No known exception signature matched."
                    ),
                    "output": output[-6000:],
                }
            )

    return failures


def detect_contract_failures(
    contracts: dict[str, Any],
) -> list[dict[str, Any]]:

    failures = []

    for category, data in contracts.items():

        if data["status"] == "MISSING_PRODUCER_EVIDENCE":

            failures.append(
                {
                    "severity": "HIGH",
                    "contract": category,
                    "problem": (
                        "Consumer evidence exists, "
                        "but this static pass found no "
                        "matching local producer definition."
                    ),
                    "producer_count": data[
                        "producer_count"
                    ],
                    "consumer_count": data[
                        "consumer_count"
                    ],
                    "unresolved_count": data[
                        "unresolved_count"
                    ],
                    "action": (
                        "Trace actual imports, external modules, "
                        "configuration, checkpoint metadata, "
                        "and runtime initialization before repair."
                    ),
                    "fabrication_allowed": False,
                }
            )

        elif data["status"] == "UNRESOLVED_REFERENCE":

            failures.append(
                {
                    "severity": "HIGH",
                    "contract": category,
                    "problem": (
                        "Contract-related calls or attributes "
                        "cannot be resolved to local definitions."
                    ),
                    "producer_count": data[
                        "producer_count"
                    ],
                    "consumer_count": data[
                        "consumer_count"
                    ],
                    "unresolved_count": data[
                        "unresolved_count"
                    ],
                    "action": (
                        "Trace actual imports and runtime "
                        "initialization before constructing a repair."
                    ),
                    "fabrication_allowed": False,
                }
            )

    return failures


def backup_file(
    path: Path,
    run_id: str,
) -> Path:

    destination = (
        BACKUP_DIR
        / str(run_id)
        / rel(path)
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


def restore_backup(
    backup: Path,
    original: Path,
) -> None:

    original.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        backup,
        original,
    )


def fingerprint_failure(
    failure: dict[str, Any],
) -> str:

    raw = json.dumps(
        {
            "kind": failure.get("kind"),
            "detail": failure.get("detail"),
            "contract": failure.get("contract"),
        },
        sort_keys=True,
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]


def learned_match(
    learned: dict[str, Any],
    failure: dict[str, Any],
) -> list[dict[str, Any]]:

    fingerprint = fingerprint_failure(
        failure
    )

    patterns = learned.get(
        "patterns",
        {},
    )

    matches = []

    for key, value in patterns.items():

        if (
            key == fingerprint
            or failure.get("kind")
            == value.get("failure_kind")
        ):
            matches.append(value)

    return matches


def record_learning(
    learned: dict[str, Any],
    failure: dict[str, Any],
    repair: dict[str, Any],
    validation: dict[str, Any],
) -> None:

    # Only validated repairs are eligible for positive learning.
    if not validation.get("passed"):
        return

    fingerprint = fingerprint_failure(
        failure
    )

    patterns = learned.setdefault(
        "patterns",
        {},
    )

    current = patterns.get(
        fingerprint,
        {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
        },
    )

    current["attempts"] += 1
    current["successes"] += 1
    current["failure_kind"] = failure.get(
        "kind"
    )
    current["failure_detail"] = failure.get(
        "detail"
    )
    current["last_repair"] = repair
    current["last_validation"] = validation

    current["success_rate"] = (
        current["successes"]
        / current["attempts"]
    )

    patterns[fingerprint] = current


def safe_text_replace(
    path: Path,
    old: str,
    new: str,
) -> bool:

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if old not in source:
        return False

    if source.count(old) != 1:
        return False

    updated = source.replace(
        old,
        new,
        1,
    )

    path.write_text(
        updated,
        encoding="utf-8",
    )

    return True


def propose_runtime_repair(
    failure: dict[str, Any],
    graph: dict[str, Any],
) -> dict[str, Any] | None:

    kind = failure.get("kind")
    detail = failure.get("detail")

    if kind == "missing_name":

        name = str(detail)

        matches = [
            symbol
            for symbol in graph["symbols"]
            if symbol["name"] == name
        ]

        if len(matches) == 1:

            return {
                "type": "import_or_reference_repair",
                "reason": (
                    "Exactly one local definition exists "
                    "for the missing runtime name."
                ),
                "name": name,
                "definition": matches[0],
                "automatic": False,
                "requires_source_evidence": True,
            }

    return None


def validate_system(
    entrypoints: list[dict[str, Any]],
) -> dict[str, Any]:

    compile_result = compile_all()

    if compile_result["failed"]:

        return {
            "passed": False,
            "reason": "compile_failure",
            "compile": compile_result,
            "smoke": [],
            "runtime_failures": [],
        }

    smoke = runtime_smoke_test(
        entrypoints,
        timeout=8,
    )

    runtime_failures = extract_runtime_failures(
        smoke
    )

    passed = len(runtime_failures) == 0

    return {
        "passed": passed,
        "reason": (
            "runtime_smoke_passed"
            if passed
            else "runtime_failures"
        ),
        "compile": compile_result,
        "smoke": smoke,
        "runtime_failures": runtime_failures,
    }


def autonomous_repair_cycle(
    state: dict[str, Any],
    learned: dict[str, Any],
) -> dict[str, Any]:

    graph = build_symbol_graph()

    contracts = contract_analysis(
        graph
    )

    contract_failures = detect_contract_failures(
        contracts
    )

    entrypoints = find_entrypoints()

    before_validation = validate_system(
        entrypoints
    )

    runtime_failures = before_validation[
        "runtime_failures"
    ]

    all_failures = []

    for failure in contract_failures:
        all_failures.append(
            {
                "source": "static_contract",
                **failure,
            }
        )

    for failure in runtime_failures:
        all_failures.append(
            {
                "source": "runtime",
                **failure,
            }
        )

    repair_results = []

    for failure in all_failures:

        state["repairs_attempted"] += 1

        matches = learned_match(
            learned,
            failure,
        )

        candidate = None

        if failure.get("source") == "runtime":

            candidate = propose_runtime_repair(
                failure,
                graph,
            )

        if candidate is None:

            repair_results.append(
                {
                    "failure": failure,
                    "status": "BLOCKED",
                    "reason": (
                        "No evidence-backed automatic "
                        "repair is currently safe."
                    ),
                    "learned_matches": matches,
                }
            )

            state["repairs_failed"] += 1

            continue

        repair_results.append(
            {
                "failure": failure,
                "candidate": candidate,
                "status": "CANDIDATE_ONLY",
                "learned_matches": matches,
            }
        )

    save_learned(
        learned
    )

    return {
        "graph": graph,
        "contracts": contracts,
        "contract_failures": contract_failures,
        "entrypoints": entrypoints,
        "before_validation": before_validation,
        "runtime_failures": runtime_failures,
        "repair_results": repair_results,
    }


def source_inventory() -> list[dict[str, Any]]:

    result = []

    for path in python_files():

        try:

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            result.append(
                {
                    "path": rel(path),
                    "bytes": path.stat().st_size,
                    "lines": text.count("\n") + 1,
                    "sha256": sha256_file(path),
                }
            )

        except Exception as exc:

            result.append(
                {
                    "path": rel(path),
                    "error": repr(exc),
                }
            )

    return result


def auxiliary_inventory() -> list[dict[str, Any]]:

    result = []

    for path in auxiliary_files():

        try:

            result.append(
                {
                    "path": rel(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

        except Exception:
            pass

    return result


def runtime_environment() -> dict[str, Any]:

    keys = [
        "HOME",
        "PREFIX",
        "PATH",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "TERMUX_VERSION",
    ]

    return {
        key: os.environ.get(key)
        for key in keys
        if os.environ.get(key) is not None
    }


def runtime_processes() -> str:

    try:

        proc = subprocess.run(
            ["ps", "-A"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return proc.stdout[:20000]

    except Exception as exc:

        return f"PROCESS_QUERY_ERROR: {exc!r}"


def build_evidence_bundle(
    graph: dict[str, Any],
    contracts: dict[str, Any],
    failures: list[dict[str, Any]],
) -> Path:

    path = (
        REPORT_DIR
        / "runtime_evidence_bundle.txt"
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as out:

        out.write(
            "=" * 90
            + "\nBLOOM RUNTIME EVIDENCE BUNDLE V3\n"
            + "=" * 90
            + "\n"
        )

        out.write(
            f"Generated: {now()}\n"
        )

        out.write(
            f"Root: {ROOT}\n\n"
        )

        out.write(
            "\nSYMBOL DEFINITIONS\n"
        )

        for symbol in graph["symbols"]:

            out.write(
                json.dumps(
                    symbol,
                    ensure_ascii=False,
                )
                + "\n"
            )

        out.write(
            "\nIMPORTS\n"
        )

        for item in graph["imports"]:

            out.write(
                json.dumps(
                    item,
                    ensure_ascii=False,
                )
                + "\n"
            )

        out.write(
            "\nCONTRACT ANALYSIS\n"
        )

        out.write(
            json.dumps(
                contracts,
                indent=2,
                ensure_ascii=False,
            )
        )

        out.write(
            "\n\nFAILURES\n"
        )

        out.write(
            json.dumps(
                failures,
                indent=2,
                ensure_ascii=False,
            )
        )

    return path


def main() -> int:

    state = load_state()
    learned = load_learned()

    state["runs"] = int(
        state.get("runs", 0)
    ) + 1

    state["last_run"] = now()

    print("=" * 90)
    print("BLOOM AUTONOMOUS REPAIR ENGINE V3")
    print("=" * 90)
    print(f"ROOT: {ROOT}")
    print(f"RUN:  {state['runs']}")
    print()

    inventory = source_inventory()
    auxiliary = auxiliary_inventory()

    print(
        f"Python files: {len(inventory)}"
    )

    print(
        f"Auxiliary files: {len(auxiliary)}"
    )

    result = autonomous_repair_cycle(
        state,
        learned,
    )

    graph = result["graph"]
    contracts = result["contracts"]

    print()
    print("=" * 90)
    print("SYMBOL GRAPH")
    print("=" * 90)

    print(
        f"Definitions: {len(graph['symbols'])}"
    )

    print(
        f"References:  {len(graph['references'])}"
    )

    print(
        f"Imports:     {len(graph['imports'])}"
    )

    print(
        f"Parse errors:{len(graph['parse_errors'])}"
    )

    print()
    print("=" * 90)
    print("CONTRACT STATUS")
    print("=" * 90)

    for category, data in contracts.items():

        print(
            f"{category:12} "
            f"{data['status']:28} "
            f"producers={data['producer_count']} "
            f"consumers={data['consumer_count']} "
            f"unresolved={data['unresolved_count']}"
        )

    print()
    print("=" * 90)
    print("VALIDATION BEFORE REPAIR")
    print("=" * 90)

    before = result["before_validation"]

    print(
        f"PASS: {before['passed']}"
    )

    print(
        f"Reason: {before['reason']}"
    )

    print(
        "Runtime failures: "
        f"{len(before['runtime_failures'])}"
    )

    for failure in before[
        "runtime_failures"
    ][:20]:

        print(
            f"  [{failure['kind']}] "
            f"{failure['file']}: "
            f"{failure['detail']}"
        )

    print()
    print("=" * 90)
    print("REPAIR DECISIONS")
    print("=" * 90)

    blocked = 0
    candidates = 0
    learned_matches = 0

    for item in result[
        "repair_results"
    ]:

        status = item["status"]

        if status == "BLOCKED":
            blocked += 1

        elif status == "CANDIDATE_ONLY":
            candidates += 1

        learned_matches += len(
            item.get(
                "learned_matches",
                [],
            )
        )

        failure = item["failure"]

        print(
            f"[{status}] "
            f"{failure.get('source')} "
            f"{failure.get('kind', failure.get('contract'))}"
        )

        if status == "BLOCKED":

            print(
                "    "
                + item["reason"]
            )

    evidence = build_evidence_bundle(
        graph,
        contracts,
        (
            result["contract_failures"]
            + result["runtime_failures"]
        ),
    )

    report = {
        "version": 3,
        "timestamp": now(),
        "root": str(ROOT),
        "source_inventory": inventory,
        "auxiliary_inventory": auxiliary,
        "graph": graph,
        "contracts": contracts,
        "contract_failures": result[
            "contract_failures"
        ],
        "entrypoints": result[
            "entrypoints"
        ],
        "validation_before": result[
            "before_validation"
        ],
        "runtime_failures": result[
            "runtime_failures"
        ],
        "repair_results": result[
            "repair_results"
        ],
        "learned_patterns": len(
            learned.get(
                "patterns",
                {},
            )
        ),
        "evidence_bundle": str(evidence),
        "runtime_environment": runtime_environment(),
        "runtime_processes": runtime_processes(),
    }

    report_path = (
        REPORT_DIR
        / f"repair_report_v3_{int(time.time())}.json"
    )

    save_json(
        report_path,
        report,
    )

    state["last_report"] = str(
        report_path
    )

    state["last_evidence_bundle"] = str(
        evidence
    )

    state.setdefault(
        "failure_history",
        []
    ).append(
        {
            "timestamp": now(),
            "contract_failures": len(
                result["contract_failures"]
            ),
            "runtime_failures": len(
                result["runtime_failures"]
            ),
        }
    )

    state["failure_history"] = state[
        "failure_history"
    ][-100:]

    append_ledger(
        "AUTONOMOUS_DIAGNOSIS_COMPLETED",
        {
            "report": str(report_path),
            "contract_failures": len(
                result["contract_failures"]
            ),
            "runtime_failures": len(
                result["runtime_failures"]
            ),
            "blocked_repairs": blocked,
            "repair_candidates": candidates,
            "learned_matches": learned_matches,
        },
    )

    save_state(state)

    print()
    print("=" * 90)
    print("AUTONOMOUS LEARNING")
    print("=" * 90)

    print(
        "Learned repair patterns: "
        f"{len(learned.get('patterns', {}))}"
    )

    print(
        "Historical attempts: "
        f"{state['repairs_attempted']}"
    )

    print(
        "Historical successful: "
        f"{state['repairs_successful']}"
    )

    print(
        "Historical failed: "
        f"{state['repairs_failed']}"
    )

    print()
    print("=" * 90)
    print("ARTIFACTS")
    print("=" * 90)

    print(
        f"REPORT:   {report_path}"
    )

    print(
        f"EVIDENCE: {evidence}"
    )

    print(
        f"STATE:    {STATE_FILE}"
    )

    print(
        f"LEDGER:   {LEDGER_FILE}"
    )

    print(
        f"LEARNING: {LEARNED_FILE}"
    )

    print()
    print("=" * 90)
    print("ENGINE INTEGRITY")
    print("=" * 90)

    print(
        "save_state(): PRESENT"
    )

    print(
        "self-smoke-test exclusion: ENABLED"
    )

    print(
        "keyword-only contract evidence: NOT treated as proof"
    )

    print(
        "fabricated runtime vocabulary: FORBIDDEN"
    )

    print(
        "automatic mutation without validated evidence: FORBIDDEN"
    )

    print("=" * 90)

    return 0


if __name__ == "__main__":

    try:
        raise SystemExit(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\nInterrupted."
        )

        raise SystemExit(130)

    except Exception:

        traceback.print_exc()

        raise SystemExit(1)
