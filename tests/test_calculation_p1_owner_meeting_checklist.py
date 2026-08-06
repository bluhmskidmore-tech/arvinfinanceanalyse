from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.calculation_p1_owner_meeting_checklist import (
    DEFAULT_OUTPUT,
    build_checklist,
    render_markdown,
)
from scripts.verify_system_audit_completion_snapshot import (
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calculation_p1_owner_meeting_checklist.py"


def test_calculation_p1_owner_meeting_checklist_prepares_owner_intake() -> None:
    checklist = build_checklist()

    assert checklist["packet_kind"] == "calculation_p1_owner_meeting_checklist"
    assert checklist["source_snapshot_status"] == "owner_decision_required"
    assert checklist["owner_meeting_material_ready"] is True
    assert checklist["implementation_ready"] is False
    assert checklist["decision_item_count"] == len(EXPECTED_OPEN_CALCULATION_P1_IDS)
    assert checklist["pending_decision_count"] == len(EXPECTED_OPEN_CALCULATION_P1_IDS)
    assert checklist["captured_decision_count"] == 0
    assert checklist["incomplete_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert checklist["total_missing_capture_field_count"] == 40
    assert checklist["meeting_missing_field_count"] == 8
    assert checklist["meeting_record_complete"] is False
    assert checklist["execution_anchor_ready"] is True
    assert checklist["execution_referenced_path_count"] == 18
    assert checklist["missing_execution_referenced_path_count"] == 0
    assert checklist["decision_ids"] == EXPECTED_OPEN_CALCULATION_P1_IDS
    assert checklist["post_meeting_required_fields"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
        "status",
    ]
    assert checklist["post_meeting_allowed_statuses"] == [
        "approved-for-implementation",
        "deferred",
        "rejected",
    ]
    assert "undefined option letters" in checklist["capture_validation_rule"]
    assert checklist["readiness_checks"] == {
        "decision_ids_match_expected": True,
        "all_rows_pending_owner_decision": True,
        "captured_decision_count_is_zero": True,
        "meeting_record_is_incomplete": True,
        "execution_anchor_ready": True,
        "captures_owner_decisions": False,
        "chooses_or_approves_conventions": False,
        "changes_implementation_code": False,
    }
    assert checklist["evidence_scope"]["captures_owner_decisions"] is False
    assert checklist["evidence_scope"]["approves_metrics"] is False
    assert "treat this checklist as owner approval" in checklist["prohibited_actions"]
    assert "does not choose or approve calculation conventions" in checklist["boundary"]

    p101 = next(item for item in checklist["items"] if item["p1_id"] == "P1-01")
    assert p101["area"] == "Campisi coupon income"
    assert "Define the stored and calculation unit" in p101["owner_question"]
    assert "A: source values are decimals" in p101["candidate_decisions"]
    assert p101["allowed_candidate_options"]["C"] == (
        "source must carry explicit unit metadata and fail if absent"
    )
    assert p101["owner_decision_gate"] == (
        "`docs/calc_rules.md` unit rule; one implementation path; numeric golden test "
        "for decimal and percent-shaped inputs."
    )
    assert p101["missing_capture_fields"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
        "status",
    ]
    assert "backend/app/core_finance/balance_analysis_workbook.py" in p101[
        "post_decision_execution_slice"
    ]


def test_calculation_p1_owner_meeting_checklist_cli_writes_markdown(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "calculation-p1-owner-meeting-checklist.md"

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
    assert payload["packet_kind"] == "calculation_p1_owner_meeting_checklist"
    assert payload["packet_path"] == str(output_path)
    assert payload["owner_meeting_material_ready"] is True
    assert payload["implementation_ready"] is False
    assert payload["decision_item_count"] == len(EXPECTED_OPEN_CALCULATION_P1_IDS)
    assert payload["pending_decision_count"] == len(EXPECTED_OPEN_CALCULATION_P1_IDS)
    assert payload["captured_decision_count"] == 0
    assert payload["total_missing_capture_field_count"] == 40
    assert payload["meeting_missing_field_count"] == 8
    assert payload["execution_anchor_ready"] is True
    assert payload["evidence_scope"]["authorizes_ledger_pnl_governance_write"] is False

    text = output_path.read_text(encoding="utf-8")
    assert "Calculation P1 Owner Meeting Checklist" in text
    assert "Owner meeting material ready: `true`" in text
    assert "Implementation ready: `false`" in text
    assert "`decision_item_count=8`" in text
    assert "`total_missing_capture_field_count=40`" in text
    assert "`meeting_missing_field_count=8`" in text
    assert "## Owner Questions" in text
    assert "Owner decision gate" in text
    assert "`docs/calc_rules.md` unit rule" in text
    assert "## Candidate Option Contract" in text
    assert "Allowed option letters are row-specific" in text
    assert "`Option C`: source must carry explicit unit metadata and fail if absent" in text
    assert "`Option A`: backend provides governed matrix" in text
    assert "`Option B`: frontend aggregates rows and owns bucket mapping" in text
    assert "Required capture format, not a recommendation" in text
    assert "`Option <allowed letter> - <copied option description>`" in text
    assert "| `P1-01` | `Option A`: source values are decimals" in text
    assert "`Option A - source values are decimals`" not in text
    assert "unrelated option text" in text
    assert "evidence-only text on approved-for-implementation rows" in text
    assert "## Closure Evidence And Engineering Handoff" in text
    assert "Every row must have `selected_decision`" in text
    assert "`verification_gate`" in text
    assert "selected_decision` must use a row-specific allowed option" in text
    assert "P1-01" in text
    assert "P1-11" in text
    assert "treat this checklist as owner approval" in text
    assert "authorizes_ledger_pnl_governance_write=false" in text
    assert "authorize Ledger PnL --write" in text
    assert "does not choose or approve calculation conventions" in text


def test_checked_in_calculation_p1_owner_meeting_checklist_matches_renderer() -> None:
    checklist = build_checklist()
    expected_markdown = render_markdown(checklist)

    checked_in_markdown = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    assert checked_in_markdown == expected_markdown
    assert "Owner meeting material ready: `true`" in checked_in_markdown
    assert "`captures_owner_decisions=false`" in checked_in_markdown
    assert "`chooses_or_approves_conventions=false`" in checked_in_markdown
    assert "## Candidate Option Contract" in checked_in_markdown
    assert "Owner decision gate" in checked_in_markdown
