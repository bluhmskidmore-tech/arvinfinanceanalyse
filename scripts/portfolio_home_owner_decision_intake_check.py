from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import (  # noqa: E402
    DEFAULT_TEMPLATE,
    build_status as build_approval_status,
)
from scripts.portfolio_home_dependency_consistency_check import (  # noqa: E402
    build_dependency_consistency,
)
from scripts.portfolio_home_krd_contract_decision_export import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as DEFAULT_KRD_EXPORT_DIR,
    build_current_status as build_krd_export_current_status,
)
from scripts.portfolio_home_maturity_remediation_export import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as DEFAULT_MATURITY_EXPORT_DIR,
    build_current_status as build_maturity_export_current_status,
)
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    non_negative_portfolio_limit,
)
from scripts.portfolio_home_limit import validate_non_negative_portfolio_limit  # noqa: E402


VALID_KRD_DECISIONS = {
    "approve_nearest_bucket",
    "require_exact_bucket_schema",
    "reject",
}
KRD_NOTE_REQUIRED = VALID_KRD_DECISIONS
VALID_MATURITY_DECISIONS = {
    "remediate_source",
    "approve_scoped_exclusion",
    "reject",
}
MATURITY_NOTE_REQUIRED = VALID_MATURITY_DECISIONS
EXACT_BUCKET_SCHEMA_EVIDENCE_FILE = "exact_bucket_schema_evidence.json"
NEAREST_BUCKET_APPROVAL_EVIDENCE_FILE = "nearest_bucket_approval_evidence.json"
MATURITY_SCOPED_EXCLUSION_EVIDENCE_FILE = "maturity_scoped_exclusion_evidence.json"
INTAKE_ALLOWED_DEPENDENCY_BLOCKERS = {
    "krd_contract_decision_manifest_owner_decision_fields_not_blank",
    "maturity_remediation_manifest_owner_fields_not_blank",
}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = (row.get(field) or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _all_rows_have_field(rows: list[dict[str, str]], field: str) -> bool:
    return all(bool((row.get(field) or "").strip()) for row in rows)


def _missing_field_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if not (row.get(field) or "").strip())


def _all_rows_notes_filled_for(rows: list[dict[str, str]], *, decision_field: str, note_field: str, note_required: set[str]) -> bool:
    for row in rows:
        decision = (row.get(decision_field) or "").strip()
        if decision in note_required and not (row.get(note_field) or "").strip():
            return False
    return True


def _note_gap_counts(
    rows: list[dict[str, str]],
    *,
    decision_field: str,
    note_field: str,
    note_required: set[str],
    missing_count_field: str,
) -> dict[str, object]:
    gaps: dict[str, int] = {}
    for row in rows:
        decision = (row.get(decision_field) or "").strip()
        if decision in note_required and not (row.get(note_field) or "").strip():
            gaps[decision] = gaps.get(decision, 0) + 1
    if not gaps:
        return {}
    if len(gaps) == 1:
        decision, row_count = next(iter(gaps.items()))
        return {
            decision_field: decision,
            missing_count_field: row_count,
        }
    return {
        "by_decision": [
            {
                decision_field: decision,
                missing_count_field: row_count,
            }
            for decision, row_count in sorted(gaps.items())
        ],
    }


def _all_rows_have_proposed_date_for_remediation(rows: list[dict[str, str]]) -> bool:
    for row in rows:
        decision = (row.get("owner_decision") or "").strip()
        if decision == "remediate_source" and not (row.get("proposed_maturity_date") or "").strip():
            return False
    return True


def _all_remediation_proposed_dates_are_valid(rows: list[dict[str, str]]) -> bool:
    for row in rows:
        decision = (row.get("owner_decision") or "").strip()
        value = (row.get("proposed_maturity_date") or "").strip()
        if decision != "remediate_source" or not value:
            continue
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
    return True


