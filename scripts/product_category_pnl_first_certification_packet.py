from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_product_category_pnl_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402
from scripts.product_category_pnl_owner_decision_packet import (  # noqa: E402
    DEFAULT_OUTPUT as OWNER_DECISION_PACKET_OUTPUT,
    build_packet as build_owner_decision_packet,
)


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "product-category-pnl-first-certification-packet.md"
FIRST_CERTIFICATION_FRESHNESS_MARKERS = (
    "## Packet Freshness Guard\n"
    "`packet_generator=script-owned`\n"
    "`source_artifacts=readiness_report, approval_template, closure_blocker_triage`"
)
OWNER_DECISION_FRESHNESS_MARKERS = (
    "## Packet Freshness Guard\n"
    "`packet_generator=script-owned`\n"
    "`source_artifact=docs/pnl/product-category-remaining-blockers.md`"
)
FRESHNESS_MARKERS_BY_ARTIFACT_KEY = {
    "first_certification_packet": FIRST_CERTIFICATION_FRESHNESS_MARKERS,
    "owner_decision_packet": OWNER_DECISION_FRESHNESS_MARKERS,
}

OWNER_REVIEW_ARTIFACTS: list[dict[str, str]] = [
    {
        "key": "boundary_status",
        "path": "docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json",
    },
    {
        "key": "first_certification_packet",
        "path": "docs/pnl/product-category-pnl-first-certification-packet.md",
        "requires_freshness_guard": "true",
        "freshness_markers": FIRST_CERTIFICATION_FRESHNESS_MARKERS,
    },
    {
        "key": "owner_decision_packet",
        "path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
        "requires_freshness_guard": "true",
        "freshness_markers": OWNER_DECISION_FRESHNESS_MARKERS,
    },
    {
        "key": "approval_template",
        "path": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
    },
    {
        "key": "closure_checklist",
        "path": "docs/pnl/product-category-closure-checklist.md",
    },
    {
        "key": "closure_blocker_triage",
        "path": "docs/pnl/product-category-remaining-blockers.md",
    },
    {
        "key": "golden_sample_approval_artifact",
        "path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
    },
]


ACTION_SIGNOFF_METADATA = {
    "business_owner_name": {
        "signoff_group": "owner_identity",
        "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
        "pre_signature_action": "Fill the business owner legal or operating name.",
    },
    "business_owner_role": {
        "signoff_group": "owner_identity",
        "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
        "pre_signature_action": "Fill the accountable business owner role.",
    },
    "approval_decision": {
        "signoff_group": "owner_decision",
        "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
        "pre_signature_action": "Set approval decision to approve after all review gates are satisfied.",
    },
    "approval_date": {
        "signoff_group": "owner_decision",
        "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
        "pre_signature_action": "Fill an approval date in YYYY-MM-DD format.",
    },
    "business_owner_signature": {
        "signoff_group": "owner_decision",
        "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
        "pre_signature_action": "Capture the business owner signature after all prerequisite review fields are valid.",
    },
    "governance_record_review": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json",
        "pre_signature_action": "Review the governance boundary record and mark this field yes only after review.",
    },
    "reviewed_owner_decision_packet": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
        "pre_signature_action": "Review the owner decision packet and keep unresolved product/API decisions pending.",
    },
    "owner_decision_next_review_queue_acknowledgement": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md#next-review-queue",
        "pre_signature_action": "Acknowledge 4 next-review queue topics as intake follow-ups, not captured decisions.",
    },
    "golden_sample_artifact_reconciliation": {
        "signoff_group": "evidence_review",
        "evidence_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
        "pre_signature_action": "Reconcile the golden sample approval artifact to approved with non-placeholder owner, approver, and approval date.",
    },
    "closure_checklist_review": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/pnl/product-category-closure-checklist.md",
        "pre_signature_action": "Review closure checklist units and leave certification pending while any unit remains PARTIAL.",
    },
    "fallback_liability_branch_boundary_review": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/pnl/product-category-page-truth-contract.md",
        "pre_signature_action": "Review fallback liability branch boundary evidence without treating it as synthetic production proof.",
    },
    "ui_api_payload_review": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#source-to-screen-trace",
        "pre_signature_action": "Review current UI/API payload against MTR-PCP-001 through MTR-PCP-012 source-to-screen trace.",
    },
    "certification_packet_consistency": {
        "signoff_group": "evidence_review",
        "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#certification-packet-consistency",
        "pre_signature_action": (
            "Regenerate and review the first-certification packet consistency section "
            "without treating consistency as approval or certification."
        ),
    },
    "live_smoke_evidence_review": {
        "signoff_group": "pre_signature_verification",
        "evidence_path": "latest_readiness_gate_evidence",
        "pre_signature_action": "Review fresh live smoke/browser evidence before signature.",
    },
    "verification_commands_rerun": {
        "signoff_group": "pre_signature_verification",
        "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#pre-signature-verification-rerun-receipt",
        "pre_signature_action": "Rerun the pre-signature readiness and approval checker commands.",
    },
    "evidence_pending_boundary_acceptance": {
        "signoff_group": "boundary_acceptance",
        "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#evidence-scope",
        "pre_signature_action": "Explicitly accept the evidence-pending boundary if approval proceeds without route certification.",
    },
}


METRIC_TRACE_ROWS: list[dict[str, str]] = [
    {
        "metric_id": "MTR-PCP-001",
        "metric_name": "Product-category asset-side business net income",
        "api_field": "result.asset_total.business_net_income",
        "client_model_path": "getProductCategoryPnl -> ProductCategoryPnlPage -> assetTotal",
        "component_anchor": "product-category-formal-headline-totals",
        "formatter": "formatProductCategoryValue",
        "display_unit": "yi_yuan",
        "status_boundary": "formal/governed evidence-pending; owner approval not captured",
    },
    {
        "metric_id": "MTR-PCP-002",
        "metric_name": "Product-category liability-side business net income",
        "api_field": "result.liability_total.business_net_income",
        "client_model_path": "getProductCategoryPnl -> ProductCategoryPnlPage -> liabilityTotal",
        "component_anchor": "product-category-formal-headline-totals",
        "formatter": "formatProductCategoryValue",
        "display_unit": "yi_yuan",
        "status_boundary": "formal/governed evidence-pending; owner approval not captured",
    },
    {
        "metric_id": "MTR-PCP-003",
        "metric_name": "Product-category total business net income",
        "api_field": "result.grand_total.business_net_income",
        "client_model_path": "getProductCategoryPnl -> ProductCategoryPnlPage -> displayedGrandTotal",
        "component_anchor": "product-category-formal-headline-totals",
        "formatter": "formatProductCategoryValue",
        "display_unit": "yi_yuan",
        "status_boundary": "backend total wins; frontend must not recompute asset + liability",
    },
    {
        "metric_id": "MTR-PCP-004",
        "metric_name": "Product-category row CNX scale",
        "api_field": "result.rows[].cnx_scale",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cnx_scale",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "row-scoped detail metric; category_id/side/view/report_date are dimensions",
    },
    {
        "metric_id": "MTR-PCP-005",
        "metric_name": "Product-category row CNY scale",
        "api_field": "result.rows[].cny_scale",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cny_scale",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "row-scoped detail metric; category_id/side/view/report_date are dimensions",
    },
    {
        "metric_id": "MTR-PCP-006",
        "metric_name": "Product-category row foreign-currency scale",
        "api_field": "result.rows[].foreign_scale",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.foreign_scale",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "row-scoped detail metric; category_id/side/view/report_date are dimensions",
    },
    {
        "metric_id": "MTR-PCP-007",
        "metric_name": "Product-category row CNY FTP",
        "api_field": "result.rows[].cny_ftp",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cny_ftp",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "scenario may change backend FTP payload; frontend must not recompute",
    },
    {
        "metric_id": "MTR-PCP-008",
        "metric_name": "Product-category row foreign-currency FTP",
        "api_field": "result.rows[].foreign_ftp",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.foreign_ftp",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "scenario may change backend FTP payload; frontend must not recompute",
    },
    {
        "metric_id": "MTR-PCP-009",
        "metric_name": "Product-category row CNY net income",
        "api_field": "result.rows[].cny_net",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.cny_net",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "backend payload wins; liability sign normalization is display-only",
    },
    {
        "metric_id": "MTR-PCP-010",
        "metric_name": "Product-category row foreign-currency net income",
        "api_field": "result.rows[].foreign_net",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.foreign_net",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "backend payload wins; liability sign normalization is display-only",
    },
    {
        "metric_id": "MTR-PCP-011",
        "metric_name": "Product-category row business net income",
        "api_field": "result.rows[].business_net_income",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.business_net_income",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryRowDisplayValue",
        "display_unit": "yi_yuan",
        "status_boundary": "backend payload wins; liability sign normalization is display-only",
    },
    {
        "metric_id": "MTR-PCP-012",
        "metric_name": "Product-category row weighted yield",
        "api_field": "result.rows[].weighted_yield",
        "client_model_path": "getProductCategoryPnl -> selectProductCategoryDetailRows -> row.weighted_yield",
        "component_anchor": "product-category-table",
        "formatter": "formatProductCategoryYieldValue",
        "display_unit": "percent",
        "status_boundary": "not money-scaled; null remains explicit",
    },
]

