import hashlib
import json
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval import validate_task as validate_task_cli
from scripts.agent_eval.collect import (
    CommandOutcome,
    collect_changed_files,
    collect_measured_result,
    compute_task_digest,
    derive_probe_paths,
    verify_evidence_receipt,
)
from scripts.agent_eval.receipts import append_receipt, canonical_json_bytes, digest_params
from scripts.agent_eval.reward import evaluate_result
from scripts.agent_eval.spec import validate_measured_result, validate_task_spec
from scripts.mcp.moss_project_mcp import McpProvider, ProjectMcpServer

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


# --- Call-receipt cross-checking (opt-in via `evidence_receipt_log`) ---

RECEIPT_TASK = dict(TASK, evidence_receipt_log=".codex-tmp/receipts.jsonl")

_RECEIPT_LINE = json.dumps(
    {
        "server": "moss-metric-contracts",
        "tool": "search_contract_docs",
        "params_digest": "d0",
        "response_sha256": "abc123",
        "recorded_at": "2026-08-12T00:00:00+00:00",
    }
)


def _write_artifact(repo, payload):
    artifact = repo / "evidence" / "contracts.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    return artifact


def test_task_without_receipt_optin_keeps_minimal_schema_behavior(git_repo):
    _write_artifact(
        git_repo,
        {"source": "moss-metric-contracts", "receipt": {"response_sha256": "never-checked"}},
    )
    assert "evidence_receipt_log" not in TASK

    result = collect_measured_result(TASK, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == ["moss-metric-contracts"]
    entry = result["measurement"]["evidence_artifacts"][0]
    assert entry["status"] == "present"
    assert "receipt_status" not in entry


def test_receipt_backed_artifact_is_present_when_log_has_a_matching_record(git_repo):
    response_bytes = canonical_json_bytes({"content": [{"type": "text", "text": "net_interest"}]})
    append_receipt(
        git_repo / ".codex-tmp" / "receipts.jsonl",
        server="moss-metric-contracts",
        tool="search_contract_docs",
        params_digest=digest_params({"query": "net interest"}),
        response_bytes=response_bytes,
    )
    _write_artifact(
        git_repo,
        {
            "source": "moss-metric-contracts",
            "metric_id": "ledger_pnl_net_interest",
            "receipt": {"response_sha256": hashlib.sha256(response_bytes).hexdigest()},
        },
    )

    result = collect_measured_result(RECEIPT_TASK, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == ["moss-metric-contracts"]
    entry = result["measurement"]["evidence_artifacts"][0]
    assert entry["status"] == "present"
    assert entry["receipt_status"] == "matched"
    assert entry["source"] == "moss-metric-contracts"


def test_receipt_sha_mismatch_is_recorded_and_not_counted(git_repo):
    append_receipt(
        git_repo / ".codex-tmp" / "receipts.jsonl",
        server="moss-metric-contracts",
        tool="search_contract_docs",
        params_digest=digest_params({"query": "net interest"}),
        response_bytes=b"the real response",
    )
    _write_artifact(
        git_repo,
        {
            "source": "moss-metric-contracts",
            "receipt": {"response_sha256": hashlib.sha256(b"a forged response").hexdigest()},
        },
    )

    result = collect_measured_result(RECEIPT_TASK, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == []
    entry = result["measurement"]["evidence_artifacts"][0]
    assert entry["status"] == "receipt_mismatch"
    assert entry["receipt_status"] == "receipt_mismatch"
    assert "source" not in entry


def test_self_declared_source_without_receipt_no_longer_counts_when_opted_in(git_repo):
    append_receipt(
        git_repo / ".codex-tmp" / "receipts.jsonl",
        server="moss-metric-contracts",
        tool="search_contract_docs",
        params_digest=digest_params({"query": "net interest"}),
        response_bytes=b"a real call happened",
    )
    _write_artifact(
        git_repo,
        {"source": "moss-metric-contracts", "metric_id": "ledger_pnl_net_interest"},
    )

    result = collect_measured_result(RECEIPT_TASK, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == []
    entry = result["measurement"]["evidence_artifacts"][0]
    assert entry["status"] == "receipt_mismatch"
    assert entry["receipt_status"] == "receipt_mismatch"


def test_declared_but_missing_receipt_log_fails_all_evidence_closed(git_repo):
    task = dict(
        TASK,
        required_evidence=["moss-metric-contracts", "moss-lineage-evidence"],
        evidence_probes={"moss-metric-contracts": "evidence/contracts.json"},
        evidence_receipt_log="receipts/absent.jsonl",
    )
    _write_artifact(git_repo, {"source": "moss-metric-contracts"})

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    assert result["evidence"] == []
    entries = result["measurement"]["evidence_artifacts"]
    assert {entry["evidence"]: entry["status"] for entry in entries} == {
        "moss-metric-contracts": "receipt_log_missing",
        "moss-lineage-evidence": "receipt_log_missing",
    }
    assert all(entry["receipt_log"] == "receipts/absent.jsonl" for entry in entries)


@pytest.mark.parametrize(
    ("payload", "lines", "expected"),
    [
        pytest.param(
            {"source": "moss-metric-contracts", "receipt": {"response_sha256": "abc123"}},
            [_RECEIPT_LINE],
            "matched",
            id="matching-record",
        ),
        pytest.param(
            {"source": "moss-lineage-evidence", "receipt": {"response_sha256": "abc123"}},
            [_RECEIPT_LINE],
            "receipt_mismatch",
            id="log-server-differs-from-source",
        ),
        pytest.param(
            {"source": "moss-metric-contracts", "receipt": {"response_sha256": "other"}},
            [_RECEIPT_LINE],
            "receipt_mismatch",
            id="sha-differs",
        ),
        pytest.param(
            {"source": "moss-metric-contracts"},
            [_RECEIPT_LINE],
            "receipt_mismatch",
            id="artifact-without-receipt",
        ),
        pytest.param(
            {"source": "moss-metric-contracts", "receipt": {"response_sha256": ""}},
            [_RECEIPT_LINE],
            "receipt_mismatch",
            id="empty-sha",
        ),
        pytest.param(
            {"source": "moss-metric-contracts", "receipt": "abc123"},
            [_RECEIPT_LINE],
            "receipt_mismatch",
            id="receipt-not-an-object",
        ),
        pytest.param(
            {"source": "moss-metric-contracts", "receipt": {"response_sha256": "abc123"}},
            ["not json", "", "[1]", _RECEIPT_LINE],
            "matched",
            id="corrupt-and-blank-lines-are-skipped",
        ),
        pytest.param(
            {"source": "moss-metric-contracts", "receipt": {"response_sha256": "abc123"}},
            [],
            "receipt_mismatch",
            id="empty-log",
        ),
        pytest.param("not-a-dict", [_RECEIPT_LINE], "receipt_mismatch", id="payload-not-an-object"),
    ],
)
def test_verify_evidence_receipt_matching_rules(payload, lines, expected):
    assert verify_evidence_receipt(payload, lines) == expected


def test_append_receipt_writes_verifiable_jsonl_records(tmp_path):
    log = tmp_path / "nested" / "receipts.jsonl"

    append_receipt(
        log,
        server="moss-metric-contracts",
        tool="search_contract_docs",
        params_digest=digest_params({"query": "x"}),
        response_bytes=b"payload-1",
    )
    append_receipt(
        log,
        server="moss-lineage-evidence",
        tool="get_page_lineage",
        params_digest=digest_params({}),
        response_bytes=b"payload-2",
    )

    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["server"] == "moss-metric-contracts"
    assert first["tool"] == "search_contract_docs"
    assert first["params_digest"] == digest_params({"query": "x"})
    assert first["response_sha256"] == hashlib.sha256(b"payload-1").hexdigest()
    assert first["recorded_at"].endswith("+00:00")
    assert json.loads(lines[1])["server"] == "moss-lineage-evidence"


class _ReceiptProbeProvider(McpProvider):
    name = "moss-metric-contracts"

    def call_tool(self, name, arguments):
        return {
            "content": [{"type": "text", "text": f"echo:{arguments.get('query')}"}],
            "isError": False,
        }


def test_mcp_receipt_hook_records_a_receipt_the_evidence_check_can_match(tmp_path, monkeypatch):
    log_path = tmp_path / "receipts.jsonl"
    monkeypatch.setenv("MOSS_MCP_RECEIPT_LOG", str(log_path))
    server = ProjectMcpServer(_ReceiptProbeProvider())

    response = server._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "search_contract_docs", "arguments": {"query": "net interest"}},
        }
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["server"] == "moss-metric-contracts"
    assert record["tool"] == "search_contract_docs"
    assert record["params_digest"] == digest_params({"query": "net interest"})

    artifact_payload = {
        "source": "moss-metric-contracts",
        "receipt": {
            "response_sha256": hashlib.sha256(canonical_json_bytes(response["result"])).hexdigest()
        },
    }
    assert verify_evidence_receipt(artifact_payload, lines) == "matched"


def test_mcp_receipt_hook_is_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("MOSS_MCP_RECEIPT_LOG", raising=False)
    server = ProjectMcpServer(_ReceiptProbeProvider())

    response = server._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "search_contract_docs", "arguments": {"query": "net interest"}},
        }
    )

    assert server._receipt_log is None
    assert response["result"]["isError"] is False
    assert list(tmp_path.iterdir()) == []
