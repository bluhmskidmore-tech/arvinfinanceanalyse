from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_product_category_pnl_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)


DEFAULT_OUTPUT = ROOT / "docs" / "pnl" / "product-category-pnl-owner-decision-packet.md"
DECISION_CLASS_LABELS = {
    "1": "product_decision_required",
    "2": "backend_api_contract_required",
}
OWNER_BY_CLASS = {
    "1": "product_owner",
    "2": "backend_api_contract_owner",
}
NEXT_REVIEW_QUEUE_DETAILS = {
    "next_1_outward_as_of_date": {
        "review_owner_type": "product_owner",
        "evidence_path": "docs/pnl/product-category-page-truth-contract.md",
        "blocker_reason": (
            "The page currently preserves selected report_date and resolved report_date semantics, "
            "but no owner-approved outward as_of_date field exists."
        ),
        "pre_signature_action": (
            "Owner must either approve no standalone outward as_of_date or specify the exact API/UI "
            "field before signature."
        ),
    },
    "next_2_refresh_timeout_stale_copy": {
        "review_owner_type": "product_owner",
        "evidence_path": "frontend/src/test/ProductCategoryPnlPage.test.tsx",
        "blocker_reason": (
            "Queued/running/failed states are tested, but timeout-specific stale copy is not "
            "product-frozen."
        ),
        "pre_signature_action": (
            "Owner must approve timeout and stale-state copy or defer it explicitly before signature."
        ),
    },
    "next_3_unit_4_extended_validation_copy": {
        "review_owner_type": "product_owner",
        "evidence_path": "docs/pnl/product-category-closure-checklist.md",
        "blocker_reason": (
            "The two primary empty-payload cases are covered, but extended validation wording remains "
            "outside the frozen checklist scope."
        ),
        "pre_signature_action": (
            "Owner must approve the extended validation copy scope or confirm the current two-case "
            "scope is sufficient."
        ),
    },
    "next_4_dual_sort_rationale": {
        "review_owner_type": "product_owner",
        "evidence_path": "docs/pnl/product-category-remaining-blockers.md",
        "blocker_reason": (
            "The dual-sort behavior is visible, but the product rationale for two independent controls "
            "is not recorded."
        ),
        "pre_signature_action": (
            "Owner must record the product rationale for dual sort or approve a single-sort model "
            "before signature."
        ),
    },
    "next_5_revoke_confirmation_policy": {
        "review_owner_type": "product_owner",
        "evidence_path": "frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx",
        "blocker_reason": (
            "Browser confirmation behavior is tested, but no owner policy states whether that is "
            "sufficient for destructive revoke."
        ),
        "pre_signature_action": (
            "Owner must approve browser confirmation as sufficient or specify an additional revoke "
            "policy gate."
        ),
    },
}
DECISION_KEY_ALIASES = {
    "long-running refresh ux ... timeout messaging vs `runpollingtask` generic timeout": (
        "long_running_refresh_timeout_messaging"
    ),
    "long copy/ux for validation beyond the two primary empty-payload cases is not exhaustively specified": (
        "extended_validation_copy_policy"
    ),
    "product rationale for two independent sort controls ... narrative gap": "dual_sort_rationale",
    "backend/global utf-8 bom policy for generated csv not specified": (
        "backend_global_utf_8_bom_policy_for_generated_csv"
    ),
    "no frozen behavior for very large exports": "large_export_behavior_policy",
    "no confirmation modal for destructive revoke": "destructive_revoke_confirmation_policy",
}


