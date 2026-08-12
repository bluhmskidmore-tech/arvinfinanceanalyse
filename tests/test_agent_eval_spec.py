import json
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval import validate_task as validate_task_cli
from scripts.agent_eval.spec import validate_result_spec, validate_task_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = REPO_ROOT / "scripts" / "agent_eval" / "tasks"
METRIC_DICTIONARY_PATH = REPO_ROOT / "docs" / "metric_dictionary.md"

VALID_TASK = {
    "id": "ledger_pnl_unit_mismatch_001",
    "page": "ledger-pnl",
    "goal": "Fix a unit mismatch.",
    "required_evidence": ["moss-metric-contracts"],
    "checks": ["npm run test -- LedgerPnl"],
    "business_gates": ["unit_consistency"],
    "page_gates": ["no_console_errors"],
    "allowed_scope": ["frontend/src/features/ledger-pnl/"],
    "forbidden": ["frontend/src/api/client.ts"],
}

VALID_RESULT = {
    "evidence": ["moss-metric-contracts"],
    "checks": {"npm run test -- LedgerPnl": "passed"},
    "business_gates": {"unit_consistency": True},
    "page_gates": {"no_console_errors": "ok"},
    "changed_files": ["frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx"],
}


def test_validate_task_spec_accepts_valid_moss_task():
    assert validate_task_spec(VALID_TASK) == VALID_TASK


def test_validate_task_spec_rejects_missing_required_field():
    task = dict(VALID_TASK)
    task.pop("id")

    with pytest.raises(ValueError, match="Task field 'id' is required"):
        validate_task_spec(task)


def test_validate_task_spec_rejects_non_string_list_items():
    task = dict(VALID_TASK)
    task["checks"] = ["npm run test -- LedgerPnl", 123]

    with pytest.raises(ValueError, match="Task field 'checks' must be a list of strings"):
        validate_task_spec(task)


def test_validate_task_spec_rejects_empty_allowed_scope():
    task = dict(VALID_TASK, allowed_scope=[])

    with pytest.raises(ValueError, match="Task field 'allowed_scope' must be a non-empty list"):
        validate_task_spec(task)


def test_validate_task_spec_rejects_gate_probe_command_outside_whitelist():
    task = dict(VALID_TASK, gate_probes={"unit_consistency": "bash scripts/fake_green_gate.sh"})

    with pytest.raises(ValueError) as excinfo:
        validate_task_spec(task)

    message = str(excinfo.value)
    assert "bash scripts/fake_green_gate.sh" in message
    assert "'python -m pytest '" in message
    assert "'npm --prefix frontend run '" in message


def test_validate_task_spec_accepts_whitelisted_gate_probe_commands():
    task = dict(
        VALID_TASK,
        business_gates=["unit_consistency", "no_frontend_official_metric_recalculation"],
        gate_probes={
            "unit_consistency": "npm --prefix frontend run test -- LedgerPnlUnitContract",
            "no_frontend_official_metric_recalculation": "python -m pytest tests/test_no_finance_logic_in_frontend.py -q",
        },
    )

    assert validate_task_spec(task) == task


@pytest.mark.parametrize(
    "metric_ids",
    [
        pytest.param("MTR-LPN-001", id="not-a-list"),
        pytest.param([], id="empty-list"),
        pytest.param(["MTR-LPN-001", 123], id="non-string-item"),
    ],
)
def test_validate_task_spec_rejects_malformed_metric_ids(metric_ids):
    task = dict(VALID_TASK, metric_ids=metric_ids)

    with pytest.raises(ValueError, match="metric_ids"):
        validate_task_spec(task)


def test_validate_task_spec_accepts_non_empty_string_metric_ids():
    task = dict(VALID_TASK, metric_ids=["MTR-LPN-001", "MTR-LPN-002", "MTR-LPN-003"])

    assert validate_task_spec(task) == task


def test_task_manifest_is_spec_valid_and_metric_ids_exist_in_metric_dictionary():
    """Every shipped task must pass the spec, and every declared metric id must
    resolve against the governance metric dictionary, so a task cannot bind
    gates to a metric that governance has never registered."""

    task_paths = sorted(TASKS_DIR.glob("*.json"))
    assert task_paths, f"No task specs found under {TASKS_DIR}"

    dictionary_text = METRIC_DICTIONARY_PATH.read_text(encoding="utf-8")
    for task_path in task_paths:
        task = json.loads(task_path.read_text(encoding="utf-8"))
        validate_task_spec(task)
        for metric_id in task.get("metric_ids", []):
            assert metric_id in dictionary_text, (
                f"{task_path.name} declares metric id '{metric_id}' "
                "which does not appear in docs/metric_dictionary.md"
            )


def test_validate_result_spec_accepts_valid_result_status_values():
    assert validate_result_spec(VALID_RESULT) == VALID_RESULT


def test_validate_result_spec_rejects_bad_check_status_value():
    result = dict(VALID_RESULT)
    result["checks"] = {"npm run test -- LedgerPnl": "maybe"}

    with pytest.raises(ValueError, match="Result field 'checks' values must be bool or pass/fail-like strings"):
        validate_result_spec(result)


def test_validate_task_cli_rejects_malformed_result_before_scoring(tmp_path, monkeypatch, capsys):
    task_path = tmp_path / "task.json"
    result_path = tmp_path / "result.json"
    task_path.write_text(json.dumps(VALID_TASK), encoding="utf-8")
    malformed_result = dict(VALID_RESULT)
    malformed_result.pop("changed_files")
    result_path.write_text(json.dumps(malformed_result), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_task.py",
            "--task",
            str(task_path),
            "--result",
            str(result_path),
        ],
    )

    assert validate_task_cli.main() != 0
    assert "Result field 'changed_files' is required" in capsys.readouterr().err
