"""Unit tests for market_derived.py: spread calculation and credit spread lookup."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.market_derived import (
    DEFAULT_CREDIT_SPREADS,
    calculate_spreads,
    get_credit_spread,
    interpolate_ftp_rate,
)


def test_calculate_spreads_all_fields_present():
    """Verify spread calculation with complete market data."""
    market_data = {
        "ncd_aaa_1y": 2.80,
        "treasury_1y": 2.55,
        "treasury_10y": 3.20,
        "treasury_5y": 2.90,
        "treasury_3y": 2.70,
        "credit_aaa_3y": 3.05,
        "cdb_5y": 3.10,
        "r007": 2.60,
        "dr007": 2.50,
        "credit_aa_plus_3y": 3.30,
        "credit_aa_3y": 3.50,
        "us_treasury_10y": 4.50,
        "cdb_10y": 3.40,
    }

    spreads = calculate_spreads(market_data)

    # Spread formula: (a - b) * 100 → BP
    assert spreads["ncd_treasury_spread_1y"] == pytest.approx(25.0)  # (2.80 - 2.55) * 100
    assert spreads["term_spread_10y_1y"] == pytest.approx(65.0)  # (3.20 - 2.55) * 100
    assert spreads["term_spread_10y_5y"] == pytest.approx(30.0)  # (3.20 - 2.90) * 100
    assert spreads["credit_spread_aaa_3y"] == pytest.approx(35.0)  # (3.05 - 2.70) * 100
    assert spreads["cdb_treasury_spread_5y"] == pytest.approx(20.0)  # (3.10 - 2.90) * 100
    assert spreads["r007_dr007_spread"] == pytest.approx(10.0)  # (2.60 - 2.50) * 100
    assert spreads["credit_spread_aa_plus_3y"] == pytest.approx(60.0)  # (3.30 - 2.70) * 100
    assert spreads["credit_spread_aa_3y"] == pytest.approx(80.0)  # (3.50 - 2.70) * 100
    assert spreads["aa_aaa_spread_3y"] == pytest.approx(45.0)  # (3.50 - 3.05) * 100
    assert spreads["china_us_spread_10y"] == pytest.approx(-130.0)  # (3.20 - 4.50) * 100
    assert spreads["cdb_treasury_spread_10y"] == pytest.approx(20.0)  # (3.40 - 3.20) * 100


def test_calculate_spreads_missing_fields():
    """Verify spreads return None when input fields are missing."""
    market_data = {
        "treasury_1y": 2.55,
        "treasury_10y": 3.20,
        # Missing ncd_aaa_1y, treasury_5y, etc.
    }

    spreads = calculate_spreads(market_data)

    assert spreads["ncd_treasury_spread_1y"] is None
    assert spreads["term_spread_10y_1y"] == pytest.approx(65.0)
    assert spreads["term_spread_10y_5y"] is None
    assert spreads["credit_spread_aaa_3y"] is None


def test_calculate_spreads_negative_spread():
    """Verify negative spreads are calculated correctly."""
    market_data = {
        "treasury_10y": 2.50,
        "us_treasury_10y": 3.80,
    }

    spreads = calculate_spreads(market_data)

    assert spreads["china_us_spread_10y"] == pytest.approx(-130.0)  # (2.50 - 3.80) * 100


def test_calculate_spreads_empty_dict():
    """Verify all spreads are None when market data is empty."""
    spreads = calculate_spreads({})

    assert all(v is None for v in spreads.values())


def test_get_credit_spread_default_table_exact_match():
    """Verify default spread table lookup with exact rating/tenor match."""
    spread = get_credit_spread("AAA", 3.0, curve=None)
    assert spread == Decimal("35") / Decimal("10000")  # 35 BP → 0.0035

    spread = get_credit_spread("AA+", 5.0, curve=None)
    assert spread == Decimal("75") / Decimal("10000")  # 75 BP → 0.0075

    spread = get_credit_spread("AA", 1.0, curve=None)
    assert spread == Decimal("70") / Decimal("10000")  # 70 BP → 0.0070


def test_get_credit_spread_tenor_bucketing():
    """Verify tenor years are mapped to 1Y/3Y/5Y buckets."""
    # 0-2 years → 1Y
    spread = get_credit_spread("AAA", 1.5, curve=None)
    assert spread == Decimal("25") / Decimal("10000")

    # 2-4 years → 3Y
    spread = get_credit_spread("AAA", 3.5, curve=None)
    assert spread == Decimal("35") / Decimal("10000")

    # 4+ years → 5Y
    spread = get_credit_spread("AAA", 7.0, curve=None)
    assert spread == Decimal("45") / Decimal("10000")


def test_get_credit_spread_fallback_to_other_tenors():
    """Verify fallback to 3Y/5Y/1Y when exact tenor not in default table."""
    # BBB rating not in table, should fallback to default 80bp
    spread = get_credit_spread("BBB", 3.0, curve=None)
    assert spread == Decimal("0.008")  # 80 BP fallback


def test_get_credit_spread_curve_priority():
    """Verify curve data takes priority over default table."""
    curve = {
        "3Y": 120,  # 120 BP
        "5Y": 150,
    }

    spread = get_credit_spread("AAA", 3.0, curve=curve)
    assert spread == Decimal("120") / Decimal("10000")  # Use curve, not default 35 BP


def test_get_credit_spread_curve_fallback():
    """Verify curve fallback to 3Y/5Y/1Y when exact tenor missing."""
    curve = {
        "5Y": 100,
        "1Y": 50,
    }

    # Request 3Y, not in curve → fallback to 3Y (not in curve) → 5Y (in curve)
    spread = get_credit_spread("AAA", 3.0, curve=curve)
    assert spread == Decimal("100") / Decimal("10000")


def test_get_credit_spread_curve_with_none_values():
    """Verify curve with None values falls back correctly."""
    curve = {
        "3Y": None,
        "5Y": 90,
    }

    spread = get_credit_spread("AAA", 3.0, curve=curve)
    assert spread == Decimal("90") / Decimal("10000")  # Skip None, use 5Y


def test_get_credit_spread_rating_normalization():
    """Verify rating strings are normalized (uppercase, strip spaces)."""
    spread1 = get_credit_spread("aaa", 3.0, curve=None)
    spread2 = get_credit_spread("AAA", 3.0, curve=None)
    spread3 = get_credit_spread(" AA+ ", 3.0, curve=None)

    assert spread1 == spread2
    assert spread3 == Decimal("60") / Decimal("10000")


def test_get_credit_spread_default_fallback():
    """Verify final fallback to 80bp when no match found."""
    spread = get_credit_spread("UNKNOWN_RATING", 3.0, curve=None)
    assert spread == Decimal("0.008")  # 80 BP


def test_interpolate_ftp_rate_single_point():
    """Verify single point returns that point's rate."""
    curve_points = [(12.0, 0.025)]  # 12 months, 2.5%

    rate = interpolate_ftp_rate(6.0, curve_points)
    assert rate == pytest.approx(0.025)

    rate = interpolate_ftp_rate(24.0, curve_points)
    assert rate == pytest.approx(0.025)


