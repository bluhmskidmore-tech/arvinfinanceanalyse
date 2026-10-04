from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from backend.app.governance.stock_analysis_calendar_receipt import (
    APPROVED_AUTHORITY_STATUS,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    SEMANTICS as CALENDAR_SEMANTICS,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    SOURCE_ID as CALENDAR_SOURCE_ID,
)

SCHEMA_VERSION = "stock-analysis-calendar-approval-decision-v1"
DECISION_KIND = "stock_analysis_calendar_approval_decision"
APPROVAL_MODE = "local_human_attestation"
SIGNATURE_STATUS = "unsigned_local_record"
AUTHORITY_SCOPE = "calendar_only"
STRICT_COVERAGE = True
FALLBACK_COVERED = False
EXTERNAL_SIGNATURE_VERIFIED = False
SELF_HASH_FIELD = "canonical_decision_sha256"

_DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "decision_kind",
        "approval_mode",
        "signature_status",
        "external_signature_verified",
        "authority_scope",
        "approved_at",
        "recorded_at",
        "approved_by_label",
        "recorded_by_agent",
        "approval_reference",
        "calendar_receipt_sha256",
        "calendar_source_id",
        "calendar_semantics",
        "owner_approval_id",
        "strict_coverage",
        "fallback_covered",
        SELF_HASH_FIELD,
    }
)


class CalendarApprovalDecisionError(ValueError):
    """Raised when a local calendar approval record is not trustworthy."""


def build_stock_analysis_calendar_approval_decision(
    *,
    approved_calendar_receipt: Mapping[str, object],
    owner_approval_id: str,
    approved_at: str,
    recorded_at: str,
    approved_by_label: str,
    recorded_by_agent: str,
    approval_reference: str,
    calendar_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    binding = _approved_calendar_binding(approved_calendar_receipt)
    normalized_owner_approval_id = _required_text(
        owner_approval_id,
        field_name="owner_approval_id",
    )
    if normalized_owner_approval_id != binding["owner_approval_id"]:
        raise CalendarApprovalDecisionError(
            "owner_approval_id must exactly match the approved calendar receipt"
        )

    if calendar_receipt_sha256 is not None:
        explicit_receipt_sha256 = _sha256_text(
            calendar_receipt_sha256,
            field_name="calendar_receipt_sha256",
        )
        if explicit_receipt_sha256 != binding["calendar_receipt_sha256"]:
            raise CalendarApprovalDecisionError(
                "calendar_receipt_sha256 must exactly match the approved calendar receipt"
            )

    normalized_approved_at = _utc_datetime_text(
        approved_at,
        field_name="approved_at",
    )
    normalized_recorded_at = _utc_datetime_text(
        recorded_at,
        field_name="recorded_at",
    )
    if _parse_utc_datetime(normalized_recorded_at) < _parse_utc_datetime(
        normalized_approved_at
    ):
        raise CalendarApprovalDecisionError("recorded_at must not be before approved_at")

    decision: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "decision_kind": DECISION_KIND,
        "approval_mode": APPROVAL_MODE,
        "signature_status": SIGNATURE_STATUS,
        "external_signature_verified": EXTERNAL_SIGNATURE_VERIFIED,
        "authority_scope": AUTHORITY_SCOPE,
        "approved_at": normalized_approved_at,
        "recorded_at": normalized_recorded_at,
        "approved_by_label": _required_text(
            approved_by_label,
            field_name="approved_by_label",
        ),
        "recorded_by_agent": _required_text(
            recorded_by_agent,
            field_name="recorded_by_agent",
        ),
        "approval_reference": _required_text(
            approval_reference,
            field_name="approval_reference",
        ),
        **binding,
        "strict_coverage": STRICT_COVERAGE,
        "fallback_covered": FALLBACK_COVERED,
    }
    decision[SELF_HASH_FIELD] = _decision_sha256(decision)
    ok, errors = validate_stock_analysis_calendar_approval_decision(
        decision,
        approved_calendar_receipt=approved_calendar_receipt,
    )
    if not ok:
        raise CalendarApprovalDecisionError(
            "built calendar approval decision is invalid: " + "; ".join(errors)
        )
    return decision


