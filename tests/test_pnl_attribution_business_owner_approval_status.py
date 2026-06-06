from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_pnl_attribution_business_owner_approval import build_status


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_pnl_attribution_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "pnl-attribution-business-owner-approval-template.md"


def _filled_template_text(*, decision: str = "approve", approval_date: str = "2026-06-05") -> str:
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `PnL Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Finance Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `PnL Owner`")
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace("- Golden sample `GS-PNL-ATTR-WB-A` reviewed: `<yes | no>`", "- Golden sample `GS-PNL-ATTR-WB-A` reviewed: `yes`")
        .replace("- UI/API payload evidence reviewed: `<yes | no>`", "- UI/API payload evidence reviewed: `yes`")
        .replace("- Live smoke evidence reviewed: `<yes | no>`", "- Live smoke evidence reviewed: `yes`")
        .replace("- Verification commands rerun before approval: `<yes | no>`", "- Verification commands rerun before approval: `yes`")
        .replace("- Candidate-only boundary accepted: `<yes | no>`", "- Candidate-only boundary accepted: `yes`")
    )


def _run_checker(*args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return json.loads(completed.stdout)


def test_pnl_attribution_business_owner_approval_checker_reports_pending_template() -> None:
    payload = _run_checker("--template-path", str(TEMPLATE))

    assert payload == {
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "page_slug": "pnl-attribution",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "approval_check": "business_owner_approval",
        "approval_status": "pending",
        "business_owner_approval_captured": False,
        "formal_use_allowed": False,
        "closure_approved": False,
        "remaining_blockers": [
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
        ],
        "approval_field_status": {
            "business_owner_name": "missing",
            "business_owner_role": "missing",
            "approval_decision": "missing",
            "approval_date": "missing",
            "business_owner_signature": "missing",
            "reviewed_signoff_packet": "valid",
            "reviewed_governance_audit_packet": "valid",
            "reviewed_owner_evidence_packet": "valid",
            "governance_record_review": "pending",
            "golden_sample_review": "pending",
            "ui_api_payload_review": "pending",
            "live_smoke_evidence_review": "pending",
            "verification_commands_rerun": "pending",
            "candidate_boundary_acceptance": "pending",
            "decision_notes": "not_required",
            "formal_use_allowed": "valid",
            "closure_approved": "valid",
        },
        "approval_action_items": [
            {
                "blocker": "business_owner_name",
                "template_field": "Business owner name",
                "required_value": "Business owner legal or operating name",
                "current_status": "missing",
            },
            {
                "blocker": "business_owner_role",
                "template_field": "Business owner role",
                "required_value": "Business owner accountability role",
                "current_status": "missing",
            },
            {
                "blocker": "approval_decision",
                "template_field": "Approval decision",
                "required_value": "approve",
                "current_status": "missing",
            },
            {
                "blocker": "approval_date",
                "template_field": "Approval date",
                "required_value": "YYYY-MM-DD",
                "current_status": "missing",
            },
            {
                "blocker": "business_owner_signature",
                "template_field": "Business owner signature",
                "required_value": "Business owner signature",
                "current_status": "missing",
            },
            {
                "blocker": "governance_record_review",
                "template_field": "- Governance record reviewed",
                "required_value": "yes",
                "current_status": "pending",
            },
            {
                "blocker": "golden_sample_review",
                "template_field": "- Golden sample `GS-PNL-ATTR-WB-A` reviewed",
                "required_value": "yes",
                "current_status": "pending",
            },
            {
                "blocker": "ui_api_payload_review",
                "template_field": "- UI/API payload evidence reviewed",
                "required_value": "yes",
                "current_status": "pending",
            },
            {
                "blocker": "live_smoke_evidence_review",
                "template_field": "- Live smoke evidence reviewed",
                "required_value": "yes",
                "current_status": "pending",
            },
            {
                "blocker": "verification_commands_rerun",
                "template_field": "- Verification commands rerun before approval",
                "required_value": "yes",
                "current_status": "pending",
            },
            {
                "blocker": "candidate_boundary_acceptance",
                "template_field": "- Candidate-only boundary accepted",
                "required_value": "yes",
                "current_status": "pending",
            },
        ],
        "approval_action_item_count": 11,
        "template_path": str(TEMPLATE),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
        },
    }


def test_pnl_attribution_business_owner_approval_checker_default_cli_allows_pending() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--template-path", str(TEMPLATE)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False


def test_pnl_attribution_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--template-path", str(TEMPLATE), "--require-captured"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_pnl_attribution_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--template-path", str(template), "--require-captured"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []


def test_pnl_attribution_business_owner_approval_checker_rejects_placeholder_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    text = TEMPLATE.read_text(encoding="utf-8")
    template.write_text(
        text.replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`"),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
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
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_captures_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_field_status"]["business_owner_name"] == "valid"
    assert payload["approval_field_status"]["approval_decision"] == "valid"
    assert payload["approval_field_status"]["approval_date"] == "valid"
    assert payload["approval_field_status"]["decision_notes"] == "not_required"
    assert payload["approval_field_status"]["verification_commands_rerun"] == "valid"
    assert payload["approval_field_status"]["candidate_boundary_acceptance"] == "valid"
    assert payload["approval_action_items"] == []
    assert payload["approval_action_item_count"] == 0
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["proves_page_execution"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_missing_signature(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Business owner signature: `PnL Owner`",
            "Business owner signature: `<required>`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "business_owner_signature"]
    assert payload["approval_action_items"] == [
        {
            "blocker": "business_owner_signature",
            "template_field": "Business owner signature",
            "required_value": "Business owner signature",
            "current_status": "missing",
        },
    ]
    assert payload["approval_action_item_count"] == 1
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_wrong_signoff_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed sign-off packet: `docs/pnl/pnl-attribution-sign-off-packet.md`",
            "Reviewed sign-off packet: `docs/pnl/other-sign-off-packet.md`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "reviewed_signoff_packet"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_wrong_audit_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed governance audit packet: `docs/pnl/pnl-attribution-governance-audit-packet.md`",
            "Reviewed governance audit packet: `docs/pnl/other-governance-audit-packet.md`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "reviewed_governance_audit_packet"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_wrong_owner_evidence_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`",
            "Reviewed owner evidence packet: `docs/pnl/other-owner-evidence-packet.md`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "reviewed_owner_evidence_packet"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_non_approve_decision(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(_filled_template_text(decision="reject"), encoding="utf-8")

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_decision", "decision_notes"]
    assert payload["approval_field_status"]["approval_decision"] == "invalid"
    assert payload["approval_field_status"]["decision_notes"] == "missing"
    assert payload["approval_action_items"] == [
        {
            "blocker": "approval_decision",
            "template_field": "Approval decision",
            "required_value": "approve",
            "current_status": "invalid",
        },
        {
            "blocker": "decision_notes",
            "template_field": "Decision notes",
            "required_value": "Required if decision is reject or request_changes",
            "current_status": "missing",
        },
    ]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_requires_notes_for_request_changes(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(_filled_template_text(decision="request_changes"), encoding="utf-8")

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_decision", "decision_notes"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_bad_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(_filled_template_text(approval_date="06/05/2026"), encoding="utf-8")

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_date"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_formal_use_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Formal use allowed: `formal_use_allowed=false`",
            "Formal use allowed: `formal_use_allowed=true`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
    assert payload["remaining_blockers"] == ["business_owner_approval", "formal_use_promotion_boundary"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_pnl_attribution_business_owner_approval_checker_rejects_closure_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Closure approved: `closure_approved=false`",
            "Closure approved: `closure_approved=true`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["closure_approved"] is True
    assert payload["remaining_blockers"] == ["business_owner_approval", "closure_promotion_boundary"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False