def _invalid_values(rows: list[dict[str, str]], field: str, valid_values: set[str]) -> list[str]:
    invalid: list[str] = []
    for row in rows:
        value = (row.get(field) or "").strip()
        if value and value not in valid_values and value not in invalid:
            invalid.append(value)
    return invalid


def _is_missing_or_placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return True
    stripped = value.strip()
    return not stripped or (stripped.startswith("<") and stripped.endswith(">"))


def _append_required_text_blocker(
    blockers: list[str],
    payload: dict[str, object],
    *,
    field: str,
    blocker_prefix: str,
) -> None:
    if _is_missing_or_placeholder(payload.get(field)):
        blockers.append(f"{blocker_prefix}_{field}_missing")


def _append_required_date_blocker(
    blockers: list[str],
    payload: dict[str, object],
    *,
    field: str,
    blocker_prefix: str,
    report_date: str,
) -> None:
    value = payload.get(field)
    if _is_missing_or_placeholder(value):
        blockers.append(f"{blocker_prefix}_{field}_missing")
        return
    assert isinstance(value, str)
    try:
        evidence_date = date.fromisoformat(value.strip())
        anchor_date = date.fromisoformat(report_date)
    except ValueError:
        blockers.append(f"{blocker_prefix}_{field}_invalid")
        return
    if evidence_date < anchor_date:
        blockers.append(f"{blocker_prefix}_{field}_stale")


def _owner_input_boundary(
    *,
    pre_intake_dependency_blockers: list[str],
    active_dependency_blockers: list[str],
    active_export_current_blockers: list[str],
) -> dict[str, object]:
    return {
        "generated_export_owner_fields_must_be_blank": True,
        "filled_owner_fields_are_owner_input_only": True,
        "generated_export_system_fields_must_be_current": True,
        "allowed_pre_intake_dependency_blockers": sorted(INTAKE_ALLOWED_DEPENDENCY_BLOCKERS),
        "pre_intake_dependency_blockers": pre_intake_dependency_blockers,
        "active_dependency_blockers": active_dependency_blockers,
        "active_export_current_blockers": active_export_current_blockers,
    }


def _export_current_summary(statuses: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for name, value in statuses.items():
        status = value if isinstance(value, dict) else {}
        blockers = status.get("current_blockers", [])
        summary[name] = {
            "status": status.get("status"),
            "current": status.get("current"),
            "current_blockers": blockers if isinstance(blockers, list) else [],
        }
    return summary


def _exact_bucket_schema_evidence(docs_root: Path, report_date: str) -> dict[str, object]:
    relative_path = (
        f"docs/portfolio/krd-contract-decision/{report_date}/"
        f"{EXACT_BUCKET_SCHEMA_EVIDENCE_FILE}"
    )
    path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / report_date
        / EXACT_BUCKET_SCHEMA_EVIDENCE_FILE
    )
    if not path.exists():
        return {
            "status": "missing",
            "artifact": relative_path,
            "valid": False,
            "blockers": ["krd_exact_bucket_schema_evidence_missing"],
        }

    blockers: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
        blockers.append("krd_exact_bucket_schema_evidence_invalid_json")
    if not isinstance(payload, dict):
        payload = {}
        blockers.append("krd_exact_bucket_schema_evidence_invalid_payload")

    expected_true_fields = [
        "metric_contract_updated",
        "api_schema_updated",
        "risk_tensor_rematerialized",
        "verification_rerun_matched",
    ]
    if payload.get("evidence_kind") != "portfolio_home_exact_bucket_schema_evidence":
        blockers.append("krd_exact_bucket_schema_evidence_kind_mismatch")
    if payload.get("page_id") != "PAGE-PORTFOLIO-HOME-001":
        blockers.append("krd_exact_bucket_schema_evidence_page_id_mismatch")
    if payload.get("page_slug") != "portfolio":
        blockers.append("krd_exact_bucket_schema_evidence_page_slug_mismatch")
    if payload.get("report_date") != report_date:
        blockers.append("krd_exact_bucket_schema_evidence_report_date_mismatch")
    if payload.get("decision") != "require_exact_bucket_schema":
        blockers.append("krd_exact_bucket_schema_evidence_decision_mismatch")
    for field in expected_true_fields:
        if payload.get(field) is not True:
            blockers.append(f"krd_exact_bucket_schema_evidence_{field}_missing")
    _append_required_text_blocker(
        blockers,
        payload,
        field="metric_contract_owner_name",
        blocker_prefix="krd_exact_bucket_schema_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="metric_contract_update_date",
        blocker_prefix="krd_exact_bucket_schema_evidence",
        report_date=report_date,
    )
    _append_required_text_blocker(
        blockers,
        payload,
        field="api_schema_owner_name",
        blocker_prefix="krd_exact_bucket_schema_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="api_schema_update_date",
        blocker_prefix="krd_exact_bucket_schema_evidence",
        report_date=report_date,
    )
    _append_required_text_blocker(
        blockers,
        payload,
        field="risk_tensor_owner_name",
        blocker_prefix="krd_exact_bucket_schema_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="risk_tensor_rematerialization_date",
        blocker_prefix="krd_exact_bucket_schema_evidence",
        report_date=report_date,
    )
    _append_required_text_blocker(
        blockers,
        payload,
        field="verifier_name",
        blocker_prefix="krd_exact_bucket_schema_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="verification_rerun_date",
        blocker_prefix="krd_exact_bucket_schema_evidence",
        report_date=report_date,
    )

    return {
        "status": "valid" if not blockers else "blocked",
        "artifact": relative_path,
        "valid": not blockers,
        "blockers": blockers,
    }