LATEST_READINESS_GATE_EVIDENCE = {
    "command": (
        "powershell -NoProfile -ExecutionPolicy Bypass -File "
        "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive"
    ),
    "evidence_basis": "recorded_prior_gate_output",
    "packet_generator_reruns_gate": "false",
    "status": "passed",
    "static_readiness": "passed",
    "live_smoke": "passed",
    "mcp_contract_tests": "175 passed",
    "backend_flow_mapping_tests": "59 passed",
    "frontend_tests": "155 passed",
    "browser_a11y_smoke": "1 passed",
    "frontend_typecheck": "passed",
    "frontend_debt_audit": "passed",
    "frontend_production_build": "passed",
    "certification_boundary": (
        "This evidence proves the verification gate passed; it does not capture "
        "business-owner approval, manual audit closure, or golden approval artifact reconciliation."
    ),
    "rerun_boundary": (
        "Regenerating this packet only records the latest available gate evidence; "
        "the pre-approval runbook must rerun the gate before owner signature."
    ),
}


def _latest_readiness_gate_evidence(readiness: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(LATEST_READINESS_GATE_EVIDENCE)
    artifacts = list(readiness["golden_sample_approval_artifacts"])
    primary_artifact = artifacts[0] if artifacts else {}
    evidence.update(
        {
            "golden_boundary_status": str(
                primary_artifact.get("readiness_boundary_status", "missing")
            ),
            "golden_artifact_status": str(
                readiness["golden_sample_approval_artifact_status"]
            ),
            "golden_artifact_approved": _golden_artifacts_have_full_approval(artifacts),
            "golden_sample_approval_artifact_mismatch": bool(
                readiness["golden_sample_approval_artifact_mismatch"]
            ),
        }
    )
    return evidence


def _golden_artifacts_have_full_approval(artifacts: list[dict[str, Any]]) -> bool:
    if not artifacts:
        return False
    return all(
        artifact.get("status") == "approved"
        and artifact.get("owner") not in {None, "", "TBD", "unknown"}
        and artifact.get("approver") not in {None, "", "TBD", "unknown"}
        and artifact.get("approved_at") not in {None, "", "TBD", "unknown"}
        for artifact in artifacts
    )


def _generated_artifact_freshness_scope(
    generated_artifact_freshness: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    artifact_count = len(generated_artifact_freshness)
    valid_artifact_count = sum(
        1
        for artifact in generated_artifact_freshness.values()
        if artifact.get("freshness_status") == "valid"
    )
    return {
        "scope_kind": "generated_artifact_freshness_scope",
        "artifact_count": artifact_count,
        "valid_artifact_count": valid_artifact_count,
        "stale_or_missing_artifact_count": artifact_count - valid_artifact_count,
        "freshness_check_effect": "none",
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "writes_governance_records": False,
        "certification_effect": "none",
        "boundary": (
            "Generated artifact freshness proves only that script-owned packet outputs match the current "
            "renderers; it does not approve, sign, certify, write governance records, or capture decisions."
        ),
    }


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict[str, Any]:
    readiness = build_page_readiness_report("product-category-pnl")
    approval = build_approval_status(template_path)
    triage = dict(approval["closure_blocker_triage"])
    owner_decision_packet = build_owner_decision_packet(template_path=template_path)
    owner_review_intake_checklist = _owner_review_intake_checklist()
    signoff_summary = dict(approval["business_owner_action_signoff_summary"])
    generated_artifact_freshness = dict(approval["generated_artifact_freshness"])
    golden_status = str(readiness["golden_sample_approval_artifact_status"])
    golden_mismatch = bool(readiness["golden_sample_approval_artifact_mismatch"])
    latest_readiness_gate_evidence = _latest_readiness_gate_evidence(readiness)
    closure_checklist = dict(approval["closure_checklist_artifact"])
    reviewer_checklist = _reviewer_checklist(
        approval["closure_blocker_triage"],
        owner_decision_packet=owner_decision_packet,
    )
    owner_reviewer_receipt = _owner_reviewer_receipt(reviewer_checklist)
    return {
        "packet_kind": "product_category_pnl_first_certification_packet",
        "page_id": readiness["page_id"],
        "page_slug": readiness["page_slug"],
        "route": readiness["route"],
        "primary_api": readiness["primary_api"],
        "business_contract_status": "evidence-pending",
        "business_contract_certified": False,
        "handoff_status": "owner_actions_required",
        "approval_status": approval["approval_status"],
        "formal_use_allowed": approval["formal_use_allowed"],
        "closure_approved": approval["closure_approved"],
        "business_owner_approval_captured": approval["business_owner_approval_captured"],
        "approval_action_item_count": approval["approval_action_item_count"],
        "remaining_blockers": list(approval["remaining_blockers"]),
        "owner_action_items": list(approval["approval_action_items"]),
        "closure_blocker_triage": triage,
        "owner_closure_gate_matrix": _owner_closure_gate_matrix(
            readiness_gate=latest_readiness_gate_evidence,
            triage=triage,
            golden_status=golden_status,
            golden_mismatch=golden_mismatch,
            closure_checklist=closure_checklist,
            approval_action_item_count=int(approval["approval_action_item_count"]),
            business_owner_action_signed_item_count=int(signoff_summary["signed_item_count"]),
            business_owner_action_pending_or_missing_item_count=int(
                signoff_summary["unsigned_item_count"]
            ),
        ),
        "owner_readiness_receipt": _owner_readiness_receipt(
            approval=approval,
            triage=triage,
            golden_mismatch=golden_mismatch,
            closure_checklist=closure_checklist,
            owner_review_intake_checklist=owner_review_intake_checklist,
        ),
        "owner_review_intake_checklist": owner_review_intake_checklist,
        "approval_checker_generated_artifact_freshness": generated_artifact_freshness,
        "approval_checker_generated_artifact_freshness_scope": _generated_artifact_freshness_scope(
            generated_artifact_freshness
        ),
        "certification_packet_consistency": dict(
            approval["certification_packet_consistency"]
        ),
        "owner_action_status_scope": dict(approval["owner_action_status_scope"]),
        "owner_pre_signature_blocker_scope": dict(
            approval["owner_pre_signature_blocker_scope"]
        ),
        "owner_decision_packet_bridge": _owner_decision_packet_bridge(owner_decision_packet),
        "pre_signature_verification_rerun_receipt": _pre_signature_verification_rerun_receipt(
            approval=approval,
            triage=triage,
            readiness_gate=latest_readiness_gate_evidence,
            golden_mismatch=golden_mismatch,
            closure_checklist=closure_checklist,
            owner_review_intake_checklist=owner_review_intake_checklist,
        ),
        "golden_sample_approval_artifact_status": golden_status,
        "golden_sample_approval_artifact_mismatch": golden_mismatch,
        "golden_sample_approval_artifacts": list(
            readiness["golden_sample_approval_artifacts"]
        ),
        "metric_trace_rows": [dict(row) for row in METRIC_TRACE_ROWS],
        "latest_readiness_gate_evidence": latest_readiness_gate_evidence,
        "reviewer_checklist": reviewer_checklist,
        "owner_reviewer_receipt": owner_reviewer_receipt,
        "owner_reviewer_receipt_field_coverage": _owner_reviewer_receipt_field_coverage(
            owner_reviewer_receipt,
            approval["approval_field_status"],
        ),
        "business_owner_action_signoff_matrix": _business_owner_action_signoff_matrix(
            approval["approval_action_items"],
        ),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "captures_product_or_api_decisions": False,
            "certification_effect": "none",
        },
        "evidence_anchors": {
            "truth_contract": "docs/pnl/product-category-page-truth-contract.md",
            "metric_dictionary": "docs/metric_dictionary.md",
            "golden_sample": "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "boundary_status": "docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json",
            "approval_template": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
            "owner_decision_packet": "docs/pnl/product-category-pnl-owner-decision-packet.md",
            "model_tests": "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts",
            "page_tests": "frontend/src/test/ProductCategoryPnlPage.test.tsx",
        },
    }


def _owner_closure_gate_matrix(
    *,
    readiness_gate: dict[str, str],
    triage: dict[str, Any],
    golden_status: str,
    golden_mismatch: bool,
    closure_checklist: dict[str, Any],
    approval_action_item_count: int,
    business_owner_action_signed_item_count: int,
    business_owner_action_pending_or_missing_item_count: int,
) -> list[dict[str, object]]:
    partial_units = int(closure_checklist["partial_count"])
    return [
        {
            "gate": "machine_verification",
            "status": str(readiness_gate["status"]),
            "evidence": "latest_readiness_gate_evidence",
            "can_be_closed_by_code": False,
            "required_owner_action": "Review evidence; no approval is captured by this gate.",
        },
        {
            "gate": "owner_decisions",
            "status": "pending_owner_decisions",
            "evidence": "docs/pnl/product-category-pnl-owner-decision-packet.md",
            "can_be_closed_by_code": False,
            "required_owner_action": (
                f"Resolve {triage['decision_required_count']} product decisions and "
                f"{triage['api_contract_required_count']} backend/API contract decisions."
            ),
        },
        {
            "gate": "golden_sample_approval",
            "status": f"{golden_status}; mismatch={str(golden_mismatch).lower()}",
            "evidence": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
            "can_be_closed_by_code": False,
            "required_owner_action": (
                "Approve GS-PROD-CAT-PNL-A with non-placeholder owner, approver, and approval date."
            ),
        },
        {
            "gate": "manual_closure_checklist",
            "status": f"{partial_units} partial units remain",
            "evidence": "docs/pnl/product-category-closure-checklist.md",
            "can_be_closed_by_code": False,
            "required_owner_action": (
                "Review and close each checklist unit from PARTIAL to CLOSED only when evidence and "
                "decisions support it."
            ),
        },
        {
            "gate": "business_owner_approval",
            "status": (
                f"pending; {approval_action_item_count} action items; "
                f"{business_owner_action_signed_item_count} signed; "
                f"{business_owner_action_pending_or_missing_item_count} pending or missing"
            ),
            "evidence": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
            "can_be_closed_by_code": False,
            "required_owner_action": (
                "Complete and sign the approval template after reviewing all prior gates."
            ),
        },
    ]


def _owner_readiness_receipt(
    *,
    approval: dict[str, Any],
    triage: dict[str, Any],
    golden_mismatch: bool,
    closure_checklist: dict[str, Any],
    owner_review_intake_checklist: dict[str, object],
) -> dict[str, object]:
    partial_units = int(closure_checklist["partial_count"])
    owner_decisions_pending = int(triage["decision_required_count"]) + int(
        triage["api_contract_required_count"]
    )
    machine_evidence_ready = bool(owner_review_intake_checklist["review_intake_ready"])
    promotion_blockers = [
        "business_owner_approval_captured=false",
        "closure_approved=false",
        f"golden_sample_approval_artifact_mismatch={str(golden_mismatch).lower()}",
        f"manual_closure_checklist_has_partial_units={partial_units}",
        f"owner_decisions_pending={owner_decisions_pending}",
    ]
    if not machine_evidence_ready:
        promotion_blockers.append("owner_review_intake_ready=false")
    intake_required_evidence = [
        f"missing_required_artifact:{item}"
        for item in owner_review_intake_checklist["missing_required_artifacts"]
    ] + [
        f"missing_freshness_guard_artifact:{item}"
        for item in owner_review_intake_checklist["missing_freshness_guard_artifacts"]
    ]
    human_required_evidence = [
        str(item["blocker"]) for item in approval["approval_action_items"]
    ] + intake_required_evidence
    artifact_exists = {
        str(artifact["key"]): bool(artifact["exists"])
        for artifact in owner_review_intake_checklist["artifacts"]
    }
    machine_prepared_evidence = [
        "latest_readiness_gate_evidence",
        "source_to_screen_trace:MTR-PCP-001..MTR-PCP-012",
    ]
    if artifact_exists.get("owner_decision_packet", False):
        machine_prepared_evidence.append("owner_decision_packet_artifact_exists")
    if artifact_exists.get("approval_template", False):
        machine_prepared_evidence.append("approval_template_artifact_exists")
    return {
        "receipt_kind": "pre_signature_owner_readiness_receipt",
        "owner_signable": False,
        "machine_evidence_ready": machine_evidence_ready,
        "business_decisions_ready": owner_decisions_pending == 0,
        "golden_sample_ready": not golden_mismatch,
        "manual_audit_ready": partial_units == 0,
        "business_owner_signature_ready": bool(
            approval["business_owner_approval_captured"]
        ),
        "can_promote_certification": False,
        "captures_business_owner_approval": False,
        "human_required_item_count": len(human_required_evidence),
        "machine_prepared_evidence": machine_prepared_evidence,
        "human_required_evidence": human_required_evidence,
        "promotion_blockers": promotion_blockers,
        "boundary": (
            "Receipt is an owner-review intake aid only; it does not approve the page, "
            "write governance records, close manual audit, approve the golden sample, "
            "or capture business-owner approval."
        ),
    }


def _owner_review_intake_checklist() -> dict[str, object]:
    artifacts = [
        _owner_review_artifact_status(artifact)
        for artifact in OWNER_REVIEW_ARTIFACTS
    ]
    missing_required = [
        str(artifact["key"])
        for artifact in artifacts
        if artifact["required_before_owner_review"] and not artifact["exists"]
    ]
    missing_freshness_guard = [
        str(artifact["key"])
        for artifact in artifacts
        if artifact["freshness_guard_present"] is False
    ]
    return {
        "checklist_kind": "owner_review_intake_artifact_checklist",
        "review_intake_ready": not missing_required and not missing_freshness_guard,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "artifacts": artifacts,
        "freshness_guarded_artifact_count": sum(
            1 for artifact in artifacts if artifact["freshness_guard_present"] is True
        ),
        "missing_freshness_guard_artifacts": missing_freshness_guard,
        "missing_required_artifacts": missing_required,
        "boundary": (
            "All required owner-review artifacts exist, but this checklist does not approve the page, "
            "capture signature, close manual audit, approve the golden sample, or make the route owner-signable."
        ),
    }


def _owner_review_artifact_status(artifact: dict[str, str]) -> dict[str, object]:
    path = ROOT / artifact["path"]
    exists = path.is_file()
    requires_freshness_guard = artifact.get("requires_freshness_guard") == "true"
    freshness_guard_present: bool | None
    if requires_freshness_guard:
        freshness_guard_present = exists and _has_freshness_markers(path, artifact)
    else:
        freshness_guard_present = None
    return {
        "key": artifact["key"],
        "path": artifact["path"],
        "exists": exists,
        "required_before_owner_review": True,
        "freshness_guard_present": freshness_guard_present,
    }


def _has_freshness_markers(path: Path, artifact: dict[str, str]) -> bool:
    marker_text = artifact.get(
        "freshness_markers",
        FRESHNESS_MARKERS_BY_ARTIFACT_KEY.get(artifact["key"], "## Packet Freshness Guard"),
    )
    markers = marker_text.splitlines()
    text = path.read_text(encoding="utf-8")
    return all(marker in text for marker in markers)


def _owner_decision_packet_bridge(owner_decision_packet: dict[str, Any]) -> dict[str, object]:
    formal_count = int(owner_decision_packet["decision_item_count"])
    next_review_count = int(owner_decision_packet["next_review_queue_scope"]["item_count"])
    evidence_scope = owner_decision_packet["evidence_scope"]
    missing_freshness_markers = _missing_freshness_markers(
        OWNER_DECISION_PACKET_OUTPUT,
        OWNER_DECISION_FRESHNESS_MARKERS,
    )
    return {
        "bridge_kind": "owner_decision_packet_bridge",
        "packet_path": OWNER_DECISION_PACKET_OUTPUT.relative_to(ROOT).as_posix(),
        "packet_exists": OWNER_DECISION_PACKET_OUTPUT.is_file(),
        "packet_freshness_status": (
            "valid"
            if OWNER_DECISION_PACKET_OUTPUT.is_file() and not missing_freshness_markers
            else "stale_or_missing"
        ),
        "missing_freshness_markers": missing_freshness_markers,
        "formal_decision_item_count": formal_count,
        "next_review_queue_item_count": next_review_count,
        "counts_next_review_as_decision": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": bool(
            evidence_scope["captures_golden_sample_approval"]
        ),
        "captures_closure_approval": bool(evidence_scope["captures_closure_approval"]),
        "certification_effect": str(evidence_scope["certification_effect"]),
        "required_owner_action": (
            f"Review {formal_count} formal decision items plus {next_review_count} "
            "next-review queue topics; the queue topics are intake follow-ups and do not "
            "capture decisions."
        ),
    }


