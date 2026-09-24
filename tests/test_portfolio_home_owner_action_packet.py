from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_portfolio_home_business_owner_approval_status import _filled_template_text
from tests.test_portfolio_home_closure_scorecard import (
    REPORT_DATE,
    _approved_template_text,
    _create_schema,
    _insert_clean_data,
    _write_clean_fixture_manifests,
    _write_clean_handoff_snapshot,
)
from tests.test_portfolio_home_owner_decision_intake_check import (
    _rewrite_csv,
    _write_exact_bucket_schema_evidence,
    _write_maturity_scoped_exclusion_evidence,
    _write_nearest_bucket_approval_evidence,
)

from scripts.portfolio_home_owner_action_packet import (
    _assignment_coverage,
    _business_owner_blockers,
    _closure_artifacts_for_blocker,
    _closure_evidence_sources_for_blocker,
    _closure_exit_signal,
    _closure_recheck_commands,
    _data_owner_decision_artifacts,
    _strict_gate_clean,
    build_packet,
)
from scripts.portfolio_home_business_owner_approval_packet import (
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    PORTFOLIO_HOME_SCORE_BLOCKERS,
    _owner_decision_intake_summary as _business_owner_decision_intake_summary,
    _activation_guard,
)
from scripts.portfolio_home_owner_decision_intake_check import build_intake_check
from tests.test_portfolio_home_business_owner_approval_packet import (
    APPROVAL_BOUNDARY_BLOCKER_ORDER,
    RISK_WARNING_EVIDENCE_SCOPE,
    RISK_WARNING_RESOLUTION_SCOPE,
    _valid_rerun_payload,
    _write_rerun_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_owner_action_packet.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DUCKDB.exists(),
        reason="requires local governed DuckDB at data/moss.duckdb",
    ),
]
def test_bond_no_maturity_is_not_a_data_owner_decision_artifact() -> None:
    artifacts = _data_owner_decision_artifacts(REPORT_DATE)
    paths = [str(item["artifact"]) for item in artifacts]

    assert paths == [
        f"docs/portfolio/maturity-remediation/{REPORT_DATE}/tyw_liability_missing_maturity.csv",
        f"docs/portfolio/maturity-remediation/{REPORT_DATE}/maturity_scoped_exclusion_evidence.json",
    ]
    assert _closure_artifacts_for_blocker(
        "bond_maturity_date_remediation_required",
        REPORT_DATE,
    ) == []
    assert _closure_recheck_commands(
        "bond_maturity_date_remediation_required",
        REPORT_DATE,
    ) == []
def test_matured_outstanding_does_not_advertise_unimplemented_exception_closure() -> None:
    blocker = "bond_matured_outstanding_reconciliation_required"

    assert _closure_artifacts_for_blocker(blocker, REPORT_DATE) == []
    exit_signal = _closure_exit_signal(blocker, REPORT_DATE)
    assert "exception" not in exit_signal.lower()
    assert "strict queue exits 0" in exit_signal




def test_closure_recheck_commands_are_report_date_scoped() -> None:
    report_date = "2026-06-30"
    blockers = [
        "risk_tensor_quality_warning",
        "krd_bucket_warning_mismatch",
        "risk_tensor_warning_mismatch",
        "duration_exclusion_warning_mismatch",
        "krd_contract_decision_required",
        "bond_matured_outstanding_reconciliation_required",
        "tyw_liability_maturity_date_remediation_required",
        "business_owner_approval",
        "owner_decision_intake_blocked",
    ]

    for blocker in blockers:
        commands = _closure_recheck_commands(blocker, report_date)
        assert commands
        assert all(f"--report-date {report_date}" in command for command in commands)




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


def _assert_duration_exclusion_delta_detail_structure(detail: dict[str, object]) -> None:
    # 该细节反映本机治理库当前 parsed vs recomputed 的差异；只锁定字段存在、
    # 取值域与代码不变式（matched 当且仅当无逐字段不一致），不锁定具体数值。
    assert detail["status"] in {"matched", "mismatch"}
    assert detail["delta_basis"] == "recomputed_minus_parsed"
    assert isinstance(detail["mismatch_fields"], list)
    assert (detail["status"] == "matched") is (detail["mismatch_fields"] == [])
    assert isinstance(detail["owner_reconciliation_hint"], str) and detail["owner_reconciliation_hint"]
    delta = detail["delta"]
    assert set(delta) == {
        "row_count",
        "market_value_sum",
        "no_maturity_rows",
        "no_maturity_market_value",
        "matured_or_expired_outstanding_rows",
        "matured_or_expired_outstanding_market_value",
        "nonpositive_duration_rows",
        "nonpositive_duration_market_value",
    }
    for field_name, field_value in delta.items():
        if field_name.endswith("_rows") or field_name == "row_count":
            assert isinstance(field_value, int)
        else:
            assert re.fullmatch(r"-?\d+\.\d{8}", str(field_value))
    assert isinstance(detail["parsed_warning_text"], str) and detail["parsed_warning_text"]


def _assert_warning_resolution_matrix_structure(matrix: list[object]) -> None:
    # warning_key 目录与每项固定 owner 是代码常量；动态项（duration_no_maturity /
    # bond_liquidity_gap_no_maturity）的 owner 与 current_status 取决于
    # parsed==recomputed 是否一致，属于本机库可变状态。
    matrix_by_key = {row["warning_key"]: row for row in matrix}
    assert list(matrix_by_key) == [
        "krd_bucket_remap",
        "duration_no_maturity",
        "matured_or_expired_outstanding",
        "nonpositive_duration",
        "bond_liquidity_gap_no_maturity",
        "tyw_liability_gap_missing_maturity",
    ]
    fixed_owner_keys = {
        "krd_bucket_remap": "risk_owner",
        "matured_or_expired_outstanding": "data_owner",
        "nonpositive_duration": "data_owner",
        "tyw_liability_gap_missing_maturity": "data_owner",
    }
    dynamic_owner_keys = {"duration_no_maturity", "bond_liquidity_gap_no_maturity"}
    for key, expected_owner in fixed_owner_keys.items():
        row = matrix_by_key[key]
        assert row["owner"] == expected_owner
        assert row["current_status"] in {"clean", "blocked"}
    for key in dynamic_owner_keys:
        row = matrix_by_key[key]
        assert row["owner"] in {"none", "risk_owner"}
        assert row["current_status"] in {"informational", "blocked"}
        assert (row["owner"] == "none") is (row["current_status"] == "informational")


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


def _expected_not_required_nearest_bucket_approval_evidence() -> dict[str, object]:
    return {
        "status": "not_required",
        "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
        "valid": True,
        "blockers": [],
    }


