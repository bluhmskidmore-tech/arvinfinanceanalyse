from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import TypedDict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
DEFAULT_REPORT_DATE = "2026-05-31"
EXPECTED_SIGNOFF_PACKET = "docs/portfolio/portfolio-home-full-closure-sign-off-packet.md"
EXPECTED_AUDIT_PACKET = "docs/audits/2026-06-05-portfolio-readiness-gate-audit.md"

VALID_KRD_DECISIONS = {"approve_nearest_bucket", "require_exact_bucket_schema", "reject"}
VALID_MATURITY_DECISIONS = {"remediate_source", "approve_scoped_exclusion", "reject"}
VALID_WARNING_DECISIONS = {"keep_warning", "approve_after_clean_rerun"}
NOTE_REQUIRED_DECISIONS = {"reject", "request_changes", "approve_nearest_bucket", "approve_scoped_exclusion"}

ACTION_ITEM_DEFINITIONS = {
    "business_owner_name": {
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
    },
    "business_owner_role": {
        "template_field": "Business owner role",
        "required_value": "Business owner accountability role",
    },
    "risk_owner_name": {
        "template_field": "Risk owner name",
        "required_value": "Risk owner legal or operating name",
    },
    "risk_owner_role": {
        "template_field": "Risk owner role",
        "required_value": "Risk owner accountability role",
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
    "risk_owner_signature": {
        "template_field": "Risk owner signature",
        "required_value": "Risk owner signature",
    },
    "reviewed_signoff_packet": {
        "template_field": "Reviewed sign-off packet",
        "required_value": EXPECTED_SIGNOFF_PACKET,
    },
    "reviewed_audit_packet": {
        "template_field": "Reviewed audit packet",
        "required_value": EXPECTED_AUDIT_PACKET,
    },
    "krd_contract_decision": {
        "template_field": "KRD contract decision",
        "required_value": "approve_nearest_bucket, require_exact_bucket_schema, or reject",
    },
    "maturity_data_decision": {
        "template_field": "Maturity data decision",
        "required_value": "remediate_source, approve_scoped_exclusion, or reject",
    },
    "risk_tensor_warning_decision": {
        "template_field": "Risk tensor warning decision",
        "required_value": "keep_warning or approve_after_clean_rerun",
    },
    "governance_record_review": {
        "template_field": "- Governance record reviewed",
        "required_value": "yes",
    },
    "portfolio_sample_review": {
        "template_field": "- Supporting sample `GS-PORTFOLIO-HOME-A` reviewed",
        "required_value": "yes",
    },
    "risk_warning_sample_review": {
        "template_field": "- Risk warning sample `GS-RISK-WARN-B` reviewed",
        "required_value": "yes",
    },
    "live_proof_review": {
        "template_field": "- Live proof reviewed",
        "required_value": "yes",
    },
    "duckdb_maturity_gap_review": {
        "template_field": "- DuckDB maturity-gap evidence reviewed",
        "required_value": "yes",
    },
    "krd_remap_evidence_review": {
        "template_field": "- KRD remap evidence reviewed",
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
        "required_value": "Required for request changes, nearest-bucket approval, or scoped exclusion",
    },
    "formal_use_allowed": {
        "template_field": "Formal use allowed",
        "required_value": "formal_use_allowed=false for candidate review or formal_use_allowed=true for full page approval",
    },
    "closure_approved": {
        "template_field": "Closure approved",
        "required_value": "closure_approved=false for candidate review or closure_approved=true for full page approval",
    },
    "evidence_scope_approves_metric_or_page": {
        "template_field": "- `approves_metric_or_page=...`",
        "required_value": "false for candidate review or true for full page approval",
    },
    "evidence_scope_writes_governance_records": {
        "template_field": "- `writes_governance_records=...`",
        "required_value": "false for candidate review or true for full page approval",
    },
    "evidence_scope_proves_capture_ready_page_execution": {
        "template_field": "- `proves_capture_ready_page_execution=...`",
        "required_value": "false for candidate review or true for full page approval",
    },
    "evidence_scope_captures_business_owner_approval": {
        "template_field": "- `captures_business_owner_approval=...`",
        "required_value": "true once business-owner approval is explicitly captured",
    },
    "evidence_scope_certification_effect": {
        "template_field": "- `certification_effect=...`",
        "required_value": "none",
    },
}


class EvidenceScopeClaims(TypedDict):
    approves_metric_or_page: bool
    writes_governance_records: bool
    proves_capture_ready_page_execution: bool
    captures_business_owner_approval: bool
    certification_effect: str


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


def _extract_bulleted_assignment(text: str, name: str) -> str:
    prefix = f"- `{name}="
    for line in text.splitlines():
        if line.startswith(prefix) and line.endswith("`"):
            return line[len("- `") : -1]
    raise ValueError(f"Missing required approval template evidence-scope field: {name}")


def _extract_plain_value(text: str, label: str) -> str:
    prefix = f"{label}: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise ValueError(f"Missing required approval template field: {label}")


def _normalize_value(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def _is_placeholder(value: str) -> bool:
    stripped = _normalize_value(value)
    return stripped.startswith("<") and stripped.endswith(">")


def _plain_value(text: str, label: str) -> str:
    return _normalize_value(_extract_plain_value(text, label))


def _plain_value_is_filled(text: str, label: str) -> bool:
    return not _is_placeholder(_plain_value(text, label))


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


def _approval_decision_status(value: str) -> str:
    if _is_placeholder(value):
        return "missing"
    return "valid" if value == "approve" else "invalid"


def _approval_date_status(text: str, report_date: str) -> str:
    if not _plain_value_is_filled(text, "Approval date"):
        return "missing"
    if not _approval_date_is_valid(text):
        return "invalid"
    approval_date = date.fromisoformat(_plain_value(text, "Approval date"))
    anchor_date = date.fromisoformat(report_date)
    return "valid" if approval_date >= anchor_date else "stale"


def _review_status(text: str, label: str) -> str:
    return "valid" if _review_is_yes(text, label) else "pending"


def _choice_status(value: str, valid_values: set[str]) -> str:
    if _is_placeholder(value):
        return "missing"
    return "valid" if value in valid_values else "invalid"


def _warning_decision_status(value: str, *, full_page_approval_requested: bool) -> str:
    base_status = _choice_status(value, VALID_WARNING_DECISIONS)
    if base_status != "valid":
        return base_status
    if full_page_approval_requested and value != "approve_after_clean_rerun":
        return "invalid_for_full_approval"
    return "valid"


def _bool_assignment(value: str, name: str) -> bool:
    extracted = _extract_assignment(value, name)
    if extracted == "true":
        return True
    if extracted == "false":
        return False
    raise ValueError(f"Expected {name}=true|false but found {value!r}")


def _evidence_scope_claims(text: str) -> EvidenceScopeClaims:
    return {
        "approves_metric_or_page": _bool_assignment(
            _extract_bulleted_assignment(text, "approves_metric_or_page"),
            "approves_metric_or_page",
        ),
        "writes_governance_records": _bool_assignment(
            _extract_bulleted_assignment(text, "writes_governance_records"),
            "writes_governance_records",
        ),
        "proves_capture_ready_page_execution": _bool_assignment(
            _extract_bulleted_assignment(text, "proves_capture_ready_page_execution"),
            "proves_capture_ready_page_execution",
        ),
        "captures_business_owner_approval": _bool_assignment(
            _extract_bulleted_assignment(text, "captures_business_owner_approval"),
            "captures_business_owner_approval",
        ),
        "certification_effect": _extract_assignment(
            _extract_bulleted_assignment(text, "certification_effect"),
            "certification_effect",
        ),
    }


def _full_page_approval_requested(
    *,
    formal_use_allowed: str,
    closure_approved: str,
    evidence_scope_claims: EvidenceScopeClaims,
) -> bool:
    return (
        formal_use_allowed == "true"
        or closure_approved == "true"
        or evidence_scope_claims["approves_metric_or_page"]
    )


def _decision_notes_required(*, approval_decision: str, krd_decision: str, maturity_decision: str) -> bool:
    return bool(
        {approval_decision, krd_decision, maturity_decision} & NOTE_REQUIRED_DECISIONS
    )


def _decision_notes_status(
    text: str,
    *,
    approval_decision: str,
    krd_decision: str,
    maturity_decision: str,
) -> str:
    if not _decision_notes_required(
        approval_decision=approval_decision,
        krd_decision=krd_decision,
        maturity_decision=maturity_decision,
    ):
        return "not_required"
    return "valid" if _plain_value_is_filled(text, "Decision notes") else "missing"


def _approval_field_status(
    text: str,
    *,
    approval_status: str,
    formal_use_allowed: str,
    closure_approved: str,
    evidence_scope_claims: EvidenceScopeClaims,
    report_date: str,
) -> dict[str, str]:
    approval_decision = _plain_value(text, "Approval decision")
    krd_decision = _plain_value(text, "KRD contract decision")
    maturity_decision = _plain_value(text, "Maturity data decision")
    warning_decision = _plain_value(text, "Risk tensor warning decision")
    full_page_approval_requested = _full_page_approval_requested(
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        evidence_scope_claims=evidence_scope_claims,
    )

    status: dict[str, str] = {
        "business_owner_name": "valid" if _plain_value_is_filled(text, "Business owner name") else "missing",
        "business_owner_role": "valid" if _plain_value_is_filled(text, "Business owner role") else "missing",
        "risk_owner_name": "valid" if _plain_value_is_filled(text, "Risk owner name") else "missing",
        "risk_owner_role": "valid" if _plain_value_is_filled(text, "Risk owner role") else "missing",
        "approval_decision": _approval_decision_status(approval_decision),
        "approval_date": _approval_date_status(text, report_date),
        "business_owner_signature": (
            "valid" if _plain_value_is_filled(text, "Business owner signature") else "missing"
        ),
        "risk_owner_signature": (
            "valid" if _plain_value_is_filled(text, "Risk owner signature") else "missing"
        ),
        "reviewed_signoff_packet": (
            "valid" if _plain_value(text, "Reviewed sign-off packet") == EXPECTED_SIGNOFF_PACKET else "invalid"
        ),
        "reviewed_audit_packet": (
            "valid" if _plain_value(text, "Reviewed audit packet") == EXPECTED_AUDIT_PACKET else "invalid"
        ),
        "krd_contract_decision": _choice_status(krd_decision, VALID_KRD_DECISIONS),
        "maturity_data_decision": _choice_status(maturity_decision, VALID_MATURITY_DECISIONS),
        "risk_tensor_warning_decision": _warning_decision_status(
            warning_decision,
            full_page_approval_requested=full_page_approval_requested,
        ),
        "governance_record_review": _review_status(text, "- Governance record reviewed"),
        "portfolio_sample_review": _review_status(text, "- Supporting sample `GS-PORTFOLIO-HOME-A` reviewed"),
        "risk_warning_sample_review": _review_status(text, "- Risk warning sample `GS-RISK-WARN-B` reviewed"),
        "live_proof_review": _review_status(text, "- Live proof reviewed"),
        "duckdb_maturity_gap_review": _review_status(text, "- DuckDB maturity-gap evidence reviewed"),
        "krd_remap_evidence_review": _review_status(text, "- KRD remap evidence reviewed"),
        "verification_commands_rerun": _review_status(text, "- Verification commands rerun before approval"),
        "candidate_boundary_acceptance": _review_status(text, "- Candidate-only boundary accepted"),
        "decision_notes": _decision_notes_status(
            text,
            approval_decision=approval_decision,
            krd_decision=krd_decision,
            maturity_decision=maturity_decision,
        ),
        "formal_use_allowed": (
            "valid" if (formal_use_allowed == "true") == full_page_approval_requested else "invalid"
        ),
        "closure_approved": (
            "valid" if (closure_approved == "true") == full_page_approval_requested else "invalid"
        ),
        "evidence_scope_approves_metric_or_page": (
            "valid"
            if evidence_scope_claims["approves_metric_or_page"] == full_page_approval_requested
            else "invalid"
        ),
        "evidence_scope_writes_governance_records": (
            "valid"
            if evidence_scope_claims["writes_governance_records"] == full_page_approval_requested
            else "invalid"
        ),
        "evidence_scope_proves_capture_ready_page_execution": (
            "valid"
            if evidence_scope_claims["proves_capture_ready_page_execution"] == full_page_approval_requested
            else "invalid"
        ),
    }
    capture_prerequisites_valid = all(
        field_status in {"valid", "not_required"}
        for field, field_status in status.items()
        if not field.startswith("evidence_scope_")
    )
    status["evidence_scope_captures_business_owner_approval"] = (
        "valid"
        if evidence_scope_claims["captures_business_owner_approval"]
        == (approval_status == "approved" and capture_prerequisites_valid)
        else "invalid"
    )
    status["evidence_scope_certification_effect"] = (
        "valid" if evidence_scope_claims["certification_effect"] == "none" else "invalid"
    )
    return status


def _approval_blockers(
    text: str,
    approval_status: str,
    *,
    formal_use_allowed: str,
    closure_approved: str,
    evidence_scope_claims: EvidenceScopeClaims,
    report_date: str,
) -> list[str]:
    field_status = _approval_field_status(
        text,
        approval_status=approval_status,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        evidence_scope_claims=evidence_scope_claims,
        report_date=report_date,
    )
    blockers = [
        blocker
        for blocker, status in field_status.items()
        if status not in {"valid", "not_required"}
    ]
    if approval_status != "approved" or blockers:
        return ["business_owner_approval", *blockers]
    return []


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


def build_status(template_path: Path, *, report_date: str = DEFAULT_REPORT_DATE) -> dict[str, object]:
    text = template_path.read_text(encoding="utf-8")
    approval_status = _extract_assignment(_extract_code_value(text, "Approval status"), "approval_status")
    formal_use_allowed = _extract_assignment(_extract_code_value(text, "Formal use allowed"), "formal_use_allowed")
    closure_approved = _extract_assignment(_extract_code_value(text, "Closure approved"), "closure_approved")
    evidence_scope_claims = _evidence_scope_claims(text)

    approval_field_status = _approval_field_status(
        text,
        approval_status=approval_status,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        evidence_scope_claims=evidence_scope_claims,
        report_date=report_date,
    )
    remaining_blockers = _approval_blockers(
        text,
        approval_status,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
        evidence_scope_claims=evidence_scope_claims,
        report_date=report_date,
    )
    approval_action_items = _approval_action_items(remaining_blockers, approval_field_status)
    approval_captured = approval_status == "approved" and not remaining_blockers
    return {
        "page_id": _extract_code_value(text, "Page ID"),
        "page_slug": _extract_code_value(text, "Page slug"),
        "primary_api": _extract_code_value(text, "Primary API"),
        "approval_check": _extract_code_value(text, "Approval check"),
        "report_date": report_date,
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
            "approves_metric_or_page": evidence_scope_claims["approves_metric_or_page"] and approval_captured,
            "writes_governance_records": evidence_scope_claims["writes_governance_records"] and approval_captured,
            "proves_capture_ready_page_execution": (
                evidence_scope_claims["proves_capture_ready_page_execution"] and approval_captured
            ),
            "captures_business_owner_approval": (
                evidence_scope_claims["captures_business_owner_approval"] and approval_captured
            ),
            "certification_effect": str(evidence_scope_claims["certification_effect"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the portfolio-home business-owner approval template and report its current status.",
    )
    parser.add_argument(
        "--template-path",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Path to the business-owner approval template.",
    )
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--require-captured",
        action="store_true",
        help="Return a non-zero exit code unless business-owner approval is fully captured.",
    )
    args = parser.parse_args(argv)

    status = build_status(Path(args.template_path), report_date=str(args.report_date))
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if args.require_captured and not status["business_owner_approval_captured"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
