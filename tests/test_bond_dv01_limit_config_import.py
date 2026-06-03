from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from tests.helpers import load_module


STREAM = "bond_dv01_limit_config"
REPORT_DATE = "2026-03-31"
EFFECTIVE_DATE = "2026-03-01"


def _valid_record(accounting_class: str) -> dict[str, str]:
    return {
        "accounting_class": accounting_class,
        "limit_dv01": "1200000",
        "warning_dv01": "900000",
        "hedge_target_dv01": "800000",
        "limit_source": "risk_committee_minutes",
        "limit_source_version": f"risk_minutes_2026_03_{accounting_class}",
        "limit_rule_version": "rv_dv01_limit_policy_v1",
        "limit_effective_date": EFFECTIVE_DATE,
    }


def _load_import_task():
    return load_module(
        "backend.app.tasks.bond_dv01_limit_config_import",
        "backend/app/tasks/bond_dv01_limit_config_import.py",
    )


def test_import_bond_dv01_limit_config_rejects_missing_classes_without_writing(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    config_path = tmp_path / "dv01_limits.json"
    config_path.write_text(
        json.dumps([_valid_record("OCI"), _valid_record("all")]),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    task_mod = _load_import_task()

    payload = task_mod.import_bond_dv01_limit_config.fn(
        config_path=str(config_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "blocked"
    assert payload["records_written"] == 0
    assert payload["configured_accounting_classes"] == ["OCI", "all"]
    assert payload["missing_accounting_classes"] == ["AC", "TPL"]
    assert any("AC, TPL" in error for error in payload["validation_errors"])
    assert GovernanceRepository(base_dir=governance_dir).read_all(STREAM) == []
    get_settings.cache_clear()


def test_import_bond_dv01_limit_config_writes_all_classes_and_returns_ready_status(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    config_path = tmp_path / "dv01_limits.json"
    config_path.write_text(
        json.dumps([_valid_record(accounting_class) for accounting_class in ["AC", "OCI", "TPL", "all"]]),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    task_mod = _load_import_task()

    payload = task_mod.import_bond_dv01_limit_config.fn(
        config_path=str(config_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    rows = GovernanceRepository(base_dir=governance_dir).read_all(STREAM)
    status_result = payload["limit_config_status"]["result"]

    assert payload["status"] == "imported"
    assert payload["records_written"] == 4
    assert payload["configured_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert payload["validation_errors"] == []
    assert len(rows) == 4
    assert {row["accounting_class"] for row in rows} == {"AC", "OCI", "TPL", "all"}
    assert rows[0]["report_date"] == REPORT_DATE
    assert rows[0]["limit_effective_date"] == EFFECTIVE_DATE
    assert status_result["acceptance_status"] == "ready"
    assert status_result["configured_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert status_result["missing_accounting_classes"] == []
    get_settings.cache_clear()


def test_import_bond_dv01_limit_config_validates_csv_without_writing_in_dry_run(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    config_path = tmp_path / "dv01_limits.csv"
    rows = [_valid_record(accounting_class) for accounting_class in ["AC", "OCI", "TPL", "all"]]
    header = list(rows[0])
    config_path.write_text(
        "\n".join([",".join(header), *[",".join(row[column] for column in header) for row in rows]]),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    task_mod = _load_import_task()

    payload = task_mod.import_bond_dv01_limit_config.fn(
        config_path=str(config_path),
        governance_dir=str(governance_dir),
        report_date=date.fromisoformat(REPORT_DATE),
        dry_run=True,
    )

    assert payload["status"] == "validated"
    assert payload["records_written"] == 0
    assert payload["configured_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert payload["validation_errors"] == []
    assert payload["limit_config_status"]["result"]["acceptance_status"] == "blocked"
    assert GovernanceRepository(base_dir=governance_dir).read_all(STREAM) == []
    get_settings.cache_clear()


def test_import_bond_dv01_limit_config_cli_dry_run_then_import(tmp_path):
    governance_dir = tmp_path / "governance"
    config_path = tmp_path / "dv01_limits.csv"
    rows = [_valid_record(accounting_class) for accounting_class in ["AC", "OCI", "TPL", "all"]]
    header = list(rows[0])
    config_path.write_text(
        "\n".join([",".join(header), *[",".join(row[column] for column in header) for row in rows]]),
        encoding="utf-8",
    )
    env = {**os.environ, "MOSS_ENVIRONMENT": "test", "MOSS_GOVERNANCE_PATH": str(governance_dir)}

    dry_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.tasks.bond_dv01_limit_config_import",
            "--config-path",
            str(config_path),
            "--governance-dir",
            str(governance_dir),
            "--report-date",
            REPORT_DATE,
            "--dry-run",
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    dry_run_payload = json.loads(dry_run.stdout)

    assert dry_run_payload["status"] == "validated"
    assert dry_run_payload["records_written"] == 0
    assert dry_run_payload["validation_errors"] == []
    assert GovernanceRepository(base_dir=governance_dir).read_all(STREAM) == []

    imported = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.tasks.bond_dv01_limit_config_import",
            "--config-path",
            str(config_path),
            "--governance-dir",
            str(governance_dir),
            "--report-date",
            REPORT_DATE,
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    imported_payload = json.loads(imported.stdout)
    status_result = imported_payload["limit_config_status"]["result"]

    assert imported_payload["status"] == "imported"
    assert imported_payload["records_written"] == 4
    assert imported_payload["configured_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert status_result["acceptance_status"] == "ready"
    assert status_result["missing_accounting_classes"] == []
    assert len(GovernanceRepository(base_dir=governance_dir).read_all(STREAM)) == 4
