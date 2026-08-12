import json
import subprocess
import sys

import pytest

from scripts.agent_eval import validate_task as validate_task_cli
from scripts.agent_eval.collect import (
    CommandOutcome,
    collect_changed_files,
    collect_measured_result,
    compute_task_digest,
    derive_probe_paths,
)
from scripts.agent_eval.reward import evaluate_result
from scripts.agent_eval.spec import validate_measured_result, validate_task_spec

TASK = {
    "id": "probe_demo_001",
    "page": "ledger-pnl",
    "goal": "Demonstrate measured gates.",
    "required_evidence": ["moss-metric-contracts"],
    "evidence_probes": {"moss-metric-contracts": "evidence/contracts.json"},
    "checks": ["run-unit-tests"],
    "business_gates": ["unit_consistency", "date_semantics"],
    "page_gates": ["no_console_errors"],
    "gate_probes": {"unit_consistency": "python -m pytest tests/probe_unit_consistency.py -q"},
    "allowed_scope": ["frontend/src/features/ledger-pnl/"],
    "forbidden": ["frontend/src/api/client.ts"],
    "gate_probe_gaps": {"date_semantics": "Needs a trade-date basis assertion."},
}


def _runner(exit_codes=None):
    codes = exit_codes or {}
    calls = []

    def run(command, cwd, timeout_seconds):
        calls.append(command)
        return CommandOutcome(exit_code=codes.get(command, 0), duration_ms=1)

    run.calls = calls
    return run


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relative_path)
    _git(repo, "commit", "-m", f"add {relative_path}")
    return path


@pytest.fixture
def git_repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "harness@example.com")
    _git(tmp_path, "config", "user.name", "harness")
    _commit(tmp_path, "seed.txt", "seed\n")
    return tmp_path


def test_gate_without_probe_is_scored_as_failed_not_assumed_passing(git_repo):
    result = collect_measured_result(TASK, repo_root=git_repo, run_command=_runner())

    assert result["business_gates"]["unit_consistency"] == "passed"
    assert result["business_gates"]["date_semantics"] == "failed"
    assert result["page_gates"]["no_console_errors"] == "failed"
    assert result["measurement"]["unprobed_gates"] == ["date_semantics", "no_console_errors"]
    assert (
        result["measurement"]["unprobed_gate_reasons"]["date_semantics"]
        == "Needs a trade-date basis assertion."
    )


def test_gate_and_check_status_come_from_process_exit_codes(git_repo):
    runner = _runner({"python -m pytest tests/probe_unit_consistency.py -q": 1, "run-unit-tests": 2})

    result = collect_measured_result(TASK, repo_root=git_repo, run_command=runner)

    assert result["business_gates"]["unit_consistency"] == "failed"
    assert result["checks"]["run-unit-tests"] == "failed"
    failed_commands = {entry["command"]: entry["exit_code"] for entry in result["measurement"]["commands"]}
    assert failed_commands["run-unit-tests"] == 2


def test_repeated_probe_command_is_executed_once(git_repo):
    task = dict(TASK, gate_probes={"unit_consistency": "shared-probe", "date_semantics": "shared-probe"})
    runner = _runner()

    collect_measured_result(task, repo_root=git_repo, run_command=runner)

    assert runner.calls.count("shared-probe") == 1


def test_evidence_requires_a_non_empty_declared_artifact(git_repo):
    empty_artifact = git_repo / "evidence" / "contracts.json"
    empty_artifact.parent.mkdir(parents=True)
    empty_artifact.write_text("", encoding="utf-8")

    result = collect_measured_result(TASK, repo_root=git_repo, run_command=_runner())
    assert result["evidence"] == []
    assert result["measurement"]["evidence_artifacts"][0]["status"] == "empty"

    empty_artifact.write_text(
        json.dumps({"source": "moss-metric-contracts", "metric_id": "ledger_pnl_net_interest"}),
        encoding="utf-8",
    )

    result = collect_measured_result(TASK, repo_root=git_repo, run_command=_runner())
    assert result["evidence"] == ["moss-metric-contracts"]
    assert result["measurement"]["evidence_artifacts"][0]["status"] == "present"


