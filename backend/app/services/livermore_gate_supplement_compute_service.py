"""Compute breadth_5d and limit_up_quality_ok from landed market data.

Preferred basis — **market_breadth**: real all-market advance/decline and
limit-up seal/break counts aggregated from ``choice_stock_daily_observation``
(see :mod:`backend.app.core_finance.market_breadth` for the formal
definitions and :mod:`backend.app.tasks.market_breadth_materialize` for the
DuckDB write path).

Fallback basis — **csi300_proxy** (legacy behavior, unchanged): when the
all-market source table is not landed, derive proxy inputs from CSI300 daily
returns (fact_choice_macro_daily / choice_market_snapshot):

- Breadth proxy: net up-days (up_days - down_days) over the 5-day window of
  CSI300 daily returns ending at the current trade date, so the gate's
  ``breadth_5d > 0`` check keeps the same sign semantics as the formal basis.
- Limit-up quality proxy: a simplified signal based on CSI300 return
  characteristics.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, TypeAlias, cast

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository

GovernanceRecord: TypeAlias = dict[str, object]


class _LivermoreGateSupplementMaterializer(Protocol):
    def __call__(
        self,
        *,
        duckdb_path: str | None = None,
        rows: list[dict[str, Any]],
        run_id: str | None = None,
    ) -> dict[str, object]: ...


class _MarketBreadthMaterializer(Protocol):
    def __call__(
        self,
        *,
        duckdb_path: str,
        as_of_date: date,
        lookback_days: int,
        min_observations_per_day: int | None = None,
    ) -> dict[str, object]: ...


class _LivermoreRefreshTaskActor(Protocol):
    def send(
        self,
        *,
        duckdb_path: str,
        governance_dir: str,
        run_id: str,
        as_of_date: str,
        lookback_days: int,
        min_observations_per_day: int | None = None,
        storage_target_digest: str,
        request_fingerprint: str,
        idempotency_key: str | None = None,
    ) -> object: ...


def materialize_livermore_gate_supplement_daily(
    *,
    duckdb_path: str | None = None,
    rows: list[dict[str, Any]],
    run_id: str | None = None,
) -> dict[str, object]:
    """Lazy bridge keeps task registration out of the HTTP service import path."""
    from backend.app.tasks.livermore_gate_supplement import (
        materialize_livermore_gate_supplement_daily as _materialize,
    )

    typed_materialize = cast(_LivermoreGateSupplementMaterializer, _materialize)
    return typed_materialize(
        duckdb_path=duckdb_path,
        rows=rows,
        run_id=run_id,
    )


def materialize_market_breadth_daily(
    *,
    duckdb_path: str,
    as_of_date: date,
    lookback_days: int,
    min_observations_per_day: int | None = None,
) -> dict[str, object]:
    """Lazy bridge keeps market-breadth write tasks worker-owned."""
    from backend.app.tasks.market_breadth_materialize import (
        materialize_market_breadth_daily as _materialize,
    )

    typed_materialize = cast(_MarketBreadthMaterializer, _materialize)
    return typed_materialize(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        min_observations_per_day=min_observations_per_day,
    )


class _RunLivermoreGateSupplementRefreshTaskProxy:
    def send(
        self,
        *,
        duckdb_path: str,
        governance_dir: str,
        run_id: str,
        as_of_date: str,
        lookback_days: int,
        min_observations_per_day: int | None = None,
        storage_target_digest: str,
        request_fingerprint: str,
        idempotency_key: str | None = None,
    ) -> object:
        from backend.app.tasks.livermore_gate_supplement import (
            run_livermore_gate_supplement_refresh_task as _actor,
        )

        typed_actor = cast(_LivermoreRefreshTaskActor, _actor)
        return typed_actor.send(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            run_id=run_id,
            as_of_date=as_of_date,
            lookback_days=lookback_days,
            min_observations_per_day=min_observations_per_day,
            storage_target_digest=storage_target_digest,
            request_fingerprint=request_fingerprint,
            idempotency_key=idempotency_key,
        )


run_livermore_gate_supplement_refresh_task: _LivermoreRefreshTaskActor = (
    _RunLivermoreGateSupplementRefreshTaskProxy()
)

logger = logging.getLogger(__name__)

RULE_VERSION = "rv_livermore_gate_supplement_compute_v1"
LIVERMORE_GATE_SUPPLEMENT_MATERIALIZE_RULE_VERSION = "rv_livermore_gate_supplement_v1"
BROAD_INDEX_SERIES_ID = "CA.CSI300"
PCT_CHG_SERIES_ID = "CA.CSI300_PCT_CHG"
BREADTH_WINDOW = 5
# Minimum number of historical daily returns needed to compute supplement.
MIN_HISTORY_FOR_SUPPLEMENT = BREADTH_WINDOW + 1
LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME = "livermore_gate_supplement_refresh"
LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY = "livermore_gate_supplement_daily"
LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION = "cv_livermore_gate_supplement_refresh_v1"
LIVERMORE_GATE_SUPPLEMENT_REFRESH_LOCK_TIMEOUT_SECONDS = 30.0
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS = 300.0
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_LOCK_ATTEMPT_SECONDS = 0.25
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_SECONDS = 0.05
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_MAX_SECONDS = 1.0
LIVERMORE_GATE_SUPPLEMENT_STATUS_RECONCILE_LOCK_TIMEOUT_SECONDS = 0.5
_LIVERMORE_REFRESH_IN_FLIGHT_STATUSES = {"queued", "running", "retrying"}
_LIVERMORE_REFRESH_STALE_AFTER = timedelta(hours=1)


class LivermoreGateSupplementRefreshConflictError(RuntimeError):
    pass


class LivermoreGateSupplementRefreshQueueError(RuntimeError):
    pass


def _append_stale_livermore_refresh_failure(
    repo: GovernanceRepository,
    record: GovernanceRecord,
) -> GovernanceRecord:
    stale_failure: GovernanceRecord = {
        **record,
        "status": "failed",
        "trigger_mode": "terminal",
        "finished_at": datetime.now(UTC).isoformat(),
        "error_message": "Marked stale Livermore gate-supplement refresh as failed.",
        "failure_category": "stale_inflight",
        "failure_reason": "stale_inflight",
    }
    repo.append(CACHE_BUILD_RUN_STREAM, stale_failure)
    return stale_failure


def queue_gate_supplement_refresh(
    *,
    duckdb_path: str,
    governance_path: str,
    as_of_date: date | None = None,
    lookback_days: int = 30,
    idempotency_key: str | None = None,
    min_observations_per_day: int | None = None,
) -> dict[str, object]:
    if int(lookback_days) < 7 or int(lookback_days) > 365:
        raise ValueError("lookback_days must be between 7 and 365.")
    target_date = as_of_date or date.today()
    target_date_text = target_date.isoformat()
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    storage_target_digest = _storage_target_digest(duckdb_path)
    request_fingerprint = hashlib.sha256(
        repr(
            (
                storage_target_digest,
                target_date_text,
                int(lookback_days),
                min_observations_per_day,
            )
        ).encode("utf-8")
    ).hexdigest()
    trigger_lock = _refresh_trigger_lock(
        as_of_date=target_date_text,
        lookback_days=int(lookback_days),
        storage_target_digest=storage_target_digest,
    )
    repo = GovernanceRepository(base_dir=governance_path)
    try:
        with acquire_lock(trigger_lock, base_dir=governance_path, timeout_seconds=0.1):
            records = _queued_livermore_refresh_records(repo)
            if normalized_idempotency_key is not None:
                for record in _latest_livermore_refresh_records_for_request(
                    records,
                    request_fingerprint=request_fingerprint,
                    as_of_date=target_date_text,
                    lookback_days=int(lookback_days),
                    storage_target_digest=storage_target_digest,
                    idempotency_key=normalized_idempotency_key,
                ):
                    status = str(record.get("status") or "")
                    if (
                        status in _LIVERMORE_REFRESH_IN_FLIGHT_STATUSES
                        and _livermore_refresh_record_is_stale(record)
                    ):
                        _append_stale_livermore_refresh_failure(repo, record)
                        records = _queued_livermore_refresh_records(repo)
                        break
                    if _livermore_refresh_record_is_retryable_stale_failure(record):
                        continue
                    return _normalize_livermore_refresh_record(record, idempotency_replay=True)

            latest_by_run_id: dict[str, GovernanceRecord] = {}
            for record in records:
                if _livermore_refresh_record_matches_request(
                    record,
                    request_fingerprint=request_fingerprint,
                    as_of_date=target_date_text,
                    lookback_days=int(lookback_days),
                    storage_target_digest=storage_target_digest,
                ):
                    latest_by_run_id[str(record.get("run_id") or "")] = record
            fresh_active_records: list[GovernanceRecord] = []
            for record in latest_by_run_id.values():
                if str(record.get("status") or "") not in _LIVERMORE_REFRESH_IN_FLIGHT_STATUSES:
                    continue
                if _livermore_refresh_record_is_stale(record):
                    _append_stale_livermore_refresh_failure(repo, record)
                else:
                    fresh_active_records.append(record)
            if fresh_active_records:
                raise LivermoreGateSupplementRefreshConflictError(
                    f"Livermore gate-supplement refresh already in progress for as_of_date={target_date_text}."
                )

            queued_at = datetime.now(UTC).isoformat()
            run_id = (
                f"{LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME}:"
                f"{target_date_text}:{uuid.uuid4().hex[:12]}"
            )
            queued_payload: dict[str, object] = {
                "run_id": run_id,
                "job_name": LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME,
                "status": "queued",
                "trigger_mode": "async",
                "cache_key": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY,
                "cache_version": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION,
                "lock": trigger_lock.key,
                "source_version": "sv_pending",
                "vendor_version": "vv_pending",
                "rule_version": RULE_VERSION,
                "report_date": target_date_text,
                "as_of_date": target_date_text,
                "lookback_days": int(lookback_days),
                "min_observations_per_day": min_observations_per_day,
                "duckdb_path": str(duckdb_path),
                "storage_target_digest": storage_target_digest,
                "request_fingerprint": request_fingerprint,
                "idempotency_key": normalized_idempotency_key,
                "queued_at": queued_at,
            }
            repo.append(CACHE_BUILD_RUN_STREAM, queued_payload)
            try:
                run_livermore_gate_supplement_refresh_task.send(
                    duckdb_path=str(duckdb_path),
                    governance_dir=str(governance_path),
                    run_id=run_id,
                    as_of_date=target_date_text,
                    lookback_days=int(lookback_days),
                    min_observations_per_day=min_observations_per_day,
                    storage_target_digest=storage_target_digest,
                    request_fingerprint=request_fingerprint,
                    idempotency_key=normalized_idempotency_key,
                )
            except Exception as exc:
                repo.append(
                    CACHE_BUILD_RUN_STREAM,
                    {
                        **queued_payload,
                        "status": "failed",
                        "trigger_mode": "terminal",
                        "finished_at": datetime.now(UTC).isoformat(),
                        "error_message": str(exc),
                        "failure_category": "queue_dispatch_failure",
                        "failure_reason": "queue_dispatch_failed",
                    },
                )
                raise LivermoreGateSupplementRefreshQueueError(
                    "Livermore gate-supplement refresh queue dispatch failed."
                ) from exc
    except TimeoutError as exc:
        raise LivermoreGateSupplementRefreshConflictError(
            f"Livermore gate-supplement refresh already in progress for as_of_date={target_date_text}."
        ) from exc

    return _normalize_livermore_refresh_record(queued_payload, idempotency_replay=False)


def livermore_gate_supplement_refresh_status(
    governance_path: str | Path,
    *,
    run_id: str = "",
) -> dict[str, object]:
    repo = GovernanceRepository(base_dir=governance_path)
    records = _queued_livermore_refresh_records(repo)
    run_id_text = str(run_id or "").strip()
    if run_id_text:
        latest = _latest_livermore_refresh_record(records, run_id=run_id_text)
        if latest is None:
            raise ValueError(f"Livermore gate-supplement refresh run not found: {run_id_text}")
        return _normalize_livermore_refresh_record(
            _reconcile_stale_livermore_refresh_record(
                repo,
                governance_path=governance_path,
                run_id=run_id_text,
            ),
            idempotency_replay=None,
        )
    if not records:
        return {
            "status": "idle",
            "run_id": None,
            "job_name": LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME,
            "cache_key": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY,
            "cache_version": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION,
            "rule_version": RULE_VERSION,
            "trigger_mode": "idle",
            "idempotency_replay": False,
        }
    latest = records[-1]
    latest_run_id = str(latest.get("run_id") or "").strip()
    if latest_run_id:
        latest = _reconcile_stale_livermore_refresh_record(
            repo,
            governance_path=governance_path,
            run_id=latest_run_id,
        )
    return _normalize_livermore_refresh_record(latest, idempotency_replay=None)


def _queued_livermore_refresh_records(repo: GovernanceRepository) -> list[GovernanceRecord]:
    return [
        record
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key") or "") == LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY
        and str(record.get("job_name") or "") == LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME
    ]


def _livermore_refresh_record_matches_request(
    record: GovernanceRecord,
    *,
    request_fingerprint: str,
    as_of_date: str,
    lookback_days: int,
    storage_target_digest: str,
) -> bool:
    recorded_fingerprint = str(record.get("request_fingerprint") or "").strip()
    if recorded_fingerprint:
        return recorded_fingerprint == request_fingerprint
    return (
        str(record.get("as_of_date") or record.get("report_date") or "") == as_of_date
        and str(record.get("lookback_days") or "") == str(int(lookback_days))
        and str(record.get("storage_target_digest") or "") == storage_target_digest
    )


def _latest_livermore_refresh_record(
    records: list[GovernanceRecord],
    *,
    run_id: str,
) -> GovernanceRecord | None:
    matching = [record for record in records if str(record.get("run_id") or "") == run_id]
    return matching[-1] if matching else None


def _latest_livermore_refresh_records_for_request(
    records: list[GovernanceRecord],
    *,
    request_fingerprint: str,
    as_of_date: str,
    lookback_days: int,
    storage_target_digest: str,
    idempotency_key: str,
) -> list[GovernanceRecord]:
    latest_records: list[GovernanceRecord] = []
    seen_run_ids: set[str] = set()
    for record in reversed(records):
        run_id = str(record.get("run_id") or "").strip()
        if not run_id or run_id in seen_run_ids:
            continue
        if not _livermore_refresh_record_matches_request(
            record,
            request_fingerprint=request_fingerprint,
            as_of_date=as_of_date,
            lookback_days=lookback_days,
            storage_target_digest=storage_target_digest,
        ):
            continue
        if str(record.get("idempotency_key") or "").strip() != idempotency_key:
            continue
        seen_run_ids.add(run_id)
        latest_records.append(record)
    return latest_records


def _livermore_refresh_record_is_retryable_stale_failure(record: GovernanceRecord) -> bool:
    return (
        str(record.get("status") or "") == "failed"
        and str(record.get("failure_category") or "") == "stale_inflight"
    )


def _livermore_refresh_status_reconcile_lock(run_id: str) -> LockDefinition:
    return LockDefinition(
        key=f"lock:livermore-gate-supplement-refresh-status:{run_id}",
        ttl_seconds=30,
    )


def _reconcile_stale_livermore_refresh_record(
    repo: GovernanceRepository,
    *,
    governance_path: str | Path,
    run_id: str,
) -> GovernanceRecord:
    def _latest_for_run() -> GovernanceRecord:
        latest = _latest_livermore_refresh_record(_queued_livermore_refresh_records(repo), run_id=run_id)
        if latest is None:
            raise ValueError(f"Livermore gate-supplement refresh run not found: {run_id}")
        return latest

    latest = _latest_for_run()
    if (
        str(latest.get("status") or "") not in _LIVERMORE_REFRESH_IN_FLIGHT_STATUSES
        or not _livermore_refresh_record_is_stale(latest)
    ):
        return latest

    try:
        with acquire_lock(
            _livermore_refresh_status_reconcile_lock(run_id),
            base_dir=governance_path,
            timeout_seconds=LIVERMORE_GATE_SUPPLEMENT_STATUS_RECONCILE_LOCK_TIMEOUT_SECONDS,
        ):
            refreshed = _latest_for_run()
            if (
                str(refreshed.get("status") or "") in _LIVERMORE_REFRESH_IN_FLIGHT_STATUSES
                and _livermore_refresh_record_is_stale(refreshed)
            ):
                return _append_stale_livermore_refresh_failure(repo, refreshed)
            return refreshed
    except TimeoutError:
        return _latest_for_run()


def _normalize_livermore_refresh_record(
    record: GovernanceRecord,
    *,
    idempotency_replay: bool | None,
) -> dict[str, object]:
    status = str(record.get("status") or "").strip() or "failed"
    normalized: dict[str, object] = {
        "run_id": str(record.get("run_id") or "") or None,
        "job_name": LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME,
        "status": status,
        "trigger_mode": (
            "async"
            if status in _LIVERMORE_REFRESH_IN_FLIGHT_STATUSES
            else "idle" if status == "idle" else "terminal"
        ),
        "cache_key": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY,
        "cache_version": str(record.get("cache_version") or LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION),
        "rule_version": str(record.get("rule_version") or RULE_VERSION),
        "report_date": str(record.get("report_date") or record.get("as_of_date") or "") or None,
        "as_of_date": str(record.get("as_of_date") or record.get("report_date") or "") or None,
        "lookback_days": _coerce_optional_int(record.get("lookback_days")),
        "min_observations_per_day": _coerce_optional_int(record.get("min_observations_per_day")),
        "queued_at": str(record.get("queued_at") or "") or None,
        "started_at": str(record.get("started_at") or "") or None,
        "finished_at": str(record.get("finished_at") or "") or None,
        "basis": str(record.get("basis") or "") or None,
        "computed_rows": _coerce_optional_int(record.get("computed_rows")),
        "first_date": str(record.get("first_date") or "") or None,
        "last_date": str(record.get("last_date") or "") or None,
        "message": str(record.get("message") or "") or None,
        "failure_category": str(record.get("failure_category") or "") or None,
        "failure_reason": str(record.get("failure_reason") or "") or None,
        "error_message": str(record.get("error_message") or "") or None,
        "idempotency_key": _normalize_idempotency_key(str(record.get("idempotency_key") or "")),
        "idempotency_replay": False if idempotency_replay is None else idempotency_replay,
    }
    result = record.get("result")
    if isinstance(result, dict):
        normalized["result"] = result
    return normalized


def _livermore_refresh_record_is_stale(record: dict[str, object]) -> bool:
    for field_name in ("started_at", "queued_at", "created_at"):
        raw_value = str(record.get(field_name) or "").strip()
        if not raw_value:
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return datetime.now(UTC) - parsed > _LIVERMORE_REFRESH_STALE_AFTER
    return True


def compute_and_materialize_gate_supplement(
    *,
    duckdb_path: str,
    as_of_date: date | None = None,
    lookback_days: int = 30,
    idempotency_key: str | None = None,
    min_observations_per_day: int | None = None,
) -> dict[str, object]:
    """Compute breadth_5d + limit_up_quality_ok and write to DuckDB supplement table.

    Returns a summary dict suitable for API response.
    """
    target_date = as_of_date or date.today()
    target_date_text = target_date.isoformat()
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    storage_target_digest = _storage_target_digest(duckdb_path)
    settings = get_settings()

    lock_definition = _refresh_trigger_lock(
        as_of_date=target_date_text,
        lookback_days=lookback_days,
        storage_target_digest=storage_target_digest,
    )
    if normalized_idempotency_key is not None:
        return _run_idempotent_refresh(
            duckdb_path=duckdb_path,
            target_date=target_date,
            target_date_text=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=normalized_idempotency_key,
            storage_target_digest=storage_target_digest,
            lock_definition=lock_definition,
            min_observations_per_day=min_observations_per_day,
        )

    with acquire_lock(
        lock_definition,
        base_dir=settings.governance_path,
        timeout_seconds=LIVERMORE_GATE_SUPPLEMENT_REFRESH_LOCK_TIMEOUT_SECONDS,
    ):
        return _compute_gate_supplement_payload(
            duckdb_path=duckdb_path,
            target_date=target_date,
            target_date_text=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=None,
            storage_target_digest=storage_target_digest,
            min_observations_per_day=min_observations_per_day,
        )


def _run_idempotent_refresh(
    *,
    duckdb_path: str,
    target_date: date,
    target_date_text: str,
    lookback_days: int,
    idempotency_key: str,
    storage_target_digest: str,
    lock_definition: LockDefinition,
    min_observations_per_day: int | None = None,
) -> dict[str, object]:
    settings = get_settings()
    deadline = time.monotonic() + LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS
    poll_seconds = LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_SECONDS

    while True:
        existing_run = _latest_refresh_for_idempotency_key(
            as_of_date=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=idempotency_key,
            storage_target_digest=storage_target_digest,
        )
        if existing_run is not None:
            return _idempotent_refresh_response(existing_run)

        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            existing_run = _latest_refresh_for_idempotency_key(
                as_of_date=target_date_text,
                lookback_days=lookback_days,
                idempotency_key=idempotency_key,
                storage_target_digest=storage_target_digest,
            )
            if existing_run is not None:
                return _idempotent_refresh_response(existing_run)
            raise TimeoutError(
                "Timed out waiting for Livermore gate supplement idempotency replay "
                f"as_of_date={target_date_text} lookback_days={int(lookback_days)}."
            )

        acquired_lock = False
        try:
            with acquire_lock(
                lock_definition,
                base_dir=settings.governance_path,
                timeout_seconds=min(
                    LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_LOCK_ATTEMPT_SECONDS,
                    remaining_seconds,
                ),
                poll_interval_seconds=min(
                    LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_SECONDS,
                    max(remaining_seconds, 0.0),
                ),
            ):
                acquired_lock = True
                existing_run = _latest_refresh_for_idempotency_key(
                    as_of_date=target_date_text,
                    lookback_days=lookback_days,
                    idempotency_key=idempotency_key,
                    storage_target_digest=storage_target_digest,
                )
                if existing_run is not None:
                    return _idempotent_refresh_response(existing_run)
                return _compute_gate_supplement_payload(
                    duckdb_path=duckdb_path,
                    target_date=target_date,
                    target_date_text=target_date_text,
                    lookback_days=lookback_days,
                    idempotency_key=idempotency_key,
                    storage_target_digest=storage_target_digest,
                    min_observations_per_day=min_observations_per_day,
                )
        except TimeoutError:
            if acquired_lock:
                raise
            existing_run = _latest_refresh_for_idempotency_key(
                as_of_date=target_date_text,
                lookback_days=lookback_days,
                idempotency_key=idempotency_key,
                storage_target_digest=storage_target_digest,
            )
            if existing_run is not None:
                return _idempotent_refresh_response(existing_run)
            sleep_seconds = min(
                poll_seconds,
                max(deadline - time.monotonic(), 0.0),
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
                poll_seconds = min(
                    poll_seconds * 2,
                    LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_MAX_SECONDS,
                )


def _compute_gate_supplement_payload(
    *,
    duckdb_path: str,
    target_date: date,
    target_date_text: str,
    lookback_days: int,
    idempotency_key: str | None,
    storage_target_digest: str,
    min_observations_per_day: int | None = None,
) -> dict[str, object]:
    real_payload = _try_market_breadth_payload(
        duckdb_path=duckdb_path,
        target_date=target_date,
        lookback_days=lookback_days,
        idempotency_key=idempotency_key,
        min_observations_per_day=min_observations_per_day,
    )
    if real_payload is not None:
        if idempotency_key is not None:
            _record_idempotent_refresh(
                as_of_date=target_date_text,
                lookback_days=lookback_days,
                idempotency_key=idempotency_key,
                storage_target_digest=storage_target_digest,
                response_payload=real_payload,
            )
        return real_payload

    daily_returns = _load_csi300_daily_returns(
        duckdb_path=duckdb_path,
        end_date=target_date,
        lookback_days=lookback_days,
    )

    if len(daily_returns) < MIN_HISTORY_FOR_SUPPLEMENT:
        return {
            "status": "insufficient_data",
            "basis": "csi300_proxy",
            "message": (
                f"Need at least {MIN_HISTORY_FOR_SUPPLEMENT} daily return "
                f"observations; found {len(daily_returns)}."
            ),
            "computed_rows": 0,
            "idempotency_key": idempotency_key,
            "idempotency_replay": False,
        }

    supplement_rows = _compute_supplement_rows(daily_returns)
    if not supplement_rows:
        return {
            "status": "no_computable_dates",
            "basis": "csi300_proxy",
            "message": "No trade dates yielded computable supplement rows.",
            "computed_rows": 0,
            "idempotency_key": idempotency_key,
            "idempotency_replay": False,
        }

    result = materialize_livermore_gate_supplement_daily(
        duckdb_path=duckdb_path,
        rows=supplement_rows,
    )

    payload: dict[str, object] = {
        "status": "completed",
        "basis": "csi300_proxy",
        "computed_rows": len(supplement_rows),
        "first_date": str(supplement_rows[0]["trade_date"]),
        "last_date": str(supplement_rows[-1]["trade_date"]),
        "materialize_result": result,
        "idempotency_key": idempotency_key,
        "idempotency_replay": False,
    }
    if idempotency_key is not None:
        _record_idempotent_refresh(
            as_of_date=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=idempotency_key,
            storage_target_digest=storage_target_digest,
            response_payload=payload,
        )
    return payload


def _try_market_breadth_payload(
    *,
    duckdb_path: str,
    target_date: date,
    lookback_days: int,
    idempotency_key: str | None,
    min_observations_per_day: int | None,
) -> dict[str, object] | None:
    """Real all-market breadth basis; returns None to fall back to the CSI300 proxy."""
    try:
        if min_observations_per_day is None:
            result = materialize_market_breadth_daily(
                duckdb_path=duckdb_path,
                as_of_date=target_date,
                lookback_days=lookback_days,
            )
        else:
            result = materialize_market_breadth_daily(
                duckdb_path=duckdb_path,
                as_of_date=target_date,
                lookback_days=lookback_days,
                min_observations_per_day=int(min_observations_per_day),
            )
    except Exception:
        logger.warning(
            "Market breadth materialization failed; falling back to CSI300 proxy.",
            exc_info=True,
        )
        return None
    result_status = str(result.get("status") or "")
    if result_status == "insufficient_data":
        return None
    if result_status != "completed":
        return {
            "status": result_status or "market_breadth_failed",
            "basis": "market_breadth",
            "message": str(result.get("message") or "Market breadth materialization failed."),
            "computed_rows": 0,
            "market_breadth_result": {
                "daily_row_count": result.get("daily_row_count"),
                "table": result.get("table"),
                "rule_version": result.get("rule_version"),
                "run_id": result.get("run_id"),
                "limit_price_basis": result.get("limit_price_basis"),
                "limit_price_matched_count": result.get("limit_price_matched_count"),
            },
            "idempotency_key": idempotency_key,
            "idempotency_replay": False,
        }
    supplement_row_count = _coerce_optional_int(result.get("supplement_row_count")) or 0
    if supplement_row_count <= 0:
        # The all-market source is landed (status=completed) but no complete
        # 5-day breadth window could be computed (e.g. partial-universe days).
        # Do NOT fall back to the CSI300 proxy here: the proxy path would
        # delete+insert proxy rows over previously materialized real
        # market_breadth supplement rows, silently degrading the gate basis.
        return {
            "status": "no_computable_dates",
            "basis": "market_breadth",
            "message": (
                "All-market breadth source is landed but no complete "
                f"{BREADTH_WINDOW}-day windows were computable; existing "
                "supplement rows are left untouched."
            ),
            "computed_rows": 0,
            "market_breadth_result": {
                "daily_row_count": result.get("daily_row_count"),
                "table": result.get("table"),
                "rule_version": result.get("rule_version"),
                "run_id": result.get("run_id"),
            },
            "idempotency_key": idempotency_key,
            "idempotency_replay": False,
        }
    return {
        "status": "completed",
        "basis": "market_breadth",
        "computed_rows": supplement_row_count,
        "first_date": result.get("first_supplement_date"),
        "last_date": result.get("last_supplement_date"),
        "materialize_result": result.get("materialize_result"),
        "market_breadth_result": {
            "daily_row_count": result.get("daily_row_count"),
            "table": result.get("table"),
            "rule_version": result.get("rule_version"),
            "run_id": result.get("run_id"),
        },
        "idempotency_key": idempotency_key,
        "idempotency_replay": False,
    }


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    return int(str(value))


def _storage_target_digest(duckdb_path: str) -> str:
    target = Path(duckdb_path).expanduser().resolve(strict=False)
    return hashlib.sha256(os.path.normcase(str(target)).encode("utf-8")).hexdigest()[:16]


def _refresh_trigger_lock(*, as_of_date: str, lookback_days: int, storage_target_digest: str) -> LockDefinition:
    return LockDefinition(
        key=(
            "lock:livermore-gate-supplement-refresh:"
            f"{as_of_date}:{int(lookback_days)}:{storage_target_digest}"
        ),
        ttl_seconds=30,
    )


def _load_refresh_run_records() -> list[dict[str, object]]:
    settings = get_settings()
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY
        and str(record.get("job_name")) == LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME
    ]


def _latest_refresh_for_idempotency_key(
    *,
    as_of_date: str,
    lookback_days: int,
    idempotency_key: str,
    storage_target_digest: str,
) -> dict[str, object] | None:
    for record in reversed(_load_refresh_run_records()):
        if str(record.get("idempotency_key") or "").strip() != idempotency_key:
            continue
        if str(record.get("as_of_date")) != as_of_date:
            continue
        if str(record.get("lookback_days")) != str(int(lookback_days)):
            continue
        if str(record.get("storage_target_digest") or "").strip() != storage_target_digest:
            continue
        return record
    return None


def _idempotent_refresh_response(record: dict[str, object]) -> dict[str, object]:
    response_payload = record.get("response_payload")
    if isinstance(response_payload, dict):
        payload = dict(response_payload)
    else:
        payload = {
            "status": str(record.get("status") or "completed"),
            "materialize_result": {"run_id": str(record.get("run_id") or "")},
        }
    payload["idempotency_key"] = _normalize_idempotency_key(str(record.get("idempotency_key") or ""))
    payload["idempotency_replay"] = True
    return payload


def _record_idempotent_refresh(
    *,
    as_of_date: str,
    lookback_days: int,
    idempotency_key: str,
    storage_target_digest: str,
    response_payload: dict[str, object],
) -> None:
    settings = get_settings()
    materialize_result = response_payload.get("materialize_result")
    materialize_payload = materialize_result if isinstance(materialize_result, dict) else {}
    run_id = str(materialize_payload.get("run_id") or "")
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME,
            "status": "completed",
            "cache_key": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY,
            "cache_version": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION,
            "rule_version": str(
                materialize_payload.get("rule_version") or LIVERMORE_GATE_SUPPLEMENT_MATERIALIZE_RULE_VERSION
            ),
            "report_date": as_of_date,
            "as_of_date": as_of_date,
            "lookback_days": int(lookback_days),
            "idempotency_key": idempotency_key,
            "storage_target_digest": storage_target_digest,
            "response_payload": response_payload,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_csi300_daily_returns(
    *,
    duckdb_path: str,
    end_date: date,
    lookback_days: int,
) -> list[dict[str, Any]]:
    """Load CSI300 close + pct_chg from landed macro tables.

    Returns list of dicts with keys: trade_date (date), close (float),
    pct_chg (float | None).
    """
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return []

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return []

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        close_rows = _query_series_history(
            conn, tables, BROAD_INDEX_SERIES_ID, end_date, lookback_days
        )
        pct_chg_rows = _query_series_history(
            conn, tables, PCT_CHG_SERIES_ID, end_date, lookback_days
        )
    except duckdb.Error:
        return []
    finally:
        conn.close()

    # Index pct_chg by date
    pct_chg_by_date: dict[str, float] = {}
    for row in pct_chg_rows:
        pct_chg_by_date[row["trade_date"]] = row["value"]

    # Build merged list, computing pct_chg from close if not available
    result: list[dict[str, Any]] = []
    sorted_close = sorted(close_rows, key=lambda r: r["trade_date"])
    for i, row in enumerate(sorted_close):
        td = row["trade_date"]
        pct = pct_chg_by_date.get(td)
        if pct is None and i > 0:
            prev_close = sorted_close[i - 1]["value"]
            if prev_close and prev_close > 0:
                pct = (row["value"] - prev_close) / prev_close * 100
        result.append({
            "trade_date": td,
            "close": row["value"],
            "pct_chg": pct,
        })

    return result


def _query_series_history(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    series_id: str,
    end_date: date,
    lookback_days: int,
) -> list[dict[str, Any]]:
    """Query a single series from fact_choice_macro_daily / choice_market_snapshot."""
    queries: list[str] = []
    params: list[object] = []

    lookback_extra = lookback_days + BREADTH_WINDOW + 10  # extra buffer

    if "fact_choice_macro_daily" in tables:
        queries.append("""
            select
              cast(trade_date as date) as trade_date,
              cast(value_numeric as double) as value_numeric,
              0 as src_rank
            from fact_choice_macro_daily
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
        """)
        params.extend([series_id, end_date.isoformat(),
                       _offset_date(end_date, lookback_extra)])

    if "choice_market_snapshot" in tables:
        queries.append("""
            select
              cast(trade_date as date) as trade_date,
              cast(value_numeric as double) as value_numeric,
              1 as src_rank
            from choice_market_snapshot
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
        """)
        params.extend([series_id, end_date.isoformat(),
                       _offset_date(end_date, lookback_extra)])

    if not queries:
        return []

    sql = f"""
        with unioned as (
          {" union all ".join(queries)}
        ),
        deduped as (
          select
            trade_date,
            value_numeric,
            row_number() over (
              partition by trade_date
              order by src_rank asc
            ) as rn
          from unioned
        )
        select trade_date, value_numeric
        from deduped
        where rn = 1
        order by trade_date asc
    """
    rows = conn.execute(sql, params).fetchall()
    return [
        {"trade_date": str(row[0]), "value": float(row[1])}
        for row in rows
        if row[0] is not None and row[1] is not None
    ]


def _offset_date(d: date, days: int) -> str:
    from datetime import timedelta
    return (d - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _compute_supplement_rows(
    daily_returns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute breadth_5d and limit_up_quality_ok for each trade date.

    breadth_5d:
      Net up-days (up_days - down_days) over the BREADTH_WINDOW days ending
      at (and including) the current trade date. Range [-BREADTH_WINDOW,
      +BREADTH_WINDOW]. A value > 0 means more up-days than down-days, which
      matches the formal basis semantics (net advancers, gate passes on > 0)
      in :mod:`backend.app.core_finance.market_breadth`.

    limit_up_quality_ok:
      True when the market shows healthy momentum characteristics:
      - No single-day drawdown exceeding -3% in the trailing window
      - Average return in the window is positive
      This is a proxy; replace with actual limit-up seal/break data when available.
    """
    rows: list[dict[str, Any]] = []
    for i in range(BREADTH_WINDOW, len(daily_returns)):
        # Window ends at the current trade date, matching the formal basis
        # (5 most recent trade dates ending exactly at as_of).
        window = daily_returns[i - BREADTH_WINDOW + 1 : i + 1]
        current = daily_returns[i]
        td = current["trade_date"]

        # Skip if any window element lacks pct_chg
        pct_values = [d["pct_chg"] for d in window]
        if any(v is None for v in pct_values):
            continue

        # Breadth: net up-days, same sign semantics as the formal basis.
        up_days = sum(1 for v in pct_values if v > 0)
        down_days = sum(1 for v in pct_values if v < 0)
        breadth_5d = float(up_days - down_days)

        # Limit-up quality proxy
        avg_return = sum(pct_values) / len(pct_values)
        max_drawdown = min(pct_values)
        limit_up_quality_ok = bool(avg_return > 0 and max_drawdown > -3.0)

        source_digest = hashlib.sha256(
            json.dumps(
                {"trade_date": td, "breadth_5d": breadth_5d, "lim": limit_up_quality_ok},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]

        rows.append({
            "trade_date": td,
            "breadth_5d": breadth_5d,
            "limit_up_quality_ok": limit_up_quality_ok,
            "source_version": f"sv_gate_supplement_compute_{source_digest}",
            # "netdays" marks the net-up-days basis; older proxy rows without
            # this marker carry the legacy up-day-ratio values in [0, 1].
            "vendor_version": f"vv_gate_supplement_proxy_netdays_{td.replace('-', '')}",
        })

    return rows
