from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.governance.locks import LockDefinition, acquire_lock
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool


CACHE_BUILD_RUN_STREAM = "cache_build_run"
CACHE_MANIFEST_STREAM = "cache_manifest"
SOURCE_MANIFEST_STREAM = "source_manifest"
SNAPSHOT_BUILD_RUN_STREAM = "snapshot_build_run"
SNAPSHOT_MANIFEST_STREAM = "snapshot_manifest"
VENDOR_SNAPSHOT_MANIFEST_STREAM = "vendor_snapshot_manifest"
VENDOR_VERSION_REGISTRY_STREAM = "vendor_version_registry"
SUPPORTED_SQL_STREAMS = frozenset({CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM})
SQL_BACKEND_MODES = frozenset({"sql-shadow", "sql-authority"})


@dataclass
class GovernanceRepository:
    base_dir: Path | str = Path("data/governance")
    sql_dsn: str = ""
    backend_mode: str = "jsonl"
    _sql_engine: Engine | None = field(init=False, default=None, repr=False)
    _sql_tables: dict[str, Table] = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if self.backend_mode not in {"jsonl", *SQL_BACKEND_MODES}:
            raise ValueError(f"Unsupported governance backend mode: {self.backend_mode}")
        if self.backend_mode != "jsonl" and not str(self.sql_dsn or "").strip():
            raise ValueError("sql_dsn is required when governance backend mode is not jsonl")
        if self._sql_enabled:
            self._sql_engine = create_engine(
                _normalize_sqlalchemy_dsn(self.sql_dsn),
                future=True,
                poolclass=NullPool,
            )
            metadata, tables = _build_sql_tables(
                use_public_schema=self._sql_engine.dialect.name != "sqlite"
            )
            metadata.create_all(self._sql_engine)
            self._sql_tables = tables

    def append(self, stream: str, payload: dict[str, object]) -> Path:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            if self._writes_sql(stream):
                assert self._sql_engine is not None
                with self._sql_engine.begin() as connection:
                    self._append_sql_unlocked(connection, stream, payload)
                    return self._append_unlocked(stream, payload)
            return self._append_unlocked(stream, payload)

    def _append_unlocked(self, stream: str, payload: dict[str, object]) -> Path:
        target = self.base_dir / f"{stream}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return target

    def append_many_atomic(self, entries: list[tuple[str, dict[str, object]]]) -> list[Path]:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            original_sizes: dict[Path, int] = {}
            try:
                if any(self._writes_sql(stream) for stream, _ in entries):
                    assert self._sql_engine is not None
                    with self._sql_engine.begin() as connection:
                        for stream, payload in entries:
                            if self._writes_sql(stream):
                                self._append_sql_unlocked(connection, stream, payload)
                        return self._append_many_jsonl_unlocked(
                            entries,
                            original_sizes=original_sizes,
                        )
                return self._append_many_jsonl_unlocked(
                    entries,
                    original_sizes=original_sizes,
                )
            except Exception:
                for target, size in original_sizes.items():
                    if not target.exists():
                        continue
                    with target.open("r+b") as handle:
                        handle.truncate(size)
                    if size == 0:
                        target.unlink(missing_ok=True)
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
        except Exception as exc:
            raise RuntimeError(f"SQL governance read failed for stream={stream}") from exc
        return [json.loads(str(row[0])) for row in rows]


def _build_sql_tables(*, use_public_schema: bool) -> tuple[MetaData, dict[str, Table]]:
    metadata = MetaData()
    schema = "public" if use_public_schema else None
    tables = {
        CACHE_BUILD_RUN_STREAM: Table(
            CACHE_BUILD_RUN_STREAM,
            metadata,
            Column("row_id", Integer, primary_key=True, autoincrement=True),
            Column("run_id", Text, nullable=False),
            Column("job_name", Text, nullable=False),
            Column("status", Text, nullable=False),
            Column("cache_key", Text, nullable=False),
            Column("lock", Text, nullable=True),
            Column("source_version", Text, nullable=True),
            Column("vendor_version", Text, nullable=True),
            Column("rule_version", Text, nullable=True),
            Column("started_at", Text, nullable=True),
            Column("finished_at", Text, nullable=True),
            Column("error_message", Text, nullable=True),
            Column("payload_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            schema=schema,
        ),
        CACHE_MANIFEST_STREAM: Table(
            CACHE_MANIFEST_STREAM,
            metadata,
            Column("row_id", Integer, primary_key=True, autoincrement=True),
            Column("cache_key", Text, nullable=False),
            Column("source_version", Text, nullable=True),
            Column("vendor_version", Text, nullable=True),
            Column("rule_version", Text, nullable=True),
            Column("payload_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            schema=schema,
        ),
    }
    return metadata, tables


def _sql_record_for_stream(stream: str, payload: dict[str, object]) -> dict[str, object]:
    created_at = _coerce_created_at(payload.get("created_at"))
    payload_json = json.dumps(payload, ensure_ascii=False)
    if stream == CACHE_BUILD_RUN_STREAM:
        return {
            "run_id": str(payload.get("run_id") or ""),
            "job_name": str(payload.get("job_name") or ""),
            "status": str(payload.get("status") or ""),
            "cache_key": str(payload.get("cache_key") or ""),
            "lock": _optional_text(payload.get("lock")),
            "source_version": _optional_text(payload.get("source_version")),
            "vendor_version": _optional_text(payload.get("vendor_version")),
            "rule_version": _optional_text(payload.get("rule_version")),
            "started_at": _optional_text(payload.get("started_at")),
            "finished_at": _optional_text(payload.get("finished_at")),
            "error_message": _optional_text(payload.get("error_message")),
            "payload_json": payload_json,
            "created_at": created_at,
        }
    if stream == CACHE_MANIFEST_STREAM:
        return {
            "cache_key": str(payload.get("cache_key") or ""),
            "source_version": _optional_text(payload.get("source_version")),
            "vendor_version": _optional_text(payload.get("vendor_version")),
            "rule_version": _optional_text(payload.get("rule_version")),
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