def _expected_closure_artifact_presence_summary() -> dict[str, object]:
    return {
        "status": "current",
        "current": True,
        "blockers": [],
        "artifact_current_summary": {
            **_expected_export_current_summary(),
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


def test_portfolio_home_owner_action_packet_cli_writes_and_checks_current(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "portfolio-home-owner-action-packet.json"

    returncode, payload = _run_packet(
        "--limit",
        "1",
        "--output",
        str(output_path),
    )

    assert returncode == 0
    assert payload["packet_kind"] == "portfolio_home_owner_action_packet"
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


def test_portfolio_home_owner_action_packet_check_current_blocks_stale_file(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "portfolio-home-owner-action-packet.json"
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


def test_portfolio_home_owner_action_packet_assigns_owner_intake_blocker() -> None:
    assert _business_owner_blockers(
        [
            "business_owner_approval",
            "formal_page_approval_missing",
            "approval_dependency_consistency_blocked",
            "owner_decision_intake_blocked",
            "owner_decision_intake_alignment_blocked",
        ]
    ) == [
        "business_owner_approval",
        "formal_page_approval_missing",
        "approval_dependency_consistency_blocked",
        "owner_decision_intake_blocked",
        "owner_decision_intake_alignment_blocked",
    ]

    coverage = _assignment_coverage(
        [
            "owner_decision_intake_blocked",
            "owner_decision_intake_alignment_blocked",
        ],
        {
            "risk_owner": {"blockers": []},
            "data_owner": {"blockers": []},
            "business_owner": {
                "blockers": [
                    "owner_decision_intake_blocked",
                    "owner_decision_intake_alignment_blocked",
                ],
            },
        },
    )

    assert coverage == {
        "status": "clean",
        "score_blockers": [
            "owner_decision_intake_blocked",
            "owner_decision_intake_alignment_blocked",
        ],
        "assigned_blockers": [
            "owner_decision_intake_blocked",
            "owner_decision_intake_alignment_blocked",
        ],
        "unassigned_blockers": [],
        "duplicate_assigned_blockers": [],
        "unexpected_assigned_blockers": [],
    }


def test_portfolio_home_owner_action_packet_blocks_unexpected_owner_assigned_blocker() -> None:
    coverage = _assignment_coverage(
        ["risk_tensor_quality_warning"],
        {
            "risk_owner": {
                "blockers": [
                    "risk_tensor_quality_warning",
                    "krd_owner_decision_rejected",
                ],
            },
            "data_owner": {"blockers": []},
            "business_owner": {"blockers": []},
        },
    )

    assert coverage == {
        "status": "blocked",
        "score_blockers": ["risk_tensor_quality_warning"],
        "assigned_blockers": [
            "risk_tensor_quality_warning",
            "krd_owner_decision_rejected",
        ],
        "unassigned_blockers": [],
        "duplicate_assigned_blockers": [],
        "unexpected_assigned_blockers": ["krd_owner_decision_rejected"],
    }
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "assignment_coverage": coverage,
                "score_blocker_action_coverage": {"status": "clean"},
                "blocker_closure_matrix_coverage": {"status": "clean"},
                "business_owner_approval_boundary": {
                    "template_approval_captured": True,
                    "formal_authorization_allowed": True,
                    "governance_write_allowed": True,
                    "page_execution_proven": True,
                    "full_score_closure_ready": True,
                    "activation_ready": True,
                    "status": "activated",
                    "blockers": [],
                },
            }
        )
        is False
    )


def test_portfolio_home_owner_action_packet_keeps_resolved_warning_mismatch_blockers_cleared() -> None:
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
    )

    for blocker in (
        "krd_bucket_warning_mismatch",
        "duration_exclusion_warning_mismatch",
        "risk_tensor_warning_mismatch",
    ):
        assert blocker not in packet["score_blockers"]
        for owner_packet in packet["owner_packets"].values():
            assert blocker not in owner_packet["blockers"]
    assert packet["assignment_coverage"]["status"] == "clean"
    assert packet["assignment_coverage"]["unassigned_blockers"] == []


def test_portfolio_home_owner_action_packet_krd_bucket_warning_mismatch_reuses_warning_consistency_evidence_chain() -> None:
    report_date = "2026-06-30"

    assert _closure_evidence_sources_for_blocker(
        "krd_bucket_warning_mismatch",
        report_date,
    ) == [
        {
            "name": "risk_warning_consistency",
            "command": (
                "python scripts/portfolio_home_risk_warning_consistency.py "
                f"--report-date {report_date} --require-consistent"
            ),
            "fields": [
                "parsed_warnings",
                "recomputed_warnings",
                "duration_exclusion_delta_detail",
                "warning_resolution_matrix",
                "decision_blockers",
            ],
            "boundary": (
                "Evidence-only warning consistency check; does not approve "
                "the metric, clean the risk tensor, or close the page."
            ),
        }
    ]
    assert _closure_recheck_commands(
        "krd_bucket_warning_mismatch",
        report_date,
    ) == [
        (
            "python scripts/portfolio_home_risk_warning_consistency.py "
            f"--report-date {report_date} --require-consistent"
        ),
        (
            "python scripts/portfolio_home_full_closure_evidence.py "
            f"--report-date {report_date} --require-clean"
        ),
    ]
    assert _closure_exit_signal(
        "krd_bucket_warning_mismatch",
        report_date,
    ) == (
        "KRD bucket warning evidence matches current formal bonds, and the risk tensor "
        "is rematerialized or /portfolio remains candidate-only until the warning can "
        "be cleared."
    )

def test_portfolio_home_owner_action_packet_assigns_warning_mismatch_blockers() -> None:
    coverage = _assignment_coverage(
        [
            "duration_exclusion_warning_mismatch",
            "risk_tensor_warning_mismatch",
        ],
        {
            "risk_owner": {"blockers": ["risk_tensor_warning_mismatch"]},
            "data_owner": {"blockers": ["duration_exclusion_warning_mismatch"]},
            "business_owner": {"blockers": []},
        },
    )

    assert coverage == {
        "status": "clean",
        "score_blockers": [
            "duration_exclusion_warning_mismatch",
            "risk_tensor_warning_mismatch",
        ],
        "assigned_blockers": [
            "duration_exclusion_warning_mismatch",
            "risk_tensor_warning_mismatch",
        ],
        "unassigned_blockers": [],
        "duplicate_assigned_blockers": [],
        "unexpected_assigned_blockers": [],
    }


def test_portfolio_home_owner_action_packet_reuses_business_owner_intake_summary_contract() -> None:
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=2,
    )
    intake_check = build_intake_check(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=2,
    )

    assert packet["owner_decision_intake_summary"] == (
        _business_owner_decision_intake_summary(intake_check)
    )


def test_portfolio_home_owner_action_packet_blocks_rerun_verifier_result_drift(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_root / "audits")
    artifact = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    payload = _valid_rerun_payload()
    verifier = payload["verification_report"]
    assert isinstance(verifier, dict)
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["matches_expected_exit"] = False
    _write_rerun_artifact(artifact, payload)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["rerun_evidence_status"] == {
        "status": "blocked",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": [
            "rerun_evidence_verifier_result_mismatch",
        ],
    }
    assert packet["business_owner_approval_boundary"]["activation_ready"] is False


