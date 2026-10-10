from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.app.config.product_category_mapping import resolve_product_category_ftp_rate_pct
from backend.app.governance.locks import LockDefinition, acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
)
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION, PnlRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.pnl import PnlByBusinessManualAdjustmentPayload
from backend.app.services.pnl_by_business_adjustment_handoff import (
    begin_pnl_by_business_adjustment_handoff,
    mark_pnl_by_business_adjustment_content_committed,
    mark_pnl_by_business_adjustment_dispatch_failed,
    pending_pnl_by_business_adjustment_handoffs,
)
from backend.app.services.pnl_by_business_adjustments import (
    PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
    active_pnl_by_business_manual_adjustments_for_period,
    pnl_by_business_manual_adjustment_source_version,
)
from backend.app.services.pnl_service_by_business_support import (
    _available_pnl_by_business_precompute_cutoffs,
    _normalize_pnl_by_business_precompute_as_of_date,
    _normalize_pnl_by_business_precompute_year,
    _pnl_by_business_precompute_cutoff_result,
    _pnl_by_business_precompute_record_target_dates,
    _safe_pnl_by_business_precompute_error_message,
)
from backend.app.services.pnl_service_shared_utils import _parse_created_at, _safe_int
from backend.app.services.pnl_task_dispatch import (
    PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
    PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
    PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
    PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION,
    PNL_MATERIALIZE_LOCK,
    rebuild_pnl_by_business_precompute,
)
from backend.app.tasks.pnl_by_business_resource_scope import (
    pnl_by_business_dependency_resource_failure,
)

logger = logging.getLogger(__name__)

PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES = frozenset({"queued", "running"})
PNL_BY_BUSINESS_PRECOMPUTE_STALE_AFTER = timedelta(hours=2)
PNL_BY_BUSINESS_PRECOMPUTE_DISPATCH_LOCK = LockDefinition(
    key="lock:pnl:by-business:precompute-dispatch",
    ttl_seconds=30,
)


class PnlByBusinessPrecomputeConflictError(RuntimeError):
    pass


class PnlByBusinessPrecomputeDispatchError(RuntimeError):
    pass


def append_adjustment_event_with_handoff(
    settings: Settings,
    *,
    record: PnlByBusinessManualAdjustmentPayload,
    dependency_dates: Sequence[str],
    reason: str,
    clear_caches: Callable[[], None],
    enqueue_refresh: Callable[..., bool],
) -> list[dict[str, object]]:
    serialized = record.model_dump(mode="json")
    normalized_dates = sorted(
        {
            date.fromisoformat(str(value)).isoformat()
            for value in dependency_dates
            if str(value or "").strip()
        }
    )
    dates_by_year: dict[int, list[str]] = {}
    for report_date in normalized_dates:
        dates_by_year.setdefault(date.fromisoformat(report_date).year, []).append(report_date)
    handoffs = [
        begin_pnl_by_business_adjustment_handoff(
            settings.governance_path,
            adjustment_id=record.adjustment_id,
            dependency_dates=year_dates,
            reason=reason,
            expected_adjustment_event=serialized,
        )
        for _year, year_dates in sorted(dates_by_year.items())
    ]
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        serialized,
    )
    committed_handoffs = [
        mark_pnl_by_business_adjustment_content_committed(
            settings.governance_path,
            handoff=handoff,
        )
        for handoff in handoffs
    ]
    clear_caches()
    for handoff in committed_handoffs:
        handoff_dates = list(_required_date_sequence(handoff, "dependency_dates"))
        enqueued = enqueue_refresh(
            settings,
            report_date=min(handoff_dates),
            dependency_dates=handoff_dates,
            adjustment_handoff_ids=[str(handoff.get("handoff_id") or "")],
        )
        if not enqueued:
            mark_pnl_by_business_adjustment_dispatch_failed(
                settings.governance_path,
                handoff=handoff,
                error_message="Adjustment handoff remains pending for background recovery.",
            )
    return committed_handoffs


