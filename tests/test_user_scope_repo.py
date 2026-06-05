from __future__ import annotations

import backend.app.repositories.user_scope_repo as user_scope_repo_module
from backend.app.repositories.user_scope_repo import _normalize_sqlalchemy_dsn


def test_user_scope_repo_normalizes_plain_postgresql_dsn_to_psycopg_driver() -> None:
    assert (
        _normalize_sqlalchemy_dsn("postgresql://moss:moss@127.0.0.1:55432/moss")
        == "postgresql+psycopg://moss:moss@127.0.0.1:55432/moss"
    )


def test_user_scope_repo_keeps_sqlite_dsn_unchanged() -> None:
    assert _normalize_sqlalchemy_dsn("sqlite:///auth-scope.db") == "sqlite:///auth-scope.db"


def test_user_scope_repo_uses_fast_postgres_connect_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeDialect:
        name = "postgresql"

    class FakeEngine:
        dialect = FakeDialect()

    def fake_create_engine(dsn, future=True, connect_args=None):
        captured["dsn"] = dsn
        captured["future"] = future
        captured["connect_args"] = connect_args
        return FakeEngine()

    monkeypatch.setattr(user_scope_repo_module, "create_engine", fake_create_engine)

    user_scope_repo_module.UserScopeRepository("postgresql://moss:moss@127.0.0.1:55432/moss")

    assert captured["dsn"] == "postgresql+psycopg://moss:moss@127.0.0.1:55432/moss"
    assert captured["future"] is True
    assert captured["connect_args"] == {"connect_timeout": 1}
