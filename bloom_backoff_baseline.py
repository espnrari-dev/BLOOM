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

unigram = Counter()
bigram = Counter()
trigram = Counter()
contexts2 = Counter()
contexts3 = Counter()

for line in train_lines:
    tokens = ["<BOS>"] + tokenize(line) + ["<EOS>"]

    for token in tokens:
        unigram[token] += 1

    for i in range(1, len(tokens)):
        bigram[(tokens[i-1], tokens[i])] += 1
        contexts2[tokens[i-1]] += 1

    for i in range(2, len(tokens)):
        trigram[
            (tokens[i-2], tokens[i-1], tokens[i])
        ] += 1
        contexts3[
            (tokens[i-2], tokens[i-1])
        ] += 1

vocab = set(unigram)
V = len(vocab)
total = sum(unigram.values())

def uni_prob(word):
    return (unigram[word] + 1) / (total + V)

def bi_prob(prev, word):
    context = contexts2[prev]

    if context == 0:
        return uni_prob(word)

    # Interpolated smoothing.
    ml = bigram[(prev, word)] / context
    return 0.7 * ml + 0.3 * uni_prob(word)

def tri_prob(a, b, word):
    context = contexts3[(a, b)]

    if context == 0:
        return bi_prob(b, word)

    ml = trigram[(a, b, word)] / context
    return 0.7 * ml + 0.3 * bi_prob(b, word)

def evaluate(order):
    loss = 0.0
    tokens = 0
    exact_hits = 0

    for line in valid_lines:
        words = tokenize(line)
        seq = ["<BOS>"] + words + ["<EOS>"]

        for i in range(1, len(seq)):
            word = seq[i]

            if order == 1:
                p = uni_prob(word)
            elif order == 2:
                p = bi_prob(seq[i-1], word)
            else:
                a = seq[i-2] if i >= 2 else "<BOS>"
                p = tri_prob(a, seq[i-1], word)

            loss -= math.log(max(p, 1e-12))
            tokens += 1

            if order > 1:
                if order == 2:
                    if bigram[(seq[i-1], word)]:
                        exact_hits += 1
                else:
                    if trigram[(a, seq[i-1], word)]:
                        exact_hits += 1

    entropy = loss / tokens
    perplexity = math.exp(entropy)

    return entropy, perplexity, tokens, exact_hits

print("=" * 72)
print("BLOOM BACKOFF / INTERPOLATION BASELINE")
print("=" * 72)

print(f"Training records   : {len(train_lines):,}")
print(f"Validation records : {len(valid_lines):,}")
print(f"Vocabulary         : {V:,}")

results = {}

for order, name in [
    (1, "UNIGRAM"),
    (2, "BIGRAM_BACKOFF"),
    (3, "TRIGRAM_BACKOFF"),
]:
    entropy, ppl, tokens, hits = evaluate(order)

    results[name] = ppl

    print()
    print("=" * 72)
    print(name)
    print("=" * 72)
    print(f"Cross entropy      : {entropy:.6f}")
    print(f"Perplexity         : {ppl:.6f}")

    if order > 1:
        print(
            f"Seen {order}-grams      : "
            f"{hits:,}/{tokens:,} "
            f"({hits/max(1,tokens):.2%})"
        )

print()
print("=" * 72)
print("SEQUENCE SIGNAL")
print("=" * 72)

for name, ppl in results.items():
    print(f"{name:16s} | {ppl:.6f}")

if results["BIGRAM_BACKOFF"] < results["UNIGRAM"]:
    print()
    print("BIGRAM BACKOFF: POSITIVE SEQUENCE SIGNAL")
else:
    print()
    print("BIGRAM BACKOFF: NO IMPROVEMENT")

if results["TRIGRAM_BACKOFF"] < results["BIGRAM_BACKOFF"]:
    print("TRIGRAM BACKOFF: HIGHER-ORDER SIGNAL")
else:
    print("TRIGRAM BACKOFF: NO ADDITIONAL SIGNAL")

print()
print("NOTE: This is a diagnostic baseline, not BLOOM training.")
print("=" * 72)
