#!/usr/bin/env python3

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


ROOT = Path.home() / "BLOOM"
MODEL = ROOT / "bloom_real.py"

STATE_FILE = ROOT / "bloom_operator_state.json"
LEDGER_FILE = ROOT / "bloom_operator_ledger.jsonl"


# ============================================================
# CORE DATA TYPES
# ============================================================

@dataclass
class CommandResult:
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool

    @property
    def success(self):
        return (
            self.returncode == 0
            and not self.timed_out
        )

    def as_dict(self):
        return asdict(self)


# ============================================================
# AUTONOMOUS TERMINAL
# ============================================================

class BloomTerminal:

    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def snapshot(self):
        result = {}

        for path in self.root.rglob("*"):

            if not path.is_file():
                continue

            # Do not allow the terminal's own logs to become
            # an uncontrolled recursive observation surface.
            try:
                rel = path.relative_to(self.root)
            except Exception:
                continue

            try:
                raw = path.read_bytes()
            except Exception:
                continue

            result[str(rel)] = {
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

        return result

    def run(
        self,
        command,
        timeout=120,
        cwd=None,
    ):

        cwd = (
            self.root
            if cwd is None
            else Path(cwd).resolve()
        )

        if self.root not in cwd.parents and cwd != self.root:
            raise ValueError(
                "Terminal cwd escaped BLOOM root."
            )

        before = self.snapshot()

        started = time.time()

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
                duration=time.time() - started,
                timed_out=False,
            )

        except subprocess.TimeoutExpired as e:

            stdout = e.stdout or ""
            stderr = e.stderr or ""

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
                duration=time.time() - started,
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

        record = {
            "timestamp": time.time(),
            "type": "terminal_execution",
            "command": command,
            "cwd": str(cwd),
            "result": result.as_dict(),
            "changed_files": changed,
        }

        self.record(record)

        return result

    def record(self, record):

        with LEDGER_FILE.open(
            "a",
            encoding="utf-8",
        ) as f:

            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )


# ============================================================
# SOURCE INTROSPECTION
# ============================================================

class SourceIntrospector:

    def __init__(self, model=MODEL):

        self.model = Path(model)

        self.source = ""
        self.tree = None

        self.definitions = {}
        self.references = {}
        self.functions = {}
        self.classes = {}
        self.imports = set()

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

        self._inspect()

        return self

    def _inspect(self):

        self.definitions.clear()
        self.references.clear()
        self.functions.clear()
        self.classes.clear()
        self.imports.clear()

        # Imports

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

        # Top-level definitions

        for node in self.tree.body:

            if isinstance(node, ast.Assign):

                for target in node.targets:

                    if isinstance(
                        target,
                        ast.Name,
                    ):

                        self.definitions[
                            target.id
                        ] = {
                            "line": node.lineno,
                            "kind": "assignment",
                        }

            elif isinstance(
                node,
                ast.AnnAssign,
            ):

                if isinstance(
                    node.target,
                    ast.Name,
                ):

                    self.definitions[
                        node.target.id
                    ] = {
                        "line": node.lineno,
                        "kind": "assignment",
                    }

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):

                self.definitions[
                    node.name
                ] = {
                    "line": node.lineno,
                    "kind": type(node).__name__,
                }

        # Functions/classes anywhere

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

        # References

        for node in ast.walk(self.tree):

            if not isinstance(
                node,
                ast.Name,
            ):
                continue

            if not isinstance(
                node.ctx,
                ast.Load,
            ):
                continue

            self.references.setdefault(
                node.id,
                [],
            ).append(node.lineno)

    def source_segment(
        self,
        name,
    ):

        node = None

        if name in self.functions:

            target_line = self.functions[
                name
            ]["line"]

            for n in ast.walk(self.tree):

                if isinstance(
                    n,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ) and n.name == name:

                    if n.lineno == target_line:
                        node = n
                        break

        elif name in self.classes:

            target_line = self.classes[
                name
            ]["line"]

            for n in ast.walk(self.tree):

                if isinstance(
                    n,
                    ast.ClassDef,
                ) and n.name == name:

                    if n.lineno == target_line:
                        node = n
                        break

        if node is None:
            return None

        return ast.get_source_segment(
            self.source,
            node,
        )

    def top_level_source(self):

        return [
            {
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
                "type": type(node).__name__,
            }
            for node in self.tree.body
        ]

    def unresolved_references(
        self,
        names=None,
    ):

        if names is None:
            names = sorted(
                self.references
            )

        result = {}

        builtin_names = set(
            dir(__builtins__)
        )

        for name in names:

            if name in self.definitions:
                continue

            if name in self.imports:
                continue

            if name in builtin_names:
                continue

            result[name] = self.references.get(
                name,
                [],
            )

        return result


# ============================================================
# RUNTIME PROBE
# ============================================================