def validate_stock_analysis_calendar_approval_decision(
    decision: Mapping[str, object],
    *,
    approved_calendar_receipt: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    if not isinstance(decision, Mapping):
        return False, ("decision must be a mapping",)

    payload = dict(decision)
    actual_fields = frozenset(payload)
    if actual_fields != _DECISION_FIELDS:
        missing = sorted(_DECISION_FIELDS.difference(actual_fields))
        unexpected = sorted(actual_fields.difference(_DECISION_FIELDS))
        details: list[str] = []
        if missing:
            details.append("missing fields: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected fields: " + ", ".join(unexpected))
        return False, ("decision field set mismatch (" + "; ".join(details) + ")",)

    errors: list[str] = []
    try:
        observed_hash = _sha256_text(
            payload.get(SELF_HASH_FIELD),
            field_name=SELF_HASH_FIELD,
        )
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    else:
        if observed_hash != _decision_sha256(payload):
            errors.append(f"{SELF_HASH_FIELD} mismatch")

    _expect_exact_text(payload, "schema_version", SCHEMA_VERSION, errors)
    _expect_exact_text(payload, "decision_kind", DECISION_KIND, errors)
    _expect_exact_text(payload, "approval_mode", APPROVAL_MODE, errors)
    _expect_exact_text(payload, "signature_status", SIGNATURE_STATUS, errors)
    _expect_exact_bool(
        payload,
        "external_signature_verified",
        EXTERNAL_SIGNATURE_VERIFIED,
        errors,
    )
    _expect_exact_text(payload, "authority_scope", AUTHORITY_SCOPE, errors)
    _expect_exact_text(payload, "calendar_source_id", CALENDAR_SOURCE_ID, errors)
    _expect_exact_text(payload, "calendar_semantics", CALENDAR_SEMANTICS, errors)
    _expect_exact_bool(payload, "strict_coverage", STRICT_COVERAGE, errors)
    _expect_exact_bool(payload, "fallback_covered", FALLBACK_COVERED, errors)

    for field_name in (
        "approved_by_label",
        "recorded_by_agent",
        "approval_reference",
        "owner_approval_id",
    ):
        try:
            _required_text(payload.get(field_name), field_name=field_name)
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))

    parsed_times: dict[str, datetime] = {}
    for field_name in ("approved_at", "recorded_at"):
        try:
            normalized = _utc_datetime_text(
                payload.get(field_name),
                field_name=field_name,
            )
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
        else:
            if normalized != payload.get(field_name):
                errors.append(f"{field_name} must use canonical UTC Z format")
            parsed_times[field_name] = _parse_utc_datetime(normalized)
    if (
        parsed_times.get("recorded_at") is not None
        and parsed_times.get("approved_at") is not None
        and parsed_times["recorded_at"] < parsed_times["approved_at"]
    ):
        errors.append("recorded_at must not be before approved_at")

    try:
        decision_receipt_sha256 = _sha256_text(
            payload.get("calendar_receipt_sha256"),
            field_name="calendar_receipt_sha256",
        )
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        decision_receipt_sha256 = None

    try:
        binding = _approved_calendar_binding(approved_calendar_receipt)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    else:
        if decision_receipt_sha256 != binding["calendar_receipt_sha256"]:
            errors.append(
                "calendar_receipt_sha256 does not match the approved calendar receipt"
            )
        for field_name in (
            "calendar_source_id",
            "calendar_semantics",
            "owner_approval_id",
        ):
            if payload.get(field_name) != binding[field_name]:
                errors.append(
                    f"{field_name} does not match the approved calendar receipt"
                )

    return not errors, tuple(errors)


def _approved_calendar_binding(
    approved_calendar_receipt: Mapping[str, object],
) -> dict[str, str]:
    ok, receipt_errors = validate_stock_analysis_calendar_receipt(
        approved_calendar_receipt
    )
    if not ok:
        raise CalendarApprovalDecisionError(
            "approved calendar receipt is invalid: " + "; ".join(receipt_errors)
        )
    if approved_calendar_receipt.get("authority_status") != APPROVED_AUTHORITY_STATUS:
        raise CalendarApprovalDecisionError(
            "calendar receipt authority_status must be approved"
        )
    if approved_calendar_receipt.get("certification_allowed") is not True:
        raise CalendarApprovalDecisionError(
            "approved calendar receipt must allow certification"
        )
    source_id = _required_text(
        approved_calendar_receipt.get("source_id"),
        field_name="approved_calendar_receipt.source_id",
    )
    semantics = _required_text(
        approved_calendar_receipt.get("semantics"),
        field_name="approved_calendar_receipt.semantics",
    )
    if source_id != CALENDAR_SOURCE_ID:
        raise CalendarApprovalDecisionError(
            f"approved calendar receipt source_id must equal {CALENDAR_SOURCE_ID}"
        )
    if semantics != CALENDAR_SEMANTICS:
        raise CalendarApprovalDecisionError(
            f"approved calendar receipt semantics must equal {CALENDAR_SEMANTICS}"
        )
    return {
        "calendar_receipt_sha256": _sha256_text(
            approved_calendar_receipt.get("canonical_receipt_sha256"),
            field_name="approved_calendar_receipt.canonical_receipt_sha256",
        ),
        "calendar_source_id": source_id,
        "calendar_semantics": semantics,
        "owner_approval_id": _required_text(
            approved_calendar_receipt.get("owner_approval_id"),
            field_name="approved_calendar_receipt.owner_approval_id",
        ),
    }


def _expect_exact_text(
    payload: Mapping[str, object],
    field_name: str,
    expected: str,
    errors: list[str],
) -> None:
    value = payload.get(field_name)
    if value != expected:
        errors.append(f"{field_name} must equal {expected}")


def _expect_exact_bool(
    payload: Mapping[str, object],
    field_name: str,
    expected: bool,
    errors: list[str],
) -> None:
    value = payload.get(field_name)
    if not isinstance(value, bool) or value is not expected:
        errors.append(f"{field_name} must be {str(expected).lower()}")


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if normalized != value:
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    return normalized


def _sha256_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    if len(normalized) != 64 or any(ch not in "0123456789ABCDEF" for ch in normalized):
        raise ValueError(
            f"{field_name} must be a 64-character uppercase sha256 hex string"
        )
    return normalized


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field_name} must be a UTC datetime")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _decision_sha256(decision: Mapping[str, object]) -> str:
    payload = dict(decision)
    payload.pop(SELF_HASH_FIELD, None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()