@pytest.mark.parametrize(
    ("content", "expected_status"),
    [
        pytest.param("not json", "invalid_json", id="unparseable-text"),
        pytest.param("[1, 2]", "invalid_json", id="json-but-not-an-object"),
        pytest.param(
            json.dumps({"metric_id": "ledger_pnl_net_interest"}),
            "missing_source",
            id="object-without-source",
        ),
        pytest.param(
            json.dumps({"source": "", "metric_id": "ledger_pnl_net_interest"}),
            "missing_source",
            id="object-with-empty-source",
        ),
    ],
)
def test_evidence_artifact_failing_the_minimal_schema_is_not_counted(
    git_repo, content, expected_status
):
    artifact = git_repo / "evidence" / "contracts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(content, encoding="utf-8")

    result = collect_measured_result(TASK, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == []
    entry = result["measurement"]["evidence_artifacts"][0]
    assert entry["status"] == expected_status
    assert entry["bytes"] > 0
    assert "source" not in entry


def test_evidence_artifact_with_a_source_is_present_and_records_the_source(git_repo):
    artifact = git_repo / "evidence" / "contracts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps({"source": "moss-metric-contracts", "metric_id": "ledger_pnl_net_interest"}),
        encoding="utf-8",
    )

    result = collect_measured_result(TASK, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == ["moss-metric-contracts"]
    entry = result["measurement"]["evidence_artifacts"][0]
    assert entry["status"] == "present"
    assert entry["source"] == "moss-metric-contracts"
    assert entry["bytes"] > 0


def test_changed_files_include_untracked_and_modified_paths(git_repo):
    (git_repo / "seed.txt").write_text("changed\n", encoding="utf-8")
    nested = git_repo / "frontend" / "src" / "features" / "ledger-pnl"
    nested.mkdir(parents=True)
    (nested / "LedgerPnlPage.tsx").write_text("export const x = 1;\n", encoding="utf-8")

    changed = collect_changed_files(git_repo)

    assert "seed.txt" in changed
    assert "frontend/src/features/ledger-pnl/LedgerPnlPage.tsx" in changed


def test_modifying_a_committed_task_definition_marks_the_measurement_untrusted(git_repo):
    task_path = _commit(git_repo, "scripts/agent_eval/tasks/probe_demo_001.json", json.dumps(TASK))
    task_path.write_text(json.dumps(dict(TASK, business_gates=[])), encoding="utf-8")

    result = collect_measured_result(
        TASK, repo_root=git_repo, task_path=task_path, run_command=_runner()
    )

    integrity = result["measurement"]["integrity"]
    assert integrity["trusted"] is False
    assert "Task definition modified during the run" in integrity["violations"][0]
    with pytest.raises(ValueError, match="Measurement is not trustworthy"):
        validate_measured_result(result)


def test_a_new_untracked_task_definition_is_not_treated_as_tampering(git_repo):
    task_path = git_repo / "new_task.json"
    task_path.write_text(json.dumps(TASK), encoding="utf-8")

    result = collect_measured_result(
        TASK, repo_root=git_repo, task_path=task_path, run_command=_runner()
    )

    assert result["measurement"]["integrity"]["trusted"] is True


def test_task_digest_mismatch_is_detected_even_without_git_tracking(git_repo):
    task_path = git_repo / "new_task.json"
    task_path.write_text(json.dumps(TASK), encoding="utf-8")
    digest_before = compute_task_digest(task_path)
    task_path.write_text(json.dumps(dict(TASK, business_gates=[])), encoding="utf-8")

    result = collect_measured_result(
        TASK,
        repo_root=git_repo,
        task_path=task_path,
        expected_task_digest=digest_before,
        run_command=_runner(),
    )

    integrity = result["measurement"]["integrity"]
    assert integrity["trusted"] is False
    assert integrity["task_digest_verified"] is False
    assert "digest changed during the run" in integrity["violations"][0]


def test_modifying_a_probe_target_marks_the_measurement_untrusted(git_repo):
    probe_target = _commit(
        git_repo, "tests/test_no_finance_logic_in_frontend.py", "def test_real():\n    assert True\n"
    )
    probe_target.write_text("def test_noop():\n    pass\n", encoding="utf-8")
    task = dict(TASK, probe_protected_paths=["tests/test_no_finance_logic_in_frontend.py"])

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    integrity = result["measurement"]["integrity"]
    assert integrity["trusted"] is False
    assert "Gate probe target modified during the run" in integrity["violations"][0]


def test_self_reported_result_is_rejected_when_measurement_is_enforced():
    self_reported = {
        "evidence": ["moss-metric-contracts"],
        "checks": {"run-unit-tests": "passed"},
        "business_gates": {"unit_consistency": True, "date_semantics": True},
        "page_gates": {"no_console_errors": True},
        "changed_files": ["frontend/src/features/ledger-pnl/LedgerPnlPage.tsx"],
    }

    assert evaluate_result(TASK, self_reported)["score"] == 100

    with pytest.raises(ValueError, match="'measurement' is required"):
        validate_measured_result(self_reported)


def test_measured_result_rejects_a_forged_measurement_source():
    forged = {
        "evidence": [],
        "checks": {},
        "business_gates": {},
        "page_gates": {},
        "changed_files": [],
        "measurement": {"source": "agent", "schema_version": 1, "integrity": {"trusted": True}},
    }

    with pytest.raises(ValueError, match="must be produced by"):
        validate_measured_result(forged)


def test_task_spec_rejects_a_probe_keyed_on_an_undeclared_gate():
    task = dict(TASK, gate_probes={"unit_consitency": "probe"})

    with pytest.raises(ValueError, match="undeclared gates: unit_consitency"):
        validate_task_spec(task)


def test_cli_measure_mode_scores_from_observed_state(git_repo, monkeypatch, capsys):
    task_path = git_repo / "task.json"
    task_path.write_text(json.dumps(TASK), encoding="utf-8")
    scorecard_path = git_repo / "scorecard.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_task.py",
            "--task",
            str(task_path),
            "--measure",
            "--repo-root",
            str(git_repo),
            "--out",
            str(scorecard_path),
        ],
    )

    assert validate_task_cli.main() == 1

    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    assert scorecard["measured"] is True
    assert "Business gate failed: date_semantics" in scorecard["hard_failures"]
    assert "no probe is declared" in capsys.readouterr().err


