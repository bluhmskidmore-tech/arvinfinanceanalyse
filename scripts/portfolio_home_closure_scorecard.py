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
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
    build_evidence as build_full_closure_evidence,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_krd_remap_review_queue import (  # noqa: E402
    build_queue as build_krd_queue,
)
from scripts.portfolio_home_maturity_remediation_queue import (  # noqa: E402
    build_queue as build_maturity_queue,
)
from scripts.portfolio_home_manifest_consistency import (  # noqa: E402
    consistency_blockers as manifest_consistency_blockers,
    generated_owner_fields_boundaries,
    manifest_consistency_checks,
)
from scripts.portfolio_home_risk_warning_consistency import (  # noqa: E402
    build_evidence as build_warning_consistency,
)


CURRENT_SCORE = "99.86 / 100"
CURRENT_REMAINING_GAP = "0.14"
FULL_SCORE = "100.00 / 100"
NO_REMAINING_GAP = "0.00"
PORTFOLIO_HOME_PAGE_ID = "PAGE-PORTFOLIO-HOME-001"
PORTFOLIO_HOME_PAGE_SLUG = "portfolio"
PORTFOLIO_HOME_SNAPSHOT_KIND = "portfolio_home_closure_evidence"
PORTFOLIO_HOME_OWNER_INPUT_SUMMARY_ARTIFACT = "portfolio-home-owner-input-needed-summary.json"
PORTFOLIO_HOME_OWNER_HANDOFF_ARTIFACT = "portfolio-home-owner-handoff-packet.md"


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
OWNER_HANDOFF_REQUIRED_ROUTES = ["risk_owner", "data_owner", "business_owner"]
OWNER_HANDOFF_EVIDENCE_SCOPE_FALSE_FIELDS = [
    "approves_metric_or_page",
    "writes_governance_records",
    "fills_owner_decisions",
    "captures_business_owner_approval",
    "proves_full_score_closure",
]
OWNER_HANDOFF_CERTIFICATION_EFFECT = "none"
REQUIRED_VERIFICATION_COMMANDS = [
    "full_closure_strict",
    "risk_warning_clean",
    "krd_review_strict",
    "maturity_remediation_strict",
    "matured_outstanding_strict",
    "business_owner_approval_strict",
    "owner_decision_intake_check_strict",
    "owner_action_packet_current",
    "owner_action_packet_strict",
    "business_owner_approval_packet_current",
    "business_owner_approval_packet_strict",
    "dependency_consistency_check_strict",
    "owner_input_needed_summary_current",
    "evidence_snapshot_current",
    "evidence_snapshot_alignment_check",
    "owner_handoff_packet_current",
    "owner_handoff_completeness_check",
    "krd_contract_decision_export_current",
    "maturity_remediation_export_current",
    "closure_artifact_presence_check",
    "evidence_packet_guard",
    "blocker_closure_matrix_check",
    "score_blocker_consistency_check",
    "verification_command_runner",
]
BLOCKED_STATE_NONZERO_VERIFICATION_COMMANDS = [
    "full_closure_strict",
    "risk_warning_clean",
    "krd_review_strict",
    "maturity_remediation_strict",
    "matured_outstanding_strict",
    "business_owner_approval_strict",
    "owner_decision_intake_check_strict",
    "owner_action_packet_strict",
    "business_owner_approval_packet_strict",
]

