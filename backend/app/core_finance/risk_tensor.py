"""Portfolio risk tensor from formal bond analytics fact rows (pure calculations)."""
from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from backend.app.core_finance.cashflow_projection import (
    project_bond_cashflows,
    project_liability_cashflows,
)
from backend.app.core_finance.interest_mode import (
    classify_interest_rate_style,
    resolve_interest_payment_frequency,
)

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
    asset_cashflow_30d: Decimal
    asset_cashflow_90d: Decimal
    liability_cashflow_30d: Decimal
    liability_cashflow_90d: Decimal
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
    liability_rows: list[dict] | None = None,
) -> PortfolioRiskTensor:
    rows = list(bond_analytics_rows or [])
    liabilities = list(liability_rows or [])
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
    (
        liquidity_gap_30d,
        liquidity_gap_90d,
        asset_cashflow_30d,
        asset_cashflow_90d,
        liability_cashflow_30d,
        liability_cashflow_90d,
        maturity_warnings,
    ) = _compute_liquidity_gaps(
        rows,
        report_date,
        liabilities,
    )
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
        asset_cashflow_30d=asset_cashflow_30d,
        asset_cashflow_90d=asset_cashflow_90d,
        liability_cashflow_30d=liability_cashflow_30d,
        liability_cashflow_90d=liability_cashflow_90d,
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


def _resolve_face_value(row: dict[str, Any]) -> Decimal:
    if row.get("face_value") is not None:
        return _safe_decimal(row.get("face_value"))
    return _safe_decimal(row.get("market_value"))


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
    hhi = _calc_hhi_for_group(grouped.values(), total_market_value)
    top5 = sum((_ratio(value, total_market_value) for _name, value in ranked[:5]), ZERO)
    return hhi, top5


def _calc_hhi_for_group(values: Any, total_market_value: Decimal) -> Decimal:
    if total_market_value == ZERO:
        return ZERO
    return sum((_ratio(_safe_decimal(value), total_market_value) ** 2 for value in values), ZERO)


def _compute_liquidity_gaps(
    rows: list[dict[str, Any]],
    report_date: date,
    liability_rows: list[dict[str, Any]] | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, list[str]]:
    missing_maturity_dates = 0
    missing_liability_maturity_dates = 0
    unsupported_interest_modes: set[str] = set()
    optionality_warning_needed = False
    projection_rows: list[dict[str, Any]] = []
    liability_projection_rows: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        maturity_date = _coerce_date(row.get("maturity_date"))
        if maturity_date is None:
            missing_maturity_dates += 1
            continue
        if maturity_date < report_date:
            continue

        raw_interest_mode = row.get("interest_mode")
        _normalize_interest_mode(
            row.get("interest_mode"),
            unsupported_interest_modes=unsupported_interest_modes,
        )
        if _has_optionality_inputs(row):
            optionality_warning_needed = True

        projection_rows.append(
            {
                "instrument_code": str(row.get("instrument_code") or f"risk-row-{index}"),
                "instrument_name": str(row.get("instrument_name") or row.get("issuer_name") or ""),
                "maturity_date": maturity_date,
                "face_value": _resolve_face_value(row),
                "coupon_rate": _safe_decimal(row.get("coupon_rate")),
                "interest_mode": raw_interest_mode,
                "currency_code": str(row.get("currency_code") or "CNY"),
            }
        )

    projection_report_date = report_date - timedelta(days=1)
    projected_events = project_bond_cashflows(
        projection_rows,
        projection_report_date,
        horizon_months=4,
    )
    asset_gap_30d = _sum_window_cashflows(
        projected_events,
        start_date=report_date,
        end_date=report_date + timedelta(days=30),
    )
    asset_gap_90d = _sum_window_cashflows(
        projected_events,
        start_date=report_date,
        end_date=report_date + timedelta(days=90),
    )
    for row in liability_rows or []:
        maturity_date = _coerce_date(row.get("maturity_date"))
        if maturity_date is None:
            missing_liability_maturity_dates += 1
            continue
        if maturity_date < report_date:
            continue
        liability_projection_rows.append(
            {
                "position_id": str(row.get("position_id") or ""),
                "counterparty_name": str(row.get("counterparty_name") or ""),
                "position_side": str(row.get("position_side") or "liability"),
                "maturity_date": maturity_date,
                "principal_amount": _safe_decimal(row.get("principal_amount") or row.get("principal_native")),
                "funding_cost_rate": _safe_decimal(row.get("funding_cost_rate")),
                "currency_code": str(row.get("currency_code") or "CNY"),
            }
        )

    projected_liability_events = project_liability_cashflows(
        liability_projection_rows,
        projection_report_date,
        horizon_months=4,
    )
    liability_gap_30d = _sum_window_cashflows(
        projected_liability_events,
        start_date=report_date,
        end_date=report_date + timedelta(days=30),
    )
    liability_gap_90d = _sum_window_cashflows(
        projected_liability_events,
        start_date=report_date,
        end_date=report_date + timedelta(days=90),
    )
    gap_30d = asset_gap_30d + liability_gap_30d
    gap_90d = asset_gap_90d + liability_gap_90d
    asset_cashflow_30d = max(ZERO, asset_gap_30d)
    asset_cashflow_90d = max(ZERO, asset_gap_90d)
    liability_cashflow_30d = max(ZERO, -liability_gap_30d)
    liability_cashflow_90d = max(ZERO, -liability_gap_90d)

    warnings: list[str] = []
    if missing_maturity_dates:
        warnings.append(
            f"Excluded {missing_maturity_dates} rows without maturity_date from liquidity gap calculation."
        )
    if missing_liability_maturity_dates:
        warnings.append(
            f"Excluded {missing_liability_maturity_dates} liability rows without maturity_date from liquidity gap calculation."
        )
    if unsupported_interest_modes:
        warnings.append(
            "Unsupported interest_mode defaulted to annual coupon frequency for liquidity gaps: "
            + ", ".join(sorted(unsupported_interest_modes))
        )
    if optionality_warning_needed:
        warnings.append(
            "Embedded optionality is excluded from liquidity gaps; put/call/prepayment cash flows are not modeled."
        )

    return (
        gap_30d,
        gap_90d,
        asset_cashflow_30d,
        asset_cashflow_90d,
        liability_cashflow_30d,
        liability_cashflow_90d,
        warnings,
    )


