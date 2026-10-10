from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, timedelta
from importlib import import_module
from typing import cast
from uuid import uuid4

from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RESULT_KIND = "market_data.stock_analysis.official_evidence"
RULE_VERSION = "rv_stock_official_evidence_v1"
CACHE_VERSION = "cv_stock_official_evidence_v1"
EMPTY_SOURCE_VERSION = "sv_stock_official_evidence_empty"
DEFAULT_VENDOR_VERSION = "vv_tushare_stock_official_disclosure"
DATE_BASIS = "publish_date_lte_requested_as_of_date"
# The official-evidence service contract requires a 550-day lookback. Keep
# this value local so the read path remains usable when its optional
# repository/duckdb dependency is unavailable and the lazy fallback is used.
EVIDENCE_COVERAGE_LOOKBACK_DAYS = 550

_READY_SYNC_STATUSES = {"current", "fresh", "ok", "ready", "success", "synced"}
_EMPTY_SYNC_STATUSES = {"empty", "no_data", "no_rows"}
_STALE_SYNC_STATUSES = {"degraded", "error", "expired", "failed", "partial", "stale", "timeout"}
_UNAVAILABLE_SYNC_STATUSES = {"missing", "source_table_unavailable", "table_missing", "unavailable"}

_LANE_SPECS: tuple[dict[str, object], ...] = (
    {
        "key": "official_announcement",
        "rows_key": "announcements",
        "label": "\u4e0a\u5e02\u516c\u53f8\u516c\u544a\u539f\u6587\uff08Tushare\uff09",
        "default_tables": [
            "fact_stock_official_disclosure",
            "stock_official_disclosure_sync_status",
        ],
    },
    {
        "key": "financial_report",
        "rows_key": "financial_reports",
        "label": "\u5b9a\u671f\u62a5\u544a\u539f\u6587\uff08Tushare\uff09",
        "default_tables": [
            "fact_stock_official_disclosure",
            "stock_official_disclosure_sync_status",
        ],
    },
)


