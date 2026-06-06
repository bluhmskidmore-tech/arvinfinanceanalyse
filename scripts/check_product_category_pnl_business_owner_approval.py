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


def _reviewed_artifact_status(text: str, label: str, expected_path: str) -> str:
    if _plain_value(text, label) != expected_path:
        return "invalid"
    if not (ROOT / expected_path).exists():
        return "missing_artifact"
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
        and not (ROOT / EXPECTED_OWNER_DECISION_PACKET).exists()
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
        ),
        "governance_record_review": _review_status(text, "- Governance record reviewed"),
        "reviewed_owner_decision_packet": _owner_decision_packet_review_status(text),
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
    if (ROOT / EXPECTED_OWNER_DECISION_PACKET).exists():
        return "valid"
    return "missing_artifact"


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

    remaining_blockers = _approval_blockers(
        text,
        approval_status,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        golden_sample_approval_artifact=golden_sample_approval_artifact,
        closure_checklist_artifact=closure_checklist_artifact,
    )
    approval_field_status = _approval_field_status(
        text,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        golden_sample_approval_artifact=golden_sample_approval_artifact,
        closure_checklist_artifact=closure_checklist_artifact,
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
        "golden_sample_approval_artifact": golden_sample_approval_artifact,
        "closure_checklist_artifact": closure_checklist_artifact,
        "closure_blocker_triage": closure_blocker_triage,
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
