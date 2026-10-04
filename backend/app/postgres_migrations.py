"""Run Alembic migrations against MOSS_POSTGRES_DSN."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from backend.app.governance.settings import DEFAULT_POSTGRES_DSN, resolve_postgres_dsn
from backend.app.storage_migration_flags import skip_postgres_migrations
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)
_MIGRATION_COMMAND = r".\.venv\Scripts\python.exe backend\scripts\migrate_storage.py"


class PostgresSchemaCurrentReceipt(TypedDict):
    storage: Literal["postgresql"]
    check: Literal["alembic_heads_current"]
    status: Literal["passed", "blocked", "error"]
    reason_code: str
    applied_heads: list[str] | None
    expected_heads: list[str] | None
    missing_heads: list[str]
    extra_heads: list[str]
    read_only: bool
    migration_command: str
    checked_at: str
    receipt_sha256: str


class PostgresSchemaReadinessError(RuntimeError):
    """Fail-closed PostgreSQL readiness error with a credential-safe receipt."""

    def __init__(self, receipt: PostgresSchemaCurrentReceipt) -> None:
        self.receipt = receipt
        applied = _format_heads_for_message(receipt["applied_heads"])
        expected = _format_heads_for_message(receipt["expected_heads"])
        super().__init__(
            "PostgreSQL schema readiness failed "
            f"(reason={receipt['reason_code']}; applied={applied}; expected={expected}). "
            f"Run {receipt['migration_command']} before starting the API or worker."
        )


def _format_heads_for_message(heads: list[str] | None) -> str:
    if heads is None:
        return "unavailable"
    if not heads:
        return "none"
    return ",".join(heads)


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical_sha256(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _build_schema_receipt(
    *,
    status: Literal["passed", "blocked", "error"],
    reason_code: str,
    applied_heads: tuple[str, ...] | None,
    expected_heads: tuple[str, ...] | None,
    read_only: bool,
    checked_at: str,
) -> PostgresSchemaCurrentReceipt:
    applied_set = set(applied_heads or ())
    expected_set = set(expected_heads or ())
    payload: dict[str, object] = {
        "storage": "postgresql",
        "check": "alembic_heads_current",
        "status": status,
        "reason_code": reason_code,
        "applied_heads": list(applied_heads) if applied_heads is not None else None,
        "expected_heads": list(expected_heads) if expected_heads is not None else None,
        "missing_heads": sorted(expected_set - applied_set),
        "extra_heads": sorted(applied_set - expected_set),
        "read_only": read_only,
        "migration_command": _MIGRATION_COMMAND,
        "checked_at": checked_at,
    }
    payload["receipt_sha256"] = _canonical_sha256(payload)
    return cast(PostgresSchemaCurrentReceipt, payload)


def _normalize_heads(heads: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(head).strip() for head in heads if str(head).strip()}))


def _normalized_sqlalchemy_dsn(postgres_dsn: str | None, *, backend_root: Path) -> str:
    raw_dsn = (
        postgres_dsn
        if postgres_dsn is not None
        else os.environ.get("MOSS_POSTGRES_DSN", DEFAULT_POSTGRES_DSN)
    )
    normalized_dsn = resolve_postgres_dsn(raw_dsn, repo_root=backend_root.parent)
    if normalized_dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized_dsn[len("postgresql://") :]
    return normalized_dsn


def _load_script_heads(*, backend_root: Path) -> tuple[str, ...]:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return _normalize_heads(ScriptDirectory.from_config(config).get_heads())


def assert_postgres_schema_current(
    *,
    postgres_dsn: str | None = None,
    connect_timeout_seconds: int = 5,
) -> PostgresSchemaCurrentReceipt:
    """Assert exact Alembic head-set equality without issuing DDL or DML."""

    checked_at = _utc_now_text()
    backend_root = Path(__file__).resolve().parents[1]
    expected_heads: tuple[str, ...] = ()
    script_configuration_failed = False
    try:
        expected_heads = _normalize_heads(_load_script_heads(backend_root=backend_root))
    except Exception:
        script_configuration_failed = True
    if script_configuration_failed or not expected_heads:
        receipt = _build_schema_receipt(
            status="error",
            reason_code="script_configuration_failed",
            applied_heads=None,
            expected_heads=None,
            read_only=False,
            checked_at=checked_at,
        )
        raise PostgresSchemaReadinessError(receipt)

    engine = None
    connected = False
    read_only = False
    applied_heads: tuple[str, ...] = ()
    failure_reason: str | None = None
    try:
        normalized_dsn = _normalized_sqlalchemy_dsn(postgres_dsn, backend_root=backend_root)
        connect_args: dict[str, object] = (
            {"connect_timeout": connect_timeout_seconds}
            if normalized_dsn.startswith("postgresql+")
            else {}
        )
        engine = create_engine(
            normalized_dsn,
            poolclass=NullPool,
            connect_args=connect_args,
        )
        with engine.connect() as connection:
            connected = True
            if connection.dialect.name == "postgresql":
                connection = connection.execution_options(postgresql_readonly=True)
                read_only_value = connection.exec_driver_sql("show transaction_read_only").scalar_one()
                if str(read_only_value).strip().casefold() not in {"on", "true", "1"}:
                    raise RuntimeError("PostgreSQL transaction is not read-only")
            read_only = True
            applied_heads = _normalize_heads(
                MigrationContext.configure(connection).get_current_heads()
            )
    except Exception:
        failure_reason = "database_unreachable" if not connected else "inspection_failed"
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                failure_reason = "inspection_failed"

    if failure_reason is not None:
        receipt = _build_schema_receipt(
            status="error",
            reason_code=failure_reason,
            applied_heads=None,
            expected_heads=expected_heads,
            read_only=read_only,
            checked_at=checked_at,
        )
        raise PostgresSchemaReadinessError(receipt)

    if not applied_heads:
        receipt = _build_schema_receipt(
            status="blocked",
            reason_code="migration_ledger_missing",
            applied_heads=applied_heads,
            expected_heads=expected_heads,
            read_only=read_only,
            checked_at=checked_at,
        )
        raise PostgresSchemaReadinessError(receipt)

    if set(applied_heads) != set(expected_heads):
        multiple_heads = len(applied_heads) > 1 or len(expected_heads) > 1
        receipt = _build_schema_receipt(
            status="blocked",
            reason_code=("multiple_head_mismatch" if multiple_heads else "head_mismatch"),
            applied_heads=applied_heads,
            expected_heads=expected_heads,
            read_only=read_only,
            checked_at=checked_at,
        )
        raise PostgresSchemaReadinessError(receipt)

    return _build_schema_receipt(
        status="passed",
        reason_code="current",
        applied_heads=applied_heads,
        expected_heads=expected_heads,
        read_only=read_only,
        checked_at=checked_at,
    )


def _wait_for_postgres_sql_ready(
    postgres_dsn: str,
    *,
    repo_root: Path,
    attempts: int = 5,
    retry_delay_seconds: float = 1.0,
) -> None:
    normalized_dsn = str(postgres_dsn or "").strip()
    if normalized_dsn.startswith("postgresql://"):
        normalized_dsn = "postgresql+psycopg://" + normalized_dsn[len("postgresql://") :]

    for attempt in range(1, attempts + 1):
        try:
            engine = create_engine(normalized_dsn, connect_args={"connect_timeout": 5})
            with engine.connect() as connection:
                connection.execute(text("select 1")).scalar()
            return
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(retry_delay_seconds)
        finally:
            if "engine" in locals():
                engine.dispose()


def upgrade_postgres_schema_head() -> None:
    if skip_postgres_migrations():
        return
    backend_root = Path(__file__).resolve().parents[1]
    ini_path = backend_root / "alembic.ini"
    env = os.environ.copy()
    env["MOSS_POSTGRES_DSN"] = resolve_postgres_dsn(
        env.get("MOSS_POSTGRES_DSN", DEFAULT_POSTGRES_DSN),
        repo_root=backend_root.parent,
    )
    # Run Alembic in a subprocess with cwd=backend (matches dev_postgres_cluster). In-process
    # `command.upgrade` under uvicorn on Windows has been observed to hang after DDL preamble.
    alembic_args = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ini_path),
        "upgrade",
        "head",
    ]
    for attempt in range(1, 4):
        result = subprocess.run(
            alembic_args,
            cwd=str(backend_root),
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return

        combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).lower()
        is_transient_connect_timeout = "connection timeout expired" in combined_output
        if is_transient_connect_timeout and attempt < 3:
            _wait_for_postgres_sql_ready(env["MOSS_POSTGRES_DSN"], repo_root=backend_root.parent)
            continue

        if result.stdout:
            logger.error(result.stdout)
        if result.stderr:
            logger.error(result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            alembic_args,
            output=result.stdout,
            stderr=result.stderr,
        )
