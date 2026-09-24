from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_closure_scorecard import build_scorecard  # noqa: E402
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_maturity_remediation_queue import build_queue as build_maturity_queue  # noqa: E402
from scripts.portfolio_home_owner_decision_intake_check import build_intake_check  # noqa: E402
from scripts.portfolio_home_risk_warning_consistency import build_evidence as build_risk_warning  # noqa: E402


EVIDENCE_SCOPE = {
    "read_only": True,
    "writes_database": False,
    "fills_owner_decisions": False,
    "captures_approval": False,
    "approves_metric_or_page": False,
    "changes_score": False,
    "certification_effect": "none",
}

OWNER_ORDER = ["risk_owner", "data_owner", "business_owner"]
BLOCKER_OWNER = {
    "risk_tensor_quality_warning": "risk_owner",
    "krd_contract_decision_required": "risk_owner",
    "krd_bucket_warning_mismatch": "risk_owner",
    "bond_maturity_date_remediation_required": "data_owner",
    "tyw_liability_maturity_date_remediation_required": "data_owner",
    "bond_matured_outstanding_reconciliation_required": "data_owner",
    "duration_exclusion_warning_mismatch": "data_owner",
    "risk_tensor_warning_mismatch": "risk_owner",
    "business_owner_approval": "business_owner",
    "owner_decision_intake_blocked": "business_owner",
}
REQUIRED_FULL_SCORE_COMMAND = (
    "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
)


