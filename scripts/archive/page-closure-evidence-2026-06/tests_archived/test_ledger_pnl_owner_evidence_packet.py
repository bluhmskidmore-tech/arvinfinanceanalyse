# ARCHIVED 2026-08-12（C5 脚本盘点批次 1 归档）：随 ../ledger_pnl_owner_evidence_packet.py 一并移出 tests/。
# pytest 不再收集（pytest.ini testpaths 仅 tests/、backend/tests/）；归档件冻结、不保证可运行，仅作追溯。
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ledger_pnl_owner_evidence_packet import build_packet


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ledger_pnl_owner_evidence_packet.py"


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


def test_ledger_pnl_owner_evidence_packet_preserves_candidate_boundary(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    packet = build_packet(
        governance_dir=governance_dir,
        created_at="2026-06-05T12:01:14.993184Z",
    )

    assert packet["packet_kind"] == "ledger_pnl_owner_evidence_packet"
    assert packet["page_slug"] == "ledger-pnl"
    assert packet["route"] == "/ledger-pnl"
    assert packet["primary_api"] == "/api/ledger-pnl/summary"
    assert packet["business_contract_status"] == "evidence-pending"
    assert packet["business_contract_certified"] is False
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["approval_status"] == "pending"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert packet["approval_action_item_count"] == 11
    assert packet["golden_sample_boundary"] == "dedicated_summary_capture_ready_pending_approval"
    assert packet["dedicated_golden_sample_id"] == "GS-LEDGER-PNL-SUMMARY-A"
    assert packet["covered_candidate_metric_ids"] == [
        "MTR-LPN-001",
        "MTR-LPN-002",
        "MTR-LPN-003",
    ]
    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["governance_existing_record_line"] is None
    assert packet["governance_validation_status"] == "ready_for_audit_review"
    assert packet["configured_table_names"] == [
        "qdb_general_ledger_workbook",
        "ledger_import_batch",
        "ledger_raw_row",
    ]
    assert packet["record_key"] == {
        "page_id": "PAGE-LEDGER-PNL-001",
        "primary_api": "/api/ledger-pnl/summary",
        "report_date": "2026-05-31",
        "cache_key": "ledger_pnl.summary:2026-05-31:ALL",
    }
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "validates_required_fields": True,
    }
    assert packet["evidence_anchors"]["dedicated_summary_golden_sample_sync"] == (
        "docs/audits/2026-06-06-ledger-pnl-dedicated-summary-golden-sample-sync.json"
    )
    assert "source_anchor_golden_boundary" not in packet["evidence_anchors"]
    assert packet["out_of_scope_surfaces"] == [
        "formal PnL overview truth",
        "product-category PnL truth",
        "PnL bridge truth",
        "formal financial indicator truth",
        "MTR-LPN formal-use promotion",
        "business-owner approval",
    ]
    assert "dedicated_golden_sample_review" in packet["remaining_blockers"]
    assert packet["owner_action_items"][0] == {
        "blocker": "business_owner_name",
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
        "current_status": "missing",
    }


def test_ledger_pnl_owner_evidence_packet_cli_writes_markdown(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "packet.md"
    governance_dir = tmp_path / "governance"

    returncode, payload = _run_packet(
        "--output",
        str(output_path),
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T12:01:14.993184Z",
    )

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["business_contract_certified"] is False
    assert payload["approval_action_item_count"] == 11
    assert payload["governance_record_write_status"] == "not_requested"
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"

    text = output_path.read_text(encoding="utf-8")
    assert "# Ledger PnL Owner Evidence Packet" in text
    assert "Business contract status: `evidence-pending`" in text
    assert "Formal use allowed: `formal_use_allowed=false`" in text
    assert "Closure approved: `closure_approved=false`" in text
    assert "Golden sample boundary: `dedicated_summary_capture_ready_pending_approval`" in text
    assert "Dedicated golden sample: `GS-LEDGER-PNL-SUMMARY-A`" in text
    assert (
        "dedicated_summary_golden_sample_sync: "
        "`docs/audits/2026-06-06-ledger-pnl-dedicated-summary-golden-sample-sync.json`"
    ) in text
    assert "source_anchor_golden_boundary" not in text
    assert "Governance record write status: `not_requested`" in text
    assert "Existing record line: `None`" in text
    assert "Governance validation status: `ready_for_audit_review`" in text
    assert "MTR-LPN-001" in text
    assert "MTR-LPN-003" in text
    assert "This packet does not approve page closure" in text
    assert "- `certification_effect=none`" in text
    assert "Dedicated ledger summary golden sample reviewed: `yes` (`pending`)" in text
    assert "- - Dedicated ledger summary golden sample reviewed" not in text
