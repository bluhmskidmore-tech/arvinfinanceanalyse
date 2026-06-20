from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Iterator

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


@contextmanager
def _patched_roll_down_inputs(
    *,
    years_to_maturity: float = 5.0,
    modified_duration: Decimal = Decimal("4.5"),
    market_value: Decimal = Decimal("100000000"),
) -> Iterator[None]:
    globals_map = _calculate_roll_down.__globals__
    original_years = globals_map["_years_to_maturity"]
    original_duration = globals_map["_modified_duration"]
    original_market_value = globals_map["_curve_market_value"]
    globals_map["_years_to_maturity"] = lambda **_kwargs: years_to_maturity
    globals_map["_modified_duration"] = lambda **_kwargs: modified_duration
    globals_map["_curve_market_value"] = lambda _row: market_value
    try:
        yield
    finally:
        globals_map["_years_to_maturity"] = original_years
        globals_map["_modified_duration"] = original_duration
        globals_map["_curve_market_value"] = original_market_value


def test_roll_down_negative_normal_upward_sloping_curve() -> None:
    curve = {"4Y": Decimal("2.70"), "5Y": Decimal("2.80")}
    with _patched_roll_down_inputs():
        result = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert result == Decimal("-450000")


def test_roll_down_zero_flat_curve() -> None:
    curve = {"4Y": Decimal("2.75"), "5Y": Decimal("2.75")}
    with _patched_roll_down_inputs():
        result = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert result == Decimal("0")


def test_roll_down_positive_inverted_curve() -> None:
    curve = {"4Y": Decimal("2.80"), "5Y": Decimal("2.70")}
    with _patched_roll_down_inputs():
        result = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert result == Decimal("450000")


def test_roll_down_zero_when_duration_zero() -> None:
    curve = {"4Y": Decimal("2.70"), "5Y": Decimal("2.80")}
    with _patched_roll_down_inputs(modified_duration=Decimal("0")):
        result = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert result == Decimal("0")


def test_roll_down_zero_when_market_value_zero() -> None:
    curve = {"4Y": Decimal("2.70"), "5Y": Decimal("2.80")}
    with _patched_roll_down_inputs(market_value=Decimal("0")):
        result = _calculate_roll_down(
            report_date=REPORT,
            current_balance=_balance(report_d=REPORT),
            prior_balance=_balance(report_d=PRIOR),
            curve=curve,
        )
    assert result == Decimal("0")


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
