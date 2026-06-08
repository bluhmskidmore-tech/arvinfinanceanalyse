from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import product_category_pnl_first_certification_packet as packet_builder
from scripts.product_category_pnl_first_certification_packet import (
    DEFAULT_OUTPUT,
    build_packet,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "product_category_pnl_first_certification_packet.py"


def _run_packet(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _markdown_section(text: str, heading: str) -> str:
    section = text.split(f"\n## {heading}\n", 1)[1]
    return section.split("\n## ", 1)[0]


def test_product_category_first_certification_packet_exposes_trace_and_owner_actions() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "product_category_pnl_first_certification_packet"
    assert packet["page_slug"] == "product-category-pnl"
    assert packet["route"] == "/product-category-pnl"
    assert packet["primary_api"] == "/ui/pnl/product-category"
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["business_contract_status"] == "evidence-pending"
    assert packet["business_contract_certified"] is False
    assert packet["formal_use_allowed"] is True
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert packet["approval_action_item_count"] == 15
    assert packet["closure_blocker_triage"]["blocker_count"] == 15
    assert packet["closure_blocker_triage"]["class_counts"] == {
        "1": 3,
        "2": 2,
        "3": 0,
        "4": 9,
        "5": 1,
    }
    assert packet["closure_blocker_triage"]["decision_required_count"] == 3
    assert packet["closure_blocker_triage"]["api_contract_required_count"] == 2
    assert packet["golden_sample_approval_artifact_mismatch"] is True
    assert packet["golden_sample_approval_artifact_status"] == "captured-awaiting-approval"
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "certification_effect": "none",
    }
    markdown = render_markdown(packet)
    evidence_scope_section = markdown.split("## Evidence Scope", 1)[1]
    assert "`captures_product_or_api_decisions=false`" in evidence_scope_section
    assert "`certification_effect=none`" in evidence_scope_section
    assert packet["latest_readiness_gate_evidence"] == {
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
        "golden_boundary_status": "approved",
        "golden_artifact_status": "captured-awaiting-approval",
        "golden_artifact_approved": False,
        "golden_sample_approval_artifact_mismatch": True,
        "certification_boundary": (
            "This evidence proves the verification gate passed; it does not capture "
            "business-owner approval, manual audit closure, or golden approval artifact reconciliation."
        ),
        "rerun_boundary": (
            "Regenerating this packet only records the latest available gate evidence; "
            "the pre-approval runbook must rerun the gate before owner signature."
        ),
    }

    trace_rows = packet["metric_trace_rows"]
    assert len(trace_rows) == 12
    assert [row["metric_id"] for row in trace_rows] == [f"MTR-PCP-{index:03d}" for index in range(1, 13)]

    headline = trace_rows[:3]
    assert headline[0]["api_field"] == "result.asset_total.business_net_income"
    assert headline[0]["component_anchor"] == "product-category-formal-headline-totals"
    assert headline[1]["api_field"] == "result.liability_total.business_net_income"
    assert headline[2]["api_field"] == "result.grand_total.business_net_income"
    assert all(row["display_unit"] == "yi_yuan" for row in headline)

    detail = {row["metric_id"]: row for row in trace_rows[3:]}
    assert detail["MTR-PCP-004"]["api_field"] == "result.rows[].cnx_scale"
    assert detail["MTR-PCP-007"]["api_field"] == "result.rows[].cny_ftp"
    assert detail["MTR-PCP-008"]["api_field"] == "result.rows[].foreign_ftp"
    assert detail["MTR-PCP-011"]["api_field"] == "result.rows[].business_net_income"
    assert detail["MTR-PCP-012"]["api_field"] == "result.rows[].weighted_yield"
    assert detail["MTR-PCP-012"]["display_unit"] == "percent"
    assert detail["MTR-PCP-012"]["formatter"] == "formatProductCategoryYieldValue"
    assert all(row["component_anchor"] == "product-category-table" for row in trace_rows[3:])

    assert packet["owner_action_items"][0] == {
        "blocker": "business_owner_name",
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
        "current_status": "missing",
    }
    assert "golden_sample_artifact_reconciliation" in packet["remaining_blockers"]
    assert "evidence_pending_boundary_acceptance" in packet["remaining_blockers"]
    assert packet["reviewer_checklist"] == [
        "Confirm current UI/API payload matches MTR-PCP-001 through MTR-PCP-012 source-to-screen trace rows.",
        "Review docs/pnl/product-category-pnl-owner-decision-packet.md for the 3 product decisions and 2 API/contract blockers.",
        (
            "Review docs/pnl/product-category-pnl-owner-decision-packet.md for "
            "5 formal decision items and 4 next-review queue topics; queue topics do not count as captured decisions."
        ),
        "Confirm reviewed boundary, first-certification, and owner-decision packet artifacts exist before marking template review fields yes.",
        "Resolve golden_sample_approval_artifact_mismatch before certification wording.",
        "Review closure checklist units that remain PARTIAL.",
        "Review liability fallback model-boundary evidence without synthetic production proof.",
        "Run live smoke/browser evidence review before signature.",
        "Complete and sign docs/pnl/product-category-pnl-business-owner-approval-template.md.",
    ]


def test_product_category_first_certification_packet_exposes_owner_closure_gate_matrix() -> None:
    packet = build_packet()

    assert packet["owner_closure_gate_matrix"] == [
        {
            "gate": "machine_verification",
            "status": "passed",
            "evidence": "latest_readiness_gate_evidence",
            "can_be_closed_by_code": False,
            "required_owner_action": "Review evidence; no approval is captured by this gate.",
        },
        {
            "gate": "owner_decisions",
            "status": "pending_owner_decisions",
            "evidence": "docs/pnl/product-category-pnl-owner-decision-packet.md",
            "can_be_closed_by_code": False,
            "required_owner_action": "Resolve 3 product decisions and 2 backend/API contract decisions.",
        },
        {
            "gate": "golden_sample_approval",
            "status": "captured-awaiting-approval; mismatch=true",
            "evidence": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
            "can_be_closed_by_code": False,
            "required_owner_action": "Approve GS-PROD-CAT-PNL-A with non-placeholder owner, approver, and approval date.",
        },
        {
            "gate": "manual_closure_checklist",
            "status": "10 partial units remain",
            "evidence": "docs/pnl/product-category-closure-checklist.md",
            "can_be_closed_by_code": False,
            "required_owner_action": "Review and close each checklist unit from PARTIAL to CLOSED only when evidence and decisions support it.",
        },
        {
            "gate": "business_owner_approval",
            "status": "pending; 15 action items; 0 signed; 15 pending or missing",
            "evidence": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
            "can_be_closed_by_code": False,
            "required_owner_action": "Complete and sign the approval template after reviewing all prior gates.",
        },
    ]


def test_product_category_first_certification_packet_embeds_certification_packet_consistency() -> None:
    packet = build_packet()

    assert packet["certification_packet_consistency"] == {
        "consistency_kind": "product_category_pnl_certification_packet_consistency",
        "status": "valid",
        "missing_markers": [],
        "template_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
        "first_certification_packet_path": "docs/pnl/product-category-pnl-first-certification-packet.md",
        "owner_decision_packet_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
        "formal_decision_item_count": 5,
        "next_review_queue_item_count": 4,
        "approval_action_item_count": 15,
        "business_owner_action_signoff_item_count": 15,
        "business_owner_action_signed_item_count": 0,
        "business_owner_action_pending_or_missing_item_count": 15,
        "business_owner_action_missing_or_invalid_item_count": 5,
        "business_owner_action_pending_review_item_count": 10,
        "approves_metric_or_page": False,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "captures_business_owner_signature": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "writes_governance_records": False,
        "can_promote_certification": False,
        "verification_commands_rerun_captured": False,
        "certification_effect": "none",
        "boundary": (
            "Consistency only proves packet/template counts and non-approval boundaries align; "
            "it captures no approval, signature, product/API decision, golden approval, "
            "closure approval, governance write, or certification."
        ),
    }

    markdown = render_markdown(packet)
    assert "## Certification Packet Consistency" in markdown
    assert "consistency_status=valid" in markdown
    assert "formal_decision_item_count=5" in markdown
    assert "next_review_queue_item_count=4" in markdown
    assert "business_owner_action_signoff_item_count=15" in markdown
    assert "business_owner_action_signed_item_count=0" in markdown
    assert "business_owner_action_pending_or_missing_item_count=15" in markdown
    assert "business_owner_action_missing_or_invalid_item_count=5" in markdown
    assert "business_owner_action_pending_review_item_count=10" in markdown
    assert "approves_metric_or_page=false" in markdown
    assert "captures_business_owner_signature=false" in markdown
    assert "captures_product_or_api_decisions=false" in markdown
    assert "captures_golden_sample_approval=false" in markdown
    assert "captures_closure_approval=false" in markdown
    assert "writes_governance_records=false" in markdown
    assert "verification_commands_rerun_captured=false" in markdown
    assert "certification_effect=none" in markdown


def test_product_category_first_certification_packet_exposes_owner_readiness_receipt() -> None:
    packet = build_packet()

    assert packet["owner_readiness_receipt"] == {
        "receipt_kind": "pre_signature_owner_readiness_receipt",
        "owner_signable": False,
        "machine_evidence_ready": True,
        "business_decisions_ready": False,
        "golden_sample_ready": False,
        "manual_audit_ready": False,
        "business_owner_signature_ready": False,
        "can_promote_certification": False,
        "captures_business_owner_approval": False,
        "human_required_item_count": 15,
        "machine_prepared_evidence": [
            "latest_readiness_gate_evidence",
            "source_to_screen_trace:MTR-PCP-001..MTR-PCP-012",
            "owner_decision_packet_artifact_exists",
            "approval_template_artifact_exists",
        ],
        "human_required_evidence": [
            "business_owner_name",
            "business_owner_role",
            "approval_decision",
            "approval_date",
            "business_owner_signature",
            "governance_record_review",
            "reviewed_owner_decision_packet",
            "owner_decision_next_review_queue_acknowledgement",
            "golden_sample_artifact_reconciliation",
            "closure_checklist_review",
            "fallback_liability_branch_boundary_review",
            "ui_api_payload_review",
            "live_smoke_evidence_review",
            "verification_commands_rerun",
            "evidence_pending_boundary_acceptance",
        ],
        "promotion_blockers": [
            "business_owner_approval_captured=false",
            "closure_approved=false",
            "golden_sample_approval_artifact_mismatch=true",
            "manual_closure_checklist_has_partial_units=10",
            "owner_decisions_pending=5",
        ],
        "boundary": (
            "Receipt is an owner-review intake aid only; it does not approve the page, "
            "write governance records, close manual audit, approve the golden sample, "
            "or capture business-owner approval."
        ),
    }


def test_product_category_first_certification_owner_readiness_receipt_requires_intake_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        packet_builder,
        "OWNER_REVIEW_ARTIFACTS",
        [
            {
                "key": "missing_required_packet",
                "path": str(tmp_path / "missing-required-packet.md"),
            },
        ],
    )

    packet = build_packet()

    assert packet["owner_review_intake_checklist"]["review_intake_ready"] is False
    assert packet["owner_review_intake_checklist"]["missing_required_artifacts"] == [
        "missing_required_packet"
    ]
    assert packet["owner_readiness_receipt"]["machine_evidence_ready"] is False
    assert packet["owner_readiness_receipt"]["human_required_item_count"] == 16
    assert (
        "missing_required_artifact:missing_required_packet"
        in packet["owner_readiness_receipt"]["human_required_evidence"]
    )
    assert (
        "owner_review_intake_ready=false"
        in packet["owner_readiness_receipt"]["promotion_blockers"]
    )
    assert (
        "owner_review_intake_ready=false"
        in packet["pre_signature_verification_rerun_receipt"]["still_blocking_after_rerun"]
    )


