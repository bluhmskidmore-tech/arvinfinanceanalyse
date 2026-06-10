from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock
from typing import Annotated

from backend.app.governance.settings import Settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from fastapi import Header

DEFAULT_AUTH_USER_ID = "anonymous"
DEFAULT_AUTH_ROLE = "viewer"
ROLE_HEADER_TRUST_ENV = "MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST"
_USER_SCOPE_REPO_CACHE: dict[tuple[object, str], UserScopeRepository] = {}
_USER_SCOPE_REPO_CACHE_LOCK = Lock()


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
    try:
        repo = _get_user_scope_repository(settings.governance_sql_dsn or settings.postgres_dsn)
        if repo.has_permission(
            user_id=auth.user_id,
            role=auth.role,
            resource=resource,
            action=action,
            scope_key=scope_key,
            scope_value=scope_value,
        ):
            return
    except Exception as exc:
        raise RuntimeError("User scope store is unavailable.") from exc
    raise PermissionError(f"User is not allowed to {action} {resource}.")


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