def _missing_freshness_markers(path: Path, marker_text: str) -> list[str]:
    if not path.is_file():
        return marker_text.splitlines()
    text = path.read_text(encoding="utf-8")
    return [marker for marker in marker_text.splitlines() if marker not in text]


def _pre_signature_verification_rerun_receipt(
    *,
    approval: dict[str, Any],
    triage: dict[str, Any],
    readiness_gate: dict[str, str],
    golden_mismatch: bool,
    closure_checklist: dict[str, Any],
    owner_review_intake_checklist: dict[str, object],
) -> dict[str, object]:
    partial_units = int(closure_checklist["partial_count"])
    owner_decisions_pending = int(triage["decision_required_count"]) + int(
        triage["api_contract_required_count"]
    )
    still_blocking_after_rerun = [
        f"business_owner_approval_captured={str(approval['business_owner_approval_captured']).lower()}",
        f"golden_sample_approval_artifact_mismatch={str(golden_mismatch).lower()}",
        f"manual_closure_checklist_has_partial_units={partial_units}",
        f"owner_decisions_pending={owner_decisions_pending}",
    ]
    if not bool(owner_review_intake_checklist["review_intake_ready"]):
        still_blocking_after_rerun.append("owner_review_intake_ready=false")
    return {
        "receipt_kind": "pre_signature_verification_rerun_receipt",
        "packet_generator_reruns_gate": False,
        "latest_recorded_gate_status": str(readiness_gate["status"]),
        "approval_template_requires_rerun": True,
        "verification_commands_rerun_captured": (
            str(approval["approval_field_status"]["verification_commands_rerun"])
            == "valid"
        ),
        "pre_signature_required_commands": [
            "python scripts\\product_category_pnl_first_certification_packet.py",
            "python scripts\\product_category_pnl_owner_decision_packet.py",
            "python scripts\\check_product_category_pnl_business_owner_approval.py",
            str(readiness_gate["command"]),
            "python scripts\\check_product_category_pnl_business_owner_approval.py --require-captured",
        ],
        "current_recorded_evidence": {
            "static_readiness": str(readiness_gate["static_readiness"]),
            "live_smoke": str(readiness_gate["live_smoke"]),
            "mcp_contract_tests": str(readiness_gate["mcp_contract_tests"]),
            "backend_flow_mapping_tests": str(readiness_gate["backend_flow_mapping_tests"]),
            "frontend_tests": str(readiness_gate["frontend_tests"]),
            "browser_a11y_smoke": str(readiness_gate["browser_a11y_smoke"]),
            "frontend_typecheck": str(readiness_gate["frontend_typecheck"]),
            "frontend_debt_audit": str(readiness_gate["frontend_debt_audit"]),
            "frontend_production_build": str(readiness_gate["frontend_production_build"]),
        },
        "still_blocking_after_rerun": still_blocking_after_rerun,
        "boundary": (
            "Recorded gate evidence is useful intake evidence, but owner signature requires a fresh "
            "pre-signature rerun and still cannot bypass golden, manual-audit, owner decisions, or owner approval."
        ),
    }


