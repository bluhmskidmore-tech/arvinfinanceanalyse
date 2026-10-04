"""Read-only preflight for the fixed-income controlled pilot handoff packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_PATH = Path("docs/runbooks/release-control-plane-fixed-income-pilot.md")

REQUIRED_OWNER_ROLES = (
    "business_owner",
    "fixed_income_rule_owner",
    "data_owner",
    "release_owner",
    "platform_dba_owner",
    "scheduler_owner",
    "worker_owner",
    "frontend_owner",
    "independent_reviewer",
    "approval_authority_owner",
    "backup_operator",
    "rollback_operator",
)
REQUIRED_APPROVAL_STATES = (
    "evidence_captured",
    "machine_validated",
    "business_approved",
    "formal_use_allowed",
    "closure_approved",
)
REQUIRED_WRITER_STOP_PROOFS = (
    "keepalive",
    "scheduler",
    "supervisor",
    "queue",
    "worker",
    "api",
    "connections",
    "wal",
)
REQUIRED_PATH_FIELDS = (
    "target_environment_root",
    "current_bundle",
    "previous_bundle",
    "candidate_bundle",
    "rollback_bundle_dir",
    "governance_ledger_dir",
    "backup_dir",
    "receipt_dir",
    "log_dir",
    "backend_build_artifact",
    "frontend_build_artifact",
)
EXPECTED_WRITER_STOP_STATUS = {
    "keepalive": "paused",
    "scheduler": "disabled",
    "supervisor": "stopped",
    "queue": "drained",
    "worker": "stopped",
    "api": "quiesced",
    "connections": "no_active_writers",
    "wal": "stopped",
}
REQUIRED_BACKUP_FIELDS = (
    "current_bundle",
    "governance_ledger",
    "deployment_config",
    "alias_view",
    "candidate_receipt",
    "rollback_plan",
)
REQUIRED_BUILD_FIELDS = (
    "backend",
    "frontend",
    "release_validation",
)
SEALED_BUNDLE_REACTIVATE = "sealed_bundle_reactivate"
FORWARD_REBUILD = "forward_rebuild"
ROLLBACK_MODES = (SEALED_BUNDLE_REACTIVATE, FORWARD_REBUILD)
MAX_PACKET_BYTES = 1024 * 1024

PLACEHOLDER_EXACT = {
    "",
    "PENDING",
    "TODO",
    "TBD",
    "UNKNOWN",
    "REQUIRED",
    "REDACTED",
    "N/A",
    "NA",
    "NULL",
    "NONE",
}
PLACEHOLDER_SUBSTRINGS = (
    "<",
    ">",
    "{fill",
    "placeholder",
)

OUTPUT_SCOPE = {
    "reads_structured_handoff_packet": True,
    "writes_safe_output_only": True,
    "connects_to_production": False,
    "production_writes": False,
    "authorizes_pilot": False,
    "release_eligible": False,
}

NEXT_ACTIONS = {
    "pilot_identity_complete": {
        "field": "release_id/target_environment/physical_bundle_scope/runbook_reference",
        "action": "补齐 release_id，把 target_environment 填成非占位环境名，把 physical_bundle_scope 固定为 `duckdb-main`，并绑定当前试点 runbook。",
    },
    "packet_sections_complete": {
        "field": "packet",
        "action": "补齐缺失顶层区块并保持为结构化 JSON，不要改写成 Markdown 摘要。",
    },
    "owner_roster_complete": {
        "field": "owners",
        "action": "为每个 owner 角色补齐 `name` 和 `reference`，不得保留 `PENDING` 或占位符。",
    },
    "topology_complete": {
        "field": "topology",
        "action": "补齐单实例 whole-bundle 窗口拓扑说明与工单引用。",
    },
    "maintenance_window_complete": {
        "field": "windows.maintenance",
        "action": "补齐维护窗口开始、结束、时区和引用。",
    },
    "observation_window_complete": {
        "field": "windows.observation",
        "action": "补齐观察窗口时长、成功标准和引用。",
    },
    "recovery_objectives_complete": {
        "field": "recovery_objectives",
        "action": "补齐 RTO、RPO 和对应证据引用。",
    },
    "governed_paths_complete": {
        "field": "paths",
        "action": "把 candidate/current/previous 等路径填成绝对、规范化、无占位符的 Windows 路径。",
    },
    "writer_stop_proofs_complete": {
        "field": "writer_stop_proofs",
        "action": "逐项补齐停写状态、摘要和引用，直到所有写入口都可留档证明已停。",
    },
    "backup_evidence_complete": {
        "field": "backups",
        "action": "为备份对象补齐 SHA-256 和引用，确保恢复点与当前点都可勾稽。",
    },
    "approval_authority_complete": {
        "field": "approvals.authority",
        "action": "补齐审批权威载体的引用和摘要绑定。",
    },
    "five_state_approvals_complete": {
        "field": "approvals.states",
        "action": "逐个补齐五态审批的布尔状态、引用、摘要和简要说明。",
    },
    "build_receipts_complete": {
        "field": "build_receipts",
        "action": "补齐后端、前端和 release validation 的回执引用与摘要。",
    },
    "platform_evidence_complete": {
        "field": "platform_evidence",
        "action": "补齐 GitHub 平台设置和 formal authority 证据的引用与摘要。",
    },
    "rollback_mode_supported": {
        "field": "rollback_plan.rollback_mode",
        "action": "把 rollback_mode 固定为 `sealed_bundle_reactivate` 或 `forward_rebuild` 之一。",
    },
    "rollback_branch_complete": {
        "field": "rollback_plan",
        "action": "按所选回滚模式补齐对应分支字段，不要把两类路径混写。",
    },
}


@dataclass(frozen=True)
class GateResult:
    name: str
    outcome: str
    reason_code: str | None
    detail: str
    fields: tuple[str, ...] = ()


class InvalidPacketError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


def default_handoff_packet() -> dict[str, Any]:
    return {
        "release_id": "PENDING",
        "target_environment": "PENDING",
        "physical_bundle_scope": "duckdb-main",
        "runbook_reference": RUNBOOK_PATH.as_posix(),
        "owners": {
            role: {"name": "PENDING", "reference": "PENDING"}
            for role in REQUIRED_OWNER_ROLES
        },
        "topology": {
            "topology_kind": "PENDING",
            "whole_bundle_window": "PENDING",
            "reference": "PENDING",
        },
        "windows": {
            "maintenance": {
                "start": "PENDING",
                "end": "PENDING",
                "timezone": "PENDING",
                "reference": "PENDING",
            },
            "observation": {
                "duration_minutes": "PENDING",
                "success_criteria": "PENDING",
                "reference": "PENDING",
            },
        },
        "recovery_objectives": {
            "rto": "PENDING",
            "rpo": "PENDING",
            "reference": "PENDING",
        },
        "paths": {field: "PENDING" for field in REQUIRED_PATH_FIELDS},
        "writer_stop_proofs": {
            key: {"status": "PENDING", "summary": "PENDING", "reference": "PENDING"}
            for key in REQUIRED_WRITER_STOP_PROOFS
        },
        "backups": {
            key: {"sha256": "PENDING", "reference": "PENDING"}
            for key in REQUIRED_BACKUP_FIELDS
        },
        "approvals": {
            "required_states": list(REQUIRED_APPROVAL_STATES),
            "authority": {"reference": "PENDING", "digest": "PENDING"},
            "states": {
                key: {
                    "status": "PENDING",
                    "reference": "PENDING",
                    "digest": "PENDING",
                    "summary": "PENDING",
                }
                for key in REQUIRED_APPROVAL_STATES
            },
        },
        "build_receipts": {
            key: {"reference": "PENDING", "digest": "PENDING"}
            for key in REQUIRED_BUILD_FIELDS
        },
        "platform_evidence": {
            "github": {"reference": "PENDING", "digest": "PENDING"},
            "formal_authority": {"reference": "PENDING", "digest": "PENDING"},
        },
        "rollback_plan": {
            "rollback_mode": "PENDING",
            "reason_reference": "PENDING",
            "sealed_bundle_reactivate": {
                "same_maintenance_window": "PENDING",
                "writer_still_stopped": "PENDING",
                "other_domain_writes_present": "PENDING",
                "previous_bundle_reference": "PENDING",
                "previous_bundle_sha256": "PENDING",
            },
            "forward_rebuild": {
                "latest_base_bundle_reference": "PENDING",
                "latest_base_bundle_sha256": "PENDING",
                "rollback_candidate_reference": "PENDING",
                "rollback_candidate_sha256": "PENDING",
                "revalidation_reference": "PENDING",
                "reapproval_reference": "PENDING",
            },
        },
    }


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _validated_generated_at(value: str | None) -> str:
    if value is None:
        return _default_generated_at()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidPacketError(
            "generated_at_invalid",
            "generated_at must be an ISO timestamp with timezone.",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidPacketError(
            "generated_at_invalid",
            "generated_at must be an ISO timestamp with timezone.",
        )
    return parsed.isoformat(timespec="seconds")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_placeholder(value: Any) -> bool:
    text = _clean_text(value)
    if not text:
        return True
    upper = text.upper()
    if upper in PLACEHOLDER_EXACT:
        return True
    if any(fragment in text.lower() for fragment in PLACEHOLDER_SUBSTRINGS):
        return True
    return "PENDING" in upper


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9A-Fa-f]{64}", _clean_text(value)))


def _validate_absolute_normalized_windows_path(value: Any) -> str | None:
    text = _clean_text(value)
    if _is_placeholder(text):
        return "pending"
    if any(token in text for token in ("~", "%", "$")):
        return "contains_shell_placeholder"
    path = PureWindowsPath(text)
    if not path.is_absolute():
        return "not_absolute"
    if "." in path.parts or ".." in path.parts:
        return "not_normalized"
    if str(path) != text:
        return "not_normalized"
    return None


def _gate(
    name: str,
    *,
    blocked_fields: list[str],
    reason_code: str | None,
    detail: str,
) -> GateResult:
    return GateResult(
        name=name,
        outcome="blocked" if blocked_fields else "pass",
        reason_code=reason_code if blocked_fields else None,
        detail=detail,
        fields=tuple(blocked_fields),
    )


def _required_section_gate(packet: Mapping[str, Any]) -> GateResult:
    required = (
        "owners",
        "topology",
        "windows",
        "recovery_objectives",
        "paths",
        "writer_stop_proofs",
        "backups",
        "approvals",
        "build_receipts",
        "platform_evidence",
        "rollback_plan",
    )
    missing = [name for name in required if not isinstance(packet.get(name), Mapping)]
    return _gate(
        "packet_sections_complete",
        blocked_fields=missing,
        reason_code="packet_missing_required_sections",
        detail="All required structured sections are present."
        if not missing
        else "Missing structured sections.",
    )


def _identity_gate(packet: Mapping[str, Any]) -> GateResult:
    blocked: list[str] = []
    if _is_placeholder(packet.get("release_id")):
        blocked.append("release_id")
    if _is_placeholder(packet.get("target_environment")):
        blocked.append("target_environment")
    if _clean_text(packet.get("physical_bundle_scope")) != "duckdb-main":
        blocked.append("physical_bundle_scope")
    if _clean_text(packet.get("runbook_reference")) != RUNBOOK_PATH.as_posix():
        blocked.append("runbook_reference")
    return _gate(
        "pilot_identity_complete",
        blocked_fields=blocked,
        reason_code="pilot_identity_pending",
        detail=(
            "release_id, target_environment, physical_bundle_scope, and runbook_reference are bound to the fixed-income pilot."
            if not blocked
            else "Pilot identity fields are pending or inconsistent."
        ),
    )


def _owner_gate(packet: Mapping[str, Any]) -> GateResult:
    owners = _as_mapping(packet.get("owners"))
    missing: list[str] = []
    for role in REQUIRED_OWNER_ROLES:
        item = _as_mapping(owners.get(role))
        if _is_placeholder(item.get("name")) or _is_placeholder(item.get("reference")):
            missing.append(role)
    return _gate(
        "owner_roster_complete",
        blocked_fields=missing,
        reason_code="owner_roster_pending",
        detail="Every required owner role has a non-placeholder name and reference."
        if not missing
        else "Owner roster still has pending roles.",
    )


def _simple_mapping_gate(
    packet: Mapping[str, Any],
    *,
    gate_name: str,
    reason_code: str,
    section: str,
    required_fields: tuple[str, ...],
) -> GateResult:
    mapping = _as_mapping(packet.get(section))
    missing = [
        f"{section}.{field}"
        for field in required_fields
        if _is_placeholder(mapping.get(field))
    ]
    return _gate(
        gate_name,
        blocked_fields=missing,
        reason_code=reason_code,
        detail=f"{section} is fully populated."
        if not missing
        else f"{section} still has pending fields.",
    )


def _topology_gate(packet: Mapping[str, Any]) -> GateResult:
    topology = _as_mapping(packet.get("topology"))
    blocked: list[str] = []
    if (
        _clean_text(topology.get("topology_kind"))
        != "single_instance_whole_bundle_window"
    ):
        blocked.append("topology.topology_kind")
    if _as_bool(topology.get("whole_bundle_window")) is not True:
        blocked.append("topology.whole_bundle_window")
    if _is_placeholder(topology.get("reference")):
        blocked.append("topology.reference")
    return _gate(
        "topology_complete",
        blocked_fields=blocked,
        reason_code="topology_pending",
        detail=(
            "Topology is frozen as a single-instance whole-bundle window."
            if not blocked
            else "Topology is pending or does not match the allowed pilot shape."
        ),
    )


def _nested_mapping_gate(
    packet: Mapping[str, Any],
    *,
    gate_name: str,
    reason_code: str,
    section: str,
    subsection: str,
    required_fields: tuple[str, ...],
) -> GateResult:
    mapping = _as_mapping(_as_mapping(packet.get(section)).get(subsection))
    prefix = f"{section}.{subsection}"
    missing = [
        f"{prefix}.{field}"
        for field in required_fields
        if _is_placeholder(mapping.get(field))
    ]
    return _gate(
        gate_name,
        blocked_fields=missing,
        reason_code=reason_code,
        detail=f"{prefix} is fully populated."
        if not missing
        else f"{prefix} still has pending fields.",
    )


def _maintenance_window_gate(packet: Mapping[str, Any]) -> GateResult:
    window = _as_mapping(_as_mapping(packet.get("windows")).get("maintenance"))
    blocked: list[str] = []
    start_raw = window.get("start")
    end_raw = window.get("end")
    timezone = window.get("timezone")
    reference = window.get("reference")
    if _is_placeholder(start_raw):
        blocked.append("windows.maintenance.start")
    if _is_placeholder(end_raw):
        blocked.append("windows.maintenance.end")
    if _is_placeholder(timezone):
        blocked.append("windows.maintenance.timezone")
    if _is_placeholder(reference):
        blocked.append("windows.maintenance.reference")
    if not blocked:
        try:
            zone = ZoneInfo(_clean_text(timezone))
        except ZoneInfoNotFoundError:
            blocked.append("windows.maintenance.timezone:invalid_iana")
            zone = None
        try:
            start = datetime.fromisoformat(_clean_text(start_raw))
        except ValueError:
            blocked.append("windows.maintenance.start:invalid_iso")
            start = None
        try:
            end = datetime.fromisoformat(_clean_text(end_raw))
        except ValueError:
            blocked.append("windows.maintenance.end:invalid_iso")
            end = None
        if start is not None and (start.tzinfo is None or start.utcoffset() is None):
            blocked.append("windows.maintenance.start:timezone_required")
        if end is not None and (end.tzinfo is None or end.utcoffset() is None):
            blocked.append("windows.maintenance.end:timezone_required")
        if (
            start is not None
            and end is not None
            and start.tzinfo is not None
            and start.utcoffset() is not None
            and end.tzinfo is not None
            and end.utcoffset() is not None
            and end <= start
        ):
            blocked.append("windows.maintenance.order")
        if zone is not None and start is not None and start.utcoffset() is not None:
            if start.astimezone(zone).utcoffset() != start.utcoffset():
                blocked.append("windows.maintenance.start:timezone_mismatch")
        if zone is not None and end is not None and end.utcoffset() is not None:
            if end.astimezone(zone).utcoffset() != end.utcoffset():
                blocked.append("windows.maintenance.end:timezone_mismatch")
    return _gate(
        "maintenance_window_complete",
        blocked_fields=blocked,
        reason_code="maintenance_window_pending",
        detail=(
            "Maintenance window is fully populated and chronologically valid."
            if not blocked
            else "Maintenance window is still incomplete or invalid."
        ),
    )


def _observation_window_gate(packet: Mapping[str, Any]) -> GateResult:
    window = _as_mapping(_as_mapping(packet.get("windows")).get("observation"))
    blocked: list[str] = []
    duration = window.get("duration_minutes")
    if _is_placeholder(duration):
        blocked.append("windows.observation.duration_minutes")
    else:
        try:
            if int(str(duration)) <= 0:
                blocked.append("windows.observation.duration_minutes")
        except (TypeError, ValueError):
            blocked.append("windows.observation.duration_minutes")
    for field in ("success_criteria", "reference"):
        if _is_placeholder(window.get(field)):
            blocked.append(f"windows.observation.{field}")
    return _gate(
        "observation_window_complete",
        blocked_fields=blocked,
        reason_code="observation_window_pending",
        detail=(
            "Observation window is fully populated and has a positive duration."
            if not blocked
            else "Observation window is still incomplete or invalid."
        ),
    )


def _paths_gate(packet: Mapping[str, Any]) -> GateResult:
    paths = _as_mapping(packet.get("paths"))
    blocked: list[str] = []
    for field in REQUIRED_PATH_FIELDS:
        reason = _validate_absolute_normalized_windows_path(paths.get(field))
        if reason is not None:
            blocked.append(f"paths.{field}:{reason}")
    distinct_values = {
        name: _clean_text(paths.get(name)).casefold()
        for name in ("current_bundle", "previous_bundle", "candidate_bundle")
    }
    if len(set(distinct_values.values())) != len(distinct_values):
        blocked.append("paths.bundle_identity:not_distinct")
    return _gate(
        "governed_paths_complete",
        blocked_fields=blocked,
        reason_code="governed_paths_invalid",
        detail="All governed paths are absolute, normalized, and non-placeholder."
        if not blocked
        else "Some governed paths are pending or invalid.",
    )


def _writer_stop_gate(packet: Mapping[str, Any]) -> GateResult:
    proofs = _as_mapping(packet.get("writer_stop_proofs"))
    blocked: list[str] = []
    for key in REQUIRED_WRITER_STOP_PROOFS:
        item = _as_mapping(proofs.get(key))
        status = _clean_text(item.get("status")).lower()
        if (
            status != EXPECTED_WRITER_STOP_STATUS[key]
            or _is_placeholder(item.get("summary"))
            or _is_placeholder(item.get("reference"))
        ):
            blocked.append(f"{key}:{status or 'missing'}")
    return _gate(
        "writer_stop_proofs_complete",
        blocked_fields=blocked,
        reason_code="writer_stop_proofs_pending",
        detail="Every write entrypoint has a stop-state, summary, and reference."
        if not blocked
        else "Writer-stop evidence is still incomplete.",
    )


def _backup_gate(packet: Mapping[str, Any]) -> GateResult:
    backups = _as_mapping(packet.get("backups"))
    blocked: list[str] = []
    for field in REQUIRED_BACKUP_FIELDS:
        item = _as_mapping(backups.get(field))
        if not _is_sha256(item.get("sha256")) or _is_placeholder(item.get("reference")):
            blocked.append(field)
    return _gate(
        "backup_evidence_complete",
        blocked_fields=blocked,
        reason_code="backup_evidence_pending",
        detail="All backup objects have SHA-256 and a bound reference."
        if not blocked
        else "Backup evidence is still incomplete.",
    )


def _approval_authority_gate(packet: Mapping[str, Any]) -> GateResult:
    authority = _as_mapping(_as_mapping(packet.get("approvals")).get("authority"))
    blocked = []
    if _is_placeholder(authority.get("reference")):
        blocked.append("approvals.authority.reference")
    if not _is_sha256(authority.get("digest")):
        blocked.append("approvals.authority.digest")
    return _gate(
        "approval_authority_complete",
        blocked_fields=blocked,
        reason_code="approval_authority_pending",
        detail="Approval authority reference and digest are both present."
        if not blocked
        else "Approval authority evidence is still incomplete.",
    )


def _approval_states_gate(packet: Mapping[str, Any]) -> GateResult:
    approvals = _as_mapping(packet.get("approvals"))
    states = _as_mapping(approvals.get("states"))
    required_states = approvals.get("required_states")
    blocked: list[str] = []
    if required_states != list(REQUIRED_APPROVAL_STATES):
        blocked.append("approvals.required_states")
    for state_name in REQUIRED_APPROVAL_STATES:
        item = _as_mapping(states.get(state_name))
        status = _as_bool(item.get("status"))
        if status is not True:
            blocked.append(f"approvals.states.{state_name}.status")
        if _is_placeholder(item.get("reference")):
            blocked.append(f"approvals.states.{state_name}.reference")
        if not _is_sha256(item.get("digest")):
            blocked.append(f"approvals.states.{state_name}.digest")
        if _is_placeholder(item.get("summary")):
            blocked.append(f"approvals.states.{state_name}.summary")
    return _gate(
        "five_state_approvals_complete",
        blocked_fields=blocked,
        reason_code="five_state_approvals_pending",
        detail="Five-state approvals are complete and explicitly true."
        if not blocked
        else "Five-state approvals are still incomplete or false.",
    )


def _build_receipts_gate(packet: Mapping[str, Any]) -> GateResult:
    receipts = _as_mapping(packet.get("build_receipts"))
    blocked: list[str] = []
    for key in REQUIRED_BUILD_FIELDS:
        item = _as_mapping(receipts.get(key))
        if _is_placeholder(item.get("reference")) or not _is_sha256(item.get("digest")):
            blocked.append(key)
    return _gate(
        "build_receipts_complete",
        blocked_fields=blocked,
        reason_code="build_receipts_pending",
        detail="Build and validation receipts are complete."
        if not blocked
        else "Build and validation receipts are still incomplete.",
    )


def _platform_evidence_gate(packet: Mapping[str, Any]) -> GateResult:
    evidence = _as_mapping(packet.get("platform_evidence"))
    blocked: list[str] = []
    for key in ("github", "formal_authority"):
        item = _as_mapping(evidence.get(key))
        if _is_placeholder(item.get("reference")) or not _is_sha256(item.get("digest")):
            blocked.append(key)
    return _gate(
        "platform_evidence_complete",
        blocked_fields=blocked,
        reason_code="platform_evidence_pending",
        detail="GitHub and formal authority evidence are complete."
        if not blocked
        else "Platform or authority evidence is still incomplete.",
    )


def _rollback_mode_gate(packet: Mapping[str, Any]) -> GateResult:
    rollback_plan = _as_mapping(packet.get("rollback_plan"))
    mode = _clean_text(rollback_plan.get("rollback_mode"))
    blocked = []
    if mode not in ROLLBACK_MODES:
        blocked.append("rollback_plan.rollback_mode")
    if _is_placeholder(rollback_plan.get("reason_reference")):
        blocked.append("rollback_plan.reason_reference")
    return _gate(
        "rollback_mode_supported",
        blocked_fields=blocked,
        reason_code="rollback_mode_invalid",
        detail="Rollback mode is one of the supported controlled paths."
        if not blocked
        else "Rollback mode is still pending or unsupported.",
    )


def _rollback_branch_gate(packet: Mapping[str, Any]) -> GateResult:
    rollback_plan = _as_mapping(packet.get("rollback_plan"))
    mode = _clean_text(rollback_plan.get("rollback_mode"))
    blocked: list[str] = []
    if mode == SEALED_BUNDLE_REACTIVATE:
        branch = _as_mapping(rollback_plan.get(mode))
        expected_true = ("same_maintenance_window", "writer_still_stopped")
        expected_false = ("other_domain_writes_present",)
        for field in expected_true:
            if _as_bool(branch.get(field)) is not True:
                blocked.append(f"rollback_plan.{mode}.{field}")
        for field in expected_false:
            if _as_bool(branch.get(field)) is not False:
                blocked.append(f"rollback_plan.{mode}.{field}")
        if _is_placeholder(branch.get("previous_bundle_reference")):
            blocked.append(f"rollback_plan.{mode}.previous_bundle_reference")
        if not _is_sha256(branch.get("previous_bundle_sha256")):
            blocked.append(f"rollback_plan.{mode}.previous_bundle_sha256")
    elif mode == FORWARD_REBUILD:
        branch = _as_mapping(rollback_plan.get(mode))
        for field in (
            "latest_base_bundle_reference",
            "rollback_candidate_reference",
            "revalidation_reference",
            "reapproval_reference",
        ):
            if _is_placeholder(branch.get(field)):
                blocked.append(f"rollback_plan.{mode}.{field}")
        for field in ("latest_base_bundle_sha256", "rollback_candidate_sha256"):
            if not _is_sha256(branch.get(field)):
                blocked.append(f"rollback_plan.{mode}.{field}")
    else:
        blocked.append("rollback_plan.rollback_mode")
    return _gate(
        "rollback_branch_complete",
        blocked_fields=blocked,
        reason_code="rollback_branch_pending",
        detail="The selected rollback branch is fully populated."
        if not blocked
        else "The selected rollback branch is still incomplete.",
    )


def build_fixed_income_pilot_preflight_report(
    *,
    packet: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    packet_source: str = "default_pending_template",
) -> dict[str, Any]:
    payload = dict(default_handoff_packet() if packet is None else packet)
    emitted_at = _validated_generated_at(generated_at)
    gates = [
        _required_section_gate(payload),
        _identity_gate(payload),
        _owner_gate(payload),
        _topology_gate(payload),
        _maintenance_window_gate(payload),
        _observation_window_gate(payload),
        _simple_mapping_gate(
            payload,
            gate_name="recovery_objectives_complete",
            reason_code="recovery_objectives_pending",
            section="recovery_objectives",
            required_fields=("rto", "rpo", "reference"),
        ),
        _paths_gate(payload),
        _writer_stop_gate(payload),
        _backup_gate(payload),
        _approval_authority_gate(payload),
        _approval_states_gate(payload),
        _build_receipts_gate(payload),
        _platform_evidence_gate(payload),
        _rollback_mode_gate(payload),
        _rollback_branch_gate(payload),
    ]

    blocked = [gate for gate in gates if gate.outcome == "blocked"]
    status = "blocked" if blocked else "awaiting_owner_execution"
    blocker_codes = [gate.reason_code for gate in blocked if gate.reason_code]
    next_actions = [
        {"gate": gate.name, **NEXT_ACTIONS[gate.name]}
        for gate in blocked
        if gate.name in NEXT_ACTIONS
    ]
    return {
        "report_kind": "wp7_fixed_income_pilot_preflight",
        "schema_version": "1.0",
        "generated_at": emitted_at,
        "status": status,
        "go_no_go": "no_go" if blocked else "pending_owner_execution",
        "release_eligible": False,
        "authorizes_pilot": False,
        "production_writes": False,
        "packet_observation": {
            "source_kind": "structured_handoff_packet",
            "packet_source": packet_source,
            "packet_sha256": canonical_sha256(payload),
            "all_gates_passed": not blocked,
            "blocked_gate_count": len(blocked),
        },
        "evidence_scope": dict(OUTPUT_SCOPE),
        "blocker_reason_codes": blocker_codes,
        "gates": [asdict(gate) for gate in gates],
        "next_actions": next_actions,
        "boundary": (
            "This preflight is structure-only. It never connects to production, never "
            "writes production state, never authorizes a pilot, and never upgrades "
            "formal approval by itself."
        ),
    }


def build_invalid_preflight_report(
    *,
    reason_code: str,
    generated_at: str | None = None,
    packet_source: str,
) -> dict[str, Any]:
    return {
        "report_kind": "wp7_fixed_income_pilot_preflight",
        "schema_version": "1.0",
        "generated_at": _default_generated_at()
        if generated_at is None
        else generated_at,
        "status": "invalid",
        "go_no_go": "no_go",
        "release_eligible": False,
        "authorizes_pilot": False,
        "production_writes": False,
        "packet_observation": {
            "source_kind": "structured_handoff_packet",
            "packet_source": packet_source,
            "packet_sha256": None,
            "all_gates_passed": False,
            "blocked_gate_count": 1,
        },
        "evidence_scope": dict(OUTPUT_SCOPE),
        "blocker_reason_codes": [reason_code],
        "gates": [
            asdict(
                GateResult(
                    name="input_packet_valid",
                    outcome="invalid",
                    reason_code=reason_code,
                    detail="The structured handoff packet could not be accepted.",
                    fields=(),
                )
            )
        ],
        "next_actions": [],
        "boundary": (
            "This preflight is structure-only. It never connects to production, never "
            "writes production state, never authorizes a pilot, and never upgrades "
            "formal approval by itself."
        ),
    }


def _assert_no_symlink_junction_or_reparse(path: Path, *, field_name: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        metadata = current.stat(follow_symlinks=False)
        is_junction = getattr(current, "is_junction", lambda: False)
        file_attributes = int(getattr(metadata, "st_file_attributes", 0))
        if (
            current.is_symlink()
            or is_junction()
            or bool(file_attributes & reparse_mask)
        ):
            raise ValueError(f"{field_name}_contains_symlink_junction_or_reparse")


def _safe_output_path(output: Path, *, repo_root: Path = ROOT) -> Path:
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("output must be a .json file")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError("output parent must already exist")

    repo = Path(repo_root).resolve()
    for name in ("output", ".tmp"):
        candidate = repo / name
        if candidate.exists():
            _assert_no_symlink_junction_or_reparse(candidate, field_name=name)
    _assert_no_symlink_junction_or_reparse(output.parent, field_name="output_parent")
    _assert_no_symlink_junction_or_reparse(output, field_name="output_file")

    resolved = output.resolve(strict=False)
    allowed = [
        (repo / name).resolve(strict=False)
        for name in ("output", ".tmp")
        if (repo / name).resolve(strict=False).is_relative_to(repo)
    ]
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise ValueError("output must resolve inside repository output/ or .tmp/")
    return resolved


def write_report_exclusive(
    *,
    output: Path,
    report: Mapping[str, Any],
    repo_root: Path = ROOT,
) -> Path:
    resolved = _safe_output_path(output, repo_root=repo_root)
    with resolved.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(report), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return resolved


def load_handoff_packet(packet_path: Path) -> Mapping[str, Any]:
    path = Path(packet_path)
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_PACKET_BYTES + 1)
    except OSError as exc:
        raise InvalidPacketError(
            "packet_unavailable",
            "The structured handoff packet is unavailable.",
        ) from exc
    if len(raw) > MAX_PACKET_BYTES:
        raise InvalidPacketError(
            "packet_too_large",
            "The structured handoff packet exceeds the 1 MiB limit.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidPacketError(
            "packet_not_utf8",
            "The structured handoff packet is not valid UTF-8.",
        ) from exc

    def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise InvalidPacketError(
                    "packet_duplicate_keys",
                    "The structured handoff packet contains duplicate JSON keys.",
                )
            result[key] = value
        return result

    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except InvalidPacketError:
        raise
    except json.JSONDecodeError as exc:
        raise InvalidPacketError(
            "packet_invalid_json",
            "The structured handoff packet is not valid JSON.",
        ) from exc
    if not isinstance(payload, Mapping):
        raise InvalidPacketError(
            "packet_not_object",
            "The structured handoff packet must be a JSON object.",
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    exit_codes = {
        "invalid": 1,
        "blocked": 2,
        "awaiting_owner_execution": 3,
        "template_only": 4,
    }
    parser = argparse.ArgumentParser(
        description="Read-only fail-closed preflight for the fixed-income pilot handoff packet."
    )
    parser.add_argument("--packet", type=Path, default=None)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--print-template", action="store_true")
    args = parser.parse_args(argv)

    if args.print_template:
        print(json.dumps(default_handoff_packet(), ensure_ascii=False, indent=2))
        return exit_codes["template_only"]

    try:
        packet = (
            load_handoff_packet(args.packet)
            if args.packet is not None
            else default_handoff_packet()
        )
        report = build_fixed_income_pilot_preflight_report(
            packet=packet,
            generated_at=args.generated_at,
            packet_source="json_file"
            if args.packet is not None
            else "default_pending_template",
        )
        if args.output is not None:
            write_report_exclusive(output=args.output, report=report, repo_root=ROOT)
    except InvalidPacketError as exc:
        report = build_invalid_preflight_report(
            reason_code=exc.reason_code,
            packet_source="json_file"
            if args.packet is not None
            else "default_pending_template",
        )
    except (FileExistsError, ValueError):
        report = build_invalid_preflight_report(
            reason_code="output_write_invalid",
            packet_source="json_file"
            if args.packet is not None
            else "default_pending_template",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_codes.get(str(report["status"]), exit_codes["invalid"])


if __name__ == "__main__":
    raise SystemExit(main())
