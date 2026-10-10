from __future__ import annotations

import csv
from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

import scripts.portfolio_home_krd_contract_decision_export as krd_export
from scripts.portfolio_home_krd_contract_decision_export import build_export_packet
from scripts.portfolio_home_krd_remap_review_queue import build_queue


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_krd_remap_review_queue.py"
EXPORT_SCRIPT = ROOT / "scripts" / "portfolio_home_krd_contract_decision_export.py"
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
              tenor_bucket varchar,
              dv01 decimal(24, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
    finally:
        connection.close()


def _insert_decision_required_data(path: Path) -> None:
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
                    "BOND-2Y",
                    "Two Year Bond",
                    "book-a",
                    "cc-a",
                    Decimal("100"),
                    "2028-05-31",
                    "2Y",
                    Decimal("2"),
                    "sv_bond",
                    "rv_bond",
                    "batch-1",
                    "trace-2y",
                ],
                [
                    REPORT_DATE,
                    "BOND-6M-NONZERO",
                    "Six Month Nonzero",
                    "book-b",
                    "cc-b",
                    Decimal("80"),
                    "2026-11-30",
                    "6M",
                    Decimal("3"),
                    "sv_bond",
                    "rv_bond",
                    "batch-2",
                    "trace-6m-nonzero",
                ],
                [
                    REPORT_DATE,
                    "BOND-6M-ZERO",
                    "Six Month Zero",
                    "book-b",
                    "cc-b",
                    Decimal("70"),
                    None,
                    "6M",
                    Decimal("0"),
                    "sv_bond",
                    "rv_bond",
                    "batch-3",
                    "trace-6m-zero",
                ],
                [
                    REPORT_DATE,
                    "BOND-11Y",
                    "Unsupported Tenor",
                    "book-c",
                    "cc-c",
                    Decimal("60"),
                    "2037-05-31",
                    "11Y",
                    Decimal("4"),
                    "sv_bond",
                    "rv_bond",
                    "batch-4",
                    "trace-11y",
                ],
                [
                    REPORT_DATE,
                    "BOND-5Y",
                    "Supported Tenor",
                    "book-d",
                    "cc-d",
                    Decimal("50"),
                    "2031-05-31",
                    "5Y",
                    Decimal("5"),
                    "sv_bond",
                    "rv_bond",
                    "batch-5",
                    "trace-5y",
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
              ?, 'BOND-5Y', 'Supported Tenor', 'book', 'cc', ?, '2031-05-31',
              '5Y', ?, 'sv_bond', 'rv_bond', 'batch-1', 'trace-5y'
            )
            """,
            [REPORT_DATE, Decimal("50"), Decimal("5")],
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


def test_portfolio_home_krd_remap_review_queue_reports_decision_required_scope(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)

    queue = build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=2)

    assert queue["review_status"] == "decision_required"
    assert queue["review_blockers"] == [
        "krd_contract_decision_required",
        "unsupported_krd_bucket",
    ]
    assert queue["decision_options"] == [
        "approve_nearest_bucket",
        "require_exact_bucket_schema",
        "reject",
    ]
    assert queue["review_actions"] == [
        {
            "blocker": "krd_contract_decision_required",
            "owner": "risk_owner",
            "next_action": "Approve current nearest-bucket KRD mapping or require exact tenor buckets before full closure.",
            "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
            "exit_criteria": "Approved metric contract covers every mapped non-standard tenor or no non-standard tenor carries non-zero DV01.",
        },
        {
            "blocker": "unsupported_krd_bucket",
            "owner": "risk_owner",
            "next_action": "Map the unsupported tenor in the metric contract or reject the current KRD tensor for full closure.",
            "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
            "exit_criteria": "No unsupported tenor carries non-zero DV01 under the formal risk-tensor contract.",
        },
    ]
    assert queue["krd_remap_summary"] == [
        {
            "tenor_bucket": "11Y",
            "all_rows": 1,
            "nonzero_dv01_rows": 1,
            "all_market_value": "60.00000000",
            "nonzero_dv01_market_value": "60.00000000",
            "dv01_sum": "4.00000000",
            "mapped_to": None,
            "mapping_status": "unsupported",
        },
        {
            "tenor_bucket": "2Y",
            "all_rows": 1,
            "nonzero_dv01_rows": 1,
            "all_market_value": "100.00000000",
            "nonzero_dv01_market_value": "100.00000000",
            "dv01_sum": "2.00000000",
            "mapped_to": "krd_3y",
            "mapping_status": "mapped",
        },
        {
            "tenor_bucket": "6M",
            "all_rows": 2,
            "nonzero_dv01_rows": 1,
            "all_market_value": "150.00000000",
            "nonzero_dv01_market_value": "80.00000000",
            "dv01_sum": "3.00000000",
            "mapped_to": "krd_1y",
            "mapping_status": "mapped",
        },
    ]
    assert queue["krd_remap_rows"] == [
        {
            "report_date": REPORT_DATE,
            "instrument_code": "BOND-11Y",
            "instrument_name": "Unsupported Tenor",
            "portfolio_name": "book-c",
            "cost_center": "cc-c",
            "market_value": "60.00000000",
            "maturity_date": "2037-05-31",
            "tenor_bucket": "11Y",
            "dv01": "4.00000000",
            "mapped_to": None,
            "mapping_status": "unsupported",
            "source_version": "sv_bond",
            "rule_version": "rv_bond",
            "ingest_batch_id": "batch-4",
            "trace_id": "trace-11y",
        },
        {
            "report_date": REPORT_DATE,
            "instrument_code": "BOND-6M-NONZERO",
            "instrument_name": "Six Month Nonzero",
            "portfolio_name": "book-b",
            "cost_center": "cc-b",
            "market_value": "80.00000000",
            "maturity_date": "2026-11-30",
            "tenor_bucket": "6M",
            "dv01": "3.00000000",
            "mapped_to": "krd_1y",
            "mapping_status": "mapped",
            "source_version": "sv_bond",
            "rule_version": "rv_bond",
            "ingest_batch_id": "batch-2",
            "trace_id": "trace-6m-nonzero",
        },
    ]


def test_portfolio_home_krd_remap_review_queue_rejects_negative_limit_before_query(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)

    try:
        build_queue(duckdb_path=duckdb_path, report_date=REPORT_DATE, limit=-1)
    except ValueError as exc:
        assert str(exc) == "Portfolio-home KRD review limit must be non-negative: -1"
    else:
        raise AssertionError("negative KRD review limit should be rejected")


def test_portfolio_home_krd_remap_review_queue_cli_rejects_negative_limit(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
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
    assert "Portfolio-home KRD review limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_krd_remap_review_queue_require_clean_blocks_pending_decision(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)

    returncode, payload = _run_queue(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--limit",
        "2",
        "--require-clean",
    )

    assert returncode == 1
    assert payload["review_status"] == "decision_required"
    assert "krd_contract_decision_required" in payload["review_blockers"]


def test_portfolio_home_krd_remap_review_queue_require_clean_allows_supported_buckets(
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
        "--require-clean",
    )

    assert returncode == 0
    assert payload["review_status"] == "clean"
    assert payload["review_blockers"] == []
    assert payload["review_actions"] == []
    assert payload["krd_remap_summary"] == []
    assert payload["krd_remap_rows"] == []


def test_portfolio_home_krd_contract_decision_export_writes_risk_owner_package(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    output_dir = tmp_path / "krd-export"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)

    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        output_dir=output_dir,
    )

    assert packet["packet_kind"] == "portfolio_home_krd_contract_decision_export"
    assert packet["export_status"] == "decision_required"
    assert packet["review_blockers"] == [
        "krd_contract_decision_required",
        "unsupported_krd_bucket",
    ]
    assert packet["export_summary"] == {
        "remap_tenor_count": 3,
        "mapped_tenor_count": 2,
        "unsupported_tenor_count": 1,
        "nonzero_dv01_rows": 3,
        "dv01_sum": "9.00000000",
    }
    assert packet["acceptance_criteria"]["risk_owner_decision_required"] is True
    assert packet["acceptance_criteria"]["does_not_approve_nearest_bucket"] is True
    assert packet["acceptance_criteria"]["generated_owner_fields_must_be_blank"] is True

    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    summary_rows = _read_csv(Path(str(export_files["krd_remap_summary_csv"])))
    detail_rows = _read_csv(Path(str(export_files["krd_remap_detail_csv"])))
    manifest = json.loads(Path(str(export_files["manifest_json"])).read_text(encoding="utf-8"))
    owner_summary = Path(str(export_files["owner_summary_md"])).read_text(encoding="utf-8")

    assert [row["tenor_bucket"] for row in summary_rows] == ["11Y", "2Y", "6M"]
    assert summary_rows[0]["risk_owner_decision"] == ""
    assert summary_rows[0]["decision_notes"] == ""
    assert [row["instrument_code"] for row in detail_rows] == [
        "BOND-11Y",
        "BOND-6M-NONZERO",
        "BOND-2Y",
    ]
    assert detail_rows[0]["risk_owner_decision"] == ""
    assert manifest["export_summary"] == packet["export_summary"]
    assert manifest["acceptance_criteria"]["generated_owner_fields_must_be_blank"] is True
    assert "# Portfolio Home KRD Contract Decision Summary" in owner_summary
    assert "This summary is not an approval." in owner_summary
    assert "- Export status: `decision_required`" in owner_summary
    assert "- Report date: `2026-05-31`" in owner_summary
    assert "- Required fields: `risk_owner_decision`, `decision_notes`" in owner_summary
    assert "- Allowed decisions: `approve_nearest_bucket`, `require_exact_bucket_schema`, `reject`" in owner_summary
    assert "- Strict gate: `python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`" in owner_summary
    assert "- Remap tenor count: `3`" in owner_summary
    assert "- Non-zero DV01 rows: `3`" in owner_summary
    assert "- DV01 sum: `9.00000000`" in owner_summary
    assert "- Decision queue: `krd_remap_summary.csv`, `krd_remap_detail.csv`" in owner_summary
    assert "- Generated owner fields must be blank: `true`" in owner_summary
    assert "## Owner Instructions" in owner_summary
    assert "- Fill `risk_owner_decision` on every summary and detail row." in owner_summary
    assert "- Fill `decision_notes` on every summary and detail row for every decision value; include the contract rationale or rejection reason." in owner_summary
    assert "- Do not edit `manifest.json`; rerun the export after owner decisions are captured." in owner_summary
    assert "## Post-Decision Verification" in owner_summary
    assert "- `python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`" in owner_summary
    assert "- `python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent`" in owner_summary
    assert "- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready`" in owner_summary
    assert "- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`" in owner_summary
    assert "A filled CSV is still not approval until the business-owner approval template is completed and the strict scorecard gate passes." in owner_summary


def test_portfolio_home_krd_contract_decision_export_labels_repo_relative_duckdb_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root = tmp_path / "worktree"
    fake_root.mkdir()
    monkeypatch.setattr(krd_export, "ROOT", fake_root)
    monkeypatch.chdir(fake_root)

    assert krd_export._duckdb_path_label(fake_root / "data" / "moss.duckdb") == "data/moss.duckdb"
    external_duckdb = tmp_path / "external" / "moss.duckdb"
    external_duckdb.parent.mkdir(parents=True, exist_ok=True)
    external_duckdb.touch()
    escape_path = fake_root / ".." / "external" / "moss.duckdb"
    sibling_spelling = external_duckdb.parent / "." / "moss.duckdb"
    other_external_duckdb = tmp_path / "other" / "moss.duckdb"
    other_external_duckdb.parent.mkdir(parents=True, exist_ok=True)
    other_external_duckdb.touch()
    expected_external_label = str(external_duckdb.resolve())

    assert krd_export._duckdb_path_label(escape_path) == expected_external_label
    assert krd_export._duckdb_path_label(sibling_spelling) == expected_external_label
    assert krd_export._duckdb_path_label(external_duckdb) == expected_external_label
    assert krd_export._duckdb_path_label(other_external_duckdb) != expected_external_label


def test_portfolio_home_krd_contract_decision_export_check_current_allows_owner_input_without_rewrite(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    output_dir = tmp_path / "krd-export"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)
    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        output_dir=output_dir,
    )
    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    summary_csv = Path(str(export_files["krd_remap_summary_csv"]))
    detail_csv = Path(str(export_files["krd_remap_detail_csv"]))
    summary_rows = _read_csv(summary_csv)
    detail_rows = _read_csv(detail_csv)
    summary_rows[0]["risk_owner_decision"] = "approve_nearest_bucket"
    summary_rows[0]["decision_notes"] = "owner-reviewed nearest bucket"
    detail_rows[0]["risk_owner_decision"] = "approve_nearest_bucket"
    detail_rows[0]["decision_notes"] = "owner-reviewed detail"
    _write_csv(summary_csv, summary_rows)
    _write_csv(detail_csv, detail_rows)
    before_summary = summary_csv.read_text(encoding="utf-8-sig")
    before_detail = detail_csv.read_text(encoding="utf-8-sig")

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
    assert summary_csv.read_text(encoding="utf-8-sig") == before_summary
    assert detail_csv.read_text(encoding="utf-8-sig") == before_detail


def test_portfolio_home_krd_contract_decision_export_check_current_blocks_stale_generated_fields(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    output_dir = tmp_path / "krd-export"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)
    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        output_dir=output_dir,
    )
    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    manifest_json = Path(str(export_files["manifest_json"]))
    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    manifest["export_summary"]["dv01_sum"] = "8.00000000"
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


def test_portfolio_home_krd_contract_decision_export_cli_require_clean_blocks_pending_decision(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "krd.duckdb"
    output_dir = tmp_path / "krd-export"
    _create_schema(duckdb_path)
    _insert_decision_required_data(duckdb_path)

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
    assert payload["export_status"] == "decision_required"
    assert payload["export_files"]["manifest_json"].endswith("manifest.json")


def test_portfolio_home_krd_contract_decision_export_cli_require_clean_allows_supported_buckets(
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
    assert payload["review_blockers"] == []
    assert payload["export_files"] is None
