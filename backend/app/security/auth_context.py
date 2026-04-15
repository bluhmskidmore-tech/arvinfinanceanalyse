from __future__ import annotations

import getpass
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from backend.app.governance.settings import Settings
from backend.app.repositories.user_scope_repo import UserScopeRepository


@dataclass(frozen=True)
class AuthContext:
    user_id: str = "phase1-dev-user"
    role: str = "admin"
    identity_source: str = "fallback"


def get_auth_context(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> AuthContext:
    header_user_id = (x_user_id or "").strip()
    env_user_id = os.environ.get("MOSS_USER_ID", "").strip()
    system_user_id = (
        os.environ.get("USERNAME", "").strip()
        or os.environ.get("USER", "").strip()
        or _safe_getpass_user()
    )

    if header_user_id:
        user_id = header_user_id
        identity_source = "header"
    elif env_user_id:
        user_id = env_user_id
        identity_source = "env"
    elif system_user_id:
        user_id = system_user_id
        identity_source = "system"
    else:
        user_id = AuthContext().user_id
        identity_source = "fallback"

    role = (
        (x_user_role or "").strip()
        or os.environ.get("MOSS_USER_ROLE", "").strip()
        or AuthContext().role
    )
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
    raise PermissionError(f"User is not allowed to {action} {resource}.")


def _safe_getpass_user() -> str:
    try:
        return str(getpass.getuser() or "").strip()
    except Exception:
        return ""