def request_precompute_rebuild(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None,
    scope: str,
    repository_cls: type[PnlRepository],
    queue_refresh: Callable[..., dict[str, object] | None],
) -> dict[str, object]:
    normalized_year = _normalize_pnl_by_business_precompute_year(year)
    normalized_scope = str(scope or "selected").strip().lower()
    if normalized_scope not in {"selected", "all_available"}:
        raise ValueError("scope must be selected or all_available.")
    normalized_as_of_date = _normalize_pnl_by_business_precompute_as_of_date(
        year=normalized_year,
        as_of_date=as_of_date,
    )
    target_as_of_dates: list[str] | None = None
    if normalized_scope == "all_available":
        if normalized_as_of_date is not None:
            raise ValueError("as_of_date cannot be combined with scope=all_available.")
        target_as_of_dates = _available_pnl_by_business_precompute_cutoffs(
            repository_cls(str(settings.duckdb_path)),
            year=normalized_year,
        )
    queued = queue_refresh(
        settings,
        year=normalized_year,
        as_of_date=normalized_as_of_date,
        trigger_reason=(
            "manual_retry_all_available"
            if normalized_scope == "all_available"
            else "manual_retry"
        ),
        raise_on_dispatch_failure=True,
        raise_on_duplicate=True,
        as_of_dates=target_as_of_dates,
        scope=normalized_scope,
    )
    assert queued is not None
    return queued


def legacy_precompute_status(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None,
    repository_cls: type[PnlRepository],
) -> dict[str, object]:
    normalized_year = _normalize_pnl_by_business_precompute_year(year)
    normalized_as_of_date = _normalize_pnl_by_business_precompute_as_of_date(
        year=normalized_year,
        as_of_date=as_of_date,
    )
    run_records = _precompute_run_records(settings, year=normalized_year)
    pnl_repo = repository_cls(str(settings.duckdb_path))
    latest_available_as_of_date = pnl_repo.max_formal_or_nonstd_report_date_in_year(
        year=normalized_year,
        as_of_cap=None,
    )
    period_end = pnl_repo.max_formal_or_nonstd_report_date_in_year(
        year=normalized_year,
        as_of_cap=normalized_as_of_date,
    )
    latest = _precompute_status_record(
        run_records,
        period_end=period_end,
        latest_available_as_of_date=latest_available_as_of_date,
    )
    if (
        latest is not None
        and period_end is not None
        and not str(latest.get("report_date") or "")
        and period_end in _pnl_by_business_precompute_record_target_dates(latest)
    ):
        latest = {**latest, "report_date": period_end}
        cutoff_result = _pnl_by_business_precompute_cutoff_result(
            latest,
            period_end=period_end,
        )
        if cutoff_result is not None:
            latest.update(
                source_version=str(cutoff_result.get("source_version") or ""),
                generated_at=str(cutoff_result.get("generated_at") or "") or None,
                record_count=_safe_int(cutoff_result.get("records")),
            )
    status = str(latest.get("status") or "") if latest else "idle"
    inflight = status in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES
    metadata: dict[str, object] | None = None
    if period_end:
        active_adjustments = active_pnl_by_business_manual_adjustments_for_period(
            settings.governance_path,
            year=normalized_year,
            period_end=period_end,
        )
        metadata = pnl_repo.fetch_pnl_by_business_precompute_metadata(
            year=normalized_year,
            as_of_date=period_end,
            effective_ftp_rate_pct=resolve_product_category_ftp_rate_pct(
                date(normalized_year, 12, 31), settings.ftp_rate_pct
            ),
            supplemental_source_version=pnl_by_business_manual_adjustment_source_version(
                active_adjustments
            ),
            verify_current=not inflight,
        )
    is_current = bool(metadata and metadata.get("is_current"))
    if latest is None and is_current:
        status = "completed"
    return _precompute_status_payload(
        year=normalized_year,
        status=status,
        record=latest,
        metadata=metadata,
        latest_available_as_of_date=latest_available_as_of_date,
        is_current=is_current,
    )


