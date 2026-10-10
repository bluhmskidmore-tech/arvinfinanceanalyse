"""Macro toolkit presentation and parsing helpers.

Stateless parsing/display helpers used by the macro toolkit route and by
`macro_toolkit_analysis_service`. Kept dependency-free (no imports from the
route module or from `macro_toolkit_analysis_service`) so both can import
from here without creating an import cycle.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

_SOURCE_BACKFILL_TARGETS = {
    "m0041813": {
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "default_sources": ["tushare_macro"],
        "backfill_mode": "macro_series",
    },
    "m0041653": {
        "alias": "M0041653",
        "series_id": "EMM00088132",
        "series_name": "公开市场操作:逆回购:7天:中标利率",
        "default_sources": ["choice_edb"],
        "backfill_mode": "crisis_score_inputs",
    },
    "m0017126": {
        "series_id": "M0017126",
        "series_name": "制造业PMI",
        "default_sources": ["tushare_macro"],
        "backfill_mode": "macro_series",
    },
}


def _latest_source_check_date(checks: list[dict[str, object]]) -> str | None:
    dates = [
        str(latest["date"])
        for check in checks
        if isinstance((latest := check.get("latest")), dict) and latest.get("date")
    ]
    return max(dates) if dates else None


def _commodity_status_text_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _commodity_status_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _factor_snapshot_provenance(financials: pd.DataFrame) -> dict[str, list[str]]:
    provenance = financials.attrs.get("provenance")
    if not isinstance(provenance, dict):
        return {}
    return {
        key: [str(item) for item in values if str(item or "").strip()]
        for key, values in provenance.items()
        if key.startswith("factor_") and isinstance(values, list) and values
    }


def _factor_snapshot_as_of_date(financials: pd.DataFrame) -> str | None:
    text = str(financials.attrs.get("factor_as_of_date") or "").strip()
    return text or None


def _factor_snapshot_date_status(financials: pd.DataFrame) -> str:
    text = str(financials.attrs.get("factor_date_status") or "").strip()
    return text or "unknown"


def _factor_snapshot_date_warnings(factor_date_status: str) -> list[str]:
    if factor_date_status == "fallback":
        return ["FACTOR_SNAPSHOT_DATE_FALLBACK"]
    return []


def _parse_report_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _coerce_frame_date(value: object) -> date | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except (AttributeError, TypeError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
