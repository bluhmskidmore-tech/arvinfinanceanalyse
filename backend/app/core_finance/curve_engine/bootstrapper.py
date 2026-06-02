"""
Bootstrapper — derive zero-coupon (spot) rates from par yield curves.

Two modes of operation:

1. **Direct ingest** (preferred): When Choice provides spot rate curves
   (``treasury_spot``, ``cdb_spot``), use them directly — no bootstrap needed.

2. **Bootstrap from par yields**: When only par yield snapshots are available,
   strip the zero-coupon curve via iterative bootstrapping.

The bootstrapper can also **cross-validate** — compare a self-bootstrapped
curve against the Choice-provided spot curve to detect data quality issues.

Usage
-----
>>> from backend.app.core_finance.curve_engine.bootstrapper import (
...     bootstrap_zero_curve, cross_validate_spot_curve,
... )
>>> from backend.app.core_finance.curve_engine.curve_types import CurvePoint
>>> par_yields = [
...     CurvePoint(years=1.0, rate=Decimal("2.10")),
...     CurvePoint(years=3.0, rate=Decimal("2.30")),
...     CurvePoint(years=5.0, rate=Decimal("2.50")),
...     CurvePoint(years=10.0, rate=Decimal("2.80")),
... ]
>>> zeros = bootstrap_zero_curve(par_yields)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from backend.app.core_finance.curve_engine.curve_types import CurvePoint


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Result of a bootstrap operation."""
    zero_curve: list[CurvePoint]
    discount_factors: list[tuple[float, float]]  # (years, df)
    par_source_points: int
    method: str  # "bootstrap" or "direct_spot"


@dataclass(frozen=True, slots=True)
class CrossValidationResult:
    """Comparison between bootstrapped and vendor-provided spot curves."""
    max_abs_diff_bps: float
    mean_abs_diff_bps: float
    tenor_diffs: list[tuple[float, float]]  # (years, diff_bps)
    is_consistent: bool  # True if max_abs_diff_bps < threshold


def bootstrap_zero_curve(
    par_yields: list[CurvePoint],
    *,
    coupon_frequency: int = 1,
) -> BootstrapResult:
    """Bootstrap a zero-coupon curve from par yield observations.

    Parameters
    ----------
    par_yields
        Sorted par yield points.  ``rate`` is in **percent** (e.g. 2.50 = 2.50%).
    coupon_frequency
        1 = annual, 2 = semi-annual.

    Returns
    -------
    BootstrapResult
        Zero-coupon curve points (also in percent) and discount factors.
    """
    sorted_pars = sorted(par_yields, key=lambda p: p.years)
    if not sorted_pars:
        return BootstrapResult(
            zero_curve=[], discount_factors=[], par_source_points=0, method="bootstrap",
        )

    zeros: list[CurvePoint] = []
    discount_factors: list[tuple[float, float]] = []

    for i, par_point in enumerate(sorted_pars):
        t = par_point.years
        c = float(par_point.rate) / 100.0  # pct → decimal

        if t <= 1.0 or i == 0:
            # Short end: treat par yield as zero-coupon rate directly.
            z = float(par_point.rate)
            df = 1.0 / (1.0 + c) ** t if (1.0 + c) > 0 and t > 0 else 1.0
        else:
            # Bootstrap: solve for the terminal discount factor.
            coupon_per_period = c / coupon_frequency
            n_periods = max(1, int(round(t * coupon_frequency)))

            # Sum PV of intermediate coupons using known discount factors.
            pv_coupons = 0.0
            for j in range(1, n_periods):
                tj = j / coupon_frequency
                dfj = _interpolate_df(discount_factors, tj)
                pv_coupons += coupon_per_period * dfj

            # Terminal payment: coupon + principal = (coupon_per_period + 1).
            # Par bond: price = 1 → 1 = pv_coupons + (coupon_per_period + 1) * df_T
            denominator = 1.0 + coupon_per_period
            if denominator == 0:
                df = 1.0
            else:
                df = (1.0 - pv_coupons) / denominator

            # Convert discount factor to continuously-compounded zero rate? No:
            # keep annual compounding to match Chinese bond market convention.
            if df > 0 and t > 0:
                z = ((1.0 / df) ** (1.0 / t) - 1.0) * 100.0  # → pct
            else:
                z = float(par_point.rate)  # fallback

        zeros.append(CurvePoint(years=t, rate=Decimal(str(round(z, 6)))))
        discount_factors.append((t, df))

    return BootstrapResult(
        zero_curve=zeros,
        discount_factors=discount_factors,
        par_source_points=len(sorted_pars),
        method="bootstrap",
    )