def test_portfolio_home_owner_action_packet_groups_current_blockers_by_owner() -> None:
    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=2,
    )

    # 宽松结构守卫：本机治理库当前具体值（分数、阻塞项名单、行数等）随库状态
    # 演进而变化；只锁定字段存在、类型、取值域与代码不变式，代码常量契约
    # （字段名清单、evidence_scope、闭环目录相对顺序等）保持精确断言。
    assert packet["packet_kind"] == "portfolio_home_owner_action_packet"
    assert re.fullmatch(r"\d+(?:\.\d+)? / 100", str(packet["current_score"]))
    assert re.fullmatch(r"\d+(?:\.\d+)?", str(packet["remaining_gap"]))
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
    }
    assert packet["dependency_consistency_status"] in {"consistent", "blocked"}
    assert isinstance(packet["dependency_consistency_blockers"], list)

    csv_check_summary = packet["csv_check_summary"]
    assert set(csv_check_summary) == {
        "krd_summary_row_count",
        "krd_detail_row_count",
        "krd_owner_decision_fields_blank",
        "bond_missing_maturity_row_count",
        "tyw_liability_missing_maturity_row_count",
        "maturity_owner_fields_blank",
    }
    for count_field in (
        "krd_summary_row_count",
        "krd_detail_row_count",
        "bond_missing_maturity_row_count",
        "tyw_liability_missing_maturity_row_count",
    ):
        assert isinstance(csv_check_summary[count_field], int) and csv_check_summary[count_field] >= 0
    assert isinstance(csv_check_summary["krd_owner_decision_fields_blank"], bool)
    assert isinstance(csv_check_summary["maturity_owner_fields_blank"], bool)

    assert packet["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }

    presence_summary = packet["closure_artifact_presence_summary"]
    assert set(presence_summary) == {"status", "current", "blockers", "artifact_current_summary"}
    assert isinstance(presence_summary["status"], str) and presence_summary["status"]
    assert isinstance(presence_summary["current"], bool)
    assert isinstance(presence_summary["blockers"], list)
    artifact_summary = presence_summary["artifact_current_summary"]
    assert set(artifact_summary) == {
        "krd",
        "maturity",
        "business_owner_approval_template",
        "exact_bucket_schema_evidence",
        "nearest_bucket_approval_evidence",
        "maturity_scoped_exclusion_evidence",
    }
    for artifact_name, artifact_status in artifact_summary.items():
        assert isinstance(artifact_status["status"], str) and artifact_status["status"], artifact_name
        assert isinstance(artifact_status["current"], bool), artifact_name
        assert isinstance(artifact_status["current_blockers"], list), artifact_name

    # score_blockers 是本机治理库当前实际生效的可变状态；只锁定它是完整闭环目录
    # PORTFOLIO_HOME_SCORE_BLOCKERS 的合法子序列（成员+相对顺序不变式）。
    live_score_blockers = packet["score_blockers"]
    assert isinstance(live_score_blockers, list)
    assert set(live_score_blockers).issubset(set(PORTFOLIO_HOME_SCORE_BLOCKERS))
    assert live_score_blockers == [
        blocker for blocker in PORTFOLIO_HOME_SCORE_BLOCKERS if blocker in live_score_blockers
    ]
    assert packet["assignment_coverage"] == {
        "status": "clean",
        "score_blockers": live_score_blockers,
        "assigned_blockers": live_score_blockers,
        "unassigned_blockers": [],
        "duplicate_assigned_blockers": [],
        "unexpected_assigned_blockers": [],
    }
    assert packet["score_blocker_action_coverage"] == {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": live_score_blockers,
    }
    assert packet["blocker_closure_matrix_coverage"] == {
        "status": "clean",
        "expected_blockers": live_score_blockers,
        "covered_blockers": live_score_blockers,
        "missing_blockers": [],
        "unexpected_blockers": [],
        "duplicate_blockers": [],
    }
    # blocker_closure_matrix 每一行的措辞、证据来源、决策工件清单都是代码模板常量；
    # 哪些行会出现取决于本机治理库当前哪些阻塞项仍然生效（live_score_blockers）。
    # 只对当前仍然生效的已知阻塞项做精确模板断言，不锁定它们是否仍然阻塞。
    full_blocker_closure_matrix_template = [
        {
            "blocker": "risk_tensor_quality_warning",
            "owner": "risk_owner",
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": (
                "Review the warning-consistency evidence, then rematerialize a clean risk "
                "tensor or keep the page candidate-only."
            ),
            "decision_artifacts": [],
            "evidence_sources": [
                {
                    "name": "risk_warning_consistency",
                    "command": (
                        "python scripts/portfolio_home_risk_warning_consistency.py "
                        "--report-date 2026-05-31 --require-consistent"
                    ),
                    "fields": [
                        "parsed_warnings",
                        "recomputed_warnings",
                        "duration_exclusion_delta_detail",
                        "warning_resolution_matrix",
                        "decision_blockers",
                    ],
                    "boundary": (
                        "Evidence-only warning consistency check; does not approve "
                        "the metric, clean the risk tensor, or close the page."
                    ),
                },
            ],
            "required_fields": [],
            "recheck_commands": [
                "python scripts/portfolio_home_risk_warning_consistency.py --report-date 2026-05-31 --require-clean",
                "python scripts/portfolio_home_full_closure_evidence.py --report-date 2026-05-31 --require-clean",
            ],
            "exit_criteria": (
                "Risk warning clean gate exits 0 and full-closure evidence no longer "
                "reports risk_tensor_quality_warning."
            ),
            "removes_blocker_when": (
                "Risk tensor quality is clean for report_date 2026-05-31 and strict "
                "full-closure evidence no longer reports this blocker."
            ),
        },
        {
            "blocker": "krd_contract_decision_required",
            "owner": "risk_owner",
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": (
                "Approve nearest-bucket mappings for 2Y, 6M, and 20Y, or require "
                "an exact-bucket KRD schema/API update."
            ),
            "decision_artifacts": [
                "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv",
                "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
                "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
                "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
            ],
            "required_fields": [
                "risk_owner_decision",
                "decision_notes",
                "risk_owner_name",
                "risk_owner_approval_date",
                "risk_owner_approved",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "metric_contract_decision_recorded",
                "verification_rerun_matched",
                "metric_contract_owner_name",
                "metric_contract_update_date",
                "metric_contract_updated",
                "api_schema_owner_name",
                "api_schema_update_date",
                "api_schema_updated",
                "risk_tensor_owner_name",
                "risk_tensor_rematerialization_date",
                "risk_tensor_rematerialized",
                "verifier_name",
                "verification_rerun_date",
            ],
            "recheck_commands": [
                "python scripts/portfolio_home_krd_remap_review_queue.py --report-date 2026-05-31 --require-clean",
                "python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready",
            ],
            "exit_criteria": (
                "KRD review queue exits 0 under the approved contract and the metric "
                "contract records the decision."
            ),
            "removes_blocker_when": (
                "Risk-owner KRD decision is captured with notes for every scoped row, "
                "conditional nearest-bucket or exact-bucket evidence is valid when "
                "selected, and the KRD strict gate exits 0."
            ),
        },
        {
            "blocker": "bond_matured_outstanding_reconciliation_required",
            "owner": "data_owner",
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": (
                "Reconcile matured or unparseable non-zero bond positions at source; "
                "this read-only gate does not accept an exception as closure evidence."
            ),
            "decision_artifacts": [],
            "required_fields": [],
            "recheck_commands": [
                "python scripts/portfolio_home_matured_outstanding_queue.py --report-date 2026-05-31 --require-empty",
                "python scripts/portfolio_home_full_closure_evidence.py --report-date 2026-05-31 --require-clean",
            ],
            "exit_criteria": (
                "Matured outstanding strict queue exits 0 with no matured or "
                "unparseable non-zero bond positions."
            ),
            "removes_blocker_when": (
                "Matured or unparseable non-zero bond positions are reconciled at source, "
                "and the matured-outstanding strict queue exits 0."
            ),
            "evidence_sources": [
                {
                    "name": "matured_outstanding_queue",
                    "command": (
                        "python scripts/portfolio_home_matured_outstanding_queue.py "
                        "--report-date 2026-05-31 --require-empty"
                    ),
                    "fields": ["summary", "rows"],
                    "boundary": (
                        "Read-only reconciliation evidence; does not change source positions, "
                        "approve an exception, or close the page."
                    ),
                }
            ],
        },
        {
            "blocker": "tyw_liability_maturity_date_remediation_required",
            "owner": "data_owner",
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": (
                "Remediate missing TYW liability maturity_date values or capture a signed "
                "scoped exclusion before rematerialization."
            ),
            "decision_artifacts": [
                "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv",
                "docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json",
            ],
            "required_fields": [
                "proposed_maturity_date",
                "owner_decision",
                "owner_comment",
                "data_owner_name",
                "data_owner_approval_date",
                "data_owner_approved",
                "risk_owner_name",
                "risk_owner_countersign_date",
                "risk_owner_countersigned",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "verification_rerun_matched",
            ],
            "recheck_commands": [
                "python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty",
                "python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready",
            ],
            "exit_criteria": (
                "TYW liability maturity remediation queue is empty or signed exclusion "
                "evidence is captured and surfaced as a boundary."
            ),
            "removes_blocker_when": (
                "TYW liability missing-maturity rows are remediated at source or covered "
                "by a signed scoped exclusion evidence file, and the maturity strict gate exits 0."
            ),
        },
        {
            "blocker": "business_owner_approval",
            "owner": "business_owner",
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": (
                "Complete and sign the portfolio-home business owner approval template "
                "with risk-owner countersignature."
            ),
            "decision_artifacts": [
                "docs/portfolio/portfolio-home-business-owner-approval-template.md",
            ],
            "required_fields": [
                "approval_status",
                "business_owner_name",
                "risk_owner_name",
                "approval_decision",
                "approval_date",
                "business_owner_signature",
                "risk_owner_signature",
                "krd_contract_decision",
                "maturity_data_decision",
                "risk_tensor_warning_decision",
                "evidence_scope",
            ],
            "recheck_commands": [
                "python scripts/check_portfolio_home_business_owner_approval.py --report-date 2026-05-31 --require-captured",
                "python scripts/portfolio_home_business_owner_approval_packet.py --report-date 2026-05-31 --limit 3 --require-ready",
                "python scripts/portfolio_home_closure_scorecard.py --report-date 2026-05-31 --limit 3 --require-full-score",
            ],
            "exit_criteria": (
                "Approval checker exits 0 and evidence_scope.approves_metric_or_page is true."
            ),
            "removes_blocker_when": (
                "Business-owner approval is signed, risk-owner countersignature is present, "
                "evidence scope approves the page, and the full scorecard strict gate exits 0."
            ),
        },
        {
            "blocker": "owner_decision_intake_blocked",
            "owner": "business_owner",
            "current_blocker_present": True,
            "status": "blocked",
            "next_action": (
                "Reconcile risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, "
                "data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval "
                "before full-score activation."
            ),
            "decision_artifacts": [
                "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv",
                "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
                "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
                "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
                "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv",
                "docs/portfolio/maturity-remediation/2026-05-31/maturity_scoped_exclusion_evidence.json",
                "docs/portfolio/portfolio-home-business-owner-approval-template.md",
            ],
            "required_fields": [
                "risk_owner_decision",
                "decision_notes",
                "risk_owner_name",
                "risk_owner_approval_date",
                "risk_owner_approved",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "metric_contract_decision_recorded",
                "verification_rerun_matched",
                "metric_contract_owner_name",
                "metric_contract_update_date",
                "metric_contract_updated",
                "api_schema_owner_name",
                "api_schema_update_date",
                "api_schema_updated",
                "risk_tensor_owner_name",
                "risk_tensor_rematerialization_date",
                "risk_tensor_rematerialized",
                "verifier_name",
                "verification_rerun_date",
                "proposed_maturity_date",
                "owner_decision",
                "owner_comment",
                "data_owner_name",
                "data_owner_approval_date",
                "data_owner_approved",
                "risk_owner_countersign_date",
                "risk_owner_countersigned",
                "approval_status",
                "approval_decision",
                "approval_date",
                "business_owner_signature",
                "risk_owner_signature",
                "krd_contract_decision",
                "maturity_data_decision",
                "risk_tensor_warning_decision",
                "evidence_scope",
            ],
            "recheck_commands": [
                "python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready",
            ],
            "exit_criteria": "Owner decision intake strict gate exits 0 and reports intake_ready=true.",
            "removes_blocker_when": (
                "Risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, "
                "data-owner CSV decisions, scoped-exclusion evidence, and business-owner "
                "approval are reconciled, and the owner decision intake strict gate exits 0."
            ),
        },
    ]
    assert packet["blocker_closure_matrix"] == [
        row
        for row in full_blocker_closure_matrix_template
        if row["blocker"] in live_score_blockers
    ]

    owner_packets = packet["owner_packets"]
    assert set(owner_packets) == {"risk_owner", "data_owner", "business_owner"}

    risk_owner = owner_packets["risk_owner"]
    assert risk_owner["status"] in {"clean", "blocked"}
    # risk_owner 归属的两个已知阻塞项名单是代码模板顺序；哪些当前仍然生效属于
    # 本机治理库状态，随库状态演进而变化。
    assert risk_owner["blockers"] == [
        blocker
        for blocker in ("risk_tensor_quality_warning", "krd_contract_decision_required")
        if blocker in live_score_blockers
    ]
    assert isinstance(risk_owner["risk_tensor_quality_flag"], str)
    risk_owner_warning_matrix = risk_owner["warning_resolution_matrix"]
    _assert_warning_resolution_matrix_structure(risk_owner_warning_matrix)
    assert risk_owner_warning_matrix[0]["evidence_scope"] == RISK_WARNING_RESOLUTION_SCOPE
    risk_owner_delta = risk_owner["duration_exclusion_delta_detail"]
    _assert_duration_exclusion_delta_detail_structure(risk_owner_delta)
    # 该行的具体持仓明细（代码、市值、久期等）属于本机持仓库当前状态；
    # 只锁定字段存在与结构，不锁定具体持仓数值。
    top_row = risk_owner_delta["top_recomputed_rows_by_market_value"][0]
    assert set(top_row) == {
        "exclusion_reason",
        "instrument_code",
        "instrument_name",
        "portfolio_name",
        "cost_center",
        "source_version",
        "trace_id",
        "market_value",
        "maturity_date",
        "modified_duration",
        "dv01",
    }
    assert top_row["exclusion_reason"] in {
        "no_maturity",
        "matured_or_expired_outstanding",
        "nonpositive_duration",
    }
    risk_owner_preview = risk_owner["risk_tensor_rematerialization_preview"]
    assert risk_owner_preview["preview_basis"] == "current_formal_facts_read_only"
    assert risk_owner_preview["writes_database"] is False
    assert isinstance(risk_owner_preview["would_clear_consistency_blockers"], list)
    assert risk_owner_preview["preview_decision_status"] in {"clean", "blocked"}
    assert isinstance(risk_owner_preview["preview_decision_blockers"], list)
    assert isinstance(risk_owner_preview["preview_warnings"], list)
    assert risk_owner["dependency_consistency_status"] in {"consistent", "blocked"}
    assert isinstance(risk_owner["csv_check_summary"]["krd_detail_row_count"], int)
    assert isinstance(risk_owner["csv_check_summary"]["krd_owner_decision_fields_blank"], bool)
    assert risk_owner["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }
    assert risk_owner["decision_intake_artifacts"] == [
        {
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv",
            "required_fields": ["risk_owner_decision", "decision_notes"],
            "allowed_decisions": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
            "note_required_for": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
        },
        {
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv",
            "required_fields": ["risk_owner_decision", "decision_notes"],
            "allowed_decisions": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
            "note_required_for": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
        },
        {
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
            "required_fields": [
                "risk_owner_name",
                "risk_owner_approval_date",
                "risk_owner_approved",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "metric_contract_decision_recorded",
                "verification_rerun_matched",
            ],
            "allowed_decisions": ["approve_nearest_bucket"],
            "note_required_for": [],
        },
        {
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
            "required_fields": [
                "metric_contract_owner_name",
                "metric_contract_update_date",
                "metric_contract_updated",
                "api_schema_owner_name",
                "api_schema_update_date",
                "api_schema_updated",
                "risk_tensor_owner_name",
                "risk_tensor_rematerialization_date",
                "risk_tensor_rematerialized",
                "verifier_name",
                "verification_rerun_date",
                "verification_rerun_matched",
            ],
            "allowed_decisions": ["require_exact_bucket_schema"],
            "note_required_for": [],
        },
    ]
    assert risk_owner["krd_decision_options"] == [
        "approve_nearest_bucket",
        "require_exact_bucket_schema",
        "reject",
    ]
    assert isinstance(risk_owner["krd_remap_summary"][0]["tenor_bucket"], str)

    data_owner = owner_packets["data_owner"]
    assert data_owner["status"] in {"clean", "blocked"}
    # data_owner 归属的两个已知阻塞项名单是代码模板顺序；哪些当前仍然生效属于
    # 本机治理库状态。
    assert data_owner["blockers"] == [
        blocker
        for blocker in (
            "tyw_liability_maturity_date_remediation_required",
            "bond_matured_outstanding_reconciliation_required",
        )
        if blocker in live_score_blockers
    ]
    assert isinstance(data_owner["bond_missing_maturity_summary"]["missing_maturity_rows"], int)
    data_owner_delta = data_owner["duration_exclusion_delta_detail"]
    _assert_duration_exclusion_delta_detail_structure(data_owner_delta)
    data_owner_preview = data_owner["risk_tensor_rematerialization_preview"]
    assert data_owner_preview == risk_owner_preview
    assert isinstance(
        data_owner["tyw_liability_missing_maturity_summary"]["missing_maturity_rows"], int
    )
    assert data_owner["dependency_consistency_status"] in {"consistent", "blocked"}
    assert isinstance(data_owner["csv_check_summary"]["bond_missing_maturity_row_count"], int)
    assert isinstance(
        data_owner["csv_check_summary"]["tyw_liability_missing_maturity_row_count"], int
    )
    assert isinstance(data_owner["csv_check_summary"]["maturity_owner_fields_blank"], bool)
    assert data_owner["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }
    assert data_owner["decision_intake_artifacts"] == [
        {
            "artifact": "docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv",
            "required_fields": ["proposed_maturity_date", "owner_decision", "owner_comment"],
            "allowed_decisions": [
                "remediate_source",
                "approve_scoped_exclusion",
                "reject",
            ],
            "note_required_for": [
                "remediate_source",
                "approve_scoped_exclusion",
                "reject",
            ],
        },
        {
            "artifact": (
                "docs/portfolio/maturity-remediation/2026-05-31/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "required_fields": [
                "data_owner_name",
                "data_owner_approval_date",
                "data_owner_approved",
                "risk_owner_name",
                "risk_owner_countersign_date",
                "risk_owner_countersigned",
                "business_owner_name",
                "business_owner_acknowledgement_date",
                "business_owner_acknowledged",
                "verification_rerun_matched",
            ],
            "allowed_decisions": ["approve_scoped_exclusion"],
            "note_required_for": [],
        },
    ]
    assert data_owner["scoped_exclusion_evidence"] == {
        "status": "not_required",
        "artifact": (
            "docs/portfolio/maturity-remediation/2026-05-31/"
            "maturity_scoped_exclusion_evidence.json"
        ),
        "valid": True,
        "blockers": [],
    }
    assert data_owner["bond_missing_maturity_rows"] == []

    business_owner = owner_packets["business_owner"]
    assert business_owner["status"] in {"clean", "blocked"}
    # business_owner 归属的两个已知阻塞项名单是代码模板顺序；哪些当前仍然生效属于
    # 本机治理库状态。
    assert business_owner["blockers"] == [
        blocker
        for blocker in ("business_owner_approval", "owner_decision_intake_blocked")
        if blocker in live_score_blockers
    ]
    assert business_owner["dependency_consistency_status"] in {"consistent", "blocked"}
    assert isinstance(business_owner["csv_check_summary"]["krd_summary_row_count"], int)
    assert business_owner["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }
    assert business_owner["decision_intake_artifacts"] == [
        {
            "artifact": "docs/portfolio/portfolio-home-business-owner-approval-template.md",
            "required_fields": [
                "approval_status",
                "business_owner_name",
                "risk_owner_name",
                "approval_decision",
                "approval_date",
                "business_owner_signature",
                "risk_owner_signature",
                "krd_contract_decision",
                "maturity_data_decision",
                "risk_tensor_warning_decision",
                "evidence_scope",
            ],
            "allowed_decisions": ["approve"],
            "note_required_for": [
                "approve_nearest_bucket",
                "approve_scoped_exclusion",
                "reject",
                "request_changes",
            ],
        },
    ]
    assert isinstance(business_owner["approval_action_item_count"], int)
    assert business_owner["approval_action_item_count"] >= 0
    assert isinstance(business_owner["approval_action_items"][0]["blocker"], str)

    # owner_decision_intake_summary 是本机治理库当前 intake 状态的直接摘要；
    # 与独立重建的 intake_check 做自洽比对，而不是锁定某个时间点的具体数值
    # （行数/分数/阻塞名单都会随库状态演进而变化，但两侧必须始终一致）。
    intake_check = build_intake_check(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=2,
    )
    assert packet["owner_decision_intake_summary"] == (
        _business_owner_decision_intake_summary(intake_check)
    )

    scorecard_gate = packet["scorecard_owner_decision_intake_gate_summary"]
    assert set(scorecard_gate) == {
        "status",
        "intake_status",
        "intake_ready",
        "dependency_consistency_status",
        "dependency_csv_summary_alignment",
        "owner_input_boundary",
        "export_current_summary",
        "owner_decision_statuses",
        "blockers",
        "decision_counts",
        "decision_gap_counts",
        "note_gap_counts",
        "exact_bucket_schema_evidence",
        "nearest_bucket_approval_evidence",
        "maturity_scoped_exclusion_evidence",
    }
    assert isinstance(scorecard_gate["status"], str) and scorecard_gate["status"]
    assert isinstance(scorecard_gate["intake_status"], str) and scorecard_gate["intake_status"]
    assert isinstance(scorecard_gate["intake_ready"], bool)
    assert scorecard_gate["dependency_consistency_status"] in {"consistent", "blocked"}
    # owner_input_boundary 的策略开关与允许的前置阻塞清单是代码常量。
    assert scorecard_gate["owner_input_boundary"] == {
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
    }
    assert set(scorecard_gate["owner_decision_statuses"]) == {
        "risk_owner",
        "data_owner",
        "business_owner",
    }
    assert isinstance(scorecard_gate["blockers"], list)
    for gap_field in ("decision_counts", "decision_gap_counts", "note_gap_counts"):
        assert set(scorecard_gate[gap_field]) == {"krd", "maturity"}, gap_field

    assert packet["owner_decision_intake_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }
    assert risk_owner["owner_decision_intake_alignment_status"] == "consistent"
    assert data_owner["owner_decision_intake_alignment_status"] == "consistent"
    assert business_owner["owner_decision_intake_alignment_status"] == "consistent"
    assert packet["owner_decision_intake_command"] == (
        "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready "
        "--report-date 2026-05-31"
    )
    gate_expectations = packet["strict_gate_expectations"]
    # current_state/activation_state 反映本机治理库当前评分与激活状态，随库状态
    # 演进而变化；summary 是三选一的代码模板文案，full_score_rule 与逐条命令模板
    # （name/command/expected_when_blocked/expected_when_full_score）是代码常量。
    assert gate_expectations["current_state"] in {"blocked", "ready_for_full_score"}
    assert isinstance(gate_expectations["activation_state"], str) and gate_expectations[
        "activation_state"
    ]
    assert gate_expectations["summary"] in {
        "Current strict gates: expected to exit 0; full closure evidence is ready.",
        (
            "Current strict gates: expected to fail until rerun evidence and "
            "business-owner activation boundary are both clean."
        ),
        (
            "Current strict gates: expected to fail until owner decisions, "
            "maturity remediation/exclusion, and business approval are captured."
        ),
    }
    assert gate_expectations["full_score_rule"] == (
        "After owner updates: each strict gate below must exit 0 before "
        "`/portfolio` can claim full closure."
    )
    expected_command_templates = {
        "owner_decision_intake_check_strict": (
            "python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready",
        ),
        "business_owner_approval_packet_strict": (
            "python scripts/portfolio_home_business_owner_approval_packet.py --report-date 2026-05-31 --limit 3 --require-ready",
        ),
        "scorecard_strict": (
            "python scripts/portfolio_home_closure_scorecard.py --report-date 2026-05-31 --limit 3 --require-full-score",
        ),
    }
    assert [command["name"] for command in gate_expectations["commands"]] == list(
        expected_command_templates
    )
    for command in gate_expectations["commands"]:
        (expected_command,) = expected_command_templates[command["name"]]
        assert command["command"] == expected_command
        assert command["expected_when_blocked"] == "exit_nonzero"
        assert command["expected_when_full_score"] == "exit_0"
        assert command["current_expected_exit"] in {"exit_nonzero", "exit_0"}

    risk_warning_status = packet["risk_warning_clean_status"]
    assert risk_warning_status["status"] in {"clean", "blocked"}
    assert isinstance(risk_warning_status["valid"], bool)
    assert risk_warning_status["valid"] is (risk_warning_status["status"] == "clean")
    assert risk_warning_status["decision_status"] in {"clean", "blocked"}
    assert risk_warning_status["evidence_scope"] == RISK_WARNING_EVIDENCE_SCOPE
    # decision_blockers 是风险预警证据当前实际生效的决策阻塞子集（随风险张量重算
    # 与库状态演进而变化）；risk_tensor_quality_warning 是本场景必现项。
    assert "risk_tensor_quality_warning" in risk_warning_status["decision_blockers"]
    assert set(risk_warning_status["decision_blockers"]).issubset(
        {"risk_tensor_quality_warning", "risk_tensor_warning_mismatch"}
    )
    _assert_warning_resolution_matrix_structure(risk_warning_status["warning_resolution_matrix"])
    risk_warning_delta = risk_warning_status["duration_exclusion_delta_detail"]
    _assert_duration_exclusion_delta_detail_structure(risk_warning_delta)

    approval_boundary = packet["business_owner_approval_boundary"]
    for boundary_field in (
        "template_approval_captured",
        "formal_authorization_allowed",
        "governance_write_allowed",
        "page_execution_proven",
        "full_score_closure_ready",
        "activation_ready",
    ):
        assert isinstance(approval_boundary[boundary_field], bool), boundary_field
    assert approval_boundary["status"] in {"pending_owner_input", "activated"}
    assert approval_boundary["activation_ready"] is (approval_boundary["status"] == "activated")
    # blockers 名单是当前实际未满足的激活前置条件子集；只锁定它是完整前置条件
    # 目录 APPROVAL_BOUNDARY_BLOCKER_ORDER 的合法子序列（成员+相对顺序不变式）。
    assert set(approval_boundary["blockers"]).issubset(set(APPROVAL_BOUNDARY_BLOCKER_ORDER))
    assert approval_boundary["blockers"] == [
        blocker
        for blocker in APPROVAL_BOUNDARY_BLOCKER_ORDER
        if blocker in approval_boundary["blockers"]
    ]
    assert business_owner["activation_guard"] == _activation_guard(
        approval_boundary["activation_ready"]
    )
    assert business_owner["business_owner_approval_boundary"] == packet[
        "business_owner_approval_boundary"
    ]


def test_portfolio_home_owner_action_packet_cli_require_clean_fails_current_state() -> None:
    returncode, payload = _run_packet("--limit", "1", "--require-clean")

    assert returncode == 1
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["full_score_ready"] is False
    assert payload["assignment_coverage"]["status"] == "clean"
    assert payload["owner_packets"]["risk_owner"]["status"] == "blocked"


def test_portfolio_home_owner_action_packet_rejects_negative_limit() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home owner action packet limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_owner_action_packet_build_rejects_negative_limit() -> None:
    try:
        build_packet(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            limit=-1,
        )
    except ValueError as exc:
        assert str(exc) == "Portfolio-home owner action packet limit must be non-negative: -1"
    else:
        raise AssertionError("negative owner action packet limit should be rejected")


def test_portfolio_home_owner_action_packet_strict_gate_requires_score_blocker_action_coverage() -> None:
    empty_assignment_coverage = {
        "status": "clean",
        "score_blockers": [],
        "assigned_blockers": [],
        "unassigned_blockers": [],
        "duplicate_assigned_blockers": [],
        "unexpected_assigned_blockers": [],
    }
    empty_action_coverage = {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": [],
    }
    empty_matrix_coverage = {
        "status": "clean",
        "expected_blockers": [],
        "covered_blockers": [],
        "missing_blockers": [],
        "unexpected_blockers": [],
        "duplicate_blockers": [],
    }

    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "score_blockers": ["new_unmapped_blocker"],
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "assignment_coverage": {
                    "status": "clean",
                    "score_blockers": ["new_unmapped_blocker"],
                    "assigned_blockers": ["new_unmapped_blocker"],
                    "unassigned_blockers": [],
                    "duplicate_assigned_blockers": [],
                    "unexpected_assigned_blockers": [],
                },
                "score_blocker_action_coverage": {
                    "status": "blocked",
                    "unassigned_blockers": ["new_unmapped_blocker"],
                },
                "blocker_closure_matrix_coverage": {
                    "status": "clean",
                    "expected_blockers": ["new_unmapped_blocker"],
                    "covered_blockers": ["new_unmapped_blocker"],
                    "missing_blockers": [],
                    "unexpected_blockers": [],
                    "duplicate_blockers": [],
                },
                "business_owner_approval_boundary": {"activation_ready": True},
            }
        )
        is False
    )
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "score_blockers": ["new_unmapped_blocker"],
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "assignment_coverage": {
                    "status": "clean",
                    "score_blockers": ["new_unmapped_blocker"],
                    "assigned_blockers": ["new_unmapped_blocker"],
                    "unassigned_blockers": [],
                    "duplicate_assigned_blockers": [],
                    "unexpected_assigned_blockers": [],
                },
                "score_blocker_action_coverage": {
                    "status": "clean",
                    "blockers": [],
                    "unassigned_blockers": [],
                    "covered_blockers": ["new_unmapped_blocker"],
                },
                "blocker_closure_matrix_coverage": {
                    "status": "blocked",
                    "missing_blockers": ["new_unmapped_blocker"],
                },
                "business_owner_approval_boundary": {"activation_ready": True},
            }
        )
        is False
    )
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "score_blockers": ["new_unmapped_blocker"],
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "assignment_coverage": {
                    "status": "clean",
                    "score_blockers": ["new_unmapped_blocker"],
                    "assigned_blockers": ["new_unmapped_blocker"],
                    "unassigned_blockers": [],
                    "duplicate_assigned_blockers": [],
                    "unexpected_assigned_blockers": [],
                },
                "score_blocker_action_coverage": {
                    "status": "clean",
                    "blockers": [],
                    "unassigned_blockers": [],
                    "covered_blockers": [],
                },
                "blocker_closure_matrix_coverage": {
                    "status": "clean",
                    "expected_blockers": ["new_unmapped_blocker"],
                    "covered_blockers": ["new_unmapped_blocker"],
                    "missing_blockers": [],
                    "unexpected_blockers": [],
                    "duplicate_blockers": [],
                },
                "business_owner_approval_boundary": {"activation_ready": True},
            }
        )
        is False
    )
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "full_score_ready": False,
                "score_status": "blocked",
                "score_blockers": [],
                "assignment_coverage": empty_assignment_coverage,
                "score_blocker_action_coverage": empty_action_coverage,
                "blocker_closure_matrix_coverage": empty_matrix_coverage,
                "business_owner_approval_boundary": {
                    "template_approval_captured": True,
                    "formal_authorization_allowed": True,
                    "governance_write_allowed": True,
                    "page_execution_proven": True,
                    "full_score_closure_ready": True,
                    "activation_ready": True,
                    "status": "activated",
                    "blockers": [],
                },
            }
        )
        is False
    )
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "score_blockers": [],
                "assignment_coverage": empty_assignment_coverage,
                "score_blocker_action_coverage": empty_action_coverage,
                "blocker_closure_matrix_coverage": empty_matrix_coverage,
                "business_owner_approval_boundary": {"activation_ready": False},
            }
        )
        is False
    )
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "score_blockers": [],
                "assignment_coverage": empty_assignment_coverage,
                "score_blocker_action_coverage": empty_action_coverage,
                "blocker_closure_matrix_coverage": empty_matrix_coverage,
                "business_owner_approval_boundary": {
                    "template_approval_captured": True,
                    "formal_authorization_allowed": False,
                    "governance_write_allowed": True,
                    "page_execution_proven": True,
                    "full_score_closure_ready": True,
                    "activation_ready": True,
                    "status": "activated",
                    "blockers": [],
                },
            }
        )
        is False
    )
    assert (
        _strict_gate_clean(
            {
                "handoff_status": "ready_for_full_score",
                "full_score_ready": True,
                "score_status": "ready_for_full_score",
                "score_blockers": [],
                "assignment_coverage": empty_assignment_coverage,
                "score_blocker_action_coverage": empty_action_coverage,
                "blocker_closure_matrix_coverage": empty_matrix_coverage,
                "business_owner_approval_boundary": {
                    "template_approval_captured": True,
                    "formal_authorization_allowed": True,
                    "governance_write_allowed": True,
                    "page_execution_proven": True,
                    "full_score_closure_ready": True,
                    "activation_ready": True,
                    "status": "activated",
                    "blockers": [],
                },
            }
        )
        is True
    )


