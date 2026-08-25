#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

STATE_FILE = ROOT / "bloom_autonomous_state.json"
LEDGER_FILE = ROOT / "bloom_autonomous_ledger.jsonl"
BACKUP_DIR = ROOT / ".bloom_operator_backups"

TOKEN_SYMBOLS = {
    "stoi",
    "itos",
    "vocab_size",
    "data",
    "validation_data",
    "VALIDATION_TEXT",
}

REQUIRED_SYMBOLS = [
    "load_text",
    "VALIDATION_TEXT",
    "stoi",
    "itos",
    "vocab_size",
    "data",
    "validation_data",
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


# ============================================================
# UTILITIES
# ============================================================

def now() -> float:
    return time.time()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")

    tmp.write_text(
        json.dumps(
            obj,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    tmp.replace(path)


def record_ledger(record: dict[str, Any]) -> None:
    LEDGER_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LEDGER_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


# ============================================================
# TERMINAL
# ============================================================

@dataclass
class CommandResult:
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return (
            self.returncode == 0
            and not self.timed_out
        )

    def as_dict(self):
        return asdict(self)


class AutonomousTerminal:

    def __init__(self, root: Path = ROOT):
        self.root = Path(root).resolve()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def snapshot(self) -> dict[str, Any]:
        result = {}

        for path in self.root.rglob("*"):

            if not path.is_file():
                continue

            if BACKUP_DIR in path.parents:
                continue

            try:
                raw = path.read_bytes()

                rel = path.relative_to(
                    self.root
                )

                result[str(rel)] = {
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                }

            except Exception:
                pass

        return result

    def run(
        self,
        command: str,
        timeout: int = 120,
        cwd: Path | None = None,
    ) -> CommandResult:

        cwd = (
            self.root
            if cwd is None
            else Path(cwd).resolve()
        )

        if (
            cwd != self.root
            and self.root not in cwd.parents
        ):
            raise ValueError(
                "Terminal escaped BLOOM root."
            )

        before = self.snapshot()
        started = now()

        try:

            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                text=True,
                capture_output=True,
                timeout=timeout,
            )

            result = CommandResult(
                command=command,
                cwd=str(cwd),
                returncode=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration=now() - started,
            )

        except subprocess.TimeoutExpired as exc:

            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode(
                    "utf-8",
                    "replace",
                )

            if isinstance(stderr, bytes):
                stderr = stderr.decode(
                    "utf-8",
                    "replace",
                )

            result = CommandResult(
                command=command,
                cwd=str(cwd),
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                duration=now() - started,
                timed_out=True,
            )

        after = self.snapshot()

        changed = {}

        for path in sorted(
            set(before) | set(after)
        ):

            if before.get(path) != after.get(path):

                changed[path] = {
                    "before": before.get(path),
                    "after": after.get(path),
                }

        record_ledger({
            "timestamp": now(),
            "type": "terminal_execution",
            "command": command,
            "cwd": str(cwd),
            "result": result.as_dict(),
            "changed_files": changed,
        })

        return result


# ============================================================
# SOURCE INTROSPECTION
# ============================================================

class SourceIntrospector:

    def __init__(self, model: Path = MODEL):
        self.model = Path(model)

        self.source = ""
        self.tree: ast.AST | None = None

        self.definitions = {}
        self.references = {}
        self.functions = {}
        self.classes = {}
        self.imports = set()

        self.assignments = {}
        self.calls = []
        self.top_level_order = []

    def load(self):
        if not self.model.exists():
            raise FileNotFoundError(
                f"Missing model: {self.model}"
            )

        self.source = self.model.read_text(
            encoding="utf-8",
            errors="replace",
        )

        self.tree = ast.parse(
            self.source
        )

        self.inspect()

        return self

    def _target_names(self, target):
        names = []

        if isinstance(target, ast.Name):
            names.append(target.id)

        elif isinstance(
            target,
            (ast.Tuple, ast.List),
        ):
            for item in target.elts:
                names.extend(
                    self._target_names(item)
                )

        elif isinstance(target, ast.Starred):
            names.extend(
                self._target_names(
                    target.value
                )
            )

        elif isinstance(target, ast.Attribute):
            pass

        elif isinstance(target, ast.Subscript):
            pass

        return names

    def _expr_names(self, node):
        result = []

        for child in ast.walk(node):

            if isinstance(child, ast.Name):
                result.append(child.id)

        return sorted(set(result))

    def _call_name(self, node):
        if not isinstance(node, ast.Call):
            return None

        func = node.func

        if isinstance(func, ast.Name):
            return func.id

        if isinstance(func, ast.Attribute):

            parts = []
            cur = func

            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value

            if isinstance(cur, ast.Name):
                parts.append(cur.id)

            return ".".join(reversed(parts))

        return None

    def inspect(self):

        if self.tree is None:
            raise RuntimeError(
                "AST has not been loaded."
            )

        self.definitions.clear()
        self.references.clear()
        self.functions.clear()
        self.classes.clear()
        self.imports.clear()
        self.assignments.clear()
        self.calls.clear()
        self.top_level_order.clear()

        builtin_names = set(
            dir(__builtins__)
        )

        # ----------------------------------------------------
        # IMPORTS
        # ----------------------------------------------------

        for node in ast.walk(self.tree):

            if isinstance(node, ast.Import):

                for alias in node.names:
                    self.imports.add(
                        alias.asname
                        or alias.name.split(".")[0]
                    )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):

                for alias in node.names:
                    self.imports.add(
                        alias.asname
                        or alias.name
                    )

        # ----------------------------------------------------
        # TOP LEVEL DEFINITIONS
        # ----------------------------------------------------

        for index, node in enumerate(
            self.tree.body,
            start=1,
        ):

            self.top_level_order.append({
                "index": index,
                "line": getattr(
                    node,
                    "lineno",
                    None,
                ),
                "type": type(node).__name__,
                "source": ast.get_source_segment(
                    self.source,
                    node,
                ),
            })

            if isinstance(
                node,
                ast.Assign,
            ):

                names = []

                for target in node.targets:
                    names.extend(
                        self._target_names(target)
                    )

                for name in names:

                    self.definitions[name] = {
                        "line": node.lineno,
                        "kind": "assignment",
                    }

                    self.assignments.setdefault(
                        name,
                        [],
                    ).append({
                        "line": node.lineno,
                        "end_line": getattr(
                            node,
                            "end_lineno",
                            node.lineno,
                        ),
                        "kind": "Assign",
                        "targets": names,
                        "reads": self._expr_names(
                            node.value
                        ),
                        "source": ast.get_source_segment(
                            self.source,
                            node,
                        ),
                    })

            elif isinstance(
                node,
                ast.AnnAssign,
            ):

                names = self._target_names(
                    node.target
                )

                for name in names:

                    self.definitions[name] = {
                        "line": node.lineno,
                        "kind": "annotated_assignment",
                    }

                    self.assignments.setdefault(
                        name,
                        [],
                    ).append({
                        "line": node.lineno,
                        "end_line": getattr(
                            node,
                            "end_lineno",
                            node.lineno,
                        ),
                        "kind": "AnnAssign",
                        "targets": names,
                        "reads": (
                            self._expr_names(
                                node.value
                            )
                            if node.value
                            else []
                        ),
                        "source": ast.get_source_segment(
                            self.source,
                            node,
                        ),
                    })

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):

                self.definitions[node.name] = {
                    "line": node.lineno,
                    "kind": type(node).__name__,
                }

        # ----------------------------------------------------
        # FUNCTIONS / CLASSES / CALLS / REFERENCES
        # ----------------------------------------------------

        for node in ast.walk(self.tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):

                self.functions[node.name] = {
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                }

            elif isinstance(
                node,
                ast.ClassDef,
            ):

                self.classes[node.name] = {
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                }

            elif isinstance(
                node,
                ast.Call,
            ):

                name = self._call_name(node)

                if name:

                    self.calls.append({
                        "name": name,
                        "line": node.lineno,
                        "args": [
                            ast.get_source_segment(
                                self.source,
                                arg,
                            )
                            for arg in node.args
                        ],
                    })

            elif isinstance(
                node,
                ast.Name,
            ):

                if not isinstance(
                    node.ctx,
                    ast.Load,
                ):
                    continue

                self.references.setdefault(
                    node.id,
                    [],
                ).append(
                    node.lineno
                )

    def source_segment(self, name: str):

        if self.tree is None:
            return None

        for node in ast.walk(self.tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):

                if node.name == name:
                    return ast.get_source_segment(
                        self.source,
                        node,
                    )

        return None

    def line_context(
        self,
        line: int,
        radius: int = 15,
    ):

        lines = self.source.splitlines()

        start = max(
            1,
            line - radius,
        )

        end = min(
            len(lines),
            line + radius,
        )

        return {
            "start_line": start,
            "end_line": end,
            "lines": [
                {
                    "line": i,
                    "text": lines[i - 1],
                }
                for i in range(
                    start,
                    end + 1,
                )
            ],
        }

    def symbol_forensics(
        self,
        name: str,
    ):

        return {
            "symbol": name,
            "definition": self.definitions.get(
                name
            ),
            "references": self.references.get(
                name,
                [],
            ),
            "assignments": self.assignments.get(
                name,
                [],
            ),
            "function": self.functions.get(
                name
            ),
            "class": self.classes.get(
                name
            ),
        }

    def unresolved_references(self):

        builtin_names = set(
            dir(__builtins__)
        )

        result = {}

        for name, lines in self.references.items():

            if name in self.definitions:
                continue

            if name in self.imports:
                continue

            if name in builtin_names:
                continue

            result[name] = sorted(
                set(lines)
            )

        return result

    def dependency_graph(self):

        graph = {}

        for name in self.functions:

            segment = self.source_segment(name)

            if not segment:
                continue

            try:
                tree = ast.parse(segment)
            except Exception:
                continue

            reads = sorted({
                node.id
                for node in ast.walk(tree)
                if (
                    isinstance(node, ast.Name)
                    and isinstance(
                        node.ctx,
                        ast.Load,
                    )
                )
            })

            graph[name] = {
                "reads": reads,
                "undefined_reads": [
                    x
                    for x in reads
                    if (
                        x not in self.definitions
                        and x not in self.imports
                        and x not in dir(__builtins__)
                    )
                ],
            }

        return graph

    def symbol_order(self):

        order = {}

        for name, info in self.definitions.items():
            order[name] = info.get("line")

        return order

    def summary(self):

        return {
            "model": str(self.model),
            "bytes": len(
                self.source.encode("utf-8")
            ),
            "sha256": sha256_file(
                self.model
            ),
            "definitions": self.definitions,
            "references": self.references,
            "functions": self.functions,
            "classes": self.classes,
            "imports": sorted(self.imports),
            "assignments": self.assignments,
            "unresolved_references":
                self.unresolved_references(),
            "dependency_graph":
                self.dependency_graph(),
            "symbol_order":
                self.symbol_order(),
        }


