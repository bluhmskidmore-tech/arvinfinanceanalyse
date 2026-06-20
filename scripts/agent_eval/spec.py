from __future__ import annotations

from typing import Any


TASK_LIST_FIELDS = [
    "required_evidence",
    "checks",
    "business_gates",
    "page_gates",
    "allowed_scope",
    "forbidden",
]

RESULT_LIST_FIELDS = [
    "evidence",
    "changed_files",
]

RESULT_STATUS_FIELDS = [
    "checks",
    "business_gates",
    "page_gates",
]

PASS_FAIL_VALUES = {
    "fail",
    "failed",
    "false",
    "no",
    "ok",
    "pass",
    "passed",
    "success",
    "true",
    "yes",
}


def validate_task_spec(task: dict[str, Any]) -> dict[str, Any]:
    _require_object(task, "Task")
    _require_string(task, "id", "Task")

    for field in TASK_LIST_FIELDS:
        _require_string_list(task, field, "Task")

    for field in ["page", "goal"]:
        if field in task and not isinstance(task[field], str):
            raise ValueError(f"Task field '{field}' must be a string when present")

    return task


def validate_result_spec(result: dict[str, Any]) -> dict[str, Any]:
    _require_object(result, "Result")

    for field in RESULT_LIST_FIELDS:
        _require_string_list(result, field, "Result")

    for field in RESULT_STATUS_FIELDS:
        _require_status_map(result, field)

    return result


def _require_object(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} spec must be a JSON object")


def _require_string(mapping: dict[str, Any], field: str, label: str) -> None:
    if field not in mapping:
        raise ValueError(f"{label} field '{field}' is required")
    if not isinstance(mapping[field], str):
        raise ValueError(f"{label} field '{field}' must be a string")


def _require_string_list(mapping: dict[str, Any], field: str, label: str) -> None:
    if field not in mapping:
        raise ValueError(f"{label} field '{field}' is required")
    if not isinstance(mapping[field], list) or not all(isinstance(item, str) for item in mapping[field]):
        raise ValueError(f"{label} field '{field}' must be a list of strings")


def _require_status_map(mapping: dict[str, Any], field: str) -> None:
    if field not in mapping:
        raise ValueError(f"Result field '{field}' is required")
    value = mapping[field]
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"Result field '{field}' must be an object with string keys")
    if not all(_is_bool_or_pass_fail(status) for status in value.values()):
        raise ValueError(f"Result field '{field}' values must be bool or pass/fail-like strings")


def _is_bool_or_pass_fail(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().lower() in PASS_FAIL_VALUES
    return False

