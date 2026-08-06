from __future__ import annotations

import json
import os
from pathlib import Path

import scripts.refresh_system_audit_monitoring as monitor
import scripts.system_audit_pulse as pulse


ROOT = Path(__file__).resolve().parents[1]
MONITORING_SNAPSHOT = (
    ROOT
    / "docs"
    / "audits"
    / "2026-06-10-system-audit-monitoring-snapshot.json"
)
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
EXPECTED_PULSE_DRIFT_ERRORS = [
    *EXPECTED_SECURITY_SCAN_ERRORS,
    "strict_gate_matrix.status expected 'pass', got 'fail'",
    "strict_gate_matrix.strict_pass_gate_count expected 0, got 1",
    "strict_gate_matrix.unexpected_gate_count expected 0, got 1",
]


def test_write_json_preserves_existing_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "snapshot.json"
    original = '{"status": "old"}\n'
    output_path.write_text(original, encoding="utf-8")

    def fail_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(monitor.os, "replace", fail_replace)

    try:
        monitor._write_json(output_path, {"status": "new"})
    except OSError as exc:
        assert "simulated replace failure" in str(exc)
    else:  # pragma: no cover - defensive assertion for monkeypatch failure
        raise AssertionError("expected simulated replace failure")

    assert output_path.read_text(encoding="utf-8") == original
    assert (tmp_path / ".snapshot.json.tmp").read_text(encoding="utf-8") == (
        '{\n  "status": "new"\n}\n'
    )