def test_product_category_first_certification_owner_readiness_receipt_does_not_claim_missing_owner_decision_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        packet_builder,
        "OWNER_REVIEW_ARTIFACTS",
        [
            {
                "key": "owner_decision_packet",
                "path": str(tmp_path / "missing-owner-decision-packet.md"),
            },
        ],
    )

    packet = build_packet()

    assert packet["owner_review_intake_checklist"]["review_intake_ready"] is False
    assert packet["owner_review_intake_checklist"]["missing_required_artifacts"] == [
        "owner_decision_packet"
    ]
    assert (
        "owner_decision_packet_artifact_exists"
        not in packet["owner_readiness_receipt"]["machine_prepared_evidence"]
    )
    assert (
        "missing_required_artifact:owner_decision_packet"
        in packet["owner_readiness_receipt"]["human_required_evidence"]
    )


def test_product_category_first_certification_owner_readiness_receipt_does_not_claim_missing_approval_template(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        packet_builder,
        "OWNER_REVIEW_ARTIFACTS",
        [
            {
                "key": "approval_template",
                "path": str(tmp_path / "missing-approval-template.md"),
            },
        ],
    )

    packet = build_packet()

    assert packet["owner_review_intake_checklist"]["review_intake_ready"] is False
    assert packet["owner_review_intake_checklist"]["missing_required_artifacts"] == [
        "approval_template"
    ]
    assert (
        "approval_template_artifact_exists"
        not in packet["owner_readiness_receipt"]["machine_prepared_evidence"]
    )
    assert (
        "missing_required_artifact:approval_template"
        in packet["owner_readiness_receipt"]["human_required_evidence"]
    )