def _nearest_bucket_approval_evidence(
    docs_root: Path,
    report_date: str,
    *,
    mapped_tenor_buckets: list[str],
    nonzero_dv01_rows: int,
    dv01_sum: str,
) -> dict[str, object]:
    relative_path = (
        f"docs/portfolio/krd-contract-decision/{report_date}/"
        f"{NEAREST_BUCKET_APPROVAL_EVIDENCE_FILE}"
    )
    path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / report_date
        / NEAREST_BUCKET_APPROVAL_EVIDENCE_FILE
    )
    if not path.exists():
        return {
            "status": "missing",
            "artifact": relative_path,
            "valid": False,
            "blockers": ["krd_nearest_bucket_approval_evidence_missing"],
        }

    blockers: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
        blockers.append("krd_nearest_bucket_approval_evidence_invalid_json")
    if not isinstance(payload, dict):
        payload = {}
        blockers.append("krd_nearest_bucket_approval_evidence_invalid_payload")

    expected_true_fields = [
        "risk_owner_approved",
        "business_owner_acknowledged",
        "metric_contract_decision_recorded",
        "verification_rerun_matched",
    ]
    if payload.get("evidence_kind") != "portfolio_home_nearest_bucket_approval_evidence":
        blockers.append("krd_nearest_bucket_approval_evidence_kind_mismatch")
    if payload.get("page_id") != "PAGE-PORTFOLIO-HOME-001":
        blockers.append("krd_nearest_bucket_approval_evidence_page_id_mismatch")
    if payload.get("page_slug") != "portfolio":
        blockers.append("krd_nearest_bucket_approval_evidence_page_slug_mismatch")
    if payload.get("report_date") != report_date:
        blockers.append("krd_nearest_bucket_approval_evidence_report_date_mismatch")
    if payload.get("decision") != "approve_nearest_bucket":
        blockers.append("krd_nearest_bucket_approval_evidence_decision_mismatch")
    if payload.get("mapped_tenor_buckets") != mapped_tenor_buckets:
        blockers.append("krd_nearest_bucket_approval_evidence_tenor_scope_mismatch")
    if payload.get("nonzero_dv01_rows") != nonzero_dv01_rows:
        blockers.append("krd_nearest_bucket_approval_evidence_row_count_mismatch")
    if str(payload.get("dv01_sum") or "") != dv01_sum:
        blockers.append("krd_nearest_bucket_approval_evidence_dv01_sum_mismatch")
    for field in expected_true_fields:
        if payload.get(field) is not True:
            blockers.append(f"krd_nearest_bucket_approval_evidence_{field}_missing")
    _append_required_text_blocker(
        blockers,
        payload,
        field="risk_owner_name",
        blocker_prefix="krd_nearest_bucket_approval_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="risk_owner_approval_date",
        blocker_prefix="krd_nearest_bucket_approval_evidence",
        report_date=report_date,
    )
    _append_required_text_blocker(
        blockers,
        payload,
        field="business_owner_name",
        blocker_prefix="krd_nearest_bucket_approval_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="business_owner_acknowledgement_date",
        blocker_prefix="krd_nearest_bucket_approval_evidence",
        report_date=report_date,
    )

    return {
        "status": "valid" if not blockers else "blocked",
        "artifact": relative_path,
        "valid": not blockers,
        "blockers": blockers,
    }


