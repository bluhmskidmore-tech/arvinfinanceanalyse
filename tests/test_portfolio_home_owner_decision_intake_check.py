from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from tests.test_portfolio_home_business_owner_approval_status import _filled_template_text
from tests.test_portfolio_home_closure_scorecard import (
    _create_schema,
    _insert_clean_data,
    _write_clean_fixture_manifests,
)

from scripts.portfolio_home_owner_decision_intake_check import build_intake_check


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_owner_decision_intake_check.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
REPORT_DATE = "2026-05-31"


def _expected_owner_input_boundary(
    *,
    pre_intake_dependency_blockers: list[str] | None = None,
    active_export_current_blockers: list[str] | None = None,
) -> dict[str, object]:
    return {
        "generated_export_owner_fields_must_be_blank": True,
        "filled_owner_fields_are_owner_input_only": True,
        "generated_export_system_fields_must_be_current": True,
        "allowed_pre_intake_dependency_blockers": [
            "krd_contract_decision_manifest_owner_decision_fields_not_blank",
            "maturity_remediation_manifest_owner_fields_not_blank",
        ],
        "pre_intake_dependency_blockers": pre_intake_dependency_blockers or [],
        "active_dependency_blockers": [],
        "active_export_current_blockers": active_export_current_blockers or [],
    }


def _run_check(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _rewrite_csv(path: Path, transform) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(transform(dict(row)))


def _fill_krd_decisions(docs_root: Path, decision: str, notes: str = "") -> None:
    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE
    _rewrite_csv(
        krd_dir / "krd_remap_summary.csv",
        lambda row: {
            **row,
            "risk_owner_decision": decision,
            "decision_notes": notes,
        },
    )
    _rewrite_csv(
        krd_dir / "krd_remap_detail.csv",
        lambda row: {
            **row,
            "risk_owner_decision": decision,
            "decision_notes": notes,
        },
    )


def _fill_maturity_decisions(
    docs_root: Path,
    decision: str,
    *,
    proposed_maturity_date: str = "",
    comment: str = "",
) -> None:
    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": decision,
            "proposed_maturity_date": proposed_maturity_date,
            "owner_comment": comment,
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": decision,
            "proposed_maturity_date": proposed_maturity_date,
            "owner_comment": comment,
        },
    )


