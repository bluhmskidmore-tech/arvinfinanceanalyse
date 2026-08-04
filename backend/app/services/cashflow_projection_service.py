from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.app.core_finance.bond_duration import estimate_duration
from backend.app.core_finance.cashflow_projection import MonthlyBucket, compute_duration_gap
from backend.app.core_finance.interest_mode import (
    classify_interest_rate_style,
    coupon_frequency_per_year,
    resolve_interest_payment_frequency,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.cashflow_projection_repo import CashflowProjectionRepository
from backend.app.schemas.cashflow_projection import CashflowProjectionResponse
from backend.app.schemas.common_numeric import numeric_from_raw
from backend.app.services.explicit_numeric import numeric_json
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)

Q8 = Decimal("0.00000000")
CACHE_VERSION = "cv_cashflow_projection_read_v1"
RULE_VERSION = "rv_cashflow_projection_read_v1"
EMPTY_SOURCE_VERSION = "sv_cashflow_projection_empty"
DATE_BASIS = "cashflow_projection_report_date"
ZQTZ_FORMAL_TABLE = "fact_formal_zqtz_balance_daily"
TYW_FORMAL_TABLE = "fact_formal_tyw_balance_daily"
TYWL_DEMAND_PRODUCTS = frozenset({"同业存放", "存放同业"})


def get_cashflow_projection(report_date: date) -> dict[str, object]:
    settings = get_settings()
    report_date_text = report_date.isoformat()

    cashflow_repo = CashflowProjectionRepository(str(settings.duckdb_path))
    analytics_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    zqtz_rows = cashflow_repo.fetch_formal_zqtz_rows(
        report_date=report_date_text,
        position_scope="all",
        currency_basis="CNY",
    )
    tyw_rows = cashflow_repo.fetch_formal_tyw_liability_rows(
        report_date=report_date_text,
        currency_basis="CNY",
    )
    analytics_rows = analytics_repo.fetch_bond_analytics_rows(report_date=report_date_text)
    zqtz_rows = _attach_macaulay_duration(zqtz_rows, analytics_rows)
    quality_disclosures = _cashflow_projection_quality_disclosures(zqtz_rows)
    projection_zqtz_rows = _with_effective_payment_frequency(zqtz_rows)

    if not zqtz_rows and not tyw_rows:
        raise ValueError(f"No cashflow projection data found for report_date={report_date_text}.")

    result = compute_duration_gap(
        zqtz_rows=projection_zqtz_rows,
        tyw_rows=tyw_rows,
        report_date=report_date,
        horizon_months=24,
    )

    meta = build_analytical_result_meta(
        trace_id=_trace_id(),
        result_kind="cashflow_projection.overview",
        cache_version=CACHE_VERSION,
        source_version=_merge_versions(
            [*_collect_values(zqtz_rows, "source_version"), *_collect_values(tyw_rows, "source_version")],
            empty_value=EMPTY_SOURCE_VERSION,
        ),
        rule_version=_merge_versions(
            [*_collect_values(zqtz_rows, "rule_version"), *_collect_values(tyw_rows, "rule_version")],
            empty_value=RULE_VERSION,
        ),
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis=DATE_BASIS,
        filters_applied={
            "report_date": report_date_text,
            "position_scope": "all",
            "currency_basis": "CNY",
        },
        tables_used=[ZQTZ_FORMAL_TABLE, TYW_FORMAL_TABLE],
        evidence_rows=len(zqtz_rows) + len(tyw_rows),
        source_surface="cashflow",
    )

    response = CashflowProjectionResponse(
        report_date=report_date,
        duration_gap=numeric_json(result.duration_gap, "years", True),
        asset_duration=numeric_json(result.asset_weighted_duration, "years", False),
        liability_duration=numeric_json(result.liability_weighted_duration, "years", False),
        equity_duration=numeric_json(result.equity_duration, "years", True),
        rate_sensitivity_1bp=numeric_json(result.rate_sensitivity_1bp, "yuan", True),
        reinvestment_risk_12m=_ratio_pct_numeric_json(result.reinvestment_risk_12m),
        monthly_buckets=[_serialize_monthly_bucket(bucket) for bucket in result.monthly_buckets],
        top_maturing_assets_12m=_build_top_maturing_assets_12m(zqtz_rows, tyw_rows, report_date),
        floating_rate_proxy_count=int(quality_disclosures["floating_rate_proxy_count"]),
        floating_rate_proxy_market_value=numeric_json(
            Decimal(quality_disclosures["floating_rate_proxy_market_value"]), "yuan", False
        ),
        payment_frequency_fallback_count=int(quality_disclosures["payment_frequency_fallback_count"]),
        payment_frequency_fallback_market_value=numeric_json(
            Decimal(quality_disclosures["payment_frequency_fallback_market_value"]), "yuan", False
        ),
        bullet_value_date_fallback_count=int(quality_disclosures["bullet_value_date_fallback_count"]),
        bullet_value_date_fallback_market_value=numeric_json(
            Decimal(quality_disclosures["bullet_value_date_fallback_market_value"]), "yuan", False
        ),
        warnings=[*result.warnings, *quality_disclosures["warnings"]],
        computed_at=meta.generated_at.isoformat(),
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=response.model_dump(mode="json"),
    )


