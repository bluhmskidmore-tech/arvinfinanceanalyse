from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.base import Base
from backend.app.models.job_state import JobRunState


@dataclass
class JobStateRepository:
    dsn: str

    def __post_init__(self) -> None:
        self.engine = create_engine(self.dsn, future=True)
        self._session_factory = sessionmaker(self.engine, future=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine, tables=[JobRunState.__table__])

    def record_transition(
        self,
        *,
        run_id: str,
        job_name: str,
        cache_key: str,
        status: str,
        report_date: str | None,
        source_version: str,
        vendor_version: str,
        rule_version: str | None = None,
        input_source_version: str | None = None,
        input_rule_version: str | None = None,
        trace_id: str | None = None,
        error_message: str | None = None,
        queued_at: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._session_factory() as session:
            row = session.get(JobRunState, run_id)
            if row is None:
                row = JobRunState(
                    run_id=run_id,
                    job_name=job_name,
                    cache_key=cache_key,
                    report_date=report_date,
                    status=status,
                    source_version=source_version,
                    vendor_version=vendor_version,
                    rule_version=rule_version,
                    input_source_version=input_source_version,
                    input_rule_version=input_rule_version,
                    trace_id=trace_id,
                    error_message=error_message,
                    queued_at=queued_at,
                    started_at=started_at,
                    finished_at=finished_at,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.job_name = job_name
                row.cache_key = cache_key
                row.report_date = report_date
                row.status = status
                row.source_version = source_version
                row.vendor_version = vendor_version
                row.rule_version = rule_version
                row.input_source_version = input_source_version
                row.input_rule_version = input_rule_version
                row.trace_id = trace_id
                row.error_message = error_message
                row.queued_at = queued_at or row.queued_at
                row.started_at = started_at or row.started_at
                row.finished_at = finished_at or row.finished_at
                row.updated_at = now
            session.commit()
            session.refresh(row)
            return _to_dict(row)

    def get_latest_run(self, run_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(JobRunState, run_id)
            return _to_dict(row) if row is not None else None

    def find_latest_inflight(
        self,
        *,
        job_name: str,
        cache_key: str,
        report_date: str | None,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = (
                select(JobRunState)
                .where(JobRunState.job_name == job_name)
                .where(JobRunState.cache_key == cache_key)
                .where(JobRunState.status.in_(("queued", "running")))
                .order_by(JobRunState.updated_at.desc())
            )
            if report_date is None:
                stmt = stmt.where(JobRunState.report_date.is_(None))
            else:
                stmt = stmt.where(JobRunState.report_date == report_date)
            row = session.execute(stmt).scalars().first()
            return _to_dict(row) if row is not None else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dict(row: JobRunState) -> dict[str, Any]:
    return {
        "run_id": row.run_id,
        "job_name": row.job_name,
        "cache_key": row.cache_key,
        "report_date": row.report_date,
        "status": row.status,
        "source_version": row.source_version,
        "vendor_version": row.vendor_version,
        "rule_version": row.rule_version,
        "input_source_version": row.input_source_version,
        "input_rule_version": row.input_rule_version,
        "trace_id": row.trace_id,
        "error_message": row.error_message,
        "queued_at": row.queued_at,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
