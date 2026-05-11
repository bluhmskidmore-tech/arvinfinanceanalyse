from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from backend.app.governance.settings import Settings
from backend.app.repositories.user_scope_repo import UserScopeRepository

DEFAULT_AUTH_USER_ID = "anonymous"
DEFAULT_AUTH_ROLE = "viewer"
ROLE_HEADER_TRUST_ENV = "MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST"


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

    if header_user_id:
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

    if _role_header_trust_enabled() and header_user_role:
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
        repo = UserScopeRepository(settings.governance_sql_dsn or settings.postgres_dsn)
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


def _role_header_trust_enabled() -> bool:
    return os.environ.get(ROLE_HEADER_TRUST_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
