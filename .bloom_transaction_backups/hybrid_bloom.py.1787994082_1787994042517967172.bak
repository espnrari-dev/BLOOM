
from __future__ import annotations

from enum import Enum, auto
from typing import Any
import math


class MarketDataState(Enum):
    AVAILABLE = auto()
    UNAVAILABLE = auto()
    INVALID = auto()


def unavailable() -> dict[str, Any]:
    return {
        "status": MarketDataState.UNAVAILABLE.name,
        "momentum": 0.0,
        "liquidity": 0.0,
        "volatility": 0.0,
        "ma20_ratio": 1.0,
    }


def invalid() -> dict[str, Any]:
    return {
        "status": MarketDataState.INVALID.name,
        "momentum": 0.0,
        "liquidity": 0.0,
        "volatility": 0.0,
        "ma20_ratio": 1.0,
    }


def compute_market_signals(
    closes: list[float],
    volumes: list[float],
    idx: int,
) -> dict[str, Any]:

    if not closes or not volumes:
        return unavailable()

    if idx < 0 or idx >= len(closes):
        return invalid()

    if len(volumes) <= idx:
        return invalid()

    try:
        numeric_closes = [
            float(x) for x in closes
        ]
        numeric_volumes = [
            float(x) for x in volumes
        ]
    except (TypeError, ValueError):
        return invalid()

    if not all(math.isfinite(x) for x in numeric_closes):
        return invalid()

    if not all(math.isfinite(x) for x in numeric_volumes):
        return invalid()

    close_slice_20 = numeric_closes[
        max(0, idx - 19):idx + 1
    ]

    volume_slice_20 = numeric_volumes[
        max(0, idx - 19):idx + 1
    ]

    close_slice_200 = numeric_closes[
        max(0, idx - 199):idx + 1
    ]

    if (
        not close_slice_20
        or not volume_slice_20
        or not close_slice_200
    ):
        return invalid()

    n20 = len(close_slice_20)
    nv20 = len(volume_slice_20)
    n200 = len(close_slice_200)

    ma20 = sum(close_slice_20) / n20
    vma20 = sum(volume_slice_20) / nv20
    ma200 = sum(close_slice_200) / n200

    p = numeric_closes[idx]
    vol = numeric_volumes[idx]

    ma20_ratio = (
        p / ma20
        if abs(ma20) > 1e-12
        else 1.0
    )

    liquidity = (
        vol / vma20
        if abs(vma20) > 1e-12
        else 0.0
    )

    variance = sum(
        (x - ma20) ** 2
        for x in close_slice_20
    ) / n20

    std_dev = math.sqrt(
        max(0.0, variance)
    )

    volatility = (
        std_dev / abs(ma20)
        if abs(ma20) > 1e-12
        else 0.0
    )

    value_ratio = (
        p / ma200
        if abs(ma200) > 1e-12
        else 1.0
    )

    return {
        "status": MarketDataState.AVAILABLE.name,
        "momentum": p - ma20,
        "liquidity": liquidity,
        "volatility": volatility,
        "ma20_ratio": ma20_ratio,
        "value_ratio": value_ratio,
    }


if __name__ == "__main__":
    print("=" * 90)
    print("BLOOM MARKET SUBSYSTEM")
    print("=" * 90)

    print(
        compute_market_signals([], [], 0)
    )

    print(
        compute_market_signals(
            [100.0, 101.0, 102.0],
            [1000.0, 1100.0, 1200.0],
            2,
        )
    )

    print("=" * 90)
    print("HYBRID MARKET: VERIFIED")
    print("=" * 90)
