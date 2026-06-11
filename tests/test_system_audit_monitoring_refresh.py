from __future__ import annotations

import json
from pathlib import Path

import scripts.refresh_system_audit_monitoring as monitor
import scripts.system_audit_pulse as pulse


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
        "open_decision_count": 10,
        "captured_decision_count": 0,
        "incomplete_decision_count": 10,
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
        "formal_use_allowed"
    ] is False
    assert report["refresh_results"]["ledger_pnl_direct_governance_record"][
        "closure_approved"
    ] is False
    assert report["completion_verification"]["status"] == "pass"
    assert (
        report["completion_verification"]["follow_up_completion_order_status"] == "pass"
    )
    assert report["completion_verification"]["follow_up_completion_order_error_count"] == 0
    assert report["completion_verification"]["error_count"] == 0
    assert report["pulse"]["status"] == "pass"
    assert report["pulse"]["completion_state"] == "not_complete"
    assert report["pulse"]["open_blocker_count"] == 5
    assert report["pulse"]["drift_error_count"] == 0
    assert report["blocker_intake_board"] == {
        "status": "open_external_input_required",
        "blocker_count": 5,
        "completion_order": [
            "calculation-display-p1-decisions",
            "ledger-pnl-direct-governance-record",
            "owner-approval-7-pages",
            "direct-app-mcp-gitnexus-evidence",
            "local-secret-hygiene",
        ],
        "next_blocker_id": "calculation-display-p1-decisions",
        "evidence_scope": {
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
        },
        "boundary": (
            "This blocker intake board is read-only. It does not approve metrics, pages, "
            "business-owner signoff, governance records, route certification, direct App "
            "MCP/GitNexus evidence, local secret hygiene, or Ledger PnL --write execution."
        ),
    }
    assert report["strict_gate_matrix"]["status"] == "pass"
    assert report["strict_gate_matrix"]["full_score_ready"] is False
    assert report["strict_gate_matrix"]["open_blocker_count"] == 5
    assert report["strict_gate_matrix"]["completion_order_guard_status"] == "pass"
    assert report["strict_gate_matrix"]["completion_order_guard_error_count"] == 0
    assert report["strict_gate_matrix"]["gate_count"] == 7
    assert report["strict_gate_matrix"]["expected_blocked_gate_count"] == 7
    assert report["strict_gate_matrix"]["strict_pass_gate_count"] == 0
    assert report["strict_gate_matrix"]["unexpected_gate_count"] == 0
    assert report["strict_gate_matrix"]["guard_error_count"] == 0
    assert report["strict_gate_matrix"]["guard_errors"] == []
    assert {
        gate["gate_id"] for gate in report["strict_gate_matrix"]["gates"]
    } == {
        "system-audit-full-score",
        "completion-zero-open-blockers",
        "monitoring-zero-open-blockers",
        "calculation-p1-owner-decisions-captured",
        "ledger-pnl-written-record-located",
        "direct-app-mcp-gitnexus-evidence-captured",
        "local-secret-hygiene-clean-boundary",
    }
    assert report["latest_session_recheck"]["checked_at"] == "2026-06-10T21:25:00+08:00"
    assert report["latest_session_recheck"]["closure_effect"] == "none"
    assert report["latest_session_recheck"]["open_blocker_count"] == 5
    assert report["latest_session_recheck"]["strict_gate_matrix"] == {
        "status": "pass",
        "gate_count": 7,
        "strict_pass_gate_count": 0,
        "unexpected_gate_count": 0,
        "completion_order_guard_status": "pass",
        "guard_error_count": 0,
    }
    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "checked_at"
    ] == "2026-06-10T21:25:00+08:00"
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
    assert report["latest_session_recheck"]["calculation_owner_decision"][
        "captured_decision_count"
    ] == 0
    assert report["latest_session_recheck"]["calculation_owner_decision"][
        "incomplete_decision_count"
    ] == 10
    assert "does not write DuckDB or governance records" in report["boundary"]
    assert "read or rotate secret values" in report["boundary"]


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

    assert report["pulse"]["status"] == "pass"
    assert report["pulse"]["drift_error_count"] == 0
    assert report["strict_gate_matrix"]["status"] == "pass"
    assert report["strict_gate_matrix"]["open_blocker_count"] == 5
    assert report["strict_gate_matrix"]["strict_pass_gate_count"] == 0


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
    assert exit_code == 0
    assert payload["generated_at"] == "2026-06-10T21:25:00+08:00"
    assert payload["latest_session_recheck"]["checked_at"] == "2026-06-10T21:25:00+08:00"
    assert payload["write_outputs"] is False
    assert payload["completion_verification"]["status"] == "pass"
    assert (
        payload["completion_verification"]["follow_up_completion_order_status"] == "pass"
    )
    assert payload["pulse"]["status"] == "pass"
    assert payload["blocker_intake_board"]["next_blocker_id"] == (
        "calculation-display-p1-decisions"
    )
    assert payload["strict_gate_matrix"]["strict_pass_gate_count"] == 0
    assert payload["strict_gate_matrix"]["completion_order_guard_status"] == "pass"
    assert payload["strict_gate_matrix"]["guard_error_count"] == 0


def test_system_audit_monitoring_refresh_preserves_existing_tool_surface_observations() -> None:
    report = monitor.build_monitoring_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
    )

    assert report["latest_session_recheck"]["direct_app_mcp_gitnexus_tool_surface"][
        "checked_at"
    ] == "2026-06-10T21:25:00+08:00"
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
