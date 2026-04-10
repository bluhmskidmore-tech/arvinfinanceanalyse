"""Unit tests for bond analytics shared helpers (`core_finance.bond_analytics.common`)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_analytics import common


def test_safe_decimal_coerces_and_handles_bad_input() -> None:
    assert common.safe_decimal(None) == Decimal("0")
    assert common.safe_decimal("") == Decimal("0")
    assert common.safe_decimal("12.5") == Decimal("12.5")
    assert common.safe_decimal(3.25) == Decimal(str(3.25))
    d = Decimal("7.77")
    assert common.safe_decimal(d) is d
    assert common.safe_decimal("not-a-number") == Decimal("0")


def test_classify_asset_class_rate_credit_other() -> None:
    assert common.classify_asset_class("国债") == "rate"
    assert common.classify_asset_class("企业债") == "credit"
    assert common.classify_asset_class("xxx") == "other"
    assert common.classify_asset_class("") == "other"


def test_map_accounting_class_patterns() -> None:
    assert common.map_accounting_class("持有至到期") == "AC"
    assert common.map_accounting_class("交易性") == "TPL"
    assert common.map_accounting_class("FVOCI") == "OCI"


def test_estimate_duration_macaulay_vs_fallback() -> None:
    rd = date(2026, 3, 31)
    mat = date(2031, 3, 31)
    coupon = Decimal("0.03")
    ytm = Decimal("0.035")
    d_mac = common.estimate_duration(mat, rd, coupon_rate=coupon, ytm=ytm)
    assert d_mac > Decimal("0")
    # Fallback: no coupon/ytm path uses years to maturity
    d_years = common.estimate_duration(mat, rd)
    years_approx = Decimal("1826") / Decimal("365")  # ~5y
    assert abs(d_years - years_approx) < Decimal("0.02")
    # No dates -> fixed fallback
    assert common.estimate_duration(None, rd) == Decimal("3")


@pytest.mark.parametrize(
    ("period_type", "start_expect", "end_expect"),
    [
        ("MoM", date(2026, 3, 1), date(2026, 3, 31)),
        ("YTD", date(2026, 1, 1), date(2026, 3, 31)),
        ("TTM", date(2025, 3, 31), date(2026, 3, 31)),
    ],
)
def test_resolve_period_mom_ytd_ttm(
    period_type: str,
    start_expect: date,
    end_expect: date,
) -> None:
    rd = date(2026, 3, 31)
    start, end = common.resolve_period(rd, period_type)
    assert start == start_expect
    assert end == end_expect


@pytest.mark.parametrize(
    ("years", "bucket"),
    [
        (0.25, "6M"),
        (1.0, "1Y"),
        (2.0, "2Y"),
        (3.5, "3Y"),
        (5.5, "5Y"),
        (8.0, "7Y"),
        (10.0, "10Y"),
        (15.0, "20Y"),
        (30.0, "30Y"),
    ],
)
def test_get_tenor_bucket(years: float, bucket: str) -> None:
    assert common.get_tenor_bucket(years) == bucket
