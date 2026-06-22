from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.stock_analysis_owner_evidence_packet import build_packet


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stock_analysis_owner_evidence_packet.py"
SIGNOFF_PACKET = ROOT / "docs" / "pnl" / "stock-analysis-sign-off-packet.md"
GOVERNANCE_AUDIT_PACKET = ROOT / "docs" / "pnl" / "stock-analysis-governance-audit-packet.md"
OWNER_EVIDENCE_PACKET = ROOT / "docs" / "pnl" / "stock-analysis-owner-evidence-packet.md"
OWNER_SIGNOFF_RUNBOOK = ROOT / "docs" / "pnl" / "stock-analysis-owner-signoff-runbook.md"
OWNER_QA_CHECKLIST = ROOT / "docs" / "pnl" / "stock-analysis-owner-qa-checklist.md"


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


def test_stock_analysis_owner_evidence_packet_preserves_observational_boundary() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "stock_analysis_owner_evidence_packet"
    assert packet["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
    assert packet["page_slug"] == "stock-analysis"
    assert packet["route"] == "/stock-analysis"
    assert packet["primary_api"] == "/ui/market-data/livermore"
    assert packet["business_contract_status"] == "evidence-pending"
    assert packet["business_contract_certified"] is False
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["approval_status"] == "pending"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert packet["approval_action_item_count"] == 11
    assert packet["golden_sample_boundary"] == "observational_page_dto_capture_ready_pending_approval"
    assert packet["dedicated_golden_sample_id"] == "GS-STOCK-ANALYSIS-OBS-A"
    assert packet["route_specific_evidence_scope"] == "stock_analysis_observational_livermore_dto_only"
    assert packet["trading_instruction_allowed"] is False
    assert packet["execution_approval_allowed"] is False
    assert packet["allocation_advice_allowed"] is False
    assert packet["position_change_command_allowed"] is False
    assert packet["formal_stock_metric_promotion_allowed"] is False
    assert packet["observational_boundary_status"] == "no_trading_instruction_boundary_pending_owner_acceptance"
    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["governance_validation_status"] == "direct_records_ready_for_audit_review"
    assert packet["configured_table_names"] == [
        "livermore_position_snapshot",
        "livermore_candidate_history",
        "choice_stock_daily_observation",
        "fact_livermore_gate_supplement_daily",
    ]
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "validates_required_fields": True,
    }
    assert "trading instructions" in packet["out_of_scope_surfaces"]
    assert "not_trading_instruction_review" in packet["remaining_blockers"]
    assert packet["evidence_anchors"]["owner_signoff_runbook"] == (
        "docs/pnl/stock-analysis-owner-signoff-runbook.md"
    )
    assert packet["evidence_anchors"]["owner_qa_checklist"] == (
        "docs/pnl/stock-analysis-owner-qa-checklist.md"
    )


def test_stock_analysis_owner_evidence_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "packet.md"

    returncode, payload = _run_packet("--output", str(output_path))

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["business_contract_certified"] is False
    assert payload["approval_action_item_count"] == 11
    assert payload["governance_record_write_status"] == "not_requested"
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"

    text = output_path.read_text(encoding="utf-8")
    assert "# Stock Analysis Owner Evidence Packet" in text
    assert "Business contract status: `evidence-pending`" in text
    assert "Formal use allowed: `formal_use_allowed=false`" in text
    assert "Golden sample boundary: `observational_page_dto_capture_ready_pending_approval`" in text
    assert "Dedicated golden sample: `GS-STOCK-ANALYSIS-OBS-A`" in text
    assert "Route-specific evidence scope: `stock_analysis_observational_livermore_dto_only`" in text
    assert "Trading instruction allowed: `false`" in text
    assert "Execution approval allowed: `false`" in text
    assert "Allocation advice allowed: `false`" in text
    assert "Position-change command allowed: `false`" in text
    assert "Formal stock metric promotion allowed: `false`" in text
    assert (
        "Observational boundary status: "
        "`no_trading_instruction_boundary_pending_owner_acceptance`"
    ) in text
    assert "Governance record write status: `not_requested`" in text
    assert "Governance validation status: `direct_records_ready_for_audit_review`" in text
    assert "This packet does not approve page closure" in text
    assert "- `certification_effect=none`" in text
    assert "- owner_signoff_runbook: `docs/pnl/stock-analysis-owner-signoff-runbook.md`" in text
    assert "- owner_qa_checklist: `docs/pnl/stock-analysis-owner-qa-checklist.md`" in text
    assert "No-trading-instruction boundary accepted: `yes` (`pending`)" in text


