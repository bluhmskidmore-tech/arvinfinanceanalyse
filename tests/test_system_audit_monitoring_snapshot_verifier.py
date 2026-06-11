from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_system_audit_monitoring_snapshot import verify_monitoring_snapshot


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_system_audit_monitoring_snapshot.py"
MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"
ARTIFACT_KEYS = [
    "system_audit_monitoring_snapshot",
    "completion_snapshot",
    "system_audit_pulse_snapshot",
    "calculation_owner_decision_snapshot",
    "direct_app_mcp_gitnexus_tool_surface_snapshot",
    "local_secret_hygiene_snapshot",
    "ledger_pnl_direct_governance_record_snapshot",
    "owner_governance_follow_up_packet",
    "owner_governance_follow_up_brief_zh",
    "calculation_owner_decision_matrix",
    "calculation_owner_decision_packet",
    "calculation_owner_meeting_checklist",
    "calculation_first_priority_readiness_packet",
    "calculation_post_owner_execution_plan",
]


def _copy_monitoring_package(tmp_path: Path) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit_dir = tmp_path / "docs" / "audits"
    audit_dir.mkdir(parents=True)
    original_follow_up_packet = manifest["artifacts"]["owner_governance_follow_up_packet"]
    for key in ARTIFACT_KEYS:
        source = ROOT / manifest["artifacts"][key]
        target = audit_dir / source.name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        manifest["artifacts"][key] = f"docs/audits/{source.name}"

    completion_path = tmp_path / manifest["artifacts"]["completion_snapshot"]
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    for source_key in [
        "owner_governance_follow_up_packet",
        "owner_governance_follow_up_brief_zh",
        "calculation_first_priority_readiness_packet",
        "calculation_owner_meeting_checklist",
        "calculation_post_owner_execution_plan",
        "system_audit_monitoring_snapshot",
    ]:
        completion["source_artifacts"][source_key] = manifest["artifacts"][source_key]
    completion_path.write_text(
        json.dumps(completion, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    brief_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    brief = brief_path.read_text(encoding="utf-8").replace(
        original_follow_up_packet,
        manifest["artifacts"]["owner_governance_follow_up_packet"],
    )
    brief = brief.replace(
        "`2026-06-10-owner-governance-follow-up-packet.json`",
        f"`{manifest['artifacts']['owner_governance_follow_up_packet']}`",
    )
    brief_path.write_text(brief, encoding="utf-8")

    follow_up_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    follow_up = json.loads(follow_up_path.read_text(encoding="utf-8"))
    for artifact in [
        required_artifact
        for blocker in follow_up.get("blocker_packets", [])
        for required_artifact in blocker.get("required_input_artifacts", [])
        if isinstance(required_artifact, str) and not required_artifact.startswith("<")
    ]:
        source = ROOT / artifact
        if not source.exists():
            continue
        target = tmp_path / artifact
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    manifest_path = audit_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _load_package_json(manifest_path: Path, key: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return json.loads((manifest_path.parents[2] / manifest["artifacts"][key]).read_text(encoding="utf-8"))


def _write_package_json(manifest_path: Path, key: str, payload: dict) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = manifest_path.parents[2] / manifest["artifacts"][key]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_verify_monitoring_snapshot_passes_for_checked_in_audit_package() -> None:
    result = verify_monitoring_snapshot(manifest_path=MANIFEST)

    assert result["status"] == "pass"
    assert result["generated_at"] == "2026-06-10T21:25:00+08:00"
    assert result["open_blocker_count"] == 5
    assert result["completion_status"] == "pass"
    assert result["completion_order_guard_status"] == "pass"
    assert result["pulse_status"] == "pass"
    assert result["pulse_completion_state"] == "not_complete"
    assert result["strict_gate_status"] == "pass"
    assert result["strict_pass_gate_count"] == 0
    assert result["strict_gate_count"] == 8
    assert result["strict_completion_order_guard_status"] == "pass"
    assert result["errors"] == []


def test_verify_monitoring_snapshot_fails_when_monitoring_write_flag_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["write_outputs"] = False
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "monitoring write_outputs expected True, got False" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_ledger_formal_use_is_promoted(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["ledger_pnl_direct_governance_record"][
        "formal_use_allowed"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "Ledger PnL formal_use_allowed must be false" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_direct_app_evidence_is_claimed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["direct_app_mcp_gitnexus_tool_surface"][
        "direct_app_mcp_evidence_captured"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "direct App MCP evidence captured must be false" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_secret_hygiene_is_cleared(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["local_secret_hygiene"]["clears_secret_scan"] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "local secret refresh clears_secret_scan must be false" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_latest_recheck_claims_closure(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["latest_session_recheck"]["closure_effect"] = "closed"
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "latest session recheck closure_effect expected 'none', got 'closed'" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_latest_direct_recheck_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    expected_checked_at = monitoring["latest_session_recheck"]["checked_at"]
    direct = monitoring["latest_session_recheck"][
        "direct_app_mcp_gitnexus_tool_surface"
    ]
    direct["checked_at"] = "2026-06-10T21:26:00+08:00"
    direct["returned_moss_general_tool_count"] = 1
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        f"latest session direct App checked_at expected '{expected_checked_at}', "
        "got '2026-06-10T21:26:00+08:00'"
    ) in result["errors"]
    assert (
        "latest session returned MOSS general tool count expected 0, got 1"
        in result["errors"]
    )


def test_verify_monitoring_snapshot_fails_when_pulse_completion_state_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["pulse"]["completion_state"] = "complete"
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "monitoring pulse completion_state expected 'not_complete', got 'complete'" in result[
        "errors"
    ]


def test_verify_monitoring_snapshot_fails_when_completion_order_guard_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"][
        "follow_up_completion_order_status"
    ] = "missing"
    monitoring["completion_verification"]["follow_up_completion_order_error_count"] = 1
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion follow_up_completion_order_status expected 'pass', got 'missing'"
        in result["errors"]
    )
    assert (
        "monitoring completion follow_up_completion_order_error_count expected 0, got 1"
        in result["errors"]
    )


def test_verify_monitoring_snapshot_fails_when_completion_packet_count_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"]["calculation_packet_p1_count"] = 9
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion calculation_packet_p1_count expected 10, got 9"
        in result["errors"]
    )


def test_verify_monitoring_snapshot_fails_when_completion_packet_anchor_summary_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"][
        "calculation_packet_execution_anchor_ready"
    ] = False
    monitoring["completion_verification"][
        "calculation_packet_execution_referenced_path_count"
    ] = 23
    monitoring["completion_verification"][
        "calculation_packet_missing_execution_referenced_path_count"
    ] = 1
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion calculation_packet_execution_anchor_ready "
        "expected True, got False"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_packet_execution_referenced_path_count "
        "expected 24, got 23"
    ) in result["errors"]
    assert (
        "monitoring completion "
        "calculation_packet_missing_execution_referenced_path_count expected 0, got 1"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_owner_meeting_summary_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"][
        "calculation_owner_meeting_checklist_count"
    ] = 9
    monitoring["completion_verification"][
        "calculation_owner_meeting_material_ready"
    ] = False
    monitoring["completion_verification"][
        "calculation_owner_meeting_implementation_ready"
    ] = True
    monitoring["completion_verification"][
        "calculation_owner_meeting_missing_capture_field_count"
    ] = 39
    monitoring["completion_verification"][
        "calculation_owner_meeting_missing_field_count"
    ] = 7
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion calculation_owner_meeting_checklist_count "
        "expected 10, got 9"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_owner_meeting_material_ready "
        "expected True, got False"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_owner_meeting_implementation_ready "
        "expected False, got True"
    ) in result["errors"]
    assert (
        "monitoring completion "
        "calculation_owner_meeting_missing_capture_field_count expected 50, got 39"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_owner_meeting_missing_field_count "
        "expected 8, got 7"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_first_priority_summary_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"]["calculation_first_priority_count"] = 2
    monitoring["completion_verification"][
        "calculation_first_priority_owner_intake_ready"
    ] = False
    monitoring["completion_verification"][
        "calculation_first_priority_implementation_ready"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion calculation_first_priority_count expected 3, got 2"
        in result["errors"]
    )
    assert (
        "monitoring completion calculation_first_priority_owner_intake_ready "
        "expected True, got False"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_first_priority_implementation_ready "
        "expected False, got True"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_post_owner_summary_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"][
        "calculation_post_owner_ready_for_implementation_count"
    ] = 1
    monitoring["completion_verification"][
        "calculation_post_owner_owner_decision_capture_complete"
    ] = True
    monitoring["completion_verification"][
        "calculation_post_owner_non_implementation_decision_count"
    ] = 1
    monitoring["completion_verification"][
        "calculation_post_owner_blocking_reasons"
    ] = []
    monitoring["completion_verification"]["calculation_post_owner_incomplete_count"] = 9
    monitoring["completion_verification"][
        "calculation_post_owner_global_gate_ready"
    ] = True
    monitoring["completion_verification"][
        "calculation_post_owner_implementation_ready"
    ] = True
    monitoring["completion_verification"][
        "calculation_post_owner_plan_renderer_sync"
    ] = False
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert (
        "monitoring completion "
        "calculation_post_owner_ready_for_implementation_count expected 0, got 1"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_post_owner_incomplete_count "
        "expected 10, got 9"
    ) in result["errors"]
    assert (
        "monitoring completion "
        "calculation_post_owner_owner_decision_capture_complete "
        "expected False, got True"
    ) in result["errors"]
    assert (
        "monitoring completion "
        "calculation_post_owner_non_implementation_decision_count "
        "expected 0, got 1"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_post_owner_blocking_reasons "
        "expected ['owner_decision_capture_incomplete'], got []"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_post_owner_global_gate_ready "
        "expected False, got True"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_post_owner_implementation_ready "
        "expected False, got True"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_post_owner_plan_renderer_sync "
        "expected True, got False"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_meeting_record_summary_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"]["calculation_meeting_record_complete"] = True
    monitoring["completion_verification"]["calculation_missing_meeting_field_count"] = 0
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion calculation_meeting_record_complete "
        "expected False, got True"
    ) in result["errors"]
    assert (
        "monitoring completion calculation_missing_meeting_field_count "
        "expected 8, got 0"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_local_secret_attestation_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["completion_verification"][
        "local_secret_owner_attestation_ready"
    ] = False
    monitoring["completion_verification"][
        "local_secret_owner_attestation_closure_approved"
    ] = True
    monitoring["completion_verification"][
        "local_secret_owner_attestation_secret_value_fields_present"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring completion local_secret_owner_attestation_ready "
        "expected True, got False"
    ) in result["errors"]
    assert (
        "monitoring completion local_secret_owner_attestation_closure_approved "
        "expected False, got True"
    ) in result["errors"]
    assert (
        "monitoring completion "
        "local_secret_owner_attestation_secret_value_fields_present "
        "expected False, got True"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_calculation_decision_quality_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["calculation_owner_decision"][
        "invalid_selected_decision_count"
    ] = 1
    monitoring["latest_session_recheck"]["calculation_owner_decision"][
        "invalid_status_count"
    ] = 1
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation refresh invalid_selected_decision_count expected 0, got 1"
        in result["errors"]
    )
    assert (
        "latest session calculation invalid_status_count expected 0, got 1"
        in result["errors"]
    )


def test_verify_monitoring_snapshot_fails_when_strict_gate_is_promoted(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["strict_gate_matrix"]["strict_pass_gate_count"] = 1
    monitoring["strict_gate_matrix"]["gates"][0]["strict_pass"] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "strict gate matrix strict_pass_gate_count expected 0, got 1" in result[
        "errors"
    ]
    assert "strict gate system-audit-full-score strict_pass must be false" in result[
        "errors"
    ]


def test_verify_monitoring_snapshot_fails_when_blocker_intake_board_claims_closure(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["blocker_intake_board"]["status"] = "complete"
    monitoring["blocker_intake_board"]["next_blocker_id"] = None
    monitoring["blocker_intake_board"]["evidence_scope"][
        "writes_governance_records"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "blocker intake board status expected 'open_external_input_required', got 'complete'"
        in result["errors"]
    )
    assert (
        "blocker intake board next_blocker_id expected 'calculation-display-p1-decisions', got None"
        in result["errors"]
    )
    assert "blocker intake board writes_governance_records must be false" in result[
        "errors"
    ]


def test_verify_monitoring_snapshot_fails_when_next_blocker_detail_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["pulse"]["next_blocker_id"] = "owner-approval-7-pages"
    monitoring["pulse"]["next_blocker_detail"]["responsible_owner_type"] = (
        "page_business_owner"
    )
    monitoring["blocker_intake_board"]["next_blocker_detail"][
        "strict_gate_command"
    ] = "python scripts\\unexpected.py"
    monitoring["latest_session_recheck"]["next_blocker"]["blocker_id"] = (
        "owner-approval-7-pages"
    )
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring pulse next_blocker_id expected "
        "'calculation-display-p1-decisions', got 'owner-approval-7-pages'"
    ) in result["errors"]
    assert (
        "monitoring pulse next blocker owner type expected "
        "'business_owner_and_metric_governance', got 'page_business_owner'"
    ) in result["errors"]
    assert (
        "blocker intake board next detail strict gate expected "
        "'python scripts\\\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured', got 'python scripts\\\\unexpected.py'"
    ) in result["errors"]
    assert (
        "latest session next blocker id expected 'calculation-display-p1-decisions', "
        "got 'owner-approval-7-pages'"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_post_owner_sync_summary_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["pulse"]["calculation_post_owner_plan_renderer_sync"] = False
    monitoring["latest_session_recheck"][
        "calculation_post_owner_plan_renderer_sync"
    ] = False
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "monitoring pulse calculation_post_owner_plan_renderer_sync "
        "expected True, got False"
    ) in result["errors"]
    assert (
        "latest session calculation_post_owner_plan_renderer_sync "
        "expected True, got False"
    ) in result["errors"]


def test_verify_monitoring_snapshot_fails_when_strict_gate_guard_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["strict_gate_matrix"]["completion_order_guard_status"] = "missing"
    monitoring["strict_gate_matrix"]["completion_order_guard_error_count"] = 1
    monitoring["strict_gate_matrix"]["guard_error_count"] = 1
    monitoring["strict_gate_matrix"]["guard_errors"] = ["forced drift"]
    monitoring["latest_session_recheck"]["strict_gate_matrix"][
        "completion_order_guard_status"
    ] = "missing"
    monitoring["latest_session_recheck"]["strict_gate_matrix"]["guard_error_count"] = 1
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "strict gate matrix completion_order_guard_status expected 'pass', got 'missing'"
        in result["errors"]
    )
    assert (
        "strict gate matrix completion_order_guard_error_count expected 0, got 1"
        in result["errors"]
    )
    assert "strict gate matrix guard_error_count expected 0, got 1" in result["errors"]
    assert "strict gate matrix guard_errors expected [], got ['forced drift']" in result[
        "errors"
    ]
    assert (
        "latest session completion order guard status expected 'pass', got 'missing'"
        in result["errors"]
    )
    assert "latest session guard error count expected 0, got 1" in result["errors"]


def test_verify_monitoring_snapshot_cli_outputs_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(MANIFEST)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["report_kind"] == "system_audit_monitoring_snapshot_verification"
    assert payload["status"] == "pass"
    assert payload["open_blocker_count"] == 5
    assert payload["pulse_completion_state"] == "not_complete"
    assert payload["next_blocker_id"] == "calculation-display-p1-decisions"
    assert payload["completion_order_guard_status"] == "pass"
    assert payload["strict_gate_status"] == "pass"
    assert payload["strict_pass_gate_count"] == 0
    assert payload["strict_completion_order_guard_status"] == "pass"
    assert payload["errors"] == []


def test_verify_monitoring_snapshot_cli_strict_completion_rejects_current_blockers() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(MANIFEST),
            "--require-complete",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["open_blocker_count"] == 5
    assert payload["pulse_completion_state"] == "not_complete"
    assert payload["next_blocker_id"] == "calculation-display-p1-decisions"
    assert payload["errors"] == []
    assert "System audit monitoring is not complete" in completed.stderr
    assert "open_blocker_count=5" in completed.stderr
