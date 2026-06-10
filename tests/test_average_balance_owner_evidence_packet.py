from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.average_balance_owner_evidence_packet import build_packet, render_markdown


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "average_balance_owner_evidence_packet.py"
STATIC_PACKET = ROOT / "docs" / "pnl" / "average-balance-owner-evidence-packet.md"


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


def test_average_balance_owner_evidence_packet_preserves_candidate_boundary() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "average_balance_owner_evidence_packet"
    assert packet["page_id"] == "GAP-AVERAGE-BALANCE-PAGE"
    assert packet["page_slug"] == "average-balance"
    assert packet["route"] == "/average-balance"
    assert packet["primary_api"] == "/api/analysis/adb"
    assert packet["business_contract_status"] == "evidence-pending"
    assert packet["business_contract_certified"] is False
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["approval_status"] == "pending"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert packet["approval_action_item_count"] == 13
    assert packet["golden_sample_boundary"] == (
        "daily_and_monthly_adb_candidate_dto_capture_ready_pending_approval"
    )
    assert packet["dedicated_golden_sample_id"] == "GS-AVERAGE-BALANCE-A"
    assert packet["dedicated_golden_sample_ids"] == [
        "GS-AVERAGE-BALANCE-A",
        "GS-AVERAGE-BALANCE-MONTHLY-A",
    ]
    assert packet["daily_candidate_metric_ids"] == ["MTR-ADB-001", "MTR-ADB-002"]
    assert packet["monthly_pending_metric_ids"] == ["MTR-ADB-003"]
    assert packet["monthly_adb_nim_approval_allowed"] is False
    assert packet["formal_balance_truth_approval_allowed"] is False
    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["governance_validation_status"] == "ready_for_audit_review"
    assert packet["golden_sample_approval_artifact_status"] == "captured-awaiting-approval"
    assert packet["configured_table_names"] == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
    ]
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "validates_required_fields": True,
        "approves_formal_balance_truth": False,
        "approves_monthly_adb_nim_truth": False,
    }
    assert packet["evidence_anchors"]["page_contract"] == "docs/pnl/average-balance-page-contract.md"
    assert packet["evidence_anchors"]["owner_signoff_runbook"] == (
        "docs/pnl/average-balance-owner-signoff-runbook.md"
    )
    assert packet["evidence_anchors"]["live_smoke_evidence"] == (
        "docs/audits/2026-06-09-average-balance-live-smoke-evidence.md"
    )
    assert packet["evidence_anchors"]["latest_verification_snapshot"] == (
        "docs/audits/2026-06-10-average-balance-candidate-verification.md"
    )
    assert packet["evidence_anchors"]["monthly_golden_sample"] == (
        "tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A"
    )
    assert packet["evidence_anchors"]["smoke_command"] == (
        "scripts/codex-page-smoke.ps1 -PageSlug average-balance"
    )
    assert packet["evidence_anchors"]["verify_command"] == (
        "scripts/codex-verify-page.ps1 -PageSlug average-balance -Run"
    )
    assert "formal balance truth" in packet["out_of_scope_surfaces"]
    assert "monthly ADB/NIM approval" in packet["out_of_scope_surfaces"]
    assert "daily_golden_sample_review" in packet["remaining_blockers"]
    assert "monthly_adb_nim_boundary_acceptance" in packet["remaining_blockers"]


def test_average_balance_owner_evidence_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "packet.md"
    governance_dir = tmp_path / "governance"

    returncode, payload = _run_packet(
        "--output",
        str(output_path),
        "--governance-dir",
        str(governance_dir),
    )

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["business_contract_certified"] is False
    assert payload["approval_action_item_count"] == 13
    assert payload["governance_record_write_status"] == "not_requested"
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False
    assert payload["evidence_scope"]["approves_formal_balance_truth"] is False
    assert payload["evidence_scope"]["approves_monthly_adb_nim_truth"] is False

    text = output_path.read_text(encoding="utf-8")
    assert "# Average Balance Owner Evidence Packet" in text
    assert "Business contract status: `evidence-pending`" in text
    assert "Formal use allowed: `formal_use_allowed=false`" in text
    assert "Dedicated golden samples: `GS-AVERAGE-BALANCE-A`, `GS-AVERAGE-BALANCE-MONTHLY-A`" in text
    assert "Monthly ADB/NIM approval allowed: `false`" in text
    assert "Formal balance truth approval allowed: `false`" in text
    assert "Existing record line: `dry-run not written`" in text
    assert "- `MTR-ADB-001`" in text
    assert "- `MTR-ADB-002`" in text
    assert "- `MTR-ADB-003`" in text
    assert "Governance validation status: `ready_for_audit_review`" in text
    assert "live_smoke_evidence: `docs/audits/2026-06-09-average-balance-live-smoke-evidence.md`" in text
    assert "owner_signoff_runbook: `docs/pnl/average-balance-owner-signoff-runbook.md`" in text
    assert "latest_verification_snapshot: `docs/audits/2026-06-10-average-balance-candidate-verification.md`" in text
    assert "monthly_golden_sample: `tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A`" in text
    assert "smoke_command: `scripts/codex-page-smoke.ps1 -PageSlug average-balance`" in text
    assert "verify_command: `scripts/codex-verify-page.ps1 -PageSlug average-balance -Run`" in text
    assert "This packet does not approve page closure" in text
    assert "- `certification_effect=none`" in text
    assert "- `approves_formal_balance_truth=false`" in text
    assert "- `approves_monthly_adb_nim_truth=false`" in text
    assert "Monthly ADB/NIM boundary accepted: `yes` (`pending`)" in text


def test_static_average_balance_owner_evidence_packet_matches_generator(
    tmp_path: Path,
) -> None:
    expected = build_packet(governance_dir=tmp_path / "governance")
    actual = STATIC_PACKET.read_text(encoding="utf-8")

    assert actual == render_markdown(expected)
