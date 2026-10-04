from __future__ import annotations

import pytest

from backend.app.governance.settings import Settings
from backend.app.security.auth_context import (
    ROLE_HEADER_TRUST_ENV,
    reset_scope_decision_cache,
    validate_auth_startup_guardrails,
)
from backend.app.security.route_policy import ROLE_POLICY_CLASSES, role_meets_policy_class
from backend.app.security.auth_stub import (
    AuthContext,
    ensure_user_allowed,
    get_auth_context,
)


@pytest.fixture(autouse=True)
def _clear_scope_decision_cache():
    reset_scope_decision_cache()
    yield
    reset_scope_decision_cache()


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


def test_ensure_user_allowed_caches_allow_decisions_within_ttl(monkeypatch):
    queries: list[str] = []

    class CountingRepo:
        def __init__(self, _dsn: str):
            pass

        def has_permission(self, *, resource, **_kwargs):
            queries.append(resource)
            return True

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", CountingRepo)
    settings = Settings(postgres_dsn="sqlite:///auth-decision-cache-test.db", _env_file=None)

    for _ in range(3):
        ensure_user_allowed(
            auth=AuthContext(user_id="u1", role="viewer", identity_source="header"),
            settings=settings,
            resource="balance_analysis",
            action="read",
        )

    assert queries == ["balance_analysis"]


def test_ensure_user_allowed_does_not_cache_deny_so_fresh_grants_apply(monkeypatch):
    allowed_flags = iter([False, True])
    queries: list[str] = []

    class FlippingRepo:
        def __init__(self, _dsn: str):
            pass

        def has_permission(self, *, resource, **_kwargs):
            queries.append(resource)
            return next(allowed_flags)

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", FlippingRepo)
    settings = Settings(postgres_dsn="sqlite:///auth-deny-not-cached-test.db", _env_file=None)
    auth = AuthContext(user_id="u2", role="viewer", identity_source="header")

    with pytest.raises(PermissionError):
        ensure_user_allowed(auth=auth, settings=settings, resource="balance_analysis", action="read")

    ensure_user_allowed(auth=auth, settings=settings, resource="balance_analysis", action="read")
    assert queries == ["balance_analysis", "balance_analysis"]


def test_ensure_user_allowed_cache_disabled_by_zero_ttl(monkeypatch):
    queries: list[str] = []

    class CountingRepo:
        def __init__(self, _dsn: str):
            pass

        def has_permission(self, *, resource, **_kwargs):
            queries.append(resource)
            return True

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", CountingRepo)
    monkeypatch.setenv("MOSS_AUTH_SCOPE_CACHE_TTL_SECONDS", "0")
    settings = Settings(postgres_dsn="sqlite:///auth-cache-disabled-test.db", _env_file=None)

    for _ in range(2):
        ensure_user_allowed(
            auth=AuthContext(user_id="u3", role="viewer", identity_source="header"),
            settings=settings,
            resource="balance_analysis",
            action="read",
        )

    assert queries == ["balance_analysis", "balance_analysis"]


def test_route_policy_role_levels_cover_observed_auth_roles_conservatively():
    assert ROLE_POLICY_CLASSES == {
        "admin": "admin",
        "developer": "internal",
        "ops": "internal",
        "reader": "internal",
        "reviewer": "internal",
        "viewer": "internal",
    }
    assert role_meets_policy_class("admin", "admin") is True
    assert role_meets_policy_class("viewer", "admin") is False
    assert role_meets_policy_class("unknown-role", "internal") is False


def test_ensure_user_allowed_warns_when_low_role_scope_matches_admin_policy(monkeypatch, caplog):
    class AllowingRepo:
        def __init__(self, _dsn: str):
            pass

        def has_permission(self, **_kwargs):
            return True

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", AllowingRepo)

    with caplog.at_level("WARNING", logger="backend.app.security.auth_context"):
        ensure_user_allowed(
            auth=AuthContext(user_id="viewer-with-write", role="viewer", identity_source="header"),
            settings=Settings(postgres_dsn="sqlite:///auth-policy-warning-test.db", _env_file=None),
            resource="balance_analysis.decision_status",
            action="write",
        )

    warning = next(record for record in caplog.records if record.message.startswith("Authorization policy warning"))
    assert warning.user_id == "viewer-with-write"
    assert warning.role == "viewer"
    assert warning.resource == "balance_analysis.decision_status"
    assert warning.action == "write"


@pytest.mark.parametrize(
    ("resource", "action"),
    [
        ("balance_analysis.decision_status", "write"),
        ("balance_analysis", "refresh"),
        ("agent", "execute"),
        ("decision_items", "delete"),
        ("adb_analysis", "backfill"),
        ("source_preview", "import"),
    ],
)
def test_ensure_user_allowed_does_not_cache_high_risk_allow_decisions(monkeypatch, resource, action):
    queries: list[tuple[str, str]] = []
    decisions = iter((True, False))

    class CountingRepo:
        def __init__(self, _dsn: str):
            pass

        def has_permission(self, *, resource, action, **_kwargs):
            queries.append((resource, action))
            return next(decisions)

    monkeypatch.setattr("backend.app.security.auth_context.UserScopeRepository", CountingRepo)
    settings = Settings(postgres_dsn="sqlite:///auth-high-risk-cache-test.db", _env_file=None)
    auth = AuthContext(user_id="admin-user", role="admin", identity_source="header")

    ensure_user_allowed(auth=auth, settings=settings, resource=resource, action=action)
    with pytest.raises(PermissionError):
        ensure_user_allowed(auth=auth, settings=settings, resource=resource, action=action)

    assert queries == [(resource, action), (resource, action)]


def test_high_risk_scope_actions_cover_every_admin_scope_action():
    """所有 admin 类动作（含 approve/delete/backfill/import）都是高风险：不得落入可缓存、
    可绑定 viewer 授予的层级。用 POLICY_SCOPE_SEMANTICS 反推，避免新增 admin 动作时漏登记。"""
    from backend.app.security.route_policy import (
        ADMIN_SCOPE_ACTIONS,
        HIGH_RISK_SCOPE_ACTIONS,
        POLICY_SCOPE_SEMANTICS,
    )

    admin_class_actions = {
        action
        for (_resource, action), policy in POLICY_SCOPE_SEMANTICS.items()
        if policy.policy_class == "admin"
    }
    assert admin_class_actions, "POLICY_SCOPE_SEMANTICS lost its admin-class entries"
    assert admin_class_actions <= HIGH_RISK_SCOPE_ACTIONS
    assert HIGH_RISK_SCOPE_ACTIONS == ADMIN_SCOPE_ACTIONS
    assert "read" not in HIGH_RISK_SCOPE_ACTIONS
