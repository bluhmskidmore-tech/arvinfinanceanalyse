from __future__ import annotations

import argparse
from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from scripts.portfolio_home_risk_warning_consistency import build_evidence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_risk_warning_consistency.py"
REPORT_DATE = "2026-05-31"


def _create_schema(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar,
              quality_flag varchar,
              warnings_json varchar
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              tenor_bucket varchar,
              dv01 decimal(24, 8),
              market_value decimal(24, 8),
              maturity_date varchar,
              modified_duration decimal(18, 8)
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


def _insert_consistent_warning_data(
    path: Path, *, duration_rows: int = 3, include_zero_dv01_fallback_row: bool = False
) -> None:
    warnings = [
        "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y, 6M",
        (
            f"{duration_rows} rows carry market_value=60.00000000 and are excluded from portfolio "
            "duration denominator: 2 without maturity_date (market_value=40.00000000); "
            "0 matured on or before report_date with outstanding market_value "
            "(market_value=0.00000000); 1 future-dated with non-positive "
            "modified_duration (market_value=20.00000000). "
            "DV01 totals remain sourced from row dv01; duration metrics ignore these rows until inputs are remediated."
        ),
        "Excluded 2 rows without maturity_date from liquidity gap calculation.",
        "Excluded 1 liability rows without maturity_date from liquidity gap calculation.",
    ]
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            "insert into fact_formal_risk_tensor_daily values (?, 'warning', ?)",
            [REPORT_DATE, json.dumps(warnings)],
        )
        connection.executemany(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?, ?)",
            [
                [REPORT_DATE, "2Y", Decimal("2"), Decimal("10"), "2028-05-31", Decimal("1")],
                [REPORT_DATE, "6M", Decimal("3"), Decimal("20"), "2026-11-30", Decimal("1")],
                [REPORT_DATE, "1Y", Decimal("0"), Decimal("30"), None, None],
                [REPORT_DATE, "3Y", Decimal("0"), Decimal("10"), None, None],
                [REPORT_DATE, "5Y", Decimal("0"), Decimal("20"), "2031-05-31", Decimal("0")],
                *(
                    [[REPORT_DATE, "20Y", Decimal("0E-8"), Decimal("0"), "2046-05-31", Decimal("1")]]
                    if include_zero_dv01_fallback_row
                    else []
                ),
            ],
        )
        connection.executemany(
            "insert into fact_formal_tyw_balance_daily values (?, ?, ?, ?, ?)",
            [
                [REPORT_DATE, "liability", "CNY", Decimal("100"), None],
                [REPORT_DATE, "liability", "CNY", Decimal("200"), "2026-07-31"],
                [REPORT_DATE, "asset", "CNY", Decimal("300"), None],
            ],
        )
    finally:
        connection.close()


def _insert_clean_data(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            "insert into fact_formal_risk_tensor_daily values (?, 'ok', '[]')",
            [REPORT_DATE],
        )
        connection.execute(
            "insert into fact_formal_bond_analytics_daily values (?, '5Y', ?, ?, '2031-05-31', ?)",
            [REPORT_DATE, Decimal("5"), Decimal("50"), Decimal("1")],
        )
        connection.execute(
            "insert into fact_formal_tyw_balance_daily values (?, 'liability', 'CNY', ?, '2026-07-31')",
            [REPORT_DATE, Decimal("100")],
        )
    finally:
        connection.close()


