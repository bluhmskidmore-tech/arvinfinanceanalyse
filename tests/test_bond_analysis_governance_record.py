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
SCRIPT = ROOT / "scripts" / "emit_bond_analysis_governance_record.py"


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


def test_bond_analysis_governance_record_dry_run_preflights_without_writing(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-06T00:00:00Z",
    )

    assert payload["scope"] == "bond-analysis-governance-record-generation"
    assert payload["mode"] == "dry-run"
    assert payload["target_stream"] == "cache_manifest"
    assert payload["target_path"] == str(governance_dir / "cache_manifest.jsonl")
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert payload["evidence_scope"]["approves_metric_or_page"] is False
    assert payload["evidence_scope"]["captures_business_owner_approval"] is False
    assert not governance_dir.exists()

    record = payload["record"]
    assert record == {
        "page_id": "PAGE-BOND-ANALYSIS-001",
        "page_slug": "bond-analysis",
        "frontend_route": "/bond-analysis",
        "primary_api": "/api/bond-analytics/action-attribution",
        "report_date": "2026-03-31",
        "basis": "analytical",
        "source_surface": "bond_analytics",
        "tables_used": ["fact_formal_bond_analytics_daily"],
        "source_version": "sv_bond_analysis_action_attr_gs_a",
        "rule_version": "rv_bond_analytics_formal_materialize_v2",
        "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2",
        "cache_key": "bond-analysis:action-attribution:2026-03-31:MoM",
        "result_kind": "bond_analytics.action_attribution",
        "golden_sample_id": "GS-BOND-ANALYSIS-ACTION-ATTR-A",
        "created_at": "2026-06-06T00:00:00Z",
        "formal_use_allowed": False,
    }

    preflight = payload["preflight"]
    assert preflight["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert preflight["frontend_route"] == "/bond-analysis"
    assert preflight["primary_api"] == "/api/bond-analytics/action-attribution"
    assert preflight["approval_status"] == "candidate_or_pending"
    assert preflight["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
    assert preflight["validation"]["validation_status"] == "ready_for_audit_review"
    assert preflight["validation"]["missing_required_fields"] == []
    assert preflight["validation"]["failed_required_field_groups"] == []
    assert preflight["evidence_scope"]["writes_governance_records"] is False
    assert preflight["evidence_scope"]["approves_metric_or_page"] is False


def test_bond_analysis_governance_record_explicit_write_is_mcp_validated(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-06T00:00:00Z",
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
        ["bond-analysis"],
        ["cache_manifest"],
        max_results=10,
    )
    page = validation_payload["pages"][0]
    assert page["page_id"] == "PAGE-BOND-ANALYSIS-001"
    assert page["validation_status"] == "direct_records_ready_for_audit_review"
    assert page["direct_record_validations"][0]["validation_status"] == "ready_for_audit_review"
    assert page["direct_record_validations"][0]["record_formal_use_allowed"] is False
    assert page["evidence_scope"]["approves_metric_or_page"] is False
    assert page["evidence_scope"]["proves_page_execution"] is False


def test_bond_analysis_governance_record_write_is_idempotent(tmp_path: Path) -> None:
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    (governance_dir / "cache_manifest.jsonl").write_text(
        json.dumps({"table_name": "fact_formal_bond_analytics_daily"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args = (
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-06T00:00:00Z",
        "--write",
    )

    first_payload = _run_generator(*args)
    second_payload = _run_generator(*args)

    assert first_payload["record_write_status"] == "appended"
    assert second_payload["record_write_status"] == "already_exists"
    assert second_payload["existing_record_line"] == 2
    assert second_payload["record_key"] == {
        "page_id": "PAGE-BOND-ANALYSIS-001",
        "primary_api": "/api/bond-analytics/action-attribution",
        "report_date": "2026-03-31",
        "cache_key": "bond-analysis:action-attribution:2026-03-31:MoM",
    }

    stream_path = governance_dir / "cache_manifest.jsonl"
    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written_records == [
        {"table_name": "fact_formal_bond_analytics_daily"},
        first_payload["record"],
    ]