def _sum_window_cashflows(
    events: list[Any],
    *,
    start_date: date,
    end_date: date,
) -> Decimal:
    return sum(
        (
            _safe_decimal(event.amount)
            for event in events
            if start_date <= event.event_date <= end_date
        ),
        ZERO,
    )


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


def _estimate_coupon_cashflows(
    *,
    report_date: date,
    maturity_date: date,
    face_value: Decimal,
    coupon_rate: Decimal,
    interest_mode: str,
) -> tuple[Decimal, Decimal]:
    if coupon_rate == ZERO or face_value == ZERO:
        return ZERO, ZERO

    if interest_mode == "bullet":
        coupon_amount = face_value * coupon_rate
        coupon_30d = coupon_amount if _is_within_window(report_date, maturity_date, window_days=30) else ZERO
        coupon_90d = coupon_amount if _is_within_window(report_date, maturity_date, window_days=90) else ZERO
        return coupon_30d, coupon_90d

    coupon_frequency = {
        "annual": Decimal("1"),
        "semi-annual": Decimal("2"),
        "quarterly": Decimal("4"),
    }.get(interest_mode, Decimal("1"))
    next_coupon_date = _find_next_coupon_date(
        report_date=report_date,
        maturity_date=maturity_date,
        interval_months=int(Decimal("12") / coupon_frequency),
    )
    if next_coupon_date is None:
        return ZERO, ZERO

    coupon_amount = face_value * coupon_rate / coupon_frequency
    coupon_30d = coupon_amount if _is_within_window(report_date, next_coupon_date, window_days=30) else ZERO
    coupon_90d = coupon_amount if _is_within_window(report_date, next_coupon_date, window_days=90) else ZERO
    return coupon_30d, coupon_90d


def _find_next_coupon_date(
    *,
    report_date: date,
    maturity_date: date,
    interval_months: int,
) -> date | None:
    if interval_months <= 0 or maturity_date < report_date:
        return None

    periods_back = 0
    next_coupon_date: date | None = None
    while True:
        candidate = _shift_months(maturity_date, -(periods_back * interval_months))
        if candidate < report_date:
            return next_coupon_date
        next_coupon_date = candidate
        periods_back += 1


def _shift_months(value: date, months: int) -> date:
    month_index = (value.year * 12 + (value.month - 1)) + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _is_within_window(report_date: date, cashflow_date: date, *, window_days: int) -> bool:
    days = (cashflow_date - report_date).days
    return 0 <= days <= window_days


def _normalize_interest_mode(
    value: object,
    *,
    unsupported_interest_modes: set[str],
) -> str:
    raw = str(value or "").strip()
    frequency, used_fallback = resolve_interest_payment_frequency(value)
    if used_fallback and raw and classify_interest_rate_style(raw) == "unknown":
        unsupported_interest_modes.add(raw)
    return frequency


def _has_optionality_inputs(row: dict[str, Any]) -> bool:
    for field_name in ("next_call_date", "put_date", "put_option_date", "prepayment_date"):
        if row.get(field_name):
            return True
    for field_name in ("has_put_option", "has_call_option", "has_prepayment_option"):
        value = row.get(field_name)
        if isinstance(value, bool) and value:
            return True
        if str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}:
            return True
    return False


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
