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
SCRIPT = ROOT / "scripts" / "emit_kpi_performance_governance_record.py"


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


def test_kpi_performance_governance_record_dry_run_preflights_without_writing(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-09T00:00:00Z",
    )

    assert payload["scope"] == "kpi-performance-governance-record-generation"
    assert payload["mode"] == "dry-run"
    assert payload["target_stream"] == "cache_manifest"
    assert payload["target_path"] == str(governance_dir / "cache_manifest.jsonl")
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False
    assert payload["evidence_scope"]["authorizes_score_writes"] is False
    assert not governance_dir.exists()

    record = payload["record"]
    assert record == {
        "page_id": "GAP-KPI-PERFORMANCE-PAGE",
        "page_slug": "kpi-performance",
        "frontend_route": "/kpi",
        "primary_api": "/api/kpi/values/summary",
        "supporting_apis": [
            "/api/kpi/owners",
            "/api/kpi/metrics",
            "/api/kpi/values",
            "/api/kpi/values/batch",
            "/api/kpi/fetch_and_recalc",
            "/api/kpi/report",
        ],
        "report_date": "2026-05-31",
        "basis": "candidate_scoring_workbench",
        "source_surface": "kpi.values.summary",
        "tables_used": [
            "kpi_owner",
            "kpi_metric",
            "kpi_metric_value",
        ],
        "source_version": "sv_kpi_governance_sql_2026_05_31",
        "rule_version": "rv_kpi_scoring_v1",
        "cache_version": "cv_kpi_values_summary_v1",
        "cache_key": "kpi-performance:values-summary:2026:2026-05-31",
        "result_kind": "kpi.values.summary",
        "metric_id": "MTR-KPI-001",
        "created_at": "2026-06-09T00:00:00Z",
        "formal_use_allowed": False,
        "score_write_approval_allowed": False,
        "metric_dictionary_approval_captured": False,
        "business_owner_approval_captured": False,
    }

    preflight = payload["preflight"]
    assert preflight["page_id"] == "GAP-KPI-PERFORMANCE-PAGE"
    assert preflight["frontend_route"] == "/kpi"
    assert preflight["primary_api"] == "/api/kpi/values/summary"
    assert preflight["approval_status"] == "candidate_or_pending"
    assert preflight["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
    assert preflight["validation"]["validation_status"] == "ready_for_audit_review"
    assert preflight["validation"]["missing_required_fields"] == []
    assert preflight["validation"]["failed_required_field_groups"] == []
    assert preflight["evidence_scope"]["writes_governance_records"] is False
    assert preflight["evidence_scope"]["approves_metric_or_page"] is False


def test_kpi_performance_governance_record_explicit_write_is_mcp_validated(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-09T00:00:00Z",
        "--write",
    )

    stream_path = governance_dir / "cache_manifest.jsonl"
    assert payload["mode"] == "write"
    assert payload["target_path"] == str(stream_path)
    assert payload["evidence_scope"]["writes_governance_records"] is True
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
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
        ["kpi-performance"],
        ["cache_manifest"],
        max_results=10,
    )
    page = validation_payload["pages"][0]
    assert page["page_id"] == "GAP-KPI-PERFORMANCE-PAGE"
    assert page["validation_status"] == "direct_records_ready_for_audit_review"
    assert page["direct_record_validations"][0]["validation_status"] == "ready_for_audit_review"
    assert page["direct_record_validations"][0]["record_formal_use_allowed"] is False
    assert page["evidence_scope"]["approves_metric_or_page"] is False
    assert page["evidence_scope"]["proves_page_execution"] is False


def test_kpi_performance_governance_record_write_is_idempotent(tmp_path: Path) -> None:
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    (governance_dir / "cache_manifest.jsonl").write_text(
        json.dumps({"table_name": "kpi_owner"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args = (
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-09T00:00:00Z",
        "--write",
    )

    first_payload = _run_generator(*args)
    second_payload = _run_generator(*args)

    assert first_payload["record_write_status"] == "appended"
    assert second_payload["record_write_status"] == "already_exists"
    assert second_payload["existing_record_line"] == 2
    assert second_payload["record_key"] == {
        "page_id": "GAP-KPI-PERFORMANCE-PAGE",
        "primary_api": "/api/kpi/values/summary",
        "report_date": "2026-05-31",
        "cache_key": "kpi-performance:values-summary:2026:2026-05-31",
    }

    stream_path = governance_dir / "cache_manifest.jsonl"
    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written_records == [
        {"table_name": "kpi_owner"},
        first_payload["record"],
    ]
