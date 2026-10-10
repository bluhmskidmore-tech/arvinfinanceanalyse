from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.portfolio_home_business_owner_approval_packet import (  # noqa: E402
    _activation_guard,
    _business_owner_approval_boundary,
    _evidence_dependencies,
    _owner_decision_intake_summary,
    _scorecard_owner_decision_intake_gate_summary,
    owner_decision_intake_alignment,
    _rerun_evidence_status,
)
from scripts.portfolio_home_closure_artifact_summary import (  # noqa: E402
    artifact_current_summary as build_artifact_current_summary,
    artifact_presence_report,
    closure_artifact_presence_summary,
)
from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    build_scorecard,
    non_negative_portfolio_limit,
)
from scripts.portfolio_home_limit import validate_non_negative_portfolio_limit  # noqa: E402
from scripts.portfolio_home_dependency_consistency_check import (  # noqa: E402
    build_dependency_consistency,
)
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_krd_remap_review_queue import build_queue as build_krd_queue  # noqa: E402
from scripts.portfolio_home_maturity_remediation_queue import (  # noqa: E402
    build_queue as build_maturity_queue,
)
from scripts.portfolio_home_owner_decision_intake_check import (  # noqa: E402
    build_intake_check,
)
from scripts.portfolio_home_risk_warning_consistency import (  # noqa: E402
    build_evidence as build_warning_consistency,
)


OWNER_DECISION_INTAKE_COMMAND = (
    "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready"
)
DEFAULT_OUTPUT = ROOT / "docs" / "portfolio" / "portfolio-home-owner-action-packet.json"
STRICT_HANDOFF_GATE_NAMES = [
    "owner_decision_intake_check_strict",
    "business_owner_approval_packet_strict",
    "scorecard_strict",
]


def _portable_provenance_path(value: object) -> object:
    """Keep repository-owned provenance stable across worktrees."""

    if not isinstance(value, str):
        return value
    try:
        relative = Path(value).resolve().relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return value
    return relative.as_posix()


def _action_by_blocker(actions: list[object]) -> dict[str, dict[str, object]]:
    by_blocker: dict[str, dict[str, object]] = {}
    for action in actions:
        if isinstance(action, dict):
            blocker = str(action.get("blocker") or "")
            if blocker:
                by_blocker[blocker] = action
    return by_blocker


def _select_actions(
    actions: list[object],
    blockers: list[str],
) -> list[dict[str, object]]:
    by_blocker = _action_by_blocker(actions)
    return [
        dict(by_blocker[blocker])
        for blocker in blockers
        if blocker in by_blocker
    ]


def _owner_status(blockers: list[str]) -> str:
    return "clean" if not blockers else "blocked"


def _business_owner_blockers(score_blockers: list[object]) -> list[str]:
    return [
        blocker
        for blocker in [
            "business_owner_approval",
            "formal_page_approval_missing",
            "approval_dependency_consistency_blocked",
            "owner_decision_intake_blocked",
            "owner_decision_intake_alignment_blocked",
        ]
        if blocker in score_blockers
    ]


def _assignment_coverage(
    score_blockers: list[object],
    owner_packets: dict[str, dict[str, object]],
) -> dict[str, object]:
    expected = [str(blocker) for blocker in score_blockers]
    assigned: list[str] = []
    for packet in owner_packets.values():
        blockers = packet.get("blockers", [])
        if isinstance(blockers, list):
            assigned.extend(str(blocker) for blocker in blockers)

    seen: set[str] = set()
    duplicates: list[str] = []
    for blocker in assigned:
        if blocker in seen and blocker not in duplicates:
            duplicates.append(blocker)
        seen.add(blocker)

    assigned_set = set(assigned)
    assigned_unique = [blocker for blocker in expected if blocker in assigned_set]
    assigned_unique.extend(
        blocker
        for blocker in assigned
        if blocker not in set(expected) and blocker not in assigned_unique
    )
    unassigned = [blocker for blocker in expected if blocker not in set(assigned)]
    unexpected = [blocker for blocker in assigned if blocker not in set(expected)]
    clean = not unassigned and not duplicates and not unexpected
    return {
        "status": "clean" if clean else "blocked",
        "score_blockers": expected,
        "assigned_blockers": assigned_unique,
        "unassigned_blockers": unassigned,
        "duplicate_assigned_blockers": duplicates,
        "unexpected_assigned_blockers": unexpected,
    }


def _business_owner_boundary_activated(boundary: dict[str, object]) -> bool:
    return (
        boundary.get("template_approval_captured") is True
        and boundary.get("formal_authorization_allowed") is True
        and boundary.get("governance_write_allowed") is True
        and boundary.get("page_execution_proven") is True
        and boundary.get("full_score_closure_ready") is True
        and boundary.get("activation_ready") is True
        and boundary.get("status") == "activated"
        and boundary.get("blockers") == []
    )


