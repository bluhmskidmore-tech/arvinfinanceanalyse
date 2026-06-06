from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "docs" / "pnl" / "pnl-attribution-business-owner-approval-template.md"
EXPECTED_SIGNOFF_PACKET = "docs/pnl/pnl-attribution-sign-off-packet.md"
EXPECTED_GOVERNANCE_AUDIT_PACKET = "docs/pnl/pnl-attribution-governance-audit-packet.md"
EXPECTED_OWNER_EVIDENCE_PACKET = "docs/pnl/pnl-attribution-owner-evidence-packet.md"

ACTION_ITEM_DEFINITIONS = {
    "business_owner_name": {
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
    },
    "business_owner_role": {
        "template_field": "Business owner role",
        "required_value": "Business owner accountability role",
    },
    "approval_decision": {
        "template_field": "Approval decision",
        "required_value": "approve",
    },
    "approval_date": {
        "template_field": "Approval date",
        "required_value": "YYYY-MM-DD",
    },
    "business_owner_signature": {
        "template_field": "Business owner signature",
        "required_value": "Business owner signature",
    },
    "reviewed_signoff_packet": {
        "template_field": "Reviewed sign-off packet",
        "required_value": EXPECTED_SIGNOFF_PACKET,
    },
    "reviewed_governance_audit_packet": {
        "template_field": "Reviewed governance audit packet",
        "required_value": EXPECTED_GOVERNANCE_AUDIT_PACKET,
    },
    "reviewed_owner_evidence_packet": {
        "template_field": "Reviewed owner evidence packet",
        "required_value": EXPECTED_OWNER_EVIDENCE_PACKET,
    },
    "governance_record_review": {
        "template_field": "- Governance record reviewed",
        "required_value": "yes",
    },
    "golden_sample_review": {
        "template_field": "- Golden sample `GS-PNL-ATTR-WB-A` reviewed",
        "required_value": "yes",
    },
    "ui_api_payload_review": {
        "template_field": "- UI/API payload evidence reviewed",
        "required_value": "yes",
    },
    "live_smoke_evidence_review": {
        "template_field": "- Live smoke evidence reviewed",
        "required_value": "yes",
    },
    "verification_commands_rerun": {
        "template_field": "- Verification commands rerun before approval",
        "required_value": "yes",
    },
    "candidate_boundary_acceptance": {
        "template_field": "- Candidate-only boundary accepted",
        "required_value": "yes",
    },
    "decision_notes": {
        "template_field": "Decision notes",
        "required_value": "Required if decision is reject or request_changes",
    },
    "formal_use_promotion_boundary": {
        "template_field": "Formal use allowed",
        "required_value": "formal_use_allowed=false",
    },
    "closure_promotion_boundary": {
        "template_field": "Closure approved",
        "required_value": "closure_approved=false",
    },
}


def _extract_code_value(text: str, label: str) -> str:
    prefix = f"{label}: `"
    for line in text.splitlines():
        if line.startswith(prefix) and line.endswith("`"):
            return line[len(prefix) : -1]
    raise ValueError(f"Missing required approval template field: {label}")


def _extract_assignment(value: str, name: str) -> str:
    prefix = f"{name}="
    if not value.startswith(prefix):
        raise ValueError(f"Expected {name}=... but found {value!r}")
    return value[len(prefix) :]


def _extract_plain_value(text: str, label: str) -> str:
    prefix = f"{label}: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise ValueError(f"Missing required approval template field: {label}")


