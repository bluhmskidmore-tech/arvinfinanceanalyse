from __future__ import annotations

import pytest

from backend.app.governance.settings import Settings
from backend.app.security.auth_stub import AuthContext, ensure_user_allowed, get_auth_context


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


def test_ensure_user_allowed_raises_runtime_error_when_scope_store_is_unavailable(monkeypatch):
    class BrokenRepo:
        def __init__(self, _dsn: str):
            raise OSError("dsn refused")

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", BrokenRepo)

    with pytest.raises(RuntimeError, match="User scope store is unavailable."):
        ensure_user_allowed(
            auth=AuthContext(user_id="u1", role="viewer", identity_source="header"),
            settings=Settings(),
            resource="balance_analysis.decision_status",
            action="write",
        )