# ============================================================
# RUNTIME PROBES
# ============================================================

class RuntimeProbe:

    def __init__(
        self,
        terminal: AutonomousTerminal,
    ):
        self.terminal = terminal

    def import_model(self):

        probe = r'''
import sys
import traceback

ROOT = %r

sys.path.insert(0, ROOT)

try:

    import bloom_real

    print("BLOOM_IMPORT_SUCCESS")

    names = [
        "VALIDATION_TEXT",
        "stoi",
        "itos",
        "vocab_size",
        "data",
        "validation_data",
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

    for name in names:

        if hasattr(
            bloom_real,
            name,
        ):

            value = getattr(
                bloom_real,
                name,
            )

            try:
                length = len(value)
            except Exception:
                length = None

            shape = getattr(
                value,
                "shape",
                None,
            )

            print(
                "RUNTIME_SYMBOL",
                name,
                "type=",
                type(value).__name__,
                "len=",
                length,
                "shape=",
                shape,
            )

        else:

            print(
                "RUNTIME_MISSING",
                name,
            )

except Exception as exc:

    print(
        "BLOOM_IMPORT_FAILURE",
        type(exc).__name__,
        str(exc),
    )

    traceback.print_exc()
''' % str(ROOT)

        return self.terminal.run(
            f"{shlex.quote(sys.executable)} "
            f"-c {shlex.quote(probe)}",
            timeout=120,
        )

    def corpus_probe(self):

        probe = r'''
from pathlib import Path

ROOT = Path(%r)

print("CORPUS_PROBE_START")

for name in [
    "bloom_train_v2.txt",
    "bloom_valid_v2.txt",
    "my_texts.txt",
]:

    path = ROOT / name

    print(
        "CORPUS_FILE",
        name,
        "exists=",
        path.exists(),
        "bytes=",
        path.stat().st_size
        if path.exists()
        else None,
        "sha256=",
        __import__("hashlib").sha256(
            path.read_bytes()
        ).hexdigest()
        if path.exists()
        else None,
    )

print("CORPUS_PROBE_END")
''' % str(ROOT)

        return self.terminal.run(
            f"{shlex.quote(sys.executable)} "
            f"-c {shlex.quote(probe)}",
            timeout=120,
        )


