from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import check_product_category_pnl_business_owner_approval as approval_checker


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_product_category_pnl_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "pnl" / "product-category-pnl-business-owner-approval-template.md"


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
    assert payload["approval_action_item_count"] == 15
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
    }


def test_product_category_pnl_approval_template_states_current_owner_decision_counts() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "3 product decisions and 2 API/contract blockers" in text
    assert "5 formal decision items plus 5 next-review queue topics" in text
    assert "Owner decision next-review queue acknowledged" in text
    assert "four product decisions" not in text
    assert "4 product decisions" not in text
    assert "Owner Readiness Receipt" in text
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
