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
    DEFAULT_MATRIX,
    DEFAULT_SNAPSHOT,
    build_packet as build_owner_packet,
)
from scripts.refresh_calculation_p1_owner_decision_snapshot import (  # noqa: E402
    CAPTURED_DECISION_STATUSES,
    DEFAULT_CAPTURE_TEMPLATE,
    _capture_rows,
    _incomplete_capture_fields,
    _section,
)
from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-calculation-p1-post-owner-execution-plan.md"
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

PROHIBITED_ACTIONS = [
    "treat approved-for-implementation rows as metric approval",
    "execute a row before selected_decision, owner_rationale, implementation_owner, verification_gate, and status are captured",
    "execute implementation when the meeting record is incomplete",
    "choose a convention for any pending, deferred, rejected, or invalid row",
    "write governance records or authorize Ledger PnL --write from this plan",
]
POST_OWNER_REQUIRED_FIELDS = [
    "selected_decision",
    "owner_rationale",
    "implementation_owner",
    "verification_gate",
    "status",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool_text(value: bool) -> str:
    return str(value).lower()


def _capture_rows_from_template(path: Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    return _capture_rows(_section(text, "## 10", "## 7"))


def _row_status(row: dict[str, Any]) -> str:
    return str(row.get("status", "")).strip().lower()


def _is_complete_owner_row(row: dict[str, Any]) -> bool:
    return all(
        str(row.get(field, "")).strip()
        for field in (
            "selected_decision",
            "owner_rationale",
            "implementation_owner",
            "verification_gate",
        )
    ) and _row_status(row) in CAPTURED_DECISION_STATUSES


def _status_bucket(row: dict[str, Any], missing_capture_fields: list[str]) -> str:
    if missing_capture_fields:
        return "incomplete"
    status = _row_status(row)
    if not _is_complete_owner_row(row):
        return "incomplete"
    if status == "approved-for-implementation":
        return "ready_for_implementation"
    if status == "deferred":
        return "deferred"
    if status == "rejected":
        return "rejected"
    return "incomplete"


def build_plan(
    *,
    matrix_path: Path = DEFAULT_MATRIX,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    capture_template_path: Path = DEFAULT_CAPTURE_TEMPLATE,
) -> dict[str, Any]:
    snapshot = _load_json(Path(snapshot_path))
    owner_packet = build_owner_packet(
        matrix_path=matrix_path,
        snapshot_path=snapshot_path,
    )
    capture_rows = _capture_rows_from_template(Path(capture_template_path))
    capture_by_id = {row["id"]: row for row in capture_rows}
    capture = snapshot.get("capture_template", {})
    meeting_record = snapshot.get("meeting_record", {})
    snapshot_status = snapshot.get("status", {}).get("overall")
    candidate_options_by_id = snapshot.get("matrix", {}).get("candidate_options_by_id") or {}
    snapshot_incomplete_fields_by_id = capture.get("incomplete_fields_by_id") or {}
    live_incomplete_fields_by_id = {
        row["id"]: _incomplete_capture_fields(
            row,
            allowed_options=dict(candidate_options_by_id.get(row["id"], {})),
        )
        for row in capture_rows
        if _incomplete_capture_fields(
            row,
            allowed_options=dict(candidate_options_by_id.get(row["id"], {})),
        )
    }
    incomplete_fields_by_id = {
        p1_id: list(
            dict.fromkeys(
                list(snapshot_incomplete_fields_by_id.get(p1_id, []))
                + list(live_incomplete_fields_by_id.get(p1_id, []))
            )
        )
        for p1_id in EXPECTED_OPEN_CALCULATION_P1_IDS
        if snapshot_incomplete_fields_by_id.get(p1_id)
        or live_incomplete_fields_by_id.get(p1_id)
    }
    invalid_status_by_id = capture.get("invalid_status_by_id") or {}
    invalid_selected_decision_by_id = capture.get("invalid_selected_decision_by_id") or {}
    packet_items = {
        item["p1_id"]: item for item in owner_packet.get("decision_items", [])
    }

    items = []
    for p1_id in EXPECTED_OPEN_CALCULATION_P1_IDS:
        row = capture_by_id.get(p1_id, {"id": p1_id})
        packet_item = packet_items.get(p1_id, {})
        execution_slice = packet_item.get("post_decision_execution_slice", {})
        missing_capture_fields = list(incomplete_fields_by_id.get(p1_id, []))
        bucket = (
            _status_bucket(row, missing_capture_fields)
            if snapshot_status == "owner_decision_required"
            else "incomplete"
        )
        items.append(
            {
                "p1_id": p1_id,
                "status": _row_status(row) or "pending",
                "bucket": bucket,
                "selected_decision": str(row.get("selected_decision", "")).strip(),
                "invalid_selected_decision": invalid_selected_decision_by_id.get(p1_id),
                "owner_rationale_present": bool(
                    str(row.get("owner_rationale", "")).strip()
                ),
                "implementation_owner": str(
                    row.get("implementation_owner", "")
                ).strip(),
                "verification_gate": str(row.get("verification_gate", "")).strip(),
                "owner_decision_gate": str(
                    packet_item.get("closure_evidence", "")
                ).strip(),
                "missing_capture_fields": missing_capture_fields,
                "execution_slice": execution_slice.get("implementation_slice", ""),
                "referenced_paths": list(execution_slice.get("referenced_paths") or []),
                "missing_referenced_paths": list(
                    execution_slice.get("missing_referenced_paths") or []
                ),
            }
        )

    queues = {
        "ready_for_implementation": [
            item for item in items if item["bucket"] == "ready_for_implementation"
        ],
        "deferred": [item for item in items if item["bucket"] == "deferred"],
        "rejected": [item for item in items if item["bucket"] == "rejected"],
        "incomplete": [item for item in items if item["bucket"] == "incomplete"],
    }
    owner_decision_capture_complete = (
        snapshot_status == "owner_decision_required"
        and capture.get("captured_decision_count") == capture.get("row_count")
        and meeting_record.get("is_complete") is True
        and not incomplete_fields_by_id
        and not invalid_status_by_id
        and not invalid_selected_decision_by_id
    )
    non_implementation_decision_count = len(queues["deferred"]) + len(queues["rejected"])
    post_owner_blocking_reasons: list[str] = []
    if not owner_decision_capture_complete:
        post_owner_blocking_reasons.append("owner_decision_capture_incomplete")
    if non_implementation_decision_count:
        post_owner_blocking_reasons.append("non_implementation_decisions_present")
    if any(item["missing_referenced_paths"] for item in items):
        post_owner_blocking_reasons.append("missing_execution_referenced_paths")

    global_owner_decision_gate_ready = owner_decision_capture_complete
    implementation_ready = (
        global_owner_decision_gate_ready
        and bool(queues["ready_for_implementation"])
        and non_implementation_decision_count == 0
        and not any(item["missing_referenced_paths"] for item in items)
    )

    return {
        "packet_kind": "calculation_p1_post_owner_execution_plan",
        "audit_date": AUDIT_DATE,
        "source_artifacts": {
            "calculation_owner_decision_snapshot": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
            ),
            "owner_decision_capture_template_zh": (
                f"docs/audits/{AUDIT_DATE}-owner-decision-capture-template.zh.md"
            ),
            "calculation_owner_decision_packet": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-packet.md"
            ),
            "calculation_owner_meeting_checklist": (
                f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-meeting-checklist.md"
            ),
        },
        "source_snapshot_generated_at": snapshot.get("generated_at"),
        "source_snapshot_status": snapshot_status,
        "owner_decision_capture_complete": owner_decision_capture_complete,
        "global_owner_decision_gate_ready": global_owner_decision_gate_ready,
        "implementation_ready": implementation_ready,
        "meeting_record_complete": bool(meeting_record.get("is_complete")),
        "missing_meeting_field_count": len(
            meeting_record.get("missing_required_fields") or []
        ),
        "captured_decision_count": capture.get("captured_decision_count"),
        "row_count": capture.get("row_count"),
        "invalid_status_count": len(invalid_status_by_id),
        "invalid_selected_decision_count": len(invalid_selected_decision_by_id),
        "live_template_incomplete_count": len(live_incomplete_fields_by_id),
        "post_owner_required_fields": list(POST_OWNER_REQUIRED_FIELDS),
        "ready_for_implementation_count": len(queues["ready_for_implementation"]),
        "deferred_count": len(queues["deferred"]),
        "rejected_count": len(queues["rejected"]),
        "non_implementation_decision_count": non_implementation_decision_count,
        "incomplete_count": len(queues["incomplete"]),
        "post_owner_blocking_reasons": post_owner_blocking_reasons,
        "queues": queues,
        "items": items,
        "readiness_checks": {
            "decision_ids_match_expected": [item["p1_id"] for item in items]
            == EXPECTED_OPEN_CALCULATION_P1_IDS,
            "all_execution_slice_paths_exist": not any(
                item["missing_referenced_paths"] for item in items
            ),
            "no_invalid_statuses": not invalid_status_by_id,
            "no_invalid_selected_decisions": not invalid_selected_decision_by_id,
            "source_snapshot_is_owner_decision_required": (
                snapshot_status == "owner_decision_required"
            ),
            "live_template_matches_snapshot_missing_fields": (
                live_incomplete_fields_by_id == snapshot_incomplete_fields_by_id
            ),
            "owner_decision_capture_complete": owner_decision_capture_complete,
            "non_implementation_decisions_present": non_implementation_decision_count > 0,
            "global_owner_decision_gate_ready": global_owner_decision_gate_ready,
            "implementation_ready": implementation_ready,
            "captures_owner_decisions": False,
            "chooses_or_approves_conventions": False,
            "changes_implementation_code": False,
        },
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "boundary": (
            "This plan is a read-only post-owner execution router. It only classifies "
            "captured rows into execution queues and lists existing engineering anchors; "
            "it does not choose or approve conventions, capture owner decisions, change "
            "code, write DuckDB or governance records, approve metrics/pages, authorize "
            "Ledger PnL --write, certify routes, or clear secrets."
        ),
    }


