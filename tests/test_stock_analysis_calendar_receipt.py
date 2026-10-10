from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.governance.stock_analysis_calendar_receipt import (
    build_stock_analysis_calendar_receipt,
    validate_stock_analysis_calendar_receipt,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _calendar_rows() -> list[dict[str, object]]:
    return [
        {
            "exchange": "SSE",
            "cal_date": "2026-05-03",
            "is_open": "0",
            "pretrade_date": "2026-05-02",
        },
        {
            "exchange": "SSE",
            "cal_date": "2026-05-01",
            "is_open": 1,
            "pretrade_date": "2026-04-30",
        },
        {
            "exchange": "SSE",
            "cal_date": "2026-05-02",
            "is_open": 1,
            "pretrade_date": "2026-05-01",
        },
    ]


def test_build_receipt_hash_is_stable_across_input_row_order() -> None:
    first = build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
    )
    second = build_stock_analysis_calendar_receipt(
        calendar_rows=list(reversed(_calendar_rows())),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
    )

    assert first == second
    ok, errors = validate_stock_analysis_calendar_receipt(first)
    assert ok is True
    assert errors == ()


def test_build_receipt_rejects_missing_natural_day_coverage() -> None:
    rows = _calendar_rows()
    rows.pop()

    with pytest.raises(ValueError, match="missing requested dates: 2026-05-02"):
        build_stock_analysis_calendar_receipt(
            calendar_rows=rows,
            request_start_date="2026-05-01",
            request_end_date="2026-05-03",
            fetched_at="2026-05-04T10:30:00+08:00",
        )


def test_build_receipt_rejects_duplicate_dates() -> None:
    rows = _calendar_rows()
    rows.append(
        {
            "exchange": "SSE",
            "cal_date": "2026-05-02",
            "is_open": 0,
            "pretrade_date": "2026-05-01",
        }
    )

    with pytest.raises(ValueError, match="duplicate calendar row for cal_date 2026-05-02"):
        build_stock_analysis_calendar_receipt(
            calendar_rows=rows,
            request_start_date="2026-05-01",
            request_end_date="2026-05-03",
            fetched_at="2026-05-04T10:30:00+08:00",
        )


@pytest.mark.parametrize(
    ("row_patch", "expected_message"),
    [
        ({"cal_date": "2026-05-99"}, "calendar_rows\\[0\\]\\.cal_date must be an ISO date"),
        ({"is_open": 2}, "calendar_rows\\[0\\]\\.is_open must be 0 or 1"),
        (
            {"pretrade_date": "2026-05-04"},
            "calendar_rows\\[0\\]\\.pretrade_date must not be after cal_date 2026-05-03",
        ),
    ],
)
def test_build_receipt_rejects_invalid_row_values(
    row_patch: dict[str, object],
    expected_message: str,
) -> None:
    rows = _calendar_rows()
    rows[0] = {**rows[0], **row_patch}

    with pytest.raises(ValueError, match=expected_message):
        build_stock_analysis_calendar_receipt(
            calendar_rows=rows,
            request_start_date="2026-05-01",
            request_end_date="2026-05-03",
            fetched_at="2026-05-04T10:30:00+08:00",
        )


def test_provisional_authority_stays_fail_closed_by_default() -> None:
    receipt = build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
        owner_approval_id="OWNER-123",
    )

    assert receipt["authority_status"] == "provisional"
    assert receipt["owner_approval_id"] == "OWNER-123"
    assert receipt["certification_allowed"] is False
    ok, errors = validate_stock_analysis_calendar_receipt(receipt)
    assert ok is True
    assert errors == ()

    tampered = deepcopy(receipt)
    tampered["certification_allowed"] = True
    ok, errors = validate_stock_analysis_calendar_receipt(tampered)
    assert ok is False
    assert "canonical_receipt_sha256 mismatch" in errors
    assert "provisional authority must stay fail-closed" in errors


def test_build_receipt_rejects_unknown_authority_status() -> None:
    with pytest.raises(
        ValueError,
        match="authority_status must be one of: approved, provisional",
    ):
        build_stock_analysis_calendar_receipt(
            calendar_rows=_calendar_rows(),
            request_start_date="2026-05-01",
            request_end_date="2026-05-03",
            fetched_at="2026-05-04T10:30:00+08:00",
            authority_status="ready",
        )


def test_approved_authority_requires_owner_approval_id() -> None:
    approved = build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
        authority_status="approved",
        owner_approval_id="OWNER-APPROVED-1",
    )
    ok, errors = validate_stock_analysis_calendar_receipt(approved)
    assert approved["certification_allowed"] is True
    assert ok is True
    assert errors == ()

    invalid = deepcopy(approved)
    invalid["owner_approval_id"] = None
    invalid["certification_allowed"] = False
    ok, errors = validate_stock_analysis_calendar_receipt(invalid)
    assert ok is False
    assert "canonical_receipt_sha256 mismatch" in errors
    assert "approved authority missing owner_approval_id" in errors


def test_validate_receipt_rejects_unknown_authority_status() -> None:
    receipt = build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
    )
    receipt["authority_status"] = "ready"

    ok, errors = validate_stock_analysis_calendar_receipt(receipt)

    assert ok is False
    assert errors == ("receipt.authority_status must be one of: approved, provisional",)


@pytest.mark.parametrize(
    ("field_path", "expected_error"),
    [
        ("response_row_count", "receipt.response_row_count must equal 3"),
        ("request.natural_day_count", "receipt.request.natural_day_count must equal 3"),
    ],
)
def test_validate_receipt_rejects_derived_count_tampering(
    field_path: str,
    expected_error: str,
) -> None:
    receipt = build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
    )
    if field_path == "response_row_count":
        receipt["response_row_count"] = 99
    else:
        receipt["request"]["natural_day_count"] = 99

    ok, errors = validate_stock_analysis_calendar_receipt(receipt)

    assert ok is False
    assert errors == (expected_error,)


def test_validate_receipt_detects_hash_tampering_and_row_mismatch() -> None:
    receipt = build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
    )

    tampered = deepcopy(receipt)
    tampered["calendar_rows"][0]["is_open"] = 0
    ok, errors = validate_stock_analysis_calendar_receipt(
        tampered,
        calendar_rows=_calendar_rows(),
    )

    assert ok is False
    assert "canonical_receipt_sha256 mismatch" in errors
    assert "response_sha256 mismatch" in errors
    assert "open_date_axis_sha256 mismatch" in errors
    assert "calendar_rows mismatch" in errors
