"""Apply DuckDB DDL via versioned schema registry at process startup (idempotent)."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.storage_migration_flags import skip_auto_storage_migrations

logger = logging.getLogger(__name__)


def upgrade_duckdb_schema_head(*, duckdb_path: str | None = None) -> None:
    if skip_auto_storage_migrations():
        return
    settings = get_settings()
    path = str(Path(duckdb_path or settings.duckdb_path).expanduser())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    registry = DuckDBSchemaRegistry(db_path=path)
    register_all(registry)
    applied = registry.apply_pending()
    if applied:
        logger.info("Applied %d DuckDB migrations: %s", len(applied), applied)