def stock_official_evidence_envelope(
    *,
    duckdb_path: str,
    stock_code: str,
    as_of_date: date,
    limit_per_type: int,
    list_stock_official_disclosures_fn: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    requested_as_of_date = as_of_date.isoformat()
    repository_fn = list_stock_official_disclosures_fn
    extra_warnings: list[str] = []
    if repository_fn is None:
        try:
            repository_fn = _load_stock_official_disclosures()
        except (AttributeError, ImportError, ModuleNotFoundError) as exc:
            extra_warnings.append(
                f"Official disclosure repository is unavailable: {exc.__class__.__name__}."
            )
            repository_payload: dict[str, object] = {
                "table_available": {spec["key"]: False for spec in _LANE_SPECS},
                "sync_status": {},
                "announcements": [],
                "financial_reports": [],
                "excluded_future_rows": 0,
                "latest_ingested_at": None,
                "source_versions": {},
            }
            return _build_envelope(
                repository_payload=repository_payload,
                stock_code=stock_code,
                requested_as_of_date=requested_as_of_date,
                limit_per_type=limit_per_type,
                extra_warnings=extra_warnings,
            )

    repository_payload = repository_fn(
        duckdb_path=duckdb_path,
        stock_code=stock_code,
        as_of_date=as_of_date,
        limit_per_type=limit_per_type,
    )
    return _build_envelope(
        repository_payload=repository_payload,
        stock_code=stock_code,
        requested_as_of_date=requested_as_of_date,
        limit_per_type=limit_per_type,
        extra_warnings=extra_warnings,
    )


def _load_stock_official_disclosures() -> Callable[..., dict[str, object]]:
    module = import_module("backend.app.repositories.stock_official_disclosure_repo")
    repository_fn = module.list_stock_official_disclosures
    return cast(Callable[..., dict[str, object]], repository_fn)


def _build_envelope(
    *,
    repository_payload: object,
    stock_code: str,
    requested_as_of_date: str,
    limit_per_type: int,
    extra_warnings: list[str],
) -> dict[str, object]:
    payload = _mapping(repository_payload)
    table_available = payload.get("table_available")
    sync_status = _mapping(payload.get("sync_status"))
    source_versions = payload.get("source_versions")
    latest_ingested_at = _optional_text(payload.get("latest_ingested_at"))
    excluded_future_rows = _optional_non_negative_int(payload.get("excluded_future_rows")) or 0

    source_statuses: dict[str, dict[str, object]] = {}
    public_rows: dict[str, list[dict[str, object]]] = {}
    vendor_version_inputs: list[str] = []
    source_version_inputs = _all_source_version_candidates(source_versions)
    tables_used: list[str] = []
    warnings = list(extra_warnings)
    total_rows = 0

    for spec in _LANE_SPECS:
        lane_key = cast(str, spec["key"])
        rows_key = cast(str, spec["rows_key"])
        lane_label = cast(str, spec["label"])
        default_tables = cast(list[str], spec["default_tables"])
        lane_sync = _lane_sync_entry(sync_status, lane_key)
        lane_rows_raw = _list_of_mappings(payload.get(rows_key))
        lane_rows_raw, excluded_lane_future_rows = _exclude_future_rows(
            lane_rows_raw,
            requested_as_of_date=requested_as_of_date,
        )
        excluded_future_rows += excluded_lane_future_rows
        lane_table_available, lane_tables = _lane_table_state(
            table_available,
            lane_key=lane_key,
            default_tables=default_tables,
        )
        tables_used.extend(lane_tables)

        lane_source_version = _resolve_lane_source_version(
            lane_key=lane_key,
            source_versions=source_versions,
            rows=lane_rows_raw,
            lane_sync=lane_sync,
        )
        if lane_source_version:
            source_version_inputs.append(lane_source_version)

        public_lane_rows: list[dict[str, object]] = []
        for row in lane_rows_raw:
            normalized_row = _normalize_event_row(
                row,
                lane_key=lane_key,
                lane_label=lane_label,
                default_stock_code=stock_code,
                default_source_version=lane_source_version,
                default_ingested_at=latest_ingested_at,
            )
            public_lane_rows.append(normalized_row)
            vendor = _first_text(row.get("vendor_version"), lane_sync.get("vendor_version"), payload.get("vendor_version"))
            if vendor:
                vendor_version_inputs.append(vendor)
        total_rows += len(public_lane_rows)
        public_rows[rows_key] = public_lane_rows

        lane_status = _resolve_lane_status(
            lane_sync=lane_sync,
            lane_table_available=lane_table_available,
            row_count=len(public_lane_rows),
            requested_as_of_date=requested_as_of_date,
        )
        coverage_sufficient = (
            len(public_lane_rows) > 0
            or _coverage_window_is_sufficient(lane_sync, requested_as_of_date)
        )
        latest_publish_date = _latest_publish_date(public_lane_rows)
        refreshed_at = _first_text(
            lane_sync.get("last_success_at"),
            lane_sync.get("refreshed_at"),
            lane_sync.get("latest_ingested_at"),
            latest_ingested_at,
        )
        source_statuses[lane_key] = {
            "status": lane_status,
            "sync_status": _sync_state_text(lane_sync) or None,
            "coverage_sufficient": coverage_sufficient,
            "row_count": len(public_lane_rows),
            "latest_publish_date": latest_publish_date,
            "coverage_start_date": _first_text(lane_sync.get("coverage_start_date")),
            "covered_through_date": _first_text(lane_sync.get("covered_through_date")),
            "refreshed_at": refreshed_at,
            "source_label": lane_label,
        }
        warning = _lane_warning(
            lane_label=lane_label,
            lane_status=lane_status,
            lane_table_available=lane_table_available,
            lane_sync=lane_sync,
        )
        if warning:
            warnings.append(warning)

    state = _overall_state(source_statuses)
    covered_through_date = _covered_through_date(sync_status, source_statuses, requested_as_of_date)
    as_of_date = covered_through_date if _has_stale_lane(source_statuses) and covered_through_date else requested_as_of_date
    fallback_date = covered_through_date if _has_stale_lane(source_statuses) and covered_through_date != requested_as_of_date else None
    if excluded_future_rows > 0:
        warnings.append(
            f"Excluded {excluded_future_rows} future-dated row(s) after requested as_of_date."
        )

    quality_flag = _quality_flag(source_statuses)
    vendor_status = _vendor_status(source_statuses)
    fallback_mode = "latest_snapshot" if _has_stale_lane(source_statuses) else "none"
    vendor_version = _vendor_version(vendor_version_inputs, source_statuses)
    source_version = _source_version(source_version_inputs)

    result_payload = {
        "basis": "analytical",
        "contract_status": "observational_only",
        "formal_use_allowed": False,
        "stock_code": stock_code,
        "requested_as_of_date": requested_as_of_date,
        "as_of_date": as_of_date,
        "date_basis": DATE_BASIS,
        "state": state,
        "excluded_future_rows": excluded_future_rows,
        "source_statuses": source_statuses,
        "announcements": public_rows["announcements"],
        "financial_reports": public_rows["financial_reports"],
        "warnings": warnings,
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_official_evidence_{uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version,
        vendor_status=cast(VendorStatus, vendor_status),
        fallback_mode=cast(FallbackMode, fallback_mode),
        filters_applied={
            "stock_code": stock_code,
            "requested_as_of_date": requested_as_of_date,
            "limit_per_type": limit_per_type,
            "date_basis": DATE_BASIS,
        },
        tables_used=_unique_preserving_order(tables_used),
        evidence_rows=total_rows,
        as_of_date=as_of_date,
        date_basis=DATE_BASIS,
        fallback_date=fallback_date,
        result_payload=result_payload,
    )


def _normalize_event_row(
    row: Mapping[str, object],
    *,
    lane_key: str,
    lane_label: str,
    default_stock_code: str,
    default_source_version: str | None,
    default_ingested_at: str | None,
) -> dict[str, object]:
    source_id = _first_text(
        row.get("source_id"),
        row.get("announcement_id"),
        row.get("report_id"),
        row.get("id"),
        row.get("doc_id"),
    )
    publish_date = _normalize_date_text(
        _first_text(row.get("publish_date"), row.get("disclosure_date"), row.get("event_date"))
    )
    title = _first_text(row.get("title"), row.get("headline"), row.get("name"))
    stock_code = _first_text(row.get("stock_code"), default_stock_code) or default_stock_code
    event_key = _first_text(row.get("event_key"), row.get("disclosure_key"))
    if not event_key:
        event_key = "::".join(
            item for item in (lane_key, source_id, stock_code, publish_date, title) if item
        ) or f"{lane_key}::{stock_code}"
    return {
        "event_key": event_key,
        "source_type": lane_key,
        "source_label": _first_text(row.get("source_label"), lane_label) or lane_label,
        "source_id": source_id,
        "stock_code": stock_code,
        "stock_name": _first_text(row.get("stock_name")),
        "title": title,
        "publish_date": publish_date,
        "report_period": _first_text(row.get("report_period"), row.get("reporting_period")),
        "document_url": _first_text(row.get("document_url"), row.get("doc_url"), row.get("url")),
        "ingested_at": _first_text(row.get("ingested_at"), row.get("received_at"), default_ingested_at),
        "source_version": _first_text(row.get("source_version"), default_source_version),
    }


def _exclude_future_rows(
    rows: list[dict[str, object]],
    *,
    requested_as_of_date: str,
) -> tuple[list[dict[str, object]], int]:
    requested = _parse_iso_date(requested_as_of_date)
    if requested is None:
        return rows, 0
    kept: list[dict[str, object]] = []
    excluded = 0
    for row in rows:
        publish_date = _parse_iso_date(
            _normalize_date_text(
                _first_text(row.get("publish_date"), row.get("disclosure_date"), row.get("event_date"))
            )
        )
        if publish_date is not None and publish_date > requested:
            excluded += 1
            continue
        kept.append(row)
    return kept, excluded


def _lane_sync_entry(sync_status: Mapping[str, object], lane_key: str) -> dict[str, object]:
    direct = _mapping(sync_status.get(lane_key))
    if direct:
        return direct
    alternate = _mapping(sync_status.get(f"{lane_key}s"))
    if alternate:
        return alternate
    if _looks_like_sync_status(sync_status):
        return dict(sync_status)
    return {}


def _looks_like_sync_status(value: Mapping[str, object]) -> bool:
    return any(key in value for key in ("status", "covered_through_date", "last_success_at", "error_message"))


def _lane_table_state(table_available: object, *, lane_key: str, default_tables: list[str]) -> tuple[bool, list[str]]:
    if isinstance(table_available, bool):
        return table_available, list(default_tables) if table_available else []
    mapping = _mapping(table_available)
    if not mapping:
        return False, []
    entry = mapping.get(lane_key)
    if isinstance(entry, bool):
        return entry, list(default_tables) if entry else []
    entry_mapping = _mapping(entry)
    if entry_mapping:
        available = bool(
            entry_mapping.get("available") if "available" in entry_mapping else entry_mapping.get("table_available")
        )
        if not available:
            return False, []
        tables = _table_names(entry_mapping)
        if not tables:
            tables = list(default_tables)
        return available, tables
    return False, []


def _table_names(entry_mapping: Mapping[str, object]) -> list[str]:
    names: list[str] = []
    for key in ("fact_table", "table_name", "table"):
        text = _optional_text(entry_mapping.get(key))
        if text:
            names.append(text)
    for key in ("sync_status_table", "status_table"):
        text = _optional_text(entry_mapping.get(key))
        if text:
            names.append(text)
    tables = entry_mapping.get("tables")
    if isinstance(tables, list):
        names.extend(text for text in (_optional_text(item) for item in tables) if text)
    return names


def _resolve_lane_source_version(
    *,
    lane_key: str,
    source_versions: object,
    rows: list[dict[str, object]],
    lane_sync: Mapping[str, object],
) -> str | None:
    candidates: list[str] = []
    if isinstance(source_versions, Mapping):
        _append_source_version_values(candidates, source_versions.get(lane_key))
        _append_source_version_values(candidates, source_versions.get(f"{lane_key}s"))
    elif isinstance(source_versions, list):
        for item in source_versions:
            if isinstance(item, Mapping):
                key = _first_text(item.get("key"), item.get("lane"), item.get("source_type"))
                if key == lane_key:
                    _append_source_version_values(candidates, item.get("source_version"))
                    _append_source_version_values(candidates, item.get("value"))
    _append_source_version_values(candidates, lane_sync.get("source_version"))
    for row in rows:
        _append_source_version_values(candidates, row.get("source_version"))
    unique = _unique_preserving_order(candidates)
    return unique[0] if unique else None


def _all_source_version_candidates(source_versions: object) -> list[str]:
    values: list[str] = []
    if isinstance(source_versions, Mapping):
        for item in source_versions.values():
            _append_source_version_values(values, item)
    elif isinstance(source_versions, list):
        for item in source_versions:
            if isinstance(item, Mapping):
                _append_source_version_values(values, item.get("source_version"))
                _append_source_version_values(values, item.get("value"))
            else:
                _append_source_version_values(values, item)
    return values


def _append_source_version_values(target: list[str], value: object) -> None:
    if isinstance(value, list):
        for item in value:
            _append_source_version_values(target, item)
        return
    if isinstance(value, Mapping):
        text = _first_text(value.get("source_version"), value.get("value"), value.get("version"))
        if text:
            target.append(text)
        return
    text = _optional_text(value)
    if text:
        target.append(text)


def _resolve_lane_status(
    *,
    lane_sync: Mapping[str, object],
    lane_table_available: bool,
    row_count: int,
    requested_as_of_date: str,
) -> str:
    if not lane_table_available:
        return "unavailable"
    sync_state = _sync_state_text(lane_sync)
    if sync_state in _STALE_SYNC_STATUSES:
        return "stale" if row_count > 0 else "unavailable"
    if sync_state in _UNAVAILABLE_SYNC_STATUSES:
        return "unavailable"
    if sync_state in _EMPTY_SYNC_STATUSES:
        return "ready" if row_count > 0 else ("empty" if _coverage_window_is_sufficient(lane_sync, requested_as_of_date) else "unavailable")
    if sync_state in _READY_SYNC_STATUSES:
        return "ready" if row_count > 0 else ("empty" if _coverage_window_is_sufficient(lane_sync, requested_as_of_date) else "unavailable")
    if row_count > 0:
        return "ready"
    return "unavailable"


def _sync_state_text(lane_sync: Mapping[str, object]) -> str:
    for key in ("status", "sync_status", "state", "refresh_status"):
        text = _optional_text(lane_sync.get(key))
        if text:
            return text.lower()
    return ""


def _latest_publish_date(rows: list[dict[str, object]]) -> str | None:
    dates = [text for text in (_normalize_date_text(_first_text(row.get("publish_date"))) for row in rows) if text]
    return max(dates) if dates else None


def _lane_warning(*, lane_label: str, lane_status: str, lane_table_available: bool, lane_sync: Mapping[str, object]) -> str | None:
    if lane_status in {"ready", "empty"}:
        return None
    reason = _first_text(
        lane_sync.get("error_message"),
        lane_sync.get("message"),
        lane_sync.get("detail"),
        lane_sync.get("reason"),
        lane_sync.get("error"),
    )
    if lane_status == "stale":
        base = f"{lane_label} evidence is stale; latest indexed rows are shown."
    elif not lane_table_available:
        base = f"{lane_label} source table is unavailable."
    elif _sync_state_text(lane_sync) in _READY_SYNC_STATUSES | _EMPTY_SYNC_STATUSES:
        return f"{lane_label} indexed coverage window insufficient; absence not established."
    else:
        base = f"{lane_label} evidence is unavailable."
    return f"{base} {reason}" if reason else base


def _coverage_window_is_sufficient(lane_sync: Mapping[str, object], requested_as_of_date: str) -> bool:
    requested = _parse_iso_date(requested_as_of_date)
    coverage_start = _parse_iso_date(_first_text(lane_sync.get("coverage_start_date"), lane_sync.get("requested_from_date")))
    covered_through = _parse_iso_date(_first_text(lane_sync.get("covered_through_date"), lane_sync.get("as_of_date")))
    if requested is None or coverage_start is None or covered_through is None:
        return False
    required_start = requested - timedelta(days=EVIDENCE_COVERAGE_LOOKBACK_DAYS)
    return coverage_start <= required_start and covered_through >= requested


def _overall_state(source_statuses: Mapping[str, object]) -> str:
    statuses = [_optional_text(_mapping(value).get("status")) or "unavailable" for value in source_statuses.values()]
    if statuses and all(status == "unavailable" for status in statuses):
        return "unavailable"
    if any(status in {"stale", "unavailable"} for status in statuses):
        return "partial"
    row_total = sum(_optional_non_negative_int(_mapping(value).get("row_count")) or 0 for value in source_statuses.values())
    return "missing" if row_total == 0 else "ok"


def _has_stale_lane(source_statuses: Mapping[str, object]) -> bool:
    return any((_optional_text(_mapping(value).get("status")) or "") == "stale" for value in source_statuses.values())


def _covered_through_date(sync_status: Mapping[str, object], source_statuses: Mapping[str, object], requested_as_of_date: str) -> str | None:
    requested = _parse_iso_date(requested_as_of_date)
    if requested is None:
        return None
    candidates: list[date] = []
    lane_keys = [cast(str, spec["key"]) for spec in _LANE_SPECS]
    entries = [_lane_sync_entry(sync_status, lane_key) for lane_key in lane_keys]
    if _looks_like_sync_status(sync_status):
        entries.append(dict(sync_status))
    for entry in entries:
        covered = _parse_iso_date(_normalize_date_text(_first_text(entry.get("covered_through_date"), entry.get("as_of_date"))))
        if covered is not None and covered <= requested:
            candidates.append(covered)
    if not candidates:
        return None
    return min(candidates).isoformat() if _has_stale_lane(source_statuses) else max(candidates).isoformat()


def _quality_flag(source_statuses: Mapping[str, object]) -> str:
    statuses = {_optional_text(_mapping(value).get("status")) or "unavailable" for value in source_statuses.values()}
    if "stale" in statuses:
        return "stale"
    if "unavailable" in statuses:
        return "warning"
    return "ok"


def _vendor_status(source_statuses: Mapping[str, object]) -> str:
    stale = False
    unavailable = False
    for value in source_statuses.values():
        entry = _mapping(value)
        status = _optional_text(entry.get("status")) or "unavailable"
        sync_status = _optional_text(entry.get("sync_status")) or ""
        if status == "stale" or sync_status in _STALE_SYNC_STATUSES:
            stale = True
        elif status == "unavailable" and sync_status not in _READY_SYNC_STATUSES | _EMPTY_SYNC_STATUSES:
            unavailable = True
    if stale:
        return "vendor_stale"
    if unavailable:
        return "vendor_unavailable"
    return "ok"


def _vendor_version(candidates: list[str], source_statuses: Mapping[str, object]) -> str:
    cleaned = _unique_preserving_order([text for text in (_optional_text(item) for item in candidates) if text])
    if cleaned:
        return "__".join(cleaned)
    if any(
        (
            (_optional_text(_mapping(value).get("status")) or "") in {"ready", "empty", "stale"}
            or (_optional_text(_mapping(value).get("sync_status")) or "") in _READY_SYNC_STATUSES | _EMPTY_SYNC_STATUSES
        )
        for value in source_statuses.values()
    ):
        return DEFAULT_VENDOR_VERSION
    return "vv_none"


def _source_version(candidates: list[str]) -> str:
    cleaned = _unique_preserving_order([text for text in (_optional_text(item) for item in candidates) if text])
    return "__".join(cleaned) if cleaned else EMPTY_SOURCE_VERSION


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _normalize_date_text(value: str | None) -> str | None:
    parsed = _parse_iso_date(value)
    if parsed is not None:
        return parsed.isoformat()
    return _optional_text(value)


def _first_text(*values: object) -> str | None:
    for value in values:
        text = _optional_text(value)
        if text:
            return text
    return None


def _optional_non_negative_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