def _ratio_pct_numeric_json(raw: Decimal | None) -> dict[str, object]:
    """Build a pct Numeric JSON from a verified decimal-ratio input.

    ``reinvestment_risk_12m`` is maturing face value / total asset market value
    (see ``core_finance.cashflow_projection``) — a decimal ratio that can
    legitimately reach or exceed 1, so it must bypass the legacy "auto" rescale
    heuristic via ``raw_scale="ratio"``.
    """
    value = None if raw is None else float(raw)
    return numeric_from_raw(
        raw=value,
        unit="pct",
        sign_aware=False,
        raw_scale="ratio",
    ).model_dump(mode="json")


def _serialize_monthly_bucket(bucket: MonthlyBucket) -> dict[str, object]:
    return {
        "year_month": bucket.year_month,
        "asset_inflow": numeric_json(bucket.asset_inflow, "yuan", False),
        "liability_outflow": numeric_json(bucket.liability_outflow, "yuan", False),
        "net_cashflow": numeric_json(bucket.net_cashflow, "yuan", True),
        "cumulative_net": numeric_json(bucket.cumulative_net, "yuan", True),
    }


def _build_top_maturing_assets_12m(
    zqtz_rows: list[dict[str, object]],
    tyw_rows: list[dict[str, object]],
    report_date: date,
) -> list[dict[str, object]]:
    horizon_end = date(report_date.year + 1, report_date.month, report_date.day)
    candidates: list[dict[str, object]] = []

    for row in zqtz_rows:
        if _row_scope(row) != "asset":
            continue
        maturity_date = _coerce_date(row.get("maturity_date"))
        if maturity_date is None or maturity_date <= report_date or maturity_date > horizon_end:
            continue
        face_value = _coerce_decimal(
            row.get("face_value") or row.get("face_value_amount") or row.get("face_value_native")
        )
        market_value = _coerce_decimal(
            row.get("market_value") or row.get("market_value_amount") or row.get("market_value_native")
        )
        candidates.append(
            {
                "instrument_code": str(row.get("instrument_code") or ""),
                "instrument_name": str(row.get("instrument_name") or ""),
                "maturity_date": maturity_date,
                "face_value": face_value,
                "market_value": market_value,
                "currency_code": str(row.get("currency_code") or "CNY"),
            }
        )

    for row in tyw_rows:
        if _row_scope(row) != "asset":
            continue
        maturity_date = _effective_tyw_maturity_date(row, report_date)
        if maturity_date is None or maturity_date <= report_date or maturity_date > horizon_end:
            continue
        principal = _coerce_decimal(row.get("principal_amount") or row.get("principal_native"))
        candidates.append(
            {
                "instrument_code": str(row.get("position_id") or ""),
                "instrument_name": str(row.get("counterparty_name") or row.get("product_type") or ""),
                "maturity_date": maturity_date,
                "face_value": principal,
                "market_value": principal,
                "currency_code": str(row.get("currency_code") or "CNY"),
            }
        )

    candidates.sort(
        key=lambda row: (
            -Decimal(str(row["face_value"])),
            row["maturity_date"],
            str(row["instrument_code"]),
        )
    )
    return [
        {
            "instrument_code": str(row["instrument_code"]),
            "instrument_name": str(row["instrument_name"]),
            "maturity_date": row["maturity_date"].isoformat(),
            "face_value": numeric_json(Decimal(str(row["face_value"])), "yuan", False),
            "market_value": numeric_json(Decimal(str(row["market_value"])), "yuan", False),
            "currency_code": str(row["currency_code"]),
        }
        for row in candidates[:10]
    ]