def _maturity_scoped_exclusion_evidence(
    docs_root: Path,
    report_date: str,
    *,
    bond_missing_maturity_rows: int,
    tyw_liability_missing_maturity_rows: int,
) -> dict[str, object]:
    relative_path = (
        f"docs/portfolio/maturity-remediation/{report_date}/"
        f"{MATURITY_SCOPED_EXCLUSION_EVIDENCE_FILE}"
    )
    path = (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / report_date
        / MATURITY_SCOPED_EXCLUSION_EVIDENCE_FILE
    )
    if not path.exists():
        return {
            "status": "missing",
            "artifact": relative_path,
            "valid": False,
            "blockers": ["maturity_scoped_exclusion_evidence_missing"],
        }

    blockers: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
        blockers.append("maturity_scoped_exclusion_evidence_invalid_json")
    if not isinstance(payload, dict):
        payload = {}
        blockers.append("maturity_scoped_exclusion_evidence_invalid_payload")

    expected_true_fields = [
        "data_owner_approved",
        "risk_owner_countersigned",
        "business_owner_acknowledged",
        "verification_rerun_matched",
    ]
    if payload.get("evidence_kind") != "portfolio_home_maturity_scoped_exclusion_evidence":
        blockers.append("maturity_scoped_exclusion_evidence_kind_mismatch")
    if payload.get("page_id") != "PAGE-PORTFOLIO-HOME-001":
        blockers.append("maturity_scoped_exclusion_evidence_page_id_mismatch")
    if payload.get("page_slug") != "portfolio":
        blockers.append("maturity_scoped_exclusion_evidence_page_slug_mismatch")
    if payload.get("report_date") != report_date:
        blockers.append("maturity_scoped_exclusion_evidence_report_date_mismatch")
    if payload.get("decision") != "approve_scoped_exclusion":
        blockers.append("maturity_scoped_exclusion_evidence_decision_mismatch")
    if payload.get("bond_missing_maturity_rows") != bond_missing_maturity_rows:
        blockers.append("maturity_scoped_exclusion_evidence_bond_row_count_mismatch")
    if payload.get("tyw_liability_missing_maturity_rows") != tyw_liability_missing_maturity_rows:
        blockers.append("maturity_scoped_exclusion_evidence_tyw_row_count_mismatch")
    for field in expected_true_fields:
        if payload.get(field) is not True:
            blockers.append(f"maturity_scoped_exclusion_evidence_{field}_missing")
    _append_required_text_blocker(
        blockers,
        payload,
        field="data_owner_name",
        blocker_prefix="maturity_scoped_exclusion_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="data_owner_approval_date",
        blocker_prefix="maturity_scoped_exclusion_evidence",
        report_date=report_date,
    )
    _append_required_text_blocker(
        blockers,
        payload,
        field="risk_owner_name",
        blocker_prefix="maturity_scoped_exclusion_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="risk_owner_countersign_date",
        blocker_prefix="maturity_scoped_exclusion_evidence",
        report_date=report_date,
    )
    _append_required_text_blocker(
        blockers,
        payload,
        field="business_owner_name",
        blocker_prefix="maturity_scoped_exclusion_evidence",
    )
    _append_required_date_blocker(
        blockers,
        payload,
        field="business_owner_acknowledgement_date",
        blocker_prefix="maturity_scoped_exclusion_evidence",
        report_date=report_date,
    )

    return {
        "status": "valid" if not blockers else "blocked",
        "artifact": relative_path,
        "valid": not blockers,
        "blockers": blockers,
    }


