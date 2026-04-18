"""
Annual rate unit normalization helpers migrated from MOSS-V2 core_finance.

These helpers make unit conversions explicit and avoid scattered magic
constants such as `/ 100`, `* 100`, and `/ 10000`.
"""
from __future__ import annotations

import math
from typing import Any


# Explicit unit conversions for callers that already know the input unit.


def pct_to_decimal(value: float) -> float:
    """Percent to decimal. `2.55 -> 0.0255`."""
    return value / 100.0


def decimal_to_pct(value: float) -> float:
    """Decimal to percent. `0.0255 -> 2.55`."""
    return value * 100.0


def bp_to_decimal(value: float) -> float:
    """Basis points to decimal. `50 -> 0.005`."""
    return value / 10000.0


def decimal_to_bp(value: float) -> float:
    """Decimal to basis points. `0.005 -> 50`."""
    return value * 10000.0


def pct_to_bp(value: float) -> float:
    """Percent to basis points. `2.55 -> 255`."""
    return round(value * 100.0, 10)


def bp_to_pct(value: float) -> float:
    """Basis points to percent. `255 -> 2.55`."""
    return value / 100.0


# Heuristic normalization for ambiguous stored rate units. Use sparingly.


def normalize_annual_rate_to_decimal(raw: Any) -> float | None:
    """
    Normalize stored annual rates to decimal form, where `0.035` means 3.5%.

    Rules align with `import_v1_real_snapshot._normalize_rate`:
    - `None` or negative values -> `None`
    - values above `100` -> `None`
    - values above `1` -> divide by `100` as percent input
    - otherwise treat the input as an existing decimal
    """
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0:
        return None
    if v > 100:
        return None
    if v > 1:
        return v / 100.0
    return v
