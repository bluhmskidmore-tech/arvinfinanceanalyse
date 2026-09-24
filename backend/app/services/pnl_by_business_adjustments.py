from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from backend.app.core_finance.field_normalization import is_approved_status
from backend.app.repositories.governance_repo import GovernanceRepository

PNL_BY_BUSINESS_ADJUSTMENT_STREAM = "pnl_by_business_adjustments"
PNL_BY_BUSINESS_ADJUSTMENT_SOURCE_VERSION = "sv_pnl_by_business_adjustments_v1"


def load_pnl_by_business_manual_adjustment_events(
    governance_dir: str | Path,
) -> list[dict[str, object]]:
    rows = GovernanceRepository(base_dir=governance_dir).read_all(PNL_BY_BUSINESS_ADJUSTMENT_STREAM)
    events: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        adjustment_id = str(row.get("adjustment_id") or "").strip() or f"legacy-{index}"
        events.append(
            {
                "adjustment_id": adjustment_id,
                "event_type": str(row.get("event_type") or "legacy"),
                "created_at": str(row.get("created_at") or ""),
                "stream": PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
                "report_date": str(row.get("report_date") or ""),
                "row_key": str(row.get("row_key") or ""),
                "business_type": str(row.get("business_type") or ""),
                "operator": str(row.get("operator") or "DELTA"),
                "approval_status": str(row.get("approval_status") or ""),
                "manual_adjustment": row.get("manual_adjustment") or "0",
                "reason": str(row.get("reason") or ""),
                "created_by": str(row.get("created_by") or ""),
                "approved_by": str(row.get("approved_by") or ""),
            }
        )
    return events


def reduce_latest_pnl_by_business_manual_adjustments(
    events: list[dict[str, object]],
) -> list[dict[str, object]]:
    latest_by_id: dict[str, dict[str, object]] = {}
    for event in events:
        adjustment_id = str(event.get("adjustment_id") or "")
        existing = latest_by_id.get(adjustment_id)
        if existing is None or str(event.get("created_at") or "") >= str(existing.get("created_at") or ""):
            latest_by_id[adjustment_id] = event
    return list(latest_by_id.values())


def active_pnl_by_business_manual_adjustments_for_period(
    governance_dir: str | Path,
    *,
    year: int,
    period_end: str,
) -> list[dict[str, object]]:
    records = [
        record
        for record in reduce_latest_pnl_by_business_manual_adjustments(
            load_pnl_by_business_manual_adjustment_events(governance_dir)
        )
        if str(record.get("report_date") or "").startswith(f"{year:04d}-")
        and str(record.get("report_date") or "") <= period_end
        and is_approved_status(str(record.get("approval_status") or ""))
    ]
    return sorted(
        records,
        key=lambda record: (
            str(record.get("report_date") or ""),
            str(record.get("adjustment_id") or ""),
        ),
    )


def pnl_by_business_manual_adjustment_source_version(
    records: list[dict[str, object]],
) -> str:
    fingerprint = [
        {
            "adjustment_id": str(record.get("adjustment_id") or ""),
            "report_date": str(record.get("report_date") or ""),
            "row_key": str(record.get("row_key") or ""),
            "business_type": str(record.get("business_type") or ""),
            "operator": str(record.get("operator") or "DELTA"),
            "manual_adjustment": str(record.get("manual_adjustment") or "0"),
        }
        for record in records
    ]
    digest = hashlib.sha256(
        json.dumps(
            fingerprint,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{PNL_BY_BUSINESS_ADJUSTMENT_SOURCE_VERSION}:{digest}"


def pnl_by_business_manual_adjustment_row(record: dict[str, object]) -> dict[str, object]:
    row_key = str(record.get("row_key") or "")
    adjustment = Decimal(str(record.get("manual_adjustment") or "0"))
    return {
        "source_kind": "manual_adjustment",
        "report_date": str(record.get("report_date") or ""),
        "instrument_code": f"manual::{row_key}",
        "portfolio_name": "manual_adjustment",
        "cost_center": "manual_adjustment",
        "currency_basis": "CNY",
        "invest_type_std": "",
        "accounting_basis": "manual_adjustment",
        "interest_income_514": Decimal("0"),
        "fair_value_change_516": Decimal("0"),
        "capital_gain_517": Decimal("0"),
        "manual_adjustment": adjustment,
        "total_pnl": adjustment,
        "manual_business_row_key": row_key,
        "manual_business_type": str(record.get("business_type") or ""),
        "source_note": f"{PNL_BY_BUSINESS_ADJUSTMENT_STREAM}:{record.get('adjustment_id')}",
    }
