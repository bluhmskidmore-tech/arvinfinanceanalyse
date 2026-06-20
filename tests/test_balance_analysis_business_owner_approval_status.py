from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_balance_analysis_business_owner_approval import build_status


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_balance_analysis_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md"
LIVE_SMOKE_ARTIFACT = ROOT / "docs" / "audits" / "2026-06-07-balance-analysis-live-smoke-evidence.md"
LIVE_SMOKE_ARTIFACT_REF = "docs/audits/2026-06-07-balance-analysis-live-smoke-evidence.md"


def _filled_template_text(
    *,
    decision: str = "approve",
    approval_date: str = "2026-06-07",
) -> str:
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Balance Analysis Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Finance Control Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Balance Analysis Owner`")
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace(
            "- Golden sample `GS-BAL-OVERVIEW-A` reviewed: `<yes | no>`",
            "- Golden sample `GS-BAL-OVERVIEW-A` reviewed: `yes`",
        )
        .replace("- UI/API payload evidence reviewed: `<yes | no>`", "- UI/API payload evidence reviewed: `yes`")
        .replace("- Live smoke evidence reviewed: `<yes | no>`", "- Live smoke evidence reviewed: `yes`")
        .replace(
            "- Verification commands rerun before approval: `<yes | no>`",
            "- Verification commands rerun before approval: `yes`",
        )
        .replace("- Formal balance boundary accepted: `<yes | no>`", "- Formal balance boundary accepted: `yes`")
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


def test_balance_analysis_owner_docs_make_template_canonical_and_keep_write_operator_only() -> None:
    owner_packet = (ROOT / "docs" / "pnl" / "balance-analysis-owner-evidence-packet.md").read_text(
        encoding="utf-8"
    )
    audit_packet = (ROOT / "docs" / "pnl" / "balance-analysis-governance-audit-packet.md").read_text(
        encoding="utf-8"
    )
    signoff_packet = (ROOT / "docs" / "pnl" / "balance-analysis-sign-off-packet.md").read_text(
        encoding="utf-8"
    )
    template_text = TEMPLATE.read_text(encoding="utf-8")

    assert "canonical owner-state artifact" in template_text
    assert "canonical owner-state artifact" in owner_packet
    assert "operator-only" in owner_packet
    assert "operator-only" in audit_packet
    assert "not part of this closure round" in owner_packet
    assert "not part of this closure round" in audit_packet
    assert "11 pending owner actions" in audit_packet
    assert "audit-input summary of the same canonical 11-action list" in audit_packet
    assert "not a shorter replacement checklist" in audit_packet
    assert "GS-BAL-OVERVIEW-A" in signoff_packet
    assert "Live smoke evidence" in signoff_packet
    assert "required pre-signature review steps" in signoff_packet
    assert "subset of the same 11 pending owner actions" in signoff_packet
    assert "business owner name, role, decision, date, and signature actions remain pending in the canonical template" in signoff_packet


def test_balance_analysis_owner_docs_link_durable_live_smoke_artifact() -> None:
    owner_packet = (ROOT / "docs" / "pnl" / "balance-analysis-owner-evidence-packet.md").read_text(
        encoding="utf-8"
    )
    audit_packet = (ROOT / "docs" / "pnl" / "balance-analysis-governance-audit-packet.md").read_text(
        encoding="utf-8"
    )
    signoff_packet = (ROOT / "docs" / "pnl" / "balance-analysis-sign-off-packet.md").read_text(
        encoding="utf-8"
    )
    template_text = TEMPLATE.read_text(encoding="utf-8")

    assert LIVE_SMOKE_ARTIFACT.is_file()
    artifact_text = LIVE_SMOKE_ARTIFACT.read_text(encoding="utf-8")

    for packet_text in (owner_packet, audit_packet, signoff_packet, template_text):
        assert LIVE_SMOKE_ARTIFACT_REF in packet_text
        assert "durable balance-analysis live smoke artifact path is not linked" not in packet_text

    assert "scripts/codex-page-smoke.ps1 -PageSlug balance-analysis -CheckLive" in artifact_text
    assert "execution_status: pass" in artifact_text
    assert "frontend_route: /balance-analysis" in artifact_text
    assert "primary_api: /ui/balance-analysis/overview" in artifact_text
    assert "business_owner_approval_captured=false" in artifact_text
    assert "closure_approved=false" in artifact_text
    assert "does not approve closure" in artifact_text
    assert "Result on original capture: blocked before page-specific checks completed." in artifact_text
    assert "tests/test_project_mcp_servers.py" in artifact_text
    assert "9 failed" in artifact_text
    assert "ready-for-audit-review rows" in artifact_text
    assert "record-gap routing" in artifact_text
    assert "test_balance_analysis_read_surface_allows_development_fallback_without_explicit_scope" in artifact_text
    assert "received HTTP `403`" in artifact_text
    assert "Current verification update on 2026-06-10" in artifact_text
    assert "scripts/codex-verify-page.ps1 -PageSlug balance-analysis -Run` passed" in artifact_text
    assert "MCP contract tests: `199 passed`" in artifact_text
    assert "Balance-analysis frontend tests: `25 passed`" in artifact_text
    assert "does not treat the 2026-06-10 full page verification pass as owner approval" in artifact_text
    assert "live smoke action stays pending until the owner marks" in artifact_text


