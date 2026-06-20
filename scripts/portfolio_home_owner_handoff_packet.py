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
from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    non_negative_portfolio_limit,
)
from scripts.portfolio_home_limit import validate_non_negative_portfolio_limit  # noqa: E402
from scripts.portfolio_home_owner_action_packet import build_packet  # noqa: E402


DEFAULT_OUTPUT = ROOT / "docs" / "portfolio" / "portfolio-home-owner-handoff-packet.md"
APPROVAL_PACKET_STRICT_COMMAND = (
    "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready"
)
SCORECARD_STRICT_COMMAND = (
    "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
)
ARTIFACT_PRESENCE_COMMAND = (
    "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current"
)
ARTIFACT_PRESENCE_SUMMARY_LINE = (
    "- Closure artifact presence check reports `status=current`, `current=true`, and no blockers."
)
REQUIRED_CURRENT_SEMANTIC_FRAGMENTS = [
    "- Business owner approval boundary: `",
    "- Template approval captured: `",
    "- Formal authorization allowed: `",
    "- Governance write allowed: `",
    "- Page execution proven: `",
    "- Full score closure ready: `",
    "- Certification effect: `",
    "- Handoff approves metric or page: `",
    "- Handoff writes governance records: `",
    "- Handoff captures business-owner approval: `",
    "- Risk tensor rematerialization preview: `",
    "- Risk tensor preview writes database: `",
    "- Risk tensor preview approves metric or page: `",
    "- Risk tensor preview certification effect: `",
    "- Business owner approval boundary blockers: ",
    "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.",
    "- Generated owner fields boundary: ",
    "- Generated export system-field current gate: ",
    "- Export current summary: ",
    "- Export current blockers: ",
    "- Export current boundary: ",
    "- Activation boundary state: `",
    "- Owner intake evidence alignment: `",
    "- Score blocker action coverage: `",
    "- Blocker closure matrix coverage: `",
    ARTIFACT_PRESENCE_SUMMARY_LINE,
    f"- `{ARTIFACT_PRESENCE_COMMAND}`",
    "## Owner Quickstart",
    "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.",
    "- Risk Owner quickstart:",
    "- Data Owner quickstart:",
    "- Business Owner quickstart:",
]
ACTIVATION_STATE_PREFIX = "- Activation boundary state: `"
STRICT_GATE_SUMMARY_PREFIX = "- Current strict gates: "
STRICT_GATE_READY_SUMMARY = (
    "Current strict gates: expected to exit 0; full closure evidence is ready."
)