def _join_backtick(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def render_markdown(plan: dict[str, Any]) -> str:
    source_rows = "\n".join(
        f"- `{key}`: `{value}`" for key, value in plan["source_artifacts"].items()
    )
    check_rows = "\n".join(
        f"- `{key}={_bool_text(value) if isinstance(value, bool) else value}`"
        for key, value in plan["readiness_checks"].items()
    )
    item_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | `{item['status']}` | `{item['bucket']}` | "
            f"{item['implementation_owner'] or 'none'} | "
            f"{item['verification_gate'] or 'none'} | "
            f"{item['invalid_selected_decision'] or 'none'} | "
            f"{_join_backtick(item['missing_capture_fields'])} | "
            f"{item['owner_decision_gate'] or 'none'} | "
            f"{len(item['referenced_paths'])} | {_join_backtick(item['missing_referenced_paths'])} |"
        )
        for item in plan["items"]
    )
    queue_rows = "\n".join(
        (
            f"| `{queue_name}` | {len(queue_items)} | "
            f"{_join_backtick([item['p1_id'] for item in queue_items])} |"
        )
        for queue_name, queue_items in plan["queues"].items()
    )
    prohibited = "\n".join(f"- {action}" for action in plan["prohibited_actions"])
    scope = "\n".join(
        f"- `{key}={_bool_text(value) if isinstance(value, bool) else value}`"
        for key, value in plan["evidence_scope"].items()
    )

    return f"""# Calculation P1 Post-Owner Execution Plan

Source snapshot status: `source_snapshot_status={plan['source_snapshot_status']}`
Global owner gate ready: `{_bool_text(plan['global_owner_decision_gate_ready'])}`
Implementation ready: `{_bool_text(plan['implementation_ready'])}`
Source snapshot generated at: `{plan['source_snapshot_generated_at']}`

This plan prepares deterministic execution routing after owner/governance input is captured. It does not select or approve any calculation convention.

## Summary

- `row_count={plan['row_count']}`
- `captured_decision_count={plan['captured_decision_count']}`
- `post_owner_required_fields={', '.join(plan['post_owner_required_fields'])}`
- `ready_for_implementation_count={plan['ready_for_implementation_count']}`
- `deferred_count={plan['deferred_count']}`
- `rejected_count={plan['rejected_count']}`
- `non_implementation_decision_count={plan['non_implementation_decision_count']}`
- `incomplete_count={plan['incomplete_count']}`
- `post_owner_blocking_reasons={', '.join(plan['post_owner_blocking_reasons']) or 'none'}`
- `meeting_record_complete={_bool_text(plan['meeting_record_complete'])}`
- `missing_meeting_field_count={plan['missing_meeting_field_count']}`
- `invalid_status_count={plan['invalid_status_count']}`
- `invalid_selected_decision_count={plan['invalid_selected_decision_count']}`
- `global_owner_decision_gate_ready={_bool_text(plan['global_owner_decision_gate_ready'])}`
- `implementation_ready={_bool_text(plan['implementation_ready'])}`

## Source Artifacts

{source_rows}

## Readiness Checks

{check_rows}

## Execution Queues

| Queue | Count | P1 IDs |
| --- | ---: | --- |
{queue_rows}

## Row Routing

| P1 | Status | Queue | Implementation owner | Verification gate | Invalid selected decision | Missing capture fields | Owner decision gate | Referenced path count | Missing referenced paths |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |
{item_rows}

## Prohibited Actions

{prohibited}

## Evidence Scope

{scope}

## Boundary

{plan['boundary']}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the read-only Calculation P1 post-owner execution plan.",
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--capture-template", type=Path, default=DEFAULT_CAPTURE_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-implementation-ready",
        action="store_true",
        help=(
            "Exit non-zero unless the post-owner execution plan is ready to implement. "
            "This is stricter than owner-decision capture: deferred/rejected rows, "
            "missing anchors, or incomplete capture keep it blocked."
        ),
    )
    args = parser.parse_args(argv)

    plan = build_plan(
        matrix_path=args.matrix,
        snapshot_path=args.snapshot,
        capture_template_path=args.capture_template,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(plan), encoding="utf-8")
    payload = {
        "packet_kind": plan["packet_kind"],
        "packet_path": str(output_path),
        "source_snapshot_status": plan["source_snapshot_status"],
        "owner_decision_capture_complete": plan["owner_decision_capture_complete"],
        "global_owner_decision_gate_ready": plan["global_owner_decision_gate_ready"],
        "implementation_ready": plan["implementation_ready"],
        "ready_for_implementation_count": plan["ready_for_implementation_count"],
        "deferred_count": plan["deferred_count"],
        "rejected_count": plan["rejected_count"],
        "non_implementation_decision_count": plan[
            "non_implementation_decision_count"
        ],
        "incomplete_count": plan["incomplete_count"],
        "post_owner_blocking_reasons": plan["post_owner_blocking_reasons"],
        "meeting_record_complete": plan["meeting_record_complete"],
        "invalid_selected_decision_count": plan["invalid_selected_decision_count"],
        "evidence_scope": plan["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.require_implementation_ready and plan["implementation_ready"] is not True:
        print(
            (
                "Calculation P1 post-owner execution plan is not implementation-ready: "
                f"owner_decision_capture_complete={plan['owner_decision_capture_complete']}, "
                f"ready_for_implementation_count={plan['ready_for_implementation_count']}, "
                f"non_implementation_decision_count={plan['non_implementation_decision_count']}, "
                f"incomplete_count={plan['incomplete_count']}, "
                "post_owner_blocking_reasons="
                f"{plan['post_owner_blocking_reasons']}"
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
