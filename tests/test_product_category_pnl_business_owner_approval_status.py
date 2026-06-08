from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from scripts import check_product_category_pnl_business_owner_approval as approval_checker
from scripts.product_category_pnl_owner_decision_packet import build_packet as build_owner_decision_packet


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_product_category_pnl_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "product-category-pnl-business-owner-approval-template.md"
CONTINUATION_PLAN = (
    ROOT
    / "docs"
    / "plans"
    / "2026-06-06-top-investment-bank-standard-continuation-owner-signable-ui-hardening-plan.md"
)
CERTIFICATION_BOARD = ROOT / "docs" / "audits" / "2026-06-06-top-investment-bank-certification-board.md"
OWNER_SIGNABLE_PLAN = (
    ROOT
    / "docs"
    / "plans"
    / "2026-06-06-top-investment-bank-standard-owner-signable-closure-plan.md"
)
INSTITUTIONAL_FRONTEND_SCORECARD = (
    ROOT / "docs" / "audits" / "2026-06-05-institutional-frontend-scorecard.md"
)
FRONTEND_CERTIFICATION_ROADMAP = (
    ROOT / "docs" / "plans" / "2026-06-05-top-investment-bank-frontend-certification-roadmap.md"
)
DEEP_AUDIT_GOAL_QUEUE = ROOT / "docs" / "plans" / "2026-06-06-deep-audit-goal-queue.md"
APPROVAL_RUNBOOK = ROOT / "docs" / "pnl" / "product-category-pnl-approval-runbook.md"


def _lettered_goal_key(goal_id: str) -> tuple[int, int]:
    match = re.fullmatch(r"G(\d+)([a-z])", goal_id)
    assert match is not None
    return int(match.group(1)), ord(match.group(2)) - ord("a")


def _lettered_goal_ids_between(start: str, end: str) -> list[str]:
    start_number, start_letter = _lettered_goal_key(start)
    end_number, end_letter = _lettered_goal_key(end)
    ids = []
    for number in range(start_number, end_number + 1):
        first_letter = start_letter if number == start_number else 0
        last_letter = end_letter if number == end_number else 25
        ids.extend(
            f"G{number}{chr(letter + ord('a'))}"
            for letter in range(first_letter, last_letter + 1)
        )
    return ids


def _latest_verification_checkpoint_section(text: str) -> str:
    start = text.index("## Latest Verification Checkpoints")
    end = text.index("## Execution Loop", start)
    return text[start:end]


def _filled_template_text(*, decision: str = "approve", approval_date: str = "2026-06-05") -> str:
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Product Category PnL Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Finance Product Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace(
            "Business owner signature: `<required>`",
            "Business owner signature: `Product Category PnL Owner`",
        )
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace(
            "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled: `<yes | no>`",
            "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled: `yes`",
        )
        .replace(
            "- Closure checklist units reviewed: `<yes | no>`",
            "- Closure checklist units reviewed: `yes`",
        )
        .replace(
            "- Owner decision packet reviewed: `<yes | no>`",
            "- Owner decision packet reviewed: `yes`",
        )
        .replace(
            "- Owner decision next-review queue acknowledged: `<yes | no>`",
            "- Owner decision next-review queue acknowledged: `yes`",
        )
        .replace(
            "- Fallback liability branch model-boundary evidence reviewed: `<yes | no>`",
            "- Fallback liability branch model-boundary evidence reviewed: `yes`",
        )
        .replace("- UI/API payload evidence reviewed: `<yes | no>`", "- UI/API payload evidence reviewed: `yes`")
        .replace("- Live smoke evidence reviewed: `<yes | no>`", "- Live smoke evidence reviewed: `yes`")
        .replace(
            "- Verification commands rerun before approval: `<yes | no>`",
            "- Verification commands rerun before approval: `yes`",
        )
        .replace("- Evidence-pending boundary accepted: `<yes | no>`", "- Evidence-pending boundary accepted: `yes`")
    )


