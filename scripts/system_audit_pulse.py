from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.business_display_coverage_report import (  # noqa: E402
    build_report as build_business_display_coverage_report,
)
from scripts.codex_page_readiness import (  # noqa: E402
    build_all_page_readiness_report,
    build_route_scope_classification_report,
)
from scripts.system_audit_blocker_intake_board import (  # noqa: E402
    build_board as build_blocker_intake_board,
)
from scripts.verify_system_audit_completion_snapshot import (  # noqa: E402
    verify_completion_snapshot,
)


DEFAULT_MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"

EVIDENCE_SCOPE = {
    "read_only": True,
    "writes_duckdb": False,
    "writes_governance_records": False,
    "approves_metrics": False,
    "approves_pages": False,
    "captures_business_owner_approval": False,
    "certifies_routes": False,
    "clears_secret_scan": False,
    "promotes_candidate_data": False,
}


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fresh_command_summary(manifest: dict[str, Any], command: str) -> dict[str, Any] | None:
    for item in manifest.get("fresh_verification", {}).get("commands", []):
        if item.get("command") == command:
            return dict(item.get("summary") or {})
    return None


def _append_mismatch(
    errors: list[str],
    *,
    field: str,
    expected: Any,
    actual: Any,
) -> None:
    if actual != expected:
        errors.append(f"{field} expected {expected!r}, got {actual!r}")


def _route_scope_summary(route_scope: dict[str, Any]) -> dict[str, Any]:
    summary = dict(route_scope.get("summary") or {})
    return {
        "route_count": summary.get("route_count"),
        "seeded_trace_bundle_count": summary.get("seeded_trace_bundle_count"),
        "visible_navigation_route_count": summary.get("visible_navigation_route_count"),
        "visible_unseeded_route_count": summary.get("visible_unseeded_route_count"),
        "business_contract_certified_count": summary.get("business_contract_certified_count"),
        "evidence_pending_count": summary.get("evidence_pending_count"),
        "gate_i_gap_count": summary.get("gate_i_gap_count"),
        "frontend_ready_count": summary.get("frontend_ready_count"),
        "frontend_only_count": summary.get("frontend_only_count"),
        "unclassified_count": summary.get("unclassified_count"),
    }


def _completion_summary(completion: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": completion.get("status"),
        "open_blocker_count": completion.get("open_blocker_count"),
        "completion_gate_count": completion.get("completion_gate_count"),
        "follow_up_packet_count": completion.get("follow_up_packet_count"),
        "follow_up_brief_blocker_count": completion.get("follow_up_brief_blocker_count"),
        "follow_up_completion_order_status": completion.get(
            "follow_up_completion_order_status"
        ),
        "follow_up_completion_order_error_count": completion.get(
            "follow_up_completion_order_error_count"
        ),
        "calculation_prework_p1_count": completion.get("calculation_prework_p1_count"),
        "calculation_packet_p1_count": completion.get("calculation_packet_p1_count"),
        "calculation_meeting_record_complete": completion.get(
            "calculation_meeting_record_complete"
        ),
        "calculation_missing_meeting_field_count": completion.get(
            "calculation_missing_meeting_field_count"
        ),
        "calculation_post_owner_ready_for_implementation_count": completion.get(
            "calculation_post_owner_ready_for_implementation_count"
        ),
        "calculation_post_owner_owner_decision_capture_complete": completion.get(
            "calculation_post_owner_owner_decision_capture_complete"
        ),
        "calculation_post_owner_non_implementation_decision_count": completion.get(
            "calculation_post_owner_non_implementation_decision_count"
        ),
        "calculation_post_owner_blocking_reasons": completion.get(
            "calculation_post_owner_blocking_reasons"
        ),
        "calculation_post_owner_incomplete_count": completion.get(
            "calculation_post_owner_incomplete_count"
        ),
        "calculation_post_owner_invalid_selected_decision_count": completion.get(
            "calculation_post_owner_invalid_selected_decision_count"
        ),
        "calculation_post_owner_no_invalid_selected_decisions": completion.get(
            "calculation_post_owner_no_invalid_selected_decisions"
        ),
        "calculation_post_owner_global_gate_ready": completion.get(
            "calculation_post_owner_global_gate_ready"
        ),
        "calculation_post_owner_implementation_ready": completion.get(
            "calculation_post_owner_implementation_ready"
        ),
        "calculation_post_owner_plan_renderer_sync": completion.get(
            "calculation_post_owner_plan_renderer_sync"
        ),
        "error_count": len(completion.get("errors") or []),
    }


