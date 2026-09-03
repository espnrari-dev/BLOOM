
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass(frozen=True)
class BloomConfig:
    """
    Canonical BLOOM recurrent-model contract.

    All dimensions are owned by this object.
    No execution path is allowed to invent a second vocabulary,
    hidden-state width, or output width.
    """
    vocab_size: int
    hidden_dim: int
    sequence_length: int
    batch_size: int = 1

    def __post_init__(self):
        if self.vocab_size <= 0:
            raise ValueError("vocab_size must be positive")
        if self.hidden_dim <= 0:
            raise ValueError("hidden_dim must be positive")
        if self.sequence_length <= 0:
            raise ValueError("sequence_length must be positive")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")

    @property
    def input_shape(self) -> tuple[int, int]:
        return (self.sequence_length, self.batch_size)

    @property
    def state_shape(self) -> tuple[int, int]:
        return (self.hidden_dim, self.batch_size)

    @property
    def logits_shape(self) -> tuple[int, int, int]:
        return (
            self.sequence_length,
            self.vocab_size,
            self.batch_size,
        )

    def validate_weights(self, weights: Dict[str, np.ndarray]) -> None:
        expected = {
            "Wxh": (self.hidden_dim, self.vocab_size),
            "Whh": (self.hidden_dim, self.hidden_dim),
            "Why": (self.vocab_size, self.hidden_dim),
            "bh": (self.hidden_dim, 1),
            "by": (self.vocab_size, 1),
        }

        for name, shape in expected.items():
            if name not in weights:
                raise KeyError(f"Missing required tensor: {name}")

            actual = tuple(weights[name].shape)

            if actual != shape:
                raise ValueError(
                    f"{name} invariant violated: "
                    f"expected {shape}, got {actual}; "
                    f"vocab_size={self.vocab_size}, "
                    f"hidden_dim={self.hidden_dim}"
                )


def init_weights(
    config: BloomConfig,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    rng = np.random.RandomState(seed)

    weights = {
        "Wxh": (
            rng.randn(config.hidden_dim, config.vocab_size)
            * 0.01
        ),
        "Whh": (
            rng.randn(config.hidden_dim, config.hidden_dim)
            * 0.01
        ),
        "Why": (
            rng.randn(config.vocab_size, config.hidden_dim)
            * 0.01
        ),
        "bh": np.zeros(
            (config.hidden_dim, 1),
            dtype=np.float64,
        ),
        "by": np.zeros(
            (config.vocab_size, 1),
            dtype=np.float64,
        ),
    }

    config.validate_weights(weights)
    return weights


def token_indices_to_one_hot(
    xs: np.ndarray,
    config: BloomConfig,
) -> np.ndarray:
    xs = np.asarray(xs)

    if xs.ndim != 2:
        raise ValueError(
            f"Token input must have rank 2 (T,B), got {xs.shape}"
        )

    if xs.shape != config.input_shape:
        raise ValueError(
            f"Token input mismatch: expected "
            f"{config.input_shape}, got {xs.shape}"
        )

    if not np.issubdtype(xs.dtype, np.integer):
        raise TypeError("Token indices must be integers")

    if np.any(xs < 0) or np.any(xs >= config.vocab_size):
        raise ValueError(
            "Token index outside canonical vocabulary"
        )

    out = np.zeros(
        (
            config.sequence_length,
            config.vocab_size,
            config.batch_size,
        ),
        dtype=np.float64,
    )

    for t in range(config.sequence_length):
        for b in range(config.batch_size):
            out[t, int(xs[t, b]), b] = 1.0

    return out


def forward_np(
    xs: np.ndarray,
    hprev: np.ndarray,
    weights: Dict[str, np.ndarray],
    config: BloomConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    config.validate_weights(weights)

    if hprev.shape != config.state_shape:
        raise ValueError(
            f"Initial-state mismatch: expected "
            f"{config.state_shape}, got {hprev.shape}"
        )

    one_hot = token_indices_to_one_hot(xs, config)

    Wxh = weights["Wxh"]
    Whh = weights["Whh"]
    Why = weights["Why"]
    bh = weights["bh"]
    by = weights["by"]

    H = config.hidden_dim
    V = config.vocab_size
    T = config.sequence_length
    B = config.batch_size

    h = np.zeros(
        (T + 1, H, B),
        dtype=np.float64,
    )

    logits = np.zeros(
        (T, V, B),
        dtype=np.float64,
    )

    h[0] = hprev

    for t in range(T):
        x_t = one_hot[t]

        hidden = (
            Wxh @ x_t
            + Whh @ h[t]
            + bh
        )

        h[t + 1] = np.tanh(hidden)

        logits[t] = (
            Why @ h[t + 1]
            + by
        )

    if logits.shape != config.logits_shape:
        raise AssertionError(
            f"Logit invariant violated: "
            f"{logits.shape} != {config.logits_shape}"
        )

    if h[-1].shape != config.state_shape:
        raise AssertionError(
            f"State invariant violated: "
            f"{h[-1].shape} != {config.state_shape}"
        )

    return logits, h[-1]


def validate_model_contract(
    config: BloomConfig,
    weights: Dict[str, np.ndarray],
) -> None:
    config.validate_weights(weights)

    xs = np.zeros(
        config.input_shape,
        dtype=np.int64,
    )

    hprev = np.zeros(
        config.state_shape,
        dtype=np.float64,
    )

    logits, final_state = forward_np(
        xs,
        hprev,
        weights,
        config,
    )

    if logits.shape != config.logits_shape:
        raise AssertionError("logits contract failed")

    if final_state.shape != config.state_shape:
        raise AssertionError("state contract failed")
