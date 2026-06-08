from __future__ import annotations

import csv
from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from scripts.portfolio_home_maturity_remediation_export import build_export_packet
from scripts.portfolio_home_maturity_remediation_queue import build_queue


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_maturity_remediation_queue.py"
EXPORT_SCRIPT = ROOT / "scripts" / "portfolio_home_maturity_remediation_export.py"
REPORT_DATE = "2026-05-31"


def _create_schema(path: Path) -> None:
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
              dv01 decimal(24, 8),
              tenor_bucket varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
    finally:
        connection.close()


def _create_candidate_source_schema(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            create table position_snapshot (
              as_of_date varchar,
              bond_code varchar,
              bond_name varchar,
              maturity_date varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        connection.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
    finally:
        connection.close()


def _insert_blocked_data(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.executemany(
            """
            insert into fact_formal_bond_analytics_daily values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                [
                    REPORT_DATE,
                    "BOND-SMALL",
                    "Small Missing Bond",
                    "book-a",
                    "cc-a",
                    Decimal("100"),
                    None,
                    Decimal("1.5"),
                    "2Y",
                    "sv_bond",
                    "rv_bond",
                    "batch-1",
                    "trace-small",
                ],
                [
                    REPORT_DATE,
                    "BOND-LARGE",
                    "Large Missing Bond",
                    "book-b",
                    "cc-b",
                    Decimal("200"),
                    None,
                    Decimal("2.5"),
                    "20Y",
                    "sv_bond",
                    "rv_bond",
                    "batch-2",
                    "trace-large",
                ],
                [
                    REPORT_DATE,
                    "BOND-CLEAN",
                    "Clean Bond",
                    "book-c",
                    "cc-c",
                    Decimal("300"),
                    "2030-05-31",
                    Decimal("3.5"),
                    "5Y",
                    "sv_bond",
                    "rv_bond",
                    "batch-3",
                    "trace-clean",
                ],
            ],
        )
        connection.executemany(
            """
            insert into fact_formal_tyw_balance_daily values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                [
                    REPORT_DATE,
                    "POS-SMALL",
                    "repo",
                    "short",
                    "Counterparty A",
                    "liability",
                    "CNY",
                    Decimal("10"),
                    Decimal("0.02"),
                    None,
                    "sv_tyw",
                    "rv_tyw",
                    "batch-4",
                    "trace-pos-small",
                ],
                [
                    REPORT_DATE,
                    "POS-LARGE",
                    "deposit",
                    "short",
                    "Counterparty B",
                    "liability",
                    "CNY",
                    Decimal("30"),
                    Decimal("0.03"),
                    None,
                    "sv_tyw",
                    "rv_tyw",
                    "batch-5",
                    "trace-pos-large",
                ],
                [
                    REPORT_DATE,
                    "POS-CLEAN",
                    "deposit",
                    "short",
                    "Counterparty C",
                    "liability",
                    "CNY",
                    Decimal("20"),
                    Decimal("0.01"),
                    "2026-07-31",
                    "sv_tyw",
                    "rv_tyw",
                    "batch-6",
                    "trace-pos-clean",
                ],
                [
                    REPORT_DATE,
                    "POS-OUT-OF-SCOPE",
                    "deposit",
                    "long",
                    "Counterparty D",
                    "asset",
                    "CNY",
                    Decimal("40"),
                    Decimal("0.01"),
                    None,
                    "sv_tyw",
                    "rv_tyw",
                    "batch-7",
                    "trace-pos-out",
                ],
            ],
        )
    finally:
        connection.close()


def _insert_clean_data(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            insert into fact_formal_bond_analytics_daily values (
              ?, 'BOND-CLEAN', 'Clean Bond', 'book', 'cc', ?, '2030-05-31', ?, '5Y',
              'sv_bond', 'rv_bond', 'batch-1', 'trace-clean'
            )
            """,
            [REPORT_DATE, Decimal("300"), Decimal("3.5")],
        )
        connection.execute(
            """
            insert into fact_formal_tyw_balance_daily values (
              ?, 'POS-CLEAN', 'deposit', 'short', 'Counterparty C', 'liability', 'CNY',
              ?, ?, '2026-07-31', 'sv_tyw', 'rv_tyw', 'batch-2', 'trace-pos-clean'
            )
            """,
            [REPORT_DATE, Decimal("20"), Decimal("0.01")],
        )
    finally:
        connection.close()


def _run_queue(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _run_queue_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def _run_export(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(EXPORT_SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_portfolio_home_maturity_remediation_queue_reports_blocked_rows_and_samples(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    queue = build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=1)

    assert queue["remediation_status"] == "blocked"
    assert queue["remediation_blockers"] == [
        "bond_maturity_queue_not_empty",
        "tyw_liability_maturity_queue_not_empty",
    ]
    assert queue["remediation_scope"] == {
        "bond_queue": "fact_formal_bond_analytics_daily rows where maturity_date is null",
        "tyw_liability_queue": "fact_formal_tyw_balance_daily liability CNY rows where maturity_date is null",
    }
    assert queue["remediation_actions"] == [
        {
            "blocker": "bond_maturity_queue_not_empty",
            "owner": "data_owner",
            "next_action": "Fill missing bond maturity_date values at source or capture a signed scoped exclusion.",
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
            "exit_criteria": "Bond missing-maturity queue is empty or signed exclusion evidence is captured and surfaced as a boundary.",
        },
        {
            "blocker": "tyw_liability_maturity_queue_not_empty",
            "owner": "data_owner",
            "next_action": "Fill missing TYW liability maturity_date values at source or capture a signed scoped exclusion.",
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
            "exit_criteria": "TYW liability missing-maturity queue is empty or signed exclusion evidence is captured and surfaced as a boundary.",
        },
    ]
    assert queue["bond_missing_maturity_summary"] == {
        "row_count": 3,
        "missing_maturity_rows": 2,
        "missing_maturity_market_value": "300.00000000",
    }
    assert queue["tyw_liability_missing_maturity_summary"] == {
        "row_count": 3,
        "missing_maturity_rows": 2,
        "missing_maturity_principal": "40.00000000",
    }
    assert queue["bond_missing_maturity_rows"] == [
        {
            "report_date": REPORT_DATE,
            "instrument_code": "BOND-LARGE",
            "instrument_name": "Large Missing Bond",
            "portfolio_name": "book-b",
            "cost_center": "cc-b",
            "market_value": "200.00000000",
            "dv01": "2.50000000",
            "tenor_bucket": "20Y",
            "source_version": "sv_bond",
            "rule_version": "rv_bond",
            "ingest_batch_id": "batch-2",
            "trace_id": "trace-large",
        }
    ]
    assert queue["tyw_liability_missing_maturity_rows"] == [
        {
            "report_date": REPORT_DATE,
            "position_id": "POS-LARGE",
            "product_type": "deposit",
            "position_side": "short",
            "counterparty_name": "Counterparty B",
            "position_scope": "liability",
            "currency_basis": "CNY",
            "principal_amount": "30.00000000",
            "funding_cost_rate": "0.03000000",
            "source_version": "sv_tyw",
            "rule_version": "rv_tyw",
            "ingest_batch_id": "batch-5",
            "trace_id": "trace-pos-large",
        }
    ]


def test_portfolio_home_maturity_candidate_evidence_does_not_clear_strict_gate(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "candidate.duckdb"
    _create_schema(duckdb_path)
    _create_candidate_source_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    connection = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        connection.execute(
            """
            insert into zqtz_bond_daily_snapshot values (
              ?, 'BOND-LARGE', 'book-b', 'cc-b', '2035-05-31',
              'sv_candidate_bond', 'rv_candidate_bond', 'batch-candidate-bond',
              'trace-candidate-bond'
            )
            """,
            [REPORT_DATE],
        )
        connection.execute(
            """
            insert into tyw_interbank_daily_snapshot values (
              ?, 'POS-LARGE', 'deposit', 'short', 'Counterparty B', '2026-08-31',
              'sv_candidate_tyw', 'rv_candidate_tyw', 'batch-candidate-tyw',
              'trace-candidate-tyw'
            )
            """,
            [REPORT_DATE],
        )
    finally:
        connection.close()

    queue = build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=5)

    assert queue["remediation_status"] == "blocked"
    assert queue["remediation_blockers"] == [
        "bond_maturity_queue_not_empty",
        "tyw_liability_maturity_queue_not_empty",
    ]
    candidate_evidence = queue["maturity_candidate_evidence"]
    assert candidate_evidence["status"] == "candidate_found"
    assert candidate_evidence["strict_gate_effect"] == "none"
    assert candidate_evidence["evidence_scope"] == {
        "read_only": True,
        "writes_database": False,
        "fills_maturity_date": False,
        "approves_metric_or_page": False,
        "changes_remediation_status": False,
        "certification_effect": "none",
    }
    sources = {
        str(source["source_table"]): source
        for source in candidate_evidence["candidate_sources"]
    }
    assert sources["zqtz_bond_daily_snapshot"]["status"] == "candidate_found"
    assert sources["zqtz_bond_daily_snapshot"]["summary"] == {
        "missing_rows": 2,
        "matched_missing_rows": 1,
        "candidate_rows": 1,
        "ambiguous_key_count": 0,
        "candidate_market_value": "200.00000000",
    }
    assert sources["zqtz_bond_daily_snapshot"]["sample_candidates"] == [
        {
            "instrument_code": "BOND-LARGE",
            "instrument_name": "Large Missing Bond",
            "portfolio_name": "book-b",
            "cost_center": "cc-b",
            "market_value": "200.00000000",
            "trace_id": "trace-large",
            "candidate_maturity_date": "2035-05-31",
            "candidate_source_version": "sv_candidate_bond",
            "candidate_rule_version": "rv_candidate_bond",
            "candidate_ingest_batch_id": "batch-candidate-bond",
            "candidate_trace_id": "trace-candidate-bond",
        }
    ]
    assert sources["tyw_interbank_daily_snapshot"]["status"] == "candidate_found"
    assert sources["tyw_interbank_daily_snapshot"]["summary"] == {
        "missing_rows": 2,
        "matched_missing_rows": 1,
        "candidate_rows": 1,
        "ambiguous_key_count": 0,
        "candidate_principal": "30.00000000",
    }


def test_portfolio_home_maturity_candidate_evidence_reports_no_candidates(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "no-candidate.duckdb"
    _create_schema(duckdb_path)
    _create_candidate_source_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    queue = build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=5)

    assert queue["remediation_status"] == "blocked"
    candidate_evidence = queue["maturity_candidate_evidence"]
    assert candidate_evidence["status"] == "no_candidates"
    assert {
        str(source["source_table"]): source["status"]
        for source in candidate_evidence["candidate_sources"]
    } == {
        "zqtz_bond_daily_snapshot": "no_candidates",
        "position_snapshot": "no_candidates",
        "tyw_interbank_daily_snapshot": "no_candidates",
    }
    assert all(
        source["sample_candidates"] == []
        for source in candidate_evidence["candidate_sources"]
    )


def test_portfolio_home_maturity_candidate_evidence_blocks_conflicting_candidates(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "conflicting-candidate.duckdb"
    _create_schema(duckdb_path)
    _create_candidate_source_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    connection = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        connection.executemany(
            """
            insert into zqtz_bond_daily_snapshot values (
              ?, 'BOND-LARGE', 'book-b', 'cc-b', ?, 'sv_candidate_bond',
              'rv_candidate_bond', 'batch-candidate-bond', ?
            )
            """,
            [
                [REPORT_DATE, "2035-05-31", "trace-candidate-bond-a"],
                [REPORT_DATE, "2036-05-31", "trace-candidate-bond-b"],
            ],
        )
    finally:
        connection.close()

    queue = build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=5)

    assert queue["remediation_status"] == "blocked"
    candidate_evidence = queue["maturity_candidate_evidence"]
    assert candidate_evidence["status"] == "conflicting_candidates"
    sources = {
        str(source["source_table"]): source
        for source in candidate_evidence["candidate_sources"]
    }
    assert sources["zqtz_bond_daily_snapshot"]["status"] == "conflicting_candidates"
    assert sources["zqtz_bond_daily_snapshot"]["summary"] == {
        "missing_rows": 2,
        "matched_missing_rows": 1,
        "candidate_rows": 2,
        "ambiguous_key_count": 1,
        "candidate_market_value": "200.00000000",
    }


def test_portfolio_home_maturity_remediation_queue_rejects_negative_limit_before_query(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    try:
        build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=-1)
    except ValueError as exc:
        assert str(exc) == "Portfolio-home maturity remediation limit must be non-negative: -1"
    else:
        raise AssertionError("negative maturity remediation limit should be rejected")


def test_portfolio_home_maturity_remediation_queue_cli_rejects_negative_limit(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    _create_schema(duckdb_path)

    completed = _run_queue_raw(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--limit",
        "-1",
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "Portfolio-home maturity remediation limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_maturity_remediation_queue_require_empty_blocks_missing_rows(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    returncode, payload = _run_queue(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--limit",
        "1",
        "--require-empty",
    )

    assert returncode == 1
    assert payload["remediation_status"] == "blocked"
    assert "bond_maturity_queue_not_empty" in payload["remediation_blockers"]


def test_portfolio_home_maturity_remediation_queue_require_empty_allows_clean(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)

    returncode, payload = _run_queue(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--require-empty",
    )

    assert returncode == 0
    assert payload["remediation_status"] == "clean"
    assert payload["remediation_blockers"] == []
    assert payload["remediation_actions"] == []
    assert payload["bond_missing_maturity_rows"] == []
    assert payload["tyw_liability_missing_maturity_rows"] == []


def test_portfolio_home_maturity_remediation_export_writes_data_owner_package(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    output_dir = tmp_path / "maturity-export"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        output_dir=output_dir,
    )

    assert packet["packet_kind"] == "portfolio_home_maturity_remediation_export"
    assert packet["export_status"] == "blocked"
    assert packet["remediation_blockers"] == [
        "bond_maturity_queue_not_empty",
        "tyw_liability_maturity_queue_not_empty",
    ]
    assert packet["export_summary"] == {
        "bond_missing_maturity_rows": 2,
        "tyw_liability_missing_maturity_rows": 2,
        "bond_missing_maturity_market_value": "300.00000000",
        "tyw_liability_missing_maturity_principal": "40.00000000",
    }
    assert packet["acceptance_criteria"]["strict_gate_command"] == (
        "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty"
    )
    assert packet["acceptance_criteria"]["no_frontend_or_inferred_fill"] is True
    assert packet["acceptance_criteria"]["generated_owner_fields_must_be_blank"] is True

    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    bond_rows = _read_csv(Path(str(export_files["bond_missing_maturity_csv"])))
    tyw_rows = _read_csv(Path(str(export_files["tyw_liability_missing_maturity_csv"])))
    manifest = json.loads(Path(str(export_files["manifest_json"])).read_text(encoding="utf-8"))
    owner_summary = Path(str(export_files["owner_summary_md"])).read_text(encoding="utf-8")

    assert [row["instrument_code"] for row in bond_rows] == ["BOND-LARGE", "BOND-SMALL"]
    assert [row["position_id"] for row in tyw_rows] == ["POS-LARGE", "POS-SMALL"]
    assert bond_rows[0]["proposed_maturity_date"] == ""
    assert bond_rows[0]["owner_decision"] == ""
    assert tyw_rows[0]["proposed_maturity_date"] == ""
    assert tyw_rows[0]["owner_comment"] == ""
    assert manifest["export_summary"] == packet["export_summary"]
    assert manifest["acceptance_criteria"]["requires_source_remediation_or_signed_exclusion"] is True
    assert manifest["acceptance_criteria"]["generated_owner_fields_must_be_blank"] is True
    assert "# Portfolio Home Maturity Remediation Summary" in owner_summary
    assert "This summary is not an approval." in owner_summary
    assert "- Export status: `blocked`" in owner_summary
    assert "- Report date: `2026-05-31`" in owner_summary
    assert "- Required fields: `proposed_maturity_date`, `owner_decision`, `owner_comment`" in owner_summary
    assert "- Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`" in owner_summary
    assert "- Strict gate: `python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`" in owner_summary
    assert "- Bond missing maturity rows: `2`" in owner_summary
    assert "- Bond missing maturity market value: `300.00000000`" in owner_summary
    assert "- TYW liability missing maturity rows: `2`" in owner_summary
    assert "- TYW liability missing maturity principal: `40.00000000`" in owner_summary
    assert "- Decision queue: `bond_missing_maturity.csv`, `tyw_liability_missing_maturity.csv`" in owner_summary
    assert "- Generated owner fields must be blank: `true`" in owner_summary
    assert "## Owner Instructions" in owner_summary
    assert "- Fill `owner_decision` on every bond and TYW liability row." in owner_summary
    assert "- Fill `owner_comment` on every bond and TYW liability row for every decision value." in owner_summary
    assert "- Use `remediate_source` only when the source maturity date will be fixed and rematerialized." in owner_summary
    assert "- Use `approve_scoped_exclusion` only with a signed exclusion rationale in `owner_comment`." in owner_summary
    assert "- Do not use frontend-inferred dates or synthetic maturity dates as remediation evidence." in owner_summary
    assert "- Do not edit `manifest.json`; rerun the export after owner decisions are captured." in owner_summary
    assert "## Post-Decision Verification" in owner_summary
    assert "- `python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`" in owner_summary
    assert "- `python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent`" in owner_summary
    assert "- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready`" in owner_summary
    assert "- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`" in owner_summary
    assert "A filled CSV is still not approval until source remediation or signed exclusion evidence is captured and the business-owner approval template is completed." in owner_summary


def test_portfolio_home_maturity_remediation_export_check_current_allows_owner_input_without_rewrite(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    output_dir = tmp_path / "maturity-export"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        output_dir=output_dir,
    )
    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    bond_csv = Path(str(export_files["bond_missing_maturity_csv"]))
    tyw_csv = Path(str(export_files["tyw_liability_missing_maturity_csv"]))
    bond_rows = _read_csv(bond_csv)
    tyw_rows = _read_csv(tyw_csv)
    bond_rows[0]["proposed_maturity_date"] = "2030-05-31"
    bond_rows[0]["owner_decision"] = "remediate_source"
    bond_rows[0]["owner_comment"] = "owner source remediation ticket opened"
    tyw_rows[0]["owner_decision"] = "approve_scoped_exclusion"
    tyw_rows[0]["owner_comment"] = "owner signed scoped exclusion"
    _write_csv(bond_csv, bond_rows)
    _write_csv(tyw_csv, tyw_rows)
    before_bond = bond_csv.read_text(encoding="utf-8-sig")
    before_tyw = tyw_csv.read_text(encoding="utf-8-sig")

    returncode, payload = _run_export(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--output-dir",
        str(output_dir),
        "--check-current",
    )

    assert returncode == 0
    assert payload["status"] == "current"
    assert payload["current"] is True
    assert payload["owner_input_boundary"] == {
        "owner_fields_are_owner_owned": True,
        "check_current_does_not_require_owner_fields_blank": True,
    }
    assert bond_csv.read_text(encoding="utf-8-sig") == before_bond
    assert tyw_csv.read_text(encoding="utf-8-sig") == before_tyw


def test_portfolio_home_maturity_remediation_export_check_current_blocks_stale_generated_fields(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    output_dir = tmp_path / "maturity-export"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        output_dir=output_dir,
    )
    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    manifest_json = Path(str(export_files["manifest_json"]))
    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    manifest["export_summary"]["bond_missing_maturity_rows"] = 1
    manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_export(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--output-dir",
        str(output_dir),
        "--check-current",
    )

    assert returncode == 1
    assert payload["status"] == "stale"
    assert "manifest_export_summary_mismatch" in payload["current_blockers"]


def test_portfolio_home_maturity_remediation_export_cli_require_clean_blocks_missing_rows(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    output_dir = tmp_path / "maturity-export"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)

    returncode, payload = _run_export(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--output-dir",
        str(output_dir),
        "--require-clean",
    )

    assert returncode == 1
    assert payload["export_status"] == "blocked"
    assert payload["export_files"]["manifest_json"].endswith("manifest.json")
    assert Path(payload["export_files"]["bond_missing_maturity_csv"]).exists()


def test_portfolio_home_maturity_remediation_export_cli_require_clean_allows_empty_queue(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)

    returncode, payload = _run_export(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--require-clean",
    )

    assert returncode == 0
    assert payload["export_status"] == "clean"
    assert payload["remediation_blockers"] == []
    assert payload["export_files"] is None
