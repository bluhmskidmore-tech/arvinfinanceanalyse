from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calculation_p1_owner_decision_packet import (  # noqa: E402
    AUDIT_DATE,
    DEFAULT_SNAPSHOT,
    build_packet as build_owner_packet,
)
from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-calculation-p1-owner-meeting-checklist.md"
)

EVIDENCE_SCOPE = {
    "read_only": True,
    "chooses_or_approves_conventions": False,
    "changes_code": False,
    "writes_duckdb": False,
    "writes_governance_records": False,
    "approves_metrics": False,
    "approves_pages": False,
    "captures_business_owner_approval": False,
    "captures_owner_decisions": False,
    "certifies_routes": False,
    "authorizes_ledger_pnl_governance_write": False,
}

POST_MEETING_REQUIRED_FIELDS = [
    "selected_decision",
    "owner_rationale",
    "implementation_owner",
    "verification_gate",
    "status",
]

POST_MEETING_ALLOWED_STATUSES = [
    "approved-for-implementation",
    "deferred",
    "rejected",
]

PROHIBITED_ACTIONS = [
    "treat this checklist as owner approval",
    "select proposed review defaults without business owner and metric governance input",
    "start implementation before the selected decision and owner rationale are captured",
    "count a pending row as a captured owner decision",
    "write governance records or authorize Ledger PnL --write from this checklist",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool_text(value: bool) -> str:
    return str(value).lower()


def build_checklist(
    *,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any]:
    owner_packet = build_owner_packet(snapshot_path=snapshot_path)
    snapshot = _load_json(Path(snapshot_path))
    capture_template = snapshot.get("capture_template", {})
    meeting_record = snapshot.get("meeting_record", {})

    items = []
    for item in owner_packet["decision_items"]:
        missing_fields = list(item.get("missing_capture_fields") or [])
        items.append(
            {
                "p1_id": item["p1_id"],
                "priority_rank": item["priority_rank"],
                "area": item["area"],
                "owner_question": item["decision_needed"],
                "candidate_decisions": item["candidate_decisions"],
                "allowed_candidate_options": dict(
                    item.get("allowed_candidate_options", {})
                ),
                "proposed_review_default_for_discussion": item[
                    "proposed_review_default"
                ],
                "impact_if_unresolved": item["impact_if_unresolved"],
                "closure_evidence": item["closure_evidence"],
                "missing_capture_fields": missing_fields,
                "missing_capture_field_count": len(missing_fields),
                "owner_decision_gate": item["closure_evidence"],
                "post_decision_execution_slice": item[
                    "post_decision_execution_slice"
                ].get("implementation_slice", ""),
            }
        )

    decision_ids = [item["p1_id"] for item in items]
    total_missing_capture_fields = sum(
        item["missing_capture_field_count"] for item in items
    )
    missing_meeting_fields = list(meeting_record.get("missing_required_fields") or [])
    execution_anchor_ready = bool(owner_packet.get("execution_anchor_ready"))

    return {
        "packet_kind": "calculation_p1_owner_meeting_checklist",
        "audit_date": AUDIT_DATE,
        "source_artifacts": {
            "calculation_owner_decision_matrix": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-matrix.md"
            ),
            "calculation_owner_decision_snapshot": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
            ),
            "calculation_owner_decision_packet": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-packet.md"
            ),
            "owner_decision_capture_template_zh": (
                f"docs/audits/{AUDIT_DATE}-owner-decision-capture-template.zh.md"
            ),
        },
        "source_snapshot_status": snapshot.get("status", {}).get("overall"),
        "owner_meeting_material_ready": (
            owner_packet.get("decision_item_count") == len(EXPECTED_OPEN_CALCULATION_P1_IDS)
            and owner_packet.get("pending_decision_count")
            == len(EXPECTED_OPEN_CALCULATION_P1_IDS)
            and capture_template.get("captured_decision_count") == 0
            and decision_ids == EXPECTED_OPEN_CALCULATION_P1_IDS
            and execution_anchor_ready
        ),
        "implementation_ready": False,
        "decision_item_count": len(items),
        "pending_decision_count": owner_packet.get("pending_decision_count"),
        "captured_decision_count": capture_template.get("captured_decision_count"),
        "incomplete_decision_count": capture_template.get("incomplete_decision_count"),
        "total_missing_capture_field_count": total_missing_capture_fields,
        "meeting_missing_field_count": len(missing_meeting_fields),
        "meeting_record_complete": bool(meeting_record.get("is_complete")),
        "execution_anchor_ready": execution_anchor_ready,
        "execution_referenced_path_count": owner_packet.get(
            "execution_referenced_path_count"
        ),
        "missing_execution_referenced_path_count": len(
            owner_packet.get("missing_execution_referenced_paths") or []
        ),
        "decision_ids": decision_ids,
        "post_meeting_required_fields": list(POST_MEETING_REQUIRED_FIELDS),
        "post_meeting_allowed_statuses": list(POST_MEETING_ALLOWED_STATUSES),
        "capture_validation_rule": owner_packet.get("capture_validation_rule"),
        "items": items,
        "readiness_checks": {
            "decision_ids_match_expected": decision_ids
            == EXPECTED_OPEN_CALCULATION_P1_IDS,
            "all_rows_pending_owner_decision": owner_packet.get(
                "pending_decision_count"
            )
            == len(EXPECTED_OPEN_CALCULATION_P1_IDS),
            "captured_decision_count_is_zero": capture_template.get(
                "captured_decision_count"
            )
            == 0,
            "meeting_record_is_incomplete": meeting_record.get("is_complete") is False,
            "execution_anchor_ready": execution_anchor_ready,
            "captures_owner_decisions": False,
            "chooses_or_approves_conventions": False,
            "changes_implementation_code": False,
        },
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "boundary": (
            "This checklist is read-only owner-meeting preparation. It asks what must "
            "be decided, lists candidate options from the P1 matrix, and records missing "
            "capture fields; it does not choose or approve calculation conventions, "
            "capture owner decisions, change code, approve metrics or pages, write "
            "governance records, authorize Ledger PnL --write, certify routes, or "
            "clear secrets."
        ),
    }


