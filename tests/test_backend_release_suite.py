from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def test_backend_release_suite_declares_bounded_phase2_gate():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    assert module.RELEASE_SUITE_NAME == "governed-phase2-backend-release-suite"
    assert module.GOVERNANCE_MCP_SUITE_NAME == "governance-mcp-contract-suite"
    assert module.RELEASE_SUITE_TESTS == [
        "tests/test_settings_contract.py",
        "tests/test_health_endpoints.py",
        "tests/test_positions_api_contract.py",
        "tests/test_pnl_api_contract.py",
        "tests/test_pnl_by_business_insights_contract.py",
        "tests/test_pnl_by_business_candidate_insights_contract.py",
        "tests/test_candidate_period_comparison_contract_alignment.py",
        "tests/test_risk_tensor_api.py",
        "tests/test_balance_analysis_api.py",
        "tests/test_bond_analytics_api.py",
        "tests/test_executive_dashboard_endpoints.py",
        "tests/test_cube_query_api.py",
        "tests/test_liability_analytics_api.py",
        "tests/test_liability_analytics_envelope_contract.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "tests/test_governance_lineage_audit.py",
        "tests/test_governance_doc_contract.py",
        "tests/test_golden_samples_capture_ready.py",
        "tests/test_ledger_pnl_net_interest_golden_sample.py",
        "tests/test_executive_release_contract.py",
        "tests/test_golden_sample_release_matrix.py",
        "tests/test_live_route_page_contract_completeness.py",
        "tests/test_backend_dependency_contract.py",
        "tests/test_no_finance_logic_in_frontend.py",
    ]
    assert module.GOVERNANCE_MCP_FAST_SUITE_TESTS == [
        "tests/test_project_mcp_fast_contracts.py"
    ]
    assert module.GOVERNANCE_MCP_FULL_SUITE_TESTS == ["tests/test_project_mcp_servers.py"]
    assert module.EXECUTIVE_RELEASE_SAMPLE_IDS == [
        "GS-EXEC-OVERVIEW-A",
        "GS-EXEC-PNL-ATTR-A",
        "GS-EXEC-SUMMARY-A",
    ]