def test_product_category_first_certification_packet_exposes_owner_review_intake_checklist() -> None:
    packet = build_packet()

    assert packet["owner_review_intake_checklist"] == {
        "checklist_kind": "owner_review_intake_artifact_checklist",
        "review_intake_ready": True,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "artifacts": [
            {
                "key": "boundary_status",
                "path": "docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": None,
            },
            {
                "key": "first_certification_packet",
                "path": "docs/pnl/product-category-pnl-first-certification-packet.md",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": True,
            },
            {
                "key": "owner_decision_packet",
                "path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": True,
            },
            {
                "key": "approval_template",
                "path": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": None,
            },
            {
                "key": "closure_checklist",
                "path": "docs/pnl/product-category-closure-checklist.md",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": None,
            },
            {
                "key": "closure_blocker_triage",
                "path": "docs/pnl/product-category-remaining-blockers.md",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": None,
            },
            {
                "key": "golden_sample_approval_artifact",
                "path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
                "exists": True,
                "required_before_owner_review": True,
                "freshness_guard_present": None,
            },
        ],
        "freshness_guarded_artifact_count": 2,
        "missing_freshness_guard_artifacts": [],
        "missing_required_artifacts": [],
        "boundary": (
            "All required owner-review artifacts exist, but this checklist does not approve the page, "
            "capture signature, close manual audit, approve the golden sample, or make the route owner-signable."
        ),
    }


def test_product_category_first_certification_packet_bridges_checker_generated_artifact_freshness() -> None:
    packet = build_packet()

    assert packet["approval_checker_generated_artifact_freshness"] == {
        "first_certification_packet": {
            "artifact_path": "docs/pnl/product-category-pnl-first-certification-packet.md",
            "exists": True,
            "freshness_status": "valid",
            "missing_markers": [],
        },
        "owner_decision_packet": {
            "artifact_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
            "exists": True,
            "freshness_status": "valid",
            "missing_markers": [],
        },
    }
    assert packet["approval_checker_generated_artifact_freshness_scope"] == {
        "scope_kind": "generated_artifact_freshness_scope",
        "artifact_count": 2,
        "valid_artifact_count": 2,
        "stale_or_missing_artifact_count": 0,
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

    markdown = render_markdown(packet)
    freshness_section = _markdown_section(markdown, "Approval Checker Generated Artifact Freshness")
    assert "`freshness_check_effect=none`" in freshness_section
    assert "`captures_business_owner_approval=false`" in freshness_section
    assert "`captures_product_or_api_decisions=false`" in freshness_section
    assert "`captures_golden_sample_approval=false`" in freshness_section
    assert "`captures_closure_approval=false`" in freshness_section
    assert "`writes_governance_records=false`" in freshness_section
    assert "`certification_effect=none`" in freshness_section
    assert "does not approve, sign, certify, write governance records, or capture decisions" in freshness_section


def test_product_category_first_certification_owner_review_intake_blocks_incomplete_freshness_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_packet = tmp_path / "first-certification-packet.md"
    first_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=manual-copy`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    owner_packet = tmp_path / "owner-decision-packet.md"
    owner_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifact=docs/pnl/product-category-remaining-blockers.md`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        packet_builder,
        "OWNER_REVIEW_ARTIFACTS",
        [
            {
                "key": "first_certification_packet",
                "path": str(first_packet),
                "requires_freshness_guard": "true",
            },
            {
                "key": "owner_decision_packet",
                "path": str(owner_packet),
                "requires_freshness_guard": "true",
            },
        ],
    )

    checklist = packet_builder._owner_review_intake_checklist()

    assert checklist["review_intake_ready"] is False
    assert checklist["freshness_guarded_artifact_count"] == 1
    assert checklist["missing_freshness_guard_artifacts"] == [
        "first_certification_packet"
    ]
    assert checklist["artifacts"][0]["freshness_guard_present"] is False
    assert checklist["artifacts"][1]["freshness_guard_present"] is True