def _collect_values(rows: list[dict[str, object]], field_name: str) -> list[str]:
    return [str(row.get(field_name) or "").strip() for row in rows if str(row.get(field_name) or "").strip()]


def _merge_versions(values: list[str], *, empty_value: str) -> str:
    merged = sorted({value.strip() for value in values if value and value.strip()})
    return "__".join(merged) or empty_value


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _text(value: Decimal) -> str:
    return format(value.quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _coerce_decimal(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _row_scope(row: dict[str, object]) -> str:
    raw = str(row.get("position_scope") or row.get("position_side") or "").strip().lower()
    if "asset" in raw:
        return "asset"
    if "liab" in raw:
        return "liability"
    return raw


def _effective_tyw_maturity_date(row: dict[str, object], report_date: date) -> date | None:
    maturity_date = _coerce_date(row.get("maturity_date"))
    if maturity_date is not None:
        return maturity_date
    product_type = str(row.get("product_type") or "").strip()
    if product_type in TYWL_DEMAND_PRODUCTS:
        month = report_date.month + 1
        year = report_date.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        day = min(report_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    return None


def _attach_macaulay_duration(
    zqtz_rows: list[dict[str, object]],
    analytics_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    macaulay_by_key: dict[tuple[str, str, str, str], Decimal] = {}
    for row in analytics_rows:
        value = _materialized_macaulay_duration(row.get("macaulay_duration"))
        if value is None:
            value = _recompute_macaulay_duration(row)
        if value is None:
            continue
        key = (
            str(row.get("instrument_code") or ""),
            str(row.get("portfolio_name") or ""),
            str(row.get("cost_center") or ""),
            str(row.get("currency_code") or ""),
        )
        macaulay_by_key[key] = value

    enriched: list[dict[str, object]] = []
    for row in zqtz_rows:
        if _row_scope(row) != "asset":
            enriched.append(row)
            continue
        key = (
            str(row.get("instrument_code") or ""),
            str(row.get("portfolio_name") or ""),
            str(row.get("cost_center") or ""),
            str(row.get("currency_code") or ""),
        )
        macaulay_duration = macaulay_by_key.get(key)
        if macaulay_duration is None:
            enriched.append(row)
            continue
        enriched.append({**row, "macaulay_duration": macaulay_duration})
    return enriched


def _recompute_macaulay_duration(row: dict[str, object]) -> Decimal | None:
    maturity_date = _coerce_date(row.get("maturity_date"))
    report_date = _coerce_date(row.get("report_date"))
    if maturity_date is None or report_date is None:
        return None
    coupon_rate = _coerce_decimal(row.get("coupon_rate"))
    ytm_value = row.get("ytm")
    if ytm_value in (None, ""):
        ytm_value = row.get("ytm_value")
    ytm = _coerce_decimal(ytm_value)
    interest_mode = row.get("interest_mode")
    _frequency, used_fallback = resolve_interest_payment_frequency(interest_mode)
    frequency_source = (
        row.get("interest_payment_frequency")
        if used_fallback and row.get("interest_payment_frequency") not in (None, "")
        else interest_mode
    )
    return estimate_duration(
        maturity_date,
        report_date,
        coupon_rate=coupon_rate,
        ytm=ytm,
        bond_code=str(row.get("instrument_code") or ""),
        coupon_frequency=coupon_frequency_per_year(frequency_source),
    )


def _materialized_macaulay_duration(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        duration = _coerce_decimal(value)
    except (ArithmeticError, TypeError, ValueError):
        return None
    if not duration.is_finite() or duration < Decimal("0"):
        return None
    return duration


def _cashflow_projection_quality_disclosures(
    rows: list[dict[str, object]],
) -> dict[str, object]:
    floating_rows: list[dict[str, object]] = []
    frequency_fallback_rows: list[dict[str, object]] = []
    bullet_value_date_fallback_rows: list[dict[str, object]] = []
    for row in rows:
        raw_mode = row.get("interest_mode")
        frequency, used_fallback = resolve_interest_payment_frequency(raw_mode)
        explicit_frequency = row.get("interest_payment_frequency")
        if used_fallback and explicit_frequency not in (None, ""):
            frequency, used_fallback = resolve_interest_payment_frequency(explicit_frequency)
        if used_fallback:
            frequency_fallback_rows.append(row)
        if classify_interest_rate_style(row.get("interest_rate_style") or raw_mode) == "floating":
            floating_rows.append(row)
        if frequency == "bullet" and not _has_valid_date(
            row.get("value_date"), before=row.get("maturity_date")
        ):
            bullet_value_date_fallback_rows.append(row)

    floating_market_value = _quality_market_value(floating_rows)
    frequency_fallback_market_value = _quality_market_value(frequency_fallback_rows)
    bullet_fallback_market_value = _quality_market_value(bullet_value_date_fallback_rows)
    warnings: list[str] = []
    if floating_rows:
        warnings.append(
            f"{len(floating_rows)} floating-rate rows with market_value={floating_market_value} "
            "use the current coupon rate as a frozen proxy for the full projection horizon; "
            "reset rates are not modeled."
        )
    if frequency_fallback_rows:
        warnings.append(
            f"{len(frequency_fallback_rows)} rows with market_value="
            f"{frequency_fallback_market_value} lack an explicit payment frequency; "
            "annual coupon frequency is used as a proxy."
        )
    if bullet_value_date_fallback_rows:
        warnings.append(
            f"{len(bullet_value_date_fallback_rows)} explicit bullet rows with market_value="
            f"{bullet_fallback_market_value} lack a valid value_date; a one-year interest proxy is used."
        )
    return {
        "floating_rate_proxy_count": len(floating_rows),
        "floating_rate_proxy_market_value": floating_market_value,
        "payment_frequency_fallback_count": len(frequency_fallback_rows),
        "payment_frequency_fallback_market_value": frequency_fallback_market_value,
        "bullet_value_date_fallback_count": len(bullet_value_date_fallback_rows),
        "bullet_value_date_fallback_market_value": bullet_fallback_market_value,
        "warnings": warnings,
    }


def _with_effective_payment_frequency(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    projected_rows: list[dict[str, object]] = []
    for row in rows:
        frequency, used_fallback = resolve_interest_payment_frequency(row.get("interest_mode"))
        explicit_frequency = row.get("interest_payment_frequency")
        if used_fallback and explicit_frequency not in (None, ""):
            frequency, _explicit_fallback = resolve_interest_payment_frequency(explicit_frequency)
        projected_rows.append({**row, "interest_mode": frequency})
    return projected_rows


def _quality_market_value(rows: list[dict[str, object]]) -> Decimal:
    return sum(
        (
            _coerce_decimal(
                row.get("market_value")
                or row.get("market_value_amount")
                or row.get("market_value_native")
            )
            for row in rows
        ),
        Decimal("0"),
    )


def _has_valid_date(value: object, *, before: object) -> bool:
    try:
        value_date = _coerce_date(value)
        boundary_date = _coerce_date(before)
    except (TypeError, ValueError):
        return False
    return value_date is not None and boundary_date is not None and value_date < boundary_date