def _dict_value(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _list_value(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    return value if isinstance(value, list) else []


def _int_value(payload: dict[str, object], key: str) -> int:
    return int(payload.get(key) or 0)


def _action_by_blocker(scorecard: dict[str, object]) -> dict[str, dict[str, object]]:
    actions: dict[str, dict[str, object]] = {}
    for action in _list_value(scorecard, "score_blocker_actions"):
        if not isinstance(action, dict):
            continue
        blocker = str(action.get("blocker") or "")
        if blocker:
            actions[blocker] = action
    return actions


def _strict_gate_command(blocker: str, actions: dict[str, dict[str, object]]) -> str:
    action = actions.get(blocker, {})
    command = action.get("evidence_command")
    return str(command or "")


def _next_action(blocker: str, actions: dict[str, dict[str, object]]) -> str:
    action = actions.get(blocker, {})
    return str(action.get("next_action") or "")


def _exit_criteria(blocker: str, actions: dict[str, dict[str, object]]) -> str:
    action = actions.get(blocker, {})
    return str(action.get("exit_criteria") or "")


def _candidate_boundary(maturity_queue: dict[str, object]) -> dict[str, object]:
    candidate_evidence = _dict_value(maturity_queue, "maturity_candidate_evidence")
    evidence_scope = _dict_value(candidate_evidence, "evidence_scope")
    return {
        "status": candidate_evidence.get("status"),
        "strict_gate_effect": candidate_evidence.get("strict_gate_effect"),
        "approves_metric_or_page": bool(evidence_scope.get("approves_metric_or_page")),
        "fills_maturity_date": bool(evidence_scope.get("fills_maturity_date")),
        "writes_database": bool(evidence_scope.get("writes_database")),
    }


def _bond_maturity_evidence(maturity_queue: dict[str, object]) -> dict[str, object]:
    summary = _dict_value(maturity_queue, "bond_missing_maturity_summary")
    candidate = _dict_value(maturity_queue, "maturity_candidate_evidence")
    return {
        "missing_maturity_rows": _int_value(summary, "missing_maturity_rows"),
        "missing_maturity_market_value": str(summary.get("missing_maturity_market_value") or "0"),
        "candidate_evidence_status": str(candidate.get("status") or "unknown"),
    }


def _tyw_maturity_evidence(maturity_queue: dict[str, object]) -> dict[str, object]:
    summary = _dict_value(maturity_queue, "tyw_liability_missing_maturity_summary")
    candidate = _dict_value(maturity_queue, "maturity_candidate_evidence")
    return {
        "missing_maturity_rows": _int_value(summary, "missing_maturity_rows"),
        "missing_maturity_principal": str(summary.get("missing_maturity_principal") or "0"),
        "candidate_evidence_status": str(candidate.get("status") or "unknown"),
    }


def _risk_warning_evidence(risk_warning: dict[str, object]) -> dict[str, object]:
    return {
        "decision_status": risk_warning.get("decision_status"),
        "decision_blockers": _list_value(risk_warning, "decision_blockers"),
        "warning_consistency_status": risk_warning.get("warning_consistency_status"),
        "consistency_blockers": _list_value(risk_warning, "consistency_blockers"),
        "duration_exclusion_delta_detail": _dict_value(
            risk_warning,
            "duration_exclusion_delta_detail",
        ),
    }


def _krd_evidence(scorecard: dict[str, object]) -> dict[str, object]:
    gates = _dict_value(scorecard, "gates")
    krd_contract = _dict_value(gates, "krd_contract")
    return {
        "status": krd_contract.get("status"),
        "blockers": _list_value(krd_contract, "blockers"),
        "decision_options": _list_value(krd_contract, "decision_options"),
        "krd_remap_summary": _list_value(krd_contract, "krd_remap_summary"),
    }


def _business_approval_evidence(scorecard: dict[str, object]) -> dict[str, object]:
    gates = _dict_value(scorecard, "gates")
    approval = _dict_value(gates, "business_owner_approval")
    return {
        "status": approval.get("status"),
        "blockers": _list_value(approval, "blockers"),
        "approval_action_item_count": approval.get("approval_action_item_count"),
    }


def _owner_intake_evidence(intake: dict[str, object]) -> dict[str, object]:
    return {
        "intake_status": intake.get("intake_status"),
        "intake_ready": intake.get("intake_ready"),
        "owner_decision_statuses": _dict_value(intake, "owner_decision_statuses"),
        "decision_gap_counts": _dict_value(intake, "decision_gap_counts"),
        "blockers": _list_value(intake, "blockers"),
    }


def _current_evidence(
    blocker: str,
    *,
    scorecard: dict[str, object],
    maturity_queue: dict[str, object],
    risk_warning: dict[str, object],
    intake: dict[str, object],
) -> dict[str, object]:
    if blocker == "bond_matured_outstanding_reconciliation_required":
        gates = _dict_value(scorecard, "gates")
        full_closure = _dict_value(gates, "full_closure_evidence")
        return _dict_value(full_closure, "bond_matured_outstanding")
    if blocker == "bond_maturity_date_remediation_required":
        return _bond_maturity_evidence(maturity_queue)
    if blocker == "tyw_liability_maturity_date_remediation_required":
        return _tyw_maturity_evidence(maturity_queue)
    if blocker in {
        "risk_tensor_quality_warning",
        "duration_exclusion_warning_mismatch",
        "krd_bucket_warning_mismatch",
        "risk_tensor_warning_mismatch",
    }:
        return _risk_warning_evidence(risk_warning)
    if blocker == "krd_contract_decision_required":
        return _krd_evidence(scorecard)
    if blocker == "business_owner_approval":
        return _business_approval_evidence(scorecard)
    if blocker == "owner_decision_intake_blocked":
        return _owner_intake_evidence(intake)
    return {}


def _blocker_matrix(
    scorecard: dict[str, object],
    *,
    maturity_queue: dict[str, object],
    risk_warning: dict[str, object],
    intake: dict[str, object],
) -> list[dict[str, object]]:
    actions = _action_by_blocker(scorecard)
    rows: list[dict[str, object]] = []
    for blocker_value in _list_value(scorecard, "score_blockers"):
        blocker = str(blocker_value)
        owner = BLOCKER_OWNER.get(blocker, "unassigned")
        rows.append(
            {
                "blocker": blocker,
                "owner": owner,
                "closure_status": "blocked",
                "strict_gate_command": _strict_gate_command(blocker, actions),
                "next_action": _next_action(blocker, actions),
                "exit_criteria": _exit_criteria(blocker, actions),
                "current_evidence": _current_evidence(
                    blocker,
                    scorecard=scorecard,
                    maturity_queue=maturity_queue,
                    risk_warning=risk_warning,
                    intake=intake,
                ),
            }
        )
    return rows


def _owner_routes(blocker_matrix: list[dict[str, object]]) -> list[dict[str, object]]:
    routes: list[dict[str, object]] = []
    for owner in OWNER_ORDER:
        blockers = [
            str(row.get("blocker"))
            for row in blocker_matrix
            if row.get("owner") == owner
        ]
        routes.append(
            {
                "owner": owner,
                "status": "clean" if not blockers else "blocked",
                "blockers": blockers,
            }
        )
    return routes


def _markdown_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_code(value: object) -> str:
    text = _markdown_value(value).replace("`", "\\`")
    return f"`{text}`"


def _markdown_cell(value: object, *, code: bool = False) -> str:
    text = _markdown_code(value) if code else _markdown_value(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _markdown_evidence_items(
    key: str,
    value: object,
) -> list[tuple[str, object]]:
    if isinstance(value, dict):
        items: list[tuple[str, object]] = []
        status = value.get("status")
        if status is not None:
            items.append((f"{key}.status", status))
        delta = value.get("delta")
        if isinstance(delta, dict):
            for delta_key in sorted(delta):
                items.append((f"{key}.delta.{delta_key}", delta.get(delta_key)))
        for nested_key in sorted(value):
            if nested_key in {"status", "delta"}:
                continue
            nested_value = value.get(nested_key)
            if isinstance(nested_value, list):
                items.append((f"{key}.{nested_key}", f"{len(nested_value)} rows"))
            elif not isinstance(nested_value, dict):
                items.append((f"{key}.{nested_key}", nested_value))
        if items:
            return items
        return [(key, "nested evidence available in JSON output")]
    if isinstance(value, list):
        return [(key, f"{len(value)} rows")]
    return [(key, value)]


def render_markdown(preflight: dict[str, object]) -> str:
    evidence_scope = _dict_value(preflight, "evidence_scope")
    candidate_boundary = _dict_value(preflight, "candidate_boundary")
    owner_routes = [
        route
        for route in _list_value(preflight, "owner_routes")
        if isinstance(route, dict)
    ]
    blocker_matrix = [
        row
        for row in _list_value(preflight, "blocker_matrix")
        if isinstance(row, dict)
    ]

    lines = [
        "# Portfolio Home Full-Score Preflight",
        "",
        "## Summary",
        f"- Page: {_markdown_code(preflight.get('page_id'))} ({_markdown_code(preflight.get('page_slug'))})",
        f"- Report date: {_markdown_code(preflight.get('report_date'))}",
        f"- DuckDB path: {_markdown_code(preflight.get('duckdb_path'))}",
        f"- Preflight status: {_markdown_code(preflight.get('preflight_status'))}",
        f"- Current score: {_markdown_code(preflight.get('current_score'))}",
        f"- Remaining gap: {_markdown_code(preflight.get('remaining_gap'))}",
        f"- Full score ready: {_markdown_code(preflight.get('full_score_ready'))}",
        f"- Score status: {_markdown_code(preflight.get('score_status'))}",
        "",
        "This preflight is read-only and is not an approval.",
        "",
        "## Evidence Boundary",
        f"- Read only: {_markdown_code(evidence_scope.get('read_only'))}",
        f"- Writes database: {_markdown_code(evidence_scope.get('writes_database'))}",
        f"- Fills owner decisions: {_markdown_code(evidence_scope.get('fills_owner_decisions'))}",
        f"- Captures approval: {_markdown_code(evidence_scope.get('captures_approval'))}",
        f"- Approves metric or page: {_markdown_code(evidence_scope.get('approves_metric_or_page'))}",
        f"- Changes score: {_markdown_code(evidence_scope.get('changes_score'))}",
        f"- Certification effect: {_markdown_code(evidence_scope.get('certification_effect'))}",
        f"- Candidate boundary status: {_markdown_code(candidate_boundary.get('status'))}",
        f"- Candidate strict gate effect: {_markdown_code(candidate_boundary.get('strict_gate_effect'))}",
        f"- Candidate approves metric or page: {_markdown_code(candidate_boundary.get('approves_metric_or_page'))}",
        f"- Candidate fills maturity date: {_markdown_code(candidate_boundary.get('fills_maturity_date'))}",
        f"- Candidate writes database: {_markdown_code(candidate_boundary.get('writes_database'))}",
        "",
        "## Owner Routes",
    ]
    for route in owner_routes:
        blockers = [
            _markdown_code(blocker)
            for blocker in _list_value(route, "blockers")
        ]
        blocker_text = ", ".join(blockers) if blockers else "none"
        lines.append(
            f"- {_markdown_code(route.get('owner'))}: "
            f"{_markdown_code(route.get('status'))} - {blocker_text}"
        )

    lines.extend(
        [
            "",
            "## Blocker Matrix",
            "| Blocker | Owner | Status | Strict Gate | Next Action | Exit Criteria |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in blocker_matrix:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(row.get("blocker")),
                    _markdown_cell(row.get("owner")),
                    _markdown_cell(row.get("closure_status")),
                    _markdown_cell(row.get("strict_gate_command"), code=True),
                    _markdown_cell(row.get("next_action")),
                    _markdown_cell(row.get("exit_criteria")),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Current Evidence")
    for row in blocker_matrix:
        blocker = str(row.get("blocker") or "unknown")
        evidence = _dict_value(row, "current_evidence")
        lines.append("")
        lines.append(f"### {blocker}")
        if not evidence:
            lines.append("- `status`: `no_current_evidence`")
            continue
        for key in sorted(evidence):
            for item_key, item_value in _markdown_evidence_items(key, evidence.get(key)):
                lines.append(f"- {_markdown_code(item_key)}: {_markdown_code(item_value)}")

    lines.extend(
        [
            "",
            "## Required Final Gate",
            _markdown_code(preflight.get("required_next_command")),
        ]
    )
    return "\n".join(lines) + "\n"


def build_preflight(
    *,
    duckdb_path: Path,
    report_date: str,
    limit: int,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(limit, label="full-score preflight limit")
    scorecard = build_scorecard(
        duckdb_path=Path(duckdb_path),
        template_path=Path("docs/portfolio/portfolio-home-business-owner-approval-template.md"),
        report_date=report_date,
        limit=limit,
    )
    maturity_queue = build_maturity_queue(
        duckdb_path=Path(duckdb_path),
        report_date=report_date,
        limit=limit,
    )
    risk_warning = build_risk_warning(
        duckdb_path=Path(duckdb_path),
        report_date=report_date,
    )
    intake = build_intake_check(
        duckdb_path=Path(duckdb_path),
        docs_root=Path("docs"),
        template_path=Path("docs/portfolio/portfolio-home-business-owner-approval-template.md"),
        report_date=report_date,
        limit=limit,
    )
    blocker_matrix = _blocker_matrix(
        scorecard,
        maturity_queue=maturity_queue,
        risk_warning=risk_warning,
        intake=intake,
    )
    full_score_ready = bool(scorecard.get("full_score_ready") is True)
    preflight_status = "ready_for_full_score" if full_score_ready else "blocked"
    return {
        "check_kind": "portfolio_home_full_score_preflight",
        "page_id": scorecard.get("page_id"),
        "page_slug": scorecard.get("page_slug"),
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "preflight_status": preflight_status,
        "current_score": scorecard.get("current_score"),
        "remaining_gap": scorecard.get("remaining_gap"),
        "full_score_ready": full_score_ready,
        "score_status": scorecard.get("score_status"),
        "score_blockers": _list_value(scorecard, "score_blockers"),
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "candidate_boundary": _candidate_boundary(maturity_queue),
        "owner_routes": _owner_routes(blocker_matrix),
        "blocker_matrix": blocker_matrix,
        "required_next_command": REQUIRED_FULL_SCORE_COMMAND.replace(
            " --limit",
            f" --report-date {report_date} --limit",
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only portfolio-home full-score preflight matrix.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="full-score preflight limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-full-score-ready",
        action="store_true",
        help="Return non-zero unless the preflight is ready for full score.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format.",
    )
    args = parser.parse_args(argv)

    preflight = build_preflight(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        limit=int(args.limit),
    )
    if args.format == "markdown":
        print(render_markdown(preflight), end="")
    else:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
    if args.require_full_score_ready and preflight["preflight_status"] != "ready_for_full_score":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
