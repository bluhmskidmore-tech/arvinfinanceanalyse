"""
M16: 信用利差历史分位（纯函数，自 V1 macro_analysis.credit_spread_percentile 迁入）。

由 fact_market_curve_daily 推导各利差序列（单位 BP，与 M9 一致）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from app.core_finance.macro.helpers import build_curve_history

_M16_LOOKBACK_DAYS_3Y = 756
_M16_LOOKBACK_DAYS_1Y = 252


def _spread_snapshot_for_date(
    curves_by_date: dict[date, dict[str, dict[str, Decimal]]],
    d: date,
) -> dict[str, float | None]:
    gov = curves_by_date.get(d, {}).get("CN_GOVT", {})
    aaa = curves_by_date.get(d, {}).get("CN_CREDIT_AAA", {})
    aa = curves_by_date.get(d, {}).get("CN_CREDIT_AA", {})
    aap = curves_by_date.get(d, {}).get("CN_CREDIT_AA_PLUS", {})
    cdb = curves_by_date.get(d, {}).get("CN_CDB", {})
    us = curves_by_date.get(d, {}).get("US_GOVT", {})

    def bp_spread(a: Decimal | None, b: Decimal | None) -> float | None:
        if a is None or b is None:
            return None
        return float((a - b) * Decimal("100"))

    y1, y5, y10 = gov.get("1Y"), gov.get("5Y"), gov.get("10Y")
    y3 = gov.get("3Y")
    out: dict[str, float | None] = {
        "credit_spread_aaa_3y": bp_spread(aaa.get("3Y"), y3),
        "credit_spread_aa_plus_3y": bp_spread(aap.get("3Y"), y3),
        "credit_spread_aa_3y": bp_spread(aa.get("3Y"), y3),
        "aa_aaa_spread_3y": bp_spread(aa.get("3Y"), aaa.get("3Y")),
        "cdb_treasury_spread_10y": bp_spread(cdb.get("10Y"), y10),
        "china_us_spread_10y": bp_spread(y10, us.get("10Y")),
        "term_spread_10y_1y": bp_spread(y10, y1),
        "cdb_treasury_spread_5y": bp_spread(cdb.get("5Y"), y5),
    }
    return out


def _calc_percentile(current: float, history: list[float]) -> float | None:
    if not history:
        return None
    below = sum(1 for h in history if h < current)
    return round(below / len(history) * 100, 1)


def _calc_stats(series: list[float]) -> dict[str, float | None]:
    if not series:
        return {"min": None, "max": None, "median": None, "mean": None}
    s = sorted(series)
    n = len(s)
    return {
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
        "median": round(s[n // 2], 2),
        "mean": round(sum(s) / n, 2),
    }


_SPREAD_DEFS: tuple[dict[str, str], ...] = (
    {"key": "credit_spread_aaa_3y", "name": "AAA 3Y 信用利差", "field": "credit_spread_aaa_3y"},
    {"key": "credit_spread_aa_plus_3y", "name": "AA+ 3Y 信用利差", "field": "credit_spread_aa_plus_3y"},
    {"key": "credit_spread_aa_3y", "name": "AA 3Y 信用利差", "field": "credit_spread_aa_3y"},
    {"key": "aa_aaa_spread_3y", "name": "AA-AAA 等级利差", "field": "aa_aaa_spread_3y"},
    {"key": "cdb_treasury_spread_10y", "name": "国开-国债 10Y 利差", "field": "cdb_treasury_spread_10y"},
    {"key": "china_us_spread_10y", "name": "中美利差 10Y", "field": "china_us_spread_10y"},
    {"key": "term_spread_10y_1y", "name": "期限利差 10Y-1Y", "field": "term_spread_10y_1y"},
    {"key": "cdb_treasury_spread_5y", "name": "国开-国债利差 5Y", "field": "cdb_treasury_spread_5y"},
)


def compute_credit_spread_percentile(
    curve_rows: Iterable[Any],
    report_date: date,
) -> dict[str, Any]:
    curves = build_curve_history(curve_rows, report_date=report_date)
    dates_sorted = sorted(curves.keys(), reverse=True)
    if not dates_sorted:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "spreads": [],
            "assessment": "无历史数据",
            "overall_valuation": "未知",
            "warnings": ["NO_CURVE_HISTORY"],
        }

    dates_used = dates_sorted[: _M16_LOOKBACK_DAYS_3Y + 1]
    history_wide = [_spread_snapshot_for_date(curves, d) for d in dates_used]

    try:
        cutoff_1y = date(report_date.year - 1, report_date.month, report_date.day)
    except ValueError:
        cutoff_1y = date(report_date.year - 1, report_date.month, 28)

    today_snap = history_wide[0] if history_wide else {}
    rows_1y_snaps = [
        h for h, d in zip(history_wide, dates_used) if d >= cutoff_1y
    ][: _M16_LOOKBACK_DAYS_1Y]

    spreads_out: list[dict[str, Any]] = []
    cheap_count = 0
    expensive_count = 0

    for sd in _SPREAD_DEFS:
        field = sd["field"]
        cur = today_snap.get(field)
        if cur is None:
            continue

        hist_3y = [h[field] for h in history_wide if h.get(field) is not None]
        hist_1y = [h[field] for h in rows_1y_snaps if h.get(field) is not None]

        pct_3y = _calc_percentile(float(cur), hist_3y)
        pct_1y = _calc_percentile(float(cur), hist_1y)

        if pct_3y is not None and pct_3y <= 25:
            valuation = "偏便宜"
            cheap_count += 1
        elif pct_3y is not None and pct_3y >= 75:
            valuation = "偏贵"
            expensive_count += 1
        else:
            valuation = "中性"

        spreads_out.append(
            {
                "key": sd["key"],
                "name": sd["name"],
                "current_bp": round(float(cur), 2),
                "percentile_3y": pct_3y,
                "percentile_1y": pct_1y,
                "stats_3y": _calc_stats(hist_3y),
                "stats_1y": _calc_stats(hist_1y),
                "valuation": valuation,
            }
        )

    if expensive_count >= 3:
        assessment = "多数利差处于历史高位（偏贵），信用债配置价值较低，建议等待利差收窄"
        overall_valuation = "偏贵"
    elif cheap_count >= 3:
        assessment = "多数利差处于历史低位（偏便宜），信用债具备配置价值，可逐步加仓"
        overall_valuation = "偏便宜"
    elif cheap_count > expensive_count:
        assessment = "利差整体偏低，信用债有一定配置吸引力"
        overall_valuation = "偏便宜"
    elif expensive_count > cheap_count:
        assessment = "利差整体偏高，信用债估值不具吸引力"
        overall_valuation = "偏贵"
    else:
        assessment = "利差处于历史中位，中性配置"
        overall_valuation = "中性"

    warnings: list[str] = []
    if len(dates_sorted) < 60:
        warnings.append("MARKET_HISTORY_LT_60D")
    data_status = "degraded" if warnings else "complete"
    if not spreads_out:
        data_status = "unavailable"

    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "spreads": spreads_out,
        "assessment": assessment,
        "overall_valuation": overall_valuation,
        "summary": {
            "cheap_count": cheap_count,
            "expensive_count": expensive_count,
            "total_analyzed": len(spreads_out),
        },
        "warnings": warnings,
    }