def _normalize_value(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("`") and stripped.endswith("`"):
        stripped = stripped[1:-1].strip()
    return stripped


def _is_placeholder(value: str) -> bool:
    stripped = _normalize_value(value)
    return stripped.startswith("<") and stripped.endswith(">")


def _plain_value_is_filled(text: str, label: str) -> bool:
    return not _is_placeholder(_extract_plain_value(text, label))


def _plain_value(text: str, label: str) -> str:
    return _normalize_value(_extract_plain_value(text, label))


def _review_is_yes(text: str, label: str) -> bool:
    value = _plain_value(text, label).lower()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    return value == "yes"


def _approval_date_is_valid(text: str) -> bool:
    value = _plain_value(text, "Approval date")
    if _is_placeholder(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == len("YYYY-MM-DD")


def _approval_blockers(
    text: str,
    approval_status: str,
    *,
    formal_use_allowed: str,
    closure_approved: str,
) -> list[str]:
    field_blockers: list[str] = []

    required_plain_fields = {
        "Business owner name": "business_owner_name",
        "Business owner role": "business_owner_role",
        "Approval decision": "approval_decision",
        "Approval date": "approval_date",
        "Business owner signature": "business_owner_signature",
    }
    for label, blocker in required_plain_fields.items():
        if not _plain_value_is_filled(text, label):
            field_blockers.append(blocker)
    if _plain_value(text, "Reviewed sign-off packet") != EXPECTED_SIGNOFF_PACKET:
        field_blockers.append("reviewed_signoff_packet")
    if _plain_value(text, "Reviewed governance audit packet") != EXPECTED_GOVERNANCE_AUDIT_PACKET:
        field_blockers.append("reviewed_governance_audit_packet")
    if _plain_value(text, "Reviewed owner evidence packet") != EXPECTED_OWNER_EVIDENCE_PACKET:
        field_blockers.append("reviewed_owner_evidence_packet")
    if _plain_value_is_filled(text, "Approval decision"):
        approval_decision = _plain_value(text, "Approval decision")
        if approval_decision != "approve":
            field_blockers.append("approval_decision")
        if approval_decision in {"reject", "request_changes"} and not _plain_value_is_filled(text, "Decision notes"):
            field_blockers.append("decision_notes")
    if _plain_value_is_filled(text, "Approval date") and not _approval_date_is_valid(text):
        field_blockers.append("approval_date")

    review_fields = {
        "- Governance record reviewed": "governance_record_review",
        "- Golden sample `GS-PNL-ATTR-WB-A` reviewed": "golden_sample_review",
        "- UI/API payload evidence reviewed": "ui_api_payload_review",
        "- Live smoke evidence reviewed": "live_smoke_evidence_review",
        "- Verification commands rerun before approval": "verification_commands_rerun",
        "- Candidate-only boundary accepted": "candidate_boundary_acceptance",
    }
    for label, blocker in review_fields.items():
        if not _review_is_yes(text, label):
            field_blockers.append(blocker)

    if formal_use_allowed != "false":
        field_blockers.append("formal_use_promotion_boundary")
    if closure_approved != "false":
        field_blockers.append("closure_promotion_boundary")

    if approval_status != "approved" or field_blockers:
        return ["business_owner_approval", *field_blockers]
    return []


def _approval_field_status(
    text: str,
    *,
    formal_use_allowed: str,
    closure_approved: str,
) -> dict[str, str]:
    approval_decision = _plain_value(text, "Approval decision")
    return {
        "business_owner_name": "valid" if _plain_value_is_filled(text, "Business owner name") else "missing",
        "business_owner_role": "valid" if _plain_value_is_filled(text, "Business owner role") else "missing",
        "approval_decision": _approval_decision_status(approval_decision),
        "approval_date": _approval_date_status(text),
        "business_owner_signature": (
            "valid" if _plain_value_is_filled(text, "Business owner signature") else "missing"
        ),
        "reviewed_signoff_packet": (
            "valid" if _plain_value(text, "Reviewed sign-off packet") == EXPECTED_SIGNOFF_PACKET else "invalid"
        ),
        "reviewed_governance_audit_packet": (
            "valid"
            if _plain_value(text, "Reviewed governance audit packet") == EXPECTED_GOVERNANCE_AUDIT_PACKET
            else "invalid"
        ),
        "reviewed_owner_evidence_packet": (
            "valid"
            if _plain_value(text, "Reviewed owner evidence packet") == EXPECTED_OWNER_EVIDENCE_PACKET
            else "invalid"
        ),
        "governance_record_review": _review_status(text, "- Governance record reviewed"),
        "golden_sample_review": _review_status(text, "- Golden sample `GS-PNL-ATTR-WB-A` reviewed"),
        "ui_api_payload_review": _review_status(text, "- UI/API payload evidence reviewed"),
        "live_smoke_evidence_review": _review_status(text, "- Live smoke evidence reviewed"),
        "verification_commands_rerun": _review_status(text, "- Verification commands rerun before approval"),
        "candidate_boundary_acceptance": _review_status(text, "- Candidate-only boundary accepted"),
        "decision_notes": _decision_notes_status(text, approval_decision),
        "formal_use_allowed": "valid" if formal_use_allowed == "false" else "invalid",
        "closure_approved": "valid" if closure_approved == "false" else "invalid",
    }


def _approval_action_items(
    remaining_blockers: list[str],
    field_status: dict[str, str],
) -> list[dict[str, str]]:
    action_items = []
    for blocker in remaining_blockers:
        if blocker == "business_owner_approval":
            continue
        definition = ACTION_ITEM_DEFINITIONS[blocker]
        action_items.append(
            {
                "blocker": blocker,
                "template_field": definition["template_field"],
                "required_value": definition["required_value"],
                "current_status": field_status.get(blocker, "invalid"),
            }
        )
    return action_items


def _approval_decision_status(value: str) -> str:
    if _is_placeholder(value):
        return "missing"
    return "valid" if value == "approve" else "invalid"


def _approval_date_status(text: str) -> str:
    if not _plain_value_is_filled(text, "Approval date"):
        return "missing"
    return "valid" if _approval_date_is_valid(text) else "invalid"


def _review_status(text: str, label: str) -> str:
    if _review_is_yes(text, label):
        return "valid"
    return "pending"


def _decision_notes_status(text: str, approval_decision: str) -> str:
    if approval_decision not in {"reject", "request_changes"}:
        return "not_required"
    return "valid" if _plain_value_is_filled(text, "Decision notes") else "missing"


def build_status(template_path: Path) -> dict[str, object]:
    text = template_path.read_text(encoding="utf-8")
    approval_status = _extract_assignment(_extract_code_value(text, "Approval status"), "approval_status")
    formal_use_allowed = _extract_assignment(_extract_code_value(text, "Formal use allowed"), "formal_use_allowed")
    closure_approved = _extract_assignment(_extract_code_value(text, "Closure approved"), "closure_approved")

    remaining_blockers = _approval_blockers(
        text,
        approval_status,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
    )
    approval_field_status = _approval_field_status(
        text,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
    )
    approval_action_items = _approval_action_items(remaining_blockers, approval_field_status)
    approval_captured = approval_status == "approved" and not remaining_blockers
    return {
        "page_id": _extract_code_value(text, "Page ID"),
        "page_slug": _extract_code_value(text, "Page slug"),
        "primary_api": _extract_code_value(text, "Primary API"),
        "approval_check": _extract_code_value(text, "Approval check"),
        "approval_status": approval_status,
        "business_owner_approval_captured": approval_captured,
        "formal_use_allowed": formal_use_allowed == "true",
        "closure_approved": closure_approved == "true",
        "remaining_blockers": remaining_blockers,
        "approval_field_status": approval_field_status,
        "approval_action_items": approval_action_items,
        "approval_action_item_count": len(approval_action_items),
        "template_path": str(template_path),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": approval_captured,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the pnl-attribution business-owner approval template and report its current status.",
    )
    parser.add_argument(
        "--template-path",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Path to the business-owner approval template.",
    )
    parser.add_argument(
        "--require-captured",
        action="store_true",
        help="Return a non-zero exit code unless business-owner approval is fully captured.",
    )
    args = parser.parse_args(argv)

    status = build_status(Path(args.template_path))
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if args.require_captured and not status["business_owner_approval_captured"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
