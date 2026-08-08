from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import DEFAULT_TEMPLATE  # noqa: E402
from scripts.portfolio_home_closure_artifact_summary import (  # noqa: E402
    artifact_required_now,
)
from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    VERIFICATION_COMMANDS,
    _render_verification_commands,
)
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_manifest_consistency import resolve_docs_path  # noqa: E402
from scripts.portfolio_home_owner_handoff_packet import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_HANDOFF_OUTPUT,
    _current_status as handoff_markdown_current_status,
    build_markdown as build_handoff_markdown,
)
from scripts.portfolio_home_owner_input_needed_summary import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_SUMMARY_OUTPUT,
    build_summary,
    summary_sha256,
)


REQUIRED_OWNERS = ["risk_owner", "data_owner", "business_owner"]
OWNER_INPUT_SUMMARY_COMMAND = (
    "python scripts/portfolio_home_owner_input_needed_summary.py --limit 3 "
    "--output docs/portfolio/portfolio-home-owner-input-needed-summary.json --check-current"
)
SCORECARD_VERIFICATION_COMMANDS = {
    str(command.get("command"))
    for command in VERIFICATION_COMMANDS
    if isinstance(command, dict) and command.get("command")
}


def _scorecard_verification_commands(report_date: str) -> set[str]:
    """Allow the canonical date-qualified commands emitted by the scorecard.

    The scorecard renders report-date arguments into its owner-facing command
    list, while the static command registry remains date-independent.  Keep
    both forms accepted so handoff validation follows the selected report
    date without weakening the command allowlist.
    """

    rendered = {
        str(command.get("command"))
        for command in _render_verification_commands(report_date)
        if isinstance(command, dict) and command.get("command")
    }
    return SCORECARD_VERIFICATION_COMMANDS | rendered


def _without_report_date(command: str) -> str:
    tokens = command.split()
    normalized: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token == "--report-date":
            skip_next = True
            continue
        if token.startswith("--report-date="):
            continue
        normalized.append(token)
    return " ".join(normalized)


def _report_dates(command: str) -> list[str]:
    tokens = command.split()
    dates: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            dates.append(token)
            skip_next = False
            continue
        if token == "--report-date":
            skip_next = True
            continue
        if token.startswith("--report-date="):
            dates.append(token.split("=", 1)[1])
    return dates


def _recheck_command_allowlisted(command: str, *, report_date: str) -> bool:
    allowlisted_commands = _scorecard_verification_commands(report_date)
    if command in allowlisted_commands:
        return True
    dates = _report_dates(command)
    if not dates or any(date != report_date for date in dates):
        return False
    normalized = _without_report_date(command)
    return normalized in {_without_report_date(item) for item in SCORECARD_VERIFICATION_COMMANDS}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _append_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _owner_route_coverage(routes: list[object]) -> dict[str, object]:
    present = [
        str(route.get("owner"))
        for route in routes
        if isinstance(route, dict) and route.get("owner")
    ]
    seen: set[str] = set()
    duplicates: list[str] = []
    for owner in present:
        if owner in seen and owner not in duplicates:
            duplicates.append(owner)
        seen.add(owner)
    missing = [owner for owner in REQUIRED_OWNERS if owner not in present]
    unexpected = [owner for owner in present if owner not in REQUIRED_OWNERS]
    return {
        "status": "clean" if not missing and not unexpected and not duplicates else "blocked",
        "required_owners": REQUIRED_OWNERS,
        "present_owners": present,
        "missing_owners": missing,
        "unexpected_owners": unexpected,
        "duplicate_owners": duplicates,
    }


def _artifact_check(
    *,
    owner: str,
    artifact: str,
    docs_root: Path,
    artifact_current_summary: dict[str, object],
) -> dict[str, object]:
    required_now = artifact_required_now(artifact, artifact_current_summary)
    exists = resolve_docs_path(artifact, docs_root, ROOT).exists()
    blockers: list[str] = []
    if required_now and not exists:
        blockers.append(f"{owner}_decision_artifact_missing:{artifact}")
    return {
        "artifact": artifact,
        "required_now": required_now,
        "exists": exists,
        "status": "not_required" if not required_now else "present" if exists else "missing",
        "blockers": blockers,
    }


def _route_check(
    route: dict[str, object],
    *,
    docs_root: Path,
    artifact_current_summary: dict[str, object],
    report_date: str,
) -> dict[str, object]:
    owner = str(route.get("owner") or "unknown_owner")
    blockers: list[str] = []
    if not _list(route.get("blockers")):
        blockers.append(f"{owner}_blockers_missing")
    if not _list(route.get("decision_artifacts")):
        blockers.append(f"{owner}_decision_artifacts_missing")
    if not _list(route.get("required_fields")):
        blockers.append(f"{owner}_required_fields_missing")
    if not _list(route.get("recheck_commands")):
        blockers.append(f"{owner}_recheck_commands_missing")
    if not _list(route.get("exit_criteria")):
        blockers.append(f"{owner}_exit_criteria_missing")
    recheck_commands = [str(command) for command in _list(route.get("recheck_commands")) if command]
    unallowlisted_recheck_commands = [
        command
        for command in recheck_commands
        if not _recheck_command_allowlisted(command, report_date=report_date)
    ]
    if unallowlisted_recheck_commands:
        blockers.append(f"{owner}_recheck_commands_unallowlisted")

    artifact_checks = [
        _artifact_check(
            owner=owner,
            artifact=str(artifact),
            docs_root=docs_root,
            artifact_current_summary=artifact_current_summary,
        )
        for artifact in _list(route.get("decision_artifacts"))
    ]
    for item in artifact_checks:
        _append_unique(blockers, [str(blocker) for blocker in _list(item.get("blockers"))])

    return {
        "owner": owner,
        "status": "clean" if not blockers else "blocked",
        "blockers": blockers,
        "recheck_commands": recheck_commands,
        "unallowlisted_recheck_commands": unallowlisted_recheck_commands,
        "artifact_checks": artifact_checks,
    }


