from __future__ import annotations

import argparse
import json
import re
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
from scripts.portfolio_home_closure_scorecard import VERIFICATION_COMMANDS  # noqa: E402
from scripts.portfolio_home_owner_action_packet import build_packet  # noqa: E402


DECISION_ARTIFACT_REQUIRED_BLOCKERS = {
    "krd_contract_decision_required",
    "bond_maturity_date_remediation_required",
    "tyw_liability_maturity_date_remediation_required",
    "business_owner_approval",
    "owner_decision_intake_blocked",
}
EVIDENCE_SOURCE_REQUIRED_BLOCKERS = {
    "risk_tensor_quality_warning",
    "bond_matured_outstanding_reconciliation_required",
}
BASE_REQUIRED_FIELDS = [
    "owner",
    "next_action",
    "recheck_commands",
    "exit_criteria",
    "removes_blocker_when",
]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _truthy_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def _command_allowlist_key(command: object) -> str:
    return re.sub(r"\s+--report-date\s+\S+", "", str(command), count=1).strip()


def _matrix_coverage(
    score_blockers: list[str],
    matrix: list[object],
) -> dict[str, object]:
    covered = [
        str(row.get("blocker"))
        for row in matrix
        if isinstance(row, dict) and row.get("blocker")
    ]
    seen: set[str] = set()
    duplicates: list[str] = []
    for blocker in covered:
        if blocker in seen and blocker not in duplicates:
            duplicates.append(blocker)
        seen.add(blocker)
    missing = [blocker for blocker in score_blockers if blocker not in set(covered)]
    unexpected = [blocker for blocker in covered if blocker not in set(score_blockers)]
    return {
        "status": "clean" if not missing and not unexpected and not duplicates else "blocked",
        "expected_blockers": score_blockers,
        "covered_blockers": covered,
        "missing_blockers": missing,
        "unexpected_blockers": unexpected,
        "duplicate_blockers": duplicates,
    }


def _row_missing_fields(row: dict[str, object]) -> list[str]:
    missing = [
        field
        for field in BASE_REQUIRED_FIELDS
        if not row.get(field)
    ]
    if not _truthy_list(row.get("recheck_commands")) and "recheck_commands" not in missing:
        missing.append("recheck_commands")
    blocker = str(row.get("blocker") or "")
    if blocker in EVIDENCE_SOURCE_REQUIRED_BLOCKERS:
        if not _truthy_list(row.get("evidence_sources")):
            missing.insert(0, "evidence_sources")
    if blocker in DECISION_ARTIFACT_REQUIRED_BLOCKERS:
        if not _truthy_list(row.get("decision_artifacts")):
            missing.append("decision_artifacts")
        if not _truthy_list(row.get("required_fields")):
            missing.append("required_fields")
    return missing


def matrix_completeness_report(
    *,
    score_blockers: list[str],
    matrix: list[object],
    verification_commands: list[object] | None = None,
) -> dict[str, object]:
    coverage = _matrix_coverage(score_blockers, matrix)
    allowed_commands = {
        _command_allowlist_key(command.get("command"))
        for command in verification_commands or []
        if isinstance(command, dict) and command.get("command")
    } | {
        _command_allowlist_key(command)
        for command in verification_commands or []
        if isinstance(command, str)
    }
    rows: list[dict[str, object]] = []
    blockers = list(_list(coverage.get("missing_blockers")))
    blockers.extend(_list(coverage.get("unexpected_blockers")))
    blockers.extend(_list(coverage.get("duplicate_blockers")))
    for raw_row in matrix:
        if not isinstance(raw_row, dict):
            continue
        blocker = str(raw_row.get("blocker") or "")
        missing_fields = _row_missing_fields(raw_row)
        row_blockers = [f"{blocker}_{field}_missing" for field in missing_fields]
        recheck_commands = [
            str(command)
            for command in _list(raw_row.get("recheck_commands"))
            if command
        ]
        unallowlisted = [
            command
            for command in recheck_commands
            if allowed_commands and _command_allowlist_key(command) not in allowed_commands
        ]
        if unallowlisted:
            row_blockers.append(f"{blocker}_recheck_commands_unallowlisted")
        evidence_sources = _list(raw_row.get("evidence_sources"))
        evidence_source_commands = [
            str(source.get("command"))
            for source in evidence_sources
            if isinstance(source, dict) and source.get("command")
        ]
        unallowlisted_evidence_source_commands = [
            command
            for command in evidence_source_commands
            if allowed_commands and _command_allowlist_key(command) not in allowed_commands
        ]
        if unallowlisted_evidence_source_commands:
            row_blockers.append(f"{blocker}_evidence_source_commands_unallowlisted")
        blockers.extend(row_blockers)
        rows.append(
            {
                "blocker": blocker,
                "owner": raw_row.get("owner"),
                "status": "clean" if not row_blockers else "blocked",
                "missing_fields": missing_fields,
                "decision_artifacts": raw_row.get("decision_artifacts", []),
                "evidence_sources": evidence_sources,
                "required_fields": raw_row.get("required_fields", []),
                "recheck_commands": recheck_commands,
                "unallowlisted_recheck_commands": unallowlisted,
                "unallowlisted_evidence_source_commands": unallowlisted_evidence_source_commands,
                "next_action": raw_row.get("next_action"),
                "exit_criteria": raw_row.get("exit_criteria"),
                "removes_blocker_when": raw_row.get("removes_blocker_when"),
            }
        )
    return {
        "status": "clean" if coverage.get("status") == "clean" and not blockers else "blocked",
        "blockers": blockers,
        "matrix_coverage": coverage,
        "matrix_rows": rows,
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
        label="blocker closure matrix limit",
    )
    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    score_blockers = [str(blocker) for blocker in _list(packet.get("score_blockers"))]
    matrix = _list(packet.get("blocker_closure_matrix"))
    report = matrix_completeness_report(
        score_blockers=score_blockers,
        matrix=matrix,
        verification_commands=VERIFICATION_COMMANDS,
    )
    return {
        "check_kind": "portfolio_home_blocker_closure_matrix",
        "page_id": packet.get("page_id"),
        "page_slug": packet.get("page_slug"),
        "report_date": packet.get("report_date"),
        "duckdb_path": packet.get("duckdb_path"),
        "template_path": packet.get("template_path"),
        "docs_root": str(Path(docs_root)),
        "current_score": packet.get("current_score"),
        "remaining_gap": packet.get("remaining_gap"),
        "score_status": packet.get("score_status"),
        "full_score_ready": packet.get("full_score_ready"),
        "score_blockers": score_blockers,
        **report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home blocker closure matrix completeness.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="blocker closure matrix limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless every score blocker has a complete closure matrix row.",
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
