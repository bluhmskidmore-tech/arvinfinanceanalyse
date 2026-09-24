from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.system_audit_blocker_intake_board import (
    build_board,
    format_markdown_board,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "system_audit_blocker_intake_board.py"


def test_system_audit_blocker_intake_board_summarizes_open_blockers_fail_closed() -> None:
    board = build_board(generated_at="2026-06-11T00:45:00+08:00")

    assert board["report_kind"] == "system_audit_blocker_intake_board"
    assert board["status"] == "open_external_input_required"
    assert board["generated_at"] == "2026-06-11T00:45:00+08:00"
    assert board["blocker_count"] == 5
    assert board["completion_order"] == [
        "calculation-display-p1-decisions",
        "ledger-pnl-direct-governance-record",
        "owner-approval-7-pages",
        "direct-app-mcp-gitnexus-evidence",
        "local-secret-hygiene",
    ]
    assert board["evidence_scope"] == {
        "read_only": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "authorizes_ledger_pnl_governance_write": False,
        "captures_direct_app_mcp_gitnexus_evidence": False,
        "requests_or_captures_secret_values": False,
        "clears_secret_scan": False,
        "certifies_routes": False,
    }

    blockers = {item["blocker_id"]: item for item in board["blockers"]}
    assert set(blockers) == set(board["completion_order"])
    assert all(item["current_status"] == "not_complete" for item in blockers.values())
    assert all(item["strict_gate_command"] for item in blockers.values())
    assert all(item["required_external_input_count"] > 0 for item in blockers.values())
    assert all(item["prohibited_action_count"] > 0 for item in blockers.values())
    assert blockers["calculation-display-p1-decisions"]["strict_gate_command"] == (
        "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured"
    )
    assert blockers["ledger-pnl-direct-governance-record"]["strict_gate_command"] == (
        "python scripts\\refresh_ledger_pnl_direct_governance_record_snapshot.py "
        "--require-written-record-located"
    )
    assert blockers["direct-app-mcp-gitnexus-evidence"]["strict_gate_command"] == (
        "python scripts\\refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py "
        "--require-direct-evidence-captured"
    )
    assert blockers["local-secret-hygiene"]["strict_gate_command"] == (
        "python scripts\\refresh_local_secret_hygiene_snapshot.py "
        "--require-clean-boundary"
    )
    assert (
        "python scripts\\emit_ledger_pnl_governance_record.py --write"
        in blockers["ledger-pnl-direct-governance-record"][
            "authorization_required_commands_not_preapproved"
        ]
    )
    assert board["next_blocker_id"] == "calculation-display-p1-decisions"
    assert "does not approve metrics" in board["boundary"]


def test_system_audit_blocker_intake_board_formats_markdown() -> None:
    board = build_board(generated_at="2026-06-11T00:45:00+08:00")

    markdown = format_markdown_board(board)

    assert markdown.startswith("# System Audit Blocker Intake Board")
    assert "- Status: `open_external_input_required`" in markdown
    assert "- Open blockers: `5`" in markdown
    assert "- Next blocker: `calculation-display-p1-decisions`" in markdown
    assert "`ledger-pnl-direct-governance-record`" in markdown
    assert "`local-secret-hygiene`" in markdown
    assert "`python scripts\\refresh_local_secret_hygiene_snapshot.py --require-clean-boundary`" in markdown
    assert "does not approve metrics" in markdown


def test_system_audit_blocker_intake_board_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-11T00:45:00+08:00",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["report_kind"] == "system_audit_blocker_intake_board"
    assert payload["blocker_count"] == 5
    assert payload["next_blocker_id"] == "calculation-display-p1-decisions"
