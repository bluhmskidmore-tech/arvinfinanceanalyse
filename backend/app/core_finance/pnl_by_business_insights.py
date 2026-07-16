"""Approved derived metrics for the PnL-by-business workflow.

The functions in this module are pure calculations over already governed YTD
and monthly parent rows.  They do not read storage and they do not redefine
the underlying PnL, balance, FX, or FTP calculations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from backend.app.core_finance.pnl import TWOPLACES
from backend.app.core_finance.zqtz_asset_bond_category import is_parent_zqtz_business_row

ZERO = Decimal("0")
HUNDRED = Decimal("100")
SIXPLACES = Decimal("0.000001")

DEFAULT_NEGATIVE_FTP_WARNING_THRESHOLD_PCT = Decimal("50")
DEFAULT_NEGATIVE_FTP_MINIMUM_OBSERVED_MONTHS = 6
DEFAULT_SCALE_YIELD_MINIMUM_ELIGIBLE_ROWS = 6


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _quantize_pct(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES)


def _parent_rows(items: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return [
        item
        for item in items
        if is_parent_zqtz_business_row(
            str(item.get("row_key") or ""),
            str(item.get("business_type") or ""),
            item.get("source_note"),
        )
    ]


def _trailing_month_keys(as_of_date: str, lookback_months: int) -> list[str]:
    year = int(as_of_date[:4])
    month = int(as_of_date[5:7])
    keys: list[str] = []
    for _ in range(lookback_months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def _longest_negative_streak(series: Sequence[tuple[str, Decimal | None]]) -> int:
    longest = 0
    current = 0
    for _, value in series:
        if value is not None and value < ZERO:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _persistence_stats(
    series: Sequence[tuple[str, Decimal | None]],
    *,
    minimum_observed_months: int,
) -> dict[str, object]:
    observed = [value for _, value in series if value is not None]
    negative_count = sum(1 for value in observed if value < ZERO)
    eligible = len(observed) >= minimum_observed_months
    return {
        "months_observed": len(observed),
        "eligible": eligible,
        "status": "eligible" if eligible else "insufficient_observations",
        "negative_ftp_month_share_pct": (
            _quantize_pct(Decimal(negative_count) / Decimal(len(observed)) * HUNDRED) if eligible else None
        ),
        "negative_ftp_longest_streak_months": (_longest_negative_streak(series) if eligible else None),
    }


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def build_business_type_concentration(
    *,
    items: Sequence[Mapping[str, object]],
    year: int,
    as_of_date: str | None,
    top_n: int = 3,
) -> dict[str, object]:
    """Calculate HHI and Top-N from CNY-equivalent YTD parent average balance."""
    entries: list[tuple[str, str, Decimal]] = []
    total_balance = ZERO
    for item in _parent_rows(items):
        avg_balance = _decimal(item.get("avg_balance")) or ZERO
        if avg_balance <= ZERO:
            continue
        entries.append(
            (
                str(item.get("row_key") or ""),
                str(item.get("business_type") or ""),
                avg_balance,
            )
        )
        total_balance += avg_balance

    common = {
        "year": year,
        "as_of_date": as_of_date,
        "currency_basis": "CNY_EQUIVALENT",
        "population_basis": "YTD_AVG_BALANCE_PARENT_ROWS",
        "top_n": top_n,
    }
    if not entries or total_balance <= ZERO:
        return {
            **common,
            "total_avg_balance": None,
            "hhi_pct": None,
            "top_n_share_pct": None,
            "rows": [],
        }

    ranked = sorted(entries, key=lambda entry: (-entry[2], entry[0]))
    hhi_ratio = ZERO
    rows: list[dict[str, object]] = []
    for row_key, business_type, avg_balance in ranked:
        share_ratio = avg_balance / total_balance
        hhi_ratio += share_ratio * share_ratio
        rows.append(
            {
                "row_key": row_key,
                "business_type": business_type,
                "avg_balance": avg_balance,
                "share_pct": _quantize_pct(share_ratio * HUNDRED),
            }
        )
    top_n_balance = sum((entry[2] for entry in ranked[:top_n]), ZERO)
    return {
        **common,
        "total_avg_balance": total_balance,
        "hhi_pct": _quantize_pct(hhi_ratio * HUNDRED),
        "top_n_share_pct": _quantize_pct(top_n_balance / total_balance * HUNDRED),
        "rows": rows,
    }


def build_negative_ftp_persistence(
    *,
    monthly_by_key: Mapping[str, Mapping[str, object]],
    as_of_date: str,
    lookback_months: int = 12,
    warning_threshold_pct: Decimal = DEFAULT_NEGATIVE_FTP_WARNING_THRESHOLD_PCT,
    minimum_observed_months: int = DEFAULT_NEGATIVE_FTP_MINIMUM_OBSERVED_MONTHS,
) -> dict[str, object]:
    """Measure negative FTP persistence over rolling natural months.

    Missing months are excluded from the denominator and break a streak.  A
    business warning is only valid when both the observation minimum and the
    negative-month-share threshold are met.
    """
    month_keys = _trailing_month_keys(as_of_date, lookback_months)
    overall_series: list[tuple[str, Decimal | None]] = []
    row_values: dict[str, dict[str, Decimal | None]] = {}
    row_labels: dict[str, str] = {}

    for month_key in month_keys:
        bucket = monthly_by_key.get(month_key)
        if bucket is None:
            overall_series.append((month_key, None))
            continue
        summary = bucket.get("summary")
        summary_value = summary.get("ftp_net_pnl") if isinstance(summary, Mapping) else None
        overall_series.append((month_key, _decimal(summary_value)))
        raw_items = bucket.get("items")
        items = raw_items if isinstance(raw_items, Sequence) else []
        for item in _parent_rows(items):
            row_key = str(item.get("row_key") or "")
            row_labels[row_key] = str(item.get("business_type") or "")
            row_values.setdefault(row_key, {})[month_key] = _decimal(item.get("ftp_net_pnl"))

    rows: list[dict[str, object]] = []
    for row_key in sorted(row_values):
        values = row_values[row_key]
        stats = _persistence_stats(
            [(month_key, values.get(month_key)) for month_key in month_keys],
            minimum_observed_months=minimum_observed_months,
        )
        share = stats["negative_ftp_month_share_pct"]
        warning_triggered = (
            bool(stats["eligible"]) and share is not None and Decimal(str(share)) >= warning_threshold_pct
        )
        rows.append(
            {
                "row_key": row_key,
                "business_type": row_labels[row_key],
                **stats,
                "warning_triggered": warning_triggered,
            }
        )

    overall_stats = _persistence_stats(
        overall_series,
        minimum_observed_months=minimum_observed_months,
    )
    return {
        "as_of_date": as_of_date,
        "lookback_months": lookback_months,
        "window_start_month": month_keys[0] if month_keys else None,
        "window_end_month": month_keys[-1] if month_keys else None,
        "warning_threshold_pct": warning_threshold_pct,
        "minimum_observed_months": minimum_observed_months,
        "warning_row_count": sum(1 for row in rows if row["warning_triggered"]),
        "rows": rows,
        **overall_stats,
    }


def build_business_type_share_drift(
    *,
    current: Mapping[str, object],
    baseline: Mapping[str, object] | None,
    year: int,
    as_of_date: str,
    baseline_year: int,
    baseline_as_of_date: str,
) -> dict[str, object]:
    """Compare YTD average-balance shares with the prior-year same period."""
    current_total = _decimal(current.get("total_avg_balance"))
    baseline_total = _decimal(baseline.get("total_avg_balance")) if baseline is not None else None
    current_total_valid = current_total is not None and current_total > ZERO
    baseline_total_valid = baseline_total is not None and baseline_total > ZERO
    available = current_total_valid and baseline_total_valid
    availability_reason = (
        "current_total_non_positive"
        if not current_total_valid
        else "baseline_missing"
        if baseline is None
        else "baseline_total_non_positive"
        if not baseline_total_valid
        else None
    )
    current_rows = {str(row["row_key"]): row for row in current.get("rows", []) if isinstance(row, Mapping)}
    baseline_rows = {
        str(row["row_key"]): row
        for row in (baseline.get("rows", []) if baseline is not None else [])
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, object]] = []
    for row_key in sorted(set(current_rows) | set(baseline_rows)):
        current_row = current_rows.get(row_key)
        baseline_row = baseline_rows.get(row_key)
        current_raw_share = (
            (_decimal(current_row.get("avg_balance")) or ZERO) / current_total * HUNDRED
            if current_row is not None and current_total_valid and current_total is not None
            else None
        )
        baseline_raw_share = (
            (_decimal(baseline_row.get("avg_balance")) or ZERO) / baseline_total * HUNDRED
            if baseline_row is not None and baseline_total_valid and baseline_total is not None
            else None
        )
        if available:
            current_raw_share = current_raw_share if current_row is not None else ZERO
            baseline_raw_share = baseline_raw_share if baseline_row is not None else ZERO
            lifecycle_status = (
                "new"
                if current_row is not None and baseline_row is None
                else "exited"
                if current_row is None and baseline_row is not None
                else "continued"
            )
            drift_pp = _quantize_pct(current_raw_share - baseline_raw_share)
        else:
            lifecycle_status = "unavailable"
            drift_pp = None
        source_row = current_row or baseline_row
        assert source_row is not None
        rows.append(
            {
                "row_key": row_key,
                "business_type": source_row["business_type"],
                "current_share_pct": (_quantize_pct(current_raw_share) if current_raw_share is not None else None),
                "baseline_share_pct": (_quantize_pct(baseline_raw_share) if baseline_raw_share is not None else None),
                "drift_pp": drift_pp,
                "lifecycle_status": lifecycle_status,
            }
        )
    if available:
        rows.sort(key=lambda row: (-abs(Decimal(str(row["drift_pp"]))), str(row["row_key"])))
    return {
        "year": year,
        "as_of_date": as_of_date,
        "baseline_year": baseline_year,
        "baseline_as_of_date": baseline_as_of_date if baseline is not None else None,
        "baseline_available": baseline_total_valid,
        "available": available,
        "availability_reason": availability_reason,
        "comparison_basis": "PRIOR_YEAR_SAME_PERIOD_YTD_AVG_BALANCE_SHARE",
        "rows": rows,
    }


def build_scale_yield_quadrant(
    *,
    items: Sequence[Mapping[str, object]],
    year: int,
    as_of_date: str,
    minimum_eligible_rows: int = DEFAULT_SCALE_YIELD_MINIMUM_ELIGIBLE_ROWS,
) -> dict[str, object]:
    """Build a descriptive relative scale-vs-FTP-after-yield quadrant."""
    positive_rows: list[tuple[Mapping[str, object], Decimal]] = []
    total_balance = ZERO
    for item in _parent_rows(items):
        avg_balance = _decimal(item.get("avg_balance")) or ZERO
        if avg_balance <= ZERO:
            continue
        positive_rows.append((item, avg_balance))
        total_balance += avg_balance

    eligible: list[tuple[Mapping[str, object], Decimal, Decimal, Decimal]] = []
    if total_balance > ZERO:
        for item, avg_balance in positive_rows:
            yield_pct = _decimal(item.get("ftp_net_annualized_yield_pct"))
            if yield_pct is None:
                continue
            eligible.append((item, avg_balance, avg_balance / total_balance * HUNDRED, yield_pct))

    common = {
        "year": year,
        "as_of_date": as_of_date,
        "currency_basis": "CNY_EQUIVALENT",
        "scale_basis": "YTD_AVG_BALANCE_SHARE",
        "yield_basis": "FTP_NET_ANNUALIZED_YIELD_PCT",
        "minimum_eligible_rows": minimum_eligible_rows,
        "eligible_row_count": len(eligible),
        "total_avg_balance": total_balance if total_balance > ZERO else None,
    }
    if len(eligible) < minimum_eligible_rows:
        return {
            **common,
            "available": False,
            "scale_share_median_pct": None,
            "ftp_net_annualized_yield_median_pct": None,
            "rows": [],
        }

    scale_median = _median([row[2] for row in eligible])
    yield_median = _median([row[3] for row in eligible])
    rows: list[dict[str, object]] = []
    for item, avg_balance, scale_share, yield_pct in eligible:
        is_large = scale_share >= scale_median
        is_high = yield_pct >= yield_median
        quadrant_key = (
            "LARGE_HIGH"
            if is_large and is_high
            else "LARGE_LOW"
            if is_large
            else "SMALL_HIGH"
            if is_high
            else "SMALL_LOW"
        )
        rows.append(
            {
                "row_key": str(item.get("row_key") or ""),
                "business_type": str(item.get("business_type") or ""),
                "avg_balance": avg_balance,
                "scale_share_pct": _quantize_pct(scale_share),
                "ftp_net_annualized_yield_pct": yield_pct.quantize(SIXPLACES),
                "quadrant_key": quadrant_key,
            }
        )
    rows.sort(key=lambda row: (-Decimal(str(row["scale_share_pct"])), str(row["row_key"])))
    return {
        **common,
        "available": True,
        "scale_share_median_pct": _quantize_pct(scale_median),
        "ftp_net_annualized_yield_median_pct": yield_median.quantize(SIXPLACES),
        "rows": rows,
    }


__all__ = [
    "DEFAULT_NEGATIVE_FTP_MINIMUM_OBSERVED_MONTHS",
    "DEFAULT_NEGATIVE_FTP_WARNING_THRESHOLD_PCT",
    "DEFAULT_SCALE_YIELD_MINIMUM_ELIGIBLE_ROWS",
    "build_business_type_concentration",
    "build_business_type_share_drift",
    "build_negative_ftp_persistence",
    "build_scale_yield_quadrant",
]
