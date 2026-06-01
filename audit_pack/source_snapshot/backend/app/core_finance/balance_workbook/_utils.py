"""Shared utilities for balance analysis workbook builders."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.interest_mode import classify_interest_rate_style

_ZERO = Decimal("0")
_TEN_THOUSAND = Decimal("10000")

_MATURITY_BUCKETS = (
    ("已到期/逾期", None, Decimal("0")),
    ("3个月以内", Decimal("0"), Decimal("0.25")),
    ("3-6个月", Decimal("0.25"), Decimal("0.5")),
    ("6-12个月", Decimal("0.5"), Decimal("1")),
    ("1-2年", Decimal("1"), Decimal("2")),
    ("2-3年", Decimal("2"), Decimal("3")),
    ("3-5年", Decimal("3"), Decimal("5")),
    ("5-10年", Decimal("5"), Decimal("10")),
    ("10年以上", Decimal("10"), None),
)
_RATE_BUCKETS = (
    ("零息/无息", None, Decimal("0")),
    ("1.5%以下", Decimal("0"), Decimal("1.5")),
    ("1.5%-2.0%", Decimal("1.5"), Decimal("2.0")),
    ("2.0%-2.5%", Decimal("2.0"), Decimal("2.5")),
    ("2.5%-3.0%", Decimal("2.5"), Decimal("3.0")),
    ("3.0%-3.5%", Decimal("3.0"), Decimal("3.5")),
    ("3.5%-4.0%", Decimal("3.5"), Decimal("4.0")),
    ("4.0%以上", Decimal("4.0"), None),
)
_LIQUIDITY_LAYER_ORDER = ("Level 1", "Level 2A", "Level 2B", "其他")
_LIQUIDITY_LEVEL1_BOND_TYPES = frozenset({"国债", "政策性金融债", "凭证式国债"})
_LIQUIDITY_HQLA_HAIRCUTS = {
    "Level 1": Decimal("1.00"),
    "Level 2A": Decimal("0.85"),
    "Level 2B": Decimal("0.75"),
    "其他": Decimal("0"),
}
_LIQUIDITY_HIGH_RATING = frozenset({"AAA", "AA+"})
_CAMPISI_POLICY_BOND = "政策性金融债"


def _group_rows(rows: list[Any], key_fn) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(str(key_fn(row) or "未分类"), []).append(row)
    return grouped


def _sum_decimal(rows: list[Any], value_fn) -> Decimal:
    return sum((Decimal(str(value_fn(row))) for row in rows), _ZERO)


def _weighted_average(rows: list[Any], weight_fn, value_fn) -> Decimal | None:
    numerator = _ZERO
    denominator = _ZERO
    for row in rows:
        value = value_fn(row)
        if value in (None, ""):
            continue
        weight = Decimal(str(weight_fn(row)))
        numerator += weight * Decimal(str(value))
        denominator += weight
    if denominator == _ZERO:
        return None
    return numerator / denominator


def _merged_weighted_average(specs: list[tuple[list[Any], Any, Any]]) -> Decimal | None:
    numerator = _ZERO
    denominator = _ZERO
    for rows, weight_fn, value_fn in specs:
        for row in rows:
            value = value_fn(row)
            if value in (None, ""):
                continue
            weight = Decimal(str(weight_fn(row)))
            numerator += weight * Decimal(str(value))
            denominator += weight
    if denominator == _ZERO:
        return None
    return numerator / denominator


def _remaining_years(report_date: date, maturity_date: date | None) -> Decimal:
    if maturity_date is None:
        return _ZERO
    return Decimal((maturity_date - report_date).days) / Decimal("365")


def _optional_remaining_years(report_date: date, maturity_date: date | None) -> Decimal | None:
    # Workbook 加权期限: calendar days / 365.25 (verified vs 2026-03-01 desktop reference).
    if maturity_date is None:
        return None
    if maturity_date < report_date:
        return None
    days = (maturity_date - report_date).days
    if days <= 0:
        return None
    return Decimal(days) / Decimal("365.25")


def _match_bucket(value: Decimal, lower: Decimal | None, upper: Decimal | None) -> bool:
    if lower is None:
        return value <= (upper or _ZERO)
    if upper is None:
        return value > lower
    return value > lower and value <= upper


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == _ZERO:
        return _ZERO
    return numerator / denominator


def _spread_bp(asset_rate_pct: Decimal | None, liability_rate_pct: Decimal | None) -> Decimal | None:
    if asset_rate_pct is None or liability_rate_pct is None:
        return None
    return (asset_rate_pct - liability_rate_pct) * Decimal("100")


def _rate_value(value: Decimal | None) -> Decimal:
    return Decimal(str(value)) if value is not None else _ZERO


def _normalize_interest_mode(value: str) -> str:
    style = classify_interest_rate_style(value)
    if style == "fixed":
        return "固定"
    if style == "floating":
        return "浮动"
    return "未分类"


def _to_wanyuan(value: Decimal) -> Decimal:
    return value / _TEN_THOUSAND


def _decimal_value(value: Any) -> Decimal:
    if value in (None, ""):
        return _ZERO
    return Decimal(str(value))


def _severity_from_gap(gap_value: Decimal) -> str:
    absolute_gap = abs(gap_value)
    if absolute_gap >= Decimal("20"):
        return "high"
    if absolute_gap >= Decimal("5"):
        return "medium"
    return "low"


def _month_ladder(report_date: date, months: int) -> list[str]:
    start_month_index = report_date.year * 12 + (report_date.month - 1)
    return [_month_key_from_index(start_month_index + offset) for offset in range(months)]


def _month_key(value: date | None) -> str:
    if value is None:
        return ""
    return f"{value.year:04d}-{value.month:02d}"


def _month_key_from_index(month_index: int) -> str:
    year = month_index // 12
    month = (month_index % 12) + 1
    return f"{year:04d}-{month:02d}"


def _card(key: str, label: str, value: Decimal, note: str) -> dict[str, Any]:
    return {"key": key, "label": label, "value": value, "note": note}


def _section(
    key: str,
    title: str,
    section_kind: str,
    columns: list[tuple[str, str]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "section_kind": section_kind,
        "columns": [{"key": column_key, "label": label} for column_key, label in columns],
        "rows": rows,
    }


def _table(key: str, title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _section(key, title, "table", columns, rows)
