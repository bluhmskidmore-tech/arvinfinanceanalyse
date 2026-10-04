from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.models.base import Base
from backend.app.models.governance import UserRoleScope
from backend.app.schemas.auth_context import UserScopeGrant
from backend.app.security.route_policy import HIGH_RISK_SCOPE_ACTIONS
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


@dataclass
class UserScopeRepository:
    dsn: str

    def __post_init__(self) -> None:
        self.dsn = _normalize_sqlalchemy_dsn(self.dsn)
        connect_args: dict[str, object] = {}
        if self.dsn.startswith("postgresql+psycopg://"):
            connect_args["connect_timeout"] = 1
        self.engine = create_engine(self.dsn, future=True, connect_args=connect_args)
        self._session_factory = sessionmaker(self.engine, future=True)
        if self.engine.dialect.name == "sqlite":
            Base.metadata.create_all(self.engine, tables=[UserRoleScope.__table__])

    def grant_scope(
        self,
        *,
        user_id: str,
        role: str | None,
        resource: str,
        action: str,
        scope_key: str | None = None,
        scope_value: str | None = None,
        is_active: bool = True,
        operator: str | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        normalized_user_id = user_id.strip()
        normalized_role = (role or "").strip() or None
        normalized_resource = resource.strip()
        normalized_action = action.strip()
        normalized_scope_key = (scope_key or "").strip() or None
        normalized_scope_value = (scope_value or "").strip() or None
        # Only grants bound to the viewer role are refused here. A role-less grant
        # (role=None) still authorizes any caller role in has_permission, so this is a
        # guard against an explicit "viewer may write" binding, not an authentication layer.
        if (
            (normalized_role or "").casefold() == "viewer"
            and normalized_action.casefold() in HIGH_RISK_SCOPE_ACTIONS
        ):
            raise ValueError(f"viewer role cannot be granted {normalized_action} action")

        now = datetime.now(UTC)
        with self._session_factory() as session:
            row = UserRoleScope(
                user_id=normalized_user_id,
                role=normalized_role,
                resource=normalized_resource,
                action=normalized_action,
                scope_key=normalized_scope_key,
                scope_value=normalized_scope_value,
                is_active=bool(is_active),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            result = self._to_dict(row)

        # TODO: Route this event to a dedicated SQL-backed governance stream once
        # that stream has an approved contract; structured logging is the interim audit channel.
        logger.info(
            "user_scope_grant_audit=%s",
            json.dumps(
                {
                    "event": "user_scope_grant",
                    "operator": (operator or "").strip() or "unspecified",
                    "target_user_id": normalized_user_id,
                    "role": normalized_role,
                    "resource": normalized_resource,
                    "action": normalized_action,
                    "scope_key": normalized_scope_key,
                    "scope_value": normalized_scope_value,
                    "is_active": bool(is_active),
                    "recorded_at": result["created_at"],
                    "reason": (reason or "").strip() or "unspecified",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return result

    def has_permission(
        self,
        *,
        user_id: str,
        role: str | None,
        resource: str,
        action: str,
        scope_key: str | None = None,
        scope_value: str | None = None,
    ) -> bool:
        normalized_user_id = user_id.strip()
        normalized_role = (role or "").strip()
        normalized_resource = resource.strip()
        normalized_action = action.strip()
        normalized_scope_key = (scope_key or "").strip()
        normalized_scope_value = (scope_value or "").strip()

        with self._session_factory() as session:
            stmt = (
                select(UserRoleScope)
                .where(UserRoleScope.is_active.is_(True))
                .where(UserRoleScope.resource == normalized_resource)
                .where(UserRoleScope.action == normalized_action)
                .where(
                    or_(
                        UserRoleScope.user_id == normalized_user_id,
                        UserRoleScope.user_id == "*",
                    )
                )
            )
            if normalized_role:
                stmt = stmt.where(
                    or_(
                        UserRoleScope.role.is_(None),
                        UserRoleScope.role == "",
                        UserRoleScope.role == normalized_role,
                    )
                )
            else:
                stmt = stmt.where(or_(UserRoleScope.role.is_(None), UserRoleScope.role == ""))
            global_scope = (
                or_(UserRoleScope.scope_key.is_(None), UserRoleScope.scope_key == ""),
                or_(UserRoleScope.scope_value.is_(None), UserRoleScope.scope_value == ""),
            )
            if normalized_scope_key or normalized_scope_value:
                stmt = stmt.where(
                    or_(
                        global_scope[0] & global_scope[1],
                        (UserRoleScope.scope_key == normalized_scope_key)
                        & (UserRoleScope.scope_value == normalized_scope_value),
                    )
                )
            else:
                stmt = stmt.where(global_scope[0]).where(global_scope[1])
            return session.execute(stmt).scalars().first() is not None

    def list_scopes_for_user(self, *, user_id: str) -> list[UserScopeGrant]:
        with self._session_factory() as session:
            stmt = (
                select(UserRoleScope)
                .where(UserRoleScope.user_id == user_id.strip())
                .where(UserRoleScope.is_active.is_(True))
                .order_by(UserRoleScope.resource.asc(), UserRoleScope.action.asc(), UserRoleScope.row_id.asc())
            )
            rows = session.execute(stmt).scalars().all()
        return [
            UserScopeGrant(
                user_id=row.user_id,
                role=row.role,
                resource=row.resource,
                action=row.action,
                scope_key=row.scope_key,
                scope_value=row.scope_value,
                is_active=row.is_active,
            )
            for row in rows
        ]

    @staticmethod
    def _to_dict(row: UserRoleScope) -> dict[str, object]:
        return {
            "row_id": row.row_id,
            "user_id": row.user_id,
            "role": row.role,
            "resource": row.resource,
            "action": row.action,
            "scope_key": row.scope_key,
            "scope_value": row.scope_value,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }


def _normalize_sqlalchemy_dsn(dsn: str) -> str:
    normalized = str(dsn or "").strip()
    if normalized.startswith("postgresql+psycopg://"):
        return normalized
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized[len("postgresql://") :]
    return normalized