def _template_value(template_path: Path, label: str) -> str:
    prefix = f"{label}: "
    text = template_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if value.startswith("`") and value.endswith("`"):
                return value[1:-1].strip()
            return value
    raise ValueError(f"Missing required approval template field: {label}")


def _decision_alignment(
    *,
    template_path: Path,
    krd: dict[str, object],
    maturity: dict[str, object],
) -> dict[str, object]:
    template_decisions = {
        "krd_contract_decision": _template_value(template_path, "KRD contract decision"),
        "maturity_data_decision": _template_value(template_path, "Maturity data decision"),
    }
    krd_decisions = sorted((krd.get("decision_counts") or {}).keys())
    maturity_decisions = sorted((maturity.get("decision_counts") or {}).keys())

    blockers: list[str] = []
    if krd_decisions and krd_decisions != [template_decisions["krd_contract_decision"]]:
        blockers.append("krd_business_template_decision_mismatch")
    if maturity_decisions and maturity_decisions != [template_decisions["maturity_data_decision"]]:
        blockers.append("maturity_business_template_decision_mismatch")

    return {
        "status": "consistent" if not blockers else "blocked",
        "blockers": blockers,
        "business_template_decisions": template_decisions,
        "owner_csv_decisions": {
            "krd": krd_decisions,
            "maturity": maturity_decisions,
        },
    }


def _dependency_csv_summary_alignment(
    csv_check_summary: dict[str, object],
    *,
    krd: dict[str, object],
    maturity: dict[str, object],
) -> dict[str, object]:
    expected = {
        "krd_summary_row_count": krd.get("summary_row_count"),
        "krd_detail_row_count": krd.get("detail_row_count"),
        "bond_missing_maturity_row_count": maturity.get("bond_row_count"),
        "tyw_liability_missing_maturity_row_count": maturity.get("tyw_liability_row_count"),
    }
    blockers: list[str] = []
    for field, expected_value in expected.items():
        if csv_check_summary.get(field) != expected_value:
            blockers.append(f"owner_csv_dependency_summary_{field}_mismatch")
    return {
        "status": "consistent" if not blockers else "blocked",
        "blockers": blockers,
    }


