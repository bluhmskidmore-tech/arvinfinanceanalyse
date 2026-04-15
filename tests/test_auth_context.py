from __future__ import annotations

from backend.app.security.auth_stub import get_auth_context


def test_get_auth_context_prefers_headers_over_env(monkeypatch):
    monkeypatch.setenv("MOSS_USER_ID", "env-user")
    monkeypatch.setenv("MOSS_USER_ROLE", "ops")

    ctx = get_auth_context(x_user_id="header-user", x_user_role="reviewer")

    assert ctx.user_id == "header-user"
    assert ctx.role == "reviewer"
    assert ctx.identity_source == "header"


def test_get_auth_context_uses_env_when_headers_missing(monkeypatch):
    monkeypatch.setenv("MOSS_USER_ID", "env-user")
    monkeypatch.setenv("MOSS_USER_ROLE", "ops")

    ctx = get_auth_context()

    assert ctx.user_id == "env-user"
    assert ctx.role == "ops"
    assert ctx.identity_source == "env"
