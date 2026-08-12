from __future__ import annotations

from typing import Any


MEASUREMENT_SOURCE = "scripts/agent_eval/collect.py"
MEASUREMENT_SCHEMA_VERSION = 1

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

TASK_STRING_MAP_FIELDS = [
    "gate_probes",
    "evidence_probes",
]

# Probe commands must stay inside the two runners the harness trusts; anything
# else (shell scripts, inline python, node one-liners) could fabricate a green
# gate without exercising a reviewed test file.
GATE_PROBE_COMMAND_PREFIXES = (
    "python -m pytest ",
    "npm --prefix frontend run ",
)

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

    if not task["allowed_scope"]:
        raise ValueError(
            "Task field 'allowed_scope' must be a non-empty list of strings: "
            "an empty scope disables out-of-scope detection in scoring"
        )

    for field in ["page", "goal"]:
        if field in task and not isinstance(task[field], str):
            raise ValueError(f"Task field '{field}' must be a string when present")

    for field in TASK_STRING_MAP_FIELDS:
        if field in task:
            _require_string_map(task, field, "Task")

    if "probe_protected_paths" in task:
        _require_string_list(task, "probe_protected_paths", "Task")

    if "metric_ids" in task:
        _require_string_list(task, "metric_ids", "Task")
        if not task["metric_ids"]:
            raise ValueError("Task field 'metric_ids' must be a non-empty list of strings when present")

    _require_known_gate_probes(task)
    _require_whitelisted_probe_commands(task)

    return task


def validate_measured_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reject a result that was not produced by the measurement collector.

    Guards against the default failure mode of an agent hand-writing a result
    file: without this, every gate reverts to self-report.
    """

    validate_result_spec(result)

    measurement = result.get("measurement")
    if not isinstance(measurement, dict):
        raise ValueError("Result field 'measurement' is required when measured results are enforced")

    if measurement.get("source") != MEASUREMENT_SOURCE:
        raise ValueError(f"Result measurement must be produced by '{MEASUREMENT_SOURCE}'")

    if measurement.get("schema_version") != MEASUREMENT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported measurement schema_version: {measurement.get('schema_version')!r} "
            f"(expected {MEASUREMENT_SCHEMA_VERSION})"
        )

    integrity = measurement.get("integrity")
    if not isinstance(integrity, dict):
        raise ValueError("Result measurement is missing the 'integrity' block")
    if not integrity.get("trusted"):
        violations = integrity.get("violations") or ["unspecified integrity violation"]
        raise ValueError("Measurement is not trustworthy: " + "; ".join(str(item) for item in violations))

    return result


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


def _require_string_map(mapping: dict[str, Any], field: str, label: str) -> None:
    value = mapping[field]
    if not isinstance(value, dict):
        raise ValueError(f"{label} field '{field}' must be an object")
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"{label} field '{field}' must map strings to strings")


def _require_known_gate_probes(task: dict[str, Any]) -> None:
    """A probe keyed on an unknown gate would silently leave that gate unmeasured."""

    declared_gates = set(task.get("business_gates", [])) | set(task.get("page_gates", []))
    unknown_gates = sorted(set(task.get("gate_probes", {})) - declared_gates)
    if unknown_gates:
        raise ValueError(f"Task field 'gate_probes' references undeclared gates: {', '.join(unknown_gates)}")

    unknown_evidence = sorted(set(task.get("evidence_probes", {})) - set(task.get("required_evidence", [])))
    if unknown_evidence:
        raise ValueError(
            f"Task field 'evidence_probes' references undeclared evidence: {', '.join(unknown_evidence)}"
        )


def _require_whitelisted_probe_commands(task: dict[str, Any]) -> None:
    """A probe command outside the trusted runner whitelist could be any script."""

    violations = sorted(
        command
        for command in task.get("gate_probes", {}).values()
        if not command.startswith(GATE_PROBE_COMMAND_PREFIXES)
    )
    if violations:
        allowed = " or ".join(f"'{prefix}'" for prefix in GATE_PROBE_COMMAND_PREFIXES)
        raise ValueError(
            f"Task field 'gate_probes' commands must start with {allowed}; "
            f"violating commands: {'; '.join(violations)}"
        )


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