def test_system_audit_monitoring_refresh_keeps_all_boundaries() -> None:
    report = monitor.build_monitoring_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
        gitnexus_tool_names=[
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
        ],
    )

    assert report["report_kind"] == "system_audit_monitoring_snapshot"
    assert report["write_outputs"] is False
    assert report["evidence_scope"] == {
        "read_only": True,
        "writes_duckdb": False,
        "writes_governance_records": False,
        "writes_or_rotates_secrets": False,
        "reads_secret_values": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "promotes_candidate_data": False,
    }
    assert report["refresh_results"]["calculation_owner_decision"] == {
        "status": "owner_decision_required",
        "open_decision_count": 8,
        "captured_decision_count": 0,
        "incomplete_decision_count": 8,
        "invalid_selected_decision_count": 0,
        "invalid_status_count": 0,
        "drift_error_count": 0,
    }
    assert report["refresh_results"]["direct_app_mcp_gitnexus_tool_surface"][
        "status"
    ] == "tool_surface_unavailable_in_current_codex_app_session"
    assert report["refresh_results"]["direct_app_mcp_gitnexus_tool_surface"][
        "direct_app_mcp_evidence_captured"
    ] is False
    assert report["refresh_results"]["local_secret_hygiene"][
        "secret_values_captured"
    ] is False
    assert report["refresh_results"]["local_secret_hygiene"][
        "clears_secret_scan"
    ] is False
    assert report["refresh_results"]["ledger_pnl_direct_governance_record"][
        "record_write_status"
    ] == "not_requested"
    assert report["refresh_results"]["ledger_pnl_direct_governance_record"][
        "post_write_ready"
    ] is False
    assert report["refresh_results"]["ledger_pnl_direct_governance_record"][
        "post_write_blocking_reasons"
    ] == [
        "written_record_located",
        "governance_direct_records_ready",
        "audit_review_not_blocked_by_record_gaps",
    ]
    assert report["refresh_results"]["ledger_pnl_direct_governance_record"][
        "formal_use_allowed"
    ] is False
    assert report["refresh_results"]["ledger_pnl_direct_governance_record"][
        "closure_approved"
    ] is False
    assert report["completion_verification"]["status"] == "fail"
    assert (
        report["completion_verification"]["calculation_packet_execution_anchor_ready"]
        is True
    )
    assert (
        report["completion_verification"][
            "calculation_packet_execution_referenced_path_count"
        ]
        == 18
    )
    assert (
        report["completion_verification"][
            "calculation_packet_missing_execution_referenced_path_count"
        ]
        == 0
    )
    assert report["completion_verification"]["calculation_owner_meeting_checklist_count"] == 8
    assert (
        report["completion_verification"]["calculation_owner_meeting_material_ready"]
        is True
    )
    assert (
        report["completion_verification"][
            "calculation_owner_meeting_implementation_ready"
        ]
        is False
    )
    assert (
        report["completion_verification"][
            "calculation_owner_meeting_missing_capture_field_count"
        ]
        == 40
    )
    assert (
        report["completion_verification"]["calculation_owner_meeting_missing_field_count"]
        == 8
    )
    assert report["completion_verification"]["calculation_first_priority_count"] == 2
    assert (
        report["completion_verification"][
            "calculation_first_priority_owner_intake_ready"
        ]
        is True
    )
    assert (
        report["completion_verification"][
            "calculation_first_priority_implementation_ready"
        ]
        is False
    )
    assert (
        report["completion_verification"][
            "calculation_post_owner_ready_for_implementation_count"
        ]
        == 0
    )
    assert (
        report["completion_verification"][
            "calculation_post_owner_owner_decision_capture_complete"
        ]
        is False
    )
    assert (
        report["completion_verification"][
            "calculation_post_owner_non_implementation_decision_count"
        ]
        == 0
    )
    assert report["completion_verification"][
        "calculation_post_owner_blocking_reasons"
    ] == ["owner_decision_capture_incomplete"]
    assert (
        report["completion_verification"][
            "calculation_post_owner_incomplete_count"
        ]
        == 8
    )
    assert (
        report["completion_verification"][
            "calculation_post_owner_invalid_selected_decision_count"
        ]
        == 0
    )
    assert (
        report["completion_verification"][
            "calculation_post_owner_no_invalid_selected_decisions"
        ]
        is True
    )
    assert (
        report["completion_verification"]["calculation_post_owner_global_gate_ready"]
        is False
    )
    assert (
        report["completion_verification"]["calculation_post_owner_implementation_ready"]
        is False
    )
    assert (
        report["completion_verification"]["calculation_post_owner_plan_renderer_sync"]
        is True
    )
    assert (
        report["completion_verification"]["local_secret_owner_attestation_ready"]
        is True
    )
    assert (
        report["completion_verification"][
            "local_secret_owner_attestation_closure_approved"
        ]
        is False
    )
    assert (
        report["completion_verification"][
            "local_secret_owner_attestation_secret_value_fields_present"
        ]
        is False
    )
    assert (
        report["completion_verification"]["calculation_meeting_record_complete"]
        is False
    )
    assert report["completion_verification"]["calculation_missing_meeting_field_count"] == 8
    assert (
        report["completion_verification"]["follow_up_completion_order_status"] == "pass"
    )
    assert report["completion_verification"]["follow_up_completion_order_error_count"] == 0
    assert report["completion_verification"]["error_count"] == 2
    assert report["completion_verification"]["errors"] == EXPECTED_SECURITY_SCAN_ERRORS
    assert report["pulse"]["status"] == "fail"
    assert report["pulse"]["completion_state"] == "not_complete"
    assert report["pulse"]["open_blocker_count"] == 5
    assert report["pulse"]["next_blocker_id"] == "calculation-display-p1-decisions"
    assert report["pulse"]["next_blocker_detail"]["responsible_owner_type"] == (
        "business_owner_and_metric_governance"
    )
    assert report["pulse"]["next_blocker_detail"]["strict_gate_command"] == (
        "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured"
    )
    assert report["pulse"]["drift_error_count"] == 5
    assert report["pulse"]["drift_errors"] == EXPECTED_PULSE_DRIFT_ERRORS
    assert report["blocker_intake_board"]["status"] == "open_external_input_required"
    assert report["blocker_intake_board"]["blocker_count"] == 5
    assert report["blocker_intake_board"]["completion_order"] == [
        "calculation-display-p1-decisions",
        "ledger-pnl-direct-governance-record",
        "owner-approval-7-pages",
        "direct-app-mcp-gitnexus-evidence",
        "local-secret-hygiene",
    ]
    assert report["blocker_intake_board"]["next_blocker_id"] == (
        "calculation-display-p1-decisions"
    )
    assert report["blocker_intake_board"]["next_blocker_detail"] == (
        report["pulse"]["next_blocker_detail"]
    )
    assert report["blocker_intake_board"]["evidence_scope"] == {
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
    assert "does not approve metrics" in report["blocker_intake_board"]["boundary"]
    assert report["strict_gate_matrix"]["status"] == "fail"
    assert report["strict_gate_matrix"]["full_score_ready"] is False
    assert report["strict_gate_matrix"]["open_blocker_count"] == 5
    assert report["strict_gate_matrix"]["completion_order_guard_status"] == "pass"
    assert report["strict_gate_matrix"]["completion_order_guard_error_count"] == 0
    assert report["strict_gate_matrix"]["gate_count"] == 8
    assert report["strict_gate_matrix"]["expected_blocked_gate_count"] == 8
    assert report["strict_gate_matrix"]["strict_pass_gate_count"] == 1
    assert report["strict_gate_matrix"]["unexpected_gate_count"] == 1
    assert report["strict_gate_matrix"]["guard_error_count"] == 0
    assert report["strict_gate_matrix"]["guard_errors"] == []
    assert {
        gate["gate_id"] for gate in report["strict_gate_matrix"]["gates"]
    } == {
        "system-audit-full-score",
        "completion-zero-open-blockers",
        "monitoring-zero-open-blockers",
        "calculation-p1-owner-decisions-captured",
        "calculation-p1-post-owner-implementation-ready",
        "ledger-pnl-written-record-located",
        "direct-app-mcp-gitnexus-evidence-captured",
        "local-secret-hygiene-clean-boundary",
    }
    assert report["latest_session_recheck"]["checked_at"] == "2026-06-10T21:25:00+08:00"
    assert report["latest_session_recheck"]["closure_effect"] == "none"
    assert report["latest_session_recheck"]["open_blocker_count"] == 5
    assert report["latest_session_recheck"]["next_blocker"] == (
        report["pulse"]["next_blocker_detail"]
    )
    assert report["latest_session_recheck"]["strict_gate_matrix"] == {
        "status": "fail",
        "gate_count": 8,
        "strict_pass_gate_count": 1,
        "unexpected_gate_count": 1,
        "completion_order_guard_status": "pass",
        "guard_error_count": 0,
    }
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "checked_at"
    ] == "2026-06-27T13:05:14+08:00"
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_primary_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_gitnexus_tool_count"
    ] == 3
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_moss_general_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_moss_named_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "relevant_direct_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "direct_app_mcp_evidence_captured"
    ] is False
    assert report["latest_session_recheck"]["local_secret_hygiene"][
        "values_read"
    ] is False
    assert report["latest_session_recheck"]["ledger_pnl_direct_governance_record"][
        "record_write_status"
    ] == "not_requested"
    assert report["latest_session_recheck"]["ledger_pnl_direct_governance_record"][
        "post_write_ready"
    ] is False
    assert report["latest_session_recheck"]["ledger_pnl_direct_governance_record"][
        "post_write_blocking_reasons"
    ] == [
        "written_record_located",
        "governance_direct_records_ready",
        "audit_review_not_blocked_by_record_gaps",
    ]
    assert report["latest_session_recheck"]["calculation_owner_decision"][
        "captured_decision_count"
    ] == 0
    assert report["latest_session_recheck"]["calculation_owner_decision"][
        "incomplete_decision_count"
    ] == 8
    assert report["latest_session_recheck"]["calculation_owner_decision"][
        "invalid_selected_decision_count"
    ] == 0
    assert report["latest_session_recheck"]["calculation_owner_decision"][
        "invalid_status_count"
    ] == 0
    assert "does not write DuckDB or governance records" in report["boundary"]
    assert "read or rotate secret values" in report["boundary"]


