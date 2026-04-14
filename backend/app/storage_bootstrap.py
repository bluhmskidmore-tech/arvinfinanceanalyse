"""Run Postgres + DuckDB migrations at API lifespan / worker import."""

from __future__ import annotations

from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head
from backend.app.postgres_migrations import upgrade_postgres_schema_head


def run_startup_storage_migrations() -> None:
    upgrade_postgres_schema_head()
    upgrade_duckdb_schema_head()