def test_portfolio_home_owner_action_packet_uses_supplied_docs_root_for_intake(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="approve_nearest_bucket",
            maturity_decision="approve_scoped_exclusion",
            decision_notes=(
                "Risk owner accepts nearest-bucket mapping; data owner signs scoped exclusion for "
                "current candidate review only."
            ),
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "approve_nearest_bucket",
            "decision_notes": "Accepted for current candidate review only.",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "approve_nearest_bucket",
            "decision_notes": "Accepted for current candidate review only.",
        },
    )

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _write_nearest_bucket_approval_evidence(docs_root)
    _write_maturity_scoped_exclusion_evidence(docs_root)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"] == {
        "intake_status": "ready_for_intake",
        "intake_ready": True,
        "dependency_consistency_status": "consistent",
        "dependency_csv_summary_alignment": {
            "status": "consistent",
            "blockers": [],
        },
        "csv_check_summary": {
            "krd_summary_row_count": 3,
            "krd_detail_row_count": 500,
            "krd_owner_decision_fields_blank": False,
            "bond_missing_maturity_row_count": 0,
            "tyw_liability_missing_maturity_row_count": 1455,
            "maturity_owner_fields_blank": False,
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
            "pre_intake_dependency_blockers": [
                "krd_contract_decision_manifest_owner_decision_fields_not_blank",
                "maturity_remediation_manifest_owner_fields_not_blank",
            ],
            "active_dependency_blockers": [],
            "active_export_current_blockers": [],
        },
        "export_current_summary": _expected_export_current_summary(),
        "owner_decision_statuses": {
            "risk_owner": "ready",
            "data_owner": "ready",
            "business_owner": "ready",
        },
        "owner_decision_blockers": [],
        "decision_counts": {
            "krd": {"approve_nearest_bucket": 503},
            "maturity": {"approve_scoped_exclusion": 1455},
        },
        "decision_gap_counts": {
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
        "nearest_bucket_approval_evidence": {
            "status": "valid",
            "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/nearest_bucket_approval_evidence.json",
            "valid": True,
            "blockers": [],
        },
        "maturity_scoped_exclusion_evidence": {
            "status": "valid",
            "artifact": (
                "docs/portfolio/maturity-remediation/2026-05-31/"
                "maturity_scoped_exclusion_evidence.json"
            ),
            "valid": True,
            "blockers": [],
        },
        "decision_alignment": {
            "status": "consistent",
            "blockers": [],
            "business_template_decisions": {
                "krd_contract_decision": "approve_nearest_bucket",
                "maturity_data_decision": "approve_scoped_exclusion",
            },
            "owner_csv_decisions": {
                "krd": ["approve_nearest_bucket"],
                "maturity": ["approve_scoped_exclusion"],
            },
        },
    }


