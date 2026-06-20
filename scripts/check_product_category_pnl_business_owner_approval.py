from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "docs" / "pnl" / "product-category-pnl-business-owner-approval-template.md"
DEFAULT_GOLDEN_SAMPLE_APPROVAL = ROOT / "tests" / "golden_samples" / "GS-PROD-CAT-PNL-A" / "approval.md"
DEFAULT_CLOSURE_CHECKLIST = ROOT / "docs" / "pnl" / "product-category-closure-checklist.md"
DEFAULT_CLOSURE_BLOCKER_TRIAGE = ROOT / "docs" / "pnl" / "product-category-remaining-blockers.md"
EXPECTED_BOUNDARY_PACKET = "docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json"
EXPECTED_FIRST_CERTIFICATION_PACKET = "docs/pnl/product-category-pnl-first-certification-packet.md"
EXPECTED_OWNER_DECISION_PACKET = "docs/pnl/product-category-pnl-owner-decision-packet.md"
EXPECTED_FIRST_CERTIFICATION_FRESHNESS_MARKERS = [
    "## Packet Freshness Guard",
    "`packet_generator=script-owned`",
    "`source_artifacts=readiness_report, approval_template, closure_blocker_triage`",
]
EXPECTED_OWNER_DECISION_FRESHNESS_MARKERS = [
    "## Packet Freshness Guard",
    "`packet_generator=script-owned`",
    "`source_artifact=docs/pnl/product-category-remaining-blockers.md`",
]

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
    "reviewed_boundary_packet": {
        "template_field": "Reviewed boundary packet",
        "required_value": EXPECTED_BOUNDARY_PACKET,
    },
    "reviewed_first_certification_packet": {
        "template_field": "Reviewed first-certification packet",
        "required_value": EXPECTED_FIRST_CERTIFICATION_PACKET,
    },
    "governance_record_review": {
        "template_field": "- Governance record reviewed",
        "required_value": "yes",
    },
    "reviewed_owner_decision_packet": {
        "template_field": "- Owner decision packet reviewed",
        "required_value": "yes",
    },
    "owner_decision_next_review_queue_acknowledgement": {
        "template_field": "- Owner decision next-review queue acknowledged",
        "required_value": "yes",
    },
    "golden_sample_artifact_reconciliation": {
        "template_field": "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled",
        "required_value": "yes",
    },
    "closure_checklist_review": {
        "template_field": "- Closure checklist units reviewed",
        "required_value": "yes",
    },
    "fallback_liability_branch_boundary_review": {
        "template_field": "- Fallback liability branch model-boundary evidence reviewed",
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
    "evidence_pending_boundary_acceptance": {
        "template_field": "- Evidence-pending boundary accepted",
        "required_value": "yes",
    },
    "certification_packet_consistency": {
        "template_field": "Certification packet consistency",
        "required_value": "valid",
    },
    "decision_notes": {
        "template_field": "Decision notes",
        "required_value": "Required if decision is reject or request_changes",
    },
    "formal_use_boundary": {
        "template_field": "Formal use allowed",
        "required_value": "formal_use_allowed=true",
    },
    "closure_promotion_boundary": {
        "template_field": "Closure approved",
        "required_value": "closure_approved=false",
    },
}

