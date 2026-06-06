from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.codex_page_readiness import (
    _balance_movement_read_model_freshness_gate,
    build_all_page_readiness_report,
    build_page_readiness_report,
    build_route_scope_classification_report,
)
from scripts.mcp.moss_project_mcp import product_page_trace_bundles

ROOT = Path(__file__).resolve().parents[1]


def test_balance_movement_freshness_gate_blocks_when_read_model_lags_upstream(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              currency varchar,
              account_code varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              currency_basis varchar
            )
            """
        )
        conn.execute(
            "insert into product_category_pnl_canonical_fact values "
            "('2026-05-31', 'CNX', '14100000000')"
        )
        conn.execute(
            "insert into fact_accounting_asset_movement_monthly values "
            "('2026-04-30', 'CNX')"
        )
    finally:
        conn.close()

    gate = _balance_movement_read_model_freshness_gate(duckdb_path)

    assert gate["name"] == "balance_movement_read_model_freshness"
    assert gate["outcome"] == "block"
    assert "movement_latest=2026-04-30" in gate["detail"]
    assert "control_latest=2026-05-31" in gate["detail"]


def test_product_category_readiness_static_gates_surface_contract_evidence() -> None:
    report = build_page_readiness_report("product-category-pnl")

    assert report["page_slug"] == "product-category-pnl"
    assert report["page_id"] == "PAGE-PROD-CAT-001"
    assert report["approval_status"] == "formal_or_governed"
    assert report["formal_use_allowed"] is True
    assert report["overall_status"] == "static-pass"

    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["trace_bundle_present"]["outcome"] == "pass"
    assert gates["evidence_readiness_explicit"]["outcome"] == "pass"
    assert gates["lineage_mapping_present"]["outcome"] == "pass"
    assert gates["catalog_date_review_routed"]["outcome"] == "pass"
    assert gates["catalog_date_evidence_sampled"]["outcome"] == "pass"
    assert gates["direct_governance_record_ready"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["outcome"] == "pass"
    assert gates["formal_promotion_boundary"]["outcome"] == "pass"

    assert report["route"] == "/product-category-pnl"
    assert report["primary_api"] == "/ui/pnl/product-category"
    assert report["catalog_date_evidence"]["status"] == "sampled"
    assert report["catalog_date_evidence"]["present_table_count"] == 2
    assert report["catalog_date_evidence"]["date_sampled_table_count"] == 2
    assert report["governance_record_validation"]["status"] == "direct_records_ready_for_audit_review"
    assert report["governance_record_validation"]["ready_record_count"] == 1
    assert report["audit_review"]["status"] == "ready_for_audit_review"
    assert report["audit_review"]["closure_approved"] is False
    assert report["approval_status_commands"] == [
        "python scripts/check_product_category_pnl_business_owner_approval.py",
        "python scripts/check_product_category_pnl_business_owner_approval.py --require-captured",
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
        "-PageSlug product-category-pnl -RequireApprovalCaptured",
    ]
    assert report["business_owner_approval_status"]["approval_status"] == "pending"
    assert report["business_owner_approval_status"]["business_owner_approval_captured"] is False
    assert report["business_owner_approval_status"]["approval_action_item_count"] == 15
    assert "reviewed_owner_decision_packet" in report["business_owner_approval_status"]["remaining_blockers"]
    assert (
        "owner_decision_next_review_queue_acknowledgement"
        in report["business_owner_approval_status"]["remaining_blockers"]
    )
    assert "golden_sample_artifact_reconciliation" in report["business_owner_approval_status"]["remaining_blockers"]
    assert "closure_checklist_review" in report["business_owner_approval_status"]["remaining_blockers"]
    assert "fallback_liability_branch_boundary_review" in report["business_owner_approval_status"]["remaining_blockers"]
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_boundary_packet"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_first_certification_packet"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["formal_use_allowed"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["closure_approved"] == "valid"
    assert report["business_owner_approval_status"]["closure_checklist_artifact"]["ready_for_owner_approval"] is False
    assert report["business_owner_approval_status"]["closure_checklist_artifact"]["unit_count"] == 10
    assert report["business_owner_approval_status"]["closure_checklist_artifact"]["partial_count"] == 10
    assert report["business_owner_approval_status"]["closure_checklist_artifact"]["open_unit_count"] == 10
    assert report["business_owner_approval_status"]["closure_blocker_triage"]["blocker_count"] == 15
    assert report["business_owner_approval_status"]["closure_blocker_triage"]["class_counts"] == {
        "1": 3,
        "2": 2,
        "3": 0,
        "4": 9,
        "5": 1,
    }
    assert report["business_owner_approval_status"]["closure_blocker_triage"]["decision_required_count"] == 3
    assert report["business_owner_approval_status"]["golden_sample_approval_artifact"] == {
        "sample_id": "GS-PROD-CAT-PNL-A",
        "status": "captured-awaiting-approval",
        "owner": "TBD",
        "approver": "TBD",
        "approved_at": "TBD",
        "artifact_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
        "approved": False,
    }
    assert report["golden_sample_approval_artifact_status"] == "captured-awaiting-approval"
    assert report["golden_sample_approval_artifact_owner"] == "TBD"
    assert report["golden_sample_approval_artifact_approver"] == "TBD"
    assert report["golden_sample_approval_artifact_approved_at"] == "TBD"
    assert report["golden_sample_approval_artifact_mismatch"] is True
    assert report["golden_sample_approval_artifacts"] == [
        {
            "sample_id": "GS-PROD-CAT-PNL-A",
            "status": "captured-awaiting-approval",
            "sample_type": "capture-ready",
            "owner": "TBD",
            "approver": "TBD",
            "approved_at": "TBD",
            "readiness_boundary_status": "approved",
            "mismatch": True,
            "artifact_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
        }
    ]
    assert {
        "blocker": "golden_sample_artifact_reconciliation",
        "template_field": "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled",
        "required_value": "yes",
        "current_status": "pending",
    } in report["business_owner_approval_status"]["approval_action_items"]
    assert "codex-page-smoke.ps1 -PageSlug product-category-pnl" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug product-category-pnl -Run" in report["required_commands"][1]
    assert not any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Business owner approval is still required" in gap for gap in report["residual_gaps"])


def test_dashboard_home_readiness_static_gates_preserve_mixed_source_boundary() -> None:
    report = build_page_readiness_report("dashboard-home")

    assert report["page_slug"] == "dashboard-home"
    assert report["page_id"] == "PAGE-DASH-001"
    assert report["approval_status"] == "mixed_source_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"

    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["golden_sample_boundary"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["detail"] == "supporting_or_fragment_only"
    assert gates["formal_promotion_boundary"]["outcome"] == "pass"
    assert "Mixed-source page cannot be collapsed into full-page formal truth." in report["residual_gaps"]
    assert "codex-page-smoke.ps1 -PageSlug dashboard-home" in report["required_commands"][0]


def test_balance_analysis_readiness_exposes_run_commands_without_direct_record_promotion() -> None:
    report = build_page_readiness_report("balance-analysis")

    assert report["page_slug"] == "balance-analysis"
    assert report["page_id"] == "PAGE-BALANCE-001"
    assert report["route"] == "/balance-analysis"
    assert report["primary_api"] == "/ui/balance-analysis/overview"
    assert report["approval_status"] == "formal_or_governed"
    assert report["formal_use_allowed"] is True
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug balance-analysis" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug balance-analysis -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])


def test_pnl_readiness_exposes_run_commands_without_direct_record_promotion() -> None:
    report = build_page_readiness_report("pnl")

    assert report["page_slug"] == "pnl"
    assert report["page_id"] == "PAGE-PNL-001"
    assert report["route"] == "/pnl"
    assert report["primary_api"] == "/api/pnl/overview"
    assert report["approval_status"] == "formal_or_governed"
    assert report["formal_use_allowed"] is True
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-PNL-OVERVIEW-A" in report["golden_samples"]
    assert "tests/golden_samples/GS-PNL-DATA-A" in report["golden_samples"]
    assert "codex-page-smoke.ps1 -PageSlug pnl" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug pnl -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])


def test_pnl_bridge_readiness_exposes_run_commands_without_direct_record_promotion() -> None:
    report = build_page_readiness_report("pnl-bridge")

    assert report["page_slug"] == "pnl-bridge"
    assert report["page_id"] == "PAGE-BRIDGE-001"
    assert report["route"] == "/pnl-bridge"
    assert report["primary_api"] == "/api/pnl/bridge"
    assert report["approval_status"] == "formal_or_governed"
    assert report["formal_use_allowed"] is True
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-BRIDGE-A" in report["golden_samples"]
    assert "tests/golden_samples/GS-BRIDGE-WARN-B" in report["golden_samples"]
    assert "codex-page-smoke.ps1 -PageSlug pnl-bridge" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug pnl-bridge -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])


def test_risk_tensor_readiness_surfaces_direct_catalog_and_governance_evidence() -> None:
    report = build_page_readiness_report("risk-tensor")

    assert report["page_slug"] == "risk-tensor"
    assert report["page_id"] == "PAGE-RISK-001"
    assert report["route"] == "/risk-tensor"
    assert report["primary_api"] == "/api/risk/tensor"
    assert report["approval_status"] == "formal_or_governed"
    assert report["formal_use_allowed"] is True
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-RISK-A" in report["golden_samples"]
    assert "tests/golden_samples/GS-RISK-WARN-B" in report["golden_samples"]
    assert "codex-page-smoke.ps1 -PageSlug risk-tensor" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug risk-tensor -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"]["status"] == "sampled"
    assert report["catalog_date_evidence"]["present_table_count"] == 1
    assert report["catalog_date_evidence"]["date_sampled_table_count"] == 1
    assert report["governance_record_validation"]["status"] == "direct_records_ready_for_audit_review"
    assert report["governance_record_validation"]["ready_record_count"] >= 1
    assert report["audit_review"]["status"] == "ready_for_audit_review"
    assert report["audit_review"]["closure_approved"] is False
    assert not any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert not any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Business owner approval is still required" in gap for gap in report["residual_gaps"])


def test_bond_dashboard_readiness_surfaces_direct_candidate_evidence_without_promotion() -> None:
    report = build_page_readiness_report("bond-dashboard")

    assert report["page_slug"] == "bond-dashboard"
    assert report["page_id"] == "PAGE-BOND-001"
    assert report["route"] == "/bond-dashboard"
    assert report["primary_api"] == "/api/bond-dashboard/headline-kpis"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-BOND-HEADLINE-A" in report["golden_samples"]
    assert "codex-page-smoke.ps1 -PageSlug bond-dashboard" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug bond-dashboard -Run" in report["required_commands"][1]
    assert report["run_supported"] is True

    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["catalog_date_evidence_sampled"]["outcome"] == "pass"
    assert gates["direct_governance_record_ready"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["detail"] == "page_dto_only"
    assert gates["formal_promotion_boundary"]["outcome"] == "pass"
    assert gates["formal_promotion_boundary"]["detail"] == "candidate_or_pending; formal_use_allowed=false"

    assert report["catalog_date_evidence"]["status"] == "sampled"
    assert report["catalog_date_evidence"]["present_table_count"] == 1
    assert report["catalog_date_evidence"]["date_sampled_table_count"] == 1
    assert report["governance_record_validation"]["status"] == "direct_records_ready_for_audit_review"
    assert report["governance_record_validation"]["ready_record_count"] >= 1
    assert report["audit_review"]["status"] == "ready_for_audit_review"
    assert report["audit_review"]["closure_approved"] is False
    assert not any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert not any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Candidate metric dictionary-level approval remains pending." in gap for gap in report["residual_gaps"])
    assert any("Business owner approval is still required" in gap for gap in report["residual_gaps"])


def test_bond_analysis_readiness_surfaces_direct_candidate_lane_without_borrowing_dashboard_evidence() -> None:
    report = build_page_readiness_report("bond-analysis")

    assert report["page_slug"] == "bond-analysis"
    assert report["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert report["route"] == "/bond-analysis"
    assert report["primary_api"] == "/api/bond-analytics/action-attribution"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A" in report["golden_samples"]
    assert "tests/golden_samples/GS-BOND-HEADLINE-A" not in report["golden_samples"]
    assert report["golden_sample_approval_artifact_status"] == "captured-awaiting-approval"
    assert report["golden_sample_approval_artifact_owner"] == "TBD"
    assert report["golden_sample_approval_artifact_approver"] == "TBD"
    assert report["golden_sample_approval_artifact_approved_at"] == "TBD"
    assert report["golden_sample_approval_artifact_mismatch"] is False
    assert report["golden_sample_approval_artifacts"] == [
        {
            "sample_id": "GS-BOND-ANALYSIS-ACTION-ATTR-A",
            "status": "captured-awaiting-approval",
            "sample_type": "capture-ready",
            "owner": "TBD",
            "approver": "TBD",
            "approved_at": "TBD",
            "readiness_boundary_status": "page_dto_only",
            "mismatch": False,
            "artifact_path": "tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/approval.md",
        }
    ]
    assert report["business_owner_approval_status"]["business_owner_approval_captured"] is False
    assert report["business_owner_approval_status"]["approval_action_item_count"] == 11
    assert "codex-page-smoke.ps1 -PageSlug bond-analysis" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug bond-analysis -Run" in report["required_commands"][1]
    assert "check_bond_analysis_business_owner_approval.py --require-captured" in report["approval_status_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert "docs/audits/2026-06-06-bond-analysis-gate-i-lane.md" in report["contract_docs"]

    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["golden_sample_boundary"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["detail"] == "page_dto_only"
    assert gates["formal_promotion_boundary"]["outcome"] == "pass"
    assert gates["formal_promotion_boundary"]["detail"] == "candidate_or_pending; formal_use_allowed=false"
    assert gates["business_owner_approval_status"]["outcome"] == "pass"

    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert not any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])
    assert not any("bond-analysis route contract" in gap for gap in report["residual_gaps"])
    assert any("GS-BOND-HEADLINE-A" in gap for gap in report["residual_gaps"])
    assert any("DV01" in gap and "duration" in gap for gap in report["residual_gaps"])
    assert not any("PAGE-STOCK" in gap for gap in report["residual_gaps"])
    assert any("PAGE-BOND-001" in guardrail for guardrail in report["guardrails"])
    assert any("/bond-dashboard" in guardrail for guardrail in report["guardrails"])


def test_balance_movement_readiness_surfaces_direct_candidate_evidence_without_promotion() -> None:
    report = build_page_readiness_report("balance-movement-analysis")

    assert report["page_slug"] == "balance-movement-analysis"
    assert report["page_id"] == "PAGE-BAL-MOVE-001"
    assert report["route"] == "/balance-movement-analysis"
    assert report["primary_api"] == "/ui/balance-movement-analysis"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug balance-movement-analysis -CheckLive" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug balance-movement-analysis -Run" in report["required_commands"][1]
    assert report["run_supported"] is True

    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["catalog_date_evidence_sampled"]["outcome"] == "pass"
    assert gates["catalog_date_evidence_sampled"]["detail"] == "2/2 table date samples"
    assert gates["direct_governance_record_ready"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["detail"] == "missing"
    assert gates["formal_promotion_boundary"]["outcome"] == "pass"
    assert gates["formal_promotion_boundary"]["detail"] == "candidate_or_pending; formal_use_allowed=false"

    assert report["catalog_date_evidence"]["status"] == "sampled"
    assert report["catalog_date_evidence"]["present_table_count"] == 2
    assert report["catalog_date_evidence"]["date_sampled_table_count"] == 2
    assert report["governance_record_validation"]["status"] == "direct_records_ready_for_audit_review"
    assert report["governance_record_validation"]["ready_record_count"] >= 1
    assert report["audit_review"]["status"] == "ready_for_audit_review"
    assert report["audit_review"]["closure_approved"] is False
    assert not any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert not any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])
    assert any("Business owner approval is still required" in gap for gap in report["residual_gaps"])


def test_ledger_pnl_readiness_exposes_run_commands_without_direct_record_promotion() -> None:
    report = build_page_readiness_report("ledger-pnl")

    assert report["page_slug"] == "ledger-pnl"
    assert report["page_id"] == "PAGE-LEDGER-PNL-001"
    assert report["route"] == "/ledger-pnl"
    assert report["primary_api"] == "/api/ledger-pnl/summary"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug ledger-pnl" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug ledger-pnl -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert report["governance_record_commands"] == [
        "python scripts/emit_ledger_pnl_governance_record.py",
        "python scripts/emit_ledger_pnl_governance_record.py --write",
    ]
    assert report["approval_status_commands"] == [
        "python scripts/check_ledger_pnl_business_owner_approval.py",
        "python scripts/check_ledger_pnl_business_owner_approval.py --require-captured",
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug ledger-pnl -RequireApprovalCaptured",
    ]
    assert report["business_owner_approval_status"]["approval_status"] == "pending"
    assert report["business_owner_approval_status"]["business_owner_approval_captured"] is False
    assert report["business_owner_approval_status"]["remaining_blockers"] == [
        "business_owner_approval",
        "business_owner_name",
        "business_owner_role",
        "approval_decision",
        "approval_date",
        "business_owner_signature",
        "governance_record_review",
        "dedicated_golden_sample_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "candidate_boundary_acceptance",
    ]
    assert report["business_owner_approval_status"]["approval_field_status"]["business_owner_name"] == "missing"
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_signoff_packet"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["decision_notes"] == "not_required"
    assert report["business_owner_approval_status"]["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
    }
    assert report["business_owner_approval_status"]["approval_action_item_count"] == 11
    assert {
        "blocker": "dedicated_golden_sample_review",
        "template_field": "- Dedicated ledger summary golden sample reviewed",
        "required_value": "yes",
        "current_status": "pending",
    } in report["business_owner_approval_status"]["approval_action_items"]
    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["business_owner_approval_status"]["outcome"] == "pass"
    assert gates["business_owner_approval_status"]["detail"] == "pending; captured=false"
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Candidate metric dictionary-level approval remains pending." in gap for gap in report["residual_gaps"])


def test_positions_readiness_exposes_run_commands_without_direct_record_promotion() -> None:
    report = build_page_readiness_report("positions")

    assert report["page_slug"] == "positions"
    assert report["page_id"] == "PAGE-POS-001"
    assert report["route"] == "/positions"
    assert report["primary_api"] == "/api/positions/bonds"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug positions" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug positions -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Candidate metric dictionary-level approval remains pending." in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_operations_analysis_readiness_exposes_run_commands_without_full_page_promotion() -> None:
    report = build_page_readiness_report("operations-analysis")

    assert report["page_slug"] == "operations-analysis"
    assert report["page_id"] == "PAGE-OPS-001"
    assert report["route"] == "/operations-analysis"
    assert report["primary_api"] == "/ui/pnl/product-category"
    assert report["approval_status"] == "mixed_source_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-PROD-CAT-PNL-A" in report["golden_samples"]
    assert "tests/golden_samples/GS-BAL-OVERVIEW-A" in report["golden_samples"]
    assert "codex-page-smoke.ps1 -PageSlug operations-analysis" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug operations-analysis -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Mixed-source page cannot be collapsed into full-page formal truth." in gap for gap in report["residual_gaps"])
    assert any("GAP-OPS-MACRO-FX" in gap for gap in report["residual_gaps"])


def test_liability_analytics_readiness_exposes_run_commands_without_formal_promotion() -> None:
    report = build_page_readiness_report("liability-analytics")

    assert report["page_slug"] == "liability-analytics"
    assert report["page_id"] == "PAGE-LIAB-ANALYTICS-001"
    assert report["route"] == "/liability-analytics"
    assert report["primary_api"] == "/api/risk/buckets"
    assert report["approval_status"] == "mixed_source_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug liability-analytics" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug liability-analytics -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Mixed-source page cannot be collapsed into full-page formal truth." in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_market_data_readiness_exposes_run_commands_without_full_page_promotion() -> None:
    report = build_page_readiness_report("market-data")

    assert report["page_slug"] == "market-data"
    assert report["page_id"] == "PAGE-MKT-001"
    assert report["route"] == "/market-data"
    assert report["primary_api"] == "/ui/preview/macro-foundation"
    assert report["approval_status"] == "mixed_source_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug market-data" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug market-data -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Mixed-source page cannot be collapsed into full-page formal truth." in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_cross_asset_readiness_exposes_run_commands_without_formal_promotion() -> None:
    report = build_page_readiness_report("cross-asset")

    assert report["page_slug"] == "cross-asset"
    assert report["page_id"] == "GAP-CROSS-ASSET-PAGE"
    assert report["route"] == "/cross-asset"
    assert report["primary_api"] == "frontend aggregation: cross-asset drivers"
    assert report["approval_status"] == "mixed_source_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug cross-asset" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug cross-asset -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert "docs/live_route_maturity.md" in report["contract_docs"]
    assert any("/api/macro-bond-linkage/analysis" in item for item in report["truth_chain"])
    assert any("NCD" in item and "proxy" in item for item in report["guardrails"])
    assert any("Livermore" in item and "observational" in item for item in report["guardrails"])
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Mixed-source page cannot be collapsed into full-page formal truth." in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_decision_items_readiness_exposes_read_write_boundary_without_formal_promotion() -> None:
    report = build_page_readiness_report("decision-items")

    assert report["page_slug"] == "decision-items"
    assert report["page_id"] == "GAP-DECISION-ITEMS-PAGE"
    assert report["route"] == "/decision-items"
    assert report["primary_api"] == "/ui/balance-analysis/decision-items"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug decision-items" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug decision-items -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert "docs/live_route_maturity.md" in report["contract_docs"]
    assert any("/ui/balance-analysis/decision-items/status" in item for item in report["supporting_apis"])
    assert any("read/write" in item for item in report["guardrails"])
    assert any("permissions" in item for item in report["verification_focus"])
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_kpi_performance_readiness_exposes_scoring_write_boundary_without_formal_promotion() -> None:
    report = build_page_readiness_report("kpi-performance")

    assert report["page_slug"] == "kpi-performance"
    assert report["page_id"] == "GAP-KPI-PERFORMANCE-PAGE"
    assert report["route"] == "/kpi"
    assert report["primary_api"] == "/api/kpi/values/summary"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug kpi-performance" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug kpi-performance -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert "docs/live_route_maturity.md" in report["contract_docs"]
    assert any("/api/kpi/fetch_and_recalc" in item for item in report["supporting_apis"])
    assert any("write" in item and "scoring" in item for item in report["guardrails"])
    assert any("permissions" in item for item in report["verification_focus"])
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_macro_toolkit_readiness_exposes_run_commands_without_formal_promotion() -> None:
    report = build_page_readiness_report("macro-toolkit")

    assert report["page_slug"] == "macro-toolkit"
    assert report["page_id"] == "PAGE-MACRO-TOOLKIT-001"
    assert report["route"] == "/macro-toolkit"
    assert report["primary_api"] == "/ui/macro/toolkit/analysis"
    assert report["approval_status"] == "mixed_source_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "codex-page-smoke.ps1 -PageSlug macro-toolkit" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug macro-toolkit -Run" in report["required_commands"][1]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Mixed-source page cannot be collapsed into full-page formal truth." in gap for gap in report["residual_gaps"])
    assert any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_stock_analysis_readiness_exposes_run_commands_without_formal_promotion() -> None:
    report = build_page_readiness_report("stock-analysis")

    assert report["page_slug"] == "stock-analysis"
    assert report["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
    assert report["route"] == "/stock-analysis"
    assert report["primary_api"] == "/ui/market-data/livermore"
    assert report["approval_status"] == "gap_or_observational"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert "tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A" in report["golden_samples"]
    assert report["golden_sample_approval_artifact_status"] == "captured-awaiting-approval"
    assert report["golden_sample_approval_artifact_owner"] == "TBD"
    assert report["golden_sample_approval_artifact_approver"] == "TBD"
    assert report["golden_sample_approval_artifact_approved_at"] == "TBD"
    assert report["golden_sample_approval_artifact_mismatch"] is False
    assert report["golden_sample_approval_artifacts"] == [
        {
            "sample_id": "GS-STOCK-ANALYSIS-OBS-A",
            "status": "captured-awaiting-approval",
            "sample_type": "capture-ready",
            "owner": "TBD",
            "approver": "TBD",
            "approved_at": "TBD",
            "readiness_boundary_status": "page_dto_only",
            "mismatch": False,
            "artifact_path": "tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/approval.md",
        }
    ]
    assert "docs/audits/2026-06-06-stock-analysis-gate-i-lane.md" in report["contract_docs"]
    assert "docs/pnl/stock-analysis-owner-evidence-packet.md" in report["contract_docs"]
    assert "codex-page-smoke.ps1 -PageSlug stock-analysis" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug stock-analysis -Run" in report["required_commands"][1]
    assert report["approval_status_commands"] == [
        "python scripts/check_stock_analysis_business_owner_approval.py",
        "python scripts/check_stock_analysis_business_owner_approval.py --require-captured",
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug stock-analysis -RequireApprovalCaptured",
    ]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"] is None
    assert report["governance_record_validation"] is None
    assert report["business_owner_approval_status"]["approval_status"] == "pending"
    assert report["business_owner_approval_status"]["business_owner_approval_captured"] is False
    assert report["business_owner_approval_status"]["approval_action_item_count"] == 11
    assert "not_trading_instruction_review" in report["business_owner_approval_status"]["remaining_blockers"]
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert report["business_owner_approval_status"]["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
    }

    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["golden_sample_boundary"]["outcome"] == "pass"
    assert gates["golden_sample_boundary"]["detail"] == "page_dto_only"
    assert gates["formal_promotion_boundary"]["outcome"] == "pass"
    assert gates["formal_promotion_boundary"]["detail"] == "gap_or_observational; formal_use_allowed=false"
    assert gates["business_owner_approval_status"]["outcome"] == "pass"

    assert any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("GAP/observational route lacks standalone formal page contract closure." in gap for gap in report["residual_gaps"])
    assert not any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])
    assert any("Trading instructions" in gap for gap in report["residual_gaps"])
    assert any("formal stock-analysis truth" in gap for gap in report["residual_gaps"])


def test_pnl_attribution_readiness_exposes_run_commands_without_formal_pnl_promotion() -> None:
    report = build_page_readiness_report("pnl-attribution")

    assert report["page_slug"] == "pnl-attribution"
    assert report["page_id"] == "PAGE-PNL-ATTR-WB-001"
    assert report["route"] == "/pnl-attribution"
    assert report["primary_api"] == "/api/pnl-attribution/volume-rate"
    assert report["approval_status"] == "candidate_or_pending"
    assert report["formal_use_allowed"] is False
    assert report["overall_status"] == "static-pass"
    assert len(report["required_commands"]) == 3
    assert "codex-page-smoke.ps1 -PageSlug pnl-attribution" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug pnl-attribution -Run" in report["required_commands"][1]
    assert "codex-page-readiness.ps1 -PageSlug pnl-attribution -Run" in report["required_commands"][2]
    assert report["governance_record_commands"] == [
        "python scripts/emit_pnl_attribution_governance_record.py",
        "python scripts/emit_pnl_attribution_governance_record.py --write",
    ]
    assert report["approval_status_commands"] == [
        "python scripts/check_pnl_attribution_business_owner_approval.py",
        "python scripts/check_pnl_attribution_business_owner_approval.py --require-captured",
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured",
    ]
    assert report["run_supported"] is True
    assert report["catalog_date_evidence"]["status"] == "sampled"
    assert report["catalog_date_evidence"]["present_table_count"] == 5
    assert report["catalog_date_evidence"]["date_sampled_table_count"] == 5
    assert report["governance_record_validation"]["status"] == "direct_records_ready_for_audit_review"
    assert report["governance_record_validation"]["ready_record_count"] == 1
    assert report["governance_record_validation"]["direct_record_count"] == 1
    assert report["audit_review"]["status"] == "ready_for_audit_review"
    assert report["audit_review"]["closure_approved"] is False
    assert report["business_owner_approval_status"]["approval_status"] == "pending"
    assert report["business_owner_approval_status"]["business_owner_approval_captured"] is False
    assert report["business_owner_approval_status"]["remaining_blockers"] == [
        "business_owner_approval",
        "business_owner_name",
        "business_owner_role",
        "approval_decision",
        "approval_date",
        "business_owner_signature",
        "governance_record_review",
        "golden_sample_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "candidate_boundary_acceptance",
    ]
    assert report["business_owner_approval_status"]["approval_field_status"]["business_owner_name"] == "missing"
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_signoff_packet"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert report["business_owner_approval_status"]["approval_field_status"]["decision_notes"] == "not_required"
    assert report["business_owner_approval_status"]["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
    }
    assert report["business_owner_approval_status"]["approval_action_item_count"] == 11
    assert report["business_owner_approval_status"]["approval_action_items"][0] == {
        "blocker": "business_owner_name",
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
        "current_status": "missing",
    }
    assert {
        "blocker": "verification_commands_rerun",
        "template_field": "- Verification commands rerun before approval",
        "required_value": "yes",
        "current_status": "pending",
    } in report["business_owner_approval_status"]["approval_action_items"]
    assert report["business_owner_approval_status"]["approval_action_items"][-1] == {
        "blocker": "candidate_boundary_acceptance",
        "template_field": "- Candidate-only boundary accepted",
        "required_value": "yes",
        "current_status": "pending",
    }
    gates = {gate["name"]: gate for gate in report["static_gates"]}
    assert gates["business_owner_approval_status"]["outcome"] == "pass"
    assert gates["business_owner_approval_status"]["detail"] == "pending; captured=false"
    assert "tests/golden_samples/GS-PNL-ATTR-WB-A" in report["golden_samples"]
    assert not any("full data-catalog/date review" in gap for gap in report["residual_gaps"])
    assert not any("direct page-keyed governance records" in gap for gap in report["residual_gaps"])
    assert any("Candidate metric dictionary-level approval remains pending." in gap for gap in report["residual_gaps"])
    assert any("Business owner approval is still required" in gap for gap in report["residual_gaps"])
    assert not any("dedicated golden sample is missing" in gap for gap in report["residual_gaps"])


def test_page_readiness_cli_emits_json_report() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "codex_page_readiness.py"),
            "--page-slug",
            "product-category-pnl",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["page_slug"] == "product-category-pnl"
    assert payload["overall_status"] == "static-pass"
    assert payload["blocking_gates"] == []


def test_all_page_readiness_covers_every_unique_seeded_trace_bundle() -> None:
    payload = build_all_page_readiness_report()
    expected_page_slugs = {
        bundle["page_slug"]
        for bundle in product_page_trace_bundles().values()
    }
    actual_page_slugs = {page["page_slug"] for page in payload["pages"]}

    assert payload["scope"] == "all-page-readiness"
    assert actual_page_slugs == expected_page_slugs
    assert payload["summary"]["page_count"] == len(expected_page_slugs)
    assert payload["summary"]["formal_or_governed_count"] == 5
    assert payload["summary"]["blocked_count"] == 0
    assert payload["summary"]["mixed_or_candidate_count"] == len(expected_page_slugs) - 5
    assert payload["summary"]["run_supported_count"] == sum(
        1 for page in payload["pages"] if page["run_supported"]
    )
    assert payload["summary"]["business_owner_approval_pending_count"] == 5
    assert payload["summary"]["business_owner_approval_action_item_count"] == 59
    assert payload["blocking_pages"] == []
    pending_by_slug = {
        page["page_slug"]: page
        for page in payload["business_owner_approval_pending_pages"]
    }
    assert set(pending_by_slug) == {
        "bond-analysis",
        "ledger-pnl",
        "pnl-attribution",
        "product-category-pnl",
        "stock-analysis",
    }
    product_pending = pending_by_slug["product-category-pnl"]
    assert product_pending["page_id"] == "PAGE-PROD-CAT-001"
    assert product_pending["approval_action_item_count"] == 15
    assert "reviewed_owner_decision_packet" in product_pending["remaining_blockers"]
    assert "owner_decision_next_review_queue_acknowledgement" in product_pending["remaining_blockers"]
    assert "golden_sample_artifact_reconciliation" in product_pending["remaining_blockers"]
    assert "closure_checklist_review" in product_pending["remaining_blockers"]
    assert "fallback_liability_branch_boundary_review" in product_pending["remaining_blockers"]
    assert product_pending["approval_field_status"]["golden_sample_artifact_reconciliation"] == "pending"
    assert product_pending["golden_sample_approval_artifact"]["approved"] is False
    assert product_pending["closure_checklist_artifact"]["ready_for_owner_approval"] is False
    assert product_pending["closure_checklist_artifact"]["partial_count"] == 10
    assert product_pending["closure_blocker_triage"]["blocker_count"] == 15
    assert product_pending["closure_blocker_triage"]["class_counts"] == {
        "1": 3,
        "2": 2,
        "3": 0,
        "4": 9,
        "5": 1,
    }
    assert product_pending["closure_blocker_triage"]["decision_required_count"] == 3
    assert product_pending["closure_blocker_triage"]["api_contract_required_count"] == 2
    ledger_pending = pending_by_slug["ledger-pnl"]
    assert ledger_pending["page_id"] == "PAGE-LEDGER-PNL-001"
    assert ledger_pending["approval_status"] == "pending"
    assert ledger_pending["business_owner_approval_captured"] is False
    assert ledger_pending["approval_action_item_count"] == 11
    assert "dedicated_golden_sample_review" in ledger_pending["remaining_blockers"]
    assert ledger_pending["approval_field_status"]["dedicated_golden_sample_review"] == "pending"
    assert ledger_pending["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert ledger_pending["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
    }
    assert {
        "blocker": "dedicated_golden_sample_review",
        "template_field": "- Dedicated ledger summary golden sample reviewed",
        "required_value": "yes",
        "current_status": "pending",
    } in ledger_pending["approval_action_items"]
    pnl_pending = pending_by_slug["pnl-attribution"]
    assert pnl_pending["page_id"] == "PAGE-PNL-ATTR-WB-001"
    assert pnl_pending["approval_action_item_count"] == 11
    assert "golden_sample_review" in pnl_pending["remaining_blockers"]
    assert pnl_pending["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    bond_pending = pending_by_slug["bond-analysis"]
    assert bond_pending["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert bond_pending["approval_action_item_count"] == 11
    assert "fixed_income_rule_review" in bond_pending["remaining_blockers"]
    assert bond_pending["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    stock_pending = pending_by_slug["stock-analysis"]
    assert stock_pending["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
    assert stock_pending["approval_action_item_count"] == 11
    assert "not_trading_instruction_review" in stock_pending["remaining_blockers"]
    assert stock_pending["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert payload["approval_status_commands"] == [
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -All -RequireApprovalCaptured",
    ]
    assert any(page["page_slug"] == "balance-analysis" for page in payload["pages"])
    assert any(page["page_slug"] == "reports-home" for page in payload["pages"])


def test_route_scope_classification_keeps_certification_claim_route_scoped() -> None:
    payload = build_route_scope_classification_report()
    rows_by_slug = {
        row["page_slug"]: row
        for row in payload["routes"]
    }

    assert payload["scope"] == "route-scope-classification"
    assert payload["summary"]["seeded_trace_bundle_count"] == 39
    assert payload["summary"]["route_count"] > 30
    assert payload["summary"]["business_contract_certified_count"] == 0
    assert payload["summary"]["evidence_pending_count"] == 23
    assert payload["summary"]["gate_i_gap_count"] == 0
    assert payload["summary"]["not_started_count"] == 0
    assert payload["summary"]["visible_unseeded_route_count"] == 0
    assert payload["summary"]["unclassified_count"] == 0
    assert payload["claim_boundary"] == (
        "No seeded route is business-contract-certified until direct golden approval, "
        "manual audit closure, and captured business-owner approval all exist."
    )

    assert rows_by_slug["product-category-pnl"]["classification"] == "evidence-pending"
    assert rows_by_slug["product-category-pnl"]["blocking_reason"] == "business_owner_approval_pending"
    assert rows_by_slug["product-category-pnl"]["has_approval_checker"] is True
    assert rows_by_slug["product-category-pnl"]["business_owner_approval_captured"] is False
    assert rows_by_slug["product-category-pnl"]["golden_sample_approved"] is False
    assert rows_by_slug["product-category-pnl"]["has_metric_dictionary_evidence"] is True

    assert rows_by_slug["pnl-attribution"]["classification"] == "evidence-pending"
    assert rows_by_slug["pnl-attribution"]["blocking_reason"] == "business_owner_approval_pending"
    assert rows_by_slug["pnl-attribution"]["has_approval_checker"] is True
    assert rows_by_slug["ledger-pnl"]["classification"] == "evidence-pending"
    assert rows_by_slug["ledger-pnl"]["blocking_reason"] == "business_owner_approval_pending"
    assert rows_by_slug["ledger-pnl"]["has_governance_record_command"] is True

    assert rows_by_slug["bond-analysis"]["classification"] == "evidence-pending"
    assert rows_by_slug["bond-analysis"]["blocking_reason"] == "business_owner_approval_pending"
    assert rows_by_slug["bond-analysis"]["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert rows_by_slug["bond-analysis"]["has_approval_checker"] is True
    assert rows_by_slug["stock-analysis"]["classification"] == "evidence-pending"
    assert rows_by_slug["stock-analysis"]["blocking_reason"] == "business_owner_approval_pending"
    assert rows_by_slug["stock-analysis"]["has_approval_checker"] is True
    assert rows_by_slug["stock-analysis"]["has_golden_samples"] is True
    assert rows_by_slug["stock-analysis"]["golden_sample_approved"] is False
    assert rows_by_slug["cross-asset"]["classification"] == "frontend-ready"
    assert rows_by_slug["cross-asset"]["blocking_reason"] == "analysis_surface_not_formal_business_truth"
    assert rows_by_slug["cross-asset"]["page_id"] == "GAP-CROSS-ASSET-PAGE"
    assert rows_by_slug["cross-asset"]["source"] == "seeded_trace_bundle"

    assert rows_by_slug["macro-toolkit"]["classification"] == "frontend-ready"
    assert rows_by_slug["macro-toolkit"]["blocking_reason"] == "analysis_surface_not_formal_business_truth"
    assert rows_by_slug["macro-toolkit"]["run_supported"] is True
    assert rows_by_slug["reports-home"]["classification"] == "frontend-only"
    assert rows_by_slug["reports-home"]["blocking_reason"] == "home_or_summary_surface_not_page_certification"
    assert rows_by_slug["reports-home"]["run_supported"] is False
    assert rows_by_slug["decision-items"]["classification"] == "evidence-pending"
    assert rows_by_slug["decision-items"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["decision-items"]["route"] == "/decision-items"
    assert rows_by_slug["decision-items"]["page_id"] == "GAP-DECISION-ITEMS-PAGE"
    assert rows_by_slug["decision-items"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["decision-items"]["run_supported"] is True
    assert rows_by_slug["decision-items"]["visible_navigation_route"] is True
    assert rows_by_slug["kpi-performance"]["classification"] == "evidence-pending"
    assert rows_by_slug["kpi-performance"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["kpi-performance"]["route"] == "/kpi"
    assert rows_by_slug["kpi-performance"]["page_id"] == "GAP-KPI-PERFORMANCE-PAGE"
    assert rows_by_slug["kpi-performance"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["kpi-performance"]["run_supported"] is True
    assert rows_by_slug["kpi-performance"]["visible_navigation_route"] is True
    assert rows_by_slug["average-balance"]["classification"] == "evidence-pending"
    assert rows_by_slug["average-balance"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["average-balance"]["route"] == "/average-balance"
    assert rows_by_slug["average-balance"]["page_id"] == "GAP-AVERAGE-BALANCE-PAGE"
    assert rows_by_slug["average-balance"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["average-balance"]["run_supported"] is True
    assert rows_by_slug["average-balance"]["formal_use_allowed"] is False
    assert rows_by_slug["average-balance"]["has_golden_samples"] is False
    assert rows_by_slug["average-balance"]["golden_sample_approved"] is False
    assert rows_by_slug["bank-ledger-dashboard"]["classification"] == "evidence-pending"
    assert rows_by_slug["bank-ledger-dashboard"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["bank-ledger-dashboard"]["route"] == "/bank-ledger-dashboard"
    assert rows_by_slug["bank-ledger-dashboard"]["page_id"] == "GAP-BANK-LEDGER-DASHBOARD-PAGE"
    assert rows_by_slug["bank-ledger-dashboard"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["bank-ledger-dashboard"]["run_supported"] is True
    assert rows_by_slug["bank-ledger-dashboard"]["formal_use_allowed"] is False
    assert rows_by_slug["bank-ledger-dashboard"]["has_golden_samples"] is False
    assert rows_by_slug["bank-ledger-dashboard"]["golden_sample_approved"] is False
    assert rows_by_slug["cashflow-projection"]["classification"] == "evidence-pending"
    assert rows_by_slug["cashflow-projection"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["cashflow-projection"]["route"] == "/cashflow-projection"
    assert rows_by_slug["cashflow-projection"]["page_id"] == "GAP-CASHFLOW-PROJECTION-PAGE"
    assert rows_by_slug["cashflow-projection"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["cashflow-projection"]["run_supported"] is True
    assert rows_by_slug["cashflow-projection"]["formal_use_allowed"] is False
    assert rows_by_slug["cashflow-projection"]["has_golden_samples"] is False
    assert rows_by_slug["cashflow-projection"]["golden_sample_approved"] is False
    assert rows_by_slug["concentration-monitor"]["classification"] == "evidence-pending"
    assert rows_by_slug["concentration-monitor"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["concentration-monitor"]["route"] == "/concentration-monitor"
    assert rows_by_slug["concentration-monitor"]["page_id"] == "GAP-CONCENTRATION-MONITOR-PAGE"
    assert rows_by_slug["concentration-monitor"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["concentration-monitor"]["run_supported"] is True
    assert rows_by_slug["concentration-monitor"]["formal_use_allowed"] is False
    assert rows_by_slug["concentration-monitor"]["has_golden_samples"] is False
    assert rows_by_slug["concentration-monitor"]["golden_sample_approved"] is False
    assert rows_by_slug["team-performance"]["classification"] == "evidence-pending"
    assert rows_by_slug["team-performance"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["team-performance"]["route"] == "/team-performance"
    assert rows_by_slug["team-performance"]["page_id"] == "GAP-TEAM-PERFORMANCE-PAGE"
    assert rows_by_slug["team-performance"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["team-performance"]["run_supported"] is True
    assert rows_by_slug["team-performance"]["formal_use_allowed"] is False
    assert rows_by_slug["team-performance"]["has_golden_samples"] is False
    assert rows_by_slug["team-performance"]["golden_sample_approved"] is False
    assert rows_by_slug["platform-config"]["classification"] == "evidence-pending"
    assert rows_by_slug["platform-config"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["platform-config"]["route"] == "/platform-config"
    assert rows_by_slug["platform-config"]["page_id"] == "GAP-PLATFORM-CONFIG-PAGE"
    assert rows_by_slug["platform-config"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["platform-config"]["run_supported"] is True
    assert rows_by_slug["platform-config"]["formal_use_allowed"] is False
    assert rows_by_slug["platform-config"]["has_golden_samples"] is False
    assert rows_by_slug["platform-config"]["golden_sample_approved"] is False
    assert rows_by_slug["news-events"]["classification"] == "evidence-pending"
    assert rows_by_slug["news-events"]["blocking_reason"] == "golden_or_manual_audit_or_owner_approval_pending"
    assert rows_by_slug["news-events"]["route"] == "/news-events"
    assert rows_by_slug["news-events"]["page_id"] == "GAP-NEWS-EVENTS-PAGE"
    assert rows_by_slug["news-events"]["source"] == "seeded_trace_bundle"
    assert rows_by_slug["news-events"]["run_supported"] is True
    assert rows_by_slug["news-events"]["formal_use_allowed"] is False
    assert rows_by_slug["news-events"]["has_golden_samples"] is False
    assert rows_by_slug["news-events"]["golden_sample_approved"] is False

    assert payload["certification_ready_routes"] == []
    assert "product-category-pnl" in payload["next_evidence_pending_routes"]
    assert "bond-analysis" in payload["next_evidence_pending_routes"]
    assert "stock-analysis" in payload["next_evidence_pending_routes"]
    assert "average-balance" in payload["next_evidence_pending_routes"]
    assert "bank-ledger-dashboard" in payload["next_evidence_pending_routes"]
    assert "cashflow-projection" in payload["next_evidence_pending_routes"]
    assert "concentration-monitor" in payload["next_evidence_pending_routes"]
    assert "team-performance" in payload["next_evidence_pending_routes"]
    assert "platform-config" in payload["next_evidence_pending_routes"]
    assert "news-events" in payload["next_evidence_pending_routes"]
    assert "bond-analysis" not in payload["next_gate_i_gap_routes"]
    assert payload["next_gate_i_gap_routes"] == []


def test_all_page_readiness_embeds_route_scope_classification_summary() -> None:
    payload = build_all_page_readiness_report()

    assert payload["route_scope_classification"]["scope"] == "route-scope-classification"
    assert payload["route_scope_classification"]["summary"]["seeded_trace_bundle_count"] == payload["summary"]["page_count"]
    assert payload["route_scope_classification"]["summary"]["route_count"] >= payload["summary"]["page_count"]
    assert payload["route_scope_classification"]["summary"]["business_contract_certified_count"] == 0
    assert payload["summary"]["route_scope_business_contract_certified_count"] == 0
    assert payload["summary"]["route_scope_evidence_pending_count"] >= 3
    assert payload["summary"]["route_scope_gate_i_gap_count"] == 0
    assert payload["summary"]["route_scope_unclassified_count"] == 0


def test_page_readiness_cli_all_mode_emits_batch_report() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "codex_page_readiness.py"),
            "--all",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["scope"] == "all-page-readiness"
    assert payload["summary"]["page_count"] == 39
    assert payload["summary"]["blocked_count"] == 0
    assert payload["summary"]["run_supported_count"] == 27
    assert payload["summary"]["business_owner_approval_pending_count"] == 5
    assert payload["summary"]["business_owner_approval_action_item_count"] == 59
    assert payload["blocking_pages"] == []
    assert {
        page["page_slug"]
        for page in payload["business_owner_approval_pending_pages"]
    } == {"bond-analysis", "ledger-pnl", "pnl-attribution", "product-category-pnl", "stock-analysis"}
    assert payload["approval_status_commands"] == [
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -All -RequireApprovalCaptured",
    ]
    assert any(page["page_slug"] == "product-category-pnl" for page in payload["pages"])
    assert any(page["page_slug"] == "macro-toolkit" for page in payload["pages"])


def test_page_readiness_cli_route_scope_mode_emits_classification_report() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "codex_page_readiness.py"),
            "--route-scope",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    rows_by_slug = {
        row["page_slug"]: row
        for row in payload["routes"]
    }

    assert payload["scope"] == "route-scope-classification"
    assert payload["summary"]["business_contract_certified_count"] == 0
    assert rows_by_slug["product-category-pnl"]["classification"] == "evidence-pending"
    assert rows_by_slug["bond-analysis"]["classification"] == "evidence-pending"
    assert rows_by_slug["stock-analysis"]["classification"] == "evidence-pending"
    assert rows_by_slug["decision-items"]["classification"] == "evidence-pending"
    assert rows_by_slug["kpi-performance"]["classification"] == "evidence-pending"
    assert rows_by_slug["average-balance"]["classification"] == "evidence-pending"
    assert rows_by_slug["cashflow-projection"]["classification"] == "evidence-pending"
    assert rows_by_slug["team-performance"]["classification"] == "evidence-pending"
    assert rows_by_slug["platform-config"]["classification"] == "evidence-pending"
    assert rows_by_slug["news-events"]["classification"] == "evidence-pending"
    assert payload["summary"]["visible_unseeded_route_count"] == 0
    assert payload["summary"]["not_started_count"] == 0


def test_pnl_attribution_page_readiness_powershell_surfaces_approval_blockers() -> None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "codex-page-readiness.ps1"),
            "-PageSlug",
            "pnl-attribution",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert "business_owner_approval_status: pass (pending; captured=false)" in completed.stdout
    assert "python scripts/check_pnl_attribution_business_owner_approval.py --require-captured" in completed.stdout
    assert (
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
        "-PageSlug pnl-attribution -Run"
    ) in completed.stdout
    assert (
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
        "-PageSlug pnl-attribution -RequireApprovalCaptured"
    ) in completed.stdout
    assert "Approval status blockers:" in completed.stdout
    assert "Approval evidence scope:" in completed.stdout
    assert "- proves_page_execution=False" in completed.stdout
    assert "- captures_business_owner_approval=False" in completed.stdout
    assert "- business_owner_name" in completed.stdout
    assert "- candidate_boundary_acceptance" in completed.stdout
    assert "Approval action item count: 11" in completed.stdout
    assert "Approval action items:" in completed.stdout
    assert "- Business owner name: Business owner legal or operating name (missing)" in completed.stdout
    assert "- Verification commands rerun before approval: yes (pending)" in completed.stdout
    assert "- Candidate-only boundary accepted: yes (pending)" in completed.stdout
    assert "- - Candidate-only boundary accepted" not in completed.stdout


def test_pnl_attribution_page_readiness_powershell_can_require_captured_approval() -> None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "codex-page-readiness.ps1"),
            "-PageSlug",
            "pnl-attribution",
            "-RequireApprovalCaptured",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    combined_output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "Approval capture is required but not complete." in combined_output
    assert "- business_owner_approval" in combined_output
    assert "- verification_commands_rerun" in combined_output
    assert "- candidate_boundary_acceptance" in combined_output
    assert "Approval evidence scope:" in combined_output
    assert "- proves_page_execution=False" in combined_output
    assert "- captures_business_owner_approval=False" in combined_output
    assert "Approval action items:" in combined_output
    assert combined_output.count("Approval action items:") == 1
    assert "- Business owner name: Business owner legal or operating name (missing)" in combined_output
    assert "- Verification commands rerun before approval: yes (pending)" in combined_output
    assert "- Candidate-only boundary accepted: yes (pending)" in combined_output
    assert "- - Candidate-only boundary accepted" not in combined_output


def test_all_page_readiness_powershell_can_require_captured_approval() -> None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "codex-page-readiness.ps1"),
            "-All",
            "-RequireApprovalCaptured",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    combined_output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "Approval capture is required but not complete." in combined_output
    assert "ledger-pnl" in combined_output
    assert "PAGE-LEDGER-PNL-001" in combined_output
    assert "product-category-pnl" in combined_output
    assert "PAGE-PROD-CAT-001" in combined_output
    assert "pnl-attribution" in combined_output
    assert "PAGE-PNL-ATTR-WB-001" in combined_output
    assert "bond-analysis" in combined_output
    assert "PAGE-BOND-ANALYSIS-001" in combined_output
    assert "- business_owner_approval" in combined_output
    assert "- verification_commands_rerun" in combined_output
    assert "- candidate_boundary_acceptance" in combined_output
    assert "Approval evidence scope:" in combined_output
    assert "  - proves_page_execution=False" in combined_output
    assert "  - captures_business_owner_approval=False" in combined_output
    assert "Approval action items:" in combined_output
    assert "  - Business owner name: Business owner legal or operating name (missing)" in combined_output
    assert "  - Verification commands rerun before approval: yes (pending)" in combined_output
    assert "  - Candidate-only boundary accepted: yes (pending)" in combined_output
    assert "  - Dedicated ledger summary golden sample reviewed: yes (pending)" in combined_output
    assert "  - Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled: yes (pending)" in combined_output
    assert "  - - Candidate-only boundary accepted" not in combined_output


def test_all_page_readiness_powershell_surfaces_pending_approval_summary() -> None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "codex-page-readiness.ps1"),
            "-All",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert "Business-owner approval pending pages:" in completed.stdout
    assert "business_owner_approval_action_item_count=59" in completed.stdout
    assert "- product-category-pnl (PAGE-PROD-CAT-001): pending; captured=False; action_items=15" in completed.stdout
    assert "- ledger-pnl (PAGE-LEDGER-PNL-001): pending; captured=False; action_items=11" in completed.stdout
    assert "- pnl-attribution (PAGE-PNL-ATTR-WB-001): pending; captured=False; action_items=11" in completed.stdout
    assert "- bond-analysis (PAGE-BOND-ANALYSIS-001): pending; captured=False; action_items=11" in completed.stdout
    assert "- stock-analysis (GAP-STOCK-ANALYSIS-PAGE): pending; captured=False; action_items=11" in completed.stdout
    assert "Approval evidence scope:" in completed.stdout
    assert "  - proves_page_execution=False" in completed.stdout
    assert "  - captures_business_owner_approval=False" in completed.stdout
    assert "Approval action items:" in completed.stdout
    assert "  - Business owner name: Business owner legal or operating name (missing)" in completed.stdout
    assert "  - Verification commands rerun before approval: yes (pending)" in completed.stdout
    assert "  - Candidate-only boundary accepted: yes (pending)" in completed.stdout
    assert "  - Dedicated ledger summary golden sample reviewed: yes (pending)" in completed.stdout
    assert "  - Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled: yes (pending)" in completed.stdout
    assert "  - - Candidate-only boundary accepted" not in completed.stdout
    assert "Approval status commands:" in completed.stdout
    assert (
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
        "-All -RequireApprovalCaptured"
    ) in completed.stdout