class RuntimeProbe:

    def __init__(
        self,
        terminal,
    ):

        self.terminal = terminal

    def import_model(self):

        probe = r'''
import sys
import traceback

sys.path.insert(
    0,
    %r
)

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
        "model",
        "params",
        "adam_m",
        "adam_v",
        "best_loss",
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

except Exception as e:

    print(
        "BLOOM_IMPORT_FAILURE",
        type(e).__name__,
        str(e),
    )

    traceback.print_exc()
''' % str(ROOT)

        return self.terminal.run(
            f"{shlex.quote(sys.executable)} -c {shlex.quote(probe)}",
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
        stdout,
        stderr,
        returncode,
    ):

        text = (
            (stdout or "")
            + "\n"
            + (stderr or "")
        )

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
                    "raw": text[-5000:],
                }

        if returncode == 0:

            return {
                "category": "NO_ERROR",
                "detail": "",
                "confidence": 1.0,
                "raw": text[-5000:],
            }

        return {
            "category": "UNKNOWN_RUNTIME_FAILURE",
            "detail": text[-2000:],
            "confidence": 0.25,
            "raw": text[-5000:],
        }


# ============================================================
# DEPENDENCY / NEXT-STEP REASONER
# ============================================================

class NextStepReasoner:

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

    def __init__(
        self,
        inspector,
    ):

        self.inspector = inspector

    def required_symbol_report(self):

        result = {}

        for name in self.REQUIRED:

            result[name] = {
                "defined": (
                    name in self.inspector.definitions
                ),
                "definition": self.inspector.definitions.get(
                    name
                ),
                "references": self.inspector.references.get(
                    name,
                    [],
                ),
            }

        return result

    def dependency_report(self):

        report = {}

        for name in [
            "load_text",
            "get_batch",
            "save_ckpt",
            "generate",
            "retrieve",
        ]:

            if name not in self.inspector.functions:
                continue

            segment = self.inspector.source_segment(
                name
            )

            if not segment:
                continue

            try:
                tree = ast.parse(
                    segment
                )
            except Exception:
                continue

            loads = sorted({
                n.id
                for n in ast.walk(tree)
                if isinstance(
                    n,
                    ast.Name,
                )
                and isinstance(
                    n.ctx,
                    ast.Load,
                )
            })

            report[name] = {

                "reads": loads,

                "undefined_reads": [
                    x
                    for x in loads
                    if (
                        x not in self.inspector.definitions
                        and x not in self.inspector.imports
                        and x not in dir(__builtins__)
                    )
                ],
            }

        return report

    def decide(
        self,
        runtime_error,
    ):

        symbols = self.required_symbol_report()
        dependencies = self.dependency_report()

        missing = [
            name
            for name, info in symbols.items()
            if not info["defined"]
        ]

        category = runtime_error[
            "category"
        ]

        decision = {
            "decision": None,
            "confidence": 0.0,
            "reason": [],
            "next_actions": [],
            "do_not_do": [],
        }

        # ----------------------------------------------------
        # CURRENT BLOOM CONDITION
        # ----------------------------------------------------

        if category == "NAME_ERROR":

            missing_name = runtime_error[
                "detail"
            ]

            if (
                missing_name
                in symbols
                and not symbols[
                    missing_name
                ]["defined"]
            ):

                decision["decision"] = (
                    "TRACE_MISSING_SYMBOL"
                )

                decision["confidence"] = 1.0

                decision["reason"].append(
                    f"{missing_name} is referenced "
                    "during top-level execution but "
                    "has no top-level definition."
                )

                refs = symbols[
                    missing_name
                ]["references"]

                decision["reason"].append(
                    f"Static references occur at lines {refs}."
                )

                decision["next_actions"].extend([
                    "inspect the producer function/source "
                    "for the missing symbol",
                    "determine whether the producer returns "
                    "the required value",
                    "determine where the value should enter "
                    "the runtime",
                    "repair only after the data contract "
                    "is established",
                    "re-run AST inspection",
                    "re-run import probe",
                ])

                decision["do_not_do"].extend([
                    "do not insert a guessed assignment",
                    "do not create synthetic vocabulary",
                    "do not invent stoi/itos/data values",
                    "do not declare the runtime repaired "
                    "until import succeeds",
                ])

                return decision

        # ----------------------------------------------------
        # MISSING DATA PIPELINE
        # ----------------------------------------------------

        pipeline_missing = [
            x
            for x in [
                "stoi",
                "itos",
                "vocab_size",
                "data",
            ]
            if not symbols[x]["defined"]
        ]

        if pipeline_missing:

            decision["decision"] = (
                "RECONSTRUCT_DATA_PIPELINE"
            )

            decision["confidence"] = 0.98

            decision["reason"].append(
                "The model has a broken vocabulary/data "
                "runtime contract, not merely one missing name."
            )

            decision["reason"].append(
                "The missing symbols are consumed by "
                "checkpointing, generation, and batching."
            )

            decision["next_actions"].extend([
                "inspect load_text() completely",
                "inspect its return values",
                "identify training corpus",
                "identify validation corpus",
                "construct stoi and itos from verified corpus",
                "derive vocab_size from itos/stoi",
                "construct data from the same verified vocabulary",
                "verify get_batch() against data length",
                "verify checkpoint serialization",
                "verify generation lookup",
                "import the model",
                "execute one forward pass",
                "execute one backward pass",
                "only then permit training",
            ])

            decision["do_not_do"].extend([
                "do not guess an insertion point",
                "do not hard-code vocab_size",
                "do not use random vocabulary",
                "do not fabricate training data",
            ])

            return decision

        # ----------------------------------------------------
        # OTHERWISE
        # ----------------------------------------------------

        decision["decision"] = (
            "INVESTIGATE_RUNTIME_FAILURE"
        )

        decision["confidence"] = 0.5

        decision["reason"].append(
            "The observed error does not map cleanly "
            "to a verified missing runtime dependency."
        )

        decision["next_actions"].extend([
            "capture complete traceback",
            "map failing line to AST node",
            "inspect local/global dependencies",
            "reproduce in isolated subprocess",
            "verify the smallest causal boundary",
        ])

        return decision


