"""
Pure calculation logic for Average Daily Balance (ADB / 日均资产负债) analytics.

No DB access here — only DataFrame transformations and numeric aggregations.
Imported by adb_analysis_service for orchestration.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd

from backend.app.core_finance.adb_rate_normalize import normalize_rate_values


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
    from backend.app.core_finance.adb_analytics import _clean_cat_local  # avoid circular — defined below
    df = bonds_assets_df.copy()
    df["category"] = df["sub_type"].apply(_clean_cat_local)
    df["balance"] = pd.to_numeric(df["market_value"], errors="coerce").fillna(0.0)
    df["rate_decimal"] = normalize_rate_values(df["yield_to_maturity"].tolist(), "yield_to_maturity")
    df["weighted"] = df["balance"] * df["rate_decimal"]
    return df


def enrich_bonds_liability_frame(bonds_liab_df: pd.DataFrame) -> pd.DataFrame:
    """Add category / balance / rate_decimal / weighted columns to bond liability frame."""
    from backend.app.core_finance.adb_analytics import _clean_cat_local
    df = bonds_liab_df.copy()
    df["category"] = df["sub_type"].apply(_clean_cat_local)
    df["balance"] = pd.to_numeric(df["market_value"], errors="coerce").fillna(0.0)
    normalized = normalize_rate_values(df["coupon_rate"].tolist(), "coupon_rate")
    df["rate_decimal"] = [
        rate if coupon not in (None, 0, 0.0) else 0.0
        for coupon, rate in zip(df["coupon_rate"].tolist(), normalized, strict=True)
    ]
    df["weighted"] = df["balance"] * df["rate_decimal"]
    return df


def enrich_interbank_frame(ib_df: pd.DataFrame) -> pd.DataFrame:
    """Add category / balance / rate_decimal / weighted columns to interbank frame."""
    from backend.app.core_finance.adb_analytics import _clean_cat_local
    df = ib_df.copy()
    df["category"] = df["product_type"].apply(_clean_cat_local)
    df["balance"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["rate_decimal"] = normalize_rate_values(df["interest_rate"].tolist(), "interbank_interest_rate")
    df["weighted"] = df["balance"] * df["rate_decimal"]
    return df


def _clean_cat_local(v: object) -> str:
    """Fallback used internally — mirrors _clean_cat in the service."""
    if v is None:
        return "其它"
    s = str(v).strip()
    return s if s else "其它"


# ---------------------------------------------------------------------------
# Rate map
# ---------------------------------------------------------------------------

def build_rate_map(frames: list[pd.DataFrame]) -> tuple[dict[str, float | None], float | None]:
    """Compute per-category and overall weighted average rate from enriched frames."""
    if not frames:
        return {}, None
    totals: dict[str, tuple[float, float]] = {}
    total_balance = 0.0
    total_weighted = 0.0
    for frame in frames:
        if frame.empty:
            continue
        for row in frame.itertuples(index=False):
            category = _clean_cat_local(getattr(row, "category", None))
            balance = float(getattr(row, "balance", 0) or 0)
            weighted = float(getattr(row, "weighted", 0) or 0)
            cur_bal, cur_wgt = totals.get(category, (0.0, 0.0))
            totals[category] = (cur_bal + balance, cur_wgt + weighted)
            total_balance += balance
            total_weighted += weighted
    rate_map: dict[str, float | None] = {
        cat: round(wgt / bal * 100, 4) if bal > 0 else None
        for cat, (bal, wgt) in totals.items()
    }
    total_rate = round(total_weighted / total_balance * 100, 4) if total_balance > 0 else None
    return rate_map, total_rate


# ---------------------------------------------------------------------------
# Comparison breakdown helpers
# ---------------------------------------------------------------------------

def build_comparison_rows(
    side: str,
    spot_map: dict[str, Decimal],
    sum_map: dict[str, Decimal],
    num_days_dec: Decimal,
    top_n: int,
    simulated: bool,
    end_date: date,
    stable_factor_fn: Any,
) -> list[dict[str, float]]:
    """Rank categories by deviation magnitude for the spot-vs-avg comparison view."""
    categories = set(spot_map.keys()) | set(sum_map.keys())
    rows: list[dict[str, float]] = []
    for category in categories:
        clean_key = _clean_cat_local(category)
        spot_value = spot_map.get(clean_key, Decimal("0")) or Decimal("0")
        if simulated:
            avg_value = spot_value * stable_factor_fn(f"{side}:{end_date}:{clean_key}")
        else:
            avg_value = (sum_map.get(clean_key, Decimal("0")) or Decimal("0")) / num_days_dec
        deviation = spot_value - avg_value
        if spot_value == 0 and avg_value == 0:
            continue
        rows.append(
            {
                "category": clean_key,
                "spot": float(spot_value),
                "avg": float(avg_value),
                "deviation": float(deviation),
            }
        )
    rows.sort(key=lambda r: (abs(r.get("deviation") or 0.0), r.get("spot") or 0.0), reverse=True)
    return rows[: max(int(top_n), 0)]


def enrich_breakdown(
    rows: list[dict[str, float]],
    total_avg: float,
    rate_map: dict[str, float | None],
) -> list[dict[str, Any]]:
    """Attach proportion and weighted_rate to comparison breakdown rows."""
    return [
        {
            "category": row["category"],
            "spot_balance": float(row["spot"]),
            "avg_balance": float(row["avg"]),
            "proportion": round(float(row["avg"]) / total_avg * 100, 2) if total_avg > 0 else 0.0,
            "weighted_rate": rate_map.get(row["category"]),
        }
        for row in rows
    ]


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
    """Return (month_start, month_end) capped at today."""
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year, 12, 31)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    return month_start, min(month_end, date.today())