def _run_checker(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_risk_warning_consistency_allows_consistent_warning_but_blocks_clean(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "warning.duckdb"
    _create_schema(duckdb_path)
    _insert_consistent_warning_data(duckdb_path)

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    assert evidence["warning_consistency_status"] == "consistent"
    assert evidence["decision_status"] == "blocked"
    assert evidence["evidence_scope"] == {
        "checks_warning_consistency": True,
        "checks_risk_tensor_clean_state": True,
        "captures_risk_owner_decision": False,
        "remediates_source_data": False,
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "captures_business_owner_approval": False,
        "proves_full_score_closure": False,
        "certification_effect": "none",
    }
    assert evidence["consistency_blockers"] == []
    assert evidence["decision_blockers"] == ["risk_tensor_quality_warning"]
    resolution = {
        row["warning_key"]: row
        for row in evidence["warning_resolution_matrix"]
    }
    assert list(resolution) == [
        "krd_bucket_remap",
        "duration_no_maturity",
        "matured_or_expired_outstanding",
        "nonpositive_duration",
        "bond_liquidity_gap_no_maturity",
        "tyw_liability_gap_missing_maturity",
    ]
    assert resolution["krd_bucket_remap"]["current_status"] == "blocked"
    assert resolution["duration_no_maturity"]["owner"] == "none"
    assert resolution["duration_no_maturity"]["current_status"] == "informational"
    assert resolution["matured_or_expired_outstanding"]["current_status"] == "clean"
    assert resolution["nonpositive_duration"]["current_status"] == "blocked"
    assert resolution["bond_liquidity_gap_no_maturity"]["current_status"] == "informational"
    assert resolution["tyw_liability_gap_missing_maturity"]["current_status"] == "blocked"
    assert resolution["krd_bucket_remap"]["evidence_command"] == (
        f"python scripts/portfolio_home_krd_remap_review_queue.py "
        f"--report-date {REPORT_DATE} --require-clean"
    )
    assert resolution["tyw_liability_gap_missing_maturity"]["evidence_command"] == (
        f"python scripts/portfolio_home_maturity_remediation_queue.py "
        f"--report-date {REPORT_DATE} --require-empty"
    )
    assert evidence["parsed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert evidence["recomputed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    expected_duration = {
        "row_count": 3,
        "market_value_sum": "60.00000000",
        "no_maturity_rows": 2,
        "no_maturity_market_value": "40.00000000",
        "matured_or_expired_outstanding_rows": 0,
        "matured_or_expired_outstanding_market_value": "0.00000000",
        "nonpositive_duration_rows": 1,
        "nonpositive_duration_market_value": "20.00000000",
    }
    assert evidence["parsed_warnings"]["duration_exclusion"] == expected_duration
    assert evidence["recomputed_warnings"]["duration_exclusion"] == expected_duration
    preview = evidence["risk_tensor_rematerialization_preview"]
    assert preview["preview_basis"] == "current_formal_facts_read_only"
    assert preview["writes_database"] is False
    assert preview["certification_effect"] == "none"
    assert preview["current_consistency_blockers"] == []
    assert preview["would_clear_consistency_blockers"] == []
    assert preview["preview_consistency_status"] == "consistent"
    assert preview["preview_quality_flag"] == "warning"
    assert preview["preview_decision_status"] == "blocked"
    assert preview["preview_decision_blockers"] == ["risk_tensor_quality_warning"]
    assert preview["preview_warnings"] == [
        "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y, 6M",
        (
            "3 rows carry market_value=60.00000000 and are excluded from portfolio "
            "duration denominator: 2 without maturity_date (market_value=40.00000000); "
            "0 matured on or before report_date with outstanding market_value "
            "(market_value=0.00000000); 1 future-dated with non-positive "
            "modified_duration (market_value=20.00000000). DV01 totals remain sourced "
            "from row dv01; duration metrics ignore these rows until inputs are "
            "remediated."
        ),
        "Excluded 2 rows without maturity_date from liquidity gap calculation.",
        "Excluded 1 liability rows without maturity_date from liquidity gap calculation.",
    ]

    returncode, payload = _run_checker(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--require-consistent",
    )
    assert returncode == 0
    assert payload["warning_consistency_status"] == "consistent"
    assert payload["evidence_scope"]["certification_effect"] == "none"

    returncode, payload = _run_checker(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--require-clean",
    )
    assert returncode == 1
    assert payload["decision_status"] == "blocked"


def test_portfolio_home_risk_warning_consistency_ignores_zero_dv01_fallback_rows(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "warning-zero-fallback.duckdb"
    _create_schema(duckdb_path)
    _insert_consistent_warning_data(duckdb_path, include_zero_dv01_fallback_row=True)

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    assert evidence["warning_consistency_status"] == "consistent"
    assert evidence["consistency_blockers"] == []
    assert evidence["parsed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert evidence["recomputed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert evidence["risk_tensor_rematerialization_preview"]["current_consistency_blockers"] == []
    assert evidence["risk_tensor_rematerialization_preview"]["preview_consistency_status"] == "consistent"




def test_portfolio_home_risk_warning_consistency_blocks_mismatched_warning_numbers(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "mismatch.duckdb"
    _create_schema(duckdb_path)
    _insert_consistent_warning_data(duckdb_path, duration_rows=9)

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    assert evidence["warning_consistency_status"] == "mismatch"
    assert evidence["consistency_blockers"] == ["duration_exclusion_warning_mismatch"]
    assert evidence["parsed_warnings"]["duration_exclusion"]["row_count"] == 9
    assert evidence["recomputed_warnings"]["duration_exclusion"]["row_count"] == 3
    preview = evidence["risk_tensor_rematerialization_preview"]
    assert preview["status"] == "would_remain_blocked"
    assert preview["current_consistency_blockers"] == ["duration_exclusion_warning_mismatch"]
    assert preview["would_clear_consistency_blockers"] == [
        "duration_exclusion_warning_mismatch",
    ]
    assert preview["preview_consistency_status"] == "consistent"
    assert preview["preview_decision_blockers"] == ["risk_tensor_quality_warning"]
    assert preview["preview_warnings"][1].startswith(
        "3 rows carry market_value=60.00000000",
    )

    returncode, payload = _run_checker(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--require-consistent",
    )
    assert returncode == 1
    assert payload["warning_consistency_status"] == "mismatch"


def test_portfolio_home_risk_warning_consistency_require_clean_allows_clean_tensor(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)

    returncode, payload = _run_checker(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--require-clean",
    )

    assert returncode == 0
    assert payload["warning_consistency_status"] == "consistent"
    assert payload["decision_status"] == "clean"
    assert payload["evidence_scope"] == {
        "checks_warning_consistency": True,
        "checks_risk_tensor_clean_state": True,
        "captures_risk_owner_decision": False,
        "remediates_source_data": False,
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "captures_business_owner_approval": False,
        "proves_full_score_closure": False,
        "certification_effect": "none",
    }
    assert payload["consistency_blockers"] == []
    assert payload["decision_blockers"] == []
    assert payload["risk_tensor_rematerialization_preview"] == {
        "status": "would_be_clean",
        "preview_basis": "current_formal_facts_read_only",
        "writes_database": False,
        "approves_metric_or_page": False,
        "certification_effect": "none",
        "current_consistency_blockers": [],
        "would_clear_consistency_blockers": [],
        "preview_consistency_status": "consistent",
        "preview_consistency_blockers": [],
        "preview_quality_flag": "ok",
        "preview_decision_status": "clean",
        "preview_decision_blockers": [],
        "preview_warnings": [],
    }
    assert [
        row["current_status"]
        for row in payload["warning_resolution_matrix"]
    ] == ["clean", "informational", "clean", "clean", "informational", "clean"]


def test_portfolio_home_risk_warning_consistency_separates_matured_outstanding(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "matured-outstanding.duckdb"
    _create_schema(duckdb_path)
    warnings = [
        (
            "3 rows carry market_value=60.00000000 and are excluded from portfolio "
            "duration denominator: 1 without maturity_date (market_value=30.00000000); "
            "1 matured on or before report_date with outstanding market_value "
            "(market_value=20.00000000); 1 future-dated with non-positive "
            "modified_duration (market_value=10.00000000). DV01 totals remain sourced "
            "from row dv01; duration metrics ignore these rows until inputs are remediated."
        ),
        "Excluded 1 rows without maturity_date from liquidity gap calculation.",
    ]
    connection = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        connection.execute(
            "insert into fact_formal_risk_tensor_daily values (?, 'warning', ?)",
            [REPORT_DATE, json.dumps(warnings)],
        )
        connection.executemany(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?, ?)",
            [
                [REPORT_DATE, "5Y", Decimal("1"), Decimal("50"), "2031-05-31", Decimal("1")],
                [REPORT_DATE, "5Y", Decimal("0"), Decimal("30"), None, Decimal("0")],
                [REPORT_DATE, "5Y", Decimal("0"), Decimal("20"), REPORT_DATE, Decimal("0")],
                [REPORT_DATE, "5Y", Decimal("0"), Decimal("10"), "2027-05-31", Decimal("0")],
            ],
        )
    finally:
        connection.close()

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    expected_duration = {
        "row_count": 3,
        "market_value_sum": "60.00000000",
        "no_maturity_rows": 1,
        "no_maturity_market_value": "30.00000000",
        "matured_or_expired_outstanding_rows": 1,
        "matured_or_expired_outstanding_market_value": "20.00000000",
        "nonpositive_duration_rows": 1,
        "nonpositive_duration_market_value": "10.00000000",
    }
    assert evidence["parsed_warnings"]["duration_exclusion"] == expected_duration
    assert evidence["recomputed_warnings"]["duration_exclusion"] == expected_duration
    assert evidence["warning_consistency_status"] == "consistent"
    breakdown = {
        row["exclusion_reason"]: row
        for row in evidence["duration_exclusion_delta_detail"][
            "recomputed_breakdown_by_reason"
        ]
    }
    assert breakdown["no_maturity"]["row_count"] == 1
    assert breakdown["matured_or_expired_outstanding"]["row_count"] == 1
    assert breakdown["nonpositive_duration"]["row_count"] == 1
    resolution = {
        row["warning_key"]: row
        for row in evidence["warning_resolution_matrix"]
    }
    matured_resolution = resolution["matured_or_expired_outstanding"]
    assert matured_resolution["owner"] == "data_owner"
    assert matured_resolution["current_status"] == "blocked"
    assert matured_resolution["evidence_command"] == (
        "python scripts/portfolio_home_matured_outstanding_queue.py "
        f"--report-date {REPORT_DATE} --require-empty"
    )
    assert matured_resolution["exit_criteria"] == (
        "Matured or unparseable non-zero bond positions are reconciled at source, and "
        "the matured-outstanding strict queue exits 0; exception evidence cannot close "
        "this blocker."
    )


def test_portfolio_home_risk_warning_consistency_routes_unparseable_maturity_to_reconciliation_blocker(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "unparseable-maturity.duckdb"
    _create_schema(duckdb_path)
    _insert_consistent_warning_data(duckdb_path)
    connection = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        connection.execute(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?, ?)",
            [
                REPORT_DATE,
                "1Y",
                Decimal("0.3"),
                Decimal("75"),
                "not-a-date",
                Decimal("0.7"),
            ],
        )
    finally:
        connection.close()

    evidence = build_evidence(duckdb_path=duckdb_path, report_date=REPORT_DATE)

    assert evidence["warning_consistency_status"] == "mismatch"
    assert evidence["consistency_blockers"] == [
        "duration_exclusion_warning_mismatch"
    ]
    assert evidence["decision_status"] == "blocked"
    assert "risk_tensor_warning_mismatch" in evidence["decision_blockers"]
    recomputed_duration = evidence["recomputed_warnings"]["duration_exclusion"]
    assert recomputed_duration["matured_or_expired_outstanding_rows"] == 1
    assert (
        recomputed_duration["matured_or_expired_outstanding_market_value"]
        == "75.00000000"
    )

    resolution = {
        row["warning_key"]: row
        for row in evidence["warning_resolution_matrix"]
    }
    matured_resolution = resolution["matured_or_expired_outstanding"]
    assert matured_resolution["owner"] == "data_owner"
    assert matured_resolution["current_status"] == "blocked"
    assert matured_resolution["current_evidence"] == {
        "parsed": {"row_count": 0, "market_value": "0.00000000"},
        "recomputed": {"row_count": 1, "market_value": "75.00000000"},
    }
    assert matured_resolution["evidence_command"] == (
        "python scripts/portfolio_home_matured_outstanding_queue.py "
        f"--report-date {REPORT_DATE} --require-empty"
    )

    samples = evidence["duration_exclusion_delta_detail"][
        "top_recomputed_rows_by_market_value"
    ]
    unparseable_sample = next(
        row for row in samples if row["maturity_date"] == "not-a-date"
    )
    assert unparseable_sample["exclusion_reason"] == "matured_or_expired_outstanding"


def test_build_evidence_rejects_malformed_report_date_before_database_connect(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import scripts.portfolio_home_risk_warning_consistency as risk_warning_mod

    def forbidden_connect(*args, **kwargs):
        raise AssertionError("malformed report_date must be rejected before database connect")

    monkeypatch.setattr(risk_warning_mod.duckdb, "connect", forbidden_connect)

    try:
        build_evidence(
            duckdb_path=tmp_path / "must-not-be-opened.duckdb",
            report_date="not-a-date",
        )
    except argparse.ArgumentTypeError as exc:
        message = str(exc)
    else:
        raise AssertionError("malformed report_date must be rejected")

    assert message == "invalid report date 'not-a-date'; expected YYYY-MM-DD"


def test_cli_rejects_malformed_report_date_without_duckdb_failure_or_clean_payload(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duckdb-path",
            str(tmp_path / "must-not-be-opened.duckdb"),
            "--report-date",
            "not-a-date",
            "--require-clean",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "invalid report date 'not-a-date'; expected YYYY-MM-DD" in completed.stderr
    assert "_duckdb" not in completed.stderr
    assert "ConversionException" not in completed.stderr
    assert '"decision_status": "clean"' not in completed.stdout
