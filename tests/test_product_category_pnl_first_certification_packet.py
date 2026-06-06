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
    }
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
            "5 formal decision items and 5 next-review queue topics; queue topics do not count as captured decisions."
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
            "status": "pending; 15 action items",
            "evidence": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
            "can_be_closed_by_code": False,
            "required_owner_action": "Complete and sign the approval template after reviewing all prior gates.",
        },
    ]


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
        "formal_decision_item_count": 5,
        "next_review_queue_item_count": 5,
        "counts_next_review_as_decision": False,
        "captures_product_or_api_decisions": False,
        "required_owner_action": (
            "Review 5 formal decision items plus 5 next-review queue topics; "
            "the queue topics are intake follow-ups and do not capture decisions."
        ),
    }
    assert (
        "Review docs/pnl/product-category-pnl-owner-decision-packet.md for "
        "5 formal decision items and 5 next-review queue topics; queue topics do not count as captured decisions."
    ) in packet["reviewer_checklist"]


def test_product_category_first_certification_packet_exposes_pre_signature_verification_rerun_receipt() -> None:
    packet = build_packet()

    assert packet["pre_signature_verification_rerun_receipt"] == {
        "receipt_kind": "pre_signature_verification_rerun_receipt",
        "packet_generator_reruns_gate": False,
        "latest_recorded_gate_status": "passed",
        "approval_template_requires_rerun": True,
        "verification_commands_rerun_captured": False,
        "pre_signature_required_commands": [
            (
                "powershell -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive"
            ),
            "python scripts\\check_product_category_pnl_business_owner_approval.py",
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


def test_product_category_first_certification_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "packet.md"

    returncode, payload = _run_packet("--output", str(output_path))

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    text = output_path.read_text(encoding="utf-8")
    assert "Product-Category PnL First Certification Packet" in text
    assert "MTR-PCP-001" in text
    assert "MTR-PCP-012" in text
    assert "golden_sample_approval_artifact_mismatch=true" in text
    assert "Latest Readiness/Live Gate Evidence" in text
    assert "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive" in text
    assert "MCP contract tests: `175 passed`" in text
    assert "This evidence proves the verification gate passed" in text
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
    assert "Approval Checker Generated Artifact Freshness" in text
    assert "first_certification_packet" in text
    assert "owner_decision_packet" in text
    assert "freshness_status=valid" in text
    assert "missing_markers=0" in text
    assert "Owner Decision Packet Bridge" in text
    assert "formal_decision_item_count=5" in text
    assert "next_review_queue_item_count=5" in text
    assert "counts_next_review_as_decision=false" in text
    assert "review_intake_ready=true" in text
    assert "freshness_guarded_artifact_count=2" in text
    assert "missing_freshness_guard_artifacts=0" in text
    assert "missing_required_artifacts=0" in text
    assert "owner_signable=false" in text
    assert "machine_evidence_ready=true" in text
    assert "owner_decisions_pending=5" in text
    assert "Receipt is an owner-review intake aid only" in text
    assert "Pre-Signature Verification Rerun Receipt" in text
    assert "packet_generator_reruns_gate=false" in text
    assert "approval_template_requires_rerun=true" in text
    assert "verification_commands_rerun_captured=false" in text
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
