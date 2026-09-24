"""pnl_service 门面的纯工具子模块：文本/日期/数值/JSON 叶子函数（自 pnl_service.py 逐字拆出，无业务口径）。"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal


def _parse_created_at(value: str) -> datetime:
    raw_value = str(value or "").strip()
    if not raw_value:
        return datetime.min.replace(tzinfo=UTC)
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_calendar_month_end(value: str) -> bool:
    period_end = date.fromisoformat(value)
    return (period_end + timedelta(days=1)).day == 1


def _calendar_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return max((end - start).days + 1, 0)


def _decimal_value(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def _norm_text(value: object) -> str:
    return str(value or "").strip()


def _coverage_quality_flag(coverage_days: int, expected_days: int) -> str | None:
    if expected_days > 0 and coverage_days < expected_days:
        return "warning"
    return None


def _json_safe_payload(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_payload(item) for key, item in value.items()}
    return value


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _dispatch_failure_message(exc: Exception) -> str:
    return f"Pnl refresh queue dispatch failed: {type(exc).__name__}: {exc}"
