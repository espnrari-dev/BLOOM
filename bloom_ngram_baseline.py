#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import re
import math

ROOT = Path.home() / "BLOOM"
TRAIN = ROOT / "bloom_train_v2.txt"
VALID = ROOT / "bloom_valid_v2.txt"

TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_'-]*\b")

def tokenize(text):
    return TOKEN_RE.findall(text.lower())

def evaluate_ngram(train_lines, valid_lines, n):
    context_counts = Counter()
    ngram_counts = Counter()
    vocab = set()

    for line in train_lines:
        tokens = ["<BOS>"] * (n - 1) + tokenize(line) + ["<EOS>"]
        vocab.update(tokens)

        for i in range(n - 1, len(tokens)):
            gram = tuple(tokens[i - n + 1:i + 1])
            context = gram[:-1]
            ngram_counts[gram] += 1
            context_counts[context] += 1

    V = len(vocab)
    total_tokens = 0
    total_loss = 0.0
    unknown = 0

    for line in valid_lines:
        tokens = ["<BOS>"] * (n - 1) + tokenize(line) + ["<EOS>"]

        for i in range(n - 1, len(tokens)):
            gram = tuple(tokens[i - n + 1:i + 1])
            context = gram[:-1]
            word = gram[-1]

            numerator = ngram_counts[gram] + 1
            denominator = context_counts[context] + V

            probability = numerator / denominator

            total_loss -= math.log(probability)
            total_tokens += 1

            if word not in vocab:
                unknown += 1

    entropy = total_loss / max(1, total_tokens)
    perplexity = math.exp(entropy)

    return entropy, perplexity, total_tokens, unknown, len(vocab)

train_lines = [
    x.strip()
    for x in TRAIN.read_text(encoding="utf-8").splitlines()
    if x.strip()
]

valid_lines = [
    x.strip()
    for x in VALID.read_text(encoding="utf-8").splitlines()
    if x.strip()
]

print("=" * 72)
print("BLOOM N-GRAM BASELINE")
print("=" * 72)

print(f"Training records   : {len(train_lines):,}")
print(f"Validation records : {len(valid_lines):,}")

results = {}

for n, name in [(1, "UNIGRAM"), (2, "BIGRAM"), (3, "TRIGRAM")]:
    entropy, ppl, tokens, unknown, vocab = evaluate_ngram(
        train_lines,
        valid_lines,
        n
    )

    results[name] = ppl

    print()
    print("=" * 72)
    print(name)
    print("=" * 72)

    print(f"Vocabulary         : {vocab:,}")
    print(f"Evaluation tokens  : {tokens:,}")
    print(f"Unknown tokens     : {unknown:,}")
    print(f"Cross entropy      : {entropy:.6f}")
    print(f"Perplexity         : {ppl:.6f}")

print()
print("=" * 72)
print("COMPARISON")
print("=" * 72)

for name, ppl in results.items():
    print(f"{name:10s} | perplexity={ppl:.6f}")

if results["BIGRAM"] < results["UNIGRAM"]:
    print()
    print("BIGRAM IMPROVEMENT: SEQUENTIAL STRUCTURE DETECTED")
else:
    print()
    print("BIGRAM IMPROVEMENT: NONE")

if results["TRIGRAM"] < results["BIGRAM"]:
    print("TRIGRAM IMPROVEMENT: HIGHER-ORDER STRUCTURE DETECTED")
else:
    print("TRIGRAM IMPROVEMENT: NONE")

print("=" * 72)
