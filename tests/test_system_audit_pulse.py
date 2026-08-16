from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.system_audit_pulse as pulse_module
from scripts.system_audit_pulse import build_pulse, format_markdown_pulse


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "system_audit_pulse.py"
MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"
EXPECTED_SECURITY_SCAN_ERRORS = [
    (
        "local-secret-hygiene required input artifact is missing: "
        "test_output/security-scans/osv-report.json"
    ),
    (
        "local-secret-hygiene required input artifact is missing: "
        "test_output/security-scans/gitleaks-report.json"
    ),
]
EXPECTED_DRIFT_ERRORS = [
    *EXPECTED_SECURITY_SCAN_ERRORS,
    "strict_gate_matrix.status expected 'pass', got 'fail'",
    "strict_gate_matrix.strict_pass_gate_count expected 0, got 1",
    "strict_gate_matrix.unexpected_gate_count expected 0, got 1",
]


def test_system_audit_pulse_aggregates_live_monitors_without_approval() -> None:
    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["report_kind"] == "system_audit_pulse"
    assert report["generated_at"] == "2026-06-10T19:45:00+08:00"
    assert report["status"] == "fail"
    assert report["full_score_ready"] is False
    assert report["completion_state"] == "not_complete"
    assert report["open_blocker_count"] == 5
    assert report["calculation_post_owner_plan_renderer_sync"] is True
    assert report["evidence_scope"] == {
        "read_only": True,
        "writes_duckdb": False,
        "writes_governance_records": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "promotes_candidate_data": False,
    }
    assert report["route_scope"]["route_count"] == 40
    assert report["route_scope"]["business_contract_certified_count"] == 0
    assert report["route_scope"]["visible_unseeded_route_count"] == 1
    assert report["route_scope"]["unclassified_count"] == 0
    assert report["business_display"]["tracked_route_count"] == 26
    assert report["business_display"]["route_gap_count"] == 0
    assert report["completion_snapshot"]["status"] == "fail"
    assert report["completion_snapshot"]["error_count"] == 2
    assert report["completion_snapshot"]["open_blocker_count"] == 5
    assert report["completion_snapshot"]["calculation_packet_p1_count"] == 8
    assert report["completion_snapshot"]["calculation_meeting_record_complete"] is False
    assert report["completion_snapshot"]["calculation_missing_meeting_field_count"] == 8
    assert (
        report["completion_snapshot"][
            "calculation_post_owner_ready_for_implementation_count"
        ]
        == 0
    )
    assert (
        report["completion_snapshot"][
            "calculation_post_owner_owner_decision_capture_complete"
        ]
        is False
    )
    assert (
        report["completion_snapshot"][
            "calculation_post_owner_non_implementation_decision_count"
        ]
        == 0
    )
    assert report["completion_snapshot"]["calculation_post_owner_blocking_reasons"] == [
        "owner_decision_capture_incomplete"
    ]
    assert report["completion_snapshot"]["calculation_post_owner_incomplete_count"] == 8
    assert (
        report["completion_snapshot"][
            "calculation_post_owner_invalid_selected_decision_count"
        ]
        == 0
    )
    assert (
        report["completion_snapshot"][
            "calculation_post_owner_no_invalid_selected_decisions"
        ]
        is True
    )
    assert report["completion_snapshot"]["calculation_post_owner_global_gate_ready"] is False
    assert (
        report["completion_snapshot"]["calculation_post_owner_implementation_ready"]
        is False
    )
    assert (
        report["completion_snapshot"]["calculation_post_owner_plan_renderer_sync"]
        is True
    )
    assert report["completion_snapshot"]["follow_up_completion_order_status"] == "pass"
    assert report["completion_snapshot"]["follow_up_completion_order_error_count"] == 0
    assert report["blocker_intake_board"]["status"] == "open_external_input_required"
    assert report["blocker_intake_board"]["next_blocker_id"] == (
        "calculation-display-p1-decisions"
    )
    assert report["blocker_intake_board"]["next_blocker_detail"] == {
        "blocker_id": "calculation-display-p1-decisions",
        "responsible_owner_type": "business_owner_and_metric_governance",
        "strict_gate_command": (
            "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
            "--require-owner-decisions-captured"
        ),
        "required_external_input_count": 2,
        "first_required_external_input": (
            "business owner selects the authoritative convention for P1-01 "
            "through P1-06, P1-10, and P1-11"
        ),
        "required_output_count": 9,
        "first_required_output": "authoritative convention selected for P1-01",
        "fail_closed_until": (
            "All 8 remaining owner-decision rows are moved to verified-closed evidence "
            "with targeted tests."
        ),
        "explicit_non_approval_boundary": (
            "This packet records follow-up work only; it does not choose or approve "
            "any calculation convention."
        ),
    }
    assert report["strict_gate_matrix"]["status"] == "fail"
    assert report["strict_gate_matrix"]["open_blocker_count"] == 5
    assert report["strict_gate_matrix"]["gate_count"] == 8
    assert report["strict_gate_matrix"]["expected_blocked_gate_count"] == 8
    assert report["strict_gate_matrix"]["strict_pass_gate_count"] == 1
    assert report["strict_gate_matrix"]["unexpected_gate_count"] == 1
    assert report["all_page_readiness"]["source"] == "manifest_last_full_readiness"
    assert report["all_page_readiness"]["direct_evidence_null_count"] == 0
    assert report["all_page_readiness"]["audit_review_null_count"] == 0
    assert report["drift_errors"] == EXPECTED_DRIFT_ERRORS
    assert "does not approve metrics" in report["claim_boundary"]


