from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.portfolio_home_owner_input_needed_summary as owner_input_summary_module
from scripts.portfolio_home_business_owner_approval_packet import (
    PORTFOLIO_HOME_SCORE_BLOCKERS,
)
from scripts.portfolio_home_owner_action_packet import build_packet
from scripts.portfolio_home_owner_input_needed_summary import build_summary


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_owner_input_needed_summary.py"
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


def _ready_packet() -> dict[str, object]:
    return {
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": REPORT_DATE,
        "duckdb_path": str(DUCKDB),
        "template_path": str(TEMPLATE),
        "current_score": "100.00 / 100",
        "remaining_gap": "0.00",
        "score_status": "ready_for_full_score",
        "full_score_ready": True,
        "score_blockers": ["risk_tensor_quality_warning"],
        "dependency_consistency_status": "consistent",
        "dependency_consistency_blockers": [],
        "owner_decision_intake_alignment": {
            "status": "consistent",
            "blockers": [],
            "compared_fields": [],
        },
        "owner_decision_intake_summary": {
            "intake_ready": True,
            "owner_decision_statuses": {
                "risk_owner": "ready",
                "data_owner": "ready",
                "business_owner": "ready",
            },
            "owner_decision_blockers": [],
            "owner_input_boundary": {},
            "export_current_summary": {
                "krd": {"status": "current", "current": True, "current_blockers": []},
                "maturity": {"status": "current", "current": True, "current_blockers": []},
            },
            "decision_gap_counts": {
                "krd": {"missing_decision_rows": 0},
                "maturity": {"missing_decision_rows": 0},
            },
        },
        "assignment_coverage": {
            "status": "clean",
            "score_blockers": ["risk_tensor_quality_warning"],
            "assigned_blockers": ["risk_tensor_quality_warning"],
            "unassigned_blockers": [],
            "duplicate_assigned_blockers": [],
            "unexpected_assigned_blockers": [],
        },
        "score_blocker_action_coverage": {
            "status": "clean",
            "blockers": [],
            "unassigned_blockers": [],
            "covered_blockers": ["risk_tensor_quality_warning"],
        },
        "blocker_closure_matrix_coverage": {
            "status": "clean",
            "expected_blockers": ["risk_tensor_quality_warning"],
            "covered_blockers": ["risk_tensor_quality_warning"],
            "missing_blockers": [],
            "unexpected_blockers": [],
            "duplicate_blockers": [],
        },
        "closure_artifact_presence_summary": {
            "status": "current",
            "current": True,
            "blockers": [],
            "artifact_current_summary": {},
        },
        "evidence_dependencies": [
            {"name": "signoff_packet", "path": "docs/portfolio/signoff.md", "available": True},
        ],
        "blocker_closure_matrix": [
            {
                "blocker": "risk_tensor_quality_warning",
                "decision_artifacts": [],
                "required_fields": [],
                "recheck_commands": [
                    "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
                ],
                "exit_criteria": "Risk warning clean gate exits 0.",
            },
        ],
        "owner_packets": {
            "risk_owner": {
                "status": "clean",
                "blockers": ["risk_tensor_quality_warning"],
                "risk_tensor_quality_flag": "ok",
            },
            "data_owner": {"status": "clean", "blockers": []},
            "business_owner": {
                "status": "clean",
                "blockers": [],
                "approval_status": "captured",
                "approval_action_item_count": 0,
                "business_owner_approval_boundary": {
                    "status": "activated",
                    "blockers": [],
                },
            },
        },
    }


def _run_summary(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_owner_input_needed_summary_ready_requires_detail_gate_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = _ready_packet()
    packet["assignment_coverage"] = {"status": "clean"}
    monkeypatch.setattr(
        owner_input_summary_module,
        "build_packet",
        lambda **_: packet,
    )

    summary = build_summary(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )

    assert summary["input_status"] == "owner_input_boundary_blocked"
    assert summary["owner_input_needed"] is False
    assert summary["ready_for_intake"] is False
    assert summary["owner_input_readiness_boundary"]["status"] == "blocked"
    assert summary["owner_input_readiness_boundary"]["blockers"] == [
        "assignment_coverage_not_clean",
    ]


def test_portfolio_home_owner_input_needed_summary_ready_when_detail_gates_are_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        owner_input_summary_module,
        "build_packet",
        lambda **_: _ready_packet(),
    )

    summary = build_summary(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )

    assert summary["input_status"] == "ready_for_intake"
    assert summary["owner_input_needed"] is False
    assert summary["ready_for_intake"] is True
    assert summary["owner_input_readiness_boundary"] == {
        "status": "clean",
        "boundary_ready": True,
        "blockers": [],
        "assignment_coverage": _ready_packet()["assignment_coverage"],
        "score_blocker_action_coverage": _ready_packet()["score_blocker_action_coverage"],
        "blocker_closure_matrix_coverage": _ready_packet()[
            "blocker_closure_matrix_coverage"
        ],
        "closure_artifact_presence_summary": _ready_packet()[
            "closure_artifact_presence_summary"
        ],
        "evidence_dependencies": _ready_packet()["evidence_dependencies"],
    }


