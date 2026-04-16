"""Run Alembic migrations against MOSS_POSTGRES_DSN."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from backend.app.governance.settings import DEFAULT_POSTGRES_DSN, resolve_postgres_dsn
from backend.app.storage_migration_flags import skip_auto_storage_migrations


def _wait_for_postgres_sql_ready(
    postgres_dsn: str,
    *,
    repo_root: Path,
    attempts: int = 5,
    retry_delay_seconds: float = 1.0,
) -> None:
    normalized_dsn = str(postgres_dsn or "").strip()
    if normalized_dsn.startswith("postgresql://"):
        normalized_dsn = "postgresql+psycopg://" + normalized_dsn[len("postgresql://") :]

    for attempt in range(1, attempts + 1):
        try:
            engine = create_engine(normalized_dsn, connect_args={"connect_timeout": 5})
            with engine.connect() as connection:
                connection.execute(text("select 1")).scalar()
            return
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(retry_delay_seconds)
        finally:
            if "engine" in locals():
                engine.dispose()


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
    alembic_args = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ini_path),
        "upgrade",
        "head",
    ]
    for attempt in range(1, 4):
        result = subprocess.run(
            alembic_args,
            cwd=str(backend_root),
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return

        combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).lower()
        is_transient_connect_timeout = "connection timeout expired" in combined_output
        if is_transient_connect_timeout and attempt < 3:
            _wait_for_postgres_sql_ready(env["MOSS_POSTGRES_DSN"], repo_root=backend_root.parent)
            continue

        if result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            alembic_args,
            output=result.stdout,
            stderr=result.stderr,
        )
