"""Run Alembic migrations against MOSS_POSTGRES_DSN."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from backend.app.governance.settings import DEFAULT_POSTGRES_DSN, resolve_postgres_dsn
from backend.app.storage_migration_flags import skip_auto_storage_migrations


def upgrade_postgres_schema_head() -> None:
    if skip_auto_storage_migrations():
        return
    backend_root = Path(__file__).resolve().parents[1]
    ini_path = backend_root / "alembic.ini"
    env = os.environ.copy()
    env["MOSS_POSTGRES_DSN"] = resolve_postgres_dsn(
        env.get("MOSS_POSTGRES_DSN", DEFAULT_POSTGRES_DSN),
        repo_root=backend_root.parent,
    )
    # Run Alembic in a subprocess with cwd=backend (matches dev_postgres_cluster). In-process
    # `command.upgrade` under uvicorn on Windows has been observed to hang after DDL preamble.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ini_path),
            "upgrade",
            "head",
        ],
        cwd=str(backend_root),
        check=True,
        env=env,
    )
