from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.refresh_calculation_p1_owner_decision_snapshot import (  # noqa: E402
    build_snapshot as build_calculation_snapshot,
)
from scripts.refresh_direct_app_mcp_gitnexus_tool_surface_snapshot import (  # noqa: E402
    build_snapshot as build_direct_tool_snapshot,
)
from scripts.refresh_ledger_pnl_direct_governance_record_snapshot import (  # noqa: E402
    build_snapshot as build_ledger_snapshot,
)
from scripts.refresh_local_secret_hygiene_snapshot import (  # noqa: E402
    build_snapshot as build_secret_snapshot,
)
from scripts.system_audit_blocker_intake_board import (  # noqa: E402
    build_board as build_blocker_intake_board,
)
from scripts.system_audit_pulse import (  # noqa: E402
    blocker_intake_summary_from_board,
    build_pulse,
    strict_gate_summary_from_matrix,
)
from scripts.system_audit_strict_gate_matrix import (  # noqa: E402
    build_matrix_from_inputs as build_strict_gate_matrix,
)
from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    verify_completion_snapshot,
)


AUDIT_DATE = "2026-06-10"
DEFAULT_MANIFEST = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-system-audit-manifest.json"
)
DEFAULT_OUTPUT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-system-audit-monitoring-snapshot.json"
)
DEFAULT_DIRECT_TOOL_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-direct-app-mcp-gitnexus-tool-surface-snapshot.json"
)
EVIDENCE_SCOPE = {
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


def _now_shanghai() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def _timestamp(prefix: str, generated_at: str) -> str:
    return f"{generated_at}::{prefix}"


def _repo_relative_identifier(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def _blocker_checked_at(
    blockers_by_id: dict[str, dict[str, Any]],
    blocker_id: str,
    *,
    fallback: str,
) -> str:
    value = (blockers_by_id.get(blocker_id) or {}).get("last_checked_at")
    return str(value) if value else fallback


def _tool_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [row["name"] for row in rows if isinstance(row, dict) and isinstance(row.get("name"), str)]


def _existing_direct_tool_names(path: Path = DEFAULT_DIRECT_TOOL_OUTPUT) -> dict[str, list[str]]:
    if not path.is_file():
        return {
            "primary_tool_names": [],
            "gitnexus_tool_names": [],
            "moss_general_tool_names": [],
            "moss_named_tool_names": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    focused = payload.get("focused_rechecks") or []
    return {
        "primary_tool_names": _tool_names(
            (payload.get("tool_discovery") or {}).get("discovered_tools")
        ),
        "gitnexus_tool_names": _tool_names(
            focused[0].get("returned_tools") if len(focused) > 0 and isinstance(focused[0], dict) else []
        ),
        "moss_general_tool_names": _tool_names(
            focused[1].get("returned_tools") if len(focused) > 1 and isinstance(focused[1], dict) else []
        ),
        "moss_named_tool_names": _tool_names(
            focused[2].get("returned_tools") if len(focused) > 2 and isinstance(focused[2], dict) else []
        ),
    }


def build_monitoring_snapshot(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    generated_at: str | None = None,
    latest_session_recheck_at: str | None = None,
    write_outputs: bool = False,
    primary_tool_names: list[str] | None = None,
    gitnexus_tool_names: list[str] | None = None,
    moss_general_tool_names: list[str] | None = None,
    moss_named_tool_names: list[str] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now_shanghai()
    latest_session_recheck_at = latest_session_recheck_at or generated_at
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    blockers_by_id = {
        str(item.get("id")): item
        for item in manifest.get("open_blockers") or []
        if isinstance(item, dict)
    }
    calculation_checked_at = _blocker_checked_at(
        blockers_by_id,
        "calculation-display-p1-decisions",
        fallback=generated_at,
    )
    direct_tool_checked_at = _blocker_checked_at(
        blockers_by_id,
        "direct-app-mcp-gitnexus-evidence",
        fallback=generated_at,
    )
    secret_checked_at = _blocker_checked_at(
        blockers_by_id,
        "local-secret-hygiene",
        fallback=generated_at,
    )
    ledger_checked_at = _blocker_checked_at(
        blockers_by_id,
        "ledger-pnl-direct-governance-record",
        fallback=generated_at,
    )
    existing_direct_tool_names = _existing_direct_tool_names()
    resolved_primary_tool_names = (
        primary_tool_names
        if primary_tool_names is not None
        else existing_direct_tool_names["primary_tool_names"]
    )
    resolved_gitnexus_tool_names = (
        gitnexus_tool_names
        if gitnexus_tool_names is not None
        else existing_direct_tool_names["gitnexus_tool_names"]
    )
    resolved_moss_general_tool_names = (
        moss_general_tool_names
        if moss_general_tool_names is not None
        else existing_direct_tool_names["moss_general_tool_names"]
    )
    resolved_moss_named_tool_names = (
        moss_named_tool_names
        if moss_named_tool_names is not None
        else existing_direct_tool_names["moss_named_tool_names"]
    )
    calc_snapshot = build_calculation_snapshot(generated_at=calculation_checked_at)
    direct_snapshot = build_direct_tool_snapshot(
        generated_at=direct_tool_checked_at,
        primary_tool_names=resolved_primary_tool_names,
        gitnexus_tool_names=resolved_gitnexus_tool_names,
        moss_general_tool_names=resolved_moss_general_tool_names,
        moss_named_tool_names=resolved_moss_named_tool_names,
    )
    secret_snapshot = build_secret_snapshot(generated_at=secret_checked_at)
    ledger_snapshot = build_ledger_snapshot(
        generated_at=ledger_checked_at,
        record_created_at=ledger_checked_at,
    )
    blocker_intake_board = build_blocker_intake_board(
        generated_at=generated_at,
        manifest_path=manifest_path,
        repo_root=ROOT,
    )
    completion = verify_completion_snapshot(
        manifest_path=manifest_path,
        repo_root=ROOT,
        verify_monitoring=False,
    )
    pulse_for_matrix = {
        "full_score_ready": False,
        "completion_state": (
            "not_complete"
            if completion["open_blocker_count"]
            else "ready_for_completion_audit"
        ),
        "open_blocker_count": completion["open_blocker_count"],
    }
    strict_gate_matrix = build_strict_gate_matrix(
        generated_at=generated_at,
        manifest_path=manifest_path,
        pulse=pulse_for_matrix,
        completion=completion,
        monitoring={
            "status": "pass" if completion["status"] == "pass" else "fail",
            "open_blocker_count": pulse_for_matrix["open_blocker_count"],
            "pulse_completion_state": pulse_for_matrix["completion_state"],
        },
        calculation=calc_snapshot,
        ledger=ledger_snapshot,
        direct=direct_snapshot,
        secret=secret_snapshot,
    )
    pulse_snapshot = build_pulse(
        generated_at=generated_at,
        strict_gate_summary_override=strict_gate_summary_from_matrix(
            strict_gate_matrix,
            source=_repo_relative_identifier(DEFAULT_OUTPUT),
            source_generated_at=generated_at,
        ),
        completion_override=completion,
        manifest_path=manifest_path,
        repo_root=ROOT,
    )

    outputs = {
        key: _resolve_repo_path(str(manifest["artifacts"][key]))
        for key in (
            "calculation_owner_decision_snapshot",
            "direct_app_mcp_gitnexus_tool_surface_snapshot",
            "local_secret_hygiene_snapshot",
            "ledger_pnl_direct_governance_record_snapshot",
            "system_audit_pulse_snapshot",
        )
    }

    if write_outputs:
        _write_json(outputs["calculation_owner_decision_snapshot"], calc_snapshot)
        _write_json(outputs["direct_app_mcp_gitnexus_tool_surface_snapshot"], direct_snapshot)
        _write_json(outputs["local_secret_hygiene_snapshot"], secret_snapshot)
        _write_json(outputs["ledger_pnl_direct_governance_record_snapshot"], ledger_snapshot)
        _write_json(outputs["system_audit_pulse_snapshot"], pulse_snapshot)

    return {
        "report_kind": "system_audit_monitoring_snapshot",
        "generated_at": generated_at,
        "repo_root": ".",
        "audit_date": AUDIT_DATE,
        "write_outputs": write_outputs,
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "refresh_results": {
            "calculation_owner_decision": {
                "status": calc_snapshot["status"]["overall"],
                "open_decision_count": calc_snapshot["matrix"]["open_decision_count"],
                "captured_decision_count": calc_snapshot["capture_template"][
                    "captured_decision_count"
                ],
                "incomplete_decision_count": calc_snapshot["capture_template"][
                    "incomplete_decision_count"
                ],
                "invalid_selected_decision_count": calc_snapshot["capture_template"][
                    "invalid_selected_decision_count"
                ],
                "invalid_status_count": len(
                    calc_snapshot["capture_template"]["invalid_status_by_id"]
                ),
                "drift_error_count": len(calc_snapshot["drift_errors"]),
            },
            "direct_app_mcp_gitnexus_tool_surface": {
                "status": direct_snapshot["status"]["overall"],
                "detected_direct_servers": direct_snapshot["detected_direct_servers"],
                "missing_direct_servers": direct_snapshot["missing_direct_servers"],
                "direct_app_mcp_evidence_captured": direct_snapshot["status"][
                    "direct_app_mcp_evidence_captured"
                ],
                "direct_gitnexus_evidence_captured": direct_snapshot["status"][
                    "direct_gitnexus_evidence_captured"
                ],
            },
            "local_secret_hygiene": {
                "status": secret_snapshot["status"]["overall"],
                "latest_boundary_only_recheck_at": secret_snapshot[
                    "latest_boundary_only_recheck"
                ]["checked_at"],
                "secret_values_captured": secret_snapshot["status"][
                    "secret_values_captured"
                ],
                "clears_secret_scan": secret_snapshot["status"]["clears_secret_scan"],
            },
            "ledger_pnl_direct_governance_record": {
                "status": ledger_snapshot["status"]["overall"],
                "record_write_status": ledger_snapshot["dry_run_result"][
                    "record_write_status"
                ],
                "post_write_ready": ledger_snapshot["post_write_validation"]["ready"],
                "post_write_blocking_reasons": ledger_snapshot[
                    "post_write_validation"
                ]["blocking_reasons"],
                "formal_use_allowed": ledger_snapshot["dry_run_result"][
                    "formal_use_allowed"
                ],
                "closure_approved": ledger_snapshot["page_readiness_result"][
                    "closure_approved"
                ],
            },
        },
        "completion_verification": {
            "status": completion["status"],
            "open_blocker_count": completion["open_blocker_count"],
            "calculation_packet_p1_count": completion[
                "calculation_packet_p1_count"
            ],
            "calculation_packet_execution_anchor_ready": completion[
                "calculation_packet_execution_anchor_ready"
            ],
            "calculation_packet_execution_referenced_path_count": completion[
                "calculation_packet_execution_referenced_path_count"
            ],
            "calculation_packet_missing_execution_referenced_path_count": completion[
                "calculation_packet_missing_execution_referenced_path_count"
            ],
            "calculation_owner_meeting_checklist_count": completion[
                "calculation_owner_meeting_checklist_count"
            ],
            "calculation_owner_meeting_material_ready": completion[
                "calculation_owner_meeting_material_ready"
            ],
            "calculation_owner_meeting_implementation_ready": completion[
                "calculation_owner_meeting_implementation_ready"
            ],
            "calculation_owner_meeting_missing_capture_field_count": completion[
                "calculation_owner_meeting_missing_capture_field_count"
            ],
            "calculation_owner_meeting_missing_field_count": completion[
                "calculation_owner_meeting_missing_field_count"
            ],
            "calculation_first_priority_count": completion[
                "calculation_first_priority_count"
            ],
            "calculation_first_priority_owner_intake_ready": completion[
                "calculation_first_priority_owner_intake_ready"
            ],
            "calculation_first_priority_implementation_ready": completion[
                "calculation_first_priority_implementation_ready"
            ],
            "calculation_post_owner_ready_for_implementation_count": completion[
                "calculation_post_owner_ready_for_implementation_count"
            ],
            "calculation_post_owner_owner_decision_capture_complete": completion[
                "calculation_post_owner_owner_decision_capture_complete"
            ],
            "calculation_post_owner_non_implementation_decision_count": completion[
                "calculation_post_owner_non_implementation_decision_count"
            ],
            "calculation_post_owner_blocking_reasons": completion[
                "calculation_post_owner_blocking_reasons"
            ],
            "calculation_post_owner_incomplete_count": completion[
                "calculation_post_owner_incomplete_count"
            ],
            "calculation_post_owner_invalid_selected_decision_count": completion[
                "calculation_post_owner_invalid_selected_decision_count"
            ],
            "calculation_post_owner_no_invalid_selected_decisions": completion[
                "calculation_post_owner_no_invalid_selected_decisions"
            ],
            "calculation_post_owner_global_gate_ready": completion[
                "calculation_post_owner_global_gate_ready"
            ],
            "calculation_post_owner_implementation_ready": completion[
                "calculation_post_owner_implementation_ready"
            ],
            "calculation_post_owner_plan_renderer_sync": completion[
                "calculation_post_owner_plan_renderer_sync"
            ],
            "local_secret_owner_attestation_ready": completion[
                "local_secret_owner_attestation_ready"
            ],
            "local_secret_owner_attestation_closure_approved": completion[
                "local_secret_owner_attestation_closure_approved"
            ],
            "local_secret_owner_attestation_secret_value_fields_present": completion[
                "local_secret_owner_attestation_secret_value_fields_present"
            ],
            "calculation_meeting_record_complete": completion[
                "calculation_meeting_record_complete"
            ],
            "calculation_missing_meeting_field_count": completion[
                "calculation_missing_meeting_field_count"
            ],
            "follow_up_completion_order_status": completion[
                "follow_up_completion_order_status"
            ],
            "follow_up_completion_order_error_count": completion[
                "follow_up_completion_order_error_count"
            ],
            "error_count": len(completion["errors"]),
            "errors": completion["errors"],
        },
        "pulse": {
            "status": pulse_snapshot["status"],
            "completion_state": pulse_snapshot["completion_state"],
            "open_blocker_count": pulse_snapshot["open_blocker_count"],
            "next_blocker_id": pulse_snapshot["blocker_intake_board"][
                "next_blocker_id"
            ],
            "next_blocker_detail": pulse_snapshot["blocker_intake_board"][
                "next_blocker_detail"
            ],
            "calculation_post_owner_plan_renderer_sync": pulse_snapshot[
                "calculation_post_owner_plan_renderer_sync"
            ],
            "drift_error_count": len(pulse_snapshot["drift_errors"]),
            "drift_errors": pulse_snapshot["drift_errors"],
        },
        "blocker_intake_board": blocker_intake_summary_from_board(
            blocker_intake_board
        ),
        "strict_gate_matrix": {
            "status": strict_gate_matrix["status"],
            "completion_state": strict_gate_matrix["completion_state"],
            "full_score_ready": strict_gate_matrix["full_score_ready"],
            "open_blocker_count": strict_gate_matrix["open_blocker_count"],
            "completion_order_guard_status": strict_gate_matrix[
                "completion_order_guard_status"
            ],
            "completion_order_guard_error_count": strict_gate_matrix[
                "completion_order_guard_error_count"
            ],
            "gate_count": strict_gate_matrix["gate_count"],
            "expected_blocked_gate_count": strict_gate_matrix[
                "expected_blocked_gate_count"
            ],
            "strict_pass_gate_count": strict_gate_matrix["strict_pass_gate_count"],
            "unexpected_gate_count": strict_gate_matrix["unexpected_gate_count"],
            "guard_error_count": strict_gate_matrix["guard_error_count"],
            "guard_errors": strict_gate_matrix["guard_errors"],
            "gates": strict_gate_matrix["gates"],
            "boundary": strict_gate_matrix["boundary"],
        },
        "latest_session_recheck": {
            "checked_at": latest_session_recheck_at,
            "closure_effect": "none",
            "open_blocker_count": len(pulse_snapshot["open_blockers"]),
            "next_blocker": pulse_snapshot["blocker_intake_board"][
                "next_blocker_detail"
            ],
            "strict_gate_matrix": {
                "status": strict_gate_matrix["status"],
                "gate_count": strict_gate_matrix["gate_count"],
                "strict_pass_gate_count": strict_gate_matrix["strict_pass_gate_count"],
                "unexpected_gate_count": strict_gate_matrix["unexpected_gate_count"],
                "completion_order_guard_status": strict_gate_matrix[
                    "completion_order_guard_status"
                ],
                "guard_error_count": strict_gate_matrix["guard_error_count"],
            },
            "calculation_post_owner_plan_renderer_sync": pulse_snapshot[
                "calculation_post_owner_plan_renderer_sync"
            ],
            "direct_app_mcp_gitnexus_tool_surface": {
                "checked_at": direct_tool_checked_at,
                "status": direct_snapshot["status"]["overall"],
                "returned_primary_tool_count": direct_snapshot["tool_discovery"][
                    "discovered_tool_count"
                ],
                "returned_gitnexus_tool_count": direct_snapshot["focused_rechecks"][0][
                    "returned_tool_count"
                ],
                "returned_moss_general_tool_count": direct_snapshot["focused_rechecks"][
                    1
                ]["returned_tool_count"],
                "returned_moss_named_tool_count": direct_snapshot["focused_rechecks"][
                    2
                ]["returned_tool_count"],
                "relevant_direct_tool_count": sum(
                    item["relevant_direct_tool_count"]
                    for item in direct_snapshot["focused_rechecks"]
                )
                + direct_snapshot["tool_discovery"]["relevant_direct_tool_count"],
                "direct_app_mcp_evidence_captured": direct_snapshot["status"][
                    "direct_app_mcp_evidence_captured"
                ],
                "direct_gitnexus_evidence_captured": direct_snapshot["status"][
                    "direct_gitnexus_evidence_captured"
                ],
            },
            "local_secret_hygiene": {
                "checked_at": secret_checked_at,
                "status": secret_snapshot["status"]["overall"],
                "values_read": secret_snapshot["value_handling"]["values_read"],
                "secret_values_captured": secret_snapshot["status"][
                    "secret_values_captured"
                ],
                "clears_secret_scan": secret_snapshot["status"]["clears_secret_scan"],
            },
            "ledger_pnl_direct_governance_record": {
                "checked_at": ledger_checked_at,
                "status": ledger_snapshot["status"]["overall"],
                "record_write_status": ledger_snapshot["dry_run_result"][
                    "record_write_status"
                ],
                "post_write_ready": ledger_snapshot["post_write_validation"]["ready"],
                "post_write_blocking_reasons": ledger_snapshot[
                    "post_write_validation"
                ]["blocking_reasons"],
                "writes_governance_records": ledger_snapshot["status"][
                    "writes_governance_records"
                ],
                "formal_use_allowed": ledger_snapshot["dry_run_result"][
                    "formal_use_allowed"
                ],
            },
            "calculation_owner_decision": {
                "checked_at": calculation_checked_at,
                "status": calc_snapshot["status"]["overall"],
                "captured_decision_count": calc_snapshot["capture_template"][
                    "captured_decision_count"
                ],
                "incomplete_decision_count": calc_snapshot["capture_template"][
                    "incomplete_decision_count"
                ],
                "invalid_selected_decision_count": calc_snapshot["capture_template"][
                    "invalid_selected_decision_count"
                ],
                "invalid_status_count": len(
                    calc_snapshot["capture_template"]["invalid_status_by_id"]
                ),
                "chooses_or_approves_conventions": calc_snapshot["status"][
                    "chooses_or_approves_conventions"
                ],
            },
        },
        "output_paths": {
            key: _repo_relative_identifier(path) for key, path in outputs.items()
        },
        "boundary": (
            "This monitoring snapshot refreshes read-only audit artifacts and runs the "
            "read-only pulse/completion verifier. It does not write DuckDB or governance "
            "records, read or rotate secret values, capture owner approval, approve metrics "
            "or pages, certify routes, clear secret scans, or promote candidate data."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the read-only system audit monitoring refresh bundle.",
    )
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--latest-session-recheck-at", default=None)
    parser.add_argument("--write-outputs", action="store_true")
    parser.add_argument("--primary-tool-names", nargs="*", default=None)
    parser.add_argument("--gitnexus-tool-names", nargs="*", default=None)
    parser.add_argument("--moss-general-tool-names", nargs="*", default=None)
    parser.add_argument("--moss-named-tool-names", nargs="*", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = build_monitoring_snapshot(
        manifest_path=args.manifest,
        generated_at=args.generated_at,
        latest_session_recheck_at=args.latest_session_recheck_at,
        write_outputs=args.write_outputs,
        primary_tool_names=args.primary_tool_names,
        gitnexus_tool_names=args.gitnexus_tool_names,
        moss_general_tool_names=args.moss_general_tool_names,
        moss_named_tool_names=args.moss_named_tool_names,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["pulse"]["status"] == "pass" and report["completion_verification"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
