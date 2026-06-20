from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "business": 40,
    "page": 20,
    "verification": 20,
    "diff": 20,
}

PASS_THRESHOLD = 90


def evaluate_result(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Score an agent result against a MOSS development task.

    This evaluator is intentionally small: Polar or a local runner can emit a
    JSON result, and this function turns it into a stable pass/fail scorecard.
    """

    hard_failures: list[str] = []
    warnings: list[str] = []

    business_ratio = _passed_ratio(
        task.get("business_gates", []),
        result.get("business_gates", {}),
        "Business gate failed",
        hard_failures,
    )
    page_ratio = _passed_ratio(
        task.get("page_gates", []),
        result.get("page_gates", {}),
        "Page gate failed",
        hard_failures,
    )
    verification_ratio = _verification_ratio(task, result, hard_failures)
    diff_ratio = _diff_ratio(task, result, hard_failures, warnings)

    breakdown = {
        "business": round(DEFAULT_WEIGHTS["business"] * business_ratio, 2),
        "page": round(DEFAULT_WEIGHTS["page"] * page_ratio, 2),
        "verification": round(DEFAULT_WEIGHTS["verification"] * verification_ratio, 2),
        "diff": round(DEFAULT_WEIGHTS["diff"] * diff_ratio, 2),
    }
    score = round(sum(breakdown.values()), 2)

    return {
        "task_id": task.get("id"),
        "status": "pass" if score >= PASS_THRESHOLD and not hard_failures else "fail",
        "score": score,
        "breakdown": breakdown,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }


def _passed_ratio(
    required: list[str],
    actual: dict[str, Any],
    failure_prefix: str,
    hard_failures: list[str],
) -> float:
    if not required:
        return 1.0

    passed = 0
    for name in required:
        if _is_passed(actual.get(name)):
            passed += 1
        else:
            hard_failures.append(f"{failure_prefix}: {name}")
    return passed / len(required)


def _verification_ratio(
    task: dict[str, Any],
    result: dict[str, Any],
    hard_failures: list[str],
) -> float:
    required_evidence = task.get("required_evidence", [])
    required_checks = task.get("checks", [])
    total = len(required_evidence) + len(required_checks)
    if total == 0:
        return 1.0

    passed = 0
    evidence_used = set(result.get("evidence", []))
    check_results = result.get("checks", {})

    for evidence in required_evidence:
        if evidence in evidence_used:
            passed += 1
        else:
            hard_failures.append(f"Missing required evidence: {evidence}")

    for check in required_checks:
        if _is_passed(check_results.get(check)):
            passed += 1
        else:
            hard_failures.append(f"Required check failed: {check}")

    return passed / total


def _diff_ratio(
    task: dict[str, Any],
    result: dict[str, Any],
    hard_failures: list[str],
    warnings: list[str],
) -> float:
    changed_files = result.get("changed_files", [])
    forbidden = task.get("forbidden", [])
    allowed_scope = task.get("allowed_scope", [])

    changed_forbidden = False
    changed_out_of_scope = False

    for path in changed_files:
        if any(_path_matches(path, blocked) for blocked in forbidden):
            hard_failures.append(f"Forbidden path changed: {path}")
            changed_forbidden = True
        if allowed_scope and not any(_path_matches(path, allowed) for allowed in allowed_scope):
            warnings.append(f"Out-of-scope path changed: {path}")
            changed_out_of_scope = True

    if changed_forbidden:
        return 0.0
    if changed_out_of_scope:
        return 0.0
    return 1.0


def _is_passed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"pass", "passed", "ok", "success", "true"}
    return False


def _path_matches(path: str, pattern: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_pattern = _normalize_path(pattern)
    if not normalized_pattern:
        return False
    if pattern.replace("\\", "/").endswith("/"):
        return normalized_path.startswith(normalized_pattern.rstrip("/") + "/")
    return normalized_path == normalized_pattern or normalized_path.startswith(normalized_pattern.rstrip("/") + "/")


def _normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").strip().lstrip("./").lower()

