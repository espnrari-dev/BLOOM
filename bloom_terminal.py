#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path.home() / "BLOOM"
LOG = ROOT / "operator_terminal.jsonl"


class TerminalResult:
    def __init__(
        self,
        command: str,
        cwd: str,
        returncode: int,
        stdout: str,
        stderr: str,
        duration: float,
        timed_out: bool = False,
    ):
        self.command = command
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.timed_out = timed_out

    @property
    def success(self):
        return (
            self.returncode == 0
            and not self.timed_out
        )

    def as_dict(self):
        return {
            "command": self.command,
            "cwd": self.cwd,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "timed_out": self.timed_out,
            "success": self.success,
        }


class BloomTerminal:

    def __init__(self, root: Path = ROOT):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _record(self, record: dict[str, Any]):
        LOG.parent.mkdir(parents=True, exist_ok=True)

        with LOG.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    def snapshot(self):
        result = {}

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue

            try:
                raw = path.read_bytes()
            except Exception:
                continue

            rel = str(path.relative_to(self.root))

            result[rel] = {
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

        return result

    def run(
        self,
        command: str,
        timeout: int = 120,
        cwd: Path | None = None,
    ):

        if cwd is None:
            cwd = self.root
        else:
            cwd = Path(cwd).resolve()

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

            result = TerminalResult(
                command=command,
                cwd=str(cwd),
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration=time.time() - started,
            )

        except subprocess.TimeoutExpired as e:

            result = TerminalResult(
                command=command,
                cwd=str(cwd),
                returncode=-1,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                duration=time.time() - started,
                timed_out=True,
            )

        after = self.snapshot()

        changed = {}

        all_paths = set(before) | set(after)

        for path in sorted(all_paths):

            if before.get(path) != after.get(path):

                changed[path] = {
                    "before": before.get(path),
                    "after": after.get(path),
                }

        record = {
            "timestamp": time.time(),
            "command": command,
            "cwd": str(cwd),
            "result": result.as_dict(),
            "changed_files": changed,
        }

        self._record(record)

        return result


if __name__ == "__main__":

    terminal = BloomTerminal()

    print("=" * 80)
    print("BLOOM AUTONOMOUS TERMINAL")
    print("=" * 80)
    print(f"ROOT: {ROOT}")
    print(f"LOG : {LOG}")
    print()

    while True:

        try:
            command = input("BLOOM$ ")

        except EOFError:
            break

        if command.strip() in {
            "exit",
            "quit",
        }:
            break

        if not command.strip():
            continue

        result = terminal.run(command)

        print()
        print(
            f"EXIT={result.returncode} "
            f"SUCCESS={result.success}"
        )

        if result.stdout:
            print("--- STDOUT ---")
            print(result.stdout.rstrip())

        if result.stderr:
            print("--- STDERR ---")
            print(result.stderr.rstrip())

        print(
            f"--- {result.duration:.3f}s ---"
        )
        print()
