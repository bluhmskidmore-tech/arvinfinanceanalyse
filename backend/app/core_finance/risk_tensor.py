"""Portfolio risk tensor from formal bond analytics fact rows (pure calculations)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

ZERO = Decimal("0")
SUPPORTED_KRD_BUCKETS = {
    "1Y": "krd_1y",
    "3Y": "krd_3y",
    "5Y": "krd_5y",
    "7Y": "krd_7y",
    "10Y": "krd_10y",
    "30Y": "krd_30y",
}


def _safe_decimal(value: object) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return ZERO


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ZERO if denominator == ZERO else numerator / denominator


@dataclass(slots=True, frozen=True)
class PortfolioRiskTensor:
    report_date: date
    portfolio_dv01: Decimal
    krd_1y: Decimal
    krd_3y: Decimal
    krd_5y: Decimal
    krd_7y: Decimal
    krd_10y: Decimal
    krd_30y: Decimal
    cs01: Decimal
    portfolio_convexity: Decimal
    portfolio_modified_duration: Decimal
    issuer_concentration_hhi: Decimal
    issuer_top5_weight: Decimal
    liquidity_gap_30d: Decimal
    liquidity_gap_90d: Decimal
    liquidity_gap_30d_ratio: Decimal
    total_market_value: Decimal
    bond_count: int
    quality_flag: str
    warnings: list[str]


def compute_portfolio_risk_tensor(
    bond_analytics_rows: list[dict],
    report_date: date,
) -> PortfolioRiskTensor:
    rows = list(bond_analytics_rows or [])
    warnings: list[str] = []

    total_market_value = _sum_field(rows, "market_value")
    portfolio_dv01 = _sum_field(rows, "dv01")
    krd_values = _aggregate_krd_values(rows, warnings)
    cs01 = sum(
        (_safe_decimal(row.get("spread_dv01")) for row in rows if _is_credit(row.get("is_credit"))),
        ZERO,
    )
    portfolio_convexity = _weighted_average(rows, "convexity", total_market_value)
    portfolio_modified_duration = _weighted_average(rows, "modified_duration", total_market_value)
    issuer_hhi, issuer_top5 = _issuer_concentration_metrics(rows, total_market_value)
    liquidity_gap_30d, liquidity_gap_90d, maturity_warnings = _compute_liquidity_gaps(rows, report_date)
    warnings.extend(maturity_warnings)
    liquidity_gap_30d_ratio = _ratio(liquidity_gap_30d, total_market_value)

    if not rows:
        warnings.append("No bond analytics rows available for risk tensor.")
    elif total_market_value == ZERO:
        warnings.append("Total market value is zero; weighted metrics default to 0.")

    quality_flag = "warning" if warnings else "ok"
    return PortfolioRiskTensor(
        report_date=report_date,
        portfolio_dv01=portfolio_dv01,
        krd_1y=krd_values["krd_1y"],
        krd_3y=krd_values["krd_3y"],
        krd_5y=krd_values["krd_5y"],
        krd_7y=krd_values["krd_7y"],
        krd_10y=krd_values["krd_10y"],
        krd_30y=krd_values["krd_30y"],
        cs01=cs01,
        portfolio_convexity=portfolio_convexity,
        portfolio_modified_duration=portfolio_modified_duration,
        issuer_concentration_hhi=issuer_hhi,
        issuer_top5_weight=issuer_top5,
        liquidity_gap_30d=liquidity_gap_30d,
        liquidity_gap_90d=liquidity_gap_90d,
        liquidity_gap_30d_ratio=liquidity_gap_30d_ratio,
        total_market_value=total_market_value,
        bond_count=len(rows),
        quality_flag=quality_flag,
        warnings=warnings,
    )


def _aggregate_krd_values(
    rows: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Decimal]:
    krd_values = {field_name: ZERO for field_name in SUPPORTED_KRD_BUCKETS.values()}
    unsupported_buckets: set[str] = set()

    for row in rows:
        tenor_bucket = str(row.get("tenor_bucket") or "")
        dv01 = _safe_decimal(row.get("dv01"))
        field_name = SUPPORTED_KRD_BUCKETS.get(tenor_bucket)
        if field_name is None:
            if tenor_bucket and dv01 != ZERO:
                unsupported_buckets.add(tenor_bucket)
            continue
        krd_values[field_name] += dv01

    if unsupported_buckets:
        warnings.append(
            "Unsupported tenor buckets excluded from minimal KRD tensor: "
            + ", ".join(sorted(unsupported_buckets))
        )

    return krd_values


def _issuer_concentration_metrics(
    rows: list[dict[str, Any]],
    total_market_value: Decimal,
) -> tuple[Decimal, Decimal]:
    if total_market_value == ZERO or not rows:
        return ZERO, ZERO
    grouped: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        key = str(row.get("issuer_name") or "unknown")
        grouped[key] += _safe_decimal(row.get("market_value"))
    ranked = sorted(grouped.items(), key=lambda item: (-item[1], item[0]))
    hhi = sum((_ratio(value, total_market_value) ** 2 for _name, value in ranked), ZERO)
    top5 = sum((_ratio(value, total_market_value) for _name, value in ranked[:5]), ZERO)
    return hhi, top5


def _compute_liquidity_gaps(
    rows: list[dict[str, Any]],
    report_date: date,
) -> tuple[Decimal, Decimal, list[str]]:
    gap_30d = ZERO
    gap_90d = ZERO
    missing_maturity_dates = 0

    for row in rows:
        maturity_date = _coerce_date(row.get("maturity_date"))
        if maturity_date is None:
            missing_maturity_dates += 1
            continue

        days_to_maturity = (maturity_date - report_date).days
        if days_to_maturity < 0:
            continue

        market_value = _safe_decimal(row.get("market_value"))
        if days_to_maturity <= 30:
            gap_30d += market_value
        if days_to_maturity <= 90:
            gap_90d += market_value

    warnings: list[str] = []
    if missing_maturity_dates:
        warnings.append(
            f"Excluded {missing_maturity_dates} rows without maturity_date from liquidity gap calculation."
        )

    return gap_30d, gap_90d, warnings


def _weighted_average(
    rows: list[dict[str, Any]],
    field_name: str,
    total_market_value: Decimal,
) -> Decimal:
    if total_market_value == ZERO:
        return ZERO
    numerator = sum(
        (_safe_decimal(row.get(field_name)) * _safe_decimal(row.get("market_value")) for row in rows),
        ZERO,
    )
    return numerator / total_market_value


def _sum_field(rows: list[dict[str, Any]], field_name: str) -> Decimal:
    return sum((_safe_decimal(row.get(field_name)) for row in rows), ZERO)


def _is_credit(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _coerce_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