def test_interpolate_ftp_rate_linear_interpolation():
    """Verify linear interpolation between two points."""
    curve_points = [
        (3.0, 0.020),  # 3 months, 2.0%
        (12.0, 0.030),  # 12 months, 3.0%
    ]

    # Midpoint: 7.5 months → (2.0% + 3.0%) / 2 = 2.5%
    rate = interpolate_ftp_rate(7.5, curve_points)
    assert rate == pytest.approx(0.025)

    # 1/4 of the way: 5.25 months → 2.0% + 0.25 * (3.0% - 2.0%) = 2.25%
    rate = interpolate_ftp_rate(5.25, curve_points)
    assert rate == pytest.approx(0.0225)


def test_interpolate_ftp_rate_extrapolation():
    """Verify extrapolation returns boundary rates."""
    curve_points = [
        (6.0, 0.022),
        (12.0, 0.028),
        (24.0, 0.035),
    ]

    # Below first point → return first rate
    rate = interpolate_ftp_rate(3.0, curve_points)
    assert rate == pytest.approx(0.022)

    # Above last point → return last rate
    rate = interpolate_ftp_rate(36.0, curve_points)
    assert rate == pytest.approx(0.035)


def test_interpolate_ftp_rate_empty_curve():
    """Verify empty curve returns 0.0."""
    rate = interpolate_ftp_rate(12.0, [])
    assert rate == pytest.approx(0.0)


def test_interpolate_ftp_rate_zero_term():
    """Verify zero or negative term returns first rate."""
    curve_points = [(6.0, 0.020), (12.0, 0.030)]

    rate = interpolate_ftp_rate(0.0, curve_points)
    assert rate == pytest.approx(0.020)

    rate = interpolate_ftp_rate(-5.0, curve_points)
    assert rate == pytest.approx(0.020)


def test_interpolate_ftp_rate_unsorted_input():
    """Verify function sorts curve points by tenor."""
    curve_points = [
        (24.0, 0.035),
        (6.0, 0.022),
        (12.0, 0.028),
    ]

    # Should sort to [(6, 0.022), (12, 0.028), (24, 0.035)]
    rate = interpolate_ftp_rate(9.0, curve_points)
    # 9 is between 6 and 12: 0.022 + (9-6)/(12-6) * (0.028-0.022) = 0.022 + 0.5 * 0.006 = 0.025
    assert rate == pytest.approx(0.025)


def test_interpolate_ftp_rate_exact_match():
    """Verify exact tenor match returns exact rate."""
    curve_points = [
        (3.0, 0.020),
        (6.0, 0.025),
        (12.0, 0.030),
    ]

    rate = interpolate_ftp_rate(6.0, curve_points)
    assert rate == pytest.approx(0.025)


def test_default_credit_spreads_table_structure():
    """Verify DEFAULT_CREDIT_SPREADS table has expected structure."""
    assert ("AAA", "1Y") in DEFAULT_CREDIT_SPREADS
    assert ("AAA", "3Y") in DEFAULT_CREDIT_SPREADS
    assert ("AAA", "5Y") in DEFAULT_CREDIT_SPREADS
    assert ("AA+", "1Y") in DEFAULT_CREDIT_SPREADS
    assert ("AA+", "3Y") in DEFAULT_CREDIT_SPREADS
    assert ("AA+", "5Y") in DEFAULT_CREDIT_SPREADS
    assert ("AA", "1Y") in DEFAULT_CREDIT_SPREADS
    assert ("AA", "3Y") in DEFAULT_CREDIT_SPREADS
    assert ("AA", "5Y") in DEFAULT_CREDIT_SPREADS

    # Verify values are in BP (Decimal)
    assert DEFAULT_CREDIT_SPREADS[("AAA", "3Y")] == Decimal("35")
    assert DEFAULT_CREDIT_SPREADS[("AA", "5Y")] == Decimal("110")
