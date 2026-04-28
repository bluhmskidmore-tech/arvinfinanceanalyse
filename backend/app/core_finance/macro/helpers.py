from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, MutableMapping

from app.core_finance.safe_decimal import safe_decimal


def get_value(record: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(record, Mapping) and key in record:
            value = record[key]
        else:
            value = getattr(record, key, None)
        if value is not None:
            return value
    return default


def coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


def build_curve_history(
    curve_rows: Iterable[Any],
    *,
    report_date: date,
) -> dict[date, dict[str, dict[str, Decimal]]]:
    curves: dict[date, dict[str, dict[str, Decimal]]] = defaultdict(lambda: defaultdict(dict))
    for row in curve_rows:
        row_date = coerce_date(get_value(row, "biz_date", "report_date"))
        if row_date is None or row_date > report_date:
            continue
        curve_id = str(get_value(row, "curve_id", default="")).strip()
        tenor = str(get_value(row, "tenor", default="")).strip()
        rate_value = get_value(row, "rate_value")
        if not curve_id or not tenor or rate_value is None:
            continue
        curves[row_date][curve_id][tenor] = safe_decimal(rate_value)
    return curves


def available_dates(
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
) -> list[date]:
    return sorted(curves_by_date.keys(), reverse=True)


def get_curve_rate(
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
    target_date: date,
    curve_id: str,
    tenor: str,
) -> Decimal | None:
    return curves_by_date.get(target_date, {}).get(curve_id, {}).get(tenor)


def first_available_rate(
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
    target_date: date,
    candidates: Iterable[tuple[str, str]],
) -> tuple[str | None, str | None, Decimal | None]:
    for curve_id, tenor in candidates:
        rate = get_curve_rate(curves_by_date, target_date, curve_id, tenor)
        if rate is not None:
            return curve_id, tenor, rate
    return None, None, None


def clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def pivot_macro_eav_to_by_date(rows: Iterable[Any]) -> dict[date, dict[str, float]]:
    """将 fact_macro_indicator_daily 式 EAV 行转为按日的宽表（值为 float）。"""
    out: dict[date, dict[str, float]] = defaultdict(dict)
    for row in rows:
        d = coerce_date(get_value(row, "biz_date"))
        if d is None:
            continue
        key = str(get_value(row, "indicator_key", default="") or "").strip()
        val = get_value(row, "indicator_value")
        if not key or val is None:
            continue
        try:
            out[d][key] = float(val)
        except (TypeError, ValueError):
            continue
    return dict(out)


def sort_wide_rows_for_macro(
    wide_by_date: Mapping[date, MutableMapping[str, Any]],
    *,
    report_date: date,
) -> list[dict[str, Any]]:
    """按日期降序、且不超过 report_date 的宽表行列表（键含 biz_date / trade_date）。"""
    rows: list[dict[str, Any]] = []
    for d in sorted(wide_by_date.keys(), reverse=True):
        if d > report_date:
            continue
        inner = dict(wide_by_date[d])
        inner["biz_date"] = d
        inner["trade_date"] = d
        rows.append(inner)
    return rows


def enrich_wide_with_curve_market_fields(
    wide_by_date: dict[date, dict[str, float]],
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
) -> None:
    """
    用收益率曲线推导 V1 MarketDataDaily 风格字段（利差单位为 BP，与 M9/M16 一致）。
    原地写入 wide_by_date。
    """
    for d, target in wide_by_date.items():
        gov = curves_by_date.get(d, {}).get("CN_GOVT", {})
        y1, y5, y10 = gov.get("1Y"), gov.get("5Y"), gov.get("10Y")
        if y1 is not None and y10 is not None:
            target["term_spread_10y_1y"] = float((y10 - y1) * Decimal("100"))
        y3 = gov.get("3Y")
        aaa3 = curves_by_date.get(d, {}).get("CN_CREDIT_AAA", {}).get("3Y")
        if y3 is not None and aaa3 is not None:
            target["credit_spread_aaa_3y"] = float((aaa3 - y3) * Decimal("100"))
        aa3 = curves_by_date.get(d, {}).get("CN_CREDIT_AA", {}).get("3Y")
        aap3 = curves_by_date.get(d, {}).get("CN_CREDIT_AA_PLUS", {}).get("3Y")
        if y3 is not None and aa3 is not None:
            target["credit_spread_aa_3y"] = float((aa3 - y3) * Decimal("100"))
        if y3 is not None and aap3 is not None:
            target["credit_spread_aa_plus_3y"] = float((aap3 - y3) * Decimal("100"))
        if aaa3 is not None and aa3 is not None:
            target["aa_aaa_spread_3y"] = float((aa3 - aaa3) * Decimal("100"))
        if y10 is not None:
            target["treasury_10y"] = float(y10)
        cdb10 = curves_by_date.get(d, {}).get("CN_CDB", {}).get("10Y")
        if y10 is not None and cdb10 is not None:
            target["cdb_treasury_spread_10y"] = float((cdb10 - y10) * Decimal("100"))
        cdb5 = curves_by_date.get(d, {}).get("CN_CDB", {}).get("5Y")
        if y5 is not None and cdb5 is not None:
            target["cdb_treasury_spread_5y"] = float((cdb5 - y5) * Decimal("100"))
        us10 = curves_by_date.get(d, {}).get("US_GOVT", {}).get("10Y")
        if us10 is not None:
            target["us_treasury_10y"] = float(us10)
        if y10 is not None and us10 is not None:
            target["china_us_spread_10y"] = float((y10 - us10) * Decimal("100"))


# ---------------------------------------------------------------------------
# 通用小工具（消除各模块散落的 _d / _f / _pearson 重复）
# ---------------------------------------------------------------------------

def to_decimal_safe(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def to_rounded_float(d: Decimal) -> float:
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def to_float_safe(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pearson_corr(x: list[float], y: list[float], min_samples: int = 5) -> float | None:
    if len(x) != len(y) or len(x) < min_samples:
        return None
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_xx = sum(xi * xi for xi in x)
    sum_yy = sum(yi * yi for yi in y)
    num = n * sum_xy - sum_x * sum_y
    den = (n * sum_xx - sum_x * sum_x) * (n * sum_yy - sum_y * sum_y)
    if den <= 0:
        return None
    r = num / math.sqrt(den)
    return max(-1.0, min(1.0, r))
