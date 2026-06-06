from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_product_category_pnl_business_owner_approval import (
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report
from scripts.product_category_pnl_owner_decision_packet import (
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


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict[str, Any]:
    readiness = build_page_readiness_report("product-category-pnl")
    approval = build_approval_status(template_path)
    triage = dict(approval["closure_blocker_triage"])
    owner_decision_packet = build_owner_decision_packet(template_path=template_path)
    owner_review_intake_checklist = _owner_review_intake_checklist()
    golden_status = str(readiness["golden_sample_approval_artifact_status"])
    golden_mismatch = bool(readiness["golden_sample_approval_artifact_mismatch"])
    closure_checklist = dict(approval["closure_checklist_artifact"])
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
            readiness_gate=LATEST_READINESS_GATE_EVIDENCE,
            triage=triage,
            golden_status=golden_status,
            golden_mismatch=golden_mismatch,
            closure_checklist=closure_checklist,
            approval_action_item_count=int(approval["approval_action_item_count"]),
        ),
        "owner_readiness_receipt": _owner_readiness_receipt(
            approval=approval,
            triage=triage,
            golden_mismatch=golden_mismatch,
            closure_checklist=closure_checklist,
            owner_review_intake_checklist=owner_review_intake_checklist,
        ),
        "owner_review_intake_checklist": owner_review_intake_checklist,
        "approval_checker_generated_artifact_freshness": dict(
            approval["generated_artifact_freshness"]
        ),
        "owner_decision_packet_bridge": _owner_decision_packet_bridge(owner_decision_packet),
        "pre_signature_verification_rerun_receipt": _pre_signature_verification_rerun_receipt(
            approval=approval,
            triage=triage,
            readiness_gate=LATEST_READINESS_GATE_EVIDENCE,
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
        "latest_readiness_gate_evidence": dict(LATEST_READINESS_GATE_EVIDENCE),
        "reviewer_checklist": _reviewer_checklist(
            approval["closure_blocker_triage"],
            owner_decision_packet=owner_decision_packet,
        ),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
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
            "status": f"pending; {approval_action_item_count} action items",
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
        "human_required_item_count": len(human_required_evidence),
        "machine_prepared_evidence": [
            "latest_readiness_gate_evidence",
            "source_to_screen_trace:MTR-PCP-001..MTR-PCP-012",
            "owner_decision_packet_artifact_exists",
            "approval_template_artifact_exists",
        ],
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
    return {
        "bridge_kind": "owner_decision_packet_bridge",
        "packet_path": OWNER_DECISION_PACKET_OUTPUT.relative_to(ROOT).as_posix(),
        "packet_exists": OWNER_DECISION_PACKET_OUTPUT.is_file(),
        "formal_decision_item_count": formal_count,
        "next_review_queue_item_count": next_review_count,
        "counts_next_review_as_decision": False,
        "captures_product_or_api_decisions": False,
        "required_owner_action": (
            f"Review {formal_count} formal decision items plus {next_review_count} "
            "next-review queue topics; the queue topics are intake follow-ups and do not "
            "capture decisions."
        ),
    }


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
            str(readiness_gate["command"]),
            "python scripts\\check_product_category_pnl_business_owner_approval.py",
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
    gate_rows = "\n".join(
        (
            f"| `{gate['gate']}` | `{gate['status']}` | `{gate['evidence']}` | "
            f"`{str(gate['can_be_closed_by_code']).lower()}` | {gate['required_owner_action']} |"
        )
        for gate in packet["owner_closure_gate_matrix"]
    )
    checklist = "\n".join(f"- {item}" for item in packet["reviewer_checklist"])
    anchors = "\n".join(
        f"- {label}: `{path}`"
        for label, path in packet["evidence_anchors"].items()
    )
    receipt = packet["owner_readiness_receipt"]
    intake_checklist = packet["owner_review_intake_checklist"]
    checker_freshness = packet["approval_checker_generated_artifact_freshness"]
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

## Owner Decision Packet Bridge

- Bridge kind: `{owner_decision_bridge['bridge_kind']}`
- Packet path: `{owner_decision_bridge['packet_path']}`
- `packet_exists={str(owner_decision_bridge['packet_exists']).lower()}`
- `formal_decision_item_count={owner_decision_bridge['formal_decision_item_count']}`
- `next_review_queue_item_count={owner_decision_bridge['next_review_queue_item_count']}`
- `counts_next_review_as_decision={str(owner_decision_bridge['counts_next_review_as_decision']).lower()}`
- `captures_product_or_api_decisions={str(owner_decision_bridge['captures_product_or_api_decisions']).lower()}`
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

## Business Owner Action Items

{action_items}

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
"""


def _display_template_field(template_field: str) -> str:
    return template_field.removeprefix("- ").strip()


def _optional_bool_label(value: object) -> str:
    if value is None:
        return "n/a"
    return str(bool(value)).lower()


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
        "approval_action_item_count": packet["approval_action_item_count"],
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
