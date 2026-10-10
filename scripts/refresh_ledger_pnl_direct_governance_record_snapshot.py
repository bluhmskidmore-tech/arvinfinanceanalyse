from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402
from scripts.emit_ledger_pnl_governance_record import (  # noqa: E402
    PAGE_SLUG,
    TARGET_STREAM,
    build_payload as build_governance_payload,
    build_record,
)
from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_GOVERNANCE_DIR,
    resolve_path_env,
)


AUDIT_DATE = "2026-06-10"
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-ledger-pnl-direct-governance-record-snapshot.json"
)
SEARCH_PATTERNS = (
    "PAGE-LEDGER-PNL-001",
    "/api/ledger-pnl/summary",
    "ledger_pnl.summary:2026-05-31:ALL",
)
REFRESH_COMMAND = (
    "python scripts\\refresh_ledger_pnl_direct_governance_record_snapshot.py"
)


def _now_shanghai() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _line_match_counts(path: Path, patterns: tuple[str, ...]) -> dict[str, int]:
    counts = {pattern: 0 for pattern in patterns}
    if not path.is_file():
        return counts
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            for pattern in patterns:
                if pattern in line:
                    counts[pattern] += 1
    return counts


def _catalog_blocking_detail(catalog: dict[str, Any]) -> str:
    table_evidence = list(catalog.get("table_evidence") or [])
    details: list[str] = []
    for row in table_evidence:
        table_name = str(row.get("table_name") or "unknown")
        status = row.get("status")
        if status == "unknown_table":
            details.append(f"{table_name} is not present in the current catalog sample")
        elif status == "present_no_date_column":
            details.append(f"{table_name} has no date column")
    return "; ".join(details) + "." if details else ""


def _catalog_snapshot_summary(catalog: dict[str, Any] | None) -> dict[str, Any]:
    catalog = dict(catalog or {})
    return {
        "status": catalog.get("status") or "incomplete",
        "table_count": int(catalog.get("table_count") or 0),
        "present_table_count": int(catalog.get("present_table_count") or 0),
        "date_sampled_table_count": int(catalog.get("date_sampled_table_count") or 0),
        "sampled_table_names": list(catalog.get("sampled_table_names") or []),
        "blocking_detail": _catalog_blocking_detail(catalog),
    }


def _audit_check_status(audit_review: dict[str, Any], check_name: str) -> str | None:
    for check in audit_review.get("checks") or []:
        if check.get("name") == check_name:
            return str(check.get("status"))
    return None


def _page_readiness_snapshot(readiness: dict[str, Any]) -> dict[str, Any]:
    owner_status = readiness.get("business_owner_approval_status") or {}
    audit_review = readiness.get("audit_review") or {}
    return {
        "command": "python scripts\\codex_page_readiness.py --page-slug ledger-pnl",
        "overall_status": readiness.get("overall_status"),
        "formal_use_allowed": bool(readiness.get("formal_use_allowed")),
        "closure_approved": bool(owner_status.get("closure_approved", False)),
        "business_owner_approval_captured": bool(
            owner_status.get("business_owner_approval_captured", False)
        ),
        "approval_status": owner_status.get("approval_status"),
        "approval_action_item_count": int(
            owner_status.get("approval_action_item_count") or 0
        ),
        "catalog_date_evidence": _catalog_snapshot_summary(
            readiness.get("catalog_date_evidence")
        ),
        "governance_record_validation": dict(
            readiness.get("governance_record_validation") or {}
        ),
        "audit_review": {
            "status": audit_review.get("status"),
            "closure_approved": bool(audit_review.get("closure_approved", False)),
            "direct_page_api_record_fields": _audit_check_status(
                audit_review,
                "direct_page_api_record_fields",
            ),
        },
        "residual_gaps": list(readiness.get("residual_gaps") or []),
    }


def _post_write_validation(
    *,
    existing_record_line: int | None,
    page_readiness: dict[str, Any],
) -> dict[str, Any]:
    governance = page_readiness.get("governance_record_validation") or {}
    audit_review = page_readiness.get("audit_review") or {}
    checks = {
        "written_record_located": existing_record_line is not None,
        "governance_direct_records_ready": (
            governance.get("status") == "direct_records_ready_for_audit_review"
            and int(governance.get("direct_record_count") or 0) > 0
        ),
        "audit_review_not_blocked_by_record_gaps": (
            audit_review.get("status") != "blocked_by_record_gaps"
        ),
        "formal_use_still_false_until_owner_approval": (
            page_readiness.get("formal_use_allowed") is False
        ),
        "closure_not_approved_without_owner_approval": (
            page_readiness.get("closure_approved") is False
        ),
        "business_owner_approval_not_captured": (
            page_readiness.get("business_owner_approval_captured") is False
        ),
    }
    blocking_reasons = [
        name for name, passed in checks.items() if not passed
    ]
    return {
        "ready": not blocking_reasons,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "boundary": (
            "A located record is not enough for Ledger PnL closure. Downstream "
            "governance validation, page readiness, audit review, owner approval, "
            "and live evidence must still be reviewed before formal use or closure."
        ),
    }


