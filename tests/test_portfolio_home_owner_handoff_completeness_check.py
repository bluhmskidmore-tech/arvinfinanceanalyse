from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.portfolio_home_owner_handoff_completeness_check import (
    build_report,
    handoff_completeness_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_owner_handoff_completeness_check.py"
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


def test_portfolio_home_owner_handoff_completeness_check_reports_current_clean_handoff() -> None:
    report = build_report(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=3,
    )

    assert report["check_kind"] == "portfolio_home_owner_handoff_completeness"
    assert report["status"] == "clean"
    assert report["handoff_ready"] is True
    assert report["blockers"] == []
    assert report["summary_current_status"]["current"] is True
    assert report["handoff_current_status"]["status"] == "current"
    assert report["owner_route_coverage"] == {
        "status": "clean",
        "required_owners": ["risk_owner", "data_owner", "business_owner"],
        "present_owners": ["risk_owner", "data_owner", "business_owner"],
        "missing_owners": [],
        "unexpected_owners": [],
        "duplicate_owners": [],
    }

    route_checks = {item["owner"]: item for item in report["route_checks"]}
    assert route_checks["risk_owner"]["status"] == "clean"
    assert route_checks["data_owner"]["status"] == "clean"
    assert route_checks["business_owner"]["status"] == "clean"
    assert route_checks["risk_owner"]["unallowlisted_recheck_commands"] == []
    assert route_checks["data_owner"]["unallowlisted_recheck_commands"] == []
    assert route_checks["business_owner"]["unallowlisted_recheck_commands"] == []
    # required_now/exists/status 反映本机 KRD 契约决策当前是否要求 exact-bucket
    # 证据，随库状态演进而变化；只锁定字段存在、取值域与代码不变式。
    exact_bucket_check = route_checks["risk_owner"]["artifact_checks"][2]
    assert exact_bucket_check["artifact"] == (
        "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json"
    )
    assert isinstance(exact_bucket_check["required_now"], bool)
    assert isinstance(exact_bucket_check["exists"], bool)
    assert exact_bucket_check["status"] in {"not_required", "valid", "missing", "blocked"}
    assert isinstance(exact_bucket_check["blockers"], list)
    assert (exact_bucket_check["status"] == "not_required") is (
        exact_bucket_check["required_now"] is False
    )
    assert report["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "fills_owner_decisions": False,
        "captures_business_owner_approval": False,
        "proves_full_score_closure": False,
        "certification_effect": "none",
    }


def test_portfolio_home_owner_handoff_completeness_check_cli_require_clean() -> None:
    returncode, payload = _run_check("--limit", "3", "--require-clean")

    assert returncode == 0
    assert payload["status"] == "clean"
    assert payload["handoff_ready"] is True


def test_portfolio_home_owner_handoff_completeness_check_blocks_stale_owner_summary(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    summary_path = docs_root / "portfolio" / "portfolio-home-owner-input-needed-summary.json"
    summary_path.write_text(json.dumps({"summary_kind": "stale"}), encoding="utf-8")

    report = build_report(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=docs_root,
        limit=1,
    )

    assert report["status"] == "blocked"
    assert report["handoff_ready"] is False
    assert "owner_input_needed_summary_stale" in report["blockers"]


def test_portfolio_home_owner_handoff_completeness_check_blocks_stale_handoff_markdown(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    handoff_path.write_text("# stale owner handoff", encoding="utf-8")

    report = build_report(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=docs_root,
        limit=1,
    )

    assert report["status"] == "blocked"
    assert report["handoff_ready"] is False
    assert report["handoff_current_status"]["status"] == "stale"
    assert "owner_handoff_packet_not_current" in report["blockers"]


def test_portfolio_home_owner_handoff_completeness_check_blocks_incomplete_route() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    route = next(item for item in summary["owner_routes"] if item["owner"] == "risk_owner")
    route["required_fields"] = []
    route["recheck_commands"] = []

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    assert report["status"] == "blocked"
    assert report["handoff_ready"] is False
    assert "risk_owner_required_fields_missing" in report["blockers"]
    assert "risk_owner_recheck_commands_missing" in report["blockers"]


def test_portfolio_home_owner_handoff_completeness_check_blocks_duplicate_owner_route() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    summary["owner_routes"].append(copy.deepcopy(summary["owner_routes"][0]))

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    assert report["status"] == "blocked"
    assert report["handoff_ready"] is False
    assert "risk_owner" in report["blockers"]
    assert report["owner_route_coverage"] == {
        "status": "blocked",
        "required_owners": ["risk_owner", "data_owner", "business_owner"],
        "present_owners": ["risk_owner", "data_owner", "business_owner", "risk_owner"],
        "missing_owners": [],
        "unexpected_owners": [],
        "duplicate_owners": ["risk_owner"],
    }


def test_portfolio_home_owner_handoff_completeness_check_blocks_unallowlisted_recheck_command() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    route = next(item for item in summary["owner_routes"] if item["owner"] == "risk_owner")
    route["recheck_commands"] = [
        "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        "python scripts/not_a_scorecard_gate.py --require-clean",
    ]

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    assert report["status"] == "blocked"
    assert report["handoff_ready"] is False
    assert "risk_owner_recheck_commands_unallowlisted" in report["blockers"]
    route_checks = {item["owner"]: item for item in report["route_checks"]}
    assert route_checks["risk_owner"]["unallowlisted_recheck_commands"] == [
        "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        "python scripts/not_a_scorecard_gate.py --require-clean",
    ]


def test_portfolio_home_owner_handoff_completeness_check_allows_date_qualified_gate() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    route = next(item for item in summary["owner_routes"] if item["owner"] == "risk_owner")
    route["recheck_commands"] = [
        "python scripts/portfolio_home_risk_warning_consistency.py "
        "--report-date 2026-05-31 --require-clean",
    ]

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    route_checks = {item["owner"]: item for item in report["route_checks"]}
    assert route_checks["risk_owner"]["status"] == "clean"
    assert route_checks["risk_owner"]["unallowlisted_recheck_commands"] == []


def test_portfolio_home_owner_handoff_completeness_check_blocks_wrong_report_date() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    route = next(item for item in summary["owner_routes"] if item["owner"] == "risk_owner")
    wrong_date_command = (
        "python scripts/portfolio_home_risk_warning_consistency.py "
        "--report-date 2026-06-01 --require-clean"
    )
    route["recheck_commands"] = [wrong_date_command]

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    route_checks = {item["owner"]: item for item in report["route_checks"]}
    assert route_checks["risk_owner"]["status"] == "blocked"
    assert route_checks["risk_owner"]["unallowlisted_recheck_commands"] == [wrong_date_command]


def test_portfolio_home_owner_handoff_completeness_check_blocks_unqualified_nondefault_date() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    summary["report_date"] = "2026-06-30"
    route = next(item for item in summary["owner_routes"] if item["owner"] == "risk_owner")
    unqualified_command = (
        "python scripts/portfolio_home_risk_warning_consistency.py --require-clean"
    )
    route["recheck_commands"] = [unqualified_command]

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    route_checks = {item["owner"]: item for item in report["route_checks"]}
    assert route_checks["risk_owner"]["status"] == "blocked"
    assert route_checks["risk_owner"]["unallowlisted_recheck_commands"] == [
        unqualified_command,
    ]


def test_portfolio_home_owner_handoff_completeness_check_blocks_noncanonical_argument_order() -> None:
    summary = json.loads(
        (ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    route = next(item for item in summary["owner_routes"] if item["owner"] == "business_owner")
    reordered_command = (
        "python scripts/portfolio_home_owner_decision_intake_check.py "
        "--limit 3 --require-ready --report-date 2026-05-31"
    )
    route["recheck_commands"] = [reordered_command]

    report = handoff_completeness_report(summary, docs_root=ROOT / "docs")

    route_checks = {item["owner"]: item for item in report["route_checks"]}
    assert route_checks["business_owner"]["status"] == "blocked"
    assert route_checks["business_owner"]["unallowlisted_recheck_commands"] == [
        reordered_command,
    ]


def test_portfolio_home_owner_handoff_completeness_check_blocks_missing_required_artifact(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    summary = json.loads(
        (docs_root / "portfolio" / "portfolio-home-owner-input-needed-summary.json").read_text(
            encoding="utf-8",
        ),
    )
    stale_summary = copy.deepcopy(summary)
    required_artifact = (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / REPORT_DATE
        / "tyw_liability_missing_maturity.csv"
    )
    required_artifact.unlink()

    report = handoff_completeness_report(stale_summary, docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "data_owner_decision_artifact_missing:"
        "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv"
        in report["blockers"]
    )
