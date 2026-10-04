from __future__ import annotations

import hashlib
import json
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy import event
from sqlalchemy.pool import NullPool

from backend.app import postgres_migrations


_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
_FORBIDDEN_SQL = {"ALTER", "CREATE", "DELETE", "DROP", "INSERT", "TRUNCATE", "UPDATE"}


def _alembic_config() -> Config:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return config


def _sqlite_dsn(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _assert_receipt_digest(receipt: dict[str, object]) -> None:
    payload = dict(receipt)
    actual = str(payload.pop("receipt_sha256"))
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert actual == hashlib.sha256(canonical).hexdigest()
    json.dumps(receipt, allow_nan=False)
    checked_at = datetime.fromisoformat(str(receipt["checked_at"]).replace("Z", "+00:00"))
    assert checked_at.utcoffset() is not None


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


class _FakeConnection:
    def __init__(self, events: list[str], *, read_only_value: object = "on") -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.events = events
        self.read_only_value = read_only_value

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        self.events.append("connection_exit")

    def execution_options(self, **options: object) -> _FakeConnection:
        assert options == {"postgresql_readonly": True}
        self.events.append("read_only_option")
        return self

    def exec_driver_sql(self, statement: str) -> _ScalarResult:
        assert statement.casefold() == "show transaction_read_only"
        self.events.append("show_read_only")
        return _ScalarResult(self.read_only_value)


class _FakeEngine:
    def __init__(
        self,
        events: list[str],
        *,
        connection: _FakeConnection | None = None,
        connect_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.connection = connection
        self.connect_error = connect_error

    def connect(self) -> _FakeConnection:
        self.events.append("connect")
        if self.connect_error is not None:
            raise self.connect_error
        assert self.connection is not None
        return self.connection

    def dispose(self) -> None:
        self.events.append("dispose")


def _install_fake_head_sources(
    monkeypatch: pytest.MonkeyPatch,
    *,
    expected_heads: tuple[str, ...],
    applied_heads: tuple[str, ...] = (),
    inspection_error: Exception | None = None,
    read_only_value: object = "on",
) -> tuple[list[str], dict[str, object]]:
    events: list[str] = []
    captured_create_kwargs: dict[str, object] = {}
    connection = _FakeConnection(events, read_only_value=read_only_value)
    engine = _FakeEngine(events, connection=connection)

    monkeypatch.setattr(
        postgres_migrations,
        "_load_script_heads",
        lambda **_kwargs: expected_heads,
    )

    def fake_create_engine(_dsn: str, **kwargs: object) -> _FakeEngine:
        captured_create_kwargs.update(kwargs)
        return engine

    monkeypatch.setattr(postgres_migrations, "create_engine", fake_create_engine)

    class FakeMigrationContext:
        def get_current_heads(self) -> tuple[str, ...]:
            events.append("get_current_heads")
            if inspection_error is not None:
                raise inspection_error
            return applied_heads

    def fake_configure(_connection: object) -> FakeMigrationContext:
        events.append("configure")
        return FakeMigrationContext()

    monkeypatch.setattr(postgres_migrations.MigrationContext, "configure", fake_configure)
    return events, captured_create_kwargs


def test_assert_postgres_schema_current_accepts_matching_single_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "current.db"
    dsn = _sqlite_dsn(db_path)
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    config = _alembic_config()
    command.upgrade(config, "head")

    expected = sorted(ScriptDirectory.from_config(config).get_heads())
    receipt = postgres_migrations.assert_postgres_schema_current(postgres_dsn=dsn)

    assert receipt["status"] == "passed"
    assert receipt["reason_code"] == "current"
    assert receipt["applied_heads"] == expected
    assert receipt["expected_heads"] == expected
    assert receipt["read_only"] is True
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_rejects_stale_single_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "stale.db"
    dsn = _sqlite_dsn(db_path)
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    config = _alembic_config()
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1
    down_revision = script.get_revision(heads[0]).down_revision
    assert isinstance(down_revision, str)
    command.upgrade(config, down_revision)

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(postgres_dsn=dsn)

    receipt = caught.value.receipt
    assert receipt["status"] == "blocked"
    assert receipt["reason_code"] == "head_mismatch"
    assert receipt["applied_heads"] == [down_revision]
    assert receipt["expected_heads"] == heads
    assert receipt["missing_heads"] == heads
    assert receipt["extra_heads"] == [down_revision]
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_rejects_missing_ledger_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "unversioned.db"
    sqlite3.connect(db_path).close()
    statements: list[str] = []

    def traced_create_engine(*args: object, **kwargs: object):
        engine = sqlalchemy_create_engine(*args, **kwargs)
        event.listen(
            engine,
            "before_cursor_execute",
            lambda _conn, _cursor, statement, _parameters, _context, _executemany: statements.append(
                statement.strip()
            ),
        )
        return engine

    monkeypatch.setattr(postgres_migrations, "create_engine", traced_create_engine)

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(postgres_dsn=_sqlite_dsn(db_path))

    receipt = caught.value.receipt
    assert receipt["status"] == "blocked"
    assert receipt["reason_code"] == "migration_ledger_missing"
    assert receipt["applied_heads"] == []
    assert receipt["read_only"] is True
    assert sqlite3.connect(db_path).execute(
        "select name from sqlite_master where type = 'table'"
    ).fetchall() == []
    assert statements
    assert not {
        statement.split(None, 1)[0].upper()
        for statement in statements
        if statement.split(None, 1)
    }.intersection(_FORBIDDEN_SQL)
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_accepts_matching_multiple_heads_in_any_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events, create_kwargs = _install_fake_head_sources(
        monkeypatch,
        expected_heads=("branch-b", "branch-a"),
        applied_heads=("branch-a", "branch-b"),
    )

    receipt = postgres_migrations.assert_postgres_schema_current(
        postgres_dsn="postgresql://user:secret@db.internal/app"
    )

    assert receipt["status"] == "passed"
    assert receipt["applied_heads"] == ["branch-a", "branch-b"]
    assert receipt["expected_heads"] == ["branch-a", "branch-b"]
    assert events == [
        "connect",
        "read_only_option",
        "show_read_only",
        "configure",
        "get_current_heads",
        "connection_exit",
        "dispose",
    ]
    assert create_kwargs == {
        "poolclass": NullPool,
        "connect_args": {"connect_timeout": 5},
    }
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_rejects_partial_multiple_heads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events, _create_kwargs = _install_fake_head_sources(
        monkeypatch,
        expected_heads=("branch-a", "branch-b"),
        applied_heads=("branch-a",),
    )

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(
            postgres_dsn="postgresql://user:secret@db.internal/app"
        )

    receipt = caught.value.receipt
    assert receipt["status"] == "blocked"
    assert receipt["reason_code"] == "multiple_head_mismatch"
    assert receipt["missing_heads"] == ["branch-b"]
    assert receipt["extra_heads"] == []
    assert events[-1] == "dispose"
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_fails_when_read_only_is_not_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events, _create_kwargs = _install_fake_head_sources(
        monkeypatch,
        expected_heads=("expected-head",),
        applied_heads=("expected-head",),
        read_only_value="off",
    )

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(
            postgres_dsn="postgresql://user:secret@db.internal/app"
        )

    receipt = caught.value.receipt
    assert receipt["status"] == "error"
    assert receipt["reason_code"] == "inspection_failed"
    assert receipt["read_only"] is False
    assert "configure" not in events
    assert events[-2:] == ["connection_exit", "dispose"]
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_fails_closed_when_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    secret_dsn = "postgresql://user:super-secret@db.internal/app"
    engine = _FakeEngine(
        events,
        connect_error=RuntimeError(f"could not connect to {secret_dsn}"),
    )
    monkeypatch.setattr(
        postgres_migrations,
        "_load_script_heads",
        lambda **_kwargs: ("expected-head",),
    )
    monkeypatch.setattr(postgres_migrations, "create_engine", lambda *_args, **_kwargs: engine)

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(postgres_dsn=secret_dsn)

    receipt = caught.value.receipt
    assert receipt["status"] == "error"
    assert receipt["reason_code"] == "database_unreachable"
    assert receipt["applied_heads"] is None
    assert receipt["expected_heads"] == ["expected-head"]
    assert receipt["read_only"] is False
    assert "super-secret" not in str(caught.value)
    assert "db.internal" not in str(caught.value)
    assert caught.value.__context__ is None
    formatted_exception = "".join(traceback.format_exception(caught.value))
    assert "super-secret" not in formatted_exception
    assert "db.internal" not in formatted_exception
    assert events == ["connect", "dispose"]
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_fails_closed_when_inspection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_dsn = "postgresql://user:super-secret@db.internal/app"
    events, _create_kwargs = _install_fake_head_sources(
        monkeypatch,
        expected_heads=("expected-head",),
        inspection_error=RuntimeError("driver failed for user:super-secret@db.internal"),
    )

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(postgres_dsn=secret_dsn)

    receipt = caught.value.receipt
    assert receipt["status"] == "error"
    assert receipt["reason_code"] == "inspection_failed"
    assert receipt["applied_heads"] is None
    assert receipt["read_only"] is True
    assert "super-secret" not in str(caught.value)
    assert "db.internal" not in str(caught.value)
    assert caught.value.__context__ is None
    formatted_exception = "".join(traceback.format_exception(caught.value))
    assert "super-secret" not in formatted_exception
    assert "db.internal" not in formatted_exception
    assert events[-2:] == ["connection_exit", "dispose"]
    _assert_receipt_digest(receipt)


def test_assert_postgres_schema_current_fails_before_db_access_for_invalid_scripts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        postgres_migrations,
        "_load_script_heads",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("invalid revision graph")),
    )
    monkeypatch.setattr(
        postgres_migrations,
        "create_engine",
        lambda *_args, **_kwargs: pytest.fail("invalid scripts must stop before DB access"),
    )

    with pytest.raises(postgres_migrations.PostgresSchemaReadinessError) as caught:
        postgres_migrations.assert_postgres_schema_current(
            postgres_dsn="postgresql://user:secret@db.internal/app"
        )

    receipt = caught.value.receipt
    assert receipt["status"] == "error"
    assert receipt["reason_code"] == "script_configuration_failed"
    assert receipt["applied_heads"] is None
    assert receipt["expected_heads"] is None
    assert receipt["read_only"] is False
    _assert_receipt_digest(receipt)
