# 回归：pnl_bridge._calculate_roll_down 的 roll-down 符号（正常/平坦/反转曲线；零久期/零市值）。
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from backend.app.core_finance.pnl_bridge import _calculate_roll_down

REPORT = date(2025, 12, 31)
PRIOR = date(2024, 12, 31)
MATURITY = date(2030, 12, 31)


def _balance(*, report_d: date) -> dict:
    return {
        "report_date": report_d,
        "maturity_date": MATURITY,
        "instrument_code": "TESTBOND",
        "coupon_rate": Decimal("0.04"),
        "ytm_value": Decimal("0.03"),
        "market_value_amount": Decimal("100000000"),
    }


@patch("backend.app.core_finance.pnl_bridge._years_to_maturity", return_value=5.0)
@patch("backend.app.core_finance.pnl_bridge._modified_duration", return_value=Decimal("4.5"))
@patch("backend.app.core_finance.pnl_bridge._curve_market_value", return_value=Decimal("100000000"))
def test_roll_down_negative_normal_upward_sloping_curve(
    _mv, _md, _ytm
) -> None:
    # 5Y 2.80% / 4Y 2.70% → rate_delta=+0.001 → -(Δ)×D×MV = -450_000
    curve = {"4Y": Decimal("2.70"), "5Y": Decimal("2.80")}
    r = _calculate_roll_down(
        report_date=REPORT,
        current_balance=_balance(report_d=REPORT),
        prior_balance=_balance(report_d=PRIOR),
        curve=curve,
    )
    assert r == Decimal("-450000")


@patch("backend.app.core_finance.pnl_bridge._years_to_maturity", return_value=5.0)
@patch("backend.app.core_finance.pnl_bridge._modified_duration", return_value=Decimal("4.5"))
@patch("backend.app.core_finance.pnl_bridge._curve_market_value", return_value=Decimal("100000000"))
def test_roll_down_zero_flat_curve(_mv, _md, _ytm) -> None:
    curve = {"4Y": Decimal("2.75"), "5Y": Decimal("2.75")}
    r = _calculate_roll_down(
        report_date=REPORT,
        current_balance=_balance(report_d=REPORT),
        prior_balance=_balance(report_d=PRIOR),
        curve=curve,
    )
    assert r == Decimal("0")


@patch("backend.app.core_finance.pnl_bridge._years_to_maturity", return_value=5.0)
@patch("backend.app.core_finance.pnl_bridge._modified_duration", return_value=Decimal("4.5"))
@patch("backend.app.core_finance.pnl_bridge._curve_market_value", return_value=Decimal("100000000"))
def test_roll_down_positive_inverted_curve(_mv, _md, _ytm) -> None:
    # 5Y 2.70% < 4Y 2.80% → rate_delta 为负 → 结果为 +450_000
    curve = {"4Y": Decimal("2.80"), "5Y": Decimal("2.70")}
    r = _calculate_roll_down(
        report_date=REPORT,
        current_balance=_balance(report_d=REPORT),
        prior_balance=_balance(report_d=PRIOR),
        curve=curve,
    )
    assert r == Decimal("450000")


def test_roll_down_zero_when_duration_zero() -> None:
    curve = {"4Y": Decimal("2.70"), "5Y": Decimal("2.80")}
    with (
        patch("backend.app.core_finance.pnl_bridge._years_to_maturity", return_value=5.0),
        patch("backend.app.core_finance.pnl_bridge._modified_duration", return_value=Decimal("0")),
        patch(
            "backend.app.core_finance.pnl_bridge._curve_market_value", return_value=Decimal("100000000")
        ),
    ):
        r = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert r == Decimal("0")


def test_roll_down_zero_when_market_value_zero() -> None:
    curve = {"4Y": Decimal("2.70"), "5Y": Decimal("2.80")}
    with (
        patch("backend.app.core_finance.pnl_bridge._years_to_maturity", return_value=5.0),
        patch("backend.app.core_finance.pnl_bridge._modified_duration", return_value=Decimal("4.5")),
        patch("backend.app.core_finance.pnl_bridge._curve_market_value", return_value=Decimal("0")),
    ):
        r = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert r == Decimal("0")


def test_roll_down_zero_when_any_balance_missing() -> None:
    assert (
        _calculate_roll_down(
            report_date=REPORT,
            current_balance=None,
            prior_balance=_balance(report_d=PRIOR),
            curve={"5Y": Decimal("2.8")},
        )
        == Decimal("0")
    )
