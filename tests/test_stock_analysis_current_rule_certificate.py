from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime

import pytest

from backend.app.governance.stock_analysis_calendar_receipt import (
    EXCHANGE,
    SEMANTICS,
    SOURCE_ID,
    build_stock_analysis_calendar_receipt,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
    build_current_rule_zero_signal_certificate,
    canonical_current_rule_zero_signal_certificate_bytes,
    validate_current_rule_zero_signal_certificate,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _rehash_certificate_payload(certificate: dict[str, object]) -> dict[str, object]:
    rewritten = copy.deepcopy(certificate)
    content = {key: value for key, value in rewritten.items() if key != "payload_sha256"}
    rewritten["payload_sha256"] = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest().upper()
    return rewritten


def _frozen_version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": "rv_candidate_history_current",
        "stock_candidate_selection_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "candidate_outcome_formula_version": "fv_livermore_candidate_forward_close_dual_adjust_v2",
        "execution_formula_version": "fv_livermore_candidate_execution_dual_adjust_v5",
        "matched_baseline_formula_version": "fv_livermore_matched_baseline_v3",
        "market_gate_rule_version": "rv_market_gate_current_v2",
        "signal_confluence_rule_version": "rv_signal_confluence_current_v4",
        "macro_formula_version": "fv_macro_bundle_current_v1",
        "candidate_source_version": "sv_candidate_current",
        "execution_source_version": "sv_execution_current",
        "matched_baseline_source_version": "sv_matched_baseline_current",
        "macro_source_version": "sv_macro_current",
        "theme_overlay_fingerprint": "overlay-fingerprint-1",
        "choice_catalog_fingerprint": "catalog-fingerprint-1",
        "stock_candidate_selection_policy": "exp3b",
        "decision_metric_basis": "net_next_open_adj",
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _runner_result() -> dict[str, object]:
    return {
        "trade_date": "2026-05-02",
        "status": "selection_completed_no_signals",
        "status_reason": "policy_active_zero_signal",
        "requested_as_of_date": "2026-05-02",
        "resolved_as_of_date": "2026-05-02",
        "requested_matches_resolved": True,
        "market_state": "WARM",
        "selection_policy": "exp3b",
        "stock_candidate_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "rule_tuple_matches": True,
        "candidate_count": 0,
        "candidate_item_count": 0,
        "accepted_candidate_count": 0,
        "candidate_count_matches_items": True,
        "candidate_codes": [],
        "accepted_candidate_codes": [],
        "unique_candidate_codes": [],
        "duplicate_candidate_codes": [],
        "stock_candidate_block_reason": None,
        "future_business_date_violations": [],
        "future_availability_violations": [],
    }


def _calendar_rows() -> list[dict[str, object]]:
    return [
        {
            "exchange": EXCHANGE,
            "cal_date": "2026-05-01",
            "is_open": 1,
            "pretrade_date": "2026-04-30",
        },
        {
            "exchange": EXCHANGE,
            "cal_date": "2026-05-02",
            "is_open": 1,
            "pretrade_date": "2026-05-01",
        },
        {
            "exchange": EXCHANGE,
            "cal_date": "2026-05-03",
            "is_open": 0,
            "pretrade_date": "2026-05-02",
        },
    ]


def _calendar_receipt() -> dict[str, object]:
    return build_stock_analysis_calendar_receipt(
        calendar_rows=_calendar_rows(),
        request_start_date="2026-05-01",
        request_end_date="2026-05-03",
        fetched_at="2026-05-04T10:30:00+08:00",
        authority_status="approved",
        owner_approval_id="OWNER-APPROVED-1",
    )


def test_real_calendar_receipt_and_certificate_happy_path() -> None:
    receipt = _calendar_receipt()
    ok, errors = validate_stock_analysis_calendar_receipt(receipt)
    assert ok is True
    assert errors == ()

    certificate = build_current_rule_zero_signal_certificate(
        cohort_id="cohort-202605",
        trade_date="2026-05-02",
        runner_result=_runner_result(),
        calendar_receipt=receipt,
        frozen_version_tuple=_frozen_version_tuple(),
        plan_digest_sha256="A" * 64,
        run_id="run-current-rule-cert-1",
        created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
    )

    assert certificate["status"] == "completed_no_strategy_signals"
    assert certificate["reason_code"] == "policy_active_zero_signal"
    assert certificate["candidate_count"] == 0
    assert certificate["calendar_receipt_sha256"] == receipt["canonical_receipt_sha256"]
    assert certificate["source_evidence"]["calendar"] == {
        "source_id": SOURCE_ID,
        "semantics": SEMANTICS,
        "exchange": EXCHANGE,
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "trade_date": "2026-05-02",
        "certification_allowed": True,
        "authority_status": "approved",
        "request_start_date": "2026-05-01",
        "request_end_date": "2026-05-03",
        "fetched_at": "2026-05-04T02:30:00Z",
    }
    validate_current_rule_zero_signal_certificate(certificate)
    assert canonical_current_rule_zero_signal_certificate_bytes(certificate)


def test_hash_stability_uses_real_calendar_receipt_and_tuple_order_independence() -> None:
    created_at = datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC)
    first = build_current_rule_zero_signal_certificate(
        cohort_id="cohort-202605",
        trade_date="2026-05-02",
        runner_result=_runner_result(),
        calendar_receipt=_calendar_receipt(),
        frozen_version_tuple=_frozen_version_tuple(),
        plan_digest_sha256="B" * 64,
        run_id="run-current-rule-cert-2",
        created_at=created_at,
    )
    reversed_receipt = {
        key: _calendar_receipt()[key]
        for key in reversed(list(_calendar_receipt().keys()))
    }
    reversed_tuple = {
        key: _frozen_version_tuple()[key]
        for key in reversed(list(_frozen_version_tuple().keys()))
    }
    second = build_current_rule_zero_signal_certificate(
        cohort_id="cohort-202605",
        trade_date="2026-05-02",
        runner_result=copy.deepcopy(_runner_result()),
        calendar_receipt=reversed_receipt,
        frozen_version_tuple=reversed_tuple,
        plan_digest_sha256="b" * 64,
        run_id="run-current-rule-cert-2",
        created_at=created_at,
    )

    assert first == second


