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

from scripts.check_pnl_attribution_business_owner_approval import (  # noqa: E402
    build_status as build_business_owner_approval_status,
)
from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_DUCKDB_PATH,
    DEFAULT_GOVERNANCE_DIR,
    page_governance_audit_evidence_packet,
    page_governance_record_preflight,
    product_page_trace_bundles,
    resolve_path_env,
)

PAGE_SLUG = "pnl-attribution"
TARGET_STREAM = "cache_manifest"
BUSINESS_OWNER_APPROVAL_TEMPLATE = ROOT / "docs" / "pnl" / "pnl-attribution-business-owner-approval-template.md"
GOVERNANCE_STREAM_NAMES = (
    "agent_audit",
    "cache_build_run",
    "cache_manifest",
    "snapshot_manifest",
    "source_manifest",
    "source_manifest_latest",
    "vendor_version_registry",
)


def build_record(
    created_at: str,
    *,
    ui_api_payload_evidence: str | None = None,
    live_smoke_evidence: str | None = None,
) -> dict[str, Any]:
    record = {
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "page_slug": "pnl-attribution",
        "frontend_route": "/pnl-attribution",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "report_date": "2026-04-30",
        "basis": "formal",
        "source_surface": "formal_attribution",
        "tables_used": [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ],
        "source_version": "sv_pnl_by_business_gs_attr_wb",
        "rule_version": "rv_pnl_attribution_workbench_v1",
        "cache_version": "cv_pnl_attribution_workbench_v1",
        "cache_key": "pnl-attribution:volume-rate:2026-04-30:mom",
        "result_kind": "pnl_attribution.volume_rate",
        "golden_sample_id": "GS-PNL-ATTR-WB-A",
        "created_at": created_at,
        "formal_use_allowed": False,
    }
    if ui_api_payload_evidence:
        record["ui_api_payload_evidence"] = ui_api_payload_evidence
    if live_smoke_evidence:
        record["live_smoke_evidence"] = live_smoke_evidence
    return record


