from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select, create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.base import Base
from backend.app.models.governance import UserRoleScope
from backend.app.schemas.auth_context import UserScopeGrant


@dataclass
class UserScopeRepository:
    dsn: str

    def __post_init__(self) -> None:
        self.engine = create_engine(self.dsn, future=True)
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
    ) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            row = UserRoleScope(
                user_id=user_id.strip(),
                role=(role or "").strip() or None,
                resource=resource.strip(),
                action=action.strip(),
                scope_key=(scope_key or "").strip() or None,
                scope_value=(scope_value or "").strip() or None,
                is_active=bool(is_active),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_dict(row)

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
            if normalized_scope_key:
                stmt = stmt.where(
                    or_(
                        UserRoleScope.scope_key.is_(None),
                        UserRoleScope.scope_key == "",
                        UserRoleScope.scope_key == normalized_scope_key,
                    )
                )
            if normalized_scope_value:
                stmt = stmt.where(
                    or_(
                        UserRoleScope.scope_value.is_(None),
                        UserRoleScope.scope_value == "",
                        UserRoleScope.scope_value == normalized_scope_value,
                    )
                )
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
