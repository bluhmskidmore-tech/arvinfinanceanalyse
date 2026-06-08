from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ledger_pnl_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "ledger-pnl-business-owner-approval-template.md"

TEMPLATE_TEXT = """# Ledger PnL Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `PAGE-LEDGER-PNL-001`
Page slug: `ledger-pnl`
Primary API: `/api/ledger-pnl/summary`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote `MTR-LPN-001` through `MTR-LPN-003` to formal use.
- Do not replace formal PnL, product-category PnL, PnL bridge, or formal FI truth.
- Dedicated ledger summary golden sample `GS-LEDGER-PNL-SUMMARY-A` is captured-awaiting-approval and does not approve this page for formal use.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed sign-off packet: `docs/pnl/ledger-pnl-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/ledger-pnl-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Dedicated ledger summary golden sample reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
"""


def _filled_template_text(
    *,
    decision: str = "approve",
    approval_date: str = "2026-06-05",
) -> str:
    return (
        TEMPLATE_TEXT.replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Ledger PnL Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Finance Control Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Ledger PnL Owner`")
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace(
            "- Dedicated ledger summary golden sample reviewed: `<yes | no>`",
            "- Dedicated ledger summary golden sample reviewed: `yes`",
        )
        .replace("- UI/API payload evidence reviewed: `<yes | no>`", "- UI/API payload evidence reviewed: `yes`")
        .replace("- Live smoke evidence reviewed: `<yes | no>`", "- Live smoke evidence reviewed: `yes`")
        .replace(
            "- Verification commands rerun before approval: `<yes | no>`",
            "- Verification commands rerun before approval: `yes`",
        )
        .replace("- Candidate-only boundary accepted: `<yes | no>`", "- Candidate-only boundary accepted: `yes`")
    )


def _run_checker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def test_ledger_pnl_business_owner_approval_checker_reports_pending_template() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), check=False)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)

    assert payload["page_id"] == "PAGE-LEDGER-PNL-001"
    assert payload["page_slug"] == "ledger-pnl"
    assert payload["primary_api"] == "/api/ledger-pnl/summary"
    assert payload["approval_check"] == "business_owner_approval"
    assert payload["approval_status"] == "pending"
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is False
    assert payload["closure_approved"] is False
    assert payload["remaining_blockers"] == [
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
    assert payload["approval_field_status"]["business_owner_name"] == "missing"
    assert payload["approval_field_status"]["reviewed_signoff_packet"] == "valid"
    assert payload["approval_field_status"]["reviewed_governance_audit_packet"] == "valid"
    assert payload["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert payload["approval_field_status"]["dedicated_golden_sample_review"] == "pending"
    assert payload["approval_field_status"]["decision_notes"] == "not_required"
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }
    assert payload["approval_action_item_count"] == 11
    assert {
        "blocker": "dedicated_golden_sample_review",
        "template_field": "- Dedicated ledger summary golden sample reviewed",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert payload["approval_action_items"][-1] == {
        "blocker": "candidate_boundary_acceptance",
        "template_field": "- Candidate-only boundary accepted",
        "required_value": "yes",
        "current_status": "pending",
    }


def test_ledger_pnl_business_owner_approval_checker_default_cli_allows_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), check=False)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False


def test_ledger_pnl_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), "--require-captured", check=False)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_ledger_pnl_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), "--require-captured", check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_action_items"] == []
    assert payload["approval_action_item_count"] == 0
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["proves_page_execution"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"


def test_ledger_pnl_business_owner_approval_checker_requires_no_certification_effect(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(
        _filled_template_text().replace("- `certification_effect=none`\n", ""),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_effect_boundary",
    ]
    assert payload["approval_field_status"]["certification_effect"] == "missing"
    assert {
        "blocker": "certification_effect_boundary",
        "template_field": "- `certification_effect=none`",
        "required_value": "none",
        "current_status": "missing",
    } in payload["approval_action_items"]


def test_ledger_pnl_business_owner_approval_checker_rejects_placeholder_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(
        TEMPLATE_TEXT.replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`"),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
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
            "dedicated_golden_sample_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "candidate_boundary_acceptance",
    ]


def test_ledger_pnl_business_owner_approval_checker_rejects_non_approve_decision(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(_filled_template_text(decision="request_changes"), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_decision", "decision_notes"]
    assert payload["approval_field_status"]["approval_decision"] == "invalid"
    assert payload["approval_field_status"]["decision_notes"] == "missing"


def test_ledger_pnl_business_owner_approval_checker_rejects_bad_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(_filled_template_text(approval_date="06/05/2026"), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_date"]


def test_ledger_pnl_business_owner_approval_checker_rejects_formal_use_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Formal use allowed: `formal_use_allowed=false`",
            "Formal use allowed: `formal_use_allowed=true`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
    assert payload["remaining_blockers"] == ["business_owner_approval", "formal_use_promotion_boundary"]


def test_ledger_pnl_business_owner_approval_checker_rejects_closure_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Closure approved: `closure_approved=false`",
            "Closure approved: `closure_approved=true`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["closure_approved"] is True
    assert payload["remaining_blockers"] == ["business_owner_approval", "closure_promotion_boundary"]


def test_ledger_pnl_business_owner_approval_checker_rejects_wrong_owner_evidence_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "ledger-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`",
            "Reviewed owner evidence packet: `docs/pnl/other-owner-evidence-packet.md`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "reviewed_owner_evidence_packet"]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_ledger_pnl_business_owner_approval_checker_rejects_missing_review_packets(
    tmp_path: Path,
) -> None:
    template = tmp_path / "docs" / "pnl" / "ledger-pnl-business-owner-approval-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_signoff_packet",
        "reviewed_governance_audit_packet",
        "reviewed_owner_evidence_packet",
    ]
    assert payload["approval_field_status"]["reviewed_signoff_packet"] == "missing_artifact"
    assert payload["approval_field_status"]["reviewed_governance_audit_packet"] == "missing_artifact"
    assert payload["approval_field_status"]["reviewed_owner_evidence_packet"] == "missing_artifact"
