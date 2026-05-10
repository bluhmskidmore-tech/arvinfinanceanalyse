from __future__ import annotations

from backend.app.repositories.user_scope_repo import _normalize_sqlalchemy_dsn


def test_user_scope_repo_normalizes_plain_postgresql_dsn_to_psycopg_driver() -> None:
    assert (
        _normalize_sqlalchemy_dsn("postgresql://moss:moss@127.0.0.1:55432/moss")
        == "postgresql+psycopg://moss:moss@127.0.0.1:55432/moss"
    )


def test_user_scope_repo_keeps_sqlite_dsn_unchanged() -> None:
    assert _normalize_sqlalchemy_dsn("sqlite:///auth-scope.db") == "sqlite:///auth-scope.db"
