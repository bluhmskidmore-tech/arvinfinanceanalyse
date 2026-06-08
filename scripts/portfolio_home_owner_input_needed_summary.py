from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import DEFAULT_TEMPLATE  # noqa: E402
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_owner_action_packet import (  # noqa: E402
    _assignment_coverage_ready,
    _blocker_closure_matrix_coverage_ready,
    _score_blocker_action_coverage_ready,
    build_packet,
)


DEFAULT_OUTPUT = ROOT / "docs" / "portfolio" / "portfolio-home-owner-input-needed-summary.json"
OWNER_ORDER = ["risk_owner", "data_owner", "business_owner"]


def _stable_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def summary_sha256(summary: dict[str, object]) -> str:
    return hashlib.sha256(_stable_json(summary).encode("utf-8")).hexdigest()


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _unique_strings(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def _scoped_exclusion_artifact_last(artifacts: list[str]) -> list[str]:
    nearest = "/nearest_bucket_approval_evidence.json"
    scoped = "/maturity_scoped_exclusion_evidence.json"
    return [
        artifact
        for artifact in artifacts
        if not artifact.endswith(nearest) and not artifact.endswith(scoped)
    ] + [
        artifact for artifact in artifacts if artifact.endswith(nearest)
    ] + [
        artifact for artifact in artifacts if artifact.endswith(scoped)
    ]


def _route_status(owner_packet: dict[str, object], intake_ready: bool) -> str:
    if intake_ready and owner_packet.get("status") == "clean":
        return "ready"
    return "owner_input_needed" if owner_packet.get("status") != "clean" else "waiting_for_other_owner"


def _owner_route(
    *,
    owner: str,
    owner_packet: dict[str, object],
    closure_matrix: list[object],
    intake_ready: bool,
) -> dict[str, object]:
    blockers = _unique_strings(_list(owner_packet.get("blockers")))
    blocker_rows = [
        row
        for row in closure_matrix
        if isinstance(row, dict) and str(row.get("blocker") or "") in blockers
    ]
    decision_artifacts = _unique_strings(
        [
            artifact
            for row in blocker_rows
            for artifact in _list(row.get("decision_artifacts"))
        ],
    )
    decision_artifacts = _scoped_exclusion_artifact_last(decision_artifacts)
    evidence_sources = [
        source
        for row in blocker_rows
        for source in _list(row.get("evidence_sources"))
        if isinstance(source, dict)
    ]
    required_fields = _unique_strings(
        [
            field
            for row in blocker_rows
            for field in _list(row.get("required_fields"))
        ],
    )
    recheck_commands = _unique_strings(
        [
            command
            for row in blocker_rows
            for command in _list(row.get("recheck_commands"))
        ],
    )
    exit_criteria = _unique_strings([row.get("exit_criteria") for row in blocker_rows])
    route = {
        "owner": owner,
        "input_status": _route_status(owner_packet, intake_ready),
        "blockers": blockers,
        "decision_artifacts": decision_artifacts,
        "evidence_sources": evidence_sources,
        "required_fields": required_fields,
        "recheck_commands": recheck_commands,
        "exit_criteria": exit_criteria,
    }
    if owner == "risk_owner":
        route["decision_gap_counts"] = owner_packet.get("decision_gap_counts", {})
        route["note_gap_counts"] = owner_packet.get("note_gap_counts", {})
        route["exact_bucket_schema_evidence"] = owner_packet.get(
            "exact_bucket_schema_evidence",
            {},
        )
        route["nearest_bucket_approval_evidence"] = owner_packet.get(
            "nearest_bucket_approval_evidence",
            {},
        )
        route["risk_tensor_quality_flag"] = owner_packet.get("risk_tensor_quality_flag")
        route["risk_tensor_rematerialization_preview"] = owner_packet.get(
            "risk_tensor_rematerialization_preview",
            {},
        )
    elif owner == "data_owner":
        route["decision_gap_counts"] = owner_packet.get("decision_gap_counts", {})
        route["comment_gap_counts"] = owner_packet.get("comment_gap_counts", {})
        route["scoped_exclusion_evidence"] = owner_packet.get(
            "scoped_exclusion_evidence",
            {},
        )
        route["risk_tensor_rematerialization_preview"] = owner_packet.get(
            "risk_tensor_rematerialization_preview",
            {},
        )
    elif owner == "business_owner":
        route["approval_status"] = owner_packet.get("approval_status")
        route["approval_action_item_count"] = owner_packet.get("approval_action_item_count")
        route["business_owner_approval_boundary"] = owner_packet.get(
            "business_owner_approval_boundary",
            {},
        )
    return route


def _missing_input_counts(
    *,
    intake_summary: dict[str, object],
    business_owner_packet: dict[str, object],
) -> dict[str, object]:
    decision_gap_counts = _dict(intake_summary.get("decision_gap_counts"))
    krd_counts = _dict(decision_gap_counts.get("krd"))
    maturity_counts = _dict(decision_gap_counts.get("maturity"))
    return {
        "krd_missing_decision_rows": krd_counts.get("missing_decision_rows", 0),
        "maturity_missing_decision_rows": maturity_counts.get("missing_decision_rows", 0),
        "business_owner_approval_action_items": business_owner_packet.get(
            "approval_action_item_count",
            0,
        ),
    }


def _owner_input_readiness_boundary(packet: dict[str, object]) -> dict[str, object]:
    score_blockers = [str(blocker) for blocker in _list(packet.get("score_blockers"))]
    assignment_coverage = _dict(packet.get("assignment_coverage"))
    score_blocker_action_coverage = _dict(packet.get("score_blocker_action_coverage"))
    blocker_closure_matrix_coverage = _dict(packet.get("blocker_closure_matrix_coverage"))
    closure_artifact_presence_summary = _dict(packet.get("closure_artifact_presence_summary"))
    evidence_dependencies = [
        item for item in _list(packet.get("evidence_dependencies")) if isinstance(item, dict)
    ]
    owner_decision_intake_alignment = _dict(packet.get("owner_decision_intake_alignment"))

    blockers: list[str] = []
    if not _assignment_coverage_ready(score_blockers, assignment_coverage):
        blockers.append("assignment_coverage_not_clean")
    if not _score_blocker_action_coverage_ready(
        score_blockers,
        score_blocker_action_coverage,
    ):
        blockers.append("score_blocker_action_coverage_not_clean")
    if not _blocker_closure_matrix_coverage_ready(
        score_blockers,
        blocker_closure_matrix_coverage,
    ):
        blockers.append("blocker_closure_matrix_coverage_not_clean")
    if (
        closure_artifact_presence_summary.get("current") is not True
        or closure_artifact_presence_summary.get("blockers") != []
    ):
        blockers.append("closure_artifact_presence_not_current")
    if not evidence_dependencies:
        blockers.append("evidence_dependencies_missing")
    elif any(item.get("available") is not True for item in evidence_dependencies):
        blockers.append("evidence_dependency_unavailable")
    if (
        packet.get("dependency_consistency_status") != "consistent"
        or packet.get("dependency_consistency_blockers", []) != []
    ):
        blockers.append("dependency_consistency_not_clean")
    if (
        owner_decision_intake_alignment.get("status") != "consistent"
        or owner_decision_intake_alignment.get("blockers", []) != []
    ):
        blockers.append("owner_decision_intake_alignment_not_consistent")

    return {
        "status": "clean" if not blockers else "blocked",
        "boundary_ready": not blockers,
        "blockers": blockers,
        "assignment_coverage": assignment_coverage,
        "score_blocker_action_coverage": score_blocker_action_coverage,
        "blocker_closure_matrix_coverage": blocker_closure_matrix_coverage,
        "closure_artifact_presence_summary": closure_artifact_presence_summary,
        "evidence_dependencies": evidence_dependencies,
    }


def build_summary(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    docs_root: Path,
    limit: int,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="owner input needed summary limit",
    )
    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    owner_packets = _dict(packet.get("owner_packets"))
    intake_summary = _dict(packet.get("owner_decision_intake_summary"))
    closure_matrix = _list(packet.get("blocker_closure_matrix"))
    intake_ready = bool(intake_summary.get("intake_ready"))
    owner_routes = [
        _owner_route(
            owner=owner,
            owner_packet=_dict(owner_packets.get(owner)),
            closure_matrix=closure_matrix,
            intake_ready=intake_ready,
        )
        for owner in OWNER_ORDER
    ]
    business_owner_packet = _dict(owner_packets.get("business_owner"))
    owner_input_needed = not intake_ready or any(
        route["input_status"] == "owner_input_needed" for route in owner_routes
    )
    readiness_boundary = _owner_input_readiness_boundary(packet)
    ready_for_intake = not owner_input_needed and readiness_boundary.get("status") == "clean"
    input_status = (
        "owner_input_needed"
        if owner_input_needed
        else "ready_for_intake"
        if ready_for_intake
        else "owner_input_boundary_blocked"
    )
    return {
        "summary_kind": "portfolio_home_owner_input_needed_summary",
        "page_id": packet.get("page_id"),
        "page_slug": packet.get("page_slug"),
        "report_date": packet.get("report_date"),
        "duckdb_path": packet.get("duckdb_path"),
        "template_path": packet.get("template_path"),
        "current_score": packet.get("current_score"),
        "remaining_gap": packet.get("remaining_gap"),
        "score_status": packet.get("score_status"),
        "full_score_ready": packet.get("full_score_ready"),
        "score_blockers": packet.get("score_blockers", []),
        "input_status": input_status,
        "owner_input_needed": owner_input_needed,
        "ready_for_intake": ready_for_intake,
        "owner_input_readiness_boundary": readiness_boundary,
        "owner_decision_statuses": intake_summary.get("owner_decision_statuses", {}),
        "owner_decision_blockers": intake_summary.get("owner_decision_blockers", []),
        "owner_input_boundary": intake_summary.get("owner_input_boundary", {}),
        "export_current_summary": intake_summary.get("export_current_summary", {}),
        "dependency_consistency_status": packet.get("dependency_consistency_status"),
        "dependency_consistency_blockers": packet.get("dependency_consistency_blockers", []),
        "owner_decision_intake_alignment": packet.get("owner_decision_intake_alignment", {}),
        "missing_input_counts": _missing_input_counts(
            intake_summary=intake_summary,
            business_owner_packet=business_owner_packet,
        ),
        "owner_routes": owner_routes,
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "fills_owner_decisions": False,
            "remediates_source_data": False,
            "captures_business_owner_approval": False,
            "proves_full_score_closure": False,
            "certification_effect": "none",
        },
    }


def _current_status(output: Path, expected_summary: dict[str, object]) -> dict[str, object]:
    if not output.exists():
        actual_summary: dict[str, object] = {}
    else:
        try:
            parsed = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        actual_summary = parsed if isinstance(parsed, dict) else {}
    expected_hash = summary_sha256(expected_summary)
    actual_hash = summary_sha256(actual_summary)
    current = expected_hash == actual_hash
    return {
        "artifact": str(output),
        "status": "current" if current else "stale",
        "current": current,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a machine-readable portfolio-home owner input routing summary.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="owner input needed summary limit",
        ),
        default=3,
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Return non-zero unless the output JSON matches the freshly built summary.",
    )
    args = parser.parse_args(argv)

    summary = build_summary(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        docs_root=Path(args.docs_root),
        limit=int(args.limit),
    )
    output = Path(args.output) if args.output is not None else None
    if args.check_current:
        if output is None:
            output = DEFAULT_OUTPUT
        status = _current_status(output, summary)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["current"] else 1
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
