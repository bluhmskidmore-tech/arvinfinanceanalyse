import getpass
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header


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


def _safe_getpass_user() -> str:
    try:
        return str(getpass.getuser() or "").strip()
    except Exception:
        return ""