def test_product_category_first_certification_packet_bridges_owner_decision_next_review_queue() -> None:
    packet = build_packet()

    assert packet["owner_decision_packet_bridge"] == {
        "bridge_kind": "owner_decision_packet_bridge",
        "packet_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
        "packet_exists": True,
        "packet_freshness_status": "valid",
        "missing_freshness_markers": [],
        "formal_decision_item_count": 5,
        "next_review_queue_item_count": 4,
        "counts_next_review_as_decision": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "certification_effect": "none",
        "required_owner_action": (
            "Review 5 formal decision items plus 4 next-review queue topics; "
            "the queue topics are intake follow-ups and do not capture decisions."
        ),
    }
    markdown = render_markdown(packet)
    bridge_section = markdown.split("## Owner Decision Packet Bridge", 1)[1].split(
        "## Pre-Signature Verification Rerun Receipt",
        1,
    )[0]
    assert "`captures_golden_sample_approval=false`" in bridge_section
    assert "`captures_closure_approval=false`" in bridge_section
    assert "`certification_effect=none`" in bridge_section
    assert (
        "Review docs/pnl/product-category-pnl-owner-decision-packet.md for "
        "5 formal decision items and 4 next-review queue topics; queue topics do not count as captured decisions."
    ) in packet["reviewer_checklist"]


