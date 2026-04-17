from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]


def test_backend_release_suite_declares_bounded_phase2_gate():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    assert module.RELEASE_SUITE_NAME == "governed-phase2-backend-release-suite"
    assert module.RELEASE_SUITE_TESTS == [
        "tests/test_settings_contract.py",
        "tests/test_health_endpoints.py",
        "tests/test_positions_api_contract.py",
        "tests/test_pnl_api_contract.py",
        "tests/test_risk_tensor_api.py",
        "tests/test_balance_analysis_api.py",
        "tests/test_bond_analytics_api.py",
        "tests/test_executive_dashboard_endpoints.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
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
    assert report["governance_dir"] == "data/governance"
    assert report["pytest_args"] == ["-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS]
    assert report["env"]["MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS"] == "1"
    assert report["env"]["MOSS_SKIP_POSTGRES_MIGRATIONS"] == "1"


def test_backend_release_suite_dry_run_preserves_governance_audit_output_arg(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(
        ["--dry-run", "--governance-audit-output", "governance-lineage-audit.json"]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["governance_audit_output"] == "governance-lineage-audit.json"


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
            "dirty_rows": 2,
            "findings": [{"cache_key": "broken.cache"}],
        },
    )

    calls: list[tuple[list[str], str]] = []

    def _fake_run(*args, **kwargs):
        calls.append((list(args[0]), str(kwargs.get("cwd"))))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.run_release_suite(root=ROOT)

    assert exit_code == 1
    assert calls == []


def test_backend_release_suite_runs_fixed_pytest_matrix_when_governance_is_clean(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "dirty_rows": 0,
            "findings": [],
        },
    )

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
    assert len(calls) == 1
    assert calls[0]["args"] == ["python", "-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS]
    assert calls[0]["cwd"] == str(ROOT)
    for key, value in module._release_suite_env().items():
        assert calls[0]["env"][key] == value


def test_backend_release_suite_writes_governance_audit_output_when_requested(monkeypatch, tmp_path):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    summary = {
        "governance_dir": str(tmp_path / "gov"),
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
        governance_audit_output=output_path,
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == summary
