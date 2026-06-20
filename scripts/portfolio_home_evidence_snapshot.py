from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
    DEFAULT_TEMPLATE,
    VERIFICATION_COMMANDS,
    build_scorecard,
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_business_owner_approval_packet import (  # noqa: E402
    RERUN_APPROVAL_REQUIRED_BUSINESS_OWNER_BOUNDARY,
    RERUN_EVIDENCE_ARTIFACT,
    build_packet as build_business_owner_approval_packet,
    owner_decision_intake_alignment,
    rerun_evidence_payload_status,
)
from scripts.portfolio_home_closure_artifact_presence_check import (  # noqa: E402
    build_report as build_artifact_presence_report,
)
from scripts.portfolio_home_dependency_consistency_check import (  # noqa: E402
    _csv_check_summary,
)
from scripts.portfolio_home_owner_decision_intake_check import (  # noqa: E402
    build_intake_check,
)
from scripts.portfolio_home_owner_handoff_completeness_check import (  # noqa: E402
    build_report as build_handoff_completeness_report,
)
from scripts.verify_portfolio_home_scorecard_commands import (  # noqa: E402
    RUNNER_COMMAND_NAME,
    build_report,
)


OWNER_HANDOFF_COMPLETENESS_ALIGNMENT_FIELDS = [
    "owner_handoff_completeness_status",
    "owner_handoff_completeness_ready",
    "owner_handoff_completeness_blockers",
]


def snapshot_sha256(snapshot: dict[str, object]) -> str:
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gate_summary(scorecard: dict[str, object]) -> dict[str, object]:
    gates = scorecard.get("gates", {})
    assert isinstance(gates, dict)
    full_closure = gates.get("full_closure_evidence", {})
    risk_warning = gates.get("risk_warning_consistency", {})
    krd_contract = gates.get("krd_contract", {})
    maturity = gates.get("maturity_remediation", {})
    approval = gates.get("business_owner_approval", {})
    owner_intake = gates.get("owner_decision_intake", {})
    owner_intake_alignment = gates.get("owner_decision_intake_alignment", {})
    owner_handoff_completeness = gates.get("owner_handoff_completeness", {})
    score_blocker_action_coverage = gates.get("score_blocker_action_coverage", {})
    dependency_consistency = gates.get("approval_dependency_consistency", {})
    assert isinstance(full_closure, dict)
    assert isinstance(risk_warning, dict)
    assert isinstance(krd_contract, dict)
    assert isinstance(maturity, dict)
    assert isinstance(approval, dict)
    assert isinstance(owner_intake, dict)
    assert isinstance(owner_intake_alignment, dict)
    assert isinstance(owner_handoff_completeness, dict)
    assert isinstance(score_blocker_action_coverage, dict)
    assert isinstance(dependency_consistency, dict)
    return {
        "full_closure_status": full_closure.get("status"),
        "risk_warning_decision_status": risk_warning.get("decision_status"),
        "krd_contract_status": krd_contract.get("status"),
        "maturity_remediation_status": maturity.get("status"),
        "business_owner_approval_status": approval.get("status"),
        "owner_decision_intake_status": owner_intake.get("status"),
        "owner_decision_intake_ready": owner_intake.get("intake_ready"),
        "owner_decision_intake_blockers": owner_intake.get("blockers", []),
        "owner_decision_intake_alignment_status": owner_intake_alignment.get("status"),
        "owner_decision_intake_alignment_blockers": owner_intake_alignment.get("blockers", []),
        "owner_handoff_completeness_status": owner_handoff_completeness.get("status"),
        "owner_handoff_completeness_ready": owner_handoff_completeness.get("handoff_ready"),
        "owner_handoff_completeness_blockers": owner_handoff_completeness.get("blockers", []),
        "score_blocker_action_coverage_status": score_blocker_action_coverage.get("status"),
        "score_blocker_action_coverage_blockers": score_blocker_action_coverage.get("blockers", []),
        "score_blocker_action_coverage_unassigned_blockers": score_blocker_action_coverage.get(
            "unassigned_blockers",
            [],
        ),
        "approval_dependency_consistency_status": dependency_consistency.get("status"),
        "approval_dependency_consistency_blockers": dependency_consistency.get("blockers", []),
        "generated_owner_fields_boundaries": dependency_consistency.get(
            "generated_owner_fields_boundaries",
            {},
        ),
        "risk_tensor_quality_flag": (
            full_closure.get("risk_tensor", {}).get("quality_flag")
            if isinstance(full_closure.get("risk_tensor"), dict)
            else None
        ),
        "krd_remap_tenors": [
            row.get("tenor_bucket")
            for row in full_closure.get("krd_remap_scope", [])
            if isinstance(row, dict)
        ],
        "bond_missing_maturity_rows": (
            maturity.get("bond_missing_maturity_summary", {}).get("missing_maturity_rows")
            if isinstance(maturity.get("bond_missing_maturity_summary"), dict)
            else None
        ),
        "tyw_liability_missing_maturity_rows": (
            maturity.get("tyw_liability_missing_maturity_summary", {}).get("missing_maturity_rows")
            if isinstance(maturity.get("tyw_liability_missing_maturity_summary"), dict)
            else None
        ),
    }