def test_system_audit_monitoring_refresh_locks_current_p1_counts_as_literals() -> None:
    report = monitor.build_monitoring_snapshot(
        generated_at="2026-08-06T22:30:00+08:00",
        gitnexus_tool_names=[
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
        ],
    )

    calculation = report["refresh_results"]["calculation_owner_decision"]
    assert calculation["open_decision_count"] == 8
    assert calculation["incomplete_decision_count"] == 8
    assert report["pulse"]["next_blocker_detail"]["required_output_count"] == 9
    assert report["blocker_intake_board"]["next_blocker_detail"][
        "required_output_count"
    ] == 9


def test_system_audit_monitoring_refresh_uses_blocker_evidence_timestamps() -> None:
    report = monitor.build_monitoring_snapshot(
        generated_at="2026-08-06T22:30:00+08:00",
    )

    recheck = report["latest_session_recheck"]
    assert recheck["checked_at"] == "2026-08-06T22:30:00+08:00"
    assert recheck["calculation_owner_decision"]["checked_at"] == (
        "2026-08-06T22:30:00+08:00"
    )
    assert recheck["ledger_pnl_direct_governance_record"]["checked_at"] == (
        "2026-06-10T21:25:00+08:00"
    )
    assert recheck["direct_app_mcp_gitnexus_tool_surface"]["checked_at"] == (
        "2026-06-27T13:05:14+08:00"
    )
    assert recheck["local_secret_hygiene"]["checked_at"] == (
        "2026-06-27T13:05:14+08:00"
    )
    assert report["repo_root"] == "."
    assert report["output_paths"]["system_audit_pulse_snapshot"] == (
        "docs/audits/2026-06-10-system-audit-pulse-snapshot.json"
    )