def _score_blocker_action_coverage_ready(
    expected_blockers: list[str],
    coverage: dict[str, object],
) -> bool:
    return bool(
        coverage.get("status") == "clean"
        and coverage.get("blockers") == []
        and coverage.get("unassigned_blockers") == []
        and coverage.get("covered_blockers") == expected_blockers
    )


def _assignment_coverage_ready(
    expected_blockers: list[str],
    coverage: dict[str, object],
) -> bool:
    return bool(
        coverage.get("status") == "clean"
        and coverage.get("score_blockers") == expected_blockers
        and coverage.get("assigned_blockers") == expected_blockers
        and coverage.get("unassigned_blockers") == []
        and coverage.get("duplicate_assigned_blockers") == []
        and coverage.get("unexpected_assigned_blockers") == []
    )


def _blocker_closure_matrix_coverage_ready(
    expected_blockers: list[str],
    coverage: dict[str, object],
) -> bool:
    return bool(
        coverage.get("status") == "clean"
        and coverage.get("expected_blockers") == expected_blockers
        and coverage.get("covered_blockers") == expected_blockers
        and coverage.get("missing_blockers") == []
        and coverage.get("unexpected_blockers") == []
        and coverage.get("duplicate_blockers") == []
    )


def _strict_gate_clean(packet: dict[str, object]) -> bool:
    assignment_coverage = packet.get("assignment_coverage", {})
    assert isinstance(assignment_coverage, dict)
    score_blocker_action_coverage = packet.get("score_blocker_action_coverage", {})
    assert isinstance(score_blocker_action_coverage, dict)
    blocker_closure_matrix_coverage = packet.get("blocker_closure_matrix_coverage", {})
    assert isinstance(blocker_closure_matrix_coverage, dict)
    business_owner_approval_boundary = packet.get("business_owner_approval_boundary", {})
    assert isinstance(business_owner_approval_boundary, dict)
    score_blockers = packet.get("score_blockers", [])
    expected_blockers = [str(blocker) for blocker in score_blockers] if isinstance(score_blockers, list) else []
    return (
        packet.get("handoff_status") == "ready_for_full_score"
        and packet.get("full_score_ready") is True
        and packet.get("score_status") == "ready_for_full_score"
        and _assignment_coverage_ready(expected_blockers, assignment_coverage)
        and _score_blocker_action_coverage_ready(
            expected_blockers,
            score_blocker_action_coverage,
        )
        and _blocker_closure_matrix_coverage_ready(
            expected_blockers,
            blocker_closure_matrix_coverage,
        )
        and _business_owner_boundary_activated(business_owner_approval_boundary)
    )


def _risk_warning_clean_status(warning: dict[str, object]) -> dict[str, object]:
    decision_status = warning.get("decision_status")
    decision_blockers = warning.get("decision_blockers", [])
    if not isinstance(decision_blockers, list):
        decision_blockers = []
    evidence_scope = warning.get("evidence_scope", {})
    if not isinstance(evidence_scope, dict):
        evidence_scope = {}
    warning_resolution_matrix = warning.get("warning_resolution_matrix", [])
    if not isinstance(warning_resolution_matrix, list):
        warning_resolution_matrix = []
    duration_delta_detail = warning.get("duration_exclusion_delta_detail", {})
    if not isinstance(duration_delta_detail, dict):
        duration_delta_detail = {}
    rematerialization_preview = warning.get("risk_tensor_rematerialization_preview", {})
    if not isinstance(rematerialization_preview, dict):
        rematerialization_preview = {}
    valid = decision_status == "clean"
    return {
        "status": "clean" if valid else "blocked",
        "valid": valid,
        "decision_status": decision_status,
        "decision_blockers": decision_blockers,
        "evidence_scope": dict(evidence_scope),
        "warning_resolution_matrix": warning_resolution_matrix,
        "duration_exclusion_delta_detail": duration_delta_detail,
        "risk_tensor_rematerialization_preview": rematerialization_preview,
    }


def _generated_owner_fields_boundaries(checks: list[object]) -> dict[str, object]:
    return {
        str(item.get("name")): item.get("actual_generated_owner_fields_must_be_blank")
        for item in checks
        if isinstance(item, dict)
    }


def packet_sha256(packet: dict[str, object]) -> str:
    canonical = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _current_status(output: Path, expected_packet: dict[str, object]) -> dict[str, object]:
    if not output.exists():
        actual_packet: dict[str, object] = {}
    else:
        try:
            parsed = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        actual_packet = parsed if isinstance(parsed, dict) else {}
    expected_hash = packet_sha256(expected_packet)
    actual_hash = packet_sha256(actual_packet)
    current = expected_hash == actual_hash
    return {
        "artifact": str(output),
        "status": "current" if current else "stale",
        "current": current,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
    }