# ============================================================
# VERIFIED REPAIR PLAN GENERATOR
# ============================================================

class RepairPlanner:

    def __init__(
        self,
        inspector,
        reasoner,
    ):

        self.inspector = inspector
        self.reasoner = reasoner

    def build(self):

        load_text = (
            self.inspector.source_segment(
                "load_text"
            )
            or ""
        )

        get_batch = (
            self.inspector.source_segment(
                "get_batch"
            )
            or ""
        )

        return {

            "repair_policy":
                "EVIDENCE_FIRST",

            "source_integrity": {
                "bytes": len(
                    self.inspector.source.encode(
                        "utf-8"
                    )
                ),
                "sha256":
                    hashlib.sha256(
                        self.inspector.source.encode(
                            "utf-8"
                        )
                    ).hexdigest(),
            },

            "load_text_source":
                load_text,

            "get_batch_source":
                get_batch,

            "required_symbols":
                self.reasoner.required_symbol_report(),

            "dependencies":
                self.reasoner.dependency_report(),

            "repair_order": [

                {
                    "stage": 1,
                    "name": "CORPUS_CONTRACT",
                    "purpose":
                        "Establish exactly what load_text "
                        "loads and returns.",
                },

                {
                    "stage": 2,
                    "name": "VOCABULARY_CONTRACT",
                    "purpose":
                        "Establish stoi, itos and vocab_size "
                        "from the verified corpus.",
                },

                {
                    "stage": 3,
                    "name": "TOKEN_DATA_CONTRACT",
                    "purpose":
                        "Establish data and validation data "
                        "with explicit provenance.",
                },

                {
                    "stage": 4,
                    "name": "BATCH_CONTRACT",
                    "purpose":
                        "Verify get_batch() can legally sample "
                        "the resulting data.",
                },

                {
                    "stage": 5,
                    "name": "MODEL_CONTRACT",
                    "purpose":
                        "Instantiate GPT only after vocabulary "
                        "dimensions are valid.",
                },

                {
                    "stage": 6,
                    "name": "GRADIENT_CONTRACT",
                    "purpose":
                        "Execute forward/backward without training.",
                },

                {
                    "stage": 7,
                    "name": "CHECKPOINT_CONTRACT",
                    "purpose":
                        "Verify checkpoint state can be serialized.",
                },

                {
                    "stage": 8,
                    "name": "GENERATION_CONTRACT",
                    "purpose":
                        "Verify stoi/itos/model generation path.",
                },

                {
                    "stage": 9,
                    "name": "TRAINING_PERMISSION",
                    "purpose":
                        "Permit training only after all prior stages pass.",
                },
            ],

            "current_status":
                "REPAIR_REQUIRED",
        }


# ============================================================
# SYSTEM EXECUTION
# ============================================================

