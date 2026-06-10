from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_average_balance_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "average-balance-business-owner-approval-template.md"

TEMPLATE_TEXT = """# Average Balance Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `GAP-AVERAGE-BALANCE-PAGE`
Page slug: `average-balance`
Primary API: `/api/analysis/adb`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote `MTR-ADB-001` through `MTR-ADB-003` to formal use.
- `GS-AVERAGE-BALANCE-A` covers only the daily `GET /api/analysis/adb` DTO for `MTR-ADB-001` and `MTR-ADB-002`.
- `MTR-ADB-003` remains monthly ADB/NIM pending and has no dedicated monthly/NIM golden sample.
- Do not replace `PAGE-BALANCE-001` or `/balance-analysis` formal balance truth.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `approves_formal_balance_truth=false`
- `approves_monthly_adb_nim_truth=false`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed owner evidence packet: `docs/pnl/average-balance-owner-evidence-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Daily ADB golden sample reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`
- Formal balance truth boundary accepted: `<yes | no>`
- Monthly ADB/NIM boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
"""


def _filled_template_text(
    *,
    decision: str = "approve",
    approval_date: str = "2026-06-09",
) -> str:
    return (
        TEMPLATE_TEXT.replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Average Balance Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Finance Analytics Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Average Balance Owner`")
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace("- Daily ADB golden sample reviewed: `<yes | no>`", "- Daily ADB golden sample reviewed: `yes`")
        .replace("- UI/API payload evidence reviewed: `<yes | no>`", "- UI/API payload evidence reviewed: `yes`")
        .replace("- Live smoke evidence reviewed: `<yes | no>`", "- Live smoke evidence reviewed: `yes`")
        .replace(
            "- Verification commands rerun before approval: `<yes | no>`",
            "- Verification commands rerun before approval: `yes`",
        )
        .replace("- Candidate-only boundary accepted: `<yes | no>`", "- Candidate-only boundary accepted: `yes`")
        .replace(
            "- Formal balance truth boundary accepted: `<yes | no>`",
            "- Formal balance truth boundary accepted: `yes`",
        )
        .replace(
            "- Monthly ADB/NIM boundary accepted: `<yes | no>`",
            "- Monthly ADB/NIM boundary accepted: `yes`",
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


def test_average_balance_business_owner_approval_checker_reports_pending_template() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), check=False)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)

    assert payload["page_id"] == "GAP-AVERAGE-BALANCE-PAGE"
    assert payload["page_slug"] == "average-balance"
    assert payload["primary_api"] == "/api/analysis/adb"
    assert payload["approval_check"] == "business_owner_approval"
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
        "daily_golden_sample_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "candidate_boundary_acceptance",
        "formal_balance_truth_boundary_acceptance",
        "monthly_adb_nim_boundary_acceptance",
    ]
    assert payload["approval_field_status"]["business_owner_name"] == "missing"
    assert payload["approval_field_status"]["reviewed_owner_evidence_packet"] == "valid"
    assert payload["approval_field_status"]["daily_golden_sample_review"] == "pending"
    assert payload["approval_field_status"]["monthly_adb_nim_boundary_acceptance"] == "pending"
    assert payload["approval_action_item_count"] == 13
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "approves_formal_balance_truth": False,
        "approves_monthly_adb_nim_truth": False,
    }
    assert {
        "blocker": "monthly_adb_nim_boundary_acceptance",
        "template_field": "- Monthly ADB/NIM boundary accepted",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]


def test_average_balance_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), "--require-captured", check=False)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_average_balance_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "average-balance-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), "--require-captured", check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_action_item_count"] == 0
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["approves_formal_balance_truth"] is False
    assert payload["evidence_scope"]["approves_monthly_adb_nim_truth"] is False


def test_average_balance_business_owner_approval_checker_rejects_formal_use_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "average-balance-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Formal use allowed: `formal_use_allowed=false`",
            "Formal use allowed: `formal_use_allowed=true`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
    assert payload["remaining_blockers"] == ["business_owner_approval", "formal_use_promotion_boundary"]


def test_average_balance_business_owner_approval_checker_rejects_missing_certification_effect(
    tmp_path: Path,
) -> None:
    template = tmp_path / "average-balance-approval-template.md"
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


def test_average_balance_business_owner_approval_checker_rejects_wrong_owner_evidence_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "average-balance-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed owner evidence packet: `docs/pnl/average-balance-owner-evidence-packet.md`",
            "Reviewed owner evidence packet: `docs/pnl/other-owner-evidence-packet.md`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker("--template-path", str(template), check=False)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "reviewed_owner_evidence_packet"]
