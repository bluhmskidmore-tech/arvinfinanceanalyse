from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_average_balance_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402
from scripts.emit_average_balance_governance_record import (  # noqa: E402
    build_payload as build_governance_payload,
    build_record,
)
from scripts.mcp.moss_project_mcp import (  # noqa: E402
    DEFAULT_GOVERNANCE_DIR,
    resolve_path_env,
)
from backend.app.schemas.adb_analysis import AdbAnalysisEnvelope  # noqa: E402


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "average-balance-owner-evidence-packet.md"
LIVE_SMOKE_EVIDENCE_ARTIFACT = (
    "docs/audits/2026-06-09-average-balance-live-smoke-evidence.md"
)
LATEST_VERIFICATION_SNAPSHOT_ARTIFACT = (
    "docs/audits/2026-06-10-average-balance-candidate-verification.md"
)
OWNER_SIGNOFF_RUNBOOK_ARTIFACT = "docs/pnl/average-balance-owner-signoff-runbook.md"
MONTHLY_GOLDEN_RESPONSE = (
    ROOT / "tests" / "golden_samples" / "GS-AVERAGE-BALANCE-MONTHLY-A" / "response.json"
)
MONTHLY_GOLDEN_RESPONSE_MODEL = "backend.app.schemas.adb_analysis.AdbAnalysisEnvelope"

DAILY_CANDIDATE_METRIC_IDS = [
    "MTR-ADB-001",
    "MTR-ADB-002",
]

MONTHLY_PENDING_METRIC_IDS = [
    "MTR-ADB-003",
]

DEDICATED_GOLDEN_SAMPLE_IDS = [
    "GS-AVERAGE-BALANCE-A",
    "GS-AVERAGE-BALANCE-MONTHLY-A",
]

OUT_OF_SCOPE_SURFACES = [
    "formal balance truth",
    "PAGE-BALANCE-001 replacement",
    "balance-analysis formal closure",
    "monthly ADB/NIM approval",
    "MTR-ADB formal-use promotion",
    "business-owner approval",
]

REVIEWER_CHECKLIST = [
    "Confirm MTR-ADB-001 and MTR-ADB-002 remain candidate daily ADB metrics bound to GS-AVERAGE-BALANCE-A.",
    "Confirm MTR-ADB-003 remains candidate monthly ADB/NIM evidence bound only to GS-AVERAGE-BALANCE-MONTHLY-A.",
    "Review the dry-run governance candidate without treating it as a written direct record.",
    "Review current UI/API payload and live smoke evidence before signature.",
    "Complete and sign docs/pnl/average-balance-business-owner-approval-template.md before any closure claim.",
]


