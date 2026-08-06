from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.refresh_calculation_p1_owner_decision_snapshot import (
    CAPTURE_TEMPLATE_CANDIDATE_CONTRACT_PHRASES,
    CAPTURE_TEMPLATE_NON_APPROVAL_BOUNDARY,
    build_snapshot,
)
from scripts.verify_system_audit_completion_snapshot import (
    EXPECTED_OPEN_CALCULATION_P1_IDS,
    EXPECTED_OWNER_DECISION_CLOSED_P1_IDS,
    HISTORICAL_OPEN_CALCULATION_P1_IDS,
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
    assert snapshot["matrix"]["open_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["historical_baseline"]["open_decision_ids"] == (
        HISTORICAL_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["historical_baseline"]["open_decision_count"] == 10
    assert snapshot["matrix"]["candidate_option_letters_by_id"]["P1-11"] == ["A", "B"]
    assert snapshot["matrix"]["capture_template_candidate_options_match_matrix"] is True
    assert snapshot["matrix"]["p1_08_in_open_rows"] is False
    assert snapshot["matrix"]["p1_08_verified_closed"] is True
    assert snapshot["matrix"]["owner_decision_closed_ids"] == (
        EXPECTED_OWNER_DECISION_CLOSED_P1_IDS
    )
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
    assert (
        snapshot["engineering_prework_map"]["boundary_checks"][
            "capture_template_candidate_option_contract"
        ]
        is True
    )
    assert snapshot["capture_template"]["row_ids"] == EXPECTED_OPEN_CALCULATION_P1_IDS
    assert snapshot["capture_template"]["pending_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["capture_template"]["candidate_contract_options_by_id"] == snapshot[
        "matrix"
    ]["candidate_options_by_id"]
    assert snapshot["capture_template"]["candidate_contract_options_by_id"]["P1-11"] == {
        "A": "backend provides governed matrix",
        "B": "frontend aggregates rows and owns bucket mapping",
    }
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    assert "Required capture format, not a recommendation" in capture_text
    assert "accepted selected_decision example" not in capture_text
    assert "| `P1-11` | A: backend provides governed matrix; B: frontend aggregates rows and owns bucket mapping. | `Option <allowed letter> - <copied option description>` |" in capture_text
    assert "`Option A - backend provides governed matrix`" not in capture_text
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {}
    assert snapshot["capture_template"]["invalid_selected_decision_count"] == 0
    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["incomplete_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["capture_template"]["incomplete_decision_ids"] == (
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
        "status",
    ]
    assert snapshot["meeting_record"]["field_count"] == 8
    assert snapshot["meeting_record"]["filled_required_field_count"] == 0
    assert snapshot["meeting_record"]["is_complete"] is False
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
    assert payload["matrix"]["open_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
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
    assert payload["capture_template"]["row_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert payload["capture_template"]["pending_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert payload["capture_template"]["incomplete_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert payload["meeting_record"]["is_complete"] is False
    assert "Calculation P1 owner decisions are not fully captured" in completed.stderr
    assert "captured_decision_count=0" in completed.stderr
    assert "meeting_record_complete=false" in completed.stderr


def test_calculation_p1_owner_decision_snapshot_strict_gate_requires_meeting_record(
    tmp_path: Path,
) -> None:
    option_a_by_id = {
        "P1-01": "Option A - source values are decimals",
        "P1-02": "Option A - all source rates are decimals",
        "P1-03": "Option A - attribution_daily convention",
        "P1-04": "Option A - independent position and ledger source anchors",
        "P1-05": "Option A - period average scale",
        "P1-06": "Option A - nonzero residual with zero actual warning",
        "P1-10": "Option A - backend DTO only",
        "P1-11": "Option A - backend provides governed matrix",
    }
    capture_path = tmp_path / "capture-template.md"
    capture_lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten_lines: list[str] = []
    for line in capture_lines:
        if not line.startswith("| P1-"):
            rewritten_lines.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cells[2] = option_a_by_id[cells[0]]
        cells[3] = "Owner rationale captured for audit review."
        cells[4] = "metric-governance-owner"
        cells[5] = "targeted regression and strict gate"
        cells[6] = "approved-for-implementation"
        rewritten_lines.append("| " + " | ".join(cells) + " |")
    capture_path.write_text("\n".join(rewritten_lines) + "\n", encoding="utf-8")
    output_path = tmp_path / "calculation-p1-snapshot.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T20:45:00+08:00",
            "--capture-template",
            str(capture_path),
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
    assert payload["capture_template"]["captured_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert payload["capture_template"]["invalid_selected_decision_count"] == 0
    assert payload["capture_template"]["incomplete_decision_count"] == 0
    assert payload["meeting_record"]["is_complete"] is False
    assert "meeting_record_complete=false" in completed.stderr


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
    assert snapshot["capture_template"]["incomplete_decision_count"] == len(
        EXPECTED_OPEN_CALCULATION_P1_IDS
    )
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision",
        "owner_rationale",
        "verification_gate",
        "status",
    ]


def test_calculation_p1_owner_decision_snapshot_rejects_unknown_decision_status(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Option A - source values are decimals"
    p101_cells[3] = "Owner selected basis-point units for formal display."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "targeted numeric regression"
    p101_cells[6] = "maybe"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["status"]["overall"] == "owner_decision_required"
    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "status"
    ]
    assert snapshot["capture_template"]["invalid_status_by_id"] == {"P1-01": "maybe"}


def test_calculation_p1_owner_decision_snapshot_rejects_unknown_selected_decision(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Z"
    p101_cells[3] = "Owner rationale captured for audit review."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "targeted numeric regression"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["status"]["overall"] == "owner_decision_required"
    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {
        "P1-01": "Z"
    }
    assert snapshot["capture_template"]["invalid_selected_decision_count"] == 1
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision"
    ]


def test_calculation_p1_owner_decision_snapshot_rejects_bare_candidate_option_anchor(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Candidate C"
    p101_cells[3] = "Owner rationale captured for audit review."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "targeted numeric regression"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {
        "P1-01": "Candidate C"
    }
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision"
    ]


def test_calculation_p1_owner_decision_snapshot_accepts_option_anchor_with_substance(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Candidate C - explicit unit metadata"
    p101_cells[3] = "Owner rationale captured for audit review."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "targeted numeric regression"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {}
    assert "P1-01" not in snapshot["capture_template"]["incomplete_fields_by_id"]
    assert "P1-01" in snapshot["capture_template"]["captured_decision_ids"]


def test_calculation_p1_owner_decision_snapshot_rejects_suggested_verification_gate(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Option A - source values are decimals"
    p101_cells[3] = "Owner rationale captured for audit review."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "suggested: targeted numeric regression"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "verification_gate"
    ]


def test_calculation_p1_owner_decision_snapshot_rejects_irrelevant_option_text(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Option C - backend governed matrix"
    p101_cells[3] = "Owner rationale captured for audit review."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "targeted numeric regression"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {
        "P1-01": "Option C - backend governed matrix"
    }
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision"
    ]


def test_calculation_p1_owner_decision_snapshot_rejects_option_not_defined_for_p1(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p111_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-11 |")
    )
    p111_cells = [cell.strip() for cell in p111_line.strip().strip("|").split("|")]
    p111_cells[2] = "Option C - backend governed matrix"
    p111_cells[3] = "Owner rationale captured for audit review."
    p111_cells[4] = "metric-governance-owner"
    p111_cells[5] = "targeted numeric regression"
    p111_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p111_line,
        "| " + " | ".join(p111_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["matrix"]["candidate_option_letters_by_id"]["P1-11"] == ["A", "B"]
    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {
        "P1-11": "Option C - backend governed matrix"
    }
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-11"] == [
        "selected_decision"
    ]


def test_calculation_p1_owner_decision_snapshot_accepts_defined_option_for_p1(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p111_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-11 |")
    )
    p111_cells = [cell.strip() for cell in p111_line.strip().strip("|").split("|")]
    p111_cells[2] = "Option B - frontend aggregates rows and owns bucket mapping"
    p111_cells[3] = "Owner rationale captured for audit review."
    p111_cells[4] = "metric-governance-owner"
    p111_cells[5] = "targeted numeric regression"
    p111_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p111_line,
        "| " + " | ".join(p111_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["matrix"]["candidate_option_letters_by_id"]["P1-11"] == ["A", "B"]
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {}
    assert "P1-11" not in snapshot["capture_template"]["incomplete_fields_by_id"]
    assert "P1-11" in snapshot["capture_template"]["captured_decision_ids"]


def test_calculation_p1_owner_decision_snapshot_rejects_evidence_placeholder_as_approved_decision(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "evidence required"
    p101_cells[3] = "Owner rationale captured for audit review."
    p101_cells[4] = "metric-governance-owner"
    p101_cells[5] = "targeted numeric regression"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["invalid_selected_decision_by_id"] == {
        "P1-01": "evidence required"
    }
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "selected_decision"
    ]


def test_calculation_p1_owner_decision_snapshot_rejects_placeholder_capture_fields(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8")
    p101_line = next(
        line for line in capture_text.splitlines() if line.startswith("| P1-01 |")
    )
    p101_cells = [cell.strip() for cell in p101_line.strip().strip("|").split("|")]
    p101_cells[2] = "Option A - source values are decimals"
    p101_cells[3] = "TBD"
    p101_cells[4] = "pending"
    p101_cells[5] = "todo"
    p101_cells[6] = "approved-for-implementation"
    capture_text = capture_text.replace(
        p101_line,
        "| " + " | ".join(p101_cells) + " |",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["capture_template"]["captured_decision_count"] == 0
    assert snapshot["capture_template"]["incomplete_fields_by_id"]["P1-01"] == [
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
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


def test_calculation_p1_owner_decision_snapshot_fails_closed_when_candidate_contract_is_removed(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8").replace(
        CAPTURE_TEMPLATE_CANDIDATE_CONTRACT_PHRASES[0],
        "### Candidate Contract Removed",
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["status"]["overall"] == "matrix_drift"
    assert (
        "boundary check failed: capture_template_candidate_option_contract"
        in snapshot["drift_errors"]
    )


def test_calculation_p1_owner_decision_snapshot_fails_closed_when_template_options_drift(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture-template.md"
    capture_text = CAPTURE_TEMPLATE.read_text(encoding="utf-8").replace(
        (
            "A: backend provides governed matrix; "
            "B: frontend aggregates rows and owns bucket mapping."
        ),
        (
            "A: backend provides governed matrix; "
            "B: frontend aggregates rows and owns bucket mapping; "
            "C: frontend invents a third bucket owner."
        ),
    )
    capture_path.write_text(capture_text, encoding="utf-8")

    snapshot = build_snapshot(
        generated_at="2026-06-10T20:45:00+08:00",
        matrix_path=MATRIX,
        capture_template_path=capture_path,
    )

    assert snapshot["matrix"]["capture_template_candidate_options_match_matrix"] is False
    assert snapshot["status"]["overall"] == "matrix_drift"
    assert (
        "boundary check failed: capture_template_candidate_options_match_matrix"
        in snapshot["drift_errors"]
    )