ACTION_SIGNOFF_GROUPS = {
    "business_owner_name": "owner_identity",
    "business_owner_role": "owner_identity",
    "approval_decision": "owner_decision",
    "approval_date": "owner_decision",
    "business_owner_signature": "owner_decision",
    "reviewed_boundary_packet": "evidence_review",
    "governance_record_review": "evidence_review",
    "reviewed_first_certification_packet": "evidence_review",
    "reviewed_owner_decision_packet": "evidence_review",
    "owner_decision_next_review_queue_acknowledgement": "evidence_review",
    "golden_sample_artifact_reconciliation": "evidence_review",
    "closure_checklist_review": "evidence_review",
    "fallback_liability_branch_boundary_review": "evidence_review",
    "ui_api_payload_review": "evidence_review",
    "certification_packet_consistency": "evidence_review",
    "live_smoke_evidence_review": "pre_signature_verification",
    "verification_commands_rerun": "pre_signature_verification",
    "evidence_pending_boundary_acceptance": "boundary_acceptance",
    "decision_notes": "owner_decision",
    "formal_use_boundary": "boundary_acceptance",
    "closure_promotion_boundary": "boundary_acceptance",
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


def _markdown_code_value(text: str, label: str) -> str:
    prefix = f"- {label}: `"
    for line in text.splitlines():
        if line.startswith(prefix) and line.endswith("`"):
            return line[len(prefix) : -1]
    return "missing"


def _artifact_path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _reviewed_artifact_status(
    text: str,
    label: str,
    expected_path: str,
    *,
    required_freshness_markers: list[str] | None = None,
) -> str:
    if _plain_value(text, label) != expected_path:
        return "invalid"
    path = ROOT / expected_path
    if not path.exists():
        return "missing_artifact"
    if required_freshness_markers and not _has_freshness_markers(path, required_freshness_markers):
        return "stale_generated_artifact"
    return "valid"


def _artifact_field_is_filled(value: str) -> bool:
    normalized = _normalize_value(value)
    return normalized not in {"", "TBD", "missing", "unknown"} and not _is_placeholder(normalized)


def _artifact_approval_date_is_valid(value: str) -> bool:
    if not _artifact_field_is_filled(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == len("YYYY-MM-DD")


def _golden_sample_approval_artifact(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "sample_id": "GS-PROD-CAT-PNL-A",
            "status": "missing",
            "owner": "missing",
            "approver": "missing",
            "approved_at": "missing",
            "artifact_path": _artifact_path_label(path),
            "approved": False,
        }

    text = path.read_text(encoding="utf-8")
    status = _markdown_code_value(text, "Status")
    owner = _markdown_code_value(text, "Owner")
    approver = _markdown_code_value(text, "Approver")
    approved_at = _markdown_code_value(text, "Approved at")
    return {
        "sample_id": _markdown_code_value(text, "Sample ID"),
        "status": status,
        "owner": owner,
        "approver": approver,
        "approved_at": approved_at,
        "artifact_path": _artifact_path_label(path),
        "approved": (
            status == "approved"
            and _artifact_field_is_filled(owner)
            and _artifact_field_is_filled(approver)
            and _artifact_approval_date_is_valid(approved_at)
        ),
    }


def _closure_checklist_artifact(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "artifact_path": _artifact_path_label(path),
            "ready_for_owner_approval": False,
            "unit_count": 0,
            "closed_count": 0,
            "partial_count": 0,
            "not_trusted_count": 0,
            "excluded_count": 0,
            "open_unit_count": 0,
            "open_units": [],
            "distribution": {},
        }

    text = path.read_text(encoding="utf-8")
    units = _closure_checklist_units(text)
    distribution = _closure_checklist_distribution(text)
    open_units = [
        {"unit": unit["unit"], "status": unit["status"]}
        for unit in units
        if unit["status"] != "CLOSED"
    ]
    closed_count = sum(1 for unit in units if unit["status"] == "CLOSED")
    partial_count = sum(1 for unit in units if unit["status"] == "PARTIAL")
    not_trusted_count = sum(1 for unit in units if unit["status"] == "NOT_TRUSTED")
    excluded_count = sum(1 for unit in units if unit["status"] == "EXCLUDED")
    distribution_partial = int(distribution.get("PARTIAL", partial_count))
    distribution_not_trusted = int(distribution.get("NOT_TRUSTED", not_trusted_count))
    return {
        "artifact_path": _artifact_path_label(path),
        "ready_for_owner_approval": (
            bool(units)
            and not open_units
            and distribution_partial == 0
            and distribution_not_trusted == 0
        ),
        "unit_count": len(units),
        "closed_count": closed_count,
        "partial_count": partial_count,
        "not_trusted_count": not_trusted_count,
        "excluded_count": excluded_count,
        "open_unit_count": len(open_units),
        "open_units": open_units,
        "distribution": distribution,
    }


def _closure_blocker_triage_artifact(path: Path) -> dict[str, object]:
    class_counts = {str(index): 0 for index in range(1, 6)}
    cursor_safe_counts = {
        "yes": 0,
        "no": 0,
        "partially": 0,
        "partially_complete": 0,
    }
    if not path.exists():
        return {
            "artifact_path": _artifact_path_label(path),
            "machine_readable": False,
            "blocker_count": 0,
            "class_counts": class_counts,
            "cursor_safe_counts": cursor_safe_counts,
            "decision_required_count": 0,
            "api_contract_required_count": 0,
            "out_of_scope_count": 0,
            "blockers": [],
        }

    text = path.read_text(encoding="utf-8")
    blockers = _closure_blocker_triage_rows(text)
    for blocker in blockers:
        blocker_class = blocker["class"]
        class_counts[blocker_class] = class_counts.get(blocker_class, 0) + 1
        cursor_safe = blocker["cursor_safe"]
        cursor_safe_counts[cursor_safe] = cursor_safe_counts.get(cursor_safe, 0) + 1
    return {
        "artifact_path": _artifact_path_label(path),
        "machine_readable": bool(blockers),
        "blocker_count": len(blockers),
        "class_counts": class_counts,
        "cursor_safe_counts": cursor_safe_counts,
        "decision_required_count": class_counts["1"],
        "api_contract_required_count": class_counts["2"],
        "out_of_scope_count": class_counts["5"],
        "blockers": blockers,
    }


def _closure_blocker_triage_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Unit | Blocker (from checklist) | Class |"):
            in_table = True
            continue
        if in_table and (line.startswith("## ") or line.startswith("### ")):
            break
        if not in_table or not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] == "---":
            continue
        rows.append(
            {
                "unit": cells[0],
                "blocker": _normalize_markdown_cell(cells[1]),
                "class": _normalize_markdown_cell(cells[2]),
                "minimal_next_action": _normalize_markdown_cell(cells[3]),
                "cursor_safe": _normalize_cursor_safe(cells[4]),
                "suggested_scope": _normalize_markdown_cell(cells[5]),
            }
        )
    return rows


def _normalize_markdown_cell(value: str) -> str:
    normalized = " ".join(value.strip().split())
    replacements = {
        "\u2192": "->",
        "\u2194": "<->",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a1\u00c1": "x",
        "\u00d7": "x",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _normalize_cursor_safe(value: str) -> str:
    normalized = _normalize_markdown_cell(value).lower()
    if normalized.startswith("yes"):
        return "yes"
    if normalized.startswith("no"):
        return "no"
    if normalized.startswith("partially complete"):
        return "partially_complete"
    if normalized.startswith("partially"):
        return "partially"
    return normalized.replace(" ", "_")


def _closure_checklist_units(text: str) -> list[dict[str, str]]:
    units: list[dict[str, str]] = []
    in_status_matrix = False
    for line in text.splitlines():
        if line.startswith("## 4. Status Matrix"):
            in_status_matrix = True
            continue
        if in_status_matrix and line.startswith("## "):
            break
        if not in_status_matrix or not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Unit", "---"}:
            continue
        units.append(
            {
                "unit": cells[0],
                "status": _normalize_value(cells[1]),
            }
        )
    return units


def _closure_checklist_distribution(text: str) -> dict[str, int]:
    distribution: dict[str, int] = {}
    in_distribution = False
    for line in text.splitlines():
        if line.startswith("## 6. Current Distribution"):
            in_distribution = True
            continue
        if in_distribution and line.startswith("## "):
            break
        if not in_distribution or not line.startswith("- `"):
            continue
        prefix = "- `"
        try:
            name, value = line[len(prefix) :].split("`:", maxsplit=1)
        except ValueError:
            continue
        try:
            distribution[name] = int(value.strip())
        except ValueError:
            continue
    return distribution


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
    golden_sample_approval_artifact: dict[str, object],
    closure_checklist_artifact: dict[str, object],
    certification_packet_consistency: dict[str, object],
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
    if _reviewed_artifact_status(text, "Reviewed boundary packet", EXPECTED_BOUNDARY_PACKET) != "valid":
        field_blockers.append("reviewed_boundary_packet")
    if (
        _reviewed_artifact_status(
            text,
            "Reviewed first-certification packet",
            EXPECTED_FIRST_CERTIFICATION_PACKET,
            required_freshness_markers=EXPECTED_FIRST_CERTIFICATION_FRESHNESS_MARKERS,
        )
        != "valid"
    ):
        field_blockers.append("reviewed_first_certification_packet")
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
        "- Owner decision packet reviewed": "reviewed_owner_decision_packet",
        "- Owner decision next-review queue acknowledged": (
            "owner_decision_next_review_queue_acknowledgement"
        ),
        "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled": "golden_sample_artifact_reconciliation",
        "- Closure checklist units reviewed": "closure_checklist_review",
        "- Fallback liability branch model-boundary evidence reviewed": "fallback_liability_branch_boundary_review",
        "- UI/API payload evidence reviewed": "ui_api_payload_review",
        "- Live smoke evidence reviewed": "live_smoke_evidence_review",
        "- Verification commands rerun before approval": "verification_commands_rerun",
        "- Evidence-pending boundary accepted": "evidence_pending_boundary_acceptance",
    }
    for label, blocker in review_fields.items():
        if not _review_is_yes(text, label):
            field_blockers.append(blocker)
    if (
        "reviewed_owner_decision_packet" not in field_blockers
        and _generated_artifact_status(EXPECTED_OWNER_DECISION_PACKET) != "valid"
    ):
        field_blockers.append("reviewed_owner_decision_packet")
    if (
        not golden_sample_approval_artifact["approved"]
        and "golden_sample_artifact_reconciliation" not in field_blockers
    ):
        field_blockers.append("golden_sample_artifact_reconciliation")
    if (
        not closure_checklist_artifact["ready_for_owner_approval"]
        and "closure_checklist_review" not in field_blockers
    ):
        field_blockers.append("closure_checklist_review")
    if (
        certification_packet_consistency["status"] != "valid"
        and "reviewed_first_certification_packet" not in field_blockers
        and "reviewed_owner_decision_packet" not in field_blockers
    ):
        field_blockers.append("certification_packet_consistency")

    if formal_use_allowed != "true":
        field_blockers.append("formal_use_boundary")
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
    golden_sample_approval_artifact: dict[str, object],
    closure_checklist_artifact: dict[str, object],
    certification_packet_consistency: dict[str, object],
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
        "reviewed_boundary_packet": _reviewed_artifact_status(
            text,
            "Reviewed boundary packet",
            EXPECTED_BOUNDARY_PACKET,
        ),
        "reviewed_first_certification_packet": _reviewed_artifact_status(
            text,
            "Reviewed first-certification packet",
            EXPECTED_FIRST_CERTIFICATION_PACKET,
            required_freshness_markers=EXPECTED_FIRST_CERTIFICATION_FRESHNESS_MARKERS,
        ),
        "governance_record_review": _review_status(text, "- Governance record reviewed"),
        "reviewed_owner_decision_packet": _owner_decision_packet_review_status(text),
        "owner_decision_next_review_queue_acknowledgement": _review_status(
            text,
            "- Owner decision next-review queue acknowledged",
        ),
        "golden_sample_artifact_reconciliation": _golden_sample_artifact_reconciliation_status(
            text,
            golden_sample_approval_artifact,
        ),
        "closure_checklist_review": _closure_checklist_review_status(text, closure_checklist_artifact),
        "fallback_liability_branch_boundary_review": _review_status(
            text,
            "- Fallback liability branch model-boundary evidence reviewed",
        ),
        "ui_api_payload_review": _review_status(text, "- UI/API payload evidence reviewed"),
        "live_smoke_evidence_review": _review_status(text, "- Live smoke evidence reviewed"),
        "verification_commands_rerun": _review_status(text, "- Verification commands rerun before approval"),
        "evidence_pending_boundary_acceptance": _review_status(text, "- Evidence-pending boundary accepted"),
        "certification_packet_consistency": str(certification_packet_consistency["status"]),
        "decision_notes": _decision_notes_status(text, approval_decision),
        "formal_use_allowed": "valid" if formal_use_allowed == "true" else "invalid",
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


def _business_owner_action_signoff_summary(
    approval_action_items: list[dict[str, str]],
    *,
    formal_use_allowed: bool,
    closure_approved: bool,
) -> dict[str, object]:
    signed_count = sum(
        1 for item in approval_action_items if item["current_status"] == "valid"
    )
    invalid_or_missing_count = sum(
        1
        for item in approval_action_items
        if item["current_status"] in {"missing", "invalid"}
        or item["current_status"].startswith("missing_")
        or item["current_status"].startswith("artifact_")
        or item["current_status"].startswith("stale_")
    )
    group_counts = _signoff_group_counts(approval_action_items)
    signed_group_counts = _signoff_group_counts(
        [
            item
            for item in approval_action_items
            if item["current_status"] == "valid"
        ]
    )
    unsigned_group_counts = _signoff_group_counts(
        [
            item
            for item in approval_action_items
            if item["current_status"] != "valid"
        ]
    )
    unsigned_count = len(approval_action_items) - signed_count
    pending_review_count = unsigned_count - invalid_or_missing_count
    return {
        "summary_kind": "business_owner_action_signoff_summary",
        "action_item_count": len(approval_action_items),
        "signed_item_count": signed_count,
        "unsigned_item_count": unsigned_count,
        "invalid_or_missing_item_count": invalid_or_missing_count,
        "pending_item_count": pending_review_count,
        "missing_or_invalid_item_count": invalid_or_missing_count,
        "pending_review_item_count": pending_review_count,
        "signoff_group_counts": group_counts,
        "signed_group_counts": signed_group_counts,
        "unsigned_group_counts": unsigned_group_counts,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "formal_use_allowed": formal_use_allowed,
        "closure_approved": closure_approved,
        "certification_blocked": True,
        "boundary": (
            "Approval checker signoff summary is evidence only; only current_status=valid "
            "counts as signed, unsigned items still block business-owner approval capture, "
            "and formal_use_allowed=true does not bypass closure_approved=false."
        ),
    }


def _signoff_group_counts(
    approval_action_items: list[dict[str, str]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in approval_action_items:
        group = ACTION_SIGNOFF_GROUPS[item["blocker"]]
        counts[group] = counts.get(group, 0) + 1
    return dict(sorted(counts.items()))


def _pre_signature_signoff_group(blocker: str) -> str:
    return ACTION_SIGNOFF_GROUPS[blocker]


def _pre_signature_checklist_group_counts(
    checklist_items: list[dict[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in checklist_items:
        group = str(item["signoff_group"])
        counts[group] = counts.get(group, 0) + 1
    return dict(sorted(counts.items()))


def _owner_pre_signature_blocker_scope(
    remaining_blockers: list[str],
    approval_action_items: list[dict[str, str]],
    signoff_summary: dict[str, object],
) -> dict[str, object]:
    checklist_items = [
        {
            "blocker": item["blocker"],
            "signoff_group": _pre_signature_signoff_group(item["blocker"]),
            "template_field": item["template_field"],
            "required_value": item["required_value"],
            "current_status": item["current_status"],
            "blocks_owner_signature": True,
            "certification_effect": "none",
        }
        for item in approval_action_items
    ]
    signed_checklist_items = [
        item for item in checklist_items if item["current_status"] == "valid"
    ]
    unsigned_checklist_items = [
        item for item in checklist_items if item["current_status"] != "valid"
    ]
    return {
        "scope_kind": "owner_pre_signature_blocker_scope",
        "remaining_blocker_count": len(remaining_blockers),
        "remaining_blockers": list(remaining_blockers),
        "approval_action_item_count": len(approval_action_items),
        "approval_action_blockers": [item["blocker"] for item in approval_action_items],
        "signed_item_count": signoff_summary["signed_item_count"],
        "unsigned_item_count": signoff_summary["unsigned_item_count"],
        "missing_or_invalid_item_count": signoff_summary[
            "missing_or_invalid_item_count"
        ],
        "pending_review_item_count": signoff_summary["pending_review_item_count"],
        "signoff_group_counts": _pre_signature_checklist_group_counts(checklist_items),
        "signed_group_counts": _pre_signature_checklist_group_counts(signed_checklist_items),
        "unsigned_group_counts": _pre_signature_checklist_group_counts(unsigned_checklist_items),
        "checklist_items": checklist_items,
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "captures_product_or_api_decisions": False,
        "can_promote_certification": False,
        "certification_effect": "none",
        "boundary": (
            "Owner pre-signature blocker scope is a checklist boundary only; it does not "
            "approve, sign, certify, or capture product/API decisions."
        ),
    }


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


def _owner_decision_packet_review_status(text: str) -> str:
    review_status = _review_status(text, "- Owner decision packet reviewed")
    if review_status != "valid":
        return review_status
    return _generated_artifact_status(EXPECTED_OWNER_DECISION_PACKET)


def _generated_artifact_status(path_label: str) -> str:
    return str(
        _generated_artifact_freshness(
            path_label,
            EXPECTED_OWNER_DECISION_FRESHNESS_MARKERS,
        )["freshness_status"]
    )


def _generated_artifacts_freshness() -> dict[str, dict[str, object]]:
    return {
        "first_certification_packet": _generated_artifact_freshness(
            EXPECTED_FIRST_CERTIFICATION_PACKET,
            EXPECTED_FIRST_CERTIFICATION_FRESHNESS_MARKERS,
        ),
        "owner_decision_packet": _generated_artifact_freshness(
            EXPECTED_OWNER_DECISION_PACKET,
            EXPECTED_OWNER_DECISION_FRESHNESS_MARKERS,
        ),
    }


def _generated_artifact_freshness_scope(
    generated_artifact_freshness: dict[str, dict[str, object]],
) -> dict[str, object]:
    artifact_count = len(generated_artifact_freshness)
    valid_artifact_count = sum(
        1
        for artifact in generated_artifact_freshness.values()
        if artifact.get("freshness_status") == "valid"
    )
    return {
        "scope_kind": "generated_artifact_freshness_scope",
        "artifact_count": artifact_count,
        "valid_artifact_count": valid_artifact_count,
        "stale_or_missing_artifact_count": artifact_count - valid_artifact_count,
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


def _certification_packet_consistency(template_text: str, template_path: Path) -> dict[str, object]:
    first_path = ROOT / EXPECTED_FIRST_CERTIFICATION_PACKET
    owner_path = ROOT / EXPECTED_OWNER_DECISION_PACKET
    missing_markers: list[str] = []
    first_text = first_path.read_text(encoding="utf-8") if first_path.exists() else ""
    owner_text = owner_path.read_text(encoding="utf-8") if owner_path.exists() else ""

    first_formal_count = _backtick_assignment_int(first_text, "formal_decision_item_count")
    first_next_review_count = _backtick_assignment_int(first_text, "next_review_queue_item_count")
    owner_formal_count = _backtick_assignment_int(owner_text, "formal_decision_item_count")
    owner_next_review_count = _backtick_assignment_int(owner_text, "next_review_queue_item_count")
    approval_action_count = _backtick_assignment_int(first_text, "approval_action_item_count")
    signoff_count = _backtick_assignment_int(first_text, "business_owner_action_signoff_item_count")
    signoff_signed_count = _signoff_matrix_assignment_int(first_text, "signed_item_count")
    signoff_pending_or_missing_count = _signoff_matrix_assignment_int(
        first_text,
        "pending_or_missing_item_count",
    )
    signoff_missing_or_invalid_count = _signoff_matrix_assignment_int(
        first_text,
        "missing_or_invalid_item_count",
    )
    signoff_pending_review_count = _signoff_matrix_assignment_int(
        first_text,
        "pending_review_item_count",
    )

    formal_count = owner_formal_count if owner_formal_count is not None else first_formal_count
    next_review_count = (
        owner_next_review_count if owner_next_review_count is not None else first_next_review_count
    )
    if formal_count is None:
        missing_markers.append("owner_decision_packet:formal_decision_item_count")
        formal_count = 0
    if next_review_count is None:
        missing_markers.append("owner_decision_packet:next_review_queue_item_count")
        next_review_count = 0
    if first_formal_count != formal_count:
        missing_markers.append("first_certification_packet:formal_decision_item_count")
    if first_next_review_count != next_review_count:
        missing_markers.append("first_certification_packet:next_review_queue_item_count")
    if approval_action_count is None:
        missing_markers.append("first_certification_packet:approval_action_item_count")
        approval_action_count = 0
    if signoff_count is None:
        missing_markers.append("first_certification_packet:business_owner_action_signoff_item_count")
        signoff_count = 0
    if approval_action_count != signoff_count:
        missing_markers.append("first_certification_packet:approval_action_count_matches_signoff_count")
    if signoff_signed_count != 0:
        missing_markers.append("first_certification_packet:signed_item_count=0")
    if signoff_pending_or_missing_count != approval_action_count:
        missing_markers.append(
            f"first_certification_packet:pending_or_missing_item_count={approval_action_count}"
        )
    if signoff_missing_or_invalid_count is None:
        missing_markers.append(
            "first_certification_packet:business_owner_action_signoff_matrix:missing_or_invalid_item_count"
        )
    if signoff_pending_review_count is None:
        missing_markers.append(
            "first_certification_packet:business_owner_action_signoff_matrix:pending_review_item_count"
        )
    if (
        signoff_missing_or_invalid_count is not None
        and signoff_pending_review_count is not None
        and signoff_pending_or_missing_count is not None
        and signoff_missing_or_invalid_count + signoff_pending_review_count
        != signoff_pending_or_missing_count
    ):
        missing_markers.append(
            "first_certification_packet:business_owner_action_signoff_matrix:status_split_matches_pending_or_missing"
        )
    for name in (
        "owner_signable",
        "captures_business_owner_approval",
        "can_promote_certification",
    ):
        value = _section_backtick_assignment_bool(
            first_text,
            "## Business Owner Action Signoff Matrix",
            name,
        )
        if value is not False:
            missing_markers.append(
                f"first_certification_packet:business_owner_action_signoff_matrix:{name}=false"
            )
    for phrase, marker in {
        "owner_reviewer_receipt_item_count=9": (
            "first_certification_packet:owner_reviewer_receipt_item_count"
        ),
        "referenced_approval_field_count=17": (
            "first_certification_packet:referenced_approval_field_count"
        ),
        "all_referenced_fields_known=true": (
            "first_certification_packet:all_referenced_fields_known=true"
        ),
    }.items():
        if phrase not in first_text:
            missing_markers.append(marker)
    if not _missing_approval_action_fields_section_is_none(first_text):
        missing_markers.append("first_certification_packet:missing_approval_action_fields=none")

    count_phrase = (
        f"{formal_count} formal decision items plus "
        f"{next_review_count} next-review queue topics"
    )
    if count_phrase not in template_text:
        missing_markers.append("approval_template:formal_next_review_count_phrase")
    if count_phrase not in first_text:
        missing_markers.append("first_certification_packet:formal_next_review_count_phrase")

    boundary_expectations = {
        "owner_signable": False,
        "captures_business_owner_approval": False,
        "can_promote_certification": False,
        "verification_commands_rerun_captured": False,
    }
    for name, expected in boundary_expectations.items():
        value = _backtick_assignment_bool(first_text, name)
        if value is not expected:
            missing_markers.append(f"first_certification_packet:{name}=false")
    for phrase, marker in {
        "owner_signable=false": "approval_template:owner_signable=false",
        "can_promote_certification=false": "approval_template:can_promote_certification=false",
        "verification_commands_rerun_captured=false": (
            "approval_template:verification_commands_rerun_captured=false"
        ),
        "captures_business_owner_approval=false": (
            "approval_template:captures_business_owner_approval=false"
        ),
    }.items():
        if phrase not in template_text:
            missing_markers.append(marker)

    if not first_path.exists():
        status = "missing_artifact"
        missing_markers.append("first_certification_packet:missing_artifact")
    elif not owner_path.exists():
        status = "missing_artifact"
        missing_markers.append("owner_decision_packet:missing_artifact")
    elif missing_markers:
        status = "stale_generated_artifact"
    else:
        status = "valid"
    return {
        "consistency_kind": "product_category_pnl_certification_packet_consistency",
        "status": status,
        "missing_markers": missing_markers,
        "template_path": _artifact_path_label(template_path),
        "first_certification_packet_path": EXPECTED_FIRST_CERTIFICATION_PACKET,
        "owner_decision_packet_path": EXPECTED_OWNER_DECISION_PACKET,
        "formal_decision_item_count": formal_count,
        "next_review_queue_item_count": next_review_count,
        "approval_action_item_count": approval_action_count,
        "business_owner_action_signoff_item_count": signoff_count,
        "business_owner_action_signed_item_count": (
            signoff_signed_count if signoff_signed_count is not None else 0
        ),
        "business_owner_action_pending_or_missing_item_count": (
            signoff_pending_or_missing_count
            if signoff_pending_or_missing_count is not None
            else 0
        ),
        "business_owner_action_missing_or_invalid_item_count": (
            signoff_missing_or_invalid_count
            if signoff_missing_or_invalid_count is not None
            else 0
        ),
        "business_owner_action_pending_review_item_count": (
            signoff_pending_review_count
            if signoff_pending_review_count is not None
            else 0
        ),
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


def _signoff_matrix_assignment_int(text: str, name: str) -> int | None:
    section_value = _section_backtick_assignment_int(
        text,
        "## Business Owner Action Signoff Matrix",
        name,
    )
    if section_value is not None:
        return section_value
    return _backtick_assignment_int(text, name)


def _section_backtick_assignment_int(text: str, section_heading: str, name: str) -> int | None:
    section = _markdown_section(text, section_heading)
    if section is None:
        return None
    return _backtick_assignment_int(section, name)


def _section_backtick_assignment_bool(text: str, section_heading: str, name: str) -> bool | None:
    section = _markdown_section(text, section_heading)
    if section is None:
        return None
    return _backtick_assignment_bool(section, name)


def _markdown_section(text: str, section_heading: str) -> str | None:
    lines = text.splitlines()
    in_section = False
    section_lines: list[str] = []
    for line in lines:
        if line == section_heading:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            section_lines.append(line)
    if not in_section:
        return None
    return "\n".join(section_lines)


def _missing_approval_action_fields_section_is_none(text: str) -> bool:
    try:
        section = text.split("Missing approval action fields:", maxsplit=1)[1]
    except IndexError:
        return False
    section = section.split("\n## ", maxsplit=1)[0]
    entries = [line.strip() for line in section.splitlines() if line.strip()]
    return entries == ["- `none`"]


def _backtick_assignment_int(text: str, name: str) -> int | None:
    value = _backtick_assignment_value(text, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _backtick_assignment_bool(text: str, name: str) -> bool | None:
    value = _backtick_assignment_value(text, name)
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _backtick_assignment_value(text: str, name: str) -> str | None:
    needle = f"`{name}="
    for line in text.splitlines():
        start = line.find(needle)
        if start == -1:
            continue
        value_start = start + len(needle)
        value_end = line.find("`", value_start)
        if value_end == -1:
            continue
        return line[value_start:value_end]
    return None


def _generated_artifact_freshness(
    path_label: str,
    required_markers: list[str],
) -> dict[str, object]:
    path = ROOT / path_label
    exists = path.exists()
    missing_markers: list[str]
    if exists:
        text = path.read_text(encoding="utf-8")
        missing_markers = [
            marker for marker in required_markers if marker not in text
        ]
    else:
        missing_markers = list(required_markers)
    if not exists:
        freshness_status = "missing_artifact"
    elif missing_markers:
        freshness_status = "stale_generated_artifact"
    else:
        freshness_status = "valid"
    return {
        "artifact_path": path_label,
        "exists": exists,
        "freshness_status": freshness_status,
        "missing_markers": missing_markers,
    }


def _has_freshness_markers(path: Path, markers: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    return all(marker in text for marker in markers)


def _golden_sample_artifact_reconciliation_status(
    text: str,
    golden_sample_approval_artifact: dict[str, object],
) -> str:
    review_status = _review_status(
        text,
        "- Golden sample `GS-PROD-CAT-PNL-A` approval artifact reconciled",
    )
    if review_status != "valid":
        return review_status
    if golden_sample_approval_artifact["approved"]:
        return "valid"
    return "artifact_pending"


def _closure_checklist_review_status(
    text: str,
    closure_checklist_artifact: dict[str, object],
) -> str:
    review_status = _review_status(text, "- Closure checklist units reviewed")
    if review_status != "valid":
        return review_status
    if closure_checklist_artifact["ready_for_owner_approval"]:
        return "valid"
    return "artifact_partial"


def _decision_notes_status(text: str, approval_decision: str) -> str:
    if approval_decision not in {"reject", "request_changes"}:
        return "not_required"
    return "valid" if _plain_value_is_filled(text, "Decision notes") else "missing"


def build_status(
    template_path: Path,
    *,
    golden_sample_approval_path: Path = DEFAULT_GOLDEN_SAMPLE_APPROVAL,
    closure_checklist_path: Path = DEFAULT_CLOSURE_CHECKLIST,
    closure_blocker_triage_path: Path = DEFAULT_CLOSURE_BLOCKER_TRIAGE,
) -> dict[str, object]:
    text = template_path.read_text(encoding="utf-8")
    approval_status = _extract_assignment(_extract_code_value(text, "Approval status"), "approval_status")
    formal_use_allowed = _extract_assignment(_extract_code_value(text, "Formal use allowed"), "formal_use_allowed")
    closure_approved = _extract_assignment(_extract_code_value(text, "Closure approved"), "closure_approved")
    golden_sample_approval_artifact = _golden_sample_approval_artifact(golden_sample_approval_path)
    closure_checklist_artifact = _closure_checklist_artifact(closure_checklist_path)
    closure_blocker_triage = _closure_blocker_triage_artifact(closure_blocker_triage_path)
    certification_packet_consistency = _certification_packet_consistency(text, template_path)

    remaining_blockers = _approval_blockers(
        text,
        approval_status,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        golden_sample_approval_artifact=golden_sample_approval_artifact,
        closure_checklist_artifact=closure_checklist_artifact,
        certification_packet_consistency=certification_packet_consistency,
    )
    approval_field_status = _approval_field_status(
        text,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        golden_sample_approval_artifact=golden_sample_approval_artifact,
        closure_checklist_artifact=closure_checklist_artifact,
        certification_packet_consistency=certification_packet_consistency,
    )
    approval_action_items = _approval_action_items(remaining_blockers, approval_field_status)
    approval_captured = approval_status == "approved" and not remaining_blockers
    business_owner_action_signoff_summary = _business_owner_action_signoff_summary(
        approval_action_items,
        formal_use_allowed=formal_use_allowed == "true",
        closure_approved=closure_approved == "true",
    )
    generated_artifact_freshness = _generated_artifacts_freshness()
    return {
        "page_id": _extract_code_value(text, "Page ID"),
        "page_slug": _extract_code_value(text, "Page slug"),
        "primary_api": _extract_code_value(text, "Primary API"),
        "approval_check": _extract_code_value(text, "Approval check"),
        "approval_status": approval_status,
        "business_owner_approval_captured": approval_captured,
        "formal_use_allowed": formal_use_allowed == "true",
        "closure_approved": closure_approved == "true",
        "golden_sample_approval_artifact": golden_sample_approval_artifact,
        "closure_checklist_artifact": closure_checklist_artifact,
        "closure_blocker_triage": closure_blocker_triage,
        "generated_artifact_freshness": generated_artifact_freshness,
        "generated_artifact_freshness_scope": _generated_artifact_freshness_scope(
            generated_artifact_freshness
        ),
        "certification_packet_consistency": certification_packet_consistency,
        "remaining_blockers": remaining_blockers,
        "approval_field_status": approval_field_status,
        "approval_action_items": approval_action_items,
        "approval_action_item_count": len(approval_action_items),
        "business_owner_action_signoff_summary": business_owner_action_signoff_summary,
        "owner_pre_signature_blocker_scope": _owner_pre_signature_blocker_scope(
            remaining_blockers,
            approval_action_items,
            business_owner_action_signoff_summary,
        ),
        "owner_action_status_scope": {
            "scope_kind": "owner_action_status_scope",
            "missing_or_invalid_item_count": business_owner_action_signoff_summary[
                "missing_or_invalid_item_count"
            ],
            "pending_review_item_count": business_owner_action_signoff_summary[
                "pending_review_item_count"
            ],
            "owner_signable": False,
            "captures_business_owner_approval": False,
            "captures_product_or_api_decisions": False,
            "can_promote_certification": False,
            "certification_effect": "none",
            "boundary": (
                "Owner-action status split is approval-checker evidence only; it does not "
                "capture business-owner approval, product/API decisions, or route certification."
            ),
        },
        "template_path": str(template_path),
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": approval_captured,
            "captures_product_or_api_decisions": False,
            "certification_effect": "none",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the product-category-pnl business-owner approval template and report its current status.",
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
    parser.add_argument(
        "--golden-sample-approval-path",
        type=Path,
        default=DEFAULT_GOLDEN_SAMPLE_APPROVAL,
        help="Path to the GS-PROD-CAT-PNL-A approval artifact.",
    )
    parser.add_argument(
        "--closure-checklist-path",
        type=Path,
        default=DEFAULT_CLOSURE_CHECKLIST,
        help="Path to the product-category closure checklist artifact.",
    )
    parser.add_argument(
        "--closure-blocker-triage-path",
        type=Path,
        default=DEFAULT_CLOSURE_BLOCKER_TRIAGE,
        help="Path to the product-category remaining-blocker triage artifact.",
    )
    args = parser.parse_args(argv)

    status = build_status(
        Path(args.template_path),
        golden_sample_approval_path=Path(args.golden_sample_approval_path),
        closure_checklist_path=Path(args.closure_checklist_path),
        closure_blocker_triage_path=Path(args.closure_blocker_triage_path),
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if args.require_captured and not status["business_owner_approval_captured"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
