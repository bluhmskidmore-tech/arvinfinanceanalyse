from __future__ import annotations

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


def _insert_consistent_warning_data(path: Path, *, duration_rows: int = 3) -> None:
    warnings = [
        "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y, 6M",
        (
            f"{duration_rows} rows carry market_value=60.00000000 and are excluded from portfolio "
            "duration denominator: 2 without maturity_date; 1 with non-positive modified_duration. "
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
    assert evidence["warning_resolution_matrix"] == [
        {
            "warning_key": "krd_bucket_remap",
            "owner": "risk_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": ["2Y", "6M"],
                "recomputed": ["2Y", "6M"],
            },
            "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
            "exit_criteria": (
                "Risk owner approves nearest-bucket KRD mapping or supplies exact-bucket "
                "schema evidence; KRD review queue exits 0."
            ),
            "evidence_scope": {
                "captures_owner_decision": False,
                "remediates_source_data": False,
                "approves_metric_or_page": False,
                "certification_effect": "none",
            },
        },
        {
            "warning_key": "duration_denominator_exclusion",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {
                    "row_count": 3,
                    "market_value_sum": "60.00000000",
                    "missing_maturity_rows": 2,
                    "nonpositive_duration_rows": 1,
                },
                "recomputed": {
                    "row_count": 3,
                    "market_value_sum": "60.00000000",
                    "missing_maturity_rows": 2,
                    "nonpositive_duration_rows": 1,
                },
            },
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
            "exit_criteria": (
                "Data owner remediates missing maturity dates or captures signed scoped "
                "exclusion; maturity remediation queue exits 0."
            ),
            "evidence_scope": {
                "captures_owner_decision": False,
                "remediates_source_data": False,
                "approves_metric_or_page": False,
                "certification_effect": "none",
            },
        },
        {
            "warning_key": "bond_liquidity_gap_missing_maturity",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"missing_maturity_rows": 2},
                "recomputed": {"missing_maturity_rows": 2},
            },
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
            "exit_criteria": (
                "Bond missing maturity rows are remediated or signed scoped exclusion "
                "evidence is captured; maturity remediation queue exits 0."
            ),
            "evidence_scope": {
                "captures_owner_decision": False,
                "remediates_source_data": False,
                "approves_metric_or_page": False,
                "certification_effect": "none",
            },
        },
        {
            "warning_key": "tyw_liability_gap_missing_maturity",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"missing_maturity_rows": 1},
                "recomputed": {"missing_maturity_rows": 1},
            },
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
            "exit_criteria": (
                "TYW liability missing maturity rows are remediated or signed scoped "
                "exclusion evidence is captured; maturity remediation queue exits 0."
            ),
            "evidence_scope": {
                "captures_owner_decision": False,
                "remediates_source_data": False,
                "approves_metric_or_page": False,
                "certification_effect": "none",
            },
        },
    ]
    assert evidence["parsed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert evidence["recomputed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert evidence["parsed_warnings"]["duration_exclusion"] == {
        "row_count": 3,
        "market_value_sum": "60.00000000",
        "missing_maturity_rows": 2,
        "nonpositive_duration_rows": 1,
    }
    assert evidence["recomputed_warnings"]["duration_exclusion"] == {
        "row_count": 3,
        "market_value_sum": "60.00000000",
        "missing_maturity_rows": 2,
        "nonpositive_duration_rows": 1,
    }
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
            "duration denominator: 2 without maturity_date; 1 with non-positive "
            "modified_duration. DV01 totals remain sourced from row dv01; duration "
            "metrics ignore these rows until inputs are remediated."
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
    ] == ["clean", "clean", "clean", "clean"]
