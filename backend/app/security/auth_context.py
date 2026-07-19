from __future__ import annotations

import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Annotated

from backend.app.governance.settings import Settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from fastapi import Header

DEFAULT_AUTH_USER_ID = "anonymous"
DEFAULT_AUTH_ROLE = "viewer"
ROLE_HEADER_TRUST_ENV = "MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST"
SCOPE_DECISION_CACHE_TTL_ENV = "MOSS_AUTH_SCOPE_CACHE_TTL_SECONDS"
_DEFAULT_SCOPE_DECISION_CACHE_TTL_SECONDS = 30.0
_SCOPE_DECISION_CACHE_MAX_ENTRIES = 4096
_USER_SCOPE_REPO_CACHE: dict[tuple[object, str], UserScopeRepository] = {}
_USER_SCOPE_REPO_CACHE_LOCK = Lock()
_SCOPE_DECISION_CACHE: dict[tuple[object, ...], float] = {}
_SCOPE_DECISION_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class AuthContext:
    user_id: str = DEFAULT_AUTH_USER_ID
    role: str = DEFAULT_AUTH_ROLE
    identity_source: str = "fallback"


def get_auth_context(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> AuthContext:
    header_user_id = (x_user_id or "").strip()
    env_user_id = os.environ.get("MOSS_USER_ID", "").strip()

    if _header_trust_enabled() and header_user_id:
        user_id = header_user_id
        identity_source = "header"
    elif env_user_id:
        user_id = env_user_id
        identity_source = "env"
    else:
        user_id = DEFAULT_AUTH_USER_ID
        identity_source = "fallback"

    header_user_role = (x_user_role or "").strip()
    env_user_role = os.environ.get("MOSS_USER_ROLE", "").strip()

    if _header_trust_enabled() and header_user_role:
        role = header_user_role
    else:
        role = env_user_role or DEFAULT_AUTH_ROLE

    return AuthContext(user_id=user_id, role=role, identity_source=identity_source)


def ensure_user_allowed(
    *,
    auth: AuthContext,
    settings: Settings,
    resource: str,
    action: str,
    scope_key: str | None = None,
    scope_value: str | None = None,
) -> None:
    dsn = settings.governance_sql_dsn or settings.postgres_dsn
    cache_key = (
        str(dsn or "").strip(),
        auth.user_id,
        auth.role,
        resource,
        action,
        scope_key,
        scope_value,
    )
    ttl_seconds = _scope_decision_cache_ttl_seconds()
    if _scope_decision_cache_get(cache_key, ttl_seconds):
        return
    try:
        repo = _get_user_scope_repository(dsn)
        allowed = bool(
            repo.has_permission(
                user_id=auth.user_id,
                role=auth.role,
                resource=resource,
                action=action,
                scope_key=scope_key,
                scope_value=scope_value,
            )
        )
    except Exception as exc:
        raise RuntimeError("User scope store is unavailable.") from exc
    if allowed:
        # Only allow decisions are cached: a fresh grant takes effect immediately,
        # while a revoke is delayed by at most the TTL window.
        _scope_decision_cache_set(cache_key, ttl_seconds)
        return
    raise PermissionError(f"User is not allowed to {action} {resource}.")


def _scope_decision_cache_ttl_seconds() -> float:
    raw = os.environ.get(SCOPE_DECISION_CACHE_TTL_ENV, "").strip()
    if not raw:
        return _DEFAULT_SCOPE_DECISION_CACHE_TTL_SECONDS
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return _DEFAULT_SCOPE_DECISION_CACHE_TTL_SECONDS


def _scope_decision_cache_get(key: tuple[object, ...], ttl_seconds: float) -> bool:
    if ttl_seconds <= 0:
        return False
    now = time.monotonic()
    with _SCOPE_DECISION_CACHE_LOCK:
        expires_at = _SCOPE_DECISION_CACHE.get(key)
        if expires_at is None:
            return False
        if now >= expires_at:
            _SCOPE_DECISION_CACHE.pop(key, None)
            return False
        return True


def _scope_decision_cache_set(key: tuple[object, ...], ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        return
    with _SCOPE_DECISION_CACHE_LOCK:
        if len(_SCOPE_DECISION_CACHE) >= _SCOPE_DECISION_CACHE_MAX_ENTRIES:
            _SCOPE_DECISION_CACHE.clear()
        _SCOPE_DECISION_CACHE[key] = time.monotonic() + ttl_seconds


def reset_scope_decision_cache() -> None:
    """Clear cached allow/deny decisions (used by tests and grant workflows)."""
    with _SCOPE_DECISION_CACHE_LOCK:
        _SCOPE_DECISION_CACHE.clear()


def _get_user_scope_repository(dsn: str) -> UserScopeRepository:
    repo_cls = UserScopeRepository
    key = (repo_cls, str(dsn or "").strip())
    with _USER_SCOPE_REPO_CACHE_LOCK:
        cached = _USER_SCOPE_REPO_CACHE.get(key)
        if cached is not None:
            return cached

    repo = repo_cls(key[1])

    with _USER_SCOPE_REPO_CACHE_LOCK:
        return _USER_SCOPE_REPO_CACHE.setdefault(key, repo)


def _header_trust_enabled() -> bool:
    return os.environ.get(ROLE_HEADER_TRUST_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def validate_auth_startup_guardrails(settings: Settings) -> None:
    environment = str(settings.environment).strip().lower()
    if environment == "development":
        return

    if _header_trust_enabled():
        raise RuntimeError(
            f"{environment} environment cannot trust X-User-Id/X-User-Role headers "
            f"via {ROLE_HEADER_TRUST_ENV}; only development can enable this trust switch"
        )
    if os.environ.get("MOSS_USER_ID", "").strip() or os.environ.get("MOSS_USER_ROLE", "").strip():
        raise RuntimeError(
            f"{environment} environment cannot use MOSS_USER_ID/MOSS_USER_ROLE as an identity source; "
            "configure a verified gateway, session, token, or API-key identity provider instead"
        )
    cors_origins = [origin.strip() for origin in str(settings.cors_origins or "").split(",") if origin.strip()]
    if "*" in cors_origins:
        raise RuntimeError(
            f"{environment} environment cannot use wildcard CORS origins with credentialed API responses"
        )


def _role_header_trust_enabled() -> bool:
    return _header_trust_enabled()