VERIFICATION_COMMANDS: list[dict[str, str]] = [
    {
        "name": "full_closure_evidence",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_full_closure_evidence.py",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "full_closure_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_full_closure_evidence.py --require-clean",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "risk_warning_consistency",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_risk_warning_consistency.py --require-consistent",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "risk_warning_clean",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "krd_review_queue",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_krd_remap_review_queue.py",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "krd_review_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "krd_contract_decision_export",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "krd_contract_decision_export_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --require-clean",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "krd_contract_decision_export_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "maturity_remediation_queue",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_maturity_remediation_queue.py",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "maturity_remediation_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "matured_outstanding_queue",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_matured_outstanding_queue.py",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "matured_outstanding_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_matured_outstanding_queue.py --require-empty",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "maturity_remediation_export",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "maturity_remediation_export_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --require-clean",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "maturity_remediation_export_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "closure_artifact_presence_check",
        "kind": "regression",
        "command": "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "evidence_packet_guard",
        "kind": "regression",
        "command": "python scripts/portfolio_home_evidence_packet_guard.py --require-clean",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "scorecard",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_closure_scorecard.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "scorecard_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "business_owner_approval",
        "kind": "evidence",
        "command": "python scripts/check_portfolio_home_business_owner_approval.py",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "business_owner_approval_strict",
        "kind": "strict_gate",
        "command": "python scripts/check_portfolio_home_business_owner_approval.py --require-captured",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_action_packet",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_owner_action_packet.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_action_packet_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_owner_action_packet.py --limit 3 --output docs/portfolio/portfolio-home-owner-action-packet.json --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_handoff_packet",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_owner_handoff_packet.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_handoff_packet_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_owner_handoff_packet.py --limit 3 --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_handoff_completeness_check",
        "kind": "regression",
        "command": "python scripts/portfolio_home_owner_handoff_completeness_check.py --limit 3 --require-clean",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "evidence_snapshot_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --output docs/portfolio/portfolio-home-evidence-snapshot.json --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "evidence_snapshot_alignment_check",
        "kind": "regression",
        "command": "python scripts/portfolio_home_evidence_snapshot_alignment_check.py --require-clean",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_input_needed_summary",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_owner_input_needed_summary.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_input_needed_summary_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_owner_input_needed_summary.py --limit 3 --output docs/portfolio/portfolio-home-owner-input-needed-summary.json --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_action_packet_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "business_owner_approval_packet",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "business_owner_approval_packet_current",
        "kind": "regression",
        "command": "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --output docs/portfolio/portfolio-home-business-owner-approval-packet.json --check-current",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "business_owner_approval_packet_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "dependency_consistency_check",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_dependency_consistency_check.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "dependency_consistency_check_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_decision_intake_check",
        "kind": "evidence",
        "command": "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "owner_decision_intake_check_strict",
        "kind": "strict_gate",
        "command": "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready",
        "expected_when_blocked": "exit_nonzero",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "supporting_sample_guard",
        "kind": "regression",
        "command": "python -m pytest tests/test_golden_samples_capture_ready.py::test_supporting_only_golden_sample_files_exist_without_capture_ready_claim -q",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "blocker_closure_matrix_check",
        "kind": "regression",
        "command": "python scripts/portfolio_home_blocker_closure_matrix_check.py --require-clean",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "score_blocker_consistency_check",
        "kind": "regression",
        "command": "python scripts/portfolio_home_score_blocker_consistency_check.py --require-consistent",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
    {
        "name": "verification_command_runner",
        "kind": "regression",
        "command": "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched",
        "expected_when_blocked": "exit_0",
        "expected_when_full_score": "exit_0",
    },
]

_DATE_INDEPENDENT_VERIFICATION_COMMANDS = {
    "supporting_sample_guard",
    "verification_command_runner",
}


def _render_verification_commands(report_date: str) -> list[dict[str, str]]:
    rendered: list[dict[str, str]] = []
    for command_spec in VERIFICATION_COMMANDS:
        command_for_report = dict(command_spec)
        if command_spec["name"] not in _DATE_INDEPENDENT_VERIFICATION_COMMANDS:
            command_head, separator, command_tail = command_spec["command"].partition(".py")
            command_for_report["command"] = (
                f"{command_head}{separator} --report-date {report_date}{command_tail}"
            )
        rendered.append(command_for_report)
    return rendered


BLOCKER_ACTIONS: dict[str, dict[str, str]] = {
    "risk_tensor_quality_warning": {
        "owner": "risk_owner",
        "next_action": "Review the warning-consistency evidence, then rematerialize a clean risk tensor or keep the page candidate-only.",
        "evidence_command": "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        "exit_criteria": "Risk warning clean gate exits 0 and full-closure evidence no longer reports risk_tensor_quality_warning.",
    },
    "duration_exclusion_warning_mismatch": {
        "owner": "data_owner",
        "next_action": "Reconcile the recomputed duration-exclusion warning evidence with the risk tensor warning text before any full-score claim.",
        "evidence_command": "python scripts/portfolio_home_risk_warning_consistency.py --require-consistent",
        "exit_criteria": "Risk warning consistency reports matching parsed and recomputed duration-exclusion evidence.",
    },
    "krd_bucket_warning_mismatch": {
        "owner": "risk_owner",
        "next_action": "Review the KRD bucket warning evidence, then rematerialize the risk tensor if the parsed warning is stale or keep /portfolio candidate-only until the warning matches current formal bonds.",
        "evidence_command": "python scripts/portfolio_home_risk_warning_consistency.py --require-consistent",
        "exit_criteria": "Risk warning consistency confirms the KRD bucket warning matches current formal bonds, and rematerialization is completed or /portfolio remains candidate-only when the warning cannot yet be cleared.",
    },
    "risk_tensor_warning_mismatch": {
        "owner": "risk_owner",
        "next_action": "Reconcile risk tensor warning evidence and rematerialize the risk tensor or keep /portfolio candidate-only.",
        "evidence_command": "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
        "exit_criteria": "Risk warning clean gate exits 0 with no risk tensor warning mismatch.",
    },
    "krd_contract_decision_required": {
        "owner": "risk_owner",
        "next_action": "Approve nearest-bucket mappings for 2Y, 6M, and 20Y, or require an exact-bucket KRD schema/API update.",
        "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
        "exit_criteria": "KRD review queue exits 0 under the approved contract and the metric contract records the decision.",
    },
    "tyw_liability_maturity_date_remediation_required": {
        "owner": "data_owner",
        "next_action": "Remediate missing TYW liability maturity_date values or capture a signed scoped exclusion before rematerialization.",
        "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "exit_criteria": "TYW liability maturity remediation queue is empty or signed exclusion evidence is captured and surfaced as a boundary.",
    },
    "bond_matured_outstanding_reconciliation_required": {
        "owner": "data_owner",
        "next_action": "Reconcile matured or unparseable non-zero bond positions at source; this read-only gate does not accept an exception as closure evidence.",
        "evidence_command": "python scripts/portfolio_home_matured_outstanding_queue.py --require-empty",
        "exit_criteria": "Matured outstanding strict queue exits 0 with no matured or unparseable non-zero bond positions.",
    },
    "business_owner_approval": {
        "owner": "business_owner",
        "next_action": "Complete and sign the portfolio-home business owner approval template with risk-owner countersignature.",
        "evidence_command": "python scripts/check_portfolio_home_business_owner_approval.py --require-captured",
        "exit_criteria": "Approval checker exits 0 and evidence_scope.approves_metric_or_page is true.",
    },
    "formal_page_approval_missing": {
        "owner": "business_owner",
        "next_action": "Update the captured approval so it explicitly approves the page or keep /portfolio candidate-only.",
        "evidence_command": "python scripts/check_portfolio_home_business_owner_approval.py --require-captured",
        "exit_criteria": "Captured approval explicitly approves the metric/page and preserves governance evidence scope.",
    },
    "approval_dependency_consistency_blocked": {
        "owner": "business_owner",
        "next_action": "Regenerate or reconcile the KRD and maturity export manifests so they match the current scorecard evidence.",
        "evidence_command": "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready",
        "exit_criteria": "Business-owner approval packet reports dependency_consistency_status=consistent before any full-score claim.",
    },
    "owner_decision_intake_blocked": {
        "owner": "business_owner",
        "next_action": "Reconcile risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval before full-score activation.",
        "evidence_command": "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready",
        "exit_criteria": "Owner decision intake strict gate exits 0 and reports intake_ready=true.",
    },
    "owner_decision_intake_alignment_blocked": {
        "owner": "business_owner",
        "next_action": "Reconcile the direct owner-intake evidence and scorecard gate summary before full-score activation.",
        "evidence_command": "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score",
        "exit_criteria": "Scorecard owner_decision_intake_alignment gate reports status=consistent with no blockers.",
    },
    "verification_command_coverage_blocked": {
        "owner": "business_owner",
        "next_action": "Restore the portfolio-home verification command allowlist before any full-score claim.",
        "evidence_command": "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched",
        "exit_criteria": "Verification command coverage gate reports status=clean with no missing required commands.",
    },
    "owner_handoff_completeness_blocked": {
        "owner": "business_owner",
        "next_action": "Regenerate the owner input summary and handoff packet before any full-score claim.",
        "evidence_command": "python scripts/portfolio_home_owner_handoff_completeness_check.py --limit 3 --require-clean",
        "exit_criteria": "Owner handoff completeness gate reports status=clean and handoff_ready=true.",
    },
}


def _append_unique(target: list[str], values: list[object]) -> None:
    for value in values:
        item = str(value)
        if item not in target:
            target.append(item)


def _owner_decision_intake_alignment(
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


def _csv_check_summary(checks: list[dict[str, object]]) -> dict[str, object]:
    by_name = {str(item.get("name")): item for item in checks if isinstance(item, dict)}
    krd = by_name.get("krd_contract_decision_manifest", {})
    maturity = by_name.get("maturity_remediation_manifest", {})
    krd_csv = krd.get("csv_checks", {}) if isinstance(krd, dict) else {}
    maturity_csv = maturity.get("csv_checks", {}) if isinstance(maturity, dict) else {}
    assert isinstance(krd_csv, dict)
    assert isinstance(maturity_csv, dict)
    return {
        "krd_summary_row_count": krd_csv.get("summary_row_count"),
        "krd_detail_row_count": krd_csv.get("detail_row_count"),
        "krd_owner_decision_fields_blank": krd_csv.get("owner_decision_fields_blank"),
        "bond_missing_maturity_row_count": maturity_csv.get("bond_missing_maturity_row_count"),
        "tyw_liability_missing_maturity_row_count": maturity_csv.get(
            "tyw_liability_missing_maturity_row_count",
        ),
        "maturity_owner_fields_blank": maturity_csv.get("owner_fields_blank"),
    }


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _artifact_name(value: object) -> str:
    return Path(str(value)).name if value else ""


def _stable_json_sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_artifact_sha256(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, "file_missing"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "file_invalid_json"
    if not isinstance(parsed, dict):
        return None, "file_invalid_json"
    return _stable_json_sha256(parsed), None


def _markdown_artifact_sha256(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, "file_missing"
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest(), None


def _owner_handoff_completeness_gate(
    docs_root: Path,
    *,
    report_date: str | None = None,
) -> dict[str, object]:
    artifact = Path(docs_root) / "portfolio" / "portfolio-home-evidence-snapshot.json"
    blockers: list[str] = []
    snapshot: dict[str, object] = {}
    if not artifact.exists():
        blockers.append("owner_handoff_completeness_snapshot_missing")
    else:
        try:
            parsed = json.loads(artifact.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
            blockers.append("owner_handoff_completeness_snapshot_invalid_json")
        snapshot = parsed if isinstance(parsed, dict) else {}
        if not snapshot and "owner_handoff_completeness_snapshot_invalid_json" not in blockers:
            blockers.append("owner_handoff_completeness_snapshot_invalid")

    summary = _dict(snapshot.get("handoff_completeness_summary"))
    if not summary:
        blockers.append("owner_handoff_completeness_summary_missing")

    if snapshot:
        if snapshot.get("snapshot_kind") != PORTFOLIO_HOME_SNAPSHOT_KIND:
            blockers.append("owner_handoff_snapshot_kind_mismatch")
        if snapshot.get("page_id") != PORTFOLIO_HOME_PAGE_ID:
            blockers.append("owner_handoff_snapshot_page_id_mismatch")
        if snapshot.get("page_slug") != PORTFOLIO_HOME_PAGE_SLUG:
            blockers.append("owner_handoff_snapshot_page_slug_mismatch")
        if report_date is not None and snapshot.get("report_date") != report_date:
            blockers.append("owner_handoff_snapshot_report_date_mismatch")

    summary_current_status = _dict(summary.get("summary_current_status"))
    handoff_current_status = _dict(summary.get("handoff_current_status"))
    owner_route_coverage = _dict(summary.get("owner_route_coverage"))
    route_statuses = _dict(summary.get("route_statuses"))
    evidence_scope = _dict(summary.get("evidence_scope"))

    if summary and summary.get("status") != "clean":
        blockers.append("owner_handoff_completeness_status_not_clean")
    if summary and summary.get("handoff_ready") is not True:
        blockers.append("owner_handoff_not_ready")
    if summary:
        if not summary_current_status:
            blockers.append("owner_input_needed_summary_status_missing")
        elif (
            summary_current_status.get("status") != "current"
            or summary_current_status.get("current", True) is not True
        ):
            blockers.append("owner_input_needed_summary_not_current")
        elif not _artifact_name(summary_current_status.get("artifact")):
            blockers.append("owner_input_needed_summary_current_artifact_missing")
        elif (
            _artifact_name(summary_current_status.get("artifact"))
            != PORTFOLIO_HOME_OWNER_INPUT_SUMMARY_ARTIFACT
        ):
            blockers.append("owner_input_needed_summary_current_artifact_mismatch")
        elif not summary_current_status.get("expected_sha256") or not summary_current_status.get(
            "actual_sha256",
        ):
            blockers.append("owner_input_needed_summary_current_fingerprint_missing")
        elif summary_current_status.get("expected_sha256") != summary_current_status.get(
            "actual_sha256",
        ):
            blockers.append("owner_input_needed_summary_current_fingerprint_mismatch")
        else:
            summary_file_sha, summary_file_blocker = _json_artifact_sha256(
                Path(docs_root) / "portfolio" / PORTFOLIO_HOME_OWNER_INPUT_SUMMARY_ARTIFACT,
            )
            if summary_file_blocker:
                blockers.append(f"owner_input_needed_summary_current_{summary_file_blocker}")
            elif summary_file_sha != summary_current_status.get("actual_sha256"):
                blockers.append("owner_input_needed_summary_current_file_fingerprint_mismatch")

        if not handoff_current_status:
            blockers.append("owner_handoff_packet_status_missing")
        elif handoff_current_status.get("status") != "current":
            blockers.append("owner_handoff_packet_not_current")
        elif not _artifact_name(handoff_current_status.get("artifact")):
            blockers.append("owner_handoff_packet_current_artifact_missing")
        elif (
            _artifact_name(handoff_current_status.get("artifact"))
            != PORTFOLIO_HOME_OWNER_HANDOFF_ARTIFACT
        ):
            blockers.append("owner_handoff_packet_current_artifact_mismatch")
        elif not handoff_current_status.get("expected_sha256") or not handoff_current_status.get(
            "actual_sha256",
        ):
            blockers.append("owner_handoff_packet_current_fingerprint_missing")
        elif handoff_current_status.get("expected_sha256") != handoff_current_status.get(
            "actual_sha256",
        ):
            blockers.append("owner_handoff_packet_current_fingerprint_mismatch")
        else:
            handoff_file_sha, handoff_file_blocker = _markdown_artifact_sha256(
                Path(docs_root) / "portfolio" / PORTFOLIO_HOME_OWNER_HANDOFF_ARTIFACT,
            )
            if handoff_file_blocker:
                blockers.append(f"owner_handoff_packet_current_{handoff_file_blocker}")
            elif handoff_file_sha != handoff_current_status.get("actual_sha256"):
                blockers.append("owner_handoff_packet_current_file_fingerprint_mismatch")

        if not owner_route_coverage:
            blockers.append("owner_handoff_route_coverage_missing")
        elif owner_route_coverage.get("status") != "clean":
            blockers.append("owner_handoff_route_coverage_not_clean")

        if not route_statuses:
            blockers.append("owner_handoff_route_statuses_missing")
        else:
            for owner in OWNER_HANDOFF_REQUIRED_ROUTES:
                if owner not in route_statuses:
                    blockers.append(f"owner_handoff_route_status_missing:{owner}")
                elif route_statuses.get(owner) != "clean":
                    blockers.append(f"owner_handoff_route_status_not_clean:{owner}")
            for owner in route_statuses:
                if owner not in OWNER_HANDOFF_REQUIRED_ROUTES:
                    blockers.append(f"owner_handoff_route_status_unexpected:{owner}")

        if not evidence_scope:
            blockers.append("owner_handoff_evidence_scope_missing")
        elif any(
            evidence_scope.get(field) is True
            for field in OWNER_HANDOFF_EVIDENCE_SCOPE_FALSE_FIELDS
        ):
            blockers.append("owner_handoff_evidence_scope_overclaims")
        if evidence_scope:
            certification_effect = evidence_scope.get("certification_effect")
            if certification_effect is None:
                blockers.append("owner_handoff_evidence_scope_certification_effect_missing")
            elif certification_effect != OWNER_HANDOFF_CERTIFICATION_EFFECT:
                blockers.append("owner_handoff_evidence_scope_certification_effect_overclaims")

    _append_unique(blockers, _list(summary.get("blockers")))
    return {
        "status": "clean" if not blockers else "blocked",
        "handoff_ready": bool(summary.get("handoff_ready")) and not blockers,
        "blockers": blockers,
        "artifact": str(artifact),
        "summary_current_status": summary_current_status,
        "handoff_current_status": handoff_current_status,
        "owner_route_coverage": owner_route_coverage,
        "route_statuses": route_statuses,
        "evidence_scope": evidence_scope,
    }


def _score_blockers(
    *,
    full_closure: dict[str, object],
    warning_consistency: dict[str, object],
    krd_queue: dict[str, object],
    maturity_queue: dict[str, object],
    approval_status: dict[str, object],
    dependency_consistency_blockers: list[str],
    owner_intake: dict[str, object],
    owner_intake_alignment: dict[str, object] | None = None,
    verification_command_coverage: dict[str, object] | None = None,
    owner_handoff_completeness: dict[str, object] | None = None,
) -> list[str]:
    blockers: list[str] = []
    _append_unique(blockers, list(full_closure.get("closure_blockers", [])))

    if warning_consistency.get("warning_consistency_status") != "consistent":
        _append_unique(blockers, list(warning_consistency.get("consistency_blockers", [])))
    if warning_consistency.get("decision_status") != "clean":
        _append_unique(blockers, list(warning_consistency.get("decision_blockers", [])))
    if krd_queue.get("review_status") != "clean":
        _append_unique(blockers, list(krd_queue.get("review_blockers", [])))
    if maturity_queue.get("remediation_status") != "clean":
        # The full-closure evidence already carries the business-facing maturity blockers.
        pass

    if not approval_status.get("business_owner_approval_captured"):
        _append_unique(blockers, ["business_owner_approval"])
    else:
        evidence_scope = approval_status.get("evidence_scope")
        if isinstance(evidence_scope, dict) and not evidence_scope.get("approves_metric_or_page"):
            _append_unique(blockers, ["formal_page_approval_missing"])
    if dependency_consistency_blockers:
        _append_unique(blockers, ["approval_dependency_consistency_blocked"])
    if owner_intake_alignment is not None and owner_intake_alignment.get("status") != "consistent":
        _append_unique(blockers, ["owner_decision_intake_alignment_blocked"])
    if (
        verification_command_coverage is not None
        and verification_command_coverage.get("status") != "clean"
    ):
        _append_unique(blockers, ["verification_command_coverage_blocked"])
    if (
        owner_handoff_completeness is not None
        and owner_intake.get("intake_ready")
        and owner_handoff_completeness.get("status") != "clean"
    ):
        _append_unique(blockers, ["owner_handoff_completeness_blocked"])
    if not owner_intake.get("intake_ready"):
        _append_unique(blockers, ["owner_decision_intake_blocked"])
    return blockers


def _score_blocker_actions(
    blockers: list[str],
    report_date: str = DEFAULT_REPORT_DATE,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for blocker in blockers:
        action = BLOCKER_ACTIONS.get(
            blocker,
            {
                "owner": "unassigned",
                "next_action": "Assign an owner and define evidence before any full-score claim.",
                "evidence_command": "python scripts/portfolio_home_closure_scorecard.py --require-full-score",
                "exit_criteria": "Blocker is removed from score_blockers with auditable evidence.",
            },
        )
        action_for_report = dict(action)
        evidence_command = action_for_report.get("evidence_command", "")
        if (
            "--report-date" not in evidence_command
            and evidence_command.startswith(
                (
                    "python scripts/portfolio_home_",
                    "python scripts/check_portfolio_home_business_owner_approval.py",
                )
            )
        ):
            command_head, separator, command_tail = evidence_command.partition(".py")
            action_for_report["evidence_command"] = (
                f"{command_head}{separator} --report-date {report_date}{command_tail}"
            )
        actions.append({"blocker": blocker, **action_for_report})
    return actions


def _score_blocker_action_coverage(
    blockers: list[str],
    actions: list[dict[str, str]],
) -> dict[str, object]:
    action_by_blocker = {action.get("blocker"): action for action in actions}
    unassigned = [
        blocker
        for blocker in blockers
        if action_by_blocker.get(blocker, {}).get("owner") == "unassigned"
    ]
    covered = [blocker for blocker in blockers if blocker not in unassigned]
    return {
        "status": "clean" if not unassigned else "blocked",
        "blockers": [
            f"score_blocker_action_missing:{blocker}"
            for blocker in unassigned
        ],
        "unassigned_blockers": unassigned,
        "covered_blockers": covered,
    }


def _verification_command_coverage(
    verification_commands: list[dict[str, object]],
) -> dict[str, object]:
    present = [
        str(command.get("name"))
        for command in verification_commands
        if isinstance(command, dict) and command.get("name")
    ]
    missing = [
        command
        for command in REQUIRED_VERIFICATION_COMMANDS
        if command not in set(present)
    ]
    duplicate_commands = [
        command
        for command in REQUIRED_VERIFICATION_COMMANDS
        if present.count(command) > 1
    ]
    by_name = {
        str(command.get("name")): command
        for command in verification_commands
        if isinstance(command, dict) and command.get("name")
    }
    expected_by_name = {
        item["name"]: item
        for item in VERIFICATION_COMMANDS
        if item["name"] in REQUIRED_VERIFICATION_COMMANDS
    }
    mismatched: list[dict[str, object]] = []
    for name in REQUIRED_VERIFICATION_COMMANDS:
        actual = by_name.get(name)
        expected = expected_by_name.get(name)
        if not actual or not expected:
            continue
        for field in (
            "kind",
            "command",
            "expected_when_blocked",
            "expected_when_full_score",
        ):
            if actual.get(field) != expected.get(field):
                mismatched.append(
                    {
                        "name": name,
                        "field": field,
                        "expected": expected.get(field),
                        "actual": actual.get(field),
                    }
                )
        if name in BLOCKED_STATE_NONZERO_VERIFICATION_COMMANDS:
            strict_expectations = {
                "expected_when_blocked": "exit_nonzero",
                "expected_when_full_score": "exit_0",
            }
            for field, expected_value in strict_expectations.items():
                if actual.get(field) != expected_value:
                    mismatched.append(
                        {
                            "name": name,
                            "field": f"blocked_state_gate_{field}",
                            "expected": expected_value,
                            "actual": actual.get(field),
                        }
                    )
    return {
        "status": "clean" if not missing and not mismatched and not duplicate_commands else "blocked",
        "required_commands": REQUIRED_VERIFICATION_COMMANDS,
        "present_commands": present,
        "missing_commands": missing,
        "mismatched_commands": mismatched,
        "duplicate_commands": duplicate_commands,
    }


def build_scorecard(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    limit: int = 25,
    docs_root: Path = ROOT / "docs",
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(limit)
    full_closure = build_full_closure_evidence(
        duckdb_path=duckdb_path,
        report_date=report_date,
    )
    warning_consistency = build_warning_consistency(
        duckdb_path=duckdb_path,
        report_date=report_date,
    )
    krd_queue = build_krd_queue(
        duckdb_path=duckdb_path,
        report_date=report_date,
        limit=limit,
    )
    maturity_queue = build_maturity_queue(
        duckdb_path=duckdb_path,
        report_date=report_date,
        limit=limit,
    )
    approval_status = build_approval_status(template_path)
    scorecard_for_manifest = {
        "gates": {
            "krd_contract": {
                "status": krd_queue.get("review_status"),
                "krd_remap_summary": krd_queue.get("krd_remap_summary", []),
            },
            "maturity_remediation": {
                "status": maturity_queue.get("remediation_status"),
                "bond_no_maturity_summary": maturity_queue.get(
                    "bond_no_maturity_summary",
                    {},
                ),
                "bond_missing_maturity_summary": maturity_queue.get(
                    "bond_missing_maturity_summary",
                    {},
                ),
                "tyw_liability_missing_maturity_summary": maturity_queue.get(
                    "tyw_liability_missing_maturity_summary",
                    {},
                ),
            },
        }
    }
    dependency_checks = manifest_consistency_checks(
        scorecard=scorecard_for_manifest,
        report_date=report_date,
        docs_root=Path(docs_root),
        root=ROOT,
    )
    dependency_consistency_blockers = manifest_consistency_blockers(dependency_checks)
    dependency_status = "consistent" if not dependency_consistency_blockers else "blocked"
    dependency_report = {
        "dependency_consistency_status": dependency_status,
        "dependency_consistency_blockers": dependency_consistency_blockers,
        "csv_check_summary": _csv_check_summary(dependency_checks),
        "generated_owner_fields_boundaries": generated_owner_fields_boundaries(
            dependency_checks,
        ),
    }
    from scripts.portfolio_home_owner_decision_intake_check import (
        build_intake_check as build_owner_intake_check,
    )

    owner_intake = build_owner_intake_check(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=Path(docs_root),
        limit=limit,
        dependency=dependency_report,
    )
    owner_decision_summary = owner_intake.get("owner_decision_summary", {})
    assert isinstance(owner_decision_summary, dict)
    krd_owner_summary = owner_decision_summary.get("krd", {})
    maturity_owner_summary = owner_decision_summary.get("maturity", {})
    decision_alignment = owner_decision_summary.get("decision_alignment", {})
    assert isinstance(krd_owner_summary, dict)
    assert isinstance(maturity_owner_summary, dict)
    assert isinstance(decision_alignment, dict)
    owner_intake_summary = {
        "intake_status": owner_intake.get("intake_status"),
        "intake_ready": owner_intake.get("intake_ready"),
        "dependency_consistency_status": owner_intake.get(
            "dependency_consistency_status",
        ),
        "dependency_csv_summary_alignment": owner_intake.get(
            "dependency_csv_summary_alignment",
            {},
        ),
        "owner_input_boundary": owner_intake.get("owner_input_boundary", {}),
        "export_current_summary": owner_intake.get("export_current_summary", {}),
        "owner_decision_statuses": owner_intake.get("owner_decision_statuses"),
        "decision_counts": {
            "krd": krd_owner_summary.get("decision_counts", {}),
            "maturity": maturity_owner_summary.get("decision_counts", {}),
        },
        "decision_gap_counts": {
            "krd": krd_owner_summary.get("decision_gap_counts", {}),
            "maturity": maturity_owner_summary.get("decision_gap_counts", {}),
        },
        "note_gap_counts": {
            "krd": krd_owner_summary.get("note_gap_counts", {}),
            "maturity": maturity_owner_summary.get("comment_gap_counts", {}),
        },
        "exact_bucket_schema_evidence": krd_owner_summary.get(
            "exact_bucket_schema_evidence",
            {},
        ),
        "nearest_bucket_approval_evidence": krd_owner_summary.get(
            "nearest_bucket_approval_evidence",
            {},
        ),
        "maturity_scoped_exclusion_evidence": maturity_owner_summary.get(
            "scoped_exclusion_evidence",
            {},
        ),
    }
    owner_intake_gate = {
        "status": "ready" if owner_intake.get("intake_ready") else "pending",
        "intake_status": owner_intake_summary["intake_status"],
        "intake_ready": owner_intake_summary["intake_ready"],
        "dependency_consistency_status": owner_intake_summary[
            "dependency_consistency_status"
        ],
        "dependency_csv_summary_alignment": owner_intake_summary[
            "dependency_csv_summary_alignment"
        ],
        "owner_input_boundary": owner_intake_summary["owner_input_boundary"],
        "export_current_summary": owner_intake_summary["export_current_summary"],
        "owner_decision_statuses": owner_intake_summary["owner_decision_statuses"],
        "blockers": owner_intake.get("owner_decision_blockers", []),
        "decision_alignment": decision_alignment,
        "decision_counts": owner_intake_summary["decision_counts"],
        "decision_gap_counts": owner_intake_summary["decision_gap_counts"],
        "note_gap_counts": owner_intake_summary["note_gap_counts"],
        "exact_bucket_schema_evidence": owner_intake_summary[
            "exact_bucket_schema_evidence"
        ],
        "nearest_bucket_approval_evidence": owner_intake_summary[
            "nearest_bucket_approval_evidence"
        ],
        "maturity_scoped_exclusion_evidence": owner_intake_summary[
            "maturity_scoped_exclusion_evidence"
        ],
    }
    owner_intake_alignment = _owner_decision_intake_alignment(
        owner_intake_summary,
        owner_intake_gate,
    )
    verification_command_coverage = _verification_command_coverage(VERIFICATION_COMMANDS)
    rendered_verification_commands = _render_verification_commands(report_date)
    owner_handoff_completeness = _owner_handoff_completeness_gate(
        Path(docs_root),
        report_date=report_date,
    )

    blockers = _score_blockers(
        full_closure=full_closure,
        warning_consistency=warning_consistency,
        krd_queue=krd_queue,
        maturity_queue=maturity_queue,
        approval_status=approval_status,
        dependency_consistency_blockers=dependency_consistency_blockers,
        owner_intake=owner_intake,
        owner_intake_alignment=owner_intake_alignment,
        verification_command_coverage=verification_command_coverage,
        owner_handoff_completeness=owner_handoff_completeness,
    )
    score_blocker_actions = _score_blocker_actions(blockers, report_date)
    score_blocker_action_coverage = _score_blocker_action_coverage(
        blockers,
        score_blocker_actions,
    )
    full_score_ready = not blockers
    return {
            "page_id": PORTFOLIO_HOME_PAGE_ID,
            "page_slug": PORTFOLIO_HOME_PAGE_SLUG,
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "template_path": str(template_path),
        "current_score": FULL_SCORE if full_score_ready else CURRENT_SCORE,
        "remaining_gap": NO_REMAINING_GAP if full_score_ready else CURRENT_REMAINING_GAP,
        "score_methodology": {
            "scoring_model": "discrete_full_closure_gate",
            "gap_basis": "remaining_gap is a full-score readiness gap, not a linear sum of blocker weights",
            "gap_allocation_allowed": False,
            "full_score_rule": "current_score is 100.00 / 100 only when every score_blocker is closed with auditable evidence",
            "blocked_score_rule": "current_score remains 99.86 / 100 while any full-closure blocker remains",
        },
        "score_status": "ready_for_full_score" if full_score_ready else "blocked",
        "full_score_ready": full_score_ready,
        "score_blockers": blockers,
        "score_blocker_actions": score_blocker_actions,
        "verification_commands": rendered_verification_commands,
        "gates": {
            "score_blocker_action_coverage": score_blocker_action_coverage,
            "verification_command_coverage": verification_command_coverage,
            "full_closure_evidence": {
                "status": full_closure.get("data_quality_status"),
                "blockers": full_closure.get("closure_blockers", []),
                "risk_tensor": full_closure.get("risk_tensor", {}),
                "bond_maturity_gap": full_closure.get("bond_maturity_gap", {}),
                "bond_matured_outstanding": full_closure.get(
                    "bond_matured_outstanding",
                    {},
                ),
                "tyw_liability_maturity_gap_risk_scope": full_closure.get(
                    "tyw_liability_maturity_gap_risk_scope",
                    {},
                ),
                "krd_remap_scope": full_closure.get("krd_remap_scope", []),
            },
            "risk_warning_consistency": {
                "status": warning_consistency.get("warning_consistency_status"),
                "decision_status": warning_consistency.get("decision_status"),
                "blockers": warning_consistency.get("consistency_blockers", []),
                "decision_blockers": warning_consistency.get("decision_blockers", []),
                "risk_tensor_lineage": warning_consistency.get("risk_tensor_lineage", {}),
                "parsed_warnings": warning_consistency.get("parsed_warnings", {}),
                "recomputed_warnings": warning_consistency.get("recomputed_warnings", {}),
                "duration_exclusion_delta_detail": warning_consistency.get(
                    "duration_exclusion_delta_detail",
                    {},
                ),
                "risk_tensor_rematerialization_preview": warning_consistency.get(
                    "risk_tensor_rematerialization_preview",
                    {},
                ),
            },
            "krd_contract": {
                "status": krd_queue.get("review_status"),
                "blockers": krd_queue.get("review_blockers", []),
                "krd_remap_summary": krd_queue.get("krd_remap_summary", []),
                "decision_options": krd_queue.get("decision_options", []),
                "review_actions": krd_queue.get("review_actions", []),
            },
            "maturity_remediation": {
                "status": maturity_queue.get("remediation_status"),
                "blockers": maturity_queue.get("remediation_blockers", []),
                "remediation_scope": maturity_queue.get("remediation_scope", {}),
                "bond_no_maturity_summary": maturity_queue.get(
                    "bond_no_maturity_summary",
                    {},
                ),
                "bond_missing_maturity_summary": maturity_queue.get(
                    "bond_missing_maturity_summary",
                    {},
                ),
                "tyw_liability_missing_maturity_summary": maturity_queue.get(
                    "tyw_liability_missing_maturity_summary",
                    {},
                ),
                "remediation_actions": maturity_queue.get("remediation_actions", []),
            },
            "business_owner_approval": {
                "status": (
                    "captured"
                    if approval_status.get("business_owner_approval_captured")
                    else "pending"
                ),
                "blockers": approval_status.get("remaining_blockers", []),
                "approval_action_item_count": approval_status.get("approval_action_item_count"),
                "evidence_scope": approval_status.get("evidence_scope"),
            },
            "owner_decision_intake": owner_intake_gate,
            "owner_decision_intake_alignment": owner_intake_alignment,
            "owner_handoff_completeness": owner_handoff_completeness,
            "approval_dependency_consistency": {
                "status": dependency_status,
                "blockers": dependency_consistency_blockers,
                "generated_owner_fields_boundaries": generated_owner_fields_boundaries(
                    dependency_checks,
                ),
                "manifest_consistency_checks": dependency_checks,
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize portfolio-home full-score readiness across all evidence gates.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument("--limit", type=non_negative_portfolio_limit, default=25)
    parser.add_argument(
        "--require-full-score",
        action="store_true",
        help="Return non-zero unless every portfolio-home full-score gate is ready.",
    )
    args = parser.parse_args(argv)

    scorecard = build_scorecard(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        limit=int(args.limit),
        docs_root=Path(args.docs_root),
    )
    print(json.dumps(scorecard, ensure_ascii=False, indent=2))
    if args.require_full_score and not scorecard["full_score_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