def _join_backtick(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def render_markdown(checklist: dict[str, Any]) -> str:
    source_rows = "\n".join(
        f"- `{key}`: `{value}`" for key, value in checklist["source_artifacts"].items()
    )
    check_rows = "\n".join(
        f"- `{key}={_bool_text(value) if isinstance(value, bool) else value}`"
        for key, value in checklist["readiness_checks"].items()
    )
    decision_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | {item['priority_rank']} | {item['area']} | "
            f"{item['owner_question']} | {item['candidate_decisions']} | "
            f"{item['proposed_review_default_for_discussion']} | "
            f"{_join_backtick(item['missing_capture_fields'])} | "
            f"{item['owner_decision_gate']} |"
        )
        for item in checklist["items"]
    )
    option_contract_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | "
            f"{'<br>'.join(f'`Option {letter}`: {description}' for letter, description in item['allowed_candidate_options'].items())} | "
            "`Option <allowed letter> - <copied option description>` |"
        )
        for item in checklist["items"]
    )
    closure_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | {item['impact_if_unresolved']} | "
            f"{item['closure_evidence']} | {item['post_decision_execution_slice']} |"
        )
        for item in checklist["items"]
    )
    prohibited = "\n".join(f"- {item}" for item in checklist["prohibited_actions"])
    scope = "\n".join(
        f"- `{key}={_bool_text(value) if isinstance(value, bool) else value}`"
        for key, value in checklist["evidence_scope"].items()
    )

    return f"""# Calculation P1 Owner Meeting Checklist

Source snapshot status: `source_snapshot_status={checklist['source_snapshot_status']}`
Owner meeting material ready: `{_bool_text(checklist['owner_meeting_material_ready'])}`
Implementation ready: `{_bool_text(checklist['implementation_ready'])}`
Execution anchor ready: `{_bool_text(checklist['execution_anchor_ready'])}`

This checklist prepares the owner/governance meeting for the `calculation-display-p1-decisions` blocker. It does not select a convention, approve a metric, or close any P1 row.

## Summary

- `decision_item_count={checklist['decision_item_count']}`
- `pending_decision_count={checklist['pending_decision_count']}`
- `captured_decision_count={checklist['captured_decision_count']}`
- `incomplete_decision_count={checklist['incomplete_decision_count']}`
- `total_missing_capture_field_count={checklist['total_missing_capture_field_count']}`
- `meeting_missing_field_count={checklist['meeting_missing_field_count']}`
- `meeting_record_complete={_bool_text(checklist['meeting_record_complete'])}`
- `execution_referenced_path_count={checklist['execution_referenced_path_count']}`
- `missing_execution_referenced_path_count={checklist['missing_execution_referenced_path_count']}`
- `post_meeting_required_fields={', '.join(checklist['post_meeting_required_fields'])}`
- `post_meeting_allowed_statuses={', '.join(checklist['post_meeting_allowed_statuses'])}`

## Source Artifacts

{source_rows}

## Readiness Checks

{check_rows}

## Owner Questions

| P1 | Rank | Area | Owner question | Candidate decisions | Proposed review default for discussion | Missing capture fields | Owner decision gate |
| --- | ---: | --- | --- | --- | --- | --- | --- |
{decision_rows}

## Candidate Option Contract

{checklist['capture_validation_rule']}

Allowed option letters are row-specific; some P1 rows only allow `Option A` and `Option B`. For `approved-for-implementation`, use the required capture format below rather than evidence-only wording. The format example is not a recommended option and does not approve any listed candidate.

| P1 | Allowed candidate options | Required capture format, not a recommendation |
| --- | --- | --- |
{option_contract_rows}

## Closure Evidence And Engineering Handoff

| P1 | Impact if unresolved | Closure evidence after owner input | Post-decision execution slice |
| --- | --- | --- | --- |
{closure_rows}

## Post-Meeting Capture Rule

Every row must have `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, and a `status` of `approved-for-implementation`, `deferred`, or `rejected` before the strict owner-decision capture gate can pass. For `approved-for-implementation`, `selected_decision` must use a row-specific allowed option and substantive text matching the option description. A populated checklist is still not metric approval; approved rows must be copied into the authoritative rule or contract location and verified with targeted tests.

## Prohibited Actions

{prohibited}

## Evidence Scope

{scope}

## Boundary

{checklist['boundary']}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the read-only Calculation P1 owner meeting checklist.",
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    checklist = build_checklist(snapshot_path=args.snapshot)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(checklist), encoding="utf-8")
    payload = {
        "packet_kind": checklist["packet_kind"],
        "packet_path": str(output_path),
        "source_snapshot_status": checklist["source_snapshot_status"],
        "owner_meeting_material_ready": checklist["owner_meeting_material_ready"],
        "implementation_ready": checklist["implementation_ready"],
        "decision_item_count": checklist["decision_item_count"],
        "pending_decision_count": checklist["pending_decision_count"],
        "captured_decision_count": checklist["captured_decision_count"],
        "total_missing_capture_field_count": checklist[
            "total_missing_capture_field_count"
        ],
        "meeting_missing_field_count": checklist["meeting_missing_field_count"],
        "execution_anchor_ready": checklist["execution_anchor_ready"],
        "evidence_scope": checklist["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