def enqueue_precompute_refresh(
    settings: Settings,
    *,
    report_date: str,
    dependency_dates: list[str] | None,
    adjustment_handoff_ids: list[str] | None,
    optional_cutoffs: Callable[..., list[str]],
    queue_refresh: Callable[..., dict[str, object] | None],
) -> bool:
    try:
        year = date.fromisoformat(str(report_date)).year
    except ValueError:
        logger.warning(
            "skipped pnl_by_business precompute refresh for invalid report_date=%s",
            report_date,
        )
        return False
    normalized_dependency_dates = sorted(
        {
            date.fromisoformat(str(value)).isoformat()
            for value in (dependency_dates or [report_date])
            if str(value or "").strip()
        }
    )
    earliest_date = min(normalized_dependency_dates)
    available_cutoffs = optional_cutoffs(settings, year=year)
    target_dates = [cutoff for cutoff in available_cutoffs if cutoff >= earliest_date]
    if not target_dates:
        return False
    queue_kwargs: dict[str, object] = {
        "year": year,
        "as_of_date": None,
        "trigger_reason": "manual_adjustment_state_change",
        "raise_on_dispatch_failure": False,
        "raise_on_duplicate": False,
        "as_of_dates": target_dates,
        "scope": "persistent_dirty",
    }
    if adjustment_handoff_ids:
        queue_kwargs["adjustment_handoff_ids"] = list(adjustment_handoff_ids)
    return queue_refresh(settings, **queue_kwargs) is not None


def queue_precompute_refresh(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None,
    trigger_reason: str,
    raise_on_dispatch_failure: bool,
    raise_on_duplicate: bool,
    as_of_dates: list[str] | None,
    scope: str,
    dependency_revision: int | None,
    adjustment_handoff_ids: list[str] | None,
    task_actor: Any = rebuild_pnl_by_business_precompute,
) -> dict[str, object] | None:
    run_id = f"{PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME}:{uuid4()}"
    queued_at = datetime.now(UTC).isoformat()
    writer_lock = resolve_duckdb_writer_lock(
        settings.duckdb_path,
        ttl_seconds=PNL_MATERIALIZE_LOCK.ttl_seconds,
    )
    record = CacheBuildRunRecord(
        run_id=run_id,
        job_name=PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        status="queued",
        cache_key=PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
        cache_version=PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
        lock=writer_lock.key,
        source_version=PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION,
        vendor_version="vv_none",
        rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        report_date=as_of_date,
        queued_at=queued_at,
    ).model_dump()
    record["target_year"] = int(year)
    record["trigger_reason"] = trigger_reason
    record["scope"] = scope
    if dependency_revision is not None:
        record["dependency_revision"] = int(dependency_revision)
    if adjustment_handoff_ids:
        record["adjustment_handoff_ids"] = sorted(set(adjustment_handoff_ids))
    if as_of_dates is not None:
        record["target_as_of_dates"] = list(as_of_dates)
        record["target_count"] = len(as_of_dates)
    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    try:
        with acquire_lock(
            PNL_BY_BUSINESS_PRECOMPUTE_DISPATCH_LOCK,
            base_dir=settings.governance_path,
            timeout_seconds=2.0,
        ):
            inflight_records = _inflight_precompute_runs(settings, year=int(year))
            if dependency_revision is not None and as_of_dates is not None:
                requested_dates = set(as_of_dates)
                matching_records = [
                    item
                    for item in inflight_records
                    if _safe_int(item.get("dependency_revision"))
                    == int(dependency_revision)
                ]
                covered_dates = {
                    target_date
                    for item in matching_records
                    for target_date in _pnl_by_business_precompute_record_target_dates(item)
                }
                uncovered_dates = sorted(requested_dates - covered_dates)
                if not uncovered_dates and matching_records:
                    existing = matching_records[-1]
                    return {
                        **existing,
                        "reused": True,
                        "target_as_of_dates": sorted(requested_dates),
                        "target_count": len(requested_dates),
                    }
                if uncovered_dates != as_of_dates:
                    as_of_dates = uncovered_dates
                    record["target_as_of_dates"] = list(uncovered_dates)
                    record["target_count"] = len(uncovered_dates)
            if inflight_records and raise_on_duplicate:
                raise PnlByBusinessPrecomputeConflictError(
                    f"PnL by-business precompute already in progress for year={int(year)}."
                )
            if (
                dependency_revision is None
                and any(
                    str(item.get("status") or "") == "queued"
                    for item in inflight_records
                )
            ):
                return None
            governance_repo.append(CACHE_BUILD_RUN_STREAM, record)
            try:
                task_kwargs: dict[str, object] = {
                    "duckdb_path": str(settings.duckdb_path),
                    "governance_dir": str(settings.governance_path),
                    "year": int(year),
                    "as_of_date": as_of_date,
                    "run_id": run_id,
                    "queued_at": queued_at,
                    "trigger_reason": trigger_reason,
                }
                if as_of_dates is not None:
                    task_kwargs["as_of_dates"] = list(as_of_dates)
                if dependency_revision is not None:
                    task_kwargs["dependency_revision"] = int(dependency_revision)
                if adjustment_handoff_ids:
                    task_kwargs["adjustment_handoff_ids"] = sorted(
                        set(adjustment_handoff_ids)
                    )
                task_actor.send(**task_kwargs)
            except Exception as exc:
                failed_record = {
                    **record,
                    "status": "failed",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "error_message": str(exc),
                    "failure_category": "queue_dispatch_failure",
                    "failure_reason": str(exc),
                }
                governance_repo.append(CACHE_BUILD_RUN_STREAM, failed_record)
                logger.warning(
                    "failed to enqueue pnl_by_business precompute refresh for year=%s: %s",
                    year,
                    exc,
                )
                if raise_on_dispatch_failure:
                    raise PnlByBusinessPrecomputeDispatchError(
                        "PnL by-business precompute queue dispatch failed."
                    ) from exc
                return None
    except TimeoutError as exc:
        if raise_on_duplicate:
            raise PnlByBusinessPrecomputeConflictError(
                f"PnL by-business precompute dispatch is busy for year={int(year)}."
            ) from exc
        logger.info("skipped duplicate pnl_by_business precompute dispatch for year=%s", year)
        return None
    payload = _precompute_status_payload(
        year=int(year),
        status="queued",
        record=record,
        metadata=None,
        latest_available_as_of_date=None,
        is_current=False,
    )
    payload["scope"] = scope
    if as_of_dates is not None:
        payload["target_as_of_dates"] = list(as_of_dates)
        payload["target_count"] = len(as_of_dates)
    return payload