def test_portfolio_home_owner_input_needed_summary_routes_current_owner_inputs() -> None:
    # 本机治理库可变状态：score/gap/blocker 名单/行数/预览文案都会随库演进
    # 漂移。用同一份实时 build_packet(...) 结果作为事实来源，校验 summary
    # 里的取值域、类型与内部一致性，而不是锁定某个历史快照的具体数值。
    # 代码常量（字段名清单、artifact 路径模板、evidence_sources 措辞、
    # owner_input_boundary 的固定契约字段）保持精确断言。
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )
    live_score_blockers = packet["score_blockers"]
    assert isinstance(live_score_blockers, list)
    live_blocker_set = set(live_score_blockers)

    summary = build_summary(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )

    assert summary["summary_kind"] == "portfolio_home_owner_input_needed_summary"
    assert summary["page_slug"] == "portfolio"
    assert summary["report_date"] == REPORT_DATE
    assert summary["input_status"] in {"owner_input_needed", "ready_for_intake", "owner_input_boundary_blocked"}
    assert isinstance(summary["owner_input_needed"], bool)
    assert re.fullmatch(r"\d+(?:\.\d+)? / 100", str(summary["current_score"]))
    assert re.fullmatch(r"\d+(?:\.\d+)?", str(summary["remaining_gap"]))

    # score_blockers 是 PORTFOLIO_HOME_SCORE_BLOCKERS 目录的一个有序子集
    assert summary["score_blockers"] == live_score_blockers
    assert set(summary["score_blockers"]).issubset(set(PORTFOLIO_HOME_SCORE_BLOCKERS))
    assert [
        blocker for blocker in PORTFOLIO_HOME_SCORE_BLOCKERS if blocker in live_blocker_set
    ] == summary["score_blockers"]

    assert set(summary["owner_decision_statuses"].keys()) == {
        "risk_owner",
        "data_owner",
        "business_owner",
    }
    for status in summary["owner_decision_statuses"].values():
        assert status in {"ready", "pending"}

    missing_counts = summary["missing_input_counts"]
    assert isinstance(missing_counts["krd_missing_decision_rows"], int)
    assert missing_counts["krd_missing_decision_rows"] >= 0
    assert isinstance(missing_counts["maturity_missing_decision_rows"], int)
    assert missing_counts["maturity_missing_decision_rows"] >= 0
    assert isinstance(missing_counts["business_owner_approval_action_items"], int)
    assert missing_counts["business_owner_approval_action_items"] >= 0

    owner_input_boundary = summary["owner_input_boundary"]
    # 固定契约字段（是否允许生成字段留空/是否要求导出当前等）是代码常量
    assert owner_input_boundary["generated_export_owner_fields_must_be_blank"] is True
    assert owner_input_boundary["filled_owner_fields_are_owner_input_only"] is True
    assert owner_input_boundary["generated_export_system_fields_must_be_current"] is True
    assert owner_input_boundary["allowed_pre_intake_dependency_blockers"] == [
        "krd_contract_decision_manifest_owner_decision_fields_not_blank",
        "maturity_remediation_manifest_owner_fields_not_blank",
    ]
    for key in (
        "pre_intake_dependency_blockers",
        "active_dependency_blockers",
        "active_export_current_blockers",
    ):
        assert isinstance(owner_input_boundary[key], list)

    # evidence_scope 是该报表类型的固定语义模板（本报表从不批准/写入治理），
    # 属于代码常量
    assert summary["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "fills_owner_decisions": False,
        "remediates_source_data": False,
        "captures_business_owner_approval": False,
        "proves_full_score_closure": False,
        "certification_effect": "none",
    }

    routes = {route["owner"]: route for route in summary["owner_routes"]}
    assert routes["risk_owner"]["input_status"] in {"owner_input_needed", "ready_for_intake"}
    risk_owner_expected_blockers = [
        blocker
        for blocker in ("risk_tensor_quality_warning", "krd_contract_decision_required")
        if blocker in live_blocker_set
    ]
    assert routes["risk_owner"]["blockers"] == risk_owner_expected_blockers

    risk_gap_counts = routes["risk_owner"]["decision_gap_counts"]
    assert risk_gap_counts["missing_decision_rows"] == (
        risk_gap_counts["summary_missing_decision_rows"]
        + risk_gap_counts["detail_missing_decision_rows"]
    )
    for key in risk_gap_counts:
        assert isinstance(risk_gap_counts[key], int)
        assert risk_gap_counts[key] >= 0

    risk_preview = routes["risk_owner"]["risk_tensor_rematerialization_preview"]
    assert risk_preview["status"] in {"would_remain_blocked", "would_be_clean"}
    assert risk_preview["preview_basis"] == "current_formal_facts_read_only"
    assert risk_preview["writes_database"] is False
    assert risk_preview["approves_metric_or_page"] is False
    assert risk_preview["certification_effect"] == "none"
    for key in (
        "current_consistency_blockers",
        "would_clear_consistency_blockers",
        "preview_consistency_blockers",
        "preview_decision_blockers",
        "preview_warnings",
    ):
        assert isinstance(risk_preview[key], list)
    assert risk_preview["preview_consistency_status"] in {"consistent", "blocked"}
    assert risk_preview["preview_quality_flag"] in {"ok", "warning"}
    assert risk_preview["preview_decision_status"] in {"clean", "blocked"}
    assert (risk_preview["preview_decision_status"] == "clean") is (
        risk_preview["preview_decision_blockers"] == []
    )

    assert routes["risk_owner"]["decision_artifacts"] == [
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv",
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
        "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
        "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
    ]
    assert {
        "name": "risk_warning_consistency",
        "command": "python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-consistent",
        "fields": [
            "parsed_warnings",
            "recomputed_warnings",
            "duration_exclusion_delta_detail",
            "warning_resolution_matrix",
            "decision_blockers",
        ],
        "boundary": (
            "Evidence-only warning consistency check; does not approve "
            "the metric, clean the risk tensor, or close the page."
        ),
    } in routes["risk_owner"]["evidence_sources"]
    assert "risk_owner_decision" in routes["risk_owner"]["required_fields"]
    assert "python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready" in routes[
        "risk_owner"
    ]["recheck_commands"]

    data_gap_counts = routes["data_owner"]["decision_gap_counts"]
    assert data_gap_counts["missing_decision_rows"] == (
        data_gap_counts["bond_missing_decision_rows"]
        + data_gap_counts["tyw_liability_missing_decision_rows"]
    )
    for key in data_gap_counts:
        assert isinstance(data_gap_counts[key], int)
        assert data_gap_counts[key] >= 0
    assert isinstance(
        routes["data_owner"]["risk_tensor_rematerialization_preview"][
            "would_clear_consistency_blockers"
        ],
        list,
    )
    assert routes["data_owner"]["risk_tensor_rematerialization_preview"][
        "preview_decision_status"
    ] in {"clean", "blocked"}
    assert (
        routes["data_owner"]["risk_tensor_rematerialization_preview"]["certification_effect"]
        == "none"
    )
    data_owner_expected_blockers = [
        blocker
        for blocker in (
            "tyw_liability_maturity_date_remediation_required",
            "bond_matured_outstanding_reconciliation_required",
        )
        if blocker in live_blocker_set
    ]
    assert routes["data_owner"]["blockers"] == data_owner_expected_blockers
    assert routes["data_owner"]["decision_artifacts"] == [
        "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv",
        "docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json",
    ]
    assert isinstance(routes["business_owner"]["approval_action_item_count"], int)
    assert routes["business_owner"]["approval_action_item_count"] >= 0
    assert routes["business_owner"]["decision_artifacts"] == [
        "docs/portfolio/portfolio-home-business-owner-approval-template.md",
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv",
        "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
        "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
        "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv",
        "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
        "docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json",
    ]


def test_portfolio_home_owner_input_needed_summary_cli_writes_and_checks_current(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "portfolio-home-owner-input-needed-summary.json"

    returncode, payload = _run_summary(
        "--limit",
        "1",
        "--output",
        str(output_path),
    )

    assert returncode == 0
    assert payload["summary_kind"] == "portfolio_home_owner_input_needed_summary"
    assert output_path.exists()

    check_returncode, check_payload = _run_summary(
        "--limit",
        "1",
        "--output",
        str(output_path),
        "--check-current",
    )

    assert check_returncode == 0
    assert check_payload["status"] == "current"
    assert check_payload["current"] is True
    assert check_payload["expected_sha256"] == check_payload["actual_sha256"]


def test_portfolio_home_owner_input_needed_summary_check_current_blocks_stale_file(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "portfolio-home-owner-input-needed-summary.json"
    output_path.write_text(json.dumps({"summary_kind": "stale"}), encoding="utf-8")

    returncode, payload = _run_summary(
        "--limit",
        "1",
        "--output",
        str(output_path),
        "--check-current",
    )

    assert returncode == 1
    assert payload["status"] == "stale"
    assert payload["current"] is False
    assert payload["expected_sha256"] != payload["actual_sha256"]
