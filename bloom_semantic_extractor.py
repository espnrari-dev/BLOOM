#!/usr/bin/env python3

from pathlib import Path
import ast
import re
import hashlib

ROOT = Path.home() / "BLOOM"
OUT = ROOT / "training_corpus_semantic_v2.txt"

EXTENSIONS = {".py", ".sh", ".txt", ".log", ".md", ".rst"}

SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
}

fragments = []

def add(source, text):
    text = text.strip()

    if not text:
        return

    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < 20:
        return

    # Reject obvious machine-only fragments.
    alpha = sum(c.isalpha() for c in text)
    if alpha < 12:
        return

    if len(text) > 50000:
        text = text[:50000]

    fragments.append((source, text))

def extract_python(path, text):
    try:
        tree = ast.parse(text)
    except Exception:
        return

    # Module/class/function docstrings.
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Module,
                ast.ClassDef,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            doc = ast.get_docstring(node, clean=True)
            if doc:
                add(str(path.relative_to(ROOT)), doc)

    # Natural-language comments.
    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("#"):
            comment = stripped[1:].strip()

            if comment.startswith("#"):
                comment = comment[1:].strip()

            add(str(path.relative_to(ROOT)), comment)

    # String literals that contain meaningful prose.
    try:
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value.strip()

                if len(value) >= 30 and len(value.split()) >= 5:
                    # Ignore obvious code/config strings.
                    if not re.fullmatch(
                        r"[\w./:=+\-{}[\](),'\" ]+",
                        value,
                    ):
                        add(str(path.relative_to(ROOT)), value)
    except Exception:
        pass


def extract_text(path, text):
    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith(("#", "//", ";")):
            line = re.sub(r"^(#|//|;)+\s*", "", line)

        add(str(path.relative_to(ROOT)), line)


for path in ROOT.rglob("*"):

    if not path.is_file():
        continue

    if any(part in SKIP_DIRS for part in path.parts):
        continue

    if path.name.startswith("training_corpus"):
        continue

    if path.name == "bloom_semantic_extractor.py":
        continue

    if path.suffix.lower() not in EXTENSIONS:
        continue

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        continue

    if not text.strip():
        continue

    if path.suffix.lower() == ".py":
        extract_python(path, text)
    else:
        extract_text(path, text)


# Deduplicate exact semantic fragments.
seen = set()
unique = []

for source, text in fragments:
    normalized = text.lower()

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    if digest in seen:
        continue

    seen.add(digest)
    unique.append((source, text))


with OUT.open("w", encoding="utf-8") as f:
    for source, text in unique:
        f.write(f"===== SOURCE: {source} =====\n")
        f.write(text)
        f.write("\n\n")


result = OUT.read_text(encoding="utf-8")

words = re.findall(
    r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
    result,
)

sources = set(
    re.findall(
        r"===== SOURCE: (.*?) =====",
        result,
    )
)

print("=" * 72)
print("BLOOM SEMANTIC EXTRACTOR V2")
print("=" * 72)
print(f"Fragments extracted : {len(fragments):,}")
print(f"Unique fragments    : {len(unique):,}")
print(f"Sources represented : {len(sources):,}")
print(f"Characters          : {len(result):,}")
print(f"Words               : {len(words):,}")
print(f"Bytes               : {OUT.stat().st_size:,}")
print(
    "SHA256              : "
    + hashlib.sha256(result.encode()).hexdigest()
)

print()
print("=" * 72)
print("SOURCE COVERAGE")
print("=" * 72)

coverage = {}

for source, text in unique:
    coverage.setdefault(source, 0)
    coverage[source] += len(
        re.findall(
            r"\b[A-Za-z][A-Za-z0-9_'-]*\b",
            text,
        )
    )

for source, count in sorted(
    coverage.items(),
    key=lambda x: x[1],
    reverse=True,
):
    print(f"{count:8,d} | {source}")

print()
print("=" * 72)
print("VERDICT")
print("=" * 72)

if len(words) >= 10000 and len(sources) >= 10:
    print("STATUS: RICH_SEMANTIC_CORPUS")
elif len(words) >= 3000 and len(sources) >= 5:
    print("STATUS: USABLE_SEMANTIC_CORPUS")
elif len(words) >= 1000:
    print("STATUS: SEMANTIC_CORPUS_READY")
else:
    print("STATUS: INSUFFICIENT_SEMANTIC_MATERIAL")

print(f"OUTPUT: {OUT}")
print("=" * 72)
