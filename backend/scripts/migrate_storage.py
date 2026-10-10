"""Apply storage migrations and explicit DuckDB readiness DDL outside the API."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.duckdb_schema_bootstrap import (  # noqa: E402
    materialize_declared_duckdb_readiness_schema,
    upgrade_duckdb_schema_head,
)
from backend.app.postgres_migrations import upgrade_postgres_schema_head  # noqa: E402


def main() -> int:
    upgrade_postgres_schema_head()
    upgrade_duckdb_schema_head()
    materialize_declared_duckdb_readiness_schema()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