def _strict_gate_expectations(
    scorecard: dict[str, object],
    business_owner_approval_boundary: dict[str, object],
) -> dict[str, object]:
    score_status = str(scorecard.get("score_status") or "")
    boundary_activated = _business_owner_boundary_activated(business_owner_approval_boundary)
    activation_state = str(business_owner_approval_boundary.get("status") or "unknown")
    verification_commands = scorecard.get("verification_commands", [])
    assert isinstance(verification_commands, list)
    commands_by_name = {
        str(command.get("name")): command
        for command in verification_commands
        if isinstance(command, dict)
    }
    commands: list[dict[str, object]] = []
    for name in STRICT_HANDOFF_GATE_NAMES:
        command = commands_by_name[name]
        expected_when_blocked = command.get("expected_when_blocked")
        expected_when_full_score = command.get("expected_when_full_score")
        current_expected_exit = (
            expected_when_full_score
            if score_status == "ready_for_full_score"
            else expected_when_blocked
        )
        if name == "business_owner_approval_packet_strict" and not boundary_activated:
            current_expected_exit = expected_when_blocked
        commands.append(
            {
                "name": name,
                "command": command.get("command"),
                "current_expected_exit": current_expected_exit,
                "expected_when_blocked": expected_when_blocked,
                "expected_when_full_score": expected_when_full_score,
            },
        )
    return {
        "current_state": score_status,
        "activation_state": activation_state,
        "summary": (
            "Current strict gates: expected to exit 0; full closure evidence is ready."
            if score_status == "ready_for_full_score" and boundary_activated
            else (
                "Current strict gates: expected to fail until rerun evidence and "
                "business-owner activation boundary are both clean."
            )
            if score_status == "ready_for_full_score"
            else (
                "Current strict gates: expected to fail until owner decisions, "
                "maturity remediation/exclusion, and business approval are captured."
            )
        ),
        "full_score_rule": (
            "After owner updates: each strict gate below must exit 0 before "
            "`/portfolio` can claim full closure."
        ),
        "commands": commands,
    }


def _risk_owner_decision_artifacts(report_date: str) -> list[dict[str, object]]:
    return [
        {
            "artifact": f"docs/portfolio/krd-contract-decision/{report_date}/krd_remap_summary.csv",
            "required_fields": ["risk_owner_decision", "decision_notes"],
            "allowed_decisions": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
            "note_required_for": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
        },
        {
            "artifact": f"docs/portfolio/krd-contract-decision/{report_date}/krd_remap_detail.csv",
            "required_fields": ["risk_owner_decision", "decision_notes"],
            "allowed_decisions": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
            "note_required_for": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
        },
        {
            "artifact": (
                f"docs/portfolio/krd-contract-decision/{report_date}/"
                "nearest_bucket_approval_evidence.json"
            ),
            "required_fields": [
                "risk_owner_name",
                "risk_owner_approval_date",
                "risk_owner_approved",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "metric_contract_decision_recorded",
                "verification_rerun_matched",
            ],
            "allowed_decisions": ["approve_nearest_bucket"],
            "note_required_for": [],
        },
        {
            "artifact": (
                f"docs/portfolio/krd-contract-decision/{report_date}/"
                "exact_bucket_schema_evidence.json"
            ),
            "required_fields": [
                "metric_contract_owner_name",
                "metric_contract_update_date",
                "metric_contract_updated",
                "api_schema_owner_name",
                "api_schema_update_date",
                "api_schema_updated",
                "risk_tensor_owner_name",
                "risk_tensor_rematerialization_date",
                "risk_tensor_rematerialized",
                "verifier_name",
                "verification_rerun_date",
                "verification_rerun_matched",
            ],
            "allowed_decisions": ["require_exact_bucket_schema"],
            "note_required_for": [],
        },
    ]


def _data_owner_decision_artifacts(report_date: str) -> list[dict[str, object]]:
    return [
        {
            "artifact": f"docs/portfolio/maturity-remediation/{report_date}/tyw_liability_missing_maturity.csv",
            "required_fields": ["proposed_maturity_date", "owner_decision", "owner_comment"],
            "allowed_decisions": [
                "remediate_source",
                "approve_scoped_exclusion",
                "reject",
            ],
            "note_required_for": [
                "remediate_source",
                "approve_scoped_exclusion",
                "reject",
            ],
        },
        {
            "artifact": (
                f"docs/portfolio/maturity-remediation/{report_date}/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "required_fields": [
                "data_owner_name",
                "data_owner_approval_date",
                "data_owner_approved",
                "risk_owner_name",
                "risk_owner_countersign_date",
                "risk_owner_countersigned",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "verification_rerun_matched",
            ],
            "allowed_decisions": ["approve_scoped_exclusion"],
            "note_required_for": [],
        },
    ]


