from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class JobRunState(Base):
    __tablename__ = "job_run_state"

    run_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    job_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    report_date: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_version: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor_version: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_rule_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