def test_checked_in_system_audit_pulse_maps_timestamps_by_blocker_id() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pulse_snapshot_path = ROOT / manifest["artifacts"]["system_audit_pulse_snapshot"]
    pulse_snapshot = json.loads(pulse_snapshot_path.read_text(encoding="utf-8"))

    expected = {
        row["id"]: row["last_checked_at"] for row in manifest["open_blockers"]
    }
    actual = {
        row["id"]: row["last_checked_at"] for row in pulse_snapshot["open_blockers"]
    }
    assert actual == expected
    assert actual["calculation-display-p1-decisions"] == (
        "2026-08-06T22:30:00+08:00"
    )
    assert actual["ledger-pnl-direct-governance-record"] == (
        "2026-06-10T21:25:00+08:00"
    )


def test_system_audit_pulse_default_does_not_run_full_readiness(monkeypatch) -> None:
    def fail_full_readiness():
        raise AssertionError("default pulse should use the manifest's last full readiness scan")

    monkeypatch.setattr(
        pulse_module,
        "build_all_page_readiness_report",
        fail_full_readiness,
    )

    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["status"] == "fail"
    assert report["all_page_readiness"]["source"] == "manifest_last_full_readiness"


def test_system_audit_pulse_detects_route_scope_drift(monkeypatch) -> None:
    original = pulse_module.build_route_scope_classification_report

    def drifted_route_scope():
        payload = original()
        payload["summary"] = dict(payload["summary"])
        payload["summary"]["visible_unseeded_route_count"] = 2
        return payload

    monkeypatch.setattr(
        pulse_module,
        "build_route_scope_classification_report",
        drifted_route_scope,
    )

    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["status"] == "fail"
    assert (
        "route_scope.visible_unseeded_route_count expected 1, got 2"
        in report["drift_errors"]
    )


def test_system_audit_pulse_detects_business_display_drift(monkeypatch) -> None:
    original = pulse_module.build_business_display_coverage_report

    def drifted_coverage(*args, **kwargs):
        payload = original(*args, **kwargs)
        payload["summary"] = dict(payload["summary"])
        payload["summary"]["route_gap_count"] = 1
        return payload

    monkeypatch.setattr(
        pulse_module,
        "build_business_display_coverage_report",
        drifted_coverage,
    )

    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["status"] == "fail"
    assert "business_display.route_gap_count expected 0, got 1" in report["drift_errors"]


