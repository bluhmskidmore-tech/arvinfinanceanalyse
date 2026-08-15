"""macro_toolkit_service 门面的共享支撑层：公共常量、类型转换与写刷新公共 normalize。

代码自 macro_toolkit_service.py 门面拆分逐字迁入；语义与行为不变。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast

import pandas as pd


# 本地副本，避免模块级 import tasks（commodity_daily_ingest 会 register_actor）。
ThemeOverlayRefreshMode = Literal["off", "dry_run", "archive"]


_WRITE_REFRESH_RETRY_PENDING_AFTER = timedelta(hours=1)
_WRITE_REFRESH_PUBLIC_STATUSES = {
    "queued",
    "running",
    "retrying",
    "completed",
    "partial",
    "no_rows",
    "blocked",
    "failed",
}
_WRITE_REFRESH_PUBLIC_FAILURE_CATEGORIES = {
    "backfill_failure",
    "cache_invalidation",
    "queue_dispatch_failure",
    "vendor_failure",
}


MACRO_TOOLKIT_OBSERVATION_ONLY = True
MACRO_TOOLKIT_FORMAL_USE_ALLOWED = False
MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS = ("日期", "date", "trade_date", "as_of_date")


MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT = "/ui/macro/toolkit/scripts/run-chain"
MACRO_TOOLKIT_MODEL_READINESS_SURFACE = "/macro-toolkit#macro-toolkit-model-readiness-detail"


def _write_refresh_record_blocks_dispatch(
    record: dict[str, object],
    *,
    in_flight_statuses: set[str],
) -> bool:
    status = str(record.get("status") or "")
    if status in in_flight_statuses:
        return (
            True
            if status != "retrying"
            else _write_refresh_record_is_within_retry_window(record)
        )
    if status != "failed" or record.get("retryable") is not True:
        return False
    return _write_refresh_record_is_within_retry_window(record)


def _write_refresh_record_is_within_retry_window(
    record: dict[str, object],
) -> bool:
    raw_finished_at = str(record.get("finished_at") or "").strip()
    if not raw_finished_at:
        return False
    try:
        finished_at = datetime.fromisoformat(raw_finished_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)
    else:
        finished_at = finished_at.astimezone(UTC)
    return datetime.now(UTC) - finished_at <= _WRITE_REFRESH_RETRY_PENDING_AFTER


def _write_refresh_quality_flag(status: str) -> str:
    return "ok" if str(status or "").strip() == "completed" else "warning"


def _normalize_write_refresh_public_record(
    record: dict[str, object],
    *,
    job_name: str,
    cache_key: str,
    cache_version: str,
    rule_version: str,
    idempotency_replay: bool | None,
) -> dict[str, object]:
    raw_status = str(record.get("status") or "").strip()
    status = (
        raw_status if raw_status in _WRITE_REFRESH_PUBLIC_STATUSES else "failed"
    )
    failure_category = _optional_text(record.get("failure_category"))
    if failure_category not in _WRITE_REFRESH_PUBLIC_FAILURE_CATEGORIES:
        failure_category = "worker_failure" if failure_category else None
    normalized: dict[str, object] = {
        "run_id": _optional_text(record.get("run_id")),
        "job_name": job_name,
        "status": status,
        "trigger_mode": (
            "async"
            if status in {"queued", "running", "retrying"}
            else "terminal"
        ),
        "cache_key": cache_key,
        "cache_version": _optional_text(record.get("cache_version"))
        or cache_version,
        "rule_version": _optional_text(record.get("rule_version"))
        or rule_version,
        "report_date": _optional_text(record.get("report_date")),
        "queued_at": _optional_text(record.get("queued_at")),
        "started_at": _optional_text(record.get("started_at")),
        "finished_at": _optional_text(record.get("finished_at")),
        "attempt_count": _optional_int(record.get("attempt_count")),
        "max_attempts": _optional_int(record.get("max_attempts")),
        "retryable": record.get("retryable") is True,
        "failure_category": failure_category,
        "source_version": _optional_text(record.get("source_version")),
        "vendor_version": _optional_text(record.get("vendor_version")),
    }
    if idempotency_replay is not None:
        normalized["idempotency_replay"] = idempotency_replay
    return normalized


def _public_text_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [
        text
        for item in value
        if (text := str(item or "").strip())
    ]


def _public_text_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        key_text = str(key or "").strip()
        if not key_text or not isinstance(item, (str, int, float, bool)):
            continue
        normalized[key_text] = str(item)
    return normalized


def _tail_text(value: str | bytes | None, limit: int = 12000) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return text[-limit:]


def _choice_stock_daily_observation_status_with_freshness(
    status: dict[str, object],
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    latest_trade_date = str(status.get("latest_trade_date") or "")[:10] or None
    return {
        **status,
        **_choice_stock_table_freshness(latest_trade_date, reference_date),
    }


def _choice_stock_factor_snapshot_status_with_freshness(
    status: dict[str, object],
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    as_of_date = str(status.get("as_of_date") or "")[:10] or None
    return {
        **status,
        **_choice_stock_table_freshness(as_of_date, reference_date),
    }


def _choice_stock_base_table_status(status: str) -> dict[str, object]:
    return {
        "materialized": False,
        "status": status,
        "row_count": 0,
        "stock_count": 0,
    }


def _choice_stock_table_status(status: str, *, reference_date: str | None = None) -> dict[str, object]:
    return {
        **_choice_stock_base_table_status(status),
        **_choice_stock_table_freshness(None, reference_date),
    }


def _choice_stock_table_freshness(data_date: str | None, reference_date: str | None) -> dict[str, object]:
    if not data_date:
        return {
            "freshness_status": "missing",
            "reference_date": reference_date,
            "stale_days": None,
            "fallback_mode": "missing",
            "fallback_date": None,
        }
    if not reference_date:
        return {
            "freshness_status": "unknown",
            "reference_date": None,
            "stale_days": None,
            "fallback_mode": "unknown",
            "fallback_date": None,
        }
    try:
        data_day = date.fromisoformat(data_date[:10])
        reference_day = date.fromisoformat(reference_date[:10])
    except ValueError:
        return {
            "freshness_status": "unknown",
            "reference_date": reference_date,
            "stale_days": None,
            "fallback_mode": "unknown",
            "fallback_date": None,
        }
    raw_stale_days = (reference_day - data_day).days
    stale_days = max(raw_stale_days, 0)
    if raw_stale_days <= 1:
        status = "current"
    elif raw_stale_days <= 7:
        status = "lagging"
    else:
        status = "stale"
    fallback_mode = "none" if status == "current" else "latest_available"
    return {
        "freshness_status": status,
        "reference_date": reference_day.isoformat(),
        "stale_days": stale_days,
        "fallback_mode": fallback_mode,
        "fallback_date": data_day.isoformat() if fallback_mode == "latest_available" else None,
    }


def _result_row_count(result: dict[str, object] | None) -> int | None:
    if not result:
        return None
    value = result.get("row_count")
    return None if value is None else int(value)


def _latest_result_field(field_name: str, *results: dict[str, object] | None) -> object | None:
    for result in results:
        if result and result.get(field_name):
            return result[field_name]
    return None


def _optional_text(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_theme_overlay_mode(value: object) -> ThemeOverlayRefreshMode:
    mode = str(value or "off").strip()
    if mode not in {"off", "dry_run", "archive"}:
        raise ValueError("theme_overlay_mode must be one of: off, dry_run, archive")
    return cast(ThemeOverlayRefreshMode, mode)


def _choice_stock_theme_overlay_source_version(*, parent_run_id: str, report_date: str) -> str:
    digest = hashlib.sha256(f"{parent_run_id}|{report_date}".encode()).hexdigest()[:16]
    return f"sv_choice_stock_theme_overlay_{digest}"


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


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


def _unique_texts(values: list[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output