def _business_owner_decision_artifacts() -> list[dict[str, object]]:
    return [
        {
            "artifact": "docs/portfolio/portfolio-home-business-owner-approval-template.md",
            "required_fields": [
                "approval_status",
                "business_owner_name",
                "risk_owner_name",
                "approval_decision",
                "approval_date",
                "business_owner_signature",
                "risk_owner_signature",
                "krd_contract_decision",
                "maturity_data_decision",
                "risk_tensor_warning_decision",
                "evidence_scope",
            ],
            "allowed_decisions": ["approve"],
            "note_required_for": [
                "approve_nearest_bucket",
                "approve_scoped_exclusion",
                "reject",
                "request_changes",
            ],
        },
    ]


def _artifact_paths(artifacts: list[dict[str, object]]) -> list[object]:
    paths: list[object] = []
    for artifact in artifacts:
        path = artifact.get("artifact")
        if path:
            paths.append(path)
    return paths


def _artifact_required_fields(artifacts: list[dict[str, object]]) -> list[object]:
    fields: list[object] = []
    for artifact in artifacts:
        raw_fields = artifact.get("required_fields", [])
        if not isinstance(raw_fields, list):
            continue
        for field in raw_fields:
            if field not in fields:
                fields.append(field)
    return fields


def _closure_artifacts_for_blocker(blocker: str, report_date: str) -> list[dict[str, object]]:
    if blocker == "krd_contract_decision_required":
        return _risk_owner_decision_artifacts(report_date)
    if blocker == "tyw_liability_maturity_date_remediation_required":
        maturity_artifacts = _data_owner_decision_artifacts(report_date)
        return [maturity_artifacts[0], maturity_artifacts[1]]
    if blocker == "business_owner_approval":
        return _business_owner_decision_artifacts()
    if blocker == "owner_decision_intake_blocked":
        return (
            _risk_owner_decision_artifacts(report_date)
            + _data_owner_decision_artifacts(report_date)
            + _business_owner_decision_artifacts()
        )
    return []


def _closure_evidence_sources_for_blocker(
    blocker: str,
    report_date: str,
) -> list[dict[str, object]]:
    if blocker == "bond_matured_outstanding_reconciliation_required":
        return [
            {
                "name": "matured_outstanding_queue",
                "command": (
                    "python scripts/portfolio_home_matured_outstanding_queue.py "
                    f"--report-date {report_date} --require-empty"
                ),
                "fields": ["summary", "rows"],
                "boundary": (
                    "Read-only reconciliation evidence; does not change source positions, "
                    "approve an exception, or close the page."
                ),
            }
        ]
    if blocker not in {
        "risk_tensor_quality_warning",
        "krd_bucket_warning_mismatch",
        "duration_exclusion_warning_mismatch",
        "risk_tensor_warning_mismatch",
    }:
        return []
    return [
        {
            "name": "risk_warning_consistency",
            "command": (
                f"python scripts/portfolio_home_risk_warning_consistency.py "
                f"--report-date {report_date} --require-consistent"
            ),
            "fields": [
                "parsed_warnings",
                "recomputed_warnings",
                "duration_exclusion_delta_detail",
                "warning_resolution_matrix",
                "decision_blockers",
            ],
            "boundary": (
                "Evidence-only warning consistency check; does not approve "
                "the metric, clean the risk tensor, or close the page."
            ),
        },
    ]


def _closure_recheck_commands(
    blocker: str,
    report_date: str = DEFAULT_REPORT_DATE,
) -> list[str]:
    def _date_qualified(command: str) -> str:
        command_head, separator, command_tail = command.partition(".py")
        return f"{command_head}{separator} --report-date {report_date}{command_tail}"

    if blocker == "krd_bucket_warning_mismatch":
        return [
            f"python scripts/portfolio_home_risk_warning_consistency.py --report-date {report_date} --require-consistent",
            f"python scripts/portfolio_home_full_closure_evidence.py --report-date {report_date} --require-clean",
        ]
    if blocker == "bond_matured_outstanding_reconciliation_required":
        return [
            f"python scripts/portfolio_home_matured_outstanding_queue.py --report-date {report_date} --require-empty",
            f"python scripts/portfolio_home_full_closure_evidence.py --report-date {report_date} --require-clean",
        ]
    if blocker in {"risk_tensor_quality_warning", "risk_tensor_warning_mismatch"}:
        return [
            f"python scripts/portfolio_home_risk_warning_consistency.py --report-date {report_date} --require-clean",
            f"python scripts/portfolio_home_full_closure_evidence.py --report-date {report_date} --require-clean",
        ]
    if blocker == "duration_exclusion_warning_mismatch":
        return [
            f"python scripts/portfolio_home_risk_warning_consistency.py --report-date {report_date} --require-consistent",
            f"python scripts/portfolio_home_maturity_remediation_queue.py --report-date {report_date} --require-empty",
        ]
    if blocker == "krd_contract_decision_required":
        return [
            f"python scripts/portfolio_home_krd_remap_review_queue.py --report-date {report_date} --require-clean",
            _date_qualified(OWNER_DECISION_INTAKE_COMMAND),
        ]
    if blocker == "tyw_liability_maturity_date_remediation_required":
        return [
            f"python scripts/portfolio_home_maturity_remediation_queue.py --report-date {report_date} --require-empty",
            _date_qualified(OWNER_DECISION_INTAKE_COMMAND),
        ]
    if blocker == "business_owner_approval":
        return [
            f"python scripts/check_portfolio_home_business_owner_approval.py --report-date {report_date} --require-captured",
            f"python scripts/portfolio_home_business_owner_approval_packet.py --report-date {report_date} --limit 3 --require-ready",
            f"python scripts/portfolio_home_closure_scorecard.py --report-date {report_date} --limit 3 --require-full-score",
        ]
    if blocker == "owner_decision_intake_blocked":
        return [_date_qualified(OWNER_DECISION_INTAKE_COMMAND)]
    return []