def test_backend_release_suite_dry_run_emits_expected_plan(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(["--dry-run"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["suite_name"] == "governed-phase2-backend-release-suite"
    assert report["governance_audit"] == {
        "mode": "fixture",
        "directory": None,
        "fail_on_empty": False,
    }
    assert report["pytest_args"] == ["-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS]
    assert report["governance_mcp_suite"] == {
        "suite_name": "governance-mcp-contract-suite",
        "profile": "fast",
        "pytest_args": [
            "-m",
            "pytest",
            "-q",
            "-m",
            "mcp_fast",
            *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
        ],
    }
    assert report["executive_release_sample_ids"] == module.EXECUTIVE_RELEASE_SAMPLE_IDS
    assert report["env"]["MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS"] == "1"
    assert report["env"]["MOSS_SKIP_POSTGRES_MIGRATIONS"] == "1"


def test_backend_release_suite_dry_run_preserves_governance_audit_output_arg(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(
        [
            "--dry-run",
            "--live-governance-dir",
            "tmp/governance",
            "--governance-audit-output",
            "governance-lineage-audit.json",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["governance_audit_output"] == "governance-lineage-audit.json"
    assert report["governance_audit"] == {
        "mode": "live",
        "directory": "tmp/governance",
        "fail_on_empty": True,
    }


def test_backend_release_suite_rejects_audit_output_without_live_directory():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main(
            ["--dry-run", "--governance-audit-output", "misleading-empty.json"]
        )

    assert exc_info.value.code == 2


def test_backend_release_suite_dry_run_can_select_full_mcp_profile(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(["--dry-run", "--mcp-profile", "full"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["governance_mcp_suite"] == {
        "suite_name": "governance-mcp-contract-suite",
        "profile": "full",
        "pytest_args": ["-m", "pytest", "-q", *module.GOVERNANCE_MCP_FULL_SUITE_TESTS],
    }


def test_backend_release_suite_blocks_before_pytest_when_governance_audit_is_dirty(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "files_scanned": 1,
            "dirty_rows": 2,
            "findings": [{"cache_key": "broken.cache"}],
        },
    )

    calls: list[tuple[list[str], str]] = []

    def _fake_run(*args, **kwargs):
        calls.append((list(args[0]), str(kwargs.get("cwd"))))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.run_release_suite(
        root=ROOT,
        live_governance_dir="data/governance",
    )

    assert exit_code == 1
    assert calls == []


def test_backend_release_suite_live_governance_audit_fails_closed_when_empty(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "files_scanned": 0,
            "dirty_rows": 0,
            "findings": [],
        },
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kwargs: calls.append(list(args)),
    )

    assert module.run_release_suite(
        root=ROOT,
        live_governance_dir="empty-governance",
    ) == 1
    assert calls == []


def test_backend_release_suite_live_governance_audit_fails_closed_when_no_rows(
    monkeypatch,
):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "files_scanned": 1,
            "rows_scanned": 0,
            "dirty_rows": 0,
            "findings": [],
        },
    )
    calls: list[list[str]] = []
    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(
        root=ROOT,
        live_governance_dir="empty-jsonl-governance",
    ) == 1
    assert calls == []


def test_backend_release_suite_runs_bounded_then_governance_mcp_pytest_when_clean(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    def _unexpected_live_audit(_governance_dir):
        raise AssertionError("default release suite must not inspect local live governance")

    monkeypatch.setattr(module, "audit_governance_lineage", _unexpected_live_audit)

    calls: list[dict[str, object]] = []

    def _fake_run(args, **kwargs):
        calls.append(
            {
                "args": list(args),
                "cwd": str(kwargs.get("cwd")),
                "env": dict(kwargs.get("env", {})),
            }
        )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.run_release_suite(root=ROOT)

    assert exit_code == 0
    assert len(calls) == 2
    assert calls[0]["args"] == [sys.executable, "-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS]
    assert calls[1]["args"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "mcp_fast",
        *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
    ]
    for call in calls:
        assert call["cwd"] == str(ROOT)
        for key, value in module._release_suite_env().items():
            assert call["env"][key] == value


def test_backend_release_suite_uses_one_cleaned_temp_storage_root_for_both_pytest_runs(
    monkeypatch,
    tmp_path,
):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    ambient_governance = tmp_path / "ambient-governance"
    ambient_duckdb = tmp_path / "ambient.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(ambient_governance))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(ambient_duckdb))

    observed_roots: list[Path] = []

    def _fake_run(args, **kwargs):
        env = kwargs["env"]
        governance_path = Path(env["MOSS_GOVERNANCE_PATH"])
        duckdb_path = Path(env["MOSS_DUCKDB_PATH"])

        assert governance_path != ambient_governance
        assert duckdb_path != ambient_duckdb
        assert governance_path.name == "governance"
        assert duckdb_path.name == "moss.duckdb"
        assert governance_path.parent == duckdb_path.parent

        isolated_root = governance_path.parent
        if not observed_roots:
            governance_path.mkdir(parents=True, exist_ok=True)
            (governance_path / ".locks").mkdir()
            (governance_path / ".locks" / "release-test.lock").write_text(
                "locked",
                encoding="utf-8",
            )
            duckdb_path.write_bytes(b"duckdb-test")
        else:
            assert isolated_root == observed_roots[0]
            assert (governance_path / ".locks" / "release-test.lock").is_file()
            assert duckdb_path.read_bytes() == b"duckdb-test"
        observed_roots.append(isolated_root)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT) == 0
    assert len(observed_roots) == 2
    assert not observed_roots[0].exists()
    assert not ambient_governance.exists()
    assert not ambient_duckdb.exists()


def test_bounded_release_tests_do_not_use_repo_relative_fake_governance():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    offenders = [
        test_path
        for test_path in module.RELEASE_SUITE_TESTS
        if '"fake-governance"'
        in (ROOT / test_path).read_text(encoding="utf-8")
    ]

    assert offenders == []

def test_backend_release_suite_stops_before_governance_mcp_when_bounded_pytest_fails(
    monkeypatch,
):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {"governance_dir": str(governance_dir), "dirty_rows": 0},
    )
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 7)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT) == 7
    assert calls == [[sys.executable, "-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS]]


def test_backend_release_suite_returns_governance_mcp_failure(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {"governance_dir": str(governance_dir), "dirty_rows": 0},
    )
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0 if len(calls) == 1 else 9)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT) == 9
    assert calls == [
        [sys.executable, "-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS],
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            "mcp_fast",
            *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
        ],
    ]


def test_backend_release_suite_can_run_full_governance_mcp_profile(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {"governance_dir": str(governance_dir), "dirty_rows": 0},
    )
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT, mcp_profile="full") == 0
    assert calls[-1] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *module.GOVERNANCE_MCP_FULL_SUITE_TESTS,
    ]


def test_backend_release_suite_writes_governance_audit_output_when_requested(monkeypatch, tmp_path):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    summary = {
        "governance_dir": str(tmp_path / "gov"),
        "files_scanned": 1,
        "rows_scanned": 1,
        "dirty_rows": 0,
        "findings": [],
    }
    monkeypatch.setattr(module, "audit_governance_lineage", lambda governance_dir: summary)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )

    output_path = tmp_path / "governance-lineage-audit.json"
    exit_code = module.run_release_suite(
        root=ROOT,
        live_governance_dir=str(tmp_path / "gov"),
        governance_audit_output=output_path,
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == summary
