"""One-shot catalog population: Tushare M2a descriptors + legacy ``vw_external_legacy_*`` entries."""

from __future__ import annotations

from pathlib import Path

import duckdb
from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.legacy_catalog_seed import register_legacy_seed
from backend.app.repositories.research_calendar_catalog_seed import (
    register_research_calendar_v1_catalog_descriptors,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.tushare_catalog_seed import register_tushare_m2a_catalog_descriptors


def run_external_data_catalog_seed_once() -> dict[str, int | str]:
    """Apply DuckDB head migrations, then upsert Tushare + research-calendar + legacy catalog entries."""
    settings = get_settings()
    path = str(settings.duckdb_path)
    db_file = Path(path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    # Schema head upgrade opens its own write connection, so it stays inside the
    # same writer-lock scope as the seed connection below.
    with acquire_lock(resolve_duckdb_writer_lock(db_file), base_dir=db_file.parent):
        upgrade_duckdb_schema_head()
        conn = duckdb.connect(path, read_only=False)
        try:
            repo = ExternalDataCatalogRepository(conn=conn)
            with repository_task_write_scope(__name__):
                t = register_tushare_m2a_catalog_descriptors(repo)
                rc = register_research_calendar_v1_catalog_descriptors(repo)
                leg = register_legacy_seed(repo)
        finally:
            conn.close()
    return {"tushare_m2a": t, "research_calendar": rc, "legacy": leg, "duckdb_path": path}
