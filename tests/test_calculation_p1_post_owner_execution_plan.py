from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.calculation_p1_post_owner_execution_plan import (
    DEFAULT_OUTPUT,
    POST_OWNER_REQUIRED_FIELDS,
    build_plan,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calculation_p1_post_owner_execution_plan.py"
SNAPSHOT = (
    ROOT
    / "docs"
    / "audits"
    / "2026-06-10-calculation-p1-owner-decision-snapshot.json"
)
CAPTURE_TEMPLATE = (
    ROOT / "docs" / "audits" / "2026-06-10-owner-decision-capture-template.zh.md"
)


def test_calculation_p1_post_owner_execution_plan_routes_current_pending_rows() -> None:
    plan = build_plan()

    assert plan["packet_kind"] == "calculation_p1_post_owner_execution_plan"
    assert plan["source_snapshot_status"] == "owner_decision_required"
    assert plan["global_owner_decision_gate_ready"] is False
    assert plan["implementation_ready"] is False
    assert plan["row_count"] == 8
    assert plan["captured_decision_count"] == 0
    assert plan["owner_decision_capture_complete"] is False
    assert plan["ready_for_implementation_count"] == 0
    assert plan["deferred_count"] == 0
    assert plan["rejected_count"] == 0
    assert plan["non_implementation_decision_count"] == 0
    assert plan["incomplete_count"] == 8
    assert plan["post_owner_blocking_reasons"] == [
        "owner_decision_capture_incomplete"
    ]
    assert plan["meeting_record_complete"] is False
    assert plan["missing_meeting_field_count"] == 8
    assert plan["post_owner_required_fields"] == POST_OWNER_REQUIRED_FIELDS
    assert plan["readiness_checks"] == {
        "decision_ids_match_expected": True,
        "all_execution_slice_paths_exist": True,
        "no_invalid_statuses": True,
        "no_invalid_selected_decisions": True,
        "source_snapshot_is_owner_decision_required": True,
        "live_template_matches_snapshot_missing_fields": True,
        "owner_decision_capture_complete": False,
        "non_implementation_decisions_present": False,
        "global_owner_decision_gate_ready": False,
        "implementation_ready": False,
        "captures_owner_decisions": False,
        "chooses_or_approves_conventions": False,
        "changes_implementation_code": False,
    }
    assert plan["evidence_scope"]["captures_owner_decisions"] is False
    assert plan["evidence_scope"]["changes_code"] is False
    assert "execute implementation when the meeting record is incomplete" in plan[
        "prohibited_actions"
    ]
    assert "does not choose or approve conventions" in plan["boundary"]

    assert [item["p1_id"] for item in plan["queues"]["incomplete"]] == [
        "P1-01",
        "P1-02",
        "P1-03",
        "P1-04",
        "P1-05",
        "P1-06",
        "P1-10",
        "P1-11",
    ]
    p110 = next(item for item in plan["items"] if item["p1_id"] == "P1-10")
    assert p110["bucket"] == "incomplete"
    assert p110["status"] == "pending"
    assert (
        p110["verification_gate"]
        == "suggested: backend DTO / frontend removal tests"
    )
    assert (
        p110["owner_decision_gate"]
        == "Backend DTO added or confirmed; frontend removes formal aggregation; "
        "adapter/component tests consume DTO values."
    )
    assert p110["missing_capture_fields"] == [
        "selected_decision",
        "owner_rationale",
        "implementation_owner",
        "verification_gate",
        "status",
    ]
    assert "yieldAnalysisAggregates.ts" in " ".join(p110["referenced_paths"])


def test_calculation_p1_post_owner_execution_plan_classifies_captured_rows(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["capture_template"]["captured_decision_count"] = 3
    snapshot["capture_template"]["captured_decision_ids"] = ["P1-06", "P1-10", "P1-11"]
    snapshot["capture_template"]["incomplete_decision_count"] = 5
    snapshot["capture_template"]["incomplete_decision_ids"] = [
        "P1-01",
        "P1-02",
        "P1-03",
        "P1-04",
        "P1-05",
    ]
    snapshot["capture_template"]["incomplete_fields_by_id"] = {
        key: value
        for key, value in snapshot["capture_template"][
            "incomplete_fields_by_id"
        ].items()
        if key not in {"P1-06", "P1-10", "P1-11"}
    }
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    decisions = {
        "P1-06": (
            "Option A - nonzero explained/residual with zero actual is warning/undefined",
            "approved-for-implementation",
        ),
        "P1-10": ("Option B - frontend may derive display aggregates", "deferred"),
        "P1-11": ("Option A - backend provides governed matrix", "rejected"),
    }
    for line in lines:
        if not line.startswith("| P1-"):
            rewritten.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in decisions:
            selected_decision, status = decisions[cells[0]]
            cells[2] = selected_decision
            cells[3] = "Owner rationale captured for deterministic routing."
            cells[4] = "metric-governance-owner"
            cells[5] = "targeted regression and strict gate"
            cells[6] = status
        rewritten.append("| " + " | ".join(cells) + " |")
    capture_path = tmp_path / "capture-template.md"
    capture_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    plan = build_plan(
        snapshot_path=snapshot_path,
        capture_template_path=capture_path,
    )

    assert [item["p1_id"] for item in plan["queues"]["ready_for_implementation"]] == [
        "P1-06"
    ]
    assert [item["p1_id"] for item in plan["queues"]["deferred"]] == ["P1-10"]
    assert [item["p1_id"] for item in plan["queues"]["rejected"]] == ["P1-11"]
    assert plan["ready_for_implementation_count"] == 1
    assert plan["deferred_count"] == 1
    assert plan["rejected_count"] == 1
    assert plan["incomplete_count"] == 5
    assert plan["invalid_selected_decision_count"] == 0
    assert plan["live_template_incomplete_count"] == 5
    assert plan["global_owner_decision_gate_ready"] is False
    assert plan["implementation_ready"] is False


def test_calculation_p1_post_owner_execution_plan_separates_capture_from_implementation(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    row_ids = snapshot["capture_template"]["row_ids"]
    snapshot["capture_template"]["captured_decision_count"] = len(row_ids)
    snapshot["capture_template"]["captured_decision_ids"] = row_ids
    snapshot["capture_template"]["incomplete_decision_count"] = 0
    snapshot["capture_template"]["incomplete_decision_ids"] = []
    snapshot["capture_template"]["incomplete_fields_by_id"] = {}
    snapshot["capture_template"]["invalid_selected_decision_by_id"] = {}
    snapshot["capture_template"]["invalid_selected_decision_count"] = 0
    snapshot["capture_template"]["invalid_status_by_id"] = {}
    snapshot["meeting_record"]["is_complete"] = True
    snapshot["meeting_record"]["missing_required_fields"] = []
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    decisions = {
        "P1-01": ("Option C - source must carry explicit unit metadata and fail if absent", "approved-for-implementation"),
        "P1-02": ("Option C - source supplies explicit unit metadata", "approved-for-implementation"),
        "P1-03": ("Option A - attribution_daily convention", "approved-for-implementation"),
        "P1-04": ("Option A - require independent position and ledger source anchors", "deferred"),
        "P1-05": ("Option A - period average scale", "approved-for-implementation"),
        "P1-06": ("Option A - nonzero explained/residual with zero actual is warning/undefined", "approved-for-implementation"),
        "P1-10": ("Option A - backend DTO only", "approved-for-implementation"),
        "P1-11": ("Option A - backend provides governed matrix", "rejected"),
    }
    lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith("| P1-"):
            rewritten.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        selected_decision, status = decisions[cells[0]]
        cells[2] = selected_decision
        cells[3] = "Owner rationale captured for deterministic routing."
        cells[4] = "metric-governance-owner"
        cells[5] = "targeted regression and strict gate"
        cells[6] = status
        rewritten.append("| " + " | ".join(cells) + " |")
    capture_path = tmp_path / "capture-template.md"
    capture_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    plan = build_plan(
        snapshot_path=snapshot_path,
        capture_template_path=capture_path,
    )

    assert plan["owner_decision_capture_complete"] is True
    assert plan["global_owner_decision_gate_ready"] is True
    assert plan["implementation_ready"] is False
    assert plan["ready_for_implementation_count"] == 6
    assert plan["deferred_count"] == 1
    assert plan["rejected_count"] == 1
    assert plan["non_implementation_decision_count"] == 2
    assert plan["post_owner_blocking_reasons"] == [
        "non_implementation_decisions_present"
    ]
    assert plan["readiness_checks"]["owner_decision_capture_complete"] is True
    assert plan["readiness_checks"]["non_implementation_decisions_present"] is True


def test_calculation_p1_post_owner_execution_plan_accepts_all_approved_owner_input(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    row_ids = snapshot["capture_template"]["row_ids"]
    snapshot["capture_template"]["captured_decision_count"] = len(row_ids)
    snapshot["capture_template"]["captured_decision_ids"] = row_ids
    snapshot["capture_template"]["incomplete_decision_count"] = 0
    snapshot["capture_template"]["incomplete_decision_ids"] = []
    snapshot["capture_template"]["incomplete_fields_by_id"] = {}
    snapshot["capture_template"]["invalid_selected_decision_by_id"] = {}
    snapshot["capture_template"]["invalid_selected_decision_count"] = 0
    snapshot["capture_template"]["invalid_status_by_id"] = {}
    snapshot["meeting_record"]["is_complete"] = True
    snapshot["meeting_record"]["missing_required_fields"] = []
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    decisions = {
        "P1-01": "Option C - source must carry explicit unit metadata and fail if absent",
        "P1-02": "Option C - source supplies explicit unit metadata",
        "P1-03": "Option A - attribution_daily convention",
        "P1-04": "Option A - require independent position and ledger source anchors",
        "P1-05": "Option A - period average scale",
        "P1-06": "Option A - nonzero explained/residual with zero actual is warning/undefined",
        "P1-10": "Option A - backend DTO only",
        "P1-11": "Option A - backend provides governed matrix",
    }
    lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith("| P1-"):
            rewritten.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cells[2] = decisions[cells[0]]
        cells[3] = "Owner rationale captured for deterministic routing."
        cells[4] = "metric-governance-owner"
        cells[5] = "targeted regression and strict gate"
        cells[6] = "approved-for-implementation"
        rewritten.append("| " + " | ".join(cells) + " |")
    capture_path = tmp_path / "capture-template.md"
    capture_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    plan = build_plan(
        snapshot_path=snapshot_path,
        capture_template_path=capture_path,
    )

    assert plan["owner_decision_capture_complete"] is True
    assert plan["global_owner_decision_gate_ready"] is True
    assert plan["implementation_ready"] is True
    assert plan["ready_for_implementation_count"] == 8
    assert plan["deferred_count"] == 0
    assert plan["rejected_count"] == 0
    assert plan["non_implementation_decision_count"] == 0
    assert plan["incomplete_count"] == 0
    assert plan["post_owner_blocking_reasons"] == []


def test_calculation_p1_post_owner_execution_plan_rechecks_live_template_fields(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["capture_template"]["captured_decision_count"] = 1
    snapshot["capture_template"]["captured_decision_ids"] = ["P1-10"]
    snapshot["capture_template"]["incomplete_decision_count"] = 7
    snapshot["capture_template"]["incomplete_decision_ids"] = [
        p1_id
        for p1_id in snapshot["capture_template"]["row_ids"]
        if p1_id != "P1-10"
    ]
    snapshot["capture_template"]["incomplete_fields_by_id"] = {
        key: value
        for key, value in snapshot["capture_template"][
            "incomplete_fields_by_id"
        ].items()
        if key != "P1-10"
    }
    snapshot["capture_template"]["invalid_selected_decision_by_id"] = {}
    snapshot["capture_template"]["invalid_selected_decision_count"] = 0
    snapshot["capture_template"]["invalid_status_by_id"] = {}
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith("| P1-10 |"):
            rewritten.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cells[2] = "evidence required"
        cells[3] = "Owner rationale captured for audit review."
        cells[4] = "metric-governance-owner"
        cells[5] = "targeted regression and strict gate"
        cells[6] = "approved-for-implementation"
        rewritten.append("| " + " | ".join(cells) + " |")
    capture_path = tmp_path / "capture-template.md"
    capture_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    plan = build_plan(
        snapshot_path=snapshot_path,
        capture_template_path=capture_path,
    )

    p110 = next(item for item in plan["items"] if item["p1_id"] == "P1-10")
    assert p110["bucket"] == "incomplete"
    assert p110["missing_capture_fields"] == ["selected_decision"]
    assert "P1-10" not in [
        item["p1_id"] for item in plan["queues"]["ready_for_implementation"]
    ]
    assert "P1-10" in [item["p1_id"] for item in plan["queues"]["incomplete"]]
    assert plan["live_template_incomplete_count"] == 8
    assert (
        plan["readiness_checks"]["live_template_matches_snapshot_missing_fields"]
        is False
    )
    assert plan["readiness_checks"]["source_snapshot_is_owner_decision_required"] is True
    assert plan["global_owner_decision_gate_ready"] is False
    assert plan["implementation_ready"] is False


def test_calculation_p1_post_owner_execution_plan_blocks_invalid_selected_decisions(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["capture_template"]["captured_decision_count"] = 0
    snapshot["capture_template"]["captured_decision_ids"] = []
    snapshot["capture_template"]["invalid_selected_decision_by_id"] = {"P1-10": "Z"}
    snapshot["capture_template"]["invalid_selected_decision_count"] = 1
    snapshot["capture_template"]["invalid_status_by_id"] = {}
    snapshot["capture_template"]["incomplete_fields_by_id"] = {
        key: value
        for key, value in snapshot["capture_template"][
            "incomplete_fields_by_id"
        ].items()
    }
    snapshot["capture_template"]["incomplete_fields_by_id"]["P1-10"] = [
        "selected_decision"
    ]
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith("| P1-10 |"):
            rewritten.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cells[2] = "Z"
        cells[3] = "Owner rationale captured but selected decision is invalid."
        cells[4] = "metric-governance-owner"
        cells[5] = "targeted regression and strict gate"
        cells[6] = "approved-for-implementation"
        rewritten.append("| " + " | ".join(cells) + " |")
    capture_path = tmp_path / "capture-template.md"
    capture_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    plan = build_plan(
        snapshot_path=snapshot_path,
        capture_template_path=capture_path,
    )

    p110 = next(item for item in plan["items"] if item["p1_id"] == "P1-10")
    assert p110["bucket"] == "incomplete"
    assert p110["invalid_selected_decision"] == "Z"
    assert p110["missing_capture_fields"] == ["selected_decision"]
    assert "P1-10" not in [
        item["p1_id"] for item in plan["queues"]["ready_for_implementation"]
    ]
    assert "P1-10" in [item["p1_id"] for item in plan["queues"]["incomplete"]]
    assert plan["invalid_selected_decision_count"] == 1
    assert plan["readiness_checks"]["no_invalid_selected_decisions"] is False
    assert plan["readiness_checks"]["source_snapshot_is_owner_decision_required"] is True
    assert plan["global_owner_decision_gate_ready"] is False
    assert plan["implementation_ready"] is False


def test_calculation_p1_post_owner_execution_plan_blocks_matrix_drift_snapshot(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["status"]["overall"] = "matrix_drift"
    snapshot["capture_template"]["captured_decision_count"] = 1
    snapshot["capture_template"]["captured_decision_ids"] = ["P1-10"]
    snapshot["capture_template"]["incomplete_decision_count"] = 7
    snapshot["capture_template"]["incomplete_decision_ids"] = [
        "P1-01",
        "P1-02",
        "P1-03",
        "P1-04",
        "P1-05",
        "P1-06",
        "P1-11",
    ]
    snapshot["capture_template"]["incomplete_fields_by_id"] = {
        key: value
        for key, value in snapshot["capture_template"][
            "incomplete_fields_by_id"
        ].items()
        if key != "P1-10"
    }
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = CAPTURE_TEMPLATE.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith("| P1-10 |"):
            rewritten.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cells[2] = "Option A - backend DTO only"
        cells[3] = "Owner rationale captured for deterministic routing."
        cells[4] = "metric-governance-owner"
        cells[5] = "targeted regression and strict gate"
        cells[6] = "approved-for-implementation"
        rewritten.append("| " + " | ".join(cells) + " |")
    capture_path = tmp_path / "capture-template.md"
    capture_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    plan = build_plan(
        snapshot_path=snapshot_path,
        capture_template_path=capture_path,
    )

    p110 = next(item for item in plan["items"] if item["p1_id"] == "P1-10")
    assert p110["bucket"] == "incomplete"
    assert "P1-10" not in [
        item["p1_id"] for item in plan["queues"]["ready_for_implementation"]
    ]
    assert "P1-10" in [item["p1_id"] for item in plan["queues"]["incomplete"]]
    assert plan["ready_for_implementation_count"] == 0
    assert plan["readiness_checks"]["source_snapshot_is_owner_decision_required"] is False
    assert plan["global_owner_decision_gate_ready"] is False
    assert plan["implementation_ready"] is False


def test_calculation_p1_post_owner_execution_plan_cli_writes_markdown(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "post-owner-plan.md"

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
    assert payload["packet_kind"] == "calculation_p1_post_owner_execution_plan"
    assert payload["packet_path"] == str(output_path)
    assert payload["global_owner_decision_gate_ready"] is False
    assert payload["owner_decision_capture_complete"] is False
    assert payload["implementation_ready"] is False
    assert payload["ready_for_implementation_count"] == 0
    assert payload["non_implementation_decision_count"] == 0
    assert payload["incomplete_count"] == 8
    assert payload["post_owner_blocking_reasons"] == [
        "owner_decision_capture_incomplete"
    ]
    assert payload["invalid_selected_decision_count"] == 0
    assert payload["evidence_scope"]["authorizes_ledger_pnl_governance_write"] is False

    text = output_path.read_text(encoding="utf-8")
    assert "Calculation P1 Post-Owner Execution Plan" in text
    assert "Global owner gate ready: `false`" in text
    assert (
        "`post_owner_required_fields=selected_decision, owner_rationale, "
        "implementation_owner, verification_gate, status`"
    ) in text
    assert "`ready_for_implementation_count=0`" in text
    assert "`non_implementation_decision_count=0`" in text
    assert "`incomplete_count=8`" in text
    assert "`post_owner_blocking_reasons=owner_decision_capture_incomplete`" in text
    assert "`source_snapshot_is_owner_decision_required=true`" in text
    assert "`owner_decision_capture_complete=false`" in text
    assert "`non_implementation_decisions_present=false`" in text
    assert "`global_owner_decision_gate_ready=false`" in text
    assert "`invalid_selected_decision_count=0`" in text
    assert "`no_invalid_selected_decisions=true`" in text
    assert "`changes_implementation_code=false`" in text
    assert "Verification gate" in text
    assert "Owner decision gate" in text
    assert "backend DTO / frontend removal tests" in text
    assert "execute implementation when the meeting record is incomplete" in text
    assert "does not choose or approve conventions" in text


def test_calculation_p1_post_owner_execution_plan_cli_strict_gate_rejects_current_pending_rows(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "post-owner-plan.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(output_path),
            "--require-implementation-ready",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["implementation_ready"] is False
    assert payload["owner_decision_capture_complete"] is False
    assert payload["ready_for_implementation_count"] == 0
    assert payload["post_owner_blocking_reasons"] == [
        "owner_decision_capture_incomplete"
    ]
    assert "not implementation-ready" in completed.stderr
    assert "owner_decision_capture_complete=False" in completed.stderr


def test_checked_in_calculation_p1_post_owner_execution_plan_matches_renderer() -> None:
    plan = build_plan()
    expected_markdown = render_markdown(plan)

    checked_in_markdown = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    assert checked_in_markdown == expected_markdown
    assert "## Execution Queues" in checked_in_markdown
    assert "Verification gate" in checked_in_markdown
    assert "Owner decision gate" in checked_in_markdown
    assert "`source_snapshot_is_owner_decision_required=true`" in checked_in_markdown
    assert "`captures_owner_decisions=false`" in checked_in_markdown
    assert "`chooses_or_approves_conventions=false`" in checked_in_markdown
