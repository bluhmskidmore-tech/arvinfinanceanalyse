from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pytest

from backend.app import duckdb_schema_bootstrap
from backend.app import storage_bootstrap
from backend.app import storage_migration_flags
from backend.app.schema_registry.duckdb_loader import (
    apply_declared_readiness_requirements,
    apply_registry_sql,
)


_STORAGE_FLAG_NAMES = (
    "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS",
    "MOSS_SKIP_POSTGRES_MIGRATIONS",
    "MOSS_SKIP_STORAGE_READINESS_CHECKS",
)


def _clear_storage_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _STORAGE_FLAG_NAMES:
        monkeypatch.delenv(name, raising=False)


def _settings(environment: str) -> SimpleNamespace:
    return SimpleNamespace(
        environment=environment,
        postgres_dsn="postgresql://example.invalid/moss",
        duckdb_path="unused.duckdb",
    )


def test_development_startup_keeps_automatic_storage_migrations(monkeypatch) -> None:
    calls: list[str] = []
    _clear_storage_flags(monkeypatch)
    monkeypatch.setattr(
        storage_bootstrap, "get_settings", lambda: _settings("development")
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_postgres_schema_head",
        lambda: calls.append("postgres-upgrade"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_duckdb_schema_head",
        lambda: calls.append("duckdb-upgrade"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_postgres_schema_current",
        lambda **_kwargs: pytest.fail("development startup must use the upgrade path"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_duckdb_schema_current",
        lambda **_kwargs: pytest.fail("development startup must use the upgrade path"),
    )

    storage_bootstrap.run_startup_storage_migrations()

    assert calls == ["postgres-upgrade", "duckdb-upgrade"]


def test_development_readiness_skip_does_not_suppress_upgrade_calls(
    monkeypatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    monkeypatch.setenv("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")
    monkeypatch.setenv("MOSS_SKIP_STORAGE_READINESS_CHECKS", "1")
    monkeypatch.setattr(
        storage_bootstrap, "get_settings", lambda: _settings("development")
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_postgres_schema_head",
        lambda: calls.append("postgres-upgrade-entry"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_duckdb_schema_head",
        lambda: calls.append("duckdb-upgrade-entry"),
    )

    storage_bootstrap.run_startup_storage_migrations()

    # The upgrade functions own their migration-skip checks. The orchestrator
    # must still call them, independently of the readiness bypass.
    assert calls == ["postgres-upgrade-entry", "duckdb-upgrade-entry"]


def test_non_development_startup_checks_postgres_before_duckdb(monkeypatch) -> None:
    calls: list[str] = []
    _clear_storage_flags(monkeypatch)
    settings = _settings("staging")
    monkeypatch.setattr(storage_bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_postgres_schema_head",
        lambda: pytest.fail("staging startup must not migrate Postgres"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_duckdb_schema_head",
        lambda: pytest.fail("staging startup must not migrate DuckDB"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_postgres_schema_current",
        lambda *, postgres_dsn: calls.append(f"postgres:{postgres_dsn}"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_duckdb_schema_current",
        lambda *, duckdb_path: calls.append(f"duckdb:{duckdb_path}"),
    )

    storage_bootstrap.run_startup_storage_migrations()

    assert calls == [
        f"postgres:{settings.postgres_dsn}",
        f"duckdb:{settings.duckdb_path}",
    ]


def test_non_development_startup_accepts_current_schema_without_writing(
    tmp_path,
    monkeypatch,
) -> None:
    _clear_storage_flags(monkeypatch)
    db_path = tmp_path / "current.duckdb"
    duckdb_schema_bootstrap.upgrade_duckdb_schema_head(duckdb_path=str(db_path))
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        # Startup upgrade intentionally owns only the ordinary migration ledger.
        # The fixture explicitly provisions the manifest's static/lazy contract
        # and ledger-neutral columns before claiming that the database is current.
        apply_registry_sql(conn)
        apply_declared_readiness_requirements(conn)
    finally:
        conn.close()
    before = db_path.stat()

    settings = SimpleNamespace(
        environment="staging",
        postgres_dsn="postgresql://example.invalid/moss",
        duckdb_path=str(db_path),
    )
    calls: list[str] = []
    monkeypatch.setattr(storage_bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_postgres_schema_head",
        lambda: pytest.fail("staging startup must not migrate Postgres"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "upgrade_duckdb_schema_head",
        lambda: pytest.fail("staging startup must not migrate DuckDB"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_postgres_schema_current",
        lambda *, postgres_dsn: calls.append(f"postgres:{postgres_dsn}"),
    )

    storage_bootstrap.run_startup_storage_migrations()

    after = db_path.stat()
    assert calls == [f"postgres:{settings.postgres_dsn}"]
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)


def test_non_development_postgres_failure_stops_before_duckdb(monkeypatch) -> None:
    calls: list[str] = []
    _clear_storage_flags(monkeypatch)
    monkeypatch.setattr(
        storage_bootstrap, "get_settings", lambda: _settings("production")
    )

    def _fail_postgres(*, postgres_dsn: str) -> None:
        calls.append(f"postgres:{postgres_dsn}")
        raise RuntimeError("PostgreSQL schema is not current")

    monkeypatch.setattr(
        storage_bootstrap, "assert_postgres_schema_current", _fail_postgres
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_duckdb_schema_current",
        lambda **_kwargs: calls.append("duckdb"),
    )

    with pytest.raises(RuntimeError, match="PostgreSQL schema is not current"):
        storage_bootstrap.run_startup_storage_migrations()

    assert calls == ["postgres:postgresql://example.invalid/moss"]


def test_migration_skip_flags_do_not_bypass_non_development_readiness(
    monkeypatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    monkeypatch.setenv("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")
    monkeypatch.delenv("MOSS_SKIP_STORAGE_READINESS_CHECKS", raising=False)
    monkeypatch.setattr(
        storage_bootstrap, "get_settings", lambda: _settings("production")
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_postgres_schema_current",
        lambda **_kwargs: calls.append("postgres-readiness"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_duckdb_schema_current",
        lambda **_kwargs: calls.append("duckdb-readiness"),
    )

    storage_bootstrap.run_startup_storage_migrations()

    assert calls == ["postgres-readiness", "duckdb-readiness"]


def test_test_environment_can_explicitly_skip_readiness(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setenv("MOSS_SKIP_STORAGE_READINESS_CHECKS", "yes")
    monkeypatch.setattr(storage_bootstrap, "get_settings", lambda: _settings("test"))
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_postgres_schema_current",
        lambda **_kwargs: calls.append("postgres-readiness"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_duckdb_schema_current",
        lambda **_kwargs: calls.append("duckdb-readiness"),
    )

    storage_bootstrap.run_startup_storage_migrations()

    assert calls == []


@pytest.mark.parametrize("environment", ["production", "staging", "", "unknown"])
def test_readiness_skip_is_rejected_fail_closed_outside_dev_and_test(
    monkeypatch,
    environment: str,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("MOSS_SKIP_STORAGE_READINESS_CHECKS", "true")
    monkeypatch.setattr(
        storage_bootstrap, "get_settings", lambda: _settings(environment)
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_postgres_schema_current",
        lambda **_kwargs: calls.append("postgres-readiness"),
    )
    monkeypatch.setattr(
        storage_bootstrap,
        "assert_duckdb_schema_current",
        lambda **_kwargs: calls.append("duckdb-readiness"),
    )

    with pytest.raises(
        RuntimeError,
        match=r"MOSS_SKIP_STORAGE_READINESS_CHECKS may only be enabled",
    ):
        storage_bootstrap.run_startup_storage_migrations()

    assert calls == []


def test_legacy_postgres_skip_does_not_become_global_storage_skip(monkeypatch) -> None:
    monkeypatch.delenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", raising=False)
    monkeypatch.setenv("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")

    assert storage_migration_flags.skip_auto_storage_migrations() is False
    assert storage_migration_flags.skip_postgres_migrations() is True


def test_global_migration_skip_also_skips_postgres_migration(monkeypatch) -> None:
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "true")
    monkeypatch.delenv("MOSS_SKIP_POSTGRES_MIGRATIONS", raising=False)

    assert storage_migration_flags.skip_auto_storage_migrations() is True
    assert storage_migration_flags.skip_postgres_migrations() is True


def test_read_only_duckdb_validation_does_not_create_missing_parent(tmp_path) -> None:
    db_path = tmp_path / "missing-parent" / "missing.duckdb"

    with pytest.raises(
        RuntimeError,
        match=r"DuckDB schema is not current.*database_missing.*migrate_storage\.py",
    ):
        duckdb_schema_bootstrap.assert_duckdb_schema_current(duckdb_path=str(db_path))

    assert not db_path.parent.exists()


def test_manual_storage_migration_script_calls_existing_upgrade_functions(
    monkeypatch,
) -> None:
    from tests.helpers import load_module

    module = load_module(
        "backend.scripts.migrate_storage",
        "backend/scripts/migrate_storage.py",
    )
    calls: list[str] = []
    monkeypatch.setattr(
        module, "upgrade_postgres_schema_head", lambda: calls.append("postgres")
    )
    monkeypatch.setattr(
        module, "upgrade_duckdb_schema_head", lambda: calls.append("duckdb")
    )
    monkeypatch.setattr(
        module,
        "materialize_declared_duckdb_readiness_schema",
        lambda: calls.append("duckdb_readiness"),
    )

    assert module.main() == 0
    assert calls == ["postgres", "duckdb", "duckdb_readiness"]