def test_portfolio_home_owner_action_packet_assigns_rejected_owner_decisions(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="reject",
            maturity_decision="reject",
            decision_notes="Risk owner and data owner reject the current closure boundary.",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "reject",
            "decision_notes": "Rejected current nearest-bucket KRD contract.",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "reject",
            "decision_notes": "Rejected current nearest-bucket KRD contract.",
        },
    )

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "reject",
            "owner_comment": "Rejected current maturity remediation boundary.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "reject",
            "owner_comment": "Rejected current maturity remediation boundary.",
        },
    )

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"]["owner_decision_blockers"] == [
        "krd_owner_decision_rejected",
        "maturity_owner_decision_rejected",
    ]
    assert packet["owner_packets"]["risk_owner"]["blockers"] == [
        "risk_tensor_quality_warning",
        "krd_contract_decision_required",
        "krd_owner_decision_rejected",
    ]
    assert packet["owner_packets"]["data_owner"]["blockers"] == [
        "tyw_liability_maturity_date_remediation_required",
        "bond_matured_outstanding_reconciliation_required",
        "maturity_owner_decision_rejected",
    ]


def test_portfolio_home_owner_action_packet_surfaces_krd_note_gap_counts(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="approve_nearest_bucket",
            maturity_decision="approve_scoped_exclusion",
            decision_notes=(
                "Risk owner accepts nearest-bucket mapping; data owner signs scoped exclusion for "
                "current candidate review only."
            ),
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "approve_nearest_bucket",
            "decision_notes": "",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "approve_nearest_bucket",
            "decision_notes": "",
        },
    )

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _write_nearest_bucket_approval_evidence(docs_root)
    _write_maturity_scoped_exclusion_evidence(docs_root)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"]["owner_decision_blockers"] == [
        "krd_owner_decision_notes_missing",
    ]
    assert packet["owner_decision_intake_summary"]["note_gap_counts"] == {
        "krd": {
            "risk_owner_decision": "approve_nearest_bucket",
            "missing_note_rows": 503,
        },
        "maturity": {},
    }