class BloomOperator:

    def __init__(self):

        self.terminal = BloomTerminal()

        self.inspector = (
            SourceIntrospector()
        )

        self.discerner = (
            ErrorDiscerner()
        )

        self.inspector.load()

        self.reasoner = (
            NextStepReasoner(
                self.inspector
            )
        )

        self.planner = (
            RepairPlanner(
                self.inspector,
                self.reasoner,
            )
        )

    def run(self):

        started = time.time()

        print("=" * 80)
        print(
            "BLOOM AUTONOMOUS OPERATOR"
        )
        print("=" * 80)
        print(
            "MODE: EVIDENCE-FIRST"
        )
        print(
            "ROOT:",
            ROOT,
        )
        print(
            "MODEL:",
            MODEL,
        )

        print()
        print("=" * 80)
        print("1. SOURCE INTROSPECTION")
        print("=" * 80)

        print(
            "AST: SUCCESS"
        )

        print(
            "TOP-LEVEL DEFINITIONS:",
            len(
                self.inspector.definitions
            ),
        )

        print(
            "FUNCTIONS:",
            len(
                self.inspector.functions
            ),
        )

        print(
            "CLASSES:",
            len(
                self.inspector.classes
            ),
        )

        print()
        print("=" * 80)
        print("2. REQUIRED RUNTIME CONTRACT")
        print("=" * 80)

        symbols = (
            self.reasoner
            .required_symbol_report()
        )

        for name, info in symbols.items():

            print(
                f"{name:<22} "
                f"defined={info['defined']} "
                f"refs={info['references']}"
            )

        print()
        print("=" * 80)
        print("3. ACTUAL RUNTIME PROBE")
        print("=" * 80)

        runtime = (
            RuntimeProbe(
                self.terminal
            )
            .import_model()
        )

        print(
            runtime.stdout
        )

        if runtime.stderr:

            print(
                "--- STDERR ---"
            )

            print(
                runtime.stderr
            )

        error = (
            self.discerner.classify(
                runtime.stdout,
                runtime.stderr,
                runtime.returncode,
            )
        )

        print()
        print("=" * 80)
        print("4. ERROR DISCERNMENT")
        print("=" * 80)

        print(
            "CATEGORY:",
            error["category"],
        )

        print(
            "DETAIL:",
            error["detail"],
        )

        print(
            "CONFIDENCE:",
            error["confidence"],
        )

        print()
        print("=" * 80)
        print("5. NEXT-STEP REASONING")
        print("=" * 80)

        decision = (
            self.reasoner.decide(
                error
            )
        )

        print(
            "DECISION:",
            decision["decision"],
        )

        print(
            "CONFIDENCE:",
            decision["confidence"],
        )

        print()
        print("REASONS:")

        for item in decision["reason"]:

            print(
                " -",
                item,
            )

        print()
        print("NEXT ACTIONS:")

        for i, item in enumerate(
            decision["next_actions"],
            1,
        ):

            print(
                f" {i:02d}.",
                item,
            )

        print()
        print("DO NOT DO:")

        for item in decision["do_not_do"]:

            print(
                " -",
                item,
            )

        print()
        print("=" * 80)
        print("6. VERIFIED REPAIR PLAN")
        print("=" * 80)

        plan = self.planner.build()

        for stage in plan[
            "repair_order"
        ]:

            print(
                f"{stage['stage']:02d}. "
                f"{stage['name']}"
            )

            print(
                "    ",
                stage["purpose"],
            )

        print()
        print("=" * 80)
        print("7. CURRENT FORENSIC VERDICT")
        print("=" * 80)

        print(
            "STATUS: REPAIR_REQUIRED"
        )

        print(
            "FIRST OBSERVED FAILURE:",
            error["category"],
        )

        print(
            "FIRST OBSERVED DETAIL:",
            error["detail"],
        )

        print(
            "SYSTEM-LEVEL CONDITION:",
            decision["decision"],
        )

        print(
            "TRAINING PERMISSION: DENIED"
        )

        print(
            "REASON: Runtime contract is not verified."
        )

        state = {

            "timestamp":
                time.time(),

            "duration":
                time.time() - started,

            "model":
                str(MODEL),

            "model_sha256":
                hashlib.sha256(
                    MODEL.read_bytes()
                ).hexdigest(),

            "runtime_probe":
                runtime.as_dict(),

            "error":
                error,

            "decision":
                decision,

            "plan":
                plan,
        }

        STATE_FILE.write_text(
            json.dumps(
                state,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.terminal.record({
            "timestamp":
                time.time(),

            "type":
                "autonomous_forensic_cycle",

            "error":
                error,

            "decision":
                decision,

            "state_file":
                str(STATE_FILE),
        })

        print()
        print("=" * 80)
        print("8. MACHINE STATE")
        print("=" * 80)

        print(
            "STATE:",
            STATE_FILE,
        )

        print(
            "LEDGER:",
            LEDGER_FILE,
        )

        print("=" * 80)
        print(
            "END OF AUTONOMOUS FORENSIC CYCLE"
        )
        print("=" * 80)


if __name__ == "__main__":

    try:

        BloomOperator().run()

    except Exception as e:

        print()
        print("=" * 80)
        print("OPERATOR FAILURE")
        print("=" * 80)

        print(
            type(e).__name__,
            ":",
            e,
        )

        traceback.print_exc()

        raise
