"""
Unified curve interpolation — cubic spline (primary) + linear fallback.

Pure-Python cubic spline: no numpy/scipy dependency.  Natural boundary
conditions (S''(x_0) = S''(x_n) = 0) are used, matching the standard
financial curve convention.

Usage
-----
>>> from backend.app.core_finance.curve_engine.interpolation import (
...     curve_from_tenor_map, interpolate,
... )
>>> fitted = curve_from_tenor_map({"1Y": "2.10", "3Y": "2.30", "5Y": "2.50", "10Y": "2.80"})
>>> interpolate(fitted, 7.0)
Decimal('2.66...')
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from backend.app.core_finance.curve_engine.curve_types import (
    CurvePoint,
    FittedCurve,
    InterpolationMethod,
)

# Unified tenor→years mapping (merges the 5 separate copies across the codebase).
TENOR_YEARS: dict[str, float] = {
    "ON": 1 / 365,
    "1W": 7 / 365,
    "2W": 14 / 365,
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "9M": 0.75,
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "4Y": 4.0,
    "5Y": 5.0,
    "6Y": 6.0,
    "7Y": 7.0,
    "10Y": 10.0,
    "15Y": 15.0,
    "20Y": 20.0,
    "30Y": 30.0,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpolate(fitted: FittedCurve, target_years: float) -> Decimal:
    """Interpolate on a fitted curve.  Boundary: flat extrapolation (clamp)."""
    pts = fitted.points
    if not pts:
        return Decimal("0")

    if target_years <= pts[0].years:
        return pts[0].rate
    if target_years >= pts[-1].years:
        return pts[-1].rate

    if fitted.method == InterpolationMethod.CUBIC_SPLINE and fitted.spline_coefficients is not None:
        return _evaluate_spline(fitted, target_years)
    return _linear_interpolate(pts, target_years)


def curve_from_tenor_map(
    curve: Mapping[str, object],
    *,
    method: InterpolationMethod = InterpolationMethod.CUBIC_SPLINE,
) -> FittedCurve:
    """Build a ``FittedCurve`` from a tenor→rate mapping (compatible with
    existing ``dict[str, Decimal]`` curve data from ``YieldCurveRepository``).
    """
    from backend.app.core_finance.safe_decimal import safe_decimal

    points: list[CurvePoint] = []
    for tenor, rate in curve.items():
        years = TENOR_YEARS.get(str(tenor))
        if years is not None:
            points.append(CurvePoint(years=years, rate=safe_decimal(rate)))
    points.sort(key=lambda p: p.years)

    if method == InterpolationMethod.CUBIC_SPLINE and len(points) >= 3:
        return build_cubic_spline(points)
    return FittedCurve(
        method=InterpolationMethod.LINEAR,
        points=tuple(points),
    )


def build_cubic_spline(
    points: list[CurvePoint],
    *,
    bc_type: str = "natural",
) -> FittedCurve:
    """Construct a natural cubic spline from sorted curve points.

    Requires ≥ 3 points.  Falls back to LINEAR if fewer.
    ``bc_type`` is reserved for future clamped/not-a-knot variants.
    """
    sorted_pts = sorted(points, key=lambda p: p.years)
    n = len(sorted_pts)
    if n < 3:
        return FittedCurve(
            method=InterpolationMethod.LINEAR,
            points=tuple(sorted_pts),
        )

    coefficients = _compute_natural_cubic_spline_coefficients(sorted_pts)
    return FittedCurve(
        method=InterpolationMethod.CUBIC_SPLINE,
        points=tuple(sorted_pts),
        spline_coefficients=tuple(coefficients),
    )


# ---------------------------------------------------------------------------
# Internal: Natural cubic spline (pure Python, no numpy)
# ---------------------------------------------------------------------------

def _compute_natural_cubic_spline_coefficients(
    points: list[CurvePoint],
) -> list[tuple[float, float, float, float]]:
    """Thomas algorithm for natural cubic spline.

    For *n* points there are *n-1* segments.
    Each segment *i* is defined by:
        S_i(x) = a_i + b_i·(x - x_i) + c_i·(x - x_i)² + d_i·(x - x_i)³

    Natural boundary: S''(x_0) = S''(x_n) = 0  →  c_0 = c_n = 0.
    """
    n = len(points)
    xs = [p.years for p in points]
    ys = [float(p.rate) for p in points]

    # Step 1: intervals
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]

    # Step 2: set up tridiagonal system for c coefficients
    # (n equations, natural BC: c[0] = c[n-1] = 0)
    alpha = [0.0] * n
    for i in range(1, n - 1):
        alpha[i] = (3.0 / h[i]) * (ys[i + 1] - ys[i]) - (3.0 / h[i - 1]) * (ys[i] - ys[i - 1])

    # Thomas algorithm (tridiagonal solver)
    l = [0.0] * n
    mu = [0.0] * n
    z = [0.0] * n
    l[0] = 1.0

    for i in range(1, n - 1):
        l[i] = 2.0 * (xs[i + 1] - xs[i - 1]) - h[i - 1] * mu[i - 1]
        if l[i] == 0.0:
            l[i] = 1e-12  # degenerate guard
        mu[i] = h[i] / l[i]
        z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]

    l[n - 1] = 1.0

    c = [0.0] * n
    # Back-substitution
    for j in range(n - 2, 0, -1):
        c[j] = z[j] - mu[j] * c[j + 1]

    # Step 3: compute a, b, d from c
    coefficients: list[tuple[float, float, float, float]] = []
    for i in range(n - 1):
        a_i = ys[i]
        b_i = (ys[i + 1] - ys[i]) / h[i] - h[i] * (2.0 * c[i] + c[i + 1]) / 3.0
        d_i = (c[i + 1] - c[i]) / (3.0 * h[i]) if h[i] != 0 else 0.0
        coefficients.append((a_i, b_i, c[i], d_i))

    return coefficients


def _evaluate_spline(fitted: FittedCurve, target: float) -> Decimal:
    """Evaluate the cubic spline at ``target``."""
    pts = fitted.points
    coeffs = fitted.spline_coefficients
    assert coeffs is not None  # caller guarantees

    # Find the correct segment via binary search
    n = len(pts)
    lo, hi = 0, n - 2
    while lo < hi:
        mid = (lo + hi) // 2
        if target > pts[mid + 1].years:
            lo = mid + 1
        else:
            hi = mid
    i = lo

    a, b, c, d = coeffs[i]
    dx = target - pts[i].years
    result = a + b * dx + c * dx * dx + d * dx * dx * dx
    return Decimal(str(round(result, 8)))


def _linear_interpolate(
    points: tuple[CurvePoint, ...] | list[CurvePoint],
    target: float,
) -> Decimal:
    """Piecewise linear — semantically identical to the 5 existing implementations."""
    for i in range(len(points) - 1):
        y0, r0 = points[i].years, points[i].rate
        y1, r1 = points[i + 1].years, points[i + 1].rate
        if y0 <= target <= y1:
            span = y1 - y0
            if span <= 0:
                return r0
            frac = Decimal(str((target - y0) / span))
            return r0 + frac * (r1 - r0)
    return points[-1].rate