def test_portfolio_home_owner_action_packet_surfaces_maturity_comment_gap_counts(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Data owner signs scoped exclusion for current candidate review only.",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
            "decision_notes": "Exact-bucket schema required before full closure.",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
            "decision_notes": "Exact-bucket schema required before full closure.",
        },
    )
    _write_exact_bucket_schema_evidence(docs_root)

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "",
        },
    )
    _write_maturity_scoped_exclusion_evidence(docs_root)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"]["owner_decision_blockers"] == [
        "maturity_owner_comment_missing",
    ]
    assert packet["owner_decision_intake_summary"]["note_gap_counts"] == {
        "krd": {},
        "maturity": {
            "owner_decision": "approve_scoped_exclusion",
            "missing_comment_rows": 1455,
        },
    }


def test_portfolio_home_owner_action_packet_surfaces_missing_exact_bucket_schema_evidence(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Data owner signs scoped exclusion for current candidate review only.",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / "2026-05-31"
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
            "decision_notes": "Exact-bucket schema required before full closure.",
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": "require_exact_bucket_schema",
            "decision_notes": "Exact-bucket schema required before full closure.",
        },
    )

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / "2026-05-31"
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "approve_scoped_exclusion",
            "owner_comment": "Signed exclusion for current candidate review only.",
        },
    )
    _write_maturity_scoped_exclusion_evidence(docs_root)

    packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["owner_decision_intake_summary"]["owner_decision_blockers"] == [
        "krd_exact_bucket_schema_evidence_missing",
    ]
    assert packet["owner_decision_intake_summary"]["exact_bucket_schema_evidence"] == {
        "status": "missing",
        "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
        "valid": False,
        "blockers": ["krd_exact_bucket_schema_evidence_missing"],
    }
    assert packet["owner_packets"]["risk_owner"]["exact_bucket_schema_evidence"] == {
        "status": "missing",
        "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
        "valid": False,
        "blockers": ["krd_exact_bucket_schema_evidence_missing"],
    }


