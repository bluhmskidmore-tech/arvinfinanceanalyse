"""Shared flags for Postgres Alembic + DuckDB bootstrap at API/worker startup."""

from __future__ import annotations

import os


def skip_auto_storage_migrations() -> bool:
    for key in (
        "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS",
        "MOSS_SKIP_POSTGRES_MIGRATIONS",
    ):
        val = os.environ.get(key, "").strip().lower()
        if val in ("1", "true", "yes"):
            return True
    return False