def recover_pending_precompute(
    settings: Settings,
    *,
    pending: Mapping[str, object],
    optional_cutoffs: Callable[..., list[str]],
    queue_refresh: Callable[..., dict[str, object] | None],
) -> dict[str, object] | None:
    year = _required_int_field(pending, "year")
    dependency_revision = _required_int_field(pending, "dependency_revision")
    protocol_version = str(pending.get("protocol_version") or "")
    if protocol_version != PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION:
        raise ValueError("Unsupported pnl-by-business precompute state protocol.")
    dirty_from_date = date.fromisoformat(
        str(pending.get("dirty_from_date") or "")
    ).isoformat()
    if date.fromisoformat(dirty_from_date).year != year:
        raise ValueError("Pending dirty range is outside its requested year.")
    target_dates = sorted(
        {
            date.fromisoformat(str(value)).isoformat()
            for value in _required_sequence_field(pending, "target_dates")
            if str(value or "").strip()
        }
    )
    if not target_dates:
        target_dates = [
            cutoff
            for cutoff in optional_cutoffs(settings, year=year)
            if cutoff >= dirty_from_date
        ]
    if not target_dates:
        return None
    if any(not cutoff.startswith(f"{year:04d}-") for cutoff in target_dates):
        raise ValueError("Pending target dates must stay within one year.")
    durable_resource_failure = _resource_failure_for_pending_precompute(
        settings,
        year=year,
        dependency_revision=dependency_revision,
        target_dates=target_dates,
    )
    if durable_resource_failure is not None:
        return durable_resource_failure
    return queue_refresh(
        settings,
        year=year,
        as_of_date=None,
        trigger_reason="persistent_dirty_recovery",
        raise_on_dispatch_failure=False,
        raise_on_duplicate=False,
        as_of_dates=target_dates,
        scope="persistent_dirty",
        dependency_revision=dependency_revision,
    )


def _resource_failure_for_pending_precompute(
    settings: Settings,
    *,
    year: int,
    dependency_revision: int,
    target_dates: list[str],
) -> dict[str, object] | None:
    """Keep automatic dirty recovery from replacing a resource-failed run."""
    for target_date in target_dates:
        durable_failure = pnl_by_business_dependency_resource_failure(
            settings.governance_path,
            year=year,
            dependency_revision=dependency_revision,
            as_of_date=target_date,
        )
        if durable_failure is not None:
            return dict(durable_failure)
    return None


