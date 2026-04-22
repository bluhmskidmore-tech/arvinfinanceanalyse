"""One-shot catalog population: Tushare M2a descriptors + legacy ``vw_external_legacy_*`` entries."""

from __future__ import annotations

import duckdb
from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head
from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.legacy_catalog_seed import register_legacy_seed
from backend.app.repositories.tushare_catalog_seed import register_tushare_m2a_catalog_descriptors


def run_external_data_catalog_seed_once() -> dict[str, int | str]:
    """Apply DuckDB head migrations, then upsert Tushare + legacy catalog entries."""
    upgrade_duckdb_schema_head()
    settings = get_settings()
    path = str(settings.duckdb_path)
    conn = duckdb.connect(path, read_only=False)
    try:
        repo = ExternalDataCatalogRepository(conn=conn)
        t = register_tushare_m2a_catalog_descriptors(repo)
        leg = register_legacy_seed(repo)
    finally:
        conn.close()
    return {"tushare_m2a": t, "legacy": leg, "duckdb_path": path}
