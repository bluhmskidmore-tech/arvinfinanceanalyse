from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_portfolio_home_business_owner_approval import build_status


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_portfolio_home_business_owner_approval.py"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"


def _filled_template_text(
    *,
    approval_decision: str = "approve",
    approval_date: str = "2026-06-05",
    krd_decision: str = "require_exact_bucket_schema",
    maturity_decision: str = "remediate_source",
    warning_decision: str = "keep_warning",
    decision_notes: str | None = None,
) -> str:
    text = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Business owner name: `<required>`", "Business owner name: `Portfolio Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Investment Book Owner`")
        .replace("Risk owner name: `<required>`", "Risk owner name: `Risk Owner`")
        .replace("Risk owner role: `<required>`", "Risk owner role: `Market Risk Owner`")
        .replace(
            "Approval decision: `<approve | reject | request_changes>`",
            f"Approval decision: `{approval_decision}`",
        )
        .replace("Approval date: `<YYYY-MM-DD>`", f"Approval date: `{approval_date}`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Portfolio Owner`")
        .replace("Risk owner signature: `<required>`", "Risk owner signature: `Risk Owner`")
        .replace(
            "KRD contract decision: `<approve_nearest_bucket | require_exact_bucket_schema | reject>`",
            f"KRD contract decision: `{krd_decision}`",
        )
        .replace(
            "Maturity data decision: `<remediate_source | approve_scoped_exclusion | reject>`",
            f"Maturity data decision: `{maturity_decision}`",
        )
        .replace(
            "Risk tensor warning decision: `<keep_warning | approve_after_clean_rerun | request_changes>`",
            f"Risk tensor warning decision: `{warning_decision}`",
        )
        .replace("- Governance record reviewed: `<yes | no>`", "- Governance record reviewed: `yes`")
        .replace(
            "- Supporting sample `GS-PORTFOLIO-HOME-A` reviewed: `<yes | no>`",
            "- Supporting sample `GS-PORTFOLIO-HOME-A` reviewed: `yes`",
        )
        .replace(
            "- Risk warning sample `GS-RISK-WARN-B` reviewed: `<yes | no>`",
            "- Risk warning sample `GS-RISK-WARN-B` reviewed: `yes`",
        )
        .replace("- Live proof reviewed: `<yes | no>`", "- Live proof reviewed: `yes`")
        .replace(
            "- DuckDB maturity-gap evidence reviewed: `<yes | no>`",
            "- DuckDB maturity-gap evidence reviewed: `yes`",
        )
        .replace("- KRD remap evidence reviewed: `<yes | no>`", "- KRD remap evidence reviewed: `yes`")
        .replace(
            "- Verification commands rerun before approval: `<yes | no>`",
            "- Verification commands rerun before approval: `yes`",
        )
        .replace("- Candidate-only boundary accepted: `<yes | no>`", "- Candidate-only boundary accepted: `yes`")
        .replace(
            "- `captures_business_owner_approval=false`",
            "- `captures_business_owner_approval=true`",
        )
    )
    if decision_notes is not None:
        text = text.replace(
            "Decision notes: `<required if reject, request_changes, approve_nearest_bucket, or approve_scoped_exclusion>`",
            f"Decision notes: `{decision_notes}`",
        )
    return text


def _full_approval_template_text() -> str:
    return (
        _filled_template_text(warning_decision="approve_after_clean_rerun")
        .replace("Formal use allowed: `formal_use_allowed=false`", "Formal use allowed: `formal_use_allowed=true`")
        .replace("Closure approved: `closure_approved=false`", "Closure approved: `closure_approved=true`")
        .replace("- `approves_metric_or_page=false`", "- `approves_metric_or_page=true`")
        .replace("- `writes_governance_records=false`", "- `writes_governance_records=true`")
        .replace(
            "- `proves_capture_ready_page_execution=false`",
            "- `proves_capture_ready_page_execution=true`",
        )
    )