def recover_pending_adjustment_handoffs(
    settings: Settings,
    *,
    optional_cutoffs: Callable[..., list[str]],
    queue_refresh: Callable[..., dict[str, object] | None],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for handoff in pending_pnl_by_business_adjustment_handoffs(
        settings.governance_path
    ):
        dependency_dates = sorted(
            {
                date.fromisoformat(str(value)).isoformat()
                for value in _required_sequence_field(handoff, "dependency_dates")
                if str(value or "").strip()
            }
        )
        if not dependency_dates:
            continue
        year = date.fromisoformat(dependency_dates[0]).year
        earliest_date = min(dependency_dates)
        target_dates = [
            cutoff
            for cutoff in optional_cutoffs(settings, year=year)
            if cutoff >= earliest_date
        ]
        if not target_dates:
            continue
        queued = queue_refresh(
            settings,
            year=year,
            as_of_date=None,
            trigger_reason="adjustment_handoff_recovery",
            raise_on_dispatch_failure=False,
            raise_on_duplicate=False,
            as_of_dates=target_dates,
            scope="adjustment_handoff",
            adjustment_handoff_ids=[str(handoff.get("handoff_id") or "")],
        )
        if queued is not None:
            results.append(queued)
    return results


def optional_precompute_cutoffs(
    settings: Settings,
    *,
    year: int,
    repository_cls: type[PnlRepository],
    available_cutoffs: Callable[..., list[str]] = _available_pnl_by_business_precompute_cutoffs,
) -> list[str]:
    try:
        return available_cutoffs(
            repository_cls(str(settings.duckdb_path)),
            year=year,
        )
    except ValueError as exc:
        if str(exc) == f"No available month-end cutoffs found for year={int(year)}.":
            return []
        raise


def _precompute_run_records(settings: Settings, *, year: int) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(
            CACHE_BUILD_RUN_STREAM
        )
        if str(record.get("cache_key") or "") == PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY
        and str(record.get("job_name") or "") == PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME
        and (
            _safe_int(record.get("target_year")) == year
            or str(record.get("report_date") or "").startswith(f"{year:04d}-")
        )
    ]


def _inflight_precompute_runs(
    settings: Settings,
    *,
    year: int,
) -> list[dict[str, object]]:
    effective_records = _effective_precompute_run_records(
        _precompute_run_records(settings, year=year)
    )
    return [
        record
        for record in effective_records
        if str(record.get("status") or "") in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES
    ]


def _effective_precompute_run_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    records_by_run_id: dict[str, list[dict[str, object]]] = {}
    latest_event_index: dict[str, int] = {}
    for index, record in enumerate(records):
        run_id = str(record.get("run_id") or f"missing-run-id:{index}")
        marked_record = dict(record)
        marked_record["_effective_run_id"] = run_id
        records_by_run_id.setdefault(run_id, []).append(marked_record)
        latest_event_index[run_id] = index
    effective = [
        _effective_precompute_run_record(run_records)
        for run_records in records_by_run_id.values()
    ]
    return sorted(
        effective,
        key=lambda record: latest_event_index[str(record["_effective_run_id"])],
    )


def _effective_precompute_run_record(
    run_records: list[dict[str, object]],
) -> dict[str, object]:
    latest = dict(run_records[-1])
    status = str(latest.get("status") or "")
    failure_category = str(latest.get("failure_category") or "")
    failure_count = sum(
        1 for record in run_records if str(record.get("status") or "") == "failed"
    )
    max_retries = int(
        getattr(rebuild_pnl_by_business_precompute, "options", {}).get(
            "max_retries", 3
        )
    )
    if (
        status == "failed"
        and failure_category
        not in {"queue_dispatch_failure", "resource_over_budget"}
        and failure_count <= max_retries
    ):
        latest["status"] = "queued"
        latest["failure_category"] = "automatic_retry_pending"
    if str(latest.get("status") or "") in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES:
        timestamp = str(
            latest.get("finished_at")
            or latest.get("started_at")
            or latest.get("queued_at")
            or ""
        ).strip()
        if (
            not timestamp
            or datetime.now(UTC) - _parse_created_at(timestamp)
            > PNL_BY_BUSINESS_PRECOMPUTE_STALE_AFTER
        ):
            latest["status"] = "failed"
            latest["failure_category"] = "stale_inflight"
            latest["error_message"] = "Precompute worker progress timed out."
    latest["retry_attempt"] = failure_count
    return latest