def test_portfolio_home_owner_action_packet_strict_gate_expectations_follow_activation_boundary(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    template = tmp_path / "portfolio-approval.md"
    docs_root = tmp_path / "docs"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)
    template.write_text(_approved_template_text(), encoding="utf-8")
    _write_clean_fixture_manifests(docs_root)
    _write_clean_handoff_snapshot(docs_root)

    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        template_path=template,
        limit=1,
        docs_root=docs_root,
    )

    assert packet["handoff_status"] == "ready_for_full_score"
    assert packet["business_owner_approval_boundary"] == {
        "template_approval_captured": True,
        "formal_authorization_allowed": False,
        "governance_write_allowed": False,
        "page_execution_proven": False,
        "full_score_closure_ready": False,
        "activation_ready": False,
        "status": "captured_but_not_activated",
        "blockers": [
            "rerun_evidence_not_valid",
            "evidence_dependency_unavailable",
        ],
    }
    assert packet["owner_packets"]["business_owner"]["business_owner_approval_boundary"] == packet[
        "business_owner_approval_boundary"
    ]
    expectations = packet["strict_gate_expectations"]
    assert expectations["current_state"] == "ready_for_full_score"
    assert expectations["activation_state"] == "captured_but_not_activated"
    assert expectations["summary"] == (
        "Current strict gates: expected to fail until rerun evidence and "
        "business-owner activation boundary are both clean."
    )
    assert expectations["commands"] == [
        {
            "name": "owner_decision_intake_check_strict",
            "command": "python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready",
            "current_expected_exit": "exit_0",
            "expected_when_blocked": "exit_nonzero",
            "expected_when_full_score": "exit_0",
        },
        {
            "name": "business_owner_approval_packet_strict",
            "command": "python scripts/portfolio_home_business_owner_approval_packet.py --report-date 2026-05-31 --limit 3 --require-ready",
            "current_expected_exit": "exit_nonzero",
            "expected_when_blocked": "exit_nonzero",
            "expected_when_full_score": "exit_0",
        },
        {
            "name": "scorecard_strict",
            "command": "python scripts/portfolio_home_closure_scorecard.py --report-date 2026-05-31 --limit 3 --require-full-score",
            "current_expected_exit": "exit_0",
            "expected_when_blocked": "exit_nonzero",
            "expected_when_full_score": "exit_0",
        },
    ]


def test_portfolio_home_owner_action_packet_uses_report_date_for_approval_status(
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

    approval_boundary = packet["business_owner_approval_boundary"]
    assert approval_boundary["template_approval_captured"] is False
    assert approval_boundary["status"] == "pending_owner_input"
    assert "business_owner_approval_not_captured" in approval_boundary["blockers"]
    business_owner_packet = packet["owner_packets"]["business_owner"]
    assert business_owner_packet["business_owner_approval_boundary"] == approval_boundary
    assert business_owner_packet["approval_action_items"][0]["blocker"] == "approval_date"
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
    activation_commands = business_owner_packet["activation_guard"]["required_commands"]
    assert len(activation_commands) == 10
    assert all("--report-date 2026-06-06" in command for command in activation_commands)
    assert packet["owner_packets"]["risk_owner"]["risk_warning_evidence_command"] == (
        "python scripts/portfolio_home_risk_warning_consistency.py "
        "--report-date 2026-06-06 --require-clean"
    )
