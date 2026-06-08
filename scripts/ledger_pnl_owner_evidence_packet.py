from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ledger_pnl_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402
from scripts.emit_ledger_pnl_governance_record import (  # noqa: E402
    build_payload as build_governance_payload,
    build_record,
)
from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_GOVERNANCE_DIR,
    resolve_path_env,
)


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "ledger-pnl-owner-evidence-packet.md"

CANDIDATE_METRIC_IDS = [
    "MTR-LPN-001",
    "MTR-LPN-002",
    "MTR-LPN-003",
]

OUT_OF_SCOPE_SURFACES = [
    "formal PnL overview truth",
    "product-category PnL truth",
    "PnL bridge truth",
    "formal financial indicator truth",
    "MTR-LPN formal-use promotion",
    "business-owner approval",
]

REVIEWER_CHECKLIST = [
    "Confirm MTR-LPN-001 through MTR-LPN-003 remain candidate metrics with pending confirmation.",
    "Review the dry-run governance candidate without treating it as a written direct record.",
    "Review GS-LEDGER-PNL-SUMMARY-A as a capture-ready dedicated summary sample awaiting approval.",
    "Review current UI/API payload and live smoke evidence before signature.",
    "Complete and sign docs/pnl/ledger-pnl-business-owner-approval-template.md before any closure claim.",
]


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
    governance_dir: Path = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR),
    created_at: str = "2026-06-05T12:01:14.993184Z",
) -> dict[str, Any]:
    readiness = build_page_readiness_report("ledger-pnl")
    approval = build_approval_status(template_path)
    governance = build_governance_payload(
        record=build_record(created_at),
        governance_dir=Path(governance_dir),
        write=False,
    )
    preflight = governance["preflight"]
    governance_validation = preflight["validation"]
    return {
        "packet_kind": "ledger_pnl_owner_evidence_packet",
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
        "golden_sample_boundary": "dedicated_summary_capture_ready_pending_approval",
        "dedicated_golden_sample_id": "GS-LEDGER-PNL-SUMMARY-A",
        "covered_candidate_metric_ids": list(CANDIDATE_METRIC_IDS),
        "out_of_scope_surfaces": list(OUT_OF_SCOPE_SURFACES),
        "configured_table_names": list(preflight["configured_table_names"]),
        "record_key": dict(governance["record_key"]),
        "governance_record_write_status": governance["record_write_status"],
        "governance_existing_record_line": governance["existing_record_line"],
        "governance_validation_status": governance_validation["validation_status"],
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
            "dedicated_summary_golden_sample_sync": "docs/audits/2026-06-06-ledger-pnl-dedicated-summary-golden-sample-sync.json",
            "direct_record_preflight": "docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json",
            "approval_template": "docs/pnl/ledger-pnl-business-owner-approval-template.md",
            "dedicated_golden_sample": "tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A",
            "readiness_command": "python scripts/codex_page_readiness.py --page-slug ledger-pnl",
            "governance_dry_run": "python scripts/emit_ledger_pnl_governance_record.py",
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
    metric_ids = "\n".join(
        f"- `{metric_id}`" for metric_id in packet["covered_candidate_metric_ids"]
    )
    tables = "\n".join(f"- `{table}`" for table in packet["configured_table_names"])
    return f"""# Ledger PnL Owner Evidence Packet

Page ID: `{packet['page_id']}`
Page slug: `{packet['page_slug']}`
Primary API: `{packet['primary_api']}`
Business contract status: `{packet['business_contract_status']}`
Business contract certified: `{str(packet['business_contract_certified']).lower()}`
Formal use allowed: `formal_use_allowed={str(packet['formal_use_allowed']).lower()}`
Closure approved: `closure_approved={str(packet['closure_approved']).lower()}`
Business owner approval captured: `{str(packet['business_owner_approval_captured']).lower()}`
Handoff status: `{packet['handoff_status']}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote candidate metric formal use, or certify Ledger PnL as formal PnL truth.

## Current Certification Blockers

- `golden_sample_boundary={packet['golden_sample_boundary']}`
- `approval_action_item_count={packet['approval_action_item_count']}`
- `business_owner_approval_captured={str(packet['business_owner_approval_captured']).lower()}`

## Boundary

Golden sample boundary: `{packet['golden_sample_boundary']}`
Dedicated golden sample: `{packet['dedicated_golden_sample_id']}`

Candidate metrics:

{metric_ids}

Out of scope:

{out_of_scope}

## Governance Dry-Run

Governance record write status: `{packet['governance_record_write_status']}`
Governance validation status: `{packet['governance_validation_status']}`
Existing record line: `{packet['governance_existing_record_line']}`

## Configured Table Anchors

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the ledger-pnl owner evidence packet without approving closure.",
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
        "--created-at",
        default="2026-06-05T12:01:14.993184Z",
        help="Stable dry-run record timestamp for reproducible packet output.",
    )
    args = parser.parse_args(argv)

    packet = build_packet(
        governance_dir=Path(args.governance_dir),
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
