"""
Unit tests for rate_units.py — explicit unit conversions and normalization.
"""
import math
import pytest

from backend.app.core_finance.rate_units import (
    pct_to_decimal,
    decimal_to_pct,
    bp_to_decimal,
    decimal_to_bp,
    pct_to_bp,
    bp_to_pct,
    normalize_annual_rate_to_decimal,
)


class TestPctToDecimal:
    """Test percentage to decimal conversion."""

    def test_standard_conversion(self):
        """2.55% → 0.0255"""
        assert pct_to_decimal(2.55) == 0.0255

    def test_zero(self):
        """0.0% → 0.0"""
        assert pct_to_decimal(0.0) == 0.0

    def test_hundred_percent(self):
        """100.0% → 1.0"""
        assert pct_to_decimal(100.0) == 1.0

    def test_small_percentage(self):
        """0.01% → 0.0001"""
        assert abs(pct_to_decimal(0.01) - 0.0001) < 1e-10

    def test_large_percentage(self):
        """250.0% → 2.5"""
        assert pct_to_decimal(250.0) == 2.5


class TestDecimalToPct:
    """Test decimal to percentage conversion."""

    def test_standard_conversion(self):
        """0.0255 → 2.55%"""
        assert decimal_to_pct(0.0255) == 2.55

    def test_zero(self):
        """0.0 → 0.0%"""
        assert decimal_to_pct(0.0) == 0.0

    def test_one(self):
        """1.0 → 100.0%"""
        assert decimal_to_pct(1.0) == 100.0

    def test_small_decimal(self):
        """0.0001 → 0.01%"""
        assert abs(decimal_to_pct(0.0001) - 0.01) < 1e-10


class TestBpToDecimal:
    """Test basis points to decimal conversion."""

    def test_standard_conversion(self):
        """50 BP → 0.005"""
        assert bp_to_decimal(50) == 0.005

    def test_zero(self):
        """0 BP → 0.0"""
        assert bp_to_decimal(0) == 0.0

    def test_ten_thousand_bp(self):
        """10000 BP → 1.0"""
        assert bp_to_decimal(10000) == 1.0

    def test_one_bp(self):
        """1 BP → 0.0001"""
        assert bp_to_decimal(1) == 0.0001

    def test_large_bp(self):
        """25000 BP → 2.5"""
        assert bp_to_decimal(25000) == 2.5


class TestDecimalToBp:
    """Test decimal to basis points conversion."""

    def test_standard_conversion(self):
        """0.005 → 50 BP"""
        assert decimal_to_bp(0.005) == 50.0

    def test_zero(self):
        """0.0 → 0 BP"""
        assert decimal_to_bp(0.0) == 0.0

    def test_one(self):
        """1.0 → 10000 BP"""
        assert decimal_to_bp(1.0) == 10000.0

    def test_small_decimal(self):
        """0.0001 → 1 BP"""
        assert decimal_to_bp(0.0001) == 1.0


class TestPctToBp:
    """Test percentage to basis points conversion."""

    def test_standard_conversion(self):
        """2.55% → 255 BP"""
        assert pct_to_bp(2.55) == 255.0

    def test_zero(self):
        """0.0% → 0 BP"""
        assert pct_to_bp(0.0) == 0.0

    def test_one_percent(self):
        """1.0% → 100 BP"""
        assert pct_to_bp(1.0) == 100.0

    def test_hundred_percent(self):
        """100.0% → 10000 BP"""
        assert pct_to_bp(100.0) == 10000.0


class TestBpToPct:
    """Test basis points to percentage conversion."""

    def test_standard_conversion(self):
        """255 BP → 2.55%"""
        assert bp_to_pct(255) == 2.55

    def test_zero(self):
        """0 BP → 0.0%"""
        assert bp_to_pct(0) == 0.0

    def test_hundred_bp(self):
        """100 BP → 1.0%"""
        assert bp_to_pct(100) == 1.0

    def test_ten_thousand_bp(self):
        """10000 BP → 100.0%"""
        assert bp_to_pct(10000) == 100.0


