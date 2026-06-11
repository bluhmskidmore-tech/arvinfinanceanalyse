from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.refresh_calculation_p1_owner_decision_snapshot import (
    CAPTURE_TEMPLATE_NON_APPROVAL_BOUNDARY,
    build_snapshot,
)
from scripts.verify_system_audit_completion_snapshot import (
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "refresh_calculation_p1_owner_decision_snapshot.py"
MATRIX = ROOT / "docs" / "audits" / "2026-06-10-calculation-p1-owner-decision-matrix.md"
CAPTURE_TEMPLATE = (
    ROOT / "docs" / "audits" / "2026-06-10-owner-decision-capture-template.zh.md"
)


def test_calculation_p1_owner_decision_snapshot_preserves_fail_closed_boundary() -> None:
    snapshot = build_snapshot(generated_at="2026-06-10T20:45:00+08:00")

    assert snapshot["report_kind"] == "calculation_p1_owner_decision_snapshot"
    assert snapshot["status"] == {
        "overall": "owner_decision_required",
        "fail_closed": True,
        "chooses_or_approves_conventions": False,
        "changes_code": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
    }
    assert snapshot["matrix"]["open_decision_ids"] == EXPECTED_OPEN_CALCULATION_P1_IDS
    assert snapshot["matrix"]["open_decision_count"] == 10
    assert snapshot["matrix"]["p1_08_in_open_rows"] is False
    assert snapshot["matrix"]["p1_08_verified_closed"] is True
    assert snapshot["matrix"]["p1_08_regression"] == {
        "command": (
            "npm.cmd test -- src/features/bond-dashboard/utils/format.test.ts "
            "src/test/BondDashboardPage.test.tsx"
        ),
        "rerun_at": "2026-06-10T19:29:53+08:00",
    }
    assert snapshot["engineering_prework_map"]["mapped_ids"] == (
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert all(snapshot["engineering_prework_map"]["boundary_checks"].values())
    assert snapshot["capture_template"]["row_ids"] == EXPECTED_OPEN_CALCULATION_P1_IDS
    assert snapshot["capture_template"]["pending_count"] == 10
    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["incomplete_decision_count"] == 10
    assert snapshot["capture_template"]["incomplete_decision_ids"] == (
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "status",
    ]
    assert snapshot["drift_errors"] == []
    assert "does not choose or approve any calculation convention" in snapshot["boundary"]


def test_calculation_p1_owner_decision_snapshot_cli_outputs_json(tmp_path: Path) -> None:
    output_path = tmp_path / "calculation-p1-snapshot.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T20:45:00+08:00",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["generated_at"] == "2026-06-10T20:45:00+08:00"
    assert payload["status"]["overall"] == "owner_decision_required"
    assert payload["matrix"]["open_decision_count"] == 10
    assert payload["drift_errors"] == []


def test_calculation_p1_owner_decision_snapshot_cli_strict_gate_rejects_pending_rows(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "calculation-p1-snapshot.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T20:45:00+08:00",
            "--output",
            str(output_path),
            "--require-owner-decisions-captured",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"]["overall"] == "owner_decision_required"
    assert payload["capture_template"]["captured_decision_count"] == 0
    assert payload["capture_template"]["row_count"] == 10
    assert payload["capture_template"]["pending_count"] == 10
    assert payload["capture_template"]["incomplete_decision_count"] == 10
    assert "Calculation P1 owner decisions are not fully captured" in completed.stderr
    assert "captured_decision_count=0" in completed.stderr


def test_calculation_p1_owner_decision_snapshot_does_not_count_partial_rows_as_captured(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "use-bps"
    p101_cells[4] = "alice"
    partial_p101_line = "| " + " | ".join(p101_cells) + " |"
    capture_text = capture_text.replace(p101_line, partial_p101_line)
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["status"]["overall"] == "owner_decision_required"
    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["incomplete_decision_count"] == 10
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "owner_rationale",
        "status",
    ]


def test_calculation_p1_owner_decision_snapshot_fails_closed_when_p108_reopens(
    tmp_path: Path,
) -> None:
    matrix_path = tmp_path / "matrix.md"
    matrix_text = MATRIX.read_text(encoding="utf-8")
    matrix_text = matrix_text.replace(
        "| P1-01 | Campisi coupon income |",
        "| P1-08 | Reopened null handling |",
        1,
    )
    matrix_path.write_text(matrix_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=matrix_path,
        capture_template_path=CAPTURE_TEMPLATE,
    )

    assert snapshot["status"]["overall"] == "matrix_drift"
    assert "P1-08 appears in open owner-decision rows" in snapshot["drift_errors"]
    assert "open P1 decision IDs do not match the expected order" in snapshot["drift_errors"]


def test_calculation_p1_owner_decision_snapshot_fails_closed_when_template_drifts(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8").replace(
        "| P1-11 | Credit spread rating-tenor matrix owner |",
        "| P1-12 | Unexpected owner row |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["status"]["overall"] == "matrix_drift"
    assert (
        "owner decision capture template P1 IDs do not match the expected order"
        in snapshot["drift_errors"]
    )


def test_calculation_p1_owner_decision_snapshot_fails_closed_when_capture_boundary_is_removed(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8").replace(
        CAPTURE_TEMPLATE_NON_APPROVAL_BOUNDARY,
        "Boundary removed.",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["status"]["overall"] == "matrix_drift"
    assert (
        "boundary check failed: capture_template_non_approval_boundary"
        in snapshot["drift_errors"]
    )
