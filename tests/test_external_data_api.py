from __future__ import annotations

from typing import Literal

import duckdb
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.schemas.external_data import ExternalDataCatalogEntry


DomainLit = Literal["macro", "news", "yield_curve", "fx", "other"]


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


def test_external_data_catalog_endpoints(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "t.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path.resolve()))
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
