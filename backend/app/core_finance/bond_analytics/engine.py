"""Pure bond-analytics calculations from snapshot rows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.app.core_finance.bond_analytics.common import (
    classify_asset_class,
    estimate_convexity,
    estimate_duration,
    estimate_modified_duration,
    get_accounting_rule_trace,
    get_tenor_bucket,
    map_accounting_class,
    safe_decimal,
)

MISSING_SOURCE_VERSION = "sv_bond_analytics_snapshot_missing"
ENGINE_RULE_VERSION = "rv_bond_analytics_engine_v1"
MISSING_INGEST_BATCH_ID = "ib_bond_analytics_missing"


@dataclass(slots=True, frozen=True)
class BondAnalyticsRow:
    """Per-bond analytics row derived from a standardized zqtz snapshot row."""

    report_date: date
    instrument_code: str
    instrument_name: str
    portfolio_name: str
    cost_center: str
    asset_class_raw: str
    asset_class_std: str
    bond_type: str
    issuer_name: str
    industry_name: str
    rating: str
    accounting_class: str
    accounting_rule_id: str
    currency_code: str
    face_value: Decimal
    market_value: Decimal
    amortized_cost: Decimal
    accrued_interest: Decimal
    coupon_rate: Decimal | None
    ytm: Decimal | None
    maturity_date: date | None
    years_to_maturity: Decimal
    tenor_bucket: str
    macaulay_duration: Decimal
    modified_duration: Decimal
    convexity: Decimal
    dv01: Decimal
    is_credit: bool
    spread_dv01: Decimal
    source_version: str
    rule_version: str
    ingest_batch_id: str
    trace_id: str


def compute_bond_analytics_rows(
    snapshot_rows: list[dict[str, Any]],
    report_date: date,
) -> list[BondAnalyticsRow]:
    """Project canonical snapshot rows into pure-compute bond analytics rows."""

    analytics_rows: list[BondAnalyticsRow] = []
    for index, snapshot_row in enumerate(snapshot_rows):
        if _coerce_bool(snapshot_row.get("is_issuance_like")):
            continue

        row_report_date = _resolve_report_date(
            expected_report_date=report_date,
            value=snapshot_row.get("report_date"),
        )
        instrument_code = _as_text(snapshot_row.get("instrument_code"))
        instrument_name = _as_text(snapshot_row.get("instrument_name"))
        asset_class_raw = _as_text(snapshot_row.get("asset_class"))
        bond_type = _as_text(snapshot_row.get("bond_type"))
        accounting_source = _first_non_blank(
            snapshot_row.get("account_category"),
            asset_class_raw,
        )
        asset_class_surface = " ".join(
            part
            for part in (asset_class_raw, bond_type, instrument_name)
            if part
        )
        asset_class_std = classify_asset_class(asset_class_surface)
        accounting_class = map_accounting_class(accounting_source)
        accounting_rule_id, _ = get_accounting_rule_trace(accounting_source)

        coupon_rate = _optional_decimal(snapshot_row.get("coupon_rate"))
        ytm = _optional_decimal(snapshot_row.get("ytm_value"))
        maturity_date = _coerce_date(snapshot_row.get("maturity_date"))
        years_to_maturity = _compute_years_to_maturity(
            report_date=report_date,
            maturity_date=maturity_date,
        )
        market_value = safe_decimal(snapshot_row.get("market_value_native"))
        if years_to_maturity == Decimal("0"):
            macaulay_duration = Decimal("0")
            modified_duration = Decimal("0")
            convexity = Decimal("0")
            dv01 = Decimal("0")
        else:
            macaulay_duration = estimate_duration(
                maturity_date,
                report_date,
                coupon_rate=coupon_rate or Decimal("0"),
                ytm=ytm or Decimal("0"),
                bond_code=instrument_code,
            )
            modified_duration = estimate_modified_duration(
                macaulay_duration,
                ytm or Decimal("0"),
            )
            convexity = estimate_convexity(
                macaulay_duration,
                ytm or Decimal("0"),
            )
            dv01 = market_value * modified_duration / Decimal("10000")
        is_credit = asset_class_std == "credit"

        analytics_rows.append(
            BondAnalyticsRow(
                report_date=row_report_date,
                instrument_code=instrument_code,
                instrument_name=instrument_name,
                portfolio_name=_as_text(snapshot_row.get("portfolio_name")),
                cost_center=_as_text(snapshot_row.get("cost_center")),
                asset_class_raw=asset_class_raw,
                asset_class_std=asset_class_std,
                bond_type=bond_type,
                issuer_name=_as_text(snapshot_row.get("issuer_name")),
                industry_name=_as_text(snapshot_row.get("industry_name")),
                rating=_as_text(snapshot_row.get("rating")),
                accounting_class=accounting_class,
                accounting_rule_id=accounting_rule_id,
                currency_code=_as_text(snapshot_row.get("currency_code")),
                face_value=safe_decimal(snapshot_row.get("face_value_native")),
                market_value=market_value,
                amortized_cost=safe_decimal(snapshot_row.get("amortized_cost_native")),
                accrued_interest=safe_decimal(snapshot_row.get("accrued_interest_native")),
                coupon_rate=coupon_rate,
                ytm=ytm,
                maturity_date=maturity_date,
                years_to_maturity=years_to_maturity,
                tenor_bucket=get_tenor_bucket(float(years_to_maturity)),
                macaulay_duration=macaulay_duration,
                modified_duration=modified_duration,
                convexity=convexity,
                dv01=dv01,
                is_credit=is_credit,
                spread_dv01=dv01 if is_credit else Decimal("0"),
                source_version=_first_non_blank(
                    snapshot_row.get("source_version"),
                    MISSING_SOURCE_VERSION,
                ),
                rule_version=_first_non_blank(
                    snapshot_row.get("rule_version"),
                    ENGINE_RULE_VERSION,
                ),
                ingest_batch_id=_first_non_blank(
                    snapshot_row.get("ingest_batch_id"),
                    MISSING_INGEST_BATCH_ID,
                ),
                trace_id=_first_non_blank(
                    snapshot_row.get("trace_id"),
                    f"trace_bond_analytics_{instrument_code or 'row'}_{index}",
                ),
            )
        )

    return analytics_rows


def _compute_years_to_maturity(*, report_date: date, maturity_date: date | None) -> Decimal:
    if maturity_date is None:
        return Decimal("0")
    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0")
    return Decimal(str(remaining_days)) / Decimal("365")


def _resolve_report_date(*, expected_report_date: date, value: Any) -> date:
    row_report_date = _coerce_date(value)
    if row_report_date is None:
        return expected_report_date
    if row_report_date != expected_report_date:
        raise ValueError(
            f"snapshot row report_date {row_report_date.isoformat()} does not match "
            f"requested report_date {expected_report_date.isoformat()}"
        )
    return row_report_date


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_non_blank(*values: Any) -> str:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return ""


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return safe_decimal(value)


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


__all__ = [
    "BondAnalyticsRow",
    "ENGINE_RULE_VERSION",
    "MISSING_INGEST_BATCH_ID",
    "MISSING_SOURCE_VERSION",
    "compute_bond_analytics_rows",
]