def _closure_exit_signal(blocker: str, report_date: str) -> str:
    if blocker == "risk_tensor_quality_warning":
        return (
            f"Risk tensor quality is clean for report_date {report_date} and strict "
            "full-closure evidence no longer reports this blocker."
        )
    if blocker == "krd_bucket_warning_mismatch":
        return (
            "KRD bucket warning evidence matches current formal bonds, and the risk tensor "
            "is rematerialized or /portfolio remains candidate-only until the warning can "
            "be cleared."
        )
    if blocker == "duration_exclusion_warning_mismatch":
        return (
            "Parsed and recomputed duration-exclusion warning evidence match, and "
            "risk warning consistency exits 0."
        )
    if blocker == "risk_tensor_warning_mismatch":
        return (
            "Risk tensor warning evidence is reconciled, cleanly rematerialized, and "
            "risk warning clean gate exits 0."
        )
    if blocker == "krd_contract_decision_required":
        return (
            "Risk-owner KRD decision is captured with notes for every scoped row, "
            "conditional nearest-bucket or exact-bucket evidence is valid when selected, "
            "and the KRD strict gate exits 0."
        )
    if blocker == "bond_matured_outstanding_reconciliation_required":
        return (
            "Matured or unparseable non-zero bond positions are reconciled at source, "
            "and the matured-outstanding strict queue exits 0."
        )
    if blocker == "tyw_liability_maturity_date_remediation_required":
        return (
            "TYW liability missing-maturity rows are remediated at source or covered "
            "by a signed scoped exclusion evidence file, and the maturity strict gate exits 0."
        )
    if blocker == "business_owner_approval":
        return (
            "Business-owner approval is signed, risk-owner countersignature is present, "
            "evidence scope approves the page, and the full scorecard strict gate exits 0."
        )
    if blocker == "owner_decision_intake_blocked":
        return (
            "Risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, "
            "data-owner CSV decisions, scoped-exclusion evidence, and business-owner "
            "approval are reconciled, and the owner decision intake strict gate exits 0."
        )
    return "Blocker is removed from score_blockers with auditable evidence."


def _blocker_closure_matrix(
    *,
    score_blockers: list[object],
    scorecard_actions: list[object],
    report_date: str,
) -> list[dict[str, object]]:
    actions_by_blocker = _action_by_blocker(scorecard_actions)
    current_blockers = [str(blocker) for blocker in score_blockers]
    matrix: list[dict[str, object]] = []
    for blocker in current_blockers:
        action = actions_by_blocker.get(blocker, {})
        artifacts = _closure_artifacts_for_blocker(blocker, report_date)
        evidence_sources = _closure_evidence_sources_for_blocker(blocker, report_date)
        row = {
            "blocker": blocker,
            "owner": action.get("owner"),
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": action.get("next_action"),
            "decision_artifacts": _artifact_paths(artifacts),
            "required_fields": _artifact_required_fields(artifacts),
            "recheck_commands": _closure_recheck_commands(blocker, report_date),
            "exit_criteria": action.get("exit_criteria"),
            "removes_blocker_when": _closure_exit_signal(blocker, report_date),
        }
        if evidence_sources:
            row["evidence_sources"] = evidence_sources
        matrix.append(row)
    return matrix


def _blocker_closure_matrix_coverage(
    score_blockers: list[object],
    matrix: list[dict[str, object]],
) -> dict[str, object]:
    expected = [str(blocker) for blocker in score_blockers]
    covered: list[str] = []
    for row in matrix:
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