def _closure_artifact_presence_summary(report: dict[str, object]) -> dict[str, object]:
    summary = report.get("artifact_current_summary", {})
    assert isinstance(summary, dict)
    return {
        "status": report.get("status"),
        "current": report.get("current"),
        "blockers": report.get("blockers", []),
        "artifact_current_summary": summary,
    }


def _handoff_completeness_summary(report: dict[str, object]) -> dict[str, object]:
    route_checks = report.get("route_checks", [])
    assert isinstance(route_checks, list)
    return {
        "status": report.get("status"),
        "handoff_ready": report.get("handoff_ready"),
        "blockers": report.get("blockers", []),
        "summary_current_status": report.get("summary_current_status", {}),
        "handoff_current_status": report.get("handoff_current_status", {}),
        "owner_route_coverage": report.get("owner_route_coverage", {}),
        "route_statuses": {
            str(route.get("owner")): route.get("status")
            for route in route_checks
            if isinstance(route, dict) and route.get("owner")
        },
        "evidence_scope": report.get("evidence_scope", {}),
    }


def owner_handoff_completeness_alignment(
    gate_summary: dict[str, object],
    handoff_summary: dict[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    if not gate_summary:
        blockers.append("owner_handoff_completeness_gate_summary_missing")
    if not handoff_summary:
        blockers.append("owner_handoff_completeness_detail_summary_missing")

    comparisons = [
        ("owner_handoff_completeness_status", "status"),
        ("owner_handoff_completeness_ready", "handoff_ready"),
        ("owner_handoff_completeness_blockers", "blockers"),
    ]
    for gate_field, handoff_field in comparisons:
        if gate_summary.get(gate_field) != handoff_summary.get(handoff_field):
            blockers.append(f"owner_handoff_completeness_alignment_{gate_field}_mismatch")
    return {
        "status": "consistent" if not blockers else "blocked",
        "blockers": blockers,
        "compared_fields": OWNER_HANDOFF_COMPLETENESS_ALIGNMENT_FIELDS,
    }


def verification_scope_summary(verification_report: dict[str, object]) -> dict[str, object]:
    result_count = verification_report.get("result_count")
    embedded_count = result_count if isinstance(result_count, int) else 0
    total_count = len(
        [item for item in VERIFICATION_COMMANDS if item["name"] != RUNNER_COMMAND_NAME],
    )
    all_commands_embedded = embedded_count == total_count
    return {
        "scope": "full" if all_commands_embedded else "limited",
        "embedded_result_count": embedded_count,
        "total_verification_command_count": total_count,
        "embedded_result_count_matches_report": (
            embedded_count == len(verification_report.get("results", []))
            if isinstance(verification_report.get("results"), list)
            else False
        ),
        "all_commands_embedded": all_commands_embedded,
        "full_verification_command": (
            "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched"
        ),
        "requires_full_verification_for_full_score": not all_commands_embedded,
        "proves_full_score_closure": False,
        "certification_effect": (
            "full_verifier_report_embedded"
            if all_commands_embedded
            else "limited_verifier_sample_only"
        ),
    }


def build_snapshot(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    scorecard_limit: int,
    verifier_limit: int | None,
    expected_state: str = "blocked",
    docs_root: Path = ROOT / "docs",
) -> dict[str, object]:
    scorecard_limit = validate_non_negative_portfolio_limit(
        scorecard_limit,
        label="scorecard limit",
    )
    if verifier_limit is not None:
        verifier_limit = validate_non_negative_portfolio_limit(
            verifier_limit,
            label="verifier limit",
        )
    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=scorecard_limit,
        docs_root=Path(docs_root),
    )
    approval_packet = build_business_owner_approval_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=scorecard_limit,
        docs_root=Path(docs_root),
    )
    intake_check = build_intake_check(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        limit=scorecard_limit,
    )
    verifier = build_report(
        limit=verifier_limit,
        expected_state=expected_state,
        docs_root=Path(docs_root),
    )
    artifact_presence = build_artifact_presence_report(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        limit=scorecard_limit,
    )
    handoff_completeness = build_handoff_completeness_report(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        limit=scorecard_limit,
    )
    approval_summary = approval_packet.get("approval_summary", {})
    assert isinstance(approval_summary, dict)
    approval_field_status = approval_summary.get("approval_field_status", {})
    assert isinstance(approval_field_status, dict)
    manifest_checks = approval_packet.get("manifest_consistency_checks", [])
    assert isinstance(manifest_checks, list)
    dependencies = approval_packet.get("evidence_dependencies", [])
    assert isinstance(dependencies, list)
    owner_summary_paths = {
        str(item.get("name")): item.get("path")
        for item in dependencies
        if isinstance(item, dict)
        and item.get("name")
        in {
            "krd_contract_decision_owner_summary",
            "maturity_remediation_owner_summary",
        }
    }
    owner_decision_summary = intake_check.get("owner_decision_summary", {})
    assert isinstance(owner_decision_summary, dict)
    krd_summary = owner_decision_summary.get("krd", {})
    maturity_summary = owner_decision_summary.get("maturity", {})
    decision_alignment = owner_decision_summary.get("decision_alignment", {})
    assert isinstance(krd_summary, dict)
    assert isinstance(maturity_summary, dict)
    assert isinstance(decision_alignment, dict)
    owner_decision_intake_summary = {
        "intake_status": intake_check.get("intake_status"),
        "intake_ready": intake_check.get("intake_ready"),
        "dependency_consistency_status": intake_check.get("dependency_consistency_status"),
        "dependency_csv_summary_alignment": intake_check.get(
            "dependency_csv_summary_alignment",
            {},
        ),
        "csv_check_summary": intake_check.get("csv_check_summary", {}),
        "generated_owner_fields_boundaries": intake_check.get(
            "generated_owner_fields_boundaries",
            {},
        ),
        "owner_input_boundary": intake_check.get("owner_input_boundary", {}),
        "export_current_summary": intake_check.get("export_current_summary", {}),
        "owner_decision_statuses": intake_check.get("owner_decision_statuses"),
        "owner_decision_blockers": intake_check.get("owner_decision_blockers", []),
        "decision_alignment": decision_alignment,
        "decision_counts": {
            "krd": krd_summary.get("decision_counts", {}),
            "maturity": maturity_summary.get("decision_counts", {}),
        },
        "decision_gap_counts": {
            "krd": krd_summary.get("decision_gap_counts", {}),
            "maturity": maturity_summary.get("decision_gap_counts", {}),
        },
        "note_gap_counts": {
            "krd": krd_summary.get("note_gap_counts", {}),
            "maturity": maturity_summary.get("comment_gap_counts", {}),
        },
        "exact_bucket_schema_evidence": krd_summary.get("exact_bucket_schema_evidence", {}),
        "nearest_bucket_approval_evidence": krd_summary.get(
            "nearest_bucket_approval_evidence",
            {},
        ),
        "maturity_scoped_exclusion_evidence": maturity_summary.get(
            "scoped_exclusion_evidence",
            {},
        ),
    }
    scorecard_owner_gate_summary = approval_packet.get(
        "scorecard_owner_decision_intake_gate_summary",
        {},
    )
    assert isinstance(scorecard_owner_gate_summary, dict)
    owner_intake_alignment = owner_decision_intake_alignment(
        owner_decision_intake_summary,
        scorecard_owner_gate_summary,
    )
    gate_summary = _gate_summary(scorecard)
    handoff_summary = _handoff_completeness_summary(
        handoff_completeness,
    )
    return {
        "snapshot_kind": "portfolio_home_closure_evidence",
        "page_id": scorecard["page_id"],
        "page_slug": scorecard["page_slug"],
        "report_date": scorecard["report_date"],
        "duckdb_path": scorecard["duckdb_path"],
        "template_path": scorecard["template_path"],
        "current_score": scorecard["current_score"],
        "remaining_gap": scorecard["remaining_gap"],
        "score_status": scorecard["score_status"],
        "full_score_ready": scorecard["full_score_ready"],
        "score_methodology": scorecard["score_methodology"],
        "score_blockers": scorecard["score_blockers"],
        "score_blocker_actions": scorecard["score_blocker_actions"],
        "gate_summary": gate_summary,
        "closure_artifact_presence_summary": _closure_artifact_presence_summary(
            artifact_presence,
        ),
        "handoff_completeness_summary": handoff_summary,
        "owner_handoff_completeness_alignment": owner_handoff_completeness_alignment(
            gate_summary,
            handoff_summary,
        ),
        "business_owner_approval_packet_summary": {
            "packet_status": approval_packet.get("packet_status"),
            "activation_ready": approval_packet.get("activation_ready"),
            "approval_action_item_count": approval_summary.get("approval_action_item_count"),
            "approval_field_status": {
                "approval_date": approval_field_status.get("approval_date"),
                "verification_commands_rerun": approval_field_status.get("verification_commands_rerun"),
                "evidence_scope_captures_business_owner_approval": approval_field_status.get(
                    "evidence_scope_captures_business_owner_approval",
                ),
            },
            "business_owner_approval_boundary": approval_packet.get(
                "business_owner_approval_boundary",
                {},
            ),
            "risk_warning_clean_status": approval_packet.get("risk_warning_clean_status"),
            "rerun_evidence_status": approval_packet.get("rerun_evidence_status"),
            "dependency_consistency_status": approval_packet.get("dependency_consistency_status"),
            "dependency_consistency_blockers": approval_packet.get(
                "dependency_consistency_blockers",
                [],
            ),
            "score_blocker_action_coverage": approval_packet.get(
                "score_blocker_action_coverage",
                {},
            ),
            "activation_guard": approval_packet.get("activation_guard", {}),
            "owner_decision_intake_alignment": owner_intake_alignment,
            "manifest_consistency_statuses": {
                str(item.get("name")): item.get("status")
                for item in manifest_checks
                if isinstance(item, dict)
            },
            "generated_owner_fields_boundaries": approval_packet.get(
                "generated_owner_fields_boundaries",
                {},
            ),
            "owner_summary_paths": owner_summary_paths,
            "csv_check_summary": _csv_check_summary(
                [item for item in manifest_checks if isinstance(item, dict)],
            ),
        },
        "owner_decision_intake_summary": owner_decision_intake_summary,
        "scorecard_owner_decision_intake_gate_summary": scorecard_owner_gate_summary,
        "owner_decision_intake_alignment": owner_intake_alignment,
        "verification_scope": verification_scope_summary(verifier),
        "verification_report": verifier,
    }


