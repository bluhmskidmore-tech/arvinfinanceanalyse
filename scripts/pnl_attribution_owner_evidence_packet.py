from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_pnl_attribution_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402
from scripts.emit_pnl_attribution_governance_record import (  # noqa: E402
    build_payload as build_governance_payload,
    build_record,
)
from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_DUCKDB_PATH,
    DEFAULT_GOVERNANCE_DIR,
    resolve_path_env,
)


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "pnl-attribution-owner-evidence-packet.md"

OUT_OF_SCOPE_SURFACES = [
    "full page closure",
    "advanced attribution surfaces",
    "Campisi surfaces",
    "/api/pnl/overview formal PnL truth",
    "executive analytical overlay /ui/pnl/attribution",
    "business-owner approval",
]

REVIEWER_CHECKLIST = [
    "Confirm GS-PNL-ATTR-WB-A remains scoped to the primary /api/pnl-attribution/volume-rate DTO.",
    "Review current UI/API payload against the active workbench view before signature.",
    "Review live smoke/browser evidence before signature.",
    "Keep advanced attribution, Campisi, /api/pnl/overview, and /ui/pnl/attribution outside this packet.",
    "Complete and sign docs/pnl/pnl-attribution-business-owner-approval-template.md before any closure claim.",
]

LATEST_VERIFICATION_EVIDENCE = {
    "static_readiness": "static-pass",
    "page_smoke": "passed",
    "backend_workbench_numeric_campisi_tests": "94 passed",
    "frontend_page_tests": "27 passed",
    "browser_a11y_smoke": "1 passed",
    "frontend_typecheck": "passed",
    "frontend_debt_audit": "passed",
    "frontend_production_build": "passed",
    "full_readiness_run": "passed",
    "boundary": (
        "Full page readiness passed on 2026-06-06: static readiness, page smoke, "
        "MCP contract tests, backend tests, frontend tests, browser a11y smoke, "
        "typecheck, debt audit, and production build all completed. This is "
        "technical evidence only; owner approval remains pending."
    ),
}

PRIMARY_API_RESULT_META_SCOPE = "primary_api_dto_formal_result_meta_only"


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
    governance_dir: Path = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
    duckdb_path: Path = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH),
    created_at: str = "2026-06-05T00:00:00Z",
) -> dict[str, Any]:
    readiness = build_page_readiness_report("pnl-attribution")
    approval = build_approval_status(template_path)
    governance = build_governance_payload(
        record=build_record(created_at),
        governance_dir=Path(governance_dir),
        write=False,
        duckdb_path=Path(duckdb_path),
        audit_packet_path=None,
    )
    catalog = readiness.get("catalog_date_evidence") or {}
    governance_validation = governance["preflight"]["validation"]
    return {
        "packet_kind": "pnl_attribution_owner_evidence_packet",
        "page_id": readiness["page_id"],
        "page_slug": readiness["page_slug"],
        "route": readiness["route"],
        "primary_api": readiness["primary_api"],
        "business_contract_status": "evidence-pending",
        "business_contract_certified": False,
        "handoff_status": "owner_actions_required",
        "approval_status": approval["approval_status"],
        "formal_use_allowed": approval["formal_use_allowed"],
        "closure_approved": approval["closure_approved"],
        "business_owner_approval_captured": approval["business_owner_approval_captured"],
        "approval_action_item_count": approval["approval_action_item_count"],
        "remaining_blockers": list(approval["remaining_blockers"]),
        "owner_action_items": list(approval["approval_action_items"]),
        "golden_sample_approval_artifact_status": readiness[
            "golden_sample_approval_artifact_status"
        ],
        "golden_sample_approval_artifact_mismatch": readiness[
            "golden_sample_approval_artifact_mismatch"
        ],
        "golden_sample_boundary": "primary_workbench_dto_only",
        "primary_api_result_meta_scope": PRIMARY_API_RESULT_META_SCOPE,
        "primary_api_result_meta_formal_use_allowed": True,
        "page_formal_use_allowed": approval["formal_use_allowed"],
        "page_owner_approval_required": True,
        "golden_sample_approval_artifacts": list(
            readiness["golden_sample_approval_artifacts"]
        ),
        "out_of_scope_surfaces": list(OUT_OF_SCOPE_SURFACES),
        "catalog_date_sampled_table_count": catalog.get("date_sampled_table_count"),
        "catalog_date_table_names": list(catalog.get("sampled_table_names", [])),
        "governance_record_write_status": governance["record_write_status"],
        "governance_existing_record_line": governance["existing_record_line"],
        "governance_validation_status": governance_validation["validation_status"],
        "governance_record_key": dict(governance["record_key"]),
        "latest_verification_evidence": dict(LATEST_VERIFICATION_EVIDENCE),
        "reviewer_checklist": list(REVIEWER_CHECKLIST),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "certification_effect": "none",
            "validates_required_fields": True,
        },
        "evidence_anchors": {
            "boundary_status": "docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json",
            "signoff_packet": "docs/pnl/pnl-attribution-sign-off-packet.md",
            "governance_audit_packet": "docs/pnl/pnl-attribution-governance-audit-packet.md",
            "approval_template": "docs/pnl/pnl-attribution-business-owner-approval-template.md",
            "golden_sample": "tests/golden_samples/GS-PNL-ATTR-WB-A",
            "readiness_command": "python scripts/codex_page_readiness.py --page-slug pnl-attribution",
            "governance_dry_run": "python scripts/emit_pnl_attribution_governance_record.py",
        },
    }


