# 回归：attribution_core.estimate_convexity 使用 (D²+D)/(1+y)²（非 D²×0.01）。
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.attribution_core import estimate_convexity


def test_convexity_with_ytm_uses_new_formula() -> None:
    d5 = Decimal("5")
    y = Decimal("0.03")
    exp = (Decimal("25") + d5) / (Decimal("1.03") ** 2)
    assert estimate_convexity(d5, y) == exp


def test_convexity_ytm_none_macaulay_style() -> None:
    assert estimate_convexity(Decimal("5"), None) == Decimal("30")


def test_convexity_duration_ten_ytm_five_percent() -> None:
    c = estimate_convexity(Decimal("10"), Decimal("0.05"))
    assert c == (Decimal("100") + Decimal("10")) / (Decimal("1.05") ** 2)


def test_convexity_duration_zero() -> None:
    assert estimate_convexity(Decimal("0"), Decimal("0.03")) == Decimal("0")


def test_magnitude_not_duration_squared_times_point_zero_one() -> None:
    d = Decimal("8")
    c = estimate_convexity(d, Decimal("0.04"))
    wrong_old_style = d * d * Decimal("0.01")
    assert c != wrong_old_style
    assert c > d * d * Decimal("0.5")


def test_single_arg_ytm_default_none() -> None:
    assert estimate_convexity(Decimal("5")) == Decimal("30")