def _stabilize_self_referential_rerun_status(
    snapshot: dict[str, object],
    *,
    output: Path,
    docs_root: Path,
    report_date: str,
) -> dict[str, object]:
    expected_output = Path(docs_root) / Path(RERUN_EVIDENCE_ARTIFACT).relative_to("docs")
    if output.resolve() != expected_output.resolve():
        return snapshot
    summary = snapshot.get("business_owner_approval_packet_summary", {})
    if not isinstance(summary, dict):
        return snapshot
    gate_summary = snapshot.get("gate_summary", {})
    handoff_summary = snapshot.get("handoff_completeness_summary", {})
    if isinstance(gate_summary, dict) and isinstance(handoff_summary, dict):
        gate_summary["owner_handoff_completeness_status"] = handoff_summary.get("status")
        gate_summary["owner_handoff_completeness_ready"] = handoff_summary.get("handoff_ready")
        gate_summary["owner_handoff_completeness_blockers"] = handoff_summary.get("blockers", [])
        snapshot["owner_handoff_completeness_alignment"] = owner_handoff_completeness_alignment(
            gate_summary,
            handoff_summary,
        )
    if summary.get("business_owner_approval_boundary", {}).get("status") == "pending_owner_input":
        summary["business_owner_approval_boundary"] = dict(
            RERUN_APPROVAL_REQUIRED_BUSINESS_OWNER_BOUNDARY
        )
    summary["rerun_evidence_status"] = rerun_evidence_payload_status(
        snapshot,
        report_date=report_date,
    )
    return snapshot


