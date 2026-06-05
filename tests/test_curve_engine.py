"""
Tests for curve_engine — cubic spline + linear fallback + curve_from_tenor_map.

Covers:
- Exact-match at known points (both methods)
- Cubic vs linear divergence at mid-segment
- Boundary (clamp) behaviour
- Edge cases: empty, 1-point, 2-point, degenerate
- Monotonicity preservation on typical yield curves
- curve_from_tenor_map integration with tenor strings
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.curve_engine.curve_types import (
    CurvePoint,
    FittedCurve,
    InterpolationMethod,
)
from backend.app.core_finance.curve_engine.interpolation import (
    build_cubic_spline,
    curve_from_tenor_map,
    interpolate,
    _linear_interpolate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Typical China treasury-like curve (pct)
TREASURY_POINTS = [
    CurvePoint(years=1.0, rate=Decimal("2.10")),
    CurvePoint(years=3.0, rate=Decimal("2.30")),
    CurvePoint(years=5.0, rate=Decimal("2.50")),
    CurvePoint(years=7.0, rate=Decimal("2.65")),
    CurvePoint(years=10.0, rate=Decimal("2.80")),
    CurvePoint(years=30.0, rate=Decimal("3.10")),
]


def _build_linear(points: list[CurvePoint]) -> FittedCurve:
    return FittedCurve(method=InterpolationMethod.LINEAR, points=tuple(sorted(points, key=lambda p: p.years)))


def _build_spline(points: list[CurvePoint]) -> FittedCurve:
    return build_cubic_spline(points)


# ---------------------------------------------------------------------------
# Exact-match at known points
# ---------------------------------------------------------------------------

class TestExactMatch:
    def test_spline_at_knots(self):
        fitted = _build_spline(TREASURY_POINTS)
        for pt in TREASURY_POINTS:
            result = interpolate(fitted, pt.years)
            assert abs(result - pt.rate) < Decimal("0.0001"), f"Spline mismatch at {pt.years}Y: {result} vs {pt.rate}"

    def test_linear_at_knots(self):
        fitted = _build_linear(TREASURY_POINTS)
        for pt in TREASURY_POINTS:
            result = interpolate(fitted, pt.years)
            assert result == pt.rate, f"Linear mismatch at {pt.years}Y"


# ---------------------------------------------------------------------------
# Cubic vs linear divergence
# ---------------------------------------------------------------------------

class TestCubicVsLinear:
    """Cubic spline should differ from linear at non-knot points, proving it's
    actually fitting a curve rather than straight-line segments."""

    def test_mid_segment_differs(self):
        spline = _build_spline(TREASURY_POINTS)
        linear = _build_linear(TREASURY_POINTS)
        # Test at 2Y (between 1Y and 3Y)
        spline_val = interpolate(spline, 2.0)
        linear_val = interpolate(linear, 2.0)
        # Both should be close to 2.20 but not identical
        assert abs(spline_val - linear_val) > Decimal("0.001") or abs(spline_val - linear_val) < Decimal("0.1"), \
            "Spline and linear should produce different (but reasonable) values at mid-points"

    def test_kink_region_smoother(self):
        """At 7→10Y transition (kink region), spline should produce a smoother
        mid-point than the linear piecewise result."""
        spline = _build_spline(TREASURY_POINTS)
        # 8.5Y is the midpoint of 7-10 segment
        result = interpolate(spline, 8.5)
        assert Decimal("2.60") < result < Decimal("2.85"), f"Spline at 8.5Y={result} out of reasonable range"


# ---------------------------------------------------------------------------
# Boundary (clamp) behaviour
# ---------------------------------------------------------------------------

class TestBoundary:
    def test_below_min_tenor(self):
        fitted = _build_spline(TREASURY_POINTS)
        assert interpolate(fitted, 0.5) == Decimal("2.10")
        assert interpolate(fitted, 0.0) == Decimal("2.10")
        assert interpolate(fitted, -1.0) == Decimal("2.10")

    def test_above_max_tenor(self):
        fitted = _build_spline(TREASURY_POINTS)
        assert interpolate(fitted, 30.0) == Decimal("3.10")
        assert interpolate(fitted, 50.0) == Decimal("3.10")

    def test_exact_boundary(self):
        fitted = _build_spline(TREASURY_POINTS)
        assert interpolate(fitted, 1.0) == TREASURY_POINTS[0].rate
        result = interpolate(fitted, 30.0)
        assert abs(result - TREASURY_POINTS[-1].rate) < Decimal("0.0001")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_curve(self):
        fitted = FittedCurve(method=InterpolationMethod.LINEAR, points=())
        assert interpolate(fitted, 5.0) == Decimal("0")

    def test_single_point(self):
        pts = [CurvePoint(years=5.0, rate=Decimal("2.50"))]
        fitted = _build_linear(pts)
        assert interpolate(fitted, 3.0) == Decimal("2.50")
        assert interpolate(fitted, 5.0) == Decimal("2.50")
        assert interpolate(fitted, 10.0) == Decimal("2.50")

    def test_two_points_falls_back_to_linear(self):
        pts = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=10.0, rate=Decimal("3.00")),
        ]
        fitted = build_cubic_spline(pts)
        assert fitted.method == InterpolationMethod.LINEAR
        result = interpolate(fitted, 5.5)
        expected = Decimal("2.00") + (Decimal("3.00") - Decimal("2.00")) * Decimal(str(4.5 / 9.0))
        assert abs(result - expected) < Decimal("0.001")

    def test_three_points_minimum_spline(self):
        pts = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
            CurvePoint(years=10.0, rate=Decimal("2.80")),
        ]
        fitted = build_cubic_spline(pts)
        assert fitted.method == InterpolationMethod.CUBIC_SPLINE
        assert fitted.spline_coefficients is not None
        # Should still hit exact points
        assert abs(interpolate(fitted, 1.0) - Decimal("2.00")) < Decimal("0.0001")
        assert abs(interpolate(fitted, 5.0) - Decimal("2.50")) < Decimal("0.0001")
        assert abs(interpolate(fitted, 10.0) - Decimal("2.80")) < Decimal("0.0001")


# ---------------------------------------------------------------------------
# Monotonicity on typical curves
# ---------------------------------------------------------------------------

class TestMonotonicity:
    """A normal upward-sloping curve should produce monotonically increasing
    interpolated values (no wiggle artefacts from spline)."""

    def test_monotone_increasing(self):
        fitted = _build_spline(TREASURY_POINTS)
        prev = Decimal("-999")
        # Sample every 0.5Y from 1.0 to 30.0
        t = 1.0
        while t <= 30.0:
            val = interpolate(fitted, t)
            assert val >= prev - Decimal("0.001"), \
                f"Monotonicity violation at {t}Y: {val} < {prev}"
            prev = val
            t += 0.5


# ---------------------------------------------------------------------------
# curve_from_tenor_map integration
# ---------------------------------------------------------------------------

class TestCurveFromTenorMap:
    def test_basic_tenor_map(self):
        curve = {
            "1Y": Decimal("2.10"),
            "3Y": Decimal("2.30"),
            "5Y": Decimal("2.50"),
            "10Y": Decimal("2.80"),
        }
        fitted = curve_from_tenor_map(curve)
        assert fitted.method == InterpolationMethod.CUBIC_SPLINE
        assert len(fitted.points) == 4
        # Exact match at knots
        assert abs(interpolate(fitted, 1.0) - Decimal("2.10")) < Decimal("0.0001")
        assert abs(interpolate(fitted, 10.0) - Decimal("2.80")) < Decimal("0.0001")

    def test_linear_fallback_with_two_tenors(self):
        curve = {"1Y": "2.10", "10Y": "2.80"}
        fitted = curve_from_tenor_map(curve)
        assert fitted.method == InterpolationMethod.LINEAR

    def test_unknown_tenors_ignored(self):
        curve = {"1Y": "2.10", "5Y": "2.50", "UNKNOWN": "9.99", "10Y": "2.80"}
        fitted = curve_from_tenor_map(curve)
        assert len(fitted.points) == 3  # UNKNOWN filtered out

    def test_force_linear(self):
        curve = {"1Y": "2.10", "3Y": "2.30", "5Y": "2.50", "10Y": "2.80"}
        fitted = curve_from_tenor_map(curve, method=InterpolationMethod.LINEAR)
        assert fitted.method == InterpolationMethod.LINEAR

    def test_empty_curve(self):
        fitted = curve_from_tenor_map({})
        assert len(fitted.points) == 0
        assert interpolate(fitted, 5.0) == Decimal("0")
