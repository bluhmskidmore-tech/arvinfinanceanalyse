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
    _grant_cube_read_scope(tmp_path, monkeypatch)
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


def test_cube_route_reads_retained_snapshot_through_real_service_and_repository(tmp_path, monkeypatch):
    from pathlib import Path

    import duckdb

    from backend.app.api.routes.cube_query import router
    from backend.app.main import SystemReadPublicationMiddleware
    from backend.app.repositories.system_read_publication_repo import (
        SYSTEM_READ_GENERATION_HEADER, system_read_publication_root,
    )
    from backend.app.tasks.financial_result_publication import publish_financial_result
    from tests.test_system_online_read_boundary import _seal_generation, _settings, _write_pointer
    from tests.test_system_read_publication_process_crash import _plan, _system_bundle

    settings = _settings(tmp_path)
    with duckdb.connect(str(settings.duckdb_path)) as conn:
        conn.execute("ALTER TABLE sentinel ADD COLUMN report_date DATE DEFAULT '2026-09-15'")
    _seed_cube_tables(settings.duckdb_path)
    _grant_cube_read_scope(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(settings.duckdb_path))
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-r0", "PNL")
    _write_pointer(pnl_root, "pnl-r0", [("pnl-r0", pnl_digest)])
    root = system_read_publication_root(settings)
    generations = ["system-read-2026-09-15-aaaaaaaaaaaaaaaaaaaa",
                   "system-read-2026-09-15-bbbbbbbbbbbbbbbbbbbb"]
    previous = None
    for generation in generations:
        publish_financial_result(
            source_duckdb_path=settings.duckdb_path, publication_root=root,
            plan=_plan(
                generation=generation, expected_previous_generation=previous,
                bundle=_system_bundle(settings, pnl_digest=pnl_digest,
                                      data_update_run_id=generation, global_run_id=generation),
            ),
        )
        previous = generation
        with duckdb.connect(str(settings.duckdb_path)) as conn:
            conn.execute("UPDATE fact_formal_bond_analytics_daily SET market_value = market_value * 2")

    app = FastAPI()
    app.include_router(router)
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    from backend.app.api.routes import cube_query as cube_route

    settings_dependency = cube_route.get_settings
    settings_dependency.cache_clear()
    app.dependency_overrides[settings_dependency] = lambda: settings
    request = {"report_date": "2026-03-31", "fact_table": "bond_analytics",
               "measures": ["sum(market_value)"]}
    client = TestClient(app)
    try:
        for generation, amount in zip(generations, ["450.00000000", "900.00000000"]):
            response = client.post(
                "/api/cube/query", json=request,
                headers={**CUBE_READ_HEADERS, SYSTEM_READ_GENERATION_HEADER: generation},
            )
            assert response.status_code == 200, response.text
            assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
            assert response.json()["rows"] == [{"market_value": amount}]
        assert client.post(
            "/api/cube/query", json=request,
            headers={**CUBE_READ_HEADERS, SYSTEM_READ_GENERATION_HEADER: "not-committed"},
        ).status_code == 503
    finally:
        client.close()
        get_settings.cache_clear()


def test_cube_query_route_rejects_invalid_request(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    _grant_cube_read_scope(tmp_path, monkeypatch)
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
    _grant_cube_read_scope(tmp_path, monkeypatch)
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


def test_cube_query_route_requires_explicit_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "cube-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()

    route_module = load_module(
        "backend.app.api.routes.cube_query",
        "backend/app/api/routes/cube_query.py",
    )

    class BridgeShouldNotRun:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("cube query bridge reached before authorization")

    monkeypatch.setattr(route_module, "AnalyticalBridgeService", BridgeShouldNotRun)
    test_app = FastAPI()
    test_app.include_router(route_module.router)
    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.post(
        "/api/cube/query",
        headers=CUBE_READ_HEADERS,
        json={
            "report_date": "2026-03-31",
            "fact_table": "bond_analytics",
            "measures": ["sum(market_value)"],
            "dimensions": ["asset_class_std"],
        },
    )

    assert response.status_code == 403
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
