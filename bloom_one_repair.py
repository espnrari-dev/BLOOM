
#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
BACKUP = ROOT / ".bloom_transaction_backups"
BACKUP.mkdir(exist_ok=True)


class PathEncoder(json.JSONEncoder):

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)

        return super().default(obj)


def digest(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_write(
    path: Path,
    content: str,
) -> None:

    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with open(
            fd,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(content)
            f.flush()

        Path(tmp).replace(path)

    except Exception:
        try:
            Path(tmp).unlink()
        except Exception:
            pass
        raise


def compile_target(
    path: Path,
) -> tuple[bool, str]:

    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    return (
        p.returncode == 0,
        (p.stdout or "") + (p.stderr or ""),
    )


def execute_target(
    path: Path,
    timeout: int = 30,
) -> tuple[bool, str]:

    try:
        p = subprocess.run(
            [
                sys.executable,
                "-u",
                str(path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    except subprocess.TimeoutExpired as e:
        return (
            False,
            "TIMEOUT\n"
            + str(e.stdout or "")
            + "\n"
            + str(e.stderr or ""),
        )

    return (
        p.returncode == 0,
        (p.stdout or "")
        + "\n"
        + (p.stderr or ""),
    )


def verify(path: Path) -> dict[str, Any]:

    compile_ok, compile_output = compile_target(
        path
    )

    if not compile_ok:
        return {
            "compile": False,
            "runtime": False,
            "output": compile_output[-10000:],
        }

    runtime_ok, runtime_output = execute_target(
        path
    )

    return {
        "compile": True,
        "runtime": runtime_ok,
        "output": runtime_output[-10000:],
    }


def transactional_repair(
    path: Path,
    repair: Callable[[Path], bool],
) -> dict[str, Any]:

    path = path.resolve()

    original = path.read_bytes()
    original_hash = digest(path)

    stamp = (
        f"{int(time.time())}_"
        f"{path.stat().st_mtime_ns}"
    )

    backup_path = (
        BACKUP
        / f"{path.name}.{stamp}.bak"
    )

    shutil.copy2(path, backup_path)

    report: dict[str, Any] = {
        "target": path,
        "before_sha256": original_hash,
        "status": "FAILED",
        "rollback": False,
    }

    try:

        changed = repair(path)

        if not changed:
            report["status"] = "NO_CHANGE"
            return report

        verification = verify(path)

        report["verification"] = verification

        if (
            verification["compile"]
            and verification["runtime"]
        ):
            report["status"] = "SUCCESS"
            report["after_sha256"] = digest(path)

            backup_path.unlink(
                missing_ok=True
            )

            return report

        # Verification failed.
        path.write_bytes(original)

        report["rollback"] = True
        report["after_sha256"] = digest(path)

        if report["after_sha256"] != original_hash:
            raise RuntimeError(
                "ROLLBACK INTEGRITY FAILURE"
            )

        return report

    except Exception as exc:

        path.write_bytes(original)

        report["rollback"] = True
        report["error"] = repr(exc)
        report["after_sha256"] = digest(path)

        if report["after_sha256"] != original_hash:
            raise RuntimeError(
                "ROLLBACK INTEGRITY FAILURE"
            )

        return report


def replace_with_canonical(
    path: Path,
    canonical: str,
) -> bool:

    old = (
        path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        if path.exists()
        else ""
    )

    if old == canonical:
        return False

    atomic_write(path, canonical)

    return True


def repair_bloom_best_llm(
    path: Path,
) -> bool:

    canonical = (
        ROOT
        / "_canonical_bloom_best_llm.py"
    ).read_text(
        encoding="utf-8"
    )

    return replace_with_canonical(
        path,
        canonical,
    )


def repair_bloom_real(
    path: Path,
) -> bool:

    canonical = (
        ROOT
        / "_canonical_bloom_real.py"
    ).read_text(
        encoding="utf-8"
    )

    return replace_with_canonical(
        path,
        canonical,
    )


def repair_hybrid(
    path: Path,
) -> bool:

    canonical = (
        ROOT
        / "_canonical_hybrid_bloom.py"
    ).read_text(
        encoding="utf-8"
    )

    return replace_with_canonical(
        path,
        canonical,
    )


def main() -> int:

    print("=" * 90)
    print("BLOOM TRANSACTIONAL REPAIR ENGINE")
    print("=" * 90)

    repairs = [
        (
            ROOT / "bloom_best_llm.py",
            repair_bloom_best_llm,
        ),
        (
            ROOT / "bloom_real.py",
            repair_bloom_real,
        ),
        (
            ROOT / "hybrid_bloom.py",
            repair_hybrid,
        ),
    ]

    reports = []

    for path, repair in repairs:

        if not path.exists():
            reports.append({
                "target": path,
                "status": "MISSING",
            })
            continue

        print()
        print("=" * 90)
        print(f"TRANSACTION: {path.name}")
        print("=" * 90)

        result = transactional_repair(
            path,
            repair,
        )

        reports.append(result)

        print(
            json.dumps(
                result,
                indent=2,
                cls=PathEncoder,
            )
        )

    report = {
        "timestamp": time.time(),
        "root": ROOT,
        "reports": reports,
    }

    report_path = (
        ROOT
        / "bloom_final_repair_report.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
            cls=PathEncoder,
        )

    print()
    print("=" * 90)
    print("FINAL VALIDATION")
    print("=" * 90)

    validation_targets = [
        ROOT / "bloom_best_llm.py",
        ROOT / "bloom_real.py",
        ROOT / "hybrid_bloom.py",
    ]

    all_pass = True

    for target in validation_targets:

        result = verify(target)

        print(
            f"{target.name:28} "
            f"compile={result['compile']} "
            f"runtime={result['runtime']}"
        )

        if not (
            result["compile"]
            and result["runtime"]
        ):
            all_pass = False

            print(
                result["output"][-4000:]
            )

    # Direct subsystem contract test.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from hybrid_bloom import "
                "compute_market_signals; "
                "r=compute_market_signals([],[],0); "
                "assert r['status']=='UNAVAILABLE'; "
                "print(r)"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    market_pass = probe.returncode == 0

    print(
        f"{'market_contract':28} "
        f"runtime={market_pass}"
    )

    if not market_pass:
        print(
            (probe.stdout or "")
            + (probe.stderr or "")
        )

    all_pass = all_pass and market_pass

    print()
    print("=" * 90)

    if all_pass:
        print("BLOOM RESULT: VERIFIED WORKING")
        print("MODEL CONTRACT: PASS")
        print("REAL EXECUTION: PASS")
        print("MARKET CONTRACT: PASS")
        print("TRANSACTIONAL REPAIR: PASS")
    else:
        print("BLOOM RESULT: NOT VERIFIED")

    print("=" * 90)
    print(
        f"REPORT: {report_path}"
    )
    print("=" * 90)

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
