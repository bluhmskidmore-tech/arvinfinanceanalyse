from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_stock_analysis_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "stock-analysis-owner-evidence-packet.md"

OUT_OF_SCOPE_SURFACES = [
    "PAGE-STOCK contracts",
    "MTR-STOCK metric approvals",
    "trading instructions",
    "execution approvals",
    "allocation advice",
    "position-change commands",
    "formal stock-analysis truth",
    "business-owner approval",
]

REVIEWER_CHECKLIST = [
    "Confirm GS-STOCK-ANALYSIS-OBS-A remains scoped to GET /ui/market-data/livermore DTO evidence.",
    "Review as_of_date, requested_as_of_date, fallback/stale/no-data states, supported_outputs, unsupported_outputs, rule_readiness, and data_gaps before signature.",
    "Review Livermore, Choice stock, candidate-history, and gate-supplement table/date evidence before signature.",
    "Review direct page/API governance records before signature; current packet does not write them.",
    "Complete and sign docs/pnl/stock-analysis-business-owner-approval-template.md before any closure claim.",
]


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict[str, Any]:
    readiness = build_page_readiness_report("stock-analysis")
    approval = build_approval_status(template_path)
    return {
        "packet_kind": "stock_analysis_owner_evidence_packet",
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
        "golden_sample_boundary": "observational_page_dto_capture_ready_pending_approval",
        "dedicated_golden_sample_id": "GS-STOCK-ANALYSIS-OBS-A",
        "route_specific_evidence_scope": "stock_analysis_observational_livermore_dto_only",
        "trading_instruction_allowed": False,
        "execution_approval_allowed": False,
        "allocation_advice_allowed": False,
        "position_change_command_allowed": False,
        "formal_stock_metric_promotion_allowed": False,
        "observational_boundary_status": (
            "no_trading_instruction_boundary_pending_owner_acceptance"
        ),
        "golden_sample_approval_artifact_status": readiness[
            "golden_sample_approval_artifact_status"
        ],
        "golden_sample_approval_artifact_mismatch": readiness[
            "golden_sample_approval_artifact_mismatch"
        ],
        "out_of_scope_surfaces": list(OUT_OF_SCOPE_SURFACES),
        "configured_table_names": [
            "livermore_position_snapshot",
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
        ],
        "governance_record_write_status": "not_requested",
        "governance_validation_status": (
            (readiness.get("governance_record_validation") or {}).get("status")
            or "missing_direct_records"
        ),
        "reviewer_checklist": list(REVIEWER_CHECKLIST),
        "mcp_evidence_gap": (
            "Deferred MCP app tools for moss-metric-contracts, moss-lineage-evidence, "
            "moss-data-catalog, and gitnexus were not exposed in this Codex App session; "
            "local scripts/mcp evidence is used as the current fallback."
        ),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "certification_effect": "none",
            "validates_required_fields": True,
        },
        "evidence_anchors": {
            "gate_i_lane": "docs/audits/2026-06-06-stock-analysis-gate-i-lane.md",
            "signoff_packet": "docs/pnl/stock-analysis-sign-off-packet.md",
            "governance_audit_packet": "docs/pnl/stock-analysis-governance-audit-packet.md",
            "approval_template": "docs/pnl/stock-analysis-business-owner-approval-template.md",
            "owner_signoff_runbook": "docs/pnl/stock-analysis-owner-signoff-runbook.md",
            "golden_sample": "tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A",
            "readiness_command": "python scripts/codex_page_readiness.py --page-slug stock-analysis",
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
        f"- {surface}" for surface in packet["out_of_scope_surfaces"]
    )
    tables = "\n".join(f"- `{table}`" for table in packet["configured_table_names"])
    return f"""# Stock Analysis Owner Evidence Packet

Page ID: `{packet['page_id']}`
Page slug: `{packet['page_slug']}`
Primary API: `{packet['primary_api']}`
Business contract status: `{packet['business_contract_status']}`
Business contract certified: `{str(packet['business_contract_certified']).lower()}`
Formal use allowed: `formal_use_allowed={str(packet['formal_use_allowed']).lower()}`
Closure approved: `closure_approved={str(packet['closure_approved']).lower()}`
Business owner approval captured: `{str(packet['business_owner_approval_captured']).lower()}`
Handoff status: `{packet['handoff_status']}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote stock-analysis outputs to formal use, or authorize trading instructions.

## Current Certification Blockers

- `golden_sample_boundary={packet['golden_sample_boundary']}`
- `golden_sample_approval_artifact_status={packet['golden_sample_approval_artifact_status']}`
- `approval_action_item_count={packet['approval_action_item_count']}`
- `business_owner_approval_captured={str(packet['business_owner_approval_captured']).lower()}`

## Boundary

Golden sample boundary: `{packet['golden_sample_boundary']}`
Dedicated golden sample: `{packet['dedicated_golden_sample_id']}`
Route-specific evidence scope: `{packet['route_specific_evidence_scope']}`
Trading instruction allowed: `{str(packet['trading_instruction_allowed']).lower()}`
Execution approval allowed: `{str(packet['execution_approval_allowed']).lower()}`
Allocation advice allowed: `{str(packet['allocation_advice_allowed']).lower()}`
Position-change command allowed: `{str(packet['position_change_command_allowed']).lower()}`
Formal stock metric promotion allowed: `{str(packet['formal_stock_metric_promotion_allowed']).lower()}`
Observational boundary status: `{packet['observational_boundary_status']}`

Out of scope:

{out_of_scope}

## Governance Dry-Run

Governance record write status: `{packet['governance_record_write_status']}`
Governance validation status: `{packet['governance_validation_status']}`

## Configured Table Anchors

{tables}

## Evidence Anchors

{anchors}

## MCP Evidence Gap

{packet['mcp_evidence_gap']}

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the stock-analysis owner evidence packet without approving closure.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown packet path to write.",
    )
    args = parser.parse_args(argv)

    packet = build_packet()
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
