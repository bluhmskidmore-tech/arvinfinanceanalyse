from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.system_audit_strict_gate_matrix import (
    build_matrix,
    build_matrix_from_inputs,
    format_markdown_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "system_audit_strict_gate_matrix.py"


@pytest.fixture(scope="module")
def strict_gate_matrix() -> dict:
    return build_matrix(generated_at="2026-06-10T22:55:00+08:00")


def test_system_audit_strict_gate_matrix_reports_expected_blocked_gates(
    strict_gate_matrix: dict,
) -> None:
    report = strict_gate_matrix

    assert report["report_kind"] == "system_audit_strict_gate_matrix"
    assert report["status"] == "pass"
    assert report["completion_state"] == "not_complete"
    assert report["full_score_ready"] is False
    assert report["open_blocker_count"] == 5
    assert report["completion_order_guard_status"] == "pass"
    assert report["completion_order_guard_error_count"] == 0
    assert report["gate_count"] == 7
    assert report["expected_blocked_gate_count"] == 7
    assert report["strict_pass_gate_count"] == 0
    assert report["unexpected_gate_count"] == 0
    assert report["guard_error_count"] == 0
    assert report["guard_errors"] == []

    gates = {item["gate_id"]: item for item in report["gates"]}
    assert set(gates) == {
        "system-audit-full-score",
        "completion-zero-open-blockers",
        "monitoring-zero-open-blockers",
        "calculation-p1-owner-decisions-captured",
        "ledger-pnl-written-record-located",
        "direct-app-mcp-gitnexus-evidence-captured",
        "local-secret-hygiene-clean-boundary",
    }
    assert all(item["expected_current_exit"] == "non_zero" for item in gates.values())
    assert all(item["actual_current_exit"] == "non_zero" for item in gates.values())
    assert all(item["expectation_met"] is True for item in gates.values())
    assert "captured_decision_count=0" in gates[
        "calculation-p1-owner-decisions-captured"
    ]["blocking_detail"]
    assert "existing_record_line=None" in gates["ledger-pnl-written-record-located"][
        "blocking_detail"
    ]
    assert "missing_direct_servers=" in gates[
        "direct-app-mcp-gitnexus-evidence-captured"
    ]["blocking_detail"]
    assert "ignored_status='!! config/.env'" in gates[
        "local-secret-hygiene-clean-boundary"
    ]["blocking_detail"]
    assert "does not approve owner decisions" in report["boundary"]


def test_system_audit_strict_gate_matrix_fails_when_completion_order_guard_fails() -> None:
    report = build_matrix_from_inputs(
        generated_at="2026-06-10T22:55:00+08:00",
        manifest_path=ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json",
        pulse={
            "completion_state": "not_complete",
            "full_score_ready": False,
            "open_blocker_count": 5,
        },
        completion={
            "status": "pass",
            "open_blocker_count": 5,
            "completion_gate_count": 5,
            "follow_up_completion_order_status": "fail",
            "follow_up_completion_order_error_count": 2,
        },
        monitoring={
            "status": "pass",
            "open_blocker_count": 5,
            "pulse_completion_state": "not_complete",
        },
        calculation={
            "capture_template": {
                "captured_decision_count": 0,
                "row_count": 10,
                "pending_count": 10,
            },
        },
        ledger={
            "status": {"overall": "dry_run_candidate_only"},
            "dry_run_result": {
                "record_write_status": "not_requested",
                "existing_record_line": None,
            },
        },
        direct={
            "status": {
                "direct_app_mcp_evidence_captured": False,
                "direct_gitnexus_evidence_captured": False,
            },
            "missing_direct_servers": ["gitnexus"],
        },
        secret={
            "latest_boundary_only_recheck": {
                "secret_values_captured": False,
                "boundary_checks": {
                    "git_status_ignored": {"result": "!! config/.env"},
                },
            },
            "status": {
                "secret_values_captured": False,
                "clears_secret_scan": False,
            },
        },
    )

    assert report["status"] == "fail"
    assert report["completion_order_guard_status"] == "fail"
    assert report["completion_order_guard_error_count"] == 2
    assert report["guard_error_count"] == 2
    assert (
        "completion order guard status expected 'pass', got 'fail'"
        in report["guard_errors"]
    )
    assert (
        "completion order guard error count expected 0, got 2"
        in report["guard_errors"]
    )


def test_system_audit_strict_gate_matrix_formats_markdown(
    strict_gate_matrix: dict,
) -> None:
    markdown = format_markdown_matrix(strict_gate_matrix)

    assert markdown.startswith("# System Audit Strict Gate Matrix")
    assert "- Status: `pass`" in markdown
    assert "- Strict pass gates: `0/7`" in markdown
    assert "- Completion order guard: `pass` (errors `0`)" in markdown
    assert "`calculation-p1-owner-decisions-captured`" in markdown
    assert "`local-secret-hygiene-clean-boundary`" in markdown
    assert "does not approve owner decisions" in markdown


def test_system_audit_strict_gate_matrix_cli_outputs_markdown() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T22:55:00+08:00",
            "--format",
            "markdown",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    assert "# System Audit Strict Gate Matrix" in completed.stdout
    assert "- Strict pass gates: `0/7`" in completed.stdout
    assert "- Completion order guard: `pass` (errors `0`)" in completed.stdout
    assert "`ledger-pnl-written-record-located`" in completed.stdout
