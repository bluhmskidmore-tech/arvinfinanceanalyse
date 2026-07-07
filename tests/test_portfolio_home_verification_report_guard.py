from __future__ import annotations

import pytest

from scripts.portfolio_home_verification_report_guard import (
    blocked_verification_report_guard,
)

pytestmark = pytest.mark.governance_meta


def _valid_verifier() -> dict[str, object]:
    return {
        "expected_state": "blocked",
        "verification_status": "matched_expected_blocked_state",
        "all_matched_expected_exit": True,
        "all_matched_expected_when_blocked": True,
        "result_count": 1,
        "results": [
            {
                "expected_state": "blocked",
                "expected_exit": "exit_0",
                "expected_when_blocked": "exit_0",
                "matches_expected_exit": True,
                "matches_expected_when_blocked": True,
            },
        ],
    }


def test_blocked_verification_report_guard_accepts_matched_blocked_report() -> None:
    guard = blocked_verification_report_guard(_valid_verifier())

    assert guard == {
        "valid": True,
        "blockers": [],
        "summary": {
            "expected_state": "blocked",
            "verification_status": "matched_expected_blocked_state",
            "all_matched_expected_exit": True,
            "all_matched_expected_when_blocked": True,
            "result_count": 1,
            "actual_result_count": 1,
        },
    }


def test_blocked_verification_report_guard_blocks_missing_report() -> None:
    guard = blocked_verification_report_guard(None)

    assert guard["valid"] is False
    assert guard["blockers"] == ["verification_report_missing"]
    assert guard["summary"] == {
        "expected_state": None,
        "verification_status": None,
        "all_matched_expected_exit": None,
        "all_matched_expected_when_blocked": None,
        "result_count": None,
        "actual_result_count": 0,
    }


def test_blocked_verification_report_guard_blocks_top_level_and_result_drift() -> None:
    verifier = _valid_verifier()
    verifier["expected_state"] = "full_score"
    verifier["verification_status"] = "mismatch"
    verifier["all_matched_expected_exit"] = False
    verifier["all_matched_expected_when_blocked"] = False
    verifier["result_count"] = 2
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["expected_state"] = "full_score"
    result["expected_exit"] = "exit_0"
    result["expected_when_blocked"] = "exit_nonzero"
    result["matches_expected_exit"] = False
    result["matches_expected_when_blocked"] = False

    guard = blocked_verification_report_guard(verifier)

    assert guard["valid"] is False
    assert guard["blockers"] == [
        "verification_report_expected_state_mismatch",
        "verification_report_status_mismatch",
        "verification_report_expected_exit_not_matched",
        "verification_report_blocked_exit_not_matched",
        "verification_report_result_count_mismatch",
        "verification_report_result_mismatch",
    ]


def test_blocked_verification_report_guard_blocks_empty_and_malformed_results() -> None:
    verifier = _valid_verifier()
    verifier["result_count"] = 0
    verifier["results"] = []

    empty_guard = blocked_verification_report_guard(verifier)

    assert empty_guard["valid"] is False
    assert empty_guard["blockers"] == ["verification_report_results_empty"]

    verifier["result_count"] = 1
    verifier["results"] = ["not-a-result"]

    malformed_guard = blocked_verification_report_guard(verifier)

    assert malformed_guard["valid"] is False
    assert malformed_guard["blockers"] == ["verification_report_result_mismatch"]
