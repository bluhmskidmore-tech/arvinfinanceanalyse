"""
Tests for bootstrapper — zero-coupon curve derivation and cross-validation.

Covers:
- Bootstrap from par yields: flat curve → spot == par
- Bootstrap from upward-sloping curve: spot > par for long tenors
- Direct spot result wrapping
- Cross-validation: identical curves → consistent
- Cross-validation: divergent curves → inconsistent
- Edge cases: empty, single-point, short-end only
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.curve_engine.bootstrapper import (
    BootstrapResult,
    CrossValidationResult,
    bootstrap_zero_curve,
    cross_validate_spot_curve,
    direct_spot_result,
)
from backend.app.core_finance.curve_engine.curve_types import CurvePoint


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FLAT_CURVE = [
    CurvePoint(years=1.0, rate=Decimal("3.00")),
    CurvePoint(years=3.0, rate=Decimal("3.00")),
    CurvePoint(years=5.0, rate=Decimal("3.00")),
    CurvePoint(years=10.0, rate=Decimal("3.00")),
]

UPWARD_CURVE = [
    CurvePoint(years=1.0, rate=Decimal("2.00")),
    CurvePoint(years=3.0, rate=Decimal("2.50")),
    CurvePoint(years=5.0, rate=Decimal("3.00")),
    CurvePoint(years=10.0, rate=Decimal("3.50")),
]


# ---------------------------------------------------------------------------
# Bootstrap from par yields
# ---------------------------------------------------------------------------

class TestBootstrapZeroCurve:

    def test_flat_curve_spot_equals_par(self):
        """On a flat par curve, zero rates should equal par rates."""
        result = bootstrap_zero_curve(FLAT_CURVE)
        assert result.method == "bootstrap"
        assert result.par_source_points == 4
        for pt in result.zero_curve:
            assert abs(float(pt.rate) - 3.0) < 0.05, f"Flat curve: spot at {pt.years}Y = {pt.rate}, expected ~3.0"

    def test_flat_curve_extrapolates_intermediate_tail_coupons_at_last_zero_rate(self):
        """Sparse long-end coupon dates beyond the last known DF keep flat-curve zeros flat."""
        result = bootstrap_zero_curve(FLAT_CURVE)
        ten_year_df = dict(result.discount_factors)[10.0]

        assert abs(float(result.zero_curve[-1].rate) - 3.0) < 0.01
        assert abs(ten_year_df - (1.0 / (1.0 + 0.03) ** 10.0)) < 0.0001

    def test_upward_curve_spot_above_par_at_long_end(self):
        """For upward-sloping curve, spot rates should be ≥ par at long tenors."""
        result = bootstrap_zero_curve(UPWARD_CURVE)
        assert len(result.zero_curve) == 4
        # Short end: spot ≈ par
        assert abs(float(result.zero_curve[0].rate) - 2.0) < 0.01
        # Long end: spot should be at or above par
        long_spot = float(result.zero_curve[-1].rate)
        long_par = float(UPWARD_CURVE[-1].rate)
        assert long_spot >= long_par - 0.1, f"Spot {long_spot} should be >= par {long_par} at long end"

    def test_discount_factors_decrease(self):
        """Discount factors should monotonically decrease with maturity."""
        result = bootstrap_zero_curve(UPWARD_CURVE)
        for i in range(len(result.discount_factors) - 1):
            t0, df0 = result.discount_factors[i]
            t1, df1 = result.discount_factors[i + 1]
            assert df1 < df0, f"DF at {t1}Y ({df1}) should be < DF at {t0}Y ({df0})"

    def test_discount_factors_positive(self):
        """All discount factors should be positive."""
        result = bootstrap_zero_curve(UPWARD_CURVE)
        for t, df in result.discount_factors:
            assert df > 0, f"DF at {t}Y must be positive, got {df}"

    def test_empty_input(self):
        result = bootstrap_zero_curve([])
        assert result.zero_curve == []
        assert result.discount_factors == []
        assert result.par_source_points == 0

    def test_single_point(self):
        result = bootstrap_zero_curve([CurvePoint(years=1.0, rate=Decimal("2.50"))])
        assert len(result.zero_curve) == 1
        assert abs(float(result.zero_curve[0].rate) - 2.5) < 0.01

    def test_semi_annual_frequency(self):
        """Semi-annual coupon frequency should produce valid results."""
        result = bootstrap_zero_curve(UPWARD_CURVE, coupon_frequency=2)
        assert len(result.zero_curve) == 4
        # Should still produce reasonable values
        for pt in result.zero_curve:
            assert 1.0 < float(pt.rate) < 5.0, f"Rate at {pt.years}Y = {pt.rate} out of range"


# ---------------------------------------------------------------------------
# Direct spot result
# ---------------------------------------------------------------------------

class TestDirectSpotResult:

    def test_wraps_vendor_spot_rates(self):
        spot_points = [
            CurvePoint(years=1.0, rate=Decimal("2.05")),
            CurvePoint(years=5.0, rate=Decimal("2.55")),
            CurvePoint(years=10.0, rate=Decimal("2.85")),
        ]
        result = direct_spot_result(spot_points)
        assert result.method == "direct_spot"
        assert result.par_source_points == 3
        assert len(result.zero_curve) == 3
        assert len(result.discount_factors) == 3

    def test_discount_factors_consistent(self):
        spot_points = [CurvePoint(years=1.0, rate=Decimal("3.00"))]
        result = direct_spot_result(spot_points)
        t, df = result.discount_factors[0]
        # df = 1 / (1 + 0.03)^1 ≈ 0.97087
        assert abs(df - 1.0 / 1.03) < 0.0001


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

class TestCrossValidation:

    def test_identical_curves_consistent(self):
        curve = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
            CurvePoint(years=10.0, rate=Decimal("2.80")),
        ]
        result = cross_validate_spot_curve(curve, curve)
        assert result.is_consistent
        assert result.max_abs_diff_bps == 0.0
        assert result.mean_abs_diff_bps == 0.0

    def test_small_diff_consistent(self):
        bootstrapped = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
        ]
        vendor = [
            CurvePoint(years=1.0, rate=Decimal("2.01")),  # 1bp diff
            CurvePoint(years=5.0, rate=Decimal("2.52")),  # 2bp diff
        ]
        result = cross_validate_spot_curve(bootstrapped, vendor, threshold_bps=5.0)
        assert result.is_consistent
        assert result.max_abs_diff_bps < 5.0

    def test_large_diff_inconsistent(self):
        bootstrapped = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
        ]
        vendor = [
            CurvePoint(years=1.0, rate=Decimal("2.10")),  # 10bp diff
            CurvePoint(years=5.0, rate=Decimal("2.80")),  # 30bp diff
        ]
        result = cross_validate_spot_curve(bootstrapped, vendor, threshold_bps=5.0)
        assert not result.is_consistent
        assert result.max_abs_diff_bps > 5.0

    def test_no_overlapping_tenors(self):
        bootstrapped = [CurvePoint(years=1.0, rate=Decimal("2.00"))]
        vendor = [CurvePoint(years=5.0, rate=Decimal("2.50"))]
        result = cross_validate_spot_curve(bootstrapped, vendor)
        assert result.is_consistent  # No data to compare → considered OK
        assert len(result.tenor_diffs) == 0
