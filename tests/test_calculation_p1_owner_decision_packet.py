from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.calculation_p1_owner_decision_packet import (
    DEFAULT_OUTPUT,
    build_packet,
    render_markdown,
)
from scripts.verify_system_audit_completion_snapshot import (
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calculation_p1_owner_decision_packet.py"


def test_calculation_p1_owner_decision_packet_prepares_first_blocker_without_approval() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "calculation_p1_owner_decision_packet"
    assert packet["decision_status"] == "owner_decision_required"
    assert packet["owner_decision_ready"] is False
    assert packet["implementation_ready"] is False
    assert packet["execution_anchor_ready"] is True
    assert packet["decision_item_count"] == 10
    assert packet["pending_decision_count"] == 10
    assert packet["captured_decision_count"] == 0
    assert packet["post_owner_required_fields"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
        "status",
    ]
    assert packet["execution_referenced_path_count"] >= 10
    assert packet["missing_execution_referenced_paths"] == []
    assert packet["decision_ids"] == EXPECTED_OPEN_CALCULATION_P1_IDS
    assert "`Option <letter> - <copied option description>`" in packet[
        "capture_validation_rule"
    ]
    assert "evidence-only text on approved-for-implementation rows" in packet[
        "capture_validation_rule"
    ]
    assert packet["first_priority_group"] == {
        "rank": 1,
        "p1_ids": ["P1-09", "P1-10", "P1-11"],
        "rationale": (
            "fastest remaining frontend/user-facing risk reduction once owner accepts "
            "the boundary."
        ),
    }
    assert packet["intake_checklist"] == {
        "source_matrix_exists": True,
        "source_snapshot_exists": True,
        "decision_ids_match_expected": True,
        "all_rows_pending_owner_decision": True,
        "captured_decision_count": 0,
        "invalid_status_count": 0,
        "invalid_selected_decision_count": 0,
        "execution_slice_count": 10,
        "execution_referenced_path_count": packet["execution_referenced_path_count"],
        "all_execution_slices_present": True,
        "all_execution_slice_paths_exist": True,
        "missing_execution_referenced_path_count": 0,
        "captures_owner_decisions": False,
        "chooses_or_approves_conventions": False,
    }
    assert packet["evidence_scope"] == {
        "read_only": True,
        "chooses_or_approves_conventions": False,
        "changes_code": False,
        "writes_duckdb": False,
        "writes_governance_records": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "captures_owner_decisions": False,
        "certifies_routes": False,
        "authorizes_ledger_pnl_governance_write": False,
    }
    assert "treat proposed review defaults as approved rules" in packet["prohibited_actions"]
    assert "does not choose or approve conventions" in packet["boundary"]

    p109 = next(item for item in packet["decision_items"] if item["p1_id"] == "P1-09")
    assert p109["priority_rank"] == 1
    assert p109["area"] == "Balance movement share source"
    assert p109["current_status"] == "pending_owner_decision"
    assert p109["captures_owner_decision"] is False
    assert p109["allowed_candidate_options"] == {
        "A": "backend `current_balance_pct` is authoritative",
        "B": "frontend recomputes from visible rows",
        "C": "backend provides both official and visible-row share",
    }
    assert p109["post_decision_execution_slice"]["all_referenced_paths_exist"] is True
    assert p109["post_decision_execution_slice"]["missing_referenced_paths"] == []
    assert p109["closure_evidence"] == (
        "Component/model tests prove backend value wins and missing share remains missing."
    )
    assert p109["missing_capture_fields"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
        "status",
    ]
    assert "BalanceMovementAnalysisPage.tsx" in " ".join(
        p109["post_decision_execution_slice"]["referenced_paths"]
    )


def test_calculation_p1_owner_decision_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "calculation-p1-owner-decision-packet.md"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["packet_kind"] == "calculation_p1_owner_decision_packet"
    assert payload["packet_path"] == str(output_path)
    assert payload["decision_status"] == "owner_decision_required"
    assert payload["owner_decision_ready"] is False
    assert payload["implementation_ready"] is False
    assert payload["execution_anchor_ready"] is True
    assert payload["decision_item_count"] == 10
    assert payload["pending_decision_count"] == 10
    assert payload["captured_decision_count"] == 0
    assert payload["execution_referenced_path_count"] >= 10
    assert payload["missing_execution_referenced_paths"] == []
    assert payload["first_priority_group"]["p1_ids"] == ["P1-09", "P1-10", "P1-11"]
    assert payload["intake_checklist"]["execution_slice_count"] == 10
    assert payload["intake_checklist"]["invalid_selected_decision_count"] == 0
    assert payload["intake_checklist"]["all_execution_slices_present"] is True
    assert payload["intake_checklist"]["all_execution_slice_paths_exist"] is True
    assert payload["intake_checklist"]["missing_execution_referenced_path_count"] == 0
    assert payload["intake_checklist"]["captures_owner_decisions"] is False
    assert payload["intake_checklist"]["chooses_or_approves_conventions"] is False
    assert payload["evidence_scope"]["authorizes_ledger_pnl_governance_write"] is False

    text = output_path.read_text(encoding="utf-8")
    assert "Calculation P1 Owner Decision Packet" in text
    assert "decision_status=owner_decision_required" in text
    assert "decision_item_count=10" in text
    assert "pending_decision_count=10" in text
    assert "captured_decision_count=0" in text
    assert (
        "`post_owner_required_fields=selected_decision, owner_rationale, "
        "implementation_owner, verification_gate, status`"
    ) in text
    assert "Execution anchor ready: `true`" in text
    assert "Owner decision gate" in text
    assert "Component/model tests prove backend value wins" in text
    assert "## Execution Anchor Checks" in text
    assert "## Candidate Option Contract" in text
    assert "Allowed option letters are row-specific" in text
    assert "evidence-only wording" in text
    assert "`Option A`: backend `current_balance_pct` is authoritative" in text
    assert "`Option A`: backend provides governed matrix" in text
    assert "`Option B`: frontend aggregates rows and owns bucket mapping" in text
    assert "Required capture format, not a recommendation" in text
    assert "`Option <allowed letter> - <copied option description>`" in text
    assert "| `P1-11` | `Option A`: backend provides governed matrix<br>`Option B`: frontend aggregates rows and owns bucket mapping | `Option A - backend provides governed matrix` |" not in text
    assert "undefined option letters" in text
    assert "`all_execution_slice_paths_exist=true`" in text
    assert "`missing_execution_referenced_path_count=0`" in text
    assert "First priority group: `P1-09, P1-10, P1-11`" in text
    assert "`captures_owner_decisions=false`" in text
    assert "`chooses_or_approves_conventions=false`" in text
    assert "`invalid_selected_decision_count=0`" in text
    assert "treat proposed review defaults as approved rules" in text
    assert "BalanceMovementAnalysisPage.tsx" in text
    assert "yieldAnalysisAggregates.ts" in text
    assert "CreditSpreadView.tsx" in text
    assert "authorize Ledger PnL `--write`" in text


def test_checked_in_calculation_p1_owner_decision_packet_matches_renderer() -> None:
    packet = build_packet()
    expected_markdown = render_markdown(packet)

    checked_in_markdown = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    assert checked_in_markdown == expected_markdown
    assert "## Intake Checklist" in checked_in_markdown
    assert "## Post-Decision Execution Slices" in checked_in_markdown
    assert "## Execution Anchor Checks" in checked_in_markdown
    assert "## Candidate Option Contract" in checked_in_markdown
    assert "Owner decision gate" in checked_in_markdown
    assert "`captures_owner_decisions=false`" in checked_in_markdown
