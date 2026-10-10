from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.portfolio_home_evidence_snapshot import (
    build_snapshot,
    owner_handoff_completeness_alignment,
    portable_verification_report,
    snapshot_sha256,
    owner_decision_intake_alignment,
)
from scripts.portfolio_home_business_owner_approval_packet import build_packet
from scripts.portfolio_home_business_owner_approval_packet import (
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
)

from scripts.portfolio_home_closure_scorecard import VERIFICATION_COMMANDS
from scripts.verify_portfolio_home_scorecard_commands import RUNNER_COMMAND_NAME

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_evidence_snapshot.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"

pytestmark = [
    pytest.mark.governance_meta,
    pytest.mark.integration,
    pytest.mark.skipif(
        not DUCKDB.exists(),
        reason="requires local governed DuckDB at data/moss.duckdb",
    ),
]


# 状态/证据字段的合法取值域（来自 scripts/portfolio_home_* 构建器的代码取值）。
SCORE_STATUS_DOMAIN = {"blocked", "ready_for_full_score"}
ALIGNMENT_STATUS_DOMAIN = {"consistent", "blocked"}
EVIDENCE_STATUS_DOMAIN = {"valid", "blocked", "missing", "not_required"}
OWNER_ROUTE_KEYS = {"risk_owner", "data_owner", "business_owner"}


def _assert_str_list(value: object) -> None:
    assert isinstance(value, list)
    assert all(isinstance(item, str) and item for item in value)


def _assert_evidence_status_block(block: object, *, artifact: str | None = None) -> None:
    assert isinstance(block, dict)
    assert block["status"] in EVIDENCE_STATUS_DOMAIN
    assert isinstance(block["valid"], bool)
    _assert_str_list(block["blockers"])
    if artifact is not None:
        assert block["artifact"] == artifact


