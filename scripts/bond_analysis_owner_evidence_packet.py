from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_bond_analysis_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "bond-analysis-owner-evidence-packet.md"
DEFAULT_AUDIT_OUTPUT = ROOT / "docs" / "pnl" / "bond-analysis-governance-audit-packet.md"
LIVE_SMOKE_EVIDENCE_ARTIFACT = (
    "docs/audits/2026-06-09-bond-analysis-live-smoke-evidence.md"
)
LIVE_SMOKE_COMMAND = "scripts/codex-page-smoke.ps1 -PageSlug bond-analysis"

OUT_OF_SCOPE_SURFACES = [
    "PAGE-BOND-001",
    "/bond-dashboard",
    "GS-BOND-HEADLINE-A",
    "MTR-BOND-001 through MTR-BOND-004",
    "formal fixed-income metric truth",
    "trading instructions or action recommendations",
    "business-owner approval",
]

NON_REUSABLE_DASHBOARD_EVIDENCE = [
    "PAGE-BOND-001",
    "/bond-dashboard",
    "GS-BOND-HEADLINE-A",
    "MTR-BOND-001 through MTR-BOND-004",
]

REVIEWER_CHECKLIST = [
    "Confirm GS-BOND-ANALYSIS-ACTION-ATTR-A remains scoped to GET /api/bond-analytics/action-attribution DTO evidence.",
    "Review fixed-income units and signs for action-attribution PnL, duration, DV01, KRD, yield/YTM, bp movement, credit-spread, holdings, and accounting-class fields.",
    "Review catalog/date evidence for fact_formal_bond_analytics_daily before signature.",
    "Run or review the direct page/API governance record generator before signature; current packet does not write it.",
    "Complete and sign docs/pnl/bond-analysis-business-owner-approval-template.md before any closure claim.",
]

GOVERNANCE_RECORD_COMMANDS = {
    "dry_run": "python scripts/emit_bond_analysis_governance_record.py",
    "write": "python scripts/emit_bond_analysis_governance_record.py --write",
    "validate": "python scripts/codex_page_readiness.py --page-slug bond-analysis",
}

LATEST_VERIFICATION_EVIDENCE = {
    "static_readiness": "static-pass",
    "direct_governance_record": "ready_for_audit_review",
    "ui_api_payload_evidence": "GS-BOND-ANALYSIS-ACTION-ATTR-A response.json",
    "live_smoke_evidence": LIVE_SMOKE_EVIDENCE_ARTIFACT,
    "live_smoke_command": LIVE_SMOKE_COMMAND,
    "readiness_command": "python scripts/codex_page_readiness.py --page-slug bond-analysis",
    "boundary": (
        "Direct governance record and static readiness are ready for audit review. "
        "UI/API payload and live smoke evidence remain reviewer-confirmation inputs only; "
        "owner approval remains pending."
    ),
}

MANUAL_REVIEW_EVIDENCE = {
    "ui_api_payload_review": "tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json",
    "live_smoke_evidence_review": LIVE_SMOKE_EVIDENCE_ARTIFACT,
    "live_smoke_command_reference": LIVE_SMOKE_COMMAND,
}

FIXED_INCOME_CONVENTION_DECISION_ANCHOR = (
    "docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md"
)

