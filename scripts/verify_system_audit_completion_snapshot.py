from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"
EXPECTED_OPEN_CALCULATION_P1_IDS = [
    "P1-01",
    "P1-02",
    "P1-03",
    "P1-04",
    "P1-05",
    "P1-06",
    "P1-07",
    "P1-09",
    "P1-10",
    "P1-11",
]
FOLLOW_UP_COMPLETION_ORDER_CONSTRAINTS = [
    (
        "calculation-display-p1-decisions",
        "owner-approval-7-pages",
        "calculation-display P1 decisions must precede owner approval closure",
    ),
    (
        "ledger-pnl-direct-governance-record",
        "owner-approval-7-pages",
        "Ledger PnL direct governance record must precede owner approval closure",
    ),
]
FOLLOW_UP_COMPLETION_ORDER_ERROR_PREFIX = (
    "owner/governance follow-up packet completion_order"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(repo_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def _append_if_missing(value: Any, *, errors: list[str], message: str) -> None:
    if not value:
        errors.append(message)


def _verify_completion_order(
    *,
    completion_order: Any,
    blocker_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(completion_order, list):
        errors.append("owner/governance follow-up packet completion_order must be a list")
        return

    if len(completion_order) != len(blocker_ids):
        errors.append(
            "owner/governance follow-up packet completion_order length does not match open blockers"
        )
    if set(completion_order) != blocker_ids:
        errors.append(
            "owner/governance follow-up packet completion_order does not cover all blockers"
        )

    order_index = {
        blocker_id: index
        for index, blocker_id in enumerate(completion_order)
        if isinstance(blocker_id, str)
    }
    for predecessor, successor, message in FOLLOW_UP_COMPLETION_ORDER_CONSTRAINTS:
        if predecessor not in order_index or successor not in order_index:
            continue
        if order_index[predecessor] > order_index[successor]:
            errors.append(
                f"owner/governance follow-up packet completion_order invalid: {message}"
            )


def _verify_source_artifact_link(
    *,
    manifest: dict[str, Any],
    source_artifacts: dict[str, Any],
    key: str,
    owner: str,
    errors: list[str],
) -> None:
    manifest_rel_path = manifest.get("artifacts", {}).get(key)
    if not manifest_rel_path:
        errors.append(f"manifest missing {key} artifact")
        return
    if source_artifacts.get(key) != manifest_rel_path:
        errors.append(f"{owner} {key} source mismatch")


def _verify_monitoring_snapshot(
    *,
    manifest: dict[str, Any],
    repo_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    rel_path = manifest.get("artifacts", {}).get("system_audit_monitoring_snapshot")
    if not rel_path:
        errors.append("manifest missing system_audit_monitoring_snapshot artifact")
        return None

    path = repo_root / rel_path
    if not path.exists():
        errors.append("system audit monitoring snapshot artifact is missing")
        return None

    snapshot = _load_json(path)
    if snapshot.get("report_kind") != "system_audit_monitoring_snapshot":
        errors.append("system audit monitoring snapshot report_kind is invalid")

    generated_at = snapshot.get("generated_at")
    if manifest.get("generated_at") != generated_at:
        errors.append("manifest generated_at does not match system audit monitoring snapshot")

    expected_scope = {
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
    if snapshot.get("evidence_scope") != expected_scope:
        errors.append("system audit monitoring snapshot evidence_scope is not fail-closed")

    open_blocker_count = len(manifest.get("open_blockers", []))
    completion = snapshot.get("completion_verification", {})
    if completion.get("status") != "pass":
        errors.append("system audit monitoring completion verification must pass")
    if completion.get("open_blocker_count") != open_blocker_count:
        errors.append("system audit monitoring open blocker count does not match manifest")
    if completion.get("error_count") != 0:
        errors.append("system audit monitoring completion verification has errors")

    pulse = snapshot.get("pulse", {})
    if pulse.get("status") != "pass":
        errors.append("system audit monitoring pulse must pass")
    if pulse.get("completion_state") != "not_complete":
        errors.append("system audit monitoring pulse must remain not_complete")
    if pulse.get("open_blocker_count") != open_blocker_count:
        errors.append("system audit monitoring pulse blocker count does not match manifest")
    if pulse.get("drift_errors") != []:
        errors.append("system audit monitoring pulse has drift_errors")

    blocker_board = snapshot.get("blocker_intake_board", {})
    if blocker_board.get("status") != "open_external_input_required":
        errors.append("system audit monitoring blocker intake board must remain open")
    if blocker_board.get("blocker_count") != open_blocker_count:
        errors.append("system audit monitoring blocker intake count does not match manifest")
    if blocker_board.get("next_blocker_id") != "calculation-display-p1-decisions":
        errors.append("system audit monitoring blocker intake next blocker drifted")
    board_scope = blocker_board.get("evidence_scope", {})
    if board_scope.get("read_only") is not True:
        errors.append("system audit monitoring blocker intake board must be read-only")
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
        if board_scope.get(flag) is not False:
            errors.append(f"system audit monitoring blocker intake flag {flag} must be false")

    refresh = snapshot.get("refresh_results", {})
    calculation = refresh.get("calculation_owner_decision", {})
    if calculation.get("captured_decision_count") != 0:
        errors.append("system audit monitoring must not capture calculation owner decisions")
    ledger = refresh.get("ledger_pnl_direct_governance_record", {})
    if ledger.get("record_write_status") != "not_requested":
        errors.append("system audit monitoring must not write Ledger PnL governance records")
    if ledger.get("formal_use_allowed") is not False:
        errors.append("system audit monitoring must not allow Ledger PnL formal use")
    direct_tool = refresh.get("direct_app_mcp_gitnexus_tool_surface", {})
    if direct_tool.get("direct_app_mcp_evidence_captured") is not False:
        errors.append("system audit monitoring must not capture direct App MCP evidence")
    if direct_tool.get("direct_gitnexus_evidence_captured") is not False:
        errors.append("system audit monitoring must not capture direct GitNexus evidence")
    secret = refresh.get("local_secret_hygiene", {})
    if secret.get("secret_values_captured") is not False:
        errors.append("system audit monitoring must not capture secret values")
    if secret.get("clears_secret_scan") is not False:
        errors.append("system audit monitoring must not clear secret scan")

    if "does not write DuckDB or governance records" not in snapshot.get("boundary", ""):
        errors.append("system audit monitoring snapshot missing non-write boundary")

    return snapshot


def _verify_follow_up_packet(
    *,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    repo_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    packet_rel_path = manifest.get("artifacts", {}).get("owner_governance_follow_up_packet")
    if not packet_rel_path:
        errors.append("manifest missing owner_governance_follow_up_packet artifact")
        return None

    snapshot_packet_rel_path = snapshot.get("source_artifacts", {}).get(
        "owner_governance_follow_up_packet"
    )
    if snapshot_packet_rel_path != packet_rel_path:
        errors.append("completion snapshot owner_governance_follow_up_packet source mismatch")

    packet_path = repo_root / packet_rel_path
    if not packet_path.exists():
        errors.append("owner/governance follow-up packet artifact is missing")
        return None

    packet = _load_json(packet_path)
    if packet.get("report_kind") != "owner_governance_follow_up_packet":
        errors.append("owner/governance follow-up packet report_kind is invalid")
    if packet.get("generated_at") != manifest.get("generated_at"):
        errors.append("owner/governance follow-up packet generated_at does not match manifest")

    _verify_source_artifact_link(
        manifest=manifest,
        source_artifacts=packet.get("source_artifacts", {}),
        key="system_audit_monitoring_snapshot",
        owner="owner/governance follow-up packet",
        errors=errors,
    )

    status = packet.get("status", {})
    required_status = {
        "overall": "follow_up_required",
        "fail_closed": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "captures_direct_app_mcp_gitnexus_evidence": False,
        "requests_or_captures_secret_values": False,
        "authorizes_ledger_pnl_governance_write": False,
    }
    for key, expected in required_status.items():
        if status.get(key) != expected:
            errors.append(f"owner/governance follow-up packet status {key} must be {expected!r}")

    open_blockers = manifest.get("open_blockers", [])
    blockers_by_id = {item.get("id"): item for item in open_blockers}
    packet_blockers = {
        item.get("blocker_id"): item for item in packet.get("blocker_packets", [])
    }
    if set(packet_blockers) != set(blockers_by_id):
        errors.append("owner/governance follow-up packet IDs do not match manifest open_blockers")
    if packet.get("blocker_packet_count") != len(open_blockers):
        errors.append("owner/governance follow-up packet count does not match manifest")
    _verify_completion_order(
        completion_order=packet.get("completion_order"),
        blocker_ids=set(blockers_by_id),
        errors=errors,
    )

    for blocker_id, blocker in blockers_by_id.items():
        follow_up = packet_blockers.get(blocker_id)
        if follow_up is None:
            continue
        if follow_up.get("current_status") != "not_complete":
            errors.append(f"{blocker_id} follow-up status must be not_complete")
        if follow_up.get("last_checked_at") != blocker.get("last_checked_at"):
            errors.append(f"{blocker_id} follow-up last_checked_at does not match manifest")
        _append_if_missing(
            follow_up.get("responsible_owner_type"),
            errors=errors,
            message=f"{blocker_id} missing responsible_owner_type",
        )
        _append_if_missing(
            follow_up.get("required_input_artifacts"),
            errors=errors,
            message=f"{blocker_id} missing required_input_artifacts",
        )
        for artifact in follow_up.get("required_input_artifacts") or []:
            if not isinstance(artifact, str):
                errors.append(f"{blocker_id} has non-string required input artifact")
                continue
            if artifact.startswith("<"):
                continue
            if not _resolve(repo_root, artifact).exists():
                errors.append(
                    f"{blocker_id} required input artifact is missing: {artifact}"
                )
        _append_if_missing(
            follow_up.get("required_meeting_or_governance_output"),
            errors=errors,
            message=f"{blocker_id} missing required_meeting_or_governance_output",
        )
        _append_if_missing(
            follow_up.get("required_verification_commands"),
            errors=errors,
            message=f"{blocker_id} missing required_verification_commands",
        )
        _append_if_missing(
            follow_up.get("engineering_prework_available_now"),
            errors=errors,
            message=f"{blocker_id} missing engineering_prework_available_now",
        )
        _append_if_missing(
            follow_up.get("external_input_required_for_closure"),
            errors=errors,
            message=f"{blocker_id} missing external_input_required_for_closure",
        )
        _append_if_missing(
            follow_up.get("closure_evidence_after_external_input"),
            errors=errors,
            message=f"{blocker_id} missing closure_evidence_after_external_input",
        )
        _append_if_missing(
            follow_up.get("prohibited_actions"),
            errors=errors,
            message=f"{blocker_id} missing prohibited_actions",
        )
        _append_if_missing(
            follow_up.get("fail_closed_until"),
            errors=errors,
            message=f"{blocker_id} missing fail_closed_until",
        )
        if "does not" not in follow_up.get("explicit_non_approval_boundary", ""):
            errors.append(f"{blocker_id} follow-up missing explicit non-approval boundary")

    ledger_packet = packet_blockers.get("ledger-pnl-direct-governance-record", {})
    ledger_write_command = "python scripts\\emit_ledger_pnl_governance_record.py --write"
    if ledger_write_command not in ledger_packet.get(
        "authorization_required_commands_not_preapproved", []
    ):
        errors.append("Ledger PnL --write command must remain authorization-required")
    if not any(
        "--write without explicit governance-owner/user authorization" in action
        for action in ledger_packet.get("prohibited_actions", [])
    ):
        errors.append("Ledger PnL follow-up must prohibit unauthorized --write execution")
    if "does not authorize --write execution" not in ledger_packet.get(
        "explicit_non_approval_boundary", ""
    ):
        errors.append("Ledger PnL follow-up must state it does not authorize --write")
    if "authorization" not in " ".join(
        ledger_packet.get("external_input_required_for_closure", [])
    ):
        errors.append("Ledger PnL follow-up must keep --write authorization external")

    secret_packet = packet_blockers.get("local-secret-hygiene", {})
    secret_actions = " ".join(secret_packet.get("prohibited_actions", []))
    if "read or paste config/.env values" not in secret_actions:
        errors.append("local secret follow-up must prohibit reading or pasting values")
    if "commit config/.env or any credential value" not in secret_actions:
        errors.append("local secret follow-up must prohibit committing credential values")
    if "does not read, request, capture, rotate, clear, or approve any secret value" not in (
        secret_packet.get("explicit_non_approval_boundary", "")
    ):
        errors.append("local secret follow-up must preserve explicit no-secret-values boundary")
    if "without reading config/.env values" not in " ".join(
        secret_packet.get("engineering_prework_available_now", [])
    ):
        errors.append("local secret follow-up must keep engineering prework value-free")
    if "no secret values appear" not in " ".join(
        secret_packet.get("closure_evidence_after_external_input", [])
    ):
        errors.append("local secret follow-up must require no-value closure evidence")

    direct_app_packet = packet_blockers.get("direct-app-mcp-gitnexus-evidence", {})
    if "treat local stdio MCP success as direct App-surface closure" not in " ".join(
        direct_app_packet.get("prohibited_actions", [])
    ):
        errors.append("direct App MCP/GitNexus follow-up must keep local stdio fallback separate")
    if "fallback-only" not in " ".join(
        direct_app_packet.get("engineering_prework_available_now", [])
    ):
        errors.append("direct App MCP/GitNexus follow-up must mark local evidence fallback-only")

    global_boundary = packet.get("global_non_approval_boundary", "")
    if "does not approve metrics" not in global_boundary:
        errors.append("owner/governance follow-up packet must not approve metrics")
    if "business-owner signoff" not in global_boundary:
        errors.append("owner/governance follow-up packet must not approve owner signoff")

    return packet


def _verify_follow_up_brief(
    *,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    follow_up_packet: dict[str, Any] | None,
    repo_root: Path,
    errors: list[str],
) -> int | None:
    brief_rel_path = manifest.get("artifacts", {}).get("owner_governance_follow_up_brief_zh")
    if not brief_rel_path:
        errors.append("manifest missing owner_governance_follow_up_brief_zh artifact")
        return None

    snapshot_brief_rel_path = snapshot.get("source_artifacts", {}).get(
        "owner_governance_follow_up_brief_zh"
    )
    if snapshot_brief_rel_path != brief_rel_path:
        errors.append("completion snapshot owner_governance_follow_up_brief_zh source mismatch")

    brief_path = repo_root / brief_rel_path
    if not brief_path.exists():
        errors.append("owner/governance follow-up brief artifact is missing")
        return None

    brief = brief_path.read_text(encoding="utf-8")
    packet_rel_path = manifest.get("artifacts", {}).get("owner_governance_follow_up_packet", "")
    required_phrases = [
        packet_rel_path,
        "follow_up_packet_count=5",
        "open_blocker_count=5",
        "不批准指标、页面、治理记录或 route certification",
        "不授权 Ledger PnL `--write`",
        "不读取、不请求、不捕获 secret 值",
        "local stdio MCP evidence",
    ]
    for phrase in required_phrases:
        if phrase not in brief:
            errors.append(f"owner/governance follow-up brief missing required phrase: {phrase}")

    packet_blockers = {
        item.get("blocker_id"): item
        for item in (follow_up_packet or {}).get("blocker_packets", [])
    }
    covered_blocker_count = 0
    for blocker in manifest.get("open_blockers", []):
        blocker_id = blocker.get("id")
        if not blocker_id:
            continue
        if blocker_id not in brief:
            errors.append(f"owner/governance follow-up brief missing blocker {blocker_id}")
            continue
        covered_blocker_count += 1
        follow_up = packet_blockers.get(blocker_id, {})
        for path in follow_up.get("required_input_artifacts", []):
            if path not in brief:
                errors.append(
                    f"owner/governance follow-up brief missing input artifact {path}"
                )

    return covered_blocker_count


def _verify_calculation_p1_prework_map(
    *,
    manifest: dict[str, Any],
    repo_root: Path,
    errors: list[str],
) -> int | None:
    matrix_rel_path = manifest.get("artifacts", {}).get("calculation_owner_decision_matrix")
    if not matrix_rel_path:
        errors.append("manifest missing calculation_owner_decision_matrix artifact")
        return None

    matrix_path = repo_root / matrix_rel_path
    if not matrix_path.exists():
        errors.append("calculation owner decision matrix artifact is missing")
        return None

    matrix = matrix_path.read_text(encoding="utf-8")
    if "## Verified Closed Before Owner Review" not in matrix:
        errors.append("calculation decision matrix missing verified-closed section")
        return None

    open_decision_section, verified_closed_section = matrix.split(
        "## Verified Closed Before Owner Review",
        maxsplit=1,
    )
    open_decision_rows = [
        line
        for line in open_decision_section.splitlines()
        if line.startswith("| P1-")
    ]
    open_decision_ids = [line.split("|")[1].strip() for line in open_decision_rows]
    expected_count = manifest.get("counts", {}).get("calculation_display_open_p1")
    if len(open_decision_rows) != expected_count:
        errors.append(
            "calculation decision matrix open P1 row count does not match manifest"
        )
    if open_decision_ids != EXPECTED_OPEN_CALCULATION_P1_IDS:
        errors.append("calculation decision matrix open P1 IDs do not match expected order")
    if any(line.startswith("| P1-08 |") for line in open_decision_rows):
        errors.append("P1-08 must not appear as an open owner-decision row")
    if "P1-08" not in verified_closed_section:
        errors.append("P1-08 verified-closed evidence is missing")

    prework_marker = "## Engineering Prework / Impact Slice Map"
    if prework_marker not in verified_closed_section:
        errors.append("calculation decision matrix missing engineering prework map")
        return len(open_decision_rows)

    prework_section = verified_closed_section.split(prework_marker, maxsplit=1)[1]
    required_boundaries = [
        "does not choose or approve any convention",
        "does not change code",
        "does not certify routes/pages",
    ]
    for boundary in required_boundaries:
        if boundary not in prework_section:
            errors.append(f"calculation prework map missing boundary: {boundary}")
    if "| P1-" in prework_section:
        errors.append("calculation prework map must not add P1 table rows")
    for p1_id in EXPECTED_OPEN_CALCULATION_P1_IDS:
        if f"- **{p1_id} " not in prework_section:
            errors.append(f"calculation prework map missing {p1_id}")

    return len(open_decision_rows)


def _verify_calculation_p1_snapshot(
    *,
    manifest: dict[str, Any],
    repo_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    snapshot_rel_path = manifest.get("artifacts", {}).get(
        "calculation_owner_decision_snapshot"
    )
    if not snapshot_rel_path:
        errors.append("manifest missing calculation_owner_decision_snapshot artifact")
        return None

    snapshot_path = repo_root / snapshot_rel_path
    if not snapshot_path.exists():
        errors.append("calculation owner decision snapshot artifact is missing")
        return None

    snapshot = _load_json(snapshot_path)
    if snapshot.get("report_kind") != "calculation_p1_owner_decision_snapshot":
        errors.append("calculation owner decision snapshot report_kind is invalid")
    status = snapshot.get("status", {})
    expected_status = {
        "overall": "owner_decision_required",
        "fail_closed": True,
        "chooses_or_approves_conventions": False,
        "changes_code": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
    }
    for key, expected in expected_status.items():
        if status.get(key) != expected:
            errors.append(
                f"calculation owner decision snapshot status {key} must be {expected!r}"
            )
    if snapshot.get("drift_errors") != []:
        errors.append("calculation owner decision snapshot has drift_errors")

    matrix = snapshot.get("matrix", {})
    expected_count = manifest.get("counts", {}).get("calculation_display_open_p1")
    if matrix.get("open_decision_ids") != EXPECTED_OPEN_CALCULATION_P1_IDS:
        errors.append("calculation owner decision snapshot open IDs do not match expected")
    if matrix.get("open_decision_count") != expected_count:
        errors.append("calculation owner decision snapshot open count does not match manifest")
    if matrix.get("p1_08_in_open_rows") is not False:
        errors.append("calculation owner decision snapshot must keep P1-08 out of open rows")
    if matrix.get("p1_08_verified_closed") is not True:
        errors.append("calculation owner decision snapshot must keep P1-08 verified closed")

    prework = snapshot.get("engineering_prework_map", {})
    if prework.get("mapped_ids") != EXPECTED_OPEN_CALCULATION_P1_IDS:
        errors.append("calculation owner decision snapshot prework IDs do not match expected")
    if not all((prework.get("boundary_checks") or {}).values()):
        errors.append("calculation owner decision snapshot boundary checks must all pass")

    capture = snapshot.get("capture_template", {})
    if capture.get("row_ids") != EXPECTED_OPEN_CALCULATION_P1_IDS:
        errors.append("calculation owner decision snapshot capture IDs do not match expected")
    if capture.get("pending_count") != expected_count:
        errors.append("calculation owner decision snapshot pending count does not match manifest")
    if capture.get("captured_decision_count") != 0:
        errors.append("calculation owner decision snapshot must not capture owner decisions")
    if capture.get("incomplete_decision_count") != expected_count:
        errors.append(
            "calculation owner decision snapshot incomplete decision count does not match manifest"
        )
    if capture.get("incomplete_decision_ids") != EXPECTED_OPEN_CALCULATION_P1_IDS:
        errors.append(
            "calculation owner decision snapshot incomplete decision IDs do not match expected"
        )
    if "does not choose or approve any calculation convention" not in snapshot.get(
        "boundary",
        "",
    ):
        errors.append("calculation owner decision snapshot missing non-approval boundary")

    return snapshot


def verify_completion_snapshot(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    snapshot_path = repo_root / manifest["artifacts"]["completion_snapshot"]
    snapshot = _load_json(snapshot_path)
    errors: list[str] = []

    _verify_monitoring_snapshot(
        manifest=manifest,
        repo_root=repo_root,
        errors=errors,
    )
    if snapshot.get("generated_at") != manifest.get("generated_at"):
        errors.append("completion snapshot generated_at does not match manifest")

    _verify_source_artifact_link(
        manifest=manifest,
        source_artifacts=snapshot.get("source_artifacts", {}),
        key="system_audit_monitoring_snapshot",
        owner="completion snapshot",
        errors=errors,
    )

    open_blockers = manifest.get("open_blockers", [])
    gates = snapshot.get("completion_gates", [])
    blockers_by_id = {item.get("id"): item for item in open_blockers}
    gates_by_id = {item.get("blocker_id"): item for item in gates}

    if set(blockers_by_id) != set(gates_by_id):
        errors.append("completion gate IDs do not match manifest open_blockers")

    status = snapshot.get("status", {})
    required_false_flags = [
        "approves_metrics",
        "approves_pages",
        "captures_business_owner_approval",
        "writes_governance_records",
        "certifies_routes",
        "clears_secret_scan",
        "captures_direct_app_mcp_gitnexus_evidence",
    ]
    if status.get("overall") != "not_complete":
        errors.append("completion snapshot overall status must be not_complete")
    if status.get("fail_closed") is not True:
        errors.append("completion snapshot must stay fail_closed")
    for flag in required_false_flags:
        if status.get(flag) is not False:
            errors.append(f"completion snapshot flag {flag} must be false")

    summary = snapshot.get("summary", {})
    expected_summary = {
        "open_blocker_count": len(open_blockers),
        "completed_blocker_count": 0,
        "required_completion_gate_count": len(gates),
        "business_contract_certified_routes": manifest["counts"][
            "business_contract_certified_routes"
        ],
        "owner_approval_pending_pages": manifest["counts"]["owner_approval_pending_pages"],
        "calculation_display_open_p1": manifest["counts"]["calculation_display_open_p1"],
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            errors.append(f"summary {key} expected {expected!r}, got {summary.get(key)!r}")

    for blocker_id, blocker in blockers_by_id.items():
        gate = gates_by_id.get(blocker_id)
        if gate is None:
            continue
        if gate.get("status") != "not_complete":
            errors.append(f"{blocker_id} gate status must be not_complete")
        if gate.get("last_checked_at") != blocker.get("last_checked_at"):
            errors.append(f"{blocker_id} last_checked_at does not match manifest")
        if not gate.get("required_evidence"):
            errors.append(f"{blocker_id} missing required_evidence")
        if not gate.get("current_contradicting_evidence"):
            errors.append(f"{blocker_id} missing current_contradicting_evidence")
        if not gate.get("fail_closed_until"):
            errors.append(f"{blocker_id} missing fail_closed_until")

    follow_up_packet = _verify_follow_up_packet(
        manifest=manifest,
        snapshot=snapshot,
        repo_root=repo_root,
        errors=errors,
    )
    follow_up_brief_blocker_count = _verify_follow_up_brief(
        manifest=manifest,
        snapshot=snapshot,
        follow_up_packet=follow_up_packet,
        repo_root=repo_root,
        errors=errors,
    )
    calculation_prework_p1_count = _verify_calculation_p1_prework_map(
        manifest=manifest,
        repo_root=repo_root,
        errors=errors,
    )
    calculation_snapshot = _verify_calculation_p1_snapshot(
        manifest=manifest,
        repo_root=repo_root,
        errors=errors,
    )

    return {
        "report_kind": "system_audit_completion_snapshot_verification",
        "status": "pass" if not errors else "fail",
        "manifest_path": str(manifest_path),
        "snapshot_path": str(snapshot_path),
        "open_blocker_count": len(open_blockers),
        "completion_gate_count": len(gates),
        "follow_up_packet_count": (
            follow_up_packet.get("blocker_packet_count") if follow_up_packet else None
        ),
        "follow_up_brief_blocker_count": follow_up_brief_blocker_count,
        "calculation_prework_p1_count": calculation_prework_p1_count,
        "calculation_snapshot_status": (
            (calculation_snapshot or {}).get("status", {}).get("overall")
            if calculation_snapshot
            else None
        ),
        "calculation_incomplete_decision_count": (
            (calculation_snapshot or {}).get("capture_template", {}).get(
                "incomplete_decision_count"
            )
            if calculation_snapshot
            else None
        ),
        "follow_up_completion_order_status": (
            "fail"
            if any(
                error.startswith(FOLLOW_UP_COMPLETION_ORDER_ERROR_PREFIX)
                for error in errors
            )
            else "pass"
        ),
        "follow_up_completion_order_error_count": sum(
            1
            for error in errors
            if error.startswith(FOLLOW_UP_COMPLETION_ORDER_ERROR_PREFIX)
        ),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the 2026-06-10 system audit completion snapshot against the manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the system audit manifest.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help=(
            "Exit non-zero unless the completion verifier passes with zero open blockers. "
            "Use this as the strict completion gate; the default verifies package consistency."
        ),
    )
    args = parser.parse_args(argv)

    result = verify_completion_snapshot(manifest_path=args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "pass":
        return 1
    if args.require_complete and result["open_blocker_count"] != 0:
        print(
            (
                "System audit completion is not complete: "
                f"open_blocker_count={result['open_blocker_count']}, "
                f"completion_gate_count={result['completion_gate_count']}, "
                f"calculation_snapshot_status={result['calculation_snapshot_status']}"
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