def _display_coverage_summary(coverage: dict[str, Any]) -> dict[str, Any]:
    summary = dict(coverage.get("summary") or {})
    return {
        "tracked_route_count": summary.get("tracked_route_count"),
        "route_gap_count": summary.get("route_gap_count"),
        "browser_smoke_a11y_configured_route_count": summary.get(
            "browser_smoke_a11y_configured_route_count"
        ),
        "browser_smoke_a11y_gap_count": summary.get("browser_smoke_a11y_gap_count"),
        "coverage_status": summary.get("coverage_status"),
    }


def _resolve_path(repo_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def _repo_relative_identifier(path: Path, *, repo_root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _strict_gate_summary(
    *,
    manifest: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    path_value = (manifest.get("artifacts") or {}).get("system_audit_monitoring_snapshot")
    if not path_value:
        return {
            "status": "missing_artifact_link",
            "source": None,
            "gate_count": None,
            "strict_pass_gate_count": None,
            "unexpected_gate_count": None,
            "expected_blocked_gate_count": None,
        }
    path = _resolve_path(repo_root, str(path_value))
    if not path.is_file():
        return {
            "status": "missing_artifact",
            "source": str(path),
            "gate_count": None,
            "strict_pass_gate_count": None,
            "unexpected_gate_count": None,
            "expected_blocked_gate_count": None,
        }
    monitoring = _load_json(path)
    matrix = monitoring.get("strict_gate_matrix") or {}
    return {
        "status": matrix.get("status"),
        "source": _repo_relative_identifier(path, repo_root=repo_root),
        "source_generated_at": monitoring.get("generated_at"),
        "completion_state": matrix.get("completion_state"),
        "full_score_ready": matrix.get("full_score_ready"),
        "open_blocker_count": matrix.get("open_blocker_count"),
        "gate_count": matrix.get("gate_count"),
        "expected_blocked_gate_count": matrix.get("expected_blocked_gate_count"),
        "strict_pass_gate_count": matrix.get("strict_pass_gate_count"),
        "unexpected_gate_count": matrix.get("unexpected_gate_count"),
    }


def strict_gate_summary_from_matrix(
    matrix: dict[str, Any],
    *,
    source: str | None = None,
    source_generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "status": matrix.get("status"),
        "source": source,
        "source_generated_at": source_generated_at,
        "completion_state": matrix.get("completion_state"),
        "full_score_ready": matrix.get("full_score_ready"),
        "open_blocker_count": matrix.get("open_blocker_count"),
        "gate_count": matrix.get("gate_count"),
        "expected_blocked_gate_count": matrix.get("expected_blocked_gate_count"),
        "strict_pass_gate_count": matrix.get("strict_pass_gate_count"),
        "unexpected_gate_count": matrix.get("unexpected_gate_count"),
    }


def _next_blocker_detail(board: dict[str, Any]) -> dict[str, Any] | None:
    next_blocker_id = board.get("next_blocker_id")
    for item in board.get("blockers") or []:
        if item.get("blocker_id") == next_blocker_id:
            return {
                "blocker_id": item.get("blocker_id"),
                "responsible_owner_type": item.get("responsible_owner_type"),
                "strict_gate_command": item.get("strict_gate_command"),
                "required_external_input_count": item.get(
                    "required_external_input_count"
                ),
                "first_required_external_input": item.get(
                    "first_required_external_input"
                ),
                "required_output_count": item.get("required_output_count"),
                "first_required_output": item.get("first_required_output"),
                "fail_closed_until": item.get("fail_closed_until"),
                "explicit_non_approval_boundary": item.get(
                    "explicit_non_approval_boundary"
                ),
            }
    return None


def blocker_intake_summary_from_board(board: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": board.get("status"),
        "blocker_count": board.get("blocker_count"),
        "completion_order": board.get("completion_order"),
        "next_blocker_id": board.get("next_blocker_id"),
        "next_blocker_detail": _next_blocker_detail(board),
        "evidence_scope": board.get("evidence_scope"),
        "boundary": board.get("boundary"),
    }


def _all_page_readiness_summary(
    *,
    manifest: dict[str, Any],
    include_full_readiness: bool,
) -> dict[str, Any]:
    if include_full_readiness:
        report = build_all_page_readiness_report()
        pages = list(report.get("pages") or [])
        missing_direct_records_count = sum(
            1
            for page in pages
            if (page.get("governance_record_validation") or {}).get("status")
            == "missing_direct_records"
        )
        direct_ready_count = sum(
            1
            for page in pages
            if (page.get("governance_record_validation") or {}).get("status")
            == "direct_records_ready_for_audit_review"
        )
        catalog_incomplete_count = sum(
            1
            for page in pages
            if (page.get("catalog_date_evidence") or {}).get("status") == "incomplete"
        )
        return {
            "source": "live_full_readiness",
            "page_count": report["summary"]["page_count"],
            "static_pass_count": report["summary"]["static_pass_count"],
            "run_supported_count": report["summary"]["run_supported_count"],
            "owner_approval_pending_count": report["summary"][
                "business_owner_approval_pending_count"
            ],
            "owner_approval_action_item_sum": report["summary"][
                "business_owner_approval_action_item_count"
            ],
            "direct_evidence_null_count": sum(
                1 for page in pages if page.get("governance_record_validation") is None
            ),
            "audit_review_null_count": sum(
                1 for page in pages if page.get("audit_review") is None
            ),
            "missing_direct_records_count": missing_direct_records_count,
            "direct_records_ready_for_audit_review_count": direct_ready_count,
            "catalog_date_incomplete_count": catalog_incomplete_count,
        }

    summary = _fresh_command_summary(
        manifest,
        "python scripts\\codex_page_readiness.py --all",
    )
    return {
        "source": "manifest_last_full_readiness",
        **(summary or {}),
    }


def build_pulse(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = ROOT,
    generated_at: str | None = None,
    include_full_readiness: bool = False,
    strict_gate_summary_override: dict[str, Any] | None = None,
    completion_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _default_generated_at()
    manifest = _load_json(manifest_path)
    counts = dict(manifest.get("counts") or {})
    route_scope = build_route_scope_classification_report()
    coverage = build_business_display_coverage_report(repo_root=repo_root)
    completion = (
        dict(completion_override)
        if completion_override is not None
        else verify_completion_snapshot(
            manifest_path=manifest_path,
            repo_root=repo_root,
            verify_monitoring=False,
        )
    )
    blocker_intake_board = build_blocker_intake_board(
        generated_at=generated_at,
        manifest_path=manifest_path,
        repo_root=repo_root,
    )

    open_blockers = list(manifest.get("open_blockers") or [])
    route_summary = _route_scope_summary(route_scope)
    coverage_summary = _display_coverage_summary(coverage)
    completion_status = _completion_summary(completion)
    strict_gate_status = (
        dict(strict_gate_summary_override)
        if strict_gate_summary_override is not None
        else _strict_gate_summary(manifest=manifest, repo_root=repo_root)
    )
    readiness_summary = _all_page_readiness_summary(
        manifest=manifest,
        include_full_readiness=include_full_readiness,
    )

    drift_errors: list[str] = []
    if completion.get("status") != "pass":
        drift_errors.extend(str(error) for error in completion.get("errors") or [])
    if strict_gate_status.get("status") != "pass":
        drift_errors.append(
            f"strict_gate_matrix.status expected 'pass', got {strict_gate_status.get('status')!r}"
        )
    _append_mismatch(
        drift_errors,
        field="strict_gate_matrix.open_blocker_count",
        expected=len(open_blockers),
        actual=strict_gate_status.get("open_blocker_count"),
    )
    _append_mismatch(
        drift_errors,
        field="strict_gate_matrix.strict_pass_gate_count",
        expected=0,
        actual=strict_gate_status.get("strict_pass_gate_count"),
    )
    _append_mismatch(
        drift_errors,
        field="strict_gate_matrix.unexpected_gate_count",
        expected=0,
        actual=strict_gate_status.get("unexpected_gate_count"),
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.seeded_trace_bundle_count",
        expected=counts.get("seeded_pages"),
        actual=route_summary["seeded_trace_bundle_count"],
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.business_contract_certified_count",
        expected=counts.get("business_contract_certified_routes"),
        actual=route_summary["business_contract_certified_count"],
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.visible_unseeded_route_count",
        expected=0,
        actual=route_summary["visible_unseeded_route_count"],
    )
    _append_mismatch(
        drift_errors,
        field="route_scope.unclassified_count",
        expected=0,
        actual=route_summary["unclassified_count"],
    )
    _append_mismatch(
        drift_errors,
        field="business_display.tracked_route_count",
        expected=counts.get("business_display_tracked_routes"),
        actual=coverage_summary["tracked_route_count"],
    )
    _append_mismatch(
        drift_errors,
        field="business_display.route_gap_count",
        expected=counts.get("business_display_route_gaps"),
        actual=coverage_summary["route_gap_count"],
    )
    _append_mismatch(
        drift_errors,
        field="business_display.browser_smoke_a11y_configured_route_count",
        expected=counts.get("browser_smoke_a11y_configured_routes"),
        actual=coverage_summary["browser_smoke_a11y_configured_route_count"],
    )
    if readiness_summary.get("page_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.page_count",
            expected=counts.get("seeded_pages"),
            actual=readiness_summary.get("page_count"),
        )
    if readiness_summary.get("static_pass_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.static_pass_count",
            expected=counts.get("static_pass_pages"),
            actual=readiness_summary.get("static_pass_count"),
        )
    if readiness_summary.get("direct_evidence_null_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.direct_evidence_null_count",
            expected=0,
            actual=readiness_summary.get("direct_evidence_null_count"),
        )
    if readiness_summary.get("audit_review_null_count") is not None:
        _append_mismatch(
            drift_errors,
            field="readiness.audit_review_null_count",
            expected=0,
            actual=readiness_summary.get("audit_review_null_count"),
        )

    return {
        "report_kind": "system_audit_pulse",
        "generated_at": generated_at,
        "repo_root": ".",
        "manifest_path": _repo_relative_identifier(
            manifest_path,
            repo_root=repo_root,
        ),
        "status": "pass" if not drift_errors else "fail",
        "full_score_ready": False,
        "completion_state": "not_complete" if open_blockers else "ready_for_completion_audit",
        "open_blocker_count": len(open_blockers),
        "calculation_post_owner_plan_renderer_sync": completion_status.get(
            "calculation_post_owner_plan_renderer_sync"
        ),
        "open_blockers": [
            {
                "id": blocker.get("id"),
                "status": blocker.get("status"),
                "last_checked_at": blocker.get("last_checked_at"),
            }
            for blocker in open_blockers
        ],
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "route_scope": route_summary,
        "business_display": coverage_summary,
        "completion_snapshot": completion_status,
        "blocker_intake_board": blocker_intake_summary_from_board(
            blocker_intake_board
        ),
        "strict_gate_matrix": strict_gate_status,
        "all_page_readiness": readiness_summary,
        "drift_errors": drift_errors,
        "claim_boundary": (
            "This pulse is a read-only monitoring aggregate. It does not approve metrics, "
            "pages, owner signoff, governance records, secret hygiene, direct App MCP/GitNexus "
            "evidence, or route certification."
        ),
    }


def format_markdown_pulse(report: dict[str, Any]) -> str:
    route_scope = report["route_scope"]
    business_display = report["business_display"]
    completion = report["completion_snapshot"]
    blocker_intake = report["blocker_intake_board"]
    next_blocker = blocker_intake.get("next_blocker_detail") or {}
    strict_gates = report["strict_gate_matrix"]
    readiness = report["all_page_readiness"]
    lines = [
        "# System Audit Pulse",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Completion state: `{report['completion_state']}`",
        f"- Full score ready: `{str(report['full_score_ready']).lower()}`",
        f"- Open blockers: `{report['open_blocker_count']}`",
        f"- Next blocker: `{blocker_intake['next_blocker_id']}`",
        "",
        "## Live Counts",
        "",
        "| Lane | Key Counts |",
        "| --- | --- |",
        (
            "| Route scope | "
            f"`routes={route_scope['route_count']}`, "
            f"`business_contract_certified={route_scope['business_contract_certified_count']}`, "
            f"`evidence_pending={route_scope['evidence_pending_count']}`, "
            f"`visible_unseeded={route_scope['visible_unseeded_route_count']}`, "
            f"`unclassified={route_scope['unclassified_count']}` |"
        ),
        (
            "| Business display | "
            f"`tracked_routes={business_display['tracked_route_count']}`, "
            f"`route_gaps={business_display['route_gap_count']}`, "
            f"`smoke_configured={business_display['browser_smoke_a11y_configured_route_count']}` |"
        ),
        (
            "| Completion snapshot | "
            f"`status={completion['status']}`, "
            f"`open_blockers={completion['open_blocker_count']}`, "
            f"`p1_packet={completion['calculation_packet_p1_count']}`, "
            f"`meeting_record={str(completion['calculation_meeting_record_complete']).lower()}`, "
            f"`missing_meeting_fields={completion['calculation_missing_meeting_field_count']}`, "
            f"`post_owner_ready={completion['calculation_post_owner_ready_for_implementation_count']}`, "
            f"`post_owner_incomplete={completion['calculation_post_owner_incomplete_count']}`, "
            f"`post_owner_invalid_selected={completion['calculation_post_owner_invalid_selected_decision_count']}`, "
            f"`post_owner_gate={str(completion['calculation_post_owner_global_gate_ready']).lower()}`, "
            f"`post_owner_sync={str(completion['calculation_post_owner_plan_renderer_sync']).lower()}`, "
            f"`order_guard={completion['follow_up_completion_order_status']}`, "
            f"`errors={completion['error_count']}` |"
        ),
        (
            "| Blocker intake | "
            f"`status={blocker_intake['status']}`, "
            f"`next={blocker_intake['next_blocker_id']}`, "
            f"`owner={next_blocker.get('responsible_owner_type')}` |"
        ),
        (
            "| Strict gates | "
            f"`status={strict_gates['status']}`, "
            f"`pass={strict_gates['strict_pass_gate_count']}/{strict_gates['gate_count']}`, "
            f"`expected_blocked={strict_gates['expected_blocked_gate_count']}`, "
            f"`unexpected={strict_gates['unexpected_gate_count']}` |"
        ),
        (
            "| All-page readiness | "
            f"`source={readiness['source']}`, "
            f"`pages={readiness.get('page_count')}`, "
            f"`static_pass={readiness.get('static_pass_count')}`, "
            f"`direct_evidence_null={readiness.get('direct_evidence_null_count')}`, "
            f"`audit_review_null={readiness.get('audit_review_null_count')}` |"
        ),
        "",
        "## Next Blocker",
        "",
    ]
    if next_blocker:
        lines.extend(
            [
                f"- ID: `{next_blocker['blocker_id']}`",
                f"- Owner type: `{next_blocker['responsible_owner_type']}`",
                f"- Strict gate: `{next_blocker['strict_gate_command']}`",
                (
                    "- First required external input: "
                    f"{next_blocker['first_required_external_input']}"
                ),
                f"- Fail-closed until: {next_blocker['fail_closed_until']}",
            ]
        )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Open Blockers",
            "",
        ]
    )
    if report["open_blockers"]:
        lines.extend(
            f"- `{item['id']}`: `{item['status']}`; last_checked_at=`{item['last_checked_at']}`"
            for item in report["open_blockers"]
        )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Drift",
            "",
        ]
    )
    if report["drift_errors"]:
        lines.extend(f"- `{error}`" for error in report["drift_errors"])
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            report["claim_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only pulse for system audit readiness and closure drift.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the system audit manifest.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Stable timestamp for reproducible tests.",
    )
    parser.add_argument(
        "--include-full-readiness",
        action="store_true",
        help="Run the slower all-page readiness scan instead of using the manifest's last full scan.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. The script never writes DuckDB or governance records.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--require-full-score-ready",
        action="store_true",
        help=(
            "Exit non-zero unless the pulse proves full_score_ready=true. "
            "Use this as a strict gate; the normal pulse remains a health monitor."
        ),
    )
    args = parser.parse_args(argv)

    report = build_pulse(
        manifest_path=args.manifest,
        generated_at=args.generated_at,
        include_full_readiness=args.include_full_readiness,
    )
    payload = (
        format_markdown_pulse(report)
        if args.format == "markdown"
        else json.dumps(report, ensure_ascii=False, indent=2)
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if report["status"] != "pass":
        return 1
    if args.require_full_score_ready and not report["full_score_ready"]:
        print(
            (
                "System audit is not full-score ready: "
                f"completion_state={report['completion_state']}, "
                f"open_blocker_count={report['open_blocker_count']}, "
                f"drift_error_count={len(report['drift_errors'])}"
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
