from __future__ import annotations

import argparse


def non_negative_portfolio_limit(value: str, *, label: str = "limit") -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError(
            f"Portfolio-home {label} must be non-negative: {parsed}"
        )
    return parsed


def validate_non_negative_portfolio_limit(
    limit: int,
    *,
    label: str = "limit",
) -> int:
    if limit < 0:
        raise ValueError(f"Portfolio-home {label} must be non-negative: {limit}")
    return limit
