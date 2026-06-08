from __future__ import annotations

from pathlib import Path

from scripts.check_ledger_pnl_business_owner_approval import build_status


ROOT = Path(__file__).resolve().parents[1]
SIGNOFF_PACKET = ROOT / "docs" / "pnl" / "ledger-pnl-sign-off-packet.md"
AUDIT_PACKET = ROOT / "docs" / "pnl" / "ledger-pnl-governance-audit-packet.md"
OWNER_EVIDENCE_PACKET = ROOT / "docs" / "pnl" / "ledger-pnl-owner-evidence-packet.md"
APPROVAL_TEMPLATE = ROOT / "docs" / "pnl" / "ledger-pnl-business-owner-approval-template.md"


def test_ledger_pnl_signoff_packet_preserves_candidate_boundary() -> None:
    text = SIGNOFF_PACKET.read_text(encoding="utf-8")

    assert "# Ledger PnL Sign-Off Packet" in text
    assert "PAGE-LEDGER-PNL-001" in text
    assert "`ledger-pnl`" in text
    assert "`/api/ledger-pnl/summary`" in text
    assert "`candidate_or_pending`" in text
    assert "`formal_use_allowed=false`" in text
    assert "`closure_approved=false`" in text
    assert "Owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`" in text
    assert "Business owner approval captured: `false`" in text
    assert "Business owner approval status: `pending`" in text
    assert (
        "Business owner approval blockers: `business_owner_approval, business_owner_name, "
        "business_owner_role, approval_decision, approval_date, business_owner_signature, "
        "governance_record_review, dedicated_golden_sample_review, ui_api_payload_review, "
        "live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`"
    ) in text
    assert "- `approves_metric_or_page=false`" in text
    assert "- `writes_governance_records=false`" in text
    assert "- `proves_page_execution=false`" in text
    assert "- `captures_business_owner_approval=false`" in text
    assert "Do not promote `MTR-LPN-001` through `MTR-LPN-003` to formal use." in text
    assert "Dedicated ledger summary golden sample `GS-LEDGER-PNL-SUMMARY-A` is captured-awaiting-approval" in text


def test_ledger_pnl_approval_packets_match_checker_output() -> None:
    status = build_status(APPROVAL_TEMPLATE)
    expected_lines = [
        f"Business owner approval captured: `{str(status['business_owner_approval_captured']).lower()}`",
        f"Business owner approval status: `{status['approval_status']}`",
        "Business owner approval blockers: "
        f"`{', '.join(str(blocker) for blocker in status['remaining_blockers'])}`",
        f"- `approves_metric_or_page={str(status['evidence_scope']['approves_metric_or_page']).lower()}`",
        f"- `writes_governance_records={str(status['evidence_scope']['writes_governance_records']).lower()}`",
        f"- `proves_page_execution={str(status['evidence_scope']['proves_page_execution']).lower()}`",
        (
            "- `captures_business_owner_approval="
            f"{str(status['evidence_scope']['captures_business_owner_approval']).lower()}`"
        ),
        f"- `certification_effect={status['evidence_scope']['certification_effect']}`",
        "## Business Owner Approval Action Items",
        *[
            (
                f"- {str(item['template_field']).lstrip('-').strip()}: "
                f"`{item['required_value']}` (`{item['current_status']}`)"
            )
            for item in status["approval_action_items"]
        ],
    ]

    signoff = SIGNOFF_PACKET.read_text(encoding="utf-8")
    audit = AUDIT_PACKET.read_text(encoding="utf-8")

    for line in expected_lines:
        assert line in signoff
        assert line in audit
    assert "- - Dedicated ledger summary golden sample reviewed" not in signoff
    assert "- - Dedicated ledger summary golden sample reviewed" not in audit


def test_ledger_pnl_packets_reference_owner_evidence_packet() -> None:
    signoff = SIGNOFF_PACKET.read_text(encoding="utf-8")
    audit = AUDIT_PACKET.read_text(encoding="utf-8")
    owner = OWNER_EVIDENCE_PACKET.read_text(encoding="utf-8")

    owner_packet_path = "docs/pnl/ledger-pnl-owner-evidence-packet.md"
    assert f"Owner evidence packet: `{owner_packet_path}`" in signoff
    assert f"Owner evidence packet: `{owner_packet_path}`" in audit
    assert "# Ledger PnL Owner Evidence Packet" in owner
    assert "Golden sample boundary: `dedicated_summary_capture_ready_pending_approval`" in owner
    assert "Dedicated golden sample: `GS-LEDGER-PNL-SUMMARY-A`" in owner
    assert "Governance record write status: `not_requested`" in owner
    assert "This packet does not approve page closure" in owner


def test_ledger_pnl_business_owner_approval_template_references_review_packets() -> None:
    template = APPROVAL_TEMPLATE.read_text(encoding="utf-8")

    assert "Reviewed sign-off packet: `docs/pnl/ledger-pnl-sign-off-packet.md`" in template
    assert (
        "Reviewed governance audit packet: `docs/pnl/ledger-pnl-governance-audit-packet.md`"
        in template
    )
    assert "Reviewed owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`" in template
