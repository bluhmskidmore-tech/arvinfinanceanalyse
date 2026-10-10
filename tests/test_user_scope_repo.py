from __future__ import annotations

import json
import logging

import backend.app.repositories.user_scope_repo as user_scope_repo_module
import pytest
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


def test_scoped_grant_does_not_authorize_unscoped_request(tmp_path) -> None:
    repo = user_scope_repo_module.UserScopeRepository(f"sqlite:///{(tmp_path / 'scope.db').as_posix()}")
    repo.grant_scope(
        user_id="portfolio-user",
        role=None,
        resource="formal_pnl",
        action="read",
        scope_key="portfolio_id",
        scope_value="P001",
    )

    assert (
        repo.has_permission(
            user_id="portfolio-user",
            role=None,
            resource="formal_pnl",
            action="read",
        )
        is False
    )
    assert (
        repo.has_permission(
            user_id="portfolio-user",
            role=None,
            resource="formal_pnl",
            action="read",
            scope_key="portfolio_id",
            scope_value="P001",
        )
        is True
    )


def test_global_grant_authorizes_scoped_request(tmp_path) -> None:
    repo = user_scope_repo_module.UserScopeRepository(f"sqlite:///{(tmp_path / 'global.db').as_posix()}")
    repo.grant_scope(
        user_id="global-user",
        role=None,
        resource="formal_pnl",
        action="read",
    )

    assert (
        repo.has_permission(
            user_id="global-user",
            role=None,
            resource="formal_pnl",
            action="read",
            scope_key="portfolio_id",
            scope_value="P001",
        )
        is True
    )


@pytest.mark.parametrize("action", ("write", "refresh", "execute", "delete", "backfill", "import"))
def test_grant_scope_rejects_viewer_high_risk_action_before_write(tmp_path, action) -> None:
    repo = user_scope_repo_module.UserScopeRepository(f"sqlite:///{(tmp_path / f'{action}.db').as_posix()}")

    with pytest.raises(ValueError, match=f"viewer.*{action}"):
        repo.grant_scope(
            user_id="viewer-user",
            role="viewer",
            resource="test-resource",
            action=action,
            operator="security-admin",
            reason="must be rejected",
        )

    assert repo.list_scopes_for_user(user_id="viewer-user") == []


def test_grant_scope_logs_structured_audit_context_after_commit(tmp_path, caplog) -> None:
    repo = user_scope_repo_module.UserScopeRepository(f"sqlite:///{(tmp_path / 'audit.db').as_posix()}")

    with caplog.at_level(logging.INFO, logger="backend.app.repositories.user_scope_repo"):
        row = repo.grant_scope(
            user_id="target-user",
            role="admin",
            resource="balance_analysis",
            action="refresh",
            scope_key="portfolio_id",
            scope_value="P001",
            operator="security-admin",
            reason="approved Wave2 grant",
        )

    record = next(record for record in caplog.records if record.message.startswith("user_scope_grant_audit="))
    payload = json.loads(record.message.removeprefix("user_scope_grant_audit="))
    assert payload == {
        "action": "refresh",
        "event": "user_scope_grant",
        "is_active": True,
        "operator": "security-admin",
        "reason": "approved Wave2 grant",
        "recorded_at": row["created_at"],
        "resource": "balance_analysis",
        "role": "admin",
        "scope_key": "portfolio_id",
        "scope_value": "P001",
        "target_user_id": "target-user",
    }