def _reviewer_checklist(
    triage: dict[str, Any],
    *,
    owner_decision_packet: dict[str, Any],
) -> list[str]:
    formal_count = int(owner_decision_packet["decision_item_count"])
    next_review_count = int(owner_decision_packet["next_review_queue_scope"]["item_count"])
    return [
        "Confirm current UI/API payload matches MTR-PCP-001 through MTR-PCP-012 source-to-screen trace rows.",
        (
            "Review docs/pnl/product-category-pnl-owner-decision-packet.md for "
            f"the {triage['decision_required_count']} product decisions and "
            f"{triage['api_contract_required_count']} API/contract blockers."
        ),
        (
            "Review docs/pnl/product-category-pnl-owner-decision-packet.md for "
            f"{formal_count} formal decision items and {next_review_count} next-review "
            "queue topics; queue topics do not count as captured decisions."
        ),
        "Confirm reviewed boundary, first-certification, and owner-decision packet artifacts exist before marking template review fields yes.",
        "Resolve golden_sample_approval_artifact_mismatch before certification wording.",
        "Review closure checklist units that remain PARTIAL.",
        "Review liability fallback model-boundary evidence without synthetic production proof.",
        "Run live smoke/browser evidence review before signature.",
        "Complete and sign docs/pnl/product-category-pnl-business-owner-approval-template.md.",
    ]


def _owner_reviewer_receipt(reviewer_checklist: list[str]) -> dict[str, object]:
    items = [
        {
            "review_key": "source_to_screen_trace_review",
            "checklist_item": reviewer_checklist[0],
            "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#source-to-screen-trace",
            "approval_action_fields": ["ui_api_payload_review"],
            "current_status": "pending_owner_review",
            "blocking_condition": "ui_api_payload_review=pending",
        },
        {
            "review_key": "formal_decision_item_review",
            "checklist_item": reviewer_checklist[1],
            "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md#decision-items",
            "approval_action_fields": ["reviewed_owner_decision_packet"],
            "current_status": "pending_owner_review",
            "blocking_condition": "reviewed_owner_decision_packet=pending",
        },
        {
            "review_key": "next_review_queue_acknowledgement",
            "checklist_item": reviewer_checklist[2],
            "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md#next-review-queue",
            "approval_action_fields": ["owner_decision_next_review_queue_acknowledgement"],
            "current_status": "pending_owner_review",
            "blocking_condition": "owner_decision_next_review_queue_acknowledgement=pending",
        },
        {
            "review_key": "artifact_freshness_review",
            "checklist_item": reviewer_checklist[3],
            "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#owner-review-intake-checklist",
            "approval_action_fields": [
                "reviewed_boundary_packet",
                "reviewed_first_certification_packet",
                "reviewed_owner_decision_packet",
                "governance_record_review",
            ],
            "current_status": "pending_owner_review",
            "blocking_condition": "governance_record_review=pending",
        },
        {
            "review_key": "golden_sample_reconciliation",
            "checklist_item": reviewer_checklist[4],
            "evidence_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
            "approval_action_fields": ["golden_sample_artifact_reconciliation"],
            "current_status": "pending_owner_review",
            "blocking_condition": "golden_sample_artifact_reconciliation=pending",
        },
        {
            "review_key": "manual_closure_checklist_review",
            "checklist_item": reviewer_checklist[5],
            "evidence_path": "docs/pnl/product-category-closure-checklist.md",
            "approval_action_fields": ["closure_checklist_review"],
            "current_status": "pending_owner_review",
            "blocking_condition": "closure_checklist_review=pending",
        },
        {
            "review_key": "fallback_liability_boundary_review",
            "checklist_item": reviewer_checklist[6],
            "evidence_path": "docs/pnl/product-category-page-truth-contract.md",
            "approval_action_fields": ["fallback_liability_branch_boundary_review"],
            "current_status": "pending_owner_review",
            "blocking_condition": "fallback_liability_branch_boundary_review=pending",
        },
        {
            "review_key": "live_smoke_evidence_review",
            "checklist_item": reviewer_checklist[7],
            "evidence_path": "latest_readiness_gate_evidence",
            "approval_action_fields": [
                "live_smoke_evidence_review",
                "verification_commands_rerun",
            ],
            "current_status": "pending_owner_review",
            "blocking_condition": "live_smoke_evidence_review=pending; verification_commands_rerun=pending",
        },
        {
            "review_key": "business_owner_signature_completion",
            "checklist_item": reviewer_checklist[8],
            "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
            "approval_action_fields": [
                "business_owner_name",
                "business_owner_role",
                "approval_decision",
                "approval_date",
                "business_owner_signature",
                "evidence_pending_boundary_acceptance",
            ],
            "current_status": "owner_signature_missing",
            "blocking_condition": "business_owner_approval_captured=false",
        },
    ]
    return {
        "receipt_kind": "owner_reviewer_checklist_receipt",
        "item_count": len(items),
        "signed_item_count": 0,
        "pending_item_count": len(items),
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "items": items,
        "boundary": (
            "Reviewer receipt structures owner-review work for signature intake only; it does not "
            "capture business-owner approval, close manual audit, approve golden samples, or certify the route."
        ),
    }


def _owner_reviewer_receipt_field_coverage(
    owner_reviewer_receipt: dict[str, object],
    approval_field_status: dict[str, object],
) -> dict[str, object]:
    referenced_fields = sorted(
        {
            str(field)
            for item in owner_reviewer_receipt["items"]
            for field in item["approval_action_fields"]
        }
    )
    known_fields = set(approval_field_status)
    missing_fields = [
        field for field in referenced_fields if field not in known_fields
    ]
    return {
        "coverage_kind": "owner_reviewer_receipt_approval_field_coverage",
        "receipt_item_count": int(owner_reviewer_receipt["item_count"]),
        "referenced_approval_field_count": len(referenced_fields),
        "all_referenced_fields_known": not missing_fields,
        "missing_approval_action_fields": missing_fields,
        "referenced_approval_fields": referenced_fields,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "boundary": (
            "Coverage only proves receipt fields are known to the approval checker; it does not "
            "mark any field reviewed, signed, or certification-ready."
        ),
    }