def _monthly_golden_response_model_readiness(
    response_path: Path = MONTHLY_GOLDEN_RESPONSE,
) -> dict[str, Any]:
    try:
        payload = json.loads(Path(response_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "status": "recapture-required",
            "response_model": MONTHLY_GOLDEN_RESPONSE_MODEL,
            "response_model_valid": False,
            "recapture_required": True,
            "missing_required_fields": [],
            "validation_error_types": ["response_missing"],
            "writes_golden_sample": False,
            "captures_golden_sample_approval": False,
        }
    except (OSError, json.JSONDecodeError):
        return {
            "status": "recapture-required",
            "response_model": MONTHLY_GOLDEN_RESPONSE_MODEL,
            "response_model_valid": False,
            "recapture_required": True,
            "missing_required_fields": [],
            "validation_error_types": ["response_unreadable"],
            "writes_golden_sample": False,
            "captures_golden_sample_approval": False,
        }

    try:
        AdbAnalysisEnvelope.model_validate(payload)
    except ValidationError as exc:
        errors = exc.errors(
            include_url=False, include_context=False, include_input=False
        )
        missing_fields = sorted(
            {
                ".".join(str(part) for part in error["loc"])
                for error in errors
                if error["type"] == "missing"
            }
        )
        return {
            "status": "recapture-required",
            "response_model": MONTHLY_GOLDEN_RESPONSE_MODEL,
            "response_model_valid": False,
            "recapture_required": True,
            "missing_required_fields": missing_fields,
            "validation_error_types": sorted({str(error["type"]) for error in errors}),
            "writes_golden_sample": False,
            "captures_golden_sample_approval": False,
        }

    return {
        "status": "model-valid-awaiting-owner-review",
        "response_model": MONTHLY_GOLDEN_RESPONSE_MODEL,
        "response_model_valid": True,
        "recapture_required": False,
        "missing_required_fields": [],
        "validation_error_types": [],
        "writes_golden_sample": False,
        "captures_golden_sample_approval": False,
    }


def build_packet(
    *,
    template_path: Path = DEFAULT_TEMPLATE,
    governance_dir: Path = resolve_path_env(
        "MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR
    ),
    created_at: str = "2026-06-09T00:00:00Z",
) -> dict[str, Any]:
    readiness = build_page_readiness_report("average-balance")
    approval = build_approval_status(template_path)
    governance = build_governance_payload(
        record=build_record(created_at),
        governance_dir=Path(governance_dir),
        write=False,
    )
    preflight = governance["preflight"]
    governance_validation = preflight["validation"]
    monthly_golden_readiness = _monthly_golden_response_model_readiness()
    remaining_blockers = list(approval["remaining_blockers"])
    if monthly_golden_readiness["recapture_required"]:
        remaining_blockers.append("monthly_golden_response_model_recapture")
    reviewer_checklist = list(REVIEWER_CHECKLIST)
    if monthly_golden_readiness["recapture_required"]:
        reviewer_checklist.insert(
            2,
            "Regenerate the monthly response from the deterministic fixture-backed producer, review the full diff, and keep approval as a separate owner action.",
        )
    return {
        "packet_kind": "average_balance_owner_evidence_packet",
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
        "business_owner_approval_captured": approval[
            "business_owner_approval_captured"
        ],
        "approval_action_item_count": approval["approval_action_item_count"],
        "remaining_blockers": remaining_blockers,
        "owner_action_items": list(approval["approval_action_items"]),
        "golden_sample_boundary": "daily_and_monthly_adb_candidate_dto_capture_ready_pending_approval",
        "dedicated_golden_sample_id": "GS-AVERAGE-BALANCE-A",
        "dedicated_golden_sample_ids": list(DEDICATED_GOLDEN_SAMPLE_IDS),
        "daily_candidate_metric_ids": list(DAILY_CANDIDATE_METRIC_IDS),
        "monthly_pending_metric_ids": list(MONTHLY_PENDING_METRIC_IDS),
        "monthly_adb_nim_approval_allowed": False,
        "formal_balance_truth_approval_allowed": False,
        "out_of_scope_surfaces": list(OUT_OF_SCOPE_SURFACES),
        "configured_table_names": list(preflight["configured_table_names"]),
        "record_key": dict(governance["record_key"]),
        "governance_record_write_status": governance["record_write_status"],
        "governance_existing_record_line": governance["existing_record_line"],
        "governance_validation_status": governance_validation["validation_status"],
        "golden_sample_approval_artifact_status": readiness[
            "golden_sample_approval_artifact_status"
        ],
        "golden_sample_approval_artifact_mismatch": readiness[
            "golden_sample_approval_artifact_mismatch"
        ],
        "monthly_golden_response_model_readiness": monthly_golden_readiness,
        "reviewer_checklist": reviewer_checklist,
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "certification_effect": "none",
            "validates_required_fields": True,
            "approves_formal_balance_truth": False,
            "approves_monthly_adb_nim_truth": False,
            "validates_monthly_golden_response_model": True,
        },
        "evidence_anchors": {
            "page_contract": "docs/pnl/average-balance-page-contract.md",
            "owner_approval_template": "docs/pnl/average-balance-business-owner-approval-template.md",
            "owner_signoff_runbook": OWNER_SIGNOFF_RUNBOOK_ARTIFACT,
            "daily_golden_sample": "tests/golden_samples/GS-AVERAGE-BALANCE-A",
            "monthly_golden_sample": "tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A",
            "monthly_golden_response_model": "backend/app/schemas/adb_analysis.py",
            "response_model_preservation_test": "tests/test_api_response_model_field_preservation.py",
            "monthly_recapture_candidate_tool": "scripts/capture_average_balance_monthly_golden_candidate.py",
            "monthly_recapture_candidate_command": "python scripts/capture_average_balance_monthly_golden_candidate.py --output-dir <new-review-dir>",
            "metric_dictionary": "docs/metric_dictionary.md",
            "live_smoke_evidence": LIVE_SMOKE_EVIDENCE_ARTIFACT,
            "latest_verification_snapshot": LATEST_VERIFICATION_SNAPSHOT_ARTIFACT,
            "readiness_command": "python scripts/codex_page_readiness.py --page-slug average-balance",
            "smoke_command": "scripts/codex-page-smoke.ps1 -PageSlug average-balance",
            "verify_command": "scripts/codex-verify-page.ps1 -PageSlug average-balance -Run",
            "governance_dry_run": "python scripts/emit_average_balance_governance_record.py",
            "owner_approval_checker": "python scripts/check_average_balance_business_owner_approval.py",
        },
    }


