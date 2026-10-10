"""Closed-form golden tests for the formal yield-curve engine.

Every numerical expectation below is a literal derived from the cash-flow or
model formula shown in the adjacent comment.  No expected value is generated
by calling the implementation under test.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.curve_engine.bootstrapper import (
    bootstrap_zero_curve,
    cross_validate_spot_curve,
    direct_spot_result,
)
from backend.app.core_finance.curve_engine.curve_types import (
    CurvePoint,
    FittedCurve,
    InterpolationMethod,
)
from backend.app.core_finance.curve_engine.interpolation import (
    build_cubic_spline,
    curve_from_tenor_map,
    interpolate,
)
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
# Bootstrap closed-form goldens
# ---------------------------------------------------------------------------


def test_bootstrap_zero_coupon_node_uses_percent_and_annual_effective_discounting():
    result = bootstrap_zero_curve(
        [CurvePoint(years=0.5, rate=Decimal("4.00"))],
    )

    # The input rate is percent, so r = 4 / 100 = 0.04.
    # With annual-effective discounting,
    # D(0.5) = (1 + 0.04)^(-0.5) = 0.9805806756909202.
    assert result.zero_curve[0].rate == Decimal("4.0")
    assert result.discount_factors[0] == pytest.approx(
        (0.5, 0.9805806756909202),
        abs=1e-15,
    )


def test_bootstrap_annual_coupon_node_strips_prior_coupon_cash_flow():
    result = bootstrap_zero_curve(
        [
            CurvePoint(years=1.0, rate=Decimal("4.00")),
            CurvePoint(years=2.0, rate=Decimal("5.00")),
        ],
        coupon_frequency=1,
    )

    # D1 = 1 / 1.04 = 0.9615384615384615.
    # A par 2Y annual 5% bond obeys 1 = 0.05*D1 + 1.05*D2, hence
    # D2 = (1 - 0.05*D1) / 1.05 = 0.9065934065934066.
    # z2 = (D2^(-1/2) - 1)*100 = 5.025249489363415%, rounded to 6 dp.
    assert [years for years, _ in result.discount_factors] == [1.0, 2.0]
    assert [df for _, df in result.discount_factors] == pytest.approx(
        [0.9615384615384615, 0.9065934065934066],
        abs=1e-15,
    )
    assert [point.rate for point in result.zero_curve] == [
        Decimal("4.0"),
        Decimal("5.025249"),
    ]


def test_bootstrap_semiannual_one_year_node_strips_six_month_coupon():
    result = bootstrap_zero_curve(
        [
            CurvePoint(years=0.5, rate=Decimal("2.00")),
            CurvePoint(years=1.0, rate=Decimal("3.00")),
        ],
        coupon_frequency=2,
    )

    # D(0.5) = (1 + 0.02)^(-0.5) = 0.9901475429766743.
    # The 1Y par bond pays 3% / 2 = 1.5% each half-year:
    # 1 = 0.015*D(0.5) + 1.015*D(1).
    # D(1) = 0.9705889525668472 and
    # z1 = (D(1)^(-1) - 1)*100 = 3.030226890113629%, rounded to 3.030227.
    assert [years for years, _ in result.discount_factors] == [0.5, 1.0]
    assert [df for _, df in result.discount_factors] == pytest.approx(
        [0.9901475429766743, 0.9705889525668472],
        abs=1e-15,
    )
    assert result.zero_curve[1].rate == Decimal("3.030227")


def test_bootstrap_multi_node_chain_uses_all_preceding_discount_factors():
    result = bootstrap_zero_curve(
        [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=2.0, rate=Decimal("4.00")),
            CurvePoint(years=3.0, rate=Decimal("6.00")),
        ],
        coupon_frequency=1,
    )

    # D1 = 1/1.02 = 0.9803921568627451.
    # D2 = (1 - 0.04*D1)/1.04 = 0.9238310708898944.
    # D3 = (1 - 0.06*(D1 + D2))/1.06 = 0.8356100059762657.
    # Therefore z2 = (D2^(-1/2)-1)*100 = 4.040808320189282% and
    # z3 = (D3^(-1/3)-1)*100 = 6.169259773259926%, each rounded to 6 dp.
    assert [years for years, _ in result.discount_factors] == [1.0, 2.0, 3.0]
    assert [df for _, df in result.discount_factors] == pytest.approx(
        [0.9803921568627451, 0.9238310708898944, 0.8356100059762657],
        abs=1e-15,
    )
    assert [point.rate for point in result.zero_curve] == [
        Decimal("2.0"),
        Decimal("4.040808"),
        Decimal("6.16926"),
    ]


def test_bootstrap_lone_long_annual_node_locks_current_underidentified_policy():
    result = bootstrap_zero_curve(
        [CurvePoint(years=2.0, rate=Decimal("5.00"))],
        coupon_frequency=1,
    )

    # Current-behaviour lock, not the standard coupon-bond identity:
    # with no earlier D(1), the implementation silently treats the first 2Y
    # annual par node as a zero node, so z2 = 5% and
    # D2 = (1.05)^(-2) = 0.9070294784580498.
    # A standard strip cannot identify D2 from this bond alone because
    # 1 = 0.05*D1 + 1.05*D2 contains the unobserved D1.
    assert result.zero_curve[0].rate == Decimal("5.0")
    assert result.discount_factors[0] == pytest.approx(
        (2.0, 0.9070294784580498),
        abs=1e-15,
    )


def test_direct_spot_result_converts_each_percent_rate_to_discount_factor():
    result = direct_spot_result(
        [
            CurvePoint(years=2.0, rate=Decimal("10.00")),
            CurvePoint(years=1.0, rate=Decimal("5.00")),
        ],
    )

    # Sorting is by maturity.  Annual-effective discount factors are
    # D1 = 1/1.05 = 20/21 = 0.9523809523809523 and
    # D2 = 1/(1.10)^2 = 100/121 = 0.8264462809917356.
    assert [point.years for point in result.zero_curve] == [1.0, 2.0]
    assert [years for years, _ in result.discount_factors] == [1.0, 2.0]
    assert [df for _, df in result.discount_factors] == pytest.approx(
        [0.9523809523809523, 0.8264462809917356],
        abs=1e-15,
    )


def test_cross_validation_reports_signed_basis_points_and_strict_threshold():
    result = cross_validate_spot_curve(
        [
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=5.0, rate=Decimal("3.00")),
        ],
        [
            CurvePoint(years=1.0, rate=Decimal("1.50")),
            CurvePoint(years=5.0, rate=Decimal("3.25")),
        ],
        threshold_bps=50.0,
    )

    # Percent differences convert to bp by multiplying by 100:
    # (2.00 - 1.50)*100 = +50 bp; (3.00 - 3.25)*100 = -25 bp.
    # max(|diff|) = 50 bp and mean(|diff|) = (50+25)/2 = 37.5 bp.
    assert result.tenor_diffs == [(1.0, 50.0), (5.0, -25.0)]
    assert result.max_abs_diff_bps == 50.0
    assert result.mean_abs_diff_bps == 37.5
    # Current policy is max_diff < threshold, not <=, so equality is rejected.
    assert result.is_consistent is False


def test_cross_validation_without_common_tenors_is_explicitly_incomparable():
    result = cross_validate_spot_curve(
        [CurvePoint(years=1.0, rate=Decimal("2.00"))],
        [CurvePoint(years=2.0, rate=Decimal("2.00"))],
    )

    # There are zero matched observations, so no numerical difference exists:
    # the max/mean sentinels are 0.0 but consistency is None, not True.
    assert result.tenor_diffs == []
    assert result.max_abs_diff_bps == 0.0
    assert result.mean_abs_diff_bps == 0.0
    assert result.is_consistent is None


# ---------------------------------------------------------------------------
# Interpolation closed-form goldens
# ---------------------------------------------------------------------------


def test_linear_interpolation_at_knots_between_knots_and_outside_domain():
    fitted = FittedCurve(
        method=InterpolationMethod.LINEAR,
        points=(
            CurvePoint(years=1.0, rate=Decimal("2.00")),
            CurvePoint(years=3.0, rate=Decimal("6.00")),
        ),
    )

    # At 2Y, w=(2-1)/(3-1)=1/2 and y=2+(1/2)*(6-2)=4.
    assert interpolate(fitted, 1.0) == Decimal("2.00")
    assert interpolate(fitted, 2.0) == Decimal("4.000")
    assert interpolate(fitted, 3.0) == Decimal("6.00")
    # Current boundary policy is flat clamping, not line extrapolation.
    assert interpolate(fitted, 0.0) == Decimal("2.00")
    assert interpolate(fitted, 4.0) == Decimal("6.00")


def test_natural_cubic_spline_coefficients_and_values_are_closed_form():
    fitted = build_cubic_spline(
        [
            CurvePoint(years=3.0, rate=Decimal("0")),
            CurvePoint(years=1.0, rate=Decimal("0")),
            CurvePoint(years=2.0, rate=Decimal("1")),
        ],
    )

    # For knots (1,0), (2,1), (3,0), h0=h1=1 and natural boundaries give
    # c0=c2=0.  The sole tridiagonal equation is 4*c1=-6, so c1=-3/2.
    # Thus S0=1.5*dx-0.5*dx^3 and
    # S1=1-1.5*dx^2+0.5*dx^3.
    assert fitted.method == InterpolationMethod.CUBIC_SPLINE
    assert fitted.spline_coefficients is not None
    assert fitted.spline_coefficients[0] == pytest.approx(
        (0.0, 1.5, 0.0, -0.5),
        abs=1e-15,
    )
    assert fitted.spline_coefficients[1] == pytest.approx(
        (1.0, 0.0, -1.5, 0.5),
        abs=1e-15,
    )

    # The polynomials hit all knots exactly.  At either midpoint dx=1/2:
    # S0=1.5/2-0.5/8=0.6875 and S1=1-1.5/4+0.5/8=0.6875.
    assert interpolate(fitted, 1.0) == Decimal("0")
    assert interpolate(fitted, 2.0) == Decimal("1.0")
    assert interpolate(fitted, 3.0) == Decimal("0")
    assert interpolate(fitted, 1.5) == Decimal("0.6875")
    assert interpolate(fitted, 2.5) == Decimal("0.6875")
    # Current behaviour clamps outside the knot range instead of extending
    # the first/last cubic polynomial.
    assert interpolate(fitted, 0.0) == Decimal("0")
    assert interpolate(fitted, 4.0) == Decimal("0")


def test_curve_from_tenor_map_maps_sorts_and_ignores_unknown_tenors():
    fitted = curve_from_tenor_map(
        {"3Y": "6.00", "UNKNOWN": "99.00", "1Y": "2.00"},
        method=InterpolationMethod.LINEAR,
    )

    # The authoritative map assigns 1Y->1 and 3Y->3; UNKNOWN has no mapping.
    # After maturity sorting, linear interpolation at 2Y is
    # 2 + (2-1)/(3-1)*(6-2) = 4.
    assert fitted.points == (
        CurvePoint(years=1.0, rate=Decimal("2.00")),
        CurvePoint(years=3.0, rate=Decimal("6.00")),
    )
    assert interpolate(fitted, 2.0) == Decimal("4.000")


def test_empty_and_single_node_curves_lock_boundary_sentinels():
    empty = build_cubic_spline([])
    single = build_cubic_spline(
        [CurvePoint(years=5.0, rate=Decimal("2.50"))],
    )

    # With zero observations there is no interpolable ordinate; current
    # behaviour returns a numeric 0 sentinel and a LINEAR fallback container.
    assert empty.method == InterpolationMethod.LINEAR
    assert interpolate(empty, 5.0) == Decimal("0")

    # With one observation every target is on an outer boundary, so flat
    # clamping returns the sole ordinate 2.50 on both sides and at the knot.
    assert single.method == InterpolationMethod.LINEAR
    assert interpolate(single, 1.0) == Decimal("2.50")
    assert interpolate(single, 5.0) == Decimal("2.50")
    assert interpolate(single, 10.0) == Decimal("2.50")


# ---------------------------------------------------------------------------
# Nelson-Siegel / Svensson closed-form goldens
# ---------------------------------------------------------------------------


def test_ns_rate_matches_closed_form_factor_loadings():
    params = NSParams(beta0=3.0, beta1=-1.0, beta2=2.0, lam=2.0)

    # At t=2 and lambda=2, x=t/lambda=1:
    # f1=1-e^-1, f2=1-2e^-1, and
    # y=3-(1-e^-1)+2*(1-2e^-1)=4-3e^-1
    #  = 2.896361676485673.
    assert ns_rate(2.0, params) == pytest.approx(
        2.896361676485673,
        abs=1e-15,
    )
    # The t->0 limits are f1->1 and f2->0, so y(0)=beta0+beta1=2.
    assert ns_rate(0.0, params) == 2.0


def test_svensson_rate_matches_closed_form_second_hump():
    params = SvenssonParams(
        beta0=3.0,
        beta1=-1.0,
        beta2=2.0,
        lam=2.0,
        beta3=2.0,
        lam2=1.0,
    )

    # The NS base at t=2 is 4-3e^-1.  For lambda2=1, x2=2 and
    # f3=(1-e^-2)/2-e^-2=1/2-(3/2)e^-2.
    # y=(4-3e^-1)+2*f3=5-3e^-1-3e^-2
    #  = 3.490355826775835.
    assert svensson_rate(2.0, params) == pytest.approx(
        3.490355826775835,
        abs=1e-15,
    )
    # At t=0 the extra Svensson loading tends to zero, leaving 3-1=2.
    assert svensson_rate(0.0, params) == 2.0


def test_ns_interpolate_dispatches_models_and_rounds_closed_form_values():
    ns_result = NSFitResult(
        model="nelson_siegel",
        params=NSParams(beta0=3.0, beta1=-1.0, beta2=2.0, lam=2.0),
        rmse=0.0,
        iterations=0,
        source_points=0,
    )
    svensson_result = NSFitResult(
        model="svensson",
        params=SvenssonParams(
            beta0=3.0,
            beta1=-1.0,
            beta2=2.0,
            lam=2.0,
            beta3=2.0,
            lam2=1.0,
        ),
        rmse=0.0,
        iterations=0,
        source_points=0,
    )

    # From the two derivations above, 8-decimal output rounding gives
    # 2.896361676... -> 2.89636168 and
    # 3.490355826... -> 3.49035583.
    assert ns_interpolate(ns_result, 2.0) == Decimal("2.89636168")
    assert ns_interpolate(svensson_result, 2.0) == Decimal("3.49035583")


def test_fit_nelson_siegel_accepts_underidentified_three_point_fit():
    points = [
        CurvePoint(years=1.0, rate=Decimal("2.50")),
        CurvePoint(years=2.0, rate=Decimal("2.50")),
        CurvePoint(years=3.0, rate=Decimal("2.50")),
    ]
    result = fit_nelson_siegel(points, max_iter=0)

    # Current-behaviour lock: three observations are fewer than the four NS
    # parameters, but validation accepts them.  The documented initial guess
    # is (last rate, short-long, 0, 2)=(2.5,0,0,2), which prices every point
    # at 2.5, so SSE=0 and RMSE=sqrt(0/3)=0.
    assert result.params == NSParams(2.5, 0.0, 0.0, 2.0)
    assert result.rmse == 0.0
    assert result.iterations == 0
    assert result.source_points == 3
    # max_iter=0 performs no convergence step, yet the result has no status
    # field distinguishing convergence from iteration-budget exhaustion.
    assert not hasattr(result, "converged")


def test_fit_nelson_siegel_rejects_only_below_implementation_minimum():
    points = [
        CurvePoint(years=1.0, rate=Decimal("2.50")),
        CurvePoint(years=2.0, rate=Decimal("2.50")),
    ]

    # The current gate is observation_count < 3, not the four-parameter
    # identifiability threshold, so exactly two observations raise.
    with pytest.raises(ValueError, match="at least 3"):
        fit_nelson_siegel(points)


def test_fit_svensson_accepts_underidentified_five_point_fit():
    points = [
        CurvePoint(years=1.0, rate=Decimal("3.00")),
        CurvePoint(years=2.0, rate=Decimal("3.00")),
        CurvePoint(years=3.0, rate=Decimal("3.00")),
        CurvePoint(years=4.0, rate=Decimal("3.00")),
        CurvePoint(years=5.0, rate=Decimal("3.00")),
    ]
    result = fit_svensson(points, max_iter=0)

    # Current-behaviour lock: five observations are fewer than six Svensson
    # parameters, but validation accepts them.  The initial guess is
    # (3,0,0,2,0,5), which is the constant 3% curve, so
    # SSE=0 and RMSE=sqrt(0/5)=0 without any optimisation iteration.
    assert result.params == SvenssonParams(3.0, 0.0, 0.0, 2.0, 0.0, 5.0)
    assert result.rmse == 0.0
    assert result.iterations == 0
    assert result.source_points == 5
    assert not hasattr(result, "converged")


def test_fit_svensson_rejects_only_below_implementation_minimum():
    points = [
        CurvePoint(years=1.0, rate=Decimal("3.00")),
        CurvePoint(years=2.0, rate=Decimal("3.00")),
        CurvePoint(years=3.0, rate=Decimal("3.00")),
        CurvePoint(years=4.0, rate=Decimal("3.00")),
    ]

    # The current gate is observation_count < 5, not the six-parameter
    # identifiability threshold, so exactly four observations raise.
    with pytest.raises(ValueError, match="at least 5"):
        fit_svensson(points)