def test_product_category_first_certification_packet_exposes_owner_reviewer_receipt() -> None:
    packet = build_packet()

    assert packet["owner_reviewer_receipt"] == {
        "receipt_kind": "owner_reviewer_checklist_receipt",
        "item_count": 9,
        "signed_item_count": 0,
        "pending_item_count": 9,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "items": [
            {
                "review_key": "source_to_screen_trace_review",
                "checklist_item": "Confirm current UI/API payload matches MTR-PCP-001 through MTR-PCP-012 source-to-screen trace rows.",
                "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#source-to-screen-trace",
                "approval_action_fields": ["ui_api_payload_review"],
                "current_status": "pending_owner_review",
                "blocking_condition": "ui_api_payload_review=pending",
            },
            {
                "review_key": "formal_decision_item_review",
                "checklist_item": "Review docs/pnl/product-category-pnl-owner-decision-packet.md for the 3 product decisions and 2 API/contract blockers.",
                "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md#decision-items",
                "approval_action_fields": ["reviewed_owner_decision_packet"],
                "current_status": "pending_owner_review",
                "blocking_condition": "reviewed_owner_decision_packet=pending",
            },
            {
                "review_key": "next_review_queue_acknowledgement",
                "checklist_item": (
                    "Review docs/pnl/product-category-pnl-owner-decision-packet.md for "
                    "5 formal decision items and 4 next-review queue topics; queue topics do not count as captured decisions."
                ),
                "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md#next-review-queue",
                "approval_action_fields": ["owner_decision_next_review_queue_acknowledgement"],
                "current_status": "pending_owner_review",
                "blocking_condition": "owner_decision_next_review_queue_acknowledgement=pending",
            },
            {
                "review_key": "artifact_freshness_review",
                "checklist_item": "Confirm reviewed boundary, first-certification, and owner-decision packet artifacts exist before marking template review fields yes.",
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
                "checklist_item": "Resolve golden_sample_approval_artifact_mismatch before certification wording.",
                "evidence_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
                "approval_action_fields": ["golden_sample_artifact_reconciliation"],
                "current_status": "pending_owner_review",
                "blocking_condition": "golden_sample_artifact_reconciliation=pending",
            },
            {
                "review_key": "manual_closure_checklist_review",
                "checklist_item": "Review closure checklist units that remain PARTIAL.",
                "evidence_path": "docs/pnl/product-category-closure-checklist.md",
                "approval_action_fields": ["closure_checklist_review"],
                "current_status": "pending_owner_review",
                "blocking_condition": "closure_checklist_review=pending",
            },
            {
                "review_key": "fallback_liability_boundary_review",
                "checklist_item": "Review liability fallback model-boundary evidence without synthetic production proof.",
                "evidence_path": "docs/pnl/product-category-page-truth-contract.md",
                "approval_action_fields": ["fallback_liability_branch_boundary_review"],
                "current_status": "pending_owner_review",
                "blocking_condition": "fallback_liability_branch_boundary_review=pending",
            },
            {
                "review_key": "live_smoke_evidence_review",
                "checklist_item": "Run live smoke/browser evidence review before signature.",
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
                "checklist_item": "Complete and sign docs/pnl/product-category-pnl-business-owner-approval-template.md.",
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
        ],
        "boundary": (
            "Reviewer receipt structures owner-review work for signature intake only; it does not "
            "capture business-owner approval, close manual audit, approve golden samples, or certify the route."
        ),
    }


def test_product_category_first_certification_packet_covers_owner_reviewer_receipt_fields() -> None:
    packet = build_packet()

    assert packet["owner_reviewer_receipt_field_coverage"] == {
        "coverage_kind": "owner_reviewer_receipt_approval_field_coverage",
        "receipt_item_count": 9,
        "referenced_approval_field_count": 17,
        "all_referenced_fields_known": True,
        "missing_approval_action_fields": [],
        "referenced_approval_fields": [
            "approval_date",
            "approval_decision",
            "business_owner_name",
            "business_owner_role",
            "business_owner_signature",
            "closure_checklist_review",
            "evidence_pending_boundary_acceptance",
            "fallback_liability_branch_boundary_review",
            "golden_sample_artifact_reconciliation",
            "governance_record_review",
            "live_smoke_evidence_review",
            "owner_decision_next_review_queue_acknowledgement",
            "reviewed_boundary_packet",
            "reviewed_first_certification_packet",
            "reviewed_owner_decision_packet",
            "ui_api_payload_review",
            "verification_commands_rerun",
        ],
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "boundary": (
            "Coverage only proves receipt fields are known to the approval checker; it does not "
            "mark any field reviewed, signed, or certification-ready."
        ),
    }


def test_product_category_first_certification_packet_exposes_business_owner_action_signoff_matrix() -> None:
    packet = build_packet()

    assert packet["business_owner_action_signoff_matrix"] == {
        "matrix_kind": "business_owner_action_signoff_matrix",
        "action_item_count": 15,
        "signed_item_count": 0,
        "pending_or_missing_item_count": 15,
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "items": [
            {
                "blocker": "business_owner_name",
                "signoff_group": "owner_identity",
                "required_owner_type": "business_owner",
                "template_field": "Business owner name",
                "required_value": "Business owner legal or operating name",
                "current_status": "missing",
                "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
                "pre_signature_action": "Fill the business owner legal or operating name.",
                "blocks_certification": True,
            },
            {
                "blocker": "business_owner_role",
                "signoff_group": "owner_identity",
                "required_owner_type": "business_owner",
                "template_field": "Business owner role",
                "required_value": "Business owner accountability role",
                "current_status": "missing",
                "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
                "pre_signature_action": "Fill the accountable business owner role.",
                "blocks_certification": True,
            },
            {
                "blocker": "approval_decision",
                "signoff_group": "owner_decision",
                "required_owner_type": "business_owner",
                "template_field": "Approval decision",
                "required_value": "approve",
                "current_status": "missing",
                "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
                "pre_signature_action": "Set approval decision to approve after all review gates are satisfied.",
                "blocks_certification": True,
            },
            {
                "blocker": "approval_date",
                "signoff_group": "owner_decision",
                "required_owner_type": "business_owner",
                "template_field": "Approval date",
                "required_value": "YYYY-MM-DD",
                "current_status": "missing",
                "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
                "pre_signature_action": "Fill an approval date in YYYY-MM-DD format.",
                "blocks_certification": True,
            },
            {
                "blocker": "business_owner_signature",
                "signoff_group": "owner_decision",
                "required_owner_type": "business_owner",
                "template_field": "Business owner signature",
                "required_value": "Business owner signature",
                "current_status": "missing",
                "evidence_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md#required-business-decision",
                "pre_signature_action": "Capture the business owner signature after all prerequisite review fields are valid.",
                "blocks_certification": True,
            },
            {
                "blocker": "governance_record_review",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "Governance record reviewed",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json",
                "pre_signature_action": "Review the governance boundary record and mark this field yes only after review.",
                "blocks_certification": True,
            },
            {
                "blocker": "reviewed_owner_decision_packet",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "Owner decision packet reviewed",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
                "pre_signature_action": "Review the owner decision packet and keep unresolved product/API decisions pending.",
                "blocks_certification": True,
            },
            {
                "blocker": "owner_decision_next_review_queue_acknowledgement",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "Owner decision next-review queue acknowledged",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-pnl-owner-decision-packet.md#next-review-queue",
                "pre_signature_action": "Acknowledge 4 next-review queue topics as intake follow-ups, not captured decisions.",
                "blocks_certification": True,
            },
            {
                "blocker": "golden_sample_artifact_reconciliation",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
                "pre_signature_action": "Reconcile the golden sample approval artifact to approved with non-placeholder owner, approver, and approval date.",
                "blocks_certification": True,
            },
            {
                "blocker": "closure_checklist_review",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "Closure checklist units reviewed",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-closure-checklist.md",
                "pre_signature_action": "Review closure checklist units and leave certification pending while any unit remains PARTIAL.",
                "blocks_certification": True,
            },
            {
                "blocker": "fallback_liability_branch_boundary_review",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "Fallback liability branch model-boundary evidence reviewed",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-page-truth-contract.md",
                "pre_signature_action": "Review fallback liability branch boundary evidence without treating it as synthetic production proof.",
                "blocks_certification": True,
            },
            {
                "blocker": "ui_api_payload_review",
                "signoff_group": "evidence_review",
                "required_owner_type": "business_owner",
                "template_field": "UI/API payload evidence reviewed",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#source-to-screen-trace",
                "pre_signature_action": "Review current UI/API payload against MTR-PCP-001 through MTR-PCP-012 source-to-screen trace.",
                "blocks_certification": True,
            },
            {
                "blocker": "live_smoke_evidence_review",
                "signoff_group": "pre_signature_verification",
                "required_owner_type": "business_owner",
                "template_field": "Live smoke evidence reviewed",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "latest_readiness_gate_evidence",
                "pre_signature_action": "Review fresh live smoke/browser evidence before signature.",
                "blocks_certification": True,
            },
            {
                "blocker": "verification_commands_rerun",
                "signoff_group": "pre_signature_verification",
                "required_owner_type": "business_owner",
                "template_field": "Verification commands rerun before approval",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#pre-signature-verification-rerun-receipt",
                "pre_signature_action": "Rerun the pre-signature readiness and approval checker commands.",
                "blocks_certification": True,
            },
            {
                "blocker": "evidence_pending_boundary_acceptance",
                "signoff_group": "boundary_acceptance",
                "required_owner_type": "business_owner",
                "template_field": "Evidence-pending boundary accepted",
                "required_value": "yes",
                "current_status": "pending",
                "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#evidence-scope",
                "pre_signature_action": "Explicitly accept the evidence-pending boundary if approval proceeds without route certification.",
                "blocks_certification": True,
            },
        ],
        "group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "signed_group_counts": {},
        "pending_or_missing_group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "boundary": (
            "Action signoff matrix prepares owner signature intake only. Only current_status=valid counts as signed; all other statuses still block "
            "business-owner approval capture and business-contract certification."
        ),
    }


