import json
import sys

import pytest

from scripts.agent_eval import validate_task as validate_task_cli
from scripts.agent_eval.spec import validate_result_spec, validate_task_spec


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