def _krd_summary(docs_root: Path, report_date: str) -> dict[str, object]:
    base = docs_root / "portfolio" / "krd-contract-decision" / report_date
    summary_rows = _csv_rows(base / "krd_remap_summary.csv")
    detail_rows = _csv_rows(base / "krd_remap_detail.csv")
    all_rows = [*summary_rows, *detail_rows]
    missing = not _all_rows_have_field(all_rows, "risk_owner_decision")
    summary_missing_decisions = _missing_field_count(summary_rows, "risk_owner_decision")
    detail_missing_decisions = _missing_field_count(detail_rows, "risk_owner_decision")
    invalid_values = _invalid_values(all_rows, "risk_owner_decision", VALID_KRD_DECISIONS)
    decision_counts = _counts(all_rows, "risk_owner_decision")
    mapped_rows = [
        row
        for row in summary_rows
        if (row.get("mapping_status") or "").strip() == "mapped"
        and int(row.get("nonzero_dv01_rows") or 0) > 0
    ]
    mapped_tenor_buckets = [str(row.get("tenor_bucket") or "") for row in mapped_rows]
    nonzero_dv01_rows = sum(int(row.get("nonzero_dv01_rows") or 0) for row in mapped_rows)
    dv01_sum = format(
        sum((Decimal(str(row.get("dv01_sum") or "0")) for row in mapped_rows), Decimal("0")).quantize(
            Decimal("0.00000001"),
        ),
        "f",
    )
    notes_missing = not _all_rows_notes_filled_for(
        all_rows,
        decision_field="risk_owner_decision",
        note_field="decision_notes",
        note_required=KRD_NOTE_REQUIRED,
    )
    note_gap_counts = _note_gap_counts(
        all_rows,
        decision_field="risk_owner_decision",
        note_field="decision_notes",
        note_required=KRD_NOTE_REQUIRED,
        missing_count_field="missing_note_rows",
    )
    exact_bucket_schema_evidence = (
        _exact_bucket_schema_evidence(docs_root, report_date)
        if "require_exact_bucket_schema" in decision_counts
        else {
            "status": "not_required",
            "artifact": (
                f"docs/portfolio/krd-contract-decision/{report_date}/"
                f"{EXACT_BUCKET_SCHEMA_EVIDENCE_FILE}"
            ),
            "valid": True,
            "blockers": [],
        }
    )
    nearest_bucket_approval_evidence = (
        _nearest_bucket_approval_evidence(
            docs_root,
            report_date,
            mapped_tenor_buckets=mapped_tenor_buckets,
            nonzero_dv01_rows=nonzero_dv01_rows,
            dv01_sum=dv01_sum,
        )
        if "approve_nearest_bucket" in decision_counts
        else {
            "status": "not_required",
            "artifact": (
                f"docs/portfolio/krd-contract-decision/{report_date}/"
                f"{NEAREST_BUCKET_APPROVAL_EVIDENCE_FILE}"
            ),
            "valid": True,
            "blockers": [],
        }
    )
    blockers: list[str] = []
    if missing:
        blockers.append("krd_owner_decision_missing")
    if invalid_values:
        blockers.append("krd_owner_decision_invalid")
    if "reject" in decision_counts:
        blockers.append("krd_owner_decision_rejected")
    if notes_missing:
        blockers.append("krd_owner_decision_notes_missing")
    blockers.extend(str(blocker) for blocker in exact_bucket_schema_evidence["blockers"])
    blockers.extend(str(blocker) for blocker in nearest_bucket_approval_evidence["blockers"])
    return {
        "status": "ready" if not blockers else "pending",
        "blockers": blockers,
        "summary_row_count": len(summary_rows),
        "detail_row_count": len(detail_rows),
        "decision_counts": decision_counts,
        "decision_gap_counts": {
            "missing_decision_rows": summary_missing_decisions + detail_missing_decisions,
            "summary_missing_decision_rows": summary_missing_decisions,
            "detail_missing_decision_rows": detail_missing_decisions,
        },
        "note_gap_counts": note_gap_counts,
        "invalid_decisions": invalid_values,
        "exact_bucket_schema_evidence": exact_bucket_schema_evidence,
        "nearest_bucket_approval_evidence": nearest_bucket_approval_evidence,
    }


