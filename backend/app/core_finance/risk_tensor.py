"""Portfolio risk tensor from formal bond analytics fact rows (pure calculations)."""
from __future__ import annotations

import logging
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
from backend.app.core_finance.risk_tensor_regulatory_scope import (
    DEFAULT_REGULATORY_DV01_SCOPE_RULES,
    RegulatoryDv01ScopeRule,
    row_in_regulatory_dv01_scope,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
SUPPORTED_KRD_BUCKETS = {
    "1Y": "krd_1y",
    "3Y": "krd_3y",
    "5Y": "krd_5y",
    "7Y": "krd_7y",
    "10Y": "krd_10y",
    "30Y": "krd_30y",
}

# Non-standard tenors mapped to nearest supported KRD bucket.
KRD_BUCKET_FALLBACK: dict[str, str] = {
    "6M": "krd_1y",
    "2Y": "krd_3y",
    "4Y": "krd_5y",
    "6Y": "krd_7y",
    "8Y": "krd_10y",
    "9Y": "krd_10y",
    "15Y": "krd_10y",
    "20Y": "krd_30y",
    "25Y": "krd_30y",
}


def _safe_decimal(value: object) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value if value.is_finite() else ZERO
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        logger.exception("_safe_decimal: failed to convert %r", type(value).__name__)
        return ZERO
    return result if result.is_finite() else ZERO


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ZERO if denominator == ZERO else numerator / denominator


@dataclass(slots=True, frozen=True)
class PortfolioRiskTensor:
    report_date: date
    portfolio_dv01: Decimal
    regulatory_dv01: Decimal
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
    rate_risk_market_value: Decimal = ZERO
    rate_risk_dv01: Decimal = ZERO
    rate_risk_modified_duration: Decimal = ZERO
    duration_excluded_market_value: Decimal = ZERO
    duration_excluded_count: int = 0
    missing_maturity_market_value: Decimal = ZERO
    missing_maturity_count: int = 0
    floating_rate_proxy_market_value: Decimal = ZERO
    floating_rate_proxy_count: int = 0
    payment_frequency_fallback_market_value: Decimal = ZERO
    payment_frequency_fallback_count: int = 0
    bullet_value_date_fallback_market_value: Decimal = ZERO
    bullet_value_date_fallback_count: int = 0


def compute_portfolio_risk_tensor(
    bond_analytics_rows: list[dict],
    report_date: date,
    liability_rows: list[dict] | None = None,
    regulatory_scope_rules: list[RegulatoryDv01ScopeRule] | tuple[RegulatoryDv01ScopeRule, ...] | None = None,
) -> PortfolioRiskTensor:
    rows = list(bond_analytics_rows or [])
    liabilities = list(liability_rows or [])
    warnings: list[str] = []
    scope_rules = (
        DEFAULT_REGULATORY_DV01_SCOPE_RULES
        if regulatory_scope_rules is None
        else tuple(regulatory_scope_rules)
    )

    total_market_value = _sum_field(rows, "market_value")
    portfolio_dv01 = _sum_field(rows, "dv01")
    regulatory_dv01 = _sum_field(
        [row for row in rows if row_in_regulatory_dv01_scope(row, scope_rules)],
        "dv01",
    )
    krd_values = _aggregate_krd_values(rows, warnings)
    cs01 = sum(
        (_safe_decimal(row.get("spread_dv01")) for row in rows if _is_credit(row.get("is_credit"))),
        ZERO,
    )
    _warn_duration_exclusion_inputs(rows, report_date, warnings)
    duration_rows = _duration_denominator_rows(rows, report_date)
    duration_excluded_rows = _duration_excluded_rows(rows, report_date)
    missing_maturity_rows = [row for row in rows if _coerce_date(row.get("maturity_date")) is None]
    duration_market_value = _sum_field(duration_rows, "market_value")
    rate_risk_dv01 = _sum_field(duration_rows, "dv01")
    duration_excluded_market_value = _sum_field(duration_excluded_rows, "market_value")
    portfolio_convexity = _weighted_average(duration_rows, "convexity", duration_market_value)
    portfolio_modified_duration = _weighted_average(
        duration_rows,
        "modified_duration",
        duration_market_value,
    )
    issuer_hhi, issuer_top5 = _issuer_concentration_metrics(rows, total_market_value)
    (
        liquidity_gap_30d,
        liquidity_gap_90d,
        asset_cashflow_30d,
        asset_cashflow_90d,
        liability_cashflow_30d,
        liability_cashflow_90d,
        maturity_warnings,
        projection_quality,
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
        regulatory_dv01=regulatory_dv01,
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
        rate_risk_market_value=duration_market_value,
        rate_risk_dv01=rate_risk_dv01,
        rate_risk_modified_duration=portfolio_modified_duration,
        duration_excluded_market_value=duration_excluded_market_value,
        duration_excluded_count=len(duration_excluded_rows),
        missing_maturity_market_value=_sum_field(missing_maturity_rows, "market_value"),
        missing_maturity_count=len(missing_maturity_rows),
        floating_rate_proxy_market_value=projection_quality["floating_rate_proxy_market_value"],
        floating_rate_proxy_count=int(projection_quality["floating_rate_proxy_count"]),
        payment_frequency_fallback_market_value=projection_quality["payment_frequency_fallback_market_value"],
        payment_frequency_fallback_count=int(projection_quality["payment_frequency_fallback_count"]),
        bullet_value_date_fallback_market_value=projection_quality["bullet_value_date_fallback_market_value"],
        bullet_value_date_fallback_count=int(projection_quality["bullet_value_date_fallback_count"]),
    )


def _aggregate_krd_values(
    rows: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Decimal]:
    """Aggregate per-row DV01 into the 6 standard KRD buckets.

    Non-standard tenor buckets (2Y, 15Y, 20Y, etc.) are remapped to the nearest
    supported bucket via ``KRD_BUCKET_FALLBACK``.  Truly unknown buckets with
    non-zero DV01 are excluded and reported in ``warnings``.
    """
    krd_values = {field_name: ZERO for field_name in SUPPORTED_KRD_BUCKETS.values()}
    unsupported_buckets: set[str] = set()
    remapped_buckets: set[str] = set()

    for row in rows:
        tenor_bucket = str(row.get("tenor_bucket") or "")
        dv01 = _safe_decimal(row.get("dv01"))
        field_name = SUPPORTED_KRD_BUCKETS.get(tenor_bucket)
        if field_name is None:
            # Try fallback mapping before discarding.
            field_name = KRD_BUCKET_FALLBACK.get(tenor_bucket)
            if field_name is not None:
                if dv01 != ZERO:
                    remapped_buckets.add(tenor_bucket)
            elif tenor_bucket and dv01 != ZERO:
                unsupported_buckets.add(tenor_bucket)
                continue
            else:
                continue
        krd_values[field_name] += dv01

    if remapped_buckets:
        warnings.append(
            "Non-standard tenor buckets remapped to nearest KRD bucket: "
            + ", ".join(sorted(remapped_buckets))
        )
    if unsupported_buckets:
        warnings.append(
            "Unsupported tenor buckets excluded from minimal KRD tensor: "
            + ", ".join(sorted(unsupported_buckets))
        )

    return krd_values


def _warn_duration_exclusion_inputs(
    rows: list[dict[str, Any]],
    report_date: date,
    warnings: list[str],
) -> None:
    excluded_rows = _duration_excluded_rows(rows, report_date)
    if not excluded_rows:
        return
    excluded_market_value = sum(
        (_safe_decimal(row.get("market_value")) for row in excluded_rows),
        ZERO,
    )
    no_maturity_rows = [row for row in excluded_rows if _coerce_date(row.get("maturity_date")) is None]
    matured_outstanding_rows = [
        row
        for row in excluded_rows
        if (maturity_date := _coerce_date(row.get("maturity_date"))) is not None
        and maturity_date <= report_date
    ]
    non_positive_duration_rows = [
        row
        for row in excluded_rows
        if (maturity_date := _coerce_date(row.get("maturity_date"))) is not None
        and maturity_date > report_date
        and _safe_decimal(row.get("modified_duration")) <= ZERO
    ]
    warnings.append(
        f"{len(excluded_rows)} rows carry market_value={excluded_market_value} and are "
        "excluded from portfolio duration denominator: "
        f"{len(no_maturity_rows)} without maturity_date "
        f"(market_value={_sum_field(no_maturity_rows, 'market_value')}); "
        f"{len(matured_outstanding_rows)} matured on or before report_date with outstanding "
        f"market_value (market_value={_sum_field(matured_outstanding_rows, 'market_value')}); "
        f"{len(non_positive_duration_rows)} future-dated with non-positive modified_duration "
        f"(market_value={_sum_field(non_positive_duration_rows, 'market_value')}). "
        "DV01 totals remain sourced from row dv01; duration metrics ignore these rows until inputs are remediated."
    )


def _duration_denominator_rows(
    rows: list[dict[str, Any]],
    report_date: date,
) -> list[dict[str, Any]]:
    return [row for row in rows if _is_duration_denominator_row(row, report_date)]


def _duration_excluded_rows(
    rows: list[dict[str, Any]],
    report_date: date,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _safe_decimal(row.get("market_value")) != ZERO
        and not _is_duration_denominator_row(row, report_date)
    ]


def _is_duration_denominator_row(row: dict[str, Any], report_date: date) -> bool:
    maturity_date = _coerce_date(row.get("maturity_date"))
    return (
        maturity_date is not None
        and maturity_date > report_date
        and _safe_decimal(row.get("modified_duration")) > ZERO
        and _safe_decimal(row.get("market_value")) != ZERO
    )


def _resolve_face_value(row: dict[str, Any]) -> Decimal:
    """Return face_value for coupon cashflow projection, falling back to market_value.

    When the source bond analytics fact row lacks an explicit ``face_value`` column
    (e.g. imported from legacy balance snapshots that only carry MV), market_value is
    used as an approximation.  This is acceptable for near-par bonds but may overstate
    coupon cashflows for deep-discount or premium positions.
    """
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
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, list[str], dict[str, Decimal | int]]:
    missing_maturity_dates = 0
    missing_liability_maturity_dates = 0
    unsupported_interest_modes: set[str] = set()
    optionality_warning_needed = False
    floating_rate_proxy_count = 0
    floating_rate_proxy_market_value = ZERO
    payment_frequency_fallback_count = 0
    payment_frequency_fallback_market_value = ZERO
    bullet_value_date_fallback_count = 0
    bullet_value_date_fallback_market_value = ZERO
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
        payment_frequency, raw_frequency_fallback = resolve_interest_payment_frequency(raw_interest_mode)
        explicit_frequency = row.get("interest_payment_frequency")
        fallback_provenance = row.get("interest_payment_frequency_fallback_used")
        used_frequency_fallback = (
            fallback_provenance
            if isinstance(fallback_provenance, bool)
            else raw_frequency_fallback
        )
        if raw_frequency_fallback and explicit_frequency not in (None, ""):
            payment_frequency, explicit_frequency_fallback = resolve_interest_payment_frequency(
                explicit_frequency
            )
            if not isinstance(fallback_provenance, bool):
                used_frequency_fallback = explicit_frequency_fallback
        if used_frequency_fallback:
            payment_frequency_fallback_count += 1
            payment_frequency_fallback_market_value += _safe_decimal(row.get("market_value"))
            _normalize_interest_mode(
                raw_interest_mode,
                unsupported_interest_modes=unsupported_interest_modes,
            )
        rate_style = classify_interest_rate_style(
            row.get("interest_rate_style") or raw_interest_mode
        )
        if rate_style == "floating":
            floating_rate_proxy_count += 1
            floating_rate_proxy_market_value += _safe_decimal(row.get("market_value"))
        value_date = _coerce_date(row.get("value_date"))
        if payment_frequency == "bullet" and (
            value_date is None or value_date >= maturity_date
        ):
            bullet_value_date_fallback_count += 1
            bullet_value_date_fallback_market_value += _safe_decimal(row.get("market_value"))
        if _has_optionality_inputs(row):
            optionality_warning_needed = True

        projection_rows.append(
            {
                "instrument_code": str(row.get("instrument_code") or f"risk-row-{index}"),
                "instrument_name": str(row.get("instrument_name") or row.get("issuer_name") or ""),
                "value_date": value_date,
                "maturity_date": maturity_date,
                "face_value": _resolve_face_value(row),
                "coupon_rate": _safe_decimal(row.get("coupon_rate")),
                "interest_mode": payment_frequency,
                "currency_code": str(row.get("currency_code") or "CNY"),
            }
        )

    projection_report_date = report_date - timedelta(days=1)
    projected_events = project_bond_cashflows(
        projection_rows,
        projection_report_date,
        horizon_months=4,
        # rows 来自 fact_formal_bond_analytics_daily（engine 归一后的小数口径）。
        coupon_rate_unit="decimal",
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
        # 余额为 0 是合法业务值（fact_formal_tyw_balance_daily 中约 10.9% 的行），
        # 而 ``principal_native`` 是换汇前的原币口径：用 ``or`` 会在余额为 0 时静默
        # 改用原币金额，既凭空造出敞口又混淆币种口径。只有字段缺失才回退到原币。
        # 口径与 ``core_finance/cashflow_projection.py`` 的 ``_get_value`` 一致。
        principal_amount = row.get("principal_amount")
        if principal_amount is None:
            principal_amount = row.get("principal_native")
        liability_projection_rows.append(
            {
                "position_id": str(row.get("position_id") or ""),
                "counterparty_name": str(row.get("counterparty_name") or ""),
                "position_side": str(row.get("position_side") or "liability"),
                "maturity_date": maturity_date,
                "principal_amount": _safe_decimal(principal_amount),
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
    if floating_rate_proxy_count:
        warnings.append(
            f"{floating_rate_proxy_count} floating-rate rows with market_value="
            f"{floating_rate_proxy_market_value} use the current coupon rate as a frozen proxy "
            "for the full projection horizon; reset rates are not modeled."
        )
    if payment_frequency_fallback_count:
        warnings.append(
            f"{payment_frequency_fallback_count} rows with market_value="
            f"{payment_frequency_fallback_market_value} lack an explicit payment frequency; "
            "annual coupon frequency is used as a proxy."
        )
    if bullet_value_date_fallback_count:
        warnings.append(
            f"{bullet_value_date_fallback_count} explicit bullet rows with market_value="
            f"{bullet_value_date_fallback_market_value} lack a valid value_date; "
            "a one-year interest proxy is used."
        )

    return (
        gap_30d,
        gap_90d,
        asset_cashflow_30d,
        asset_cashflow_90d,
        liability_cashflow_30d,
        liability_cashflow_90d,
        warnings,
        {
            "floating_rate_proxy_count": floating_rate_proxy_count,
            "floating_rate_proxy_market_value": floating_rate_proxy_market_value,
            "payment_frequency_fallback_count": payment_frequency_fallback_count,
            "payment_frequency_fallback_market_value": payment_frequency_fallback_market_value,
            "bullet_value_date_fallback_count": bullet_value_date_fallback_count,
            "bullet_value_date_fallback_market_value": bullet_value_date_fallback_market_value,
        },
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
