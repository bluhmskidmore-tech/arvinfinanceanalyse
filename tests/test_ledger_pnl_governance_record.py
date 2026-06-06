from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.mcp.moss_project_mcp import (
    page_governance_record_validation,
    product_page_trace_bundles,
)

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
