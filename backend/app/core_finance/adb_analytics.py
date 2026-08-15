"""
Pure calculation logic for Average Daily Balance (ADB / 日均资产负债) analytics.

No DB access here — only DataFrame transformations and numeric aggregations.
Imported by adb_analysis_service for orchestration.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from backend.app.core_finance.adb_rate_normalize import normalize_rate_values

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------

def compute_adb_trend(
    all_days: list[date],
    daily_assets: dict[date, Decimal],
) -> list[dict[str, float]]:
    """Build 30-day moving-average trend series over *all_days*."""
    trend: list[dict[str, float]] = []
    window: list[Decimal] = []
    window_sum = Decimal("0")
    for current_day in all_days:
        spot = daily_assets.get(current_day, Decimal("0"))
        window.append(spot)
        window_sum += spot
        if len(window) > 30:
            window_sum -= window.pop(0)
        moving_avg = (window_sum / Decimal(str(len(window)))) if window else Decimal("0")
        trend.append(
            {
                "date": current_day.strftime("%Y-%m-%d"),
                "daily_balance": float(spot),
                "moving_average_30d": float(moving_avg),
            }
        )
    return trend


def aggregate_daily_totals(
    all_days: list[date],
    bonds_assets: dict[date, Decimal],
    bonds_liabilities: dict[date, Decimal],
    ib_assets: dict[date, Decimal],
    ib_liabilities: dict[date, Decimal],
) -> tuple[dict[date, Decimal], dict[date, Decimal], Decimal, Decimal]:
    """Sum per-day asset/liability balances and return daily maps + period totals."""
    daily_assets: dict[date, Decimal] = {}
    daily_liabilities: dict[date, Decimal] = {}
    total_assets_sum = Decimal("0")
    total_liabilities_sum = Decimal("0")
    for current_day in all_days:
        assets_amount = bonds_assets.get(current_day, Decimal("0")) + ib_assets.get(current_day, Decimal("0"))
        liabilities_amount = (
            bonds_liabilities.get(current_day, Decimal("0")) + ib_liabilities.get(current_day, Decimal("0"))
        )
        daily_assets[current_day] = assets_amount
        daily_liabilities[current_day] = liabilities_amount
        total_assets_sum += assets_amount
        total_liabilities_sum += liabilities_amount
    return daily_assets, daily_liabilities, total_assets_sum, total_liabilities_sum


# ---------------------------------------------------------------------------
# Rate frame preparation
# ---------------------------------------------------------------------------

def enrich_bonds_asset_frame(bonds_assets_df: pd.DataFrame) -> pd.DataFrame:
    """Add category / balance / rate_decimal / weighted columns to bond asset frame."""
    from backend.app.core_finance.zqtz_asset_bond_category import classify_zqtz_asset_bond_label

    df = bonds_assets_df.copy()
    if "bond_category" in df.columns:
        df["category"] = df["bond_category"].apply(_clean_cat_local)
    else:
        df["category"] = df.apply(lambda r: classify_zqtz_asset_bond_label(r.to_dict()), axis=1)
    df["balance"] = _coerce_numeric_balance_with_warning(df, "market_value", "bonds_asset")
    df["rate_decimal"] = normalize_rate_values(df["yield_to_maturity"].tolist(), "yield_to_maturity")
    df["weighted"] = df["balance"] * df["rate_decimal"]
    return df


def enrich_bonds_liability_frame(bonds_liab_df: pd.DataFrame) -> pd.DataFrame:
    """Add category / balance / rate_decimal / weighted columns to bond liability frame."""
    df = bonds_liab_df.copy()
    if "bond_category" in df.columns:
        df["category"] = df["bond_category"].apply(_clean_cat_local)
    else:
        df["category"] = df["sub_type"].apply(_clean_cat_local)
    df["balance"] = _coerce_numeric_balance_with_warning(df, "market_value", "bonds_liability")
    # Keep missing coupon rates nullable; explicit 0 remains 0% for zero-coupon liabilities.
    df["rate_decimal"] = pd.Series(
        normalize_rate_values(df["coupon_rate"].tolist(), "coupon_rate"),
        index=df.index,
        dtype=object,
    )
    df["weighted"] = df["balance"] * df["rate_decimal"]
    return df


def enrich_interbank_frame(ib_df: pd.DataFrame) -> pd.DataFrame:
    """Add category / balance / rate_decimal / weighted columns to interbank frame."""
    from backend.app.core_finance.adb_analytics import _clean_cat_local
    df = ib_df.copy()
    df["category"] = df["product_type"].apply(_clean_cat_local)
    df["balance"] = _coerce_numeric_balance_with_warning(df, "amount", "interbank")
    df["rate_decimal"] = normalize_rate_values(df["interest_rate"].tolist(), "interbank_interest_rate")
    df["weighted"] = df["balance"] * df["rate_decimal"]
    return df


def _clean_cat_local(v: object) -> str:
    """Fallback used internally — mirrors _clean_cat in the service."""
    if v is None:
        return "其它"
    s = str(v).strip()
    return s if s else "其它"


def _coerce_numeric_balance_with_warning(
    df: pd.DataFrame,
    column: str,
    frame_name: str,
) -> pd.Series:
    numeric = pd.to_numeric(df[column], errors="coerce")
    missing_mask = numeric.isna()
    missing_count = int(missing_mask.sum())
    if missing_count:
        samples = [repr(value) for value in df.loc[missing_mask, column].head(3).tolist()]
        logger.warning(
            "ADB balance input %s.%s coerced %d row(s) to NaN before fillna(0.0); samples=%s",
            frame_name,
            column,
            missing_count,
            samples,
        )
    return numeric.fillna(0.0)


# ---------------------------------------------------------------------------
# Rate map
# ---------------------------------------------------------------------------

def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_rate_map(
    frames: list[pd.DataFrame],
) -> tuple[dict[str, float | None], float | None, dict[str, float | None]]:
    """Compute per-category and overall weighted average rate from enriched frames."""
    if not frames:
        return {}, None, {}
    totals: dict[str, tuple[float, float, float]] = {}
    total_balance = 0.0
    total_rate_balance = 0.0
    total_weighted = 0.0
    for frame in frames:
        if frame.empty:
            continue
        for row in frame.itertuples(index=False):
            balance_valid = getattr(row, "balance_valid", True)
            if pd.isna(balance_valid) or not bool(balance_valid):
                continue
            category = _clean_cat_local(getattr(row, "category", None))
            balance = _finite_float(getattr(row, "balance", 0) or 0)
            if balance is None:
                continue
            rate = _finite_float(getattr(row, "rate_decimal", None))
            weighted = balance * rate if rate is not None else 0.0
            rate_balance = balance if rate is not None else 0.0
            cur_bal, cur_rate_bal, cur_wgt = totals.get(category, (0.0, 0.0, 0.0))
            totals[category] = (cur_bal + balance, cur_rate_bal + rate_balance, cur_wgt + weighted)
            total_balance += balance
            total_rate_balance += rate_balance
            total_weighted += weighted
    rate_map: dict[str, float | None] = {
        cat: round(wgt / rate_bal * 100, 4) if rate_bal > 0 else None
        for cat, (_bal, rate_bal, wgt) in totals.items()
    }
    coverage_map: dict[str, float | None] = {
        cat: round(rate_bal / bal, 4) if bal > 0 else None
        for cat, (bal, rate_bal, _wgt) in totals.items()
    }
    total_rate = round(total_weighted / total_rate_balance * 100, 4) if total_rate_balance > 0 else None
    coverage_map["__total__"] = round(total_rate_balance / total_balance, 4) if total_balance > 0 else None
    return rate_map, total_rate, coverage_map


# ---------------------------------------------------------------------------
# Comparison breakdown helpers
# ---------------------------------------------------------------------------

def build_comparison_rows(
    side: str,
    spot_map: dict[str, Decimal],
    sum_map: dict[str, Decimal],
    num_days_dec: Decimal,
    top_n: int | None,
    simulated: bool,
    end_date: date,
    stable_factor_fn: Any,
    *,
    insufficient_window: bool = False,
) -> list[dict[str, float | None]]:
    """Build per-category spot/period-avg rows; sort by average balance (desc) for classification tables.

    When ``top_n`` is None, returns all categories (caller trims for display and totals).
    When ``insufficient_window`` is True (window too short to support a period average and
    simulation is not explicitly enabled), ``avg`` / ``deviation`` are None instead of a
    synthesized or spot-echoing number (fail-visible: missing != zero).
    """
    categories = set(spot_map.keys()) | set(sum_map.keys())
    rows: list[dict[str, float | None]] = []
    for category in categories:
        clean_key = _clean_cat_local(category)
        spot_value = spot_map.get(clean_key, Decimal("0")) or Decimal("0")
        avg_value: Decimal | None
        if simulated:
            avg_value = spot_value * stable_factor_fn(f"{side}:{end_date}:{clean_key}")
        elif insufficient_window:
            avg_value = None
        else:
            avg_value = (sum_map.get(clean_key, Decimal("0")) or Decimal("0")) / num_days_dec
        deviation = spot_value - avg_value if avg_value is not None else None
        if spot_value == 0 and (avg_value is None or avg_value == 0):
            continue
        rows.append(
            {
                "category": clean_key,
                "spot": float(spot_value),
                "avg": float(avg_value) if avg_value is not None else None,
                "deviation": float(deviation) if deviation is not None else None,
            }
        )
    rows.sort(key=lambda r: (r.get("avg") or 0.0, r.get("spot") or 0.0), reverse=True)
    if top_n is None:
        return rows
    return rows[: max(int(top_n), 0)]


def enrich_breakdown(
    rows: list[dict[str, float | None]],
    total_avg: float | None,
    rate_map: dict[str, float | None],
    rate_coverage_map: dict[str, float | None] | None = None,
) -> list[dict[str, Any]]:
    """Attach proportion and weighted_rate to comparison breakdown rows.

    ``avg`` may be None (insufficient window); then avg_balance/proportion stay None.
    """
    enriched: list[dict[str, Any]] = []
    for row in rows:
        avg = row["avg"]
        if avg is None:
            proportion = None
        elif total_avg is not None and total_avg > 0:
            proportion = round(float(avg) / total_avg * 100, 2)
        else:
            proportion = 0.0
        enriched.append(
            {
                "category": row["category"],
                "spot_balance": float(row["spot"]),
                "avg_balance": float(avg) if avg is not None else None,
                "proportion": proportion,
                "weighted_rate": rate_map.get(row["category"]),
                "rate_coverage_ratio": (rate_coverage_map or {}).get(row["category"]),
            }
        )
    return enriched


# ---------------------------------------------------------------------------
# Monthly helpers
# ---------------------------------------------------------------------------

def compute_mom_changes(
    avg_assets: float,
    avg_liabilities: float,
    prev_avg_assets: float | None,
    prev_avg_liabilities: float | None,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Return (assets_mom, assets_mom_pct, liabilities_mom, liabilities_mom_pct)."""
    assets_mom = assets_mom_pct = liabilities_mom = liabilities_mom_pct = None
    if prev_avg_assets is not None and prev_avg_assets != 0:
        assets_mom = round(avg_assets - prev_avg_assets, 2)
        assets_mom_pct = round((avg_assets - prev_avg_assets) / prev_avg_assets * 100, 2)
    if prev_avg_liabilities is not None and prev_avg_liabilities != 0:
        liabilities_mom = round(avg_liabilities - prev_avg_liabilities, 2)
        liabilities_mom_pct = round((avg_liabilities - prev_avg_liabilities) / prev_avg_liabilities * 100, 2)
    return assets_mom, assets_mom_pct, liabilities_mom, liabilities_mom_pct


def compute_nim(asset_yield: float | None, liability_cost: float | None) -> float | None:
    """Net interest margin = asset_yield - liability_cost (both in percent)."""
    if asset_yield is not None and liability_cost is not None:
        return round(asset_yield - liability_cost, 4)
    return None


def compute_weighted_rate(total_weighted: float, total_amount: float) -> float | None:
    """Weighted average rate as a percentage; None when amount is zero."""
    if total_amount > 0:
        return round(float(total_weighted / total_amount * 100), 4)
    return None


def month_date_range(year: int, month: int) -> tuple[date, date]:
    """Return (month_start, month_end) for the given calendar month.

    No truncation to today — callers that need a "not beyond today" cap should
    apply it themselves so historical queries remain reproducible.
    """
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year, 12, 31)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    return month_start, month_end
