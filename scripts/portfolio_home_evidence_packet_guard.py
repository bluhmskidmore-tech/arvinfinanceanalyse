from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import DEFAULT_TEMPLATE  # noqa: E402
from scripts.portfolio_home_closure_artifact_presence_check import (  # noqa: E402
    build_report as build_artifact_presence_report,
)
from scripts.portfolio_home_closure_scorecard import build_scorecard  # noqa: E402
from scripts.portfolio_home_business_owner_approval_packet import (  # noqa: E402
    build_packet as build_business_owner_approval_packet,
    _owner_decision_intake_summary,
    _scorecard_owner_decision_intake_gate_summary,
    owner_decision_intake_alignment,
)
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_owner_input_needed_summary import (  # noqa: E402
    build_summary as build_owner_input_summary,
    summary_sha256,
)
from scripts.portfolio_home_owner_decision_intake_check import build_intake_check  # noqa: E402
from scripts.portfolio_home_owner_handoff_completeness_check import (  # noqa: E402
    build_report as build_handoff_completeness_report,
)
from scripts.portfolio_home_owner_action_packet import (  # noqa: E402
    build_packet as build_owner_action_packet,
)
from scripts.portfolio_home_evidence_snapshot import (  # noqa: E402
    _gate_summary,
    verification_scope_summary,
)
from scripts.verify_portfolio_home_scorecard_commands import (  # noqa: E402
    build_report as build_verification_report,
)


ARTIFACT_PRESENCE_COMMAND = (
    "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current"
)
ARTIFACT_PRESENCE_SUMMARY_LINE = (
    "Closure artifact presence check reports `status=current`, `current=true`, and no blockers."
)
MARKDOWN_SCOPE_LINES = {
    "owner_handoff_packet": [
        {
            "field": "certification_effect",
            "expected_line": "- Certification effect: `none`",
            "prefix": "- Certification effect: ",
        },
        {
            "field": "approves_metric_or_page",
            "expected_line": "- Handoff approves metric or page: `false`",
            "prefix": "- Handoff approves metric or page: ",
        },
        {
            "field": "writes_governance_records",
            "expected_line": "- Handoff writes governance records: `false`",
            "prefix": "- Handoff writes governance records: ",
        },
        {
            "field": "captures_business_owner_approval",
            "expected_line": "- Handoff captures business-owner approval: `false`",
            "prefix": "- Handoff captures business-owner approval: ",
        },
    ],
    "full_closure_signoff_packet": [
        {
            "field": "formal_use_allowed",
            "expected_line": "Formal use allowed: `formal_use_allowed=false`",
            "prefix": "Formal use allowed: ",
        },
        {
            "field": "closure_approved",
            "expected_line": "Closure approved: `closure_approved=false`",
            "prefix": "Closure approved: ",
        },
        {
            "field": "approves_metric_or_page",
            "expected_line": "- `approves_metric_or_page=false`",
            "prefix": "- `approves_metric_or_page=",
        },
        {
            "field": "writes_governance_records",
            "expected_line": "- `writes_governance_records=false`",
            "prefix": "- `writes_governance_records=",
        },
        {
            "field": "proves_capture_ready_page_execution",
            "expected_line": "- `proves_capture_ready_page_execution=false`",
            "prefix": "- `proves_capture_ready_page_execution=",
        },
        {
            "field": "captures_business_owner_approval",
            "expected_line": "- `captures_business_owner_approval=false`",
            "prefix": "- `captures_business_owner_approval=",
        },
        {
            "field": "certification_effect",
            "expected_line": "- `certification_effect=none`",
            "prefix": "- `certification_effect=",
        },
    ],
}
MARKDOWN_SCOPE_TEXT = {
    "full_closure_signoff_packet": [
        {
            "field": "decision_boundary",
            "expected_text": (
                "This packet is prepared for business-owner and risk-owner review only. "
                "It does not approve page closure, metric formal use, or portfolio "
                "decision-grade wording."
            ),
        },
        {
            "field": "reviewer_handoff",
            "expected_text": (
                "This handoff does not capture approval, write governance records, prove "
                "capture-ready page parity, or grant closure. Keep "
                "`formal_use_allowed=false` and `closure_approved=false` until "
                "business-owner approval and rematerialized evidence are explicitly captured."
            ),
        },
    ],
}
MARKDOWN_REQUIRED_TEXT = {
    "owner_handoff_packet": [
        {
            "field": "owner_decision_intake_krd_evidence_wording",
            "expected_text": "nearest-bucket or exact-bucket evidence",
        },
        {
            "field": "owner_decision_intake_scoped_exclusion_wording",
            "expected_text": "scoped-exclusion evidence",
        },
    ],
    "full_closure_signoff_packet": [
        {
            "field": "owner_decision_intake_krd_evidence_wording",
            "expected_text": "nearest-bucket approval or exact-bucket schema evidence",
        },
        {
            "field": "owner_decision_intake_scoped_exclusion_wording",
            "expected_text": "scoped-exclusion evidence",
        },
    ],
}
MARKDOWN_FORBIDDEN_TEXT = {
    "owner_handoff_packet": [
        {
            "field": "owner_decision_intake_stale_krd_evidence_wording",
            "forbidden_text": (
                "Risk-owner CSV decisions, data-owner CSV decisions, exact-bucket "
                "evidence, and business-owner approval"
            ),
        },
    ],
    "full_closure_signoff_packet": [
        {
            "field": "owner_decision_intake_stale_krd_evidence_wording",
            "forbidden_text": "note/comment gaps, and exact-bucket evidence",
        },
    ],
}
BOUNDARY_FIELDS = [
    "page_id",
    "page_slug",
    "report_date",
    "current_score",
    "remaining_gap",
    "score_status",
    "full_score_ready",
    "score_blockers",
]
ARTIFACTS = [
    {
        "name": "evidence_snapshot",
        "path": Path("portfolio") / "portfolio-home-evidence-snapshot.json",
        "kind": "json",
    },
    {
        "name": "owner_action_packet",
        "path": Path("portfolio") / "portfolio-home-owner-action-packet.json",
        "kind": "json",
    },
    {
        "name": "business_owner_approval_packet",
        "path": Path("portfolio") / "portfolio-home-business-owner-approval-packet.json",
        "kind": "json",
    },
    {
        "name": "owner_input_needed_summary",
        "path": Path("portfolio") / "portfolio-home-owner-input-needed-summary.json",
        "kind": "owner_summary",
    },
    {
        "name": "owner_handoff_packet",
        "path": Path("portfolio") / "portfolio-home-owner-handoff-packet.md",
        "kind": "markdown",
    },
    {
        "name": "full_closure_signoff_packet",
        "path": Path("portfolio") / "portfolio-home-full-closure-sign-off-packet.md",
        "kind": "markdown",
    },
]
OWNER_DECISION_SUMMARY_ARTIFACTS = {
    "evidence_snapshot",
    "owner_action_packet",
    "business_owner_approval_packet",
}
OWNER_DECISION_ALIGNMENT_ARTIFACTS = {
    "evidence_snapshot",
    "owner_action_packet",
    "business_owner_approval_packet",
}
SCORECARD_OWNER_GATE_SUMMARY_ARTIFACTS = {
    "evidence_snapshot",
    "owner_action_packet",
    "business_owner_approval_packet",
}
SCORE_BLOCKER_ACTION_COVERAGE_ARTIFACTS = {
    "owner_action_packet",
    "business_owner_approval_packet",
}
BUSINESS_OWNER_ACTIVATION_GUARD_TRUE_FIELDS = [
    "no_automatic_approval",
    "partial_activation_invalid",
    "partial_owner_evidence_activation_invalid",
    "strict_scorecard_required",
    "dependency_consistency_required",
    "owner_decision_intake_required",
    "owner_decision_intake_alignment_required",
    "score_blocker_action_coverage_required",
    "rerun_evidence_required",
    "risk_warning_clean_required",
    "closure_artifact_presence_required",
]
ARTIFACT_EVIDENCE_SCOPE_EXPECTED_CERTIFICATION_EFFECT = "none"
ARTIFACT_EVIDENCE_SCOPE_FALSE_FIELDS = [
    "approves_metric_or_page",
    "writes_governance_records",
    "proves_page_execution",
    "proves_capture_ready_page_execution",
    "fills_owner_decisions",
    "captures_risk_owner_decision",
    "captures_business_owner_approval",
    "proves_full_score_closure",
    "remediates_source_data",
]
ARTIFACT_EVIDENCE_SCOPE_REQUIRED_PATHS = {
    "evidence_snapshot": [
        ("handoff_completeness_summary", "evidence_scope"),
        (
            "business_owner_approval_packet_summary",
            "risk_warning_clean_status",
            "evidence_scope",
        ),
    ],
    "owner_action_packet": [
        ("evidence_scope",),
        ("risk_warning_clean_status", "evidence_scope"),
        ("owner_packets", "business_owner", "evidence_scope"),
    ],
    "business_owner_approval_packet": [
        ("approval_summary", "evidence_scope"),
        ("risk_warning_clean_status", "evidence_scope"),
    ],
    "owner_input_needed_summary": [
        ("evidence_scope",),
    ],
}
BUSINESS_OWNER_ACTIVATION_GUARD_SUMMARY_PATHS = {
    "evidence_snapshot": [
        (
            ("business_owner_approval_packet_summary", "activation_guard"),
            "business_owner_approval_packet_summary",
        ),
    ],
    "owner_action_packet": [
        (
            ("owner_packets", "business_owner", "activation_guard"),
            "business_owner",
        ),
    ],
}
MISSING = object()