def test_product_category_first_certification_packet_exposes_owner_action_status_scope() -> None:
    packet = build_packet()

    assert packet["owner_action_status_scope"] == {
        "scope_kind": "owner_action_status_scope",
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "can_promote_certification": False,
        "certification_effect": "none",
        "boundary": (
            "Owner-action status split is approval-checker evidence only; it does not "
            "capture business-owner approval, product/API decisions, or route certification."
        ),
    }

    markdown = render_markdown(packet)
    section = _markdown_section(markdown, "Owner Action Status Scope")
    assert "`missing_or_invalid_item_count=5`" in section
    assert "`pending_review_item_count=10`" in section
    assert "`captures_business_owner_approval=false`" in section
    assert "`captures_product_or_api_decisions=false`" in section
    assert "`can_promote_certification=false`" in section
    assert "`certification_effect=none`" in section


def test_product_category_first_certification_packet_exposes_pre_signature_blocker_scope() -> None:
    packet = build_packet()

    scope = packet["owner_pre_signature_blocker_scope"]
    assert scope["scope_kind"] == "owner_pre_signature_blocker_scope"
    assert scope["remaining_blocker_count"] == 16
    assert scope["remaining_blockers"] == packet["remaining_blockers"]
    assert scope["approval_action_item_count"] == 15
    assert scope["approval_action_blockers"] == [
        item["blocker"] for item in packet["owner_action_items"]
    ]
    assert scope["signed_item_count"] == 0
    assert scope["unsigned_item_count"] == 15
    assert scope["missing_or_invalid_item_count"] == 5
    assert scope["pending_review_item_count"] == 10
    assert scope["signoff_group_counts"] == {
        "boundary_acceptance": 1,
        "evidence_review": 7,
        "owner_decision": 3,
        "owner_identity": 2,
        "pre_signature_verification": 2,
    }
    assert scope["owner_signable"] is False
    assert scope["captures_business_owner_approval"] is False
    assert scope["captures_product_or_api_decisions"] is False
    assert scope["can_promote_certification"] is False
    assert scope["certification_effect"] == "none"
    assert len(scope["checklist_items"]) == 15
    assert {
        "blocker": "verification_commands_rerun",
        "signoff_group": "pre_signature_verification",
        "template_field": "- Verification commands rerun before approval",
        "required_value": "yes",
        "current_status": "pending",
        "blocks_owner_signature": True,
        "certification_effect": "none",
    } in scope["checklist_items"]

    markdown = render_markdown(packet)
    section = _markdown_section(markdown, "Owner Pre-Signature Blocker Scope")
    assert "`remaining_blocker_count=16`" in section
    assert "`approval_action_item_count=15`" in section
    assert "`unsigned_item_count=15`" in section
    assert "`missing_or_invalid_item_count=5`" in section
    assert "`pending_review_item_count=10`" in section
    assert "`captures_product_or_api_decisions=false`" in section
    assert "`certification_effect=none`" in section
    assert "owner_decision_next_review_queue_acknowledgement" in section
    assert "verification_commands_rerun" in section


def test_product_category_first_certification_pre_signature_scope_keeps_next_review_acknowledgement_as_evidence_review() -> None:
    packet = build_packet()

    scope = packet["owner_pre_signature_blocker_scope"]
    next_review_items = [
        item
        for item in scope["checklist_items"]
        if item["blocker"] == "owner_decision_next_review_queue_acknowledgement"
    ]

    assert next_review_items == [
        {
            "blocker": "owner_decision_next_review_queue_acknowledgement",
            "signoff_group": "evidence_review",
            "template_field": "- Owner decision next-review queue acknowledged",
            "required_value": "yes",
            "current_status": "pending",
            "blocks_owner_signature": True,
            "certification_effect": "none",
        }
    ]


