from __future__ import annotations

import csv
from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from scripts.portfolio_home_maturity_remediation_export import build_export_packet
from scripts.portfolio_home_maturity_remediation_queue import (
    MATURITY_REMEDIATION_ACTIONS,
    build_queue,
)


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


def _insert_june_no_maturity_counts(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            insert into fact_formal_bond_analytics_daily
            select
              '2026-06-30',
              'BOND-NO-MATURITY-' || cast(row_number as varchar),
              'Bond Without Maturity',
              'book',
              'cc',
              case when row_number = 0 then 44190587082.30000032 else 0 end,
              null,
              0,
              null,
              'sv_bond',
              'rv_bond',
              'batch-bond',
              'trace-bond-' || cast(row_number as varchar)
            from range(127) as rows(row_number)
            """
        )
        connection.execute(
            """
            insert into fact_formal_tyw_balance_daily
            select
              '2026-06-30',
              'TYW-MISSING-' || cast(row_number as varchar),
              'deposit',
              'short',
              'Counterparty',
              'liability',
              'CNY',
              case when row_number = 0 then 47032453217.05000088 else 0 end,
              0,
              null,
              'sv_tyw',
              'rv_tyw',
              'batch-tyw',
              'trace-tyw-' || cast(row_number as varchar)
            from range(1476) as rows(row_number)
            """
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
    assert queue["remediation_blockers"] == ["tyw_liability_maturity_queue_not_empty"]
    assert queue["remediation_scope"] == {
        "bond_no_maturity_information": (
            "fact_formal_bond_analytics_daily rows where maturity_date is null; "
            "ledger null means formally no maturity date"
        ),
        "bond_queue": (
            "compatibility-only empty queue; bond ledger null maturity requires no remediation"
        ),
        "tyw_liability_queue": "fact_formal_tyw_balance_daily liability CNY rows where maturity_date is null",
    }
    assert queue["remediation_actions"] == [
        {
            "blocker": "tyw_liability_maturity_queue_not_empty",
            "owner": "data_owner",
            "next_action": "Fill missing TYW liability maturity_date values at source or capture a signed scoped exclusion.",
            "evidence_command": (
                "python scripts/portfolio_home_maturity_remediation_queue.py "
                "--report-date 2026-05-31 --require-empty"
            ),
            "exit_criteria": "TYW liability missing-maturity queue is empty or signed exclusion evidence is captured and surfaced as a boundary.",
        },
    ]
    assert queue["bond_no_maturity_summary"] == {
        "row_count": 3,
        "no_maturity_rows": 2,
        "no_maturity_market_value": "300.00000000",
    }
    assert queue["bond_missing_maturity_summary"] == {
        "row_count": 3,
        "missing_maturity_rows": 0,
        "missing_maturity_market_value": "0",
    }
    assert queue["tyw_liability_missing_maturity_summary"] == {
        "row_count": 3,
        "missing_maturity_rows": 2,
        "missing_maturity_principal": "40.00000000",
    }
    assert queue["bond_missing_maturity_rows"] == []
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


def test_portfolio_home_maturity_queue_classifies_june_bond_nulls_as_no_maturity(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "june-no-maturity.duckdb"
    _create_schema(duckdb_path)
    _insert_june_no_maturity_counts(duckdb_path)

    queue = build_queue(duckdb_path=duckdb_path, report_date="2026-06-30", limit=1)

    assert queue["bond_no_maturity_summary"] == {
        "row_count": 127,
        "no_maturity_rows": 127,
        "no_maturity_market_value": "44190587082.30000032",
    }
    assert queue["bond_missing_maturity_summary"] == {
        "row_count": 127,
        "missing_maturity_rows": 0,
        "missing_maturity_market_value": "0",
    }
    assert queue["bond_missing_maturity_rows"] == []
    assert queue["tyw_liability_missing_maturity_summary"]["missing_maturity_rows"] == 1476
    assert queue["tyw_liability_missing_maturity_summary"]["missing_maturity_principal"] == (
        "47032453217.05000088"
    )
    assert queue["remediation_blockers"] == ["tyw_liability_maturity_queue_not_empty"]


def test_portfolio_home_maturity_actions_scope_evidence_to_requested_report_date_without_mutating_spec(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "june-blocked.duckdb"
    _create_schema(duckdb_path)
    _insert_june_no_maturity_counts(duckdb_path)

    queue = build_queue(duckdb_path=duckdb_path, report_date="2026-06-30", limit=1)

    assert queue["remediation_actions"][0]["evidence_command"] == (
        "python scripts/portfolio_home_maturity_remediation_queue.py "
        "--report-date 2026-06-30 --require-empty"
    )
    assert MATURITY_REMEDIATION_ACTIONS["tyw_liability_maturity_queue_not_empty"][
        "evidence_command"
    ] == "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty"


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
    assert queue["remediation_blockers"] == ["tyw_liability_maturity_queue_not_empty"]
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
    assert candidate_evidence["next_action"] == (
        "Use TYW candidate rows only for data-owner review; strict closure still requires "
        "TYW source remediation or signed scoped exclusion evidence."
    )
    sources = {
        str(source["source_table"]): source
        for source in candidate_evidence["candidate_sources"]
    }
    assert set(sources) == {"tyw_interbank_daily_snapshot"}
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
        "tyw_interbank_daily_snapshot": "no_candidates",
    }
    assert all(
        source["sample_candidates"] == []
        for source in candidate_evidence["candidate_sources"]
    )


def test_portfolio_home_maturity_candidate_evidence_blocks_conflicting_tyw_candidates(
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
            insert into tyw_interbank_daily_snapshot values (
              ?, 'POS-LARGE', 'deposit', 'short', 'Counterparty B', ?,
              'sv_candidate_tyw', 'rv_candidate_tyw', 'batch-candidate-tyw', ?
            )
            """,
            [
                [REPORT_DATE, "2026-08-31", "trace-candidate-tyw-a"],
                [REPORT_DATE, "2026-09-30", "trace-candidate-tyw-b"],
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
    assert set(sources) == {"tyw_interbank_daily_snapshot"}
    assert sources["tyw_interbank_daily_snapshot"]["status"] == "conflicting_candidates"
    assert sources["tyw_interbank_daily_snapshot"]["summary"] == {
        "missing_rows": 2,
        "matched_missing_rows": 1,
        "candidate_rows": 2,
        "ambiguous_key_count": 1,
        "candidate_principal": "30.00000000",
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
    assert payload["remediation_blockers"] == ["tyw_liability_maturity_queue_not_empty"]


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
    assert packet["remediation_blockers"] == ["tyw_liability_maturity_queue_not_empty"]
    assert packet["export_summary"] == {
        "bond_no_maturity_rows": 2,
        "bond_no_maturity_market_value": "300.00000000",
        "bond_missing_maturity_rows": 0,
        "bond_missing_maturity_market_value": "0",
        "tyw_liability_missing_maturity_rows": 2,
        "tyw_liability_missing_maturity_principal": "40.00000000",
    }
    assert packet["acceptance_criteria"]["strict_gate_command"] == (
        "python scripts/portfolio_home_maturity_remediation_queue.py "
        "--report-date 2026-05-31 --require-empty"
    )
    assert packet["acceptance_criteria"]["no_frontend_or_inferred_fill"] is True
    assert packet["acceptance_criteria"]["generated_owner_fields_must_be_blank"] is True
    assert packet["acceptance_criteria"]["owner_decision_scope"] == "TYW liability missing-maturity rows only"
    assert packet["acceptance_criteria"]["bond_no_maturity_requires_owner_decision"] is False

    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    bond_rows = _read_csv(Path(str(export_files["bond_missing_maturity_csv"])))
    tyw_rows = _read_csv(Path(str(export_files["tyw_liability_missing_maturity_csv"])))
    manifest = json.loads(Path(str(export_files["manifest_json"])).read_text(encoding="utf-8"))
    owner_summary = Path(str(export_files["owner_summary_md"])).read_text(encoding="utf-8")

    assert bond_rows == []
    assert [row["position_id"] for row in tyw_rows] == ["POS-LARGE", "POS-SMALL"]
    assert tyw_rows[0]["proposed_maturity_date"] == ""
    assert tyw_rows[0]["owner_comment"] == ""
    assert manifest["export_summary"] == packet["export_summary"]
    assert manifest["acceptance_criteria"]["requires_source_remediation_or_signed_exclusion"] is True
    assert manifest["acceptance_criteria"]["owner_decision_scope"] == "TYW liability missing-maturity rows only"
    assert manifest["acceptance_criteria"]["generated_owner_fields_must_be_blank"] is True
    assert "# Portfolio Home Maturity Remediation Summary" in owner_summary
    assert "This summary is not an approval." in owner_summary
    assert "- Export status: `blocked`" in owner_summary
    assert "- Report date: `2026-05-31`" in owner_summary
    assert "- Required TYW fields on every row: `owner_decision`, `owner_comment`" in owner_summary
    assert (
        "- Conditionally required TYW field: `proposed_maturity_date` only when "
        "`owner_decision=remediate_source`"
    ) in owner_summary
    assert "- Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`" in owner_summary
    assert (
        "- Strict gate: `python scripts/portfolio_home_maturity_remediation_queue.py "
        "--report-date 2026-05-31 --require-empty`"
    ) in owner_summary
    assert "- Bond no-maturity rows: `2`" in owner_summary
    assert "- Bond no-maturity market value: `300.00000000`" in owner_summary
    assert "- Bond remediation rows (compatibility): `0`" in owner_summary
    assert "- TYW liability missing maturity rows: `2`" in owner_summary
    assert "- TYW liability missing maturity principal: `40.00000000`" in owner_summary
    assert "- Decision queue: `tyw_liability_missing_maturity.csv` only" in owner_summary
    assert "- Compatibility file: `bond_missing_maturity.csv` is header-only; no bond owner decision is required." in owner_summary
    assert "- Bond ledger boundary: null `maturity_date` means no maturity date and requires no owner-supplied date." in owner_summary
    assert "- Generated owner fields must be blank: `true`" in owner_summary
    assert "## Owner Instructions" in owner_summary
    assert "- Fill `owner_decision` on every TYW liability row." in owner_summary
    assert "- Fill `owner_comment` on every TYW liability row for every decision value." in owner_summary
    assert (
        "- Fill `proposed_maturity_date` only when `owner_decision` is "
        "`remediate_source`; leave it blank for `approve_scoped_exclusion` and `reject`."
    ) in owner_summary
    assert "- Use `remediate_source` only when the TYW source maturity date will be fixed and rematerialized." in owner_summary
    assert "- Use `approve_scoped_exclusion` only with a signed TYW exclusion rationale in `owner_comment`." in owner_summary
    assert "- Do not use frontend-inferred dates or synthetic TYW maturity dates as remediation evidence." in owner_summary
    assert "- After owner decisions are captured, do not rerun the normal export; use `--check-current` before owner-decision intake." in owner_summary
    assert "## Post-Decision Verification" in owner_summary
    assert (
        "- `python scripts/portfolio_home_maturity_remediation_export.py "
        "--report-date 2026-05-31 --output-dir docs/portfolio/maturity-remediation --check-current`"
    ) in owner_summary
    assert (
        "- `python scripts/portfolio_home_maturity_remediation_queue.py "
        "--report-date 2026-05-31 --require-empty`"
    ) in owner_summary
    assert (
        "- `python scripts/portfolio_home_dependency_consistency_check.py "
        "--report-date 2026-05-31 --limit 3 --require-consistent`"
    ) in owner_summary
    assert (
        "- `python scripts/portfolio_home_owner_decision_intake_check.py "
        "--report-date 2026-05-31 --limit 3 --require-ready`"
    ) in owner_summary
    assert (
        "- `python scripts/portfolio_home_closure_scorecard.py "
        "--report-date 2026-05-31 --limit 3 --require-full-score`"
    ) in owner_summary
    assert "A filled TYW CSV is still not approval until source remediation or signed exclusion evidence is captured and the business-owner approval template is completed." in owner_summary


def test_portfolio_home_maturity_remediation_export_strict_gate_uses_requested_report_date(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    _create_schema(duckdb_path)

    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date="2026-06-30",
        output_dir=tmp_path / "maturity-export",
        write_files=False,
    )

    assert packet["acceptance_criteria"]["strict_gate_command"] == (
        "python scripts/portfolio_home_maturity_remediation_queue.py "
        "--report-date 2026-06-30 --require-empty"
    )


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
    tyw_rows = _read_csv(tyw_csv)
    tyw_rows[0]["proposed_maturity_date"] = "2030-05-31"
    tyw_rows[0]["owner_decision"] = "approve_scoped_exclusion"
    tyw_rows[0]["owner_comment"] = "owner signed scoped exclusion"
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


def test_portfolio_home_maturity_remediation_export_refuses_to_overwrite_owner_input(
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
    tyw_csv = Path(str(export_files["tyw_liability_missing_maturity_csv"]))
    tyw_rows = _read_csv(tyw_csv)
    tyw_rows[0]["proposed_maturity_date"] = "2030-05-31"
    tyw_rows[0]["owner_decision"] = "remediate_source"
    tyw_rows[0]["owner_comment"] = "owner source remediation ticket opened"
    _write_csv(tyw_csv, tyw_rows)
    before_tyw = tyw_csv.read_text(encoding="utf-8-sig")

    try:
        build_export_packet(
            duckdb_path=duckdb_path,
            report_date=REPORT_DATE,
            output_dir=output_dir,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("normal export must not overwrite nonblank owner input")

    assert "Refusing to overwrite maturity remediation owner input" in message
    assert "tyw_liability_missing_maturity.csv" in message
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
    manifest["export_summary"]["bond_no_maturity_rows"] = 1
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