# ============================================================
# ERROR DISCERNMENT
# ============================================================

class ErrorDiscerner:

    PATTERNS = [

        (
            "NAME_ERROR",
            re.compile(
                r"NameError:\s+name ['\"]([^'\"]+)['\"] is not defined"
            ),
        ),

        (
            "ATTRIBUTE_ERROR",
            re.compile(
                r"AttributeError:\s+(.+)"
            ),
        ),

        (
            "TYPE_ERROR",
            re.compile(
                r"TypeError:\s+(.+)"
            ),
        ),

        (
            "VALUE_ERROR",
            re.compile(
                r"ValueError:\s+(.+)"
            ),
        ),

        (
            "KEY_ERROR",
            re.compile(
                r"KeyError:\s+(.+)"
            ),
        ),

        (
            "INDEX_ERROR",
            re.compile(
                r"IndexError:\s+(.+)"
            ),
        ),

        (
            "FILE_NOT_FOUND",
            re.compile(
                r"FileNotFoundError:\s+(.+)"
            ),
        ),

        (
            "IMPORT_ERROR",
            re.compile(
                r"(?:ImportError|ModuleNotFoundError):\s+(.+)"
            ),
        ),

        (
            "SYNTAX_ERROR",
            re.compile(
                r"SyntaxError:\s+(.+)"
            ),
        ),
    ]

    def classify(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
    ):

        text = (
            (stdout or "")
            + "\n"
            + (stderr or "")
        )

        if "BLOOM_IMPORT_SUCCESS" in text:
            return {
                "category": "NO_ERROR",
                "detail": "",
                "confidence": 1.0,
                "raw": text[-12000:],
            }

        for category, pattern in self.PATTERNS:

            match = pattern.search(text)

            if match:

                detail = (
                    match.group(1)
                    if match.groups()
                    else match.group(0)
                )

                return {
                    "category": category,
                    "detail": detail,
                    "confidence": 1.0,
                    "raw": text[-12000:],
                }

        if returncode == 0:

            return {
                "category": "NO_ERROR",
                "detail": "",
                "confidence": 1.0,
                "raw": text[-12000:],
            }

        return {
            "category": "UNKNOWN_RUNTIME_FAILURE",
            "detail": text[-5000:],
            "confidence": 0.25,
            "raw": text[-12000:],
        }

    def analyze(
        self,
        error: dict[str, Any],
        trace: dict[str, Any],
    ):

        category = error.get(
            "category",
            "UNKNOWN_RUNTIME_FAILURE",
        )

        knowledge = {
            "known": [],
            "inferred": [],
            "unknown": [],
            "evidence": [],
        }

        decision = {
            "decision": "INVESTIGATE",
            "confidence": 0.0,
            "knowledge": knowledge,
            "next_actions": [],
            "prohibited_actions": [
                "invent training data",
                "invent validation data",
                "invent vocabulary",
                "guess vocab_size",
                "invent token IDs",
                "invent model dimensions",
                "invent model weights",
                "train before validation passes",
            ],
        }

        # ----------------------------------------------------
        # CLEAN IMPORT
        # ----------------------------------------------------

        if category == "NO_ERROR":

            decision["decision"] = (
                "VALIDATE_NEXT_CONTRACT"
            )

            decision["confidence"] = 1.0

            knowledge["known"].append(
                "Runtime import succeeds."
            )

            decision["next_actions"] = [
                "validate vocabulary contract",
                "validate batch contract",
                "validate model dimensions",
                "validate forward pass",
                "validate backward pass",
                "validate checkpoint contract",
                "validate generation contract",
                "only then permit training",
            ]

            return decision

        # ----------------------------------------------------
        # NAME ERROR
        # ----------------------------------------------------

        if category == "NAME_ERROR":

            missing = error["detail"]

            knowledge["known"].append(
                f"Runtime reports undefined symbol: {missing}."
            )

            definition = trace.get(
                "definitions",
                {},
            ).get(missing)

            references = trace.get(
                "references",
                {},
            ).get(
                missing,
                [],
            )

            assignments = trace.get(
                "assignments",
                {},
            ).get(
                missing,
                [],
            )

            knowledge["evidence"].append(
                {
                    "symbol": missing,
                    "definition": definition,
                    "references": references,
                    "assignments": assignments,
                }
            )

            if definition is None:

                knowledge["known"].append(
                    f"{missing} has no discovered top-level definition."
                )

            else:

                knowledge["known"].append(
                    f"{missing} has a source definition."
                )

                knowledge["inferred"].append(
                    f"{missing} may exist in source but is unavailable at runtime due to execution ordering, conditional initialization, or an earlier dependency failure."
                )

            # ----------------------------------------------
            # TOKEN SYMBOL
            # ----------------------------------------------

            if missing in TOKEN_SYMBOLS:

                tokenization = trace.get(
                    "tokenization",
                    {},
                )

                symbol_info = tokenization.get(
                    "symbols",
                    {},
                ).get(
                    missing,
                    {},
                )

                producer_exists = bool(
                    symbol_info.get(
                        "producer_exists"
                    )
                )

                if producer_exists:

                    decision["decision"] = (
                        "TRACE_EXISTING_TOKEN_PRODUCER"
                    )

                    decision["confidence"] = 0.99

                    knowledge["known"].append(
                        f"{missing} has a discovered source producer."
                    )

                    decision["next_actions"] = [
                        f"trace producer of {missing}",
                        f"trace every consumer of {missing}",
                        "verify producer execution ordering",
                        "verify producer dependencies",
                        "verify runtime namespace",
                        "verify corpus provenance",
                        "re-run import probe",
                    ]

                else:

                    decision["decision"] = (
                        "TOKEN_PRODUCER_MISSING"
                    )

                    decision["confidence"] = 0.98

                    knowledge["known"].append(
                        f"{missing} has no discovered producer."
                    )

                    knowledge["inferred"].append(
                        "The runtime vocabulary pipeline is incomplete, removed, or structurally disconnected from the current source."
                    )

                    decision["next_actions"] = [
                        "inspect all tokenization symbols",
                        "trace real corpus source",
                        "trace corpus-to-token producer",
                        "inspect encode/decode logic",
                        "inspect GPT vocabulary dimensions",
                        "inspect validation encoding",
                        "verify vocabulary consistency",
                        "identify exact historical/source-backed producer",
                        "only repair from verified evidence",
                        "backup bloom_real.py before modification",
                        "apply smallest evidence-backed repair",
                        "re-run import probe",
                    ]

                return decision

            # ----------------------------------------------
            # GENERAL NAME ERROR
            # ----------------------------------------------

            decision["decision"] = (
                "TRACE_MISSING_SYMBOL"
            )

            decision["confidence"] = 0.90

            decision["next_actions"] = [
                "locate producer",
                "inspect producer output",
                "locate first consumer",
                "verify execution ordering",
                "verify dependency chain",
                "reproduce in isolated subprocess",
                "repair only after contract verification",
                "re-run runtime probe",
            ]

            return decision

        # ----------------------------------------------------
        # OTHER ERRORS
        # ----------------------------------------------------

        decision["decision"] = (
            "FORENSIC_RUNTIME_INVESTIGATION"
        )

        decision["confidence"] = 0.50

        decision["next_actions"] = [
            "capture complete traceback",
            "map failing line to source",
            "inspect AST context",
            "inspect dependency graph",
            "reproduce in isolated subprocess",
            "identify smallest causal boundary",
            "form competing hypotheses",
            "select evidence-supported repair",
            "validate repair",
        ]

        knowledge["unknown"].append(
            "The current runtime failure is not yet mapped to a safe repair boundary."
        )

        return decision