def test_build_rejects_null_candidate_count_even_when_status_is_zero_signal() -> None:
    runner_result = _runner_result()
    runner_result["candidate_count"] = None

    with pytest.raises(ValueError, match="runner_result.candidate_count"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-02",
            runner_result=runner_result,
            calendar_receipt=_calendar_receipt(),
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="C" * 64,
            run_id="run-current-rule-cert-3",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_build_rejects_policy_inactive_dates() -> None:
    runner_result = _runner_result()
    runner_result["status"] = "selection_policy_inactive"
    runner_result["market_state"] = "OVERHEAT"

    with pytest.raises(ValueError, match="policy-inactive"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-02",
            runner_result=runner_result,
            calendar_receipt=_calendar_receipt(),
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="D" * 64,
            run_id="run-current-rule-cert-4",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_build_rejects_signal_dates_until_execution_and_baseline_are_proven() -> None:
    runner_result = _runner_result()
    runner_result["status"] = "selection_completed_with_signals"
    runner_result["candidate_count"] = 1
    runner_result["candidate_item_count"] = 1
    runner_result["accepted_candidate_count"] = 1
    runner_result["candidate_codes"] = ["000001.SZ"]
    runner_result["accepted_candidate_codes"] = ["000001.SZ"]
    runner_result["unique_candidate_codes"] = ["000001.SZ"]

    with pytest.raises(ValueError, match="execution and matched-baseline proof"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-02",
            runner_result=runner_result,
            calendar_receipt=_calendar_receipt(),
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="E" * 64,
            run_id="run-current-rule-cert-5",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_build_rejects_future_dated_inputs() -> None:
    runner_result = _runner_result()
    runner_result["future_business_date_violations"] = [
        {"path": "payload.as_of_date", "value": "2026-05-03"}
    ]

    with pytest.raises(ValueError, match="future-dated inputs"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-02",
            runner_result=runner_result,
            calendar_receipt=_calendar_receipt(),
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="F" * 64,
            run_id="run-current-rule-cert-6",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_build_rejects_date_mismatch() -> None:
    runner_result = _runner_result()
    runner_result["resolved_as_of_date"] = "2026-05-03"
    runner_result["requested_matches_resolved"] = False

    with pytest.raises(ValueError, match="requested/resolved date"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-02",
            runner_result=runner_result,
            calendar_receipt=_calendar_receipt(),
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="1" * 64,
            run_id="run-current-rule-cert-7",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_build_rejects_closed_trade_day_from_real_calendar_receipt() -> None:
    with pytest.raises(ValueError, match="trade_date row must be open"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-03",
            runner_result={**_runner_result(), "trade_date": "2026-05-03", "requested_as_of_date": "2026-05-03", "resolved_as_of_date": "2026-05-03"},
            calendar_receipt=_calendar_receipt(),
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="2" * 64,
            run_id="run-current-rule-cert-8",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_build_rejects_tampered_calendar_receipt() -> None:
    calendar_receipt = _calendar_receipt()
    calendar_receipt["calendar_rows"][1]["is_open"] = 0

    with pytest.raises(ValueError, match="calendar receipt validation failed: canonical_receipt_sha256 mismatch"):
        build_current_rule_zero_signal_certificate(
            cohort_id="cohort-202605",
            trade_date="2026-05-02",
            runner_result=_runner_result(),
            calendar_receipt=calendar_receipt,
            frozen_version_tuple=_frozen_version_tuple(),
            plan_digest_sha256="3" * 64,
            run_id="run-current-rule-cert-9",
            created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
        )


def test_validate_detects_certificate_tampering() -> None:
    certificate = build_current_rule_zero_signal_certificate(
        cohort_id="cohort-202605",
        trade_date="2026-05-02",
        runner_result=_runner_result(),
        calendar_receipt=_calendar_receipt(),
        frozen_version_tuple=_frozen_version_tuple(),
        plan_digest_sha256="4" * 64,
        run_id="run-current-rule-cert-10",
        created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
    )
    tampered = copy.deepcopy(certificate)
    tampered["candidate_count"] = 1

    with pytest.raises(ValueError, match="payload_sha256 mismatch"):
        validate_current_rule_zero_signal_certificate(tampered)


@pytest.mark.parametrize(
    ("mutator", "expected_message"),
    [
        (
            lambda certificate: certificate.__setitem__("trade_date", "2026-05-03"),
            "runner source evidence trade_date must match certificate trade_date",
        ),
        (
            lambda certificate: certificate["version_tuple"].__setitem__(
                "coverage_authority_mode",
                "tampered-authority-mode",
            ),
            "frozen_version_tuple.coverage_authority_mode must match the approved calendar authority constant",
        ),
        (
            lambda certificate: certificate["source_evidence"]["calendar"].__setitem__(
                "source_id",
                "tampered.source",
            ),
            "calendar source evidence source_id must match the approved calendar authority",
        ),
        (
            lambda certificate: certificate["source_evidence"]["runner"].__setitem__(
                "future_business_date_violation_count",
                1,
            ),
            "runner source evidence future_business_date_violation_count must equal 0",
        ),
    ],
)
def test_validate_rejects_semantic_tampering_even_after_payload_rehash(
    mutator,
    expected_message: str,
) -> None:
    certificate = build_current_rule_zero_signal_certificate(
        cohort_id="cohort-202605",
        trade_date="2026-05-02",
        runner_result=_runner_result(),
        calendar_receipt=_calendar_receipt(),
        frozen_version_tuple=_frozen_version_tuple(),
        plan_digest_sha256="5" * 64,
        run_id="run-current-rule-cert-11",
        created_at=datetime(2026, 8, 21, 5, 6, 7, tzinfo=UTC),
    )
    tampered = copy.deepcopy(certificate)
    mutator(tampered)
    tampered = _rehash_certificate_payload(tampered)

    with pytest.raises(ValueError, match=expected_message):
        validate_current_rule_zero_signal_certificate(tampered)