def test_system_audit_pulse_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T19:45:00+08:00",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["report_kind"] == "system_audit_pulse"
    assert payload["status"] == "fail"
    assert payload["full_score_ready"] is False
    assert payload["open_blocker_count"] == 5
    assert payload["calculation_post_owner_plan_renderer_sync"] is True
    assert payload["blocker_intake_board"]["next_blocker_id"] == (
        "calculation-display-p1-decisions"
    )
    assert payload["blocker_intake_board"]["next_blocker_detail"][
        "responsible_owner_type"
    ] == "business_owner_and_metric_governance"
    assert payload["completion_snapshot"]["calculation_packet_p1_count"] == 8
    assert payload["completion_snapshot"]["calculation_meeting_record_complete"] is False
    assert payload["completion_snapshot"]["calculation_missing_meeting_field_count"] == 8
    assert (
        payload["completion_snapshot"][
            "calculation_post_owner_ready_for_implementation_count"
        ]
        == 0
    )
    assert (
        payload["completion_snapshot"][
            "calculation_post_owner_owner_decision_capture_complete"
        ]
        is False
    )
    assert (
        payload["completion_snapshot"][
            "calculation_post_owner_non_implementation_decision_count"
        ]
        == 0
    )
    assert payload["completion_snapshot"]["calculation_post_owner_blocking_reasons"] == [
        "owner_decision_capture_incomplete"
    ]
    assert payload["completion_snapshot"]["calculation_post_owner_incomplete_count"] == 8
    assert (
        payload["completion_snapshot"][
            "calculation_post_owner_invalid_selected_decision_count"
        ]
        == 0
    )
    assert (
        payload["completion_snapshot"]["calculation_post_owner_global_gate_ready"]
        is False
    )
    assert (
        payload["completion_snapshot"]["calculation_post_owner_plan_renderer_sync"]
        is True
    )
    assert payload["completion_snapshot"]["follow_up_completion_order_status"] == "pass"
    assert payload["strict_gate_matrix"]["strict_pass_gate_count"] == 1
    assert payload["strict_gate_matrix"]["gate_count"] == 8
    assert payload["all_page_readiness"]["source"] == "manifest_last_full_readiness"
    assert payload["drift_errors"] == EXPECTED_DRIFT_ERRORS


def test_system_audit_pulse_formats_markdown_without_approval() -> None:
    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    markdown = format_markdown_pulse(report)

    assert markdown.startswith("# System Audit Pulse")
    assert "- Completion state: `not_complete`" in markdown
    assert "- Open blockers: `5`" in markdown
    assert "- Next blocker: `calculation-display-p1-decisions`" in markdown
    assert "`business_contract_certified=0`" in markdown
    assert "`route_gaps=0`" in markdown
    assert "`owner=business_owner_and_metric_governance`" in markdown
    assert "## Next Blocker" in markdown
    assert (
        "`python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured`"
    ) in markdown
    assert "`p1_packet=8`" in markdown
    assert "`meeting_record=false`" in markdown
    assert "`missing_meeting_fields=8`" in markdown
    assert "`post_owner_ready=0`" in markdown
    assert "`post_owner_incomplete=8`" in markdown
    assert "`post_owner_invalid_selected=0`" in markdown
    assert "`post_owner_gate=false`" in markdown
    assert "`post_owner_sync=true`" in markdown
    assert "`order_guard=pass`" in markdown
    assert "`pass=1/8`" in markdown
    assert "`unexpected=1`" in markdown
    assert "`direct_evidence_null=0`" in markdown
    assert "`audit_review_null=0`" in markdown
    assert "test_output/security-scans/osv-report.json" in markdown
    assert "test_output/security-scans/gitleaks-report.json" in markdown
    assert "does not approve metrics" in markdown
    assert "governance records" in markdown


def test_system_audit_pulse_cli_outputs_markdown() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T19:45:00+08:00",
            "--format",
            "markdown",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    assert "# System Audit Pulse" in completed.stdout
    assert "- Completion state: `not_complete`" in completed.stdout
    assert "- Next blocker: `calculation-display-p1-decisions`" in completed.stdout
    assert "`business_contract_certified=0`" in completed.stdout
    assert "`p1_packet=8`" in completed.stdout
    assert "`meeting_record=false`" in completed.stdout
    assert "`missing_meeting_fields=8`" in completed.stdout
    assert "`post_owner_ready=0`" in completed.stdout
    assert "`post_owner_incomplete=8`" in completed.stdout
    assert "`post_owner_invalid_selected=0`" in completed.stdout
    assert "`post_owner_gate=false`" in completed.stdout
    assert "`post_owner_sync=true`" in completed.stdout
    assert "`order_guard=pass`" in completed.stdout
    assert "`pass=1/8`" in completed.stdout
    assert "does not approve metrics" in completed.stdout


def test_system_audit_pulse_cli_strict_full_score_gate_rejects_current_blockers() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T19:45:00+08:00",
            "--require-full-score-ready",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "fail"
    assert payload["full_score_ready"] is False
    assert payload["completion_state"] == "not_complete"
    assert payload["open_blocker_count"] == 5
    assert payload["drift_errors"] == EXPECTED_DRIFT_ERRORS
    assert completed.stderr == ""
