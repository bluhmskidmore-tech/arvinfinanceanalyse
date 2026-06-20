from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_GOVERNANCE_DIR,
    page_governance_record_preflight,
    product_page_trace_bundles,
    resolve_path_env,
)

PAGE_SLUG = "bond-analysis"
TARGET_STREAM = "cache_manifest"


def build_record(created_at: str) -> dict[str, Any]:
    return {
        "page_id": "PAGE-BOND-ANALYSIS-001",
        "page_slug": "bond-analysis",
        "frontend_route": "/bond-analysis",
        "primary_api": "/api/bond-analytics/action-attribution",
        "report_date": "2026-03-31",
        "basis": "analytical",
        "source_surface": "bond_analytics",
        "tables_used": ["fact_formal_bond_analytics_daily"],
        "source_version": "sv_bond_analysis_action_attr_gs_a",
        "rule_version": "rv_bond_analytics_formal_materialize_v1",
        "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1",
        "cache_key": "bond-analysis:action-attribution:2026-03-31:MoM",
        "result_kind": "bond_analytics.action_attribution",
        "golden_sample_id": "GS-BOND-ANALYSIS-ACTION-ATTR-A",
        "created_at": created_at,
        "formal_use_allowed": False,
    }


def build_payload(
    *,
    record: dict[str, Any],
    governance_dir: Path,
    write: bool,
) -> dict[str, Any]:
    preflight = page_governance_record_preflight(
        product_page_trace_bundles(),
        PAGE_SLUG,
        record,
    )
    target_path = governance_dir / f"{TARGET_STREAM}.jsonl"
    existing_record_line = find_existing_record_line(target_path, record)
    record_write_status = "not_requested"
    if write:
        record_write_status = "already_exists" if existing_record_line is not None else "pending_append"
    return {
        "scope": "bond-analysis-governance-record-generation",
        "disclaimer": (
            "This command generates and preflights the PAGE-BOND-ANALYSIS-001 action-attribution "
            "candidate governance record only. It does not approve page closure, promote fixed-income "
            "metrics to formal use, prove live page/API execution, or capture business-owner approval."
        ),
        "mode": "write" if write else "dry-run",
        "target_stream": TARGET_STREAM,
        "target_path": str(target_path),
        "record_key": record_key(record),
        "record_write_status": record_write_status,
        "existing_record_line": existing_record_line,
        "record": record,
        "preflight": preflight,
        "evidence_scope": {
            "writes_governance_records": write,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
            "captures_business_owner_approval": False,
        },
    }


def record_key(record: dict[str, Any]) -> dict[str, str]:
    return {
        "page_id": str(record["page_id"]),
        "primary_api": str(record["primary_api"]),
        "report_date": str(record["report_date"]),
        "cache_key": str(record["cache_key"]),
    }


def records_share_key(left: dict[str, Any], right: dict[str, Any]) -> bool:
    required = ("page_id", "primary_api", "report_date", "cache_key")
    if any(field not in left or field not in right for field in required):
        return False
    return record_key(left) == record_key(right)


def find_existing_record_line(path: Path, record: dict[str, Any]) -> int | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(existing, dict) and records_share_key(existing, record):
                return line_number
    return None


def emit_record(path: Path, record: dict[str, Any]) -> str:
    if find_existing_record_line(path, record) is not None:
        return "already_exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return "appended"


def default_created_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the /bond-analysis action-attribution candidate governance record.",
    )
    parser.add_argument(
        "--governance-dir",
        type=Path,
        default=resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
    )
    parser.add_argument("--created-at", default=default_created_at())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    record = build_record(str(args.created_at))
    payload = build_payload(
        record=record,
        governance_dir=args.governance_dir,
        write=bool(args.write),
    )
    validation_status = payload["preflight"]["validation"]["validation_status"]
    if validation_status != "ready_for_audit_review":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    if args.write:
        target_path = args.governance_dir / f"{TARGET_STREAM}.jsonl"
        payload["record_write_status"] = emit_record(target_path, record)
        payload["existing_record_line"] = find_existing_record_line(target_path, record)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
