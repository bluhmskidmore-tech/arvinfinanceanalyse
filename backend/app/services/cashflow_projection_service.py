from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from backend.app.core_finance.cashflow_projection import MonthlyBucket, compute_duration_gap
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.cashflow_projection_repo import CashflowProjectionRepository
from backend.app.schemas.cashflow_projection import CashflowProjectionResponse
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)

Q8 = Decimal("0.00000000")
CACHE_VERSION = "cv_cashflow_projection_read_v1"
RULE_VERSION = "rv_cashflow_projection_read_v1"
EMPTY_SOURCE_VERSION = "sv_cashflow_projection_empty"


def get_cashflow_projection(report_date: date) -> dict[str, object]:
    settings = get_settings()
    report_date_text = report_date.isoformat()

    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    projection_repo = CashflowProjectionRepository(str(settings.duckdb_path))
    bond_rows = bond_repo.fetch_bond_analytics_rows(report_date=report_date_text)
    tyw_rows = projection_repo.fetch_formal_tyw_liability_rows(
        report_date=report_date_text,
        currency_basis="CNY",
    )

    if not bond_rows and not tyw_rows:
        raise ValueError(f"No cashflow projection data found for report_date={report_date_text}.")

    result = compute_duration_gap(
        bond_rows=bond_rows,
        tyw_rows=tyw_rows,
        report_date=report_date,
        horizon_months=24,
    )

    meta = build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind="cashflow_projection.overview",
        cache_version=CACHE_VERSION,
        source_version=_merge_versions(
            [*_collect_values(bond_rows, "source_version"), *_collect_values(tyw_rows, "source_version")],
            empty_value=EMPTY_SOURCE_VERSION,
        ),
        rule_version=_merge_versions(
            [*_collect_values(bond_rows, "rule_version"), *_collect_values(tyw_rows, "rule_version")],
            empty_value=RULE_VERSION,
        ),
    )

    response = CashflowProjectionResponse(
        report_date=report_date,
        duration_gap=_text(result.duration_gap),
        asset_duration=_text(result.asset_weighted_duration),
        liability_duration=_text(result.liability_weighted_duration),
        equity_duration=_text(result.equity_duration),
        rate_sensitivity_1bp=_text(result.rate_sensitivity_1bp),
        reinvestment_risk_12m=_text(result.reinvestment_risk_12m),
        monthly_buckets=[_serialize_monthly_bucket(bucket) for bucket in result.monthly_buckets],
        top_maturing_assets_12m=_build_top_maturing_assets_12m(bond_rows, report_date),
        warnings=list(result.warnings),
        computed_at=meta.generated_at.isoformat(),
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=response.model_dump(mode="json"),
    )


def _serialize_monthly_bucket(bucket: MonthlyBucket) -> dict[str, str]:
    return {
        "year_month": bucket.year_month,
        "asset_inflow": _text(bucket.asset_inflow),
        "liability_outflow": _text(bucket.liability_outflow),
        "net_cashflow": _text(bucket.net_cashflow),
        "cumulative_net": _text(bucket.cumulative_net),
    }


def _build_top_maturing_assets_12m(
    bond_rows: list[dict[str, object]],
    report_date: date,
) -> list[dict[str, str]]:
    horizon_end = date(report_date.year + 1, report_date.month, report_date.day)
    candidates: list[dict[str, object]] = []
    for row in bond_rows:
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
            "face_value": _text(Decimal(str(row["face_value"]))),
            "market_value": _text(Decimal(str(row["market_value"]))),
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