def build_packet(*, template_path: Path = DEFAULT_TEMPLATE) -> dict[str, Any]:
    approval = build_approval_status(template_path)
    triage = approval["closure_blocker_triage"]
    source_artifact = str(triage["artifact_path"])
    decision_items = [
        _decision_item(row)
        for row in triage["blockers"]
        if row["class"] in DECISION_CLASS_LABELS
    ]
    decision_intake_checklist = _decision_intake_checklist(
        source_artifact=source_artifact,
        decision_items=decision_items,
    )
    next_review_queue = _next_review_queue(source_artifact)
    return {
        "packet_kind": "product_category_pnl_owner_decision_packet",
        "page_id": approval["page_id"],
        "page_slug": approval["page_slug"],
        "primary_api": approval["primary_api"],
        "decision_status": "pending_owner_decisions",
        "owner_decision_ready": False,
        "decision_required_count": triage["decision_required_count"],
        "api_contract_required_count": triage["api_contract_required_count"],
        "decision_item_count": len(decision_items),
        "decision_classes": dict(DECISION_CLASS_LABELS),
        "source_artifact": triage["artifact_path"],
        "decision_intake_checklist": decision_intake_checklist,
        "next_review_queue": next_review_queue,
        "next_review_queue_scope": {
            "source_section": "Next cursor-safe tasks",
            "item_count": len(next_review_queue),
            "counts_as_owner_decision": False,
            "captures_product_or_api_decisions": False,
        },
        "decision_items": decision_items,
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "captures_product_or_api_decisions": False,
        },
    }


def _next_review_queue(source_artifact: str) -> list[dict[str, str]]:
    source_path = ROOT / source_artifact
    if not source_path.is_file():
        return []
    text = source_path.read_text(encoding="utf-8")
    try:
        section = text.split("## Next cursor-safe tasks", maxsplit=1)[1]
    except IndexError:
        return []

    queue: list[dict[str, str]] = []
    for line in section.splitlines():
        if line.startswith("## "):
            break
        match = re.match(r"^(\d+)\.\s+\*\*(.+?):\*\*\s+(.+)$", line.strip())
        if match is None:
            continue
        rank, topic, required_review = match.groups()
        review_key = _review_key(rank, topic)
        queue.append(
            {
                "review_key": review_key,
                "rank": rank,
                "topic": topic,
                "required_review": required_review,
                **_next_review_detail(review_key, source_artifact),
                "current_status": "pending_review",
            }
        )
    return queue


def _next_review_detail(review_key: str, source_artifact: str) -> dict[str, str]:
    detail = NEXT_REVIEW_QUEUE_DETAILS.get(review_key)
    if detail is not None:
        return dict(detail)
    return {
        "review_owner_type": "product_owner",
        "evidence_path": source_artifact,
        "blocker_reason": "Pending owner review is captured in the source blocker artifact.",
        "pre_signature_action": "Owner must resolve or explicitly defer this review topic before signature.",
    }


def _review_key(rank: str, topic: str) -> str:
    normalized = topic.replace("`", "").lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return f"next_{rank}_{normalized}"


def _decision_intake_checklist(
    *,
    source_artifact: str,
    decision_items: list[dict[str, str]],
) -> dict[str, object]:
    pending_count = sum(1 for item in decision_items if item["current_decision"] == "pending")
    required_owner_types = list(dict.fromkeys(item["owner_type"] for item in decision_items))
    return {
        "checklist_kind": "owner_decision_intake_checklist",
        "decision_intake_ready": bool(decision_items) and (ROOT / source_artifact).is_file(),
        "owner_decision_ready": False,
        "captures_product_or_api_decisions": False,
        "decision_item_count": len(decision_items),
        "pending_decision_count": pending_count,
        "source_artifact_exists": (ROOT / source_artifact).is_file(),
        "decision_classes": dict(DECISION_CLASS_LABELS),
        "required_owner_types": required_owner_types,
        "boundary": (
            "Decision intake is ready for owner review, but every decision item remains pending; "
            "this checklist does not capture product/API decisions or approve certification."
        ),
    }


def _decision_item(row: dict[str, str]) -> dict[str, str]:
    return {
        "decision_key": _decision_key(row["unit"], row["blocker"]),
        "unit": row["unit"],
        "class": row["class"],
        "class_label": DECISION_CLASS_LABELS[row["class"]],
        "owner_type": OWNER_BY_CLASS[row["class"]],
        "blocker": row["blocker"],
        "required_decision": row["minimal_next_action"],
        "suggested_scope": row["suggested_scope"],
        "current_decision": "pending",
    }


