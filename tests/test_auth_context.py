from __future__ import annotations

import pytest

from backend.app.governance.settings import Settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV, validate_auth_startup_guardrails
from backend.app.security.auth_stub import (
    AuthContext,
    ensure_user_allowed,
    get_auth_context,
)


def test_get_auth_context_defaults_to_anonymous_viewer(monkeypatch):
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)

    ctx = get_auth_context()

    assert ctx.user_id == "anonymous"
    assert ctx.role == "viewer"
    assert ctx.identity_source == "fallback"


def test_get_auth_context_uses_env_when_headers_missing(monkeypatch):
    monkeypatch.setenv("MOSS_USER_ID", "env-user")
    monkeypatch.setenv("MOSS_USER_ROLE", "ops")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)

    ctx = get_auth_context()

    assert ctx.user_id == "env-user"
    assert ctx.role == "ops"
    assert ctx.identity_source == "env"


def test_get_auth_context_ignores_role_header_by_default(monkeypatch):
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)

    ctx = get_auth_context(x_user_id="header-user", x_user_role="reviewer")

    assert ctx.user_id == "anonymous"
    assert ctx.role == "viewer"
    assert ctx.identity_source == "fallback"


def test_get_auth_context_accepts_user_and_role_headers_only_when_enabled(monkeypatch):
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")

    ctx = get_auth_context(x_user_id="header-user", x_user_role="reviewer")

    assert ctx.user_id == "header-user"
    assert ctx.role == "reviewer"
    assert ctx.identity_source == "header"


def test_startup_guardrails_reject_trusted_headers_outside_development(monkeypatch):
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")

    with pytest.raises(RuntimeError, match="development.*X-User-Role|X-User-Role.*development"):
        validate_auth_startup_guardrails(Settings(environment="staging", _env_file=None))


def test_startup_guardrails_reject_env_identity_outside_development(monkeypatch):
    monkeypatch.setenv("MOSS_USER_ID", "prod-spoof-user")
    monkeypatch.setenv("MOSS_USER_ROLE", "admin")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)

    with pytest.raises(RuntimeError, match="production.*MOSS_USER_ID|MOSS_USER_ID.*production"):
        validate_auth_startup_guardrails(Settings(environment="production", _env_file=None))


def test_startup_guardrails_reject_wildcard_cors_outside_development(monkeypatch):
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)

    with pytest.raises(RuntimeError, match="production.*CORS|CORS.*production"):
        validate_auth_startup_guardrails(
            Settings(environment="production", cors_origins="https://app.example,*", _env_file=None)
        )


def test_ensure_user_allowed_checks_scope_store_for_development_fallback_read(monkeypatch):
    class BrokenRepo:
        def __init__(self, _dsn: str):
            raise OSError("dsn refused")

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", BrokenRepo)

    with pytest.raises(RuntimeError, match="User scope store is unavailable."):
        ensure_user_allowed(
            auth=AuthContext(),
            settings=Settings(_env_file=None),
            resource="balance_analysis",
            action="read",
        )


def test_ensure_user_allowed_checks_scope_store_for_production_read(monkeypatch):
    class BrokenRepo:
        def __init__(self, _dsn: str):
            raise OSError("dsn refused")

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", BrokenRepo)

    with pytest.raises(RuntimeError, match="User scope store is unavailable."):
        ensure_user_allowed(
            auth=AuthContext(),
            settings=Settings(environment="production", _env_file=None),
            resource="balance_analysis",
            action="read",
        )


def test_ensure_user_allowed_checks_scope_store_for_development_explicit_identity_read(monkeypatch):
    class BrokenRepo:
        def __init__(self, _dsn: str):
            raise OSError("dsn refused")

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", BrokenRepo)

    with pytest.raises(RuntimeError, match="User scope store is unavailable."):
        ensure_user_allowed(
            auth=AuthContext(user_id="u1", role="viewer", identity_source="header"),
            settings=Settings(_env_file=None),
            resource="balance_analysis",
            action="read",
        )


def test_ensure_user_allowed_checks_scope_store_for_development_fallback_write(monkeypatch):
    class BrokenRepo:
        def __init__(self, _dsn: str):
            raise OSError("dsn refused")

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", BrokenRepo)

    with pytest.raises(RuntimeError, match="User scope store is unavailable."):
        ensure_user_allowed(
            auth=AuthContext(),
            settings=Settings(_env_file=None),
            resource="balance_analysis.decision_status",
            action="write",
        )


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


def test_ensure_user_allowed_reuses_scope_repository_for_same_dsn(monkeypatch):
    created: list[str] = []

    class CountingRepo:
        def __init__(self, dsn: str):
            created.append(dsn)

        def has_permission(self, **_kwargs):
            return True

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", CountingRepo)
    settings = Settings(postgres_dsn="sqlite:///auth-cache-test.db", _env_file=None)

    for _ in range(2):
        ensure_user_allowed(
            auth=AuthContext(user_id="u1", role="viewer", identity_source="header"),
            settings=settings,
            resource="balance_analysis",
            action="read",
        )

    assert created == [settings.governance_sql_dsn or settings.postgres_dsn]
