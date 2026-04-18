from __future__ import annotations

import json
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.governance.settings import (
    DEFAULT_POSTGRES_DSN,
    resolve_governance_sql_dsn,
    resolve_postgres_dsn,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.models.base import Base
from backend.app.models.governance import CacheBuildRun, CacheManifest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import Table

logger = logging.getLogger(__name__)


CACHE_BUILD_RUN_STREAM = "cache_build_run"
CACHE_MANIFEST_STREAM = "cache_manifest"
SOURCE_MANIFEST_STREAM = "source_manifest"
SNAPSHOT_BUILD_RUN_STREAM = "snapshot_build_run"
SNAPSHOT_MANIFEST_STREAM = "snapshot_manifest"
VENDOR_SNAPSHOT_MANIFEST_STREAM = "vendor_snapshot_manifest"
VENDOR_VERSION_REGISTRY_STREAM = "vendor_version_registry"
SUPPORTED_SQL_STREAMS = frozenset({CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM})
SQL_BACKEND_MODES = frozenset({"sql-shadow", "sql-authority"})
DEFAULT_GOVERNANCE_BACKEND = "jsonl"
STREAM_CONTRACT_FIELDS: dict[str, tuple[str, ...]] = {
    CACHE_BUILD_RUN_STREAM: (
        "run_id",
        "job_name",
        "status",
        "cache_key",
        "cache_version",
        "lock",
        "source_version",
        "vendor_version",
        "rule_version",
        "report_date",
        "queued_at",
        "started_at",
        "finished_at",
        "error_message",
        "failure_category",
        "failure_reason",
        "created_at",
    ),
    CACHE_MANIFEST_STREAM: (
        "cache_key",
        "cache_version",
        "source_version",
        "vendor_version",
        "rule_version",
        "module_name",
        "basis",
        "input_sources",
        "fact_tables",
        "lineage",
        "created_at",
    ),
}


@dataclass
class GovernanceRepository:
    base_dir: Path | str = Path("data/governance")
    sql_dsn: str = ""
    backend_mode: str = ""
    _sql_engine: Engine | None = field(init=False, default=None, repr=False)
    _sql_tables: dict[str, Table] = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.backend_mode = _resolve_governance_backend_mode(self.backend_mode)
        self.sql_dsn = _resolve_governance_sql_dsn_for_repo(self.sql_dsn, backend_mode=self.backend_mode)
        if self.backend_mode not in {"jsonl", *SQL_BACKEND_MODES}:
            raise ValueError(f"Unsupported governance backend mode: {self.backend_mode}")
        if self.backend_mode == "jsonl" and _is_production_environment():
            raise ValueError("production governance backend cannot use jsonl authority")
        if self.backend_mode != "jsonl" and not str(self.sql_dsn or "").strip():
            raise ValueError("sql_dsn is required when governance backend mode is not jsonl")
        if self._sql_enabled:
            self._sql_engine = create_engine(
                _normalize_sqlalchemy_dsn(self.sql_dsn),
                future=True,
                poolclass=NullPool,
            )
            self._sql_tables = {
                CACHE_BUILD_RUN_STREAM: CacheBuildRun.__table__,
                CACHE_MANIFEST_STREAM: CacheManifest.__table__,
            }
            if self._sql_engine.dialect.name == "sqlite":
                Base.metadata.create_all(
                    self._sql_engine,
                    tables=[CacheBuildRun.__table__, CacheManifest.__table__],
                )

    def append(self, stream: str, payload: dict[str, object]) -> Path:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            normalized_payload = self._normalize_payload_for_stream(stream, payload)
            target = self.base_dir / f"{stream}.jsonl"
            original_sizes = {target: target.stat().st_size if target.exists() else 0}
            if self._writes_sql(stream):
                assert self._sql_engine is not None
                with self._sql_engine.begin() as connection:
                    self._append_sql_unlocked(connection, stream, normalized_payload)
                    try:
                        return self._append_unlocked(stream, normalized_payload)
                    except Exception:
                        # Broad catch is intentional: any failure writing JSONL after
                        # the SQL commit must trigger a rollback regardless of error type.
                        self._rollback_jsonl_files(original_sizes)
                        raise
            try:
                return self._append_unlocked(stream, normalized_payload)
            except Exception:
                # Broad catch is intentional: any failure writing JSONL must trigger
                # a rollback to keep the file consistent regardless of error type.
                self._rollback_jsonl_files(original_sizes)
                raise

    def _append_unlocked(self, stream: str, payload: dict[str, object]) -> Path:
        target = self.base_dir / f"{stream}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return target

    def append_many_atomic(self, entries: list[tuple[str, dict[str, object]]]) -> list[Path]:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            original_sizes: dict[Path, int] = {}
            normalized_entries = [
                (stream, self._normalize_payload_for_stream(stream, payload))
                for stream, payload in entries
            ]
            try:
                if any(self._writes_sql(stream) for stream, _ in normalized_entries):
                    assert self._sql_engine is not None
                    with self._sql_engine.begin() as connection:
                        for stream, payload in normalized_entries:
                            if self._writes_sql(stream):
                                self._append_sql_unlocked(connection, stream, payload)
                        return self._append_many_jsonl_unlocked(
                            normalized_entries,
                            original_sizes=original_sizes,
                        )
                return self._append_many_jsonl_unlocked(
                    normalized_entries,
                    original_sizes=original_sizes,
                )
            except Exception:
                # Broad catch is intentional: any failure during atomic multi-stream
                # JSONL write must trigger a rollback regardless of error type.
                self._rollback_jsonl_files(original_sizes)
                raise

    def read_all(self, stream: str) -> list[dict[str, object]]:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            if self._reads_sql(stream):
                return self._read_all_sql(stream)
            target = self.base_dir / f"{stream}.jsonl"
            if not target.exists():
                return []
            return [
                json.loads(line)
                for line in target.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

    def _batch_lock(self) -> LockDefinition:
        digest = hashlib.sha256(str(self.base_dir).encode("utf-8")).hexdigest()[:8]
        return LockDefinition(
            key=f"lock:governance:jsonl:{digest}",
            ttl_seconds=30,
        )

    @property
    def _sql_enabled(self) -> bool:
        return bool(str(self.sql_dsn or "").strip()) and self.backend_mode in SQL_BACKEND_MODES

    def _writes_sql(self, stream: str) -> bool:
        return self._sql_enabled and stream in SUPPORTED_SQL_STREAMS

    def _reads_sql(self, stream: str) -> bool:
        return self.backend_mode == "sql-authority" and stream in SUPPORTED_SQL_STREAMS

    def _append_many_jsonl_unlocked(
        self,
        entries: list[tuple[str, dict[str, object]]],
        *,
        original_sizes: dict[Path, int],
    ) -> list[Path]:
        written_paths: list[Path] = []
        for stream, payload in entries:
            target = self.base_dir / f"{stream}.jsonl"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target not in original_sizes:
                original_sizes[target] = target.stat().st_size if target.exists() else 0
            written_paths.append(self._append_unlocked(stream, payload))
        return written_paths

    def _append_sql_unlocked(
        self,
        connection,
        stream: str,
        payload: dict[str, object],
    ) -> None:
        table = self._sql_tables[stream]
        record = _sql_record_for_stream(stream, payload)
        connection.execute(table.insert().values(**record))

    def _read_all_sql(self, stream: str) -> list[dict[str, Any]]:
        assert self._sql_engine is not None
        table = self._sql_tables[stream]
        try:
            with self._sql_engine.connect() as connection:
                rows = connection.execute(_read_all_sql_statement(stream, table)).fetchall()
        except SQLAlchemyError as exc:
            raise RuntimeError(f"SQL governance read failed for stream={stream}") from exc
        return [json.loads(str(row[0])) for row in rows]

    def read_latest_manifest(self, cache_key: str) -> dict[str, object] | None:
        cache_key_text = str(cache_key or "").strip()
        if not cache_key_text:
            return None
        rows = self.read_all(CACHE_MANIFEST_STREAM)
        for row in reversed(rows):
            if str(row.get("cache_key") or "").strip() == cache_key_text:
                return row
        return None

    def read_latest_completed_run(
        self,
        cache_key: str,
        *,
        job_name: str | None = None,
        report_date: str | None = None,
        require_source_version: bool = False,
    ) -> dict[str, object] | None:
        cache_key_text = str(cache_key or "").strip()
        if not cache_key_text:
            return None
        job_name_text = str(job_name or "").strip()
        report_date_text = str(report_date or "").strip()
        rows = self.read_all(CACHE_BUILD_RUN_STREAM)
        for row in reversed(rows):
            if str(row.get("cache_key") or "").strip() != cache_key_text:
                continue
            if str(row.get("status") or "").strip() != "completed":
                continue
            if job_name_text and str(row.get("job_name") or "").strip() != job_name_text:
                continue
            if report_date_text and str(row.get("report_date") or "").strip() != report_date_text:
                continue
            if require_source_version and not str(row.get("source_version") or "").strip():
                continue
            return row
        return None

    def _normalize_payload_for_stream(
        self,
        stream: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if stream not in STREAM_CONTRACT_FIELDS:
            return payload
        normalized = dict(payload)
        for field_name in STREAM_CONTRACT_FIELDS[stream]:
            normalized.setdefault(field_name, None)
        return normalized

    def _rollback_jsonl_files(self, original_sizes: dict[Path, int]) -> None:
        rollback_errors: list[Exception] = []
        for target, size in original_sizes.items():
            if not target.exists():
                continue
            try:
                with target.open("r+b") as handle:
                    handle.truncate(size)
                if size == 0:
                    target.unlink(missing_ok=True)
            except Exception as exc:
                # Broad catch is intentional: file truncation can fail with OSError,
                # PermissionError, or other IO errors — collect all and report together.
                rollback_errors.append(exc)
        if rollback_errors:
            raise RuntimeError(
                "Governance JSONL rollback failed; possible partial writes remain."
            ) from rollback_errors[0]


def _sql_record_for_stream(stream: str, payload: dict[str, object]) -> dict[str, object]:
    created_at = _coerce_created_at(payload.get("created_at"))
    payload_json = json.dumps(payload, ensure_ascii=False)
    if stream == CACHE_BUILD_RUN_STREAM:
        return {
            "run_id": str(payload.get("run_id") or ""),
            "job_name": str(payload.get("job_name") or ""),
            "status": str(payload.get("status") or ""),
            "cache_key": str(payload.get("cache_key") or ""),
            "cache_version": _optional_text(payload.get("cache_version")),
            "lock": _optional_text(payload.get("lock")),
            "source_version": _optional_text(payload.get("source_version")),
            "vendor_version": _optional_text(payload.get("vendor_version")),
            "rule_version": _optional_text(payload.get("rule_version")),
            "report_date": _optional_text(payload.get("report_date")),
            "queued_at": _optional_text(payload.get("queued_at")),
            "started_at": _optional_text(payload.get("started_at")),
            "finished_at": _optional_text(payload.get("finished_at")),
            "error_message": _optional_text(payload.get("error_message")),
            "failure_category": _optional_text(payload.get("failure_category")),
            "failure_reason": _optional_text(payload.get("failure_reason")),
            "payload_json": payload_json,
            "created_at": created_at,
        }
    if stream == CACHE_MANIFEST_STREAM:
        return {
            "cache_key": str(payload.get("cache_key") or ""),
            "cache_version": _optional_text(payload.get("cache_version")),
            "source_version": _optional_text(payload.get("source_version")),
            "vendor_version": _optional_text(payload.get("vendor_version")),
            "rule_version": _optional_text(payload.get("rule_version")),
            "module_name": _optional_text(payload.get("module_name")),
            "basis": _optional_text(payload.get("basis")),
            "payload_json": payload_json,
            "created_at": created_at,
        }
    raise KeyError(f"Unsupported SQL governance stream: {stream}")


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _coerce_created_at(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(text)


def _normalize_sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql+psycopg://"):
        return dsn
    if dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + dsn[len("postgresql://") :]
    return dsn


def _resolve_governance_backend_mode(backend_mode: str) -> str:
    normalized = str(backend_mode or "").strip()
    if normalized:
        return normalized
    env_mode = str(os.getenv("MOSS_GOVERNANCE_BACKEND", "")).strip()
    if env_mode:
        return env_mode
    if str(os.getenv("MOSS_ENVIRONMENT", "")).strip().lower() == "production":
        return "sql-authority"
    return DEFAULT_GOVERNANCE_BACKEND


def _is_production_environment() -> bool:
    return str(os.getenv("MOSS_ENVIRONMENT", "")).strip().lower() == "production"


def _resolve_governance_sql_dsn_for_repo(sql_dsn: str, *, backend_mode: str) -> str:
    normalized = str(sql_dsn or "").strip()
    if normalized:
        return normalized
    if backend_mode == "jsonl":
        return ""
    postgres_dsn = resolve_postgres_dsn(
        os.getenv("MOSS_POSTGRES_DSN", DEFAULT_POSTGRES_DSN),
    )
    return resolve_governance_sql_dsn(
        os.getenv("MOSS_GOVERNANCE_SQL_DSN", ""),
        postgres_dsn,
    )


def _read_all_sql_statement(stream: str, table: Table):
    if stream == CACHE_BUILD_RUN_STREAM:
        return select(table.c.payload_json).order_by(
            table.c.created_at.asc(),
            table.c.run_id.asc(),
            table.c.status.asc(),
        )
    if stream == CACHE_MANIFEST_STREAM:
        return select(table.c.payload_json).order_by(
            table.c.created_at.asc(),
            table.c.cache_key.asc(),
            table.c.source_version.asc(),
        )
    raise KeyError(f"Unsupported SQL governance stream: {stream}")
