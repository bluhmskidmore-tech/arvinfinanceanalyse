"""Tests for accrued interest fallback marking in four effects."""
from datetime import date
from decimal import Decimal
import logging

import pytest

from backend.app.core_finance.bond_four_effects import compute_bond_four_effects


def _make_bond(**overrides):
    base = {
        "bond_code": "TEST001.IB",
        "coupon_rate": 0.03,
        "face_value": 10_000_000.0,
        "market_value_start": 10_000_000.0,
        "market_value_end": 10_050_000.0,
        "yield_to_maturity": 0.035,
        "asset_class": "AAA企业债",
        "maturity_date": date(2030, 12, 31),
    }
    base.update(overrides)
    return base


class TestAccruedInterestFallbackMarker:
    """Verify that missing accrued interest is explicitly marked in results."""

    def test_with_accrued_interest_present(self):
        bond = _make_bond(
            accrued_interest_start=50000.0,
            accrued_interest_end=75000.0,
        )
        result = compute_bond_four_effects(
            bond=bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.001"),
            spread_change=Decimal("0.0005"),
            report_date=date(2026, 3, 31),
        )
        assert result["has_accrued_interest"] is True
        assert result["diagnostics"] == []

    def test_without_accrued_interest_marks_fallback(self):
        bond = _make_bond()
        result = compute_bond_four_effects(
            bond=bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.001"),
            spread_change=Decimal("0.0005"),
            report_date=date(2026, 3, 31),
        )
        assert result["has_accrued_interest"] is False
        assert "accrued_interest_fallback_to_zero" in result["diagnostics"]

    def test_partial_accrued_interest_marks_fallback(self):
        """Only start present, end missing — should still mark as fallback."""
        bond = _make_bond(accrued_interest_start=50000.0)
        result = compute_bond_four_effects(
            bond=bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.001"),
            spread_change=Decimal("0.0005"),
            report_date=date(2026, 3, 31),
        )
        assert result["has_accrued_interest"] is False
        assert "accrued_interest_fallback_to_zero" in result["diagnostics"]

    def test_calculation_still_works_without_accrued(self):
        """Fallback should not break the calculation — all numeric keys still present."""
        bond = _make_bond()
        result = compute_bond_four_effects(
            bond=bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.001"),
            spread_change=Decimal("0.0005"),
            report_date=date(2026, 3, 31),
        )
        for key in (
            "income_return",
            "treasury_effect",
            "spread_effect",
            "selection_effect",
            "total_return",
        ):
            assert key in result
            assert isinstance(result[key], Decimal)

    def test_four_effects_sum_to_total(self):
        """Regardless of accrued interest presence, four effects should sum to total."""
        bond = _make_bond()
        result = compute_bond_four_effects(
            bond=bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.001"),
            spread_change=Decimal("0.0005"),
            report_date=date(2026, 3, 31),
        )
        components_sum = (
            result["income_return"]
            + result["treasury_effect"]
            + result["spread_effect"]
            + result["selection_effect"]
        )
        assert abs(components_sum - result["total_return"]) < Decimal("0.01")

    def test_warning_logged_on_fallback(self, caplog):
        """Should emit a warning log when falling back."""
        bond = _make_bond()
        with caplog.at_level(logging.WARNING):
            compute_bond_four_effects(
                bond=bond,
                num_days=30,
                benchmark_yield_change=Decimal("0.001"),
                spread_change=Decimal("0.0005"),
                report_date=date(2026, 3, 31),
            )
        assert "accrued_interest missing" in caplog.text
        assert "TEST001.IB" in caplog.text
