from __future__ import annotations

from pathlib import Path

from scripts.check_pnl_attribution_business_owner_approval import build_status


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs" / "pnl" / "pnl-attribution-sign-off-packet.md"
APPROVAL_TEMPLATE = ROOT / "docs" / "pnl" / "pnl-attribution-business-owner-approval-template.md"
AUDIT_PACKET = ROOT / "docs" / "pnl" / "pnl-attribution-governance-audit-packet.md"
OWNER_EVIDENCE_PACKET = ROOT / "docs" / "pnl" / "pnl-attribution-owner-evidence-packet.md"


def test_pnl_attribution_signoff_packet_preserves_candidate_boundary() -> None:
    text = PACKET.read_text(encoding="utf-8")

    assert "# PnL Attribution Sign-Off Packet" in text
    assert "PAGE-PNL-ATTR-WB-001" in text
    assert "`pnl-attribution`" in text
    assert "`/api/pnl-attribution/volume-rate`" in text
    assert "`candidate_or_pending`" in text
    assert "`formal_use_allowed=false`" in text
    assert "`closure_approved=false`" in text
    assert "`data/governance/cache_manifest.jsonl:5403`" in text
    assert "`GS-PNL-ATTR-WB-A`" in text
    assert "Owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`" in text
    assert "Evidence references attached for reviewer confirmation: `ui_api_payload_review`, `live_smoke_evidence_review`" in text
    assert "`ui_api_payload_review`" in text
    assert "`live_smoke_evidence_review`" in text
    assert "`business_owner_approval`" in text
    assert "Business owner approval captured: `false`" in text
    assert "Business owner approval status: `pending`" in text
    assert "Business owner approval blockers: `business_owner_approval, business_owner_name, business_owner_role, approval_decision, approval_date, business_owner_signature, governance_record_review, golden_sample_review, ui_api_payload_review, live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`" in text
    assert "## Evidence Scope" in text
    assert "- `approves_metric_or_page=false`" in text
    assert "- `writes_governance_records=false`" in text
    assert "- `proves_page_execution=false`" in text
    assert "- `captures_business_owner_approval=false`" in text
    assert "## Business Owner Approval Action Items" in text
    assert "- Business owner name: `Business owner legal or operating name` (`missing`)" in text
    assert "- Approval decision: `approve` (`missing`)" in text
    assert "- Verification commands rerun before approval: `yes` (`pending`)" in text
    assert "- Candidate-only boundary accepted: `yes` (`pending`)" in text
    assert "- - Candidate-only boundary accepted" not in text
    assert "Do not promote this page to formal PnL truth." in text
    assert "Do not replace `/api/pnl/overview`." in text
    assert "Do not merge with `/ui/pnl/attribution`." in text
    assert "Advanced/Campisi full-surface closure remains out of scope." in text


