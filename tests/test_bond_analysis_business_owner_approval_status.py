from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_bond_analysis_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "bond-analysis-business-owner-approval-template.md"
PLAYBOOK = ROOT / "docs" / "plans" / "2026-06-10-bond-analysis-desktop-100-playbook.md"

TEMPLATE_TEXT = """# Bond Analysis Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `PAGE-BOND-ANALYSIS-001`
Page slug: `bond-analysis`
Primary API: `/api/bond-analytics/action-attribution`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote fixed-income action-attribution, DV01, duration, KRD, yield/YTM, credit-spread, holdings, or accounting-class values to formal metric truth.
- Do not borrow `PAGE-BOND-001`, `/bond-dashboard`, `GS-BOND-HEADLINE-A`, or `MTR-BOND-001` through `MTR-BOND-004`.
- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` is captured-awaiting-approval and does not approve this page for formal use.

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
Reviewed sign-off packet: `docs/pnl/bond-analysis-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/bond-analysis-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/bond-analysis-owner-evidence-packet.md`
Reviewed fixed-income convention decision draft: `docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`
Owner signoff runbook: `docs/pnl/bond-analysis-owner-signoff-runbook.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed: `<yes | no>`
- Fixed-income convention decision draft reviewed: `<yes | no>`
- Fixed-income units/sign/date rules reviewed: `<yes | no>`
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
    approval_date: str = "2026-06-06",
) -> str:
    return (
        TEMPLATE_TEXT.replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Bond Analysis Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Fixed Income Control Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Bond Analysis Owner`")
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace(
            "- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed: `<yes | no>`",
            "- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed: `yes`",
        )
        .replace(
            "- Fixed-income convention decision draft reviewed: `<yes | no>`",
            "- Fixed-income convention decision draft reviewed: `yes`",
        )
        .replace(
            "- Fixed-income units/sign/date rules reviewed: `<yes | no>`",
            "- Fixed-income units/sign/date rules reviewed: `yes`",
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


def test_bond_analysis_business_owner_approval_checker_reports_pending_template() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), check=False)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)

    assert payload["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert payload["page_slug"] == "bond-analysis"
    assert payload["primary_api"] == "/api/bond-analytics/action-attribution"
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
        "golden_sample_review",
        "fixed_income_convention_review",
        "fixed_income_rule_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "candidate_boundary_acceptance",
    ]
    assert payload["approval_action_item_count"] == 12
    assert {
        "blocker": "golden_sample_review",
        "template_field": "- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert payload["approval_field_status"]["fixed_income_convention_review"] == "pending"
    assert payload["approval_field_status"]["fixed_income_rule_review"] == "pending"
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }


def test_bond_analysis_business_owner_approval_template_references_owner_runbook() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "Reviewed sign-off packet: `docs/pnl/bond-analysis-sign-off-packet.md`" in text
    assert (
        "Reviewed governance audit packet: `docs/pnl/bond-analysis-governance-audit-packet.md`"
        in text
    )
    assert "Reviewed owner evidence packet: `docs/pnl/bond-analysis-owner-evidence-packet.md`" in text
    assert (
        "Reviewed fixed-income convention decision draft: "
        "`docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`"
    ) in text
    assert "Owner signoff runbook: `docs/pnl/bond-analysis-owner-signoff-runbook.md`" in text
    assert "Latest verification evidence is summarized in the sign-off packet" in text
    assert "Full page verification: `scripts/codex-verify-page.ps1 -PageSlug bond-analysis -Run`" in text
    assert "Golden sample capture-ready verification: `python -m pytest tests/test_golden_samples_capture_ready.py -q`" in text
    assert (
        "Owner boundary verification: `python -m pytest "
        "tests/test_bond_analysis_business_owner_approval_status.py "
        "tests/test_golden_samples_capture_ready.py -q`"
    ) in text
    assert "owner approval remains fail-closed until this template is completed" in text


def test_bond_analysis_desktop_playbook_owner_handoff_stays_fail_closed() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")
    start = text.index("## Owner Handoff Status")
    end = text.index("## Current Gap List", start)
    section = text[start:end]

    assert "Desktop candidate implementation is ready for owner handoff." in section
    assert "Business-owner approval is not captured." in section
    assert (
        "`formal_use_allowed=false`, `closure_approved=false`, and "
        "`certification_effect=none` must remain in force."
    ) in section
    assert (
        "`python scripts/check_bond_analysis_business_owner_approval.py --require-captured` "
        "must pass before anyone says owner approval is captured."
    ) in section
    assert "mobile layout, backend metric redesign, `/bond-dashboard` certification evidence" in section
    assert "formal_use_allowed=true" not in section
    assert "closure_approved=true" not in section


def test_bond_analysis_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), "--require-captured", check=False)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_bond_analysis_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "bond-analysis-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), "--require-captured", check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_action_items"] == []
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"


def test_bond_analysis_business_owner_approval_checker_requires_no_certification_effect(
    tmp_path: Path,
) -> None:
    template = tmp_path / "bond-analysis-approval-template.md"
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


def test_bond_analysis_business_owner_approval_checker_requires_fixed_income_decision_draft(
    tmp_path: Path,
) -> None:
    template = tmp_path / "bond-analysis-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed fixed-income convention decision draft: "
            "`docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`",
            "Reviewed fixed-income convention decision draft: `docs/pnl/other-decision-draft.md`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_fixed_income_decision_draft",
    ]
    assert payload["approval_field_status"]["reviewed_fixed_income_decision_draft"] == "invalid"
    assert {
        "blocker": "reviewed_fixed_income_decision_draft",
        "template_field": "Reviewed fixed-income convention decision draft",
        "required_value": "docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md",
        "current_status": "invalid",
    } in payload["approval_action_items"]


def test_bond_analysis_business_owner_approval_checker_rejects_bad_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "bond-analysis-approval-template.md"
    template.write_text(_filled_template_text(approval_date="06/06/2026"), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_date"]