def _resolved_docs_root(docs_root: Path) -> Path:
    path = Path(docs_root)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _artifact_presence_summary(report: dict[str, object]) -> dict[str, object]:
    summary = report.get("artifact_current_summary", {})
    assert isinstance(summary, dict)
    return {
        "status": report.get("status"),
        "current": report.get("current"),
        "blockers": report.get("blockers", []),
        "artifact_current_summary": summary,
    }


def _handoff_completeness_blockers(report: dict[str, object]) -> list[str]:
    if report.get("status") == "clean":
        return []
    blockers = report.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        return ["owner_handoff_completeness_blocked"]
    return [f"owner_handoff_completeness_{blocker}" for blocker in blockers]


def _json_payload(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _path_label(path: tuple[str, ...]) -> str:
    return "_".join(path)


def _path_value(payload: dict[str, object], path: tuple[str, ...]) -> object:
    current: object = payload
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _walk_evidence_scopes(
    value: object,
    path: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], object]]:
    locations: list[tuple[tuple[str, ...], object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, str(key))
            if key == "evidence_scope":
                locations.append((child_path, child))
            locations.extend(_walk_evidence_scopes(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            locations.extend(_walk_evidence_scopes(child, (*path, str(index))))
    return locations


def _evidence_scope_mismatches(
    *,
    name: str,
    payload: dict[str, object],
    expected_boundary: dict[str, object],
) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    candidate_only = (
        expected_boundary.get("full_score_ready") is not True
        or expected_boundary.get("score_status") != "ready_for_full_score"
    )
    seen_paths = {
        path
        for path, scope in _walk_evidence_scopes(payload)
        if isinstance(scope, dict)
    }
    for required_path in ARTIFACT_EVIDENCE_SCOPE_REQUIRED_PATHS.get(name, []):
        if required_path not in seen_paths:
            actual = _path_value(payload, required_path)
            label = _path_label(required_path)
            mismatches.append(
                {
                    "path": ".".join(required_path),
                    "field": "evidence_scope",
                    "expected": "object",
                    "actual": None if actual is MISSING else actual,
                    "blocker": f"{name}_{label}_missing",
                },
            )
    for path, scope in _walk_evidence_scopes(payload):
        label = _path_label(path)
        if not isinstance(scope, dict):
            mismatches.append(
                {
                    "path": ".".join(path),
                    "field": "evidence_scope",
                    "expected": "object",
                    "actual": scope,
                    "blocker": f"{name}_{label}_missing",
                },
            )
            continue
        if candidate_only:
            for field in ARTIFACT_EVIDENCE_SCOPE_FALSE_FIELDS:
                if scope.get(field) is True:
                    mismatches.append(
                        {
                            "path": ".".join(path),
                            "field": field,
                            "expected": False,
                            "actual": True,
                            "blocker": f"{name}_{label}_{field}_overclaims",
                        },
                    )
        if "certification_effect" not in scope:
            mismatches.append(
                {
                    "path": ".".join(path),
                    "field": "certification_effect",
                    "expected": ARTIFACT_EVIDENCE_SCOPE_EXPECTED_CERTIFICATION_EFFECT,
                    "actual": None,
                    "blocker": f"{name}_{label}_certification_effect_missing",
                },
            )
        elif (
            scope.get("certification_effect")
            != ARTIFACT_EVIDENCE_SCOPE_EXPECTED_CERTIFICATION_EFFECT
        ):
            mismatches.append(
                {
                    "path": ".".join(path),
                    "field": "certification_effect",
                    "expected": ARTIFACT_EVIDENCE_SCOPE_EXPECTED_CERTIFICATION_EFFECT,
                    "actual": scope.get("certification_effect"),
                    "blocker": f"{name}_{label}_certification_effect_overclaims",
                },
            )
    return mismatches


def _boundary_mismatches(
    *,
    payload: dict[str, object],
    expected_boundary: dict[str, object],
) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    for field in BOUNDARY_FIELDS:
        actual = payload.get(field)
        expected = expected_boundary.get(field)
        if actual != expected:
            mismatches.append(
                {
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                },
            )
    return mismatches


def _business_owner_activation_guard_blockers(payload: dict[str, object]) -> list[str]:
    activation_guard = payload.get("activation_guard")
    if not isinstance(activation_guard, dict):
        return ["business_owner_approval_packet_activation_guard_missing"]
    blockers: list[str] = []
    for field in BUSINESS_OWNER_ACTIVATION_GUARD_TRUE_FIELDS:
        if field not in activation_guard:
            blockers.append(f"business_owner_approval_packet_activation_guard_{field}_missing")
        elif activation_guard.get(field) is not True:
            blockers.append(f"business_owner_approval_packet_activation_guard_{field}_invalid")
    if activation_guard.get("activation_ready") is not False:
        blockers.append("business_owner_approval_packet_activation_guard_activation_ready_invalid")
    return blockers


def _activation_guard_summary_blockers(
    *,
    name: str,
    payload: dict[str, object],
    expected_activation_guard: dict[str, object],
) -> list[str]:
    blockers: list[str] = []
    for path, label in BUSINESS_OWNER_ACTIVATION_GUARD_SUMMARY_PATHS.get(name, []):
        activation_guard = _path_value(payload, path)
        blocker_prefix = f"{name}_{label}_activation_guard"
        if not isinstance(activation_guard, dict):
            blockers.append(f"{blocker_prefix}_missing")
            continue
        for field in BUSINESS_OWNER_ACTIVATION_GUARD_TRUE_FIELDS:
            if field not in activation_guard:
                blockers.append(f"{blocker_prefix}_{field}_missing")
            elif activation_guard.get(field) != expected_activation_guard.get(field):
                blockers.append(f"{blocker_prefix}_{field}_mismatch")
        if activation_guard.get("activation_ready") != expected_activation_guard.get(
            "activation_ready",
        ):
            blockers.append(f"{blocker_prefix}_activation_ready_mismatch")
        if activation_guard.get("required_commands") != expected_activation_guard.get(
            "required_commands",
        ):
            blockers.append(f"{blocker_prefix}_required_commands_mismatch")
    return blockers


def _expected_business_owner_approval_summary(
    packet: dict[str, object],
) -> dict[str, object]:
    approval_summary = packet.get("approval_summary", {})
    assert isinstance(approval_summary, dict)
    approval_field_status = approval_summary.get("approval_field_status", {})
    assert isinstance(approval_field_status, dict)
    return {
        "packet_status": packet.get("packet_status"),
        "activation_ready": packet.get("activation_ready"),
        "approval_action_item_count": approval_summary.get("approval_action_item_count"),
        "approval_field_status": {
            "approval_date": approval_field_status.get("approval_date"),
            "verification_commands_rerun": approval_field_status.get(
                "verification_commands_rerun",
            ),
            "evidence_scope_captures_business_owner_approval": (
                approval_field_status.get(
                    "evidence_scope_captures_business_owner_approval",
                )
            ),
        },
        "risk_warning_clean_status": packet.get("risk_warning_clean_status"),
        "dependency_consistency_status": packet.get("dependency_consistency_status"),
        "dependency_consistency_blockers": packet.get(
            "dependency_consistency_blockers",
            [],
        ),
        "score_blocker_action_coverage": packet.get(
            "score_blocker_action_coverage",
            {},
        ),
        "activation_guard": packet.get("activation_guard", {}),
        "generated_owner_fields_boundaries": packet.get(
            "generated_owner_fields_boundaries",
            {},
        ),
    }


def _business_owner_approval_summary_canonical_blockers(
    *,
    name: str,
    payload: dict[str, object],
    expected_summary: dict[str, object],
) -> list[str]:
    if name != "evidence_snapshot":
        return []
    actual_summary = payload.get("business_owner_approval_packet_summary")
    if not isinstance(actual_summary, dict):
        return ["evidence_snapshot_business_owner_approval_packet_summary_missing"]
    for field, expected in expected_summary.items():
        if actual_summary.get(field) != expected:
            return ["evidence_snapshot_business_owner_approval_packet_summary_canonical_mismatch"]
    return []


def _verification_report_canonical_blockers(
    *,
    name: str,
    payload: dict[str, object],
    docs_root: Path,
) -> list[str]:
    if name != "evidence_snapshot":
        return []
    verification_report = payload.get("verification_report")
    if not isinstance(verification_report, dict):
        return ["evidence_snapshot_verification_report_missing"]
    result_count = verification_report.get("result_count")
    if not isinstance(result_count, int):
        return ["evidence_snapshot_verification_report_result_count_missing"]
    expected_report = build_verification_report(
        limit=result_count,
        expected_state=str(verification_report.get("expected_state") or "blocked"),
        docs_root=docs_root,
    )
    if verification_report != expected_report:
        return ["evidence_snapshot_verification_report_canonical_mismatch"]
    return []


def _verification_scope_canonical_blockers(
    *,
    name: str,
    payload: dict[str, object],
) -> list[str]:
    if name != "evidence_snapshot":
        return []
    verification_report = payload.get("verification_report")
    if not isinstance(verification_report, dict):
        return []
    verification_scope = payload.get("verification_scope")
    if not isinstance(verification_scope, dict):
        return ["evidence_snapshot_verification_scope_missing"]
    if verification_scope != verification_scope_summary(verification_report):
        return ["evidence_snapshot_verification_scope_canonical_mismatch"]
    return []


def _evidence_snapshot_gate_summary_canonical_blockers(
    *,
    name: str,
    payload: dict[str, object],
    expected_scorecard: dict[str, object],
) -> list[str]:
    if name != "evidence_snapshot":
        return []
    gate_summary = payload.get("gate_summary")
    if not isinstance(gate_summary, dict):
        return ["evidence_snapshot_gate_summary_missing"]
    if gate_summary != _gate_summary(expected_scorecard):
        return ["evidence_snapshot_gate_summary_canonical_mismatch"]
    return []


def _owner_action_owner_summary_mismatches(
    *,
    payload: dict[str, object],
    expected_owner_decision_alignment: dict[str, object],
) -> list[str]:
    owner_packets = payload.get("owner_packets")
    if not isinstance(owner_packets, dict):
        return ["owner_action_packet_owner_packets_missing"]
    expected_status = expected_owner_decision_alignment.get("status")
    expected_blockers = expected_owner_decision_alignment.get("blockers", [])
    expected_dependency_status = payload.get("dependency_consistency_status")
    expected_dependency_blockers = payload.get("dependency_consistency_blockers")
    expected_csv_check_summary = payload.get("csv_check_summary")
    expected_generated_owner_fields_boundaries = payload.get(
        "generated_owner_fields_boundaries",
    )
    blockers: list[str] = []
    for owner in ("risk_owner", "data_owner", "business_owner"):
        owner_packet = owner_packets.get(owner)
        if not isinstance(owner_packet, dict):
            blockers.append(f"owner_action_packet_{owner}_missing")
            continue
        actual_status = owner_packet.get("owner_decision_intake_alignment_status")
        actual_blockers = owner_packet.get("owner_decision_intake_alignment_blockers")
        if actual_status is None or actual_blockers is None:
            blockers.append(
                f"owner_action_packet_{owner}_owner_decision_intake_alignment_missing",
            )
        elif actual_status != expected_status or actual_blockers != expected_blockers:
            blockers.append(
                f"owner_action_packet_{owner}_owner_decision_intake_alignment_mismatch",
            )
        if (
            owner_packet.get("dependency_consistency_status") != expected_dependency_status
            or owner_packet.get("dependency_consistency_blockers")
            != expected_dependency_blockers
        ):
            blockers.append(
                f"owner_action_packet_{owner}_dependency_consistency_mismatch",
            )
        if owner_packet.get("csv_check_summary") != expected_csv_check_summary:
            blockers.append(f"owner_action_packet_{owner}_csv_check_summary_mismatch")
        if (
            owner_packet.get("generated_owner_fields_boundaries")
            != expected_generated_owner_fields_boundaries
        ):
            blockers.append(
                f"owner_action_packet_{owner}_generated_owner_fields_boundaries_mismatch",
            )
    return blockers


def _owner_action_assignment_coverage(payload: dict[str, object]) -> dict[str, object]:
    score_blockers = payload.get("score_blockers", [])
    expected = [str(blocker) for blocker in score_blockers] if isinstance(score_blockers, list) else []
    owner_packets = payload.get("owner_packets")
    assigned: list[str] = []
    if isinstance(owner_packets, dict):
        for owner_packet in owner_packets.values():
            if not isinstance(owner_packet, dict):
                continue
            blockers = owner_packet.get("blockers", [])
            if isinstance(blockers, list):
                assigned.extend(str(blocker) for blocker in blockers)

    seen: set[str] = set()
    duplicates: list[str] = []
    for blocker in assigned:
        if blocker in seen and blocker not in duplicates:
            duplicates.append(blocker)
        seen.add(blocker)

    unassigned = [blocker for blocker in expected if blocker not in set(assigned)]
    unexpected = [blocker for blocker in assigned if blocker not in set(expected)]
    assigned_unique = [blocker for blocker in expected if blocker in set(assigned)]
    assigned_unique.extend(
        blocker
        for blocker in assigned
        if blocker not in set(expected) and blocker not in assigned_unique
    )
    clean = not unassigned and not duplicates and not unexpected
    return {
        "status": "clean" if clean else "blocked",
        "score_blockers": expected,
        "assigned_blockers": assigned_unique,
        "unassigned_blockers": unassigned,
        "duplicate_assigned_blockers": duplicates,
        "unexpected_assigned_blockers": unexpected,
    }


def _owner_action_blocker_closure_matrix_coverage(
    payload: dict[str, object],
) -> dict[str, object]:
    score_blockers = payload.get("score_blockers", [])
    expected = [str(blocker) for blocker in score_blockers] if isinstance(score_blockers, list) else []
    matrix = payload.get("blocker_closure_matrix")
    covered: list[str] = []
    if isinstance(matrix, list):
        for row in matrix:
            if not isinstance(row, dict):
                continue
            blocker = str(row.get("blocker") or "")
            if blocker:
                covered.append(blocker)

    seen: set[str] = set()
    duplicates: list[str] = []
    for blocker in covered:
        if blocker in seen and blocker not in duplicates:
            duplicates.append(blocker)
        seen.add(blocker)

    missing = [blocker for blocker in expected if blocker not in set(covered)]
    unexpected = [blocker for blocker in covered if blocker not in set(expected)]
    clean = not missing and not unexpected and not duplicates
    return {
        "status": "clean" if clean else "blocked",
        "expected_blockers": expected,
        "covered_blockers": covered,
        "missing_blockers": missing,
        "unexpected_blockers": unexpected,
        "duplicate_blockers": duplicates,
    }


def _owner_action_action_mismatches(payload: dict[str, object]) -> list[str]:
    owner_packets = payload.get("owner_packets")
    if not isinstance(owner_packets, dict):
        return ["owner_action_packet_owner_packets_missing"]
    matrix = payload.get("blocker_closure_matrix")
    if not isinstance(matrix, list):
        return ["owner_action_packet_blocker_closure_matrix_missing"]

    blockers: list[str] = []
    for row in matrix:
        if not isinstance(row, dict):
            continue
        blocker = str(row.get("blocker") or "")
        owner = str(row.get("owner") or "")
        if not blocker or not owner:
            continue
        owner_packet = owner_packets.get(owner)
        if not isinstance(owner_packet, dict):
            blockers.append(f"owner_action_packet_{owner}_missing")
            continue
        actions = owner_packet.get("actions")
        if not isinstance(actions, list):
            blockers.append(f"owner_action_packet_{owner}_actions_missing")
            continue
        actual = next(
            (
                action
                for action in actions
                if isinstance(action, dict) and action.get("blocker") == blocker
            ),
            None,
        )
        if not isinstance(actual, dict):
            blockers.append(f"owner_action_packet_{owner}_action_{blocker}_missing")
            continue
        recheck_commands = row.get("recheck_commands")
        expected_evidence_command = (
            recheck_commands[0]
            if isinstance(recheck_commands, list) and recheck_commands
            else None
        )
        expected = {
            "blocker": blocker,
            "owner": owner,
            "next_action": row.get("next_action"),
            "evidence_command": expected_evidence_command,
            "exit_criteria": row.get("exit_criteria"),
        }
        if any(actual.get(field) != value for field, value in expected.items()):
            blockers.append(f"owner_action_packet_{owner}_action_{blocker}_mismatch")
    return blockers


def _markdown_bool(value: object) -> str:
    return "true" if value is True else "false"


def _markdown_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()]


def _line_mismatches(
    *,
    lines: list[str],
    field: str,
    expected_line: str,
    prefix: str,
) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    matching_lines = [line for line in lines if line.startswith(prefix)]
    if expected_line not in matching_lines:
        mismatches.append(
            {
                "field": field,
                "expected": expected_line,
                "actual": matching_lines,
            },
        )
    unexpected_lines = [line for line in matching_lines if line != expected_line]
    if unexpected_lines:
        mismatches.append(
            {
                "field": f"{field}_current_claim",
                "expected": expected_line,
                "actual": unexpected_lines,
            },
        )
    return mismatches


def _markdown_section_score_blockers(text: str) -> list[str] | None:
    lines = text.splitlines()
    in_section = False
    blockers: list[str] = []
    for line in lines:
        if line.strip() == "## Current Blockers":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        stripped = line.strip()
        if stripped.startswith("- `") and stripped.endswith("`"):
            blockers.append(stripped[3:-1])
    return blockers if in_section else None


def _scorecard_line_score_blockers(text: str) -> list[str] | None:
    prefix = "- Closure scorecard blockers: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return [
                part
                for index, part in enumerate(line.split("`"))
                if index % 2 == 1
            ]
    return None


def _score_blocker_mismatches(
    *,
    name: str,
    text: str,
    expected_boundary: dict[str, object],
) -> list[dict[str, object]]:
    expected = expected_boundary.get("score_blockers")
    expected_blockers = expected if isinstance(expected, list) else []
    if name == "owner_handoff_packet":
        actual_blockers = _markdown_section_score_blockers(text)
    elif name == "full_closure_signoff_packet":
        actual_blockers = _scorecard_line_score_blockers(text)
    else:
        actual_blockers = None
    if actual_blockers == expected_blockers:
        return []
    return [
        {
            "field": "score_blockers",
            "expected": expected_blockers,
            "actual": actual_blockers,
        },
    ]


def _markdown_scope_mismatches(
    *,
    name: str,
    text: str,
) -> list[dict[str, object]]:
    lines = _markdown_lines(text)
    mismatches: list[dict[str, object]] = []
    for line_spec in MARKDOWN_SCOPE_LINES.get(name, []):
        mismatches.extend(
            {
                **mismatch,
                "field": f"{line_spec['field']}_scope",
            }
            for mismatch in _line_mismatches(
                lines=lines,
                field=str(line_spec["field"]),
                expected_line=str(line_spec["expected_line"]),
                prefix=str(line_spec["prefix"]),
            )
        )
    for text_spec in MARKDOWN_SCOPE_TEXT.get(name, []):
        expected_text = str(text_spec["expected_text"])
        if expected_text not in text:
            mismatches.append(
                {
                    "field": f"{text_spec['field']}_scope",
                    "expected": expected_text,
                    "actual": "missing",
                },
            )
    return mismatches


def _markdown_wording_mismatches(
    *,
    name: str,
    text: str,
) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    for text_spec in MARKDOWN_REQUIRED_TEXT.get(name, []):
        expected_text = str(text_spec["expected_text"])
        if expected_text not in text:
            mismatches.append(
                {
                    "field": str(text_spec["field"]),
                    "expected": expected_text,
                    "actual": "missing",
                },
            )
    for text_spec in MARKDOWN_FORBIDDEN_TEXT.get(name, []):
        forbidden_text = str(text_spec["forbidden_text"])
        if forbidden_text in text:
            mismatches.append(
                {
                    "field": str(text_spec["field"]),
                    "expected": "absent",
                    "actual": forbidden_text,
                },
            )
    return mismatches


def _markdown_boundary_mismatches(
    *,
    name: str,
    text: str,
    expected_boundary: dict[str, object],
) -> list[dict[str, object]]:
    page_id = str(expected_boundary.get("page_id"))
    page_slug = str(expected_boundary.get("page_slug"))
    report_date = str(expected_boundary.get("report_date"))
    current_score = str(expected_boundary.get("current_score"))
    remaining_gap = str(expected_boundary.get("remaining_gap"))
    score_status = str(expected_boundary.get("score_status"))
    full_score_ready = _markdown_bool(expected_boundary.get("full_score_ready"))
    lines = _markdown_lines(text)
    if name == "owner_handoff_packet":
        mismatches = [
            *_line_mismatches(
                lines=lines,
                field="page",
                expected_line=f"- Page: `{page_slug}` (`{page_id}`)",
                prefix="- Page: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="report_date",
                expected_line=f"- Report date: `{report_date}`",
                prefix="- Report date: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="current_score",
                expected_line=f"- Current score: `{current_score}`",
                prefix="- Current score: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="remaining_gap",
                expected_line=f"- Remaining gap: `{remaining_gap}`",
                prefix="- Remaining gap: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="score_status",
                expected_line=f"- Score status: `{score_status}`",
                prefix="- Score status: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="full_score_ready",
                expected_line=f"- Full score closure ready: `{full_score_ready}`",
                prefix="- Full score closure ready: ",
            ),
        ]
    elif name == "full_closure_signoff_packet":
        mismatches = [
            *_line_mismatches(
                lines=lines,
                field="page_id",
                expected_line=f"Page ID: `{page_id}`",
                prefix="Page ID: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="page_slug",
                expected_line=f"Page slug: `{page_slug}`",
                prefix="Page slug: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="report_date",
                expected_line=f"- Decision anchor date: `{report_date}`",
                prefix="- Decision anchor date: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="current_score",
                expected_line=f"Current closure score: `{current_score}`",
                prefix="Current closure score: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="remaining_gap",
                expected_line=f"Remaining full-score gap: `{remaining_gap}`",
                prefix="Remaining full-score gap: ",
            ),
            *_line_mismatches(
                lines=lines,
                field="score_status",
                expected_line=(
                    "- Closure scorecard reports "
                    f"`score_status={score_status}` and `full_score_ready={full_score_ready}`."
                ),
                prefix="- Closure scorecard reports ",
            ),
            *_line_mismatches(
                lines=lines,
                field="full_score_ready",
                expected_line=(
                    "- Evidence snapshot reports `snapshot_kind=portfolio_home_closure_evidence`, "
                    f"`score_status={score_status}`, `full_score_ready={full_score_ready}`, "
                    "and an embedded verifier status of `matched_expected_blocked_state`."
                ),
                prefix="- Evidence snapshot reports ",
            ),
        ]
    else:
        mismatches = []
    return [
        *mismatches,
        *_markdown_scope_mismatches(
            name=name,
            text=text,
        ),
        *_markdown_wording_mismatches(
            name=name,
            text=text,
        ),
        *_score_blocker_mismatches(
            name=name,
            text=text,
            expected_boundary=expected_boundary,
        ),
    ]


def _compare_json_artifact(
    *,
    name: str,
    path: Path,
    docs_root: Path,
    expected_summary: dict[str, object],
    expected_owner_decision_summary: dict[str, object],
    expected_scorecard_owner_gate_summary: dict[str, object],
    expected_owner_decision_alignment: dict[str, object],
    expected_score_blocker_action_coverage: dict[str, object],
    expected_business_owner_approval_summary: dict[str, object],
    expected_business_owner_activation_guard: dict[str, object],
    expected_owner_action_blocker_closure_matrix: list[object],
    expected_scorecard: dict[str, object],
    expected_boundary: dict[str, object],
) -> dict[str, object]:
    payload = _json_payload(path)
    if payload is None:
        return {
            "name": name,
            "path": str(path),
            "kind": "json",
            "status": "blocked",
            "blockers": [f"{name}_invalid_or_missing_json"],
        }
    actual_summary = payload.get("closure_artifact_presence_summary")
    blockers: list[str] = []
    if not isinstance(actual_summary, dict):
        blockers.append(f"{name}_closure_artifact_presence_summary_missing")
    elif actual_summary != expected_summary:
        blockers.append(f"{name}_closure_artifact_presence_summary_mismatch")
    boundary_mismatches = _boundary_mismatches(
        payload=payload,
        expected_boundary=expected_boundary,
    )
    evidence_scope_mismatches = _evidence_scope_mismatches(
        name=name,
        payload=payload,
        expected_boundary=expected_boundary,
    )
    blockers.extend(
        f"{name}_{mismatch['field']}_mismatch"
        for mismatch in boundary_mismatches
    )
    for mismatch in evidence_scope_mismatches:
        _append_unique(blockers, str(mismatch["blocker"]))
    for blocker in _activation_guard_summary_blockers(
        name=name,
        payload=payload,
        expected_activation_guard=expected_business_owner_activation_guard,
    ):
        _append_unique(blockers, blocker)
    for blocker in _business_owner_approval_summary_canonical_blockers(
        name=name,
        payload=payload,
        expected_summary=expected_business_owner_approval_summary,
    ):
        _append_unique(blockers, blocker)
    for blocker in _verification_report_canonical_blockers(
        name=name,
        payload=payload,
        docs_root=docs_root,
    ):
        _append_unique(blockers, blocker)
    for blocker in _verification_scope_canonical_blockers(
        name=name,
        payload=payload,
    ):
        _append_unique(blockers, blocker)
    for blocker in _evidence_snapshot_gate_summary_canonical_blockers(
        name=name,
        payload=payload,
        expected_scorecard=expected_scorecard,
    ):
        _append_unique(blockers, blocker)
    if name in OWNER_DECISION_SUMMARY_ARTIFACTS:
        owner_decision_summary = payload.get("owner_decision_intake_summary")
        if not isinstance(owner_decision_summary, dict):
            blockers.append(f"{name}_owner_decision_intake_summary_missing")
        elif owner_decision_summary != expected_owner_decision_summary:
            blockers.append(f"{name}_owner_decision_intake_summary_mismatch")
    if name in SCORECARD_OWNER_GATE_SUMMARY_ARTIFACTS:
        scorecard_owner_gate_summary = payload.get(
            "scorecard_owner_decision_intake_gate_summary",
        )
        if not isinstance(scorecard_owner_gate_summary, dict):
            blockers.append(f"{name}_scorecard_owner_decision_intake_gate_summary_missing")
        elif scorecard_owner_gate_summary != expected_scorecard_owner_gate_summary:
            blockers.append(f"{name}_scorecard_owner_decision_intake_gate_summary_mismatch")
    if name in OWNER_DECISION_ALIGNMENT_ARTIFACTS:
        owner_decision_alignment = payload.get("owner_decision_intake_alignment")
        if not isinstance(owner_decision_alignment, dict):
            blockers.append(f"{name}_owner_decision_intake_alignment_missing")
        elif owner_decision_alignment != expected_owner_decision_alignment:
            blockers.append(f"{name}_owner_decision_intake_alignment_mismatch")
    if name in SCORE_BLOCKER_ACTION_COVERAGE_ARTIFACTS:
        score_blocker_action_coverage = payload.get("score_blocker_action_coverage")
        if not isinstance(score_blocker_action_coverage, dict):
            blockers.append(f"{name}_score_blocker_action_coverage_missing")
        elif score_blocker_action_coverage != expected_score_blocker_action_coverage:
            blockers.append(f"{name}_score_blocker_action_coverage_mismatch")
    if name == "business_owner_approval_packet":
        blockers.extend(_business_owner_activation_guard_blockers(payload))
    if name == "owner_action_packet":
        assignment_coverage = payload.get("assignment_coverage")
        if not isinstance(assignment_coverage, dict):
            blockers.append("owner_action_packet_assignment_coverage_missing")
        elif assignment_coverage != _owner_action_assignment_coverage(payload):
            blockers.append("owner_action_packet_assignment_coverage_mismatch")
        blocker_closure_matrix_coverage = payload.get("blocker_closure_matrix_coverage")
        if not isinstance(blocker_closure_matrix_coverage, dict):
            blockers.append("owner_action_packet_blocker_closure_matrix_coverage_missing")
        elif blocker_closure_matrix_coverage != _owner_action_blocker_closure_matrix_coverage(payload):
            blockers.append("owner_action_packet_blocker_closure_matrix_coverage_mismatch")
        if payload.get("blocker_closure_matrix") != expected_owner_action_blocker_closure_matrix:
            blockers.append("owner_action_packet_blocker_closure_matrix_canonical_mismatch")
        for blocker in _owner_action_owner_summary_mismatches(
            payload=payload,
            expected_owner_decision_alignment=expected_owner_decision_alignment,
        ):
            _append_unique(blockers, blocker)
        for blocker in _owner_action_action_mismatches(payload):
            _append_unique(blockers, blocker)
    return {
        "name": name,
        "path": str(path),
        "kind": "json",
        "status": "clean" if not blockers else "blocked",
        "boundary_status": "clean" if not boundary_mismatches else "blocked",
        "boundary_mismatches": boundary_mismatches,
        "evidence_scope_status": "clean" if not evidence_scope_mismatches else "blocked",
        "evidence_scope_mismatches": evidence_scope_mismatches,
        "blockers": blockers,
    }


def _compare_markdown_artifact(
    *,
    name: str,
    path: Path,
    expected_boundary: dict[str, object],
) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    blockers: list[str] = []
    if ARTIFACT_PRESENCE_COMMAND not in text:
        blockers.append(f"{name}_artifact_presence_command_missing")
    if ARTIFACT_PRESENCE_SUMMARY_LINE not in text:
        blockers.append(f"{name}_artifact_presence_summary_missing")
    boundary_mismatches = _markdown_boundary_mismatches(
        name=name,
        text=text,
        expected_boundary=expected_boundary,
    )
    blockers.extend(
        f"{name}_{mismatch['field']}_mismatch"
        for mismatch in boundary_mismatches
    )
    return {
        "name": name,
        "path": str(path),
        "kind": "markdown",
        "status": "clean" if not blockers else "blocked",
        "boundary_status": "clean" if not boundary_mismatches else "blocked",
        "boundary_mismatches": boundary_mismatches,
        "blockers": blockers,
    }


def _compare_owner_summary_artifact(
    *,
    name: str,
    path: Path,
    expected_summary: dict[str, object],
    expected_boundary: dict[str, object],
) -> dict[str, object]:
    actual_summary = _json_payload(path)
    blockers: list[str] = []
    if actual_summary is None:
        blockers.append(f"{name}_invalid_or_missing_json")
        actual_hash = None
        current = False
        boundary_mismatches: list[dict[str, object]] = []
        evidence_scope_mismatches: list[dict[str, object]] = []
    else:
        expected_hash = summary_sha256(expected_summary)
        actual_hash = summary_sha256(actual_summary)
        current = expected_hash == actual_hash
        if not current:
            blockers.append(f"{name}_stale")
        boundary_mismatches = _boundary_mismatches(
            payload=actual_summary,
            expected_boundary=expected_boundary,
        )
        evidence_scope_mismatches = _evidence_scope_mismatches(
            name=name,
            payload=actual_summary,
            expected_boundary=expected_boundary,
        )
        blockers.extend(
            f"{name}_{mismatch['field']}_mismatch"
            for mismatch in boundary_mismatches
        )
        for mismatch in evidence_scope_mismatches:
            _append_unique(blockers, str(mismatch["blocker"]))
    return {
        "name": name,
        "path": str(path),
        "kind": "owner_summary",
        "status": "clean" if not blockers else "blocked",
        "current": current,
        "expected_sha256": summary_sha256(expected_summary),
        "actual_sha256": actual_hash,
        "boundary_status": "clean" if not boundary_mismatches else "blocked",
        "boundary_mismatches": boundary_mismatches,
        "evidence_scope_status": "clean" if not evidence_scope_mismatches else "blocked",
        "evidence_scope_mismatches": evidence_scope_mismatches,
        "blockers": blockers,
    }


def _compare_artifact(
    *,
    artifact: dict[str, object],
    docs_root: Path,
    expected_summary: dict[str, object],
    expected_owner_decision_summary: dict[str, object],
    expected_scorecard_owner_gate_summary: dict[str, object],
    expected_owner_decision_alignment: dict[str, object],
    expected_score_blocker_action_coverage: dict[str, object],
    expected_business_owner_approval_summary: dict[str, object],
    expected_business_owner_activation_guard: dict[str, object],
    expected_owner_action_blocker_closure_matrix: list[object],
    expected_scorecard: dict[str, object],
    owner_input_summary: dict[str, object],
    expected_boundary: dict[str, object],
) -> dict[str, object]:
    name = str(artifact["name"])
    path = docs_root / artifact["path"]
    kind = str(artifact["kind"])
    if kind == "json":
        return _compare_json_artifact(
            name=name,
            path=path,
            docs_root=docs_root,
            expected_summary=expected_summary,
            expected_owner_decision_summary=expected_owner_decision_summary,
            expected_scorecard_owner_gate_summary=expected_scorecard_owner_gate_summary,
            expected_owner_decision_alignment=expected_owner_decision_alignment,
            expected_score_blocker_action_coverage=expected_score_blocker_action_coverage,
            expected_business_owner_approval_summary=(
                expected_business_owner_approval_summary
            ),
            expected_business_owner_activation_guard=expected_business_owner_activation_guard,
            expected_owner_action_blocker_closure_matrix=(
                expected_owner_action_blocker_closure_matrix
            ),
            expected_scorecard=expected_scorecard,
            expected_boundary=expected_boundary,
        )
    if kind == "markdown":
        return _compare_markdown_artifact(
            name=name,
            path=path,
            expected_boundary=expected_boundary,
        )
    if kind == "owner_summary":
        return _compare_owner_summary_artifact(
            name=name,
            path=path,
            expected_summary=owner_input_summary,
            expected_boundary=expected_boundary,
        )
    raise ValueError(f"Unsupported portfolio-home evidence packet kind: {kind}")


def build_report(
    *,
    docs_root: Path = ROOT / "docs",
    duckdb_path: Path = DEFAULT_DUCKDB,
    report_date: str = DEFAULT_REPORT_DATE,
    template_path: Path = DEFAULT_TEMPLATE,
    limit: int | None = None,
) -> dict[str, object]:
    if limit is not None:
        limit = validate_non_negative_portfolio_limit(
            limit,
            label="evidence packet guard limit",
        )
    resolved_docs_root = _resolved_docs_root(docs_root)
    artifact_report = build_artifact_presence_report(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=resolved_docs_root,
        limit=3,
    )
    artifact_presence_summary = _artifact_presence_summary(artifact_report)
    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=3,
        docs_root=resolved_docs_root,
    )
    expected_boundary = {
        field: scorecard.get(field)
        for field in BOUNDARY_FIELDS
    }
    owner_input_summary = build_owner_input_summary(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=resolved_docs_root,
        limit=3,
    )
    intake_check = build_intake_check(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=resolved_docs_root,
        limit=3,
    )
    expected_owner_decision_summary = _owner_decision_intake_summary(intake_check)
    expected_scorecard_owner_gate_summary = _scorecard_owner_decision_intake_gate_summary(
        scorecard,
    )
    scorecard_gates = scorecard.get("gates", {})
    expected_score_blocker_action_coverage = (
        scorecard_gates.get("score_blocker_action_coverage", {})
        if isinstance(scorecard_gates, dict)
        else {}
    )
    assert isinstance(expected_score_blocker_action_coverage, dict)
    expected_owner_decision_alignment = owner_decision_intake_alignment(
        expected_owner_decision_summary,
        expected_scorecard_owner_gate_summary,
    )
    business_owner_approval_packet = build_business_owner_approval_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=resolved_docs_root,
        limit=3,
    )
    expected_business_owner_approval_summary = _expected_business_owner_approval_summary(
        business_owner_approval_packet,
    )
    expected_business_owner_activation_guard = business_owner_approval_packet.get(
        "activation_guard",
        {},
    )
    assert isinstance(expected_business_owner_activation_guard, dict)
    owner_action_packet = build_owner_action_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=resolved_docs_root,
        limit=3,
    )
    expected_owner_action_blocker_closure_matrix = owner_action_packet.get(
        "blocker_closure_matrix",
        [],
    )
    assert isinstance(expected_owner_action_blocker_closure_matrix, list)
    handoff_completeness = build_handoff_completeness_report(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=resolved_docs_root,
        limit=3,
    )
    selected_artifacts = ARTIFACTS[:limit] if limit is not None else ARTIFACTS
    artifacts = [
        _compare_artifact(
            artifact=artifact,
            docs_root=resolved_docs_root,
            expected_summary=artifact_presence_summary,
            expected_owner_decision_summary=expected_owner_decision_summary,
            expected_scorecard_owner_gate_summary=expected_scorecard_owner_gate_summary,
            expected_owner_decision_alignment=expected_owner_decision_alignment,
            expected_score_blocker_action_coverage=expected_score_blocker_action_coverage,
            expected_business_owner_approval_summary=(
                expected_business_owner_approval_summary
            ),
            expected_business_owner_activation_guard=expected_business_owner_activation_guard,
            expected_owner_action_blocker_closure_matrix=(
                expected_owner_action_blocker_closure_matrix
            ),
            expected_scorecard=scorecard,
            owner_input_summary=owner_input_summary,
            expected_boundary=expected_boundary,
        )
        for artifact in selected_artifacts
    ]
    blockers = [
        blocker
        for artifact in artifacts
        for blocker in artifact.get("blockers", [])
    ]
    blockers.extend(_handoff_completeness_blockers(handoff_completeness))
    return {
        "check_kind": "portfolio_home_evidence_packet_guard",
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": report_date,
        "docs_root": str(resolved_docs_root),
        "status": "clean" if not blockers else "blocked",
        "blockers": blockers,
        "required_command": ARTIFACT_PRESENCE_COMMAND,
        "expected_boundary": expected_boundary,
        "artifact_presence_summary": artifact_presence_summary,
        "handoff_completeness": handoff_completeness,
        "artifacts": artifacts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home evidence packets include artifact presence/currentness evidence.",
    )
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="evidence packet guard limit",
        ),
        default=None,
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless all evidence packets include artifact presence evidence.",
    )
    args = parser.parse_args(argv)

    report = build_report(
        docs_root=Path(args.docs_root),
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_clean and report["status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
