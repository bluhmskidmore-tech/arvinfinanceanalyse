from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_system_audit_completion_snapshot import verify_completion_snapshot


DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"

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
    "ledger-pnl-written-record-located",
    "direct-app-mcp-gitnexus-evidence-captured",
    "local-secret-hygiene-clean-boundary",
}


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


def _blockers_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("id"): item for item in manifest.get("open_blockers", [])}


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
    generated_at = monitoring.get("generated_at")

    calculation_result = refresh.get("calculation_owner_decision") or {}
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
        expected=calculation.get("capture_template", {}).get("captured_decision_count"),
    )
    _expect_equal(
        errors,
        label="calculation refresh incomplete_decision_count",
        actual=calculation_result.get("incomplete_decision_count"),
        expected=calculation.get("capture_template", {}).get(
            "incomplete_decision_count"
        ),
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
        actual=(blockers.get("calculation-display-p1-decisions") or {}).get(
            "last_checked_at"
        ),
        expected=calculation.get("generated_at"),
    )
    _expect_equal(
        errors,
        label="calculation snapshot generated_at",
        actual=calculation.get("generated_at"),
        expected=generated_at,
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
        expected=generated_at,
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
        expected=generated_at,
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
        expected=generated_at,
    )


def _verify_pulse(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
    pulse_snapshot: dict[str, Any],
    errors: list[str],
) -> None:
    monitor_pulse = monitoring.get("pulse") or {}
    open_blocker_count = len(manifest.get("open_blockers", []))
    _expect_equal(
        errors,
        label="monitoring pulse status",
        actual=monitor_pulse.get("status"),
        expected="pass",
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
        label="monitoring pulse drift_errors",
        actual=monitor_pulse.get("drift_errors"),
        expected=[],
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
        label="current pulse drift_errors",
        actual=pulse_snapshot.get("drift_errors"),
        expected=monitor_pulse.get("drift_errors"),
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
        label="strict gate matrix status",
        actual=matrix.get("status"),
        expected="pass",
    )
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
    _expect_equal(
        errors,
        label="strict gate matrix expected_blocked_gate_count",
        actual=matrix.get("expected_blocked_gate_count"),
        expected=len(EXPECTED_STRICT_GATE_IDS),
    )
    _expect_equal(
        errors,
        label="strict gate matrix strict_pass_gate_count",
        actual=matrix.get("strict_pass_gate_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="strict gate matrix unexpected_gate_count",
        actual=matrix.get("unexpected_gate_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="strict gate matrix guard_error_count",
        actual=matrix.get("guard_error_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="strict gate matrix guard_errors",
        actual=matrix.get("guard_errors"),
        expected=[],
    )
    if not isinstance(gates, list):
        errors.append("strict gate matrix gates must be a list")
        return
    gate_ids = {gate.get("gate_id") for gate in gates if isinstance(gate, dict)}
    if gate_ids != EXPECTED_STRICT_GATE_IDS:
        errors.append("strict gate matrix gate IDs do not match expected gates")
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("strict gate matrix gates must contain objects")
            continue
        gate_id = gate.get("gate_id")
        if gate.get("expected_current_exit") != "non_zero":
            errors.append(f"strict gate {gate_id} expected_current_exit must be non_zero")
        if gate.get("actual_current_exit") != "non_zero":
            errors.append(f"strict gate {gate_id} actual_current_exit must be non_zero")
        if gate.get("strict_pass") is not False:
            errors.append(f"strict gate {gate_id} strict_pass must be false")
        if gate.get("expectation_met") is not True:
            errors.append(f"strict gate {gate_id} expectation_met must be true")
    boundary = matrix.get("boundary", "")
    if "does not approve owner decisions" not in boundary:
        errors.append("strict gate matrix boundary must deny owner-decision approval")
    if "governance writes" not in boundary:
        errors.append("strict gate matrix boundary must deny governance writes")


def _verify_blocker_intake_board(
    *,
    manifest: dict[str, Any],
    monitoring: dict[str, Any],
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
        expected="calculation-display-p1-decisions",
    )
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
    strict = recheck.get("strict_gate_matrix") or {}
    _expect_equal(
        errors,
        label="latest session strict gate matrix status",
        actual=strict.get("status"),
        expected="pass",
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
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session unexpected strict gate count",
        actual=strict.get("unexpected_gate_count"),
        expected=0,
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
        expected=0,
    )

    direct = recheck.get("direct_app_mcp_gitnexus_tool_surface") or {}
    _expect_equal(
        errors,
        label="latest session direct App checked_at",
        actual=direct.get("checked_at"),
        expected=recheck.get("checked_at"),
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
        label="latest session calculation captured_decision_count",
        actual=calculation.get("captured_decision_count"),
        expected=0,
    )
    _expect_equal(
        errors,
        label="latest session calculation incomplete_decision_count",
        actual=calculation.get("incomplete_decision_count"),
        expected=10,
    )
    _expect_false(
        errors,
        label="latest session chooses_or_approves_conventions",
        actual=calculation.get("chooses_or_approves_conventions"),
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
    assert pulse_path is not None
    assert calculation_path is not None
    assert direct_path is not None
    assert secret_path is not None
    assert ledger_path is not None

    monitoring = _load_json(monitoring_path)
    completion_snapshot = _load_json(completion_path)
    pulse_snapshot = _load_json(pulse_path)
    calculation = _load_json(calculation_path)
    direct_tool = _load_json(direct_path)
    secret = _load_json(secret_path)
    ledger = _load_json(ledger_path)
    completion_verification = verify_completion_snapshot(
        manifest_path=manifest_path,
        repo_root=repo_root,
    )

    _expect_equal(
        errors,
        label="monitoring report_kind",
        actual=monitoring.get("report_kind"),
        expected="system_audit_monitoring_snapshot",
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
        expected=True,
    )
    boundary = monitoring.get("boundary", "")
    if "does not write DuckDB or governance records" not in boundary:
        errors.append("monitoring boundary must deny DuckDB/governance writes")
    if "read or rotate secret values" not in boundary:
        errors.append("monitoring boundary must deny secret reads/rotation")
    if "approve metrics or pages" not in boundary:
        errors.append("monitoring boundary must deny metric/page approval")

    _expect_equal(
        errors,
        label="completion verifier status",
        actual=completion_verification.get("status"),
        expected="pass",
    )
    _expect_equal(
        errors,
        label="monitoring completion status",
        actual=monitoring.get("completion_verification", {}).get("status"),
        expected=completion_verification.get("status"),
    )
    _expect_equal(
        errors,
        label="monitoring completion open_blocker_count",
        actual=monitoring.get("completion_verification", {}).get("open_blocker_count"),
        expected=completion_verification.get("open_blocker_count"),
    )
    _expect_equal(
        errors,
        label="monitoring completion follow_up_completion_order_status",
        actual=monitoring.get("completion_verification", {}).get(
            "follow_up_completion_order_status"
        ),
        expected=completion_verification.get("follow_up_completion_order_status"),
    )
    _expect_equal(
        errors,
        label="monitoring completion follow_up_completion_order_error_count",
        actual=monitoring.get("completion_verification", {}).get(
            "follow_up_completion_order_error_count"
        ),
        expected=completion_verification.get("follow_up_completion_order_error_count"),
    )
    _expect_equal(
        errors,
        label="monitoring completion errors",
        actual=monitoring.get("completion_verification", {}).get("errors"),
        expected=completion_verification.get("errors"),
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