class TestNormalizeAnnualRateToDecimal:
    """Test heuristic normalization to decimal format."""

    def test_percentage_input(self):
        """2.55 (percentage) → 0.0255"""
        result = normalize_annual_rate_to_decimal(2.55)
        assert result == 0.0255

    def test_decimal_input(self):
        """0.0255 (already decimal) → 0.0255"""
        result = normalize_annual_rate_to_decimal(0.0255)
        assert result == 0.0255

    def test_zero(self):
        """0.0 → 0.0"""
        result = normalize_annual_rate_to_decimal(0.0)
        assert result == 0.0

    def test_one(self):
        """1.0 (edge case) → 1.0 (treated as decimal)"""
        result = normalize_annual_rate_to_decimal(1.0)
        assert result == 1.0

    def test_just_above_one(self):
        """1.5 (percentage) → 0.015"""
        result = normalize_annual_rate_to_decimal(1.5)
        assert result == 0.015

    def test_hundred(self):
        """100.0 (edge case) → 1.0"""
        result = normalize_annual_rate_to_decimal(100.0)
        assert result == 1.0

    def test_above_hundred_returns_none(self):
        """150.0 (dirty data) → None"""
        result = normalize_annual_rate_to_decimal(150.0)
        assert result is None

    def test_negative_returns_none(self):
        """-2.5 (invalid) → None"""
        result = normalize_annual_rate_to_decimal(-2.5)
        assert result is None

    def test_none_input(self):
        """None → None"""
        result = normalize_annual_rate_to_decimal(None)
        assert result is None

    def test_nan_returns_none(self):
        """NaN → None"""
        result = normalize_annual_rate_to_decimal(float('nan'))
        assert result is None

    def test_inf_returns_none(self):
        """Infinity → None"""
        result = normalize_annual_rate_to_decimal(float('inf'))
        assert result is None

    def test_string_number(self):
        """'2.55' (string) → 0.0255"""
        result = normalize_annual_rate_to_decimal('2.55')
        assert result == 0.0255

    def test_invalid_string_returns_none(self):
        """'invalid' → None"""
        result = normalize_annual_rate_to_decimal('invalid')
        assert result is None

    def test_small_decimal(self):
        """0.0001 (already decimal) → 0.0001"""
        result = normalize_annual_rate_to_decimal(0.0001)
        assert result == 0.0001

    def test_boundary_at_one(self):
        """Test boundary behavior around 1.0."""
        # Exactly 1.0 is treated as decimal
        assert normalize_annual_rate_to_decimal(1.0) == 1.0

        # Just above 1.0 is treated as percentage
        assert normalize_annual_rate_to_decimal(1.0001) == 0.010001

    def test_typical_bond_yields(self):
        """Test typical bond yield values."""
        # 3.5% stored as percentage
        assert normalize_annual_rate_to_decimal(3.5) == 0.035

        # 3.5% stored as decimal
        assert normalize_annual_rate_to_decimal(0.035) == 0.035

        # 12% stored as percentage
        assert normalize_annual_rate_to_decimal(12.0) == 0.12


class TestRoundTripConversions:
    """Test round-trip conversions maintain precision."""

    def test_pct_decimal_roundtrip(self):
        """Percentage → Decimal → Percentage"""
        original = 2.55
        result = decimal_to_pct(pct_to_decimal(original))
        assert abs(result - original) < 1e-10

    def test_bp_decimal_roundtrip(self):
        """BP → Decimal → BP"""
        original = 50.0
        result = decimal_to_bp(bp_to_decimal(original))
        assert abs(result - original) < 1e-10

    def test_pct_bp_roundtrip(self):
        """Percentage → BP → Percentage"""
        original = 2.55
        result = bp_to_pct(pct_to_bp(original))
        assert abs(result - original) < 1e-10
