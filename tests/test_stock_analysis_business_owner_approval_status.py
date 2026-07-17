from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_stock_analysis_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "stock-analysis-business-owner-approval-template.md"

TEMPLATE_TEXT = """# Stock Analysis Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `GAP-STOCK-ANALYSIS-PAGE`
Page slug: `stock-analysis`
Primary API: `/ui/market-data/stock-analysis/workbench`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Observational Boundary

- Do not promote Livermore candidates, signal confluence, strategy-score, optimization, sector rank, or proxy backtests to formal stock-analysis truth.
- Do not create trading instructions, execution approvals, allocation advice, or position-change commands from this page.
- Golden sample `GS-STOCK-ANALYSIS-OBS-A` is captured-awaiting-approval and does not approve this page for formal use.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed sign-off packet: `docs/pnl/stock-analysis-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/stock-analysis-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/stock-analysis-owner-evidence-packet.md`
Owner signoff runbook: `docs/pnl/stock-analysis-owner-signoff-runbook.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Golden sample `GS-STOCK-ANALYSIS-OBS-A` reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- No-trading-instruction boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
"""


def _filled_template_text(
    *,
    decision: str = "approve",
    approval_date: str = "2026-06-06",
) -> str:
    return (
        TEMPLATE_TEXT.replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Stock Analysis Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Market Research Control Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Stock Analysis Owner`")
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace(
            "- Golden sample `GS-STOCK-ANALYSIS-OBS-A` reviewed: `<yes | no>`",
            "- Golden sample `GS-STOCK-ANALYSIS-OBS-A` reviewed: `yes`",
        )
        .replace("- UI/API payload evidence reviewed: `<yes | no>`", "- UI/API payload evidence reviewed: `yes`")
        .replace("- Live smoke evidence reviewed: `<yes | no>`", "- Live smoke evidence reviewed: `yes`")
        .replace(
            "- Verification commands rerun before approval: `<yes | no>`",
            "- Verification commands rerun before approval: `yes`",
        )
        .replace(
            "- No-trading-instruction boundary accepted: `<yes | no>`",
            "- No-trading-instruction boundary accepted: `yes`",
        )
    )


def _run_checker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def test_stock_analysis_business_owner_approval_checker_reports_pending_template() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), check=False)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)

    assert payload["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
    assert payload["page_slug"] == "stock-analysis"
    assert payload["primary_api"] == "/ui/market-data/stock-analysis/workbench"
    assert payload["approval_status"] == "pending"
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is False
    assert payload["closure_approved"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "business_owner_name",
        "business_owner_role",
        "approval_decision",
        "approval_date",
        "business_owner_signature",
        "governance_record_review",
        "golden_sample_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "not_trading_instruction_review",
    ]
    assert payload["approval_action_item_count"] == 11
    assert {
        "blocker": "not_trading_instruction_review",
        "template_field": "- No-trading-instruction boundary accepted",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert payload["approval_field_status"]["not_trading_instruction_review"] == "pending"
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }


def test_stock_analysis_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), "--require-captured", check=False)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_stock_analysis_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "stock-analysis-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), "--require-captured", check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_action_items"] == []
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"


def test_stock_analysis_business_owner_approval_checker_requires_no_certification_effect(
    tmp_path: Path,
) -> None:
    template = tmp_path / "stock-analysis-approval-template.md"
    template.write_text(
        _filled_template_text().replace("- `certification_effect=none`\n", ""),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_effect_boundary",
    ]
    assert payload["approval_field_status"]["certification_effect"] == "missing"
    assert {
        "blocker": "certification_effect_boundary",
        "template_field": "- `certification_effect=none`",
        "required_value": "none",
        "current_status": "missing",
    } in payload["approval_action_items"]


def test_stock_analysis_business_owner_approval_checker_rejects_bad_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "stock-analysis-approval-template.md"
    template.write_text(_filled_template_text(approval_date="06/06/2026"), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_date"]


def test_stock_analysis_business_owner_approval_template_references_owner_runbook() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "Reviewed sign-off packet: `docs/pnl/stock-analysis-sign-off-packet.md`" in text
    assert (
        "Reviewed governance audit packet: "
        "`docs/pnl/stock-analysis-governance-audit-packet.md`"
    ) in text
    assert "Reviewed owner evidence packet: `docs/pnl/stock-analysis-owner-evidence-packet.md`" in text
    assert "Owner signoff runbook: `docs/pnl/stock-analysis-owner-signoff-runbook.md`" in text
