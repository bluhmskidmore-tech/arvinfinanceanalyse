# 回归：rate_units 六类显式转换与 normalize_annual_rate_to_decimal 边界行为（Decimal/启发式）。
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.rate_units import (
    bp_to_decimal,
    bp_to_pct,
    decimal_to_bp,
    decimal_to_pct,
    normalize_annual_rate_to_decimal,
    pct_to_bp,
    pct_to_decimal,
)


def test_six_conversion_functions_return_decimal() -> None:
    assert isinstance(pct_to_decimal(2.55), Decimal)
    assert isinstance(decimal_to_pct(Decimal("0.01")), Decimal)
    assert isinstance(bp_to_decimal(50), Decimal)
    assert isinstance(decimal_to_bp(Decimal("0.005")), Decimal)
    assert isinstance(pct_to_bp(Decimal("2.55")), Decimal)
    assert isinstance(bp_to_pct(255), Decimal)

    for fn, inp in (
        (pct_to_decimal, 1.0),
        (decimal_to_pct, "0.5"),
        (bp_to_decimal, Decimal("10")),
        (decimal_to_bp, 0.001),
        (pct_to_bp, 3.0),
        (bp_to_pct, 100.0),
    ):
        assert isinstance(fn(inp), Decimal)


def test_pct_and_bp_golden_no_float_drift() -> None:
    assert pct_to_decimal(Decimal("2.55")) == Decimal("0.0255")
    assert bp_to_decimal(Decimal("50")) == Decimal("0.005")


def test_pct_round_trip() -> None:
    assert decimal_to_pct(pct_to_decimal(Decimal("2.55"))) == Decimal("2.55")


def test_normalize_annual_rate_boundaries() -> None:
    assert normalize_annual_rate_to_decimal(1.0) == 0.01
    assert normalize_annual_rate_to_decimal(0.99) == 0.99
