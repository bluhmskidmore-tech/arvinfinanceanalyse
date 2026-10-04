from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

SCHEMA_VERSION = 1
RECEIPT_KIND = "stock_analysis_calendar_receipt"
SOURCE_ID = "tushare.trade_cal:SSE"
ENDPOINT = "trade_cal"
EXCHANGE = "SSE"
SEMANTICS = "realized_calendar_as_observed"
DEFAULT_AUTHORITY_STATUS = "provisional"
APPROVED_AUTHORITY_STATUS = "approved"
ALLOWED_AUTHORITY_STATUSES = frozenset(
    {
        DEFAULT_AUTHORITY_STATUS,
        APPROVED_AUTHORITY_STATUS,
    }
)


def build_stock_analysis_calendar_receipt(
    *,
    calendar_rows: Sequence[Mapping[str, object]],
    request_start_date: str,
    request_end_date: str,
    fetched_at: str,
    authority_status: str = DEFAULT_AUTHORITY_STATUS,
    owner_approval_id: str | None = None,
) -> dict[str, Any]:
    start = _parse_date(request_start_date, field_name="request_start_date")
    end = _parse_date(request_end_date, field_name="request_end_date")
    if end < start:
        raise ValueError("request_end_date must be on or after request_start_date")
    _parse_datetime(fetched_at, field_name="fetched_at")

    normalized_rows = _normalize_calendar_rows(
        calendar_rows=calendar_rows,
        request_start_date=start,
        request_end_date=end,
    )
    normalized_authority_status = _normalize_authority_status(
        authority_status,
        field_name="authority_status",
    )
    normalized_owner_approval_id = _normalized_optional_text(owner_approval_id)
    certification_allowed = (
        normalized_authority_status == APPROVED_AUTHORITY_STATUS
        and normalized_owner_approval_id is not None
    )

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "source_id": SOURCE_ID,
        "endpoint": ENDPOINT,
        "exchange": EXCHANGE,
        "request": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "natural_day_count": len(normalized_rows),
        },
        "fetched_at": fetched_at,
        "semantics": SEMANTICS,
        "authority_status": normalized_authority_status,
        "owner_approval_id": normalized_owner_approval_id,
        "certification_allowed": certification_allowed,
        "response_row_count": len(normalized_rows),
        "calendar_rows": normalized_rows,
        "response_sha256": _canonical_json_sha256(normalized_rows),
        "open_date_axis_sha256": _canonical_json_sha256(
            [row["cal_date"] for row in normalized_rows if row["is_open"] == 1]
        ),
    }
    receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
    return receipt