def test_cli_rejects_mixing_measure_and_result_inputs(monkeypatch, tmp_path, capsys):
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(TASK), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["validate_task.py", "--task", str(task_path), "--measure", "--result", str(task_path)],
    )

    assert validate_task_cli.main() == 2
    assert "exactly one of --measure or --result" in capsys.readouterr().err


def test_derive_probe_paths_extracts_only_explicit_repo_test_paths():
    task = {
        "gate_probes": {
            "a": "python -m pytest tests/test_alpha.py backend\\tests\\test_beta.py -q",
            "b": "npx vitest run frontend/src/test/msw/Ledger-Pnl.handlers.ts",
            "c": "npm --prefix frontend run test -- LedgerPnlUnitContract",
        }
    }

    assert derive_probe_paths(task) == [
        "backend/tests/test_beta.py",
        "frontend/src/test/msw/ledger-pnl.handlers.ts",
        "tests/test_alpha.py",
    ]
    assert derive_probe_paths({}) == []


def test_modifying_an_undeclared_probe_target_is_caught_by_derived_protection(git_repo):
    probe_target = _commit(
        git_repo, "tests/test_no_finance_logic_in_frontend.py", "def test_real():\n    assert True\n"
    )
    probe_target.write_text("def test_noop():\n    pass\n", encoding="utf-8")
    task = dict(
        TASK,
        gate_probes={"unit_consistency": "python -m pytest tests/test_no_finance_logic_in_frontend.py -q"},
    )
    assert "probe_protected_paths" not in task

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    integrity = result["measurement"]["integrity"]
    assert integrity["trusted"] is False
    assert (
        "Gate probe target modified during the run: tests/test_no_finance_logic_in_frontend.py"
        in integrity["violations"]
    )
    assert "tests/test_no_finance_logic_in_frontend.py" in integrity["protected_paths"]
    with pytest.raises(ValueError, match="Measurement is not trustworthy"):
        validate_measured_result(result)


def test_filter_word_probe_is_recorded_underivable_without_false_violation(git_repo):
    (git_repo / "seed.txt").write_text("changed\n", encoding="utf-8")
    command = "npm --prefix frontend run test -- LedgerPnlUnitContract"
    task = dict(TASK, gate_probes={"unit_consistency": command})

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    integrity = result["measurement"]["integrity"]
    assert integrity["trusted"] is True
    assert integrity["violations"] == []
    assert integrity["underivable_probe_commands"] == [command]
    assert integrity["protected_paths"] == []


def test_protected_paths_merge_manual_and_derived_without_duplicates(git_repo):
    task = dict(
        TASK,
        gate_probes={
            "unit_consistency": "python -m pytest tests/test_no_finance_logic_in_frontend.py -q",
            "date_semantics": "npx vitest run frontend/src/test/msw/ledger-pnl.handlers.ts",
        },
        probe_protected_paths=[
            "tests/test_no_finance_logic_in_frontend.py",
            "TESTS\\Test_Extra_Fixture.py",
        ],
    )

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    integrity = result["measurement"]["integrity"]
    assert integrity["protected_paths"] == [
        "frontend/src/test/msw/ledger-pnl.handlers.ts",
        "tests/test_extra_fixture.py",
        "tests/test_no_finance_logic_in_frontend.py",
    ]
    assert integrity["underivable_probe_commands"] == []
    assert integrity["trusted"] is True
