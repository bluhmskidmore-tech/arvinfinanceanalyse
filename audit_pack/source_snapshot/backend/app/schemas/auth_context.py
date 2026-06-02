from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserScopeGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    role: str | None = None
    resource: str
    action: str
    scope_key: str | None = None
    scope_value: str | None = None
    is_active: bool = True