def _decision_key(unit: str, blocker: str) -> str:
    text = blocker.lower()
    alias = DECISION_KEY_ALIASES.get(text)
    if alias is not None:
        return f"unit_{unit}_{alias}"
    text = text.replace("utf-8", "utf_8")
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    return f"unit_{unit}_{text}"


def render_markdown(packet: dict[str, Any]) -> str:
    checklist = packet["decision_intake_checklist"]
    queue_scope = packet["next_review_queue_scope"]
    required_owner_types = ", ".join(f"`{owner}`" for owner in checklist["required_owner_types"])
    queue_rows = "\n".join(
        (
            f"| `{item['review_key']}` | {item['rank']} | {item['topic']} | "
            f"{item['required_review']} | `{item['review_owner_type']}` | "
            f"`{item['evidence_path']}` | {item['blocker_reason']} | "
            f"{item['pre_signature_action']} | `{item['current_status']}` |"
        )
        for item in packet["next_review_queue"]
    )
    rows = "\n".join(
        (
            f"| `{item['decision_key']}` | Unit {item['unit']} | `{item['class_label']}` | "
            f"`{item['owner_type']}` | {item['blocker']} | {item['required_decision']} | "
            f"`{item['current_decision']}` |"
        )
        for item in packet["decision_items"]
    )
    return f"""# Product-Category PnL Owner Decision Packet

Page ID: `{packet['page_id']}`
Page slug: `{packet['page_slug']}`
Primary API: `{packet['primary_api']}`
Decision status: `decision_status={packet['decision_status']}`
Owner decision ready: `{str(packet['owner_decision_ready']).lower()}`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, capture product/API decisions, or grant final certification.

## Decision Summary

- Source artifact: `{packet['source_artifact']}`
- `decision_item_count={packet['decision_item_count']}`
- Class 1 product decisions: `{packet['decision_required_count']}`
- Class 2 API/contract decisions: `{packet['api_contract_required_count']}`

## Packet Freshness Guard

- `packet_generator=script-owned`
- `source_artifact={packet['source_artifact']}`
- Boundary: Manual edits to this packet must be followed by rerunning the generator.

## Decision Intake Checklist

- Checklist kind: `{checklist['checklist_kind']}`
- `decision_intake_ready={str(checklist['decision_intake_ready']).lower()}`
- `owner_decision_ready={str(checklist['owner_decision_ready']).lower()}`
- `captures_product_or_api_decisions={str(checklist['captures_product_or_api_decisions']).lower()}`
- `decision_item_count={checklist['decision_item_count']}`
- `pending_decision_count={checklist['pending_decision_count']}`
- `source_artifact_exists={str(checklist['source_artifact_exists']).lower()}`
- Required owner types: {required_owner_types}
- Boundary: {checklist['boundary']}

## Next Review Queue

- Source section: `{queue_scope['source_section']}`
- `next_review_queue_item_count={queue_scope['item_count']}`
- `counts_as_owner_decision={str(queue_scope['counts_as_owner_decision']).lower()}`
- `captures_product_or_api_decisions={str(queue_scope['captures_product_or_api_decisions']).lower()}`

| Review key | Rank | Topic | Required review | Review owner type | Evidence path | Blocker reason | Pre-signature action | Current status |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
{queue_rows}

## Decision Items

| Decision key | Unit | Class | Owner type | Blocker | Required decision | Current decision |
| --- | --- | --- | --- | --- | --- | --- |
{rows}

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `captures_product_or_api_decisions=false`
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the product-category-pnl owner decision packet for product/API blockers.",
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
        "decision_status": packet["decision_status"],
        "owner_decision_ready": packet["owner_decision_ready"],
        "decision_item_count": packet["decision_item_count"],
        "next_review_queue_item_count": packet["next_review_queue_scope"]["item_count"],
        "decision_required_count": packet["decision_required_count"],
        "api_contract_required_count": packet["api_contract_required_count"],
        "evidence_scope": packet["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
