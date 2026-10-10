from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from backend.app.governance.stock_analysis_calendar_approval_decision import (
    CalendarApprovalDecisionError,
    build_stock_analysis_calendar_approval_decision,
    validate_stock_analysis_calendar_approval_decision,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    build_stock_analysis_calendar_receipt,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _calendar_receipt(
    *,
    authority_status: str = "approved",
    owner_approval_id: str = "OWNER-CALENDAR-20260823",
) -> dict[str, object]:
    return build_stock_analysis_calendar_receipt(
        calendar_rows=[
            {
                "exchange": "SSE",
                "cal_date": "2026-08-21",
                "is_open": 1,
                "pretrade_date": "2026-08-20",
            },
            {
                "exchange": "SSE",
                "cal_date": "2026-08-22",
                "is_open": 0,
                "pretrade_date": "2026-08-21",
            },
        ],
        request_start_date="2026-08-21",
        request_end_date="2026-08-22",
        fetched_at="2026-08-23T02:00:00Z",
        authority_status=authority_status,
        owner_approval_id=owner_approval_id,
    )


def _decision(
    receipt: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    approved_receipt = receipt or _calendar_receipt()
    decision = build_stock_analysis_calendar_approval_decision(
        approved_calendar_receipt=approved_receipt,
        owner_approval_id=str(approved_receipt["owner_approval_id"]),
        approved_at="2026-08-23T02:30:00Z",
        recorded_at="2026-08-23T02:31:00+00:00",
        approved_by_label="workspace user",
        recorded_by_agent="Codex local workspace agent",
        approval_reference="codex-task:stock-analysis-calendar-policy",
    )
    return decision, approved_receipt


def _reseal(decision: dict[str, object]) -> None:
    payload = {
        key: value
        for key, value in decision.items()
        if key != "canonical_decision_sha256"
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    decision["canonical_decision_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest().upper()


def test_build_is_idempotent_and_records_only_local_unsigned_approval() -> None:
    receipt = _calendar_receipt()
    first, _ = _decision(receipt)
    second, _ = _decision(receipt)

    assert first == second
    assert first["approval_mode"] == "local_human_attestation"
    assert first["signature_status"] == "unsigned_local_record"
    assert first["external_signature_verified"] is False
    assert first["authority_scope"] == "calendar_only"
    assert first["strict_coverage"] is True
    assert first["fallback_covered"] is False
    assert first["approved_at"] == "2026-08-23T02:30:00Z"
    assert first["recorded_at"] == "2026-08-23T02:31:00Z"
    assert first["calendar_receipt_sha256"] == receipt["canonical_receipt_sha256"]
    assert first["calendar_source_id"] == receipt["source_id"]
    assert first["calendar_semantics"] == receipt["semantics"]
    assert first["owner_approval_id"] == receipt["owner_approval_id"]
    ok, errors = validate_stock_analysis_calendar_approval_decision(
        first,
        approved_calendar_receipt=receipt,
    )
    assert ok is True
    assert errors == ()


def test_validate_rejects_tampering() -> None:
    decision, receipt = _decision()
    tampered = deepcopy(decision)
    tampered["approved_by_label"] = "someone else"

    ok, errors = validate_stock_analysis_calendar_approval_decision(
        tampered,
        approved_calendar_receipt=receipt,
    )

    assert ok is False
    assert errors == ("canonical_decision_sha256 mismatch",)


def test_build_rejects_explicit_receipt_sha_and_owner_approval_mismatch() -> None:
    receipt = _calendar_receipt()

    with pytest.raises(
        CalendarApprovalDecisionError,
        match="calendar_receipt_sha256 must exactly match",
    ):
        build_stock_analysis_calendar_approval_decision(
            approved_calendar_receipt=receipt,
            calendar_receipt_sha256="A" * 64,
            owner_approval_id=str(receipt["owner_approval_id"]),
            approved_at="2026-08-23T02:30:00Z",
            recorded_at="2026-08-23T02:31:00Z",
            approved_by_label="workspace user",
            recorded_by_agent="Codex local workspace agent",
            approval_reference="codex-task:stock-analysis-calendar-policy",
        )

    with pytest.raises(
        CalendarApprovalDecisionError,
        match="owner_approval_id must exactly match",
    ):
        build_stock_analysis_calendar_approval_decision(
            approved_calendar_receipt=receipt,
            owner_approval_id="OWNER-WRONG",
            approved_at="2026-08-23T02:30:00Z",
            recorded_at="2026-08-23T02:31:00Z",
            approved_by_label="workspace user",
            recorded_by_agent="Codex local workspace agent",
            approval_reference="codex-task:stock-analysis-calendar-policy",
        )


def test_validate_rejects_binding_to_a_different_approved_receipt() -> None:
    decision, _ = _decision()
    other_receipt = _calendar_receipt(owner_approval_id="OWNER-CALENDAR-OTHER")

    ok, errors = validate_stock_analysis_calendar_approval_decision(
        decision,
        approved_calendar_receipt=other_receipt,
    )

    assert ok is False
    assert "calendar_receipt_sha256 does not match the approved calendar receipt" in errors
    assert "owner_approval_id does not match the approved calendar receipt" in errors


def test_validate_rejects_wrong_calendar_semantics_even_when_resealed() -> None:
    decision, receipt = _decision()
    decision["calendar_semantics"] = "latest_calendar_backfill"
    _reseal(decision)

    ok, errors = validate_stock_analysis_calendar_approval_decision(
        decision,
        approved_calendar_receipt=receipt,
    )

    assert ok is False
    assert "calendar_semantics must equal realized_calendar_as_observed" in errors
    assert "calendar_semantics does not match the approved calendar receipt" in errors


def test_validate_rejects_fallback_true_even_when_resealed() -> None:
    decision, receipt = _decision()
    decision["fallback_covered"] = True
    _reseal(decision)

    ok, errors = validate_stock_analysis_calendar_approval_decision(
        decision,
        approved_calendar_receipt=receipt,
    )

    assert ok is False
    assert "fallback_covered must be false" in errors


def test_build_rejects_nonapproved_calendar_receipt() -> None:
    provisional = _calendar_receipt(authority_status="provisional")

    with pytest.raises(
        CalendarApprovalDecisionError,
        match="calendar receipt authority_status must be approved",
    ):
        build_stock_analysis_calendar_approval_decision(
            approved_calendar_receipt=provisional,
            owner_approval_id=str(provisional["owner_approval_id"]),
            approved_at="2026-08-23T02:30:00Z",
            recorded_at="2026-08-23T02:31:00Z",
            approved_by_label="workspace user",
            recorded_by_agent="Codex local workspace agent",
            approval_reference="codex-task:stock-analysis-calendar-policy",
        )


@pytest.mark.parametrize(
    ("field_name", "value", "expected_message"),
    [
        ("approved_at", "2026-08-23T10:30:00+08:00", "approved_at must be a UTC datetime"),
        ("recorded_at", "2026-08-23T02:31:00", "recorded_at must be a UTC datetime"),
        ("approved_by_label", "", "approved_by_label must be non-empty"),
        ("recorded_by_agent", " ", "recorded_by_agent must be non-empty"),
        ("approval_reference", "", "approval_reference must be non-empty"),
    ],
)
def test_build_rejects_non_utc_or_empty_attestation_fields(
    field_name: str,
    value: str,
    expected_message: str,
) -> None:
    receipt = _calendar_receipt()
    kwargs = {
        "approved_calendar_receipt": receipt,
        "owner_approval_id": str(receipt["owner_approval_id"]),
        "approved_at": "2026-08-23T02:30:00Z",
        "recorded_at": "2026-08-23T02:31:00Z",
        "approved_by_label": "workspace user",
        "recorded_by_agent": "Codex local workspace agent",
        "approval_reference": "codex-task:stock-analysis-calendar-policy",
    }
    kwargs[field_name] = value

    with pytest.raises((TypeError, ValueError), match=expected_message):
        build_stock_analysis_calendar_approval_decision(**kwargs)
