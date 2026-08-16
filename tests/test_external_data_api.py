from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.main import app
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.external_data_migrations_extra import (
    ensure_std_external_macro_schema,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
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


def _register(repo: ExternalDataCatalogRepository, *entries: ExternalDataCatalogEntry) -> None:
    with repository_task_write_scope("backend.app.tasks.external_data_catalog_seed_test"):
        for entry in entries:
            repo.register(entry)


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
        _register(
            repo,
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
        "/api/external-data/watermarks",
        "/api/external-data/catalog/api.series",
        "/api/external-data/catalog/by-domain/macro",
        "/api/external-data/series/api.series/data",
        "/api/external-data/series/api.series/data/recent",
    )
    for path in read_requests:
        response = client.get(path, headers=EXTERNAL_DATA_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_external_data_route_keeps_duckdb_reads_in_service_layer() -> None:
    source = Path("backend/app/api/routes/external_data.py").read_text(encoding="utf-8")

    assert "import duckdb" not in source
    assert "duckdb.connect" not in source


def test_external_data_catalog_endpoints(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "t.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path.resolve()))
    _grant_external_data_read_scope(tmp_path, monkeypatch)
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        _register(repo, _seed_entry("api.series", "macro"), _seed_entry("api.news", "news"))
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


def test_external_data_series_data_endpoints_return_rows(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "series.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path.resolve()))
    _grant_external_data_read_scope(tmp_path, monkeypatch)
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        _register(
            ExternalDataCatalogRepository(conn=conn),
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
        conn.execute(
            """
            insert or replace into std_external_macro_daily (
              series_id, vendor_name, domain, trade_date, value_numeric,
              frequency, unit, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_zone_path, created_at
            ) values
            ('api.series', 'v', 'macro', '2026-04-20', 1.25, 'd', 'pct', 'sv', 'vv', 'rv', 'batch', null, '2026-04-21T00:00:00'),
            ('other.series', 'v', 'macro', '2026-04-21', 9.99, 'd', 'pct', 'sv', 'vv', 'rv', 'batch', null, '2026-04-21T00:00:00')
            """,
        )
    finally:
        conn.close()

    client = TestClient(app)

    page = client.get(
        "/api/external-data/series/api.series/data",
        params={"limit": 10, "offset": 0},
    )
    recent = client.get(
        "/api/external-data/series/api.series/data/recent",
        params={"days": 3650, "limit": 10},
    )
    missing = client.get("/api/external-data/series/missing/data")

    assert page.status_code == 200, page.text
    page_payload = page.json()
    assert page_payload["series_id"] == "api.series"
    assert page_payload["table_name"] == "vw_external_macro_daily"
    assert page_payload["count"] == 1
    assert page_payload["rows"][0]["series_id"] == "api.series"
    assert page_payload["rows"][0]["value_numeric"] == 1.25

    assert recent.status_code == 200, recent.text
    recent_payload = recent.json()
    assert recent_payload["series_id"] == "api.series"
    assert recent_payload["count"] == 1
    assert recent_payload["rows"][0]["trade_date"] == "2026-04-20"

    assert missing.status_code == 404
    assert missing.json()["detail"] == "series_id not found"


def test_external_data_watermark_endpoint_returns_catalog_freshness(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "watermark-api.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path.resolve()))
    _grant_external_data_read_scope(tmp_path, monkeypatch)
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        _register(
            repo,
            ExternalDataCatalogEntry(
                series_id="api.watermark.series",
                series_name="API watermark series",
                vendor_name="v",
                source_family="sf",
                domain="macro",
                standardized_table="std_external_macro_daily",
                view_name="vw_external_macro_daily",
                catalog_version="cv",
                created_at="2026-04-21T00:00:00+00:00",
            )
        )
        conn.execute(
            """
            insert or replace into std_external_macro_daily (
              series_id, vendor_name, domain, trade_date, value_numeric,
              frequency, unit, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_zone_path, created_at
            ) values
            ('api.watermark.series', 'v', 'macro', '2026-04-20', 1.25, 'd', 'pct', 'sv', 'vv', 'rv', 'batch', null, timestamp '2026-04-21 08:00:00')
            """,
        )
    finally:
        conn.close()

    client = TestClient(app)
    request_day_before = date.today()
    response = client.get("/api/external-data/watermarks")
    request_day_after = date.today()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["catalog_count"] == 1
    assert payload["summary"]["available_count"] == 1
    assert payload["summary"]["oldest_available_business_date"] == "2026-04-20"
    assert payload["summary"]["newest_available_business_date"] == "2026-04-20"
    assert payload["summary"]["last_successful_ingest"] == "2026-04-21 08:00:00"
    # age_days 由服务端在请求时刻计算：用请求前后窗口断言，避免跨午夜双读翻车。
    assert len(payload["entries"]) == 1
    observed_age_days = payload["entries"][0]["age_days"]
    assert observed_age_days in {
        (day - date(2026, 4, 20)).days for day in (request_day_before, request_day_after)
    }
    assert payload["entries"] == [
        {
            "series_id": "api.watermark.series",
            "series_name": "API watermark series",
            "vendor_name": "v",
            "source_family": "sf",
            "domain": "macro",
            "frequency": None,
            "unit": None,
            "refresh_tier": None,
            "fetch_mode": None,
            "relation_name": "vw_external_macro_daily",
            "date_column": "trade_date",
            "row_count": 1,
            "latest_business_date": "2026-04-20",
            "latest_loaded_at": "2026-04-21 08:00:00",
            "age_days": observed_age_days,
            "freshness_tier": "unknown",
            "data_status": "available",
            "error_message": None,
        }
    ]