def _business_owner_action_signoff_matrix(
    owner_action_items: list[dict[str, str]],
) -> dict[str, object]:
    items = [_business_owner_action_signoff_item(item) for item in owner_action_items]
    group_counts: dict[str, int] = {}
    for item in items:
        group = str(item["signoff_group"])
        group_counts[group] = group_counts.get(group, 0) + 1
    signed_count = sum(1 for item in items if item["current_status"] == "valid")
    pending_or_missing_count = len(items) - signed_count
    missing_or_invalid_count = sum(
        1 for item in items if _action_status_is_missing_or_invalid(str(item["current_status"]))
    )
    pending_review_count = pending_or_missing_count - missing_or_invalid_count
    signed_group_counts = _signoff_item_group_counts(
        [item for item in items if item["current_status"] == "valid"]
    )
    pending_or_missing_group_counts = _signoff_item_group_counts(
        [item for item in items if item["current_status"] != "valid"]
    )
    return {
        "matrix_kind": "business_owner_action_signoff_matrix",
        "action_item_count": len(items),
        "signed_item_count": signed_count,
        "pending_or_missing_item_count": pending_or_missing_count,
        "missing_or_invalid_item_count": missing_or_invalid_count,
        "pending_review_item_count": pending_review_count,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "items": items,
        "group_counts": dict(sorted(group_counts.items())),
        "signed_group_counts": signed_group_counts,
        "pending_or_missing_group_counts": pending_or_missing_group_counts,
        "boundary": (
            "Action signoff matrix prepares owner signature intake only. Only current_status=valid counts as signed; "
            "all other statuses still block business-owner approval capture and business-contract certification."
        ),
    }


def _action_status_is_missing_or_invalid(status: str) -> bool:
    return status in {"missing", "invalid"} or status.startswith("artifact_") or status.startswith("stale_")


