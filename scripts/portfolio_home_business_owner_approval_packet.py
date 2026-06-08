from __future__ import annotations

import argparse
import hashlib
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
from scripts.portfolio_home_closure_artifact_summary import (  # noqa: E402
    artifact_current_summary as build_artifact_current_summary,
    artifact_presence_report,
    closure_artifact_presence_summary,
)
from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    build_scorecard,
    non_negative_portfolio_limit,
)
from scripts.portfolio_home_limit import validate_non_negative_portfolio_limit  # noqa: E402
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_manifest_consistency import (  # noqa: E402
    consistency_blockers as manifest_consistency_blockers,
    generated_owner_fields_boundaries,
    manifest_consistency_checks,
    resolve_docs_path,
)
from scripts.portfolio_home_owner_decision_intake_check import (  # noqa: E402
    build_intake_check,
)
from scripts.portfolio_home_risk_warning_consistency import (  # noqa: E402
    EVIDENCE_SCOPE as RISK_WARNING_EVIDENCE_SCOPE,
    RESOLUTION_SCOPE as RISK_WARNING_RESOLUTION_SCOPE,
    build_evidence as build_risk_warning_evidence,
)
from scripts.portfolio_home_verification_report_guard import (  # noqa: E402
    blocked_verification_report_guard,
)


SIGNOFF_PACKET = "docs/portfolio/portfolio-home-full-closure-sign-off-packet.md"
AUDIT_PACKET = "docs/audits/2026-06-05-portfolio-readiness-gate-audit.md"

STRICT_SCORECARD_COMMAND = "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
STRICT_APPROVAL_COMMAND = "python scripts/check_portfolio_home_business_owner_approval.py --require-captured"
EVIDENCE_SNAPSHOT_COMMAND = (
    "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 "
    "--require-verifier-matched"
)
OWNER_ACTION_PACKET_COMMAND = "python scripts/portfolio_home_owner_action_packet.py --limit 3"
OWNER_ACTION_PACKET_STRICT_COMMAND = "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean"
ARTIFACT_PRESENCE_COMMAND = (
    "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current"
)
EVIDENCE_PACKET_GUARD_COMMAND = "python scripts/portfolio_home_evidence_packet_guard.py --require-clean"
DEPENDENCY_CONSISTENCY_STRICT_COMMAND = (
    "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent"
)
OWNER_DECISION_INTAKE_STRICT_COMMAND = (
    "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready"
)
RERUN_EVIDENCE_ARTIFACT = "docs/portfolio/portfolio-home-evidence-snapshot.json"
DEFAULT_OUTPUT = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-packet.json"
OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS = [
    "intake_status",
    "intake_ready",
    "dependency_consistency_status",
    "dependency_csv_summary_alignment",
    "owner_input_boundary",
    "export_current_summary",
    "owner_decision_statuses",
    "decision_counts",
    "decision_gap_counts",
    "note_gap_counts",
    "exact_bucket_schema_evidence",
    "nearest_bucket_approval_evidence",
    "maturity_scoped_exclusion_evidence",
]

