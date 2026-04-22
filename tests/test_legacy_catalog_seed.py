from __future__ import annotations

import duckdb

from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.legacy_catalog_seed import register_legacy_seed

_EXPECTED = {
    "legacy.choice.macro",
    "legacy.choice.news",
    "legacy.akshare.yield_curve",
    "legacy.akshare.fx_mid",
}


def test_legacy_catalog_seed_registers_four(tmp_path, monkeypatch) -> None:
    db = tmp_path / "c.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db.resolve()))
    upgrade_duckdb_schema_head(duckdb_path=str(db))
    conn = duckdb.connect(str(db))
    try:
        ensure_external_data_catalog_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        n = register_legacy_seed(repo)
        assert n == 4
        ids = {e.series_id for e in repo.list_all()}
        assert _EXPECTED.issubset(ids)
    finally:
        conn.close()