# ============================================================
# CONTRACT TRACER
# ============================================================

class ContractTracer:

    def __init__(
        self,
        inspector: SourceIntrospector,
    ):
        self.inspector = inspector

    def trace_symbol(
        self,
        symbol: str,
    ):

        evidence = {
            "symbol": symbol,
            "definition":
                self.inspector.definitions.get(
                    symbol
                ),
            "assignments":
                self.inspector.assignments.get(
                    symbol,
                    [],
                ),
            "references":
                self.inspector.references.get(
                    symbol,
                    [],
                ),
            "producer_exists": bool(
                self.inspector.assignments.get(
                    symbol
                )
                or self.inspector.definitions.get(
                    symbol
                )
            ),
        }

        contexts = []

        for line in evidence["references"]:

            contexts.append(
                self.inspector.line_context(
                    line,
                    radius=10,
                )
            )

        evidence[
            "reference_contexts"
        ] = contexts

        return evidence

    def trace_tokenization(self):

        result = {
            "symbols": {},
            "corpus_producers": [],
            "tokenization_functions": [],
            "likely_contract": [],
        }

        for symbol in sorted(
            TOKEN_SYMBOLS
        ):

            result["symbols"][symbol] = (
                self.trace_symbol(symbol)
            )

        # ----------------------------------------------------
        # TOKENIZATION FUNCTIONS
        # ----------------------------------------------------

        for name, info in (
            self.inspector.functions.items()
        ):

            segment = (
                self.inspector.source_segment(
                    name
                )
            )

            if not segment:
                continue

            lower = segment.lower()

            token_words = [
                "stoi",
                "itos",
                "vocab",
                "encode",
                "decode",
                "token",
                "tokens",
            ]

            if any(
                word in lower
                for word in token_words
            ):

                result[
                    "tokenization_functions"
                ].append({
                    "name": name,
                    "line": info["line"],
                    "end_line": info["end_line"],
                })

        # ----------------------------------------------------
        # REAL CORPUS
        # ----------------------------------------------------

        for filename in [
            "bloom_train_v2.txt",
            "bloom_valid_v2.txt",
            "my_texts.txt",
        ]:

            path = ROOT / filename

            if path.exists():

                result[
                    "corpus_producers"
                ].append({
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                })

        # ----------------------------------------------------
        # CONTRACT ASSESSMENT
        # ----------------------------------------------------

        for symbol in [
            "stoi",
            "itos",
            "vocab_size",
        ]:

            info = result[
                "symbols"
            ][symbol]

            if info["producer_exists"]:

                result["likely_contract"].append(
                    f"{symbol} has an existing source producer."
                )

            else:

                result["likely_contract"].append(
                    f"{symbol} has no discovered source producer."
                )

        return result

    def model_contract(self):

        result = {
            "GPT": self.trace_symbol("GPT"),
            "model": self.trace_symbol("model"),
            "params": self.trace_symbol("params"),
            "calls": [],
        }

        for call in self.inspector.calls:

            if (
                call["name"] == "GPT"
                or call["name"].endswith(".GPT")
            ):

                result["calls"].append(call)

        return result

    def batching_contract(self):

        return {
            "get_batch":
                self.trace_symbol("get_batch"),
            "data":
                self.trace_symbol("data"),
            "validation_data":
                self.trace_symbol(
                    "validation_data"
                ),
        }

    def inference_contract(self):

        return {
            "generate":
                self.trace_symbol("generate"),
            "retrieve":
                self.trace_symbol("retrieve"),
        }

    def full_trace(self):

        return {
            "tokenization":
                self.trace_tokenization(),
            "model":
                self.model_contract(),
            "batching":
                self.batching_contract(),
            "inference":
                self.inference_contract(),
            "definitions":
                self.inspector.definitions,
            "references":
                self.inspector.references,
            "assignments":
                self.inspector.assignments,
            "functions":
                self.inspector.functions,
            "classes":
                self.inspector.classes,
        }