def _maturity_summary(docs_root: Path, report_date: str) -> dict[str, object]:
    base = docs_root / "portfolio" / "maturity-remediation" / report_date
    bond_rows = _csv_rows(base / "bond_missing_maturity.csv")
    tyw_rows = _csv_rows(base / "tyw_liability_missing_maturity.csv")
    all_rows = [*bond_rows, *tyw_rows]
    missing = not _all_rows_have_field(all_rows, "owner_decision")
    bond_missing_decisions = _missing_field_count(bond_rows, "owner_decision")
    tyw_missing_decisions = _missing_field_count(tyw_rows, "owner_decision")
    invalid_values = _invalid_values(all_rows, "owner_decision", VALID_MATURITY_DECISIONS)
    decision_counts = _counts(all_rows, "owner_decision")
    notes_missing = not _all_rows_notes_filled_for(
        all_rows,
        decision_field="owner_decision",
        note_field="owner_comment",
        note_required=MATURITY_NOTE_REQUIRED,
    )
    comment_gap_counts = _note_gap_counts(
        all_rows,
        decision_field="owner_decision",
        note_field="owner_comment",
        note_required=MATURITY_NOTE_REQUIRED,
        missing_count_field="missing_comment_rows",
    )
    proposed_date_missing = not _all_rows_have_proposed_date_for_remediation(all_rows)
    proposed_date_invalid = not _all_remediation_proposed_dates_are_valid(all_rows)
    scoped_exclusion_evidence = (
        _maturity_scoped_exclusion_evidence(
            docs_root,
            report_date,
            bond_missing_maturity_rows=len(bond_rows),
            tyw_liability_missing_maturity_rows=len(tyw_rows),
        )
        if "approve_scoped_exclusion" in decision_counts
        else {
            "status": "not_required",
            "artifact": (
                f"docs/portfolio/maturity-remediation/{report_date}/"
                f"{MATURITY_SCOPED_EXCLUSION_EVIDENCE_FILE}"
            ),
            "valid": True,
            "blockers": [],
        }
    )
    blockers: list[str] = []
    if missing:
        blockers.append("maturity_owner_decision_missing")
    if invalid_values:
        blockers.append("maturity_owner_decision_invalid")
    if "reject" in decision_counts:
        blockers.append("maturity_owner_decision_rejected")
    if notes_missing:
        blockers.append("maturity_owner_comment_missing")
    if proposed_date_missing:
        blockers.append("maturity_proposed_maturity_date_missing")
    if proposed_date_invalid:
        blockers.append("maturity_proposed_maturity_date_invalid")
    blockers.extend(str(blocker) for blocker in scoped_exclusion_evidence["blockers"])
    return {
        "status": "ready" if not blockers else "pending",
        "blockers": blockers,
        "bond_row_count": len(bond_rows),
        "tyw_liability_row_count": len(tyw_rows),
        "decision_counts": decision_counts,
        "decision_gap_counts": {
            "missing_decision_rows": bond_missing_decisions + tyw_missing_decisions,
            "bond_missing_decision_rows": bond_missing_decisions,
            "tyw_liability_missing_decision_rows": tyw_missing_decisions,
        },
        "comment_gap_counts": comment_gap_counts,
        "invalid_decisions": invalid_values,
        "scoped_exclusion_evidence": scoped_exclusion_evidence,
    }


