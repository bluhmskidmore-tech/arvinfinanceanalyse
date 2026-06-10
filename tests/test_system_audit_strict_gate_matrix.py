from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.system_audit_strict_gate_matrix import (
    build_matrix,
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
    assert report["gate_count"] == 7
    assert report["expected_blocked_gate_count"] == 7
    assert report["strict_pass_gate_count"] == 0
    assert report["unexpected_gate_count"] == 0

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


def test_system_audit_strict_gate_matrix_formats_markdown(
    strict_gate_matrix: dict,
) -> None:
    markdown = format_markdown_matrix(strict_gate_matrix)

    assert markdown.startswith("# System Audit Strict Gate Matrix")
    assert "- Status: `pass`" in markdown
    assert "- Strict pass gates: `0/7`" in markdown
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
    assert "`ledger-pnl-written-record-located`" in completed.stdout
