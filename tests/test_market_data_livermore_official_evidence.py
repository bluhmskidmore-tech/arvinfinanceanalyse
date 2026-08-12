from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.routes import market_data_livermore as route_module


def _client(tmp_path, monkeypatch, *, guard=None, service_fn=None) -> TestClient:
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "moss.duckdb"),
    )
    monkeypatch.setattr(
        route_module,
        "_ensure_livermore_read_allowed",
        guard or (lambda **_kwargs: None),
    )
    monkeypatch.setattr(
        route_module,
        "stock_official_evidence_envelope",
        service_fn
        or (
            lambda **_kwargs: {
                "result_meta": {
                    "basis": "analytical",
                    "formal_use_allowed": False,
                    "scenario_flag": False,
                    "result_kind": "market_data.stock_analysis.official_evidence",
                    "quality_flag": "ok",
                    "source_version": "sv_route_stub",
                    "vendor_version": "vv_route_stub",
                    "rule_version": "rv_route_stub",
                    "cache_version": "cv_route_stub",
                    "vendor_status": "ok",
                    "fallback_mode": "none",
                    "evidence_rows": 0,
                    "tables_used": [],
                    "filters_applied": {},
                    "as_of_date": "2026-07-26",
                    "date_basis": "publish_date_lte_requested_as_of_date",
                },
                "result": {
                    "basis": "analytical",
                    "contract_status": "observational_only",
                    "formal_use_allowed": False,
                    "stock_code": "000001.SZ",
                    "requested_as_of_date": "2026-07-26",
                    "as_of_date": "2026-07-26",
                    "date_basis": "publish_date_lte_requested_as_of_date",
                    "state": "missing",
                    "excluded_future_rows": 0,
                    "source_statuses": {},
                    "announcements": [],
                    "financial_reports": [],
                    "warnings": [],
                },
            }
        ),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[route_module.get_auth_context] = lambda: route_module.AuthContext(
        user_id="route-test",
        role="viewer",
        identity_source="test",
    )
    return TestClient(app)


def test_official_evidence_route_calls_service_without_cache_and_sets_server_timing(
    tmp_path, monkeypatch
) -> None:
    calls: list[dict[str, object]] = []

    def service_fn(**kwargs):
        calls.append(kwargs)
        return {
            "result_meta": {
                "basis": "analytical",
                "formal_use_allowed": False,
                "scenario_flag": False,
                "result_kind": "market_data.stock_analysis.official_evidence",
                "quality_flag": "ok",
                "source_version": "sv_route",
                "vendor_version": "vv_route",
                "rule_version": "rv_route",
                "cache_version": "cv_route",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "evidence_rows": 1,
                "tables_used": [],
                "filters_applied": {},
                "as_of_date": kwargs["as_of_date"].isoformat(),
                "date_basis": "publish_date_lte_requested_as_of_date",
            },
            "result": {
                "basis": "analytical",
                "contract_status": "observational_only",
                "formal_use_allowed": False,
                "stock_code": kwargs["stock_code"],
                "requested_as_of_date": kwargs["as_of_date"].isoformat(),
                "as_of_date": kwargs["as_of_date"].isoformat(),
                "date_basis": "publish_date_lte_requested_as_of_date",
                "state": "ok",
                "excluded_future_rows": 0,
                "source_statuses": {},
                "announcements": [],
                "financial_reports": [],
                "warnings": [],
            },
        }

    client = _client(tmp_path, monkeypatch, service_fn=service_fn)
    first = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "000001.SZ", "as_of_date": "2026-04-10", "limit_per_type": 7},
    )
    second = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "000001.SZ", "as_of_date": "2026-04-10", "limit_per_type": 7},
    )
    default_as_of_before = date.today()
    third = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "000001.SZ"},
    )
    default_as_of_after = date.today()

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert len(calls) == 3
    assert calls[0]["stock_code"] == "000001.SZ"
    assert calls[0]["as_of_date"] == date(2026, 4, 10)
    assert calls[0]["limit_per_type"] == 7
    # 路由默认 as_of=today：用请求前后的日期窗口断言，避免跨午夜双读翻车。
    assert calls[2]["as_of_date"] in {default_as_of_before, default_as_of_after}
    assert "official-evidence" in first.headers["Server-Timing"]
    assert "query;dur=" in first.headers["Server-Timing"]


def test_official_evidence_route_rejects_invalid_inputs(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    invalid_stock = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "bad/code"},
    )
    invalid_date = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "000001.SZ", "as_of_date": "bad-date"},
    )
    invalid_limit = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "000001.SZ", "limit_per_type": 21},
    )

    assert invalid_stock.status_code == 422
    assert invalid_date.status_code == 422
    assert invalid_limit.status_code == 422


def test_official_evidence_route_requires_read_scope(tmp_path, monkeypatch) -> None:
    client = _client(
        tmp_path,
        monkeypatch,
        guard=lambda **_kwargs: (_ for _ in ()).throw(HTTPException(status_code=403, detail="forbidden")),
    )

    response = client.get(
        "/ui/market-data/stock-analysis/official-evidence",
        params={"stock_code": "000001.SZ"},
    )

    assert response.status_code == 403
