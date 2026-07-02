from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module


def _strategy_envelope() -> dict[str, Any]:
    return {
        "result_meta": {
            "trace_id": "tr_livermore_strategy_test",
            "basis": "analytical",
            "result_kind": "market_data.livermore",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "source_version": "sv_livermore_test",
            "vendor_version": "vv_livermore_test",
            "rule_version": "rv_livermore_strategy_v1",
            "cache_version": "cv_livermore_strategy_v1",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": 7,
            "filters_applied": {"as_of_date": "2026-06-26"},
            "source_surface": "market_data",
        },
        "result": {
            "as_of_date": "2026-06-26",
            "requested_as_of_date": "2026-06-26",
            "basis": "analytical",
            "market_gate": {"state": "WARM", "passed": 2, "required": 3},
            "sector_rank": {
                "items": [
                    {"sector_code": "801010", "sector_name": "银行", "rank": 1, "score": 0.82},
                ],
            },
            "stock_candidates": {
                "items": [
                    {"stock_code": "000001.SZ", "stock_name": "平安银行", "rank": 1},
                ],
            },
            "risk_exit": {"items": [], "watch_items": []},
            "data_gaps": [],
            "diagnostics": [],
            "supported_outputs": ["market_gate", "sector_rank", "stock_candidates"],
            "unsupported_outputs": [],
        },
    }


def test_build_stock_analysis_workbench_envelope_wraps_livermore_strategy_as_observational_contract() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )

    envelope = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=_strategy_envelope(),
        requested_as_of_date="2026-06-26",
        include="main,signal_confluence",
        sector_window_days=20,
        top_k=2,
    )

    meta = envelope["result_meta"]
    result = envelope["result"]

    assert meta["result_kind"] == "market_data.stock_analysis.workbench"
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["source_surface"] == "market_data"
    assert meta["source_version"] == "sv_livermore_test"
    assert meta["tables_used"] == ["choice_stock_daily_observation"]
    assert meta["evidence_rows"] == 7

    assert result["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
    assert result["route"] == "/stock-analysis"
    assert result["contract_status"] == "observational_only"
    assert result["formal_use_allowed"] is False
    assert result["as_of_date"] == "2026-06-26"
    assert result["decision_summary"]["gate_state"] == "WARM"
    assert result["decision_summary"]["top_review_stock_code"] == "000001.SZ"
    assert result["first_screen"]["review_queue"][0]["stock_name"] == "平安银行"
    assert result["first_screen"]["sector_snapshot"][0]["sector_name"] == "银行"
    assert result["modules"]["main"]["status"] == "ready"
    assert result["modules"]["signal_confluence"]["status"] == "deferred"
    assert result["links"]["stock_detail"] == "/ui/market-data/livermore/stock-detail"
    assert result["endpoint_evidence"][0]["endpoint"] == "/ui/market-data/livermore"

    serialized = json.dumps(result, ensure_ascii=False)
    assert "买入建议" not in serialized
    assert "卖出建议" not in serialized
    assert "下单" not in serialized


def test_stock_analysis_workbench_route_validates_date_and_delegates_to_service(monkeypatch: pytest.MonkeyPatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    calls: list[dict[str, Any]] = []

    def fake_workbench(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "result_meta": {
                "trace_id": "tr_stock_analysis_workbench_test",
                "basis": "analytical",
                "result_kind": "market_data.stock_analysis.workbench",
                "formal_use_allowed": False,
                "scenario_flag": False,
                "source_version": "sv_test",
                "vendor_version": "vv_test",
                "rule_version": "rv_stock_analysis_workbench_v1",
                "cache_version": "cv_stock_analysis_workbench_v1",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": [],
                "evidence_rows": 0,
                "source_surface": "market_data",
            },
            "result": {"route": "/stock-analysis"},
        }

    monkeypatch.setattr(route_module, "stock_analysis_workbench_envelope", fake_workbench, raising=False)
    monkeypatch.setattr(route_module, "_ensure_livermore_read_allowed", lambda **_kwargs: None)

    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[route_module.get_auth_context] = lambda: route_module.AuthContext(
        user_id="route-test",
        role="viewer",
        identity_source="test",
    )
    client = TestClient(app)

    response = client.get(
        "/ui/market-data/stock-analysis/workbench",
        params={
            "as_of_date": "2026-06-26",
            "include": "main,signal_confluence",
            "sector_window_days": 30,
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["route"] == "/stock-analysis"
    assert calls
    assert calls[0]["as_of_date"] == "2026-06-26"
    assert calls[0]["include"] == "main,signal_confluence"
    assert calls[0]["sector_window_days"] == 30
    assert calls[0]["top_k"] == 3

    invalid = client.get(
        "/ui/market-data/stock-analysis/workbench",
        params={"as_of_date": "bad-date"},
    )

    assert invalid.status_code == 422
    assert len(calls) == 1
