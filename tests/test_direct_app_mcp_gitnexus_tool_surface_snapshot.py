from __future__ import annotations

import json
from pathlib import Path

import scripts.refresh_direct_app_mcp_gitnexus_tool_surface_snapshot as refresh_module


def test_direct_app_tool_surface_snapshot_preserves_fail_closed_gap() -> None:
    snapshot = refresh_module.build_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
        gitnexus_tool_names=[
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
        ],
    )

    assert snapshot["report_kind"] == "direct_app_mcp_gitnexus_tool_surface_snapshot"
    assert snapshot["status"] == {
        "overall": "tool_surface_unavailable_in_current_codex_app_session",
        "fail_closed": True,
        "direct_app_mcp_evidence_captured": False,
        "direct_gitnexus_evidence_captured": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "certifies_routes": False,
    }
    assert snapshot["tool_discovery"]["checked_at"] == "2026-06-10T21:25:00+08:00"
    assert snapshot["tool_discovery"]["discovered_tool_count"] == 0
    assert snapshot["detected_direct_servers"] == []
    assert set(snapshot["missing_direct_servers"]) == set(
        refresh_module.EXPECTED_DIRECT_SERVERS
    )

    focused_rechecks = {item["query"]: item for item in snapshot["focused_rechecks"]}
    gitnexus_recheck = focused_rechecks[refresh_module.GITNEXUS_QUERY]
    assert gitnexus_recheck["returned_tool_count"] == 3
    assert gitnexus_recheck["returned_tools"] == [
        {
            "name": "codex_app.handoff_thread",
            "classification": "codex_app_thread_management",
            "relevant_direct_moss_or_gitnexus_evidence": False,
        },
        {
            "name": "codex_app.fork_thread",
            "classification": "codex_app_thread_management",
            "relevant_direct_moss_or_gitnexus_evidence": False,
        },
        {
            "name": "codex_app.automation_update",
            "classification": "codex_app_automation_management",
            "relevant_direct_moss_or_gitnexus_evidence": False,
        },
    ]
    assert all(
        value == "not_callable_as_direct_codex_app_tool_in_this_session"
        for value in snapshot["direct_evidence_gap"].values()
    )
    assert snapshot["interpretation"] == {
        "repo_configuration_status": "expected_servers_declared_locally",
        "current_app_tool_surface_status": "direct_moss_and_gitnexus_tools_not_exposed",
        "local_stdio_evidence_status": "fallback_only_not_direct_app_surface_evidence",
        "closure_effect": "none",
    }
    assert "does not approve metrics" in snapshot["boundary"]
    assert "does not write governance records" in snapshot["boundary"]


def test_direct_app_tool_surface_snapshot_does_not_close_when_tools_are_exposed() -> None:
    snapshot = refresh_module.build_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
        primary_tool_names=[
            "mcp__moss_data_catalog.describe_table",
            "mcp__gitnexus.query",
        ],
    )

    assert snapshot["status"]["overall"] == (
        "partial_tool_surface_exposed_evidence_capture_required"
    )
    assert snapshot["status"]["fail_closed"] is True
    assert snapshot["status"]["direct_app_mcp_evidence_captured"] is False
    assert snapshot["status"]["direct_gitnexus_evidence_captured"] is False
    assert snapshot["interpretation"]["closure_effect"] == "none"
    assert snapshot["direct_evidence_gap"]["gitnexus"] == (
        "direct_tool_exposed_but_evidence_not_captured"
    )
    assert snapshot["direct_evidence_gap"]["moss-data-catalog"] == (
        "direct_tool_exposed_but_evidence_not_captured"
    )
    assert snapshot["direct_evidence_gap"]["moss-lineage-evidence"] == (
        "not_callable_as_direct_codex_app_tool_in_this_session"
    )


def test_direct_app_tool_surface_snapshot_cli_writes_only_output(tmp_path: Path) -> None:
    output_path = tmp_path / "direct-tool-snapshot.json"

    exit_code = refresh_module.main(
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
    assert payload["refresh_command"] == refresh_module.REFRESH_COMMAND
    assert payload["status"]["overall"] == (
        "tool_surface_unavailable_in_current_codex_app_session"
    )
    assert payload["status"]["writes_governance_records"] is False
    assert payload["tool_discovery"]["discovered_tool_count"] == 0


def test_direct_app_tool_surface_snapshot_cli_strict_gate_rejects_missing_evidence(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "direct-tool-snapshot.json"

    exit_code = refresh_module.main(
        [
            "--generated-at",
            "2026-06-10T21:25:00+08:00",
            "--gitnexus-tool-names",
            "codex_app.handoff_thread",
            "codex_app.fork_thread",
            "codex_app.automation_update",
            "--output",
            str(output_path),
            "--require-direct-evidence-captured",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"]["overall"] == (
        "tool_surface_unavailable_in_current_codex_app_session"
    )
    assert payload["status"]["direct_app_mcp_evidence_captured"] is False
    assert payload["status"]["direct_gitnexus_evidence_captured"] is False
    assert set(payload["missing_direct_servers"]) == set(
        refresh_module.EXPECTED_DIRECT_SERVERS
    )
