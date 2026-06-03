from __future__ import annotations

import csv
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import date

import duckdb

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.bond_analytics_service import (
    DV01_LIMIT_CONFIG_CLASSES,
    DV01_LIMIT_CONFIG_REQUIRED_FIELDS,
)
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


def _run_import_cli(args: list[str], monkeypatch) -> dict[str, object]:
    task_mod = _load_import_task()
    monkeypatch.setattr(sys, "argv", ["bond_dv01_limit_config_import", *args])
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        task_mod.main()
    return json.loads(stdout.getvalue())


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


def test_import_bond_dv01_limit_config_cli_dry_run_then_import(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    config_path = tmp_path / "dv01_limits.csv"
    rows = [_valid_record(accounting_class) for accounting_class in ["AC", "OCI", "TPL", "all"]]
    header = list(rows[0])
    config_path.write_text(
        "\n".join([",".join(header), *[",".join(row[column] for column in header) for row in rows]]),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    dry_run_payload = _run_import_cli(
        [
            "--config-path",
            str(config_path),
            "--governance-dir",
            str(governance_dir),
            "--report-date",
            REPORT_DATE,
            "--dry-run",
        ],
        monkeypatch,
    )

    assert dry_run_payload["status"] == "validated"
    assert dry_run_payload["records_written"] == 0
    assert dry_run_payload["validation_errors"] == []
    assert GovernanceRepository(base_dir=governance_dir).read_all(STREAM) == []

    imported_payload = _run_import_cli(
        [
            "--config-path",
            str(config_path),
            "--governance-dir",
            str(governance_dir),
            "--report-date",
            REPORT_DATE,
        ],
        monkeypatch,
    )
    status_result = imported_payload["limit_config_status"]["result"]

    assert imported_payload["status"] == "imported"
    assert imported_payload["records_written"] == 4
    assert imported_payload["configured_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert status_result["acceptance_status"] == "ready"
    assert status_result["missing_accounting_classes"] == []
    assert len(GovernanceRepository(base_dir=governance_dir).read_all(STREAM)) == 4
    get_settings.cache_clear()


def test_import_bond_dv01_limit_config_cli_can_write_blank_template(tmp_path, monkeypatch):
    template_path = tmp_path / "blank_dv01_limits.csv"
    payload = _run_import_cli(["--write-template", str(template_path)], monkeypatch)

    with template_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert payload["status"] == "template_written"
    assert payload["template_path"] == str(template_path)
    assert reader.fieldnames == list(DV01_LIMIT_CONFIG_REQUIRED_FIELDS)
    assert [row["accounting_class"] for row in rows] == list(DV01_LIMIT_CONFIG_CLASSES)
    for row in rows:
        assert row["limit_dv01"] == ""
        assert row["warning_dv01"] == ""
        assert row["hedge_target_dv01"] == ""


def test_import_bond_dv01_limit_config_cli_can_check_current_status(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    config_path = tmp_path / "dv01_limits.csv"
    rows = [_valid_record(accounting_class) for accounting_class in ["AC", "OCI", "TPL", "all"]]
    header = list(rows[0])
    config_path.write_text(
        "\n".join([",".join(header), *[",".join(row[column] for column in header) for row in rows]]),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _run_import_cli(
        [
            "--config-path",
            str(config_path),
            "--governance-dir",
            str(governance_dir),
            "--report-date",
            REPORT_DATE,
        ],
        monkeypatch,
    )

    payload = _run_import_cli(
        [
            "--check-status",
            "--governance-dir",
            str(governance_dir),
            "--report-date",
            REPORT_DATE,
        ],
        monkeypatch,
    )

    assert payload["status"] == "status_checked"
    assert payload["governance_dir"] == str(governance_dir)
    assert payload["report_date"] == REPORT_DATE
    assert payload["limit_config_status"]["result"]["acceptance_status"] == "ready"
    assert payload["limit_config_status"]["result"]["missing_accounting_classes"] == []
    get_settings.cache_clear()


def test_import_bond_dv01_limit_config_cli_builds_reference_baseline_without_limits(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table fact_formal_bond_analytics_daily (
            report_date varchar,
            accounting_class varchar,
            face_value decimal(24, 8),
            market_value decimal(24, 8),
            modified_duration decimal(18, 8),
            dv01 decimal(24, 8)
        )
        """
    )
    conn.executemany(
        "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?, ?)",
        [
            ("2026-04-30", "OCI", "900", "910", "1.5", "9"),
            ("2026-05-31", "TPL", "1000", "980", "2", "20"),
            ("2026-05-31", "TPL", "2000", "2010", "4", "80"),
            ("2026-05-31", "other", "500", "480", "3", "15"),
        ],
    )
    conn.close()
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    payload = _run_import_cli(["--reference-baseline"], monkeypatch)
    rows_by_class = {row["accounting_class"]: row for row in payload["rows"]}

    assert payload["status"] == "reference_baseline_built"
    assert payload["report_date"] == "2026-05-31"
    assert payload["source_table"] == "fact_formal_bond_analytics_daily"
    assert payload["business_limit_fields_blank"] is True
    assert payload["unmapped_accounting_classes"] == ["other"]
    assert payload["required_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert rows_by_class["AC"]["position_count"] == 0
    assert rows_by_class["OCI"]["current_total_dv01"] == "0"
    assert rows_by_class["TPL"]["position_count"] == 2
    assert rows_by_class["TPL"]["current_total_dv01"] == "100.00000000"
    assert rows_by_class["TPL"]["face_weighted_modified_duration"] == "3.33333333"
    assert rows_by_class["all"]["position_count"] == 3
    assert rows_by_class["all"]["current_total_dv01"] == "115.00000000"
    assert rows_by_class["all"]["limit_dv01"] == ""
    assert rows_by_class["all"]["warning_dv01"] == ""
    assert rows_by_class["all"]["hedge_target_dv01"] == ""
    assert GovernanceRepository(base_dir=tmp_path / "governance").read_all(STREAM) == []
    get_settings.cache_clear()