def render_markdown(packet: dict[str, Any]) -> str:
    existing_record_line = (
        "dry-run not written"
        if packet["governance_record_write_status"] == "not_requested"
        else str(packet["governance_existing_record_line"])
    )
    action_items = "\n".join(
        (
            f"- {_display_template_field(str(item['template_field']))}: "
            f"`{item['required_value']}` (`{item['current_status']}`)"
        )
        for item in packet["owner_action_items"]
    )
    checklist = "\n".join(f"- {item}" for item in packet["reviewer_checklist"])
    anchors = "\n".join(
        f"- {label}: `{path}`" for label, path in packet["evidence_anchors"].items()
    )
    out_of_scope = "\n".join(
        f"- {surface}" for surface in packet["out_of_scope_surfaces"]
    )
    daily_metric_ids = "\n".join(
        f"- `{metric_id}`" for metric_id in packet["daily_candidate_metric_ids"]
    )
    monthly_metric_ids = "\n".join(
        f"- `{metric_id}`" for metric_id in packet["monthly_pending_metric_ids"]
    )
    dedicated_samples = ", ".join(
        f"`{sample_id}`" for sample_id in packet["dedicated_golden_sample_ids"]
    )
    tables = "\n".join(f"- `{table}`" for table in packet["configured_table_names"])
    monthly_readiness = packet["monthly_golden_response_model_readiness"]
    missing_required_fields = (
        ", ".join(
            f"`{field}`" for field in monthly_readiness["missing_required_fields"]
        )
        or "`none`"
    )
    validation_error_types = (
        ", ".join(
            f"`{error_type}`"
            for error_type in monthly_readiness["validation_error_types"]
        )
        or "`none`"
    )
    return f"""# Average Balance Owner Evidence Packet

Page ID: `{packet["page_id"]}`
Page slug: `{packet["page_slug"]}`
Primary API: `{packet["primary_api"]}`
Business contract status: `{packet["business_contract_status"]}`
Business contract certified: `{str(packet["business_contract_certified"]).lower()}`
Formal use allowed: `formal_use_allowed={str(packet["formal_use_allowed"]).lower()}`
Closure approved: `closure_approved={str(packet["closure_approved"]).lower()}`
Business owner approval captured: `{str(packet["business_owner_approval_captured"]).lower()}`
Handoff status: `{packet["handoff_status"]}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote ADB metrics to formal use, replace formal balance truth, or approve monthly ADB/NIM truth.

## Current Certification Blockers

- `golden_sample_boundary={packet["golden_sample_boundary"]}`
- `golden_sample_approval_artifact_status={packet["golden_sample_approval_artifact_status"]}`
- `monthly_golden_response_model_status={monthly_readiness["status"]}`
- `monthly_golden_recapture_required={str(monthly_readiness["recapture_required"]).lower()}`
- `approval_action_item_count={packet["approval_action_item_count"]}`
- `business_owner_approval_captured={str(packet["business_owner_approval_captured"]).lower()}`

## Monthly Golden Response-Model Readiness

- Response model: `{monthly_readiness["response_model"]}`
- Status: `{monthly_readiness["status"]}`
- Response-model valid: `{str(monthly_readiness["response_model_valid"]).lower()}`
- Deterministic recapture required: `{str(monthly_readiness["recapture_required"]).lower()}`
- Missing required fields: {missing_required_fields}
- Validation error types: {validation_error_types}
- `writes_golden_sample={str(monthly_readiness["writes_golden_sample"]).lower()}`
- `captures_golden_sample_approval={str(monthly_readiness["captures_golden_sample_approval"]).lower()}`

This packet diagnoses the stored sample only. It does not regenerate `response.json`, accept the producer diff, or record owner approval.

## Boundary

Golden sample boundary: `{packet["golden_sample_boundary"]}`
Dedicated golden samples: {dedicated_samples}
Monthly ADB/NIM approval allowed: `{str(packet["monthly_adb_nim_approval_allowed"]).lower()}`
Formal balance truth approval allowed: `{str(packet["formal_balance_truth_approval_allowed"]).lower()}`

Daily candidate metrics covered by the sample:

{daily_metric_ids}

Monthly candidate metrics covered only by the monthly candidate sample:

{monthly_metric_ids}

Out of scope:

{out_of_scope}

## Governance Dry-Run

Governance record write status: `{packet["governance_record_write_status"]}`
Governance validation status: `{packet["governance_validation_status"]}`
Existing record line: `{existing_record_line}`

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
- `approves_formal_balance_truth=false`
- `approves_monthly_adb_nim_truth=false`
- `validates_monthly_golden_response_model=true`
"""


def _display_template_field(template_field: str) -> str:
    return template_field.removeprefix("- ").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the average-balance owner evidence packet without approving closure.",
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
        default="2026-06-09T00:00:00Z",
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
        "monthly_golden_response_model_readiness": packet[
            "monthly_golden_response_model_readiness"
        ],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