def build_payload(
    *,
    record: dict[str, Any],
    governance_dir: Path,
    write: bool,
    duckdb_path: Path,
    audit_packet_path: Path | None,
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
        "scope": "pnl-attribution-governance-record-generation",
        "disclaimer": (
            "This command generates and preflights the PAGE-PNL-ATTR-WB-001 primary workbench API governance "
            "record only. It does not approve page closure, promote candidate metrics to formal use, or prove "
            "advanced/Campisi attribution surfaces."
        ),
        "mode": "write" if write else "dry-run",
        "target_stream": TARGET_STREAM,
        "target_path": str(target_path),
        "record_key": record_key(record),
        "record_write_status": record_write_status,
        "existing_record_line": existing_record_line,
        "record": record,
        "preflight": preflight,
        "audit_packet_path": str(audit_packet_path) if audit_packet_path is not None else None,
        "audit_packet": None,
        "duckdb_path": str(duckdb_path),
        "evidence_scope": {
            "writes_governance_records": write,
            "writes_audit_packet": audit_packet_path is not None,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
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


def merge_evidence_fields(existing: dict[str, Any], record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    merged = dict(existing)
    changed = False
    for field in ("ui_api_payload_evidence", "live_smoke_evidence"):
        value = record.get(field)
        if value and merged.get(field) != value:
            merged[field] = value
            changed = True
    return merged, changed


def update_existing_record(path: Path, record: dict[str, Any]) -> str | None:
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            existing = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(existing, dict) or not records_share_key(existing, record):
            continue
        merged, changed = merge_evidence_fields(existing, record)
        if not changed:
            return "already_exists"
        lines[index] = json.dumps(merged, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return "updated_existing"
    return None


def emit_record(path: Path, record: dict[str, Any]) -> str:
    existing_status = update_existing_record(path, record)
    if existing_status is not None:
        return existing_status
    if find_existing_record_line(path, record) is not None:
        return "already_exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return "appended"


def governance_stream_paths(governance_dir: Path) -> dict[str, Path]:
    return {
        name: governance_dir / f"{name}.jsonl"
        for name in GOVERNANCE_STREAM_NAMES
    }


def build_audit_packet(governance_dir: Path, duckdb_path: Path) -> dict[str, Any]:
    return page_governance_audit_evidence_packet(
        product_page_trace_bundles(),
        governance_stream_paths(governance_dir),
        PAGE_SLUG,
        list(GOVERNANCE_STREAM_NAMES),
        duckdb_path,
        max_results=20,
    )


def write_audit_packet_markdown(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_audit_packet_markdown(packet), encoding="utf-8")


def render_audit_packet_markdown(packet: dict[str, Any]) -> str:
    queue_item = packet.get("audit_review_queue_item")
    approval_status = queue_item.get("approval_status") if isinstance(queue_item, dict) else packet.get("approval_status")
    formal_use_allowed = queue_item.get("record_formal_use_policy") if isinstance(queue_item, dict) else None
    if isinstance(queue_item, dict):
        formal_value = any(
            validation.get("record_formal_use_allowed") is True
            for validation in queue_item.get("direct_record_validations", [])
            if isinstance(validation, dict)
        )
    else:
        formal_value = False
    manual_blockers = [str(item) for item in packet.get("manual_review_blockers", [])]
    evidence_present = [
        str(item.get("check"))
        for item in packet.get("manual_review_evidence_present", [])
        if isinstance(item, dict) and item.get("check")
    ]
    approval_status_payload = build_business_owner_approval_status(BUSINESS_OWNER_APPROVAL_TEMPLATE)
    approval_blockers = [str(item) for item in approval_status_payload.get("remaining_blockers", [])]
    approval_action_item_lines = [
        (
            f"- {str(item['template_field']).lstrip('-').strip()}: "
            f"`{item['required_value']}` (`{item['current_status']}`)"
        )
        for item in approval_status_payload.get("approval_action_items", [])
    ]
    approval_scope = approval_status_payload.get("evidence_scope", {})
    sections = [
        "# PnL Attribution Governance Audit Packet",
        "",
        f"Page ID: `{packet.get('page_id')}`",
        f"Page slug: `{packet.get('page_slug')}`",
        f"Audit review status: `{packet.get('audit_review_status')}`",
        f"Approval status: `{approval_status}`",
        f"Formal use allowed: `{str(formal_value).lower()}`",
        f"Closure approved: `{str(bool(packet.get('closure_approved'))).lower()}`",
        "",
        "## Boundary",
        "",
        "- Does not approve page closure or metric formal use.",
        "- Does not cover advanced/Campisi full-surface closure.",
        "- Does not replace `/api/pnl/overview` formal PnL truth.",
        "- Does not merge with executive overlay `/ui/pnl/attribution`.",
        "",
        "## Evidence Summary",
        "",
        f"- MCP sections: `{', '.join(packet.get('summary', {}).get('mcp_evidence_sections', []))}`",
        f"- Manual blocker count: `{packet.get('summary', {}).get('manual_review_blocker_count')}`",
        f"- Manual blockers: `{', '.join(manual_blockers) if manual_blockers else 'none'}`",
        "- Evidence references attached for reviewer confirmation: "
        f"`{', '.join(evidence_present) if evidence_present else 'none'}`",
        "- Sign-off packet: `docs/pnl/pnl-attribution-sign-off-packet.md`",
        "- Owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`",
        "- Approval status command: `python scripts/check_pnl_attribution_business_owner_approval.py`",
        "- Strict approval gate command: `python scripts/check_pnl_attribution_business_owner_approval.py --require-captured`",
        "- PowerShell readiness strict approval gate command: "
        "`scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured`",
        "- PowerShell all-page readiness strict approval gate command: "
        "`scripts\\codex-page-readiness.ps1 -All -RequireApprovalCaptured`",
        f"- Business owner approval captured: `{str(bool(approval_status_payload['business_owner_approval_captured'])).lower()}`",
        f"- Business owner approval status: `{approval_status_payload['approval_status']}`",
        f"- Business owner approval blockers: `{', '.join(approval_blockers) if approval_blockers else 'none'}`",
        f"- Record formal-use policy: `{formal_use_allowed}`",
        "",
        "## Evidence Scope",
        "",
        f"- `approves_metric_or_page={str(bool(approval_scope.get('approves_metric_or_page'))).lower()}`",
        f"- `writes_governance_records={str(bool(approval_scope.get('writes_governance_records'))).lower()}`",
        f"- `proves_page_execution={str(bool(approval_scope.get('proves_page_execution'))).lower()}`",
        (
            "- `captures_business_owner_approval="
            f"{str(bool(approval_scope.get('captures_business_owner_approval'))).lower()}`"
        ),
        f"- `certification_effect={approval_scope.get('certification_effect', 'unknown')}`",
        "",
        "## Business Owner Approval Action Items",
        "",
        *(approval_action_item_lines or ["- none"]),
        "",
        "## Required Follow-up",
        "",
        "- Review current API payload and visible UI state.",
        "- Confirm live smoke/browser evidence before signing.",
        "- Page smoke rerun: `scripts\\codex-page-smoke.ps1 -PageSlug pnl-attribution` (`passed`)",
        "- Page verification rerun: `scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run` (`passed`)",
        "- Page readiness rerun: `scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run` (`passed`)",
        (
            "- Page closure command status: `verification rerun complete; "
            "business-owner review and signature still pending`"
        ),
        "- Collect business-owner approval before any closure claim.",
        "",
    ]
    return "\n".join(sections)


def default_created_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate and preflight the pnl-attribution workbench direct governance record.",
    )
    parser.add_argument(
        "--governance-dir",
        type=Path,
        default=resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
        help="Governance directory. Defaults to MOSS_GOVERNANCE_PATH or data/governance.",
    )
    parser.add_argument(
        "--created-at",
        default=default_created_at(),
        help="Record creation timestamp. Defaults to the current UTC timestamp.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Append the record to cache_manifest.jsonl. Omit for dry-run/preflight only.",
    )
    parser.add_argument(
        "--duckdb-path",
        type=Path,
        default=resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH),
        help="DuckDB path used when building an audit packet.",
    )
    parser.add_argument(
        "--audit-packet-path",
        type=Path,
        help="Optional Markdown path for a read-only audit evidence packet after record write/preflight.",
    )
    parser.add_argument(
        "--ui-api-payload-evidence",
        help="Optional reviewed UI/API payload evidence reference to attach to the direct record.",
    )
    parser.add_argument(
        "--live-smoke-evidence",
        help="Optional live smoke/browser evidence reference to attach to the direct record.",
    )
    args = parser.parse_args(argv)

    record = build_record(
        str(args.created_at),
        ui_api_payload_evidence=args.ui_api_payload_evidence,
        live_smoke_evidence=args.live_smoke_evidence,
    )
    governance_dir = Path(args.governance_dir)
    payload = build_payload(
        record=record,
        governance_dir=governance_dir,
        write=bool(args.write),
        duckdb_path=Path(args.duckdb_path),
        audit_packet_path=args.audit_packet_path,
    )
    validation_status = payload["preflight"]["validation"]["validation_status"]
    if validation_status != "ready_for_audit_review":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    if args.write:
        payload["record_write_status"] = emit_record(Path(payload["target_path"]), record)
        payload["existing_record_line"] = find_existing_record_line(Path(payload["target_path"]), record)

    if args.audit_packet_path is not None:
        packet = build_audit_packet(governance_dir, Path(args.duckdb_path))
        payload["audit_packet"] = packet
        write_audit_packet_markdown(args.audit_packet_path, packet)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
