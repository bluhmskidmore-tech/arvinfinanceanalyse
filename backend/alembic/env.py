from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from alembic import context
from sqlalchemy import create_engine, pool

from backend.app.governance.settings import DEFAULT_POSTGRES_DSN, resolve_postgres_dsn
from backend.app.models.base import Base
from backend.app.models.governance import (  # noqa: F401
    CacheBuildRun,
    CacheManifest,
    RuleVersionRegistry,
    SourceVersionRegistry,
)
from backend.app.models.job_state import JobRunState  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    dsn = resolve_postgres_dsn(
        os.environ.get("MOSS_POSTGRES_DSN", DEFAULT_POSTGRES_DSN),
        repo_root=_REPO_ROOT,
    )
    if dsn.startswith("postgresql://"):
        dsn = "postgresql+psycopg://" + dsn[len("postgresql://") :]
    return dsn


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    # psycopg accepts connect_timeout; sqlite (used in tests) does not.
    connect_args: dict[str, object] = (
        {"connect_timeout": 15} if url.startswith("postgresql+psycopg://") else {}
    )
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
