from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.portfolio_home_evidence_snapshot_alignment_check import build_report
from scripts.portfolio_home_business_owner_approval_packet import (
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    PORTFOLIO_HOME_SCORE_BLOCKERS,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_evidence_snapshot_alignment_check.py"
SNAPSHOT = ROOT / "docs" / "portfolio" / "portfolio-home-evidence-snapshot.json"


def _run_check(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_evidence_snapshot_alignment_check_reports_clean_current_snapshot() -> None:
    report = build_report(SNAPSHOT)

    assert report["check_kind"] == "portfolio_home_evidence_snapshot_alignment"
    assert report["status"] == "clean"
    assert report["valid"] is True
    assert report["blockers"] == []
    assert report["actual_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": [
            "owner_handoff_completeness_status",
            "owner_handoff_completeness_ready",
            "owner_handoff_completeness_blockers",
        ],
    }
    assert report["expected_owner_decision_intake_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }
    assert (
        report["actual_owner_decision_intake_alignment"]
        == report["expected_owner_decision_intake_alignment"]
    )
    assert (
        report["approval_summary_owner_decision_intake_alignment"]
        == report["expected_owner_decision_intake_alignment"]
    )
    assert report["expected_score_blocker_action_coverage"] == {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
    }
    assert report["approval_summary_score_blocker_action_coverage"] == {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": PORTFOLIO_HOME_SCORE_BLOCKERS,
    }
    assert report["embedded_verifier_summary"] == {
        "expected_state": "blocked",
        "verification_status": "matched_expected_blocked_state",
        "all_matched_expected_exit": True,
        "all_matched_expected_when_blocked": True,
        "result_count": 1,
        "actual_result_count": 1,
    }


def test_portfolio_home_evidence_snapshot_alignment_check_cli_require_clean() -> None:
    returncode, payload = _run_check("--require-clean")

    assert returncode == 0
    assert payload["status"] == "clean"
    assert payload["valid"] is True


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_stale_alignment(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["owner_handoff_completeness_alignment"] = {
        "status": "consistent",
        "blockers": [],
        "compared_fields": [
            "owner_handoff_completeness_status",
            "owner_handoff_completeness_ready",
        ],
    }
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "owner_handoff_completeness_alignment_mismatch",
        "owner_handoff_completeness_alignment_fields_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_wrong_snapshot_identity(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["snapshot_kind"] = "portfolio_home_owner_handoff"
    snapshot["page_id"] = "PAGE-BOND-DASHBOARD-001"
    snapshot["page_slug"] = "bond-dashboard"
    snapshot["report_date"] = "2026-04-30"
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "evidence_snapshot_kind_mismatch",
        "evidence_snapshot_page_id_mismatch",
        "evidence_snapshot_page_slug_mismatch",
        "evidence_snapshot_report_date_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_owner_intake_alignment_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["owner_decision_intake_alignment"] = {
        "status": "consistent",
        "blockers": [],
        "compared_fields": [
            "intake_status",
            "intake_ready",
        ],
    }
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "owner_decision_intake_alignment_mismatch",
        "owner_decision_intake_alignment_fields_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_owner_gate_summary_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    gate = snapshot["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate, dict)
    gate["intake_ready"] = True
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "owner_decision_intake_alignment_mismatch",
        "approval_summary_owner_decision_intake_alignment_mismatch",
    ]
    assert payload["expected_owner_decision_intake_alignment"] == {
        "status": "blocked",
        "blockers": ["owner_decision_intake_alignment_intake_ready_mismatch"],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_gate_summary_alignment_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    gate_summary = snapshot["gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["owner_decision_intake_alignment_status"] = "blocked"
    gate_summary["owner_decision_intake_alignment_blockers"] = [
        "owner_decision_intake_alignment_intake_ready_mismatch",
    ]
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "gate_summary_owner_decision_intake_alignment_status_mismatch",
        "gate_summary_owner_decision_intake_alignment_blockers_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_approval_summary_alignment_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    approval_summary = snapshot["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary["owner_decision_intake_alignment"] = {
        "status": "blocked",
        "blockers": ["owner_decision_intake_alignment_owner_input_boundary_mismatch"],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "approval_summary_owner_decision_intake_alignment_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_action_coverage_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    approval_summary = snapshot["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    coverage = approval_summary["score_blocker_action_coverage"]
    assert isinstance(coverage, dict)
    coverage["status"] = "blocked"
    coverage["blockers"] = ["score_blocker_action_missing:business_owner_approval"]
    coverage["unassigned_blockers"] = ["business_owner_approval"]
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "approval_summary_score_blocker_action_coverage_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_dependency_status_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    approval_summary = snapshot["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary["dependency_consistency_status"] = "blocked"
    approval_summary["dependency_consistency_blockers"] = [
        "krd_contract_decision_manifest_report_date_mismatch",
    ]
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "approval_summary_dependency_consistency_status_mismatch",
        "approval_summary_dependency_consistency_blockers_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_verifier_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    verifier = snapshot["verification_report"]
    assert isinstance(verifier, dict)
    verifier["expected_state"] = "full_score"
    verifier["verification_status"] = "mismatch"
    verifier["all_matched_expected_exit"] = False
    verifier["all_matched_expected_when_blocked"] = False
    verifier["result_count"] = 2
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["matches_expected_exit"] = False
    result["matches_expected_when_blocked"] = False
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "verification_report_expected_state_mismatch",
        "verification_report_status_mismatch",
        "verification_report_expected_exit_not_matched",
        "verification_report_blocked_exit_not_matched",
        "verification_report_result_count_mismatch",
        "verification_report_result_mismatch",
    ]
    assert payload["embedded_verifier_summary"] == {
        "expected_state": "full_score",
        "verification_status": "mismatch",
        "all_matched_expected_exit": False,
        "all_matched_expected_when_blocked": False,
        "result_count": 2,
        "actual_result_count": 1,
    }


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_malformed_verifier_result(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    verifier = snapshot["verification_report"]
    assert isinstance(verifier, dict)
    verifier["results"] = ["not-a-verifier-result"]
    verifier["result_count"] = 1
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "verification_report_result_mismatch",
    ]
    assert payload["embedded_verifier_summary"] == {
        "expected_state": "blocked",
        "verification_status": "matched_expected_blocked_state",
        "all_matched_expected_exit": True,
        "all_matched_expected_when_blocked": True,
        "result_count": 1,
        "actual_result_count": 1,
    }


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_verifier_result_state_drift(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    verifier = snapshot["verification_report"]
    assert isinstance(verifier, dict)
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["expected_state"] = "full_score"
    result["expected_exit"] = "exit_0"
    result["expected_when_blocked"] = "exit_nonzero"
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    returncode, payload = _run_check("--snapshot", str(output), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "verification_report_result_mismatch",
    ]


def test_portfolio_home_evidence_snapshot_alignment_check_blocks_missing_snapshot(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"

    returncode, payload = _run_check("--snapshot", str(missing), "--require-clean")

    assert returncode == 1
    assert payload["status"] == "blocked"
    assert payload["valid"] is False
    assert payload["blockers"] == [
        "evidence_snapshot_missing",
        "owner_handoff_completeness_alignment_missing",
        "owner_decision_intake_summary_missing",
        "scorecard_owner_decision_intake_gate_summary_missing",
        "owner_decision_intake_alignment_missing",
        "business_owner_approval_packet_summary_missing",
        "approval_summary_owner_decision_intake_alignment_missing",
        "approval_summary_score_blocker_action_coverage_missing",
        "approval_summary_dependency_consistency_status_missing",
        "approval_summary_dependency_consistency_blockers_missing",
        "verification_report_missing",
    ]
