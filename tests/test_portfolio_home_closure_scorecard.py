from __future__ import annotations

from decimal import Decimal
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

import scripts.portfolio_home_closure_scorecard as scorecard_module
from scripts.portfolio_home_closure_scorecard import (
    OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    VERIFICATION_COMMANDS,
    _owner_decision_intake_alignment,
    _owner_handoff_completeness_gate,
    _score_blockers,
    _score_blocker_actions,
    _score_blocker_action_coverage,
    _verification_command_coverage,
    build_scorecard,
)
from scripts.portfolio_home_krd_contract_decision_export import (
    build_export_packet as build_krd_export_packet,
)
from scripts.portfolio_home_maturity_remediation_export import (
    build_export_packet as build_maturity_export_packet,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_closure_scorecard.py"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
REPORT_DATE = "2026-05-31"


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


def _expected_not_required_nearest_bucket_approval_evidence(
    report_date: str = REPORT_DATE,
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


def _required_verification_commands() -> list[dict[str, object]]:
    required_names = {
        "full_closure_strict",
        "risk_warning_clean",
        "krd_review_strict",
        "maturity_remediation_strict",
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
    }
    return [
        dict(command)
        for command in VERIFICATION_COMMANDS
        if command["name"] in required_names
    ]


def _create_schema(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar,
              quality_flag varchar,
              portfolio_dv01 decimal(24, 8),
              krd_1y decimal(24, 8),
              krd_3y decimal(24, 8),
              krd_5y decimal(24, 8),
              krd_7y decimal(24, 8),
              krd_10y decimal(24, 8),
              krd_30y decimal(24, 8),
              warnings_json varchar,
              source_version varchar,
              upstream_source_version varchar,
              liability_source_version varchar
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar,
              instrument_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              market_value decimal(24, 8),
              maturity_date varchar,
              dv01 decimal(24, 8),
              tenor_bucket varchar,
              modified_duration decimal(18, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        connection.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
    finally:
        connection.close()


def _insert_blocked_data(path: Path) -> None:
    warnings = [
        "Non-standard tenor buckets remapped to nearest KRD bucket: 2Y, 6M",
        (
            "3 rows carry market_value=60.00000000 and are excluded from portfolio duration denominator: "
            "2 without maturity_date; 1 with non-positive modified_duration. DV01 totals remain sourced "
            "from row dv01; duration metrics ignore these rows until inputs are remediated."
        ),
        "Excluded 2 rows without maturity_date from liquidity gap calculation.",
        "Excluded 1 liability rows without maturity_date from liquidity gap calculation.",
    ]
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            insert into fact_formal_risk_tensor_daily values (
              ?, 'warning', ?, ?, ?, 0, 0, 0, 0, ?, 'sv_risk', 'sv_bond', 'sv_tyw'
            )
            """,
            [REPORT_DATE, Decimal("5"), Decimal("3"), Decimal("2"), json.dumps(warnings)],
        )
        connection.executemany(
            """
            insert into fact_formal_bond_analytics_daily values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                [
                    REPORT_DATE,
                    "BOND-2Y",
                    "Two Year Bond",
                    "book-a",
                    "cc-a",
                    Decimal("10"),
                    "2028-05-31",
                    Decimal("2"),
                    "2Y",
                    Decimal("1"),
                    "sv_bond",
                    "rv_bond",
                    "batch-1",
                    "trace-2y",
                ],
                [
                    REPORT_DATE,
                    "BOND-6M",
                    "Six Month Bond",
                    "book-b",
                    "cc-b",
                    Decimal("20"),
                    "2026-11-30",
                    Decimal("3"),
                    "6M",
                    Decimal("1"),
                    "sv_bond",
                    "rv_bond",
                    "batch-2",
                    "trace-6m",
                ],
                [
                    REPORT_DATE,
                    "BOND-MISSING-A",
                    "Missing A",
                    "book-c",
                    "cc-c",
                    Decimal("30"),
                    None,
                    Decimal("0"),
                    "1Y",
                    None,
                    "sv_bond",
                    "rv_bond",
                    "batch-3",
                    "trace-missing-a",
                ],
                [
                    REPORT_DATE,
                    "BOND-MISSING-B",
                    "Missing B",
                    "book-d",
                    "cc-d",
                    Decimal("10"),
                    None,
                    Decimal("0"),
                    "3Y",
                    None,
                    "sv_bond",
                    "rv_bond",
                    "batch-4",
                    "trace-missing-b",
                ],
                [
                    REPORT_DATE,
                    "BOND-ZERO-DURATION",
                    "Zero Duration",
                    "book-e",
                    "cc-e",
                    Decimal("20"),
                    "2031-05-31",
                    Decimal("0"),
                    "5Y",
                    Decimal("0"),
                    "sv_bond",
                    "rv_bond",
                    "batch-5",
                    "trace-zero-duration",
                ],
            ],
        )
        connection.executemany(
            """
            insert into fact_formal_tyw_balance_daily values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                [
                    REPORT_DATE,
                    "POS-MISSING",
                    "deposit",
                    "short",
                    "Counterparty A",
                    "liability",
                    "CNY",
                    Decimal("100"),
                    Decimal("0.02"),
                    None,
                    "sv_tyw",
                    "rv_tyw",
                    "batch-6",
                    "trace-pos-missing",
                ],
                [
                    REPORT_DATE,
                    "POS-CLEAN",
                    "deposit",
                    "short",
                    "Counterparty B",
                    "liability",
                    "CNY",
                    Decimal("200"),
                    Decimal("0.01"),
                    "2026-07-31",
                    "sv_tyw",
                    "rv_tyw",
                    "batch-7",
                    "trace-pos-clean",
                ],
            ],
        )
    finally:
        connection.close()


def _insert_clean_data(path: Path) -> None:
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute(
            """
            insert into fact_formal_risk_tensor_daily values (
              ?, 'ok', ?, ?, 0, 0, 0, 0, 0, ?, 'sv_risk_clean', 'sv_bond_clean', 'sv_tyw_clean'
            )
            """,
            [REPORT_DATE, Decimal("5"), Decimal("5"), json.dumps([])],
        )
        connection.execute(
            """
            insert into fact_formal_bond_analytics_daily values (
              ?, 'BOND-1Y', 'Clean One Year Bond', 'book-a', 'cc-a', ?, '2027-05-31',
              ?, '1Y', ?, 'sv_bond_clean', 'rv_bond_clean', 'batch-clean-bond', 'trace-clean-bond'
            )
            """,
            [REPORT_DATE, Decimal("100"), Decimal("5"), Decimal("1")],
        )
        connection.execute(
            """
            insert into fact_formal_tyw_balance_daily values (
              ?, 'POS-CLEAN', 'deposit', 'short', 'Counterparty Clean', 'liability', 'CNY',
              ?, ?, '2026-07-31', 'sv_tyw_clean', 'rv_tyw_clean', 'batch-clean-tyw', 'trace-clean-tyw'
            )
            """,
            [REPORT_DATE, Decimal("200"), Decimal("0.01")],
        )
    finally:
        connection.close()


def _write_manifest(
    docs_root: Path,
    *,
    report_date: str,
    krd_summary: dict[str, object],
    maturity_summary: dict[str, object],
    krd_status: str,
    maturity_status: str,
) -> None:
    krd_dir = docs_root / "portfolio" / "krd-contract-decision" / report_date
    maturity_dir = docs_root / "portfolio" / "maturity-remediation" / report_date
    krd_dir.mkdir(parents=True, exist_ok=True)
    maturity_dir.mkdir(parents=True, exist_ok=True)
    (krd_dir / "manifest.json").write_text(
        json.dumps(
            {
                "report_date": report_date,
                "export_status": krd_status,
                "export_summary": krd_summary,
                "acceptance_criteria": {
                    "generated_owner_fields_must_be_blank": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (maturity_dir / "manifest.json").write_text(
        json.dumps(
            {
                "report_date": report_date,
                "export_status": maturity_status,
                "export_summary": maturity_summary,
                "acceptance_criteria": {
                    "generated_owner_fields_must_be_blank": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_blocked_fixture_manifests(docs_root: Path, duckdb_path: Path | None = None) -> None:
    if duckdb_path is not None:
        build_krd_export_packet(
            duckdb_path=duckdb_path,
            report_date=REPORT_DATE,
            output_dir=docs_root / "portfolio" / "krd-contract-decision",
        )
        build_maturity_export_packet(
            duckdb_path=duckdb_path,
            report_date=REPORT_DATE,
            output_dir=docs_root / "portfolio" / "maturity-remediation",
        )
        return

    _write_manifest(
        docs_root,
        report_date=REPORT_DATE,
        krd_status="decision_required",
        maturity_status="blocked",
        krd_summary={
            "remap_tenor_count": 2,
            "nonzero_dv01_rows": 2,
            "dv01_sum": "5.00000000",
        },
        maturity_summary={
            "bond_missing_maturity_rows": 2,
            "tyw_liability_missing_maturity_rows": 1,
            "bond_missing_maturity_market_value": "40.00000000",
            "tyw_liability_missing_maturity_principal": "100.00000000",
        },
    )
    _write_csv(
        docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE / "krd_remap_summary.csv",
        [
            "tenor_bucket",
            "nonzero_dv01_rows",
            "dv01_sum",
            "risk_owner_decision",
            "decision_notes",
        ],
        [
            {"tenor_bucket": "2Y", "nonzero_dv01_rows": 1, "dv01_sum": "2.00000000"},
            {"tenor_bucket": "6M", "nonzero_dv01_rows": 1, "dv01_sum": "3.00000000"},
        ],
    )
    _write_csv(
        docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE / "krd_remap_detail.csv",
        ["report_date", "instrument_code", "risk_owner_decision", "decision_notes"],
        [
            {"report_date": REPORT_DATE, "instrument_code": "BOND-2Y"},
            {"report_date": REPORT_DATE, "instrument_code": "BOND-6M"},
        ],
    )
    _write_csv(
        docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE / "bond_missing_maturity.csv",
        ["report_date", "instrument_code", "proposed_maturity_date", "owner_decision", "owner_comment"],
        [
            {"report_date": REPORT_DATE, "instrument_code": "BOND-MISSING-A"},
            {"report_date": REPORT_DATE, "instrument_code": "BOND-MISSING-B"},
        ],
    )
    _write_csv(
        docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE / "tyw_liability_missing_maturity.csv",
        ["report_date", "position_id", "proposed_maturity_date", "owner_decision", "owner_comment"],
        [{"report_date": REPORT_DATE, "position_id": "POS-MISSING"}],
    )


def _write_clean_fixture_manifests(docs_root: Path) -> None:
    _write_manifest(
        docs_root,
        report_date=REPORT_DATE,
        krd_status="clean",
        maturity_status="clean",
        krd_summary={
            "remap_tenor_count": 0,
            "nonzero_dv01_rows": 0,
            "dv01_sum": "0.00000000",
        },
        maturity_summary={
            "bond_missing_maturity_rows": 0,
            "tyw_liability_missing_maturity_rows": 0,
            "bond_missing_maturity_market_value": "0E-8",
            "tyw_liability_missing_maturity_principal": "0E-8",
        },
    )
    _write_csv(
        docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE / "krd_remap_summary.csv",
        ["tenor_bucket", "nonzero_dv01_rows", "dv01_sum", "risk_owner_decision", "decision_notes"],
        [],
    )
    _write_csv(
        docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE / "krd_remap_detail.csv",
        ["report_date", "instrument_code", "risk_owner_decision", "decision_notes"],
        [],
    )
    _write_csv(
        docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE / "bond_missing_maturity.csv",
        ["report_date", "instrument_code", "proposed_maturity_date", "owner_decision", "owner_comment"],
        [],
    )
    _write_csv(
        docs_root / "portfolio" / "maturity-remediation" / REPORT_DATE / "tyw_liability_missing_maturity.csv",
        ["report_date", "position_id", "proposed_maturity_date", "owner_decision", "owner_comment"],
        [],
    )


def _stable_json_sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_current_handoff_artifacts(docs_root: Path) -> tuple[Path, str, Path, str]:
    summary_path = docs_root / "portfolio" / "portfolio-home-owner-input-needed-summary.json"
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload: dict[str, object] = {
        "artifact_kind": "owner_input_needed_summary_fixture",
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": REPORT_DATE,
    }
    handoff_markdown = "# Owner Handoff Fixture\n\nEvidence-only test fixture.\n"
    summary_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    handoff_path.write_text(handoff_markdown, encoding="utf-8")
    return (
        summary_path,
        _stable_json_sha256(summary_payload),
        handoff_path,
        hashlib.sha256(handoff_markdown.encode("utf-8")).hexdigest(),
    )


def _write_clean_handoff_snapshot(docs_root: Path) -> None:
    summary_path, summary_hash, handoff_path, handoff_hash = _write_current_handoff_artifacts(
        docs_root,
    )
    snapshot = {
        "snapshot_kind": "portfolio_home_closure_evidence",
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": REPORT_DATE,
        "handoff_completeness_summary": {
            "status": "clean",
            "handoff_ready": True,
            "blockers": [],
            "summary_current_status": {
                "artifact": str(summary_path),
                "status": "current",
                "current": True,
                "expected_sha256": summary_hash,
                "actual_sha256": summary_hash,
            },
            "handoff_current_status": {
                "artifact": str(handoff_path),
                "status": "current",
                "expected_sha256": handoff_hash,
                "actual_sha256": handoff_hash,
            },
            "owner_route_coverage": {
                "status": "clean",
            },
            "route_statuses": {
                "risk_owner": "clean",
                "data_owner": "clean",
                "business_owner": "clean",
            },
            "evidence_scope": {
                "approves_metric_or_page": False,
                "writes_governance_records": False,
                "fills_owner_decisions": False,
                "captures_business_owner_approval": False,
                "proves_full_score_closure": False,
                "certification_effect": "none",
            },
        },
    }
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_missing_required_snapshot_sections(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "handoff_completeness_summary": {
                    "status": "clean",
                    "handoff_ready": True,
                    "blockers": [],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = _owner_handoff_completeness_gate(docs_root)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_input_needed_summary_status_missing",
        "owner_handoff_packet_status_missing",
        "owner_handoff_route_coverage_missing",
        "owner_handoff_route_statuses_missing",
        "owner_handoff_evidence_scope_missing",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_certification_effect_overclaim(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    _write_clean_handoff_snapshot(docs_root)
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    summary = snapshot["handoff_completeness_summary"]
    summary["evidence_scope"]["certification_effect"] = "certifies_page"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_handoff_evidence_scope_certification_effect_overclaims",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_requires_certification_effect_boundary(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    _write_clean_handoff_snapshot(docs_root)
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    summary = snapshot["handoff_completeness_summary"]
    summary["evidence_scope"].pop("certification_effect")
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_handoff_evidence_scope_certification_effect_missing",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_requires_all_owner_route_statuses(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    _write_clean_handoff_snapshot(docs_root)
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    summary = snapshot["handoff_completeness_summary"]
    summary["route_statuses"] = {
        "risk_owner": "clean",
    }
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = _owner_handoff_completeness_gate(docs_root)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_handoff_route_status_missing:data_owner",
        "owner_handoff_route_status_missing:business_owner",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_wrong_page_or_report_date(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    _write_clean_handoff_snapshot(docs_root)
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    snapshot["page_id"] = "PAGE-BOND-DASHBOARD-001"
    snapshot["page_slug"] = "bond-dashboard"
    snapshot["report_date"] = "2026-04-30"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_handoff_snapshot_page_id_mismatch",
        "owner_handoff_snapshot_page_slug_mismatch",
        "owner_handoff_snapshot_report_date_mismatch",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_wrong_snapshot_kind_and_missing_current_fingerprints(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_owner_handoff",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "handoff_completeness_summary": {
                    "status": "clean",
                    "handoff_ready": True,
                    "blockers": [],
                    "summary_current_status": {
                        "artifact": "F:\\MOSS-V3\\docs\\portfolio\\portfolio-home-owner-input-needed-summary.json",
                        "status": "current",
                        "current": True,
                    },
                    "handoff_current_status": {
                        "artifact": "F:\\MOSS-V3\\docs\\portfolio\\portfolio-home-owner-handoff-packet.md",
                        "status": "current",
                    },
                    "owner_route_coverage": {
                        "status": "clean",
                    },
                    "route_statuses": {
                        "risk_owner": "clean",
                        "data_owner": "clean",
                        "business_owner": "clean",
                    },
                    "evidence_scope": {
                        "approves_metric_or_page": False,
                        "writes_governance_records": False,
                        "fills_owner_decisions": False,
                        "captures_business_owner_approval": False,
                        "proves_full_score_closure": False,
                        "certification_effect": "none",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_handoff_snapshot_kind_mismatch",
        "owner_input_needed_summary_current_fingerprint_missing",
        "owner_handoff_packet_current_fingerprint_missing",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_current_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "handoff_completeness_summary": {
                    "status": "clean",
                    "handoff_ready": True,
                    "blockers": [],
                    "summary_current_status": {
                        "artifact": "F:\\MOSS-V3\\docs\\portfolio\\portfolio-home-owner-input-needed-summary.json",
                        "status": "current",
                        "current": True,
                        "expected_sha256": "expected-summary",
                        "actual_sha256": "actual-summary",
                    },
                    "handoff_current_status": {
                        "artifact": "F:\\MOSS-V3\\docs\\portfolio\\portfolio-home-owner-handoff-packet.md",
                        "status": "current",
                        "expected_sha256": "expected-handoff",
                        "actual_sha256": "actual-handoff",
                    },
                    "owner_route_coverage": {
                        "status": "clean",
                    },
                    "route_statuses": {
                        "risk_owner": "clean",
                        "data_owner": "clean",
                        "business_owner": "clean",
                    },
                    "evidence_scope": {
                        "approves_metric_or_page": False,
                        "writes_governance_records": False,
                        "fills_owner_decisions": False,
                        "captures_business_owner_approval": False,
                        "proves_full_score_closure": False,
                        "certification_effect": "none",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_input_needed_summary_current_fingerprint_mismatch",
        "owner_handoff_packet_current_fingerprint_mismatch",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_stale_disk_artifacts(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    _write_clean_handoff_snapshot(docs_root)
    summary_path = docs_root / "portfolio" / "portfolio-home-owner-input-needed-summary.json"
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    summary_path.write_text(
        json.dumps(
            {
                "artifact_kind": "owner_input_needed_summary_fixture",
                "report_date": REPORT_DATE,
                "stale": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    handoff_path.write_text("# Owner Handoff Fixture\n\nStale content.\n", encoding="utf-8")

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_input_needed_summary_current_file_fingerprint_mismatch",
        "owner_handoff_packet_current_file_fingerprint_mismatch",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_current_artifact_mismatch(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "handoff_completeness_summary": {
                    "status": "clean",
                    "handoff_ready": True,
                    "blockers": [],
                    "summary_current_status": {
                        "artifact": "F:\\MOSS-V3\\docs\\portfolio\\wrong-summary.json",
                        "status": "current",
                        "current": True,
                        "expected_sha256": "same-summary",
                        "actual_sha256": "same-summary",
                    },
                    "handoff_current_status": {
                        "artifact": "F:\\MOSS-V3\\docs\\portfolio\\wrong-handoff.md",
                        "status": "current",
                        "expected_sha256": "same-handoff",
                        "actual_sha256": "same-handoff",
                    },
                    "owner_route_coverage": {
                        "status": "clean",
                    },
                    "route_statuses": {
                        "risk_owner": "clean",
                        "data_owner": "clean",
                        "business_owner": "clean",
                    },
                    "evidence_scope": {
                        "approves_metric_or_page": False,
                        "writes_governance_records": False,
                        "fills_owner_decisions": False,
                        "captures_business_owner_approval": False,
                        "proves_full_score_closure": False,
                        "certification_effect": "none",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_input_needed_summary_current_artifact_mismatch",
        "owner_handoff_packet_current_artifact_mismatch",
    ]


def test_portfolio_home_closure_scorecard_handoff_gate_blocks_missing_current_artifact(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    output = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "snapshot_kind": "portfolio_home_closure_evidence",
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": REPORT_DATE,
                "handoff_completeness_summary": {
                    "status": "clean",
                    "handoff_ready": True,
                    "blockers": [],
                    "summary_current_status": {
                        "status": "current",
                        "current": True,
                        "expected_sha256": "same-summary",
                        "actual_sha256": "same-summary",
                    },
                    "handoff_current_status": {
                        "status": "current",
                        "expected_sha256": "same-handoff",
                        "actual_sha256": "same-handoff",
                    },
                    "owner_route_coverage": {
                        "status": "clean",
                    },
                    "route_statuses": {
                        "risk_owner": "clean",
                        "data_owner": "clean",
                        "business_owner": "clean",
                    },
                    "evidence_scope": {
                        "approves_metric_or_page": False,
                        "writes_governance_records": False,
                        "fills_owner_decisions": False,
                        "captures_business_owner_approval": False,
                        "proves_full_score_closure": False,
                        "certification_effect": "none",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = _owner_handoff_completeness_gate(docs_root, report_date=REPORT_DATE)

    assert gate["status"] == "blocked"
    assert gate["handoff_ready"] is False
    assert gate["blockers"] == [
        "owner_input_needed_summary_current_artifact_missing",
        "owner_handoff_packet_current_artifact_missing",
    ]


def _approved_template_text() -> str:
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("Approval status: `approval_status=pending`", "Approval status: `approval_status=approved`")
        .replace("Formal use allowed: `formal_use_allowed=false`", "Formal use allowed: `formal_use_allowed=true`")
        .replace("Closure approved: `closure_approved=false`", "Closure approved: `closure_approved=true`")
        .replace("- `approves_metric_or_page=false`", "- `approves_metric_or_page=true`")
        .replace("- `writes_governance_records=false`", "- `writes_governance_records=true`")
        .replace(
            "- `proves_capture_ready_page_execution=false`",
            "- `proves_capture_ready_page_execution=true`",
        )
        .replace(
            "- `captures_business_owner_approval=false`",
            "- `captures_business_owner_approval=true`",
        )
        .replace("Business owner name: `<required>`", "Business owner name: `Portfolio Owner`")
        .replace("Business owner role: `<required>`", "Business owner role: `Investment Book Owner`")
        .replace("Risk owner name: `<required>`", "Risk owner name: `Risk Owner`")
        .replace("Risk owner role: `<required>`", "Risk owner role: `Market Risk Owner`")
        .replace("Approval decision: `<approve | reject | request_changes>`", "Approval decision: `approve`")
        .replace("Approval date: `<YYYY-MM-DD>`", "Approval date: `2026-06-05`")
        .replace("Business owner signature: `<required>`", "Business owner signature: `Portfolio Owner`")
        .replace("Risk owner signature: `<required>`", "Risk owner signature: `Risk Owner`")
        .replace(
            "KRD contract decision: `<approve_nearest_bucket | require_exact_bucket_schema | reject>`",
            "KRD contract decision: `require_exact_bucket_schema`",
        )
        .replace(
            "Maturity data decision: `<remediate_source | approve_scoped_exclusion | reject>`",
            "Maturity data decision: `remediate_source`",
        )
        .replace(
            "Risk tensor warning decision: `<keep_warning | approve_after_clean_rerun | request_changes>`",
            "Risk tensor warning decision: `approve_after_clean_rerun`",
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
    )


def _run_scorecard(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_closure_scorecard_summarizes_blocked_gates(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    docs_root = tmp_path / "docs"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    _write_blocked_fixture_manifests(docs_root, duckdb_path)

    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        template_path=TEMPLATE,
        limit=2,
        docs_root=docs_root,
    )

    assert scorecard["current_score"] == "99.86 / 100"
    assert scorecard["remaining_gap"] == "0.14"
    assert scorecard["score_methodology"] == {
        "scoring_model": "discrete_full_closure_gate",
        "gap_basis": "remaining_gap is a full-score readiness gap, not a linear sum of blocker weights",
        "gap_allocation_allowed": False,
        "full_score_rule": "current_score is 100.00 / 100 only when every score_blocker is closed with auditable evidence",
        "blocked_score_rule": "current_score remains 99.86 / 100 while any full-closure blocker remains",
    }
    assert scorecard["score_status"] == "blocked"
    assert scorecard["full_score_ready"] is False
    assert scorecard["score_blockers"] == [
        "risk_tensor_quality_warning",
        "krd_contract_decision_required",
        "bond_maturity_date_remediation_required",
        "tyw_liability_maturity_date_remediation_required",
        "business_owner_approval",
        "owner_decision_intake_blocked",
    ]
    commands = {item["name"]: item for item in scorecard["verification_commands"]}
    assert commands["scorecard"]["command"] == "python scripts/portfolio_home_closure_scorecard.py --limit 3"
    assert commands["scorecard"]["expected_when_blocked"] == "exit_0"
    assert commands["scorecard"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["scorecard_strict"]["command"]
        == "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score"
    )
    assert commands["scorecard_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["scorecard_strict"]["expected_when_full_score"] == "exit_0"
    assert commands["full_closure_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["full_closure_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["maturity_remediation_export"]["command"]
        == "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation"
    )
    assert commands["maturity_remediation_export"]["expected_when_blocked"] == "exit_0"
    assert commands["maturity_remediation_export"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["maturity_remediation_export_strict"]["command"]
        == "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --require-clean"
    )
    assert commands["maturity_remediation_export_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["maturity_remediation_export_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["maturity_remediation_export_current"]["command"]
        == "python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --check-current"
    )
    assert commands["maturity_remediation_export_current"]["kind"] == "regression"
    assert commands["maturity_remediation_export_current"]["expected_when_blocked"] == "exit_0"
    assert commands["maturity_remediation_export_current"]["expected_when_full_score"] == "exit_0"
    assert commands["supporting_sample_guard"]["kind"] == "regression"
    assert commands["verification_command_runner"]["expected_when_blocked"] == "exit_0"
    assert commands["owner_action_packet"]["command"] == "python scripts/portfolio_home_owner_action_packet.py --limit 3"
    assert commands["owner_action_packet"]["expected_when_blocked"] == "exit_0"
    assert commands["owner_action_packet"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["owner_handoff_packet"]["command"]
        == "python scripts/portfolio_home_owner_handoff_packet.py --limit 3"
    )
    assert commands["owner_handoff_packet"]["expected_when_blocked"] == "exit_0"
    assert commands["owner_handoff_packet"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["owner_handoff_packet_current"]["command"]
        == "python scripts/portfolio_home_owner_handoff_packet.py --limit 3 --check-current"
    )
    assert commands["owner_handoff_packet_current"]["expected_when_blocked"] == "exit_0"
    assert commands["owner_handoff_packet_current"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["owner_handoff_completeness_check"]["command"]
        == "python scripts/portfolio_home_owner_handoff_completeness_check.py --limit 3 --require-clean"
    )
    assert commands["owner_handoff_completeness_check"]["kind"] == "regression"
    assert commands["owner_handoff_completeness_check"]["expected_when_blocked"] == "exit_0"
    assert commands["owner_handoff_completeness_check"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["evidence_snapshot_current"]["command"]
        == "python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --output docs/portfolio/portfolio-home-evidence-snapshot.json --check-current"
    )
    assert commands["evidence_snapshot_current"]["expected_when_blocked"] == "exit_0"
    assert commands["evidence_snapshot_current"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["evidence_snapshot_alignment_check"]["command"]
        == "python scripts/portfolio_home_evidence_snapshot_alignment_check.py --require-clean"
    )
    assert commands["evidence_snapshot_alignment_check"]["kind"] == "regression"
    assert commands["evidence_snapshot_alignment_check"]["expected_when_blocked"] == "exit_0"
    assert commands["evidence_snapshot_alignment_check"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["closure_artifact_presence_check"]["command"]
        == "python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current"
    )
    assert commands["closure_artifact_presence_check"]["kind"] == "regression"
    assert commands["closure_artifact_presence_check"]["expected_when_blocked"] == "exit_0"
    assert commands["closure_artifact_presence_check"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["evidence_packet_guard"]["command"]
        == "python scripts/portfolio_home_evidence_packet_guard.py --require-clean"
    )
    assert commands["evidence_packet_guard"]["kind"] == "regression"
    assert commands["evidence_packet_guard"]["expected_when_blocked"] == "exit_0"
    assert commands["evidence_packet_guard"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["owner_action_packet_strict"]["command"]
        == "python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean"
    )
    assert commands["owner_action_packet_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["owner_action_packet_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["business_owner_approval_packet"]["command"]
        == "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3"
    )
    assert commands["business_owner_approval_packet"]["expected_when_blocked"] == "exit_0"
    assert commands["business_owner_approval_packet"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["business_owner_approval_packet_strict"]["command"]
        == "python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready"
    )
    assert commands["business_owner_approval_packet_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["business_owner_approval_packet_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["dependency_consistency_check"]["command"]
        == "python scripts/portfolio_home_dependency_consistency_check.py --limit 3"
    )
    assert commands["dependency_consistency_check"]["expected_when_blocked"] == "exit_0"
    assert commands["dependency_consistency_check"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["dependency_consistency_check_strict"]["command"]
        == "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent"
    )
    assert commands["dependency_consistency_check_strict"]["expected_when_blocked"] == "exit_0"
    assert commands["dependency_consistency_check_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["owner_decision_intake_check"]["command"]
        == "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3"
    )
    assert commands["owner_decision_intake_check"]["expected_when_blocked"] == "exit_0"
    assert commands["owner_decision_intake_check"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["owner_decision_intake_check_strict"]["command"]
        == "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready"
    )
    assert commands["owner_decision_intake_check_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["owner_decision_intake_check_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["krd_contract_decision_export"]["command"]
        == "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision"
    )
    assert commands["krd_contract_decision_export"]["expected_when_blocked"] == "exit_0"
    assert commands["krd_contract_decision_export"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["krd_contract_decision_export_strict"]["command"]
        == "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --require-clean"
    )
    assert commands["krd_contract_decision_export_strict"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["krd_contract_decision_export_strict"]["expected_when_full_score"] == "exit_0"
    assert (
        commands["krd_contract_decision_export_current"]["command"]
        == "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --check-current"
    )
    assert commands["krd_contract_decision_export_current"]["kind"] == "regression"
    assert commands["krd_contract_decision_export_current"]["expected_when_blocked"] == "exit_0"
    assert commands["krd_contract_decision_export_current"]["expected_when_full_score"] == "exit_0"
    assert commands["risk_warning_consistency"]["expected_when_blocked"] == "exit_nonzero"
    assert commands["risk_warning_consistency"]["expected_when_full_score"] == "exit_0"
    actions = {item["blocker"]: item for item in scorecard["score_blocker_actions"]}
    assert actions["risk_tensor_quality_warning"]["owner"] == "risk_owner"
    assert (
        actions["risk_tensor_quality_warning"]["evidence_command"]
        == "python scripts/portfolio_home_risk_warning_consistency.py --require-clean"
    )
    assert actions["krd_contract_decision_required"]["owner"] == "risk_owner"
    assert "exact-bucket KRD schema/API" in actions["krd_contract_decision_required"]["next_action"]
    assert actions["bond_maturity_date_remediation_required"]["owner"] == "data_owner"
    assert actions["tyw_liability_maturity_date_remediation_required"]["owner"] == "data_owner"
    assert actions["business_owner_approval"]["owner"] == "business_owner"
    assert (
        actions["business_owner_approval"]["evidence_command"]
        == "python scripts/check_portfolio_home_business_owner_approval.py --require-captured"
    )
    assert actions["owner_decision_intake_blocked"]["owner"] == "business_owner"
    assert (
        "nearest-bucket or exact-bucket evidence"
        in actions["owner_decision_intake_blocked"]["next_action"]
    )
    assert (
        actions["owner_decision_intake_blocked"]["evidence_command"]
        == "python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready"
    )
    assert scorecard["gates"]["score_blocker_action_coverage"] == {
        "status": "clean",
        "blockers": [],
        "unassigned_blockers": [],
        "covered_blockers": [
            "risk_tensor_quality_warning",
            "krd_contract_decision_required",
            "bond_maturity_date_remediation_required",
            "tyw_liability_maturity_date_remediation_required",
            "business_owner_approval",
            "owner_decision_intake_blocked",
        ],
    }
    assert scorecard["gates"]["verification_command_coverage"]["status"] == "clean"
    assert scorecard["gates"]["verification_command_coverage"]["missing_commands"] == []
    assert scorecard["gates"]["risk_warning_consistency"]["status"] == "consistent"
    assert scorecard["gates"]["risk_warning_consistency"]["decision_status"] == "blocked"
    assert scorecard["gates"]["risk_warning_consistency"]["parsed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert scorecard["gates"]["risk_warning_consistency"]["recomputed_warnings"]["krd_buckets"] == ["2Y", "6M"]
    assert scorecard["gates"]["risk_warning_consistency"]["risk_tensor_rematerialization_preview"][
        "preview_basis"
    ] == "current_formal_facts_read_only"
    assert scorecard["gates"]["risk_warning_consistency"]["risk_tensor_rematerialization_preview"][
        "writes_database"
    ] is False
    assert scorecard["gates"]["risk_warning_consistency"]["risk_tensor_rematerialization_preview"][
        "preview_decision_status"
    ] == "blocked"
    assert scorecard["gates"]["full_closure_evidence"]["risk_tensor"]["quality_flag"] == "warning"
    assert scorecard["gates"]["full_closure_evidence"]["bond_maturity_gap"]["missing_maturity_rows"] == 2
    assert (
        scorecard["gates"]["full_closure_evidence"]["tyw_liability_maturity_gap_risk_scope"][
            "missing_maturity_rows"
        ]
        == 1
    )
    assert scorecard["gates"]["full_closure_evidence"]["krd_remap_scope"][0]["tenor_bucket"] == "2Y"
    assert scorecard["gates"]["krd_contract"]["status"] == "decision_required"
    assert scorecard["gates"]["krd_contract"]["krd_remap_summary"][0]["tenor_bucket"] == "2Y"
    assert scorecard["gates"]["krd_contract"]["decision_options"] == [
        "approve_nearest_bucket",
        "require_exact_bucket_schema",
        "reject",
    ]
    assert scorecard["gates"]["krd_contract"]["review_actions"][0]["owner"] == "risk_owner"
    assert scorecard["gates"]["maturity_remediation"]["status"] == "blocked"
    assert scorecard["gates"]["maturity_remediation"]["remediation_scope"] == {
        "bond_queue": "fact_formal_bond_analytics_daily rows where maturity_date is null",
        "tyw_liability_queue": "fact_formal_tyw_balance_daily liability CNY rows where maturity_date is null",
    }
    assert (
        scorecard["gates"]["maturity_remediation"]["bond_missing_maturity_summary"][
            "missing_maturity_market_value"
        ]
        == "40.00000000"
    )
    assert (
        scorecard["gates"]["maturity_remediation"]["tyw_liability_missing_maturity_summary"][
            "missing_maturity_principal"
        ]
        == "100.00000000"
    )
    assert scorecard["gates"]["maturity_remediation"]["remediation_actions"][0]["owner"] == "data_owner"
    assert scorecard["gates"]["business_owner_approval"]["status"] == "pending"
    assert scorecard["gates"]["owner_decision_intake"] == {
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
                "missing_decision_rows": 4,
                "summary_missing_decision_rows": 2,
                "detail_missing_decision_rows": 2,
            },
            "maturity": {
                "missing_decision_rows": 3,
                "bond_missing_decision_rows": 2,
                "tyw_liability_missing_decision_rows": 1,
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
    assert scorecard["gates"]["owner_decision_intake_alignment"] == {
        "status": "consistent",
        "blockers": [],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }


def test_portfolio_home_closure_scorecard_require_full_score_blocks_current_gap(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "blocked.duckdb"
    docs_root = tmp_path / "docs"
    _create_schema(duckdb_path)
    _insert_blocked_data(duckdb_path)
    _write_blocked_fixture_manifests(docs_root, duckdb_path)

    returncode, payload = _run_scorecard(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--template-path",
        str(TEMPLATE),
        "--docs-root",
        str(docs_root),
        "--limit",
        "2",
        "--require-full-score",
    )

    assert returncode == 1
    assert payload["score_status"] == "blocked"
    assert payload["remaining_gap"] == "0.14"
    assert "business_owner_approval" in payload["score_blockers"]


def test_portfolio_home_closure_scorecard_rejects_negative_limit() -> None:
    try:
        build_scorecard(
            duckdb_path=ROOT / "data" / "moss.duckdb",
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            limit=-1,
        )
    except ValueError as error:
        assert str(error) == "Portfolio-home limit must be non-negative: -1"
    else:
        raise AssertionError("negative scorecard limit was accepted")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home limit must be non-negative: -1" in completed.stderr


def test_portfolio_home_closure_scorecard_allows_full_score_when_all_gates_close(
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

    returncode, payload = _run_scorecard(
        "--duckdb-path",
        str(duckdb_path),
        "--report-date",
        REPORT_DATE,
        "--template-path",
        str(template),
        "--docs-root",
        str(docs_root),
        "--require-full-score",
    )

    assert returncode == 0
    assert payload["current_score"] == "100.00 / 100"
    assert payload["remaining_gap"] == "0.00"
    assert payload["score_methodology"]["gap_allocation_allowed"] is False
    assert payload["score_status"] == "ready_for_full_score"
    assert payload["full_score_ready"] is True
    assert payload["score_blockers"] == []
    assert payload["score_blocker_actions"] == []
    assert payload["verification_commands"][0]["name"] == "full_closure_evidence"
    assert payload["gates"]["full_closure_evidence"]["status"] == "clean"
    assert payload["gates"]["full_closure_evidence"]["risk_tensor"]["quality_flag"] == "ok"
    assert payload["gates"]["full_closure_evidence"]["bond_maturity_gap"]["missing_maturity_rows"] == 0
    assert payload["gates"]["risk_warning_consistency"]["decision_status"] == "clean"
    assert payload["gates"]["krd_contract"]["status"] == "clean"
    assert payload["gates"]["krd_contract"]["krd_remap_summary"] == []
    assert payload["gates"]["krd_contract"]["review_actions"] == []
    assert payload["gates"]["maturity_remediation"]["status"] == "clean"
    assert payload["gates"]["maturity_remediation"]["bond_missing_maturity_summary"]["missing_maturity_rows"] == 0
    assert payload["gates"]["maturity_remediation"]["remediation_actions"] == []
    assert payload["gates"]["business_owner_approval"]["status"] == "captured"
    assert payload["gates"]["owner_decision_intake"]["status"] == "ready"
    assert payload["gates"]["owner_decision_intake"]["intake_ready"] is True
    assert payload["gates"]["owner_decision_intake"]["blockers"] == []
    assert payload["gates"]["owner_decision_intake_alignment"]["status"] == "consistent"
    assert payload["gates"]["owner_decision_intake_alignment"]["blockers"] == []
    assert payload["gates"]["owner_handoff_completeness"]["status"] == "clean"
    assert payload["gates"]["owner_handoff_completeness"]["handoff_ready"] is True
    assert payload["gates"]["owner_handoff_completeness"]["blockers"] == []
    assert payload["gates"]["owner_handoff_completeness"]["handoff_current_status"]["status"] == "current"
    assert payload["gates"]["approval_dependency_consistency"]["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": True,
        "maturity_remediation_manifest": True,
    }


def test_portfolio_home_closure_scorecard_surfaces_owner_intake_when_not_ready(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    template = tmp_path / "portfolio-approval.md"
    docs_root = tmp_path / "docs"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)
    template.write_text(_approved_template_text(), encoding="utf-8")
    _write_clean_fixture_manifests(docs_root)
    _write_csv(
        docs_root / "portfolio" / "krd-contract-decision" / REPORT_DATE / "krd_remap_summary.csv",
        ["tenor_bucket", "nonzero_dv01_rows", "dv01_sum", "risk_owner_decision", "decision_notes"],
        [
            {
                "tenor_bucket": "6M",
                "nonzero_dv01_rows": 1,
                "dv01_sum": "1.00000000",
                "risk_owner_decision": "require_exact_bucket_schema",
            },
        ],
    )

    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_root,
    )

    assert scorecard["current_score"] == "99.86 / 100"
    assert scorecard["remaining_gap"] == "0.14"
    assert scorecard["score_status"] == "blocked"
    assert scorecard["full_score_ready"] is False
    assert scorecard["score_blockers"] == [
        "approval_dependency_consistency_blocked",
        "owner_decision_intake_blocked",
    ]
    owner_gate = scorecard["gates"]["owner_decision_intake"]
    assert owner_gate["status"] == "pending"
    assert owner_gate["intake_ready"] is False
    assert "krd_contract_decision_manifest_summary_csv_row_count_mismatch" in owner_gate["blockers"]
    assert "krd_exact_bucket_schema_evidence_missing" in owner_gate["blockers"]
    assert owner_gate["exact_bucket_schema_evidence"] == {
        "status": "missing",
        "artifact": "docs/portfolio/krd-contract-decision/2026-05-31/exact_bucket_schema_evidence.json",
        "valid": False,
        "blockers": ["krd_exact_bucket_schema_evidence_missing"],
    }


def test_portfolio_home_closure_scorecard_owner_intake_is_final_full_score_gate() -> None:
    blockers = _score_blockers(
        full_closure={"closure_blockers": []},
        warning_consistency={
            "warning_consistency_status": "consistent",
            "decision_status": "clean",
        },
        krd_queue={"review_status": "clean"},
        maturity_queue={"remediation_status": "clean"},
        approval_status={
            "business_owner_approval_captured": True,
            "evidence_scope": {"approves_metric_or_page": True},
        },
        dependency_consistency_blockers=[],
        owner_intake={"intake_ready": False},
    )

    assert blockers == ["owner_decision_intake_blocked"]


def test_portfolio_home_closure_scorecard_owner_intake_remains_visible_with_other_blockers() -> None:
    blockers = _score_blockers(
        full_closure={"closure_blockers": ["risk_tensor_quality_warning"]},
        warning_consistency={
            "warning_consistency_status": "consistent",
            "decision_status": "clean",
        },
        krd_queue={"review_status": "clean"},
        maturity_queue={"remediation_status": "clean"},
        approval_status={
            "business_owner_approval_captured": True,
            "evidence_scope": {"approves_metric_or_page": True},
        },
        dependency_consistency_blockers=[],
        owner_intake={"intake_ready": False},
    )

    assert blockers == [
        "risk_tensor_quality_warning",
        "owner_decision_intake_blocked",
    ]


def test_portfolio_home_closure_scorecard_owner_intake_alignment_is_full_score_gate() -> None:
    blockers = _score_blockers(
        full_closure={"closure_blockers": []},
        warning_consistency={
            "warning_consistency_status": "consistent",
            "decision_status": "clean",
        },
        krd_queue={"review_status": "clean"},
        maturity_queue={"remediation_status": "clean"},
        approval_status={
            "business_owner_approval_captured": True,
            "evidence_scope": {"approves_metric_or_page": True},
        },
        dependency_consistency_blockers=[],
        owner_intake={"intake_ready": True},
        owner_intake_alignment={
            "status": "blocked",
            "blockers": ["owner_decision_intake_alignment_intake_ready_mismatch"],
        },
    )

    assert blockers == ["owner_decision_intake_alignment_blocked"]


def test_portfolio_home_closure_scorecard_verification_command_coverage_is_full_score_gate() -> None:
    blockers = _score_blockers(
        full_closure={"closure_blockers": []},
        warning_consistency={
            "warning_consistency_status": "consistent",
            "decision_status": "clean",
        },
        krd_queue={"review_status": "clean"},
        maturity_queue={"remediation_status": "clean"},
        approval_status={
            "business_owner_approval_captured": True,
            "evidence_scope": {"approves_metric_or_page": True},
        },
        dependency_consistency_blockers=[],
        owner_intake={"intake_ready": True},
        owner_intake_alignment={"status": "consistent", "blockers": []},
        verification_command_coverage={
            "status": "blocked",
            "missing_commands": ["owner_handoff_packet_current"],
        },
    )

    assert blockers == ["verification_command_coverage_blocked"]


def test_portfolio_home_closure_scorecard_owner_handoff_completeness_is_full_score_gate() -> None:
    blockers = _score_blockers(
        full_closure={"closure_blockers": []},
        warning_consistency={
            "warning_consistency_status": "consistent",
            "decision_status": "clean",
        },
        krd_queue={"review_status": "clean"},
        maturity_queue={"remediation_status": "clean"},
        approval_status={
            "business_owner_approval_captured": True,
            "evidence_scope": {"approves_metric_or_page": True},
        },
        dependency_consistency_blockers=[],
        owner_intake={"intake_ready": True},
        owner_intake_alignment={"status": "consistent", "blockers": []},
        verification_command_coverage={"status": "clean", "missing_commands": []},
        owner_handoff_completeness={
            "status": "blocked",
            "blockers": ["owner_handoff_packet_not_current"],
        },
    )

    assert blockers == ["owner_handoff_completeness_blocked"]


def test_portfolio_home_closure_scorecard_owner_intake_alignment_blocker_has_owner_action() -> None:
    actions = _score_blocker_actions(["owner_decision_intake_alignment_blocked"])

    assert actions == [
        {
            "blocker": "owner_decision_intake_alignment_blocked",
            "owner": "business_owner",
            "next_action": (
                "Reconcile the direct owner-intake evidence and scorecard gate summary "
                "before full-score activation."
            ),
            "evidence_command": "python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score",
            "exit_criteria": (
                "Scorecard owner_decision_intake_alignment gate reports status=consistent "
                "with no blockers."
            ),
        }
    ]


def test_portfolio_home_closure_scorecard_verification_command_coverage_blocker_has_owner_action() -> None:
    actions = _score_blocker_actions(["verification_command_coverage_blocked"])

    assert actions == [
        {
            "blocker": "verification_command_coverage_blocked",
            "owner": "business_owner",
            "next_action": "Restore the portfolio-home verification command allowlist before any full-score claim.",
            "evidence_command": "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched",
            "exit_criteria": (
                "Verification command coverage gate reports status=clean with no missing required commands."
            ),
        }
    ]


def test_portfolio_home_closure_scorecard_owner_handoff_completeness_blocker_has_owner_action() -> None:
    actions = _score_blocker_actions(["owner_handoff_completeness_blocked"])

    assert actions == [
        {
            "blocker": "owner_handoff_completeness_blocked",
            "owner": "business_owner",
            "next_action": "Regenerate the owner input summary and handoff packet before any full-score claim.",
            "evidence_command": "python scripts/portfolio_home_owner_handoff_completeness_check.py --limit 3 --require-clean",
            "exit_criteria": "Owner handoff completeness gate reports status=clean and handoff_ready=true.",
        }
    ]


def test_portfolio_home_closure_scorecard_warning_mismatch_blockers_have_owner_actions() -> None:
    actions = _score_blocker_actions(
        [
            "duration_exclusion_warning_mismatch",
            "risk_tensor_warning_mismatch",
        ],
    )

    assert actions == [
        {
            "blocker": "duration_exclusion_warning_mismatch",
            "owner": "data_owner",
            "next_action": (
                "Reconcile the recomputed duration-exclusion warning evidence with the "
                "risk tensor warning text before any full-score claim."
            ),
            "evidence_command": "python scripts/portfolio_home_risk_warning_consistency.py --require-consistent",
            "exit_criteria": (
                "Risk warning consistency reports matching parsed and recomputed "
                "duration-exclusion evidence."
            ),
        },
        {
            "blocker": "risk_tensor_warning_mismatch",
            "owner": "risk_owner",
            "next_action": (
                "Reconcile risk tensor warning evidence and rematerialize the risk tensor "
                "or keep /portfolio candidate-only."
            ),
            "evidence_command": "python scripts/portfolio_home_risk_warning_consistency.py --require-clean",
            "exit_criteria": (
                "Risk warning clean gate exits 0 with no risk tensor warning mismatch."
            ),
        },
    ]


def test_portfolio_home_closure_scorecard_score_blockers_include_warning_mismatches() -> None:
    blockers = _score_blockers(
        full_closure={"closure_blockers": []},
        warning_consistency={
            "warning_consistency_status": "mismatch",
            "consistency_blockers": ["duration_exclusion_warning_mismatch"],
            "decision_status": "blocked",
            "decision_blockers": [
                "risk_tensor_quality_warning",
                "risk_tensor_warning_mismatch",
            ],
        },
        krd_queue={"review_status": "clean"},
        maturity_queue={"remediation_status": "clean"},
        approval_status={"business_owner_approval_captured": True},
        dependency_consistency_blockers=[],
        owner_intake={"intake_ready": True},
    )

    assert blockers == [
        "duration_exclusion_warning_mismatch",
        "risk_tensor_quality_warning",
        "risk_tensor_warning_mismatch",
    ]


def test_portfolio_home_closure_scorecard_blocks_unassigned_score_blocker_actions() -> None:
    coverage = _score_blocker_action_coverage(
        ["business_owner_approval", "new_unmapped_blocker"],
        _score_blocker_actions(["business_owner_approval", "new_unmapped_blocker"]),
    )

    assert coverage == {
        "status": "blocked",
        "blockers": ["score_blocker_action_missing:new_unmapped_blocker"],
        "unassigned_blockers": ["new_unmapped_blocker"],
        "covered_blockers": ["business_owner_approval"],
    }


def test_portfolio_home_closure_scorecard_requires_critical_verification_commands() -> None:
    commands = _required_verification_commands()
    present_commands = [command["name"] for command in commands]
    coverage = _verification_command_coverage(commands)

    assert coverage == {
        "status": "clean",
        "required_commands": [
            "full_closure_strict",
            "risk_warning_clean",
            "krd_review_strict",
            "maturity_remediation_strict",
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
        ],
        "present_commands": present_commands,
        "missing_commands": [],
        "mismatched_commands": [],
        "duplicate_commands": [],
    }

    assert _verification_command_coverage(commands[:2]) == {
        "status": "blocked",
        "required_commands": [
            "full_closure_strict",
            "risk_warning_clean",
            "krd_review_strict",
            "maturity_remediation_strict",
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
        ],
        "present_commands": ["full_closure_strict", "risk_warning_clean"],
        "missing_commands": [
            "krd_review_strict",
            "maturity_remediation_strict",
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
        ],
        "mismatched_commands": [],
        "duplicate_commands": [],
    }


def test_portfolio_home_closure_scorecard_verification_command_coverage_blocks_spec_drift() -> None:
    coverage = _verification_command_coverage(
        [
            {
                "name": "full_closure_strict",
                "kind": "strict_gate",
                "command": "python scripts/portfolio_home_full_closure_evidence.py --require-clean",
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
                "name": "krd_review_strict",
                "kind": "strict_gate",
                "command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
                "expected_when_blocked": "exit_nonzero",
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
                "name": "business_owner_approval_strict",
                "kind": "strict_gate",
                "command": "python scripts/check_portfolio_home_business_owner_approval.py --require-captured",
                "expected_when_blocked": "exit_nonzero",
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
                "name": "owner_action_packet_current",
                "kind": "regression",
                "command": "python scripts/portfolio_home_owner_action_packet.py --limit 3 --output docs/portfolio/portfolio-home-owner-action-packet.json --check-current",
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
                "name": "dependency_consistency_check_strict",
                "kind": "strict_gate",
                "command": "python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent",
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
                "name": "owner_handoff_packet_current",
                "kind": "regression",
                "command": "python scripts/portfolio_home_owner_handoff_packet.py --limit 3",
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
                "name": "krd_contract_decision_export_current",
                "kind": "regression",
                "command": "python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --check-current",
                "expected_when_blocked": "exit_0",
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
    )

    assert coverage["status"] == "blocked"
    assert coverage["missing_commands"] == []
    assert coverage["mismatched_commands"] == [
        {
            "name": "owner_handoff_packet_current",
            "field": "command",
            "expected": "python scripts/portfolio_home_owner_handoff_packet.py --limit 3 --check-current",
            "actual": "python scripts/portfolio_home_owner_handoff_packet.py --limit 3",
        }
    ]


def test_portfolio_home_closure_scorecard_verification_command_coverage_blocks_missing_spec_fields() -> None:
    commands = _required_verification_commands()
    for command in commands:
        if command["name"] == "owner_handoff_packet_current":
            del command["expected_when_blocked"]
            break

    coverage = _verification_command_coverage(commands)

    assert coverage["status"] == "blocked"
    assert coverage["missing_commands"] == []
    assert coverage["mismatched_commands"] == [
        {
            "name": "owner_handoff_packet_current",
            "field": "expected_when_blocked",
            "expected": "exit_0",
            "actual": None,
        }
    ]


def test_portfolio_home_closure_scorecard_verification_command_coverage_blocks_strict_gate_expectation_drift(
    monkeypatch,
) -> None:
    drifted_commands = [dict(command) for command in scorecard_module.VERIFICATION_COMMANDS]
    for command in drifted_commands:
        if command["name"] == "full_closure_strict":
            command["expected_when_blocked"] = "exit_0"
            break
    required_names = set(scorecard_module.REQUIRED_VERIFICATION_COMMANDS)
    commands = [
        dict(command)
        for command in drifted_commands
        if command["name"] in required_names
    ]
    monkeypatch.setattr(scorecard_module, "VERIFICATION_COMMANDS", drifted_commands)

    coverage = scorecard_module._verification_command_coverage(commands)

    assert coverage["status"] == "blocked"
    assert coverage["missing_commands"] == []
    assert {
        "name": "full_closure_strict",
        "field": "blocked_state_gate_expected_when_blocked",
        "expected": "exit_nonzero",
        "actual": "exit_0",
    } in coverage["mismatched_commands"]


def test_portfolio_home_closure_scorecard_verification_command_coverage_blocks_duplicate_required_commands() -> None:
    commands = _required_verification_commands()
    duplicate = next(
        dict(command)
        for command in commands
        if command["name"] == "owner_handoff_packet_current"
    )

    coverage = _verification_command_coverage([*commands, duplicate])

    assert coverage["status"] == "blocked"
    assert coverage["missing_commands"] == []
    assert coverage["duplicate_commands"] == ["owner_handoff_packet_current"]


def test_portfolio_home_closure_scorecard_owner_intake_alignment_blocks_mismatch() -> None:
    direct = {
        "intake_status": "ready_for_intake",
        "intake_ready": True,
        "dependency_consistency_status": "consistent",
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": True},
        "owner_decision_statuses": {"risk_owner": "ready"},
        "decision_counts": {"krd": {}, "maturity": {}},
        "decision_gap_counts": {"krd": {"missing_decision_rows": 0}},
        "note_gap_counts": {"krd": {}},
        "exact_bucket_schema_evidence": {"status": "not_required"},
        "nearest_bucket_approval_evidence": {"status": "not_required"},
    }
    scorecard_gate = {
        **direct,
        "intake_ready": False,
        "owner_input_boundary": {"filled_owner_fields_are_owner_input_only": False},
        "owner_decision_statuses": {"risk_owner": "pending"},
        "decision_counts": {"krd": {"approve_nearest_bucket": 1}, "maturity": {}},
    }

    assert _owner_decision_intake_alignment(direct, scorecard_gate) == {
        "status": "blocked",
        "blockers": [
            "owner_decision_intake_alignment_intake_ready_mismatch",
            "owner_decision_intake_alignment_owner_input_boundary_mismatch",
            "owner_decision_intake_alignment_owner_decision_statuses_mismatch",
            "owner_decision_intake_alignment_decision_counts_mismatch",
        ],
        "compared_fields": OWNER_DECISION_INTAKE_ALIGNMENT_FIELDS,
    }


def test_portfolio_home_closure_scorecard_blocks_full_score_when_dependency_manifest_mismatches(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "clean.duckdb"
    template = tmp_path / "portfolio-approval.md"
    docs_dir = tmp_path / "docs"
    _create_schema(duckdb_path)
    _insert_clean_data(duckdb_path)
    template.write_text(_approved_template_text(), encoding="utf-8")
    shutil.copytree(ROOT / "docs" / "portfolio", docs_dir / "portfolio")
    shutil.copytree(ROOT / "docs" / "audits", docs_dir / "audits")

    krd_dir = docs_dir / "portfolio" / "krd-contract-decision" / REPORT_DATE
    maturity_dir = docs_dir / "portfolio" / "maturity-remediation" / REPORT_DATE
    krd_dir.mkdir(parents=True, exist_ok=True)
    maturity_dir.mkdir(parents=True, exist_ok=True)
    (krd_dir / "manifest.json").write_text(
        json.dumps(
            {
                "report_date": "2026-04-30",
                "export_status": "decision_required",
                "export_summary": {
                    "remap_tenor_count": 1,
                    "nonzero_dv01_rows": 1,
                    "dv01_sum": "1.00000000",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (maturity_dir / "manifest.json").write_text(
        json.dumps(
            {
                "report_date": REPORT_DATE,
                "export_status": "blocked",
                "export_summary": {
                    "bond_missing_maturity_rows": 1,
                    "tyw_liability_missing_maturity_rows": 1,
                    "bond_missing_maturity_market_value": "1.00000000",
                    "tyw_liability_missing_maturity_principal": "1.00000000",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=REPORT_DATE,
        template_path=template,
        docs_root=docs_dir,
    )

    assert scorecard["current_score"] == "99.86 / 100"
    assert scorecard["remaining_gap"] == "0.14"
    assert scorecard["score_status"] == "blocked"
    assert scorecard["full_score_ready"] is False
    assert scorecard["score_blockers"] == [
        "approval_dependency_consistency_blocked",
        "owner_decision_intake_blocked",
    ]
    dependency_gate = scorecard["gates"]["approval_dependency_consistency"]
    assert dependency_gate["status"] == "blocked"
    assert dependency_gate["generated_owner_fields_boundaries"] == {
        "krd_contract_decision_manifest": None,
        "maturity_remediation_manifest": None,
    }
    for blocker in (
        "krd_contract_decision_manifest_report_date_mismatch",
        "krd_contract_decision_manifest_export_status_mismatch",
        "krd_contract_decision_manifest_remap_tenor_count_mismatch",
        "krd_contract_decision_manifest_nonzero_dv01_rows_mismatch",
        "krd_contract_decision_manifest_dv01_sum_mismatch",
        "krd_contract_decision_manifest_summary_csv_row_count_mismatch",
        "krd_contract_decision_manifest_detail_csv_row_count_mismatch",
        "maturity_remediation_manifest_export_status_mismatch",
        "maturity_remediation_manifest_bond_missing_maturity_rows_mismatch",
        "maturity_remediation_manifest_tyw_liability_missing_maturity_rows_mismatch",
        "maturity_remediation_manifest_bond_missing_maturity_market_value_mismatch",
        "maturity_remediation_manifest_tyw_liability_missing_maturity_principal_mismatch",
        "maturity_remediation_manifest_bond_csv_row_count_mismatch",
        "maturity_remediation_manifest_tyw_liability_csv_row_count_mismatch",
    ):
        assert blocker in dependency_gate["blockers"]