def validate_stock_analysis_calendar_receipt(
    receipt: Mapping[str, object],
    *,
    calendar_rows: Sequence[Mapping[str, object]] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    try:
        normalized_receipt = _normalize_receipt(receipt)
    except (TypeError, ValueError) as exc:
        return False, (str(exc),)

    expected_receipt_hash = _receipt_sha256(normalized_receipt)
    actual_receipt_hash = normalized_receipt["canonical_receipt_sha256"]
    if expected_receipt_hash != actual_receipt_hash:
        errors.append("canonical_receipt_sha256 mismatch")

    receipt_rows = normalized_receipt["calendar_rows"]
    expected_response_hash = _canonical_json_sha256(receipt_rows)
    if expected_response_hash != normalized_receipt["response_sha256"]:
        errors.append("response_sha256 mismatch")

    expected_open_hash = _canonical_json_sha256(
        [row["cal_date"] for row in receipt_rows if row["is_open"] == 1]
    )
    if expected_open_hash != normalized_receipt["open_date_axis_sha256"]:
        errors.append("open_date_axis_sha256 mismatch")

    if normalized_receipt["authority_status"] != APPROVED_AUTHORITY_STATUS:
        if normalized_receipt["certification_allowed"]:
            errors.append("provisional authority must stay fail-closed")
    elif not normalized_receipt["owner_approval_id"]:
        if normalized_receipt["certification_allowed"]:
            errors.append("approved authority requires owner_approval_id")
        else:
            errors.append("approved authority missing owner_approval_id")
    elif not normalized_receipt["certification_allowed"]:
        errors.append("approved authority with owner_approval_id must allow certification")

    if calendar_rows is not None:
        request = normalized_receipt["request"]
        try:
            expected_rows = _normalize_calendar_rows(
                calendar_rows=calendar_rows,
                request_start_date=_parse_date(
                    request["start_date"],
                    field_name="receipt.request.start_date",
                ),
                request_end_date=_parse_date(
                    request["end_date"],
                    field_name="receipt.request.end_date",
                ),
            )
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
        else:
            if expected_rows != receipt_rows:
                errors.append("calendar_rows mismatch")
            if _canonical_json_sha256(expected_rows) != normalized_receipt["response_sha256"]:
                errors.append("calendar_rows response_sha256 mismatch")

    return not errors, tuple(errors)


def _normalize_calendar_rows(
    *,
    calendar_rows: Sequence[Mapping[str, object]],
    request_start_date: date,
    request_end_date: date,
) -> list[dict[str, Any]]:
    if not calendar_rows:
        raise ValueError("calendar_rows must not be empty")

    expected_dates = _expected_date_axis(request_start_date, request_end_date)
    by_date: dict[str, dict[str, Any]] = {}

    for index, raw_row in enumerate(calendar_rows):
        if not isinstance(raw_row, Mapping):
            raise TypeError(f"calendar_rows[{index}] must be a mapping")
        normalized = _normalize_single_row(raw_row, index=index)
        cal_date = normalized["cal_date"]
        if cal_date not in expected_dates:
            raise ValueError(
                f"calendar_rows[{index}].cal_date {cal_date} is outside requested range "
                f"{request_start_date.isoformat()}..{request_end_date.isoformat()}"
            )
        if cal_date in by_date:
            raise ValueError(f"duplicate calendar row for cal_date {cal_date}")
        by_date[cal_date] = normalized

    missing = sorted(expected_dates.difference(by_date))
    if missing:
        raise ValueError(f"calendar_rows missing requested dates: {', '.join(missing)}")

    return [by_date[current.isoformat()] for current in _iter_dates(request_start_date, request_end_date)]


def _normalize_single_row(raw_row: Mapping[str, object], *, index: int) -> dict[str, Any]:
    exchange = raw_row.get("exchange", EXCHANGE)
    normalized_exchange = _normalize_text(exchange, field_name=f"calendar_rows[{index}].exchange")
    if normalized_exchange != EXCHANGE:
        raise ValueError(
            f"calendar_rows[{index}].exchange must be {EXCHANGE}, got {normalized_exchange}"
        )

    cal_date = _parse_date(
        raw_row.get("cal_date"),
        field_name=f"calendar_rows[{index}].cal_date",
    )
    is_open = _normalize_is_open(raw_row.get("is_open"), field_name=f"calendar_rows[{index}].is_open")
    pretrade_date = _normalize_pretrade_date(
        raw_row.get("pretrade_date"),
        field_name=f"calendar_rows[{index}].pretrade_date",
        cal_date=cal_date,
    )

    return {
        "exchange": normalized_exchange,
        "cal_date": cal_date.isoformat(),
        "is_open": is_open,
        "pretrade_date": pretrade_date,
    }


def _normalize_receipt(receipt: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")

    normalized = deepcopy(dict(receipt))
    if normalized.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"receipt.schema_version must equal {SCHEMA_VERSION}")
    if normalized.get("receipt_kind") != RECEIPT_KIND:
        raise ValueError(f"receipt.receipt_kind must equal {RECEIPT_KIND}")
    if normalized.get("source_id") != SOURCE_ID:
        raise ValueError(f"receipt.source_id must equal {SOURCE_ID}")
    if normalized.get("endpoint") != ENDPOINT:
        raise ValueError(f"receipt.endpoint must equal {ENDPOINT}")
    if normalized.get("exchange") != EXCHANGE:
        raise ValueError(f"receipt.exchange must equal {EXCHANGE}")
    if normalized.get("semantics") != SEMANTICS:
        raise ValueError(f"receipt.semantics must equal {SEMANTICS}")

    request = normalized.get("request")
    if not isinstance(request, Mapping):
        raise TypeError("receipt.request must be a mapping")
    start = _parse_date(request.get("start_date"), field_name="receipt.request.start_date")
    end = _parse_date(request.get("end_date"), field_name="receipt.request.end_date")
    if end < start:
        raise ValueError("receipt.request.end_date must be on or after start_date")

    _parse_datetime(normalized.get("fetched_at"), field_name="receipt.fetched_at")
    normalized["authority_status"] = _normalize_authority_status(
        normalized.get("authority_status"),
        field_name="receipt.authority_status",
    )
    normalized["owner_approval_id"] = _normalized_optional_text(
        normalized.get("owner_approval_id")
    )
    if not isinstance(normalized.get("certification_allowed"), bool):
        raise TypeError("receipt.certification_allowed must be a boolean")

    normalized_rows = _normalize_calendar_rows(
        calendar_rows=_require_sequence(
            normalized.get("calendar_rows"),
            field_name="receipt.calendar_rows",
        ),
        request_start_date=start,
        request_end_date=end,
    )
    expected_count = len(normalized_rows)
    _require_exact_int(
        normalized.get("response_row_count"),
        expected=expected_count,
        field_name="receipt.response_row_count",
    )
    _require_exact_int(
        request.get("natural_day_count"),
        expected=expected_count,
        field_name="receipt.request.natural_day_count",
    )
    normalized["calendar_rows"] = normalized_rows
    normalized["request"] = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "natural_day_count": expected_count,
    }
    normalized["response_row_count"] = expected_count
    normalized["response_sha256"] = _normalize_hex_hash(
        normalized.get("response_sha256"),
        field_name="receipt.response_sha256",
    )
    normalized["open_date_axis_sha256"] = _normalize_hex_hash(
        normalized.get("open_date_axis_sha256"),
        field_name="receipt.open_date_axis_sha256",
    )
    normalized["canonical_receipt_sha256"] = _normalize_hex_hash(
        normalized.get("canonical_receipt_sha256"),
        field_name="receipt.canonical_receipt_sha256",
    )
    return normalized


