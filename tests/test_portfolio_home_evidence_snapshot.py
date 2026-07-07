from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.portfolio_home_evidence_snapshot import (
    build_snapshot,
    owner_handoff_completeness_alignment,
    snapshot_sha256,
    owner_decision_intake_alignment,
)
from scripts.portfolio_home_business_owner_approval_packet import build_packet
from scripts.portfolio_home_business_owner_approval_packet import (
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
)

from tests.test_portfolio_home_business_owner_approval_packet import (
    CURRENT_SCORE_BLOCKERS,
    RISK_WARNING_EVIDENCE_SCOPE,
    _expected_current_duration_exclusion_delta_detail,
    _expected_current_risk_tensor_rematerialization_preview,
    _expected_current_warning_resolution_matrix,
    _expected_not_required_nearest_bucket_approval_evidence,
)
from scripts.portfolio_home_closure_scorecard import VERIFICATION_COMMANDS
from scripts.verify_portfolio_home_scorecard_commands import RUNNER_COMMAND_NAME

pytestmark = pytest.mark.governance_meta


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_evidence_snapshot.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"


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


def _run_snapshot(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_evidence_snapshot_summarizes_current_blocked_state() -> None:
    snapshot = build_snapshot(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        scorecard_limit=1,
        verifier_limit=1,
    )

    assert snapshot["snapshot_kind"] == "portfolio_home_closure_evidence"
    assert snapshot["current_score"] == "99.86 / 100"
    assert snapshot["remaining_gap"] == "0.14"
    assert snapshot["score_status"] == "blocked"
    assert snapshot["full_score_ready"] is False
    assert "risk_tensor_quality_warning" in snapshot["score_blockers"]
    assert snapshot["gate_summary"]["risk_tensor_quality_flag"] == "warning"
    assert snapshot["gate_summary"]["bond_missing_maturity_rows"] == 114
    assert snapshot["gate_summary"]["owner_decision_intake_status"] == "pending"
    assert snapshot["gate_summary"]["owner_decision_intake_ready"] is False
    assert snapshot["gate_summary"]["owner_decision_intake_blockers"] == [
        "krd_owner_decision_missing",
        "maturity_owner_decision_missing",
        "business_owner_approval_missing",
    ]
    assert snapshot["gate_summary"]["owner_decision_intake_alignment_status"] == "consistent"
    assert snapshot["gate_summary"]["owner_decision_intake_alignment_blockers"] == []
    assert snapshot["gate_summary"]["score_blocker_action_coverage_status"] == "clean"
    assert snapshot["gate_summary"]["score_blocker_action_coverage_blockers"] == []
    assert snapshot["gate_summary"]["score_blocker_action_coverage_unassigned_blockers"] == []
    assert snapshot["gate_summary"]["approval_dependency_consistency_status"] == "consistent"
    assert snapshot["gate_summary"]["approval_dependency_consistency_blockers"] == []
    assert snapshot["gate_summary"]["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }
    assert snapshot["gate_summary"]["owner_handoff_completeness_status"] == "clean"
    assert snapshot["gate_summary"]["owner_handoff_completeness_ready"] is True
    assert snapshot["gate_summary"]["owner_handoff_completeness_blockers"] == []
    assert snapshot["closure_artifact_presence_summary"] == {
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
    handoff_summary = snapshot["handoff_completeness_summary"]
    assert handoff_summary["status"] == "clean"
    assert handoff_summary["handoff_ready"] is True
    assert handoff_summary["blockers"] == []
    assert handoff_summary["summary_current_status"]["status"] == "current"
    assert handoff_summary["summary_current_status"]["current"] is True
    assert handoff_summary["handoff_current_status"]["status"] == "current"
    assert handoff_summary["owner_route_coverage"] == {
        "status": "clean",
        "required_owners": ["risk_owner", "data_owner", "business_owner"],
        "present_owners": ["risk_owner", "data_owner", "business_owner"],
        "missing_owners": [],
        "unexpected_owners": [],
        "duplicate_owners": [],
    }
    assert handoff_summary["route_statuses"] == {
        "risk_owner": "clean",
        "data_owner": "clean",
        "business_owner": "clean",
    }
    assert handoff_summary["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "fills_owner_decisions": False,
        "captures_business_owner_approval": False,
        "proves_full_score_closure": False,
        "certification_effect": "none",
    }
    assert snapshot["owner_handoff_completeness_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": [
            "owner_handoff_completeness_status",
            "owner_handoff_completeness_ready",
            "owner_handoff_completeness_blockers",
        ],
    }
    assert snapshot["verification_scope"] == {
        "scope": "limited",
        "embedded_result_count": 1,
        "total_verification_command_count": len(
            [item for item in VERIFICATION_COMMANDS if item["name"] != RUNNER_COMMAND_NAME],
        ),
        "embedded_result_count_matches_report": True,
        "all_commands_embedded": False,
        "full_verification_command": (
            "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched"
        ),
        "requires_full_verification_for_full_score": True,
        "proves_full_score_closure": False,
        "certification_effect": "limited_verifier_sample_only",
    }
    approval_packet = snapshot["business_owner_approval_packet_summary"]
    source_approval_packet = build_packet(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        limit=1,
    )
    assert approval_packet == {
        "packet_status": "pending",
        "activation_ready": False,
        "approval_action_item_count": 19,
        "approval_field_status": {
            "approval_date": "missing",
            "verification_commands_rerun": "pending",
            "evidence_scope_captures_business_owner_approval": "valid",
        },
        "business_owner_approval_boundary": {
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
        },
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
        "rerun_evidence_status": {
            "status": "valid",
            "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
            "valid": True,
            "blockers": [],
        },
        "dependency_consistency_status": "consistent",
        "dependency_consistency_blockers": [],
        "score_blocker_action_coverage": {
            "status": "clean",
            "blockers": [],
            "unassigned_blockers": [],
            "covered_blockers": CURRENT_SCORE_BLOCKERS,
        },
        "activation_guard": source_approval_packet["activation_guard"],
        "owner_decision_intake_alignment": {
            "status": "consistent",
            "blockers": [],
            "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
        },
        "manifest_consistency_statuses": {
            "krd_contract_decision_manifest": "consistent",
            "maturity_remediation_manifest": "consistent",
        },
        "generated_owner_fields_boundaries": {
            "krd_contract_decision_manifest": True,
            "maturity_remediation_manifest": True,
        },
        "owner_summary_paths": {
            "krd_contract_decision_owner_summary": "docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md",
            "maturity_remediation_owner_summary": "docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md",
        },
        "csv_check_summary": {
            "krd_summary_row_count": 3,
            "krd_detail_row_count": 500,
            "krd_owner_decision_fields_blank": True,
            "bond_missing_maturity_row_count": 114,
            "tyw_liability_missing_maturity_row_count": 1455,
            "maturity_owner_fields_blank": True,
        },
    }
    assert approval_packet["generated_owner_fields_boundaries"] == source_approval_packet[
        "generated_owner_fields_boundaries"
    ]
    assert snapshot["owner_decision_intake_summary"] == {
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
            "bond_missing_maturity_row_count": 114,
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
    assert snapshot["scorecard_owner_decision_intake_gate_summary"] == {
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
    assert snapshot["owner_decision_intake_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }
    assert snapshot["verification_report"]["verification_status"] == "matched_expected_blocked_state"


def test_owner_decision_intake_alignment_blocks_key_field_mismatch() -> None:
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
        "maturity_scoped_exclusion_evidence": {"status": "not_required"},
    }
    scorecard_gate = {
        **direct,
        "intake_ready": True,
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": False},
        "decision_counts": {"krd": {"approve_nearest_bucket": 1}, "maturity": {}},
        "decision_gap_counts": {"krd": {"missing_decision_rows": 0}},
    }

    assert owner_decision_intake_alignment(direct, scorecard_gate) == {
        "status": "blocked",
        "blockers": [
            "owner_decision_intake_alignment_intake_ready_mismatch",
            "owner_decision_intake_alignment_owner_input_boundary_mismatch",
            "owner_decision_intake_alignment_decision_counts_mismatch",
            "owner_decision_intake_alignment_decision_gap_counts_mismatch",
        ],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }


def test_owner_handoff_completeness_alignment_blocks_summary_mismatch() -> None:
    gate_summary = {
        "owner_handoff_completeness_status": "clean",
        "owner_handoff_completeness_ready": True,
        "owner_handoff_completeness_blockers": [],
    }
    handoff_summary = {
        "status": "blocked",
        "handoff_ready": False,
        "blockers": ["owner_handoff_packet_not_current"],
    }

    assert owner_handoff_completeness_alignment(gate_summary, handoff_summary) == {
        "status": "blocked",
        "blockers": [
            "owner_handoff_completeness_alignment_owner_handoff_completeness_status_mismatch",
            "owner_handoff_completeness_alignment_owner_handoff_completeness_ready_mismatch",
            "owner_handoff_completeness_alignment_owner_handoff_completeness_blockers_mismatch",
        ],
        "compared_fields": [
            "owner_handoff_completeness_status",
            "owner_handoff_completeness_ready",
            "owner_handoff_completeness_blockers",
        ],
    }


def test_portfolio_home_evidence_snapshot_cli_require_verifier_matched() -> None:
    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--require-verifier-matched",
    )

    assert returncode == 0
    assert payload["verification_report"]["all_matched_expected_exit"] is True
    assert payload["gate_summary"]["business_owner_approval_status"] == "pending"
    assert payload["business_owner_approval_packet_summary"]["activation_ready"] is False
    assert (
        payload["business_owner_approval_packet_summary"]["dependency_consistency_status"]
        == "consistent"
    )
    assert payload["owner_decision_intake_summary"]["intake_ready"] is False


def test_portfolio_home_evidence_snapshot_rejects_negative_limits() -> None:
    try:
        build_snapshot(
            duckdb_path=DUCKDB,
            report_date="2026-05-31",
            template_path=TEMPLATE,
            scorecard_limit=-1,
            verifier_limit=1,
        )
    except ValueError as error:
        assert str(error) == "Portfolio-home scorecard limit must be non-negative: -1"
    else:
        raise AssertionError("negative scorecard snapshot limit was accepted")

    for args, message in (
        (
            ["--scorecard-limit", "-1"],
            "Portfolio-home scorecard limit must be non-negative: -1",
        ),
        (
            ["--verifier-limit", "-1"],
            "Portfolio-home verifier limit must be non-negative: -1",
        ),
    ):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
        )

        assert completed.returncode == 2
        assert message in completed.stderr


def test_portfolio_home_evidence_snapshot_cli_writes_output_artifact(tmp_path: Path) -> None:
    output = tmp_path / "portfolio-home-evidence-snapshot.json"

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
    )

    assert returncode == 0
    assert output.exists()
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact == payload
    assert artifact["snapshot_kind"] == "portfolio_home_closure_evidence"
    assert artifact["report_date"] == "2026-05-31"
    assert artifact["verification_report"]["all_matched_expected_exit"] is True


def test_portfolio_home_evidence_snapshot_cli_rewrites_self_referential_artifact_once(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    output = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": "2026-05-31",
                "scorecard_owner_decision_intake_gate_summary": {},
                "owner_decision_intake_alignment": {
                    "status": "consistent",
                    "blockers": [],
                    "compared_fields": [
                        "intake_status",
                        "intake_ready",
                        "dependency_consistency_status",
                        "owner_decision_statuses",
                        "decision_gap_counts",
                        "note_gap_counts",
                        "exact_bucket_schema_evidence",
                    ],
                },
                "verification_report": {
                    "verification_status": "matched_expected_blocked_state",
                    "all_matched_expected_exit": True,
                    "all_matched_expected_when_blocked": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--docs-root",
        str(docs_dir),
        "--output",
        str(output),
    )

    assert returncode == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact == payload
    rerun_status = artifact["business_owner_approval_packet_summary"]["rerun_evidence_status"]
    assert rerun_status == {
        "status": "valid",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": True,
        "blockers": [],
    }


def test_portfolio_home_evidence_snapshot_cli_stabilizes_self_referential_handoff_alignment_once(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    output = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": "2026-05-31",
                "handoff_completeness_summary": {
                    "status": "blocked",
                    "handoff_ready": False,
                    "blockers": ["owner_handoff_packet_not_current"],
                },
                "owner_handoff_completeness_alignment": {
                    "status": "blocked",
                    "blockers": [
                        "owner_handoff_completeness_alignment_owner_handoff_completeness_status_mismatch",
                    ],
                    "compared_fields": [
                        "owner_handoff_completeness_status",
                        "owner_handoff_completeness_ready",
                        "owner_handoff_completeness_blockers",
                    ],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--docs-root",
        str(docs_dir),
        "--output",
        str(output),
    )

    assert returncode == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact == payload
    handoff_summary = artifact["handoff_completeness_summary"]
    gate_summary = artifact["gate_summary"]
    assert artifact["owner_handoff_completeness_alignment"]["status"] == "consistent"
    assert gate_summary["owner_handoff_completeness_status"] == handoff_summary["status"]
    assert gate_summary["owner_handoff_completeness_ready"] == handoff_summary["handoff_ready"]
    assert gate_summary["owner_handoff_completeness_blockers"] == handoff_summary["blockers"]

    check_returncode, check_payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--docs-root",
        str(docs_dir),
        "--output",
        str(output),
        "--check-current",
    )

    assert check_returncode == 0
    assert check_payload["status"] == "current"


def test_portfolio_home_evidence_snapshot_cli_check_current_passes_matching_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
    )
    assert returncode == 0

    check_returncode, check_payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
        "--check-current",
    )

    assert check_returncode == 0
    assert check_payload == {
        "artifact": str(output),
        "status": "current",
        "expected_sha256": snapshot_sha256(payload),
        "actual_sha256": snapshot_sha256(payload),
    }


def test_portfolio_home_evidence_snapshot_cli_check_current_fails_stale_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "portfolio-home-evidence-snapshot.json"
    output.write_text('{"snapshot_kind":"stale"}', encoding="utf-8")

    returncode, payload = _run_snapshot(
        "--scorecard-limit",
        "1",
        "--verifier-limit",
        "1",
        "--output",
        str(output),
        "--check-current",
    )

    assert returncode == 1
    assert payload["artifact"] == str(output)
    assert payload["status"] == "stale"
    assert payload["expected_sha256"] != payload["actual_sha256"]


def test_portfolio_home_evidence_snapshot_uses_supplied_docs_root_for_approval_packet(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")
    artifact = docs_dir / "portfolio" / "portfolio-home-evidence-snapshot.json"
    if artifact.exists():
        artifact.unlink()

    snapshot = build_snapshot(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        scorecard_limit=1,
        verifier_limit=1,
        docs_root=docs_dir,
    )

    assert snapshot["business_owner_approval_packet_summary"]["rerun_evidence_status"] == {
        "status": "missing",
        "artifact": "docs/portfolio/portfolio-home-evidence-snapshot.json",
        "valid": False,
        "blockers": ["rerun_evidence_artifact_missing"],
    }


def test_portfolio_home_evidence_snapshot_passes_docs_root_to_embedded_verifier(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")

    snapshot = build_snapshot(
        duckdb_path=DUCKDB,
        report_date="2026-05-31",
        template_path=TEMPLATE,
        scorecard_limit=1,
        verifier_limit=17,
        docs_root=docs_dir,
    )

    scorecard_result = next(
        item
        for item in snapshot["verification_report"]["results"]
        if item["name"] == "scorecard"
    )
    assert scorecard_result["argv"] == [
        sys.executable,
        "scripts/portfolio_home_closure_scorecard.py",
        "--limit",
        "3",
        "--docs-root",
        str(docs_dir),
    ]
