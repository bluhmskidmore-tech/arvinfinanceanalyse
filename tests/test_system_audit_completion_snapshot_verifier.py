from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_system_audit_completion_snapshot import verify_completion_snapshot


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_system_audit_completion_snapshot.py"
MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"


def _copy_audit_files(tmp_path: Path) -> Path:
    audit_dir = tmp_path / "docs" / "audits"
    audit_dir.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    snapshot = json.loads(
        (ROOT / manifest["artifacts"]["completion_snapshot"]).read_text(encoding="utf-8")
    )
    follow_up_packet = json.loads(
        (ROOT / manifest["artifacts"]["owner_governance_follow_up_packet"]).read_text(
            encoding="utf-8"
        )
    )
    follow_up_brief = (
        ROOT / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    ).read_text(encoding="utf-8")
    calculation_matrix = (
        ROOT / manifest["artifacts"]["calculation_owner_decision_matrix"]
    ).read_text(encoding="utf-8")
    calculation_snapshot = json.loads(
        (ROOT / manifest["artifacts"]["calculation_owner_decision_snapshot"]).read_text(
            encoding="utf-8"
        )
    )
    calculation_packet = (
        ROOT / manifest["artifacts"]["calculation_owner_decision_packet"]
    ).read_text(encoding="utf-8")
    owner_meeting_checklist = (
        ROOT / manifest["artifacts"]["calculation_owner_meeting_checklist"]
    ).read_text(encoding="utf-8")
    first_priority_packet = (
        ROOT / manifest["artifacts"]["calculation_first_priority_readiness_packet"]
    ).read_text(encoding="utf-8")
    post_owner_plan = (
        ROOT / manifest["artifacts"]["calculation_post_owner_execution_plan"]
    ).read_text(encoding="utf-8")
    local_secret_attestation = (
        ROOT / manifest["artifacts"]["local_secret_hygiene_owner_attestation_packet"]
    ).read_text(encoding="utf-8")
    monitoring_snapshot = json.loads(
        (ROOT / manifest["artifacts"]["system_audit_monitoring_snapshot"]).read_text(
            encoding="utf-8"
        )
    )
    manifest_path = audit_dir / "manifest.json"
    snapshot_path = audit_dir / "completion-snapshot.json"
    follow_up_packet_path = audit_dir / "owner-governance-follow-up-packet.json"
    follow_up_brief_path = audit_dir / "owner-governance-follow-up-brief.zh.md"
    calculation_matrix_path = audit_dir / "calculation-p1-owner-decision-matrix.md"
    calculation_snapshot_path = audit_dir / "calculation-p1-owner-decision-snapshot.json"
    calculation_packet_path = audit_dir / "calculation-p1-owner-decision-packet.md"
    owner_meeting_checklist_path = (
        audit_dir / "calculation-p1-owner-meeting-checklist.md"
    )
    first_priority_packet_path = (
        audit_dir / "calculation-p1-first-priority-readiness-packet.md"
    )
    post_owner_plan_path = (
        audit_dir / "calculation-p1-post-owner-execution-plan.md"
    )
    local_secret_attestation_path = (
        audit_dir / "local-secret-hygiene-owner-attestation-packet.md"
    )
    monitoring_snapshot_path = audit_dir / "system-audit-monitoring-snapshot.json"
    original_follow_up_packet_path = manifest["artifacts"][
        "owner_governance_follow_up_packet"
    ]
    for blocker in follow_up_packet["blocker_packets"]:
        for artifact in blocker.get("required_input_artifacts", []):
            if not isinstance(artifact, str) or artifact.startswith("<"):
                continue
            source = ROOT / artifact
            if not source.exists():
                continue
            target = tmp_path / artifact
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    manifest["artifacts"]["completion_snapshot"] = "docs/audits/completion-snapshot.json"
    manifest["artifacts"][
        "owner_governance_follow_up_packet"
    ] = "docs/audits/owner-governance-follow-up-packet.json"
    manifest["artifacts"][
        "owner_governance_follow_up_brief_zh"
    ] = "docs/audits/owner-governance-follow-up-brief.zh.md"
    manifest["artifacts"][
        "calculation_owner_decision_matrix"
    ] = "docs/audits/calculation-p1-owner-decision-matrix.md"
    manifest["artifacts"][
        "calculation_owner_decision_snapshot"
    ] = "docs/audits/calculation-p1-owner-decision-snapshot.json"
    manifest["artifacts"][
        "calculation_owner_decision_packet"
    ] = "docs/audits/calculation-p1-owner-decision-packet.md"
    manifest["artifacts"][
        "calculation_owner_meeting_checklist"
    ] = "docs/audits/calculation-p1-owner-meeting-checklist.md"
    manifest["artifacts"][
        "calculation_first_priority_readiness_packet"
    ] = "docs/audits/calculation-p1-first-priority-readiness-packet.md"
    manifest["artifacts"][
        "calculation_post_owner_execution_plan"
    ] = "docs/audits/calculation-p1-post-owner-execution-plan.md"
    manifest["artifacts"][
        "local_secret_hygiene_owner_attestation_packet"
    ] = "docs/audits/local-secret-hygiene-owner-attestation-packet.md"
    manifest["artifacts"][
        "system_audit_monitoring_snapshot"
    ] = "docs/audits/system-audit-monitoring-snapshot.json"
    follow_up_brief = follow_up_brief.replace(
        original_follow_up_packet_path,
        manifest["artifacts"]["owner_governance_follow_up_packet"],
    )
    follow_up_brief = follow_up_brief.replace(
        "`2026-06-10-owner-governance-follow-up-packet.json`",
        f"`{manifest['artifacts']['owner_governance_follow_up_packet']}`",
    )
    snapshot["source_artifacts"][
        "owner_governance_follow_up_packet"
    ] = "docs/audits/owner-governance-follow-up-packet.json"
    snapshot["source_artifacts"][
        "owner_governance_follow_up_brief_zh"
    ] = "docs/audits/owner-governance-follow-up-brief.zh.md"
    snapshot["source_artifacts"][
        "system_audit_monitoring_snapshot"
    ] = "docs/audits/system-audit-monitoring-snapshot.json"
    snapshot["source_artifacts"][
        "calculation_first_priority_readiness_packet"
    ] = "docs/audits/calculation-p1-first-priority-readiness-packet.md"
    snapshot["source_artifacts"][
        "calculation_owner_meeting_checklist"
    ] = "docs/audits/calculation-p1-owner-meeting-checklist.md"
    snapshot["source_artifacts"][
        "calculation_post_owner_execution_plan"
    ] = "docs/audits/calculation-p1-post-owner-execution-plan.md"
    follow_up_packet["source_artifacts"][
        "system_audit_monitoring_snapshot"
    ] = "docs/audits/system-audit-monitoring-snapshot.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    follow_up_packet_path.write_text(
        json.dumps(follow_up_packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    follow_up_brief_path.write_text(follow_up_brief, encoding="utf-8")
    calculation_matrix_path.write_text(calculation_matrix, encoding="utf-8")
    calculation_snapshot_path.write_text(
        json.dumps(calculation_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    calculation_packet_path.write_text(calculation_packet, encoding="utf-8")
    owner_meeting_checklist_path.write_text(owner_meeting_checklist, encoding="utf-8")
    first_priority_packet_path.write_text(first_priority_packet, encoding="utf-8")
    post_owner_plan_path.write_text(post_owner_plan, encoding="utf-8")
    local_secret_attestation_path.write_text(
        local_secret_attestation,
        encoding="utf-8",
    )
    monitoring_snapshot_path.write_text(
        json.dumps(monitoring_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def test_verify_completion_snapshot_passes_for_checked_in_audit_package() -> None:
    result = verify_completion_snapshot(manifest_path=MANIFEST)

    assert result["status"] == "pass"
    assert result["open_blocker_count"] == 5
    assert result["completion_gate_count"] == 5
    assert result["follow_up_packet_count"] == 5
    assert result["follow_up_brief_blocker_count"] == 5
    assert result["calculation_prework_p1_count"] == 10
    assert result["calculation_packet_p1_count"] == 10
    assert result["calculation_packet_execution_anchor_ready"] is True
    assert result["calculation_packet_execution_referenced_path_count"] == 24
    assert result["calculation_packet_missing_execution_referenced_path_count"] == 0
    assert result["calculation_owner_meeting_checklist_count"] == 10
    assert result["calculation_owner_meeting_material_ready"] is True
    assert result["calculation_owner_meeting_implementation_ready"] is False
    assert result["calculation_owner_meeting_missing_capture_field_count"] == 50
    assert result["calculation_owner_meeting_missing_field_count"] == 8
    assert result["calculation_first_priority_count"] == 3
    assert result["calculation_first_priority_owner_intake_ready"] is True
    assert result["calculation_first_priority_implementation_ready"] is False
    assert result["calculation_post_owner_ready_for_implementation_count"] == 0
    assert result["calculation_post_owner_owner_decision_capture_complete"] is False
    assert result["calculation_post_owner_non_implementation_decision_count"] == 0
    assert result["calculation_post_owner_blocking_reasons"] == [
        "owner_decision_capture_incomplete"
    ]
    assert result["calculation_post_owner_incomplete_count"] == 10
    assert result["calculation_post_owner_invalid_selected_decision_count"] == 0
    assert result["calculation_post_owner_no_invalid_selected_decisions"] is True
    assert result["calculation_post_owner_global_gate_ready"] is False
    assert result["calculation_post_owner_implementation_ready"] is False
    assert result["calculation_post_owner_plan_renderer_sync"] is True
    assert result["calculation_snapshot_status"] == "owner_decision_required"
    assert result["calculation_incomplete_decision_count"] == 10
    assert result["calculation_meeting_record_complete"] is False
    assert result["calculation_missing_meeting_field_count"] == 8
    assert result["follow_up_completion_order_status"] == "pass"
    assert result["follow_up_completion_order_error_count"] == 0
    assert result["errors"] == []


def test_verify_completion_snapshot_fails_when_gate_timestamp_drifts(tmp_path: Path) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["completion_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["completion_gates"][0]["last_checked_at"] = "2099-01-01T00:00:00+00:00"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert any("last_checked_at does not match manifest" in item for item in result["errors"])


def test_verify_completion_snapshot_fails_when_monitoring_timestamp_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monitoring_path = tmp_path / manifest["artifacts"]["system_audit_monitoring_snapshot"]
    monitoring = json.loads(monitoring_path.read_text(encoding="utf-8"))
    monitoring["generated_at"] = "2099-01-01T00:00:00+00:00"
    monitoring_path.write_text(
        json.dumps(monitoring, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "manifest generated_at does not match system audit monitoring snapshot" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_monitoring_writes_governance(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monitoring_path = tmp_path / manifest["artifacts"]["system_audit_monitoring_snapshot"]
    monitoring = json.loads(monitoring_path.read_text(encoding="utf-8"))
    monitoring["evidence_scope"]["writes_governance_records"] = True
    monitoring["refresh_results"]["ledger_pnl_direct_governance_record"][
        "record_write_status"
    ] = "written"
    monitoring_path.write_text(
        json.dumps(monitoring, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "system audit monitoring snapshot evidence_scope is not fail-closed" in result[
        "errors"
    ]
    assert "system audit monitoring must not write Ledger PnL governance records" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_follow_up_packet_approves_metrics(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["status"]["approves_metrics"] = True
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert any(
        "owner/governance follow-up packet status approves_metrics must be False" in item
        for item in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_follow_up_completion_order_breaks_dependencies(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["completion_order"] = [
        "owner-approval-7-pages",
        "calculation-display-p1-decisions",
        "ledger-pnl-direct-governance-record",
        "direct-app-mcp-gitnexus-evidence",
        "local-secret-hygiene",
    ]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert result["follow_up_completion_order_status"] == "fail"
    assert result["follow_up_completion_order_error_count"] == 2
    assert (
        "owner/governance follow-up packet completion_order invalid: "
        "calculation-display P1 decisions must precede owner approval closure"
    ) in result["errors"]
    assert (
        "owner/governance follow-up packet completion_order invalid: "
        "Ledger PnL direct governance record must precede owner approval closure"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_follow_up_completion_order_has_duplicates(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["completion_order"].append("local-secret-hygiene")
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert result["follow_up_completion_order_status"] == "fail"
    assert result["follow_up_completion_order_error_count"] == 1
    assert (
        "owner/governance follow-up packet completion_order length does not match open blockers"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_follow_up_input_artifact_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    direct_packet = next(
        item
        for item in packet["blocker_packets"]
        if item["blocker_id"] == "direct-app-mcp-gitnexus-evidence"
    )
    direct_packet["required_input_artifacts"].append(".missing-tool-config.toml")
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "direct-app-mcp-gitnexus-evidence required input artifact is missing: .missing-tool-config.toml"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_snapshot_approves_convention(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["status"]["chooses_or_approves_conventions"] = True
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert any(
        "calculation owner decision snapshot status chooses_or_approves_conventions must be False"
        in item
        for item in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_snapshot_drift_is_present(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["drift_errors"] = ["P1-08 appears in open owner-decision rows"]
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "calculation owner decision snapshot has drift_errors" in result["errors"]


def test_verify_completion_snapshot_fails_when_calculation_incomplete_count_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["capture_template"]["incomplete_decision_count"] = 0
    snapshot["capture_template"]["incomplete_decision_ids"] = []
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision snapshot incomplete decision count does not match manifest"
        in result["errors"]
    )
    assert (
        "calculation owner decision snapshot incomplete decision IDs do not match expected"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_owner_status_is_invalid(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["capture_template"]["invalid_status_by_id"] = {"P1-01": "maybe"}
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision snapshot has invalid owner-decision statuses"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_selected_decision_is_invalid(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["capture_template"]["invalid_selected_decision_by_id"] = {"P1-01": "Z"}
    snapshot["capture_template"]["invalid_selected_decision_count"] = 1
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision snapshot has invalid selected decisions"
        in result["errors"]
    )
    assert (
        "calculation owner decision snapshot invalid selected decision count must be zero"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_meeting_record_claims_complete(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["meeting_record"]["is_complete"] = True
    snapshot["meeting_record"]["missing_required_fields"] = []
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision snapshot must not mark meeting record complete"
        in result["errors"]
    )
    assert (
        "calculation owner decision snapshot must report missing meeting fields"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_packet_claims_approval(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_packet"]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "`captures_owner_decisions=false`",
        "`captures_owner_decisions=true`",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision packet missing required phrase: `captures_owner_decisions=false`"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_packet_drops_execution_anchor(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_packet"]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "Execution anchor ready: `true`",
        "Execution anchor ready: `false`",
    )
    packet = packet.replace(
        "`all_execution_slice_paths_exist=true`",
        "`all_execution_slice_paths_exist=false`",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision packet missing required phrase: "
        "Execution anchor ready: `true`"
    ) in result["errors"]
    assert (
        "calculation owner decision packet missing required phrase: "
        "`all_execution_slice_paths_exist=true`"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_calculation_packet_drops_owner_gate(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_packet"]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "Owner decision gate",
        "Owner gate removed",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner decision packet missing required phrase: "
        "Owner decision gate"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_owner_meeting_checklist_claims_implementation(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["calculation_owner_meeting_checklist"]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "Implementation ready: `false`",
        "Implementation ready: `true`",
    )
    packet = packet.replace(
        "`captures_owner_decisions=false`",
        "`captures_owner_decisions=true`",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner meeting checklist missing required phrase: "
        "Implementation ready: `false`"
    ) in result["errors"]
    assert (
        "calculation owner meeting checklist missing required phrase: "
        "`captures_owner_decisions=false`"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_owner_meeting_checklist_drops_owner_gate(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["calculation_owner_meeting_checklist"]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "Owner decision gate",
        "Owner gate removed",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation owner meeting checklist missing required phrase: "
        "Owner decision gate"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_first_priority_packet_claims_implementation(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"][
        "calculation_first_priority_readiness_packet"
    ]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "`implementation_ready=false`",
        "`implementation_ready=true`",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation first priority readiness packet missing required phrase: "
        "`implementation_ready=false`"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_first_priority_packet_drops_anchor(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"][
        "calculation_first_priority_readiness_packet"
    ]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "CreditSpreadView.tsx",
        "CreditSpreadView-removed.tsx",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation first priority readiness packet missing required phrase: "
        "CreditSpreadView.tsx"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_first_priority_packet_drops_owner_gate(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"][
        "calculation_first_priority_readiness_packet"
    ]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "Owner Decision Gate",
        "Owner Gate Removed",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation first priority readiness packet missing required phrase: "
        "Owner Decision Gate"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_post_owner_plan_claims_ready(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"][
        "calculation_post_owner_execution_plan"
    ]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "`ready_for_implementation_count=0`",
        "`ready_for_implementation_count=1`",
    )
    packet = packet.replace(
        "`global_owner_decision_gate_ready=false`",
        "`global_owner_decision_gate_ready=true`",
    )
    packet = packet.replace(
        "Global owner gate ready: `false`",
        "Global owner gate ready: `true`",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert (
        "calculation post-owner execution plan missing required phrase: "
        "`ready_for_implementation_count=0`"
    ) in result["errors"]
    assert (
        "calculation post-owner execution plan missing required phrase: "
        "`global_owner_decision_gate_ready=false`"
    ) in result["errors"]
    assert (
        "calculation post-owner execution plan missing required phrase: "
        "Global owner gate ready: `false`"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_post_owner_plan_is_stale(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"][
        "calculation_post_owner_execution_plan"
    ]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "| `incomplete` | 10 |",
        "| `incomplete` | 10 | `P1-01`, `P1-02`, `P1-03`, `P1-04`, `P1-05`, `P1-06`, `P1-07`, `P1-09`, `P1-10`, `P1-11`, `P1-99` |",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert result["calculation_post_owner_plan_renderer_sync"] is False
    assert (
        "calculation post-owner execution plan does not match current "
        "matrix/snapshot/capture-template renderer output"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_post_owner_plan_sources_drift(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_matrix"]
    matrix = matrix_path.read_text(encoding="utf-8").replace(
        "Component/model tests prove backend value wins and missing share remains missing.",
        "Component/model tests prove backend value wins after source drift.",
    )
    matrix_path.write_text(matrix, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert result["calculation_post_owner_plan_renderer_sync"] is False
    assert (
        "calculation post-owner execution plan does not match current "
        "matrix/snapshot/capture-template renderer output"
    ) in result["errors"]


def test_verify_completion_snapshot_fails_when_ledger_write_guard_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    ledger_packet = next(
        item
        for item in packet["blocker_packets"]
        if item["blocker_id"] == "ledger-pnl-direct-governance-record"
    )
    ledger_packet["authorization_required_commands_not_preapproved"] = []
    ledger_packet["prohibited_actions"] = []
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "Ledger PnL --write command must remain authorization-required" in result["errors"]
    assert "Ledger PnL follow-up must prohibit unauthorized --write execution" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_secret_boundary_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    secret_packet = next(
        item
        for item in packet["blocker_packets"]
        if item["blocker_id"] == "local-secret-hygiene"
    )
    secret_packet["prohibited_actions"] = []
    secret_packet["explicit_non_approval_boundary"] = "Secret values may be handled later."
    secret_packet["engineering_prework_available_now"] = []
    secret_packet["closure_evidence_after_external_input"] = []
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "local secret follow-up must prohibit reading or pasting values" in result["errors"]
    assert "local secret follow-up must prohibit committing credential values" in result[
        "errors"
    ]
    assert "local secret follow-up must preserve explicit no-secret-values boundary" in result[
        "errors"
    ]
    assert "local-secret-hygiene missing engineering_prework_available_now" in result[
        "errors"
    ]
    assert "local-secret-hygiene missing closure_evidence_after_external_input" in result[
        "errors"
    ]
    assert "local secret follow-up must keep engineering prework value-free" in result[
        "errors"
    ]
    assert "local secret follow-up must require no-value closure evidence" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_local_secret_attestation_claims_approval(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"][
        "local_secret_hygiene_owner_attestation_packet"
    ]
    packet = packet_path.read_text(encoding="utf-8").replace(
        "Closure approved: `false`",
        "Closure approved: `true`",
    )
    packet = packet.replace(
        "`captures_secret_values=false`",
        "`captures_secret_values=true`",
    )
    packet_path.write_text(packet, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "local secret owner attestation packet must deny closure approval"
        in result["errors"]
    )
    assert (
        "local secret owner attestation packet must deny captured secret values"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_follow_up_brief_drops_blocker(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    brief_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    brief = brief_path.read_text(encoding="utf-8").replace(
        "calculation-display-p1-decisions",
        "calc-display-p1-decisions-removed",
    )
    brief_path.write_text(brief, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "owner/governance follow-up brief missing blocker calculation-display-p1-decisions"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_follow_up_brief_boundary_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    brief_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    brief = brief_path.read_text(encoding="utf-8").replace(
        "不授权 Ledger PnL `--write`",
        "Ledger PnL write may be handled later",
    )
    brief_path.write_text(brief, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "owner/governance follow-up brief missing required phrase: 不授权 Ledger PnL `--write`"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_prework_map_drops_item(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_matrix"]
    matrix = matrix_path.read_text(encoding="utf-8").replace(
        "- **P1-10 Frontend formal aggregation**:",
        "- **P1-10-removed Frontend formal aggregation**:",
    )
    matrix_path.write_text(matrix, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "calculation prework map missing P1-10" in result["errors"]


def test_verify_completion_snapshot_fails_when_calculation_prework_boundary_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_matrix"]
    matrix = matrix_path.read_text(encoding="utf-8").replace(
        "It does not choose or approve any convention; it does not change code; it does not certify routes/pages.",
        "It prepares implementation work.",
    )
    matrix_path.write_text(matrix, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation prework map missing boundary: does not choose or approve any convention"
        in result["errors"]
    )
    assert (
        "calculation prework map missing boundary: does not change code"
        in result["errors"]
    )
    assert (
        "calculation prework map missing boundary: does not certify routes/pages"
        in result["errors"]
    )


def test_verify_completion_snapshot_cli_outputs_json() -> None:
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
    assert payload["report_kind"] == "system_audit_completion_snapshot_verification"
    assert payload["status"] == "pass"
    assert payload["follow_up_packet_count"] == 5
    assert payload["follow_up_brief_blocker_count"] == 5
    assert payload["calculation_prework_p1_count"] == 10
    assert payload["errors"] == []


def test_verify_completion_snapshot_cli_strict_completion_rejects_current_blockers() -> None:
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
    assert payload["errors"] == []
    assert "System audit completion is not complete" in completed.stderr
    assert "open_blocker_count=5" in completed.stderr