def _receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_receipt_sha256", None)
    return _canonical_json_sha256(payload)


def _canonical_json_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def _normalize_hex_hash(value: object, *, field_name: str) -> str:
    normalized = _normalize_text(value, field_name=field_name)
    if len(normalized) != 64 or any(ch not in "0123456789ABCDEF" for ch in normalized):
        raise ValueError(f"{field_name} must be a 64-character uppercase sha256 hex string")
    return normalized


def _normalize_is_open(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    if isinstance(value, str) and value.strip() in {"0", "1"}:
        return int(value.strip())
    raise ValueError(f"{field_name} must be 0 or 1")


def _normalize_pretrade_date(
    value: object,
    *,
    field_name: str,
    cal_date: date,
) -> str | None:
    normalized = _normalized_optional_text(value)
    if normalized is None:
        return None
    parsed = _parse_date(normalized, field_name=field_name)
    if parsed > cal_date:
        raise ValueError(f"{field_name} must not be after cal_date {cal_date.isoformat()}")
    return parsed.isoformat()


def _normalize_text(value: object, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _normalize_authority_status(value: object, *, field_name: str) -> str:
    normalized = _normalize_text(value, field_name=field_name)
    if normalized not in ALLOWED_AUTHORITY_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_AUTHORITY_STATUSES))
        raise ValueError(f"{field_name} must be one of: {allowed}")
    return normalized


def _normalized_optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _parse_date(value: object, *, field_name: str) -> date:
    try:
        return date.fromisoformat(_normalize_text(value, field_name=field_name))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _parse_datetime(value: object, *, field_name: str) -> datetime:
    normalized = _normalize_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone offset")
    return parsed


def _expected_date_axis(start: date, end: date) -> set[str]:
    return {current.isoformat() for current in _iter_dates(start, end)}


def _iter_dates(start: date, end: date) -> list[date]:
    total_days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(total_days + 1)]


def _require_sequence(value: object, *, field_name: str) -> Sequence[Mapping[str, object]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    raise TypeError(f"{field_name} must be a sequence")


def _require_exact_int(value: object, *, expected: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int equal to {expected}")
    if value != expected:
        raise ValueError(f"{field_name} must equal {expected}")
