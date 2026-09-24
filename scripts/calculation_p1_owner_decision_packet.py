from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    EXPECTED_OPEN_CALCULATION_P1_IDS,
)


AUDIT_DATE = "2026-06-10"
DEFAULT_MATRIX = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-matrix.md"
)
DEFAULT_SNAPSHOT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
)
DEFAULT_OUTPUT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-calculation-p1-owner-decision-packet.md"
)

SOURCE_ARTIFACTS = {
    "calculation_logic_audit": f"docs/audits/{AUDIT_DATE}-calculation-logic-audit.md",
    "calculation_owner_decision_matrix": (
        f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-matrix.md"
    ),
    "calculation_owner_decision_snapshot": (
        f"docs/audits/{AUDIT_DATE}-calculation-p1-owner-decision-snapshot.json"
    ),
    "owner_decision_capture_template": (
        f"docs/audits/{AUDIT_DATE}-owner-decision-capture-template.zh.md"
    ),
    "calc_rules": "docs/calc_rules.md",
}
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
    "choose an authoritative calculation convention without business-owner input",
    "treat proposed review defaults as approved rules",
    "change formal implementation before the selected rule is captured",
    "count pending capture-template rows as owner decisions",
    "reopen P1-08 without new contradictory evidence",
]
POST_OWNER_REQUIRED_FIELDS = [
    "selected_decision",
    "owner_rationale",
    "implementation_owner",
    "verification_gate",
    "status",
]


