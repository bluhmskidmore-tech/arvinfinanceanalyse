from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.product_category_pnl_owner_decision_packet import (
    DEFAULT_OUTPUT,
    build_packet,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "product_category_pnl_owner_decision_packet.py"


def _run_packet(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_product_category_owner_decision_packet_groups_product_and_api_blockers() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "product_category_pnl_owner_decision_packet"
    assert packet["page_slug"] == "product-category-pnl"
    assert packet["decision_status"] == "pending_owner_decisions"
    assert packet["owner_decision_ready"] is False
    assert packet["decision_required_count"] == 3
    assert packet["api_contract_required_count"] == 2
    assert packet["decision_item_count"] == 5
    assert packet["decision_classes"] == {
        "1": "product_decision_required",
        "2": "backend_api_contract_required",
    }
    assert packet["next_review_queue"] == [
        {
            "review_key": "next_1_refresh_timeout_stale_copy",
            "rank": "1",
            "topic": "refresh timeout/stale copy",
            "required_review": "specify the copy shown when refresh exceeds the current UI polling window.",
            "review_owner_type": "product_owner",
            "evidence_path": "frontend/src/test/ProductCategoryPnlPage.test.tsx",
            "blocker_reason": "Queued/running/failed states are tested, but timeout-specific stale copy is not product-frozen.",
            "pre_signature_action": "Owner must approve timeout and stale-state copy or defer it explicitly before signature.",
            "current_status": "pending_review",
        },
        {
            "review_key": "next_2_unit_4_extended_validation_copy",
            "rank": "2",
            "topic": "Unit 4 extended validation copy",
            "required_review": "freeze any additional backend validation wording beyond the two covered empty-payload cases.",
            "review_owner_type": "product_owner",
            "evidence_path": "docs/pnl/product-category-closure-checklist.md",
            "blocker_reason": "The two primary empty-payload cases are covered, but extended validation wording remains outside the frozen checklist scope.",
            "pre_signature_action": "Owner must approve the extended validation copy scope or confirm the current two-case scope is sufficient.",
            "current_status": "pending_review",
        },
        {
            "review_key": "next_3_dual_sort_rationale",
            "rank": "3",
            "topic": "dual-sort rationale",
            "required_review": "record the product intent for keeping current and event sort controls independent.",
            "review_owner_type": "product_owner",
            "evidence_path": "docs/pnl/product-category-remaining-blockers.md",
            "blocker_reason": "The dual-sort behavior is visible, but the product rationale for two independent controls is not recorded.",
            "pre_signature_action": "Owner must record the product rationale for dual sort or approve a single-sort model before signature.",
            "current_status": "pending_review",
        },
        {
            "review_key": "next_4_revoke_confirmation_policy",
            "rank": "4",
            "topic": "revoke confirmation policy",
            "required_review": "freeze whether destructive revoke needs policy beyond the already tested browser confirmation gate.",
            "review_owner_type": "product_owner",
            "evidence_path": "frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx",
            "blocker_reason": "Browser confirmation behavior is tested, but no owner policy states whether that is sufficient for destructive revoke.",
            "pre_signature_action": "Owner must approve browser confirmation as sufficient or specify an additional revoke policy gate.",
            "current_status": "pending_review",
        },
    ]
    assert packet["next_review_queue_scope"] == {
        "source_section": "Owner Review Queue",
        "item_count": 4,
        "formal_decision_item_count": 5,
        "formal_decision_class_count": 5,
        "supplemental_review_topic_count": 1,
        "counts_as_owner_decision": False,
        "captures_product_or_api_decisions": False,
        "boundary": (
            "Owner Review Queue has 4 review topics. Three map to formal Class 1 product "
            "decision blockers and one is supplemental revoke-policy review; the queue does "
            "not change the 5 formal decision/API contract item count."
        ),
    }
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "certification_effect": "none",
    }
    assert packet["decision_intake_checklist"] == {
        "checklist_kind": "owner_decision_intake_checklist",
        "decision_intake_ready": True,
        "owner_decision_ready": False,
        "captures_product_or_api_decisions": False,
        "decision_item_count": 5,
        "pending_decision_count": 5,
        "source_artifact_exists": True,
        "decision_classes": {
            "1": "product_decision_required",
            "2": "backend_api_contract_required",
        },
        "required_owner_types": ["product_owner", "backend_api_contract_owner"],
        "boundary": (
            "Decision intake is ready for owner review, but every decision item remains pending; "
            "this checklist does not capture product/API decisions or approve certification."
        ),
    }

    items = packet["decision_items"]
    assert [item["class"] for item in items] == ["1", "1", "1", "2", "2"]
    assert [item["unit"] for item in items] == ["3", "4", "5", "6", "6"]
    assert items[0]["decision_key"] == "unit_3_long_running_refresh_timeout_messaging"
    assert items[0]["required_decision"] == (
        "Decide timeout user messaging and whether to surface run_id after timeout"
    )
    assert items[3]["decision_key"] == "unit_6_backend_global_utf_8_bom_policy_for_generated_csv"
    assert items[3]["owner_type"] == "backend_api_contract_owner"


def test_product_category_owner_decision_packet_cli_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "owner-decision-packet.md"

    returncode, payload = _run_packet("--output", str(output_path))

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["decision_status"] == "pending_owner_decisions"
    assert payload["owner_decision_ready"] is False
    assert payload["decision_item_count"] == 5
    assert payload["next_review_queue_item_count"] == 4
    assert payload["formal_decision_item_count"] == 5
    assert payload["formal_decision_class_count"] == 5
    assert payload["supplemental_review_topic_count"] == 1
    assert payload["decision_intake_checklist"] == {
        "decision_intake_ready": True,
        "owner_decision_ready": False,
        "captures_product_or_api_decisions": False,
        "pending_decision_count": 5,
    }
    assert payload["next_review_queue_scope"] == {
        "counts_as_owner_decision": False,
        "captures_product_or_api_decisions": False,
        "formal_decision_item_count": 5,
        "supplemental_review_topic_count": 1,
    }
    assert payload["certification_effect"] == "none"
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "captures_golden_sample_approval": False,
        "captures_closure_approval": False,
        "certification_effect": "none",
    }

    text = output_path.read_text(encoding="utf-8")
    assert "Product-Category PnL Owner Decision Packet" in text
    assert "decision_status=pending_owner_decisions" in text
    assert "decision_item_count=5" in text
    assert "Class 1 product decisions: `3`" in text
    assert "Class 2 API/contract decisions: `2`" in text
    assert "Decision Intake Checklist" in text
    assert "decision_intake_ready=true" in text
    assert "pending_decision_count=5" in text
    assert "Next Review Queue" in text
    assert "next_review_queue_item_count=4" in text
    assert "formal_decision_item_count=5" in text
    assert "supplemental_review_topic_count=1" in text
    assert "supplemental revoke-policy review" in text
    assert "Evidence path" in text
    assert "Blocker reason" in text
    assert "Pre-signature action" in text
    assert "next_1_refresh_timeout_stale_copy" in text
    assert "next_4_revoke_confirmation_policy" in text
    assert "next_1_outward_as_of_date" not in text
    assert "outward `as_of_date`" not in text
    assert "Owner must approve browser confirmation as sufficient or specify an additional revoke policy gate." in text
    assert "counts_as_owner_decision=false" in text
    assert "unit_3_long_running_refresh_timeout_messaging" in text
    assert "unit_6_backend_global_utf_8_bom_policy_for_generated_csv" in text
    assert "unit_7_destructive_revoke_confirmation_policy" not in text
    assert "captures_product_or_api_decisions=false" in text
    assert "captures_golden_sample_approval=false" in text
    assert "captures_closure_approval=false" in text
    assert "certification_effect=none" in text
    assert "This packet does not approve page closure" in text


def test_checked_in_product_category_owner_decision_packet_matches_renderer() -> None:
    packet = build_packet()
    expected_markdown = render_markdown(packet)

    checked_in_markdown = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    assert checked_in_markdown == expected_markdown
    assert "## Packet Freshness Guard" in checked_in_markdown
    assert "source_artifact=docs/pnl/product-category-remaining-blockers.md" in checked_in_markdown
    assert "packet_generator=script-owned" in checked_in_markdown
    assert "Manual edits to this packet must be followed by rerunning the generator." in checked_in_markdown
