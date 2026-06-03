from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_cube_query_service import _seed_cube_tables


CUBE_READ_HEADERS = {"X-User-Id": "cube-read-user", "X-User-Role": "viewer"}


def _grant_cube_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    sqlite_path = tmp_path / "cube-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id=user_id,
        role=None,
        resource="cube",
        action="read",
    )


def test_cube_query_route_returns_formal_cube_response(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post(
        "/api/cube/query",
        json={
            "report_date": "2026-03-31",
            "fact_table": "bond_analytics",
            "measures": ["sum(market_value)"],
            "dimensions": ["asset_class_std"],
            "order_by": ["-market_value"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fact_table"] == "bond_analytics"
    assert payload["total_rows"] == 2
    assert payload["rows"][0] == {"asset_class_std": "credit", "market_value": "350.00000000"}
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    get_settings.cache_clear()


def test_cube_query_route_rejects_invalid_request(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post(
        "/api/cube/query",
        json={
            "report_date": "2026-03-31",
            "fact_table": "bond_analytics",
            "measures": ["sum(market_value)"],
            "dimensions": ["unsupported_dimension"],
        },
    )

    assert response.status_code == 400
    assert "Unsupported dimensions" in response.json()["detail"]
    get_settings.cache_clear()


def test_cube_query_route_returns_503_when_storage_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post(
        "/api/cube/query",
        json={
            "report_date": "2026-03-31",
            "fact_table": "bond_analytics",
            "measures": ["sum(market_value)"],
            "dimensions": ["asset_class_std"],
        },
    )

    assert response.status_code == 503
    assert "storage is unavailable" in response.json()["detail"]
    get_settings.cache_clear()


def test_cube_dimensions_route_requires_explicit_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "cube-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()

    route_module = load_module(
        "backend.app.api.routes.cube_query",
        "backend/app/api/routes/cube_query.py",
    )
    test_app = FastAPI()
    test_app.include_router(route_module.router)
    client = TestClient(test_app)

    response = client.get("/api/cube/dimensions/bond_analytics", headers=CUBE_READ_HEADERS)

    assert response.status_code == 403
    get_settings.cache_clear()


def test_cube_dimensions_route_returns_promoted_contract(tmp_path, monkeypatch):
    _grant_cube_read_scope(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/cube/dimensions/bond_analytics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fact_table"] == "bond_analytics"
    assert "asset_class_std" in payload["dimensions"]
    assert payload["measures"] == ["sum", "avg", "count", "min", "max"]
    assert "market_value" in payload["measure_fields"]


def test_cube_dimensions_route_rejects_unknown_fact_table(tmp_path, monkeypatch):
    _grant_cube_read_scope(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/cube/dimensions/unknown_table")

    assert response.status_code == 400
    assert "Unsupported fact_table" in response.json()["detail"]
