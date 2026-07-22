from __future__ import annotations

from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from scripts.portfolio_home_matured_outstanding_queue import build_queue, main


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_matured_outstanding_queue.py"
REPORT_DATE = "2026-06-30"


def _create_database(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar,
              instrument_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              market_value decimal(24, 8),
              maturity_date varchar,
              modified_duration decimal(18, 8),
              dv01 decimal(24, 8),
              source_version varchar,
              trace_id varchar
            )
            """
        )
        connection.executemany(
            """
            insert into fact_formal_bond_analytics_daily values
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [REPORT_DATE, "MAT-POS", "Matured positive", "book-a", "cc-a", Decimal("100"), "2026-06-20", Decimal("0.5"), Decimal("1.2"), "sv-1", "trace-1"],
                [REPORT_DATE, "MAT-NEG", "Matured negative", "book-b", "cc-b", Decimal("-40"), "2026-06-30", Decimal("0"), Decimal("-0.4"), "sv-2", "trace-2"],
                [REPORT_DATE, "MAT-ZERO", "Matured zero", "book-c", "cc-c", Decimal("0"), "2026-06-01", Decimal("0"), Decimal("0"), "sv-3", "trace-3"],
                [REPORT_DATE, "FUTURE", "Future bond", "book-d", "cc-d", Decimal("300"), "2026-07-01", Decimal("1.1"), Decimal("2.0"), "sv-4", "trace-4"],
                [REPORT_DATE, "NO-DATE", "No maturity", "book-e", "cc-e", Decimal("500"), None, Decimal("0"), Decimal("0"), "sv-5", "trace-5"],
            ],
        )
    finally:
        connection.close()


def test_queue_reports_matured_nonzero_positions_and_strict_gate(
    tmp_path: Path,
    capsys,
) -> None:
    database = tmp_path / "moss.duckdb"
    _create_database(database)

    payload = build_queue(
        duckdb_path=database,
        report_date=REPORT_DATE,
    )

    assert payload["reconciliation_status"] == "blocked"
    assert payload["reconciliation_blockers"] == [
        "bond_matured_outstanding_reconciliation_required"
    ]
    assert payload["summary"] == {
        "row_count": 2,
        "net_market_value": "60.00000000",
        "absolute_market_value": "140.00000000",
        "dv01_sum": "0.80000000",
        "earliest_maturity_date": "2026-06-20",
        "latest_maturity_date": "2026-06-30",
        "unparseable_maturity_date_rows": 0,
        "unparseable_maturity_date_market_value": "0E-8",
    }
    assert [row["instrument_code"] for row in payload["rows"]] == ["MAT-POS", "MAT-NEG"]
    assert [row["days_past_maturity"] for row in payload["rows"]] == [10, 0]
    assert payload["evidence_scope"] == {
        "read_only": True,
        "writes_database": False,
        "changes_reconciliation_status": False,
        "approves_metric_or_page": False,
        "certification_effect": "none",
    }
    assert payload["next_action"] == (
        "Reconcile every queued non-zero row at source. Non-null unparseable "
        "maturity_date values must be corrected at source; no replacement maturity date "
        "or duration may be inferred."
    )
    assert "exception" not in payload["next_action"].lower()

    exit_code = main(
        ["--duckdb-path", str(database), "--report-date", REPORT_DATE, "--require-empty"]
    )
    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["reconciliation_status"] == "blocked"


def test_require_empty_passes_when_only_zero_future_or_null_maturity_rows_exist(
    tmp_path: Path,
    capsys,
) -> None:
    database = tmp_path / "moss.duckdb"
    _create_database(database)
    connection = duckdb.connect(str(database), read_only=False)
    try:
        connection.execute(
            """
            delete from fact_formal_bond_analytics_daily
            where instrument_code in ('MAT-POS', 'MAT-NEG')
            """
        )
    finally:
        connection.close()

    exit_code = main(
        ["--duckdb-path", str(database), "--report-date", REPORT_DATE, "--require-empty"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["reconciliation_status"] == "clean"
    assert payload["summary"]["row_count"] == 0
    assert payload["summary"]["unparseable_maturity_date_rows"] == 0
    assert payload["summary"]["unparseable_maturity_date_market_value"] == "0E-8"
    assert payload["rows"] == []


def test_non_null_unparseable_maturity_date_fails_closed_and_is_visible(
    tmp_path: Path,
    capsys,
) -> None:
    database = tmp_path / "moss.duckdb"
    _create_database(database)
    connection = duckdb.connect(str(database), read_only=False)
    try:
        connection.execute(
            """
            delete from fact_formal_bond_analytics_daily
            where instrument_code in ('MAT-POS', 'MAT-NEG')
            """
        )
        connection.execute(
            """
            insert into fact_formal_bond_analytics_daily values
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                REPORT_DATE,
                "BAD-DATE",
                "Unparseable maturity",
                "book-invalid",
                "cc-invalid",
                Decimal("75"),
                "not-a-date",
                Decimal("0.7"),
                Decimal("0.3"),
                "sv-invalid",
                "trace-invalid",
            ],
        )
    finally:
        connection.close()

    payload = build_queue(
        duckdb_path=database,
        report_date=REPORT_DATE,
    )

    assert payload["reconciliation_status"] == "blocked"
    assert payload["reconciliation_blockers"] == [
        "bond_matured_outstanding_reconciliation_required"
    ]
    assert payload["summary"] == {
        "row_count": 0,
        "net_market_value": "0E-8",
        "absolute_market_value": "0E-8",
        "dv01_sum": "0E-8",
        "earliest_maturity_date": None,
        "latest_maturity_date": None,
        "unparseable_maturity_date_rows": 1,
        "unparseable_maturity_date_market_value": "75.00000000",
    }
    assert [row["instrument_code"] for row in payload["rows"]] == ["BAD-DATE"]
    assert payload["rows"][0]["maturity_date"] == "not-a-date"
    assert payload["rows"][0]["parsed_maturity_date"] is None
    assert payload["rows"][0]["maturity_date_status"] == "unparseable"
    assert payload["rows"][0]["days_past_maturity"] is None

    exit_code = main(
        ["--duckdb-path", str(database), "--report-date", REPORT_DATE, "--require-empty"]
    )
    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["reconciliation_status"] == "blocked"


def test_malformed_report_date_cannot_emit_a_clean_strict_gate(tmp_path: Path) -> None:
    database = tmp_path / "moss.duckdb"
    _create_database(database)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duckdb-path",
            str(database),
            "--report-date",
            "not-a-date",
            "--require-empty",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode != 0
    assert '"reconciliation_status": "clean"' not in completed.stdout
