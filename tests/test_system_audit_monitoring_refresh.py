from __future__ import annotations

import json
from pathlib import Path

import scripts.refresh_system_audit_monitoring as monitor


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
    assert report["completion_verification"]["error_count"] == 0
    assert report["pulse"]["status"] == "pass"
    assert report["pulse"]["completion_state"] == "not_complete"
    assert report["pulse"]["open_blocker_count"] == 5
    assert report["pulse"]["drift_error_count"] == 0
    assert "does not write DuckDB or governance records" in report["boundary"]
    assert "read or rotate secret values" in report["boundary"]


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
    assert payload["write_outputs"] is False
    assert payload["completion_verification"]["status"] == "pass"
    assert payload["pulse"]["status"] == "pass"
