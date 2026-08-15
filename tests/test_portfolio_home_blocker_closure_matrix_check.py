from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.portfolio_home_blocker_closure_matrix_check import (
    build_report,
    matrix_completeness_report,
)
from scripts.portfolio_home_business_owner_approval_packet import (
    PORTFOLIO_HOME_SCORE_BLOCKERS,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_blocker_closure_matrix_check.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DUCKDB.exists(),
        reason="requires local governed DuckDB at data/moss.duckdb",
    ),
]
CURRENT_SCORE_BLOCKERS = PORTFOLIO_HOME_SCORE_BLOCKERS


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


def test_portfolio_home_blocker_closure_matrix_check_reports_current_matrix() -> None:
    report = build_report(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=2,
    )

    assert report["status"] == "clean"
    assert report["blockers"] == []
    live_score_blockers = report["score_blockers"]
    # score_status/full_score_ready/score_blockers 都是本机治理库当前实际生效的
    # 可变状态，随库状态演进而变化；只锁定代码不变式（ready 当且仅当无阻塞项）
    # 与合法取值域，不锁定具体分数状态或阻塞项名单。
    assert report["score_status"] in {"blocked", "ready_for_full_score"}
    assert isinstance(report["full_score_ready"], bool)
    assert report["full_score_ready"] is (live_score_blockers == [])
    assert report["score_status"] == (
        "ready_for_full_score" if report["full_score_ready"] else "blocked"
    )
    # 只锁定它是完整闭环目录 CURRENT_SCORE_BLOCKERS 的合法子序列（成员+相对顺序不变式）。
    assert set(live_score_blockers).issubset(set(CURRENT_SCORE_BLOCKERS))
    assert live_score_blockers == [
        blocker for blocker in CURRENT_SCORE_BLOCKERS if blocker in live_score_blockers
    ]
    assert report["matrix_coverage"] == {
        "status": "clean",
        "expected_blockers": live_score_blockers,
        "covered_blockers": live_score_blockers,
        "missing_blockers": [],
        "unexpected_blockers": [],
        "duplicate_blockers": [],
    }
    assert [row["blocker"] for row in report["matrix_rows"]] == live_score_blockers
    for row in report["matrix_rows"]:
        assert row["status"] == "clean"
        assert row["owner"] in {"risk_owner", "data_owner", "business_owner"}
        assert row["next_action"]
        assert row["exit_criteria"]
        assert row["removes_blocker_when"]
        assert row["recheck_commands"]
        assert row["unallowlisted_recheck_commands"] == []

    risk_warning_row = report["matrix_rows"][0]
    assert risk_warning_row["blocker"] == "risk_tensor_quality_warning"
    assert risk_warning_row["decision_artifacts"] == []
    assert risk_warning_row["required_fields"] == []
    assert risk_warning_row["evidence_sources"] == [
        {
            "name": "risk_warning_consistency",
            "command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                "--report-date 2026-05-31 --require-consistent"
            ),
            "fields": [
                    "parsed_warnings",
                    "recomputed_warnings",
                    "duration_exclusion_delta_detail",
                    "warning_resolution_matrix",
                    "decision_blockers",
                ],
            "boundary": (
                "Evidence-only warning consistency check; does not approve the metric, "
                "clean the risk tensor, or close the page."
            ),
        },
    ]
    assert risk_warning_row["unallowlisted_evidence_source_commands"] == []

    warning_evidence_blockers = {
        "risk_tensor_quality_warning",
        "bond_matured_outstanding_reconciliation_required",
        "krd_bucket_warning_mismatch",
        "duration_exclusion_warning_mismatch",
        "risk_tensor_warning_mismatch",
    }
    decision_rows = [
        row for row in report["matrix_rows"] if row["blocker"] not in warning_evidence_blockers
    ]
    for row in decision_rows:
        assert row["decision_artifacts"]
        assert row["required_fields"]
        assert row["evidence_sources"] == []
        assert row["unallowlisted_evidence_source_commands"] == []


def test_portfolio_home_blocker_closure_matrix_check_cli_require_clean() -> None:
    returncode, payload = _run_check("--limit", "2", "--require-clean")

    assert returncode == 0
    assert payload["status"] == "clean"
    live_score_blockers = payload["score_blockers"]
    assert set(live_score_blockers).issubset(set(CURRENT_SCORE_BLOCKERS))
    assert live_score_blockers == [
        blocker for blocker in CURRENT_SCORE_BLOCKERS if blocker in live_score_blockers
    ]