def _summary_current_status(output: Path, expected_summary: dict[str, object]) -> dict[str, object]:
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


def handoff_completeness_report(
    summary: dict[str, object],
    *,
    docs_root: Path,
    summary_current_status: dict[str, object] | None = None,
    handoff_current_status: dict[str, object] | None = None,
) -> dict[str, object]:
    routes = _list(summary.get("owner_routes"))
    coverage = _owner_route_coverage(routes)
    artifact_current_summary = _dict(summary.get("export_current_summary"))
    report_date = str(summary.get("report_date") or DEFAULT_REPORT_DATE)
    if "business_owner_approval_template" not in artifact_current_summary:
        artifact_current_summary["business_owner_approval_template"] = {
            "status": "present",
            "current": True,
            "current_blockers": [],
        }
    if "exact_bucket_schema_evidence" not in artifact_current_summary:
        risk_route = next(
            (route for route in routes if isinstance(route, dict) and route.get("owner") == "risk_owner"),
            {},
        )
        exact = _dict(risk_route.get("exact_bucket_schema_evidence"))
        artifact_current_summary["exact_bucket_schema_evidence"] = {
            "status": exact.get("status"),
            "current": bool(exact.get("valid")) and not _list(exact.get("blockers")),
            "current_blockers": _list(exact.get("blockers")),
        }
    if "nearest_bucket_approval_evidence" not in artifact_current_summary:
        risk_route = next(
            (route for route in routes if isinstance(route, dict) and route.get("owner") == "risk_owner"),
            {},
        )
        nearest = _dict(risk_route.get("nearest_bucket_approval_evidence"))
        artifact_current_summary["nearest_bucket_approval_evidence"] = {
            "status": nearest.get("status"),
            "current": bool(nearest.get("valid")) and not _list(nearest.get("blockers")),
            "current_blockers": _list(nearest.get("blockers")),
        }
    if "maturity_scoped_exclusion_evidence" not in artifact_current_summary:
        data_route = next(
            (route for route in routes if isinstance(route, dict) and route.get("owner") == "data_owner"),
            {},
        )
        scoped = _dict(data_route.get("scoped_exclusion_evidence"))
        artifact_current_summary["maturity_scoped_exclusion_evidence"] = {
            "status": scoped.get("status"),
            "current": bool(scoped.get("valid")) and not _list(scoped.get("blockers")),
            "current_blockers": _list(scoped.get("blockers")),
        }

    route_checks = [
        _route_check(
            route=route,
            docs_root=docs_root,
            artifact_current_summary=artifact_current_summary,
            report_date=report_date,
        )
        for route in routes
        if isinstance(route, dict)
    ]
    blockers: list[str] = []
    if summary_current_status is not None and not summary_current_status.get("current"):
        blockers.append("owner_input_needed_summary_stale")
    if handoff_current_status is not None and handoff_current_status.get("status") != "current":
        blockers.append("owner_handoff_packet_not_current")
    _append_unique(blockers, [str(item) for item in _list(coverage.get("missing_owners"))])
    _append_unique(blockers, [str(item) for item in _list(coverage.get("unexpected_owners"))])
    _append_unique(blockers, [str(item) for item in _list(coverage.get("duplicate_owners"))])
    for route in route_checks:
        _append_unique(blockers, [str(blocker) for blocker in _list(route.get("blockers"))])

    return {
        "check_kind": "portfolio_home_owner_handoff_completeness",
        "page_id": summary.get("page_id"),
        "page_slug": summary.get("page_slug"),
        "report_date": summary.get("report_date"),
        "current_score": summary.get("current_score"),
        "remaining_gap": summary.get("remaining_gap"),
        "score_status": summary.get("score_status"),
        "full_score_ready": summary.get("full_score_ready"),
        "status": "clean" if not blockers else "blocked",
        "handoff_ready": not blockers,
        "blockers": blockers,
        "required_command": OWNER_INPUT_SUMMARY_COMMAND,
        "summary_current_status": summary_current_status or {},
        "handoff_current_status": handoff_current_status or {},
        "owner_route_coverage": coverage,
        "route_checks": route_checks,
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "fills_owner_decisions": False,
            "captures_business_owner_approval": False,
            "proves_full_score_closure": False,
            "certification_effect": "none",
        },
    }


def build_report(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    docs_root: Path,
    limit: int,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="owner handoff completeness limit",
    )
    summary = build_summary(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    output = docs_root / DEFAULT_SUMMARY_OUTPUT.relative_to(ROOT / "docs")
    current_status = _summary_current_status(output, summary)
    handoff_output = docs_root / DEFAULT_HANDOFF_OUTPUT.relative_to(ROOT / "docs")
    expected_handoff_markdown = build_handoff_markdown(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    handoff_status = handoff_markdown_current_status(handoff_output, expected_handoff_markdown)
    return handoff_completeness_report(
        summary,
        docs_root=docs_root,
        summary_current_status=current_status,
        handoff_current_status=handoff_status,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home owner handoff routes are complete and current.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="owner handoff completeness limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless the owner handoff is complete and current.",
    )
    args = parser.parse_args(argv)

    report = build_report(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        docs_root=Path(args.docs_root),
        limit=int(args.limit),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_clean and report["status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