RERUN_APPROVAL_SUMMARY_REQUIRED_DICT_FIELDS = {
    "manifest_consistency_statuses": "rerun_evidence_approval_summary_manifest_consistency_statuses_missing",
    "owner_summary_paths": "rerun_evidence_approval_summary_owner_summary_paths_missing",
    "csv_check_summary": "rerun_evidence_approval_summary_csv_check_summary_missing",
}
RERUN_APPROVAL_REQUIRED_MANIFEST_STATUSES = {
    "krd_contract_decision_manifest": "consistent",
    "maturity_remediation_manifest": "consistent",
}
RERUN_APPROVAL_REQUIRED_CSV_COUNTS = {
    "krd_summary_row_count": 3,
    "krd_detail_row_count": 500,
    "bond_missing_maturity_row_count": 114,
    "tyw_liability_missing_maturity_row_count": 1455,
}
RERUN_APPROVAL_REQUIRED_CSV_BLANK_FLAGS = [
    "krd_owner_decision_fields_blank",
    "maturity_owner_fields_blank",
]
PORTFOLIO_HOME_SCORE_BLOCKERS = [
    "risk_tensor_quality_warning",
    "krd_contract_decision_required",
    "bond_maturity_date_remediation_required",
    "tyw_liability_maturity_date_remediation_required",
    "duration_exclusion_warning_mismatch",
    "risk_tensor_warning_mismatch",
    "business_owner_approval",
    "owner_decision_intake_blocked",
]
RERUN_APPROVAL_REQUIRED_WARNING_RESOLUTION_MATRIX = [
    {
        "warning_key": "krd_bucket_remap",
        "owner": "risk_owner",
        "current_status": "blocked",
        "current_evidence": {
            "parsed": ["20Y", "2Y", "6M"],
            "recomputed": ["20Y", "2Y", "6M"],
        },
        "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
        "exit_criteria": (
            "Risk owner approves nearest-bucket KRD mapping or supplies exact-bucket "
            "schema evidence; KRD review queue exits 0."
        ),
        "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
    },
    {
        "warning_key": "duration_denominator_exclusion",
        "owner": "data_owner",
        "current_status": "blocked",
        "current_evidence": {
            "parsed": {
                "row_count": 120,
                "market_value_sum": "38318400505.50000008",
                "missing_maturity_rows": 114,
                "nonpositive_duration_rows": 6,
            },
            "recomputed": {
                "row_count": 120,
                "market_value_sum": "39109594105.50000008",
                "missing_maturity_rows": 114,
                "nonpositive_duration_rows": 6,
            },
        },
        "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "exit_criteria": (
            "Data owner remediates missing maturity dates or captures signed scoped "
            "exclusion; maturity remediation queue exits 0."
        ),
        "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
    },
    {
        "warning_key": "bond_liquidity_gap_missing_maturity",
        "owner": "data_owner",
        "current_status": "blocked",
        "current_evidence": {
            "parsed": {"missing_maturity_rows": 114},
            "recomputed": {"missing_maturity_rows": 114},
        },
        "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "exit_criteria": (
            "Bond missing maturity rows are remediated or signed scoped exclusion "
            "evidence is captured; maturity remediation queue exits 0."
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
        "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "exit_criteria": (
            "TYW liability missing maturity rows are remediated or signed scoped "
            "exclusion evidence is captured; maturity remediation queue exits 0."
        ),
        "evidence_scope": dict(RISK_WARNING_RESOLUTION_SCOPE),
    },
]
RERUN_APPROVAL_REQUIRED_RISK_WARNING_STATUS = {
    "status": "blocked",
    "valid": False,
    "decision_status": "blocked",
    "decision_blockers": [
        "risk_tensor_quality_warning",
        "risk_tensor_warning_mismatch",
    ],
    "evidence_scope": dict(RISK_WARNING_EVIDENCE_SCOPE),
    "warning_resolution_matrix": RERUN_APPROVAL_REQUIRED_WARNING_RESOLUTION_MATRIX,
    "duration_exclusion_delta_detail": {
        "status": "mismatch",
        "delta_basis": "recomputed_minus_parsed",
        "owner_reconciliation_hint": (
            "Recompute or rematerialize risk tensor warnings so parsed warning "
            "numbers match fact_formal_bond_analytics_daily evidence."
        ),
        "mismatch_fields": ["market_value_sum"],
        "delta": {
            "row_count": 0,
            "market_value_sum": "791193600.00000000",
            "missing_maturity_rows": 0,
            "nonpositive_duration_rows": 0,
        },
        "parsed_warning_text": (
            "120 rows carry market_value=38318400505.50000008 and are excluded "
            "from portfolio duration denominator: 114 without maturity_date; 6 "
            "with non-positive modified_duration. DV01 totals remain sourced from "
            "row dv01; duration metrics ignore these rows until inputs are remediated."
        ),
        "expected_warning_text_from_recomputed": (
            "120 rows carry market_value=39109594105.50000008 and are excluded "
            "from portfolio duration denominator: 114 without maturity_date; 6 "
            "with non-positive modified_duration. DV01 totals remain sourced from "
            "row dv01; duration metrics ignore these rows until inputs are remediated."
        ),
        "recomputed_breakdown_by_reason": [
            {
                "exclusion_reason": "missing_maturity",
                "row_count": 114,
                "market_value_sum": "37622164239.83000008",
                "dv01_sum": "0.00000000",
            },
            {
                "exclusion_reason": "nonpositive_duration",
                "row_count": 6,
                "market_value_sum": "1487429865.67000000",
                "dv01_sum": "0.00000000",
            },
        ],
    },
    "risk_tensor_rematerialization_preview": {
        "status": "would_remain_blocked",
        "preview_basis": "current_formal_facts_read_only",
        "writes_database": False,
        "approves_metric_or_page": False,
        "certification_effect": "none",
        "current_consistency_blockers": ["duration_exclusion_warning_mismatch"],
        "would_clear_consistency_blockers": ["duration_exclusion_warning_mismatch"],
        "preview_consistency_status": "consistent",
        "preview_consistency_blockers": [],
        "preview_quality_flag": "warning",
        "preview_decision_status": "blocked",
        "preview_decision_blockers": ["risk_tensor_quality_warning"],
        "preview_warnings": [
            "Non-standard tenor buckets remapped to nearest KRD bucket: 20Y, 2Y, 6M",
            (
                "120 rows carry market_value=39109594105.50000008 and are excluded "
                "from portfolio duration denominator: 114 without maturity_date; 6 "
                "with non-positive modified_duration. DV01 totals remain sourced from "
                "row dv01; duration metrics ignore these rows until inputs are remediated."
            ),
            "Excluded 114 rows without maturity_date from liquidity gap calculation.",
            "Excluded 1455 liability rows without maturity_date from liquidity gap calculation.",
        ],
    },
}
RERUN_APPROVAL_REQUIRED_BUSINESS_OWNER_BOUNDARY = {
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
RERUN_VERIFICATION_REPORT_BLOCKER_MAP = {
    "verification_report_missing": "rerun_evidence_verifier_missing",
    "verification_report_expected_state_mismatch": "rerun_evidence_verifier_state_mismatch",
    "verification_report_status_mismatch": "rerun_evidence_verifier_state_mismatch",
    "verification_report_expected_exit_not_matched": "rerun_evidence_verifier_not_matched",
    "verification_report_blocked_exit_not_matched": (
        "rerun_evidence_verifier_blocked_expectation_missing"
    ),
    "verification_report_result_count_mismatch": (
        "rerun_evidence_verifier_result_count_mismatch"
    ),
    "verification_report_results_empty": "rerun_evidence_verifier_results_empty",
    "verification_report_result_mismatch": "rerun_evidence_verifier_result_mismatch",
}


def _unique_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def packet_sha256(packet: dict[str, object]) -> str:
    canonical = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _current_status(output: Path, expected_packet: dict[str, object]) -> dict[str, object]:
    if not output.exists():
        actual_packet: dict[str, object] = {}
    else:
        try:
            parsed = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        actual_packet = parsed if isinstance(parsed, dict) else {}
    expected_hash = packet_sha256(expected_packet)
    actual_hash = packet_sha256(actual_packet)
    current = expected_hash == actual_hash
    return {
        "artifact": str(output),
        "status": "current" if current else "stale",
        "current": current,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
    }


def owner_decision_intake_alignment(
    direct_summary: dict[str, object],
    scorecard_gate_summary: dict[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    for field in OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS:
        if direct_summary.get(field) != scorecard_gate_summary.get(field):
            blockers.append(f"owner_decision_intake_alignment_{field}_mismatch")
    return {
        "status": "consistent" if not blockers else "blocked",
        "blockers": blockers,
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }


def _resolve_docs_path(path: str, docs_root: Path) -> Path:
    return resolve_docs_path(path, docs_root, ROOT)


def _path_available(path: str, docs_root: Path) -> bool:
    return _resolve_docs_path(path, docs_root).exists()


def _command_available(command: str) -> bool:
    for token in command.split():
        if token.endswith(".py"):
            return (ROOT / token).exists()
    return True


def _dependency(
    name: str,
    *,
    docs_root: Path,
    path: str | None = None,
    command: str | None = None,
) -> dict[str, object]:
    if path is None and command is None:
        raise ValueError("Either path or command is required.")
    item: dict[str, object] = {"name": name}
    if path is not None:
        item["path"] = path
        item["available"] = _path_available(path, docs_root)
    if command is not None:
        item["command"] = command
        item["available"] = _command_available(command)
    return item


def _evidence_dependencies(report_date: str, docs_root: Path) -> list[dict[str, object]]:
    return [
        _dependency("signoff_packet", docs_root=docs_root, path=SIGNOFF_PACKET),
        _dependency("audit_packet", docs_root=docs_root, path=AUDIT_PACKET),
        _dependency("evidence_snapshot", docs_root=docs_root, command=EVIDENCE_SNAPSHOT_COMMAND),
        _dependency("owner_action_packet", docs_root=docs_root, command=OWNER_ACTION_PACKET_COMMAND),
        _dependency(
            "closure_artifact_presence_check",
            docs_root=docs_root,
            command=ARTIFACT_PRESENCE_COMMAND,
        ),
        _dependency(
            "evidence_packet_guard",
            docs_root=docs_root,
            command=EVIDENCE_PACKET_GUARD_COMMAND,
        ),
        _dependency(
            "krd_contract_decision_manifest",
            docs_root=docs_root,
            path=f"docs/portfolio/krd-contract-decision/{report_date}/manifest.json",
        ),
        _dependency(
            "krd_contract_decision_owner_summary",
            docs_root=docs_root,
            path=f"docs/portfolio/krd-contract-decision/{report_date}/owner_summary.md",
        ),
        _dependency(
            "maturity_remediation_manifest",
            docs_root=docs_root,
            path=f"docs/portfolio/maturity-remediation/{report_date}/manifest.json",
        ),
        _dependency(
            "maturity_remediation_owner_summary",
            docs_root=docs_root,
            path=f"docs/portfolio/maturity-remediation/{report_date}/owner_summary.md",
        ),
        _dependency(
            "dependency_consistency_strict_gate",
            docs_root=docs_root,
            command=DEPENDENCY_CONSISTENCY_STRICT_COMMAND,
        ),
        _dependency(
            "owner_decision_intake_strict_gate",
            docs_root=docs_root,
            command=OWNER_DECISION_INTAKE_STRICT_COMMAND,
        ),
        _dependency("scorecard_strict_gate", docs_root=docs_root, command=STRICT_SCORECARD_COMMAND),
        _dependency(
            "business_owner_approval_strict_gate",
            docs_root=docs_root,
            command=STRICT_APPROVAL_COMMAND,
        ),
    ]


def _approval_summary(approval: dict[str, object]) -> dict[str, object]:
    return {
        "approval_status": approval["approval_status"],
        "report_date": approval["report_date"],
        "business_owner_approval_captured": approval["business_owner_approval_captured"],
        "formal_use_allowed": approval["formal_use_allowed"],
        "closure_approved": approval["closure_approved"],
        "approval_action_item_count": approval["approval_action_item_count"],
        "approval_action_items": approval["approval_action_items"],
        "approval_field_status": approval["approval_field_status"],
        "remaining_blockers": approval["remaining_blockers"],
        "evidence_scope": approval["evidence_scope"],
    }


def _owner_decision_intake_summary(intake_check: dict[str, object]) -> dict[str, object]:
    owner_decision_summary = intake_check.get("owner_decision_summary", {})
    assert isinstance(owner_decision_summary, dict)
    krd_summary = owner_decision_summary.get("krd", {})
    maturity_summary = owner_decision_summary.get("maturity", {})
    decision_alignment = owner_decision_summary.get("decision_alignment", {})
    assert isinstance(krd_summary, dict)
    assert isinstance(maturity_summary, dict)
    assert isinstance(decision_alignment, dict)
    return {
        "intake_status": intake_check.get("intake_status"),
        "intake_ready": intake_check.get("intake_ready"),
        "dependency_consistency_status": intake_check.get("dependency_consistency_status"),
        "dependency_csv_summary_alignment": intake_check.get(
            "dependency_csv_summary_alignment",
            {},
        ),
        "csv_check_summary": intake_check.get("csv_check_summary", {}),
        "generated_owner_fields_boundaries": intake_check.get(
            "generated_owner_fields_boundaries",
            {},
        ),
        "owner_input_boundary": intake_check.get("owner_input_boundary", {}),
        "export_current_summary": intake_check.get("export_current_summary", {}),
        "owner_decision_statuses": intake_check.get("owner_decision_statuses"),
        "owner_decision_blockers": intake_check.get("owner_decision_blockers", []),
        "decision_alignment": decision_alignment,
        "decision_counts": {
            "krd": krd_summary.get("decision_counts", {}),
            "maturity": maturity_summary.get("decision_counts", {}),
        },
        "decision_gap_counts": {
            "krd": krd_summary.get("decision_gap_counts", {}),
            "maturity": maturity_summary.get("decision_gap_counts", {}),
        },
        "note_gap_counts": {
            "krd": krd_summary.get("note_gap_counts", {}),
            "maturity": maturity_summary.get("comment_gap_counts", {}),
        },
        "exact_bucket_schema_evidence": krd_summary.get("exact_bucket_schema_evidence", {}),
        "nearest_bucket_approval_evidence": krd_summary.get(
            "nearest_bucket_approval_evidence",
            {},
        ),
        "maturity_scoped_exclusion_evidence": maturity_summary.get(
            "scoped_exclusion_evidence",
            {},
        ),
    }


def _scorecard_owner_decision_intake_gate_summary(
    scorecard: dict[str, object],
) -> dict[str, object]:
    gates = scorecard.get("gates", {})
    assert isinstance(gates, dict)
    owner_gate = gates.get("owner_decision_intake", {})
    assert isinstance(owner_gate, dict)
    return {
        "status": owner_gate.get("status"),
        "intake_status": owner_gate.get("intake_status"),
        "intake_ready": owner_gate.get("intake_ready"),
        "dependency_consistency_status": owner_gate.get("dependency_consistency_status"),
        "dependency_csv_summary_alignment": owner_gate.get(
            "dependency_csv_summary_alignment",
            {},
        ),
        "owner_input_boundary": owner_gate.get("owner_input_boundary", {}),
        "export_current_summary": owner_gate.get("export_current_summary", {}),
        "owner_decision_statuses": owner_gate.get("owner_decision_statuses"),
        "blockers": owner_gate.get("blockers", []),
        "decision_counts": owner_gate.get("decision_counts", {}),
        "decision_gap_counts": owner_gate.get("decision_gap_counts", {}),
        "note_gap_counts": owner_gate.get("note_gap_counts", {}),
        "exact_bucket_schema_evidence": owner_gate.get("exact_bucket_schema_evidence", {}),
        "nearest_bucket_approval_evidence": owner_gate.get(
            "nearest_bucket_approval_evidence",
            {},
        ),
        "maturity_scoped_exclusion_evidence": owner_gate.get(
            "maturity_scoped_exclusion_evidence",
            {},
        ),
    }


def _expected_rerun_owner_summary_paths(report_date: str) -> dict[str, str]:
    return {
        "krd_contract_decision_owner_summary": (
            f"docs/portfolio/krd-contract-decision/{report_date}/owner_summary.md"
        ),
        "maturity_remediation_owner_summary": (
            f"docs/portfolio/maturity-remediation/{report_date}/owner_summary.md"
        ),
    }


def _expected_rerun_scorecard_owner_gate_summary(report_date: str) -> dict[str, object]:
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
        "export_current_summary": {
            "krd": {
                "current": True,
                "status": "current",
                "current_blockers": [],
            },
            "maturity": {
                "current": True,
                "status": "current",
                "current_blockers": [],
            },
        },
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
                "missing_decision_rows": 1569,
                "bond_missing_decision_rows": 114,
                "tyw_liability_missing_decision_rows": 1455,
            },
        },
        "note_gap_counts": {
            "krd": {},
            "maturity": {},
        },
        "exact_bucket_schema_evidence": {
            "status": "not_required",
            "artifact": (
                f"docs/portfolio/krd-contract-decision/{report_date}/"
                "exact_bucket_schema_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
        "nearest_bucket_approval_evidence": {
            "status": "not_required",
            "artifact": (
                f"docs/portfolio/krd-contract-decision/{report_date}/"
                "nearest_bucket_approval_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
        "maturity_scoped_exclusion_evidence": {
            "status": "not_required",
            "artifact": (
                f"docs/portfolio/maturity-remediation/{report_date}/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
    }


def _expected_rerun_owner_decision_intake_summary(report_date: str) -> dict[str, object]:
    gate_summary = _expected_rerun_scorecard_owner_gate_summary(report_date)
    return {
        "intake_status": gate_summary["intake_status"],
        "intake_ready": gate_summary["intake_ready"],
        "dependency_consistency_status": gate_summary["dependency_consistency_status"],
        "dependency_csv_summary_alignment": gate_summary["dependency_csv_summary_alignment"],
        "csv_check_summary": {
            "krd_summary_row_count": 3,
            "krd_detail_row_count": 500,
            "krd_owner_decision_fields_blank": True,
            "bond_missing_maturity_row_count": 114,
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


def _rerun_alignment_blockers(
    alignment: dict[str, object],
    *,
    not_consistent_blocker: str,
    fields_mismatch_blocker: str,
) -> list[str]:
    blockers: list[str] = []
    if alignment.get("status") != "consistent" or alignment.get("blockers") != []:
        blockers.append(not_consistent_blocker)
    if alignment.get("compared_fields") != OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS:
        blockers.append(fields_mismatch_blocker)
    return blockers


def _rerun_verification_report_blockers(verifier: object) -> list[str]:
    guard = blocked_verification_report_guard(verifier)
    result: list[str] = []
    for blocker in guard["blockers"]:
        mapped = RERUN_VERIFICATION_REPORT_BLOCKER_MAP[str(blocker)]
        if mapped not in result:
            result.append(mapped)
    return result


def rerun_evidence_payload_status(
    payload: object,
    *,
    report_date: str,
) -> dict[str, object]:
    blockers: list[str] = []
    status = "valid"
    if not isinstance(payload, dict):
        payload = {}
        blockers.append("rerun_evidence_artifact_invalid_payload")

    if payload.get("snapshot_kind") != "portfolio_home_closure_evidence":
        blockers.append("rerun_evidence_snapshot_kind_mismatch")
    if payload.get("page_id") != "PAGE-PORTFOLIO-HOME-001":
        blockers.append("rerun_evidence_page_id_mismatch")
    if payload.get("page_slug") != "portfolio":
        blockers.append("rerun_evidence_page_slug_mismatch")
    if payload.get("report_date") != report_date:
        blockers.append("rerun_evidence_report_date_mismatch")
    expected_score_blockers = _unique_strings(payload.get("score_blockers"))
    if not expected_score_blockers:
        blockers.append("rerun_evidence_score_blockers_missing")

    blockers.extend(_rerun_verification_report_blockers(payload.get("verification_report")))

    scorecard_owner_gate = payload.get("scorecard_owner_decision_intake_gate_summary", {})
    if not isinstance(scorecard_owner_gate, dict):
        scorecard_owner_gate = {}
        blockers.append("rerun_evidence_scorecard_owner_gate_missing")
    if "owner_input_boundary" not in scorecard_owner_gate:
        blockers.append("rerun_evidence_owner_input_boundary_missing")
    if scorecard_owner_gate != _expected_rerun_scorecard_owner_gate_summary(report_date):
        blockers.append("rerun_evidence_scorecard_owner_gate_summary_mismatch")

    owner_decision_summary_missing = "owner_decision_intake_summary" not in payload
    if owner_decision_summary_missing:
        owner_decision_summary = {}
        blockers.append("rerun_evidence_owner_decision_intake_summary_missing")
    else:
        owner_decision_summary = payload.get("owner_decision_intake_summary")
    if not isinstance(owner_decision_summary, dict):
        owner_decision_summary_missing = True
        owner_decision_summary = {}
        blockers.append("rerun_evidence_owner_decision_intake_summary_missing")
    elif (
        not owner_decision_summary_missing
        and owner_decision_summary != _expected_rerun_owner_decision_intake_summary(report_date)
    ):
        blockers.append("rerun_evidence_owner_decision_intake_summary_mismatch")

    owner_alignment = payload.get("owner_decision_intake_alignment", {})
    if not isinstance(owner_alignment, dict):
        owner_alignment = {}
        blockers.append("rerun_evidence_owner_intake_alignment_missing")
    owner_compared_fields = owner_alignment.get("compared_fields", [])
    if not isinstance(owner_compared_fields, list) or "owner_input_boundary" not in owner_compared_fields:
        blockers.append("rerun_evidence_owner_intake_alignment_owner_input_boundary_missing")
    blockers.extend(
        _rerun_alignment_blockers(
            owner_alignment,
            not_consistent_blocker="rerun_evidence_owner_intake_alignment_not_consistent",
            fields_mismatch_blocker="rerun_evidence_owner_intake_alignment_fields_mismatch",
        )
    )
    approval_summary = payload.get("business_owner_approval_packet_summary", {})
    if not isinstance(approval_summary, dict):
        approval_summary = {}
    approval_alignment = approval_summary.get("owner_decision_intake_alignment", {})
    if not isinstance(approval_alignment, dict):
        approval_alignment = {}
        blockers.append("rerun_evidence_approval_summary_alignment_missing")
    approval_compared_fields = approval_alignment.get("compared_fields", [])
    if (
        not isinstance(approval_compared_fields, list)
        or "owner_input_boundary" not in approval_compared_fields
    ):
        blockers.append("rerun_evidence_approval_summary_alignment_owner_input_boundary_missing")
    blockers.extend(
        _rerun_alignment_blockers(
            approval_alignment,
            not_consistent_blocker="rerun_evidence_approval_summary_alignment_not_consistent",
            fields_mismatch_blocker="rerun_evidence_approval_summary_alignment_fields_mismatch",
        )
    )
    for field, blocker in RERUN_APPROVAL_SUMMARY_REQUIRED_DICT_FIELDS.items():
        if not isinstance(approval_summary.get(field), dict):
            blockers.append(blocker)
    manifest_statuses = approval_summary.get("manifest_consistency_statuses")
    if isinstance(manifest_statuses, dict) and any(
        manifest_statuses.get(name) != status
        for name, status in RERUN_APPROVAL_REQUIRED_MANIFEST_STATUSES.items()
    ):
        blockers.append("rerun_evidence_approval_summary_manifest_consistency_statuses_not_consistent")
    owner_summary_paths = approval_summary.get("owner_summary_paths")
    if (
        isinstance(owner_summary_paths, dict)
        and owner_summary_paths != _expected_rerun_owner_summary_paths(report_date)
    ):
        blockers.append("rerun_evidence_approval_summary_owner_summary_paths_mismatch")
    csv_check_summary = approval_summary.get("csv_check_summary")
    if isinstance(csv_check_summary, dict):
        if any(
            csv_check_summary.get(name) != count
            for name, count in RERUN_APPROVAL_REQUIRED_CSV_COUNTS.items()
        ):
            blockers.append("rerun_evidence_approval_summary_csv_check_summary_mismatch")
        if any(csv_check_summary.get(name) is not True for name in RERUN_APPROVAL_REQUIRED_CSV_BLANK_FLAGS):
            blockers.append("rerun_evidence_approval_summary_csv_check_summary_owner_fields_not_blank")
    risk_warning_clean_status = approval_summary.get("risk_warning_clean_status")
    if not isinstance(risk_warning_clean_status, dict):
        blockers.append("rerun_evidence_approval_summary_risk_warning_clean_status_missing")
    elif risk_warning_clean_status != RERUN_APPROVAL_REQUIRED_RISK_WARNING_STATUS:
        blockers.append("rerun_evidence_approval_summary_risk_warning_clean_status_mismatch")
    business_owner_boundary = approval_summary.get("business_owner_approval_boundary")
    if not isinstance(business_owner_boundary, dict):
        blockers.append("rerun_evidence_approval_summary_business_owner_boundary_missing")
    elif business_owner_boundary != RERUN_APPROVAL_REQUIRED_BUSINESS_OWNER_BOUNDARY:
        blockers.append("rerun_evidence_approval_summary_business_owner_boundary_mismatch")
    score_blocker_action_coverage = approval_summary.get("score_blocker_action_coverage")
    if not isinstance(score_blocker_action_coverage, dict):
        blockers.append("rerun_evidence_approval_summary_score_blocker_action_coverage_missing")
    elif (
        score_blocker_action_coverage.get("status") != "clean"
        or score_blocker_action_coverage.get("blockers") != []
        or score_blocker_action_coverage.get("unassigned_blockers") != []
        or score_blocker_action_coverage.get("covered_blockers") != expected_score_blockers
    ):
        blockers.append("rerun_evidence_approval_summary_score_blocker_action_coverage_mismatch")
    approval_field_status = approval_summary.get("approval_field_status", {})
    if not isinstance(approval_field_status, dict):
        approval_field_status = {}
    if "approval_date" not in approval_field_status:
        blockers.append("rerun_evidence_approval_summary_approval_date_missing")
    if "verification_commands_rerun" not in approval_field_status:
        blockers.append("rerun_evidence_approval_summary_verification_commands_rerun_missing")
    capture_scope_status = approval_field_status.get("evidence_scope_captures_business_owner_approval")
    if capture_scope_status is None:
        blockers.append("rerun_evidence_approval_summary_capture_scope_missing")
    elif capture_scope_status != "valid":
        blockers.append("rerun_evidence_approval_summary_capture_scope_not_valid")

    if blockers:
        status = "blocked"
    return {
        "status": status,
        "artifact": RERUN_EVIDENCE_ARTIFACT,
        "valid": not blockers,
        "blockers": blockers,
    }


def _rerun_evidence_status(*, docs_root: Path, report_date: str) -> dict[str, object]:
    artifact = _resolve_docs_path(RERUN_EVIDENCE_ARTIFACT, docs_root)
    if not artifact.exists():
        return {
            "status": "missing",
            "artifact": RERUN_EVIDENCE_ARTIFACT,
            "valid": False,
            "blockers": ["rerun_evidence_artifact_missing"],
        }

    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "blocked",
            "artifact": RERUN_EVIDENCE_ARTIFACT,
            "valid": False,
            "blockers": ["rerun_evidence_artifact_invalid_json"],
        }
    return rerun_evidence_payload_status(payload, report_date=report_date)


def _risk_warning_clean_status(*, duckdb_path: Path, report_date: str) -> dict[str, object]:
    evidence = build_risk_warning_evidence(duckdb_path=duckdb_path, report_date=report_date)
    decision_status = evidence.get("decision_status")
    decision_blockers = evidence.get("decision_blockers", [])
    evidence_scope = evidence.get("evidence_scope", {})
    warning_resolution_matrix = evidence.get("warning_resolution_matrix", [])
    duration_delta_detail = evidence.get("duration_exclusion_delta_detail", {})
    rematerialization_preview = evidence.get("risk_tensor_rematerialization_preview", {})
    assert isinstance(decision_blockers, list)
    assert isinstance(evidence_scope, dict)
    assert isinstance(warning_resolution_matrix, list)
    assert isinstance(duration_delta_detail, dict)
    assert isinstance(rematerialization_preview, dict)
    duration_delta_summary = dict(duration_delta_detail)
    duration_delta_summary.pop("top_recomputed_rows_by_market_value", None)
    valid = decision_status == "clean"
    return {
        "status": "clean" if valid else "blocked",
        "valid": valid,
        "decision_status": decision_status,
        "decision_blockers": decision_blockers,
        "evidence_scope": dict(evidence_scope),
        "warning_resolution_matrix": warning_resolution_matrix,
        "duration_exclusion_delta_detail": duration_delta_summary,
        "risk_tensor_rematerialization_preview": dict(rematerialization_preview),
    }


def _score_blocker_action_coverage_ready(
    scorecard: dict[str, object],
    score_blocker_action_coverage: dict[str, object],
) -> bool:
    score_blockers = scorecard.get("score_blockers")
    return bool(
        isinstance(score_blockers, list)
        and score_blocker_action_coverage.get("status") == "clean"
        and score_blocker_action_coverage.get("blockers") == []
        and score_blocker_action_coverage.get("unassigned_blockers") == []
        and score_blocker_action_coverage.get("covered_blockers") == score_blockers
    )


def _activation_ready(
    *,
    scorecard: dict[str, object],
    approval: dict[str, object],
    dependencies: list[dict[str, object]],
    dependency_consistency_status: str,
    intake_check: dict[str, object],
    owner_intake_alignment: dict[str, object],
    rerun_evidence_status: dict[str, object],
    risk_warning_clean_status: dict[str, object],
    score_blocker_action_coverage: dict[str, object],
    closure_artifact_presence_summary: dict[str, object] | None = None,
) -> bool:
    evidence_scope = approval.get("evidence_scope", {})
    if not isinstance(evidence_scope, dict):
        return False
    closure_artifact_presence_summary = closure_artifact_presence_summary or {
        "current": True,
        "blockers": [],
    }
    return bool(
        scorecard.get("full_score_ready")
        and scorecard.get("score_status") == "ready_for_full_score"
        and approval.get("business_owner_approval_captured")
        and approval.get("formal_use_allowed")
        and approval.get("closure_approved")
        and evidence_scope.get("approves_metric_or_page")
        and evidence_scope.get("writes_governance_records")
        and evidence_scope.get("proves_capture_ready_page_execution")
        and evidence_scope.get("captures_business_owner_approval")
        and all(bool(item.get("available")) for item in dependencies)
        and dependency_consistency_status == "consistent"
        and intake_check.get("intake_ready")
        and owner_intake_alignment.get("status") == "consistent"
        and rerun_evidence_status.get("valid")
        and risk_warning_clean_status.get("valid")
        and _score_blocker_action_coverage_ready(scorecard, score_blocker_action_coverage)
        and closure_artifact_presence_summary.get("current") is True
        and closure_artifact_presence_summary.get("blockers") == []
    )


def _activation_guard(activation_ready: bool) -> dict[str, object]:
    return {
        "no_automatic_approval": True,
        "partial_activation_invalid": True,
        "partial_owner_evidence_activation_invalid": True,
        "strict_scorecard_required": True,
        "dependency_consistency_required": True,
        "owner_decision_intake_required": True,
        "owner_decision_intake_alignment_required": True,
        "score_blocker_action_coverage_required": True,
        "rerun_evidence_required": True,
        "risk_warning_clean_required": True,
        "closure_artifact_presence_required": True,
        "activation_ready": activation_ready,
        "required_commands": [
            STRICT_SCORECARD_COMMAND,
            STRICT_APPROVAL_COMMAND,
            EVIDENCE_SNAPSHOT_COMMAND,
            OWNER_ACTION_PACKET_STRICT_COMMAND,
            "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
            DEPENDENCY_CONSISTENCY_STRICT_COMMAND,
            OWNER_DECISION_INTAKE_STRICT_COMMAND,
            ARTIFACT_PRESENCE_COMMAND,
            EVIDENCE_PACKET_GUARD_COMMAND,
            EVIDENCE_SNAPSHOT_COMMAND + f" --output {RERUN_EVIDENCE_ARTIFACT}",
        ],
    }


def _business_owner_approval_boundary(
    *,
    approval: dict[str, object],
    scorecard: dict[str, object],
    intake_check: dict[str, object],
    rerun_evidence_status: dict[str, object],
    risk_warning_clean_status: dict[str, object],
    activation_ready: bool,
    dependencies: list[dict[str, object]] | None = None,
    dependency_consistency_status: str | None = None,
    owner_intake_alignment: dict[str, object] | None = None,
    score_blocker_action_coverage: dict[str, object] | None = None,
    closure_artifact_presence_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    template_approval_captured = bool(approval.get("business_owner_approval_captured"))
    blockers: list[str] = []
    if not template_approval_captured:
        blockers.append("business_owner_approval_not_captured")
    if not scorecard.get("full_score_ready"):
        blockers.append("scorecard_full_score_not_ready")
    if scorecard.get("score_status") != "ready_for_full_score":
        blockers.append("scorecard_score_status_not_ready")
    if not intake_check.get("intake_ready"):
        blockers.append("owner_decision_intake_not_ready")
    if not rerun_evidence_status.get("valid"):
        blockers.append("rerun_evidence_not_valid")
    if not risk_warning_clean_status.get("valid"):
        blockers.append("risk_warning_not_clean")
    if dependencies is not None and not all(bool(item.get("available")) for item in dependencies):
        blockers.append("evidence_dependency_unavailable")
    if dependency_consistency_status is not None and dependency_consistency_status != "consistent":
        blockers.append("dependency_consistency_not_ready")
    if owner_intake_alignment is not None and owner_intake_alignment.get("status") != "consistent":
        blockers.append("owner_decision_intake_alignment_not_ready")
    if score_blocker_action_coverage is not None:
        if not _score_blocker_action_coverage_ready(scorecard, score_blocker_action_coverage):
            blockers.append("score_blocker_action_coverage_not_ready")
    if closure_artifact_presence_summary is not None and (
        closure_artifact_presence_summary.get("current") is not True
        or closure_artifact_presence_summary.get("blockers") != []
    ):
        blockers.append("closure_artifact_presence_not_current")

    if activation_ready:
        status = "activated"
    elif template_approval_captured:
        status = "captured_but_not_activated"
    else:
        status = "pending_owner_input"

    return {
        "template_approval_captured": template_approval_captured,
        "formal_authorization_allowed": activation_ready,
        "governance_write_allowed": activation_ready,
        "page_execution_proven": activation_ready,
        "full_score_closure_ready": bool(scorecard.get("full_score_ready")) and activation_ready,
        "activation_ready": activation_ready,
        "status": status,
        "blockers": blockers,
    }


def _manifest_consistency_checks(
    *,
    scorecard: dict[str, object],
    report_date: str,
    docs_root: Path,
) -> list[dict[str, object]]:
    return manifest_consistency_checks(
        scorecard=scorecard,
        report_date=report_date,
        docs_root=docs_root,
        root=ROOT,
    )


def _consistency_blockers(checks: list[dict[str, object]]) -> list[str]:
    return manifest_consistency_blockers(checks)


def build_packet(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    limit: int,
    docs_root: Path = ROOT / "docs",
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="business owner approval packet limit",
    )
    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=limit,
        docs_root=Path(docs_root),
    )
    approval = build_approval_status(template_path, report_date=report_date)
    dependencies = _evidence_dependencies(report_date, Path(docs_root))
    manifest_checks = _manifest_consistency_checks(
        scorecard=scorecard,
        report_date=report_date,
        docs_root=Path(docs_root),
    )
    generated_owner_fields_summary = generated_owner_fields_boundaries(manifest_checks)
    consistency_blockers = _consistency_blockers(manifest_checks)
    dependency_consistency_status = "consistent" if not consistency_blockers else "blocked"
    intake_check = build_intake_check(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        limit=limit,
    )
    owner_intake_dependency_consistency_status = str(
        intake_check.get("dependency_consistency_status") or dependency_consistency_status
    )
    rerun_status = _rerun_evidence_status(docs_root=Path(docs_root), report_date=report_date)
    risk_warning_clean_status = _risk_warning_clean_status(
        duckdb_path=duckdb_path,
        report_date=report_date,
    )
    owner_intake_summary = _owner_decision_intake_summary(intake_check)
    scorecard_owner_gate_summary = _scorecard_owner_decision_intake_gate_summary(scorecard)
    owner_intake_alignment = owner_decision_intake_alignment(
        owner_intake_summary,
        scorecard_owner_gate_summary,
    )
    scorecard_gates = scorecard.get("gates", {})
    assert isinstance(scorecard_gates, dict)
    score_blocker_action_coverage = scorecard_gates.get("score_blocker_action_coverage", {})
    assert isinstance(score_blocker_action_coverage, dict)
    closure_matrix = scorecard_gates.get("blocker_closure_matrix", [])
    if not isinstance(closure_matrix, list):
        closure_matrix = []
    if not closure_matrix:
        closure_matrix = []
        for action in scorecard.get("score_blocker_actions", []):
            if not isinstance(action, dict):
                continue
            blocker = str(action.get("blocker") or "")
            if blocker:
                closure_matrix.append(
                    {
                        "blocker": blocker,
                        "decision_artifacts": [],
                    }
                )
    artifact_current = build_artifact_current_summary(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        intake_summary=owner_intake_summary,
    )
    artifact_presence = artifact_presence_report(
        docs_root=Path(docs_root),
        closure_matrix=closure_matrix,
        artifact_current_summary=artifact_current,
    )
    artifact_presence_summary = closure_artifact_presence_summary(artifact_presence)
    activation_ready = _activation_ready(
        scorecard=scorecard,
        approval=approval,
        dependencies=dependencies,
        dependency_consistency_status=owner_intake_dependency_consistency_status,
        intake_check=intake_check,
        owner_intake_alignment=owner_intake_alignment,
        rerun_evidence_status=rerun_status,
        risk_warning_clean_status=risk_warning_clean_status,
        score_blocker_action_coverage=score_blocker_action_coverage,
        closure_artifact_presence_summary=artifact_presence_summary,
    )
    approval_boundary = _business_owner_approval_boundary(
        approval=approval,
        scorecard=scorecard,
        intake_check=intake_check,
        rerun_evidence_status=rerun_status,
        risk_warning_clean_status=risk_warning_clean_status,
        activation_ready=activation_ready,
        dependencies=dependencies,
        dependency_consistency_status=owner_intake_dependency_consistency_status,
        owner_intake_alignment=owner_intake_alignment,
        score_blocker_action_coverage=score_blocker_action_coverage,
        closure_artifact_presence_summary=artifact_presence_summary,
    )
    return {
        "packet_kind": "portfolio_home_business_owner_approval_packet",
        "page_id": scorecard["page_id"],
        "page_slug": scorecard["page_slug"],
        "report_date": scorecard["report_date"],
        "duckdb_path": scorecard["duckdb_path"],
        "template_path": scorecard["template_path"],
        "packet_status": "ready_for_activation" if activation_ready else "pending",
        "activation_ready": activation_ready,
        "current_score": scorecard["current_score"],
        "remaining_gap": scorecard["remaining_gap"],
        "score_status": scorecard["score_status"],
        "full_score_ready": scorecard["full_score_ready"],
        "score_blockers": scorecard["score_blockers"],
        "approval_summary": _approval_summary(approval),
        "business_owner_approval_boundary": approval_boundary,
        "owner_decision_intake_summary": owner_intake_summary,
        "scorecard_owner_decision_intake_gate_summary": scorecard_owner_gate_summary,
        "owner_decision_intake_alignment": owner_intake_alignment,
        "score_blocker_action_coverage": score_blocker_action_coverage,
        "closure_artifact_presence_summary": artifact_presence_summary,
        "rerun_evidence_status": rerun_status,
        "risk_warning_clean_status": risk_warning_clean_status,
        "activation_guard": _activation_guard(activation_ready),
        "evidence_dependencies": dependencies,
        "dependency_consistency_status": dependency_consistency_status,
        "dependency_consistency_blockers": consistency_blockers,
        "generated_owner_fields_boundaries": generated_owner_fields_summary,
        "manifest_consistency_checks": manifest_checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a business-owner approval packet for portfolio-home full closure.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="business owner approval packet limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the business-owner approval packet is ready for full activation.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Return non-zero unless the output JSON matches the freshly built packet.",
    )
    args = parser.parse_args(argv)

    packet = build_packet(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        limit=int(args.limit),
        docs_root=Path(args.docs_root),
    )
    output = Path(args.output) if args.output is not None else None
    if args.check_current:
        if output is None:
            output = DEFAULT_OUTPUT
        status = _current_status(output, packet)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["current"] else 1
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    if args.require_ready and not packet["activation_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
