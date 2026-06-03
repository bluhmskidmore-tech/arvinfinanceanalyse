from __future__ import annotations

from typing import Literal

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.external_data_migrations_extra import ensure_std_external_macro_schema
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from tests.helpers import load_module


DomainLit = Literal["macro", "news", "yield_curve", "fx", "other"]
EXTERNAL_DATA_READ_HEADERS = {"X-User-Id": "external-data-read-user", "X-User-Role": "viewer"}


def _grant_external_data_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    sqlite_path = tmp_path / "external-data-read-scope.db"
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
        resource="external_data",
        action="read",
    )


def _seed_entry(series_id: str, domain: DomainLit) -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=series_id,
        series_name="n",
        vendor_name="v",
        source_family="sf",
        domain=domain,
        catalog_version="cv",
        created_at="2026-04-21T00:00:00+00:00",
    )


def test_external_data_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "external-data-read-scope.db"
    duckdb_path = tmp_path / "external-data.duckdb"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path.resolve()))
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        repo.register(
            ExternalDataCatalogEntry(
                series_id="api.series",
                series_name="API series",
                vendor_name="v",
                source_family="sf",
                domain="macro",
                standardized_table="std_external_macro_daily",
                view_name="vw_external_macro_daily",
                catalog_version="cv",
                created_at="2026-04-21T00:00:00+00:00",
            )
        )
    finally:
        conn.close()

    route_module = load_module(
        "backend.app.api.routes.external_data",
        "backend/app/api/routes/external_data.py",
    )
    test_app = FastAPI()
    test_app.include_router(route_module.router)
    client = TestClient(test_app)

    read_requests = (
        "/api/external-data/catalog",
        "/api/external-data/catalog/api.series",
        "/api/external-data/catalog/by-domain/macro",
        "/api/external-data/series/api.series/data",
        "/api/external-data/series/api.series/data/recent",
    )
    for path in read_requests:
        response = client.get(path, headers=EXTERNAL_DATA_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_external_data_catalog_endpoints(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "t.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path.resolve()))
    _grant_external_data_read_scope(tmp_path, monkeypatch)
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        repo.register(_seed_entry("api.series", "macro"))
        repo.register(_seed_entry("api.news", "news"))
    finally:
        conn.close()

    client = TestClient(app)
    r = client.get("/api/external-data/catalog")
    assert r.status_code == 200
    ids = {row["series_id"] for row in r.json()}
    assert ids == {"api.series", "api.news"}

    r_one = client.get("/api/external-data/catalog/api.series")
    assert r_one.status_code == 200
    assert r_one.json()["series_id"] == "api.series"

    r_404 = client.get("/api/external-data/catalog/missing")
    assert r_404.status_code == 404

    r_dom = client.get("/api/external-data/catalog/by-domain/macro")
    assert r_dom.status_code == 200
    assert {row["series_id"] for row in r_dom.json()} == {"api.series"}
