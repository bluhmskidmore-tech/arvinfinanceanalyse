from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.bond_analysis_owner_evidence_packet import (
    build_packet,
    render_audit_markdown,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bond_analysis_owner_evidence_packet.py"
SIGNOFF_PACKET = ROOT / "docs" / "pnl" / "bond-analysis-sign-off-packet.md"
GOVERNANCE_AUDIT_PACKET = ROOT / "docs" / "pnl" / "bond-analysis-governance-audit-packet.md"
OWNER_EVIDENCE_PACKET = ROOT / "docs" / "pnl" / "bond-analysis-owner-evidence-packet.md"
OWNER_SIGNOFF_RUNBOOK = ROOT / "docs" / "pnl" / "bond-analysis-owner-signoff-runbook.md"
LIVE_SMOKE_EVIDENCE_ARTIFACT = (
    "docs/audits/2026-06-09-bond-analysis-live-smoke-evidence.md"
)
LIVE_SMOKE_COMMAND = "scripts/codex-page-smoke.ps1 -PageSlug bond-analysis"


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


def test_bond_analysis_owner_evidence_packet_preserves_candidate_boundary() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "bond_analysis_owner_evidence_packet"
    assert packet["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert packet["page_slug"] == "bond-analysis"
    assert packet["route"] == "/bond-analysis"
    assert packet["primary_api"] == "/api/bond-analytics/action-attribution"
    assert packet["business_contract_status"] == "evidence-pending"
    assert packet["business_contract_certified"] is False
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["approval_status"] == "pending"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert packet["approval_action_item_count"] == 12
    assert packet["golden_sample_boundary"] == "action_attribution_capture_ready_pending_approval"
    assert packet["dedicated_golden_sample_id"] == "GS-BOND-ANALYSIS-ACTION-ATTR-A"
    assert packet["route_specific_evidence_scope"] == "bond_analysis_action_attribution_dto_only"
    assert packet["borrowed_dashboard_evidence_allowed"] is False
    assert packet["dashboard_evidence_reuse_status"] == "blocked_for_bond_analysis_certification"
    assert packet["non_reusable_dashboard_evidence"] == [
        "PAGE-BOND-001",
        "/bond-dashboard",
        "GS-BOND-HEADLINE-A",
        "MTR-BOND-001 through MTR-BOND-004",
    ]
    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["governance_validation_status"] == "direct_records_ready_for_audit_review"
    assert packet["governance_record_commands"] == {
        "dry_run": "python scripts/emit_bond_analysis_governance_record.py",
        "write": "python scripts/emit_bond_analysis_governance_record.py --write",
        "validate": "python scripts/codex_page_readiness.py --page-slug bond-analysis",
    }
    assert packet["governance_record_post_write_validation_status"] == "direct_records_ready_for_audit_review"
    assert packet["latest_verification_evidence"] == {
        "static_readiness": "static-pass",
        "direct_governance_record": "ready_for_audit_review",
        "ui_api_payload_evidence": "GS-BOND-ANALYSIS-ACTION-ATTR-A response.json",
        "live_smoke_evidence": LIVE_SMOKE_EVIDENCE_ARTIFACT,
        "live_smoke_command": LIVE_SMOKE_COMMAND,
        "readiness_command": "python scripts/codex_page_readiness.py --page-slug bond-analysis",
        "boundary": (
            "Direct governance record and static readiness are ready for audit review. "
            "UI/API payload and live smoke evidence remain reviewer-confirmation inputs only; "
            "owner approval remains pending."
        ),
    }
    assert packet["manual_review_evidence"] == {
        "ui_api_payload_review": "tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json",
        "live_smoke_evidence_review": LIVE_SMOKE_EVIDENCE_ARTIFACT,
        "live_smoke_command_reference": LIVE_SMOKE_COMMAND,
    }
    assert packet["configured_table_names"] == ["fact_formal_bond_analytics_daily"]
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "validates_required_fields": True,
    }
    assert "PAGE-BOND-001" in packet["out_of_scope_surfaces"]
    assert "fixed_income_rule_review" in packet["remaining_blockers"]


def test_bond_analysis_owner_evidence_packet_reports_missing_records_when_governance_is_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "empty-governance"))

    packet = build_packet()

    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["governance_validation_status"] == "missing_direct_records"
    assert packet["governance_record_post_write_validation_status"] == "direct_records_ready_for_audit_review"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False