def _section(text: str, start_marker: str, end_marker: str | None = None) -> str:
    if start_marker not in text:
        return ""
    section = text.split(start_marker, maxsplit=1)[1]
    if end_marker is not None and end_marker in section:
        section = section.split(end_marker, maxsplit=1)[0]
    return section


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _decision_rows(decision_section: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in decision_section.splitlines():
        if not line.startswith("| P1-"):
            continue
        cells = _markdown_cells(line)
        if len(cells) < 7:
            continue
        rows.append(
            {
                "p1_id": cells[0],
                "area": cells[1],
                "decision_needed": cells[2],
                "candidate_decisions": cells[3],
                "proposed_review_default": cells[4],
                "impact_if_unresolved": cells[5],
                "closure_evidence": cells[6],
            }
        )
    return rows


def _priority_groups(suggested_section: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for line in suggested_section.splitlines():
        match = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
        if match is None:
            continue
        rank, text = match.groups()
        p1_ids = re.findall(r"P1-\d{2}", text)
        if not p1_ids:
            continue
        rationale = text.split(":", maxsplit=1)[1].strip() if ":" in text else ""
        groups.append({"rank": int(rank), "p1_ids": p1_ids, "rationale": rationale})
    return groups


def _prework_slices(prework_section: str) -> dict[str, dict[str, Any]]:
    slices: dict[str, dict[str, Any]] = {}
    for line in prework_section.splitlines():
        match = re.match(r"^-\s+\*\*(P1-\d{2})\s+(.+?)\*\*:\s+(.+)$", line.strip())
        if match is None:
            continue
        p1_id, title, text = match.groups()
        paths = [
            value
            for value in re.findall(r"`([^`]+)`", text)
            if "/" in value or "\\" in value or value.endswith((".py", ".ts", ".tsx", ".md"))
        ]
        slices[p1_id] = {
            "title": title,
            "implementation_slice": text,
            "referenced_paths": paths,
        }
    return slices


def _priority_rank_by_id(groups: list[dict[str, Any]]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for group in groups:
        for p1_id in group["p1_ids"]:
            ranks[p1_id] = group["rank"]
    return ranks


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _path_status(paths: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "exists": (ROOT / path).exists(),
        }
        for path in paths
    ]


def build_packet(
    *,
    matrix_path: Path = DEFAULT_MATRIX,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any]:
    matrix_text = Path(matrix_path).read_text(encoding="utf-8")
    snapshot = _load_json(Path(snapshot_path))
    decision_section = _section(matrix_text, "## Decision Matrix", "## Suggested Review Order")
    suggested_section = _section(
        matrix_text,
        "## Suggested Review Order",
        "## Non-Approvals",
    )
    prework_section = _section(matrix_text, "## Engineering Prework / Impact Slice Map")
    rows = _decision_rows(decision_section)
    groups = _priority_groups(suggested_section)
    ranks = _priority_rank_by_id(groups)
    prework = _prework_slices(prework_section)
    incomplete_by_id = snapshot.get("capture_template", {}).get(
        "incomplete_fields_by_id",
        {},
    )
    invalid_status_by_id = snapshot.get("capture_template", {}).get(
        "invalid_status_by_id",
        {},
    )
    invalid_selected_decision_by_id = snapshot.get("capture_template", {}).get(
        "invalid_selected_decision_by_id",
        {},
    )
    candidate_options_by_id = snapshot.get("matrix", {}).get(
        "candidate_options_by_id",
        {},
    )

    decision_items = []
    for row in rows:
        execution_slice = dict(prework.get(row["p1_id"], {}))
        referenced_paths = list(execution_slice.get("referenced_paths", []))
        path_status = _path_status(referenced_paths)
        missing_paths = [
            path_item["path"] for path_item in path_status if not path_item["exists"]
        ]
        execution_slice.update(
            {
                "path_status": path_status,
                "all_referenced_paths_exist": not missing_paths,
                "missing_referenced_paths": missing_paths,
            }
        )
        decision_items.append(
            {
                **row,
                "priority_rank": ranks.get(row["p1_id"]),
                "current_status": "pending_owner_decision",
                "captures_owner_decision": False,
                "missing_capture_fields": incomplete_by_id.get(row["p1_id"], []),
                "invalid_capture_status": invalid_status_by_id.get(row["p1_id"]),
                "invalid_selected_decision": invalid_selected_decision_by_id.get(
                    row["p1_id"]
                ),
                "allowed_candidate_options": dict(
                    candidate_options_by_id.get(row["p1_id"], {})
                ),
                "post_decision_execution_slice": execution_slice,
            }
        )
    pending_count = sum(1 for item in decision_items if item["current_status"] != "closed")
    missing_execution_paths = sorted(
        {
            path
            for item in decision_items
            for path in item["post_decision_execution_slice"]["missing_referenced_paths"]
        }
    )
    execution_path_count = sum(
        len(item["post_decision_execution_slice"].get("referenced_paths", []))
        for item in decision_items
    )

    return {
        "packet_kind": "calculation_p1_owner_decision_packet",
        "audit_date": AUDIT_DATE,
        "decision_status": snapshot.get("status", {}).get("overall"),
        "owner_decision_ready": False,
        "implementation_ready": False,
        "execution_anchor_ready": not missing_execution_paths,
        "source_artifacts": dict(SOURCE_ARTIFACTS),
        "source_snapshot_generated_at": snapshot.get("generated_at"),
        "decision_item_count": len(decision_items),
        "pending_decision_count": pending_count,
        "captured_decision_count": snapshot.get("capture_template", {}).get(
            "captured_decision_count",
            0,
        ),
        "post_owner_required_fields": list(POST_OWNER_REQUIRED_FIELDS),
        "execution_referenced_path_count": execution_path_count,
        "missing_execution_referenced_paths": missing_execution_paths,
        "expected_open_decision_ids": list(EXPECTED_OPEN_CALCULATION_P1_IDS),
        "decision_ids": [item["p1_id"] for item in decision_items],
        "priority_groups": groups,
        "first_priority_group": groups[0] if groups else None,
        "decision_items": decision_items,
        "capture_validation_rule": (
            "selected_decision must reference an allowed option letter for that P1 "
            "and include substantive text matching the option description from the "
            "Decision Matrix Candidate Decisions column. The safest accepted shape is "
            "`Option <letter> - <copied option description>`. Bare Option A/B/C labels, "
            "undefined option letters, unrelated option text, and evidence-only text on "
            "approved-for-implementation rows remain invalid."
        ),
        "intake_checklist": {
            "source_matrix_exists": Path(matrix_path).is_file(),
            "source_snapshot_exists": Path(snapshot_path).is_file(),
            "decision_ids_match_expected": (
                [item["p1_id"] for item in decision_items]
                == EXPECTED_OPEN_CALCULATION_P1_IDS
            ),
            "all_rows_pending_owner_decision": pending_count == len(decision_items),
            "captured_decision_count": snapshot.get("capture_template", {}).get(
                "captured_decision_count",
                0,
            ),
            "invalid_status_count": len(invalid_status_by_id),
            "invalid_selected_decision_count": len(invalid_selected_decision_by_id),
            "execution_slice_count": len(prework),
            "execution_referenced_path_count": execution_path_count,
            "all_execution_slices_present": (
                sorted(prework) == sorted(EXPECTED_OPEN_CALCULATION_P1_IDS)
            ),
            "all_execution_slice_paths_exist": not missing_execution_paths,
            "missing_execution_referenced_path_count": len(missing_execution_paths),
            "captures_owner_decisions": False,
            "chooses_or_approves_conventions": False,
        },
        "next_engineering_action_after_owner_input": (
            "For each captured owner convention, update docs/calc_rules.md or the "
            "applicable contract, normalize the authoritative implementation path, "
            "update tests that froze the losing convention, then rerun the P1 snapshot "
            "strict capture gate and the system audit completion verifier."
        ),
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "boundary": (
            "This packet is a read-only execution-preparation artifact. It does not choose "
            "or approve conventions, capture owner decisions, change code, write DuckDB or "
            "governance records, approve metrics/pages, authorize Ledger PnL --write, or "
            "certify routes."
        ),
    }


def render_markdown(packet: dict[str, Any]) -> str:
    source_rows = "\n".join(
        f"- `{key}`: `{value}`" for key, value in packet["source_artifacts"].items()
    )
    priority_rows = "\n".join(
        (
            f"| {group['rank']} | {', '.join(f'`{p1_id}`' for p1_id in group['p1_ids'])} | "
            f"{group['rationale']} |"
        )
        for group in packet["priority_groups"]
    )
    decision_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | {item['priority_rank']} | {item['area']} | "
            f"{item['decision_needed']} | {item['candidate_decisions']} | "
            f"{item['proposed_review_default']} | `{item['current_status']}` | "
            f"{', '.join(item['missing_capture_fields']) or 'none'} | "
            f"{item['closure_evidence']} |"
        )
        for item in packet["decision_items"]
    )
    option_contract_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | "
            f"{'<br>'.join(f'`Option {letter}`: {description}' for letter, description in item['allowed_candidate_options'].items())} | "
            "`Option <allowed letter> - <copied option description>` |"
        )
        for item in packet["decision_items"]
    )
    execution_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | "
            f"{item['post_decision_execution_slice'].get('implementation_slice', '')} | "
            f"{', '.join(f'`{path}`' for path in item['post_decision_execution_slice'].get('referenced_paths', [])) or 'none'} |"
        )
        for item in packet["decision_items"]
    )
    anchor_rows = "\n".join(
        (
            f"| `{item['p1_id']}` | "
            f"{len(item['post_decision_execution_slice'].get('referenced_paths', []))} | "
            f"`{str(item['post_decision_execution_slice']['all_referenced_paths_exist']).lower()}` | "
            f"{', '.join(f'`{path}`' for path in item['post_decision_execution_slice']['missing_referenced_paths']) or 'none'} |"
        )
        for item in packet["decision_items"]
    )
    prohibited = "\n".join(f"- {item}" for item in packet["prohibited_actions"])
    scope = "\n".join(
        f"- `{key}={str(value).lower() if isinstance(value, bool) else value}`"
        for key, value in packet["evidence_scope"].items()
    )

    return f"""# Calculation P1 Owner Decision Packet

Decision status: `decision_status={packet['decision_status']}`
Owner decision ready: `{str(packet['owner_decision_ready']).lower()}`
Implementation ready: `{str(packet['implementation_ready']).lower()}`
Execution anchor ready: `{str(packet['execution_anchor_ready']).lower()}`
Source snapshot generated at: `{packet['source_snapshot_generated_at']}`

This packet prepares the first open blocker for owner/governance intake. It does not approve a calculation convention, capture owner decisions, change implementation code, write governance records, approve pages, authorize Ledger PnL `--write`, or certify routes.

## Summary

- `decision_item_count={packet['decision_item_count']}`
- `pending_decision_count={packet['pending_decision_count']}`
- `captured_decision_count={packet['captured_decision_count']}`
- `post_owner_required_fields={', '.join(packet['post_owner_required_fields'])}`
- `execution_referenced_path_count={packet['execution_referenced_path_count']}`
- `missing_execution_referenced_path_count={len(packet['missing_execution_referenced_paths'])}`
- First priority group: `{', '.join(packet['first_priority_group']['p1_ids']) if packet['first_priority_group'] else ''}`

## Source Artifacts

{source_rows}

## Intake Checklist

- `source_matrix_exists={str(packet['intake_checklist']['source_matrix_exists']).lower()}`
- `source_snapshot_exists={str(packet['intake_checklist']['source_snapshot_exists']).lower()}`
- `decision_ids_match_expected={str(packet['intake_checklist']['decision_ids_match_expected']).lower()}`
- `all_rows_pending_owner_decision={str(packet['intake_checklist']['all_rows_pending_owner_decision']).lower()}`
- `captured_decision_count={packet['intake_checklist']['captured_decision_count']}`
- `invalid_status_count={packet['intake_checklist']['invalid_status_count']}`
- `invalid_selected_decision_count={packet['intake_checklist']['invalid_selected_decision_count']}`
- `execution_slice_count={packet['intake_checklist']['execution_slice_count']}`
- `execution_referenced_path_count={packet['intake_checklist']['execution_referenced_path_count']}`
- `all_execution_slices_present={str(packet['intake_checklist']['all_execution_slices_present']).lower()}`
- `all_execution_slice_paths_exist={str(packet['intake_checklist']['all_execution_slice_paths_exist']).lower()}`
- `missing_execution_referenced_path_count={packet['intake_checklist']['missing_execution_referenced_path_count']}`
- `captures_owner_decisions=false`
- `chooses_or_approves_conventions=false`

## Priority Groups

| Rank | P1 IDs | Rationale |
| ---: | --- | --- |
{priority_rows}

## Decision Items

| P1 | Rank | Area | Decision needed | Candidate decisions | Proposed review default | Current status | Missing capture fields | Owner decision gate |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
{decision_rows}

## Candidate Option Contract

{packet['capture_validation_rule']}

Allowed option letters are row-specific; some P1 rows only allow `Option A` and `Option B`. For `approved-for-implementation`, use the required capture format below rather than evidence-only wording. The format example is not a recommended option and does not approve any listed candidate.

| P1 | Allowed candidate options | Required capture format, not a recommendation |
| --- | --- | --- |
{option_contract_rows}

## Post-Decision Execution Slices

| P1 | Execution slice after owner input | Referenced paths |
| --- | --- | --- |
{execution_rows}

## Execution Anchor Checks

Every referenced execution path below is an engineering handoff anchor only. Existing paths do not approve the corresponding owner decision.

| P1 | Referenced path count | All referenced paths exist | Missing referenced paths |
| --- | ---: | --- | --- |
{anchor_rows}

## Next Engineering Action After Owner Input

{packet['next_engineering_action_after_owner_input']}

## Prohibited Actions

{prohibited}

## Evidence Scope

{scope}

## Boundary

{packet['boundary']}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the read-only calculation/display P1 owner-decision execution packet."
        )
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    packet = build_packet(matrix_path=args.matrix, snapshot_path=args.snapshot)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(packet), encoding="utf-8")
    payload = {
        "packet_kind": packet["packet_kind"],
        "packet_path": str(output_path),
        "decision_status": packet["decision_status"],
        "owner_decision_ready": packet["owner_decision_ready"],
        "implementation_ready": packet["implementation_ready"],
        "execution_anchor_ready": packet["execution_anchor_ready"],
        "decision_item_count": packet["decision_item_count"],
        "pending_decision_count": packet["pending_decision_count"],
        "captured_decision_count": packet["captured_decision_count"],
        "execution_referenced_path_count": packet["execution_referenced_path_count"],
        "missing_execution_referenced_paths": packet["missing_execution_referenced_paths"],
        "first_priority_group": packet["first_priority_group"],
        "intake_checklist": packet["intake_checklist"],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