def test_portfolio_home_blocker_closure_matrix_check_blocks_missing_row_fields() -> None:
    report = matrix_completeness_report(
        score_blockers=[
            "risk_tensor_quality_warning",
            "business_owner_approval",
        ],
        matrix=[
            {
                "blocker": "risk_tensor_quality_warning",
                "owner": "risk_owner",
                "next_action": "",
                "decision_artifacts": [],
                "required_fields": [],
                "recheck_commands": [],
                "exit_criteria": "",
                "removes_blocker_when": "",
            },
            {
                "blocker": "business_owner_approval",
                "owner": "business_owner",
                "next_action": "Collect approval.",
                "decision_artifacts": [],
                "required_fields": [],
                "recheck_commands": ["python scripts/check_portfolio_home_business_owner_approval.py --require-captured"],
                "exit_criteria": "Approval checker exits 0.",
                "removes_blocker_when": "Business owner signs approval.",
            },
        ],
    )

    assert report["status"] == "blocked"
    assert report["blockers"] == [
        "risk_tensor_quality_warning_evidence_sources_missing",
        "risk_tensor_quality_warning_next_action_missing",
        "risk_tensor_quality_warning_recheck_commands_missing",
        "risk_tensor_quality_warning_exit_criteria_missing",
        "risk_tensor_quality_warning_removes_blocker_when_missing",
        "business_owner_approval_decision_artifacts_missing",
        "business_owner_approval_required_fields_missing",
    ]
    assert report["matrix_rows"][0]["missing_fields"] == [
        "evidence_sources",
        "next_action",
        "recheck_commands",
        "exit_criteria",
        "removes_blocker_when",
    ]
    assert report["matrix_rows"][1]["missing_fields"] == [
        "decision_artifacts",
        "required_fields",
    ]


def test_portfolio_home_blocker_closure_matrix_check_blocks_unallowlisted_recheck_commands() -> None:
    report = matrix_completeness_report(
        score_blockers=["risk_tensor_quality_warning"],
        matrix=[
            {
                "blocker": "risk_tensor_quality_warning",
                "owner": "risk_owner",
                "next_action": "Review risk warning.",
                "decision_artifacts": [],
                "evidence_sources": [
                    {
                        "name": "risk_warning_consistency",
                        "command": (
                            "python scripts/portfolio_home_risk_warning_consistency.py "
                            "--require-consistent"
                        ),
                        "fields": ["parsed_warnings"],
                        "boundary": "Evidence only.",
                    },
                ],
                "required_fields": [],
                "recheck_commands": [
                    "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
                    "python scripts/not_allowlisted.py --require-clean",
                ],
                "exit_criteria": "Risk warning clean gate exits 0.",
                "removes_blocker_when": "Risk tensor quality is clean.",
            },
        ],
        verification_commands=[
            "python scripts/portfolio_home_risk_warning_consistency.py --require-consistent",
            "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        ],
    )

    assert report["status"] == "blocked"
    assert report["blockers"] == [
        "risk_tensor_quality_warning_recheck_commands_unallowlisted",
    ]
    assert report["matrix_rows"][0]["unallowlisted_recheck_commands"] == [
        "python scripts/not_allowlisted.py --require-clean",
    ]


def test_portfolio_home_blocker_closure_matrix_check_blocks_missing_risk_warning_evidence_source() -> None:
    report = matrix_completeness_report(
        score_blockers=["risk_tensor_quality_warning"],
        matrix=[
            {
                "blocker": "risk_tensor_quality_warning",
                "owner": "risk_owner",
                "next_action": "Review risk warning.",
                "decision_artifacts": [],
                "required_fields": [],
                "recheck_commands": [
                    "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
                ],
                "exit_criteria": "Risk warning clean gate exits 0.",
                "removes_blocker_when": "Risk tensor quality is clean.",
            },
        ],
        verification_commands=[
            "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        ],
    )

    assert report["status"] == "blocked"
    assert report["blockers"] == [
        "risk_tensor_quality_warning_evidence_sources_missing",
    ]
    assert report["matrix_rows"][0]["missing_fields"] == ["evidence_sources"]


def test_portfolio_home_blocker_closure_matrix_check_blocks_unallowlisted_evidence_source_command() -> None:
    report = matrix_completeness_report(
        score_blockers=["risk_tensor_quality_warning"],
        matrix=[
            {
                "blocker": "risk_tensor_quality_warning",
                "owner": "risk_owner",
                "next_action": "Review risk warning.",
                "decision_artifacts": [],
                "evidence_sources": [
                    {
                        "name": "risk_warning_consistency",
                        "command": "python scripts/not_allowlisted.py",
                        "fields": ["parsed_warnings"],
                        "boundary": "Evidence only.",
                    },
                ],
                "required_fields": [],
                "recheck_commands": [
                    "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
                ],
                "exit_criteria": "Risk warning clean gate exits 0.",
                "removes_blocker_when": "Risk tensor quality is clean.",
            },
        ],
        verification_commands=[
            "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        ],
    )

    assert report["status"] == "blocked"
    assert report["blockers"] == [
        "risk_tensor_quality_warning_evidence_source_commands_unallowlisted",
    ]
    assert report["matrix_rows"][0]["unallowlisted_evidence_source_commands"] == [
        "python scripts/not_allowlisted.py",
    ]


def test_portfolio_home_blocker_closure_matrix_check_rejects_negative_limit() -> None:
    with pytest.raises(ValueError) as error:
        build_report(
            duckdb_path=DUCKDB,
            report_date="2026-05-31",
            template_path=TEMPLATE,
            docs_root=ROOT / "docs",
            limit=-1,
        )

    assert str(error.value) == "Portfolio-home blocker closure matrix limit must be non-negative: -1"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home blocker closure matrix limit must be non-negative: -1" in completed.stderr