def _run_snapshot(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_evidence_snapshot_summarizes_current_blocked_state() -> None:
    snapshot = build_snapshot(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        scorecard_limit=1,
        verifier_limit=1,
    )

    # —— 宽松结构守卫：字段在场、格式与取值域合法、代码不变式成立 ——
    # 不锁定本机瞬时状态值（分数、阻塞清单、行数随治理库与 docs 工件演进而漂移）。
    assert snapshot["snapshot_kind"] == "portfolio_home_closure_evidence"
    assert re.fullmatch(r"\d+(?:\.\d+)? / 100", str(snapshot["current_score"]))
    assert re.fullmatch(r"\d+(?:\.\d+)?", str(snapshot["remaining_gap"]))
    assert snapshot["score_status"] in SCORE_STATUS_DOMAIN
    assert isinstance(snapshot["full_score_ready"], bool)
    _assert_str_list(snapshot["score_blockers"])
    # scorecard 代码不变式：full_score_ready 当且仅当 score_blockers 全部闭合。
    assert snapshot["full_score_ready"] is (snapshot["score_blockers"] == [])
    assert snapshot["score_status"] == (
        "ready_for_full_score" if snapshot["full_score_ready"] else "blocked"
    )

    gate_summary = snapshot["gate_summary"]
    assert isinstance(gate_summary["risk_tensor_quality_flag"], str)
    assert gate_summary["risk_tensor_quality_flag"]
    bond_missing_rows = gate_summary["bond_missing_maturity_rows"]
    assert bond_missing_rows is None or (
        isinstance(bond_missing_rows, int) and bond_missing_rows >= 0
    )
    assert isinstance(gate_summary["owner_decision_intake_status"], str)
    assert gate_summary["owner_decision_intake_status"]
    assert isinstance(gate_summary["owner_decision_intake_ready"], bool)
    _assert_str_list(gate_summary["owner_decision_intake_blockers"])
    assert gate_summary["owner_decision_intake_alignment_status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(gate_summary["owner_decision_intake_alignment_blockers"])
    assert isinstance(gate_summary["score_blocker_action_coverage_status"], str)
    assert gate_summary["score_blocker_action_coverage_status"]
    _assert_str_list(gate_summary["score_blocker_action_coverage_blockers"])
    _assert_str_list(gate_summary["score_blocker_action_coverage_unassigned_blockers"])
    assert gate_summary["approval_dependency_consistency_status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(gate_summary["approval_dependency_consistency_blockers"])
    assert set(gate_summary["generated_owner_fields_boundaries"]) == {
        "krd_contract_decision_manifest",
        "maturity_remediation_manifest",
    }
    assert all(
        isinstance(value, bool)
        for value in gate_summary["generated_owner_fields_boundaries"].values()
    )
    assert isinstance(gate_summary["owner_handoff_completeness_status"], str)
    assert gate_summary["owner_handoff_completeness_status"]
    assert isinstance(gate_summary["owner_handoff_completeness_ready"], bool)
    _assert_str_list(gate_summary["owner_handoff_completeness_blockers"])
    presence_summary = snapshot["closure_artifact_presence_summary"]
    assert set(presence_summary) == {"status", "current", "blockers", "artifact_current_summary"}
    assert isinstance(presence_summary["status"], str) and presence_summary["status"]
    assert isinstance(presence_summary["current"], bool)
    _assert_str_list(presence_summary["blockers"])
    # 工件清单键集是收口检查器的代码常量。
    artifact_summary = presence_summary["artifact_current_summary"]
    assert set(artifact_summary) == {
        "krd",
        "maturity",
        "business_owner_approval_template",
        "exact_bucket_schema_evidence",
        "nearest_bucket_approval_evidence",
        "maturity_scoped_exclusion_evidence",
    }
    for artifact_name, artifact_status in artifact_summary.items():
        assert isinstance(artifact_status["status"], str) and artifact_status["status"], artifact_name
        assert isinstance(artifact_status["current"], bool), artifact_name
        _assert_str_list(artifact_status["current_blockers"])
    handoff_summary = snapshot["handoff_completeness_summary"]
    assert isinstance(handoff_summary["status"], str) and handoff_summary["status"]
    assert isinstance(handoff_summary["handoff_ready"], bool)
    _assert_str_list(handoff_summary["blockers"])
    assert isinstance(handoff_summary["summary_current_status"]["status"], str)
    assert isinstance(handoff_summary["summary_current_status"]["current"], bool)
    assert isinstance(handoff_summary["handoff_current_status"]["status"], str)
    route_coverage = handoff_summary["owner_route_coverage"]
    assert isinstance(route_coverage["status"], str) and route_coverage["status"]
    # 必需 owner 路由集合是代码常量，不随本机状态漂移。
    assert set(route_coverage["required_owners"]) == OWNER_ROUTE_KEYS
    for coverage_field in (
        "present_owners",
        "missing_owners",
        "unexpected_owners",
        "duplicate_owners",
    ):
        _assert_str_list(route_coverage[coverage_field])
    route_statuses = handoff_summary["route_statuses"]
    assert set(route_statuses) <= OWNER_ROUTE_KEYS
    assert all(isinstance(value, str) and value for value in route_statuses.values())
    # 交接证据边界是代码常量：只读证据不产生审批/治理写入效力。
    assert handoff_summary["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "fills_owner_decisions": False,
        "captures_business_owner_approval": False,
        "proves_full_score_closure": False,
        "certification_effect": "none",
    }
    handoff_alignment = snapshot["owner_handoff_completeness_alignment"]
    assert handoff_alignment["compared_fields"] == [
        "owner_handoff_completeness_status",
        "owner_handoff_completeness_ready",
        "owner_handoff_completeness_blockers",
    ]
    assert handoff_alignment["status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(handoff_alignment["blockers"])
    # 对齐结论必须忠实反映 gate 视图与 handoff 视图的实际一致性（状态无关的血缘守卫）。
    gate_matches_handoff = all(
        gate_summary[gate_field] == handoff_summary[handoff_field]
        for gate_field, handoff_field in (
            ("owner_handoff_completeness_status", "status"),
            ("owner_handoff_completeness_ready", "handoff_ready"),
            ("owner_handoff_completeness_blockers", "blockers"),
        )
    )
    assert (handoff_alignment["status"] == "consistent") is gate_matches_handoff
    assert snapshot["verification_scope"] == {
        "scope": "limited",
        "embedded_result_count": 1,
        "total_verification_command_count": len(
            [item for item in VERIFICATION_COMMANDS if item["name"] != RUNNER_COMMAND_NAME],
        ),
        "embedded_result_count_matches_report": True,
        "all_commands_embedded": False,
        "full_verification_command": (
            "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched"
        ),
        "requires_full_verification_for_full_score": True,
        "proves_full_score_closure": False,
        "certification_effect": "limited_verifier_sample_only",
    }
    approval_packet = snapshot["business_owner_approval_packet_summary"]
    source_approval_packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
    )
    # 摘要键集是快照构建器的代码常量；具体取值属于本机治理状态，按结构断言。
    assert set(approval_packet) == {
        "packet_status",
        "activation_ready",
        "approval_action_item_count",
        "approval_field_status",
        "business_owner_approval_boundary",
        "risk_warning_clean_status",
        "rerun_evidence_status",
        "dependency_consistency_status",
        "dependency_consistency_blockers",
        "score_blocker_action_coverage",
        "activation_guard",
        "owner_decision_intake_alignment",
        "manifest_consistency_statuses",
        "generated_owner_fields_boundaries",
        "owner_summary_paths",
        "csv_check_summary",
    }
    assert isinstance(approval_packet["packet_status"], str) and approval_packet["packet_status"]
    assert isinstance(approval_packet["activation_ready"], bool)
    assert isinstance(approval_packet["approval_action_item_count"], int)
    assert approval_packet["approval_action_item_count"] >= 0
    approval_field_status = approval_packet["approval_field_status"]
    assert set(approval_field_status) == {
        "approval_date",
        "verification_commands_rerun",
        "evidence_scope_captures_business_owner_approval",
    }
    assert all(isinstance(value, str) and value for value in approval_field_status.values())
    approval_boundary = approval_packet["business_owner_approval_boundary"]
    assert isinstance(approval_boundary["status"], str) and approval_boundary["status"]
    _assert_str_list(approval_boundary["blockers"])
    for boundary_field in (
        "template_approval_captured",
        "formal_authorization_allowed",
        "governance_write_allowed",
        "page_execution_proven",
        "full_score_closure_ready",
        "activation_ready",
    ):
        assert isinstance(approval_boundary[boundary_field], bool), boundary_field
    risk_warning_status = approval_packet["risk_warning_clean_status"]
    assert isinstance(risk_warning_status["status"], str) and risk_warning_status["status"]
    assert isinstance(risk_warning_status["valid"], bool)
    assert isinstance(risk_warning_status["decision_status"], str)
    _assert_str_list(risk_warning_status["decision_blockers"])
    for risk_field in (
        "evidence_scope",
        "warning_resolution_matrix",
        "duration_exclusion_delta_detail",
        "risk_tensor_rematerialization_preview",
    ):
        assert risk_field in risk_warning_status, risk_field
    _assert_evidence_status_block(
        approval_packet["rerun_evidence_status"],
        artifact="docs/portfolio/portfolio-home-evidence-snapshot.json",
    )
    assert approval_packet["dependency_consistency_status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(approval_packet["dependency_consistency_blockers"])
    action_coverage = approval_packet["score_blocker_action_coverage"]
    assert set(action_coverage) == {"status", "blockers", "unassigned_blockers", "covered_blockers"}
    assert isinstance(action_coverage["status"], str) and action_coverage["status"]
    _assert_str_list(action_coverage["blockers"])
    _assert_str_list(action_coverage["unassigned_blockers"])
    _assert_str_list(action_coverage["covered_blockers"])
    # 嵌入摘要与同源直接构建的审批包保持一致（与本机状态无关的血缘一致性守卫）。
    assert approval_packet["activation_guard"] == source_approval_packet["activation_guard"]
    approval_alignment = approval_packet["owner_decision_intake_alignment"]
    assert approval_alignment["status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(approval_alignment["blockers"])
    assert approval_alignment["compared_fields"] == OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS
    manifest_statuses = approval_packet["manifest_consistency_statuses"]
    assert set(manifest_statuses) == {
        "krd_contract_decision_manifest",
        "maturity_remediation_manifest",
    }
    assert all(isinstance(value, str) and value for value in manifest_statuses.values())
    assert approval_packet["generated_owner_fields_boundaries"] == source_approval_packet[
        "generated_owner_fields_boundaries"
    ]
    # owner summary 路径由 report_date 派生（代码规则，非本机状态）。
    assert approval_packet["owner_summary_paths"] == {
        "krd_contract_decision_owner_summary": "docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md",
        "maturity_remediation_owner_summary": "docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md",
    }
    csv_check_summary = approval_packet["csv_check_summary"]
    assert set(csv_check_summary) == {
        "krd_summary_row_count",
        "krd_detail_row_count",
        "krd_owner_decision_fields_blank",
        "bond_missing_maturity_row_count",
        "tyw_liability_missing_maturity_row_count",
        "maturity_owner_fields_blank",
    }
    for csv_count_field in (
        "krd_summary_row_count",
        "krd_detail_row_count",
        "bond_missing_maturity_row_count",
        "tyw_liability_missing_maturity_row_count",
    ):
        csv_count = csv_check_summary[csv_count_field]
        assert isinstance(csv_count, int) and csv_count >= 0, csv_count_field
    assert isinstance(csv_check_summary["krd_owner_decision_fields_blank"], bool)
    assert isinstance(csv_check_summary["maturity_owner_fields_blank"], bool)
    intake_summary = snapshot["owner_decision_intake_summary"]
    assert set(intake_summary) == {
        "intake_status",
        "intake_ready",
        "dependency_consistency_status",
        "dependency_csv_summary_alignment",
        "csv_check_summary",
        "generated_owner_fields_boundaries",
        "owner_input_boundary",
        "export_current_summary",
        "owner_decision_statuses",
        "owner_decision_blockers",
        "decision_alignment",
        "decision_counts",
        "decision_gap_counts",
        "note_gap_counts",
        "exact_bucket_schema_evidence",
        "nearest_bucket_approval_evidence",
        "maturity_scoped_exclusion_evidence",
    }
    assert isinstance(intake_summary["intake_status"], str) and intake_summary["intake_status"]
    assert isinstance(intake_summary["intake_ready"], bool)
    assert intake_summary["dependency_consistency_status"] in ALIGNMENT_STATUS_DOMAIN
    csv_alignment = intake_summary["dependency_csv_summary_alignment"]
    assert csv_alignment["status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(csv_alignment["blockers"])
    assert set(intake_summary["csv_check_summary"]) == set(csv_check_summary)
    intake_boundaries = intake_summary["generated_owner_fields_boundaries"]
    assert set(intake_boundaries) == {
        "krd_contract_decision_manifest",
        "maturity_remediation_manifest",
    }
    assert all(isinstance(value, bool) for value in intake_boundaries.values())
    owner_input_boundary = intake_summary["owner_input_boundary"]
    # owner 输入边界的策略开关与允许的前置阻塞清单是代码常量。
    assert owner_input_boundary["generated_export_owner_fields_must_be_blank"] is True
    assert owner_input_boundary["filled_owner_fields_are_owner_input_only"] is True
    assert owner_input_boundary["generated_export_system_fields_must_be_current"] is True
    assert owner_input_boundary["allowed_pre_intake_dependency_blockers"] == [
        "krd_contract_decision_manifest_owner_decision_fields_not_blank",
        "maturity_remediation_manifest_owner_fields_not_blank",
    ]
    for boundary_list_field in (
        "pre_intake_dependency_blockers",
        "active_dependency_blockers",
        "active_export_current_blockers",
    ):
        _assert_str_list(owner_input_boundary[boundary_list_field])
    export_summary = intake_summary["export_current_summary"]
    assert set(export_summary) == {"krd", "maturity"}
    for export_name, export_status in export_summary.items():
        assert isinstance(export_status["status"], str) and export_status["status"], export_name
        assert isinstance(export_status["current"], bool), export_name
        _assert_str_list(export_status["current_blockers"])
    owner_statuses = intake_summary["owner_decision_statuses"]
    assert set(owner_statuses) == OWNER_ROUTE_KEYS
    assert all(isinstance(value, str) and value for value in owner_statuses.values())
    _assert_str_list(intake_summary["owner_decision_blockers"])
    decision_alignment = intake_summary["decision_alignment"]
    assert decision_alignment["status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(decision_alignment["blockers"])
    assert set(decision_alignment["business_template_decisions"]) == {
        "krd_contract_decision",
        "maturity_data_decision",
    }
    assert set(decision_alignment["owner_csv_decisions"]) == {"krd", "maturity"}
    for gap_field in ("decision_counts", "decision_gap_counts", "note_gap_counts"):
        gap_summary = intake_summary[gap_field]
        assert set(gap_summary) == {"krd", "maturity"}, gap_field
        for gap_counts in gap_summary.values():
            assert isinstance(gap_counts, dict), gap_field
            assert all(
                isinstance(value, int) and value >= 0 for value in gap_counts.values()
            ), gap_field
    _assert_evidence_status_block(
        intake_summary["exact_bucket_schema_evidence"],
        artifact="docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
    )
    _assert_evidence_status_block(
        intake_summary["nearest_bucket_approval_evidence"],
        artifact="docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
    )
    _assert_evidence_status_block(
        intake_summary["maturity_scoped_exclusion_evidence"],
        artifact=(
            "docs/portfolio/maturity-remediation/2026-05-31/"
            "maturity_scoped_exclusion_evidence.json"
        ),
    )
    scorecard_gate = snapshot["scorecard_owner_decision_intake_gate_summary"]
    assert set(scorecard_gate) == {
        "status",
        "intake_status",
        "intake_ready",
        "dependency_consistency_status",
        "dependency_csv_summary_alignment",
        "owner_input_boundary",
        "export_current_summary",
        "owner_decision_statuses",
        "blockers",
        "decision_counts",
        "decision_gap_counts",
        "note_gap_counts",
        "exact_bucket_schema_evidence",
        "nearest_bucket_approval_evidence",
        "maturity_scoped_exclusion_evidence",
    }
    assert isinstance(scorecard_gate["status"], str) and scorecard_gate["status"]
    assert isinstance(scorecard_gate["intake_status"], str) and scorecard_gate["intake_status"]
    assert isinstance(scorecard_gate["intake_ready"], bool)
    assert scorecard_gate["dependency_consistency_status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(scorecard_gate["blockers"])
    assert set(scorecard_gate["owner_decision_statuses"]) == OWNER_ROUTE_KEYS
    assert set(scorecard_gate["export_current_summary"]) == {"krd", "maturity"}
    for gap_field in ("decision_counts", "decision_gap_counts", "note_gap_counts"):
        assert set(scorecard_gate[gap_field]) == {"krd", "maturity"}, gap_field

    intake_alignment = snapshot["owner_decision_intake_alignment"]
    assert intake_alignment["status"] in ALIGNMENT_STATUS_DOMAIN
    _assert_str_list(intake_alignment["blockers"])
    assert intake_alignment["compared_fields"] == OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS
    # 对齐机器的代码不变式：consistent 当且仅当无 blockers。
    assert (intake_alignment["status"] == "consistent") is (intake_alignment["blockers"] == [])
    verification_status = snapshot["verification_report"]["verification_status"]
    assert isinstance(verification_status, str) and verification_status


def test_owner_decision_intake_alignment_blocks_key_field_mismatch() -> None:
    direct = {
        "intake_status": "pending_owner_decisions",
        "intake_ready": False,
        "dependency_consistency_status": "consistent",
        "dependency_csv_summary_alignment": {
            "status": "consistent",
            "blockers": [],
        },
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": True},
        "owner_decision_statuses": {"risk_owner": "pending"},
        "decision_counts": {"krd": {}, "maturity": {}},
        "decision_gap_counts": {"krd": {"missing_decision_rows": 503}},
        "note_gap_counts": {"krd": {}},
        "exact_bucket_schema_evidence": {"status": "not_required"},
        "nearest_bucket_approval_evidence": {"status": "not_required"},
        "maturity_scoped_exclusion_evidence": {"status": "not_required"},
    }
    scorecard_gate = {
        **direct,
        "intake_ready": True,
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": False},
        "decision_counts": {"krd": {"approve_nearest_bucket": 1}, "maturity": {}},
        "decision_gap_counts": {"krd": {"missing_decision_rows": 0}},
    }

    assert owner_decision_intake_alignment(direct, scorecard_gate) == {
        "status": "blocked",
        "blockers": [
            "owner_decision_intake_alignment_intake_ready_mismatch",
            "owner_decision_intake_alignment_owner_input_boundary_mismatch",
            "owner_decision_intake_alignment_decision_counts_mismatch",
            "owner_decision_intake_alignment_decision_gap_counts_mismatch",
        ],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }


def test_owner_handoff_completeness_alignment_blocks_summary_mismatch() -> None:
    gate_summary = {
        "owner_handoff_completeness_status": "clean",
        "owner_handoff_completeness_ready": True,
        "owner_handoff_completeness_blockers": [],
    }
    handoff_summary = {
        "status": "blocked",
        "handoff_ready": False,
        "blockers": ["owner_handoff_packet_not_current"],
    }

    assert owner_handoff_completeness_alignment(gate_summary, handoff_summary) == {
        "status": "blocked",
        "blockers": [
            "owner_handoff_completeness_alignment_owner_handoff_completeness_status_mismatch",
            "owner_handoff_completeness_alignment_owner_handoff_completeness_ready_mismatch",
            "owner_handoff_completeness_alignment_owner_handoff_completeness_blockers_mismatch",
        ],
        "compared_fields": [
            "owner_handoff_completeness_status",
            "owner_handoff_completeness_ready",
            "owner_handoff_completeness_blockers",
        ],
    }


def test_portfolio_home_evidence_snapshot_cli_require_verifier_matched() -> None:
    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--require-verifier-matched",
    )

    assert returncode == 0
    assert payload["verification_report"]["all_matched_expected_exit"] is True
    assert payload["gate_summary"]["business_owner_approval_status"] == "pending"
    assert payload["business_owner_approval_packet_summary"]["activation_ready"] is False
    assert (
        payload["business_owner_approval_packet_summary"]["dependency_consistency_status"]
        == "consistent"
    )
    assert payload["owner_decision_intake_summary"]["intake_ready"] is False


def test_portfolio_home_evidence_snapshot_rejects_negative_limits() -> None:
    try:
        build_snapshot(
            duckdb_path=DUCKDB,
            report_date="2026-05-31",
            template_path=TEMPLATE,
            scorecard_limit=-1,
            verifier_limit=1,
        )
    except ValueError as error:
        assert str(error) == "Portfolio-home scorecard limit must be non-negative: -1"
    else:
        raise AssertionError("negative scorecard snapshot limit was accepted")

    for args, message in (
        (
            ["--scorecard-limit", "-1"],
            "Portfolio-home scorecard limit must be non-negative: -1",
        ),
        (
            ["--verifier-limit", "-1"],
            "Portfolio-home verifier limit must be non-negative: -1",
        ),
    ):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
        )

        assert completed.returncode == 2
        assert message in completed.stderr


def test_portfolio_home_evidence_snapshot_cli_writes_output_artifact(tmp_path: Path) -> None:
    output = tmp_path / "portfolio-home-evidence-snapshot.json"

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
    )

    assert returncode == 0
    assert output.exists()
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact == payload
    assert artifact["snapshot_kind"] == "portfolio_home_closure_evidence"
    assert artifact["report_date"] == "2026-05-31"
    assert artifact["verification_report"]["all_matched_expected_exit"] is True


def test_portfolio_home_evidence_snapshot_cli_rewrites_self_referential_artifact_once(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    output = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": "2026-05-31",
                "scorecard_owner_decision_intake_gate_summary": {},
                "owner_decision_intake_alignment": {
                    "status": "consistent",
                    "blockers": [],
                    "compared_fields": [
                        "intake_status",
                        "intake_ready",
                        "dependency_consistency_status",
                        "owner_decision_statuses",
                        "decision_gap_counts",
                        "note_gap_counts",
                        "exact_bucket_schema_evidence",
                    ],
                },
                "verification_report": {
                    "verification_status": "matched_expected_blocked_state",
                    "all_matched_expected_exit": True,
                    "all_matched_expected_when_blocked": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--docs-root",
        str(docs_dir),
        "--output",
        str(output),
    )

    assert returncode == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    # 核心守卫：自引用工件一次重写即收敛（写盘内容与最终输出一致）。
    assert artifact == payload
    rerun_status = artifact["business_owner_approval_packet_summary"]["rerun_evidence_status"]
    # rerun 证据有效性取决于 docs 工件与治理库的当前一致性，属于本机状态；
    # 只断言结构与 status/valid/blockers 的代码不变式，不锁定 valid 状态值。
    assert set(rerun_status) == {"status", "artifact", "valid", "blockers"}
    assert rerun_status["artifact"] == "docs/portfolio/portfolio-home-evidence-snapshot.json"
    assert rerun_status["status"] in {"valid", "blocked", "missing"}
    assert isinstance(rerun_status["valid"], bool)
    _assert_str_list(rerun_status["blockers"])
    assert rerun_status["valid"] is (rerun_status["status"] == "valid")
    assert (rerun_status["status"] == "valid") == (rerun_status["blockers"] == [])


def test_portfolio_home_evidence_snapshot_cli_stabilizes_self_referential_handoff_alignment_once(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    output = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": "2026-05-31",
                "handoff_completeness_summary": {
                    "status": "blocked",
                    "handoff_ready": False,
                    "blockers": ["owner_handoff_packet_not_current"],
                },
                "owner_handoff_completeness_alignment": {
                    "status": "blocked",
                    "blockers": [
                        "owner_handoff_completeness_alignment_owner_handoff_completeness_status_mismatch",
                    ],
                    "compared_fields": [
                        "owner_handoff_completeness_status",
                        "owner_handoff_completeness_ready",
                        "owner_handoff_completeness_blockers",
                    ],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--docs-root",
        str(docs_dir),
        "--output",
        str(output),
    )

    assert returncode == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact == payload
    handoff_summary = artifact["handoff_completeness_summary"]
    gate_summary = artifact["gate_summary"]
    assert artifact["owner_handoff_completeness_alignment"]["status"] == "consistent"
    assert gate_summary["owner_handoff_completeness_status"] == handoff_summary["status"]
    assert gate_summary["owner_handoff_completeness_ready"] == handoff_summary["handoff_ready"]
    assert gate_summary["owner_handoff_completeness_blockers"] == handoff_summary["blockers"]

    check_returncode, check_payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--docs-root",
        str(docs_dir),
        "--output",
        str(output),
        "--check-current",
    )

    assert check_returncode == 0
    assert check_payload["status"] == "current"


def test_portfolio_home_evidence_snapshot_cli_check_current_passes_matching_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
    )
    assert returncode == 0

    check_returncode, check_payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
        "--check-current",
    )

    assert check_returncode == 0
    assert check_payload == {
        "artifact": str(output),
        "status": "current",
        "expected_sha256": snapshot_sha256(payload),
        "actual_sha256": snapshot_sha256(payload),
    }


def test_portfolio_home_evidence_snapshot_cli_check_current_fails_stale_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text('{"snapshot_kind":"stale"}', encoding="utf-8")

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
        "--check-current",
    )

    assert returncode == 1
    assert payload["artifact"] == str(output)
    assert payload["status"] == "stale"
    assert payload["expected_sha256"] != payload["actual_sha256"]


def test_portfolio_home_evidence_snapshot_uses_supplied_docs_root_for_approval_packet(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    if artifact.exists():
        artifact.unlink()

    snapshot = build_snapshot(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        scorecard_limit=1,
        verifier_limit=1,
        docs_root=docs_dir,
    )

    assert snapshot["business_owner_approval_packet_summary"]["rerun_evidence_status"] == {
        "status": "missing",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": ["rerun_evidence_artifact_missing"],
    }


def test_portfolio_home_evidence_snapshot_passes_docs_root_to_embedded_verifier(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")

    snapshot = build_snapshot(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        scorecard_limit=1,
        verifier_limit=19,
        docs_root=docs_dir,
    )

    scorecard_result = next(
        item
        for item in snapshot["verification_report"]["results"]
        if item["name"] == "scorecard"
    )
    assert scorecard_result["argv"] == [
        "python",
        "scripts/portfolio_home_closure_scorecard.py",
        "--limit",
        "3",
        "--docs-root",
        "docs",
    ]


def test_portfolio_home_evidence_snapshot_portable_verifier_normalizes_worktree_and_python(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first-worktree"
    second_root = tmp_path / "second-worktree"
    first_report = {
        "docs_root": str(first_root / "docs"),
        "results": [
            {
                "argv": [
                    str(first_root / "venv" / "Scripts" / "python.exe"),
                    "scripts/portfolio_home_closure_scorecard.py",
                    "--docs-root",
                    str(first_root / "docs"),
                ],
            },
        ],
    }
    second_report = {
        "docs_root": str(second_root / "docs"),
        "results": [
            {
                "argv": [
                    str(second_root / "venv" / "python.exe"),
                    "scripts/portfolio_home_closure_scorecard.py",
                    "--docs-root",
                    str(second_root / "docs"),
                ],
            },
        ],
    }

    first = portable_verification_report(first_report, repo_root=first_root)
    second = portable_verification_report(second_report, repo_root=second_root)

    assert first == second == {
        "docs_root": "docs",
        "results": [
            {
                "argv": [
                    "python",
                    "scripts/portfolio_home_closure_scorecard.py",
                    "--docs-root",
                    "docs",
                ],
            },
        ],
    }


def test_portfolio_home_evidence_snapshot_portable_verifier_preserves_external_paths(
    tmp_path: Path,
) -> None:
    report = {
        "docs_root": str(tmp_path / "repo" / "docs"),
        "results": [
            {
                "argv": [
                    "C:/external/tool.exe",
                    "--output",
                    "C:/external/result.json",
                ],
            },
        ],
    }

    normalized = portable_verification_report(report, repo_root=tmp_path / "repo")

    assert normalized["results"][0]["argv"] == [
        "C:/external/tool.exe",
        "--output",
        "C:/external/result.json",
    ]


def test_portfolio_home_evidence_snapshot_portable_verifier_preserves_python_wrapper(
    tmp_path: Path,
) -> None:
    report = {
        "docs_root": str(tmp_path / "repo" / "docs"),
        "results": [
            {
                "argv": [
                    "C:/external/python-wrapper.exe",
                    "scripts/portfolio_home_closure_scorecard.py",
                ],
            },
        ],
    }

    normalized = portable_verification_report(report, repo_root=tmp_path / "repo")

    assert normalized["results"][0]["argv"][0] == "C:/external/python-wrapper.exe"
