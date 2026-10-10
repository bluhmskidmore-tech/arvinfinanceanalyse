"""Synthetic workbook HTTP/null contracts; repository and authorization are mocked."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core_finance.balance_analysis_workbook import _build_campisi_table
from tests.test_balance_campisi_fin002_completeness import _asset, _benchmark


pytestmark = pytest.mark.unit
REPORT_DATE = "2026-09-30"


@pytest.fixture
def workbook_service(monkeypatch):
    from backend.app.services import balance_analysis_service as service

    state = {"rows": [], "lineage": {
        "source_version": "sv_synthetic_only",
        "rule_version": "rv_synthetic_formal_fact",
        "cache_version": "cv_synthetic_formal_fact",
        "vendor_version": "vv_none",
    }}

    def synthetic_payload(**_kwargs):
        return {
            "report_date": REPORT_DATE,
            "position_scope": "all",
            "currency_basis": "CNY",
            "cards": [],
            "tables": [_build_campisi_table(state["rows"])],
        }, state["lineage"]

    monkeypatch.setattr(service, "_duckdb_storage_identity", lambda _path: None)
    monkeypatch.setattr(service, "_build_balance_workbook_payload", synthetic_payload)
    return service, state


def test_real_workbook_route_preserves_null_and_known_amounts_in_json(workbook_service, monkeypatch, tmp_path) -> None:
    from backend.app.api.routes import balance_analysis as routes

    service, state = workbook_service
    state["rows"] = [_benchmark(), _asset("known", Decimal("4")), _asset("unknown", None)]
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(
        duckdb_path=tmp_path / "unused.duckdb", governance_path=tmp_path / "unused-governance",
    ))
    monkeypatch.setattr(routes, "_ensure_balance_analysis_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "timed_api_call", lambda _path, callback: callback())
    monkeypatch.setattr(routes, "balance_analysis_workbook_envelope", service.balance_analysis_workbook_envelope)
    app = FastAPI()
    app.dependency_overrides[routes.get_auth_context] = lambda: object()
    app.include_router(routes.router)

    with TestClient(app) as client:
        response = client.get("/ui/balance-analysis/workbook", params={"report_date": REPORT_DATE})
    assert response.status_code == 200
    payload = response.json()
    result = next(row for row in payload["result"]["tables"][0]["rows"] if row["bond_type"] == "企业债")
    for key in ("coupon_income_amount", "weighted_rate_pct", "spread_bp", "spread_income_amount", "share_of_income", "total_coupon_income_amount"):
        assert result[key] is None
    assert Decimal(result["known_coupon_income_amount"]) == Decimal("400")
    assert Decimal(result["known_spread_income_amount"]) == Decimal("100")
    assert Decimal(result["coupon_known_abs_face_amount"]) == Decimal("10000")
    assert Decimal(result["coupon_total_abs_face_amount"]) == Decimal("20000")
    assert result["coupon_coverage_status"] == "部分缺失"
    meta = payload["result_meta"]
    assert meta["quality_flag"] == "warning"
    assert meta["source_version"] == "sv_synthetic_only"
    assert meta["rule_version"] == f"rv_synthetic_formal_fact|{service.BALANCE_WORKBOOK_QUERY_RULE_VERSION}"
    assert meta["cache_version"] == f"cv_synthetic_formal_fact|{service.BALANCE_WORKBOOK_QUERY_CACHE_VERSION}"
    assert service.RULE_VERSION == "rv_balance_analysis_formal_materialize_v1"


@pytest.mark.parametrize("profile", ["empty", "zero-face", "complete", "missing-coupon", "missing-benchmark", "partial-benchmark"])
def test_workbook_quality_marks_only_applicable_missing_income_evidence(workbook_service, profile) -> None:
    service, state = workbook_service
    rows_by_profile = {
        "empty": [],
        "zero-face": [_asset("zero", None, face=Decimal("0"))],
        "complete": [_benchmark(), _asset("known", Decimal("4"))],
        "missing-coupon": [_benchmark(), _asset("unknown", None)],
        "missing-benchmark": [_asset("known", Decimal("4"))],
        "partial-benchmark": [_benchmark(), _asset("unknown-policy", None, bond_type="政策性金融债"), _asset("known", Decimal("4"))],
    }
    state["rows"] = rows_by_profile[profile]
    envelope = service.balance_analysis_workbook_envelope(
        duckdb_path="unused", governance_dir="unused", report_date=REPORT_DATE,
    )
    expected_warning = profile in {"missing-coupon", "missing-benchmark", "partial-benchmark"}
    assert (envelope["result_meta"]["quality_flag"] == "warning") == expected_warning


@pytest.mark.parametrize("missing_field", ["source_version", "rule_version"])
def test_workbook_query_identity_does_not_rescue_missing_formal_lineage(workbook_service, missing_field) -> None:
    service, state = workbook_service
    state["lineage"].pop(missing_field)
    with pytest.raises(RuntimeError, match=missing_field):
        service.balance_analysis_workbook_envelope(
            duckdb_path="unused", governance_dir="unused", report_date=REPORT_DATE,
        )


def test_query_versions_invalidate_both_workbook_cache_keys_only(workbook_service, monkeypatch, tmp_path) -> None:
    service, _state = workbook_service
    monkeypatch.setattr(service, "_duckdb_storage_identity", lambda _path: ("synthetic", 1, 1))
    monkeypatch.setattr(service, "_resolve_governance_backend_mode", lambda _mode: "jsonl")
    monkeypatch.setattr(service, "_jsonl_file_cache_key", lambda _path: None)
    args = {
        "duckdb_path": "unused", "governance_dir": str(tmp_path),
        "report_date": REPORT_DATE, "position_scope": "all", "currency_basis": "CNY",
    }
    before = service._balance_workbook_payload_cache_key(**args)
    overview_before = service._balance_analysis_cache_key("overview", "unused", str(tmp_path), REPORT_DATE)
    monkeypatch.setattr(service, "BALANCE_WORKBOOK_QUERY_RULE_VERSION", "rv_query_new")
    after = service._balance_workbook_payload_cache_key(**args)
    assert before != after
    assert service._balance_analysis_cache_key("overview", "unused", str(tmp_path), REPORT_DATE) == overview_before

    captured = []
    monkeypatch.setattr(service, "_balance_analysis_cache_key", lambda *parts: captured.append(parts) or None)
    monkeypatch.setattr(service, "_balance_analysis_workbook_envelope_uncached", lambda **_kwargs: {})
    service.balance_analysis_workbook_envelope(**args)
    assert captured[0][-2:] == ("rv_query_new", service.BALANCE_WORKBOOK_QUERY_CACHE_VERSION)
