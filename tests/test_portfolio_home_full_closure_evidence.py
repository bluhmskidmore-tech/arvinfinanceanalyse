from __future__ import annotations

from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from scripts.portfolio_home_full_closure_evidence import build_evidence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_full_closure_evidence.py"
REPORT_DATE = "2026-05-31"


def _create_schema(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar,
              quality_flag varchar,
              portfolio_dv01 decimal(24, 8),
              krd_1y decimal(24, 8),
              krd_3y decimal(24, 8),
              krd_5y decimal(24, 8),
              krd_7y decimal(24, 8),
              krd_10y decimal(24, 8),
              krd_30y decimal(24, 8),
              warnings_json varchar,
              source_version varchar,
              upstream_source_version varchar,
              liability_source_version varchar
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              market_value decimal(24, 8),
              maturity_date varchar,
              tenor_bucket varchar,
              dv01 decimal(24, 8)
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              maturity_date varchar
            )
            """
        )
    finally:
        connection.close()


def _insert_blocked_data(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            insert into fact_formal_risk_tensor_daily values (
              ?, 'warning', ?, ?, ?, 0, 0, 0, 0,
              '["warning"]', 'sv_risk', 'sv_bond', 'sv_tyw'
            )
            """,
            [REPORT_DATE, Decimal("6"), Decimal("1"), Decimal("5")],
        )
        connection.executemany(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?)",
            [
                [REPORT_DATE, Decimal("100"), None, "2Y", Decimal("2")],
                [REPORT_DATE, Decimal("200"), "2028-05-31", "6M", Decimal("3")],
                [REPORT_DATE, Decimal("300"), "2030-05-31", "1Y", Decimal("1")],
            ],
        )
        connection.executemany(
            "insert into fact_formal_tyw_balance_daily values (?, ?, ?, ?, ?)",
            [
                [REPORT_DATE, "liability", "CNY", Decimal("10"), None],
                [REPORT_DATE, "liability", "CNY", Decimal("20"), "2026-07-31"],
                [REPORT_DATE, "liability", "native", Decimal("10"), None],
                [REPORT_DATE, "asset", "CNY", Decimal("30"), None],
            ],
        )
    finally:
        connection.close()


def _insert_clean_data(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            insert into fact_formal_risk_tensor_daily values (
              ?, 'ok', ?, ?, 0, 0, 0, 0, 0,
              '[]', 'sv_risk', 'sv_bond', 'sv_tyw'
            )
            """,
            [REPORT_DATE, Decimal("1"), Decimal("1")],
        )
        connection.execute(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?)",
            [REPORT_DATE, Decimal("300"), "2030-05-31", "1Y", Decimal("1")],
        )
        connection.execute(
            "insert into fact_formal_tyw_balance_daily values (?, ?, ?, ?, ?)",
            [REPORT_DATE, "liability", "CNY", Decimal("20"), "2026-07-31"],
        )
    finally:
        connection.close()


def test_portfolio_home_full_closure_evidence_reports_blocked_real_data_shape(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    assert evidence["data_quality_status"] == "blocked"
    assert evidence["closure_blockers"] == [
        "risk_tensor_quality_warning",
        "krd_contract_decision_required",
        "bond_maturity_date_remediation_required",
        "tyw_liability_maturity_date_remediation_required",
    ]
    assert evidence["risk_tensor"]["quality_flag"] == "warning"
    assert evidence["risk_tensor"]["portfolio_dv01"] == "6.00000000"
    assert evidence["risk_tensor"]["krd_sum"] == "6.00000000"
    assert evidence["bond_maturity_gap"]["missing_maturity_rows"] == 1
    assert evidence["bond_maturity_gap"]["missing_maturity_market_value"] == "100.00000000"
    assert evidence["tyw_liability_maturity_gap_risk_scope"]["row_count"] == 2
    assert evidence["tyw_liability_maturity_gap_risk_scope"]["missing_maturity_rows"] == 1
    assert evidence["tyw_liability_maturity_gap_full_formal"]["row_count"] == 4
    assert evidence["tyw_liability_maturity_gap_full_formal"]["missing_maturity_rows"] == 3
    assert evidence["krd_remap_scope"] == [
        {
            "tenor_bucket": "2Y",
            "row_count": 1,
            "dv01_sum": "2.00000000",
            "mapped_to": "krd_3y",
            "mapping_status": "mapped",
        },
        {
            "tenor_bucket": "6M",
            "row_count": 1,
            "dv01_sum": "3.00000000",
            "mapped_to": "krd_1y",
            "mapping_status": "mapped",
        },
    ]


def test_portfolio_home_full_closure_evidence_reports_clean_data_shape(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    assert evidence["data_quality_status"] == "clean"
    assert evidence["closure_blockers"] == []
    assert evidence["risk_tensor"]["quality_flag"] == "ok"
    assert evidence["bond_maturity_gap"]["missing_maturity_rows"] == 0
    assert evidence["tyw_liability_maturity_gap_risk_scope"]["missing_maturity_rows"] == 0
    assert evidence["krd_remap_scope"] == []


def test_portfolio_home_full_closure_evidence_cli_require_clean_blocks_warning(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duckdb-path",
            str(duckdb_path),
            "--report-date",
            REPORT_DATE,
            "--require-clean",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["data_quality_status"] == "blocked"
    assert "risk_tensor_quality_warning" in payload["closure_blockers"]


def test_portfolio_home_full_closure_evidence_cli_require_clean_allows_clean(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duckdb-path",
            str(duckdb_path),
            "--report-date",
            REPORT_DATE,
            "--require-clean",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["data_quality_status"] == "clean"
    assert payload["closure_blockers"] == []