FIXED_INCOME_CONVENTION_OWNER_CHOICES = [
    "market_value_basis=clean",
    "dirty_market_value_formula=market_value + accrued_interest",
    {
        "value": "accrued_interest_usage=dirty_price",
        "note": "current carry and action attribution do not directly consume accrued interest as an independent attribution driver",
    },
    "day_count=ACT/365_approximation",
    "yield_compounding=nominal_annual_with_coupon_frequency",
    "duration_convexity_scope=vanilla_fixed_rate_only",
    "dv01_unit=CNY_per_1bp",
    "dv01_base=CNY_face_value",
    "mcp_evidence_status=fallback_local_evidence_until_mcp_recheck",
]


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict[str, Any]:
    readiness = build_page_readiness_report("bond-analysis")
    approval = build_approval_status(template_path)
    catalog = readiness.get("catalog_date_evidence") or {}
    governance = readiness.get("governance_record_validation") or {}
    return {
        "packet_kind": "bond_analysis_owner_evidence_packet",
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
        "golden_sample_boundary": "action_attribution_capture_ready_pending_approval",
        "dedicated_golden_sample_id": "GS-BOND-ANALYSIS-ACTION-ATTR-A",
        "route_specific_evidence_scope": "bond_analysis_action_attribution_dto_only",
        "borrowed_dashboard_evidence_allowed": False,
        "dashboard_evidence_reuse_status": "blocked_for_bond_analysis_certification",
        "non_reusable_dashboard_evidence": list(NON_REUSABLE_DASHBOARD_EVIDENCE),
        "golden_sample_approval_artifact_status": readiness[
            "golden_sample_approval_artifact_status"
        ],
        "golden_sample_approval_artifact_mismatch": readiness[
            "golden_sample_approval_artifact_mismatch"
        ],
        "out_of_scope_surfaces": list(OUT_OF_SCOPE_SURFACES),
        "configured_table_names": list(
            catalog.get("sampled_table_names")
            or ["fact_formal_bond_analytics_daily"]
        ),
        "governance_record_write_status": "not_requested",
        "governance_validation_status": governance.get("status") or "missing_direct_records",
        "governance_record_commands": dict(GOVERNANCE_RECORD_COMMANDS),
        "governance_record_post_write_validation_status": "direct_records_ready_for_audit_review",
        "latest_verification_evidence": dict(LATEST_VERIFICATION_EVIDENCE),
        "manual_review_evidence": dict(MANUAL_REVIEW_EVIDENCE),
        "reviewer_checklist": list(REVIEWER_CHECKLIST),
        "fixed_income_convention_decision_draft": FIXED_INCOME_CONVENTION_DECISION_ANCHOR,
        "fixed_income_convention_owner_choices": list(FIXED_INCOME_CONVENTION_OWNER_CHOICES),
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
            "gate_i_lane": "docs/audits/2026-06-06-bond-analysis-gate-i-lane.md",
            "signoff_packet": "docs/pnl/bond-analysis-sign-off-packet.md",
            "governance_audit_packet": "docs/pnl/bond-analysis-governance-audit-packet.md",
            "approval_template": "docs/pnl/bond-analysis-business-owner-approval-template.md",
            "fixed_income_convention_decision_draft": FIXED_INCOME_CONVENTION_DECISION_ANCHOR,
            "live_smoke_evidence": LIVE_SMOKE_EVIDENCE_ARTIFACT,
            "golden_sample": "tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A",
            "readiness_command": "python scripts/codex_page_readiness.py --page-slug bond-analysis",
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
    governance_commands = "\n".join(
        [
            f"- Dry run: `{packet['governance_record_commands']['dry_run']}`",
            f"- Write: `{packet['governance_record_commands']['write']}`",
            f"- Validate: `{packet['governance_record_commands']['validate']}`",
        ]
    )
    out_of_scope = "\n".join(
        f"- {surface}" for surface in packet["out_of_scope_surfaces"]
    )
    fixed_income_choices = "\n".join(
        _display_fixed_income_choice(choice)
        for choice in packet["fixed_income_convention_owner_choices"]
    )
    latest = packet["latest_verification_evidence"]
    manual_evidence = packet["manual_review_evidence"]
    non_reusable_dashboard_evidence = _display_sentence_list(
        packet["non_reusable_dashboard_evidence"]
    )
    tables = "\n".join(f"- `{table}`" for table in packet["configured_table_names"])
    return f"""# Bond Analysis Owner Evidence Packet

Page ID: `{packet['page_id']}`
Page slug: `{packet['page_slug']}`
Primary API: `{packet['primary_api']}`
Business contract status: `{packet['business_contract_status']}`
Business contract certified: `{str(packet['business_contract_certified']).lower()}`
Formal use allowed: `formal_use_allowed={str(packet['formal_use_allowed']).lower()}`
Closure approved: `closure_approved={str(packet['closure_approved']).lower()}`
Business owner approval captured: `{str(packet['business_owner_approval_captured']).lower()}`
Handoff status: `{packet['handoff_status']}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote fixed-income metrics to formal use, or certify Bond Analysis as formal fixed-income truth.

## Current Certification Blockers

- `golden_sample_boundary={packet['golden_sample_boundary']}`
- `golden_sample_approval_artifact_status={packet['golden_sample_approval_artifact_status']}`
- `approval_action_item_count={packet['approval_action_item_count']}`
- `business_owner_approval_captured={str(packet['business_owner_approval_captured']).lower()}`

## Boundary

Golden sample boundary: `{packet['golden_sample_boundary']}`
Dedicated golden sample: `{packet['dedicated_golden_sample_id']}`
Route-specific evidence scope: `{packet['route_specific_evidence_scope']}`
Borrowed dashboard evidence allowed: `{str(packet['borrowed_dashboard_evidence_allowed']).lower()}`
Dashboard evidence reuse status: `{packet['dashboard_evidence_reuse_status']}`

{non_reusable_dashboard_evidence} are non-reusable for /bond-analysis certification.

Out of scope:

{out_of_scope}

## Governance Dry-Run

Governance record write status: `{packet['governance_record_write_status']}`
Governance validation status: `{packet['governance_validation_status']}`
Governance post-write validation target: `{packet['governance_record_post_write_validation_status']}`

Commands:

{governance_commands}

## Configured Table Anchors

{tables}

## Latest Verification Evidence

- Static readiness: `{latest['static_readiness']}`
- Direct governance record: `{latest['direct_governance_record']}`
- UI/API payload evidence: `{latest['ui_api_payload_evidence']}`
- Live smoke evidence: `{latest['live_smoke_evidence']}`
- Live smoke command: `{latest['live_smoke_command']}`
- Readiness command: `{latest['readiness_command']}`
- Boundary: {latest['boundary']}

## Manual Review Evidence References

- UI/API payload review: `{manual_evidence['ui_api_payload_review']}`
- Live smoke evidence review: `{manual_evidence['live_smoke_evidence_review']}`
- Live smoke command reference: `{manual_evidence['live_smoke_command_reference']}`

## Evidence Anchors

{anchors}

## Fixed-Income Convention Review

Delegated read-only review has been completed for the remaining fixed-income convention blockers. The current recommended owner choices are captured in `{packet['fixed_income_convention_decision_draft']}`.

Owner confirmation is still required for:

{fixed_income_choices}

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


def render_audit_markdown(packet: dict[str, Any]) -> str:
    governance_commands = "\n".join(
        [
            f"- Dry run: `{packet['governance_record_commands']['dry_run']}`",
            f"- Write: `{packet['governance_record_commands']['write']}`",
            f"- Validate: `{packet['governance_record_commands']['validate']}`",
        ]
    )
    tables = "\n".join(f"- `{table}`" for table in packet["configured_table_names"])
    manual_evidence = packet["manual_review_evidence"]
    direct_record_status = (
        "ready_for_audit_review"
        if packet["governance_validation_status"] == "direct_records_ready_for_audit_review"
        else "missing_or_incomplete"
    )
    return f"""# Bond Analysis Governance Audit Packet

Page ID: `{packet['page_id']}`
Route: `{packet['route']}`
Primary API: `{packet['primary_api']}`
Governance record write status: `{packet['governance_record_write_status']}`
Governance validation status: `{packet['governance_validation_status']}`
Direct page/API governance record status: `{direct_record_status}`
Closure approved: `closure_approved={str(packet['closure_approved']).lower()}`
Formal use allowed: `formal_use_allowed={str(packet['formal_use_allowed']).lower()}`

This packet does not write governance records, approve page closure, promote fixed-income metrics to formal use, prove live page/API execution, or capture business-owner approval.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Current Audit Status

- Direct page/API governance record: `{direct_record_status}`
- Catalog/date evidence: `sampled`
- Golden sample boundary: `{packet['golden_sample_boundary']}`
- UI/API payload review evidence: `{manual_evidence['ui_api_payload_review']}`
- Live smoke evidence review: `{manual_evidence['live_smoke_evidence_review']}`
- Live smoke command reference: `{manual_evidence['live_smoke_command_reference']}`
- Business owner approval: `{packet['approval_status']}`
- Business owner approval captured: `{str(packet['business_owner_approval_captured']).lower()}`

## Configured Table Anchors

{tables}

## Audit Requirements

- Review direct page/API governance record for `PAGE-BOND-ANALYSIS-001` and `/api/bond-analytics/action-attribution`.
- Review catalog/date evidence for `fact_formal_bond_analytics_daily`.
- Review lineage for source/rule/cache versions and fallback/stale states.
- Manually review DV01, duration, KRD, yield/YTM, bp movement, credit-spread, holdings, accounting-class, and action-attribution PnL units/sign/date rules.
- Complete business-owner approval after manual review.

## Governance Record Commands

{governance_commands}

The write command appends a candidate direct record only. It does not approve page closure, promote fixed-income metrics to formal use, prove live page/API execution, or capture business-owner approval.
"""


def _display_template_field(template_field: str) -> str:
    return template_field.removeprefix("- ").strip()


def _display_fixed_income_choice(choice: Any) -> str:
    if isinstance(choice, dict):
        return f"- `{choice['value']}`; {choice['note']}"
    return f"- `{choice}`"


def _display_sentence_list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the bond-analysis owner evidence packet without approving closure.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown packet path to write.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        default=DEFAULT_AUDIT_OUTPUT,
        help="Governance audit packet markdown path to write.",
    )
    args = parser.parse_args(argv)

    packet = build_packet()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(packet), encoding="utf-8")
    audit_output_path = Path(args.audit_output)
    audit_output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_output_path.write_text(render_audit_markdown(packet), encoding="utf-8")
    payload = {
        "packet_kind": packet["packet_kind"],
        "packet_path": str(output_path),
        "audit_packet_path": str(audit_output_path),
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
