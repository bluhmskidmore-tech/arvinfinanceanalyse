"""
Tests for Nelson-Siegel and Svensson parametric curve fitting.

Covers:
- NS fit convergence on typical treasury curves
- NS knot reproduction (fitted values ≈ observed at input points)
- NS extrapolation beyond observed range
- NS parameter interpretation (β₀ ≈ long rate, β₀+β₁ ≈ short rate)
- Svensson fit on 6-point curves
- Edge cases: minimum points, flat curve
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.curve_engine.curve_types import CurvePoint
from backend.app.core_finance.curve_engine.nelson_siegel import (
    NSFitResult,
    NSParams,
    SvenssonParams,
    fit_nelson_siegel,
    fit_svensson,
    ns_interpolate,
    ns_rate,
    svensson_rate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TREASURY_POINTS = [
    CurvePoint(years=0.25, rate=Decimal("1.80")),
    CurvePoint(years=1.0, rate=Decimal("2.10")),
    CurvePoint(years=3.0, rate=Decimal("2.30")),
    CurvePoint(years=5.0, rate=Decimal("2.50")),
    CurvePoint(years=7.0, rate=Decimal("2.65")),
    CurvePoint(years=10.0, rate=Decimal("2.80")),
    CurvePoint(years=30.0, rate=Decimal("3.10")),
]

FLAT_POINTS = [
    CurvePoint(years=1.0, rate=Decimal("3.00")),
    CurvePoint(years=3.0, rate=Decimal("3.00")),
    CurvePoint(years=5.0, rate=Decimal("3.00")),
    CurvePoint(years=10.0, rate=Decimal("3.00")),
]


# ---------------------------------------------------------------------------
# Nelson-Siegel fitting
# ---------------------------------------------------------------------------

class TestNelsonSiegelFit:

    def test_convergence(self):
        result = fit_nelson_siegel(TREASURY_POINTS)
        assert result.model == "nelson_siegel"
        assert result.rmse < 0.15  # < 15bp RMSE
        assert result.source_points == 7
        assert isinstance(result.params, NSParams)

    def test_knot_reproduction(self):
        """Fitted values at observed points should be close to input."""
        result = fit_nelson_siegel(TREASURY_POINTS)
        for pt in TREASURY_POINTS:
            fitted_rate = float(ns_interpolate(result, pt.years))
            observed_rate = float(pt.rate)
            assert abs(fitted_rate - observed_rate) < 0.2, \
                f"At {pt.years}Y: fitted={fitted_rate:.4f} vs observed={observed_rate:.4f}"

    def test_extrapolation_beyond_30y(self):
        """NS should produce reasonable extrapolation beyond max observed tenor."""
        result = fit_nelson_siegel(TREASURY_POINTS)
        rate_40y = float(ns_interpolate(result, 40.0))
        rate_50y = float(ns_interpolate(result, 50.0))
        # Should approach β₀ (long-term level) ≈ around 3.1-3.2
        assert 2.5 < rate_40y < 4.0, f"40Y extrapolation {rate_40y} out of range"
        assert 2.5 < rate_50y < 4.0, f"50Y extrapolation {rate_50y} out of range"
        # Should converge (40Y and 50Y should be close)
        assert abs(rate_50y - rate_40y) < 0.1

    def test_parameter_interpretation(self):
        """β₀ ≈ long-term rate, β₀+β₁ ≈ instantaneous short rate."""
        result = fit_nelson_siegel(TREASURY_POINTS)
        p = result.params
        assert isinstance(p, NSParams)
        # β₀ should be near the long end (3.0-3.2)
        assert 2.5 < p.beta0 < 4.0, f"β₀={p.beta0} should be near long rate"
        # β₀+β₁ should be near the short end (1.8-2.1)
        short_rate = p.beta0 + p.beta1
        assert 1.0 < short_rate < 3.0, f"β₀+β₁={short_rate} should be near short rate"

    def test_flat_curve(self):
        result = fit_nelson_siegel(FLAT_POINTS)
        assert result.rmse < 0.05
        # All fitted values should be ≈ 3.0
        for t in [1.0, 5.0, 10.0, 20.0]:
            rate = float(ns_interpolate(result, t))
            assert abs(rate - 3.0) < 0.1, f"Flat curve at {t}Y: {rate}"

    def test_minimum_3_points(self):
        pts = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
            CurvePoint(years=10.0, rate=Decimal("2.80")),
        ]
        result = fit_nelson_siegel(pts)
        assert result.source_points == 3

    def test_too_few_points_raises(self):
        pts = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
        ]
        with pytest.raises(ValueError, match="at least 3"):
            fit_nelson_siegel(pts)


# ---------------------------------------------------------------------------
# Svensson fitting
# ---------------------------------------------------------------------------

class TestSvenssonFit:

    def test_convergence(self):
        result = fit_svensson(TREASURY_POINTS)
        assert result.model == "svensson"
        assert result.rmse < 0.15
        assert isinstance(result.params, SvenssonParams)

    def test_better_than_ns_on_humped_curve(self):
        """Svensson (6 params) should fit at least as well as NS (4 params)."""
        ns_result = fit_nelson_siegel(TREASURY_POINTS)
        sv_result = fit_svensson(TREASURY_POINTS)
        assert sv_result.rmse <= ns_result.rmse + 0.01  # Should be equal or better

    def test_too_few_points_raises(self):
        pts = [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=3.0, rate=Decimal("2.30")),
            CurvePoint(years=5.0, rate=Decimal("2.50")),
            CurvePoint(years=10.0, rate=Decimal("2.80")),
        ]
        with pytest.raises(ValueError, match="at least 5"):
            fit_svensson(pts)


# ---------------------------------------------------------------------------
# Direct model evaluation
# ---------------------------------------------------------------------------

class TestModelEvaluation:

    def test_ns_rate_at_zero(self):
        p = NSParams(beta0=3.0, beta1=-1.0, beta2=0.5, lam=2.0)
        # At t=0: y = β₀ + β₁ = 3.0 + (-1.0) = 2.0
        assert abs(ns_rate(0.0, p) - 2.0) < 0.001

    def test_ns_rate_at_infinity(self):
        p = NSParams(beta0=3.0, beta1=-1.0, beta2=0.5, lam=2.0)
        # At t→∞: y → β₀ = 3.0
        assert abs(ns_rate(1000.0, p) - 3.0) < 0.001

    def test_svensson_extends_ns(self):
        ns_p = NSParams(beta0=3.0, beta1=-1.0, beta2=0.5, lam=2.0)
        sv_p = SvenssonParams(beta0=3.0, beta1=-1.0, beta2=0.5, lam=2.0, beta3=0.0, lam2=5.0)
        # With β₃=0, Svensson should equal NS
        for t in [0.5, 1.0, 5.0, 10.0, 30.0]:
            assert abs(ns_rate(t, ns_p) - svensson_rate(t, sv_p)) < 0.0001
