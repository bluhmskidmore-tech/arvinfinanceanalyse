# 回归：campisi._aggregate_by_class 零市值不再用 1 元分母伪装；weight 仅含非零市值。
from __future__ import annotations

import pytest

from backend.app.core_finance.campisi import _aggregate_by_class


def _row(
    asset_class: str,
    mv: float,
    income: float,
) -> dict:
    return {
        "asset_class": asset_class,
        "market_value_start": mv,
        "income_return": income,
        "treasury_effect": 0.0,
        "spread_effect": 0.0,
        "selection_effect": 0.0,
        "total_return": income,
    }


def test_zero_market_value_class_pct_fields_are_zero() -> None:
    out = _aggregate_by_class(
        [
            _row("Z", 0.0, 1000.0),
            _row("N", 100_000_000.0, 500_000.0),
        ]
    )
    by_name = {b["asset_class"]: b for b in out}
    z = by_name["Z"]
    n = by_name["N"]
    assert z["income_return_pct"] == 0.0
    assert z["total_return_pct"] == 0.0
    assert z["weight_pct"] == 0.0
    assert n["income_return_pct"] == pytest.approx(0.5, rel=0, abs=1e-9)
    assert n["weight_pct"] == 100.0