def _code_list(values: list[object]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def _activation_state_values(markdown: str) -> list[str]:
    values: list[str] = []
    for line in markdown.splitlines():
        if line.startswith(ACTIVATION_STATE_PREFIX) and line.endswith("`"):
            values.append(line[len(ACTIVATION_STATE_PREFIX) : -1])
    return values


def _strict_gate_summary_lines(markdown: str) -> list[str]:
    return [
        line
        for line in markdown.splitlines()
        if line.startswith(STRICT_GATE_SUMMARY_PREFIX)
    ]


def _owner_heading(owner: str) -> str:
    return {
        "risk_owner": "Risk Owner",
        "data_owner": "Data Owner",
        "business_owner": "Business Owner",
    }.get(owner, owner)


def _artifact_lines(artifacts: list[object]) -> list[str]:
    lines: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        lines.append(f"- Artifact: `{artifact.get('artifact')}`")
        fields = artifact.get("required_fields", [])
        allowed = artifact.get("allowed_decisions", [])
        notes = artifact.get("note_required_for", [])
        if isinstance(fields, list):
            lines.append(f"  Required fields: {_code_list(fields)}")
        if isinstance(allowed, list):
            lines.append(f"  Allowed decisions: {_code_list(allowed)}")
        if isinstance(notes, list) and notes:
            lines.append(f"  Note required for: {_code_list(notes)}")
    return lines


def _artifact_paths(artifacts: list[object]) -> list[object]:
    paths: list[object] = []
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("artifact"):
            paths.append(artifact["artifact"])
    return paths


def _artifact_values(artifacts: list[object], key: str) -> list[object]:
    values: list[object] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        raw_values = artifact.get(key, [])
        if not isinstance(raw_values, list):
            continue
        for value in raw_values:
            if value not in values:
                values.append(value)
    return values


def _artifact_field_groups(artifacts: list[object]) -> tuple[list[object], list[tuple[str, list[object]]]]:
    common_fields: list[object] = []
    conditional_fields: list[tuple[str, list[object]]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        fields = artifact.get("required_fields", [])
        if not isinstance(fields, list) or not fields:
            continue
        decisions = artifact.get("allowed_decisions", [])
        if isinstance(decisions, list) and len(decisions) == 1 and decisions[0] != "approve":
            conditional_fields.append((str(decisions[0]), fields))
            continue
        for field in fields:
            if field not in common_fields:
                common_fields.append(field)
    return common_fields, conditional_fields


def _evidence_commands(actions: list[object]) -> list[object]:
    commands: list[object] = []
    for action in actions:
        if isinstance(action, dict) and action.get("evidence_command"):
            command = action["evidence_command"]
            if command not in commands:
                commands.append(command)
    return commands


def _exit_criteria(actions: list[object]) -> list[object]:
    criteria: list[object] = []
    for action in actions:
        if isinstance(action, dict) and action.get("exit_criteria"):
            criterion = action["exit_criteria"]
            if criterion not in criteria:
                criteria.append(criterion)
    return criteria


def _criteria_text(criteria: list[object]) -> str:
    parts = [str(criterion).rstrip(".") for criterion in criteria]
    if parts:
        parts[-1] = f"{parts[-1]}."
    return "; ".join(parts)


def _table_cell_list(values: list[object]) -> str:
    if not values:
        return "`none`"
    return "; ".join(f"`{value}`" for value in values)


def _evidence_source_list(values: list[object]) -> list[str]:
    sources: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        fields = value.get("fields", [])
        if not name or not isinstance(fields, list):
            continue
        field_text = ", ".join(f"`{field}`" for field in fields)
        sources.append(f"`{name}` ({field_text})")
    return sources


def _fill_or_evidence_cell(row: dict[str, object]) -> str:
    artifacts = row.get("decision_artifacts", [])
    evidence_sources = row.get("evidence_sources", [])
    assert isinstance(artifacts, list)
    assert isinstance(evidence_sources, list)
    evidence_source_text = _evidence_source_list(evidence_sources)
    values = [*artifacts, *evidence_source_text]
    if not values:
        return "`none`"
    return "; ".join(
        value if str(value).startswith("`") else f"`{value}`"
        for value in values
    )


def _summary_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "missing"
    return str(value)


def _summary_kv_list(payload: dict[str, object], keys: list[str]) -> str:
    return ", ".join(
        f"`{key}={_summary_value(payload.get(key))}`"
        for key in keys
    )


def _owner_intake_boundary_lines(
    *,
    packet: dict[str, object],
    intake: dict[str, object],
) -> list[str]:
    csv_summary = intake.get("csv_check_summary") or packet.get("csv_check_summary")
    boundaries = (
        intake.get("generated_owner_fields_boundaries")
        or packet.get("generated_owner_fields_boundaries")
    )
    owner_input_boundary = intake.get("owner_input_boundary", {})
    export_current_summary = intake.get("export_current_summary", {})
    lines: list[str] = []
    if isinstance(csv_summary, dict) and csv_summary:
        row_keys = [
            "krd_summary_row_count",
            "krd_detail_row_count",
            "bond_missing_maturity_row_count",
            "tyw_liability_missing_maturity_row_count",
        ]
        blank_keys = [
            "krd_owner_decision_fields_blank",
            "maturity_owner_fields_blank",
        ]
        lines.append(f"- Owner intake CSV summary: {_summary_kv_list(csv_summary, row_keys)}.")
        lines.append(
            f"- Owner intake blank-field status: {_summary_kv_list(csv_summary, blank_keys)}.",
        )
    if isinstance(boundaries, dict) and boundaries:
        boundary_keys = [
            "krd_contract_decision_manifest",
            "maturity_remediation_manifest",
        ]
        lines.append(
            "- Manifest generated-owner boundary status: "
            f"{_summary_kv_list(boundaries, boundary_keys)}.",
        )
    if isinstance(owner_input_boundary, dict) and owner_input_boundary:
        lines.append(
            "- Generated export system-field current gate: "
            "`generated_export_system_fields_must_be_current="
            f"{_summary_value(owner_input_boundary.get('generated_export_system_fields_must_be_current'))}`.",
        )
    if isinstance(export_current_summary, dict) and export_current_summary:
        krd = export_current_summary.get("krd", {})
        maturity = export_current_summary.get("maturity", {})
        if isinstance(krd, dict) and isinstance(maturity, dict):
            lines.append(
                "- Export current summary: "
                f"`krd_status={_summary_value(krd.get('status'))}`, "
                f"`krd_current={_summary_value(krd.get('current'))}`, "
                f"`maturity_status={_summary_value(maturity.get('status'))}`, "
                f"`maturity_current={_summary_value(maturity.get('current'))}`.",
            )
            blockers = []
            for source in (krd, maturity):
                current_blockers = source.get("current_blockers", [])
                if isinstance(current_blockers, list):
                    blockers.extend(current_blockers)
            active_blockers = owner_input_boundary.get("active_export_current_blockers", [])
            if isinstance(active_blockers, list):
                blockers.extend(active_blockers)
            deduped_blockers = list(dict.fromkeys(blockers))
            lines.append(
                "- Export current blockers: "
                f"{_code_list(deduped_blockers) if deduped_blockers else '`none`'}.",
            )
            lines.append(
                "- Export current boundary: current export system fields prove package "
                "freshness only; they do not approve KRD decisions, maturity remediation, "
                "signed exclusions, or business-owner closure.",
            )
            lines.append(ARTIFACT_PRESENCE_SUMMARY_LINE)
    return lines


def _blocker_closure_matrix_lines(matrix: list[object]) -> list[str]:
    lines = [
        "## Blocker Closure Matrix",
        "| Blocker | Owner | Fill / Evidence | Recheck | Exit Signal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in matrix:
        if not isinstance(row, dict):
            continue
        commands = row.get("recheck_commands", [])
        assert isinstance(commands, list)
        lines.append(
            "| "
            f"`{row.get('blocker')}` | "
            f"`{row.get('owner')}` | "
            f"{_fill_or_evidence_cell(row)} | "
            f"{_table_cell_list(commands)} | "
            f"{row.get('removes_blocker_when')} |"
        )
    return lines


def _owner_workload_line(owner: str, owner_packet: dict[str, object]) -> str | None:
    summary = owner_packet.get("csv_check_summary", {})
    if not isinstance(summary, dict):
        return None
    if owner == "risk_owner":
        summary_rows = int(summary.get("krd_summary_row_count") or 0)
        detail_rows = int(summary.get("krd_detail_row_count") or 0)
        total_rows = summary_rows + detail_rows
        if total_rows:
            return (
                f"  - Workload: KRD owner decision fields across {total_rows} rows "
                f"(summary {summary_rows}, detail {detail_rows})."
            )
    if owner == "data_owner":
        bond_rows = int(summary.get("bond_missing_maturity_row_count") or 0)
        tyw_rows = int(summary.get("tyw_liability_missing_maturity_row_count") or 0)
        total_rows = bond_rows + tyw_rows
        if total_rows:
            return (
                f"  - Workload: maturity remediation fields across {total_rows} rows "
                f"(bond {bond_rows}, TYW liability {tyw_rows})."
            )
    return None


def _owner_gap_line(owner: str, owner_packet: dict[str, object]) -> str | None:
    gaps = owner_packet.get("decision_gap_counts", {})
    if not isinstance(gaps, dict):
        return None
    if owner == "risk_owner":
        total_rows = int(gaps.get("missing_decision_rows") or 0)
        summary_rows = int(gaps.get("summary_missing_decision_rows") or 0)
        detail_rows = int(gaps.get("detail_missing_decision_rows") or 0)
        if total_rows:
            return (
                f"  - Current gaps: KRD owner decision missing on {total_rows} rows "
                f"(summary {summary_rows}, detail {detail_rows})."
            )
    if owner == "data_owner":
        total_rows = int(gaps.get("missing_decision_rows") or 0)
        bond_rows = int(gaps.get("bond_missing_decision_rows") or 0)
        tyw_rows = int(gaps.get("tyw_liability_missing_decision_rows") or 0)
        if total_rows:
            return (
                f"  - Current gaps: maturity owner decision missing on {total_rows} rows "
                f"(bond {bond_rows}, TYW liability {tyw_rows})."
            )
    return None


def _owner_note_gap_line(owner: str, owner_packet: dict[str, object]) -> str | None:
    if owner == "risk_owner":
        gaps = owner_packet.get("note_gap_counts", {})
        if not isinstance(gaps, dict):
            return None
        by_decision = gaps.get("by_decision", [])
        if isinstance(by_decision, list) and by_decision:
            parts = []
            for item in by_decision:
                if not isinstance(item, dict):
                    continue
                decision = item.get("risk_owner_decision")
                rows = int(item.get("missing_note_rows") or 0)
                if decision and rows:
                    parts.append(f"KRD `{decision}` decision notes missing on {rows} rows")
            if parts:
                return f"  - Current note gaps: {'; '.join(parts)}."
        decision = gaps.get("risk_owner_decision")
        rows = int(gaps.get("missing_note_rows") or 0)
        if decision and rows:
            return (
                f"  - Current note gaps: KRD `{decision}` decision notes missing "
                f"on {rows} rows."
            )
    if owner == "data_owner":
        gaps = owner_packet.get("comment_gap_counts", {})
        if not isinstance(gaps, dict):
            return None
        by_decision = gaps.get("by_decision", [])
        if isinstance(by_decision, list) and by_decision:
            parts = []
            for item in by_decision:
                if not isinstance(item, dict):
                    continue
                decision = item.get("owner_decision")
                rows = int(item.get("missing_comment_rows") or 0)
                if decision and rows:
                    parts.append(f"maturity `{decision}` owner comments missing on {rows} rows")
            if parts:
                return f"  - Current comment gaps: {'; '.join(parts)}."
        decision = gaps.get("owner_decision")
        rows = int(gaps.get("missing_comment_rows") or 0)
        if decision and rows:
            return (
                f"  - Current comment gaps: maturity `{decision}` owner comments missing "
                f"on {rows} rows."
            )
    return None


def _owner_checklist(owner_packets: dict[str, object]) -> list[str]:
    lines = ["## Owner Checklist"]
    for owner in ("risk_owner", "data_owner", "business_owner"):
        owner_packet = owner_packets.get(owner, {})
        if not isinstance(owner_packet, dict):
            continue
        blockers = owner_packet.get("blockers", [])
        actions = owner_packet.get("actions", [])
        artifacts = owner_packet.get("decision_intake_artifacts", [])
        assert isinstance(blockers, list)
        assert isinstance(actions, list)
        assert isinstance(artifacts, list)
        lines.append(
            f"- [ ] {_owner_heading(owner)}: close "
            f"{_code_list(blockers) if blockers else '`none`'}",
        )
        commands = _evidence_commands(actions)
        if commands:
            lines.append(f"  - Evidence commands: {'; '.join(f'`{command}`' for command in commands)}")
        criteria = _exit_criteria(actions)
        if criteria:
            lines.append(f"  - Exit criteria: {_criteria_text(criteria)}")
        artifact_paths = _artifact_paths(artifacts)
        if artifact_paths:
            lines.append(f"  - Artifacts: {'; '.join(f'`{artifact}`' for artifact in artifact_paths)}")
        workload_line = _owner_workload_line(owner, owner_packet)
        if workload_line:
            lines.append(workload_line)
        gap_line = _owner_gap_line(owner, owner_packet)
        if gap_line:
            lines.append(gap_line)
        note_gap_line = _owner_note_gap_line(owner, owner_packet)
        if note_gap_line:
            lines.append(note_gap_line)
        common_fields, conditional_fields = _artifact_field_groups(artifacts)
        if common_fields:
            lines.append(f"  - Artifact fields to review/fill: {_code_list(common_fields)}")
        for decision, fields in conditional_fields:
            lines.append(
                f"  - Conditional artifact fields (`{decision}` only): {_code_list(fields)}",
            )
        allowed_decisions = _artifact_values(artifacts, "allowed_decisions")
        if allowed_decisions:
            lines.append(f"  - Allowed decisions: {_code_list(allowed_decisions)}")
        note_required_for = _artifact_values(artifacts, "note_required_for")
        if note_required_for:
            note_label = (
                "Notes required for"
                if all(decision in allowed_decisions for decision in note_required_for)
                else "Dependent decision notes required for"
            )
            lines.append(f"  - {note_label}: {_code_list(note_required_for)}")
    lines.append("- [ ] Re-run intake and strict scorecard commands after owner updates are captured.")
    return lines


def _owner_quickstart(owner_packets: dict[str, object]) -> list[str]:
    lines = [
        "## Owner Quickstart",
        "- Quickstart boundary: fill owner-controlled fields only; do not edit generated system fields.",
    ]
    for owner in ("risk_owner", "data_owner", "business_owner"):
        owner_packet = owner_packets.get(owner, {})
        if not isinstance(owner_packet, dict):
            continue
        blockers = owner_packet.get("blockers", [])
        actions = owner_packet.get("actions", [])
        artifacts = owner_packet.get("decision_intake_artifacts", [])
        assert isinstance(blockers, list)
        assert isinstance(actions, list)
        assert isinstance(artifacts, list)
        artifact_paths = _artifact_paths(artifacts)
        common_fields, conditional_fields = _artifact_field_groups(artifacts)
        commands = _evidence_commands(actions)
        lines.append(f"- {_owner_heading(owner)} quickstart:")
        lines.append(f"  - Close: {_code_list(blockers) if blockers else '`none`'}")
        if artifact_paths:
            lines.append(f"  - Fill/review: {'; '.join(f'`{artifact}`' for artifact in artifact_paths)}")
        if common_fields:
            lines.append(f"  - Required fields: {_code_list(common_fields)}")
        for decision, fields in conditional_fields:
            lines.append(f"  - Conditional fields (`{decision}` only): {_code_list(fields)}")
        if commands:
            lines.append(f"  - Recheck: {'; '.join(f'`{command}`' for command in commands)}")
    return lines


def _strict_gate_expectations(expectations: dict[str, object]) -> list[str]:
    commands = expectations.get("commands", [])
    assert isinstance(commands, list)
    lines = [
        "## Strict Gate Expectations",
        f"- Activation boundary state: `{expectations.get('activation_state')}`",
        f"- {expectations.get('summary')}",
        f"- {expectations.get('full_score_rule')}",
    ]
    for command in commands:
        if not isinstance(command, dict):
            continue
        lines.append(
            f"- `{command.get('command')}`: currently `{command.get('current_expected_exit')}`; "
            f"after updates `{command.get('expected_when_full_score')}`.",
        )
    return lines


def _krd_decision_scale_line(owner_packet: dict[str, object]) -> str | None:
    summary = owner_packet.get("krd_remap_summary", [])
    if not isinstance(summary, list) or not summary:
        return None

    parts: list[str] = []
    for item in summary:
        if not isinstance(item, dict):
            continue
        tenor = item.get("tenor_bucket")
        mapped_to = item.get("mapped_to")
        all_rows = item.get("all_rows")
        nonzero_rows = item.get("nonzero_dv01_rows")
        dv01_sum = item.get("dv01_sum")
        if not tenor or not mapped_to or all_rows is None or dv01_sum is None:
            continue
        nonzero_note = ""
        if nonzero_rows is not None and str(nonzero_rows) != str(all_rows):
            nonzero_note = f" ({nonzero_rows} non-zero DV01 rows)"
        parts.append(
            f"`{tenor}` maps to `{mapped_to}` across {all_rows} rows"
            f"{nonzero_note} with DV01 {dv01_sum}"
        )
    if not parts:
        return None
    return f"- KRD decision scale: {'; '.join(parts)}."


def _maturity_decision_scale_line(owner_packet: dict[str, object]) -> str | None:
    bond = owner_packet.get("bond_missing_maturity_summary", {})
    tyw = owner_packet.get("tyw_liability_missing_maturity_summary", {})
    if not isinstance(bond, dict) or not isinstance(tyw, dict):
        return None

    bond_rows = bond.get("missing_maturity_rows")
    bond_value = bond.get("missing_maturity_market_value")
    tyw_rows = tyw.get("missing_maturity_rows")
    tyw_principal = tyw.get("missing_maturity_principal")
    if (
        bond_rows is None
        or bond_value is None
        or tyw_rows is None
        or tyw_principal is None
    ):
        return None

    return (
        "- Maturity decision scale: bond queue has "
        f"{bond_rows} missing maturity rows with market value {bond_value}; "
        f"TYW liability queue has {tyw_rows} missing maturity rows with "
        f"principal {tyw_principal}."
    )


def _owner_section(owner: str, owner_packet: dict[str, object]) -> list[str]:
    blockers = owner_packet.get("blockers", [])
    actions = owner_packet.get("actions", [])
    artifacts = owner_packet.get("decision_intake_artifacts", [])
    assert isinstance(blockers, list)
    assert isinstance(actions, list)
    assert isinstance(artifacts, list)

    lines = [
        f"## {_owner_heading(owner)}",
        f"- Status: `{owner_packet.get('status')}`",
        f"- Blockers: {_code_list(blockers) if blockers else '`none`'}",
    ]
    if owner == "risk_owner":
        scale_line = _krd_decision_scale_line(owner_packet)
        if scale_line:
            lines.append(scale_line)
    if owner == "data_owner":
        scale_line = _maturity_decision_scale_line(owner_packet)
        if scale_line:
            lines.append(scale_line)
    if actions:
        lines.append("- Required actions:")
        for action in actions:
            if isinstance(action, dict):
                lines.append(
                    f"  - `{action.get('blocker')}`: {action.get('next_action')}",
                )
                lines.append(f"    Evidence command: `{action.get('evidence_command')}`")
    lines.append("- Decision intake artifacts:")
    artifact_lines = _artifact_lines(artifacts)
    lines.extend(f"  {line}" for line in artifact_lines)
    return lines


def _render_packet_markdown(packet: dict[str, object]) -> str:
    intake = packet.get("owner_decision_intake_summary", {})
    assert isinstance(intake, dict)
    intake_blockers = intake.get("owner_decision_blockers", [])
    assert isinstance(intake_blockers, list)
    decision_alignment = intake.get("decision_alignment", {})
    assert isinstance(decision_alignment, dict)
    owner_intake_alignment = packet.get("owner_decision_intake_alignment", {})
    assert isinstance(owner_intake_alignment, dict)
    owner_intake_alignment_blockers = owner_intake_alignment.get("blockers", [])
    assert isinstance(owner_intake_alignment_blockers, list)
    score_blocker_action_coverage = packet.get("score_blocker_action_coverage", {})
    assert isinstance(score_blocker_action_coverage, dict)
    score_blocker_action_coverage_blockers = score_blocker_action_coverage.get("blockers", [])
    assert isinstance(score_blocker_action_coverage_blockers, list)
    score_blocker_action_coverage_unassigned = score_blocker_action_coverage.get("unassigned_blockers", [])
    assert isinstance(score_blocker_action_coverage_unassigned, list)
    score_blocker_action_coverage_covered = score_blocker_action_coverage.get("covered_blockers", [])
    assert isinstance(score_blocker_action_coverage_covered, list)
    blocker_closure_matrix_coverage = packet.get("blocker_closure_matrix_coverage", {})
    assert isinstance(blocker_closure_matrix_coverage, dict)
    blocker_closure_matrix_missing = blocker_closure_matrix_coverage.get("missing_blockers", [])
    assert isinstance(blocker_closure_matrix_missing, list)
    blocker_closure_matrix_unexpected = blocker_closure_matrix_coverage.get("unexpected_blockers", [])
    assert isinstance(blocker_closure_matrix_unexpected, list)
    blocker_closure_matrix_duplicates = blocker_closure_matrix_coverage.get("duplicate_blockers", [])
    assert isinstance(blocker_closure_matrix_duplicates, list)
    rerun_evidence = packet.get("rerun_evidence_status", {})
    assert isinstance(rerun_evidence, dict)
    risk_warning_clean_status = packet.get("risk_warning_clean_status", {})
    assert isinstance(risk_warning_clean_status, dict)
    risk_warning_blockers = risk_warning_clean_status.get("decision_blockers", [])
    assert isinstance(risk_warning_blockers, list)
    rematerialization_preview = risk_warning_clean_status.get(
        "risk_tensor_rematerialization_preview",
        {},
    )
    assert isinstance(rematerialization_preview, dict)
    preview_clear_blockers = rematerialization_preview.get(
        "would_clear_consistency_blockers",
        [],
    )
    assert isinstance(preview_clear_blockers, list)
    preview_decision_blockers = rematerialization_preview.get(
        "preview_decision_blockers",
        [],
    )
    assert isinstance(preview_decision_blockers, list)
    approval_boundary = packet.get("business_owner_approval_boundary", {})
    assert isinstance(approval_boundary, dict)
    approval_boundary_blockers = approval_boundary.get("blockers", [])
    assert isinstance(approval_boundary_blockers, list)
    strict_gate_expectations = packet.get("strict_gate_expectations", {})
    assert isinstance(strict_gate_expectations, dict)
    owner_packets = packet.get("owner_packets", {})
    assert isinstance(owner_packets, dict)
    business_owner_packet = owner_packets.get("business_owner", {})
    assert isinstance(business_owner_packet, dict)
    approval_field_status = business_owner_packet.get("approval_field_status", {})
    assert isinstance(approval_field_status, dict)

    lines = [
        "# Portfolio Home Owner Handoff Packet",
        "",
        "## Summary",
        f"- Page: `{packet.get('page_slug')}` (`{packet.get('page_id')}`)",
        f"- Report date: `{packet.get('report_date')}`",
        f"- Current score: `{packet.get('current_score')}`",
        f"- Remaining gap: `{packet.get('remaining_gap')}`",
        f"- Score status: `{packet.get('score_status')}`",
        f"- Handoff status: `{packet.get('handoff_status')}`",
        f"- Intake status: `{intake.get('intake_status')}`",
        f"- Owner intake ready: `{intake.get('intake_ready')}`",
        f"- Owner intake blockers: {_code_list(intake_blockers) if intake_blockers else '`none`'}",
        f"- Approval date status: `{approval_field_status.get('approval_date')}`",
        f"- Verification rerun status: `{approval_field_status.get('verification_commands_rerun')}`",
        f"- Rerun evidence status: `{rerun_evidence.get('status')}`",
        f"- Rerun evidence artifact: `{rerun_evidence.get('artifact')}`",
        f"- Risk warning clean status: `{risk_warning_clean_status.get('status')}`",
        f"- Risk warning blockers: {_code_list(risk_warning_blockers) if risk_warning_blockers else '`none`'}",
        f"- Risk tensor rematerialization preview: `{rematerialization_preview.get('status')}`",
        (
            "- Risk tensor preview would clear: "
            f"{_code_list(preview_clear_blockers) if preview_clear_blockers else '`none`'}"
        ),
        (
            "- Risk tensor preview decision status: "
            f"`{rematerialization_preview.get('preview_decision_status')}`"
        ),
        (
            "- Risk tensor preview decision blockers: "
            f"{_code_list(preview_decision_blockers) if preview_decision_blockers else '`none`'}"
        ),
        (
            "- Risk tensor preview writes database: "
            f"`{_summary_value(rematerialization_preview.get('writes_database'))}`"
        ),
        (
            "- Risk tensor preview approves metric or page: "
            f"`{_summary_value(rematerialization_preview.get('approves_metric_or_page'))}`"
        ),
        (
            "- Risk tensor preview certification effect: "
            f"`{_summary_value(rematerialization_preview.get('certification_effect'))}`"
        ),
        f"- Business owner approval boundary: `{approval_boundary.get('status')}`",
        f"- Template approval captured: `{_summary_value(approval_boundary.get('template_approval_captured'))}`",
        f"- Formal authorization allowed: `{_summary_value(approval_boundary.get('formal_authorization_allowed'))}`",
        f"- Governance write allowed: `{_summary_value(approval_boundary.get('governance_write_allowed'))}`",
        f"- Page execution proven: `{_summary_value(approval_boundary.get('page_execution_proven'))}`",
        f"- Full score closure ready: `{_summary_value(approval_boundary.get('full_score_closure_ready'))}`",
        "- Certification effect: `none`",
        "- Handoff approves metric or page: `false`",
        "- Handoff writes governance records: `false`",
        "- Handoff captures business-owner approval: `false`",
        (
            "- Business owner approval boundary blockers: "
            f"{_code_list(approval_boundary_blockers) if approval_boundary_blockers else '`none`'}"
        ),
        f"- Decision alignment: `{decision_alignment.get('status')}`",
        f"- Owner intake evidence alignment: `{owner_intake_alignment.get('status')}`",
        (
            "- Owner intake evidence alignment blockers: "
            f"{_code_list(owner_intake_alignment_blockers) if owner_intake_alignment_blockers else '`none`'}"
        ),
        f"- Score blocker action coverage: `{score_blocker_action_coverage.get('status')}`",
        (
            "- Score blocker action coverage blockers: "
            f"{_code_list(score_blocker_action_coverage_blockers) if score_blocker_action_coverage_blockers else '`none`'}"
        ),
        (
            "- Score blocker action coverage unassigned blockers: "
            f"{_code_list(score_blocker_action_coverage_unassigned) if score_blocker_action_coverage_unassigned else '`none`'}"
        ),
        (
            "- Score blocker action coverage covered blockers: "
            f"{_code_list(score_blocker_action_coverage_covered) if score_blocker_action_coverage_covered else '`none`'}"
        ),
        f"- Blocker closure matrix coverage: `{blocker_closure_matrix_coverage.get('status')}`",
        (
            "- Blocker closure matrix missing blockers: "
            f"{_code_list(blocker_closure_matrix_missing) if blocker_closure_matrix_missing else '`none`'}"
        ),
        (
            "- Blocker closure matrix unexpected blockers: "
            f"{_code_list(blocker_closure_matrix_unexpected) if blocker_closure_matrix_unexpected else '`none`'}"
        ),
        (
            "- Blocker closure matrix duplicate blockers: "
            f"{_code_list(blocker_closure_matrix_duplicates) if blocker_closure_matrix_duplicates else '`none`'}"
        ),
        "- Activation boundary: no automatic approval; owner decisions must be captured and rechecked.",
        (
            "- Generated owner fields boundary: KRD and maturity export manifests require "
            "`generated_owner_fields_must_be_blank=true`; dependency consistency blocks missing, false, "
            "or pre-filled generated owner fields."
        ),
    ]
    lines.extend(_owner_intake_boundary_lines(packet=packet, intake=intake))
    lines.extend(
        [
            "",
        ],
    )
    lines.extend(_owner_quickstart(owner_packets))
    lines.extend(
        [
            "",
            "## Current Blockers",
        ],
    )
    score_blockers = packet.get("score_blockers", [])
    assert isinstance(score_blockers, list)
    lines.extend(f"- `{blocker}`" for blocker in score_blockers)
    lines.append("")
    closure_matrix = packet.get("blocker_closure_matrix", [])
    assert isinstance(closure_matrix, list)
    lines.extend(_blocker_closure_matrix_lines(closure_matrix))
    lines.append("")
    lines.extend(_owner_checklist(owner_packets))
    lines.append("")
    lines.extend(_strict_gate_expectations(strict_gate_expectations))
    lines.append("")

    for owner in ("risk_owner", "data_owner", "business_owner"):
        owner_packet = owner_packets.get(owner, {})
        if isinstance(owner_packet, dict):
            lines.extend(_owner_section(owner, owner_packet))
            lines.append("")

    lines.extend(
        [
            "## Recheck Commands",
            f"- `{packet.get('owner_decision_intake_command')}`",
            f"- `{APPROVAL_PACKET_STRICT_COMMAND}`",
            f"- `{SCORECARD_STRICT_COMMAND}`",
            f"- `{ARTIFACT_PRESENCE_COMMAND}`",
            "",
        ],
    )
    return "\n".join(lines)


def build_markdown(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    docs_root: Path,
    limit: int,
) -> str:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="owner handoff packet limit",
    )
    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    return _render_packet_markdown(packet)


def _markdown_sha256(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def _current_status(output: Path, expected_markdown: str) -> dict[str, object]:
    actual_markdown = output.read_text(encoding="utf-8") if output.exists() else ""
    status = {
        "artifact": str(output),
        "status": "current" if actual_markdown == expected_markdown else "stale",
        "expected_length": len(expected_markdown),
        "actual_length": len(actual_markdown),
        "expected_sha256": _markdown_sha256(expected_markdown),
        "actual_sha256": _markdown_sha256(actual_markdown),
    }
    if status["status"] != "current":
        return status

    missing_fragments = [
        fragment
        for fragment in REQUIRED_CURRENT_SEMANTIC_FRAGMENTS
        if fragment not in actual_markdown
    ]
    if missing_fragments:
        return {
            **status,
            "status": "invalid_semantics",
            "semantic_status": "blocked",
            "missing_required_fragments": missing_fragments,
        }
    semantic_conflicts: list[str] = []
    activation_states = _activation_state_values(actual_markdown)
    if len(activation_states) != 1:
        semantic_conflicts.append("activation_state_ambiguous")
    strict_gate_summaries = _strict_gate_summary_lines(actual_markdown)
    if len(strict_gate_summaries) != 1:
        semantic_conflicts.append("strict_gate_summary_ambiguous")
    if (
        len(activation_states) == 1
        and activation_states[0] != "activated"
        and STRICT_GATE_READY_SUMMARY in actual_markdown
    ):
        semantic_conflicts.append("activation_state_not_activated_but_summary_claims_ready")
    if semantic_conflicts:
        return {
            **status,
            "status": "invalid_semantics",
            "semantic_status": "blocked",
            "semantic_conflicts": semantic_conflicts,
        }
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown owner handoff packet for portfolio-home closure.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="owner handoff packet limit",
        ),
        default=3,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Return non-zero unless the output file matches the freshly rendered handoff packet.",
    )
    args = parser.parse_args(argv)

    markdown = build_markdown(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        docs_root=Path(args.docs_root),
        limit=int(args.limit),
    )
    output = Path(args.output)
    if args.check_current:
        status = _current_status(output, markdown)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["status"] == "current" else 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
