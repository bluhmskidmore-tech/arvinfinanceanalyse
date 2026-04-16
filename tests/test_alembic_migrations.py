"""Verify Alembic migrations apply cleanly and match ORM metadata."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from backend.app.models.base import Base
from backend.app.models.governance import (  # noqa: F401
    CacheBuildRun,
    CacheManifest,
    RuleVersionRegistry,
    SourceVersionRegistry,
    UserRoleScope,
)
from backend.app.models.job_state import JobRunState  # noqa: F401
from tests.helpers import load_module

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"

_EXPECTED_TABLES = frozenset(
    {
        "alembic_version",
        "job_run_state",
        "cache_build_run",
        "cache_manifest",
        "source_version_registry",
        "rule_version_registry",
        "user_role_scope",
    }
)


def _sqlite_dsn(db_file: Path) -> str:
    return f"sqlite:///{db_file.resolve().as_posix()}"


def _alembic_config() -> Config:
    ini_path = _BACKEND_ROOT / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return cfg


def test_alembic_upgrade_head(tmp_path, monkeypatch) -> None:
    """Alembic upgrade head on an empty SQLite database should succeed."""
    db_file = tmp_path / "alembic_test.db"
    dsn = _sqlite_dsn(db_file)
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    engine = create_engine(dsn)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert _EXPECTED_TABLES <= names
    assert "job_run_state" in names
    assert "cache_build_run" in names


def test_alembic_current_model_matches_migrations(tmp_path, monkeypatch) -> None:
    """After upgrade head, autogenerate comparison finds no metadata drift vs the live DB."""
    db_file = tmp_path / "alembic_autogen_test.db"
    dsn = _sqlite_dsn(db_file)
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    engine = create_engine(dsn)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"Unexpected autogenerate drift (apply a migration or fix models): {diff}"


def test_upgrade_postgres_schema_head_passes_resolved_dev_cluster_dsn_to_subprocess(
    monkeypatch, tmp_path
) -> None:
    module = load_module(
        "backend.app.postgres_migrations",
        "backend/app/postgres_migrations.py",
    )
    repo_root = tmp_path / "repo"
    backend_root = repo_root / "backend"
    app_root = backend_root / "app"
    app_root.mkdir(parents=True, exist_ok=True)
    (backend_root / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n", encoding="utf-8")
    (repo_root / "tmp-governance" / "pgdev" / "data").mkdir(parents=True, exist_ok=True)

    captured: dict[str, object] = {}

    def _fake_run(args, *, cwd, check, env):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["check"] = check
        captured["dsn"] = env.get("MOSS_POSTGRES_DSN")
        return None

    monkeypatch.setattr(module, "skip_auto_storage_migrations", lambda: False)
    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(module.Path, "resolve", lambda _self: app_root / "postgres_migrations.py")
    monkeypatch.setenv("MOSS_POSTGRES_DSN", "")

    module.upgrade_postgres_schema_head()

    assert captured["cwd"] == str(backend_root)
    assert captured["check"] is True
    assert captured["dsn"] == "postgresql://moss:moss@127.0.0.1:55432/moss"