def test_product_category_first_certification_packet_exposes_pre_signature_verification_rerun_receipt() -> None:
    packet = build_packet()

    assert packet["pre_signature_verification_rerun_receipt"] == {
        "receipt_kind": "pre_signature_verification_rerun_receipt",
        "packet_generator_reruns_gate": False,
        "latest_recorded_gate_status": "passed",
        "approval_template_requires_rerun": True,
        "verification_commands_rerun_captured": False,
        "pre_signature_required_commands": [
            "python scripts\\product_category_pnl_first_certification_packet.py",
            "python scripts\\product_category_pnl_owner_decision_packet.py",
            "python scripts\\check_product_category_pnl_business_owner_approval.py",
            (
                "powershell -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive"
            ),
            "python scripts\\check_product_category_pnl_business_owner_approval.py --require-captured",
        ],
        "current_recorded_evidence": {
            "static_readiness": "passed",
            "live_smoke": "passed",
            "mcp_contract_tests": "175 passed",
            "backend_flow_mapping_tests": "59 passed",
            "frontend_tests": "155 passed",
            "browser_a11y_smoke": "1 passed",
            "frontend_typecheck": "passed",
            "frontend_debt_audit": "passed",
            "frontend_production_build": "passed",
        },
        "still_blocking_after_rerun": [
            "business_owner_approval_captured=false",
            "golden_sample_approval_artifact_mismatch=true",
            "manual_closure_checklist_has_partial_units=10",
            "owner_decisions_pending=5",
        ],
        "boundary": (
            "Recorded gate evidence is useful intake evidence, but owner signature requires a fresh "
            "pre-signature rerun and still cannot bypass golden, manual-audit, owner decisions, or owner approval."
        ),
    }


def test_product_category_first_certification_action_signoff_matrix_treats_invalid_status_as_unsigned() -> None:
    matrix = packet_builder._business_owner_action_signoff_matrix(
        [
            {
                "blocker": "approval_decision",
                "template_field": "Approval decision",
                "required_value": "approve",
                "current_status": "invalid",
            }
        ]
    )

    assert matrix["action_item_count"] == 1
    assert matrix["signed_item_count"] == 0
    assert matrix["pending_or_missing_item_count"] == 1
    assert matrix["missing_or_invalid_item_count"] == 1
    assert matrix["pending_review_item_count"] == 0
    assert matrix["owner_signable"] is False
    assert matrix["can_promote_certification"] is False
    assert "Only current_status=valid counts as signed" in matrix["boundary"]


def test_product_category_first_certification_action_signoff_matrix_handles_stale_consistency_packet() -> None:
    matrix = packet_builder._business_owner_action_signoff_matrix(
        [
            {
                "blocker": "certification_packet_consistency",
                "template_field": "Certification packet consistency",
                "required_value": "valid",
                "current_status": "stale_generated_artifact",
            }
        ]
    )

    assert matrix["action_item_count"] == 1
    assert matrix["signed_item_count"] == 0
    assert matrix["pending_or_missing_item_count"] == 1
    assert matrix["missing_or_invalid_item_count"] == 1
    assert matrix["pending_review_item_count"] == 0
    assert matrix["items"] == [
        {
            "blocker": "certification_packet_consistency",
            "signoff_group": "evidence_review",
            "required_owner_type": "business_owner",
            "template_field": "Certification packet consistency",
            "required_value": "valid",
            "current_status": "stale_generated_artifact",
            "evidence_path": "docs/pnl/product-category-pnl-first-certification-packet.md#certification-packet-consistency",
            "pre_signature_action": (
                "Regenerate and review the first-certification packet consistency section "
                "without treating consistency as approval or certification."
            ),
            "blocks_certification": True,
        }
    ]


