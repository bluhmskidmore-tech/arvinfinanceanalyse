from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_evidence_snapshot import (  # noqa: E402
    OWNER_HANDOFF_COMPLETENESS_ALIGNMENT_FIELDS,
    owner_handoff_completeness_alignment,
)
from scripts.portfolio_home_business_owner_approval_packet import (  # noqa: E402
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    owner_decision_intake_alignment,
)
from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    DEFAULT_REPORT_DATE,
    PORTFOLIO_HOME_PAGE_ID,
    PORTFOLIO_HOME_PAGE_SLUG,
    PORTFOLIO_HOME_SNAPSHOT_KIND,
)
from scripts.portfolio_home_verification_report_guard import (  # noqa: E402
    blocked_verification_report_guard,
)


DEFAULT_SNAPSHOT = ROOT / "docs" / "portfolio" / "portfolio-home-evidence-snapshot.json"


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def build_report(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    *,
    report_date: str = DEFAULT_REPORT_DATE,
) -> dict[str, object]:
    blockers: list[str] = []
    payload: dict[str, object] = {}
    path = Path(snapshot_path)
    if not path.exists():
        blockers.append("evidence_snapshot_missing")
    else:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
            blockers.append("evidence_snapshot_invalid_json")
        payload = parsed if isinstance(parsed, dict) else {}
        if not payload and "evidence_snapshot_invalid_json" not in blockers:
            blockers.append("evidence_snapshot_invalid_payload")

    if payload:
        if payload.get("snapshot_kind") != PORTFOLIO_HOME_SNAPSHOT_KIND:
            blockers.append("evidence_snapshot_kind_mismatch")
        if payload.get("page_id") != PORTFOLIO_HOME_PAGE_ID:
            blockers.append("evidence_snapshot_page_id_mismatch")
        if payload.get("page_slug") != PORTFOLIO_HOME_PAGE_SLUG:
            blockers.append("evidence_snapshot_page_slug_mismatch")
        if payload.get("report_date") != report_date:
            blockers.append("evidence_snapshot_report_date_mismatch")

    gate_summary = _dict(payload.get("gate_summary"))
    handoff_summary = _dict(payload.get("handoff_completeness_summary"))
    expected_alignment = owner_handoff_completeness_alignment(gate_summary, handoff_summary)
    actual_alignment = _dict(payload.get("owner_handoff_completeness_alignment"))
    if not actual_alignment:
        blockers.append("owner_handoff_completeness_alignment_missing")
    elif actual_alignment != expected_alignment:
        blockers.append("owner_handoff_completeness_alignment_mismatch")
    if actual_alignment and actual_alignment.get("status") != "consistent":
        blockers.append("owner_handoff_completeness_alignment_not_consistent")
    if actual_alignment and actual_alignment.get("blockers") != []:
        blockers.append("owner_handoff_completeness_alignment_has_blockers")
    if actual_alignment and (
        actual_alignment.get("compared_fields") != OWNER_HANDOFF_COMPLETENESS_ALIGNMENT_FIELDS
    ):
        blockers.append("owner_handoff_completeness_alignment_fields_mismatch")

    owner_direct_summary = _dict(payload.get("owner_decision_intake_summary"))
    owner_gate_summary = _dict(payload.get("scorecard_owner_decision_intake_gate_summary"))
    expected_owner_alignment = owner_decision_intake_alignment(
        owner_direct_summary,
        owner_gate_summary,
    )
    actual_owner_alignment = _dict(payload.get("owner_decision_intake_alignment"))
    approval_summary = _dict(payload.get("business_owner_approval_packet_summary"))
    approval_owner_alignment = _dict(approval_summary.get("owner_decision_intake_alignment"))

    if not owner_direct_summary:
        blockers.append("owner_decision_intake_summary_missing")
    if not owner_gate_summary:
        blockers.append("scorecard_owner_decision_intake_gate_summary_missing")
    if not actual_owner_alignment:
        blockers.append("owner_decision_intake_alignment_missing")
    elif actual_owner_alignment != expected_owner_alignment:
        blockers.append("owner_decision_intake_alignment_mismatch")
    if actual_owner_alignment and actual_owner_alignment.get("status") != "consistent":
        blockers.append("owner_decision_intake_alignment_not_consistent")
    if actual_owner_alignment and actual_owner_alignment.get("blockers") != []:
        blockers.append("owner_decision_intake_alignment_has_blockers")
    if actual_owner_alignment and (
        actual_owner_alignment.get("compared_fields") != OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS
    ):
        blockers.append("owner_decision_intake_alignment_fields_mismatch")

    if gate_summary.get("owner_decision_intake_alignment_status") != actual_owner_alignment.get(
        "status",
    ):
        blockers.append("gate_summary_owner_decision_intake_alignment_status_mismatch")
    if gate_summary.get("owner_decision_intake_alignment_blockers") != actual_owner_alignment.get(
        "blockers",
    ):
        blockers.append("gate_summary_owner_decision_intake_alignment_blockers_mismatch")

    if not approval_summary:
        blockers.append("business_owner_approval_packet_summary_missing")
    if not approval_owner_alignment:
        blockers.append("approval_summary_owner_decision_intake_alignment_missing")
    elif approval_owner_alignment != expected_owner_alignment:
        blockers.append("approval_summary_owner_decision_intake_alignment_mismatch")

    approval_action_coverage = _dict(approval_summary.get("score_blocker_action_coverage"))
    gate_action_coverage = {
        "status": gate_summary.get("score_blocker_action_coverage_status"),
        "blockers": gate_summary.get("score_blocker_action_coverage_blockers"),
        "unassigned_blockers": gate_summary.get(
            "score_blocker_action_coverage_unassigned_blockers",
        ),
    }
    if not approval_action_coverage:
        blockers.append("approval_summary_score_blocker_action_coverage_missing")
    else:
        actual_action_coverage = {
            "status": approval_action_coverage.get("status"),
            "blockers": approval_action_coverage.get("blockers"),
            "unassigned_blockers": approval_action_coverage.get("unassigned_blockers"),
        }
        if actual_action_coverage != gate_action_coverage:
            blockers.append("approval_summary_score_blocker_action_coverage_mismatch")

    approval_dependency_status = approval_summary.get("dependency_consistency_status")
    approval_dependency_blockers = approval_summary.get("dependency_consistency_blockers")
    if approval_dependency_status is None:
        blockers.append("approval_summary_dependency_consistency_status_missing")
    elif approval_dependency_status != gate_summary.get("approval_dependency_consistency_status"):
        blockers.append("approval_summary_dependency_consistency_status_mismatch")
    if approval_dependency_blockers is None:
        blockers.append("approval_summary_dependency_consistency_blockers_missing")
    elif approval_dependency_blockers != gate_summary.get("approval_dependency_consistency_blockers"):
        blockers.append("approval_summary_dependency_consistency_blockers_mismatch")

    verification_guard = blocked_verification_report_guard(payload.get("verification_report"))
    blockers.extend(str(blocker) for blocker in verification_guard["blockers"])
    embedded_verifier_summary = verification_guard["summary"]

    return {
        "check_kind": "portfolio_home_evidence_snapshot_alignment",
        "artifact": str(path),
        "status": "clean" if not blockers else "blocked",
        "valid": not blockers,
        "blockers": blockers,
        "expected_alignment": expected_alignment,
        "actual_alignment": actual_alignment,
        "expected_owner_decision_intake_alignment": expected_owner_alignment,
        "actual_owner_decision_intake_alignment": actual_owner_alignment,
        "approval_summary_owner_decision_intake_alignment": approval_owner_alignment,
        "expected_score_blocker_action_coverage": gate_action_coverage,
        "approval_summary_score_blocker_action_coverage": approval_action_coverage,
        "embedded_verifier_summary": embedded_verifier_summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home evidence snapshot summary/detail alignment.",
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless snapshot alignment is clean.",
    )
    args = parser.parse_args(argv)

    report = build_report(Path(args.snapshot), report_date=str(args.report_date))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_clean and report["status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