def _write_exact_bucket_schema_evidence(docs_root: Path) -> None:
    evidence_path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "exact_bucket_schema_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_exact_bucket_schema_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "decision": "require_exact_bucket_schema",
                "metric_contract_owner_name": "Metric Contract Owner",
                "metric_contract_update_date": REPORT_DATE,
                "metric_contract_updated": True,
                "api_schema_owner_name": "API Schema Owner",
                "api_schema_update_date": REPORT_DATE,
                "api_schema_updated": True,
                "risk_tensor_owner_name": "Risk Owner",
                "risk_tensor_rematerialization_date": REPORT_DATE,
                "risk_tensor_rematerialized": True,
                "verifier_name": "Verifier",
                "verification_rerun_date": REPORT_DATE,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_nearest_bucket_approval_evidence(docs_root: Path) -> None:
    evidence_path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "nearest_bucket_approval_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_nearest_bucket_approval_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "decision": "approve_nearest_bucket",
                "mapped_tenor_buckets": ["20Y", "2Y", "6M"],
                "nonzero_dv01_rows": 500,
                "dv01_sum": "33365026.29780176",
                "risk_owner_name": "Risk Owner",
                "risk_owner_approval_date": REPORT_DATE,
                "risk_owner_approved": True,
                "business_owner_name": "Portfolio Owner",
                "business_owner_acknowledgement_date": REPORT_DATE,
                "business_owner_acknowledged": True,
                "metric_contract_decision_recorded": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_maturity_scoped_exclusion_evidence(docs_root: Path) -> None:
    evidence_path = (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / REPORT_DATE
        / "maturity_scoped_exclusion_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_maturity_scoped_exclusion_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "decision": "approve_scoped_exclusion",
                "bond_missing_maturity_rows": 0,
                "tyw_liability_missing_maturity_rows": 1455,
                "data_owner_name": "Data Owner",
                "data_owner_approval_date": REPORT_DATE,
                "data_owner_approved": True,
                "risk_owner_name": "Risk Owner",
                "risk_owner_countersign_date": REPORT_DATE,
                "risk_owner_countersigned": True,
                "business_owner_name": "Portfolio Owner",
                "business_owner_acknowledgement_date": REPORT_DATE,
                "business_owner_acknowledged": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_portfolio_home_owner_decision_intake_check_reports_current_pending_state() -> None:
    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        docs_root=ROOT / "docs",
        limit=1,
    )

    assert payload["check_kind"] == "portfolio_home_owner_decision_intake"
    assert payload["intake_status"] == "pending_owner_decisions"
    assert payload["intake_ready"] is False
    assert payload["dependency_consistency_status"] == "consistent"
    assert payload["csv_check_summary"] == {
        "krd_summary_row_count": 3,
        "krd_detail_row_count": 500,
        "krd_owner_decision_fields_blank": True,
        "bond_missing_maturity_row_count": 0,
        "tyw_liability_missing_maturity_row_count": 1455,
        "maturity_owner_fields_blank": True,
    }
    assert payload["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }
    assert payload["owner_input_boundary"] == {
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
    assert payload["owner_decision_statuses"] == {
        "risk_owner": "pending",
        "data_owner": "pending",
        "business_owner": "pending",
    }
    assert payload["owner_decision_blockers"] == [
        "krd_owner_decision_missing",
        "maturity_owner_decision_missing",
        "business_owner_approval_missing",
    ]
    assert payload["owner_decision_summary"]["krd"]["decision_counts"] == {}
    assert payload["owner_decision_summary"]["krd"]["decision_gap_counts"] == {
        "missing_decision_rows": 503,
        "summary_missing_decision_rows": 3,
        "detail_missing_decision_rows": 500,
    }
    assert payload["owner_decision_summary"]["maturity"]["decision_counts"] == {}
    assert payload["owner_decision_summary"]["maturity"]["decision_gap_counts"] == {
        "missing_decision_rows": 1455,
        "bond_missing_decision_rows": 0,
        "tyw_liability_missing_decision_rows": 1455,
    }
    assert payload["owner_decision_summary"]["business_owner"]["approval_status"] == "pending"


def test_portfolio_home_owner_decision_intake_check_cli_require_ready_blocks_current_state() -> None:
    returncode, payload = _run_check("--limit", "1", "--require-ready")

    assert returncode == 1
    assert payload["intake_ready"] is False
    assert payload["owner_decision_statuses"]["risk_owner"] == "pending"


def test_portfolio_home_owner_decision_intake_check_rejects_negative_limit() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home owner decision intake limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_owner_decision_intake_check_build_rejects_negative_limit() -> None:
    try:
        build_intake_check(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=ROOT / "docs",
            limit=-1,
        )
    except ValueError as exc:
        assert str(exc) == "Portfolio-home owner decision intake limit must be non-negative: -1"
    else:
        raise AssertionError("negative owner decision intake limit should be rejected")


def test_portfolio_home_owner_decision_intake_check_accepts_complete_candidate_decisions(
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

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE
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

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE
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
    _write_nearest_bucket_approval_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_status"] == "ready_for_intake"
    assert payload["intake_ready"] is True
    assert payload["owner_input_boundary"] == {
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
    }
    assert payload["owner_decision_statuses"] == {
        "risk_owner": "ready",
        "data_owner": "ready",
        "business_owner": "ready",
    }
    assert payload["owner_decision_blockers"] == []
    assert payload["owner_decision_summary"]["krd"]["decision_counts"] == {
        "approve_nearest_bucket": 503,
    }
    assert payload["owner_decision_summary"]["maturity"]["decision_counts"] == {
        "approve_scoped_exclusion": 1455,
    }
    assert payload["owner_decision_summary"]["business_owner"]["approval_status"] == "approved"


def test_portfolio_home_owner_decision_intake_check_blocks_dependency_csv_summary_drift(
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
    _write_maturity_scoped_exclusion_evidence(docs_root)
    _write_nearest_bucket_approval_evidence(docs_root)
    _write_nearest_bucket_approval_evidence(docs_root)

    dependency = {
        "dependency_consistency_blockers": [],
        "csv_check_summary": {
            "krd_summary_row_count": 2,
            "krd_detail_row_count": 499,
            "krd_owner_decision_fields_blank": False,
            "bond_missing_maturity_row_count": 113,
            "tyw_liability_missing_maturity_row_count": 1454,
            "maturity_owner_fields_blank": False,
        },
        "generated_owner_fields_boundaries": {
            "krd_contract_decision_manifest": True,
            "maturity_remediation_manifest": True,
        },
    }

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
        dependency=dependency,
    )

    assert payload["intake_ready"] is False
    assert payload["dependency_csv_summary_alignment"] == {
        "status": "blocked",
        "blockers": [
            "owner_csv_dependency_summary_krd_summary_row_count_mismatch",
            "owner_csv_dependency_summary_krd_detail_row_count_mismatch",
            "owner_csv_dependency_summary_bond_missing_maturity_row_count_mismatch",
            "owner_csv_dependency_summary_tyw_liability_missing_maturity_row_count_mismatch",
        ],
    }
    assert payload["owner_decision_blockers"] == [
        "owner_csv_dependency_summary_krd_summary_row_count_mismatch",
        "owner_csv_dependency_summary_krd_detail_row_count_mismatch",
        "owner_csv_dependency_summary_bond_missing_maturity_row_count_mismatch",
        "owner_csv_dependency_summary_tyw_liability_missing_maturity_row_count_mismatch",
    ]


def test_portfolio_home_owner_decision_intake_check_blocks_stale_export_current_gate(
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
    _write_maturity_scoped_exclusion_evidence(docs_root)
    _write_nearest_bucket_approval_evidence(docs_root)
    detail_csv = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "krd_remap_detail.csv"
    )
    _rewrite_csv(
        detail_csv,
        lambda row: {
            **row,
            "dv01": "0.00000000",
        },
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["export_current_statuses"]["krd"]["current"] is False
    assert payload["export_current_statuses"]["maturity"]["current"] is True
    assert payload["owner_decision_blockers"] == [
        "krd_contract_decision_export_stale",
    ]
    assert payload["owner_input_boundary"]["active_export_current_blockers"] == [
        "krd_contract_decision_export_stale",
    ]


def test_portfolio_home_owner_decision_intake_check_blocks_rejected_owner_decisions(
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

    _fill_krd_decisions(
        docs_root,
        "reject",
        notes="Rejected current nearest-bucket KRD contract.",
    )
    _fill_maturity_decisions(
        docs_root,
        "reject",
        comment="Rejected current maturity remediation boundary.",
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_statuses"] == {
        "risk_owner": "pending",
        "data_owner": "pending",
        "business_owner": "ready",
    }
    assert payload["owner_decision_blockers"] == [
        "krd_owner_decision_rejected",
        "maturity_owner_decision_rejected",
    ]
    assert payload["owner_decision_summary"]["krd"]["decision_counts"] == {
        "reject": 503,
    }
    assert payload["owner_decision_summary"]["maturity"]["decision_counts"] == {
        "reject": 1455,
    }


def test_portfolio_home_owner_decision_intake_check_blocks_template_csv_decision_mismatch(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="remediate_source",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE
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

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE
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
    _write_nearest_bucket_approval_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "krd_business_template_decision_mismatch",
        "maturity_business_template_decision_mismatch",
    ]
    assert payload["owner_decision_summary"]["decision_alignment"] == {
        "status": "blocked",
        "blockers": [
            "krd_business_template_decision_mismatch",
            "maturity_business_template_decision_mismatch",
        ],
        "business_template_decisions": {
            "krd_contract_decision": "require_exact_bucket_schema",
            "maturity_data_decision": "remediate_source",
        },
        "owner_csv_decisions": {
            "krd": ["approve_nearest_bucket"],
            "maturity": ["approve_scoped_exclusion"],
        },
    }


def test_portfolio_home_owner_decision_intake_check_reports_krd_note_gap_counts(
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
    _fill_krd_decisions(docs_root, "approve_nearest_bucket", notes="")
    _fill_maturity_decisions(
        docs_root,
        "approve_scoped_exclusion",
        comment="Signed exclusion for current candidate review only.",
    )
    _write_maturity_scoped_exclusion_evidence(docs_root)
    _write_nearest_bucket_approval_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == ["krd_owner_decision_notes_missing"]
    assert payload["owner_decision_summary"]["krd"]["note_gap_counts"] == {
        "risk_owner_decision": "approve_nearest_bucket",
        "missing_note_rows": 503,
    }


def test_portfolio_home_owner_decision_intake_check_requires_nearest_bucket_approval_evidence(
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
    _write_maturity_scoped_exclusion_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "krd_nearest_bucket_approval_evidence_missing",
    ]
    assert payload["owner_decision_summary"]["krd"]["nearest_bucket_approval_evidence"] == {
        "status": "missing",
        "artifact": (
            "docs/portfolio/krd-contract-decision/2026-05-31/"
            "nearest_bucket_approval_evidence.json"
        ),
        "valid": False,
        "blockers": ["krd_nearest_bucket_approval_evidence_missing"],
    }


def test_portfolio_home_owner_decision_intake_check_requires_named_nearest_bucket_approval(
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
    _write_maturity_scoped_exclusion_evidence(docs_root)
    evidence_path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "nearest_bucket_approval_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_nearest_bucket_approval_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "decision": "approve_nearest_bucket",
                "mapped_tenor_buckets": ["20Y", "2Y", "6M"],
                "nonzero_dv01_rows": 500,
                "dv01_sum": "33365026.29780176",
                "risk_owner_approved": True,
                "business_owner_acknowledged": True,
                "metric_contract_decision_recorded": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "krd_nearest_bucket_approval_evidence_risk_owner_name_missing",
        "krd_nearest_bucket_approval_evidence_risk_owner_approval_date_missing",
        "krd_nearest_bucket_approval_evidence_business_owner_name_missing",
        "krd_nearest_bucket_approval_evidence_business_owner_acknowledgement_date_missing",
    ]
    assert payload["owner_decision_summary"]["krd"]["nearest_bucket_approval_evidence"]["status"] == "blocked"


def test_portfolio_home_owner_decision_intake_check_reports_maturity_comment_gap_counts(
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
    _fill_krd_decisions(
        docs_root,
        "require_exact_bucket_schema",
        notes="Exact-bucket schema required before full closure.",
    )
    _write_exact_bucket_schema_evidence(docs_root)
    _fill_maturity_decisions(docs_root, "approve_scoped_exclusion", comment="")
    _write_maturity_scoped_exclusion_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == ["maturity_owner_comment_missing"]
    assert payload["owner_decision_summary"]["maturity"]["comment_gap_counts"] == {
        "owner_decision": "approve_scoped_exclusion",
        "missing_comment_rows": 1455,
    }


def test_portfolio_home_owner_decision_intake_check_requires_notes_for_exact_bucket_schema(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="approve_scoped_exclusion",
            decision_notes=(
                "Risk owner requires exact buckets; data owner signs scoped exclusion for "
                "current candidate review only."
            ),
        ),
        encoding="utf-8",
    )
    _fill_krd_decisions(docs_root, "require_exact_bucket_schema", notes="")
    _write_exact_bucket_schema_evidence(docs_root)
    _fill_maturity_decisions(
        docs_root,
        "approve_scoped_exclusion",
        comment="Signed exclusion for current candidate review only.",
    )
    _write_maturity_scoped_exclusion_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == ["krd_owner_decision_notes_missing"]
    assert payload["owner_decision_summary"]["krd"]["note_gap_counts"] == {
        "risk_owner_decision": "require_exact_bucket_schema",
        "missing_note_rows": 503,
    }


def test_portfolio_home_owner_decision_intake_check_requires_comment_for_source_remediation(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="remediate_source",
            decision_notes=(
                "Risk owner requires exact buckets; data owner will remediate source maturity "
                "dates for current candidate review."
            ),
        ),
        encoding="utf-8",
    )
    _fill_krd_decisions(
        docs_root,
        "require_exact_bucket_schema",
        notes="Exact-bucket schema required before full closure.",
    )
    _write_exact_bucket_schema_evidence(docs_root)
    _fill_maturity_decisions(
        docs_root,
        "remediate_source",
        proposed_maturity_date="2027-05-31",
        comment="",
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == ["maturity_owner_comment_missing"]
    assert payload["owner_decision_summary"]["maturity"]["comment_gap_counts"] == {
        "owner_decision": "remediate_source",
        "missing_comment_rows": 1455,
    }


def test_portfolio_home_owner_decision_intake_check_requires_exact_bucket_schema_evidence(
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
    _fill_krd_decisions(
        docs_root,
        "require_exact_bucket_schema",
        notes="Exact-bucket schema required before full closure.",
    )
    _fill_maturity_decisions(
        docs_root,
        "approve_scoped_exclusion",
        comment="Signed exclusion for current candidate review only.",
    )
    _write_maturity_scoped_exclusion_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "krd_exact_bucket_schema_evidence_missing",
    ]
    assert payload["owner_decision_summary"]["krd"]["exact_bucket_schema_evidence"] == {
        "status": "missing",
        "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
        "valid": False,
        "blockers": ["krd_exact_bucket_schema_evidence_missing"],
    }


def test_portfolio_home_owner_decision_intake_check_requires_named_exact_bucket_schema_evidence(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="approve_scoped_exclusion",
            decision_notes=(
                "Risk owner requires exact buckets; data owner signs scoped exclusion for "
                "current candidate review only."
            ),
        ),
        encoding="utf-8",
    )
    _fill_krd_decisions(
        docs_root,
        "require_exact_bucket_schema",
        notes="Exact-bucket schema required before full closure.",
    )
    _fill_maturity_decisions(
        docs_root,
        "approve_scoped_exclusion",
        comment="Signed exclusion for current candidate review only.",
    )
    _write_maturity_scoped_exclusion_evidence(docs_root)
    evidence_path = (
        docs_root
        / "portfolio"
        / "krd-contract-decision"
        / REPORT_DATE
        / "exact_bucket_schema_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_exact_bucket_schema_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "decision": "require_exact_bucket_schema",
                "metric_contract_updated": True,
                "api_schema_updated": True,
                "risk_tensor_rematerialized": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "krd_exact_bucket_schema_evidence_metric_contract_owner_name_missing",
        "krd_exact_bucket_schema_evidence_metric_contract_update_date_missing",
        "krd_exact_bucket_schema_evidence_api_schema_owner_name_missing",
        "krd_exact_bucket_schema_evidence_api_schema_update_date_missing",
        "krd_exact_bucket_schema_evidence_risk_tensor_owner_name_missing",
        "krd_exact_bucket_schema_evidence_risk_tensor_rematerialization_date_missing",
        "krd_exact_bucket_schema_evidence_verifier_name_missing",
        "krd_exact_bucket_schema_evidence_verification_rerun_date_missing",
    ]
    assert payload["owner_decision_summary"]["krd"]["exact_bucket_schema_evidence"]["status"] == "blocked"


def test_portfolio_home_owner_decision_intake_check_accepts_exact_bucket_schema_evidence(
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
    _fill_krd_decisions(
        docs_root,
        "require_exact_bucket_schema",
        notes="Exact-bucket schema required before full closure.",
    )
    _fill_maturity_decisions(
        docs_root,
        "approve_scoped_exclusion",
        comment="Signed exclusion for current candidate review only.",
    )
    _write_exact_bucket_schema_evidence(docs_root)
    _write_maturity_scoped_exclusion_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_status"] == "ready_for_intake"
    assert payload["intake_ready"] is True
    assert payload["owner_decision_blockers"] == []
    assert payload["owner_decision_summary"]["krd"]["exact_bucket_schema_evidence"]["status"] == "valid"


def test_portfolio_home_owner_decision_intake_check_requires_scoped_exclusion_evidence(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="approve_nearest_bucket",
            maturity_decision="approve_scoped_exclusion",
            decision_notes="Data owner signs scoped exclusion for current candidate review only.",
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
    _write_nearest_bucket_approval_evidence(docs_root)

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "maturity_scoped_exclusion_evidence_missing",
    ]
    assert payload["owner_decision_summary"]["maturity"]["scoped_exclusion_evidence"] == {
        "status": "missing",
        "artifact": (
            "docs/portfolio/maturity-remediation/2026-05-31/"
            "maturity_scoped_exclusion_evidence.json"
        ),
        "valid": False,
        "blockers": ["maturity_scoped_exclusion_evidence_missing"],
    }


def test_portfolio_home_owner_decision_intake_check_requires_named_scoped_exclusion_approval(
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
    _write_nearest_bucket_approval_evidence(docs_root)
    evidence_path = (
        docs_root
        / "portfolio"
        / "maturity-remediation"
        / REPORT_DATE
        / "maturity_scoped_exclusion_evidence.json"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "evidence_kind": "portfolio_home_maturity_scoped_exclusion_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "decision": "approve_scoped_exclusion",
                "bond_missing_maturity_rows": 0,
                "tyw_liability_missing_maturity_rows": 1455,
                "data_owner_approved": True,
                "risk_owner_countersigned": True,
                "business_owner_acknowledged": True,
                "verification_rerun_matched": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "maturity_scoped_exclusion_evidence_data_owner_name_missing",
        "maturity_scoped_exclusion_evidence_data_owner_approval_date_missing",
        "maturity_scoped_exclusion_evidence_risk_owner_name_missing",
        "maturity_scoped_exclusion_evidence_risk_owner_countersign_date_missing",
        "maturity_scoped_exclusion_evidence_business_owner_name_missing",
        "maturity_scoped_exclusion_evidence_business_owner_acknowledgement_date_missing",
    ]
    assert payload["owner_decision_summary"]["maturity"]["scoped_exclusion_evidence"]["status"] == "blocked"


def test_portfolio_home_owner_decision_intake_check_requires_proposed_date_for_remediation(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="remediate_source",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE
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

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "remediate_source",
            "proposed_maturity_date": "",
            "owner_comment": "Source maturity date will be remediated before rematerialization.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "remediate_source",
            "proposed_maturity_date": "",
            "owner_comment": "Source maturity date will be remediated before rematerialization.",
        },
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "maturity_proposed_maturity_date_missing",
    ]
    assert payload["owner_decision_summary"]["maturity"]["status"] == "pending"


def test_portfolio_home_owner_decision_intake_check_requires_valid_proposed_date_for_remediation(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    template = tmp_path / "portfolio-approval.md"
    template.write_text(
        _filled_template_text(
            krd_decision="require_exact_bucket_schema",
            maturity_decision="remediate_source",
        ),
        encoding="utf-8",
    )

    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE
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

    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE
    _rewrite_csv(
        maturity_dir / "bond_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "remediate_source",
            "proposed_maturity_date": "not-a-date",
            "owner_comment": "Source maturity date will be remediated before rematerialization.",
        },
    )
    _rewrite_csv(
        maturity_dir / "tyw_liability_missing_maturity.csv",
        lambda row: {
            **row,
            "owner_decision": "remediate_source",
            "proposed_maturity_date": "not-a-date",
            "owner_comment": "Source maturity date will be remediated before rematerialization.",
        },
    )

    payload = build_intake_check(
        duckdb_path=DUCKDB,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_ready"] is False
    assert payload["owner_decision_blockers"] == [
        "maturity_proposed_maturity_date_invalid",
    ]
    assert payload["owner_decision_summary"]["maturity"]["status"] == "pending"


def test_portfolio_home_owner_decision_intake_check_treats_empty_clean_queues_as_ready(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    docs_root = tmp_path / "docs"
    template = tmp_path / "portfolio-approval.md"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)
    _write_clean_fixture_manifests(docs_root)
    template.write_text(_filled_template_text(), encoding="utf-8")

    payload = build_intake_check(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
        limit=1,
    )

    assert payload["intake_status"] == "ready_for_intake"
    assert payload["intake_ready"] is True
    assert payload["owner_decision_statuses"] == {
        "risk_owner": "ready",
        "data_owner": "ready",
        "business_owner": "ready",
    }
    assert payload["owner_decision_blockers"] == []