def test_system_audit_monitoring_refresh_does_not_read_stale_strict_gate_summary(
    monkeypatch,
) -> None:
    def fail_if_stale_summary_is_read(**_: object) -> dict[str, object]:
        raise AssertionError("monitoring refresh must not read existing strict gate summary")

    monkeypatch.setattr(pulse, "_strict_gate_summary", fail_if_stale_summary_is_read)

    report = monitor.build_monitoring_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
        gitnexus_tool_names=[
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
        ],
    )

    assert report["pulse"]["status"] == "fail"
    assert report["pulse"]["drift_errors"] == EXPECTED_PULSE_DRIFT_ERRORS
    assert report["strict_gate_matrix"]["status"] == "fail"
    assert report["strict_gate_matrix"]["open_blocker_count"] == 5
    assert report["strict_gate_matrix"]["strict_pass_gate_count"] == 1


def test_system_audit_monitoring_refresh_does_not_reuse_stale_monitoring_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stale_monitoring = json.loads(MONITORING_SNAPSHOT.read_text(encoding="utf-8"))
    stale_monitoring["completion_verification"]["status"] = "fail"
    stale_monitoring["completion_verification"]["errors"] = ["stale monitoring failure"]
    stale_monitoring["completion_verification"]["error_count"] = 1
    stale_monitoring["pulse"]["status"] = "fail"
    stale_monitoring["pulse"]["drift_errors"] = ["stale monitoring failure"]
    stale_monitoring["pulse"]["drift_error_count"] = 1
    stale_path = tmp_path / "stale-monitoring.json"
    stale_path.write_text(
        json.dumps(stale_monitoring, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor, "DEFAULT_OUTPUT", stale_path)

    report = monitor.build_monitoring_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
        gitnexus_tool_names=[
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
        ],
    )

    assert report["completion_verification"]["status"] == "fail"
    assert report["completion_verification"]["errors"] == EXPECTED_SECURITY_SCAN_ERRORS
    assert "stale monitoring failure" not in report["completion_verification"]["errors"]
    assert report["pulse"]["status"] == "fail"
    assert report["pulse"]["drift_errors"] == EXPECTED_PULSE_DRIFT_ERRORS
    assert "stale monitoring failure" not in report["pulse"]["drift_errors"]


