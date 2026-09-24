from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from scripts.mcp.moss_project_mcp import (
    page_governance_record_validation,
    page_trace_bundle,
    product_page_trace_bundles,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "emit_pnl_by_business_insights_governance_record.py"


def _load_emitter() -> ModuleType:
    assert SCRIPT.is_file(), f"Missing Insights governance emitter: {SCRIPT}"
    spec = importlib.util.spec_from_file_location(
        "emit_pnl_by_business_insights_governance_record",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _live_envelope() -> dict[str, object]:
    return {
        "result_meta": {
            "trace_id": "tr_pnl_by_business_insights_live_a",
            "basis": "formal",
            "result_kind": "pnl.by_business_insights",
            "formal_use_allowed": True,
            "source_version": "sv_pnl_by_business_insights_live_a",
            "vendor_version": "vv_none",
            "rule_version": "rv_pnl_by_business_insights_v2",
            "cache_version": "cv_pnl_by_business_insights_v2",
            "cache_key": None,
            "quality_flag": "warning",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "requested_report_date": "2026-06-30",
            "resolved_report_date": "2026-06-30",
            "as_of_date": "2026-06-30",
            "date_basis": "formal_report_date_cutoff",
            "fallback_date": None,
            "generated_at": "2026-07-16T08:00:49Z",
            "filters_applied": {"year": 2026, "as_of_date": "2026-06-30"},
            "tables_used": [
                "ZQTZ_ASSET_BOND_ROWS",
                "fact_formal_pnl_fi",
                "fact_formal_zqtz_balance_daily",
                "fact_nonstd_pnl_bridge",
                "pnl_by_business_adjustments",
            ],
            "evidence_rows": 12,
            "source_surface": "formal_pnl",
        },
        "result": {
            "result_version": "v2",
            "year": 2026,
            "as_of_date": "2026-06-30",
            "component_evidence": [
                {
                    "component": component,
                    "requested_report_date": "2026-06-30",
                    "resolved_report_date": "2026-06-30",
                    "fallback_mode": "none",
                    "trace_id": f"tr_{component}",
                    "source_version": f"sv_{component}",
                    "rule_version": "rv_pnl_phase2_materialize_v3",
                    "cache_version": "cv_pnl_formal__rv_pnl_phase2_materialize_v3",
                    "tables_used": ["fact_formal_pnl_fi"],
                    "formal_source_admitted": True,
                    "admission_reason": None,
                }
                for component in (
                    "current_ytd",
                    "baseline_ytd",
                    "monthly_2025",
                    "monthly_2026",
                )
            ],
        },
    }


@pytest.mark.parametrize(
    "route_alias",
    ["pnl-by-business-insights", "/pnl-by-business-insights"],
)
def test_insights_detail_route_resolves_to_the_governing_page_bundle(route_alias: str) -> None:
    bundle = page_trace_bundle(product_page_trace_bundles(), route_alias)

    assert bundle["page_id"] == "PAGE-PNL-BY-BUSINESS-001"
    assert bundle["page_slug"] == "pnl-by-business"
    assert bundle["primary_api"] == "/api/pnl/by-business-insights"


def _run_main(
    module: ModuleType,
    *,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    governance_dir: Path,
    write: bool = False,
) -> tuple[int, dict[str, object]]:
    monkeypatch.setattr(
        module,
        "fetch_live_envelope",
        lambda *, year, as_of_date: _live_envelope(),
    )
    argv = [
        "--governance-dir",
        str(governance_dir),
        "--year",
        "2026",
        "--as-of-date",
        "2026-06-30",
        "--created-at",
        "2026-07-16T08:01:00Z",
    ]
    if write:
        argv.append("--write")
    exit_code = module.main(argv)
    return exit_code, json.loads(capsys.readouterr().out)


def test_insights_governance_record_dry_run_uses_exact_live_api_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_emitter()
    governance_dir = tmp_path / "governance"

    exit_code, payload = _run_main(
        module,
        monkeypatch=monkeypatch,
        capsys=capsys,
        governance_dir=governance_dir,
    )

    assert exit_code == 0
    assert payload["scope"] == "pnl-by-business-insights-governance-record-generation"
    assert payload["mode"] == "dry-run"
    assert payload["target_stream"] == "cache_manifest"
    assert payload["evidence_scope"] == {
        "writes_governance_records": False,
        "approves_metric_or_page": False,
        "proves_page_execution_completeness": False,
        "validates_required_fields": True,
        "captures_business_owner_approval": False,
        "uses_live_api_response": True,
    }
    assert not governance_dir.exists()

    record = payload["record"]
    assert record["page_id"] == "PAGE-PNL-BY-BUSINESS-001"
    assert record["page_slug"] == "pnl-by-business"
    assert record["frontend_route"] == "/pnl-by-business"
    assert record["detail_frontend_route"] == "/pnl-by-business-insights"
    assert record["primary_api"] == "/api/pnl/by-business-insights"
    assert record["api_query"] == (
        "/api/pnl/by-business-insights?year=2026&as_of_date=2026-06-30"
    )
    assert record["report_date"] == "2026-06-30"
    assert record["run_id"] == "tr_pnl_by_business_insights_live_a"
    assert record["formal_use_allowed"] is True
    assert record["result_kind"] == "pnl.by_business_insights"
    assert record["metric_ids"] == [f"MTR-PNLBIZ-{index:03d}" for index in range(1, 8)]
    assert record["golden_sample_id"] == "GS-PNL-BUSINESS-INSIGHTS-A"
    assert [row["component"] for row in record["component_admission_evidence"]] == [
        "current_ytd",
        "baseline_ytd",
        "monthly_2025",
        "monthly_2026",
    ]
    assert all(row["formal_source_admitted"] is True for row in record["component_admission_evidence"])
    assert record["ui_api_payload_evidence"] == "live_api_trace:tr_pnl_by_business_insights_live_a"
    assert record["browser_smoke_evidence"].startswith(
        "frontend/tests/playwright/pnl-by-business-insights-smoke.spec.mjs::"
    )
    assert record["evidence_boundary"] == (
        "Direct exact-cutoff API response evidence only; not independent source-fact certification "
        "or page-execution completeness proof."
    )

    preflight = payload["preflight"]
    assert preflight["page_id"] == "PAGE-PNL-BY-BUSINESS-001"
    assert preflight["approval_status"] == "formal_or_governed"
    assert preflight["validation"]["validation_status"] == "ready_for_audit_review"
    assert preflight["validation"]["missing_required_fields"] == []
    assert preflight["validation"]["failed_required_field_groups"] == []
    assert preflight["evidence_scope"]["approves_metric_or_page"] is False


def test_insights_governance_record_explicit_write_is_mcp_validated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_emitter()
    governance_dir = tmp_path / "governance"

    exit_code, payload = _run_main(
        module,
        monkeypatch=monkeypatch,
        capsys=capsys,
        governance_dir=governance_dir,
        write=True,
    )

    assert exit_code == 0
    assert payload["mode"] == "write"
    assert payload["record_write_status"] == "appended"
    assert payload["evidence_scope"]["writes_governance_records"] is True

    stream_path = governance_dir / "cache_manifest.jsonl"
    validation_payload = page_governance_record_validation(
        product_page_trace_bundles(),
        {"cache_manifest": stream_path},
        ["pnl-by-business"],
        ["cache_manifest"],
        max_results=10,
    )
    page = validation_payload["pages"][0]
    assert page["validation_status"] == "direct_records_ready_for_audit_review"
    assert page["direct_record_validations"][0]["validation_status"] == "ready_for_audit_review"
    assert page["direct_record_validations"][0]["record_formal_use_allowed"] is True
    assert page["evidence_scope"]["approves_metric_or_page"] is False
    assert page["evidence_scope"]["proves_page_execution"] is False


def test_insights_governance_record_write_is_idempotent_for_same_source_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_emitter()
    governance_dir = tmp_path / "governance"

    first_code, first_payload = _run_main(
        module,
        monkeypatch=monkeypatch,
        capsys=capsys,
        governance_dir=governance_dir,
        write=True,
    )
    second_code, second_payload = _run_main(
        module,
        monkeypatch=monkeypatch,
        capsys=capsys,
        governance_dir=governance_dir,
        write=True,
    )

    assert first_code == second_code == 0
    assert first_payload["record_write_status"] == "appended"
    assert second_payload["record_write_status"] == "already_exists"
    assert second_payload["existing_record_line"] == 1
    stream_path = governance_dir / "cache_manifest.jsonl"
    assert len([line for line in stream_path.read_text(encoding="utf-8").splitlines() if line]) == 1


def test_insights_governance_record_rejects_fallback_or_non_exact_cutoff() -> None:
    module = _load_emitter()
    envelope = _live_envelope()
    meta = envelope["result_meta"]
    assert isinstance(meta, dict)
    meta["fallback_mode"] = "latest_snapshot"
    meta["resolved_report_date"] = "2026-05-31"

    with pytest.raises(ValueError, match="exact-cutoff"):
        module.build_record(
            envelope,
            year=2026,
            as_of_date="2026-06-30",
            created_at="2026-07-16T08:01:00Z",
        )


def test_insights_governance_record_rejects_non_admitted_component() -> None:
    module = _load_emitter()
    envelope = _live_envelope()
    result = envelope["result"]
    assert isinstance(result, dict)
    component_evidence = result["component_evidence"]
    assert isinstance(component_evidence, list)
    component_evidence[1]["formal_source_admitted"] = False
    component_evidence[1]["admission_reason"] = "fallback_date"

    with pytest.raises(ValueError, match="component admission"):
        module.build_record(
            envelope,
            year=2026,
            as_of_date="2026-06-30",
            created_at="2026-07-16T08:01:00Z",
        )
