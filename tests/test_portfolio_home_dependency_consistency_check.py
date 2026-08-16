from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.portfolio_home_dependency_consistency_check import build_dependency_consistency


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_dependency_consistency_check.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
REPORT_DATE = "2026-05-31"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DUCKDB.exists(),
        reason="requires local governed DuckDB at data/moss.duckdb",
    ),
]


def _run_check(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_dependency_consistency_reports_current_clean_export_package() -> None:
    report = build_dependency_consistency(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        limit=1,
    )

    assert report["check_kind"] == "portfolio_home_dependency_consistency"
    assert report["dependency_consistency_status"] == "consistent"
    assert report["dependency_consistency_blockers"] == []
    assert report["csv_check_summary"] == {
        "krd_summary_row_count": 3,
        "krd_detail_row_count": 500,
        "krd_owner_decision_fields_blank": True,
        "bond_missing_maturity_row_count": 0,
        "tyw_liability_missing_maturity_row_count": 1455,
        "maturity_owner_fields_blank": True,
    }
    assert report["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }


def test_portfolio_home_dependency_consistency_blocks_missing_csv_files(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_root / "audits")
    (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "krd_remap_detail.csv"
    ).unlink()
    (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / REPORT_DATE
        / "tyw_liability_missing_maturity.csv"
    ).unlink()

    report = build_dependency_consistency(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_root,
    )

    assert report["dependency_consistency_status"] == "blocked"
    assert report["csv_check_summary"]["krd_detail_row_count"] is None
    assert report["csv_check_summary"]["tyw_liability_missing_maturity_row_count"] is None
    assert report["csv_check_summary"]["krd_owner_decision_fields_blank"] is False
    assert report["csv_check_summary"]["maturity_owner_fields_blank"] is False
    assert report["dependency_consistency_blockers"] == [
        "krd_contract_decision_manifest_detail_csv_row_count_mismatch",
        "krd_contract_decision_manifest_owner_decision_fields_not_blank",
        "maturity_remediation_manifest_tyw_liability_csv_row_count_mismatch",
        "maturity_remediation_manifest_owner_fields_not_blank",
    ]


def test_portfolio_home_dependency_consistency_cli_require_consistent_fails_when_csv_missing(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_root / "audits")
    (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "krd_remap_summary.csv"
    ).unlink()

    returncode, payload = _run_check(
        "--docs-root",
        str(docs_root),
        "--limit",
        "1",
        "--require-consistent",
    )

    assert returncode == 1
    assert payload["dependency_consistency_status"] == "blocked"
    assert payload["csv_check_summary"]["krd_summary_row_count"] is None


def test_portfolio_home_dependency_consistency_build_rejects_negative_limit() -> None:
    try:
        build_dependency_consistency(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            limit=-1,
        )
    except ValueError as exc:
        assert str(exc) == "Portfolio-home dependency consistency limit must be non-negative: -1"
    else:
        raise AssertionError("negative dependency consistency limit should be rejected")


def test_portfolio_home_dependency_consistency_rejects_negative_limit() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home dependency consistency limit must be non-negative: -1" in completed.stderr
