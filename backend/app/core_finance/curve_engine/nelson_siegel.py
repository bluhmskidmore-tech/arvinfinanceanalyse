"""
Nelson-Siegel and Svensson parametric yield curve models.

Pure-Python implementation — no scipy/numpy dependency.  Uses Nelder-Mead
simplex optimisation (built-in) for least-squares fitting.

Nelson-Siegel (4 parameters):
    y(τ) = β₀ + β₁·[(1 - e^(-τ/λ)) / (τ/λ)]
              + β₂·[(1 - e^(-τ/λ)) / (τ/λ) - e^(-τ/λ)]

Svensson (6 parameters):
    y(τ) = NS(τ) + β₃·[(1 - e^(-τ/λ₂)) / (τ/λ₂) - e^(-τ/λ₂)]

Usage
-----
>>> from backend.app.core_finance.curve_engine.nelson_siegel import (
...     fit_nelson_siegel, ns_interpolate,
... )
>>> fitted = fit_nelson_siegel(points)
>>> rate = ns_interpolate(fitted, 7.5)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from backend.app.core_finance.curve_engine.curve_types import CurvePoint


# ---------------------------------------------------------------------------
# Parameter containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NSParams:
    """Nelson-Siegel parameters."""
    beta0: float  # long-term level
    beta1: float  # short-term factor
    beta2: float  # medium-term hump
    lam: float    # decay speed (λ)


@dataclass(frozen=True, slots=True)
class SvenssonParams:
    """Svensson parameters (extends NS with a second hump)."""
    beta0: float
    beta1: float
    beta2: float
    lam: float
    beta3: float
    lam2: float


@dataclass(frozen=True, slots=True)
class NSFitResult:
    """Result of a Nelson-Siegel or Svensson fit."""
    model: str  # "nelson_siegel" or "svensson"
    params: NSParams | SvenssonParams
    rmse: float  # root-mean-square error (pct)
    iterations: int
    source_points: int


# ---------------------------------------------------------------------------
# Model evaluation
# ---------------------------------------------------------------------------

def ns_rate(t: float, p: NSParams) -> float:
    """Evaluate Nelson-Siegel model at maturity ``t`` (years)."""
    if t <= 0:
        return p.beta0 + p.beta1
    x = t / p.lam
    if x > 500:
        return p.beta0  # exp(-x) ≈ 0
    exp_x = math.exp(-x)
    f1 = (1.0 - exp_x) / x
    f2 = f1 - exp_x
    return p.beta0 + p.beta1 * f1 + p.beta2 * f2


def svensson_rate(t: float, p: SvenssonParams) -> float:
    """Evaluate Svensson model at maturity ``t`` (years)."""
    base = ns_rate(t, NSParams(p.beta0, p.beta1, p.beta2, p.lam))
    if t <= 0:
        return base
    x2 = t / p.lam2
    if x2 > 500:
        return base
    exp_x2 = math.exp(-x2)
    f3 = (1.0 - exp_x2) / x2 - exp_x2
    return base + p.beta3 * f3


def ns_interpolate(result: NSFitResult, target_years: float) -> Decimal:
    """Interpolate (or extrapolate) using a fitted NS/Svensson model."""
    if isinstance(result.params, SvenssonParams):
        value = svensson_rate(target_years, result.params)
    else:
        value = ns_rate(target_years, result.params)
    return Decimal(str(round(value, 8)))


# ---------------------------------------------------------------------------
# Fitting: Nelder-Mead simplex (pure Python, no scipy)
# ---------------------------------------------------------------------------

def fit_nelson_siegel(
    points: list[CurvePoint],
    *,
    max_iter: int = 2000,
) -> NSFitResult:
    """Fit Nelson-Siegel model to observed curve points.

    Uses Nelder-Mead simplex to minimize sum of squared residuals.
    """
    if len(points) < 3:
        raise ValueError("Nelson-Siegel requires at least 3 data points.")

    sorted_pts = sorted(points, key=lambda p: p.years)
    xs = [p.years for p in sorted_pts]
    ys = [float(p.rate) for p in sorted_pts]

    # Initial guess: β₀ ≈ long rate, β₁ ≈ short-long spread, β₂ ≈ 0, λ ≈ 2
    x0 = [ys[-1], ys[0] - ys[-1], 0.0, 2.0]

    def objective(params: list[float]) -> float:
        b0, b1, b2, lam = params
        if lam <= 0.01:
            return 1e12
        p = NSParams(b0, b1, b2, lam)
        return sum((ns_rate(t, p) - y) ** 2 for t, y in zip(xs, ys))

    best, iters = _nelder_mead(objective, x0, max_iter=max_iter)
    params = NSParams(best[0], best[1], best[2], max(best[3], 0.01))
    rmse = math.sqrt(objective(best) / len(xs))

    return NSFitResult(
        model="nelson_siegel",
        params=params,
        rmse=rmse,
        iterations=iters,
        source_points=len(xs),
    )


def fit_svensson(
    points: list[CurvePoint],
    *,
    max_iter: int = 3000,
) -> NSFitResult:
    """Fit Svensson model (6 parameters). Requires ≥ 5 points."""
    if len(points) < 5:
        raise ValueError("Svensson requires at least 5 data points.")

    sorted_pts = sorted(points, key=lambda p: p.years)
    xs = [p.years for p in sorted_pts]
    ys = [float(p.rate) for p in sorted_pts]

    x0 = [ys[-1], ys[0] - ys[-1], 0.0, 2.0, 0.0, 5.0]

    def objective(params: list[float]) -> float:
        b0, b1, b2, lam, b3, lam2 = params
        if lam <= 0.01 or lam2 <= 0.01:
            return 1e12
        p = SvenssonParams(b0, b1, b2, lam, b3, lam2)
        return sum((svensson_rate(t, p) - y) ** 2 for t, y in zip(xs, ys))

    best, iters = _nelder_mead(objective, x0, max_iter=max_iter)
    params = SvenssonParams(
        best[0], best[1], best[2], max(best[3], 0.01),
        best[4], max(best[5], 0.01),
    )
    rmse = math.sqrt(objective(best) / len(xs))

    return NSFitResult(
        model="svensson",
        params=params,
        rmse=rmse,
        iterations=iters,
        source_points=len(xs),
    )


# ---------------------------------------------------------------------------
# Nelder-Mead simplex (pure Python)
# ---------------------------------------------------------------------------

def _nelder_mead(
    func,
    x0: list[float],
    *,
    max_iter: int = 2000,
    tol: float = 1e-10,
    alpha: float = 1.0,
    gamma: float = 2.0,
    rho: float = 0.5,
    sigma: float = 0.5,
) -> tuple[list[float], int]:
    """Nelder-Mead simplex optimisation.

    Returns (best_point, iterations_used).
    """
    n = len(x0)

    # Build initial simplex
    simplex: list[list[float]] = [list(x0)]
    for i in range(n):
        point = list(x0)
        point[i] += max(0.5, abs(x0[i]) * 0.1)
        simplex.append(point)

    values = [func(s) for s in simplex]

    for iteration in range(max_iter):
        # Sort by function value
        order = sorted(range(n + 1), key=lambda k: values[k])
        simplex = [simplex[k] for k in order]
        values = [values[k] for k in order]

        best_val = values[0]
        worst_val = values[-1]
        second_worst_val = values[-2]

        # Check convergence
        spread = worst_val - best_val
        if spread < tol:
            return simplex[0], iteration

        # Centroid of all except worst
        centroid = [0.0] * n
        for i in range(n):
            for j in range(n):
                centroid[j] += simplex[i][j]
            # (accumulated in inner loop)
        centroid = [c / n for c in centroid]

        # Reflection
        reflected = [centroid[j] + alpha * (centroid[j] - simplex[-1][j]) for j in range(n)]
        f_reflected = func(reflected)

        if best_val <= f_reflected < second_worst_val:
            simplex[-1] = reflected
            values[-1] = f_reflected
            continue

        if f_reflected < best_val:
            # Expansion
            expanded = [centroid[j] + gamma * (reflected[j] - centroid[j]) for j in range(n)]
            f_expanded = func(expanded)
            if f_expanded < f_reflected:
                simplex[-1] = expanded
                values[-1] = f_expanded
            else:
                simplex[-1] = reflected
                values[-1] = f_reflected
            continue

        # Contraction
        contracted = [centroid[j] + rho * (simplex[-1][j] - centroid[j]) for j in range(n)]
        f_contracted = func(contracted)

        if f_contracted < worst_val:
            simplex[-1] = contracted
            values[-1] = f_contracted
            continue

        # Shrink
        best = simplex[0]
        for i in range(1, n + 1):
            simplex[i] = [best[j] + sigma * (simplex[i][j] - best[j]) for j in range(n)]
            values[i] = func(simplex[i])

    return simplex[0], max_iter