def _is_self_referential_rerun_output(*, output: Path, docs_root: Path) -> bool:
    expected_output = Path(docs_root) / Path(RERUN_EVIDENCE_ARTIFACT).relative_to("docs")
    return output.resolve() == expected_output.resolve()


def _snapshot_current_status(output: Path, expected_snapshot: dict[str, object]) -> dict[str, object]:
    if not output.exists():
        actual_snapshot: dict[str, object] = {}
    else:
        try:
            parsed = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        actual_snapshot = parsed if isinstance(parsed, dict) else {}
    expected_hash = snapshot_sha256(expected_snapshot)
    actual_hash = snapshot_sha256(actual_snapshot)
    return {
        "artifact": str(output),
        "status": "current" if actual_hash == expected_hash else "stale",
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a portfolio-home evidence snapshot from scorecard and verifier output.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--scorecard-limit",
        type=lambda value: non_negative_portfolio_limit(value, label="scorecard limit"),
        default=3,
    )
    parser.add_argument(
        "--verifier-limit",
        type=lambda value: non_negative_portfolio_limit(value, label="verifier limit"),
        default=None,
    )
    parser.add_argument(
        "--expected-state",
        choices=("blocked", "full_score"),
        default="blocked",
    )
    parser.add_argument(
        "--require-verifier-matched",
        action="store_true",
        help="Return non-zero unless the embedded verifier report matches the selected expected state.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path for a rerun evidence artifact.",
    )
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Return non-zero unless the output artifact matches the freshly built snapshot.",
    )
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        scorecard_limit=int(args.scorecard_limit),
        verifier_limit=args.verifier_limit,
        expected_state=str(args.expected_state),
        docs_root=Path(args.docs_root),
    )
    if args.output is not None:
        output = Path(args.output)
        snapshot = _stabilize_self_referential_rerun_status(
            snapshot,
            output=output,
            docs_root=Path(args.docs_root),
            report_date=str(args.report_date),
        )
        if args.check_current:
            status = _snapshot_current_status(output, snapshot)
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0 if status["status"] == "current" else 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        if _is_self_referential_rerun_output(output=output, docs_root=Path(args.docs_root)):
            snapshot = build_snapshot(
                duckdb_path=Path(args.duckdb_path),
                report_date=str(args.report_date),
                template_path=Path(args.template_path),
                scorecard_limit=int(args.scorecard_limit),
                verifier_limit=args.verifier_limit,
                expected_state=str(args.expected_state),
                docs_root=Path(args.docs_root),
            )
            snapshot = _stabilize_self_referential_rerun_status(
                snapshot,
                output=output,
                docs_root=Path(args.docs_root),
                report_date=str(args.report_date),
            )
            output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    verifier = snapshot["verification_report"]
    assert isinstance(verifier, dict)
    if args.require_verifier_matched and not verifier["all_matched_expected_exit"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