def _written_record_search(target_path: Path) -> dict[str, Any]:
    matches = _line_match_counts(target_path, SEARCH_PATTERNS)
    found = any(count > 0 for count in matches.values())
    return {
        "command": (
            "Select-String -Path "
            f"'{target_path}' -Pattern "
            "'PAGE-LEDGER-PNL-001','/api/ledger-pnl/summary',"
            "'ledger_pnl.summary:2026-05-31:ALL'"
        ),
        "matches": matches,
        "interpretation": (
            "Potential matching written direct page/API governance record anchors were found; "
            "rerun downstream readiness and owner gates before any closure claim."
            if found
            else "No matching written direct page/API governance record was found in cache_manifest.jsonl."
        ),
    }


def build_snapshot(
    *,
    generated_at: str | None = None,
    governance_dir: Path = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
    record_created_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now_shanghai()
    record = build_record(record_created_at or generated_at)
    dry_run = build_governance_payload(
        record=record,
        governance_dir=Path(governance_dir),
        write=False,
    )
    readiness = build_page_readiness_report(PAGE_SLUG)
    target_path = Path(dry_run["target_path"])
    validation = dry_run["preflight"]["validation"]
    existing_record_line = dry_run["existing_record_line"]
    page_readiness = _page_readiness_snapshot(readiness)
    post_write_validation = _post_write_validation(
        existing_record_line=existing_record_line,
        page_readiness=page_readiness,
    )
    closure_blocked_by_missing_written_record = existing_record_line is None
    return {
        "report_kind": "ledger_pnl_direct_governance_record_snapshot",
        "generated_at": generated_at,
        "repo_root": str(ROOT),
        "audit_date": AUDIT_DATE,
        "refresh_command": REFRESH_COMMAND,
        "page": {
            "page_slug": PAGE_SLUG,
            "page_id": "PAGE-LEDGER-PNL-001",
            "frontend_route": "/ledger-pnl",
            "primary_api": "/api/ledger-pnl/summary",
        },
        "status": {
            "overall": (
                "written_record_located"
                if existing_record_line is not None
                else "dry_run_candidate_only"
            ),
            "fail_closed": True,
            "writes_governance_records": False,
            "approves_metrics": False,
            "approves_pages": False,
            "captures_business_owner_approval": False,
            "certifies_routes": False,
            "closure_blocked_by_missing_written_record": closure_blocked_by_missing_written_record,
        },
        "dry_run_result": {
            "command": "python scripts\\emit_ledger_pnl_governance_record.py",
            "mode": dry_run["mode"],
            "target_stream": TARGET_STREAM,
            "target_path": dry_run["target_path"],
            "record_write_status": dry_run["record_write_status"],
            "existing_record_line": existing_record_line,
            "validation_status": validation["validation_status"],
            "missing_required_fields": list(validation["missing_required_fields"]),
            "failed_required_field_groups": list(validation["failed_required_field_groups"]),
            "formal_use_allowed": bool(record["formal_use_allowed"]),
            "residual_gap": " ".join(validation.get("residual_gaps") or []),
        },
        "record_key": dict(dry_run["record_key"]),
        "candidate_record": dict(record),
        "written_record_search": _written_record_search(target_path),
        "page_readiness_result": page_readiness,
        "post_write_validation": post_write_validation,
        "closure_blocked_by_missing_written_record": closure_blocked_by_missing_written_record,
        "closure_gate": (
            "Only an approved governance workflow may write or locate the direct page/API record. "
            "After that, post_write_validation.ready must be true, governance validation must no "
            "longer be blocked by direct-record gaps, Ledger PnL page readiness, owner approval "
            "strict checks, and live page/API evidence review must be rerun. Keep "
            "formal_use_allowed=false and closure_approved=false until owner approval and all "
            "page-specific gates are captured."
        ),
        "boundary": (
            "This snapshot is refreshed by a read-only preflight. It proves only whether a "
            "field-complete dry-run candidate exists and whether matching direct-record anchors "
            "are visible in the configured governance stream. It does not write governance records, "
            "approve metrics/pages, certify routes, prove live page/API execution, or capture "
            "business-owner approval."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the Ledger PnL direct governance-record snapshot without writing "
            "governance records or approving closure."
        ),
    )
    parser.add_argument(
        "--governance-dir",
        type=Path,
        default=resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
        help="Governance directory to search. The command never appends records.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional snapshot timestamp. Defaults to current UTC+08 time.",
    )
    parser.add_argument(
        "--record-created-at",
        default=None,
        help="Optional candidate-record timestamp. Defaults to --generated-at.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Snapshot JSON output path. Only this audit artifact is written.",
    )
    parser.add_argument(
        "--require-written-record-located",
        action="store_true",
        help=(
            "Exit non-zero unless an existing direct page/API governance record is located. "
            "This never writes the record; it is a strict post-governance-write gate."
        ),
    )
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        generated_at=args.generated_at,
        governance_dir=Path(args.governance_dir),
        record_created_at=args.record_created_at,
    )
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if (
        args.require_written_record_located
        and (
            snapshot["status"]["overall"] != "written_record_located"
            or snapshot["post_write_validation"]["ready"] is not True
        )
    ):
        dry_run = snapshot["dry_run_result"]
        post_write_validation = snapshot["post_write_validation"]
        print(
            (
                "Ledger PnL direct governance record is not located: "
                f"status={snapshot['status']['overall']}, "
                f"record_write_status={dry_run['record_write_status']}, "
                f"existing_record_line={dry_run['existing_record_line']}, "
                f"post_write_ready={post_write_validation['ready']}, "
                "post_write_blocking_reasons="
                f"{post_write_validation['blocking_reasons']}"
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