def test_system_audit_monitoring_refresh_cli_writes_monitor_report_only(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "monitoring.json"

    exit_code = monitor.main(
        [
            "--generated-at",
            "2026-06-10T21:25:00+08:00",
            "--gitnexus-tool-names",
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["generated_at"] == "2026-06-10T21:25:00+08:00"
    assert payload["latest_session_recheck"]["checked_at"] == "2026-06-10T21:25:00+08:00"
    assert payload["write_outputs"] is False
    assert payload["completion_verification"]["status"] == "fail"
    assert payload["completion_verification"]["errors"] == EXPECTED_SECURITY_SCAN_ERRORS
    assert (
        payload["completion_verification"]["calculation_packet_execution_anchor_ready"]
        is True
    )
    assert (
        payload["completion_verification"][
            "calculation_packet_execution_referenced_path_count"
        ]
        == 18
    )
    assert (
        payload["completion_verification"][
            "calculation_packet_missing_execution_referenced_path_count"
        ]
        == 0
    )
    assert (
        payload["completion_verification"]["calculation_owner_meeting_checklist_count"]
        == 8
    )
    assert (
        payload["completion_verification"]["calculation_owner_meeting_material_ready"]
        is True
    )
    assert (
        payload["completion_verification"][
            "calculation_owner_meeting_implementation_ready"
        ]
        is False
    )
    assert (
        payload["completion_verification"][
            "calculation_owner_meeting_missing_capture_field_count"
        ]
        == 40
    )
    assert (
        payload["completion_verification"]["calculation_owner_meeting_missing_field_count"]
        == 8
    )
    assert payload["completion_verification"]["calculation_first_priority_count"] == 2
    assert (
        payload["completion_verification"][
            "calculation_first_priority_owner_intake_ready"
        ]
        is True
    )
    assert (
        payload["completion_verification"][
            "calculation_first_priority_implementation_ready"
        ]
        is False
    )
    assert (
        payload["completion_verification"][
            "calculation_post_owner_ready_for_implementation_count"
        ]
        == 0
    )
    assert (
        payload["completion_verification"][
            "calculation_post_owner_owner_decision_capture_complete"
        ]
        is False
    )
    assert (
        payload["completion_verification"][
            "calculation_post_owner_non_implementation_decision_count"
        ]
        == 0
    )
    assert payload["completion_verification"][
        "calculation_post_owner_blocking_reasons"
    ] == ["owner_decision_capture_incomplete"]
    assert payload["completion_verification"]["calculation_post_owner_incomplete_count"] == 8
    assert (
        payload["completion_verification"]["calculation_post_owner_global_gate_ready"]
        is False
    )
    assert (
        payload["completion_verification"]["calculation_post_owner_implementation_ready"]
        is False
    )
    assert (
        payload["completion_verification"]["calculation_post_owner_plan_renderer_sync"]
        is True
    )
    assert (
        payload["completion_verification"]["local_secret_owner_attestation_ready"]
        is True
    )
    assert (
        payload["completion_verification"][
            "local_secret_owner_attestation_closure_approved"
        ]
        is False
    )
    assert (
        payload["completion_verification"][
            "local_secret_owner_attestation_secret_value_fields_present"
        ]
        is False
    )
    assert (
        payload["completion_verification"]["calculation_meeting_record_complete"]
        is False
    )
    assert payload["completion_verification"]["calculation_missing_meeting_field_count"] == 8
    assert (
        payload["completion_verification"]["follow_up_completion_order_status"] == "pass"
    )
    assert payload["pulse"]["status"] == "fail"
    assert payload["pulse"]["drift_errors"] == EXPECTED_PULSE_DRIFT_ERRORS
    assert payload["pulse"]["calculation_post_owner_plan_renderer_sync"] is True
    assert payload["pulse"]["next_blocker_id"] == "calculation-display-p1-decisions"
    assert payload["pulse"]["next_blocker_detail"]["strict_gate_command"] == (
        "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured"
    )
    assert payload["blocker_intake_board"]["next_blocker_id"] == (
        "calculation-display-p1-decisions"
    )
    assert (
        payload["latest_session_recheck"][
            "calculation_post_owner_plan_renderer_sync"
        ]
        is True
    )
    assert payload["blocker_intake_board"]["next_blocker_detail"] == (
        payload["pulse"]["next_blocker_detail"]
    )
    assert payload["strict_gate_matrix"]["strict_pass_gate_count"] == 1
    assert payload["strict_gate_matrix"]["completion_order_guard_status"] == "pass"
    assert payload["strict_gate_matrix"]["guard_error_count"] == 0


def test_system_audit_monitoring_refresh_preserves_existing_tool_surface_observations() -> None:
    report = monitor.build_monitoring_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
    )

    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "checked_at"
    ] == "2026-06-27T13:05:14+08:00"
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_gitnexus_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_moss_general_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "returned_moss_named_tool_count"
    ] == 0
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "relevant_direct_tool_count"
    ] == 0