def direct_spot_result(spot_points: list[CurvePoint]) -> BootstrapResult:
    """Wrap vendor-provided spot rates into a BootstrapResult (no bootstrap needed)."""
    sorted_pts = sorted(spot_points, key=lambda p: p.years)
    dfs: list[tuple[float, float]] = []
    for pt in sorted_pts:
        r = float(pt.rate) / 100.0
        t = pt.years
        df = 1.0 / (1.0 + r) ** t if (1.0 + r) > 0 and t > 0 else 1.0
        dfs.append((t, df))
    return BootstrapResult(
        zero_curve=sorted_pts,
        discount_factors=dfs,
        par_source_points=len(sorted_pts),
        method="direct_spot",
    )


def cross_validate_spot_curve(
    bootstrapped: list[CurvePoint],
    vendor_spot: list[CurvePoint],
    *,
    threshold_bps: float = 5.0,
) -> CrossValidationResult:
    """Compare bootstrapped zero rates against vendor-provided spot rates.

    Parameters
    ----------
    threshold_bps
        Maximum acceptable absolute difference (in basis points) for
        the curves to be considered consistent.
    """
    vendor_map = {pt.years: float(pt.rate) for pt in vendor_spot}
    tenor_diffs: list[tuple[float, float]] = []

    for pt in bootstrapped:
        vendor_rate = vendor_map.get(pt.years)
        if vendor_rate is not None:
            diff_bps = (float(pt.rate) - vendor_rate) * 100.0  # pct diff → bps
            tenor_diffs.append((pt.years, diff_bps))

    if not tenor_diffs:
        return CrossValidationResult(
            max_abs_diff_bps=0.0,
            mean_abs_diff_bps=0.0,
            tenor_diffs=[],
            is_consistent=True,
        )

    abs_diffs = [abs(d) for _, d in tenor_diffs]
    return CrossValidationResult(
        max_abs_diff_bps=max(abs_diffs),
        mean_abs_diff_bps=sum(abs_diffs) / len(abs_diffs),
        tenor_diffs=tenor_diffs,
        is_consistent=max(abs_diffs) < threshold_bps,
    )


# ---------------------------------------------------------------------------
# Internal: discount factor interpolation
# ---------------------------------------------------------------------------

def _interpolate_df(
    dfs: list[tuple[float, float]],
    target: float,
) -> float:
    """Log-linear interpolation of discount factors."""
    if not dfs:
        return 1.0
    if target <= dfs[0][0]:
        t0, df0 = dfs[0]
        if t0 <= 0:
            return df0
        return df0 ** (target / t0)
    if target >= dfs[-1][0]:
        t_last, df_last = dfs[-1]
        if t_last > 0 and df_last > 0:
            # Tail policy: extrapolate at the last observed zero rate.
            return df_last ** (target / t_last)
        return df_last

    for i in range(len(dfs) - 1):
        t0, df0 = dfs[i]
        t1, df1 = dfs[i + 1]
        if t0 <= target <= t1:
            if t1 == t0:
                return df0
            w = (target - t0) / (t1 - t0)
            # Log-linear: ln(df) = (1-w)*ln(df0) + w*ln(df1)
            if df0 > 0 and df1 > 0:
                ln_df = math.log(df0) + w * (math.log(df1) - math.log(df0))
                return math.exp(ln_df)
            return df0 + w * (df1 - df0)
    return dfs[-1][1]
