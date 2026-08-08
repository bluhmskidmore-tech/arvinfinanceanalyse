from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

from tests.test_portfolio_home_business_owner_approval_status import _full_approval_template_text
from tests.test_portfolio_home_closure_scorecard import (
    _approved_template_text,
    _create_schema,
    _insert_blocked_data as _insert_legacy_blocked_data,
    _insert_clean_data,
    _write_blocked_fixture_manifests,
    _write_clean_fixture_manifests,
)
from tests.test_portfolio_home_owner_decision_intake_check import (
    _fill_krd_decisions,
    _fill_maturity_decisions,
)

from scripts.portfolio_home_business_owner_approval_packet import (
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    PORTFOLIO_HOME_SCORE_BLOCKERS,
    RERUN_APPROVAL_REQUIRED_BUSINESS_OWNER_BOUNDARY,
    RERUN_APPROVAL_REQUIRED_WARNING_RESOLUTION_MATRIX,
    _activation_ready,
    _business_owner_approval_boundary,
    _score_blocker_action_coverage_ready,
    build_packet,
    owner_decision_intake_alignment,
    rerun_evidence_payload_status,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_business_owner_approval_packet.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
OWNER_ALIGNMENT_COMPARED_FIELDS = [
    *OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
]
CURRENT_SCORE_BLOCKERS = PORTFOLIO_HOME_SCORE_BLOCKERS
RISK_WARNING_EVIDENCE_SCOPE = {
    "checks_warning_consistency": True,
    "checks_risk_tensor_clean_state": True,
    "captures_risk_owner_decision": False,
    "remediates_source_data": False,
    "approves_metric_or_page": False,
    "writes_governance_records": False,
    "captures_business_owner_approval": False,
    "proves_full_score_closure": False,
    "certification_effect": "none",
}
RISK_WARNING_RESOLUTION_SCOPE = {
    "captures_owner_decision": False,
    "remediates_source_data": False,
    "approves_metric_or_page": False,
    "certification_effect": "none",
}
FIXTURE_DURATION_WARNING = (
    "3 rows carry market_value=60.00000000 and are excluded from portfolio "
    "duration denominator: 2 without maturity_date (market_value=40.00000000); "
    "0 matured on or before report_date with outstanding market_value "
    "(market_value=0.00000000); 1 future-dated with non-positive "
    "modified_duration (market_value=20.00000000). DV01 totals remain sourced "
    "from row dv01; duration metrics ignore these rows until inputs are remediated."
)

def _collect_packet_command_strings(
    value: object,
    field_name: str = "",
    path: str = "packet",
) -> list[tuple[str, str]]:
    if isinstance(value, str):
        return (
            [(path, value)]
            if "command" in field_name and value.startswith(("python ", "pytest "))
            else []
        )
    if isinstance(value, dict):
        commands: list[tuple[str, str]] = []
        for key, child in value.items():
            commands.extend(
                _collect_packet_command_strings(
                    child,
                    str(key),
                    f"{path}.{key}",
                )
            )
        return commands
    if isinstance(value, list):
        commands: list[tuple[str, str]] = []
        for index, child in enumerate(value):
            commands.extend(
                _collect_packet_command_strings(
                    child,
                    field_name,
                    f"{path}[{index}]",
                )
            )
        return commands
    return []


def _is_date_independent_meta_command(command: str) -> bool:
    return command.startswith("pytest ")



def test_rerun_required_matured_outstanding_resolution_is_source_only() -> None:
    matured_resolution = next(
        row
        for row in RERUN_APPROVAL_REQUIRED_WARNING_RESOLUTION_MATRIX
        if row["warning_key"] == "matured_or_expired_outstanding"
    )

    assert matured_resolution["exit_criteria"] == (
        "Matured or unparseable non-zero bond positions are reconciled at source, and "
        "the matured-outstanding strict queue exits 0; exception evidence cannot close "
        "this blocker."
    )


def _insert_blocked_data(path: Path) -> None:
    _insert_legacy_blocked_data(path)
    warnings = [
        "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y, 6M",
        FIXTURE_DURATION_WARNING,
        "Excluded 2 rows without maturity_date from liquidity gap calculation.",
        "Excluded 1 liability rows without maturity_date from liquidity gap calculation.",
    ]
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            update fact_formal_risk_tensor_daily
            set warnings_json = ?
            where report_date = ?
            """,
            [json.dumps(warnings), "2026-05-31"],
        )
    finally:
        connection.close()


def _write_blocked_fixture_nearest_bucket_approval_evidence(docs_root: Path) -> None:
    evidence_path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / "2026-05-31"
        / "nearest_bucket_approval_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_nearest_bucket_approval_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": "2026-05-31",
                "decision": "approve_nearest_bucket",
                "mapped_tenor_buckets": ["2Y", "6M"],
                "nonzero_dv01_rows": 2,
                "dv01_sum": "5.00000000",
                "risk_owner_name": "Risk Owner",
                "risk_owner_approval_date": "2026-05-31",
                "risk_owner_approved": True,
                "business_owner_name": "Portfolio Owner",
                "business_owner_acknowledgement_date": "2026-05-31",
                "business_owner_acknowledged": True,
                "metric_contract_decision_recorded": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_blocked_fixture_maturity_scoped_exclusion_evidence(docs_root: Path) -> None:
    evidence_path = (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / "2026-05-31"
        / "maturity_scoped_exclusion_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_maturity_scoped_exclusion_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": "2026-05-31",
                "decision": "approve_scoped_exclusion",
                "bond_missing_maturity_rows": 0,
                "tyw_liability_missing_maturity_rows": 1,
                "data_owner_name": "Data Owner",
                "data_owner_approval_date": "2026-05-31",
                "data_owner_approved": True,
                "risk_owner_name": "Risk Owner",
                "risk_owner_countersign_date": "2026-05-31",
                "risk_owner_countersigned": True,
                "business_owner_name": "Portfolio Owner",
                "business_owner_acknowledgement_date": "2026-05-31",
                "business_owner_acknowledged": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _expected_not_required_nearest_bucket_approval_evidence(
    report_date: str = "2026-05-31",
) -> dict[str, object]:
    return {
        "status": "not_required",
        "artifact": (
            f"docs/portfolio/krd-contract-decision/{report_date}/"
            "nearest_bucket_approval_evidence.json"
        ),
        "valid": True,
        "blockers": [],
    }


def _expected_export_current_summary() -> dict[str, object]:
    return {
        "krd": {
            "status": "current",
            "current": True,
            "current_blockers": [],
        },
        "maturity": {
            "status": "current",
            "current": True,
            "current_blockers": [],
        },
    }


def _expected_fixture_warning_resolution_matrix() -> list[dict[str, object]]:
    return [
        {
            "warning_key": "krd_bucket_remap",
            "owner": "risk_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": ["2Y", "6M"],
                "recomputed": ["2Y", "6M"],
            },
            "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean",
            "exit_criteria": (
                "Risk owner approves nearest-bucket KRD mapping or supplies exact-bucket "
                "schema evidence; KRD review queue exits 0."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "duration_no_maturity",
            "owner": "none",
            "current_status": "informational",
            "current_evidence": {
                "parsed": {"row_count": 2, "market_value": "40.00000000"},
                "recomputed": {"row_count": 2, "market_value": "40.00000000"},
            },
            "evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                "--report-date 2026-05-31 --require-consistent"
            ),
            "exit_criteria": (
                "Contractual no-maturity rows remain disclosed and excluded from maturity "
                "risk math; no date remediation is required."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "matured_or_expired_outstanding",
            "owner": "data_owner",
            "current_status": "clean",
            "current_evidence": {
                "parsed": {"row_count": 0, "market_value": "0.00000000"},
                "recomputed": {"row_count": 0, "market_value": "0.00000000"},
            },
            "evidence_command": (
                "python scripts/portfolio_home_matured_outstanding_queue.py "
                "--report-date 2026-05-31 --require-empty"
            ),
            "exit_criteria": (
                "Matured or unparseable non-zero bond positions are reconciled at source, and "
                "the matured-outstanding strict queue exits 0; exception evidence cannot close "
                "this blocker."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "nonpositive_duration",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"row_count": 1, "market_value": "20.00000000"},
                "recomputed": {"row_count": 1, "market_value": "20.00000000"},
            },
            "evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                "--report-date 2026-05-31 --require-clean"
            ),
            "exit_criteria": (
                "Future-dated positions with non-positive modified_duration are remediated "
                "at source and the risk warning clean gate exits 0."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "bond_liquidity_gap_no_maturity",
            "owner": "none",
            "current_status": "informational",
            "current_evidence": {
                "parsed": {"missing_maturity_rows": 2},
                "recomputed": {"missing_maturity_rows": 2},
            },
            "evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-consistent"
            ),
            "exit_criteria": (
                "Bond ledger null maturity is disclosed as contractual no-maturity; "
                "no date remediation or scoped exclusion is required."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "tyw_liability_gap_missing_maturity",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"missing_maturity_rows": 1},
                "recomputed": {"missing_maturity_rows": 1},
            },
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty",
            "exit_criteria": (
                "TYW liability missing maturity rows are remediated or signed scoped "
                "exclusion evidence is captured; maturity remediation queue exits 0."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
    ]


def _expected_current_warning_resolution_matrix() -> list[dict[str, object]]:
    return [
        {
            "warning_key": "krd_bucket_remap",
            "owner": "risk_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": ["15Y", "20Y", "2Y", "6M"],
                "recomputed": ["20Y", "2Y", "6M"],
            },
            "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean",
            "exit_criteria": (
                "Risk owner approves nearest-bucket KRD mapping or supplies exact-bucket "
                "schema evidence; KRD review queue exits 0."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "duration_no_maturity",
            "owner": "risk_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"row_count": 0, "market_value": "0.00000000"},
                "recomputed": {
                    "row_count": 114,
                    "market_value": "37622164239.83000008",
                },
            },
            "evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                "--report-date 2026-05-31 --require-consistent"
            ),
            "exit_criteria": (
                "Contractual no-maturity rows remain disclosed and excluded from maturity "
                "risk math; no date remediation is required."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "matured_or_expired_outstanding",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"row_count": 0, "market_value": "0.00000000"},
                "recomputed": {
                    "row_count": 6,
                    "market_value": "1487429865.67000000",
                },
            },
            "evidence_command": (
                "python scripts/portfolio_home_matured_outstanding_queue.py "
                "--report-date 2026-05-31 --require-empty"
            ),
            "exit_criteria": (
                "Matured or unparseable non-zero bond positions are reconciled at source, and "
                "the matured-outstanding strict queue exits 0; exception evidence cannot close "
                "this blocker."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "nonpositive_duration",
            "owner": "data_owner",
            "current_status": "clean",
            "current_evidence": {
                "parsed": {"row_count": 0, "market_value": "0.00000000"},
                "recomputed": {"row_count": 0, "market_value": "0.00000000"},
            },
            "evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                "--report-date 2026-05-31 --require-clean"
            ),
            "exit_criteria": (
                "Future-dated positions with non-positive modified_duration are remediated "
                "at source and the risk warning clean gate exits 0."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "bond_liquidity_gap_no_maturity",
            "owner": "none",
            "current_status": "informational",
            "current_evidence": {
                "parsed": {"missing_maturity_rows": 114},
                "recomputed": {"missing_maturity_rows": 114},
            },
            "evidence_command": (
                "python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-consistent"
            ),
            "exit_criteria": (
                "Bond ledger null maturity is disclosed as contractual no-maturity; "
                "no date remediation or scoped exclusion is required."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
        {
            "warning_key": "tyw_liability_gap_missing_maturity",
            "owner": "data_owner",
            "current_status": "blocked",
            "current_evidence": {
                "parsed": {"missing_maturity_rows": 1455},
                "recomputed": {"missing_maturity_rows": 1455},
            },
            "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty",
            "exit_criteria": (
                "TYW liability missing maturity rows are remediated or signed scoped "
                "exclusion evidence is captured; maturity remediation queue exits 0."
            ),
            "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
        },
    ]


def _expected_current_warning_resolution_matrix_summary() -> list[tuple[str, str, str]]:
    return [
        ("krd_bucket_remap", "risk_owner", "blocked"),
        ("duration_no_maturity", "risk_owner", "blocked"),
        ("matured_or_expired_outstanding", "data_owner", "blocked"),
        ("nonpositive_duration", "data_owner", "clean"),
        ("bond_liquidity_gap_no_maturity", "none", "informational"),
        ("tyw_liability_gap_missing_maturity", "data_owner", "blocked"),
    ]


def _expected_fixture_duration_exclusion_delta_detail() -> dict[str, object]:
    return {
        "status": "matched",
        "delta_basis": "recomputed_minus_parsed",
        "owner_reconciliation_hint": (
            "Parsed risk tensor warning matches recomputed duration exclusion evidence."
        ),
        "mismatch_fields": [],
        "delta": {
            "row_count": 0,
            "market_value_sum": "0.00000000",
            "no_maturity_rows": 0,
            "no_maturity_market_value": "0.00000000",
            "matured_or_expired_outstanding_rows": 0,
            "matured_or_expired_outstanding_market_value": "0.00000000",
            "nonpositive_duration_rows": 0,
            "nonpositive_duration_market_value": "0.00000000",
        },
        "parsed_warning_text": FIXTURE_DURATION_WARNING,
        "expected_warning_text_from_recomputed": FIXTURE_DURATION_WARNING,
        "recomputed_breakdown_by_reason": [
            {
                "exclusion_reason": "no_maturity",
                "row_count": 2,
                "market_value_sum": "40.00000000",
                "dv01_sum": "0.00000000",
            },
            {
                "exclusion_reason": "nonpositive_duration",
                "row_count": 1,
                "market_value_sum": "20.00000000",
                "dv01_sum": "0.00000000",
            },
        ],
    }


def _expected_fixture_risk_tensor_rematerialization_preview() -> dict[str, object]:
    return {
        "status": "would_remain_blocked",
        "preview_basis": "current_formal_facts_read_only",
        "writes_database": False,
        "approves_metric_or_page": False,
        "certification_effect": "none",
        "current_consistency_blockers": [],
        "would_clear_consistency_blockers": [],
        "preview_consistency_status": "consistent",
        "preview_consistency_blockers": [],
        "preview_quality_flag": "warning",
        "preview_decision_status": "blocked",
        "preview_decision_blockers": ["risk_tensor_quality_warning"],
        "preview_warnings": [
            "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y, 6M",
            FIXTURE_DURATION_WARNING,
            "Excluded 2 rows without maturity_date from liquidity gap calculation.",
            "Excluded 1 liability rows without maturity_date from liquidity gap calculation.",
        ],
    }


def _expected_current_duration_exclusion_delta_detail() -> dict[str, object]:
    return {
        "status": "mismatch",
        "delta_basis": "recomputed_minus_parsed",
        "owner_reconciliation_hint": (
            "Recompute or rematerialize risk tensor warnings so parsed warning "
            "numbers match fact_formal_bond_analytics_daily evidence."
        ),
        "mismatch_fields": [
            "row_count",
            "market_value_sum",
            "no_maturity_rows",
            "no_maturity_market_value",
            "matured_or_expired_outstanding_rows",
            "matured_or_expired_outstanding_market_value",
        ],
        "delta": {
            "row_count": 120,
            "market_value_sum": "39109594105.50000008",
            "no_maturity_rows": 114,
            "no_maturity_market_value": "37622164239.83000008",
            "matured_or_expired_outstanding_rows": 6,
            "matured_or_expired_outstanding_market_value": "1487429865.67000000",
            "nonpositive_duration_rows": 0,
            "nonpositive_duration_market_value": "0.00000000",
        },
        "parsed_warning_text": (
            "120 rows carry market_value=39109594105.50000008 and are excluded "
            "from portfolio duration denominator: 114 without maturity_date; 6 "
            "with non-positive modified_duration. DV01 totals remain sourced from "
            "row dv01; duration metrics ignore these rows until inputs are remediated."
        ),
        "expected_warning_text_from_recomputed": (
            "120 rows carry market_value=39109594105.50000008 and are excluded "
            "from portfolio duration denominator: 114 without maturity_date "
            "(market_value=37622164239.83000008); 6 matured on or before report_date "
            "with outstanding market_value (market_value=1487429865.67000000); 0 "
            "future-dated with non-positive modified_duration (market_value=0.00000000). "
            "DV01 totals remain sourced from row dv01; duration metrics ignore these "
            "rows until inputs are remediated."
        ),
        "recomputed_breakdown_by_reason": [
            {
                "exclusion_reason": "matured_or_expired_outstanding",
                "row_count": 6,
                "market_value_sum": "1487429865.67000000",
                "dv01_sum": "0.00000000",
            },
            {
                "exclusion_reason": "no_maturity",
                "row_count": 114,
                "market_value_sum": "37622164239.83000008",
                "dv01_sum": "0.00000000",
            },
        ],
    }


def _expected_current_risk_tensor_rematerialization_preview() -> dict[str, object]:
    return {
        "status": "would_remain_blocked",
        "preview_basis": "current_formal_facts_read_only",
        "writes_database": False,
        "approves_metric_or_page": False,
        "certification_effect": "none",
        "current_consistency_blockers": [
            "krd_bucket_warning_mismatch",
            "duration_exclusion_warning_mismatch",
        ],
        "would_clear_consistency_blockers": [
            "krd_bucket_warning_mismatch",
            "duration_exclusion_warning_mismatch",
        ],
        "preview_consistency_status": "consistent",
        "preview_consistency_blockers": [],
        "preview_quality_flag": "warning",
        "preview_decision_status": "blocked",
        "preview_decision_blockers": ["risk_tensor_quality_warning"],
        "preview_warnings": [
            "Non-standard tenor buckets remapped to nearest KRD bucket: 20Y, 2Y, 6M",
            (
                "120 rows carry market_value=39109594105.50000008 and are "
                "excluded from portfolio duration denominator: 114 without "
                "maturity_date (market_value=37622164239.83000008); 6 matured on or "
                "before report_date with outstanding market_value "
                "(market_value=1487429865.67000000); 0 future-dated with non-positive "
                "modified_duration (market_value=0.00000000). DV01 totals remain "
                "sourced from row dv01; duration metrics ignore these rows until "
                "inputs are remediated."
            ),
            "Excluded 114 rows without maturity_date from liquidity gap calculation.",
            "Excluded 1455 liability rows without maturity_date from liquidity gap calculation.",
        ],
    }


def _expected_scorecard_owner_gate_summary() -> dict[str, object]:
    return {
        "status": "pending",
        "intake_status": "pending_owner_decisions",
        "intake_ready": False,
        "dependency_consistency_status": "consistent",
        "dependency_csv_summary_alignment": {
            "status": "consistent",
            "blockers": [],
        },
        "owner_input_boundary": {
            "generated_export_owner_fields_must_be_blank": True,
            "filled_owner_fields_are_owner_input_only": True,
            "generated_export_system_fields_must_be_current": True,
            "allowed_pre_intake_dependency_blockers": [
                "krd_contract_decision_manifest_owner_decision_fields_not_blank",
                "maturity_remediation_manifest_owner_fields_not_blank",
            ],
            "pre_intake_dependency_blockers": [],
            "active_dependency_blockers": [],
            "active_export_current_blockers": [],
        },
        "export_current_summary": _expected_export_current_summary(),
        "owner_decision_statuses": {
            "risk_owner": "pending",
            "data_owner": "pending",
            "business_owner": "pending",
        },
        "blockers": [
            "krd_owner_decision_missing",
            "maturity_owner_decision_missing",
            "business_owner_approval_missing",
        ],
        "decision_counts": {
            "krd": {},
            "maturity": {},
        },
        "decision_gap_counts": {
            "krd": {
                "missing_decision_rows": 503,
                "summary_missing_decision_rows": 3,
                "detail_missing_decision_rows": 500,
            },
            "maturity": {
                "missing_decision_rows": 1455,
                "bond_missing_decision_rows": 0,
                "tyw_liability_missing_decision_rows": 1455,
            },
        },
        "note_gap_counts": {
            "krd": {},
            "maturity": {},
        },
        "exact_bucket_schema_evidence": {
            "status": "not_required",
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
            "valid": True,
            "blockers": [],
        },
        "nearest_bucket_approval_evidence": (
            _expected_not_required_nearest_bucket_approval_evidence()
        ),
        "maturity_scoped_exclusion_evidence": {
            "status": "not_required",
            "artifact": (
                "docs/portfolio/maturity-remediation/2026-05-31/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
    }


def _expected_owner_decision_intake_summary() -> dict[str, object]:
    gate_summary = _expected_scorecard_owner_gate_summary()
    return {
        "intake_status": gate_summary["intake_status"],
        "intake_ready": gate_summary["intake_ready"],
        "dependency_consistency_status": gate_summary["dependency_consistency_status"],
        "dependency_csv_summary_alignment": gate_summary["dependency_csv_summary_alignment"],
        "csv_check_summary": {
            "krd_summary_row_count": 3,
            "krd_detail_row_count": 500,
            "krd_owner_decision_fields_blank": True,
            "bond_missing_maturity_row_count": 0,
            "tyw_liability_missing_maturity_row_count": 1455,
            "maturity_owner_fields_blank": True,
        },
        "generated_owner_fields_boundaries": {
            "krd_contract_decision_manifest": True,
            "maturity_remediation_manifest": True,
        },
        "owner_input_boundary": gate_summary["owner_input_boundary"],
        "export_current_summary": gate_summary["export_current_summary"],
        "owner_decision_statuses": gate_summary["owner_decision_statuses"],
        "owner_decision_blockers": gate_summary["blockers"],
        "decision_alignment": {
            "status": "consistent",
            "blockers": [],
            "business_template_decisions": {
                "krd_contract_decision": "<approve_nearest_bucket | require_exact_bucket_schema | reject>",
                "maturity_data_decision": "<remediate_source | approve_scoped_exclusion | reject>",
            },
            "owner_csv_decisions": {
                "krd": [],
                "maturity": [],
            },
        },
        "decision_counts": {
            "krd": {},
            "maturity": {},
        },
        "decision_gap_counts": gate_summary["decision_gap_counts"],
        "note_gap_counts": gate_summary["note_gap_counts"],
        "exact_bucket_schema_evidence": gate_summary["exact_bucket_schema_evidence"],
        "nearest_bucket_approval_evidence": gate_summary[
            "nearest_bucket_approval_evidence"
        ],
        "maturity_scoped_exclusion_evidence": gate_summary[
            "maturity_scoped_exclusion_evidence"
        ],
    }


def _approval_summary_required_evidence_fields() -> dict[str, object]:
    return {
        "manifest_consistency_statuses": {
            "krd_contract_decision_manifest": "consistent",
            "maturity_remediation_manifest": "consistent",
        },
        "owner_summary_paths": {
            "krd_contract_decision_owner_summary": "docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md",
            "maturity_remediation_owner_summary": "docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md",
        },
        "csv_check_summary": {
            "krd_summary_row_count": 3,
            "krd_detail_row_count": 500,
            "krd_owner_decision_fields_blank": True,
            "bond_missing_maturity_row_count": 0,
            "tyw_liability_missing_maturity_row_count": 1455,
            "maturity_owner_fields_blank": True,
        },
    }


def _valid_rerun_payload() -> dict[str, object]:
    return {
        "snapshot_kind": "portfolio_home_closure_evidence",
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": "2026-05-31",
        "score_blockers": list(CURRENT_SCORE_BLOCKERS),
        "scorecard_owner_decision_intake_gate_summary": _expected_scorecard_owner_gate_summary(),
        "owner_decision_intake_summary": _expected_owner_decision_intake_summary(),
        "owner_decision_intake_alignment": {
            "status": "consistent",
            "blockers": [],
            "compared_fields": OWNER_ALIGNMENT_COMPARED_FIELDS,
        },
        "business_owner_approval_packet_summary": {
            "approval_field_status": {
                "approval_date": "missing",
                "verification_commands_rerun": "pending",
                "evidence_scope_captures_business_owner_approval": "valid",
            },
            "business_owner_approval_boundary": copy.deepcopy(
                RERUN_APPROVAL_REQUIRED_BUSINESS_OWNER_BOUNDARY,
            ),
            "risk_warning_clean_status": {
                "status": "blocked",
                "valid": False,
                "decision_status": "blocked",
                "decision_blockers": [
                    "risk_tensor_quality_warning",
                    "risk_tensor_warning_mismatch",
                ],
                "evidence_scope": RISK_WARNING_EVIDENCE_SCOPE,
                "warning_resolution_matrix": _expected_current_warning_resolution_matrix(),
                "duration_exclusion_delta_detail": (
                    _expected_current_duration_exclusion_delta_detail()
                ),
                "risk_tensor_rematerialization_preview": (
                    _expected_current_risk_tensor_rematerialization_preview()
                ),
            },
            "score_blocker_action_coverage": {
                "status": "clean",
                "blockers": [],
                "unassigned_blockers": [],
                "covered_blockers": list(CURRENT_SCORE_BLOCKERS),
            },
            "owner_decision_intake_alignment": {
                "status": "consistent",
                "blockers": [],
                "compared_fields": OWNER_ALIGNMENT_COMPARED_FIELDS,
            },
            **_approval_summary_required_evidence_fields(),
        },
        "verification_report": {
            "expected_state": "blocked",
            "verification_status": "matched_expected_blocked_state",
            "all_matched_expected_exit": True,
            "all_matched_expected_when_blocked": True,
            "result_count": 1,
            "results": [
                {
                    "name": "scorecard",
                    "kind": "evidence",
                    "command": "python scripts/portfolio_home_closure_scorecard.py --limit 3",
                    "expected_state": "blocked",
                    "expected_exit": "exit_0",
                    "expected_when_blocked": "exit_0",
                    "expected_when_full_score": "exit_0",
                    "returncode": 0,
                    "matches_expected_exit": True,
                    "matches_expected_when_blocked": True,
                },
            ],
        },
    }


def _write_rerun_artifact(artifact: Path, payload: dict[str, object]) -> None:
    artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def test_portfolio_home_business_owner_approval_packet_cli_writes_and_checks_current(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "portfolio-home-business-owner-approval-packet.json"

    returncode, payload = _run_packet(
        "--limit",
        "1",
        "--output",
        str(output_path),
    )

    assert returncode == 0
    assert payload["packet_kind"] == "portfolio_home_business_owner_approval_packet"
    assert output_path.exists()

    check_returncode, check_payload = _run_packet(
        "--limit",
        "1",
        "--output",
        str(output_path),
        "--check-current",
    )

    assert check_returncode == 0
    assert check_payload["status"] == "current"
    assert check_payload["current"] is True
    assert check_payload["expected_sha256"] == check_payload["actual_sha256"]


def test_portfolio_home_business_owner_approval_packet_check_current_blocks_stale_file(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "portfolio-home-business-owner-approval-packet.json"
    output_path.write_text(json.dumps({"packet_kind": "stale"}), encoding="utf-8")

    returncode, payload = _run_packet(
        "--limit",
        "1",
        "--output",
        str(output_path),
        "--check-current",
    )

    assert returncode == 1
    assert payload["status"] == "stale"
    assert payload["current"] is False
    assert payload["expected_sha256"] != payload["actual_sha256"]


def _activation_ready_args(
    *,
    score_blocker_action_coverage: dict[str, object],
) -> dict[str, object]:
    return {
        "scorecard": {
            "full_score_ready": True,
            "score_status": "ready_for_full_score",
            "score_blockers": list(CURRENT_SCORE_BLOCKERS),
        },
        "approval": {
            "business_owner_approval_captured": True,
            "formal_use_allowed": True,
            "closure_approved": True,
            "evidence_scope": {
                "approves_metric_or_page": True,
                "writes_governance_records": True,
                "proves_capture_ready_page_execution": True,
                "captures_business_owner_approval": True,
                "certification_effect": "none",
            },
        },
        "dependencies": [{"available": True}],
        "dependency_consistency_status": "consistent",
        "intake_check": {"intake_ready": True},
        "owner_intake_alignment": {"status": "consistent"},
        "rerun_evidence_status": {"valid": True},
        "risk_warning_clean_status": {"valid": True},
        "score_blocker_action_coverage": score_blocker_action_coverage,
    }


def test_portfolio_home_business_owner_activation_requires_score_blocker_action_coverage() -> None:
    assert _activation_ready(
        **_activation_ready_args(score_blocker_action_coverage={"status": "clean"})
    ) is False
    assert _activation_ready(
        **_activation_ready_args(
            score_blocker_action_coverage={
                "status": "clean",
                "blockers": [],
                "unassigned_blockers": [],
                "covered_blockers": list(CURRENT_SCORE_BLOCKERS),
            }
        )
    ) is True
    assert _activation_ready(
        **_activation_ready_args(
            score_blocker_action_coverage={
                "status": "blocked",
                "unassigned_blockers": ["new_unmapped_blocker"],
            }
        )
    ) is False


def test_portfolio_home_business_owner_activation_requires_current_score_blocker_coverage() -> None:
    missing_blocker_coverage = {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": list(CURRENT_SCORE_BLOCKERS[:-1]),
    }
    assert (
        _activation_ready(
            **_activation_ready_args(
                score_blocker_action_coverage=missing_blocker_coverage,
            )
        )
        is False
    )


def test_portfolio_home_score_blocker_action_coverage_ready_requires_exact_current_blockers() -> None:
    valid_coverage = {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": list(CURRENT_SCORE_BLOCKERS),
    }

    assert _score_blocker_action_coverage_ready(
        {"score_blockers": list(CURRENT_SCORE_BLOCKERS)},
        valid_coverage,
    ) is True
    assert _score_blocker_action_coverage_ready(
        {},
        valid_coverage,
    ) is False
    assert _score_blocker_action_coverage_ready(
        {"score_blockers": list(CURRENT_SCORE_BLOCKERS)},
        {
            **valid_coverage,
            "covered_blockers": list(CURRENT_SCORE_BLOCKERS[:-1]),
        },
    ) is False


def test_portfolio_home_business_owner_activation_requires_score_status_ready() -> None:
    args = _activation_ready_args(
        score_blocker_action_coverage={
            "status": "clean",
            "blockers": [],
            "unassigned_blockers": [],
            "covered_blockers": list(CURRENT_SCORE_BLOCKERS),
        }
    )
    scorecard = args["scorecard"]
    assert isinstance(scorecard, dict)
    scorecard["full_score_ready"] = True
    scorecard["score_status"] = "blocked"

    assert _activation_ready(**args) is False


def test_portfolio_home_business_owner_boundary_reports_score_status_not_ready() -> None:
    boundary = _business_owner_approval_boundary(
        approval={"business_owner_approval_captured": True},
        scorecard={
            "full_score_ready": True,
            "score_status": "blocked",
        },
        intake_check={"intake_ready": True},
        rerun_evidence_status={"valid": True},
        risk_warning_clean_status={"valid": True},
        activation_ready=False,
    )

    assert boundary == {
        "template_approval_captured": True,
        "formal_authorization_allowed": False,
        "governance_write_allowed": False,
        "page_execution_proven": False,
        "full_score_closure_ready": False,
        "activation_ready": False,
        "status": "captured_but_not_activated",
        "blockers": [
            "scorecard_score_status_not_ready",
        ],
    }


def test_portfolio_home_business_owner_boundary_reports_activation_guard_gaps() -> None:
    boundary = _business_owner_approval_boundary(
        approval={"business_owner_approval_captured": True},
        scorecard={
            "full_score_ready": True,
            "score_status": "ready_for_full_score",
            "score_blockers": list(CURRENT_SCORE_BLOCKERS),
        },
        intake_check={"intake_ready": True},
        rerun_evidence_status={"valid": True},
        risk_warning_clean_status={"valid": True},
        activation_ready=False,
        dependencies=[{"available": False}],
        dependency_consistency_status="blocked",
        owner_intake_alignment={"status": "blocked"},
        score_blocker_action_coverage={
            "status": "clean",
            "blockers": [],
            "unassigned_blockers": [],
            "covered_blockers": list(CURRENT_SCORE_BLOCKERS[:-1]),
        },
        closure_artifact_presence_summary={
            "current": False,
            "blockers": ["owner_handoff_packet_stale"],
        },
    )

    assert boundary == {
        "template_approval_captured": True,
        "formal_authorization_allowed": False,
        "governance_write_allowed": False,
        "page_execution_proven": False,
        "full_score_closure_ready": False,
        "activation_ready": False,
        "status": "captured_but_not_activated",
        "blockers": [
            "evidence_dependency_unavailable",
            "dependency_consistency_not_ready",
            "owner_decision_intake_alignment_not_ready",
            "score_blocker_action_coverage_not_ready",
            "closure_artifact_presence_not_current",
        ],
    }


def test_portfolio_home_business_owner_approval_packet_reports_pending_scope() -> None:
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=2,
    )

    assert packet["packet_kind"] == "portfolio_home_business_owner_approval_packet"
    assert packet["packet_status"] == "pending"
    assert packet["activation_ready"] is False
    assert packet["current_score"] == "99.86 / 100"
    assert packet["remaining_gap"] == "0.14"
    assert packet["score_status"] == "blocked"
    assert packet["score_blockers"] == CURRENT_SCORE_BLOCKERS

    approval = packet["approval_summary"]
    assert approval["approval_status"] == "pending"
    assert approval["report_date"] == "2026-05-31"
    assert approval["business_owner_approval_captured"] is False
    assert approval["formal_use_allowed"] is False
    assert approval["closure_approved"] is False
    assert approval["approval_action_item_count"] == 19
    assert approval["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_capture_ready_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }
    assert approval["approval_field_status"]["approval_date"] == "missing"
    assert approval["approval_field_status"]["verification_commands_rerun"] == "pending"
    assert approval["approval_action_items"][0]["blocker"] == "business_owner_name"
    assert packet["business_owner_approval_boundary"] == {
        "template_approval_captured": False,
        "formal_authorization_allowed": False,
        "governance_write_allowed": False,
        "page_execution_proven": False,
        "full_score_closure_ready": False,
        "activation_ready": False,
        "status": "pending_owner_input",
        "blockers": [
            "business_owner_approval_not_captured",
            "scorecard_full_score_not_ready",
            "scorecard_score_status_not_ready",
            "owner_decision_intake_not_ready",
            "risk_warning_not_clean",
        ],
    }
    risk_warning_status = packet["risk_warning_clean_status"]
    assert {
        key: risk_warning_status[key]
        for key in (
            "status",
            "valid",
            "decision_status",
            "decision_blockers",
            "evidence_scope",
        )
    } == {
        "status": "blocked",
        "valid": False,
        "decision_status": "blocked",
        "decision_blockers": [
            "risk_tensor_quality_warning",
            "risk_tensor_warning_mismatch",
        ],
        "evidence_scope": RISK_WARNING_EVIDENCE_SCOPE,
    }
    warning_matrix = risk_warning_status["warning_resolution_matrix"]
    assert [
        (row["warning_key"], row["owner"], row["current_status"])
        for row in warning_matrix
    ] == _expected_current_warning_resolution_matrix_summary()
    assert risk_warning_status["duration_exclusion_delta_detail"] == (
        _expected_current_duration_exclusion_delta_detail()
    )
    assert risk_warning_status["risk_tensor_rematerialization_preview"] == (
        _expected_current_risk_tensor_rematerialization_preview()
    )
    assert risk_warning_status["risk_tensor_rematerialization_preview"][
        "writes_database"
    ] is False
    assert risk_warning_status["risk_tensor_rematerialization_preview"][
        "approves_metric_or_page"
    ] is False
    assert (
        risk_warning_status["risk_tensor_rematerialization_preview"]["certification_effect"]
        == "none"
    )
    assert warning_matrix[0]["current_evidence"] == {
        "parsed": ["15Y", "20Y", "2Y", "6M"],
        "recomputed": ["20Y", "2Y", "6M"],
    }
    assert warning_matrix[0]["evidence_scope"] == RISK_WARNING_RESOLUTION_SCOPE
    assert packet["score_blocker_action_coverage"] == {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": CURRENT_SCORE_BLOCKERS,
    }
    assert packet["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }
    assert packet["closure_artifact_presence_summary"] == {
        "status": "current",
        "current": True,
        "blockers": [],
        "artifact_current_summary": {
            "krd": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "maturity": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "business_owner_approval_template": {
                "status": "present",
                "current": True,
                "current_blockers": [],
            },
            "exact_bucket_schema_evidence": {
                "status": "not_required",
                "current": True,
                "current_blockers": [],
            },
            "nearest_bucket_approval_evidence": {
                "status": "not_required",
                "current": True,
                "current_blockers": [],
            },
            "maturity_scoped_exclusion_evidence": {
                "status": "not_required",
                "current": True,
                "current_blockers": [],
            },
        },
    }

    assert packet["owner_decision_intake_summary"] == {
        "intake_status": "pending_owner_decisions",
        "intake_ready": False,
        "dependency_consistency_status": "consistent",
        "dependency_csv_summary_alignment": {
            "status": "consistent",
            "blockers": [],
        },
        "csv_check_summary": {
            "krd_summary_row_count": 3,
            "krd_detail_row_count": 500,
            "krd_owner_decision_fields_blank": True,
            "bond_missing_maturity_row_count": 0,
            "tyw_liability_missing_maturity_row_count": 1455,
            "maturity_owner_fields_blank": True,
        },
        "generated_owner_fields_boundaries": {
            "krd_contract_decision_manifest": True,
            "maturity_remediation_manifest": True,
        },
        "owner_input_boundary": {
            "generated_export_owner_fields_must_be_blank": True,
            "filled_owner_fields_are_owner_input_only": True,
            "generated_export_system_fields_must_be_current": True,
            "allowed_pre_intake_dependency_blockers": [
                "krd_contract_decision_manifest_owner_decision_fields_not_blank",
                "maturity_remediation_manifest_owner_fields_not_blank",
            ],
            "pre_intake_dependency_blockers": [],
            "active_dependency_blockers": [],
            "active_export_current_blockers": [],
        },
        "export_current_summary": _expected_export_current_summary(),
        "owner_decision_statuses": {
            "risk_owner": "pending",
            "data_owner": "pending",
            "business_owner": "pending",
        },
        "owner_decision_blockers": [
            "krd_owner_decision_missing",
            "maturity_owner_decision_missing",
            "business_owner_approval_missing",
        ],
        "decision_alignment": {
            "status": "consistent",
            "blockers": [],
            "business_template_decisions": {
                "krd_contract_decision": "<approve_nearest_bucket | require_exact_bucket_schema | reject>",
                "maturity_data_decision": "<remediate_source | approve_scoped_exclusion | reject>",
            },
            "owner_csv_decisions": {
                "krd": [],
                "maturity": [],
            },
        },
        "decision_counts": {
            "krd": {},
            "maturity": {},
        },
        "decision_gap_counts": {
            "krd": {
                "missing_decision_rows": 503,
                "summary_missing_decision_rows": 3,
                "detail_missing_decision_rows": 500,
            },
            "maturity": {
                "missing_decision_rows": 1455,
                "bond_missing_decision_rows": 0,
                "tyw_liability_missing_decision_rows": 1455,
            },
        },
        "note_gap_counts": {
            "krd": {},
            "maturity": {},
        },
        "exact_bucket_schema_evidence": {
            "status": "not_required",
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
            "valid": True,
            "blockers": [],
        },
        "nearest_bucket_approval_evidence": (
            _expected_not_required_nearest_bucket_approval_evidence()
        ),
        "maturity_scoped_exclusion_evidence": {
            "status": "not_required",
            "artifact": (
                "docs/portfolio/maturity-remediation/2026-05-31/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
    }
    assert packet["scorecard_owner_decision_intake_gate_summary"] == {
        "status": "pending",
        "intake_status": "pending_owner_decisions",
        "intake_ready": False,
        "dependency_consistency_status": "consistent",
        "dependency_csv_summary_alignment": {
            "status": "consistent",
            "blockers": [],
        },
        "owner_input_boundary": {
            "generated_export_owner_fields_must_be_blank": True,
            "filled_owner_fields_are_owner_input_only": True,
            "generated_export_system_fields_must_be_current": True,
            "allowed_pre_intake_dependency_blockers": [
                "krd_contract_decision_manifest_owner_decision_fields_not_blank",
                "maturity_remediation_manifest_owner_fields_not_blank",
            ],
            "pre_intake_dependency_blockers": [],
            "active_dependency_blockers": [],
            "active_export_current_blockers": [],
        },
        "export_current_summary": _expected_export_current_summary(),
        "owner_decision_statuses": {
            "risk_owner": "pending",
            "data_owner": "pending",
            "business_owner": "pending",
        },
        "blockers": [
            "krd_owner_decision_missing",
            "maturity_owner_decision_missing",
            "business_owner_approval_missing",
        ],
        "decision_counts": {
            "krd": {},
            "maturity": {},
        },
        "decision_gap_counts": {
            "krd": {
                "missing_decision_rows": 503,
                "summary_missing_decision_rows": 3,
                "detail_missing_decision_rows": 500,
            },
            "maturity": {
                "missing_decision_rows": 1455,
                "bond_missing_decision_rows": 0,
                "tyw_liability_missing_decision_rows": 1455,
            },
        },
        "note_gap_counts": {
            "krd": {},
            "maturity": {},
        },
        "exact_bucket_schema_evidence": {
            "status": "not_required",
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
            "valid": True,
            "blockers": [],
        },
        "nearest_bucket_approval_evidence": (
            _expected_not_required_nearest_bucket_approval_evidence()
        ),
        "maturity_scoped_exclusion_evidence": {
            "status": "not_required",
            "artifact": (
                "docs/portfolio/maturity-remediation/2026-05-31/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
    }
    assert packet["owner_decision_intake_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": OWNER_ALIGNMENT_COMPARED_FIELDS,
    }

    guard = packet["activation_guard"]
    assert guard["no_automatic_approval"] is True
    assert guard["partial_activation_invalid"] is True
    assert guard["strict_scorecard_required"] is True
    assert guard["rerun_evidence_required"] is True
    assert guard["risk_warning_clean_required"] is True
    assert guard["owner_decision_intake_alignment_required"] is True
    assert guard["score_blocker_action_coverage_required"] is True
    assert guard["closure_artifact_presence_required"] is True
    assert guard["activation_ready"] is False
    assert guard["required_commands"] == [
        "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score --report-date 2026-05-31",
        "python scripts/check_portfolio_home_business_owner_approval.py --require-captured --report-date 2026-05-31",
        "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched --report-date 2026-05-31",
        "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean --report-date 2026-05-31",
        "python scripts/portfolio_home_risk_warning_consistency.py --require-clean --report-date 2026-05-31",
        "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent --report-date 2026-05-31",
        "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready --report-date 2026-05-31",
        "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current --report-date 2026-05-31",
        "python scripts/portfolio_home_evidence_packet_guard.py --require-clean --report-date 2026-05-31",
        "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched --output docs/portfolio/portfolio-home-evidence-snapshot.json --report-date 2026-05-31",
    ]


def test_portfolio_home_business_owner_approval_packet_lists_evidence_dependencies() -> None:
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
    )

    dependencies = {item["name"]: item for item in packet["evidence_dependencies"]}
    assert dependencies["signoff_packet"]["path"] == (
        "docs/portfolio/portfolio-home-full-closure-sign-off-packet.md"
    )
    assert dependencies["audit_packet"]["path"] == (
        "docs/audits/2026-06-05-portfolio-readiness-gate-audit.md"
    )
    assert dependencies["evidence_snapshot"]["command"] == (
        "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched --report-date 2026-05-31"
    )
    assert dependencies["owner_action_packet"]["command"] == (
        "python scripts/portfolio_home_owner_action_packet.py --limit 3 --report-date 2026-05-31"
    )
    assert dependencies["closure_artifact_presence_check"]["command"] == (
        "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current --report-date 2026-05-31"
    )
    assert dependencies["evidence_packet_guard"]["command"] == (
        "python scripts/portfolio_home_evidence_packet_guard.py --require-clean --report-date 2026-05-31"
    )
    assert dependencies["krd_contract_decision_manifest"]["path"] == (
        "docs/portfolio/krd-contract-decision/2026-05-31/manifest.json"
    )
    assert dependencies["krd_contract_decision_owner_summary"]["path"] == (
        "docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md"
    )
    assert dependencies["maturity_remediation_manifest"]["path"] == (
        "docs/portfolio/maturity-remediation/2026-05-31/manifest.json"
    )
    assert dependencies["maturity_remediation_owner_summary"]["path"] == (
        "docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md"
    )
    assert dependencies["dependency_consistency_strict_gate"]["command"] == (
        "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent --report-date 2026-05-31"
    )
    assert dependencies["owner_decision_intake_strict_gate"]["command"] == (
        "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready --report-date 2026-05-31"
    )
    assert dependencies["scorecard_strict_gate"]["command"] == (
        "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score --report-date 2026-05-31"
    )
    assert dependencies["business_owner_approval_strict_gate"]["command"] == (
        "python scripts/check_portfolio_home_business_owner_approval.py --require-captured --report-date 2026-05-31"
    )
    assert all(item["available"] is True for item in dependencies.values())


def test_portfolio_home_business_owner_approval_packet_reports_missing_rerun_artifact(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    if artifact.exists():
        artifact.unlink()

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "missing",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": ["rerun_evidence_artifact_missing"],
    }
    assert packet["activation_guard"]["rerun_evidence_required"] is True
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_accepts_valid_rerun_artifact(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    artifact.write_text(
        json.dumps(
            _valid_rerun_payload(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "valid",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": True,
        "blockers": [],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_verifier_results() -> None:
    payload = _valid_rerun_payload()
    verifier = payload["verification_report"]
    assert isinstance(verifier, dict)
    verifier.pop("results")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_verifier_result_count_mismatch",
            "rerun_evidence_verifier_results_empty",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_verifier_result_drift() -> None:
    payload = _valid_rerun_payload()
    verifier = payload["verification_report"]
    assert isinstance(verifier, dict)
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["matches_expected_when_blocked"] = False

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_verifier_result_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_verifier_result_state_drift() -> None:
    payload = _valid_rerun_payload()
    verifier = payload["verification_report"]
    assert isinstance(verifier, dict)
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["expected_state"] = "full_score"
    result["expected_exit"] = "exit_0"
    result["expected_when_blocked"] = "exit_nonzero"

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_verifier_result_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_manifest_consistency_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary.pop("manifest_consistency_statuses")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_manifest_consistency_statuses_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_owner_summary_paths() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary.pop("owner_summary_paths")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_owner_summary_paths_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_csv_check_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary.pop("csv_check_summary")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_csv_check_summary_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_non_consistent_manifest_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    manifest_statuses = approval_summary["manifest_consistency_statuses"]
    assert isinstance(manifest_statuses, dict)
    manifest_statuses["maturity_remediation_manifest"] = "blocked"

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_manifest_consistency_statuses_not_consistent",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_owner_summary_path() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    owner_summary_paths = approval_summary["owner_summary_paths"]
    assert isinstance(owner_summary_paths, dict)
    owner_summary_paths["krd_contract_decision_owner_summary"] = "docs/portfolio/stale.md"

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_owner_summary_paths_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_csv_count_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    csv_summary = approval_summary["csv_check_summary"]
    assert isinstance(csv_summary, dict)
    csv_summary["krd_detail_row_count"] = 499

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_csv_check_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_nonblank_owner_field_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    csv_summary = approval_summary["csv_check_summary"]
    assert isinstance(csv_summary, dict)
    csv_summary["maturity_owner_fields_blank"] = False

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_csv_check_summary_owner_fields_not_blank",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_risk_warning_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary.pop("risk_warning_clean_status")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_risk_warning_clean_status_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_business_owner_boundary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary.pop("business_owner_approval_boundary")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_business_owner_boundary_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_spoofed_business_owner_boundary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    boundary = approval_summary["business_owner_approval_boundary"]
    assert isinstance(boundary, dict)
    boundary["formal_authorization_allowed"] = True
    boundary["governance_write_allowed"] = True

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_business_owner_boundary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_spoofed_clean_risk_warning_summary() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    risk_summary = approval_summary["risk_warning_clean_status"]
    assert isinstance(risk_summary, dict)
    risk_summary["status"] = "clean"
    risk_summary["valid"] = True
    risk_summary["decision_status"] = "clean"
    risk_summary["decision_blockers"] = []

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_risk_warning_clean_status_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_risk_warning_scope() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    risk_summary = approval_summary["risk_warning_clean_status"]
    assert isinstance(risk_summary, dict)
    risk_summary.pop("evidence_scope", None)

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_risk_warning_clean_status_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_warning_resolution_matrix() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    risk_summary = approval_summary["risk_warning_clean_status"]
    assert isinstance(risk_summary, dict)
    risk_summary.pop("warning_resolution_matrix", None)

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_risk_warning_clean_status_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_rematerialization_preview() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    risk_summary = approval_summary["risk_warning_clean_status"]
    assert isinstance(risk_summary, dict)
    risk_summary.pop("risk_tensor_rematerialization_preview", None)

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_risk_warning_clean_status_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_score_blocker_action_coverage() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary.pop("score_blocker_action_coverage")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_score_blocker_action_coverage_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_score_blockers() -> None:
    payload = _valid_rerun_payload()
    payload.pop("score_blockers")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_score_blockers_missing",
            "rerun_evidence_approval_summary_score_blocker_action_coverage_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_incomplete_score_blocker_action_coverage() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    coverage = approval_summary["score_blocker_action_coverage"]
    assert isinstance(coverage, dict)
    covered_blockers = coverage["covered_blockers"]
    assert isinstance(covered_blockers, list)
    covered_blockers.remove("business_owner_approval")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_score_blocker_action_coverage_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_uses_snapshot_score_blockers_as_authority() -> None:
    payload = _valid_rerun_payload()
    score_blockers = payload["score_blockers"]
    assert isinstance(score_blockers, list)
    score_blockers.append("new_scorecard_blocker")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_score_blocker_action_coverage_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_scorecard_owner_gate_summary_field() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary.pop("status")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_scorecard_owner_gate_status() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["status"] = "ready"

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_scorecard_owner_gate_ready_flag() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["intake_ready"] = True

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_scorecard_owner_gate_owner_statuses() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["owner_decision_statuses"] = {
        "risk_owner": "ready",
        "data_owner": "pending",
        "business_owner": "pending",
    }

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_scorecard_owner_gate_gap_counts() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["decision_gap_counts"] = {
        "krd": {"missing_decision_rows": 0},
        "maturity": {"missing_decision_rows": 0},
    }

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_scorecard_owner_gate_decision_counts() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["decision_counts"] = {
        "krd": {"approve_nearest_bucket": 1},
        "maturity": {},
    }

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_wrong_scorecard_owner_gate_exact_bucket_evidence() -> None:
    payload = _valid_rerun_payload()
    gate_summary = payload["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["exact_bucket_schema_evidence"] = {
        "status": "approved",
        "valid": True,
        "blockers": [],
    }

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_missing_owner_decision_intake_summary() -> None:
    payload = _valid_rerun_payload()
    payload.pop("owner_decision_intake_summary")

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_owner_decision_intake_summary_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_invalid_owner_decision_intake_summary_type() -> None:
    payload = _valid_rerun_payload()
    payload["owner_decision_intake_summary"] = "ready"

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_owner_decision_intake_summary_missing",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_owner_decision_intake_summary_drift() -> None:
    payload = _valid_rerun_payload()
    direct_summary = payload["owner_decision_intake_summary"]
    assert isinstance(direct_summary, dict)
    direct_summary["intake_ready"] = True
    direct_summary["decision_gap_counts"] = {
        "krd": {
            "missing_decision_rows": 0,
            "summary_missing_decision_rows": 0,
            "detail_missing_decision_rows": 0,
        },
        "maturity": {
            "missing_decision_rows": 0,
            "bond_missing_decision_rows": 0,
            "tyw_liability_missing_decision_rows": 0,
        },
    }

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_owner_decision_intake_summary_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_blocked_top_level_owner_alignment() -> None:
    payload = _valid_rerun_payload()
    owner_alignment = payload["owner_decision_intake_alignment"]
    assert isinstance(owner_alignment, dict)
    owner_alignment["status"] = "blocked"
    owner_alignment["blockers"] = ["owner_decision_intake_alignment_intake_ready_mismatch"]

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_owner_intake_alignment_not_consistent",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_incomplete_top_level_owner_alignment_fields() -> None:
    payload = _valid_rerun_payload()
    owner_alignment = payload["owner_decision_intake_alignment"]
    assert isinstance(owner_alignment, dict)
    owner_alignment["compared_fields"] = OWNER_ALIGNMENT_COMPARED_FIELDS[:-1]

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_owner_intake_alignment_fields_mismatch",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_blocked_approval_summary_owner_alignment() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_alignment = approval_summary["owner_decision_intake_alignment"]
    assert isinstance(approval_alignment, dict)
    approval_alignment["status"] = "blocked"
    approval_alignment["blockers"] = ["owner_decision_intake_alignment_owner_input_boundary_mismatch"]

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_alignment_not_consistent",
        ],
    }


def test_portfolio_home_rerun_evidence_blocks_incomplete_approval_summary_owner_alignment_fields() -> None:
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_alignment = approval_summary["owner_decision_intake_alignment"]
    assert isinstance(approval_alignment, dict)
    approval_alignment["compared_fields"] = OWNER_ALIGNMENT_COMPARED_FIELDS[:-1]

    assert rerun_evidence_payload_status(payload, report_date="2026-05-31") == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_alignment_fields_mismatch",
        ],
    }


def test_portfolio_home_business_owner_approval_packet_blocks_stale_rerun_artifact_without_capture_scope_summary(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_field_status = approval_summary["approval_field_status"]
    assert isinstance(approval_field_status, dict)
    approval_field_status.pop("evidence_scope_captures_business_owner_approval")
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_capture_scope_missing",
        ],
    }
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_blocks_invalid_capture_scope_summary(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_field_status = approval_summary["approval_field_status"]
    assert isinstance(approval_field_status, dict)
    approval_field_status["evidence_scope_captures_business_owner_approval"] = "invalid"
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_capture_scope_not_valid",
        ],
    }
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_blocks_stale_rerun_artifact_without_approval_date_status(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_field_status = approval_summary["approval_field_status"]
    assert isinstance(approval_field_status, dict)
    approval_field_status.pop("approval_date")
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_approval_date_missing",
        ],
    }
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_blocks_stale_rerun_artifact_without_verification_rerun_status(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_field_status = approval_summary["approval_field_status"]
    assert isinstance(approval_field_status, dict)
    approval_field_status.pop("verification_commands_rerun")
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_approval_summary_verification_commands_rerun_missing",
        ],
    }
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_blocks_stale_rerun_artifact_without_owner_boundary(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    payload["scorecard_owner_decision_intake_gate_summary"] = {}
    owner_alignment = payload["owner_decision_intake_alignment"]
    assert isinstance(owner_alignment, dict)
    owner_alignment["compared_fields"] = [
        "intake_status",
        "intake_ready",
        "dependency_consistency_status",
        "owner_decision_statuses",
        "decision_gap_counts",
        "note_gap_counts",
        "exact_bucket_schema_evidence",
    ]
    approval_summary = payload["business_owner_approval_packet_summary"]
    assert isinstance(approval_summary, dict)
    approval_alignment = approval_summary["owner_decision_intake_alignment"]
    assert isinstance(approval_alignment, dict)
    approval_alignment["compared_fields"] = [
        "intake_status",
        "intake_ready",
        "dependency_consistency_status",
        "owner_decision_statuses",
        "decision_gap_counts",
        "note_gap_counts",
        "exact_bucket_schema_evidence",
    ]
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_owner_input_boundary_missing",
            "rerun_evidence_scorecard_owner_gate_summary_mismatch",
            "rerun_evidence_owner_intake_alignment_owner_input_boundary_missing",
            "rerun_evidence_owner_intake_alignment_fields_mismatch",
            "rerun_evidence_approval_summary_alignment_owner_input_boundary_missing",
            "rerun_evidence_approval_summary_alignment_fields_mismatch",
        ],
    }
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_blocks_wrong_state_rerun_artifact(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    verifier = payload["verification_report"]
    assert isinstance(verifier, dict)
    verifier["expected_state"] = "full_score"
    verifier["verification_status"] = "matched_expected_full_score_state"
    verifier["all_matched_expected_when_blocked"] = None
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_verifier_state_mismatch",
            "rerun_evidence_verifier_blocked_expectation_missing",
        ],
    }
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_validates_manifest_consistency() -> None:
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
    )

    assert packet["dependency_consistency_status"] == "consistent"
    assert packet["dependency_consistency_blockers"] == []
    manifest_checks = {item["name"]: item for item in packet["manifest_consistency_checks"]}
    assert manifest_checks["krd_contract_decision_manifest"] == {
        "name": "krd_contract_decision_manifest",
        "status": "consistent",
        "path": "docs/portfolio/krd-contract-decision/2026-05-31/manifest.json",
        "expected_report_date": "2026-05-31",
        "actual_report_date": "2026-05-31",
        "expected_export_status": "decision_required",
        "actual_export_status": "decision_required",
        "expected_remap_tenor_count": 3,
        "actual_remap_tenor_count": 3,
        "expected_nonzero_dv01_rows": 500,
        "actual_nonzero_dv01_rows": 500,
        "expected_dv01_sum": "33365026.29780176",
        "actual_dv01_sum": "33365026.29780176",
        "expected_generated_owner_fields_must_be_blank": True,
        "actual_generated_owner_fields_must_be_blank": True,
        "csv_checks": {
            "summary_row_count": 3,
            "detail_row_count": 500,
            "owner_decision_fields_blank": True,
        },
        "blockers": [],
    }
    assert manifest_checks["maturity_remediation_manifest"] == {
        "name": "maturity_remediation_manifest",
        "status": "consistent",
        "path": "docs/portfolio/maturity-remediation/2026-05-31/manifest.json",
        "expected_report_date": "2026-05-31",
        "actual_report_date": "2026-05-31",
        "expected_export_status": "blocked",
        "actual_export_status": "blocked",
        "expected_bond_no_maturity_rows": 114,
        "actual_bond_no_maturity_rows": 114,
        "expected_bond_no_maturity_market_value": "37622164239.83000008",
        "actual_bond_no_maturity_market_value": "37622164239.83000008",
        "expected_bond_missing_maturity_rows": 0,
        "actual_bond_missing_maturity_rows": 0,
        "expected_tyw_liability_missing_maturity_rows": 1455,
        "actual_tyw_liability_missing_maturity_rows": 1455,
        "expected_bond_missing_maturity_market_value": "0",
        "actual_bond_missing_maturity_market_value": "0",
        "expected_tyw_liability_missing_maturity_principal": "43822652393.01000002",
        "actual_tyw_liability_missing_maturity_principal": "43822652393.01000002",
        "expected_generated_owner_fields_must_be_blank": True,
        "actual_generated_owner_fields_must_be_blank": True,
        "csv_checks": {
            "bond_missing_maturity_row_count": 0,
            "tyw_liability_missing_maturity_row_count": 1455,
            "owner_fields_blank": True,
        },
        "blockers": [],
    }


def test_portfolio_home_business_owner_approval_packet_blocks_stale_or_mismatched_manifest(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")

    krd_manifest = docs_dir / "portfolio" / "krd-contract-decision" / "2026-05-31" / "manifest.json"
    krd_payload = json.loads(krd_manifest.read_text(encoding="utf-8"))
    krd_payload["report_date"] = "2026-04-30"
    krd_payload["export_summary"]["nonzero_dv01_rows"] = 499
    krd_manifest.write_text(json.dumps(krd_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    maturity_manifest = docs_dir / "portfolio" / "maturity-remediation" / "2026-05-31" / "manifest.json"
    maturity_payload = json.loads(maturity_manifest.read_text(encoding="utf-8"))
    maturity_payload["export_status"] = "clean"
    maturity_payload["export_summary"]["bond_missing_maturity_rows"] = 1
    maturity_manifest.write_text(
        json.dumps(maturity_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["dependency_consistency_status"] == "blocked"
    assert packet["activation_ready"] is False
    assert packet["activation_guard"]["dependency_consistency_required"] is True
    assert packet["dependency_consistency_blockers"] == [
        "krd_contract_decision_manifest_report_date_mismatch",
        "krd_contract_decision_manifest_nonzero_dv01_rows_mismatch",
        "maturity_remediation_manifest_export_status_mismatch",
        "maturity_remediation_manifest_bond_missing_maturity_rows_mismatch",
    ]
    assert "approval_dependency_consistency_blocked" in packet["score_blockers"]


def test_portfolio_home_business_owner_approval_packet_blocks_dirty_owner_csv_fields(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")

    krd_summary = docs_dir / "portfolio" / "krd-contract-decision" / "2026-05-31" / "krd_remap_summary.csv"
    krd_text = krd_summary.read_text(encoding="utf-8-sig")
    krd_summary.write_text(
        krd_text.replace("20Y,39,39,", "20Y,39,39,", 1).replace("mapped,,", "mapped,approve_nearest_bucket,", 1),
        encoding="utf-8-sig",
    )

    tyw_csv = docs_dir / "portfolio" / "maturity-remediation" / "2026-05-31" / "tyw_liability_missing_maturity.csv"
    tyw_text = tyw_csv.read_text(encoding="utf-8-sig")
    tyw_csv.write_text(
        tyw_text.replace(",,,\n", ",2027-01-01,,\n", 1),
        encoding="utf-8-sig",
    )

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_dir,
    )

    assert packet["dependency_consistency_status"] == "blocked"
    assert packet["activation_ready"] is False
    assert packet["dependency_consistency_blockers"] == [
        "krd_contract_decision_manifest_owner_decision_fields_not_blank",
        "maturity_remediation_manifest_owner_fields_not_blank",
    ]


def test_portfolio_home_business_owner_approval_packet_requires_owner_decision_intake_ready(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    docs_root = tmp_path / "docs"
    template = tmp_path / "portfolio-approval.md"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    _write_blocked_fixture_manifests(docs_root, duckdb_path)
    template.write_text(_full_approval_template_text(), encoding="utf-8")

    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date="2026-05-31",
        template_path=template,
        limit=2,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"]["intake_ready"] is False
    assert packet["owner_decision_intake_summary"]["owner_decision_blockers"] == [
        "krd_owner_decision_missing",
        "maturity_owner_decision_missing",
    ]
    assert packet["activation_ready"] is False
    assert packet["packet_status"] == "pending"
    assert packet["activation_guard"]["owner_decision_intake_required"] is True


def test_portfolio_home_business_owner_approval_packet_labels_signed_template_without_activation(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    docs_root = tmp_path / "docs"
    template = tmp_path / "portfolio-approval.md"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    _write_blocked_fixture_manifests(docs_root, duckdb_path)
    template.write_text(_full_approval_template_text(), encoding="utf-8")

    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date="2026-05-31",
        template_path=template,
        limit=2,
        docs_root=docs_root,
    )

    assert packet["approval_summary"]["business_owner_approval_captured"] is True
    assert packet["activation_ready"] is False
    assert packet["business_owner_approval_boundary"] == {
        "template_approval_captured": True,
        "formal_authorization_allowed": False,
        "governance_write_allowed": False,
        "page_execution_proven": False,
        "full_score_closure_ready": False,
        "activation_ready": False,
        "status": "captured_but_not_activated",
        "blockers": [
            "scorecard_full_score_not_ready",
            "scorecard_score_status_not_ready",
            "owner_decision_intake_not_ready",
            "rerun_evidence_not_valid",
            "risk_warning_not_clean",
            "evidence_dependency_unavailable",
        ],
    }


def test_owner_decision_intake_alignment_blocks_packet_gate_mismatch() -> None:
    direct = {
        "intake_status": "pending_owner_decisions",
        "intake_ready": False,
        "dependency_consistency_status": "consistent",
        "dependency_csv_summary_alignment": {
            "status": "consistent",
            "blockers": [],
        },
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": True},
        "owner_decision_statuses": {"risk_owner": "pending"},
        "decision_counts": {"krd": {}, "maturity": {}},
        "decision_gap_counts": {"krd": {"missing_decision_rows": 503}},
        "note_gap_counts": {"krd": {}},
        "exact_bucket_schema_evidence": {"status": "not_required"},
        "nearest_bucket_approval_evidence": {"status": "not_required"},
    }
    scorecard_gate = {
        **direct,
        "dependency_consistency_status": "blocked",
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": False},
        "owner_decision_statuses": {"risk_owner": "ready"},
        "decision_counts": {"krd": {"approve_nearest_bucket": 1}, "maturity": {}},
    }

    assert owner_decision_intake_alignment(direct, scorecard_gate) == {
        "status": "blocked",
        "blockers": [
            "owner_decision_intake_alignment_dependency_consistency_status_mismatch",
            "owner_decision_intake_alignment_owner_input_boundary_mismatch",
            "owner_decision_intake_alignment_owner_decision_statuses_mismatch",
            "owner_decision_intake_alignment_decision_counts_mismatch",
        ],
        "compared_fields": OWNER_ALIGNMENT_COMPARED_FIELDS,
    }


def test_portfolio_home_business_owner_approval_packet_requires_clean_risk_warning_evidence(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    docs_root = tmp_path / "docs"
    template = tmp_path / "portfolio-approval.md"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    _write_blocked_fixture_manifests(docs_root)
    template.write_text(_full_approval_template_text(), encoding="utf-8")

    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date="2026-05-31",
        template_path=template,
        limit=2,
        docs_root=docs_root,
    )

    assert packet["risk_warning_clean_status"] == {
        "status": "blocked",
        "valid": False,
        "decision_status": "blocked",
        "decision_blockers": ["risk_tensor_quality_warning"],
        "evidence_scope": RISK_WARNING_EVIDENCE_SCOPE,
        "warning_resolution_matrix": _expected_fixture_warning_resolution_matrix(),
        "duration_exclusion_delta_detail": (
            _expected_fixture_duration_exclusion_delta_detail()
        ),
        "risk_tensor_rematerialization_preview": (
            _expected_fixture_risk_tensor_rematerialization_preview()
        ),
    }
    assert packet["activation_guard"]["risk_warning_clean_required"] is True
    assert packet["activation_ready"] is False


def test_portfolio_home_business_owner_approval_packet_blocks_partial_owner_evidence_activation(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    docs_root = tmp_path / "docs"
    template = tmp_path / "portfolio-approval.md"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    _write_blocked_fixture_manifests(docs_root, duckdb_path)
    template.write_text(
        _full_approval_template_text()
        .replace(
            "KRD contract decision: `require_exact_bucket_schema`",
            "KRD contract decision: `approve_nearest_bucket`",
        )
        .replace(
            "Maturity data decision: `remediate_source`",
            "Maturity data decision: `approve_scoped_exclusion`",
        )
        .replace(
            (
                "Decision notes: `<required if reject, request_changes, "
                "approve_nearest_bucket, or approve_scoped_exclusion>`"
            ),
            (
                "Decision notes: `Risk owner accepts nearest-bucket mapping; "
                "data owner signs scoped exclusion for current candidate review only.`"
            ),
        ),
        encoding="utf-8",
    )
    _fill_krd_decisions(
        docs_root,
        "approve_nearest_bucket",
        notes="Accepted for current candidate review only.",
    )
    _fill_maturity_decisions(
        docs_root,
        "approve_scoped_exclusion",
        comment="Signed exclusion for current candidate review only.",
    )
    _write_blocked_fixture_nearest_bucket_approval_evidence(docs_root)
    _write_blocked_fixture_maturity_scoped_exclusion_evidence(docs_root)

    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date="2026-05-31",
        template_path=template,
        limit=2,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"]["intake_ready"] is True
    assert packet["owner_decision_intake_summary"]["owner_decision_blockers"] == []
    assert packet["risk_warning_clean_status"]["valid"] is False
    assert packet["activation_ready"] is False
    assert packet["packet_status"] == "pending"
    assert packet["activation_guard"]["partial_owner_evidence_activation_invalid"] is True
    assert packet["business_owner_approval_boundary"]["blockers"] == [
        "scorecard_full_score_not_ready",
        "scorecard_score_status_not_ready",
        "rerun_evidence_not_valid",
        "risk_warning_not_clean",
        "evidence_dependency_unavailable",
    ]



def test_portfolio_home_business_owner_approval_packet_scopes_full_payload_commands_to_report_date(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    template = tmp_path / "portfolio-approval.md"
    docs_root = tmp_path / "docs"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)
    template.write_text(_approved_template_text(), encoding="utf-8")
    _write_clean_fixture_manifests(docs_root)

    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date="2026-06-06",
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    packet_commands = _collect_packet_command_strings(packet)
    assert packet_commands
    unscoped_commands = [
        (path, command)
        for path, command in packet_commands
        if "--report-date 2026-06-06" not in command
        and not _is_date_independent_meta_command(command)
    ]
    assert unscoped_commands == []
    dependency_commands = [
        item["command"] for item in packet["evidence_dependencies"] if "command" in item
    ]
    assert len(dependency_commands) == 8
    assert all("--report-date 2026-06-06" in command for command in dependency_commands)
    activation_commands = packet["activation_guard"]["required_commands"]
    assert len(activation_commands) == 10
    assert all("--report-date 2026-06-06" in command for command in activation_commands)

def test_portfolio_home_business_owner_approval_packet_cli_require_ready_fails_current_state() -> None:
    returncode, payload = _run_packet("--limit", "1", "--require-ready")

    assert returncode == 1
    assert payload["packet_status"] == "pending"
    assert payload["activation_ready"] is False
    assert payload["activation_guard"]["activation_ready"] is False
    assert payload["approval_summary"]["approval_action_item_count"] == 19


def test_portfolio_home_business_owner_approval_packet_rejects_negative_limit() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home business owner approval packet limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_business_owner_approval_packet_build_rejects_negative_limit() -> None:
    try:
        build_packet(
            duckdb_path=DUCKDB,
            report_date="2026-05-31",
            template_path=TEMPLATE,
            limit=-1,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "Portfolio-home business owner approval packet limit must be non-negative: -1"
        )
    else:
        raise AssertionError("negative business owner approval packet limit should be rejected")
