"""Migrate development storage or validate deployed storage at startup."""

from __future__ import annotations

from backend.app.duckdb_schema_bootstrap import (
    assert_duckdb_schema_current,
    upgrade_duckdb_schema_head,
)
from backend.app.governance.settings import get_settings
from backend.app.postgres_migrations import (
    assert_postgres_schema_current,
    upgrade_postgres_schema_head,
)
from backend.app.storage_migration_flags import skip_storage_readiness_checks


def run_startup_storage_migrations() -> None:
    settings = get_settings()
    environment = str(settings.environment or "").strip().lower()
    skip_readiness = skip_storage_readiness_checks(environment=environment)

    if environment == "development":
        # Each migration entry point owns its mutation-specific skip policy.
        # A readiness bypass must never implicitly suppress these calls.
        upgrade_postgres_schema_head()
        upgrade_duckdb_schema_head()
        return

    if skip_readiness:
        return

    assert_postgres_schema_current(postgres_dsn=settings.postgres_dsn)
    assert_duckdb_schema_current(duckdb_path=settings.duckdb_path)
