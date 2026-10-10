"""Build a sanitized, non-authoritative review packet for golden-sample blockers.

The command consumes an already-produced pytest JUnit XML file.  It never runs
pytest, rewrites a golden sample, captures an approval, or writes governance or
production state.  Failure bodies are deliberately not copied into the output.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden_samples"
TARGET_TEST = "test_capture_ready_golden_sample_matches_selected_fields"
GOLDEN_FILES = ("request.json", "response.json", "assertions.md", "approval.md")

EVIDENCE_SCOPE = {
    "authoritative": False,
    "captures_approval": False,
    "writes_golden_sample": False,
    "writes_governance_records": False,
    "production_writes": False,
    "release_eligible": False,
    "sensitive_values_included": False,
}

PROHIBITED_ACTIONS = [
    "overwrite tests/golden_samples or edit captured responses in place",
    "invent, migrate, or reuse owner and approver decisions",
    "weaken selected-field validators merely to make the gate pass",
    "downgrade current calculation, rule, cache, warning, or null semantics",
    "write governance records, release aliases, production caches, or production data",
]

OWNER_DECISION_SEQUENCE = [
    "calculation_or_api_owner_freezes_the_candidate_contract_and_version",
    "data_or_lineage_owner_verifies_source_rule_cache_and_date_evidence",
    "business_owner_reviews_full_payload_diff_and_coupled_reconciliation",
    "independent_approver_records_a_new_digest_bound_decision",
    "release_custodian_updates_authoritative_artifacts_and_reruns_required_gates",
]


BLOCKER_SPECS: dict[str, dict[str, Any]] = {
    "GS-BOND-HEADLINE-A": {
        "reason_code": "golden_bond_numeric_raw_text_owner_review_required",
        "expected_assertion_path": "result",
        "owner_role": "API OWNER + BUSINESS OWNER",
        "next_action": (
            "Review the full additive Numeric.raw_text and ResultMeta contract diff, "
            "resolve the documented empty-state null semantics, then capture a new "
            "candidate outside the authoritative golden tree."
        ),
        "coupled_samples": [],
        "rule_or_cache_decision_required": False,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/schemas/common_numeric.py",
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "tests/golden_samples/GS-BOND-HEADLINE-A/assertions.md",
            "tests/golden_samples/GS-BOND-HEADLINE-A/approval.md",
        ],
    },
    "GS-RISK-WARN-B": {
        "reason_code": "golden_risk_unversioned_rule_change_owner_decision_required",
        "expected_assertion_path": "result",
        "owner_role": "FINANCE/RISK RULE OWNER + BUSINESS OWNER",
        "next_action": (
            "Freeze the leap-day cash-flow convention and warning-sample authority "
            "boundary, bump Bond Analytics and Risk Tensor rule/cache lineage, "
            "rematerialize affected dates, and independently review the candidate."
        ),
        "coupled_samples": [],
        "rule_or_cache_decision_required": True,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/core_finance/bond_analytics/common.py",
            "backend/app/tasks/bond_analytics_materialize.py",
            "backend/app/tasks/risk_tensor_materialize.py",
            "docs/prd-release-control-plane.md",
            "tests/golden_samples/GS-RISK-WARN-B/approval.md",
        ],
    },
    "GS-BRIDGE-A": {
        "reason_code": "golden_pnl_v4_lineage_owner_review_required",
        "expected_assertion_path": "result_meta.rule_version",
        "owner_role": "PNL METRIC OWNER + DATA/LINEAGE OWNER + BUSINESS OWNER",
        "next_action": (
            "Capture and review this sample together with GS-BRIDGE-WARN-B, preserving "
            "residual, warning, balance-availability, date, and null semantics."
        ),
        "coupled_samples": ["GS-BRIDGE-WARN-B"],
        "rule_or_cache_decision_required": False,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/core_finance/pnl_constants.py",
            "backend/app/services/pnl_bridge_service.py",
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "tests/golden_samples/GS-BRIDGE-A/approval.md",
        ],
    },
    "GS-BRIDGE-WARN-B": {
        "reason_code": "golden_pnl_v4_lineage_owner_review_required",
        "expected_assertion_path": "result_meta.rule_version",
        "owner_role": "PNL METRIC OWNER + DATA/LINEAGE OWNER + BUSINESS OWNER",
        "next_action": (
            "Capture and review this warning sample together with GS-BRIDGE-A; do not "
            "hide warnings, clear the residual, or approve only one side of the pair."
        ),
        "coupled_samples": ["GS-BRIDGE-A"],
        "rule_or_cache_decision_required": False,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/core_finance/pnl_constants.py",
            "backend/app/services/pnl_bridge_service.py",
            "docs/page_contracts.md",
            "tests/golden_samples/GS-BRIDGE-WARN-B/assertions.md",
            "tests/golden_samples/GS-BRIDGE-WARN-B/approval.md",
        ],
    },
    "GS-PNL-ATTR-WB-A": {
        "reason_code": "golden_pnl_decimal_closure_version_decision_required",
        "expected_assertion_path": "result.total_rate_effect",
        "owner_role": "PNL CALCULATION OWNER + BUSINESS OWNER",
        "next_action": (
            "Confirm exact Decimal closure and decide whether the workbench rule/cache "
            "version must change before reviewing a non-authoritative candidate."
        ),
        "coupled_samples": [],
        "rule_or_cache_decision_required": True,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/core_finance/pnl_attribution/workbench.py",
            "backend/app/services/pnl_attribution_service.py",
            "docs/pnl/pnl-attribution-owner-evidence-packet.md",
            "tests/golden_samples/GS-PNL-ATTR-WB-A/approval.md",
        ],
    },
    "GS-PNL-BUSINESS-INSIGHTS-A": {
        "reason_code": "golden_pnl_approved_sample_reapproval_required",
        "expected_assertion_path": "result.component_evidence",
        "owner_role": ("组合管理/固收业务分析 OWNER + 财务管理/资产负债管理 APPROVER"),
        "next_action": (
            "Re-review all upstream v4 component lineage and bind a new approval to the "
            "candidate digest; the existing approved artifact cannot be inherited."
        ),
        "coupled_samples": [],
        "rule_or_cache_decision_required": False,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/services/pnl_by_business_candidate_insights.py",
            "docs/pnl/candidate-metrics-promotion-review.md",
            "docs/page_contracts.md",
            "tests/golden_samples/GS-PNL-BUSINESS-INSIGHTS-A/approval.md",
        ],
    },
    "GS-PNL-DATA-A": {
        "reason_code": "golden_pnl_v4_lineage_owner_review_required",
        "expected_assertion_path": "result_meta.rule_version",
        "owner_role": "PNL METRIC OWNER + DATA/LINEAGE OWNER + BUSINESS OWNER",
        "next_action": (
            "Capture and approve this sample together with GS-PNL-OVERVIEW-A and "
            "re-prove the Data-to-Overview reconciliation under v4 lineage."
        ),
        "coupled_samples": ["GS-PNL-OVERVIEW-A"],
        "rule_or_cache_decision_required": False,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/core_finance/pnl_constants.py",
            "backend/app/tasks/pnl_materialize.py",
            "backend/app/services/pnl_service.py",
            "tests/golden_samples/GS-PNL-DATA-A/approval.md",
        ],
    },
    "GS-PNL-OVERVIEW-A": {
        "reason_code": "golden_pnl_v4_lineage_owner_review_required",
        "expected_assertion_path": "result_meta.rule_version",
        "owner_role": "PNL METRIC OWNER + DATA/LINEAGE OWNER + BUSINESS OWNER",
        "next_action": (
            "Capture and approve this sample together with GS-PNL-DATA-A and "
            "re-prove the Overview-to-Data reconciliation under v4 lineage."
        ),
        "coupled_samples": ["GS-PNL-DATA-A"],
        "rule_or_cache_decision_required": False,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/core_finance/pnl_constants.py",
            "backend/app/services/pnl_service.py",
            "docs/golden_sample_catalog.md",
            "tests/golden_samples/GS-PNL-OVERVIEW-A/assertions.md",
            "tests/golden_samples/GS-PNL-OVERVIEW-A/approval.md",
        ],
    },
    "GS-STOCK-ANALYSIS-OBS-A": {
        "reason_code": "golden_stock_macro_terminology_owner_decision_required",
        "expected_assertion_path": "result.data_gaps",
        "owner_role": "PRODUCT OWNER + BUSINESS OWNER",
        "next_action": (
            "Freeze the social-financing primary series, M2 fallback, and adjacent-month "
            "credit-expansion proxy terminology; review the full DTO diff and decide "
            "whether Livermore rule/cache v1 must be bumped."
        ),
        "coupled_samples": [],
        "rule_or_cache_decision_required": True,
        "full_payload_review_required": True,
        "evidence_anchors": [
            "backend/app/services/market_data_livermore_service.py",
            "docs/prd-release-control-plane.md",
            "docs/pnl/stock-analysis-business-owner-approval-template.md",
            "docs/pnl/stock-analysis-owner-evidence-packet.md",
            "tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/approval.md",
        ],
    },
}


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _approval_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    status_match = re.search(r"(?m)^- Status:\s*`([^`]+)`\s*$", text)
    owner_match = re.search(r"(?m)^- Owner:\s*`([^`]+)`\s*$", text)
    return {
        "status": status_match.group(1) if status_match else "missing",
        "owner": owner_match.group(1) if owner_match else "missing",
    }


def _sample_id_from_case_name(name: str) -> str | None:
    match = re.fullmatch(rf"{TARGET_TEST}\[(GS-[A-Z0-9-]+)\]", name)
    return match.group(1) if match else None


def _assertion_path(failure: ET.Element | None) -> str | None:
    if failure is None:
        return None
    source = "\n".join(part for part in (failure.get("message"), failure.text) if part)
    match = re.search(r"AssertionError:\s*(\([^\r\n]+?\))", source)
    if not match:
        return None
    try:
        parsed = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return None
    if not isinstance(parsed, tuple) or not all(
        isinstance(part, str) for part in parsed
    ):
        return None
    return ".".join(parsed)


def _parse_junit_cases(junit_xml: Path) -> dict[str, list[dict[str, Any]]]:
    root = ET.parse(junit_xml).getroot()
    cases: dict[str, list[dict[str, Any]]] = {
        sample_id: [] for sample_id in BLOCKER_SPECS
    }
    for case in root.findall(".//testcase"):
        sample_id = _sample_id_from_case_name(case.get("name", ""))
        if sample_id not in cases:
            continue
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if error is not None:
            status = "error"
            detail = error
        elif failure is not None:
            status = "failed"
            detail = failure
        elif skipped is not None:
            status = "skipped"
            detail = skipped
        else:
            status = "passed"
            detail = None
        cases[sample_id].append(
            {
                "test_status": status,
                "assertion_path": _assertion_path(detail),
            }
        )
    return cases


def _display_path(path: Path, *, repo_root: Path = ROOT) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return "<external-junit-xml>"


def build_review_packet(
    *,
    junit_xml: Path,
    generated_at: str | None = None,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    junit_xml = Path(junit_xml)
    cases = _parse_junit_cases(junit_xml)
    golden_root = Path(repo_root) / "tests" / "golden_samples"
    rows: list[dict[str, Any]] = []

    for sample_id, spec in BLOCKER_SPECS.items():
        observations = cases[sample_id]
        if len(observations) == 1:
            observation = observations[0]
        elif not observations:
            observation = {"test_status": "missing", "assertion_path": None}
        else:
            observation = {"test_status": "duplicate", "assertion_path": None}

        sample_root = golden_root / sample_id
        hashes = {
            filename: _sha256(sample_root / filename) for filename in GOLDEN_FILES
        }
        approval = _approval_metadata(sample_root / "approval.md")
        test_failed = observation["test_status"] in {
            "failed",
            "error",
            "skipped",
            "missing",
            "duplicate",
        }
        rows.append(
            {
                "sample_id": sample_id,
                "test_node": (
                    "tests/test_golden_samples_capture_ready.py::"
                    f"{TARGET_TEST}[{sample_id}]"
                ),
                "test_status": observation["test_status"],
                "observed_assertion_path": observation["assertion_path"],
                "expected_assertion_path": spec["expected_assertion_path"],
                "reason_code": spec["reason_code"],
                "owner_role": spec["owner_role"],
                "captured_approval_status": approval["status"],
                "captured_owner": approval["owner"],
                "approval_revalidation_required": (
                    test_failed and approval["status"] == "approved"
                ),
                "candidate_capture_mode": "non_authoritative_review_only",
                "candidate_capture_authorized": False,
                "rule_or_cache_decision_required": spec[
                    "rule_or_cache_decision_required"
                ],
                "full_payload_review_required": spec["full_payload_review_required"],
                "coupled_samples": list(spec["coupled_samples"]),
                "next_action": spec["next_action"],
                "evidence_anchors": list(spec["evidence_anchors"]),
                "artifact_sha256": hashes,
            }
        )

    counts = {
        status: sum(row["test_status"] == status for row in rows)
        for status in ("passed", "failed", "error", "skipped", "missing", "duplicate")
    }
    observation_complete = counts["missing"] == 0 and counts["duplicate"] == 0
    all_tests_passed = observation_complete and counts["passed"] == len(rows)
    status = "awaiting_owner_decisions" if all_tests_passed else "blocked"
    return {
        "report_kind": "release_control_golden_blocker_review",
        "schema_version": "1.0",
        "generated_at": generated_at or _default_generated_at(),
        "status": status,
        "release_eligible": False,
        "sample_count": len(rows),
        "observation": {
            "source_kind": "pytest_junit",
            "junit_xml_path": _display_path(junit_xml, repo_root=repo_root),
            "junit_xml_sha256": _sha256(junit_xml),
            "complete": observation_complete,
            "all_targeted_tests_passed": all_tests_passed,
            "counts": counts,
        },
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "owner_decision_sequence": list(OWNER_DECISION_SEQUENCE),
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "samples": rows,
        "boundary": (
            "This packet is a sanitized review index. It does not copy pytest failure "
            "values, approve a metric or page, authorize recapture, change a golden "
            "sample, write governance state, or make a release eligible."
        ),
    }


def _safe_output_path(output: Path, *, repo_root: Path = ROOT) -> Path:
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("output must be a .json file")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError("output parent must already exist")

    repo = Path(repo_root).resolve()
    resolved = output.resolve(strict=False)
    allowed = []
    for name in ("output", ".tmp"):
        candidate = (repo / name).resolve(strict=False)
        if candidate == repo or not candidate.is_relative_to(repo):
            continue
        allowed.append(candidate)
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise ValueError("output must resolve inside repository output/ or .tmp/")
    return resolved


def write_packet_exclusive(
    *,
    output: Path,
    packet: dict[str, Any],
    repo_root: Path = ROOT,
) -> Path:
    resolved = _safe_output_path(output, repo_root=repo_root)
    with resolved.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(packet, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a sanitized non-authoritative review packet from a targeted pytest "
            "JUnit XML file."
        )
    )
    parser.add_argument("--junit-xml", type=Path, required=True)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    packet = build_review_packet(
        junit_xml=args.junit_xml,
        generated_at=args.generated_at,
    )
    payload = json.dumps(packet, ensure_ascii=False, indent=2)
    if args.output is not None:
        write_packet_exclusive(output=args.output, packet=packet)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
