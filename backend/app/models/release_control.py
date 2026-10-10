from __future__ import annotations

from datetime import datetime

from backend.app.models.base import Base
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column


class ReleaseManifest(Base):
    """Immutable release content persisted by insert-only repository operations."""

    __tablename__ = "release_manifest"
    __table_args__ = (
        UniqueConstraint(
            "target_environment",
            "content_sha256",
            name="uq_release_manifest_environment_content_sha256",
        ),
        CheckConstraint(
            "length(content_sha256) = 64",
            name="ck_release_manifest_content_sha256_length",
        ),
        Index(
            "ix_release_manifest_environment_kind_created",
            "target_environment",
            "manifest_kind",
            "created_at",
        ),
    )

    release_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    target_environment: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReleaseEvent(Base):
    """Append-only release lifecycle event and its structured receipt."""

    __tablename__ = "release_event"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_release_event_event_id"),
        UniqueConstraint(
            "action",
            "target_environment",
            "release_id",
            "idempotency_key",
            name="uq_release_event_scoped_idempotency_key",
        ),
        CheckConstraint(
            "length(manifest_sha256) = 64",
            name="ck_release_event_manifest_sha256_length",
        ),
        CheckConstraint(
            "request_sha256 IS NULL OR length(request_sha256) = 64",
            name="ck_release_event_request_sha256_length",
        ),
        Index(
            "ix_release_event_release_occurred",
            "release_id",
            "occurred_at",
        ),
        Index(
            "ix_release_event_scope_occurred",
            "target_environment",
            "scope_kind",
            "scope_key",
            "occurred_at",
        ),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    release_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("release_manifest.release_id", name="fk_release_event_release_id"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_environment: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReleaseAlias(Base):
    """Environment-scoped current pointer updated through revision compare-and-swap."""

    __tablename__ = "release_alias"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="ck_release_alias_revision_nonnegative"),
        Index("ix_release_alias_current_release_id", "current_release_id"),
        Index("ix_release_alias_previous_release_id", "previous_release_id"),
    )

    target_environment: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    current_release_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("release_manifest.release_id", name="fk_release_alias_current_release_id"),
        nullable=False,
    )
    previous_release_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("release_manifest.release_id", name="fk_release_alias_previous_release_id"),
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    alias_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