# ============================================================
# REPAIR SAFETY
# ============================================================

class RepairSafety:

    def __init__(self):

        BACKUP_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

    def backup(
        self,
        path: Path,
    ):

        timestamp = time.strftime(
            "%Y%m%d_%H%M%S"
        )

        destination = (
            BACKUP_DIR
            / f"{path.name}.{timestamp}.bak"
        )

        shutil.copy2(
            path,
            destination,
        )

        return destination


# ============================================================
# VALIDATION
# ============================================================

class ValidationEngine:

    def __init__(
        self,
        terminal: AutonomousTerminal,
    ):
        self.terminal = terminal

    def compile(self):

        return self.terminal.run(
            "python3 -m py_compile bloom_real.py",
            timeout=120,
        )

    def import_probe(self):

        return RuntimeProbe(
            self.terminal
        ).import_model()

    def corpus_probe(self):

        return RuntimeProbe(
            self.terminal
        ).corpus_probe()


# ============================================================
# BLOOM OPERATOR
# ============================================================

class BloomAutonomousOperator:

    def __init__(self):

        self.terminal = (
            AutonomousTerminal()
        )

        self.inspector = (
            SourceIntrospector()
        )

        self.tracer = None

        self.discerner = (
            ErrorDiscerner()
        )

        self.safety = (
            RepairSafety()
        )

        self.validation = (
            ValidationEngine(
                self.terminal
            )
        )

        self.state = {
            "system": "BLOOM",
            "operator":
                "evidence-first",
            "mode":
                "OBSERVE -> TRACE -> DISCERN -> VERIFY",
            "started": now(),
            "cycles": [],
        }

    # --------------------------------------------------------
    # INSPECTION
    # --------------------------------------------------------

    def inspect(self):

        self.inspector.load()

        self.tracer = ContractTracer(
            self.inspector
        )

        return self.inspector.summary()

    # --------------------------------------------------------
    # PROBE
    # --------------------------------------------------------

    def probe(self):

        result = self.validation.import_probe()

        error = self.discerner.classify(
            result.stdout,
            result.stderr,
            result.returncode,
        )

        return result, error

    # --------------------------------------------------------
    # PRINT SYMBOL
    # --------------------------------------------------------

    def print_symbol(
        self,
        name: str,
    ):

        evidence = (
            self.tracer.trace_symbol(name)
        )

        print()
        print(
            f"--- SYMBOL: {name} ---"
        )

        print(
            "DEFINITION:",
            evidence["definition"],
        )

        print(
            "REFERENCES:",
            evidence["references"],
        )

        print(
            "PRODUCER:",
            evidence["producer_exists"],
        )

        for assignment in (
            evidence["assignments"]
        ):

            print(
                "ASSIGNMENT:",
                assignment["line"],
                "reads=",
                assignment["reads"],
            )

            print(
                assignment["source"]
            )

    # --------------------------------------------------------
    # DEEP TRACE
    # --------------------------------------------------------

    def print_deep_trace(
        self,
        trace: dict[str, Any],
    ):

        print()
        print("=" * 80)
        print(
            "DEEP TOKENIZATION CONTRACT TRACE"
        )
        print("=" * 80)

        tokenization = trace[
            "tokenization"
        ]

        print()
        print("CORPUS EVIDENCE:")

        for corpus in (
            tokenization[
                "corpus_producers"
            ]
        ):

            print(
                " ",
                corpus["path"],
                "bytes=",
                corpus["bytes"],
                "sha256=",
                corpus["sha256"],
            )

        if not tokenization[
            "corpus_producers"
        ]:

            print(
                "  NO KNOWN CORPUS FILE FOUND"
            )

        print()
        print(
            "TOKENIZATION FUNCTIONS:"
        )

        for fn in (
            tokenization[
                "tokenization_functions"
            ]
        ):

            print(
                " ",
                fn,
            )

        if not tokenization[
            "tokenization_functions"
        ]:

            print(
                "  NONE DISCOVERED"
            )

        print()

        for symbol in [
            "VALIDATION_TEXT",
            "stoi",
            "itos",
            "vocab_size",
            "data",
            "validation_data",
        ]:

            self.print_symbol(symbol)

        print()
        print("=" * 80)
        print("MODEL CONTRACT")
        print("=" * 80)

        print(
            json.dumps(
                trace["model"],
                indent=2,
                default=str,
            )
        )

        print()
        print("=" * 80)
        print("BATCH CONTRACT")
        print("=" * 80)

        print(
            json.dumps(
                trace["batching"],
                indent=2,
                default=str,
            )
        )

        print()
        print("=" * 80)
        print("INFERENCE CONTRACT")
        print("=" * 80)

        print(
            json.dumps(
                trace["inference"],
                indent=2,
                default=str,
            )
        )

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    def run(
        self,
        max_cycles: int = 5,
    ):

        print("=" * 80)
        print("BLOOM AUTONOMOUS OPERATOR")
        print("=" * 80)

        print(
            "MODE:",
            "OBSERVE -> TRACE -> DISCERN -> VERIFY",
        )

        print(
            "POLICY:",
            "EVIDENCE-FIRST / NO FABRICATION",
        )

        print(
            "MODEL:",
            MODEL,
        )

        print()

        for cycle_number in range(
            1,
            max_cycles + 1,
        ):

            cycle_started = now()

            print("=" * 80)
            print(
                f"CYCLE {cycle_number}"
            )
            print("=" * 80)

            try:

                source = self.inspect()

                print(
                    "AST: SUCCESS"
                )

                print(
                    "DEFINITIONS:",
                    len(
                        source[
                            "definitions"
                        ]
                    ),
                )

                print(
                    "FUNCTIONS:",
                    len(
                        source[
                            "functions"
                        ]
                    ),
                )

                print(
                    "CLASSES:",
                    len(
                        source[
                            "classes"
                        ]
                    ),
                )

            except Exception as exc:

                print(
                    "AST FAILURE:",
                    type(exc).__name__,
                    str(exc),
                )

                traceback.print_exc()

                self.state[
                    "fatal_error"
                ] = {
                    "type":
                        type(exc).__name__,
                    "detail":
                        str(exc),
                }

                break

            runtime, error = self.probe()

            print()
            print(
                "RUNTIME:",
                error["category"],
            )

            print(
                "DETAIL:",
                error["detail"],
            )

            trace = self.tracer.full_trace()

            decision = (
                self.discerner.analyze(
                    error,
                    trace,
                )
            )

            cycle = {
                "cycle":
                    cycle_number,
                "timestamp":
                    now(),
                "runtime":
                    runtime.as_dict(),
                "error":
                    error,
                "decision":
                    decision,
                "trace":
                    trace,
                "source": {
                    "sha256":
                        source["sha256"],
                    "definitions":
                        source["definitions"],
                    "functions":
                        source["functions"],
                    "classes":
                        source["classes"],
                    "unresolved":
                        source[
                            "unresolved_references"
                        ],
                },
                "duration":
                    now() - cycle_started,
            }

            self.state[
                "cycles"
            ].append(cycle)

            print()
            print("=" * 80)
            print("DISCERNMENT")
            print("=" * 80)

            print(
                "DECISION:",
                decision["decision"],
            )

            print(
                "CONFIDENCE:",
                decision["confidence"],
            )

            print()
            print("KNOWN:")

            for item in (
                decision[
                    "knowledge"
                ]["known"]
            ):

                print(
                    "  +",
                    item,
                )

            print()
            print("INFERRED:")

            for item in (
                decision[
                    "knowledge"
                ]["inferred"]
            ):

                print(
                    "  ~",
                    item,
                )

            print()
            print("UNKNOWN:")

            for item in (
                decision[
                    "knowledge"
                ]["unknown"]
            ):

                print(
                    "  ?",
                    item,
                )

            print()
            print("NEXT ACTIONS:")

            for index, action in enumerate(
                decision[
                    "next_actions"
                ],
                start=1,
            ):

                print(
                    f"  {index:02d}.",
                    action,
                )

            # ------------------------------------------------
            # DEEP TOKEN TRACE
            # ------------------------------------------------

            if (
                error["category"]
                == "NAME_ERROR"
                and error["detail"]
                in TOKEN_SYMBOLS
            ):

                self.print_deep_trace(
                    trace
                )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if (
                error["category"]
                == "NO_ERROR"
            ):

                print()
                print("=" * 80)
                print("IMPORT CONTRACT: PASS")
                print("=" * 80)

                print(
                    "BLOOM has passed module import."
                )

                print(
                    "TRAINING IS STILL LOCKED."
                )

                print(
                    "NEXT GATE:",
                    "vocabulary -> batch -> model -> "
                    "gradient -> checkpoint -> generation",
                )

                break

            # ------------------------------------------------
            # SAFETY GATE
            # ------------------------------------------------

            if (
                decision["confidence"]
                < 0.80
            ):

                print()
                print("=" * 80)
                print("AUTONOMY HALTED")
                print("=" * 80)

                print(
                    "Reason:",
                    "insufficient evidence for safe repair.",
                )

                break

            # ------------------------------------------------
            # MISSING TOKEN PRODUCER
            # ------------------------------------------------

            if (
                decision["decision"]
                == "TOKEN_PRODUCER_MISSING"
            ):

                print()
                print("=" * 80)
                print("REPAIR BOUNDARY REACHED")
                print("=" * 80)

                print(
                    "The operator has established that "
                    "the runtime vocabulary producer is absent."
                )

                print()
                print("CRITICAL:")

                print(
                    "No vocabulary, token IDs, validation IDs, "
                    "or model dimensions will be fabricated."
                )

                print()
                print(
                    "The next task is reconstruction of the "
                    "exact producer contract from real source evidence."
                )

                print()
                print(
                    "REPAIR STATUS:",
                    "NOT EXECUTED",
                )

                break

            # ------------------------------------------------
            # EXISTING PRODUCER
            # ------------------------------------------------

            if (
                decision["decision"]
                == "TRACE_EXISTING_TOKEN_PRODUCER"
            ):

                print()
                print("=" * 80)
                print("EXISTING PRODUCER FOUND")
                print("=" * 80)

                print(
                    "The producer exists in source."
                )

                print(
                    "Next operation:",
                    "producer ordering + dependency validation",
                )

                break

            print()
            print(
                "No safe autonomous modification boundary "
                "established in this cycle."
            )

            break

        # ----------------------------------------------------
        # SAVE STATE
        # ----------------------------------------------------

        self.state[
            "finished"
        ] = now()

        write_json(
            STATE_FILE,
            self.state,
        )

        print()
        print("=" * 80)
        print("AUTONOMOUS OPERATOR STATE")
        print("=" * 80)

        print(
            "STATE:",
            STATE_FILE,
        )

        print(
            "LEDGER:",
            LEDGER_FILE,
        )

        print(
            "BACKUPS:",
            BACKUP_DIR,
        )

        print("=" * 80)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        BloomAutonomousOperator().run(
            max_cycles=5
        )

    except KeyboardInterrupt:

        print()
        print(
            "OPERATOR INTERRUPTED"
        )

    except Exception as exc:

        print()
        print("=" * 80)
        print("OPERATOR FAILURE")
        print("=" * 80)

        print(
            type(exc).__name__,
            ":",
            exc,
        )

        traceback.print_exc()

        raise
