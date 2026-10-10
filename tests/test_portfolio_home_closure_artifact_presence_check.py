from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.portfolio_home_closure_artifact_presence_check import (
    artifact_presence_report,
    build_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_closure_artifact_presence_check.py"
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


def test_portfolio_home_closure_artifact_presence_check_reports_current_real_docs() -> None:
    report = build_report(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )

    assert report["status"] == "current"
    assert report["current"] is True
    assert report["blockers"] == []
    assert report["artifact_current_summary"] == {
        "krd": {
            "status": "current",
            "current": True,
            "current_blockers": [],
        },
        "maturity": {
            "status": "current",
            "current": True,
            "current_blockers": [],
        },
        "business_owner_approval_template": {
            "status": "present",
            "current": True,
            "current_blockers": [],
        },
        "exact_bucket_schema_evidence": {
            "status": "not_required",
            "current": True,
            "current_blockers": [],
        },
        "nearest_bucket_approval_evidence": {
            "status": "not_required",
            "current": True,
            "current_blockers": [],
        },
        "maturity_scoped_exclusion_evidence": {
            "status": "not_required",
            "current": True,
            "current_blockers": [],
        },
    }
    assert {
        row["artifact"]
        for row in report["artifact_rows"]
        if row["required_now"]
    } == {
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv",
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
        "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv",
        "docs/portfolio/portfolio-home-business-owner-approval-template.md",
    }


def test_portfolio_home_closure_artifact_presence_check_cli_require_current() -> None:
    returncode, payload = _run_check("--limit", "1", "--require-current")

    assert returncode == 0
    assert payload["status"] == "current"
    assert payload["blockers"] == []


def test_portfolio_home_closure_artifact_presence_check_blocks_missing_owner_artifact(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "krd_remap_detail.csv"
    ).unlink()

    report = build_report(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=docs_root,
        limit=1,
    )

    assert report["status"] == "stale"
    assert report["current"] is False
    assert "krd_contract_decision_export_stale" in report["blockers"]
    assert "krd_remap_detail_csv_missing" in report["blockers"]
    detail_row = next(
        row
        for row in report["artifact_rows"]
        if row["artifact"].endswith("krd_remap_detail.csv")
    )
    assert detail_row["status"] == "missing"
    assert detail_row["exists"] is False


def test_portfolio_home_closure_artifact_presence_check_blocks_stale_report_date(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    manifest_path = (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / REPORT_DATE
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["report_date"] = "2026-04-30"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check(
        "--docs-root",
        str(docs_root),
        "--limit",
        "1",
        "--require-current",
    )

    assert returncode == 1
    assert payload["status"] == "stale"
    assert "maturity_remediation_export_stale" in payload["blockers"]
    assert "manifest_report_date_mismatch" in payload["blockers"]


def test_portfolio_home_closure_artifact_presence_check_tracks_conditional_exact_bucket_schema() -> None:
    report = artifact_presence_report(
        docs_root=ROOT / "docs",
        report_date=REPORT_DATE,
        closure_matrix=[
            {
                "blocker": "krd_contract_decision_required",
                "decision_artifacts": [
                    (
                        "docs/portfolio/krd-contract-decision/2026-05-31/"
                        "exact_bucket_schema_evidence.json"
                    ),
                ],
            },
        ],
        artifact_current_summary={
            "krd": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "maturity": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "business_owner_approval_template": {
                "status": "present",
                "current": True,
                "current_blockers": [],
            },
            "exact_bucket_schema_evidence": {
                "status": "required",
                "current": False,
                "current_blockers": ["krd_exact_bucket_schema_evidence_missing"],
            },
        },
    )

    assert report["status"] == "stale"
    assert report["blockers"] == ["krd_exact_bucket_schema_evidence_missing"]
    assert report["artifact_rows"] == [
        {
            "artifact": (
                "docs/portfolio/krd-contract-decision/2026-05-31/"
                "exact_bucket_schema_evidence.json"
            ),
            "status": "missing",
            "exists": False,
            "required_now": True,
            "blockers": ["krd_exact_bucket_schema_evidence_missing"],
        },
    ]


def test_portfolio_home_closure_artifact_presence_check_keeps_missing_artifact_blockers_specific(
    tmp_path: Path,
) -> None:
    report = artifact_presence_report(
        docs_root=tmp_path / "docs",
        report_date=REPORT_DATE,
        closure_matrix=[
            {
                "blocker": "krd_contract_decision_required",
                "decision_artifacts": [
                    "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
                    (
                        "docs/portfolio/krd-contract-decision/2026-05-31/"
                        "exact_bucket_schema_evidence.json"
                    ),
                ],
            },
        ],
        artifact_current_summary={
            "krd": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "maturity": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "business_owner_approval_template": {
                "status": "present",
                "current": True,
                "current_blockers": [],
            },
            "exact_bucket_schema_evidence": {
                "status": "required",
                "current": False,
                "current_blockers": ["krd_exact_bucket_schema_evidence_missing"],
            },
        },
    )

    assert report["status"] == "stale"
    assert report["blockers"] == [
        "krd_exact_bucket_schema_evidence_missing",
        "krd_remap_detail_csv_missing",
    ]
    rows = {row["artifact"]: row for row in report["artifact_rows"]}
    assert rows[
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv"
    ]["blockers"] == ["krd_remap_detail_csv_missing"]
    assert rows[
        (
            "docs/portfolio/krd-contract-decision/2026-05-31/"
            "exact_bucket_schema_evidence.json"
        )
    ]["blockers"] == ["krd_exact_bucket_schema_evidence_missing"]


def test_portfolio_home_closure_artifact_presence_check_rejects_negative_limit() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert (
        "Portfolio-home closure artifact presence limit must be non-negative: -1"
        in completed.stderr
    )