def test_bond_analysis_owner_evidence_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "packet.md"
    audit_output_path = tmp_path / "audit.md"

    returncode, payload = _run_packet(
        "--output",
        str(output_path),
        "--audit-output",
        str(audit_output_path),
    )

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["audit_packet_path"] == str(audit_output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["business_contract_certified"] is False
    assert payload["approval_action_item_count"] == 12
    assert payload["governance_record_write_status"] == "not_requested"
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"

    text = output_path.read_text(encoding="utf-8")
    assert "# Bond Analysis Owner Evidence Packet" in text
    assert "Business contract status: `evidence-pending`" in text
    assert "Formal use allowed: `formal_use_allowed=false`" in text
    assert "Golden sample boundary: `action_attribution_capture_ready_pending_approval`" in text
    assert "Dedicated golden sample: `GS-BOND-ANALYSIS-ACTION-ATTR-A`" in text
    assert "Route-specific evidence scope: `bond_analysis_action_attribution_dto_only`" in text
    assert "Borrowed dashboard evidence allowed: `false`" in text
    assert (
        "Dashboard evidence reuse status: "
        "`blocked_for_bond_analysis_certification`"
    ) in text
    assert "PAGE-BOND-001, /bond-dashboard, GS-BOND-HEADLINE-A, and MTR-BOND-001 through MTR-BOND-004 are non-reusable for /bond-analysis certification." in text
    assert "Governance record write status: `not_requested`" in text
    assert (
        "Governance validation status: `direct_records_ready_for_audit_review`"
        in text
    )
    assert (
        "Governance post-write validation target: "
        "`direct_records_ready_for_audit_review`"
    ) in text
    assert (
        "- Dry run: `python scripts/emit_bond_analysis_governance_record.py`"
        in text
    )
    assert (
        "- Write: `python scripts/emit_bond_analysis_governance_record.py --write`"
        in text
    )
    assert (
        "- Validate: `python scripts/codex_page_readiness.py --page-slug bond-analysis`"
        in text
    )
    assert "## Latest Verification Evidence" in text
    assert "- Static readiness: `static-pass`" in text
    assert "- Direct governance record: `ready_for_audit_review`" in text
    assert "- UI/API payload evidence: `GS-BOND-ANALYSIS-ACTION-ATTR-A response.json`" in text
    assert f"- Live smoke evidence: `{LIVE_SMOKE_EVIDENCE_ARTIFACT}`" in text
    assert f"- Live smoke command: `{LIVE_SMOKE_COMMAND}`" in text
    assert "## Manual Review Evidence References" in text
    assert (
        "- UI/API payload review: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json`"
        in text
    )
    assert f"- Live smoke evidence review: `{LIVE_SMOKE_EVIDENCE_ARTIFACT}`" in text
    assert f"- Live smoke command reference: `{LIVE_SMOKE_COMMAND}`" in text
    assert "- owner_signoff_runbook: `docs/pnl/bond-analysis-owner-signoff-runbook.md`" in text
    assert "This packet does not approve page closure" in text
    assert "- `certification_effect=none`" in text
    assert "Fixed-income units/sign/date rules reviewed: `yes` (`pending`)" in text


def test_bond_analysis_owner_evidence_packet_cli_can_report_missing_records_with_empty_governance(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "packet.md"
    env = {
        **os.environ,
        "MOSS_GOVERNANCE_PATH": str(tmp_path / "empty-governance"),
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(output_path),
            "--audit-output",
            str(tmp_path / "audit.md"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["governance_validation_status"] == "missing_direct_records"
    assert "Governance validation status: `missing_direct_records`" in output_path.read_text(
        encoding="utf-8",
    )


def test_bond_analysis_owner_evidence_packet_matches_generator_output() -> None:
    expected = render_markdown(build_packet())
    actual = OWNER_EVIDENCE_PACKET.read_text(encoding="utf-8")

    assert actual == expected


def test_bond_analysis_governance_audit_packet_matches_generator_output() -> None:
    expected = render_audit_markdown(build_packet())
    actual = GOVERNANCE_AUDIT_PACKET.read_text(encoding="utf-8")

    assert actual == expected
    assert "Governance validation status: `direct_records_ready_for_audit_review`" in actual
    assert "Direct page/API governance record status: `ready_for_audit_review`" in actual
    assert "UI/API payload review evidence: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json`" in actual
    assert f"Live smoke evidence review: `{LIVE_SMOKE_EVIDENCE_ARTIFACT}`" in actual
    assert f"Live smoke command reference: `{LIVE_SMOKE_COMMAND}`" in actual
    assert "Closure approved: `closure_approved=false`" in actual


def test_bond_analysis_owner_evidence_packet_surfaces_owner_runbook_anchor() -> None:
    owner = OWNER_EVIDENCE_PACKET.read_text(encoding="utf-8")

    assert "- owner_signoff_runbook: `docs/pnl/bond-analysis-owner-signoff-runbook.md`" in owner
    assert "This packet does not approve page closure" in owner
    assert "- `certification_effect=none`" in owner


def test_bond_analysis_signoff_and_audit_packets_surface_no_certification_scope() -> None:
    signoff_packet = SIGNOFF_PACKET.read_text(encoding="utf-8")
    audit_packet = GOVERNANCE_AUDIT_PACKET.read_text(encoding="utf-8")

    for text in (signoff_packet, audit_packet):
        assert "## Evidence Scope" in text
        assert "- `approves_metric_or_page=false`" in text
        assert "- `writes_governance_records=false`" in text
        assert "- `proves_page_execution=false`" in text
        assert "- `captures_business_owner_approval=false`" in text
        assert "- `certification_effect=none`" in text
    assert "python scripts/emit_bond_analysis_governance_record.py" in audit_packet
    assert "python scripts/emit_bond_analysis_governance_record.py --write" in audit_packet


def test_bond_analysis_owner_signoff_runbook_preserves_candidate_boundary() -> None:
    text = OWNER_SIGNOFF_RUNBOOK.read_text(encoding="utf-8")

    assert "# Bond Analysis Owner Signoff Runbook" in text
    assert "`PAGE-BOND-ANALYSIS-001`" in text
    assert "`/api/bond-analytics/action-attribution`" in text
    assert "`docs/pnl/bond-analysis-business-owner-approval-template.md`" in text
    assert "`docs/pnl/bond-analysis-owner-evidence-packet.md`" in text
    assert "`docs/pnl/bond-analysis-sign-off-packet.md`" in text
    assert "`docs/pnl/bond-analysis-governance-audit-packet.md`" in text
    assert "`docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`" in text
    assert "Keep `formal_use_allowed=false`." in text
    assert "Keep `closure_approved=false`." in text
    assert "Keep `certification_effect=none`." in text
    assert "Do not promote DV01, duration, KRD, yield/YTM, credit-spread" in text
    assert "`PAGE-BOND-001`" in text
    assert "`GS-BOND-HEADLINE-A`" in text
    assert "`MTR-BOND-001` through `MTR-BOND-004`" in text
    assert "Do not treat dry-run governance output as a written direct PAGE/API governance record." in text
    assert "`GS-BOND-ANALYSIS-ACTION-ATTR-A`" in text
    assert "`captured-awaiting-approval`" in text
    assert (
        "Passing it still does not promote Bond Analysis to formal fixed-income "
        "metric truth or set `closure_approved=true`."
    ) in text
