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

PAGE_SLUG = "pnl-by-business"
PAGE_ID = "PAGE-PNL-BY-BUSINESS-001"
FRONTEND_ROUTE = "/pnl-by-business"
DETAIL_FRONTEND_ROUTE = "/pnl-by-business-insights"
PRIMARY_API = "/api/pnl/by-business-insights"
TARGET_STREAM = "cache_manifest"
RESULT_KIND = "pnl.by_business_insights"
RESULT_VERSION = "v2"
RULE_VERSION = "rv_pnl_by_business_insights_v2"
CACHE_VERSION = "cv_pnl_by_business_insights_v2"
GOLDEN_SAMPLE_ID = "GS-PNL-BUSINESS-INSIGHTS-A"
METRIC_IDS = [f"MTR-PNLBIZ-{index:03d}" for index in range(1, 8)]


def fetch_live_envelope(*, year: int, as_of_date: str) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            PRIMARY_API,
            params={"year": year, "as_of_date": as_of_date},
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Insights API returned HTTP {response.status_code}: {response.text[:500]}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Insights API response must be a JSON object.")
    return payload


def build_record(
    envelope: dict[str, Any],
    *,
    year: int,
    as_of_date: str,
    created_at: str,
) -> dict[str, Any]:
    meta = envelope.get("result_meta")
    result = envelope.get("result")
    if not isinstance(meta, dict) or not isinstance(result, dict):
        raise ValueError("Live Insights response must contain result_meta and result objects.")

    exact_cutoff_ready = (
        meta.get("basis") == "formal"
        and meta.get("result_kind") == RESULT_KIND
        and meta.get("formal_use_allowed") is True
        and meta.get("rule_version") == RULE_VERSION
        and meta.get("cache_version") == CACHE_VERSION
        and meta.get("quality_flag") in {"ok", "warning"}
        and meta.get("requested_report_date") == as_of_date
        and meta.get("resolved_report_date") == as_of_date
        and meta.get("as_of_date") == as_of_date
        and meta.get("fallback_mode") == "none"
        and meta.get("fallback_date") in (None, "")
        and meta.get("vendor_status") == "ok"
        and result.get("result_version") == RESULT_VERSION
        and result.get("year") == year
        and result.get("as_of_date") == as_of_date
    )
    if not exact_cutoff_ready:
        raise ValueError(
            "Insights live response failed the exact-cutoff formal v2 gate; no governance record was generated."
        )

    component_evidence = result.get("component_evidence")
    if not isinstance(component_evidence, list):
        raise ValueError("Insights live response failed component admission: evidence is missing.")
    component_rows = {
        str(row.get("component") or ""): row
        for row in component_evidence
        if isinstance(row, dict)
    }
    expected_components = (
        "current_ytd",
        "baseline_ytd",
        f"monthly_{year - 1}",
        f"monthly_{year}",
    )
    invalid_components = [
        component
        for component in expected_components
        if component not in component_rows
        or component_rows[component].get("formal_source_admitted") is not True
        or component_rows[component].get("admission_reason") not in (None, "")
    ]
    if invalid_components:
        raise ValueError(
            "Insights live response failed component admission: " + ", ".join(invalid_components)
        )
    admitted_components = [dict(component_rows[component]) for component in expected_components]

    required_meta_fields = (
        "trace_id",
        "source_version",
        "rule_version",
        "cache_version",
        "generated_at",
        "source_surface",
    )
    missing = [field for field in required_meta_fields if not meta.get(field)]
    tables_used = meta.get("tables_used")
    if not isinstance(tables_used, list) or not tables_used:
        missing.append("tables_used")
    if missing:
        raise ValueError(f"Insights live response is missing governance fields: {', '.join(missing)}")

    trace_id = str(meta["trace_id"])
    return {
        "page_id": PAGE_ID,
        "page_slug": PAGE_SLUG,
        "frontend_route": FRONTEND_ROUTE,
        "detail_frontend_route": DETAIL_FRONTEND_ROUTE,
        "primary_api": PRIMARY_API,
        "api_query": f"{PRIMARY_API}?year={year}&as_of_date={as_of_date}",
        "report_date": as_of_date,
        "requested_report_date": as_of_date,
        "resolved_report_date": as_of_date,
        "as_of_date": as_of_date,
        "date_basis": str(meta.get("date_basis") or "formal_report_date_cutoff"),
        "basis": "formal",
        "source_surface": str(meta["source_surface"]),
        "tables_used": [str(table) for table in tables_used],
        "source_version": str(meta["source_version"]),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta["rule_version"]),
        "cache_version": str(meta["cache_version"]),
        "run_id": trace_id,
        "trace_id": trace_id,
        "result_kind": RESULT_KIND,
        "result_version": RESULT_VERSION,
        "metric_ids": METRIC_IDS,
        "golden_sample_id": GOLDEN_SAMPLE_ID,
        "component_admission_evidence": admitted_components,
        "quality_flag": str(meta.get("quality_flag") or "unknown"),
        "vendor_status": "ok",
        "fallback_mode": "none",
        "generated_at": str(meta["generated_at"]),
        "created_at": created_at,
        "formal_use_allowed": True,
        "evidence_kind": "live_exact_cutoff_api_read",
        "evidence_row_count": int(meta.get("evidence_rows") or 0),
        "ui_api_payload_evidence": f"live_api_trace:{trace_id}",
        "browser_smoke_evidence": (
            "frontend/tests/playwright/pnl-by-business-insights-smoke.spec.mjs::"
            "renders the governed formal conclusions and has no critical axe violations"
        ),
        "evidence_boundary": (
            "Direct exact-cutoff API response evidence only; not independent source-fact certification "
            "or page-execution completeness proof."
        ),
    }


def record_key(record: dict[str, Any]) -> dict[str, str]:
    return {
        "page_id": str(record["page_id"]),
        "primary_api": str(record["primary_api"]),
        "report_date": str(record["report_date"]),
        "source_version": str(record["source_version"]),
        "rule_version": str(record["rule_version"]),
    }


def records_share_key(left: dict[str, Any], right: dict[str, Any]) -> bool:
    required = ("page_id", "primary_api", "report_date", "source_version", "rule_version")
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
        "scope": "pnl-by-business-insights-governance-record-generation",
        "disclaimer": (
            "This command executes and records one exact-cutoff GET /api/pnl/by-business-insights response. "
            "It does not independently certify source facts, prove page-execution completeness, approve page "
            "closure, or capture business-owner approval."
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
            "proves_page_execution_completeness": False,
            "validates_required_fields": True,
            "captures_business_owner_approval": False,
            "uses_live_api_response": True,
        },
    }


def default_created_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate and preflight an exact-cutoff Business PnL Insights governance record.",
    )
    parser.add_argument(
        "--governance-dir",
        type=Path,
        default=resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--created-at", default=default_created_at())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    envelope = fetch_live_envelope(year=int(args.year), as_of_date=str(args.as_of_date))
    record = build_record(
        envelope,
        year=int(args.year),
        as_of_date=str(args.as_of_date),
        created_at=str(args.created_at),
    )
    payload = build_payload(
        record=record,
        governance_dir=args.governance_dir,
        write=bool(args.write),
    )
    if payload["preflight"]["validation"]["validation_status"] != "ready_for_audit_review":
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
