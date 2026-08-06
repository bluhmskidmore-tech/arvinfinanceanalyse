from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_system_audit_completion_snapshot import verify_completion_snapshot  # noqa: E402


DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"
EXPECTED_NEXT_BLOCKER_ID = "calculation-display-p1-decisions"
EXPECTED_CALCULATION_STRICT_GATE_COMMAND = (
    "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
    "--require-owner-decisions-captured"
)
EXPECTED_EVIDENCE_SCOPE = {
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
EXPECTED_STRICT_GATE_IDS = {
    "system-audit-full-score",
    "completion-zero-open-blockers",
    "monitoring-zero-open-blockers",
    "calculation-p1-owner-decisions-captured",
    "calculation-p1-post-owner-implementation-ready",
    "ledger-pnl-written-record-located",
    "direct-app-mcp-gitnexus-evidence-captured",
    "local-secret-hygiene-clean-boundary",
}
COMPLETION_VERIFICATION_MIRROR_KEYS = [
    "status",
    "open_blocker_count",
    "calculation_packet_p1_count",
    "calculation_packet_execution_anchor_ready",
    "calculation_packet_execution_referenced_path_count",
    "calculation_packet_missing_execution_referenced_path_count",
    "calculation_owner_meeting_checklist_count",
    "calculation_owner_meeting_material_ready",
    "calculation_owner_meeting_implementation_ready",
    "calculation_owner_meeting_missing_capture_field_count",
    "calculation_owner_meeting_missing_field_count",
    "calculation_first_priority_count",
    "calculation_first_priority_owner_intake_ready",
    "calculation_first_priority_implementation_ready",
    "calculation_post_owner_ready_for_implementation_count",
    "calculation_post_owner_owner_decision_capture_complete",
    "calculation_post_owner_non_implementation_decision_count",
    "calculation_post_owner_blocking_reasons",
    "calculation_post_owner_incomplete_count",
    "calculation_post_owner_invalid_selected_decision_count",
    "calculation_post_owner_no_invalid_selected_decisions",
    "calculation_post_owner_global_gate_ready",
    "calculation_post_owner_implementation_ready",
    "calculation_post_owner_plan_renderer_sync",
    "local_secret_owner_attestation_ready",
    "local_secret_owner_attestation_closure_approved",
    "local_secret_owner_attestation_secret_value_fields_present",
    "calculation_meeting_record_complete",
    "calculation_missing_meeting_field_count",
    "follow_up_completion_order_status",
    "follow_up_completion_order_error_count",
    "errors",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(repo_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def _artifact_path(
    manifest: dict[str, Any],
    key: str,
    *,
    repo_root: Path,
    errors: list[str],
) -> Path | None:
    path_value = (manifest.get("artifacts") or {}).get(key)
    if not path_value:
        errors.append(f"manifest missing {key} artifact")
        return None

    path = _resolve(repo_root, str(path_value))
    if not path.exists():
        errors.append(f"{key} artifact is missing: {path}")
        return None
    return path


def _expect_equal(
    errors: list[str],
    *,
    label: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        errors.append(f"{label} expected {expected!r}, got {actual!r}")


def _expect_false(
    errors: list[str],
    *,
    label: str,
    actual: Any,
) -> None:
    if actual is not False:
        errors.append(f"{label} must be false")


def _expect_repo_relative_identifier(
    errors: list[str],
    *,
    label: str,
    actual: Any,
) -> None:
    if not isinstance(actual, str) or not actual:
        errors.append(f"{label} must be a non-empty repo-relative identifier")
        return
    path = Path(actual)
    if path.is_absolute() or path.drive:
        errors.append(f"{label} must be repo-relative, got {actual!r}")


def _blockers_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get("id"): item
        for item in manifest.get("open_blockers", [])
        if isinstance(item, dict)
    }


def _expected_next_blocker_detail(
    follow_up_packet: dict[str, Any],
) -> dict[str, Any]:
    packet = next(
        (
            item
            for item in follow_up_packet.get("blocker_packets") or []
            if isinstance(item, dict)
            and item.get("blocker_id") == EXPECTED_NEXT_BLOCKER_ID
        ),
        {},
    )
    external_inputs = list(packet.get("external_input_required_for_closure") or [])
    required_outputs = list(packet.get("required_meeting_or_governance_output") or [])
    return {
        "responsible_owner_type": packet.get("responsible_owner_type"),
        "required_external_input_count": len(external_inputs),
        "first_required_external_input": external_inputs[0] if external_inputs else None,
        "required_output_count": len(required_outputs),
        "first_required_output": required_outputs[0] if required_outputs else None,
        "fail_closed_until": packet.get("fail_closed_until"),
        "explicit_non_approval_boundary": packet.get(
            "explicit_non_approval_boundary"
        ),
    }


def _calculation_invalid_status_count(calculation: dict[str, Any]) -> int:
    return len(
        calculation.get("capture_template", {}).get("invalid_status_by_id") or {}
    )


def _calculation_invalid_selected_decision_count(calculation: dict[str, Any]) -> int:
    capture = calculation.get("capture_template", {})
    return int(
        capture.get(
            "invalid_selected_decision_count",
            len(capture.get("invalid_selected_decision_by_id") or {}),
        )
        or 0
    )


def _verify_refresh_results(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
    calculation: dict[str, Any],
    direct_tool: dict[str, Any],
    secret: dict[str, Any],
    ledger: dict[str, Any],
    errors: list[str],
) -> None:
    blockers = _blockers_by_id(manifest)
    refresh = monitoring.get("refresh_results") or {}

    calculation_result = refresh.get("calculation_owner_decision") or {}
    calculation_capture = calculation.get("capture_template", {})
    _expect_equal(
        errors,
        label="calculation refresh status",
        actual=calculation_result.get("status"),
        expected=calculation.get("status", {}).get("overall"),
    )
    _expect_equal(
        errors,
        label="calculation refresh open_decision_count",
        actual=calculation_result.get("open_decision_count"),
        expected=calculation.get("matrix", {}).get("open_decision_count"),
    )
    _expect_equal(
        errors,
        label="calculation refresh captured_decision_count",
        actual=calculation_result.get("captured_decision_count"),
        expected=calculation_capture.get("captured_decision_count"),
    )
    _expect_equal(
        errors,
        label="calculation refresh incomplete_decision_count",
        actual=calculation_result.get("incomplete_decision_count"),
        expected=calculation_capture.get("incomplete_decision_count"),
    )
    _expect_equal(
        errors,
        label="calculation refresh invalid_selected_decision_count",
        actual=calculation_result.get("invalid_selected_decision_count"),
        expected=_calculation_invalid_selected_decision_count(calculation),
    )
    _expect_equal(
        errors,
        label="calculation refresh invalid_status_count",
        actual=calculation_result.get("invalid_status_count"),
        expected=_calculation_invalid_status_count(calculation),
    )
    _expect_equal(
        errors,
        label="calculation refresh drift_error_count",
        actual=calculation_result.get("drift_error_count"),
        expected=len(calculation.get("drift_errors") or []),
    )
    _expect_equal(
        errors,
        label="calculation blocker last_checked_at",
        actual=(blockers.get(EXPECTED_NEXT_BLOCKER_ID) or {}).get("last_checked_at"),
        expected=calculation.get("generated_at"),
    )
    _expect_equal(
        errors,
        label="calculation snapshot generated_at",
        actual=calculation.get("generated_at"),
        expected=(blockers.get(EXPECTED_NEXT_BLOCKER_ID) or {}).get(
            "last_checked_at"
        ),
    )

    direct_result = refresh.get("direct_app_mcp_gitnexus_tool_surface") or {}
    _expect_equal(
        errors,
        label="direct App tool refresh status",
        actual=direct_result.get("status"),
        expected=direct_tool.get("status", {}).get("overall"),
    )
    _expect_equal(
        errors,
        label="direct App tool detected_direct_servers",
        actual=direct_result.get("detected_direct_servers"),
        expected=direct_tool.get("detected_direct_servers"),
    )
    _expect_equal(
        errors,
        label="direct App tool missing_direct_servers",
        actual=direct_result.get("missing_direct_servers"),
        expected=direct_tool.get("missing_direct_servers"),
    )
    _expect_false(
        errors,
        label="direct App MCP evidence captured",
        actual=direct_result.get("direct_app_mcp_evidence_captured"),
    )
    _expect_false(
        errors,
        label="direct GitNexus evidence captured",
        actual=direct_result.get("direct_gitnexus_evidence_captured"),
    )
    _expect_equal(
        errors,
        label="direct App blocker last_checked_at",
        actual=(blockers.get("direct-app-mcp-gitnexus-evidence") or {}).get(
            "last_checked_at"
        ),
        expected=direct_tool.get("generated_at"),
    )
    _expect_equal(
        errors,
        label="direct App snapshot generated_at",
        actual=direct_tool.get("generated_at"),
        expected=(blockers.get("direct-app-mcp-gitnexus-evidence") or {}).get(
            "last_checked_at"
        ),
    )

    secret_result = refresh.get("local_secret_hygiene") or {}
    secret_boundary = secret.get("latest_boundary_only_recheck") or {}
    _expect_equal(
        errors,
        label="local secret refresh status",
        actual=secret_result.get("status"),
        expected=secret.get("status", {}).get("overall"),
    )
    _expect_equal(
        errors,
        label="local secret latest_boundary_only_recheck_at",
        actual=secret_result.get("latest_boundary_only_recheck_at"),
        expected=secret_boundary.get("checked_at"),
    )
    _expect_false(
        errors,
        label="local secret refresh secret_values_captured",
        actual=secret_result.get("secret_values_captured"),
    )
    _expect_false(
        errors,
        label="local secret refresh clears_secret_scan",
        actual=secret_result.get("clears_secret_scan"),
    )
    _expect_false(
        errors,
        label="local secret snapshot secret_values_captured",
        actual=secret.get("status", {}).get("secret_values_captured"),
    )
    _expect_equal(
        errors,
        label="local secret blocker last_checked_at",
        actual=(blockers.get("local-secret-hygiene") or {}).get("last_checked_at"),
        expected=secret_boundary.get("checked_at"),
    )
    _expect_equal(
        errors,
        label="local secret boundary checked_at",
        actual=secret_boundary.get("checked_at"),
        expected=(blockers.get("local-secret-hygiene") or {}).get(
            "last_checked_at"
        ),
    )

    ledger_result = refresh.get("ledger_pnl_direct_governance_record") or {}
    _expect_equal(
        errors,
        label="Ledger PnL refresh status",
        actual=ledger_result.get("status"),
        expected=ledger.get("status", {}).get("overall"),
    )
    _expect_equal(
        errors,
        label="Ledger PnL record_write_status",
        actual=ledger_result.get("record_write_status"),
        expected=ledger.get("dry_run_result", {}).get("record_write_status"),
    )
    _expect_equal(
        errors,
        label="Ledger PnL post_write_ready",
        actual=ledger_result.get("post_write_ready"),
        expected=ledger.get("post_write_validation", {}).get("ready"),
    )
    _expect_equal(
        errors,
        label="Ledger PnL post_write_blocking_reasons",
        actual=ledger_result.get("post_write_blocking_reasons"),
        expected=ledger.get("post_write_validation", {}).get("blocking_reasons"),
    )
    _expect_false(
        errors,
        label="Ledger PnL formal_use_allowed",
        actual=ledger_result.get("formal_use_allowed"),
    )
    _expect_false(
        errors,
        label="Ledger PnL closure_approved",
        actual=ledger_result.get("closure_approved"),
    )
    _expect_equal(
        errors,
        label="Ledger PnL blocker last_checked_at",
        actual=(blockers.get("ledger-pnl-direct-governance-record") or {}).get(
            "last_checked_at"
        ),
        expected=ledger.get("generated_at"),
    )
    _expect_equal(
        errors,
        label="Ledger PnL snapshot generated_at",
        actual=ledger.get("generated_at"),
        expected=(blockers.get("ledger-pnl-direct-governance-record") or {}).get(
            "last_checked_at"
        ),
    )


def _verify_next_blocker_detail(
    *,
    detail: dict[str, Any],
    expected_detail: dict[str, Any],
    owner_label: str,
    errors: list[str],
) -> None:
    _expect_equal(
        errors,
        label=f"{owner_label} next blocker owner type",
        actual=detail.get("responsible_owner_type"),
        expected=expected_detail.get("responsible_owner_type"),
    )
    _expect_equal(
        errors,
        label=f"{owner_label} next detail strict gate",
        actual=detail.get("strict_gate_command"),
        expected=EXPECTED_CALCULATION_STRICT_GATE_COMMAND,
    )
    _expect_equal(
        errors,
        label=f"{owner_label} next detail required_external_input_count",
        actual=detail.get("required_external_input_count"),
        expected=expected_detail.get("required_external_input_count"),
    )
    _expect_equal(
        errors,
        label=f"{owner_label} next detail required_output_count",
        actual=detail.get("required_output_count"),
        expected=expected_detail.get("required_output_count"),
    )
    for field in (
        "first_required_external_input",
        "first_required_output",
        "fail_closed_until",
        "explicit_non_approval_boundary",
    ):
        _expect_equal(
            errors,
            label=f"{owner_label} next detail {field}",
            actual=detail.get(field),
            expected=expected_detail.get(field),
        )
    boundary = detail.get("explicit_non_approval_boundary", "")
    if "does not choose or approve" not in boundary:
        errors.append(
            f"{owner_label} next detail boundary must deny convention approval"
        )


def _verify_pulse(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
    pulse_snapshot: dict[str, Any],
    expected_next_detail: dict[str, Any],
    errors: list[str],
) -> None:
    monitor_pulse = monitoring.get("pulse") or {}
    completion = monitoring.get("completion_verification") or {}
    open_blocker_count = len(manifest.get("open_blockers", []))
    _expect_equal(
        errors,
        label="current pulse generated_at",
        actual=pulse_snapshot.get("generated_at"),
        expected=monitoring.get("generated_at"),
    )
    _expect_equal(
        errors,
        label="current pulse repo_root",
        actual=pulse_snapshot.get("repo_root"),
        expected=".",
    )
    _expect_repo_relative_identifier(
        errors,
        label="current pulse manifest_path",
        actual=pulse_snapshot.get("manifest_path"),
    )
    _expect_repo_relative_identifier(
        errors,
        label="current pulse strict gate source",
        actual=(pulse_snapshot.get("strict_gate_matrix") or {}).get("source"),
    )
    _expect_equal(
        errors,
        label="monitoring pulse status",
        actual=monitor_pulse.get("status"),
        expected=pulse_snapshot.get("status"),
    )
    _expect_equal(
        errors,
        label="monitoring pulse completion_state",
        actual=monitor_pulse.get("completion_state"),
        expected="not_complete",
    )
    _expect_equal(
        errors,
        label="monitoring pulse open_blocker_count",
        actual=monitor_pulse.get("open_blocker_count"),
        expected=open_blocker_count,
    )
    _expect_equal(
        errors,
        label="monitoring pulse next_blocker_id",
        actual=monitor_pulse.get("next_blocker_id"),
        expected=EXPECTED_NEXT_BLOCKER_ID,
    )
    _expect_equal(
        errors,
        label="monitoring pulse drift_errors",
        actual=monitor_pulse.get("drift_errors"),
        expected=pulse_snapshot.get("drift_errors"),
    )
    _expect_equal(
        errors,
        label="monitoring pulse drift_error_count",
        actual=monitor_pulse.get("drift_error_count"),
        expected=len(monitor_pulse.get("drift_errors") or []),
    )
    _expect_equal(
        errors,
        label="monitoring pulse calculation_post_owner_plan_renderer_sync",
        actual=monitor_pulse.get("calculation_post_owner_plan_renderer_sync"),
        expected=completion.get("calculation_post_owner_plan_renderer_sync"),
    )
    _expect_equal(
        errors,
        label="current pulse status",
        actual=pulse_snapshot.get("status"),
        expected=monitor_pulse.get("status"),
    )
    _expect_equal(
        errors,
        label="current pulse completion_state",
        actual=pulse_snapshot.get("completion_state"),
        expected=monitor_pulse.get("completion_state"),
    )
    _expect_equal(
        errors,
        label="current pulse open_blocker_count",
        actual=pulse_snapshot.get("open_blocker_count"),
        expected=monitor_pulse.get("open_blocker_count"),
    )
    _expect_equal(
        errors,
        label="current pulse blocker intake next_blocker_id",
        actual=pulse_snapshot.get("blocker_intake_board", {}).get("next_blocker_id"),
        expected=monitor_pulse.get("next_blocker_id"),
    )
    _expect_equal(
        errors,
        label="current pulse drift_errors",
        actual=pulse_snapshot.get("drift_errors"),
        expected=monitor_pulse.get("drift_errors"),
    )
    _expect_equal(
        errors,
        label="current pulse calculation_post_owner_plan_renderer_sync",
        actual=pulse_snapshot.get("calculation_post_owner_plan_renderer_sync"),
        expected=monitor_pulse.get("calculation_post_owner_plan_renderer_sync"),
    )
    _expect_equal(
        errors,
        label="current pulse business_contract_certified_count",
        actual=pulse_snapshot.get("route_scope", {}).get(
            "business_contract_certified_count"
        ),
        expected=manifest.get("counts", {}).get("business_contract_certified_routes"),
    )
    _expect_equal(
        errors,
        label="current pulse business display route_gap_count",
        actual=pulse_snapshot.get("business_display", {}).get("route_gap_count"),
        expected=manifest.get("counts", {}).get("business_display_route_gaps"),
    )

    next_detail = monitor_pulse.get("next_blocker_detail")
    if not isinstance(next_detail, dict):
        errors.append("monitoring pulse next_blocker_detail must be an object")
        return
    _verify_next_blocker_detail(
        detail=next_detail,
        expected_detail=expected_next_detail,
        owner_label="monitoring pulse",
        errors=errors,
    )


def _verify_strict_gate_matrix(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
    errors: list[str],
) -> None:
    matrix = monitoring.get("strict_gate_matrix") or {}
    gates = matrix.get("gates")
    open_blocker_count = len(manifest.get("open_blockers", []))
    _expect_equal(
        errors,
        label="strict gate matrix completion_state",
        actual=matrix.get("completion_state"),
        expected=monitoring.get("pulse", {}).get("completion_state"),
    )
    _expect_false(
        errors,
        label="strict gate matrix full_score_ready",
        actual=matrix.get("full_score_ready"),
    )
    _expect_equal(
        errors,
        label="strict gate matrix open_blocker_count",
        actual=matrix.get("open_blocker_count"),
        expected=open_blocker_count,
    )
    _expect_equal(
        errors,
        label="strict gate matrix completion_order_guard_status",
        actual=matrix.get("completion_order_guard_status"),
        expected=monitoring.get("completion_verification", {}).get(
            "follow_up_completion_order_status"
        ),
    )
    _expect_equal(
        errors,
        label="strict gate matrix completion_order_guard_error_count",
        actual=matrix.get("completion_order_guard_error_count"),
        expected=monitoring.get("completion_verification", {}).get(
            "follow_up_completion_order_error_count"
        ),
    )
    _expect_equal(
        errors,
        label="strict gate matrix gate_count",
        actual=matrix.get("gate_count"),
        expected=len(EXPECTED_STRICT_GATE_IDS),
    )
    if not isinstance(gates, list):
        errors.append("strict gate matrix gates must be a list")
        return

    guard_errors = matrix.get("guard_errors")
    if not isinstance(guard_errors, list):
        errors.append("strict gate matrix guard_errors must be a list")
        guard_errors = []
    completion = monitoring.get("completion_verification") or {}
    expected_guard_errors: list[str] = []
    completion_order_status = completion.get("follow_up_completion_order_status")
    completion_order_error_count = completion.get(
        "follow_up_completion_order_error_count"
    )
    if completion_order_status != "pass":
        expected_guard_errors.append(
            "completion order guard status expected 'pass', "
            f"got {completion_order_status!r}"
        )
    if completion_order_error_count != 0:
        expected_guard_errors.append(
            "completion order guard error count expected 0, "
            f"got {completion_order_error_count!r}"
        )
    expected_blocked_count = sum(
        1
        for gate in gates
        if isinstance(gate, dict) and gate.get("expected_current_exit") == "non_zero"
    )
    strict_pass_count = sum(
        1
        for gate in gates
        if isinstance(gate, dict) and gate.get("strict_pass") is True
    )
    unexpected_count = sum(
        1
        for gate in gates
        if isinstance(gate, dict) and gate.get("expectation_met") is False
    )
    expected_status = (
        "pass" if unexpected_count == 0 and not expected_guard_errors else "fail"
    )
    _expect_equal(
        errors,
        label="strict gate matrix status",
        actual=matrix.get("status"),
        expected=expected_status,
    )
    _expect_equal(
        errors,
        label="strict gate matrix expected_blocked_gate_count",
        actual=matrix.get("expected_blocked_gate_count"),
        expected=expected_blocked_count,
    )
    _expect_equal(
        errors,
        label="strict gate matrix strict_pass_gate_count",
        actual=matrix.get("strict_pass_gate_count"),
        expected=strict_pass_count,
    )
    _expect_equal(
        errors,
        label="strict gate matrix unexpected_gate_count",
        actual=matrix.get("unexpected_gate_count"),
        expected=unexpected_count,
    )
    _expect_equal(
        errors,
        label="strict gate matrix guard_error_count",
        actual=matrix.get("guard_error_count"),
        expected=len(expected_guard_errors),
    )
    _expect_equal(
        errors,
        label="strict gate matrix guard_errors",
        actual=guard_errors,
        expected=expected_guard_errors,
    )

    gate_ids = {gate.get("gate_id") for gate in gates if isinstance(gate, dict)}
    if gate_ids != EXPECTED_STRICT_GATE_IDS:
        errors.append("strict gate matrix gate IDs do not match expected gates")
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("strict gate matrix gates must contain objects")
            continue
        gate_id = gate.get("gate_id")
        if gate.get("expected_current_exit") != "non_zero":
            errors.append(
                f"strict gate {gate_id} expected_current_exit must be non_zero"
            )
        expected_actual_exit = "zero" if gate.get("strict_pass") is True else "non_zero"
        if gate.get("actual_current_exit") != expected_actual_exit:
            errors.append(
                f"strict gate {gate_id} actual_current_exit expected "
                f"{expected_actual_exit!r}, got {gate.get('actual_current_exit')!r}"
            )
        expected_expectation_met = (
            gate.get("actual_current_exit") == gate.get("expected_current_exit")
        )
        if gate.get("expectation_met") is not expected_expectation_met:
            errors.append(
                f"strict gate {gate_id} expectation_met expected "
                f"{expected_expectation_met!r}, got {gate.get('expectation_met')!r}"
            )

    boundary = matrix.get("boundary", "")
    if "does not approve owner decisions" not in boundary:
        errors.append("strict gate matrix boundary must deny owner-decision approval")
    if "governance writes" not in boundary:
        errors.append("strict gate matrix boundary must deny governance writes")


def _verify_blocker_intake_board(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
    expected_next_detail: dict[str, Any],
    errors: list[str],
) -> None:
    board = monitoring.get("blocker_intake_board") or {}
    open_blocker_ids = [item.get("id") for item in manifest.get("open_blockers", [])]
    expected_order = [
        "calculation-display-p1-decisions",
        "ledger-pnl-direct-governance-record",
        "owner-approval-7-pages",
        "direct-app-mcp-gitnexus-evidence",
        "local-secret-hygiene",
    ]

    _expect_equal(
        errors,
        label="blocker intake board status",
        actual=board.get("status"),
        expected="open_external_input_required",
    )
    _expect_equal(
        errors,
        label="blocker intake board blocker_count",
        actual=board.get("blocker_count"),
        expected=len(open_blocker_ids),
    )
    _expect_equal(
        errors,
        label="blocker intake board completion_order",
        actual=board.get("completion_order"),
        expected=expected_order,
    )
    if set(board.get("completion_order") or []) != set(open_blocker_ids):
        errors.append("blocker intake board completion_order does not cover open blockers")
    _expect_equal(
        errors,
        label="blocker intake board next_blocker_id",
        actual=board.get("next_blocker_id"),
        expected=EXPECTED_NEXT_BLOCKER_ID,
    )
    if board.get("next_blocker_detail") != monitoring.get("pulse", {}).get(
        "next_blocker_detail"
    ):
        errors.append(
            "blocker intake board next_blocker_detail must match monitoring pulse"
        )
    next_detail = board.get("next_blocker_detail")
    if isinstance(next_detail, dict):
        _verify_next_blocker_detail(
            detail=next_detail,
            expected_detail=expected_next_detail,
            owner_label="blocker intake board",
            errors=errors,
        )
    else:
        errors.append("blocker intake board next_blocker_detail must be an object")

    scope = board.get("evidence_scope") or {}
    _expect_equal(
        errors,
        label="blocker intake board read_only",
        actual=scope.get("read_only"),
        expected=True,
    )
    for flag in [
        "approves_metrics",
        "approves_pages",
        "captures_business_owner_approval",
        "writes_governance_records",
        "authorizes_ledger_pnl_governance_write",
        "captures_direct_app_mcp_gitnexus_evidence",
        "requests_or_captures_secret_values",
        "clears_secret_scan",
        "certifies_routes",
    ]:
        _expect_false(
            errors,
            label=f"blocker intake board {flag}",
            actual=scope.get(flag),
        )
    boundary = board.get("boundary", "")
    if "does not approve metrics" not in boundary:
        errors.append("blocker intake board boundary must deny metric approval")
    if "does not approve metrics" in boundary and "Ledger PnL --write" not in boundary:
        errors.append("blocker intake board boundary must deny Ledger PnL --write")


def _verify_latest_session_recheck(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
    errors: list[str],
) -> None:
    recheck = monitoring.get("latest_session_recheck") or {}
    blockers = _blockers_by_id(manifest)
    matrix = monitoring.get("strict_gate_matrix") or {}
    _expect_equal(
        errors,
        label="latest session recheck closure_effect",
        actual=recheck.get("closure_effect"),
        expected="none",
    )
    _expect_equal(
        errors,
        label="latest session recheck open_blocker_count",
        actual=recheck.get("open_blocker_count"),
        expected=len(manifest.get("open_blockers", [])),
    )
    _expect_equal(
        errors,
        label="latest session next blocker id",
        actual=(recheck.get("next_blocker") or {}).get("blocker_id"),
        expected=EXPECTED_NEXT_BLOCKER_ID,
    )
    _expect_equal(
        errors,
        label="latest session calculation_post_owner_plan_renderer_sync",
        actual=recheck.get("calculation_post_owner_plan_renderer_sync"),
        expected=monitoring.get("completion_verification", {}).get(
            "calculation_post_owner_plan_renderer_sync"
        ),
    )

    strict = recheck.get("strict_gate_matrix") or {}
    _expect_equal(
        errors,
        label="latest session strict gate matrix status",
        actual=strict.get("status"),
        expected=matrix.get("status"),
    )
    _expect_equal(
        errors,
        label="latest session strict gate count",
        actual=strict.get("gate_count"),
        expected=len(EXPECTED_STRICT_GATE_IDS),
    )
    _expect_equal(
        errors,
        label="latest session strict pass gate count",
        actual=strict.get("strict_pass_gate_count"),
        expected=matrix.get("strict_pass_gate_count"),
    )
    _expect_equal(
        errors,
        label="latest session unexpected strict gate count",
        actual=strict.get("unexpected_gate_count"),
        expected=matrix.get("unexpected_gate_count"),
    )
    _expect_equal(
        errors,
        label="latest session completion order guard status",
        actual=strict.get("completion_order_guard_status"),
        expected=monitoring.get("completion_verification", {}).get(
            "follow_up_completion_order_status"
        ),
    )
    _expect_equal(
        errors,
        label="latest session guard error count",
        actual=strict.get("guard_error_count"),
        expected=matrix.get("guard_error_count"),
    )

    direct = recheck.get("direct_app_mcp_gitnexus_tool_surface") or {}
    _expect_equal(
        errors,
        label="latest session direct App checked_at",
        actual=direct.get("checked_at"),
        expected=(blockers.get("direct-app-mcp-gitnexus-evidence") or {}).get(
            "last_checked_at"
        ),
    )
    _expect_equal(
        errors,
        label="latest session direct App status",
        actual=direct.get("status"),
        expected="tool_surface_unavailable_in_current_codex_app_session",
    )
    _expect_equal(
        errors,
        label="latest session returned primary tool count",
        actual=direct.get("returned_primary_tool_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session returned GitNexus tool count",
        actual=direct.get("returned_gitnexus_tool_count"),
        expected=3,
    )
    _expect_equal(
        errors,
        label="latest session returned MOSS general tool count",
        actual=direct.get("returned_moss_general_tool_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session returned MOSS named tool count",
        actual=direct.get("returned_moss_named_tool_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session relevant direct tool count",
        actual=direct.get("relevant_direct_tool_count"),
        expected=0,
    )
    _expect_false(
        errors,
        label="latest session direct App MCP evidence captured",
        actual=direct.get("direct_app_mcp_evidence_captured"),
    )
    _expect_false(
        errors,
        label="latest session direct GitNexus evidence captured",
        actual=direct.get("direct_gitnexus_evidence_captured"),
    )

    secret = recheck.get("local_secret_hygiene") or {}
    _expect_equal(
        errors,
        label="latest session local secret checked_at",
        actual=secret.get("checked_at"),
        expected=(blockers.get("local-secret-hygiene") or {}).get("last_checked_at"),
    )
    _expect_false(
        errors,
        label="latest session secret values_read",
        actual=secret.get("values_read"),
    )
    _expect_false(
        errors,
        label="latest session secret_values_captured",
        actual=secret.get("secret_values_captured"),
    )
    _expect_false(
        errors,
        label="latest session clears_secret_scan",
        actual=secret.get("clears_secret_scan"),
    )

    ledger = recheck.get("ledger_pnl_direct_governance_record") or {}
    _expect_equal(
        errors,
        label="latest session Ledger checked_at",
        actual=ledger.get("checked_at"),
        expected=(blockers.get("ledger-pnl-direct-governance-record") or {}).get(
            "last_checked_at"
        ),
    )
    _expect_equal(
        errors,
        label="latest session Ledger record_write_status",
        actual=ledger.get("record_write_status"),
        expected="not_requested",
    )
    _expect_false(
        errors,
        label="latest session writes_governance_records",
        actual=ledger.get("writes_governance_records"),
    )
    _expect_false(
        errors,
        label="latest session Ledger formal_use_allowed",
        actual=ledger.get("formal_use_allowed"),
    )

    calculation = recheck.get("calculation_owner_decision") or {}
    _expect_equal(
        errors,
        label="latest session calculation checked_at",
        actual=calculation.get("checked_at"),
        expected=(blockers.get(EXPECTED_NEXT_BLOCKER_ID) or {}).get(
            "last_checked_at"
        ),
    )
    _expect_equal(
        errors,
        label="latest session calculation captured_decision_count",
        actual=calculation.get("captured_decision_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session calculation incomplete_decision_count",
        actual=calculation.get("incomplete_decision_count"),
        expected=manifest.get("counts", {}).get("calculation_display_open_p1"),
    )
    _expect_equal(
        errors,
        label="latest session calculation invalid_selected_decision_count",
        actual=calculation.get("invalid_selected_decision_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session calculation invalid_status_count",
        actual=calculation.get("invalid_status_count"),
        expected=0,
    )
    _expect_false(
        errors,
        label="latest session chooses_or_approves_conventions",
        actual=calculation.get("chooses_or_approves_conventions"),
    )


def _verify_completion_mirror(
    *,
    monitoring: dict[str, Any],
    completion_verification: dict[str, Any],
    errors: list[str],
) -> None:
    monitoring_completion = monitoring.get("completion_verification") or {}
    for key in COMPLETION_VERIFICATION_MIRROR_KEYS:
        _expect_equal(
            errors,
            label=f"monitoring completion {key}",
            actual=monitoring_completion.get(key),
            expected=completion_verification.get(key),
        )
    _expect_equal(
        errors,
        label="monitoring completion error_count",
        actual=monitoring_completion.get("error_count"),
        expected=len(completion_verification.get("errors") or []),
    )


def verify_monitoring_snapshot(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    errors: list[str] = []

    monitoring_path = _artifact_path(
        manifest,
        "system_audit_monitoring_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    completion_path = _artifact_path(
        manifest,
        "completion_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    follow_up_packet_path = _artifact_path(
        manifest,
        "owner_governance_follow_up_packet",
        repo_root=repo_root,
        errors=errors,
    )
    pulse_path = _artifact_path(
        manifest,
        "system_audit_pulse_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    calculation_path = _artifact_path(
        manifest,
        "calculation_owner_decision_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    direct_path = _artifact_path(
        manifest,
        "direct_app_mcp_gitnexus_tool_surface_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    secret_path = _artifact_path(
        manifest,
        "local_secret_hygiene_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    ledger_path = _artifact_path(
        manifest,
        "ledger_pnl_direct_governance_record_snapshot",
        repo_root=repo_root,
        errors=errors,
    )
    if errors:
        return {
            "report_kind": "system_audit_monitoring_snapshot_verification",
            "status": "fail",
            "manifest_path": str(manifest_path),
            "monitoring_snapshot_path": str(monitoring_path) if monitoring_path else None,
            "open_blocker_count": len(manifest.get("open_blockers", [])),
            "error_count": len(errors),
            "errors": errors,
        }

    assert monitoring_path is not None
    assert completion_path is not None
    assert follow_up_packet_path is not None
    assert pulse_path is not None
    assert calculation_path is not None
    assert direct_path is not None
    assert secret_path is not None
    assert ledger_path is not None

    monitoring = _load_json(monitoring_path)
    completion_snapshot = _load_json(completion_path)
    follow_up_packet = _load_json(follow_up_packet_path)
    pulse_snapshot = _load_json(pulse_path)
    calculation = _load_json(calculation_path)
    direct_tool = _load_json(direct_path)
    secret = _load_json(secret_path)
    ledger = _load_json(ledger_path)
    completion_verification = verify_completion_snapshot(
        manifest_path=manifest_path,
        repo_root=repo_root,
        verify_monitoring=False,
    )
    expected_next_detail = _expected_next_blocker_detail(follow_up_packet)

    _expect_equal(
        errors,
        label="monitoring report_kind",
        actual=monitoring.get("report_kind"),
        expected="system_audit_monitoring_snapshot",
    )
    _expect_equal(
        errors,
        label="monitoring generated_at",
        actual=monitoring.get("generated_at"),
        expected=manifest.get("generated_at"),
    )
    _expect_equal(
        errors,
        label="monitoring evidence_scope",
        actual=monitoring.get("evidence_scope"),
        expected=EXPECTED_EVIDENCE_SCOPE,
    )
    _expect_equal(
        errors,
        label="monitoring write_outputs",
        actual=monitoring.get("write_outputs"),
        expected=False,
    )
    _expect_equal(
        errors,
        label="monitoring repo_root",
        actual=monitoring.get("repo_root"),
        expected=".",
    )
    expected_output_paths = {
        key: str(manifest.get("artifacts", {}).get(key, "")).replace("\\", "/")
        for key in (
            "calculation_owner_decision_snapshot",
            "direct_app_mcp_gitnexus_tool_surface_snapshot",
            "local_secret_hygiene_snapshot",
            "ledger_pnl_direct_governance_record_snapshot",
            "system_audit_pulse_snapshot",
        )
    }
    _expect_equal(
        errors,
        label="monitoring output_paths",
        actual=monitoring.get("output_paths"),
        expected=expected_output_paths,
    )
    for key, value in (monitoring.get("output_paths") or {}).items():
        _expect_repo_relative_identifier(
            errors,
            label=f"monitoring output path {key}",
            actual=value,
        )
    boundary = monitoring.get("boundary", "")
    if "does not write DuckDB or governance records" not in boundary:
        errors.append("monitoring boundary must deny DuckDB/governance writes")
    if "read or rotate secret values" not in boundary:
        errors.append("monitoring boundary must deny secret reads/rotation")
    if "approve metrics or pages" not in boundary:
        errors.append("monitoring boundary must deny metric/page approval")

    _verify_completion_mirror(
        monitoring=monitoring,
        completion_verification=completion_verification,
        errors=errors,
    )
    _expect_equal(
        errors,
        label="completion snapshot open_blocker_count",
        actual=completion_snapshot.get("summary", {}).get("open_blocker_count"),
        expected=len(manifest.get("open_blockers", [])),
    )

    _verify_pulse(
        manifest=manifest,
        monitoring=monitoring,
        pulse_snapshot=pulse_snapshot,
        expected_next_detail=expected_next_detail,
        errors=errors,
    )
    _verify_strict_gate_matrix(
        manifest=manifest,
        monitoring=monitoring,
        errors=errors,
    )
    _verify_blocker_intake_board(
        manifest=manifest,
        monitoring=monitoring,
        expected_next_detail=expected_next_detail,
        errors=errors,
    )
    _verify_refresh_results(
        manifest=manifest,
        monitoring=monitoring,
        calculation=calculation,
        direct_tool=direct_tool,
        secret=secret,
        ledger=ledger,
        errors=errors,
    )
    _verify_latest_session_recheck(
        manifest=manifest,
        monitoring=monitoring,
        errors=errors,
    )

    return {
        "report_kind": "system_audit_monitoring_snapshot_verification",
        "status": "pass" if not errors else "fail",
        "manifest_path": str(manifest_path),
        "monitoring_snapshot_path": str(monitoring_path),
        "generated_at": monitoring.get("generated_at"),
        "open_blocker_count": len(manifest.get("open_blockers", [])),
        "next_blocker_id": monitoring.get("pulse", {}).get("next_blocker_id"),
        "calculation_post_owner_plan_renderer_sync": monitoring.get(
            "pulse", {}
        ).get("calculation_post_owner_plan_renderer_sync"),
        "completion_status": monitoring.get("completion_verification", {}).get("status"),
        "completion_order_guard_status": monitoring.get(
            "completion_verification",
            {},
        ).get("follow_up_completion_order_status"),
        "pulse_status": monitoring.get("pulse", {}).get("status"),
        "pulse_completion_state": monitoring.get("pulse", {}).get("completion_state"),
        "strict_gate_status": monitoring.get("strict_gate_matrix", {}).get("status"),
        "strict_pass_gate_count": monitoring.get("strict_gate_matrix", {}).get(
            "strict_pass_gate_count"
        ),
        "strict_gate_count": monitoring.get("strict_gate_matrix", {}).get("gate_count"),
        "strict_completion_order_guard_status": monitoring.get(
            "strict_gate_matrix", {}
        ).get("completion_order_guard_status"),
        "error_count": len(errors),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the read-only system audit monitoring snapshot against the manifest, "
            "pulse, completion snapshot, and blocker-specific snapshots."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help=(
            "Exit non-zero unless monitoring verification passes with zero open blockers "
            "and a completion-ready pulse. The default verifies monitoring alignment."
        ),
    )
    args = parser.parse_args(argv)

    result = verify_monitoring_snapshot(manifest_path=args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "pass":
        return 1
    if args.require_complete and (
        result["open_blocker_count"] != 0
        or result["pulse_completion_state"] != "ready_for_completion_audit"
    ):
        print(
            (
                "System audit monitoring is not complete: "
                f"open_blocker_count={result['open_blocker_count']}, "
                f"pulse_completion_state={result['pulse_completion_state']}, "
                f"completion_status={result['completion_status']}"
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