def test_pnl_attribution_signoff_packet_lists_verification_evidence() -> None:
    text = PACKET.read_text(encoding="utf-8")

    assert "Commands freshly verified for this candidate sign-off packet:" in text
    assert "Business-owner review still required before approval can be captured:" in text
    assert "Commands still required before business-owner approval can be captured:" not in text
    assert (
        "python -m pytest tests/test_codex_page_readiness_gate.py "
        "tests/test_pnl_attribution_business_owner_approval_status.py "
        "tests/test_pnl_attribution_signoff_packet.py "
        "tests/test_pnl_attribution_governance_record.py "
        "tests/test_golden_samples_capture_ready.py -q"
    ) in text
    assert "python -m pytest tests/test_project_mcp_servers.py -q" in text
    assert (
        "python -m ruff check scripts/mcp/moss_project_mcp.py "
        "scripts/check_pnl_attribution_business_owner_approval.py "
        "scripts/codex_page_readiness.py "
        "scripts/emit_pnl_attribution_governance_record.py"
    ) in text
    assert "python scripts/check_pnl_attribution_business_owner_approval.py" in text
    assert "python scripts/check_pnl_attribution_business_owner_approval.py --require-captured" in text
    assert "scripts\\codex-page-smoke.ps1 -PageSlug pnl-attribution" in text
    assert "scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run" in text
    assert "scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run" in text
    assert "scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured" in text
    assert "scripts\\codex-page-readiness.ps1 -All -RequireApprovalCaptured" in text
    assert "Review current API payload and visible UI state." in text
    assert "Confirm live smoke/browser evidence." in text
    assert "Complete/sign docs\\pnl\\pnl-attribution-business-owner-approval-template.md." in text
    assert "Current pnl-attribution governance chain: `71 passed`" in text
    assert "Current MCP evidence suite: `151 passed`" in text
    assert (
        "Current pnl-attribution page verification: `94 backend passed; 27 frontend passed; "
        "1 browser a11y smoke passed; typecheck passed; debt audit passed`"
    ) in text
    assert "Current pnl-attribution readiness run: `Page readiness gate passed`" in text
    assert "Strict approval gate: `expected failure while business_owner_approval_captured=false`" in text
    assert (
        "Page closure command status: `verification rerun complete; "
        "business-owner review and signature still pending`"
    ) in text
    assert "listed for follow-up; not executed by this packet" not in text
    assert "134 passed" not in text
    assert "136 passed" not in text
    assert "60 passed" not in text
    assert "61 passed" not in text
    assert "62 passed" not in text
    assert "63 passed" not in text
    assert "65 passed" not in text
    assert "137 passed" not in text
    assert "138 passed" not in text
    assert "139 passed" not in text
    assert "140 passed" not in text
    assert "68 passed" not in text
    assert "67 passed" not in text
    assert "150 passed" not in text
    assert "147 passed" not in text
    assert "146 passed" not in text
    assert "70 passed" not in text


def test_pnl_attribution_signoff_packet_includes_business_owner_handoff_state() -> None:
    text = PACKET.read_text(encoding="utf-8")

    assert "## Business Owner Handoff" in text
    assert "Handoff status: `ready_for_business_owner_review_pending_signature`" in text
    assert "Approval action item count: `11`" in text
    assert (
        "Approval template to complete: "
        "`docs/pnl/pnl-attribution-business-owner-approval-template.md`"
    ) in text
    assert (
        "This handoff does not capture approval, write governance records, "
        "prove page execution, or grant closure."
    ) in text
    assert (
        "Keep `formal_use_allowed=false` and `closure_approved=false` until "
        "business-owner approval is explicitly captured."
    ) in text


def test_pnl_attribution_business_owner_approval_template_is_pending_only() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    template = APPROVAL_TEMPLATE.read_text(encoding="utf-8")

    assert "`docs/pnl/pnl-attribution-business-owner-approval-template.md`" in packet
    assert "# PnL Attribution Business Owner Approval Template" in template
    assert "`PAGE-PNL-ATTR-WB-001`" in template
    assert "`pnl-attribution`" in template
    assert "`/api/pnl-attribution/volume-rate`" in template
    assert "`business_owner_approval`" in template
    assert "`approval_status=pending`" in template
    assert "`formal_use_allowed=false`" in template
    assert "`closure_approved=false`" in template
    assert "This template is not an approval until completed and signed by the business owner." in template
    assert "Do not promote this page to formal PnL truth." in template
    assert "## Evidence Scope" in template
    assert "- `approves_metric_or_page=false`" in template
    assert "- `writes_governance_records=false`" in template
    assert "- `proves_page_execution=false`" in template
    assert "- `captures_business_owner_approval=false`" in template
    assert "Business owner name: `<required>`" in template
    assert "Approval decision: `<approve | reject | request_changes>`" in template
    assert "Approval date: `<YYYY-MM-DD>`" in template
    assert "Business owner signature: `<required>`" in template
    assert "Reviewed owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`" in template


