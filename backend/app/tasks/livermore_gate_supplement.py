from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.tasks.broker import register_actor_once

LIVERMORE_GATE_SUPPLEMENT_LOCK = LockDefinition(
    key="lock:duckdb:livermore-gate-supplement",
    ttl_seconds=600,
)
RULE_VERSION = "rv_livermore_gate_supplement_v1"
REFRESH_JOB_NAME = "livermore_gate_supplement_refresh"
REFRESH_CACHE_KEY = "livermore_gate_supplement_daily"
REFRESH_CACHE_VERSION = "cv_livermore_gate_supplement_refresh_v1"
REFRESH_RULE_VERSION = "rv_livermore_gate_supplement_compute_v1"


def materialize_livermore_gate_supplement_daily(
    *,
    duckdb_path: str | None = None,
    rows: list[dict[str, Any]],
    run_id: str | None = None,
) -> dict[str, object]:
    """Write analytical Livermore gate supplement rows (breadth / limit-up flags). API-safe callers must not use."""
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    path = Path(duckdb_path or settings.duckdb_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    effective_run = run_id or f"livermore_gate_supplement:{uuid.uuid4().hex[:12]}"

    with acquire_lock(LIVERMORE_GATE_SUPPLEMENT_LOCK, base_dir=path.parent):
        conn = duckdb.connect(str(path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            conn.execute("begin transaction")
            dates: list[str] = []
            for raw in rows:
                td = raw.get("trade_date")
                if hasattr(td, "isoformat"):
                    dates.append(td.isoformat())  # type: ignore[union-attr]
                else:
                    dates.append(str(td))
            for d in sorted(set(dates)):
                conn.execute(
                    "delete from fact_livermore_gate_supplement_daily where trade_date = ?",
                    [d],
                )
            for raw in rows:
                td = raw["trade_date"]
                trade_date = td.isoformat() if hasattr(td, "isoformat") else str(td)
                b = raw.get("breadth_5d")
                breadth = float(b) if b is not None else None
                lim = raw.get("limit_up_quality_ok")
                lim_ok: bool | None
                if lim is None:
                    lim_ok = None
                else:
                    lim_ok = bool(lim)
                conn.execute(
                    """
                    insert into fact_livermore_gate_supplement_daily (
                      trade_date, breadth_5d, limit_up_quality_ok,
                      source_version, vendor_version, rule_version, run_id
                    ) values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        trade_date,
                        breadth,
                        lim_ok,
                        str(raw.get("source_version") or "sv_livermore_gate_supplement"),
                        str(raw.get("vendor_version") or "vv_livermore_gate_supplement"),
                        RULE_VERSION,
                        effective_run,
                    ],
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    return {
        "status": "completed",
        "run_id": effective_run,
        "row_count": len(rows),
        "rule_version": RULE_VERSION,
    }


materialize_livermore_gate_supplement_daily.fn = materialize_livermore_gate_supplement_daily


def _execute_livermore_gate_supplement_refresh(
    *,
    duckdb_path: str,
    as_of_date: str,
    lookback_days: int,
    min_observations_per_day: int | None = None,
) -> dict[str, object]:
    from backend.app.services.livermore_gate_supplement_compute_service import (
        compute_and_materialize_gate_supplement,
    )

    return compute_and_materialize_gate_supplement(
        duckdb_path=duckdb_path,
        as_of_date=date.fromisoformat(as_of_date),
        lookback_days=lookback_days,
        idempotency_key=None,
        min_observations_per_day=min_observations_per_day,
    )


def _invalidate_livermore_worker_caches() -> None:
    from backend.app.api.response_cache import market_home_response_cache

    market_home_response_cache.invalidate()


def run_livermore_gate_supplement_refresh(
    *,
    duckdb_path: str,
    governance_dir: str,
    run_id: str,
    as_of_date: str,
    lookback_days: int,
    min_observations_per_day: int | None = None,
    storage_target_digest: str | None = None,
    request_fingerprint: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    repo = GovernanceRepository(base_dir=governance_dir)
    base: dict[str, object] = {
        "run_id": run_id,
        "job_name": REFRESH_JOB_NAME,
        "cache_key": REFRESH_CACHE_KEY,
        "cache_version": REFRESH_CACHE_VERSION,
        "rule_version": REFRESH_RULE_VERSION,
        "report_date": as_of_date,
        "as_of_date": as_of_date,
        "lookback_days": int(lookback_days),
        "min_observations_per_day": min_observations_per_day,
        "duckdb_path": duckdb_path,
        "storage_target_digest": storage_target_digest,
        "request_fingerprint": request_fingerprint,
        "idempotency_key": idempotency_key,
    }
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **base,
            "status": "running",
            "trigger_mode": "async",
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    try:
        payload = _execute_livermore_gate_supplement_refresh(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            lookback_days=int(lookback_days),
            min_observations_per_day=min_observations_per_day,
        )
    except Exception as exc:
        repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **base,
                "status": "failed",
                "trigger_mode": "terminal",
                "finished_at": datetime.now(UTC).isoformat(),
                "error_message": str(exc),
                "failure_category": "materialization_failure",
                "failure_reason": type(exc).__name__,
            },
        )
        raise

    status = str(payload.get("status") or "completed")
    terminal = {
        **base,
        **payload,
        "status": status,
        "trigger_mode": "terminal",
        "finished_at": datetime.now(UTC).isoformat(),
        "result": payload,
    }
    repo.append(CACHE_BUILD_RUN_STREAM, terminal)
    if status == "completed":
        _invalidate_livermore_worker_caches()
    return terminal


run_livermore_gate_supplement_refresh_task = register_actor_once(
    "run_livermore_gate_supplement_refresh",
    run_livermore_gate_supplement_refresh,
    max_retries=3,
    time_limit_ms=3_600_000,
)
