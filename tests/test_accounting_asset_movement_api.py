from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

BALANCE_MOVEMENT_READ_HEADERS = {"X-User-Id": "movement-read-user", "X-User-Role": "viewer"}


def _seed_balance_movement_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
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
        action="read",
    )


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


def test_balance_movement_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch):
    route_mod = load_module(
        "backend.app.api.routes.accounting_asset_movement",
        "backend/app/api/routes/accounting_asset_movement.py",
    )
    monkeypatch.setattr(
        route_mod,
        "accounting_asset_movement_dates_envelope",
        lambda *_args, **_kwargs: {"result_meta": {"result_kind": "balance.movement.dates"}, "result": {}},
    )
    monkeypatch.setattr(
        route_mod,
        "accounting_asset_movement_envelope",
        lambda *_args, **_kwargs: {"result_meta": {"result_kind": "balance.movement.detail"}, "result": {}},
    )
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)

    for path, params in (
        ("/ui/balance-movement-analysis/dates", {}),
        ("/ui/balance-movement-analysis", {"report_date": "2026-02-28"}),
    ):
        response = client.get(path, params=params or None, headers=BALANCE_MOVEMENT_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_balance_movement_refresh_api_returns_queued_payload_with_task_identity(
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
            "status": "queued",
            "cache_key": "accounting_asset_movement.monthly",
            "run_id": "run-movement",
            "job_name": "accounting_asset_movement_refresh",
            "trigger_mode": "async",
            "report_date": "2026-02-28",
            "currency_basis": "CNX",
            "source_version": "sv_accounting_asset_movement_pending",
            "rule_version": "rv_accounting_asset_movement_v2",
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
    assert payload["status"] == "queued"
    assert payload["report_date"] == "2026-02-28"
    assert payload["run_id"] == "run-movement"
    assert payload["job_name"] == "accounting_asset_movement_refresh"
    assert payload["trigger_mode"] == "async"
    assert payload["movement_refreshed_dates"] == ["2026-01-31", "2026-02-28"]
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
