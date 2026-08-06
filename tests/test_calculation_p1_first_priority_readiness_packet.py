from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.calculation_p1_first_priority_readiness_packet import (
    DEFAULT_OUTPUT,
    FIRST_PRIORITY_IDS,
    POST_OWNER_REQUIRED_FIELDS,
    build_packet,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calculation_p1_first_priority_readiness_packet.py"


def test_first_priority_readiness_packet_maps_current_p110_p111_without_approval() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "calculation_p1_first_priority_readiness_packet"
    assert packet["source_snapshot_status"] == "owner_decision_required"
    assert packet["first_priority_ids"] == FIRST_PRIORITY_IDS
    assert packet["first_priority_count"] == 2
    assert packet["owner_intake_ready"] is True
    assert packet["implementation_ready"] is False
    assert packet["captured_decision_count"] == 0
    assert packet["captured_decision_ids"] == []
    assert packet["post_owner_required_fields"] == POST_OWNER_REQUIRED_FIELDS
    assert packet["readiness_checks"] == {
        "all_first_priority_ids_still_open": True,
        "source_snapshot_is_owner_decision_required": True,
        "matrix_names_first_priority_group": True,
        "all_code_anchors_exist": True,
        "all_test_anchors_exist": True,
        "captures_owner_decisions": False,
        "chooses_or_approves_conventions": False,
        "changes_implementation_code": False,
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
    assert "count this readiness packet as owner decision capture" in packet[
        "prohibited_actions"
    ]
    assert "does not choose or approve any calculation convention" in packet["boundary"]

    items = {item["p1_id"]: item for item in packet["items"]}
    assert set(items) == set(FIRST_PRIORITY_IDS)
    assert "P1-09" not in items
    assert "yieldAnalysisAggregates.ts" in " ".join(items["P1-10"]["code_anchors"])
    assert "zqtzAdbAvgRollup.ts" in " ".join(items["P1-10"]["code_anchors"])
    assert "CreditSpreadView.tsx" in " ".join(items["P1-11"]["code_anchors"])
    assert "CreditSpreadView.test.tsx" in " ".join(items["P1-11"]["test_anchors"])
    assert "backend DTO / frontend removal tests" in items["P1-10"][
        "owner_decision_gate"
    ]
    assert "API contract plus frontend test" in items["P1-11"]["owner_decision_gate"]
    assert "rating/tenor bucket-boundary regression remains pending" in items["P1-11"][
        "known_regression_gap"
    ]
    assert all(not item["missing_code_anchors"] for item in items.values())
    assert all(not item["missing_test_anchors"] for item in items.values())
    assert all(item["current_status"] == "pending_owner_decision" for item in items.values())


def test_first_priority_readiness_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "first-priority-readiness.md"

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
    assert payload["packet_kind"] == "calculation_p1_first_priority_readiness_packet"
    assert payload["packet_path"] == str(output_path)
    assert payload["source_snapshot_status"] == "owner_decision_required"
    assert payload["owner_intake_ready"] is True
    assert payload["implementation_ready"] is False
    assert payload["first_priority_ids"] == FIRST_PRIORITY_IDS
    assert payload["captured_decision_count"] == 0
    assert payload["readiness_checks"]["chooses_or_approves_conventions"] is False
    assert payload["evidence_scope"]["writes_governance_records"] is False

    text = output_path.read_text(encoding="utf-8")
    assert "Calculation P1 First Priority Readiness Packet" in text
    assert "source_snapshot_status=owner_decision_required" in text
    assert "`first_priority_ids=P1-10, P1-11`" in text
    assert (
        "`post_owner_required_fields=selected_decision, owner_rationale, "
        "implementation_owner, verification_gate, status`"
    ) in text
    assert "`owner_intake_ready=true`" in text
    assert "`implementation_ready=false`" in text
    assert "Owner Decision Gate" in text
    assert "backend DTO / frontend removal tests" in text
    assert "API contract plus frontend test" in text
    assert "BalanceMovementAnalysisPage.tsx" not in text
    assert "yieldAnalysisAggregates.ts" in text
    assert "zqtzAdbAvgRollup.ts" in text
    assert "CreditSpreadView.tsx" in text
    assert "count this readiness packet as owner decision capture" in text
    assert "does not choose or approve any calculation convention" in text
    assert "does not approve a convention or change implementation code" in text


def test_checked_in_first_priority_readiness_packet_matches_renderer() -> None:
    packet = build_packet()
    expected_markdown = render_markdown(packet)

    checked_in_markdown = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    assert checked_in_markdown == expected_markdown
    assert "`P1-09`" not in checked_in_markdown
    assert "`P1-10`" in checked_in_markdown
    assert "`P1-11`" in checked_in_markdown
    assert "`post_owner_required_fields=selected_decision, owner_rationale" in (
        checked_in_markdown
    )
    assert "Owner Decision Gate" in checked_in_markdown
    assert "## Current Evidence And Post-Owner Gates" in checked_in_markdown
