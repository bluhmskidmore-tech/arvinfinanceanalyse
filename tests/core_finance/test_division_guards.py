"""Tests for zero-division guard fixes — golden sample assertions."""
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.bond_analytics.read_models import (
    _weighted_average_spread,
    _weighted_spread_change,
)

ZERO = Decimal("0")


class TestWeightedAverageSpread:
    def test_empty_rows_returns_zero(self) -> None:
        result = _weighted_average_spread(
            [],
            aaa_credit_curve_current={"1Y": Decimal("3.5")},
            treasury_curve_current={"1Y": Decimal("2.5")},
        )
        assert result == ZERO

    def test_all_rows_zero_market_value_returns_zero(self) -> None:
        rows = [{"market_value": "0", "years_to_maturity": "5.0"}]
        result = _weighted_average_spread(
            rows,
            aaa_credit_curve_current={"5Y": Decimal("4.0")},
            treasury_curve_current={"5Y": Decimal("3.0")},
        )
        assert result == ZERO

    def test_missing_curves_returns_zero(self) -> None:
        rows = [{"market_value": "1000000", "years_to_maturity": "3.0"}]
        result = _weighted_average_spread(rows, aaa_credit_curve_current=None, treasury_curve_current=None)
        assert result == ZERO

    def test_normal_case_returns_positive(self) -> None:
        rows = [{"market_value": "1000000", "years_to_maturity": "5.0"}]
        result = _weighted_average_spread(
            rows,
            aaa_credit_curve_current={"5Y": Decimal("4.0")},
            treasury_curve_current={"5Y": Decimal("3.0")},
        )
        assert result > ZERO


class TestWeightedSpreadChange:
    def test_zero_total_market_value_returns_zero(self) -> None:
        rows = [{"market_value": "1000000", "years_to_maturity": "3.0"}]
        result = _weighted_spread_change(
            rows,
            aaa_credit_curve_current={"3Y": Decimal("4.0")},
            aaa_credit_curve_prior={"3Y": Decimal("3.8")},
            treasury_curve_current={"3Y": Decimal("3.0")},
            treasury_curve_prior={"3Y": Decimal("2.9")},
            total_market_value=ZERO,
        )
        assert result == ZERO

    def test_negative_total_market_value_returns_zero(self) -> None:
        rows = [{"market_value": "1000000", "years_to_maturity": "3.0"}]
        result = _weighted_spread_change(
            rows,
            aaa_credit_curve_current={"3Y": Decimal("4.0")},
            aaa_credit_curve_prior={"3Y": Decimal("3.8")},
            treasury_curve_current={"3Y": Decimal("3.0")},
            treasury_curve_prior={"3Y": Decimal("2.9")},
            total_market_value=Decimal("-100"),
        )
        assert result == ZERO

    def test_empty_rows_returns_zero(self) -> None:
        result = _weighted_spread_change(
            [],
            aaa_credit_curve_current=None,
            aaa_credit_curve_prior=None,
            treasury_curve_current=None,
            treasury_curve_prior=None,
            total_market_value=Decimal("1000000"),
        )
        assert result == ZERO