def _precompute_status_record(
    records: list[dict[str, object]],
    *,
    period_end: str | None,
    latest_available_as_of_date: str | None,
) -> dict[str, object] | None:
    relevant = [
        record
        for record in _effective_precompute_run_records(records)
        if (
            (period_end is not None and str(record.get("report_date") or "") == period_end)
            or (
                period_end is not None
                and period_end in _pnl_by_business_precompute_record_target_dates(record)
            )
            or (
                not str(record.get("report_date") or "")
                and not _pnl_by_business_precompute_record_target_dates(record)
                and period_end == latest_available_as_of_date
            )
        )
    ]
    if not relevant:
        return None
    inflight = [
        record
        for record in relevant
        if str(record.get("status") or "") in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES
    ]
    return (inflight or relevant)[-1]


def _precompute_status_payload(
    *,
    year: int,
    status: str,
    record: dict[str, object] | None,
    metadata: dict[str, object] | None,
    latest_available_as_of_date: str | None,
    is_current: bool,
) -> dict[str, object]:
    actor_options = getattr(rebuild_pnl_by_business_precompute, "options", {})
    failure_category = str(record.get("failure_category") or "") if record else ""
    safe_error_message = _safe_pnl_by_business_precompute_error_message(
        status=status,
        failure_category=failure_category,
    )
    return {
        "year": year,
        "status": status,
        "serving_mode": "precomputed" if is_current else "live_fallback",
        "is_current": is_current,
        "run_id": (str(record.get("run_id") or "") or None) if record else None,
        "report_date": (
            str(metadata.get("as_of_date") or "") or None
            if metadata
            else (str(record.get("report_date") or "") or None if record else None)
        ),
        "latest_available_as_of_date": latest_available_as_of_date,
        "source_version": (
            str(metadata.get("source_version") or "") or None
            if metadata
            else (str(record.get("source_version") or "") or None if record else None)
        ),
        "rule_version": (
            str(metadata.get("rule_version") or "") or None
            if metadata
            else PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
        ),
        "queued_at": (str(record.get("queued_at") or "") or None) if record else None,
        "started_at": (str(record.get("started_at") or "") or None) if record else None,
        "finished_at": (str(record.get("finished_at") or "") or None) if record else None,
        "generated_at": (
            str(metadata.get("generated_at") or "") or None
            if metadata
            else (str(record.get("generated_at") or "") or None if record else None)
        ),
        "record_count": (
            _safe_int(metadata.get("record_count"))
            if metadata
            else (
                _safe_int(record.get("record_count"))
                if record and record.get("record_count") is not None
                else None
            )
        ),
        "error_message": safe_error_message,
        "failure_category": failure_category or None,
        "trigger_reason": (
            str(record.get("trigger_reason") or "") or None if record else None
        ),
        "retry_attempt": _safe_int(record.get("retry_attempt")) if record else 0,
        "retry_policy": {
            "max_retries": _safe_int(actor_options.get("max_retries")) or 3,
            "min_backoff_seconds": (
                _safe_int(actor_options.get("min_backoff")) or 15_000
            )
            // 1000,
        },
    }


def _required_sequence_field(
    record: Mapping[str, object],
    field: str,
) -> Sequence[object]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be a sequence.")
    return value


def _required_date_sequence(
    record: Mapping[str, object],
    field: str,
) -> tuple[str, ...]:
    values = _required_sequence_field(record, field)
    dates = tuple(
        sorted(
            {
                date.fromisoformat(str(value)).isoformat()
                for value in values
                if str(value or "").strip()
            }
        )
    )
    if not dates:
        raise ValueError(f"{field} must contain at least one date.")
    return dates


def _required_int_field(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field} must be an integer.")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer.") from exc
