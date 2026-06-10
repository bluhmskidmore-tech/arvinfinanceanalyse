from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.mcp.moss_project_mcp import (
    page_governance_record_validation,
    product_page_trace_bundles,
)
import scripts.refresh_ledger_pnl_direct_governance_record_snapshot as refresh_module

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "emit_ledger_pnl_governance_record.py"


def _run_generator(*args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return json.loads(completed.stdout)


def test_ledger_pnl_governance_record_dry_run_preflights_without_writing(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T12:01:14.993184Z",
    )

    assert payload["scope"] == "ledger-pnl-governance-record-generation"
    assert payload["mode"] == "dry-run"
    assert payload["target_stream"] == "cache_manifest"
    assert payload["target_path"] == str(governance_dir / "cache_manifest.jsonl")
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert not governance_dir.exists()

    record = payload["record"]
    assert record == {
        "page_id": "PAGE-LEDGER-PNL-001",
        "page_slug": "ledger-pnl",
        "frontend_route": "/ledger-pnl",
        "primary_api": "/api/ledger-pnl/summary",
        "report_date": "2026-05-31",
        "basis": "ledger",
        "source_surface": "ledger_pnl.summary",
        "tables_used": ["qdb_general_ledger_workbook"],
        "source_version": "sv_product_category_3353b116b9a6",
        "rule_version": "rv_ledger_pnl_v1",
        "cache_version": "cv_ledger_pnl_v1",
        "cache_key": "ledger_pnl.summary:2026-05-31:ALL",
        "result_kind": "ledger_pnl.summary",
        "created_at": "2026-06-05T12:01:14.993184Z",
        "formal_use_allowed": False,
    }

    preflight = payload["preflight"]
    assert preflight["page_id"] == "PAGE-LEDGER-PNL-001"
    assert preflight["approval_status"] == "candidate_or_pending"
    assert preflight["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
    assert preflight["validation"]["validation_status"] == "ready_for_audit_review"
    assert preflight["validation"]["missing_required_fields"] == []
    assert preflight["validation"]["failed_required_field_groups"] == []
    assert preflight["evidence_scope"]["writes_governance_records"] is False
    assert preflight["evidence_scope"]["approves_metric_or_page"] is False


def test_ledger_pnl_governance_record_explicit_write_is_mcp_validated(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T12:01:14.993184Z",
        "--write",
    )

    stream_path = governance_dir / "cache_manifest.jsonl"
    assert payload["mode"] == "write"
    assert payload["target_path"] == str(stream_path)
    assert payload["evidence_scope"]["writes_governance_records"] is True
    assert stream_path.is_file()

    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written_records == [payload["record"]]

    validation_payload = page_governance_record_validation(
        product_page_trace_bundles(),
        {"cache_manifest": stream_path},
        ["ledger-pnl"],
        ["cache_manifest"],
        max_results=10,
    )
    page = validation_payload["pages"][0]
    assert page["page_id"] == "PAGE-LEDGER-PNL-001"
    assert page["validation_status"] == "direct_records_ready_for_audit_review"
    assert page["direct_record_validations"][0]["validation_status"] == "ready_for_audit_review"
    assert page["direct_record_validations"][0]["record_formal_use_allowed"] is False
    assert page["evidence_scope"]["approves_metric_or_page"] is False
    assert page["evidence_scope"]["proves_page_execution"] is False


def test_ledger_pnl_governance_record_write_is_idempotent(tmp_path: Path) -> None:
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    (governance_dir / "cache_manifest.jsonl").write_text(
        json.dumps({"table_name": "qdb_general_ledger_workbook"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args = (
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T12:01:14.993184Z",
        "--write",
    )

    first_payload = _run_generator(*args)
    second_payload = _run_generator(*args)

    assert first_payload["record_write_status"] == "appended"
    assert second_payload["record_write_status"] == "already_exists"
    assert second_payload["existing_record_line"] == 2
    assert second_payload["record_key"] == {
        "page_id": "PAGE-LEDGER-PNL-001",
        "primary_api": "/api/ledger-pnl/summary",
        "report_date": "2026-05-31",
        "cache_key": "ledger_pnl.summary:2026-05-31:ALL",
    }

    stream_path = governance_dir / "cache_manifest.jsonl"
    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written_records == [
        {"table_name": "qdb_general_ledger_workbook"},
        first_payload["record"],
    ]


def _stub_readiness() -> dict[str, object]:
    return {
        "overall_status": "static-pass",
        "formal_use_allowed": False,
        "business_owner_approval_status": {
            "closure_approved": False,
            "business_owner_approval_captured": False,
            "approval_status": "pending",
            "approval_action_item_count": 11,
        },
        "catalog_date_evidence": {
            "status": "incomplete",
            "table_count": 3,
            "present_table_count": 2,
            "date_sampled_table_count": 1,
            "sampled_table_names": [
                "qdb_general_ledger_workbook",
                "ledger_import_batch",
                "ledger_raw_row",
            ],
            "table_evidence": [
                {
                    "table_name": "qdb_general_ledger_workbook",
                    "status": "unknown_table",
                },
                {
                    "table_name": "ledger_raw_row",
                    "status": "present_no_date_column",
                },
            ],
        },
        "governance_record_validation": {
            "status": "missing_direct_records",
            "ready_record_count": 0,
            "incomplete_record_count": 0,
            "direct_record_count": 0,
            "expanded_anchor_record_count": 0,
        },
        "audit_review": {
            "status": "blocked_by_record_gaps",
            "closure_approved": False,
            "checks": [
                {
                    "name": "direct_page_api_record_fields",
                    "status": "blocked",
                },
            ],
        },
        "residual_gaps": [
            "direct page-keyed governance records are still required before treating this as proof of a specific page/API execution.",
        ],
    }


def test_ledger_pnl_direct_governance_snapshot_refresh_is_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    governance_dir = tmp_path / "governance"
    monkeypatch.setattr(
        refresh_module,
        "build_page_readiness_report",
        lambda _page_slug: _stub_readiness(),
    )

    snapshot = refresh_module.build_snapshot(
        generated_at="2026-06-10T20:30:00+08:00",
        governance_dir=governance_dir,
    )

    assert snapshot["report_kind"] == "ledger_pnl_direct_governance_record_snapshot"
    assert snapshot["generated_at"] == "2026-06-10T20:30:00+08:00"
    assert snapshot["refresh_command"] == (
        "python scripts\\refresh_ledger_pnl_direct_governance_record_snapshot.py"
    )
    assert snapshot["status"]["overall"] == "dry_run_candidate_only"
    assert snapshot["status"]["writes_governance_records"] is False
    assert snapshot["dry_run_result"]["record_write_status"] == "not_requested"
    assert snapshot["dry_run_result"]["existing_record_line"] is None
    assert snapshot["written_record_search"]["matches"] == {
        "PAGE-LEDGER-PNL-001": 0,
        "/api/ledger-pnl/summary": 0,
        "ledger_pnl.summary:2026-05-31:ALL": 0,
    }
    assert snapshot["page_readiness_result"]["formal_use_allowed"] is False
    assert snapshot["page_readiness_result"]["closure_approved"] is False
    assert "does not write governance records" in snapshot["boundary"]
    assert not governance_dir.exists()


def test_ledger_pnl_direct_governance_snapshot_refresh_can_locate_existing_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    record = refresh_module.build_record("2026-06-10T20:30:00+08:00")
    (governance_dir / "cache_manifest.jsonl").write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        refresh_module,
        "build_page_readiness_report",
        lambda _page_slug: _stub_readiness(),
    )

    snapshot = refresh_module.build_snapshot(
        generated_at="2026-06-10T20:30:00+08:00",
        governance_dir=governance_dir,
    )

    assert snapshot["status"]["overall"] == "written_record_located"
    assert snapshot["status"]["writes_governance_records"] is False
    assert snapshot["dry_run_result"]["record_write_status"] == "not_requested"
    assert snapshot["dry_run_result"]["existing_record_line"] == 1
    assert snapshot["written_record_search"]["matches"] == {
        "PAGE-LEDGER-PNL-001": 1,
        "/api/ledger-pnl/summary": 1,
        "ledger_pnl.summary:2026-05-31:ALL": 1,
    }


def test_ledger_pnl_direct_governance_snapshot_refresh_cli_writes_only_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "snapshot.json"
    governance_dir = tmp_path / "governance"
    monkeypatch.setattr(
        refresh_module,
        "build_page_readiness_report",
        lambda _page_slug: _stub_readiness(),
    )

    exit_code = refresh_module.main(
        [
            "--generated-at",
            "2026-06-10T20:30:00+08:00",
            "--governance-dir",
            str(governance_dir),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["generated_at"] == "2026-06-10T20:30:00+08:00"
    assert payload["status"]["writes_governance_records"] is False
    assert payload["dry_run_result"]["record_write_status"] == "not_requested"
    assert not governance_dir.exists()


def test_ledger_pnl_direct_governance_snapshot_strict_gate_rejects_missing_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "snapshot.json"
    governance_dir = tmp_path / "governance"
    monkeypatch.setattr(
        refresh_module,
        "build_page_readiness_report",
        lambda _page_slug: _stub_readiness(),
    )

    exit_code = refresh_module.main(
        [
            "--generated-at",
            "2026-06-10T20:30:00+08:00",
            "--governance-dir",
            str(governance_dir),
            "--output",
            str(output_path),
            "--require-written-record-located",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"]["overall"] == "dry_run_candidate_only"
    assert payload["dry_run_result"]["record_write_status"] == "not_requested"
    assert payload["dry_run_result"]["existing_record_line"] is None
    assert not governance_dir.exists()


def test_ledger_pnl_direct_governance_snapshot_strict_gate_accepts_existing_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "snapshot.json"
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    record = refresh_module.build_record("2026-06-10T20:30:00+08:00")
    stream_path = governance_dir / "cache_manifest.jsonl"
    stream_path.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        refresh_module,
        "build_page_readiness_report",
        lambda _page_slug: _stub_readiness(),
    )

    exit_code = refresh_module.main(
        [
            "--generated-at",
            "2026-06-10T20:30:00+08:00",
            "--governance-dir",
            str(governance_dir),
            "--output",
            str(output_path),
            "--require-written-record-located",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert exit_code == 0
    assert payload["status"]["overall"] == "written_record_located"
    assert payload["dry_run_result"]["record_write_status"] == "not_requested"
    assert payload["dry_run_result"]["existing_record_line"] == 1
    assert written_records == [record]