def build_intake_check(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    docs_root: Path,
    limit: int,
    dependency: dict[str, object] | None = None,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="owner decision intake limit",
    )
    if dependency is None:
        dependency = build_dependency_consistency(
            duckdb_path=duckdb_path,
            report_date=report_date,
            template_path=template_path,
            docs_root=docs_root,
            limit=limit,
        )
    export_current_statuses = {
        "krd": build_krd_export_current_status(
            duckdb_path=duckdb_path,
            report_date=report_date,
            output_dir=docs_root / DEFAULT_KRD_EXPORT_DIR.relative_to(ROOT / "docs"),
        ),
        "maturity": build_maturity_export_current_status(
            duckdb_path=duckdb_path,
            report_date=report_date,
            output_dir=docs_root / DEFAULT_MATURITY_EXPORT_DIR.relative_to(ROOT / "docs"),
        ),
    }
    export_current_summary = _export_current_summary(export_current_statuses)
    approval = build_approval_status(template_path)
    krd = _krd_summary(docs_root, report_date)
    maturity = _maturity_summary(docs_root, report_date)
    decision_alignment = _decision_alignment(
        template_path=template_path,
        krd=krd,
        maturity=maturity,
    )
    business_ready = bool(approval.get("business_owner_approval_captured"))
    business_blockers = [] if business_ready else ["business_owner_approval_missing"]
    dependency_blockers = dependency.get("dependency_consistency_blockers", [])
    assert isinstance(dependency_blockers, list)
    csv_check_summary = dependency.get("csv_check_summary", {})
    generated_owner_fields_boundaries = dependency.get("generated_owner_fields_boundaries", {})
    assert isinstance(csv_check_summary, dict)
    assert isinstance(generated_owner_fields_boundaries, dict)
    dependency_csv_summary_alignment = _dependency_csv_summary_alignment(
        csv_check_summary,
        krd=krd,
        maturity=maturity,
    )
    intake_dependency_blockers = [
        str(blocker)
        for blocker in dependency_blockers
        if str(blocker) not in INTAKE_ALLOWED_DEPENDENCY_BLOCKERS
    ]
    export_current_blockers = []
    if not export_current_statuses["krd"].get("current"):
        export_current_blockers.append("krd_contract_decision_export_stale")
    if not export_current_statuses["maturity"].get("current"):
        export_current_blockers.append("maturity_remediation_export_stale")

    blockers = [
        *intake_dependency_blockers,
        *list(dependency_csv_summary_alignment["blockers"]),
        *export_current_blockers,
        *list(krd["blockers"]),
        *list(maturity["blockers"]),
        *list(decision_alignment["blockers"]),
        *business_blockers,
    ]
    owner_statuses = {
        "risk_owner": "ready" if krd["status"] == "ready" else "pending",
        "data_owner": "ready" if maturity["status"] == "ready" else "pending",
        "business_owner": "ready" if business_ready else "pending",
    }
    intake_ready = not blockers
    return {
        "check_kind": "portfolio_home_owner_decision_intake",
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "template_path": str(template_path),
        "docs_root": str(docs_root),
        "intake_status": "ready_for_intake" if intake_ready else "pending_owner_decisions",
        "intake_ready": intake_ready,
        "dependency_consistency_status": (
            "consistent" if not intake_dependency_blockers else "blocked"
        ),
        "dependency_consistency_blockers": intake_dependency_blockers,
        "pre_intake_dependency_blockers": dependency_blockers,
        "owner_input_boundary": _owner_input_boundary(
            pre_intake_dependency_blockers=[str(blocker) for blocker in dependency_blockers],
            active_dependency_blockers=intake_dependency_blockers,
            active_export_current_blockers=export_current_blockers,
        ),
        "export_current_statuses": export_current_statuses,
        "export_current_summary": export_current_summary,
        "csv_check_summary": csv_check_summary,
        "dependency_csv_summary_alignment": dependency_csv_summary_alignment,
        "generated_owner_fields_boundaries": generated_owner_fields_boundaries,
        "owner_decision_statuses": owner_statuses,
        "owner_decision_blockers": blockers,
        "owner_decision_summary": {
            "krd": krd,
            "maturity": maturity,
            "decision_alignment": decision_alignment,
            "business_owner": {
                "status": owner_statuses["business_owner"],
                "approval_status": approval.get("approval_status"),
                "business_owner_approval_captured": approval.get(
                    "business_owner_approval_captured",
                ),
                "approval_action_item_count": approval.get("approval_action_item_count"),
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read owner decision artifacts and report whether portfolio-home decisions are ready for intake.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="owner decision intake limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless all owner decision artifacts are ready for intake.",
    )
    args = parser.parse_args(argv)
    payload = build_intake_check(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        docs_root=Path(args.docs_root),
        limit=int(args.limit),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.require_ready and not payload["intake_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