def _run_checker(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def _approved_golden_sample_artifact(tmp_path: Path) -> Path:
    artifact = tmp_path / "GS-PROD-CAT-PNL-A-approval.md"
    artifact.write_text(
        "\n".join(
            [
                "# GS-PROD-CAT-PNL-A Approval",
                "",
                "- Sample ID: `GS-PROD-CAT-PNL-A`",
                "- Status: `approved`",
                "- Sample type: `capture-ready`",
                "- Owner: `Product Category PnL Owner`",
                "- Approver: `Finance Product Owner`",
                "- Approved at: `2026-06-05`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return artifact


def _closed_closure_checklist(tmp_path: Path) -> Path:
    checklist = tmp_path / "product-category-closure-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Product-Category PnL Closure Checklist",
                "",
                "## 4. Status Matrix",
                "",
                "| Unit | Status | Priority | Short reason |",
                "| --- | --- | --- | --- |",
                "| 1. Dates | `CLOSED` | `P1` | tested |",
                "| 2. Detail | `CLOSED` | `P0` | tested |",
                "| 3. Refresh + Status | `CLOSED` | `P0` | tested |",
                "| 4. Manual Adjustment Create | `CLOSED` | `P0` | tested |",
                "| 5. Manual Adjustment List | `CLOSED` | `P1` | tested |",
                "| 6. Manual Adjustment Export | `CLOSED` | `P1` | tested |",
                "| 7. Manual Adjustment Lifecycle | `CLOSED` | `P0` | tested |",
                "| 8. Governance / Traceability | `CLOSED` | `P0` | tested |",
                "| 9. Frontend Cross-Field Consistency | `CLOSED` | `P0` | tested |",
                "| 10. Test Coverage | `CLOSED` | `P0` | tested |",
                "",
                "## 6. Current Distribution",
                "",
                "- `CLOSED`: 10",
                "- `PARTIAL`: 0",
                "- `NOT_TRUSTED`: 0",
                "- `EXCLUDED`: 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return checklist


def test_product_category_owner_signable_continuation_plan_uses_current_action_count() -> None:
    text = CONTINUATION_PLAN.read_text(encoding="utf-8")

    assert "approval_action_item_count=15" in text
    assert "`15` owner action items and `15` closure blockers" in text
    assert "approval_action_item_count=14" not in text
    assert "`14` owner action items" not in text


def test_product_category_current_status_docs_use_current_action_count() -> None:
    for path in [CERTIFICATION_BOARD, OWNER_SIGNABLE_PLAN]:
        text = path.read_text(encoding="utf-8")
        assert "approval_action_item_count=15" in text
        assert "approval_action_item_count=14" not in text


def test_product_category_approval_checker_signoff_summary_groups_packet_boundary_blockers() -> None:
    summary = approval_checker._business_owner_action_signoff_summary(
        [
            {
                "blocker": "reviewed_first_certification_packet",
                "current_status": "stale_generated_artifact",
            },
            {
                "blocker": "certification_packet_consistency",
                "current_status": "stale_generated_artifact",
            },
        ],
        formal_use_allowed=True,
        closure_approved=False,
    )

    assert summary["signoff_group_counts"] == {"evidence_review": 2}
    assert summary["signed_group_counts"] == {}
    assert summary["unsigned_group_counts"] == {"evidence_review": 2}
    assert summary["owner_signable"] is False
    assert summary["captures_business_owner_approval"] is False


def test_product_category_approval_checker_treats_missing_artifact_as_missing_not_pending() -> None:
    summary = approval_checker._business_owner_action_signoff_summary(
        [
            {
                "blocker": "reviewed_owner_decision_packet",
                "current_status": "missing_artifact",
            },
        ],
        formal_use_allowed=True,
        closure_approved=False,
    )

    assert summary["signed_item_count"] == 0
    assert summary["unsigned_item_count"] == 1
    assert summary["missing_or_invalid_item_count"] == 1
    assert summary["pending_review_item_count"] == 0


def test_product_category_approval_checker_signoff_groups_cover_all_action_definitions() -> None:
    assert set(approval_checker.ACTION_SIGNOFF_GROUPS) == set(
        approval_checker.ACTION_ITEM_DEFINITIONS
    )


def test_product_category_certification_board_surfaces_packet_consistency_boundary() -> None:
    text = CERTIFICATION_BOARD.read_text(encoding="utf-8")

    assert "certification_packet_consistency.status=valid" in text
    assert "certification_packet_consistency.missing_marker_count=0" in text
    assert "certification_packet_consistency.business_owner_action_signed_item_count=0" in text
    assert (
        "certification_packet_consistency.business_owner_action_pending_or_missing_item_count=15"
        in text
    )
    assert "business_owner_action_signoff_group_counts.owner_identity=2" in text
    assert "business_owner_action_signoff_group_counts.owner_decision=3" in text
    assert "business_owner_action_signoff_group_counts.evidence_review=7" in text
    assert "business_owner_action_signoff_group_counts.pre_signature_verification=2" in text
    assert "business_owner_action_signoff_group_counts.boundary_acceptance=1" in text
    assert "business_owner_action_signed_group_counts.none=0" in text
    assert "business_owner_action_pending_group_counts.evidence_review=7" in text
    assert "business_owner_action_missing_or_invalid_item_count=5" in text
    assert "business_owner_action_pending_review_item_count=10" in text
    assert "approval_field_status.owner_decision_next_review_queue_acknowledgement=pending" in text
    assert "next-review queue acknowledgement remains pending" in text
    assert "certification_packet_consistency.owner_signable=false" in text
    assert "certification_packet_consistency.can_promote_certification=false" in text
    assert "certification_packet_consistency.approves_metric_or_page=false" in text
    assert "certification_packet_consistency.captures_business_owner_approval=false" in text
    assert "certification_packet_consistency.captures_business_owner_signature=false" in text
    assert "certification_packet_consistency.captures_product_or_api_decisions=false" in text
    assert "certification_packet_consistency.captures_golden_sample_approval=false" in text
    assert "certification_packet_consistency.captures_closure_approval=false" in text
    assert "certification_packet_consistency.writes_governance_records=false" in text
    assert "certification_packet_consistency.verification_commands_rerun_captured=false" in text
    assert "certification_packet_consistency.certification_effect=none" in text
    assert "generated_artifact_freshness_scope.artifact_count=2" in text
    assert "generated_artifact_freshness_scope.valid_artifact_count=2" in text
    assert "generated_artifact_freshness_scope.stale_or_missing_artifact_count=0" in text
    assert "generated_artifact_freshness_scope.freshness_check_effect=none" in text
    assert "generated_artifact_freshness_scope.captures_business_owner_approval=false" in text
    assert "generated_artifact_freshness_scope.captures_product_or_api_decisions=false" in text
    assert "generated_artifact_freshness_scope.captures_golden_sample_approval=false" in text
    assert "generated_artifact_freshness_scope.captures_closure_approval=false" in text
    assert "generated_artifact_freshness_scope.writes_governance_records=false" in text
    assert "generated_artifact_freshness_scope.certification_effect=none" in text
    assert "freshness scope proves generated packet alignment only" in text
    assert "consistency receipt does not certify the route" in text
    assert "business_contract_certified_count=0" in text
    assert "golden_boundary_status=approved" in text
    assert "golden_artifact_status=captured-awaiting-approval" in text
    assert "golden_artifact_approved=false" in text
    assert "board boundary pass is not golden approval" in text


def test_product_category_certification_board_surfaces_generated_artifact_freshness_scope() -> None:
    text = CERTIFICATION_BOARD.read_text(encoding="utf-8")

    assert "Generated artifact freshness scope now visible on this board" in text
    assert "generated_artifact_freshness_scope.artifact_count=2" in text
    assert "generated_artifact_freshness_scope.valid_artifact_count=2" in text
    assert "generated_artifact_freshness_scope.stale_or_missing_artifact_count=0" in text
    assert "generated_artifact_freshness_scope.freshness_check_effect=none" in text
    assert "generated_artifact_freshness_scope.captures_business_owner_approval=false" in text
    assert "generated_artifact_freshness_scope.captures_product_or_api_decisions=false" in text
    assert "generated_artifact_freshness_scope.captures_golden_sample_approval=false" in text
    assert "generated_artifact_freshness_scope.captures_closure_approval=false" in text
    assert "generated_artifact_freshness_scope.writes_governance_records=false" in text
    assert "generated_artifact_freshness_scope.certification_effect=none" in text
    assert "freshness scope proves generated packet alignment only" in text
    assert "does not approve the page, capture approval, or certify the route" in text
    assert "## Owner Decision Packet Bridge Scope" in text
    assert "owner_decision_packet_bridge.formal_decision_item_count=5" in text
    assert "owner_decision_packet_bridge.next_review_queue_item_count=4" in text
    assert "owner_decision_packet_bridge.counts_next_review_as_decision=false" in text
    assert "owner_decision_packet_bridge.captures_product_or_api_decisions=false" in text
    assert "owner_decision_packet_bridge.captures_golden_sample_approval=false" in text
    assert "owner_decision_packet_bridge.captures_closure_approval=false" in text
    assert "owner_decision_packet_bridge.certification_effect=none" in text
    assert "owner-decision bridge is reviewer intake only" in text
    assert "business_contract_certified_count=0" in text


def test_product_category_approval_runbook_surfaces_packet_consistency_non_approval_boundary() -> None:
    text = APPROVAL_RUNBOOK.read_text(encoding="utf-8")

    assert "golden_boundary_status=approved" in text
    assert "golden_artifact_status=captured-awaiting-approval" in text
    assert "golden_artifact_approved=false" in text
    assert "golden_sample_approval_artifact_mismatch=true" in text
    assert "boundary pass is not golden approval" in text
    assert "certification_packet_consistency.status=valid" in text
    assert "certification_packet_consistency.missing_marker_count=0" in text
    assert "certification_packet_consistency.approval_action_item_count=15" in text
    assert "certification_packet_consistency.business_owner_action_signoff_item_count=15" in text
    assert "certification_packet_consistency.business_owner_action_signed_item_count=0" in text
    assert (
        "certification_packet_consistency.business_owner_action_pending_or_missing_item_count=15"
        in text
    )
    assert "business_owner_action_signoff_group_counts.owner_identity=2" in text
    assert "business_owner_action_signoff_group_counts.owner_decision=3" in text
    assert "business_owner_action_signoff_group_counts.evidence_review=7" in text
    assert "business_owner_action_signoff_group_counts.pre_signature_verification=2" in text
    assert "business_owner_action_signoff_group_counts.boundary_acceptance=1" in text
    assert "business_owner_action_signed_group_counts.none=0" in text
    assert "business_owner_action_pending_group_counts.evidence_review=7" in text
    assert "business_owner_action_missing_or_invalid_item_count=5" in text
    assert "business_owner_action_pending_review_item_count=10" in text
    assert "certification_packet_consistency.owner_signable=false" in text
    assert "certification_packet_consistency.can_promote_certification=false" in text
    assert "certification_packet_consistency.approves_metric_or_page=false" in text
    assert "certification_packet_consistency.captures_business_owner_approval=false" in text
    assert "certification_packet_consistency.captures_business_owner_signature=false" in text
    assert "certification_packet_consistency.captures_product_or_api_decisions=false" in text
    assert "certification_packet_consistency.captures_golden_sample_approval=false" in text
    assert "certification_packet_consistency.captures_closure_approval=false" in text
    assert "certification_packet_consistency.writes_governance_records=false" in text
    assert "certification_packet_consistency.verification_commands_rerun_captured=false" in text
    assert "certification_packet_consistency.certification_effect=none" in text
    assert "## Generated Artifact Freshness Scope" in text
    assert "generated_artifact_freshness_scope.artifact_count=2" in text
    assert "generated_artifact_freshness_scope.valid_artifact_count=2" in text
    assert "generated_artifact_freshness_scope.stale_or_missing_artifact_count=0" in text
    assert "generated_artifact_freshness_scope.freshness_check_effect=none" in text
    assert "generated_artifact_freshness_scope.captures_business_owner_approval=false" in text
    assert "generated_artifact_freshness_scope.captures_product_or_api_decisions=false" in text
    assert "generated_artifact_freshness_scope.captures_golden_sample_approval=false" in text
    assert "generated_artifact_freshness_scope.captures_closure_approval=false" in text
    assert "generated_artifact_freshness_scope.writes_governance_records=false" in text
    assert "generated_artifact_freshness_scope.certification_effect=none" in text
    assert "freshness scope proves generated packet alignment only" in text
    assert "does not approve the page, capture approval, or certify the route" in text
    assert "business_contract_certified_count=0" in text
    assert "| `- Owner decision next-review queue acknowledged` | `yes` |" in text
    assert (
        "next-review queue topics are intake follow-ups and do not count as captured decisions"
        in text
    )


def test_product_category_approval_runbook_surfaces_pre_approval_command_receipt_boundary() -> None:
    text = APPROVAL_RUNBOOK.read_text(encoding="utf-8")

    assert "pre_approval_command_receipt.status=pending_rerun" in text
    assert "pre_approval_command_receipt.required_command_count=5" in text
    assert "python scripts/product_category_pnl_first_certification_packet.py" in text
    assert "python scripts/product_category_pnl_owner_decision_packet.py" in text
    assert "python scripts/check_product_category_pnl_business_owner_approval.py" in text
    assert (
        "powershell -NoProfile -ExecutionPolicy Bypass -File "
        "scripts\\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive"
        in text
    )
    assert "python scripts/codex_page_readiness.py --page-slug product-category-pnl" not in text
    assert "python scripts/check_product_category_pnl_business_owner_approval.py --require-captured" in text
    assert "pre_approval_command_receipt.strict_negative_control_expected_exit=non_zero" in text
    assert "pre_approval_command_receipt.business_owner_approval_captured=false" in text
    assert "pre_approval_command_receipt.certification_effect=none" in text


def test_product_category_approval_runbook_surfaces_owner_action_status_scope() -> None:
    text = APPROVAL_RUNBOOK.read_text(encoding="utf-8")

    assert "## Owner Action Status Scope" in text
    assert "Scope kind: `owner_action_status_scope`" in text
    assert "`missing_or_invalid_item_count=5`" in text
    assert "`pending_review_item_count=10`" in text
    assert "`captures_business_owner_approval=false`" in text
    assert "`captures_product_or_api_decisions=false`" in text
    assert "`can_promote_certification=false`" in text
    assert "`certification_effect=none`" in text
    assert "## Owner Pre-Signature Blocker Scope" in text
    assert "Scope kind: `owner_pre_signature_blocker_scope`" in text
    assert "`remaining_blocker_count=16`" in text
    assert "`approval_action_item_count=15`" in text
    assert "`signed_item_count=0`" in text
    assert "`unsigned_item_count=15`" in text
    assert "`missing_or_invalid_item_count=5`" in text
    assert "`pending_review_item_count=10`" in text
    assert "`captures_product_or_api_decisions=false`" in text
    assert "`certification_effect=none`" in text
    assert "owner_decision_next_review_queue_acknowledgement" in text
    assert "does not approve, sign, certify, or capture product/API decisions" in text
    assert "must continue to fail until real owner approval is captured" in text


def test_product_category_historical_scorecard_and_roadmap_defer_to_current_board() -> None:
    for path in [INSTITUTIONAL_FRONTEND_SCORECARD, FRONTEND_CERTIFICATION_ROADMAP]:
        text = path.read_text(encoding="utf-8")
        assert "Historical snapshot" in text
        assert "2026-06-06-top-investment-bank-certification-board.md" in text
        assert "approval_action_item_count=15" in text
        assert "closure_blocker_triage.blocker_count=15" in text
        assert "next_review_queue_item_count=4" in text

    scorecard_text = INSTITUTIONAL_FRONTEND_SCORECARD.read_text(encoding="utf-8")
    assert "and 14 action items" not in scorecard_text
    assert "with 14 action items" not in scorecard_text
    assert "current board reports 15 action items" in scorecard_text


def test_product_category_deep_audit_queue_records_current_count_drift_guard() -> None:
    text = DEEP_AUDIT_GOAL_QUEUE.read_text(encoding="utf-8")

    assert "| G10d | Guard historical product-category count snapshots" in text
    assert "## Completed Child Goal: G10d" in text
    assert "approval_action_item_count=15" in text
    assert "closure_blocker_triage.blocker_count=15" in text
    assert "next_review_queue_item_count=4" in text
    assert "captures no approval, signature, product/API decision, or certification" in text


def test_product_category_deep_audit_queue_g9_and_g10_records_are_contiguous() -> None:
    text = DEEP_AUDIT_GOAL_QUEUE.read_text(encoding="utf-8")
    lane_start = "G9a"
    lane_end = "G12u"
    table_ids = [
        goal_id
        for goal_id in re.findall(r"^\| (G\d+[a-z]) \|", text, flags=re.MULTILINE)
        if _lettered_goal_key(lane_start) <= _lettered_goal_key(goal_id) <= _lettered_goal_key(lane_end)
    ]
    completed_ids = [
        goal_id
        for goal_id in re.findall(
            r"^## Completed Child Goal: (G\d+[a-z])$",
            text,
            flags=re.MULTILINE,
        )
        if _lettered_goal_key(lane_start) <= _lettered_goal_key(goal_id) <= _lettered_goal_key(lane_end)
    ]
    expected_ids = _lettered_goal_ids_between(lane_start, lane_end)
    latest_checkpoints = _latest_verification_checkpoint_section(text)

    assert table_ids == expected_ids
    assert completed_ids == expected_ids
    assert "| G10g | Guard G9/G10 goal-queue ledger sync" in text
    assert "## Completed Child Goal: G10g" in text
    assert "| G10k | Surface signoff matrix distribution on current owner-review docs" in text
    assert "## Completed Child Goal: G10k" in text
    assert "| G10l | Surface next-review queue acknowledgement in approval runbook" in text
    assert "## Completed Child Goal: G10l" in text
    assert "| G10m | Surface signoff distribution in owner closure gate matrix" in text
    assert "## Completed Child Goal: G10m" in text
    assert "| G10n | Align first-certification pre-signature command receipt" in text
    assert "## Completed Child Goal: G10n" in text
    assert "| G10o | Surface signoff distribution in readiness outputs" in text
    assert "## Completed Child Goal: G10o" in text
    assert "| G10p | Expose signoff-matrix approval-capture boundary in CLI payload" in text
    assert "## Completed Child Goal: G10p" in text
    assert "| G10q | Align approval runbook pre-approval readiness command" in text
    assert "## Completed Child Goal: G10q" in text
    assert "| G10r | Surface pending next-review queue acknowledgement on certification board" in text
    assert "## Completed Child Goal: G10r" in text
    assert "| G10s | Expose formal-use versus closure block in signoff summary" in text
    assert "## Completed Child Goal: G10s" in text
    assert "| G10t | Expose live readiness gate evidence in first-certification CLI payload" in text
    assert "## Completed Child Goal: G10t" in text
    assert "| G10u | Show golden approval artifact status in product-category readiness gate" in text
    assert "## Completed Child Goal: G10u" in text
    assert "| G10v | Split golden boundary status from artifact approval in PowerShell readiness summary" in text
    assert "## Completed Child Goal: G10v" in text
    assert "| G10w | Expose owner-reviewer receipt approval-capture boundary in CLI payload" in text
    assert "## Completed Child Goal: G10w" in text
    assert "| G10x | Split golden boundary status from artifact approval in route-scope JSON" in text
    assert "## Completed Child Goal: G10x" in text
    assert "| G10y | Expose pre-signature rerun non-approval boundary in CLI payload" in text
    assert "## Completed Child Goal: G10y" in text
    assert "| G10z | Expose golden artifact boundary in first-certification readiness evidence" in text
    assert "## Completed Child Goal: G10z" in text
    assert "| G11a | Expose owner-readiness receipt approval-capture boundary in CLI payload" in text
    assert "## Completed Child Goal: G11a" in text
    assert "| G11b | Split golden boundary status from artifact approval in approval runbook" in text
    assert "## Completed Child Goal: G11b" in text
    assert "| G11c | Split golden boundary status from artifact approval on certification board" in text
    assert "## Completed Child Goal: G11c" in text
    assert "| G11d | Surface golden artifact mismatch in PowerShell all-page summary" in text
    assert "## Completed Child Goal: G11d" in text
    assert "| G11e | Expose owner-decision CLI non-decision boundaries" in text
    assert "## Completed Child Goal: G11e" in text
    assert "| G11f | Surface golden boundary split in all-page pending approval JSON" in text
    assert "## Completed Child Goal: G11f" in text
    assert "| G11g | Expose owner-readiness Markdown approval-capture boundary" in text
    assert "## Completed Child Goal: G11g" in text
    assert "| G11h | Expose owner action signoff group distribution in machine and owner-review docs" in text
    assert "## Completed Child Goal: G11h" in text
    assert "| G11i | Expose signed and pending signoff group split in first-certification Markdown" in text
    assert "## Completed Child Goal: G11i" in text
    assert "| G11j | Guard approval-checker signoff group coverage across blocker false paths" in text
    assert "## Completed Child Goal: G11j" in text
    assert "| G11k | Expose owner action status split in owner-review docs and packet" in text
    assert "## Completed Child Goal: G11k" in text
    assert "| G11l | Surface owner action status split in readiness JSON outputs" in text
    assert "## Completed Child Goal: G11l" in text
    assert "| G11m | Surface owner action status split in readiness summary outputs" in text
    assert "## Completed Child Goal: G11m" in text
    assert "| G11n | Guard historical product-category scorecard action-count wording" in text
    assert "## Completed Child Goal: G11n" in text
    assert "| G11o | Surface owner action status split in route-scope summary JSON" in text
    assert "## Completed Child Goal: G11o" in text
    assert "| G11p | Suppress lower-level owner-action status labels in PowerShell readiness output" in text
    assert "## Completed Child Goal: G11p" in text
    assert "| G11q | Surface owner action status aliases in approval-checker signoff summary JSON" in text
    assert "## Completed Child Goal: G11q" in text
    assert "| G11r | Add PowerShell route-scope classification summary" in text
    assert "## Completed Child Goal: G11r" in text
    assert "| G11s | Backfill early deep-audit completed-child records" in text
    assert "## Completed Child Goal: G11s" in text
    assert "| G11t | Surface owner-action status split and product/API non-decision scope in approval checker payload" in text
    assert "## Completed Child Goal: G11t" in text
    assert "| G11u | Regenerate first-certification consistency split Markdown" in text
    assert "## Completed Child Goal: G11u" in text
    assert "| G11v | Surface owner-action status scope in first-certification packet" in text
    assert "## Completed Child Goal: G11v" in text
    assert "| G11w | Surface owner-action status scope in approval runbook" in text
    assert "## Completed Child Goal: G11w" in text
    assert "| G11x | Prefer canonical owner-action status aliases in readiness readers" in text
    assert "## Completed Child Goal: G11x" in text
    assert "| G11y | Expose certification effect in approval-checker evidence scope" in text
    assert "## Completed Child Goal: G11y" in text
    assert "| G11z | Surface approval-checker evidence scope in route-scope JSON" in text
    assert "## Completed Child Goal: G11z" in text
    assert "| G12a | Expose non-approval certification consistency scope in packet consistency object" in text
    assert "## Completed Child Goal: G12a" in text
    assert "| G12b | Surface certification consistency no-effect fields in route-scope readiness outputs" in text
    assert "## Completed Child Goal: G12b" in text
    assert "| G12c | Expose owner pre-signature blocker scope/checklist" in text
    assert "## Completed Child Goal: G12c" in text
    assert "| G12d | Surface certification consistency no-effect fields in PowerShell readiness summaries" in text
    assert "## Completed Child Goal: G12d" in text
    assert "| G12e | Align pre-signature acknowledgement signoff group with evidence-review boundary" in text
    assert "## Completed Child Goal: G12e" in text
    assert "| G12f | Surface certification consistency no-effect fields in approval runbook" in text
    assert "## Completed Child Goal: G12f" in text
    assert "| G12g | Surface owner pre-signature blocker scope in PowerShell readiness summaries" in text
    assert "## Completed Child Goal: G12g" in text
    assert "| G12h | Surface certification consistency no-effect fields on certification board" in text
    assert "## Completed Child Goal: G12h" in text
    assert "| G12i | Surface owner pre-signature blocker scope in approval-required failure summaries" in text
    assert "## Completed Child Goal: G12i" in text
    assert "| G12j | Surface generated-artifact freshness no-effect scope in first-certification packet" in text
    assert "## Completed Child Goal: G12j" in text
    assert "| G12k | Surface generated-artifact freshness no-effect scope in approval-checker payload" in text
    assert "## Completed Child Goal: G12k" in text
    assert "| G12l | Surface owner-decision packet no-effect evidence scope" in text
    assert "## Completed Child Goal: G12l" in text
    assert "| G12m | Surface generated-artifact freshness no-effect scope in readiness JSON outputs" in text
    assert "## Completed Child Goal: G12m" in text
    assert "| G12n | Preserve approval/readiness false-path evidence distinctions" in text
    assert "## Completed Child Goal: G12n" in text
    assert "| G12o | Surface generated-artifact freshness no-effect scope in PowerShell readiness summaries" in text
    assert "## Completed Child Goal: G12o" in text
    assert "| G12p | Surface generated-artifact freshness no-effect scope in PowerShell route-scope rows" in text
    assert "## Completed Child Goal: G12p" in text
    assert "| G12q | Surface generated-artifact freshness no-effect scope in approval runbook" in text
    assert "## Completed Child Goal: G12q" in text
    assert "| G12r | Surface generated-artifact freshness no-effect scope on certification board" in text
    assert "## Completed Child Goal: G12r" in text
    assert "| G12s | Bridge owner-decision packet no-effect scope into first-certification packet" in text
    assert "## Completed Child Goal: G12s" in text
    assert "| G12t | Surface owner-decision bridge no-effect scope on certification board" in text
    assert "## Completed Child Goal: G12t" in text
    assert (
        "| G12u | Align `/product-category-pnl` closure checklist next-unit guidance with active 3C metrics"
        in text
    )
    assert "## Completed Child Goal: G12u" in text
    assert "G12u aligned the `/product-category-pnl` closure checklist recommended next unit" in latest_checkpoints
    assert "G12n preserved approval/readiness false-path evidence distinctions" in latest_checkpoints
    assert latest_checkpoints.index("G12u aligned") < latest_checkpoints.index("G12t surfaced")
    assert latest_checkpoints.index("G12n preserved") < latest_checkpoints.index("G12r surfaced")
    assert latest_checkpoints.index("G12t surfaced") < latest_checkpoints.index("G12n preserved")
    assert latest_checkpoints.index("G12r surfaced") < latest_checkpoints.index("G12s bridged")
    assert latest_checkpoints.index("G12s bridged") < latest_checkpoints.index("G12p surfaced")
    assert latest_checkpoints.index("G12r surfaced") < latest_checkpoints.index("G12p surfaced")
    assert latest_checkpoints.index("G12p surfaced") < latest_checkpoints.index("G12o surfaced")
    assert latest_checkpoints.index("G12o surfaced") < latest_checkpoints.index("G12q surfaced")
    assert (
        "captures no approval, signature, product/API decision, golden approval, "
        "closure approval, governance write, or certification"
        in text
    )


def test_product_category_pnl_business_owner_approval_checker_reports_pending_template() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE))

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)

    assert payload["page_id"] == "PAGE-PROD-CAT-001"
    assert payload["page_slug"] == "product-category-pnl"
    assert payload["primary_api"] == "/ui/pnl/product-category"
    assert payload["approval_check"] == "business_owner_approval"
    assert payload["approval_status"] == "pending"
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
    assert payload["closure_approved"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "business_owner_name",
        "business_owner_role",
        "approval_decision",
        "approval_date",
        "business_owner_signature",
        "governance_record_review",
        "reviewed_owner_decision_packet",
        "owner_decision_next_review_queue_acknowledgement",
        "golden_sample_artifact_reconciliation",
        "closure_checklist_review",
        "fallback_liability_branch_boundary_review",
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "verification_commands_rerun",
        "evidence_pending_boundary_acceptance",
    ]
    assert payload["approval_field_status"]["business_owner_name"] == "missing"
    assert payload["approval_field_status"]["reviewed_boundary_packet"] == "valid"
    assert payload["approval_field_status"]["reviewed_first_certification_packet"] == "valid"
    assert payload["approval_field_status"]["reviewed_owner_decision_packet"] == "pending"
    assert payload["approval_field_status"]["owner_decision_next_review_queue_acknowledgement"] == "pending"
    assert payload["approval_field_status"]["golden_sample_artifact_reconciliation"] == "pending"
    assert payload["approval_field_status"]["fallback_liability_branch_boundary_review"] == "pending"
    assert payload["approval_field_status"]["formal_use_allowed"] == "valid"
    assert payload["approval_field_status"]["closure_approved"] == "valid"
    assert payload["generated_artifact_freshness"] == {
        "first_certification_packet": {
            "artifact_path": "docs/pnl/product-category-pnl-first-certification-packet.md",
            "exists": True,
            "freshness_status": "valid",
            "missing_markers": [],
        },
        "owner_decision_packet": {
            "artifact_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
            "exists": True,
            "freshness_status": "valid",
            "missing_markers": [],
        },
    }
    assert payload["generated_artifact_freshness_scope"] == {
        "scope_kind": "generated_artifact_freshness_scope",
        "artifact_count": 2,
        "valid_artifact_count": 2,
        "stale_or_missing_artifact_count": 0,
        "freshness_check_effect": "none",
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "writes_governance_records": False,
        "certification_effect": "none",
        "boundary": (
            "Generated artifact freshness proves only that script-owned packet outputs match expected "
            "freshness markers; it does not approve, sign, certify, write governance records, or capture decisions."
        ),
    }
    assert payload["certification_packet_consistency"] == {
        "consistency_kind": "product_category_pnl_certification_packet_consistency",
        "status": "valid",
        "missing_markers": [],
        "template_path": "docs/pnl/product-category-pnl-business-owner-approval-template.md",
        "first_certification_packet_path": "docs/pnl/product-category-pnl-first-certification-packet.md",
        "owner_decision_packet_path": "docs/pnl/product-category-pnl-owner-decision-packet.md",
        "formal_decision_item_count": 5,
        "next_review_queue_item_count": 4,
        "approval_action_item_count": 15,
        "business_owner_action_signoff_item_count": 15,
        "business_owner_action_signed_item_count": 0,
        "business_owner_action_pending_or_missing_item_count": 15,
        "business_owner_action_missing_or_invalid_item_count": 5,
        "business_owner_action_pending_review_item_count": 10,
        "approves_metric_or_page": False,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "captures_business_owner_signature": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "writes_governance_records": False,
        "can_promote_certification": False,
        "verification_commands_rerun_captured": False,
        "certification_effect": "none",
        "boundary": (
            "Consistency only proves packet/template counts and non-approval boundaries align; "
            "it captures no approval, signature, product/API decision, golden approval, "
            "closure approval, governance write, or certification."
        ),
    }
    assert payload["approval_action_item_count"] == 15
    assert payload["business_owner_action_signoff_summary"] == {
        "summary_kind": "business_owner_action_signoff_summary",
        "action_item_count": 15,
        "signed_item_count": 0,
        "unsigned_item_count": 15,
        "invalid_or_missing_item_count": 5,
        "pending_item_count": 10,
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "signoff_group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "signed_group_counts": {},
        "unsigned_group_counts": {
            "boundary_acceptance": 1,
            "evidence_review": 7,
            "owner_decision": 3,
            "owner_identity": 2,
            "pre_signature_verification": 2,
        },
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "formal_use_allowed": True,
        "closure_approved": False,
        "certification_blocked": True,
        "boundary": (
            "Approval checker signoff summary is evidence only; only current_status=valid "
            "counts as signed, unsigned items still block business-owner approval capture, "
            "and formal_use_allowed=true does not bypass closure_approved=false."
        ),
    }
    assert payload["owner_action_status_scope"] == {
        "scope_kind": "owner_action_status_scope",
        "missing_or_invalid_item_count": 5,
        "pending_review_item_count": 10,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "can_promote_certification": False,
        "certification_effect": "none",
        "boundary": (
            "Owner-action status split is approval-checker evidence only; it does not "
            "capture business-owner approval, product/API decisions, or route certification."
        ),
    }
    pre_signature_scope = payload["owner_pre_signature_blocker_scope"]
    assert pre_signature_scope["scope_kind"] == "owner_pre_signature_blocker_scope"
    assert pre_signature_scope["remaining_blocker_count"] == 16
    assert pre_signature_scope["remaining_blockers"] == payload["remaining_blockers"]
    assert pre_signature_scope["approval_action_item_count"] == 15
    assert pre_signature_scope["approval_action_blockers"] == [
        item["blocker"] for item in payload["approval_action_items"]
    ]
    assert pre_signature_scope["signed_item_count"] == 0
    assert pre_signature_scope["unsigned_item_count"] == 15
    assert pre_signature_scope["missing_or_invalid_item_count"] == 5
    assert pre_signature_scope["pending_review_item_count"] == 10
    assert pre_signature_scope["signoff_group_counts"] == {
        "boundary_acceptance": 1,
        "evidence_review": 7,
        "owner_decision": 3,
        "owner_identity": 2,
        "pre_signature_verification": 2,
    }
    assert pre_signature_scope["signed_group_counts"] == {}
    assert pre_signature_scope["unsigned_group_counts"] == {
        "boundary_acceptance": 1,
        "evidence_review": 7,
        "owner_decision": 3,
        "owner_identity": 2,
        "pre_signature_verification": 2,
    }
    assert len(pre_signature_scope["checklist_items"]) == 15
    assert pre_signature_scope["checklist_items"][0] == {
        "blocker": "business_owner_name",
        "signoff_group": "owner_identity",
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
        "current_status": "missing",
        "blocks_owner_signature": True,
        "certification_effect": "none",
    }
    assert {
        "blocker": "owner_decision_next_review_queue_acknowledgement",
        "signoff_group": "evidence_review",
        "template_field": "- Owner decision next-review queue acknowledged",
        "required_value": "yes",
        "current_status": "pending",
        "blocks_owner_signature": True,
        "certification_effect": "none",
    } in pre_signature_scope["checklist_items"]
    assert pre_signature_scope["owner_signable"] is False
    assert pre_signature_scope["captures_business_owner_approval"] is False
    assert pre_signature_scope["captures_product_or_api_decisions"] is False
    assert pre_signature_scope["can_promote_certification"] is False
    assert pre_signature_scope["certification_effect"] == "none"
    assert pre_signature_scope["boundary"] == (
        "Owner pre-signature blocker scope is a checklist boundary only; it does not "
        "approve, sign, certify, or capture product/API decisions."
    )
    assert {
        "blocker": "reviewed_owner_decision_packet",
        "template_field": "- Owner decision packet reviewed",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert {
        "blocker": "owner_decision_next_review_queue_acknowledgement",
        "template_field": "- Owner decision next-review queue acknowledged",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert {
        "blocker": "golden_sample_artifact_reconciliation",
        "template_field": "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert {
        "blocker": "fallback_liability_branch_boundary_review",
        "template_field": "- Fallback liability branch model-boundary evidence reviewed",
        "required_value": "yes",
        "current_status": "pending",
    } in payload["approval_action_items"]
    assert payload["approval_action_items"][-1] == {
        "blocker": "evidence_pending_boundary_acceptance",
        "template_field": "- Evidence-pending boundary accepted",
        "required_value": "yes",
        "current_status": "pending",
    }
    assert payload["closure_blocker_triage"]["artifact_path"] == (
        "docs/pnl/product-category-remaining-blockers.md"
    )
    assert payload["closure_blocker_triage"]["blocker_count"] == 15
    assert payload["closure_blocker_triage"]["class_counts"] == {
        "1": 3,
        "2": 2,
        "3": 0,
        "4": 9,
        "5": 1,
    }
    assert payload["closure_blocker_triage"]["cursor_safe_counts"] == {
        "yes": 1,
        "no": 5,
        "partially": 0,
        "partially_complete": 9,
    }
    assert payload["closure_blocker_triage"]["decision_required_count"] == 3
    assert payload["closure_blocker_triage"]["api_contract_required_count"] == 2
    assert payload["closure_blocker_triage"]["out_of_scope_count"] == 1
    assert payload["closure_blocker_triage"]["machine_readable"] is True
    assert payload["closure_blocker_triage"]["blockers"][0] == {
        "unit": "2",
        "blocker": "exhaustive detail semantics beyond active 3C metrics are not fully page-frozen",
        "class": "4",
        "minimal_next_action": (
            "Active `MTR-PCP-004`~`MTR-PCP-012` field semantics are now model/page/golden-backed; "
            "expand only after a new governed metric matrix"
        ),
        "cursor_safe": "partially_complete",
        "suggested_scope": (
            "`productCategoryPnlPageModel.test.ts`, `ProductCategoryPnlPage.test.tsx`, "
            "`GS-PROD-CAT-PNL-A/`"
        ),
    }
    assert payload["closure_blocker_triage"]["blockers"][5] == {
        "unit": "5",
        "blocker": "broader stale/failure matrix (partial degradation, export vs list under error)",
        "class": "4",
        "minimal_next_action": (
            "Audit list/timeline failures, export-failure/list-retention behavior, and main-page "
            "adjustment-summary refetch failure are now page-frozen; partial-degradation copy remains open"
        ),
        "cursor_safe": "partially_complete",
        "suggested_scope": "Audit + main page tests, checklist",
    }
    assert all(
        blocker["blocker"] != "no confirmation modal for destructive revoke"
        for blocker in payload["closure_blocker_triage"]["blockers"]
    )
    assert payload["closure_blocker_triage"]["blockers"][12] == {
        "unit": "10",
        "blocker": "scenario is companion probe, not second full golden matrix sample",
        "class": "4",
        "minimal_next_action": (
            "Scenario promotion gate is now documented; create a separate scenario sample pack only after "
            "non-placeholder scenario approval and metric-matrix evidence exist"
        ),
        "cursor_safe": "partially_complete",
        "suggested_scope": "`tests/golden_samples/`, `product-category-golden-sample-a.md`",
    }
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "certification_effect": "none",
    }


def test_product_category_pnl_approval_template_states_current_owner_decision_counts() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    owner_packet = build_owner_decision_packet()
    formal_decision_count = owner_packet["decision_item_count"]
    next_review_queue_count = owner_packet["next_review_queue_scope"]["item_count"]

    assert "3 product decisions and 2 API/contract blockers" in text
    assert formal_decision_count == 5
    assert next_review_queue_count == 4
    assert (
        f"{formal_decision_count} formal decision items plus "
        f"{next_review_queue_count} next-review queue topics"
    ) in text
    assert "5 formal decision items plus 5 next-review queue topics" not in text
    assert "Owner decision next-review queue acknowledged" in text
    assert "four product decisions" not in text
    assert "4 product decisions" not in text
    assert "Owner Readiness Receipt" in text
    assert "Business Owner Action Signoff Matrix" in text
    assert "Pre-Signature Verification Rerun Receipt" in text
    assert "owner_signable=false" in text
    assert "can_promote_certification=false" in text
    assert "packet_generator_reruns_gate=false" in text
    assert "verification_commands_rerun_captured=false" in text
    assert (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex-page-readiness.ps1 "
        "-PageSlug product-category-pnl -Run -CheckLive"
    ) in text
    assert "does not bypass golden approval, manual checklist closure, owner decisions, or strict checker failure" in text


def test_product_category_pnl_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    completed = _run_checker("--template-path", str(TEMPLATE), "--require-captured")

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_product_category_pnl_business_owner_approval_checker_require_captured_allows_complete_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)

    completed = _run_checker(
        "--template-path",
        str(template),
        "--golden-sample-approval-path",
        str(golden_artifact),
        "--closure-checklist-path",
        str(closure_checklist),
        "--require-captured",
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_action_items"] == []
    assert payload["approval_action_item_count"] == 0
    assert payload["golden_sample_approval_artifact"]["approved"] is True
    assert payload["closure_checklist_artifact"]["ready_for_owner_approval"] is True
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["proves_page_execution"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"


def test_product_category_pnl_business_owner_approval_checker_blocks_when_closure_checklist_has_partial_units(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)

    completed = _run_checker(
        "--template-path",
        str(template),
        "--golden-sample-approval-path",
        str(golden_artifact),
        "--require-captured",
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert payload["business_owner_approval_captured"] is False
    assert "closure_checklist_review" in payload["remaining_blockers"]
    assert payload["approval_field_status"]["closure_checklist_review"] == "artifact_partial"
    assert payload["closure_checklist_artifact"]["ready_for_owner_approval"] is False
    assert payload["closure_checklist_artifact"]["unit_count"] == 10
    assert payload["closure_checklist_artifact"]["partial_count"] == 10
    assert payload["closure_checklist_artifact"]["open_unit_count"] == 10
    assert payload["closure_checklist_artifact"]["open_units"][0] == {
        "unit": "1. Dates",
        "status": "PARTIAL",
    }


def test_product_category_pnl_business_owner_approval_checker_blocks_when_golden_sample_artifact_is_not_approved(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    completed = _run_checker("--template-path", str(template), "--require-captured")
    payload = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert payload["business_owner_approval_captured"] is False
    assert "golden_sample_artifact_reconciliation" in payload["remaining_blockers"]
    assert payload["approval_field_status"]["golden_sample_artifact_reconciliation"] == "artifact_pending"
    assert payload["golden_sample_approval_artifact"] == {
        "sample_id": "GS-PROD-CAT-PNL-A",
        "status": "captured-awaiting-approval",
        "owner": "TBD",
        "approver": "TBD",
        "approved_at": "TBD",
        "artifact_path": "tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md",
        "approved": False,
    }


def test_product_category_pnl_business_owner_approval_checker_rejects_non_approve_decision(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(decision="request_changes"), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)

    completed = _run_checker(
        "--template-path",
        str(template),
        "--golden-sample-approval-path",
        str(golden_artifact),
        "--closure-checklist-path",
        str(closure_checklist),
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_decision", "decision_notes"]
    assert payload["approval_field_status"]["approval_decision"] == "invalid"
    assert payload["approval_field_status"]["decision_notes"] == "missing"


def test_product_category_pnl_business_owner_approval_checker_rejects_bad_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(approval_date="06/05/2026"), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)

    completed = _run_checker(
        "--template-path",
        str(template),
        "--golden-sample-approval-path",
        str(golden_artifact),
        "--closure-checklist-path",
        str(closure_checklist),
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "approval_date"]


def test_product_category_pnl_business_owner_approval_checker_rejects_closure_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    template.write_text(
        _filled_template_text().replace(
            "Closure approved: `closure_approved=false`",
            "Closure approved: `closure_approved=true`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker(
        "--template-path",
        str(template),
        "--golden-sample-approval-path",
        str(golden_artifact),
        "--closure-checklist-path",
        str(closure_checklist),
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == ["business_owner_approval", "closure_promotion_boundary"]


def test_product_category_pnl_business_owner_approval_checker_rejects_missing_first_certification_packet(
    tmp_path: Path,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            "Reviewed first-certification packet: `<required>`",
        ),
        encoding="utf-8",
    )

    completed = _run_checker(
        "--template-path",
        str(template),
        "--golden-sample-approval-path",
        str(golden_artifact),
        "--closure-checklist-path",
        str(closure_checklist),
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_first_certification_packet",
    ]


def test_product_category_pnl_business_owner_approval_checker_blocks_when_reviewed_first_certification_packet_file_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing_packet = "docs/pnl/missing-product-category-first-certification-packet.md"
    template = tmp_path / "product-category-approval-template.md"
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{missing_packet}`",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", missing_packet)

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_first_certification_packet",
    ]
    assert payload["approval_field_status"]["reviewed_first_certification_packet"] == "missing_artifact"


def test_product_category_pnl_business_owner_approval_checker_blocks_when_reviewed_owner_decision_packet_file_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    missing_packet = "docs/pnl/missing-product-category-owner-decision-packet.md"
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", missing_packet)

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_owner_decision_packet",
    ]
    assert payload["approval_field_status"]["reviewed_owner_decision_packet"] == "missing_artifact"


def test_product_category_pnl_business_owner_approval_checker_blocks_stale_first_certification_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stale_packet = tmp_path / "stale-first-certification-packet.md"
    stale_packet.write_text(
        "# Product-Category PnL First Certification Packet\n\nManual stale copy.\n",
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{stale_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(stale_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_first_certification_packet",
    ]
    assert payload["approval_field_status"]["reviewed_first_certification_packet"] == "stale_generated_artifact"


def test_product_category_pnl_business_owner_approval_checker_blocks_incomplete_first_certification_freshness_guard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stale_packet = tmp_path / "incomplete-first-certification-packet.md"
    stale_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=manual-copy`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{stale_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(stale_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_first_certification_packet",
    ]
    assert payload["approval_field_status"]["reviewed_first_certification_packet"] == "stale_generated_artifact"


def test_product_category_pnl_business_owner_approval_checker_blocks_first_certification_without_owner_reviewer_markers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_packet = tmp_path / "first-certification-without-owner-reviewer-markers.md"
    first_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
                "- `approval_action_item_count=15`",
                "- `business_owner_action_signoff_item_count=15`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "- `verification_commands_rerun_captured=false`",
                "- Review docs/pnl/product-category-pnl-owner-decision-packet.md for 5 formal decision items plus 4 next-review queue topics.",
                "",
                "## Business Owner Action Signoff Matrix",
                "",
                "- `signed_item_count=0`",
                "- `pending_or_missing_item_count=15`",
                "- `missing_or_invalid_item_count=5`",
                "- `pending_review_item_count=10`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
            ]
        ),
        encoding="utf-8",
    )
    owner_packet = tmp_path / "owner-decision-packet.md"
    owner_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifact=docs/pnl/product-category-remaining-blockers.md`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{first_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(first_packet))
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(owner_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_packet_consistency",
    ]
    assert payload["approval_field_status"]["reviewed_first_certification_packet"] == "valid"
    assert payload["certification_packet_consistency"]["status"] == "stale_generated_artifact"
    assert payload["certification_packet_consistency"]["missing_markers"] == [
        "first_certification_packet:owner_reviewer_receipt_item_count",
        "first_certification_packet:referenced_approval_field_count",
        "first_certification_packet:all_referenced_fields_known=true",
        "first_certification_packet:missing_approval_action_fields=none",
    ]


def test_product_category_pnl_business_owner_approval_checker_blocks_first_certification_with_incomplete_owner_reviewer_field_coverage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_packet = tmp_path / "first-certification-incomplete-owner-reviewer-coverage.md"
    first_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
                "- `approval_action_item_count=15`",
                "- `business_owner_action_signoff_item_count=15`",
                "- `owner_reviewer_receipt_item_count=9`",
                "- `referenced_approval_field_count=17`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "- `verification_commands_rerun_captured=false`",
                "- Review docs/pnl/product-category-pnl-owner-decision-packet.md for 5 formal decision items plus 4 next-review queue topics.",
                "",
                "## Business Owner Action Signoff Matrix",
                "",
                "- `signed_item_count=0`",
                "- `pending_or_missing_item_count=15`",
                "- `missing_or_invalid_item_count=5`",
                "- `pending_review_item_count=10`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "",
                "Missing approval action fields:",
                "",
                "- `unknown_owner_field`",
            ]
        ),
        encoding="utf-8",
    )
    owner_packet = tmp_path / "owner-decision-packet.md"
    owner_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifact=docs/pnl/product-category-remaining-blockers.md`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{first_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(first_packet))
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(owner_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_packet_consistency",
    ]
    assert payload["certification_packet_consistency"]["status"] == "stale_generated_artifact"
    assert payload["certification_packet_consistency"]["missing_markers"] == [
        "first_certification_packet:all_referenced_fields_known=true",
        "first_certification_packet:missing_approval_action_fields=none",
    ]


def test_product_category_pnl_business_owner_approval_checker_anchors_missing_approval_fields_none_marker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_packet = tmp_path / "first-certification-misplaced-none-marker.md"
    first_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
                "- `approval_action_item_count=15`",
                "- `business_owner_action_signoff_item_count=15`",
                "- `signed_item_count=0`",
                "- `pending_or_missing_item_count=15`",
                "- `owner_reviewer_receipt_item_count=9`",
                "- `referenced_approval_field_count=17`",
                "- `all_referenced_fields_known=true`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "- `verification_commands_rerun_captured=false`",
                "- Review docs/pnl/product-category-pnl-owner-decision-packet.md for 5 formal decision items plus 4 next-review queue topics.",
                "",
                "## Business Owner Action Signoff Matrix",
                "",
                "- `signed_item_count=0`",
                "- `pending_or_missing_item_count=15`",
                "- `missing_or_invalid_item_count=5`",
                "- `pending_review_item_count=10`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "",
                "Unrelated empty list:",
                "",
                "- `none`",
                "",
                "Missing approval action fields:",
                "",
                "- `unknown_owner_field`",
            ]
        ),
        encoding="utf-8",
    )
    owner_packet = tmp_path / "owner-decision-packet.md"
    owner_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifact=docs/pnl/product-category-remaining-blockers.md`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{first_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(first_packet))
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(owner_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_packet_consistency",
    ]
    assert payload["certification_packet_consistency"]["status"] == "stale_generated_artifact"
    assert payload["certification_packet_consistency"]["missing_markers"] == [
        "first_certification_packet:missing_approval_action_fields=none",
    ]


def test_product_category_pnl_business_owner_approval_checker_blocks_first_certification_with_false_signed_signoff_matrix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_packet = tmp_path / "first-certification-false-signed-signoff-matrix.md"
    first_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
                "- `approval_action_item_count=15`",
                "- `business_owner_action_signoff_item_count=15`",
                "- `owner_reviewer_receipt_item_count=9`",
                "- `referenced_approval_field_count=17`",
                "- `all_referenced_fields_known=true`",
                "- `signed_item_count=15`",
                "- `pending_or_missing_item_count=0`",
                "- `missing_or_invalid_item_count=0`",
                "- `pending_review_item_count=0`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "- `verification_commands_rerun_captured=false`",
                "- Review docs/pnl/product-category-pnl-owner-decision-packet.md for 5 formal decision items plus 4 next-review queue topics.",
                "",
                "## Business Owner Action Signoff Matrix",
                "",
                "- `signed_item_count=15`",
                "- `pending_or_missing_item_count=0`",
                "- `missing_or_invalid_item_count=0`",
                "- `pending_review_item_count=0`",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "",
                "Missing approval action fields:",
                "",
                "- `none`",
            ]
        ),
        encoding="utf-8",
    )
    owner_packet = tmp_path / "owner-decision-packet.md"
    owner_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifact=docs/pnl/product-category-remaining-blockers.md`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{first_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(first_packet))
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(owner_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_packet_consistency",
    ]
    assert payload["certification_packet_consistency"]["status"] == "stale_generated_artifact"
    assert payload["certification_packet_consistency"]["missing_markers"] == [
        "first_certification_packet:signed_item_count=0",
        "first_certification_packet:pending_or_missing_item_count=15",
    ]


def test_product_category_pnl_business_owner_approval_checker_blocks_signoff_matrix_owner_signable_true(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_packet = tmp_path / "first-certification-signoff-owner-signable-true.md"
    first_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL First Certification Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifacts=readiness_report, approval_template, closure_blocker_triage`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
                "- `approval_action_item_count=15`",
                "- `business_owner_action_signoff_item_count=15`",
                "- `owner_reviewer_receipt_item_count=9`",
                "- `referenced_approval_field_count=17`",
                "- `all_referenced_fields_known=true`",
                "- Review docs/pnl/product-category-pnl-owner-decision-packet.md for 5 formal decision items plus 4 next-review queue topics.",
                "",
                "## Owner Readiness Receipt",
                "",
                "- `owner_signable=false`",
                "- `captures_business_owner_approval=false`",
                "- `can_promote_certification=false`",
                "",
                "Missing approval action fields:",
                "",
                "- `none`",
                "",
                "## Business Owner Action Signoff Matrix",
                "",
                "- `signed_item_count=0`",
                "- `pending_or_missing_item_count=15`",
                "- `missing_or_invalid_item_count=5`",
                "- `pending_review_item_count=10`",
                "- `owner_signable=true`",
                "- `captures_business_owner_approval=true`",
                "- `can_promote_certification=true`",
                "",
                "## Pre-Signature Verification Rerun Receipt",
                "",
                "- `verification_commands_rerun_captured=false`",
            ]
        ),
        encoding="utf-8",
    )
    owner_packet = tmp_path / "owner-decision-packet.md"
    owner_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=script-owned`",
                "- `source_artifact=docs/pnl/product-category-remaining-blockers.md`",
                "- `formal_decision_item_count=5`",
                "- `next_review_queue_item_count=4`",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(
        _filled_template_text().replace(
            "Reviewed first-certification packet: `docs/pnl/product-category-pnl-first-certification-packet.md`",
            f"Reviewed first-certification packet: `{first_packet}`",
        ),
        encoding="utf-8",
    )
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_FIRST_CERTIFICATION_PACKET", str(first_packet))
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(owner_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "certification_packet_consistency",
    ]
    assert payload["certification_packet_consistency"]["status"] == "stale_generated_artifact"
    assert payload["certification_packet_consistency"]["missing_markers"] == [
        "first_certification_packet:business_owner_action_signoff_matrix:owner_signable=false",
        "first_certification_packet:business_owner_action_signoff_matrix:captures_business_owner_approval=false",
        "first_certification_packet:business_owner_action_signoff_matrix:can_promote_certification=false",
    ]


def test_product_category_pnl_business_owner_approval_checker_blocks_stale_owner_decision_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stale_packet = tmp_path / "stale-owner-decision-packet.md"
    stale_packet.write_text(
        "# Product-Category PnL Owner Decision Packet\n\nManual stale copy.\n",
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(stale_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_owner_decision_packet",
    ]
    assert payload["approval_field_status"]["reviewed_owner_decision_packet"] == "stale_generated_artifact"


def test_product_category_pnl_business_owner_approval_checker_blocks_incomplete_owner_decision_freshness_guard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stale_packet = tmp_path / "incomplete-owner-decision-packet.md"
    stale_packet.write_text(
        "\n".join(
            [
                "# Product-Category PnL Owner Decision Packet",
                "",
                "## Packet Freshness Guard",
                "",
                "- `packet_generator=manual-copy`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    template = tmp_path / "product-category-approval-template.md"
    template.write_text(_filled_template_text(), encoding="utf-8")
    golden_artifact = _approved_golden_sample_artifact(tmp_path)
    closure_checklist = _closed_closure_checklist(tmp_path)
    monkeypatch.setattr(approval_checker, "EXPECTED_OWNER_DECISION_PACKET", str(stale_packet))

    payload = approval_checker.build_status(
        template,
        golden_sample_approval_path=golden_artifact,
        closure_checklist_path=closure_checklist,
    )

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "reviewed_owner_decision_packet",
    ]
    assert payload["approval_field_status"]["reviewed_owner_decision_packet"] == "stale_generated_artifact"