def _run_checker(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_business_owner_approval_checker_reports_pending_template() -> None:
    returncode, payload = _run_checker("--template-path", str(TEMPLATE))

    assert returncode == 0
    assert payload["page_id"] == "PAGE-PORTFOLIO-HOME-001"
    assert payload["page_slug"] == "portfolio"
    assert payload["approval_status"] == "pending"
    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is False
    assert payload["closure_approved"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"
    for blocker in (
        "business_owner_name",
        "risk_owner_name",
        "krd_contract_decision",
        "maturity_data_decision",
        "risk_tensor_warning_decision",
        "candidate_boundary_acceptance",
    ):
        assert blocker in payload["remaining_blockers"]
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_capture_ready_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }


def test_portfolio_home_business_owner_approval_checker_require_captured_blocks_pending() -> None:
    returncode, payload = _run_checker("--template-path", str(TEMPLATE), "--require-captured")

    assert returncode == 1
    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"][0] == "business_owner_approval"


def test_portfolio_home_business_owner_approval_checker_captures_complete_candidate_review(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(_filled_template_text(), encoding="utf-8")

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is True
    assert payload["formal_use_allowed"] is False
    assert payload["closure_approved"] is False
    assert payload["remaining_blockers"] == []
    assert payload["approval_action_item_count"] == 0
    assert payload["approval_field_status"]["decision_notes"] == "not_required"
    assert payload["evidence_scope"]["captures_business_owner_approval"] is True
    assert payload["evidence_scope"]["proves_capture_ready_page_execution"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"


def test_portfolio_home_business_owner_approval_checker_rejects_placeholder_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        TEMPLATE.read_text(encoding="utf-8").replace(
            "Approval status: `approval_status=pending`",
            "Approval status: `approval_status=approved`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is False
    assert "business_owner_name" in payload["remaining_blockers"]
    assert "risk_owner_signature" in payload["remaining_blockers"]
    assert "krd_contract_decision" in payload["remaining_blockers"]
    assert "candidate_boundary_acceptance" in payload["remaining_blockers"]


def test_portfolio_home_business_owner_approval_checker_blocks_capture_scope_until_signature_complete(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        TEMPLATE.read_text(encoding="utf-8")
        .replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace(
            "- `captures_business_owner_approval=false`",
            "- `captures_business_owner_approval=true`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert "evidence_scope_captures_business_owner_approval" in payload["remaining_blockers"]
    assert payload["approval_field_status"]["evidence_scope_captures_business_owner_approval"] == "invalid"


def test_portfolio_home_business_owner_approval_checker_blocks_boundary_promotion(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text()
        .replace("Formal use allowed: `formal_use_allowed=false`", "Formal use allowed: `formal_use_allowed=true`")
        .replace("Closure approved: `closure_approved=false`", "Closure approved: `closure_approved=true`"),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
    assert payload["closure_approved"] is True
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "risk_tensor_warning_decision",
        "evidence_scope_approves_metric_or_page",
        "evidence_scope_writes_governance_records",
        "evidence_scope_proves_capture_ready_page_execution",
        "evidence_scope_captures_business_owner_approval",
    ]


def test_portfolio_home_business_owner_approval_checker_blocks_scope_without_formal_flags(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text()
        .replace("- `approves_metric_or_page=false`", "- `approves_metric_or_page=true`")
        .replace("- `writes_governance_records=false`", "- `writes_governance_records=true`")
        .replace(
            "- `proves_capture_ready_page_execution=false`",
            "- `proves_capture_ready_page_execution=true`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "risk_tensor_warning_decision",
        "formal_use_allowed",
        "closure_approved",
        "evidence_scope_captures_business_owner_approval",
    ]


def test_portfolio_home_business_owner_approval_checker_captures_full_page_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(_full_approval_template_text(), encoding="utf-8")

    payload = build_status(template)

    assert payload["approval_status"] == "approved"
    assert payload["business_owner_approval_captured"] is True
    assert payload["formal_use_allowed"] is True
    assert payload["closure_approved"] is True
    assert payload["remaining_blockers"] == []
    assert payload["evidence_scope"] == {
        "approves_metric_or_page": True,
        "writes_governance_records": True,
        "proves_capture_ready_page_execution": True,
        "captures_business_owner_approval": True,
        "certification_effect": "none",
    }
    assert payload["approval_field_status"]["approval_date"] == "valid"


def test_portfolio_home_business_owner_approval_template_exposes_no_certification_boundary() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "- `certification_effect=none`" in text


def test_portfolio_home_business_owner_approval_checker_requires_explicit_capture_scope(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _full_approval_template_text().replace(
            "- `captures_business_owner_approval=true`",
            "- `captures_business_owner_approval=false`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["evidence_scope_captures_business_owner_approval"] == "invalid"


def test_portfolio_home_business_owner_approval_checker_blocks_non_none_certification_effect(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _full_approval_template_text().replace(
            "- `certification_effect=none`",
            "- `certification_effect=certifies_page`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["evidence_scope"]["certification_effect"] == "certifies_page"
    assert payload["remaining_blockers"][0] == "business_owner_approval"
    assert "evidence_scope_certification_effect" in payload["remaining_blockers"]
    assert payload["approval_field_status"]["evidence_scope_certification_effect"] == "invalid"


def test_portfolio_home_business_owner_approval_checker_blocks_full_page_keep_warning(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _full_approval_template_text().replace(
            "Risk tensor warning decision: `approve_after_clean_rerun`",
            "Risk tensor warning decision: `keep_warning`",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["formal_use_allowed"] is True
    assert payload["closure_approved"] is True
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "risk_tensor_warning_decision",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["risk_tensor_warning_decision"] == "invalid_for_full_approval"


def test_portfolio_home_business_owner_approval_checker_accepts_report_date_approval(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(_filled_template_text(approval_date="2026-05-31"), encoding="utf-8")

    payload = build_status(template, report_date="2026-05-31")

    assert payload["business_owner_approval_captured"] is True
    assert payload["approval_field_status"]["approval_date"] == "valid"
    assert payload["remaining_blockers"] == []


def test_portfolio_home_business_owner_approval_checker_accepts_later_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(_filled_template_text(approval_date="2026-06-01"), encoding="utf-8")

    payload = build_status(template, report_date="2026-05-31")

    assert payload["business_owner_approval_captured"] is True
    assert payload["approval_field_status"]["approval_date"] == "valid"
    assert payload["remaining_blockers"] == []


def test_portfolio_home_business_owner_approval_checker_blocks_stale_approval_date(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(_filled_template_text(approval_date="2026-05-30"), encoding="utf-8")

    payload = build_status(template, report_date="2026-05-31")

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "approval_date",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["approval_date"] == "stale"
    assert payload["report_date"] == "2026-05-31"


def test_portfolio_home_business_owner_approval_checker_requires_notes_for_nearest_bucket(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(krd_decision="approve_nearest_bucket"),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "decision_notes",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["decision_notes"] == "missing"


def test_portfolio_home_business_owner_approval_checker_accepts_documented_nearest_bucket(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="approve_nearest_bucket",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Risk owner accepts current nearest-bucket and scoped-exclusion boundary for candidate review.",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_field_status"]["decision_notes"] == "valid"


def test_portfolio_home_business_owner_approval_checker_captures_documented_rejection_decisions(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="reject",
            maturity_decision="reject",
            decision_notes="Risk owner and data owner reject the current closure boundary.",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is True
    assert payload["remaining_blockers"] == []
    assert payload["approval_field_status"]["krd_contract_decision"] == "valid"
    assert payload["approval_field_status"]["maturity_data_decision"] == "valid"
    assert payload["approval_field_status"]["decision_notes"] == "valid"


def test_portfolio_home_business_owner_approval_checker_blocks_rejected_approval_decision(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            approval_decision="reject",
            decision_notes="Business owner rejects the current closure request.",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "approval_decision",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["approval_decision"] == "invalid"
    assert payload["approval_field_status"]["decision_notes"] == "valid"


def test_portfolio_home_business_owner_approval_checker_blocks_request_changes_approval_decision(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            approval_decision="request_changes",
            decision_notes="Business owner requires changes before approval.",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "approval_decision",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["approval_decision"] == "invalid"
    assert payload["approval_field_status"]["decision_notes"] == "valid"


def test_portfolio_home_business_owner_approval_checker_rejects_invalid_risk_choices(
    tmp_path: Path,
) -> None:
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="reject",
            maturity_decision="reject",
            warning_decision="request_changes",
            decision_notes="Rejected current risk boundary.",
        ),
        encoding="utf-8",
    )

    payload = build_status(template)

    assert payload["business_owner_approval_captured"] is False
    assert payload["remaining_blockers"] == [
        "business_owner_approval",
        "risk_tensor_warning_decision",
        "evidence_scope_captures_business_owner_approval",
    ]
    assert payload["approval_field_status"]["krd_contract_decision"] == "valid"
    assert payload["approval_field_status"]["maturity_data_decision"] == "valid"
    assert payload["approval_field_status"]["risk_tensor_warning_decision"] == "invalid"
