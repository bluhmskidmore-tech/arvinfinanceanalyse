from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


def _seed_balance_movement_refresh_scope(tmp_path, monkeypatch, *, user_id: str = "movement-refresh-user") -> None:
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_mod = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_mod.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id=user_id,
        role=None,
        resource="accounting_asset_movement",
        action="refresh",
    )


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
    _seed_balance_movement_refresh_scope(tmp_path, monkeypatch)
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
    get_settings.cache_clear()


def test_balance_movement_refresh_requires_explicit_refresh_grant(tmp_path, monkeypatch):
    route_mod = load_module(
        "backend.app.api.routes.accounting_asset_movement",
        "backend/app/api/routes/accounting_asset_movement.py",
    )
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()

    calls: list[str] = []

    def fake_refresh(*_args, **_kwargs):
        calls.append("called")
        return {"status": "completed", "report_date": "2026-02-28", "currency_basis": "CNX"}

    monkeypatch.setattr(route_mod, "refresh_accounting_asset_movement", fake_refresh)

    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)

    denied = client.post(
        "/ui/balance-movement-analysis/refresh",
        params={"report_date": "2026-02-28"},
        headers={"X-User-Id": "movement-refresh-user"},
    )
    assert denied.status_code == 403
    assert calls == []

    repo_mod = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_mod.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="movement-refresh-user",
        role=None,
        resource="accounting_asset_movement",
        action="refresh",
    )
    allowed = client.post(
        "/ui/balance-movement-analysis/refresh",
        params={"report_date": "2026-02-28"},
        headers={"X-User-Id": "movement-refresh-user"},
    )
    assert allowed.status_code == 200, allowed.text
    assert calls == ["called"]
    get_settings.cache_clear()


def test_balance_movement_refresh_api_keeps_sync_failure_semantics(tmp_path, monkeypatch):
    route_mod = load_module(
        "backend.app.api.routes.accounting_asset_movement",
        "backend/app/api/routes/accounting_asset_movement.py",
    )
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    _seed_balance_movement_refresh_scope(tmp_path, monkeypatch)
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
    get_settings.cache_clear()