def _signoff_item_group_counts(
    items: list[dict[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        group = str(item["signoff_group"])
        counts[group] = counts.get(group, 0) + 1
    return dict(sorted(counts.items()))


def _business_owner_action_signoff_item(item: dict[str, str]) -> dict[str, object]:
    blocker = item["blocker"]
    metadata = ACTION_SIGNOFF_METADATA[blocker]
    return {
        "blocker": blocker,
        "signoff_group": metadata["signoff_group"],
        "required_owner_type": "business_owner",
        "template_field": _display_template_field(str(item["template_field"])),
        "required_value": item["required_value"],
        "current_status": item["current_status"],
        "evidence_path": metadata["evidence_path"],
        "pre_signature_action": metadata["pre_signature_action"],
        "blocks_certification": True,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    rows = "\n".join(
        (
            f"| `{row['metric_id']}` | {row['api_field']} | {row['client_model_path']} | "
            f"`{row['component_anchor']}` | `{row['formatter']}` | `{row['display_unit']}` | "
            f"{row['status_boundary']} |"
        )
        for row in packet["metric_trace_rows"]
    )
    action_items = "\n".join(
        (
            f"- {_display_template_field(str(item['template_field']))}: `{item['required_value']}` "
            f"(`{item['current_status']}`)"
        )
        for item in packet["owner_action_items"]
    )
    signoff_matrix = packet["business_owner_action_signoff_matrix"]
    owner_action_status_scope = packet["owner_action_status_scope"]
    pre_signature_scope = packet["owner_pre_signature_blocker_scope"]
    signoff_rows = "\n".join(
        (
            f"| `{item['blocker']}` | `{item['signoff_group']}` | `{item['required_owner_type']}` | "
            f"{item['template_field']} | `{item['required_value']}` | `{item['current_status']}` | "
            f"`{item['evidence_path']}` | {item['pre_signature_action']} | "
            f"`{str(item['blocks_certification']).lower()}` |"
        )
        for item in signoff_matrix["items"]
    )
    signoff_group_counts = ", ".join(
        f"`{group}={count}`"
        for group, count in signoff_matrix["group_counts"].items()
    )
    signed_group_counts = ", ".join(
        f"`{group}={count}`"
        for group, count in signoff_matrix["signed_group_counts"].items()
    ) or "`none=0`"
    pending_or_missing_group_counts = ", ".join(
        f"`{group}={count}`"
        for group, count in signoff_matrix["pending_or_missing_group_counts"].items()
    )
    pre_signature_group_counts = ", ".join(
        f"`{group}={count}`"
        for group, count in pre_signature_scope["signoff_group_counts"].items()
    )
    pre_signature_signed_group_counts = ", ".join(
        f"`{group}={count}`"
        for group, count in pre_signature_scope["signed_group_counts"].items()
    ) or "`none=0`"
    pre_signature_unsigned_group_counts = ", ".join(
        f"`{group}={count}`"
        for group, count in pre_signature_scope["unsigned_group_counts"].items()
    )
    pre_signature_blocker_rows = "\n".join(
        (
            f"| `{item['blocker']}` | `{item['signoff_group']}` | "
            f"{item['template_field']} | `{item['required_value']}` | "
            f"`{item['current_status']}` | "
            f"`{str(item['blocks_owner_signature']).lower()}` | "
            f"`{item['certification_effect']}` |"
        )
        for item in pre_signature_scope["checklist_items"]
    )
    gate_rows = "\n".join(
        (
            f"| `{gate['gate']}` | `{gate['status']}` | `{gate['evidence']}` | "
            f"`{str(gate['can_be_closed_by_code']).lower()}` | {gate['required_owner_action']} |"
        )
        for gate in packet["owner_closure_gate_matrix"]
    )
    checklist = "\n".join(f"- {item}" for item in packet["reviewer_checklist"])
    reviewer_receipt = packet["owner_reviewer_receipt"]
    reviewer_receipt_field_coverage = packet["owner_reviewer_receipt_field_coverage"]
    reviewer_receipt_rows = "\n".join(
        (
            f"| `{item['review_key']}` | {item['checklist_item']} | `{item['evidence_path']}` | "
            f"{_inline_code_list(item['approval_action_fields'])} | "
            f"`{item['current_status']}` | `{item['blocking_condition']}` |"
        )
        for item in reviewer_receipt["items"]
    )
    referenced_approval_fields = ", ".join(
        f"`{item}`"
        for item in reviewer_receipt_field_coverage["referenced_approval_fields"]
    )
    missing_approval_action_fields = "\n".join(
        f"- `{item}`"
        for item in reviewer_receipt_field_coverage["missing_approval_action_fields"]
    ) or "- `none`"
    anchors = "\n".join(
        f"- {label}: `{path}`"
        for label, path in packet["evidence_anchors"].items()
    )
    receipt = packet["owner_readiness_receipt"]
    intake_checklist = packet["owner_review_intake_checklist"]
    checker_freshness = packet["approval_checker_generated_artifact_freshness"]
    checker_freshness_scope = packet[
        "approval_checker_generated_artifact_freshness_scope"
    ]
    consistency = packet["certification_packet_consistency"]
    owner_decision_bridge = packet["owner_decision_packet_bridge"]
    rerun_receipt = packet["pre_signature_verification_rerun_receipt"]
    machine_prepared_evidence = "\n".join(
        f"- `{item}`" for item in receipt["machine_prepared_evidence"]
    )
    human_required_evidence = "\n".join(
        f"- `{item}`" for item in receipt["human_required_evidence"]
    )
    promotion_blockers = "\n".join(
        f"- `{item}`" for item in receipt["promotion_blockers"]
    )
    intake_artifact_rows = "\n".join(
        (
            f"| `{artifact['key']}` | `{artifact['path']}` | "
            f"`{str(artifact['exists']).lower()}` | "
            f"`{str(artifact['required_before_owner_review']).lower()}` | "
            f"`{_optional_bool_label(artifact['freshness_guard_present'])}` |"
        )
        for artifact in intake_checklist["artifacts"]
    )
    missing_freshness_guard_artifacts = "\n".join(
        f"- `{item}`" for item in intake_checklist["missing_freshness_guard_artifacts"]
    ) or "- `none`"
    missing_required_artifacts = "\n".join(
        f"- `{item}`" for item in intake_checklist["missing_required_artifacts"]
    ) or "- `none`"
    checker_freshness_rows = "\n".join(
        (
            f"| `{key}` | `{artifact['artifact_path']}` | "
            f"`{str(artifact['exists']).lower()}` | "
            f"`freshness_status={artifact['freshness_status']}` | "
            f"`missing_markers={len(artifact['missing_markers'])}` |"
        )
        for key, artifact in checker_freshness.items()
    )
    consistency_missing_markers = "\n".join(
        f"- `{item}`" for item in consistency["missing_markers"]
    ) or "- `none`"
    pre_signature_commands = "\n".join(
        f"- `{item}`" for item in rerun_receipt["pre_signature_required_commands"]
    )
    current_recorded_evidence = "\n".join(
        f"- {label}: `{value}`"
        for label, value in rerun_receipt["current_recorded_evidence"].items()
    )
    still_blocking_after_rerun = "\n".join(
        f"- `{item}`" for item in rerun_receipt["still_blocking_after_rerun"]
    )
    triage = packet["closure_blocker_triage"]
    readiness_gate = packet["latest_readiness_gate_evidence"]
    return f"""# Product-Category PnL First Certification Packet

Page ID: `{packet['page_id']}`
Page slug: `{packet['page_slug']}`
Primary API: `{packet['primary_api']}`
Business contract status: `{packet['business_contract_status']}`
Business contract certified: `{str(packet['business_contract_certified']).lower()}`
Formal use allowed: `formal_use_allowed={str(packet['formal_use_allowed']).lower()}`
Closure approved: `closure_approved={str(packet['closure_approved']).lower()}`
Business owner approval captured: `{str(packet['business_owner_approval_captured']).lower()}`
Handoff status: `{packet['handoff_status']}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, or grant final certification.

## Packet Freshness Guard

- `packet_generator=script-owned`
- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`
- Boundary: Manual edits to this packet must be followed by rerunning the generator.

## Current Certification Blockers

- `golden_sample_approval_artifact_status={packet['golden_sample_approval_artifact_status']}`
- `golden_sample_approval_artifact_mismatch={str(packet['golden_sample_approval_artifact_mismatch']).lower()}`
- `approval_action_item_count={packet['approval_action_item_count']}`
- `business_owner_approval_captured={str(packet['business_owner_approval_captured']).lower()}`
- `closure_blocker_triage.blocker_count={triage['blocker_count']}`

## Latest Readiness/Live Gate Evidence

- Command: `{readiness_gate['command']}`
- Evidence basis: `{readiness_gate['evidence_basis']}`
- Packet generator reruns gate: `{readiness_gate['packet_generator_reruns_gate']}`
- Status: `{readiness_gate['status']}`
- Static readiness: `{readiness_gate['static_readiness']}`
- Live smoke: `{readiness_gate['live_smoke']}`
- MCP contract tests: `{readiness_gate['mcp_contract_tests']}`
- Product-category backend flow/mapping tests: `{readiness_gate['backend_flow_mapping_tests']}`
- Product-category frontend tests: `{readiness_gate['frontend_tests']}`
- Browser a11y smoke: `{readiness_gate['browser_a11y_smoke']}`
- Frontend typecheck: `{readiness_gate['frontend_typecheck']}`
- Frontend debt audit: `{readiness_gate['frontend_debt_audit']}`
- Frontend production build: `{readiness_gate['frontend_production_build']}`
- Golden boundary status: `{readiness_gate['golden_boundary_status']}`
- Golden artifact status: `{readiness_gate['golden_artifact_status']}`
- Golden artifact approved: `{str(readiness_gate['golden_artifact_approved']).lower()}`
- Golden artifact mismatch: `{str(readiness_gate['golden_sample_approval_artifact_mismatch']).lower()}`
- Boundary: {readiness_gate['certification_boundary']}
- Rerun boundary: {readiness_gate['rerun_boundary']}

## Closure Blocker Triage

- Artifact: `{triage['artifact_path']}`
- Machine readable: `{str(triage['machine_readable']).lower()}`
- Class 1 product decisions: `{triage['decision_required_count']}`
- Class 2 API/contract blockers: `{triage['api_contract_required_count']}`
- Class 4 evidence/test/documentation blockers: `{triage['class_counts']['4']}`
- Class 5 out-of-scope blockers: `{triage['out_of_scope_count']}`
- Cursor-safe blockers: `{triage['cursor_safe_counts']['yes']}`
- Partially cursor-safe blockers: `{triage['cursor_safe_counts']['partially']}`
- Partially complete blockers: `{triage['cursor_safe_counts']['partially_complete']}`
- Non-cursor-safe blockers: `{triage['cursor_safe_counts']['no']}`

## Owner Closure Gate Matrix

| Gate | Current status | Evidence | Can be closed by code | Required owner action |
| --- | --- | --- | --- | --- |
{gate_rows}

## Owner Readiness Receipt

- Receipt kind: `{receipt['receipt_kind']}`
- `owner_signable={str(receipt['owner_signable']).lower()}`
- `captures_business_owner_approval={str(receipt['captures_business_owner_approval']).lower()}`
- `machine_evidence_ready={str(receipt['machine_evidence_ready']).lower()}`
- `business_decisions_ready={str(receipt['business_decisions_ready']).lower()}`
- `golden_sample_ready={str(receipt['golden_sample_ready']).lower()}`
- `manual_audit_ready={str(receipt['manual_audit_ready']).lower()}`
- `business_owner_signature_ready={str(receipt['business_owner_signature_ready']).lower()}`
- `can_promote_certification={str(receipt['can_promote_certification']).lower()}`
- `human_required_item_count={receipt['human_required_item_count']}`
- Boundary: {receipt['boundary']}

Machine-prepared evidence:

{machine_prepared_evidence}

Human-required evidence:

{human_required_evidence}

Promotion blockers:

{promotion_blockers}

## Owner Review Intake Checklist

- Checklist kind: `{intake_checklist['checklist_kind']}`
- `review_intake_ready={str(intake_checklist['review_intake_ready']).lower()}`
- `owner_signable={str(intake_checklist['owner_signable']).lower()}`
- `captures_business_owner_approval={str(intake_checklist['captures_business_owner_approval']).lower()}`
- `freshness_guarded_artifact_count={intake_checklist['freshness_guarded_artifact_count']}`
- `missing_freshness_guard_artifacts={len(intake_checklist['missing_freshness_guard_artifacts'])}`
- `missing_required_artifacts={len(intake_checklist['missing_required_artifacts'])}`
- Boundary: {intake_checklist['boundary']}

| Artifact | Path | Exists | Required before owner review | Freshness guard present |
| --- | --- | --- | --- | --- |
{intake_artifact_rows}

Missing freshness guard artifacts:

{missing_freshness_guard_artifacts}

Missing required artifacts:

{missing_required_artifacts}

## Approval Checker Generated Artifact Freshness

| Artifact | Path | Exists | Freshness status | Missing markers |
| --- | --- | --- | --- | ---: |
{checker_freshness_rows}

- Scope kind: `{checker_freshness_scope['scope_kind']}`
- `artifact_count={checker_freshness_scope['artifact_count']}`
- `valid_artifact_count={checker_freshness_scope['valid_artifact_count']}`
- `stale_or_missing_artifact_count={checker_freshness_scope['stale_or_missing_artifact_count']}`
- `freshness_check_effect={checker_freshness_scope['freshness_check_effect']}`
- `captures_business_owner_approval={str(checker_freshness_scope['captures_business_owner_approval']).lower()}`
- `captures_product_or_api_decisions={str(checker_freshness_scope['captures_product_or_api_decisions']).lower()}`
- `captures_golden_sample_approval={str(checker_freshness_scope['captures_golden_sample_approval']).lower()}`
- `captures_closure_approval={str(checker_freshness_scope['captures_closure_approval']).lower()}`
- `writes_governance_records={str(checker_freshness_scope['writes_governance_records']).lower()}`
- `certification_effect={checker_freshness_scope['certification_effect']}`
- Boundary: {checker_freshness_scope['boundary']}

## Certification Packet Consistency

- Consistency kind: `{consistency['consistency_kind']}`
- `consistency_status={consistency['status']}`
- Template path: `{consistency['template_path']}`
- First-certification packet path: `{consistency['first_certification_packet_path']}`
- Owner decision packet path: `{consistency['owner_decision_packet_path']}`
- `formal_decision_item_count={consistency['formal_decision_item_count']}`
- `next_review_queue_item_count={consistency['next_review_queue_item_count']}`
- `approval_action_item_count={consistency['approval_action_item_count']}`
- `business_owner_action_signoff_item_count={consistency['business_owner_action_signoff_item_count']}`
- `business_owner_action_signed_item_count={consistency['business_owner_action_signed_item_count']}`
- `business_owner_action_pending_or_missing_item_count={consistency['business_owner_action_pending_or_missing_item_count']}`
- `business_owner_action_missing_or_invalid_item_count={consistency['business_owner_action_missing_or_invalid_item_count']}`
- `business_owner_action_pending_review_item_count={consistency['business_owner_action_pending_review_item_count']}`
- `approves_metric_or_page={str(consistency['approves_metric_or_page']).lower()}`
- `owner_signable={str(consistency['owner_signable']).lower()}`
- `captures_business_owner_approval={str(consistency['captures_business_owner_approval']).lower()}`
- `captures_business_owner_signature={str(consistency['captures_business_owner_signature']).lower()}`
- `captures_product_or_api_decisions={str(consistency['captures_product_or_api_decisions']).lower()}`
- `captures_golden_sample_approval={str(consistency['captures_golden_sample_approval']).lower()}`
- `captures_closure_approval={str(consistency['captures_closure_approval']).lower()}`
- `writes_governance_records={str(consistency['writes_governance_records']).lower()}`
- `can_promote_certification={str(consistency['can_promote_certification']).lower()}`
- `verification_commands_rerun_captured={str(consistency['verification_commands_rerun_captured']).lower()}`
- `certification_effect={consistency['certification_effect']}`
- Boundary: {consistency['boundary']}

Missing consistency markers:

{consistency_missing_markers}

## Owner Decision Packet Bridge

- Bridge kind: `{owner_decision_bridge['bridge_kind']}`
- Packet path: `{owner_decision_bridge['packet_path']}`
- `packet_exists={str(owner_decision_bridge['packet_exists']).lower()}`
- `packet_freshness_status={owner_decision_bridge['packet_freshness_status']}`
- `missing_freshness_markers={len(owner_decision_bridge['missing_freshness_markers'])}`
- `formal_decision_item_count={owner_decision_bridge['formal_decision_item_count']}`
- `next_review_queue_item_count={owner_decision_bridge['next_review_queue_item_count']}`
- `counts_next_review_as_decision={str(owner_decision_bridge['counts_next_review_as_decision']).lower()}`
- `captures_product_or_api_decisions={str(owner_decision_bridge['captures_product_or_api_decisions']).lower()}`
- `captures_golden_sample_approval={str(owner_decision_bridge['captures_golden_sample_approval']).lower()}`
- `captures_closure_approval={str(owner_decision_bridge['captures_closure_approval']).lower()}`
- `certification_effect={owner_decision_bridge['certification_effect']}`
- Required owner action: {owner_decision_bridge['required_owner_action']}

## Pre-Signature Verification Rerun Receipt

- Receipt kind: `{rerun_receipt['receipt_kind']}`
- `packet_generator_reruns_gate={str(rerun_receipt['packet_generator_reruns_gate']).lower()}`
- `latest_recorded_gate_status={rerun_receipt['latest_recorded_gate_status']}`
- `approval_template_requires_rerun={str(rerun_receipt['approval_template_requires_rerun']).lower()}`
- `verification_commands_rerun_captured={str(rerun_receipt['verification_commands_rerun_captured']).lower()}`
- Boundary: {rerun_receipt['boundary']}

Pre-signature required commands:

{pre_signature_commands}

Current recorded evidence:

{current_recorded_evidence}

Still blocking after rerun:

{still_blocking_after_rerun}

## Source-To-Screen Trace

| Metric | API field | Client/model path | Component anchor | Formatter | Unit | Boundary |
| --- | --- | --- | --- | --- | --- | --- |
{rows}

## Evidence Anchors

{anchors}

## Reviewer Checklist

{checklist}

## Owner Reviewer Receipt

- Receipt kind: `{reviewer_receipt['receipt_kind']}`
- `owner_reviewer_receipt_item_count={reviewer_receipt['item_count']}`
- `signed_item_count={reviewer_receipt['signed_item_count']}`
- `pending_item_count={reviewer_receipt['pending_item_count']}`
- `owner_signable={str(reviewer_receipt['owner_signable']).lower()}`
- `captures_business_owner_approval={str(reviewer_receipt['captures_business_owner_approval']).lower()}`
- `can_promote_certification={str(reviewer_receipt['can_promote_certification']).lower()}`
- Boundary: {reviewer_receipt['boundary']}

| Review key | Checklist item | Evidence path | Approval action fields | Current status | Blocking condition |
| --- | --- | --- | --- | --- | --- |
{reviewer_receipt_rows}

## Owner Reviewer Receipt Field Coverage

- Coverage kind: `{reviewer_receipt_field_coverage['coverage_kind']}`
- `receipt_item_count={reviewer_receipt_field_coverage['receipt_item_count']}`
- `referenced_approval_field_count={reviewer_receipt_field_coverage['referenced_approval_field_count']}`
- `all_referenced_fields_known={str(reviewer_receipt_field_coverage['all_referenced_fields_known']).lower()}`
- `owner_signable={str(reviewer_receipt_field_coverage['owner_signable']).lower()}`
- `captures_business_owner_approval={str(reviewer_receipt_field_coverage['captures_business_owner_approval']).lower()}`
- Referenced approval fields: {referenced_approval_fields}
- Boundary: {reviewer_receipt_field_coverage['boundary']}

Missing approval action fields:

{missing_approval_action_fields}

## Business Owner Action Items

{action_items}

## Business Owner Action Signoff Matrix

- Matrix kind: `{signoff_matrix['matrix_kind']}`
- `business_owner_action_signoff_item_count={signoff_matrix['action_item_count']}`
- `signed_item_count={signoff_matrix['signed_item_count']}`
- `pending_or_missing_item_count={signoff_matrix['pending_or_missing_item_count']}`
- `missing_or_invalid_item_count={signoff_matrix['missing_or_invalid_item_count']}`
- `pending_review_item_count={signoff_matrix['pending_review_item_count']}`
- `owner_signable={str(signoff_matrix['owner_signable']).lower()}`
- `captures_business_owner_approval={str(signoff_matrix['captures_business_owner_approval']).lower()}`
- `can_promote_certification={str(signoff_matrix['can_promote_certification']).lower()}`
- Group counts: {signoff_group_counts}
- Signed group counts: {signed_group_counts}
- Pending or missing group counts: {pending_or_missing_group_counts}
- Boundary: {signoff_matrix['boundary']}

| Blocker | Signoff group | Owner type | Template field | Required value | Current status | Evidence path | Pre-signature action | Blocks certification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{signoff_rows}

## Owner Action Status Scope

- Scope kind: `{owner_action_status_scope['scope_kind']}`
- `missing_or_invalid_item_count={owner_action_status_scope['missing_or_invalid_item_count']}`
- `pending_review_item_count={owner_action_status_scope['pending_review_item_count']}`
- `owner_signable={str(owner_action_status_scope['owner_signable']).lower()}`
- `captures_business_owner_approval={str(owner_action_status_scope['captures_business_owner_approval']).lower()}`
- `captures_product_or_api_decisions={str(owner_action_status_scope['captures_product_or_api_decisions']).lower()}`
- `can_promote_certification={str(owner_action_status_scope['can_promote_certification']).lower()}`
- `certification_effect={owner_action_status_scope['certification_effect']}`
- Boundary: {owner_action_status_scope['boundary']}

## Owner Pre-Signature Blocker Scope

- Scope kind: `{pre_signature_scope['scope_kind']}`
- `remaining_blocker_count={pre_signature_scope['remaining_blocker_count']}`
- `approval_action_item_count={pre_signature_scope['approval_action_item_count']}`
- `signed_item_count={pre_signature_scope['signed_item_count']}`
- `unsigned_item_count={pre_signature_scope['unsigned_item_count']}`
- `missing_or_invalid_item_count={pre_signature_scope['missing_or_invalid_item_count']}`
- `pending_review_item_count={pre_signature_scope['pending_review_item_count']}`
- `owner_signable={str(pre_signature_scope['owner_signable']).lower()}`
- `captures_business_owner_approval={str(pre_signature_scope['captures_business_owner_approval']).lower()}`
- `captures_product_or_api_decisions={str(pre_signature_scope['captures_product_or_api_decisions']).lower()}`
- `can_promote_certification={str(pre_signature_scope['can_promote_certification']).lower()}`
- `certification_effect={pre_signature_scope['certification_effect']}`
- Group counts: {pre_signature_group_counts}
- Signed group counts: {pre_signature_signed_group_counts}
- Unsigned group counts: {pre_signature_unsigned_group_counts}
- Boundary: {pre_signature_scope['boundary']}

| Blocker | Signoff group | Template field | Required value | Current status | Blocks owner signature | Certification effect |
| --- | --- | --- | --- | --- | --- | --- |
{pre_signature_blocker_rows}

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `captures_product_or_api_decisions=false`
- `certification_effect=none`
"""


def _display_template_field(template_field: str) -> str:
    return template_field.removeprefix("- ").strip()


def _optional_bool_label(value: object) -> str:
    if value is None:
        return "n/a"
    return str(bool(value)).lower()


def _inline_code_list(items: object) -> str:
    return ", ".join(f"`{item}`" for item in items)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the product-category-pnl first-certification owner packet.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown packet path to write.",
    )
    args = parser.parse_args(argv)

    packet = build_packet()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(packet), encoding="utf-8")
    payload = {
        "packet_kind": packet["packet_kind"],
        "packet_path": str(output_path),
        "handoff_status": packet["handoff_status"],
        "business_contract_certified": packet["business_contract_certified"],
        "business_owner_approval_captured": packet["business_owner_approval_captured"],
        "closure_approved": packet["closure_approved"],
        "approval_action_item_count": packet["approval_action_item_count"],
        "owner_readiness_receipt": {
            "owner_signable": packet["owner_readiness_receipt"]["owner_signable"],
            "captures_business_owner_approval": packet["owner_readiness_receipt"][
                "captures_business_owner_approval"
            ],
            "can_promote_certification": packet["owner_readiness_receipt"][
                "can_promote_certification"
            ],
            "human_required_item_count": packet["owner_readiness_receipt"][
                "human_required_item_count"
            ],
            "promotion_blockers": packet["owner_readiness_receipt"]["promotion_blockers"],
        },
        "owner_decision_packet_bridge": {
            "formal_decision_item_count": packet["owner_decision_packet_bridge"][
                "formal_decision_item_count"
            ],
            "next_review_queue_item_count": packet["owner_decision_packet_bridge"][
                "next_review_queue_item_count"
            ],
            "counts_next_review_as_decision": packet["owner_decision_packet_bridge"][
                "counts_next_review_as_decision"
            ],
            "captures_product_or_api_decisions": packet["owner_decision_packet_bridge"][
                "captures_product_or_api_decisions"
            ],
            "captures_golden_sample_approval": packet["owner_decision_packet_bridge"][
                "captures_golden_sample_approval"
            ],
            "captures_closure_approval": packet["owner_decision_packet_bridge"][
                "captures_closure_approval"
            ],
            "certification_effect": packet["owner_decision_packet_bridge"][
                "certification_effect"
            ],
        },
        "pre_signature_verification_rerun_receipt": {
            "packet_generator_reruns_gate": packet["pre_signature_verification_rerun_receipt"][
                "packet_generator_reruns_gate"
            ],
            "approval_template_requires_rerun": packet[
                "pre_signature_verification_rerun_receipt"
            ]["approval_template_requires_rerun"],
            "verification_commands_rerun_captured": packet[
                "pre_signature_verification_rerun_receipt"
            ]["verification_commands_rerun_captured"],
            "business_owner_approval_captured": packet["business_owner_approval_captured"],
            "closure_approved": packet["closure_approved"],
            "captures_business_owner_approval": False,
            "certification_effect": "none",
            "still_blocking_after_rerun": packet["pre_signature_verification_rerun_receipt"][
                "still_blocking_after_rerun"
            ],
        },
        "latest_readiness_gate_evidence": {
            "command": packet["latest_readiness_gate_evidence"]["command"],
            "evidence_basis": packet["latest_readiness_gate_evidence"]["evidence_basis"],
            "packet_generator_reruns_gate": packet["latest_readiness_gate_evidence"][
                "packet_generator_reruns_gate"
            ],
            "status": packet["latest_readiness_gate_evidence"]["status"],
            "static_readiness": packet["latest_readiness_gate_evidence"][
                "static_readiness"
            ],
            "live_smoke": packet["latest_readiness_gate_evidence"]["live_smoke"],
            "mcp_contract_tests": packet["latest_readiness_gate_evidence"][
                "mcp_contract_tests"
            ],
            "backend_flow_mapping_tests": packet["latest_readiness_gate_evidence"][
                "backend_flow_mapping_tests"
            ],
            "frontend_tests": packet["latest_readiness_gate_evidence"]["frontend_tests"],
            "browser_a11y_smoke": packet["latest_readiness_gate_evidence"][
                "browser_a11y_smoke"
            ],
            "frontend_typecheck": packet["latest_readiness_gate_evidence"][
                "frontend_typecheck"
            ],
            "frontend_debt_audit": packet["latest_readiness_gate_evidence"][
                "frontend_debt_audit"
            ],
            "frontend_production_build": packet["latest_readiness_gate_evidence"][
                "frontend_production_build"
            ],
            "golden_boundary_status": packet["latest_readiness_gate_evidence"][
                "golden_boundary_status"
            ],
            "golden_artifact_status": packet["latest_readiness_gate_evidence"][
                "golden_artifact_status"
            ],
            "golden_artifact_approved": packet["latest_readiness_gate_evidence"][
                "golden_artifact_approved"
            ],
            "golden_sample_approval_artifact_mismatch": packet[
                "latest_readiness_gate_evidence"
            ]["golden_sample_approval_artifact_mismatch"],
            "verification_commands_rerun_captured": packet[
                "pre_signature_verification_rerun_receipt"
            ]["verification_commands_rerun_captured"],
            "business_owner_approval_captured": packet["business_owner_approval_captured"],
            "certification_effect": "none",
        },
        "owner_reviewer_receipt": {
            "owner_reviewer_receipt_item_count": packet["owner_reviewer_receipt"][
                "item_count"
            ],
            "signed_item_count": packet["owner_reviewer_receipt"]["signed_item_count"],
            "pending_item_count": packet["owner_reviewer_receipt"]["pending_item_count"],
            "owner_signable": packet["owner_reviewer_receipt"]["owner_signable"],
            "captures_business_owner_approval": packet["owner_reviewer_receipt"][
                "captures_business_owner_approval"
            ],
            "can_promote_certification": packet["owner_reviewer_receipt"][
                "can_promote_certification"
            ],
        },
        "owner_reviewer_receipt_field_coverage": {
            "referenced_approval_field_count": packet[
                "owner_reviewer_receipt_field_coverage"
            ]["referenced_approval_field_count"],
            "all_referenced_fields_known": packet[
                "owner_reviewer_receipt_field_coverage"
            ]["all_referenced_fields_known"],
            "missing_approval_action_field_count": len(
                packet["owner_reviewer_receipt_field_coverage"][
                    "missing_approval_action_fields"
                ]
            ),
            "owner_signable": packet["owner_reviewer_receipt_field_coverage"][
                "owner_signable"
            ],
            "captures_business_owner_approval": packet[
                "owner_reviewer_receipt_field_coverage"
            ]["captures_business_owner_approval"],
        },
        "business_owner_action_signoff_matrix": {
            "signed_item_count": packet["business_owner_action_signoff_matrix"][
                "signed_item_count"
            ],
            "pending_or_missing_item_count": packet["business_owner_action_signoff_matrix"][
                "pending_or_missing_item_count"
            ],
            "missing_or_invalid_item_count": packet["business_owner_action_signoff_matrix"][
                "missing_or_invalid_item_count"
            ],
            "pending_review_item_count": packet["business_owner_action_signoff_matrix"][
                "pending_review_item_count"
            ],
            "group_counts": packet["business_owner_action_signoff_matrix"][
                "group_counts"
            ],
            "signed_group_counts": packet["business_owner_action_signoff_matrix"][
                "signed_group_counts"
            ],
            "pending_or_missing_group_counts": packet[
                "business_owner_action_signoff_matrix"
            ]["pending_or_missing_group_counts"],
            "owner_signable": packet["business_owner_action_signoff_matrix"]["owner_signable"],
            "captures_business_owner_approval": packet["business_owner_action_signoff_matrix"][
                "captures_business_owner_approval"
            ],
            "can_promote_certification": packet["business_owner_action_signoff_matrix"][
                "can_promote_certification"
            ],
        },
        "owner_action_status_scope": {
            "missing_or_invalid_item_count": packet["owner_action_status_scope"][
                "missing_or_invalid_item_count"
            ],
            "pending_review_item_count": packet["owner_action_status_scope"][
                "pending_review_item_count"
            ],
            "captures_business_owner_approval": packet["owner_action_status_scope"][
                "captures_business_owner_approval"
            ],
            "captures_product_or_api_decisions": packet["owner_action_status_scope"][
                "captures_product_or_api_decisions"
            ],
            "can_promote_certification": packet["owner_action_status_scope"][
                "can_promote_certification"
            ],
            "certification_effect": packet["owner_action_status_scope"][
                "certification_effect"
            ],
        },
        "owner_pre_signature_blocker_scope": {
            "remaining_blocker_count": packet["owner_pre_signature_blocker_scope"][
                "remaining_blocker_count"
            ],
            "approval_action_item_count": packet["owner_pre_signature_blocker_scope"][
                "approval_action_item_count"
            ],
            "signed_item_count": packet["owner_pre_signature_blocker_scope"][
                "signed_item_count"
            ],
            "unsigned_item_count": packet["owner_pre_signature_blocker_scope"][
                "unsigned_item_count"
            ],
            "missing_or_invalid_item_count": packet["owner_pre_signature_blocker_scope"][
                "missing_or_invalid_item_count"
            ],
            "pending_review_item_count": packet["owner_pre_signature_blocker_scope"][
                "pending_review_item_count"
            ],
            "signoff_group_counts": packet["owner_pre_signature_blocker_scope"][
                "signoff_group_counts"
            ],
            "owner_signable": packet["owner_pre_signature_blocker_scope"][
                "owner_signable"
            ],
            "captures_business_owner_approval": packet[
                "owner_pre_signature_blocker_scope"
            ]["captures_business_owner_approval"],
            "captures_product_or_api_decisions": packet[
                "owner_pre_signature_blocker_scope"
            ]["captures_product_or_api_decisions"],
            "can_promote_certification": packet["owner_pre_signature_blocker_scope"][
                "can_promote_certification"
            ],
            "certification_effect": packet["owner_pre_signature_blocker_scope"][
                "certification_effect"
            ],
        },
        "closure_blocker_triage": {
            "blocker_count": packet["closure_blocker_triage"]["blocker_count"],
            "class_counts": packet["closure_blocker_triage"]["class_counts"],
            "cursor_safe_counts": packet["closure_blocker_triage"]["cursor_safe_counts"],
        },
        "golden_sample_approval_artifact_mismatch": packet[
            "golden_sample_approval_artifact_mismatch"
        ],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