def test_product_category_first_certification_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "packet.md"

    returncode, payload = _run_packet("--output", str(output_path))

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["business_contract_certified"] is False
    assert payload["business_owner_approval_captured"] is False
    assert payload["closure_approved"] is False
    assert payload["owner_readiness_receipt"] == {
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "human_required_item_count": 15,
        "promotion_blockers": [
            "business_owner_approval_captured=false",
            "closure_approved=false",
            "golden_sample_approval_artifact_mismatch=true",
            "manual_closure_checklist_has_partial_units=10",
            "owner_decisions_pending=5",
        ],
    }
    assert payload["owner_decision_packet_bridge"] == {
        "formal_decision_item_count": 5,
        "next_review_queue_item_count": 4,
        "counts_next_review_as_decision": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "certification_effect": "none",
    }
    assert payload["pre_signature_verification_rerun_receipt"] == {
        "packet_generator_reruns_gate": False,
        "approval_template_requires_rerun": True,
        "verification_commands_rerun_captured": False,
        "business_owner_approval_captured": False,
        "closure_approved": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "still_blocking_after_rerun": [
            "business_owner_approval_captured=false",
            "golden_sample_approval_artifact_mismatch=true",
            "manual_closure_checklist_has_partial_units=10",
            "owner_decisions_pending=5",
        ],
    }
    assert payload["latest_readiness_gate_evidence"] == {
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
        "golden_boundary_status": "approved",
        "golden_artifact_status": "captured-awaiting-approval",
        "golden_artifact_approved": False,
        "golden_sample_approval_artifact_mismatch": True,
        "verification_commands_rerun_captured": False,
        "business_owner_approval_captured": False,
        "certification_effect": "none",
    }
    assert payload["owner_reviewer_receipt"] == {
        "owner_reviewer_receipt_item_count": 9,
        "signed_item_count": 0,
        "pending_item_count": 9,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
    }
    assert payload["owner_reviewer_receipt_field_coverage"] == {
        "referenced_approval_field_count": 17,
        "all_referenced_fields_known": True,
        "missing_approval_action_field_count": 0,
        "owner_signable": False,
        "captures_business_owner_approval": False,
    }
    assert payload["business_owner_action_signoff_matrix"] == {
        "signed_item_count": 0,
        "pending_or_missing_item_count": 15,
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "signed_group_counts": {},
        "pending_or_missing_group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
    }
    assert payload["owner_action_status_scope"] == {
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "can_promote_certification": False,
        "certification_effect": "none",
    }
    assert payload["owner_pre_signature_blocker_scope"] == {
        "remaining_blocker_count": 16,
        "approval_action_item_count": 15,
        "signed_item_count": 0,
        "unsigned_item_count": 15,
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "signoff_group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "can_promote_certification": False,
        "certification_effect": "none",
    }
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "certification_effect": "none",
    }
    text = output_path.read_text(encoding="utf-8")
    assert "Product-Category PnL First Certification Packet" in text
    assert "MTR-PCP-001" in text
    assert "MTR-PCP-012" in text
    assert "golden_sample_approval_artifact_mismatch=true" in text
    assert "Latest Readiness/Live Gate Evidence" in text
    assert "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive" in text
    assert "MCP contract tests: `175 passed`" in text
    assert "This evidence proves the verification gate passed" in text
    assert "Golden boundary status: `approved`" in text
    assert "Golden artifact status: `captured-awaiting-approval`" in text
    assert "Golden artifact approved: `false`" in text
    assert "Golden artifact mismatch: `true`" in text
    assert "Evidence basis: `recorded_prior_gate_output`" in text
    assert "Packet generator reruns gate: `false`" in text
    assert "the pre-approval runbook must rerun the gate before owner signature" in text
    assert "closure_blocker_triage.blocker_count=15" in text
    assert "Class 1 product decisions: `3`" in text
    assert "Class 2 API/contract blockers: `2`" in text
    assert "owner_decision_packet" in text
    assert "Owner Closure Gate Matrix" in text
    assert "Resolve 3 product decisions and 2 backend/API contract decisions." in text
    assert "Approve GS-PROD-CAT-PNL-A with non-placeholder owner, approver, and approval date." in text
    assert "10 partial units remain" in text
    assert "Owner Readiness Receipt" in text
    assert "Owner Review Intake Checklist" in text
    assert "Owner Reviewer Receipt" in text
    assert "owner_reviewer_receipt_item_count=9" in text
    assert "source_to_screen_trace_review" in text
    assert "business_owner_signature_completion" in text
    assert "Owner Reviewer Receipt Field Coverage" in text
    assert "referenced_approval_field_count=17" in text
    assert "all_referenced_fields_known=true" in text
    assert "Business Owner Action Signoff Matrix" in text
    assert "business_owner_action_signoff_item_count=15" in text
    assert "business_owner_action_signed_item_count=0" in text
    assert "business_owner_action_pending_or_missing_item_count=15" in text
    assert "pending_or_missing_item_count=15" in text
    signoff_matrix_section = _markdown_section(text, "Business Owner Action Signoff Matrix")
    assert "`missing_or_invalid_item_count=5`" in signoff_matrix_section
    assert "`pending_review_item_count=10`" in signoff_matrix_section
    assert "Signed group counts: `none=0`" in signoff_matrix_section
    assert (
        "Pending or missing group counts: `boundary_acceptance=1`, "
        "`evidence_review=7`, `owner_decision=3`, `owner_identity=2`, "
        "`pre_signature_verification=2`"
        in signoff_matrix_section
    )
    owner_action_status_scope_section = _markdown_section(text, "Owner Action Status Scope")
    assert "`missing_or_invalid_item_count=5`" in owner_action_status_scope_section
    assert "`pending_review_item_count=10`" in owner_action_status_scope_section
    assert "`captures_product_or_api_decisions=false`" in owner_action_status_scope_section
    assert "`certification_effect=none`" in owner_action_status_scope_section
    assert "owner_decision_next_review_queue_acknowledgement" in text
    assert "Approval Checker Generated Artifact Freshness" in text
    assert "first_certification_packet" in text
    assert "owner_decision_packet" in text
    assert "freshness_status=valid" in text
    assert "missing_markers=0" in text
    assert "Owner Decision Packet Bridge" in text
    assert "formal_decision_item_count=5" in text
    assert "next_review_queue_item_count=4" in text
    assert "packet_freshness_status=valid" in text
    assert "missing_freshness_markers=0" in text
    assert "counts_next_review_as_decision=false" in text
    assert "review_intake_ready=true" in text
    assert "freshness_guarded_artifact_count=2" in text
    assert "missing_freshness_guard_artifacts=0" in text
    assert "missing_required_artifacts=0" in text
    assert "owner_signable=false" in text
    assert "machine_evidence_ready=true" in text
    assert "owner_decisions_pending=5" in text
    assert "Receipt is an owner-review intake aid only" in text
    owner_readiness_section = _markdown_section(text, "Owner Readiness Receipt")
    assert "`captures_business_owner_approval=false`" in owner_readiness_section
    assert "Pre-Signature Verification Rerun Receipt" in text
    assert "packet_generator_reruns_gate=false" in text
    assert "approval_template_requires_rerun=true" in text
    assert "verification_commands_rerun_captured=false" in text
    assert "python scripts\\product_category_pnl_first_certification_packet.py" in text
    assert "python scripts\\product_category_pnl_owner_decision_packet.py" in text
    assert "python scripts\\check_product_category_pnl_business_owner_approval.py" in text
    assert "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive" in text
    assert "Recorded gate evidence is useful intake evidence" in text
    assert "This packet does not approve page closure" in text
    assert "\n- - " not in text


def test_checked_in_product_category_first_certification_packet_matches_renderer() -> None:
    packet = build_packet()
    expected_markdown = render_markdown(packet)

    checked_in_markdown = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    assert checked_in_markdown == expected_markdown
    assert "## Packet Freshness Guard" in checked_in_markdown
    assert "packet_generator=script-owned" in checked_in_markdown
    assert "source_artifacts=readiness_report, approval_template, closure_blocker_triage" in checked_in_markdown
    assert "Manual edits to this packet must be followed by rerunning the generator." in checked_in_markdown
