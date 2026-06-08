from __future__ import annotations


EXPECTED_BLOCKED_STATE = "blocked"
EXPECTED_BLOCKED_STATUS = "matched_expected_blocked_state"


def _result_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _summary(verifier: dict[str, object], result_count: int) -> dict[str, object]:
    return {
        "expected_state": verifier.get("expected_state"),
        "verification_status": verifier.get("verification_status"),
        "all_matched_expected_exit": verifier.get("all_matched_expected_exit"),
        "all_matched_expected_when_blocked": verifier.get(
            "all_matched_expected_when_blocked",
        ),
        "result_count": verifier.get("result_count"),
        "actual_result_count": result_count,
    }


def blocked_verification_report_guard(verifier: object) -> dict[str, object]:
    if not isinstance(verifier, dict):
        return {
            "valid": False,
            "blockers": ["verification_report_missing"],
            "summary": _summary({}, 0),
        }

    blockers: list[str] = []
    verification_results = _result_list(verifier.get("results"))

    if verifier.get("expected_state") != EXPECTED_BLOCKED_STATE:
        blockers.append("verification_report_expected_state_mismatch")
    if verifier.get("verification_status") != EXPECTED_BLOCKED_STATUS:
        blockers.append("verification_report_status_mismatch")
    if verifier.get("all_matched_expected_exit") is not True:
        blockers.append("verification_report_expected_exit_not_matched")
    if verifier.get("all_matched_expected_when_blocked") is not True:
        blockers.append("verification_report_blocked_exit_not_matched")
    if verifier.get("result_count") != len(verification_results):
        blockers.append("verification_report_result_count_mismatch")
    if not verification_results:
        blockers.append("verification_report_results_empty")
    elif any(
        not isinstance(result, dict)
        or result.get("expected_state") != EXPECTED_BLOCKED_STATE
        or result.get("expected_exit") != result.get("expected_when_blocked")
        or result.get("matches_expected_exit") is not True
        or result.get("matches_expected_when_blocked") is not True
        for result in verification_results
    ):
        blockers.append("verification_report_result_mismatch")

    return {
        "valid": not blockers,
        "blockers": blockers,
        "summary": _summary(verifier, len(verification_results)),
    }