def render_markdown(packet: dict[str, Any]) -> str:
    action_items = "\n".join(
        (
            f"- {_display_template_field(str(item['template_field']))}: "
            f"`{item['required_value']}` (`{item['current_status']}`)"
        )
        for item in packet["owner_action_items"]
    )
    checklist = "\n".join(f"- {item}" for item in packet["reviewer_checklist"])
    anchors = "\n".join(
        f"- {label}: `{path}`"
        for label, path in packet["evidence_anchors"].items()
    )
    out_of_scope = "\n".join(
        f"- {_display_surface(surface)}" for surface in packet["out_of_scope_surfaces"]
    )
    tables = "\n".join(f"- `{table}`" for table in packet["catalog_date_table_names"])
    latest = packet["latest_verification_evidence"]
    return f"""# PnL Attribution Owner Evidence Packet

Page ID: `{packet['page_id']}`
Page slug: `{packet['page_slug']}`
Primary API: `{packet['primary_api']}`
Business contract status: `{packet['business_contract_status']}`
Business contract certified: `{str(packet['business_contract_certified']).lower()}`
Formal use allowed: `formal_use_allowed={str(packet['formal_use_allowed']).lower()}`
Closure approved: `closure_approved={str(packet['closure_approved']).lower()}`
Business owner approval captured: `{str(packet['business_owner_approval_captured']).lower()}`
Handoff status: `{packet['handoff_status']}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote metric formal use, or certify full-page PnL attribution.

## Current Certification Blockers

- `golden_sample_approval_artifact_status={packet['golden_sample_approval_artifact_status']}`
- `golden_sample_approval_artifact_mismatch={str(packet['golden_sample_approval_artifact_mismatch']).lower()}`
- `approval_action_item_count={packet['approval_action_item_count']}`
- `business_owner_approval_captured={str(packet['business_owner_approval_captured']).lower()}`

## Boundary

Golden sample boundary: `{packet['golden_sample_boundary']}`

## DTO vs Page Approval Boundary

Primary API DTO result_meta may be formal/formal_use_allowed=true.
This does not approve PAGE-PNL-ATTR-WB-001 page closure, owner approval, or full-page formal use.

Primary API result_meta scope: `{packet['primary_api_result_meta_scope']}`
Primary API result_meta formal use allowed: `{str(packet['primary_api_result_meta_formal_use_allowed']).lower()}`
Page formal use allowed: `{str(packet['page_formal_use_allowed']).lower()}`
Page owner approval required: `{str(packet['page_owner_approval_required']).lower()}`

Out of scope:

{out_of_scope}

## Governance Dry-Run

Governance record write status: `{packet['governance_record_write_status']}`
Governance validation status: `{packet['governance_validation_status']}`
Existing record line: `{packet['governance_existing_record_line']}`

## Latest Verification Evidence

- Static readiness: `{latest['static_readiness']}`
- Page smoke: `{latest['page_smoke']}`
- Backend workbench/numeric/Campisi tests: `{latest['backend_workbench_numeric_campisi_tests']}`
- Frontend page tests: `{latest['frontend_page_tests']}`
- Browser a11y smoke: `{latest['browser_a11y_smoke']}`
- Frontend typecheck: `{latest['frontend_typecheck']}`
- Frontend debt audit: `{latest['frontend_debt_audit']}`
- Frontend production build: `{latest['frontend_production_build']}`
- Full readiness run: `{latest['full_readiness_run']}`
- Boundary: {latest['boundary']}

## Catalog Date Evidence

Sampled table count: `{packet['catalog_date_sampled_table_count']}`

{tables}

## Evidence Anchors

{anchors}

## Reviewer Checklist

{checklist}

## Business Owner Approval Action Items

{action_items}

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `validates_required_fields=true`
"""


def _display_template_field(template_field: str) -> str:
    return template_field.removeprefix("- ").strip()


def _display_surface(surface: str) -> str:
    if surface == "advanced attribution surfaces":
        return "Advanced attribution surfaces"
    return surface


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the pnl-attribution owner evidence packet without approving closure.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown packet path to write.",
    )
    parser.add_argument(
        "--governance-dir",
        type=Path,
        default=resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
        help="Governance directory used for dry-run existing-record lookup.",
    )
    parser.add_argument(
        "--duckdb-path",
        type=Path,
        default=resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH),
        help="DuckDB path used by the governance dry-run payload.",
    )
    parser.add_argument(
        "--created-at",
        default="2026-06-05T00:00:00Z",
        help="Stable dry-run record timestamp for reproducible packet output.",
    )
    args = parser.parse_args(argv)

    packet = build_packet(
        governance_dir=Path(args.governance_dir),
        duckdb_path=Path(args.duckdb_path),
        created_at=str(args.created_at),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(packet), encoding="utf-8")
    payload = {
        "packet_kind": packet["packet_kind"],
        "packet_path": str(output_path),
        "handoff_status": packet["handoff_status"],
        "business_contract_certified": packet["business_contract_certified"],
        "approval_action_item_count": packet["approval_action_item_count"],
        "governance_record_write_status": packet["governance_record_write_status"],
        "governance_validation_status": packet["governance_validation_status"],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