def test_stock_analysis_owner_evidence_packet_surfaces_owner_runbook_anchor() -> None:
    owner_packet = OWNER_EVIDENCE_PACKET.read_text(encoding="utf-8")

    assert "- owner_signoff_runbook: `docs/pnl/stock-analysis-owner-signoff-runbook.md`" in owner_packet
    assert "- owner_qa_checklist: `docs/pnl/stock-analysis-owner-qa-checklist.md`" in owner_packet


def test_stock_analysis_signoff_and_audit_packets_surface_no_certification_scope() -> None:
    signoff_packet = SIGNOFF_PACKET.read_text(encoding="utf-8")
    audit_packet = GOVERNANCE_AUDIT_PACKET.read_text(encoding="utf-8")

    for text in (signoff_packet, audit_packet):
        assert "## Evidence Scope" in text
        assert "- `approves_metric_or_page=false`" in text
        assert "- `writes_governance_records=false`" in text
        assert "- `proves_page_execution=false`" in text
        assert "- `captures_business_owner_approval=false`" in text
        assert "- `certification_effect=none`" in text


def test_stock_analysis_owner_signoff_runbook_preserves_observational_boundary() -> None:
    text = OWNER_SIGNOFF_RUNBOOK.read_text(encoding="utf-8")

    assert "It does not approve closure by itself." in text
    assert "`GAP-STOCK-ANALYSIS-PAGE`" in text
    assert "`/ui/market-data/livermore`" in text
    assert "`docs/pnl/stock-analysis-business-owner-approval-template.md`" in text
    assert "`docs/pnl/stock-analysis-owner-evidence-packet.md`" in text
    assert "`docs/pnl/stock-analysis-sign-off-packet.md`" in text
    assert "`docs/pnl/stock-analysis-governance-audit-packet.md`" in text
    assert "`docs/pnl/stock-analysis-owner-qa-checklist.md`" in text
    assert "Keep `formal_use_allowed=false`." in text
    assert "Keep `closure_approved=false`." in text
    assert "Keep `certification_effect=none`." in text
    assert "Do not create `PAGE-STOCK-*` page contracts." in text
    assert "Do not create or promote `MTR-STOCK-*` metric approvals." in text
    assert "formal stock-analysis truth" in text
    assert "trading instructions" in text
    assert "execution approvals" in text
    assert "allocation advice" in text
    assert "position-change commands" in text
    assert "dry-run governance output" in text
    assert "`GS-STOCK-ANALYSIS-OBS-A`" in text
    assert "captured-awaiting-approval" in text
    assert "python scripts/codex_page_readiness.py --page-slug stock-analysis" in text
    assert "python scripts/check_stock_analysis_business_owner_approval.py --require-captured" in text
    assert "scripts/codex-verify-page.ps1 -PageSlug stock-analysis -Run" in text


def test_stock_analysis_owner_qa_checklist_preserves_unsigned_boundary() -> None:
    text = OWNER_QA_CHECKLIST.read_text(encoding="utf-8")

    assert "# Stock Analysis Owner QA Checklist" in text
    assert "`GAP-STOCK-ANALYSIS-PAGE`" in text
    assert "`7f67fdc39`" in text
    assert "`formal_use_allowed=false`" in text
    assert "`closure_approved=false`" in text
    assert "`market_state=OVERHEAT`" in text
    assert "`fresh_trend_watchlist.candidate_count=20`" in text
    assert "`factor_screen_candidates.candidate_count=30`" in text
    assert "`GS-STOCK-ANALYSIS-OBS-A`" in text
    assert "no trading instruction" in text.lower()
    assert "`certification_effect=none`" in text