def build_packet(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    limit: int,
    docs_root: Path = ROOT / "docs",
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="owner action packet limit",
    )
    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=limit,
        docs_root=docs_root,
    )
    scorecard_actions = scorecard.get("score_blocker_actions", [])
    assert isinstance(scorecard_actions, list)

    warning = build_warning_consistency(
        duckdb_path=duckdb_path,
        report_date=report_date,
    )
    krd = build_krd_queue(
        duckdb_path=duckdb_path,
        report_date=report_date,
        limit=limit,
    )
    maturity = build_maturity_queue(
        duckdb_path=duckdb_path,
        report_date=report_date,
        limit=limit,
    )
    approval = build_approval_status(template_path, report_date=report_date)
    dependency_consistency = build_dependency_consistency(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=limit,
        docs_root=docs_root,
    )
    dependencies = _evidence_dependencies(report_date, Path(docs_root))
    intake_check = build_intake_check(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    owner_decision_intake_summary = _owner_decision_intake_summary(intake_check)
    owner_decision_blockers = owner_decision_intake_summary.get("owner_decision_blockers", [])
    assert isinstance(owner_decision_blockers, list)
    risk_owner_intake_blockers = [
        blocker
        for blocker in ["krd_owner_decision_rejected"]
        if blocker in owner_decision_blockers
    ]
    data_owner_intake_blockers = [
        blocker
        for blocker in ["maturity_owner_decision_rejected"]
        if blocker in owner_decision_blockers
    ]
    decision_gap_counts = owner_decision_intake_summary.get("decision_gap_counts", {})
    assert isinstance(decision_gap_counts, dict)
    note_gap_counts = owner_decision_intake_summary.get("note_gap_counts", {})
    assert isinstance(note_gap_counts, dict)
    exact_bucket_schema_evidence = owner_decision_intake_summary.get(
        "exact_bucket_schema_evidence",
        {},
    )
    assert isinstance(exact_bucket_schema_evidence, dict)
    nearest_bucket_approval_evidence = owner_decision_intake_summary.get(
        "nearest_bucket_approval_evidence",
        {},
    )
    assert isinstance(nearest_bucket_approval_evidence, dict)
    scoped_exclusion_evidence = owner_decision_intake_summary.get(
        "maturity_scoped_exclusion_evidence",
        {},
    )
    assert isinstance(scoped_exclusion_evidence, dict)
    scorecard_owner_gate_summary = _scorecard_owner_decision_intake_gate_summary(scorecard)
    owner_intake_alignment = owner_decision_intake_alignment(
        owner_decision_intake_summary,
        scorecard_owner_gate_summary,
    )
    rerun_status = _rerun_evidence_status(docs_root=Path(docs_root), report_date=report_date)
    dependency_consistency_status = dependency_consistency.get("dependency_consistency_status")
    dependency_consistency_status_text = str(dependency_consistency_status or "")
    dependency_consistency_blockers = dependency_consistency.get("dependency_consistency_blockers", [])
    csv_check_summary = dependency_consistency.get("csv_check_summary", {})
    manifest_consistency_checks = dependency_consistency.get("manifest_consistency_checks", [])
    assert isinstance(manifest_consistency_checks, list)
    generated_owner_fields_boundaries = _generated_owner_fields_boundaries(
        manifest_consistency_checks,
    )

    risk_blockers = [
        blocker
        for blocker in [
            "risk_tensor_quality_warning",
            "krd_bucket_warning_mismatch",
            "risk_tensor_warning_mismatch",
            "krd_contract_decision_required",
            "unsupported_krd_bucket",
        ]
        if blocker in scorecard.get("score_blockers", [])
        or blocker in warning.get("decision_blockers", [])
        or blocker in krd.get("review_blockers", [])
    ]
    risk_blockers.extend(risk_owner_intake_blockers)
    data_blockers = [
        blocker
        for blocker in [
            "tyw_liability_maturity_date_remediation_required",
            "bond_matured_outstanding_reconciliation_required",
            "duration_exclusion_warning_mismatch",
        ]
        if blocker in scorecard.get("score_blockers", [])
    ]
    data_blockers.extend(data_owner_intake_blockers)
    business_blockers = _business_owner_blockers(scorecard.get("score_blockers", []))

    risk_tensor = warning.get("risk_tensor", {})
    assert isinstance(risk_tensor, dict)
    risk_tensor_lineage = warning.get("risk_tensor_lineage", {})
    if not isinstance(risk_tensor_lineage, dict):
        risk_tensor_lineage = {}
    risk_warning_clean_status = _risk_warning_clean_status(warning)
    approval_items = approval.get("approval_action_items", [])
    assert isinstance(approval_items, list)
    scorecard_gates = scorecard.get("gates", {})
    assert isinstance(scorecard_gates, dict)
    full_closure_gate = scorecard_gates.get("full_closure_evidence", {})
    assert isinstance(full_closure_gate, dict)

    owner_packets = {
        "risk_owner": {
            "status": _owner_status(risk_blockers),
            "blockers": risk_blockers,
            "actions": _select_actions(scorecard_actions, risk_blockers),
            "risk_tensor_quality_flag": risk_tensor.get("quality_flag"),
            "risk_tensor_lineage": risk_tensor_lineage,
            "risk_warning_decision_status": warning.get("decision_status"),
            "risk_warning_evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                f"--report-date {report_date} --require-clean"
            ),
            "warning_resolution_matrix": risk_warning_clean_status.get(
                "warning_resolution_matrix",
                [],
            ),
            "duration_exclusion_delta_detail": risk_warning_clean_status.get(
                "duration_exclusion_delta_detail",
                {},
            ),
            "risk_tensor_rematerialization_preview": risk_warning_clean_status.get(
                "risk_tensor_rematerialization_preview",
                {},
            ),
            "dependency_consistency_status": dependency_consistency_status,
            "dependency_consistency_blockers": dependency_consistency_blockers,
            "csv_check_summary": csv_check_summary,
            "generated_owner_fields_boundaries": generated_owner_fields_boundaries,
            "owner_decision_intake_alignment_status": owner_intake_alignment.get("status"),
            "owner_decision_intake_alignment_blockers": owner_intake_alignment.get("blockers", []),
            "decision_gap_counts": decision_gap_counts.get("krd", {}),
            "note_gap_counts": note_gap_counts.get("krd", {}),
            "exact_bucket_schema_evidence": exact_bucket_schema_evidence,
            "nearest_bucket_approval_evidence": nearest_bucket_approval_evidence,
            "decision_intake_artifacts": _risk_owner_decision_artifacts(report_date),
            "krd_contract_status": krd.get("review_status"),
            "krd_decision_options": krd.get("decision_options", []),
            "krd_remap_summary": krd.get("krd_remap_summary", []),
            "krd_sample_rows": krd.get("krd_remap_rows", []),
        },
        "data_owner": {
            "status": _owner_status(data_blockers),
            "blockers": data_blockers,
            "actions": _select_actions(scorecard_actions, data_blockers),
            "maturity_remediation_status": maturity.get("remediation_status"),
            "risk_tensor_lineage": risk_tensor_lineage,
            "duration_exclusion_delta_detail": risk_warning_clean_status.get(
                "duration_exclusion_delta_detail",
                {},
            ),
            "risk_tensor_rematerialization_preview": risk_warning_clean_status.get(
                "risk_tensor_rematerialization_preview",
                {},
            ),
            "dependency_consistency_status": dependency_consistency_status,
            "dependency_consistency_blockers": dependency_consistency_blockers,
            "csv_check_summary": csv_check_summary,
            "generated_owner_fields_boundaries": generated_owner_fields_boundaries,
            "owner_decision_intake_alignment_status": owner_intake_alignment.get("status"),
            "owner_decision_intake_alignment_blockers": owner_intake_alignment.get("blockers", []),
            "decision_gap_counts": decision_gap_counts.get("maturity", {}),
            "comment_gap_counts": note_gap_counts.get("maturity", {}),
            "scoped_exclusion_evidence": scoped_exclusion_evidence,
            "decision_intake_artifacts": _data_owner_decision_artifacts(report_date),
            "remediation_scope": maturity.get("remediation_scope", {}),
            "bond_no_maturity_summary": maturity.get("bond_no_maturity_summary", {}),
            "bond_missing_maturity_summary": maturity.get("bond_missing_maturity_summary", {}),
            "bond_matured_outstanding_summary": full_closure_gate.get(
                "bond_matured_outstanding",
                {},
            ),
            "tyw_liability_missing_maturity_summary": maturity.get(
                "tyw_liability_missing_maturity_summary",
                {},
            ),
            "bond_missing_maturity_rows": maturity.get("bond_missing_maturity_rows", []),
            "tyw_liability_missing_maturity_rows": maturity.get(
                "tyw_liability_missing_maturity_rows",
                [],
            ),
        },
        "business_owner": {
            "status": _owner_status(business_blockers),
            "blockers": business_blockers,
            "actions": _select_actions(scorecard_actions, business_blockers),
            "approval_status": approval.get("approval_status"),
            "dependency_consistency_status": dependency_consistency_status,
            "dependency_consistency_blockers": dependency_consistency_blockers,
            "csv_check_summary": csv_check_summary,
            "generated_owner_fields_boundaries": generated_owner_fields_boundaries,
            "owner_decision_intake_alignment_status": owner_intake_alignment.get("status"),
            "owner_decision_intake_alignment_blockers": owner_intake_alignment.get("blockers", []),
            "decision_intake_artifacts": _business_owner_decision_artifacts(),
            "formal_use_allowed": approval.get("formal_use_allowed"),
            "closure_approved": approval.get("closure_approved"),
            "approval_field_status": approval.get("approval_field_status"),
            "approval_action_item_count": approval.get("approval_action_item_count"),
            "approval_action_items": approval_items,
            "evidence_scope": approval.get("evidence_scope"),
        },
    }
    score_blockers = scorecard["score_blockers"]
    assert isinstance(score_blockers, list)
    assignment_coverage = _assignment_coverage(score_blockers, owner_packets)
    score_blocker_action_coverage = scorecard_gates.get("score_blocker_action_coverage", {})
    assert isinstance(score_blocker_action_coverage, dict)
    blocker_closure_matrix = _blocker_closure_matrix(
        score_blockers=score_blockers,
        scorecard_actions=scorecard_actions,
        report_date=str(scorecard["report_date"]),
    )
    blocker_closure_matrix_coverage = _blocker_closure_matrix_coverage(
        score_blockers,
        blocker_closure_matrix,
    )
    artifact_current = build_artifact_current_summary(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        intake_summary=owner_decision_intake_summary,
    )
    artifact_presence = artifact_presence_report(
        docs_root=Path(docs_root),
        closure_matrix=blocker_closure_matrix,
        artifact_current_summary=artifact_current,
    )
    artifact_presence_summary = closure_artifact_presence_summary(artifact_presence)
    boundary_activation_ready = bool(
        scorecard["full_score_ready"]
        and _assignment_coverage_ready(
            [str(blocker) for blocker in score_blockers],
            assignment_coverage,
        )
        and _score_blocker_action_coverage_ready(
            [str(blocker) for blocker in score_blockers],
            score_blocker_action_coverage,
        )
        and _blocker_closure_matrix_coverage_ready(
            [str(blocker) for blocker in score_blockers],
            blocker_closure_matrix_coverage,
        )
        and all(bool(item.get("available")) for item in dependencies)
        and dependency_consistency_status_text == "consistent"
        and intake_check.get("intake_ready")
        and owner_intake_alignment.get("status") == "consistent"
        and artifact_presence_summary.get("current") is True
        and artifact_presence_summary.get("blockers") == []
        and rerun_status.get("valid")
        and risk_warning_clean_status.get("valid")
    )
    business_owner_approval_boundary = _business_owner_approval_boundary(
        approval=approval,
        scorecard=scorecard,
        intake_check=intake_check,
        rerun_evidence_status=rerun_status,
        risk_warning_clean_status=risk_warning_clean_status,
        activation_ready=boundary_activation_ready,
        dependencies=dependencies,
        dependency_consistency_status=dependency_consistency_status_text,
        owner_intake_alignment=owner_intake_alignment,
        score_blocker_action_coverage=score_blocker_action_coverage,
        closure_artifact_presence_summary=artifact_presence_summary,
    )
    owner_packets["business_owner"][
        "business_owner_approval_boundary"
    ] = business_owner_approval_boundary
    owner_packets["business_owner"]["activation_guard"] = _activation_guard(
        boundary_activation_ready,
        report_date,
    )

    return {
        "packet_kind": "portfolio_home_owner_action_packet",
        "page_id": scorecard["page_id"],
        "page_slug": scorecard["page_slug"],
        "report_date": scorecard["report_date"],
        "duckdb_path": _portable_provenance_path(scorecard["duckdb_path"]),
        "template_path": _portable_provenance_path(scorecard["template_path"]),
        "current_score": scorecard["current_score"],
        "remaining_gap": scorecard["remaining_gap"],
        "score_status": scorecard["score_status"],
        "full_score_ready": scorecard["full_score_ready"],
        "handoff_status": (
            "ready_for_full_score"
            if scorecard["full_score_ready"]
            else "owner_actions_required"
        ),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "certification_effect": "none",
        },
        "score_blockers": score_blockers,
        "dependency_consistency_status": dependency_consistency_status,
        "dependency_consistency_blockers": dependency_consistency_blockers,
        "csv_check_summary": csv_check_summary,
        "generated_owner_fields_boundaries": generated_owner_fields_boundaries,
        "evidence_dependencies": dependencies,
        "closure_artifact_presence_summary": artifact_presence_summary,
        "risk_warning_clean_status": risk_warning_clean_status,
        "business_owner_approval_boundary": business_owner_approval_boundary,
        "owner_decision_intake_summary": owner_decision_intake_summary,
        "scorecard_owner_decision_intake_gate_summary": scorecard_owner_gate_summary,
        "owner_decision_intake_alignment": owner_intake_alignment,
        "rerun_evidence_status": rerun_status,
        "owner_decision_intake_command": (
            f"{OWNER_DECISION_INTAKE_COMMAND} --report-date {report_date}"
        ),
        "strict_gate_expectations": _strict_gate_expectations(
            scorecard,
            business_owner_approval_boundary,
        ),
        "assignment_coverage": assignment_coverage,
        "score_blocker_action_coverage": score_blocker_action_coverage,
        "blocker_closure_matrix_coverage": blocker_closure_matrix_coverage,
        "blocker_closure_matrix": blocker_closure_matrix,
        "owner_packets": owner_packets,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an owner-grouped action packet for portfolio-home full closure.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="owner action packet limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless every owner action packet is clean.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Return non-zero unless the output JSON matches the freshly built packet.",
    )
    args = parser.parse_args(argv)

    packet = build_packet(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        limit=int(args.limit),
        docs_root=Path(args.docs_root),
    )
    output = Path(args.output) if args.output is not None else None
    if args.check_current:
        if output is None:
            output = DEFAULT_OUTPUT
        status = _current_status(output, packet)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["current"] else 1
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    if args.require_clean and not _strict_gate_clean(packet):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
