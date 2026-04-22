from __future__ import annotations

import duckdb
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.external_data_migrations_extra import ensure_std_external_macro_schema
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.schemas.external_data import ExternalDataCatalogEntry


def _seed_tushare_like(tmp_path) -> str:
    db = tmp_path / "m2b.duckdb"
    p = str(db)
    conn = duckdb.connect(p)
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        conn.execute(
            """
            insert or replace into std_external_macro_daily (
              series_id, vendor_name, domain, trade_date, value_numeric,
              frequency, unit, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_zone_path, created_at
            ) values
            (
              'api.m2b.series', 'tushare', 'macro', '2026-01-01', 3.0,
              'd', 'u', 'sv', 'vv', 'rv', 'ib', null, timestamp '2026-01-01 00:00:00'
            )
            """,
        )
        ent = ExternalDataCatalogEntry(
            series_id="api.m2b.series",
            series_name="API M2B",
            vendor_name="tushare",
            source_family="tushare_macro",
            domain="macro",
            frequency="d",
            unit="u",
            refresh_tier="r",
            fetch_mode="f",
            raw_zone_path=None,
            standardized_table="std_external_macro_daily",
            view_name="vw_external_macro_daily",
            access_path="select * from vw_external_macro_daily where series_id = 'api.m2b.series'",
            catalog_version="m2b.test",
            created_at="2026-01-01T00:00:00+00:00",
        )
        repo = ExternalDataCatalogRepository(conn=conn)
        repo.register(ent)
    finally:
        conn.close()
    return p


def test_external_data_m2b_endpoints(tmp_path, monkeypatch) -> None:
    p = _seed_tushare_like(tmp_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", p)
    client = TestClient(app)
    r = client.get("/api/external-data/series/api.m2b.series/data?limit=5&offset=0")
    assert r.status_code == 200
    j = r.json()
    assert j.get("count") == 1
    assert j["rows"][0]["value_numeric"] == 3.0
    r2 = client.get("/api/external-data/series/api.m2b.series/data/recent?days=3650&limit=10")
    assert r2.status_code == 200
    assert r2.json().get("count") == 1
    r404 = client.get("/api/external-data/series/missing.m2b.id/data")
    assert r404.status_code == 404