def test_balance_analysis_owner_docs_expose_signoff_runbook_without_approval() -> None:
    owner_packet = (ROOT / "docs" / "pnl" / "balance-analysis-owner-evidence-packet.md").read_text(
        encoding="utf-8"
    )
    template_text = TEMPLATE.read_text(encoding="utf-8")
    runbook = ROOT / "docs" / "pnl" / "balance-analysis-owner-signoff-runbook.md"
    runbook_text = runbook.read_text(encoding="utf-8")

    assert runbook.is_file()
    assert "owner_signoff_runbook: `docs/pnl/balance-analysis-owner-signoff-runbook.md`" in owner_packet
    assert "Owner signoff runbook: `docs/pnl/balance-analysis-owner-signoff-runbook.md`" in template_text
    assert "Keep `formal_use_allowed=true`" in runbook_text
    assert "Keep `closure_approved=false`" in runbook_text
    assert "it is not owner approval" in owner_packet
    assert "does not set `closure_approved=true`" in runbook_text


def test_balance_analysis_business_owner_approval_checker_reports_pending_template() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), check=False)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)

    assert payload["page_id"] == "PAGE-BALANCE-001"
    assert payload["page_slug"] == "balance-analysis"
    assert payload["primary_api"] == "/ui/balance-analysis/overview"
    assert payload["approval_check"] == "business_owner_approval"
    assert payload["approval_status"] == "pending"
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
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
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "formal_balance_boundary_acceptance",
    ]
    assert payload["approval_field_status"]["business_owner_name"] == "missing"
    assert payload["approval_field_status"]["reviewed_signoff_packet"] == "valid"
    assert payload["approval_field_status"]["reviewed_governance_audit_packet"] == "valid"
    assert payload["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert payload["approval_field_status"]["golden_sample_review"] == "pending"
    assert payload["approval_field_status"]["formal_balance_boundary_acceptance"] == "pending"
    assert payload["approval_field_status"]["decision_notes"] == "not_required"
    assert payload["approval_field_status"]["formal_use_allowed"] == "valid"
    assert payload["approval_field_status"]["closure_approved"] == "valid"
    assert payload["approval_action_item_count"] == 11
    assert {
        "blocker": "formal_balance_boundary_acceptance",
        "template_field": "- Formal balance boundary accepted",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }


def test_balance_analysis_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), "--require-captured", check=False)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_balance_analysis_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(_filled_template_text(), encoding="utf-8")
    for artifact in (
        "balance-analysis-sign-off-packet.md",
        "balance-analysis-governance-audit-packet.md",
        "balance-analysis-owner-evidence-packet.md",
    ):
        (template.parent / artifact).write_text("# packet\n", encoding="utf-8")

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


def test_balance_analysis_business_owner_approval_checker_rejects_placeholder_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "balance-analysis-approval-template.md"
    template.write_text(
        TEMPLATE.read_text(encoding="utf-8").replace(
            "Approval status: `approval_status=pending`",
            "Approval status: `approval_status=approved`",
        ),
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
        "formal_balance_boundary_acceptance",
    ]
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False


def test_balance_analysis_business_owner_approval_checker_rejects_bad_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(_filled_template_text(approval_date="06/07/2026"), encoding="utf-8")
    for artifact in (
        "balance-analysis-sign-off-packet.md",
        "balance-analysis-governance-audit-packet.md",
        "balance-analysis-owner-evidence-packet.md",
    ):
        (template.parent / artifact).write_text("# packet\n", encoding="utf-8")

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_date"]


def test_balance_analysis_business_owner_approval_checker_rejects_closure_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        _filled_template_text().replace(
            "Closure approved: `closure_approved=false`",
            "Closure approved: `closure_approved=true`",
        ),
        encoding="utf-8",
    )
    for artifact in (
        "balance-analysis-sign-off-packet.md",
        "balance-analysis-governance-audit-packet.md",
        "balance-analysis-owner-evidence-packet.md",
    ):
        (template.parent / artifact).write_text("# packet\n", encoding="utf-8")

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["closure_approved"] is True
    assert payload["remaining_blockers"] == ["business_owner_approval", "closure_promotion_boundary"]


def test_balance_analysis_business_owner_approval_checker_rejects_wrong_owner_evidence_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        _filled_template_text().replace(
            "Reviewed owner evidence packet: `docs/pnl/balance-analysis-owner-evidence-packet.md`",
            "Reviewed owner evidence packet: `docs/pnl/other-owner-evidence-packet.md`",
        ),
        encoding="utf-8",
    )
    for artifact in (
        "balance-analysis-sign-off-packet.md",
        "balance-analysis-governance-audit-packet.md",
        "balance-analysis-owner-evidence-packet.md",
    ):
        (template.parent / artifact).write_text("# packet\n", encoding="utf-8")

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "reviewed_owner_evidence_packet"]


def test_balance_analysis_business_owner_approval_checker_rejects_missing_review_packets(
    tmp_path: Path,
) -> None:
    template = tmp_path / "docs" / "pnl" / "balance-analysis-business-owner-approval-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(_filled_template_text(), encoding="utf-8")

    payload = build_status(template)

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