def test_pnl_attribution_approval_summaries_match_checker_output() -> None:
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
    ]

    signoff_packet = PACKET.read_text(encoding="utf-8")
    audit_packet = AUDIT_PACKET.read_text(encoding="utf-8")

    for line in expected_lines:
        assert line in signoff_packet
        assert line in audit_packet


def test_pnl_attribution_approval_action_items_match_checker_output() -> None:
    status = build_status(APPROVAL_TEMPLATE)
    expected_lines = [
        "## Business Owner Approval Action Items",
        *[
            (
                f"- {str(item['template_field']).lstrip('-').strip()}: "
                f"`{item['required_value']}` (`{item['current_status']}`)"
            )
            for item in status["approval_action_items"]
        ],
    ]

    signoff_packet = PACKET.read_text(encoding="utf-8")
    audit_packet = AUDIT_PACKET.read_text(encoding="utf-8")

    for line in expected_lines:
        assert line in signoff_packet
        assert line in audit_packet
    assert "- - Candidate-only boundary accepted" not in signoff_packet
    assert "- - Candidate-only boundary accepted" not in audit_packet
    assert "Evidence present for reviewer follow-up" not in signoff_packet
    assert "Evidence present:" not in audit_packet
    assert (
        "Evidence references attached for reviewer confirmation: "
        "`ui_api_payload_review, live_smoke_evidence_review`"
    ) in audit_packet


def test_pnl_attribution_packets_list_powershell_strict_approval_gate() -> None:
    signoff_packet = PACKET.read_text(encoding="utf-8")
    audit_packet = AUDIT_PACKET.read_text(encoding="utf-8")

    strict_gate = "scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured"
    batch_strict_gate = "scripts\\codex-page-readiness.ps1 -All -RequireApprovalCaptured"

    assert strict_gate in signoff_packet
    assert f"PowerShell readiness strict approval gate command: `{strict_gate}`" in audit_packet
    assert batch_strict_gate in signoff_packet
    assert f"PowerShell all-page readiness strict approval gate command: `{batch_strict_gate}`" in audit_packet


def test_pnl_attribution_packets_reference_owner_evidence_packet() -> None:
    signoff_packet = PACKET.read_text(encoding="utf-8")
    audit_packet = AUDIT_PACKET.read_text(encoding="utf-8")
    owner_packet = OWNER_EVIDENCE_PACKET.read_text(encoding="utf-8")

    owner_packet_path = "docs/pnl/pnl-attribution-owner-evidence-packet.md"
    assert f"Owner evidence packet: `{owner_packet_path}`" in signoff_packet
    assert f"Owner evidence packet: `{owner_packet_path}`" in audit_packet
    assert "# PnL Attribution Owner Evidence Packet" in owner_packet
    assert "Golden sample boundary: `primary_workbench_dto_only`" in owner_packet
    assert "Governance record write status: `not_requested`" in owner_packet
    assert "This packet does not approve page closure" in owner_packet


def test_pnl_attribution_audit_packet_lists_rerun_follow_up_without_approval() -> None:
    text = AUDIT_PACKET.read_text(encoding="utf-8")

    assert "## Required Follow-up" in text
    assert "Review current API payload and visible UI state." in text
    assert "Confirm live smoke/browser evidence before signing." in text
    assert (
        "Page smoke rerun: `scripts\\codex-page-smoke.ps1 -PageSlug pnl-attribution` (`passed`)"
        in text
    )
    assert (
        "Page verification rerun: `scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run` (`passed`)"
        in text
    )
    assert (
        "Page readiness rerun: `scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run` (`passed`)"
        in text
    )
    assert (
        "Page closure command status: `verification rerun complete; "
        "business-owner review and signature still pending`"
    ) in text
    assert "Collect business-owner approval before any closure claim." in text
    assert "Attach live smoke/browser evidence." not in text
    assert "Run page smoke: `scripts\\codex-page-smoke.ps1 -PageSlug pnl-attribution`" not in text
    assert "Run page verification: `scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run`" not in text
    assert "listed for follow-up; not executed by this packet" not in text
