from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module


def test_balance_movement_refresh_api_returns_completed_payload_without_internal_task_fields(
    tmp_path,
    monkeypatch,
):
    route_mod = load_module(
        "backend.app.api.routes.accounting_asset_movement",
        "backend/app/api/routes/accounting_asset_movement.py",
    )
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setattr(
        route_mod,
        "refresh_accounting_asset_movement",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "cache_key": "accounting_asset_movement.monthly",
            "report_date": "2026-02-28",
            "currency_basis": "CNX",
            "row_count": 3,
            "source_version": "sv-movement",
            "rule_version": "rv_accounting_asset_movement_v2",
            "product_category_refreshed_dates": ["2026-01-31"],
            "formal_balance_refreshed_dates": ["2026-02-28"],
            "movement_refreshed_dates": ["2026-01-31", "2026-02-28"],
        },
    )

    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)
    response = client.post(
        "/ui/balance-movement-analysis/refresh",
        params={"report_date": "2026-02-28"},
        headers={"X-User-Id": "movement-refresh-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["report_date"] == "2026-02-28"
    assert payload["movement_refreshed_dates"] == ["2026-01-31", "2026-02-28"]
    assert "run_id" not in payload
    assert "job_name" not in payload
    assert "trigger_mode" not in payload


def test_balance_movement_refresh_api_keeps_sync_failure_semantics(tmp_path, monkeypatch):
    route_mod = load_module(
        "backend.app.api.routes.accounting_asset_movement",
        "backend/app/api/routes/accounting_asset_movement.py",
    )
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setattr(
        route_mod,
        "refresh_accounting_asset_movement",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("movement failed")),
    )

    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/ui/balance-movement-analysis/refresh",
        params={"report_date": "2026-02-28"},
        headers={"X-User-Id": "movement-refresh-user"},
    )

    assert response.status_code == 500
    assert "completed" not in response.text
