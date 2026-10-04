"""Worker-start recovery for durable business intents and expired Redis ACKs."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
from typing import Any

from backend.app.governance.locks import acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.tasks.broker import run_expired_redis_ack_maintenance
from dramatiq import ActorNotFound
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Middleware, Retries

logger = logging.getLogger(__name__)

ACK_MAINTENANCE_GRACE_SECONDS = 1.0
ACK_MAINTENANCE_RETRY_SECONDS = 5.0
ACK_MAINTENANCE_MAX_RETRY_SECONDS = 300.0
PNL_BY_BUSINESS_PAGE_ACTOR_NAME = "prepare_pnl_by_business_page_envelope"
PNL_BY_BUSINESS_PAGE_JOB_NAME = "pnl_by_business_page_prepare"
PNL_BY_BUSINESS_PAGE_CACHE_VERSION = "cv_pnl_by_business_page_envelope_v1"
PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION = "pnl_by_business_page_intent/v1"


def _latest_page_run_status(
    governance_repo: GovernanceRepository,
    *,
    run_id: str,
) -> str | None:
    records = governance_repo.read_by_cache_keys(
        CACHE_BUILD_RUN_STREAM,
        (PNL_BY_BUSINESS_PAGE_JOB_NAME,),
    )
    for record in reversed(records):
        if (
            str(record.get("run_id") or "") == run_id
            and str(record.get("job_name") or "") == PNL_BY_BUSINESS_PAGE_JOB_NAME
        ):
            return str(record.get("status") or "") or None
    return None


def _page_receipt_lock(governance_dir: str):
    from backend.app.services.pnl_by_business_page_lifecycle import (
        PNL_BY_BUSINESS_PAGE_DISPATCH_LOCK,
    )

    return acquire_lock(
        PNL_BY_BUSINESS_PAGE_DISPATCH_LOCK,
        base_dir=Path(governance_dir),
    )


def _ack_maintenance_retry_delay(
    failure_count: int,
    *,
    initial_seconds: float,
    maximum_seconds: float,
) -> float:
    initial = max(0.01, float(initial_seconds))
    maximum = max(0.01, float(maximum_seconds))
    exponent = min(max(0, int(failure_count) - 1), 20)
    return min(maximum, initial * (2**exponent))


def recover_durable_business_intents() -> int:
    """Reuse the existing recovery orchestration without running calculations inline."""
    from backend.app.tasks.data_update_center import (
        _recover_pending_pnl_by_business_precompute,
    )

    return _recover_pending_pnl_by_business_precompute(
        get_settings(),
        include_pending_dirty=False,
    )


def persist_pnl_by_business_page_completion(message: Any, result: object) -> bool:
    """Persist the successful actor result that Dramatiq otherwise discards."""
    if str(getattr(message, "actor_name", "") or "") != PNL_BY_BUSINESS_PAGE_ACTOR_NAME:
        return False
    if not isinstance(result, Mapping) or str(result.get("status") or "") != "completed":
        return False
    kwargs = getattr(message, "kwargs", {})
    if not isinstance(kwargs, Mapping):
        kwargs = {}
    run_id = str(result.get("run_id") or kwargs.get("run_id") or "")
    governance_dir = str(kwargs.get("governance_dir") or "")
    report_date = str(result.get("report_date") or kwargs.get("as_of_date") or "")
    year_raw: object = (
        result.get("year")
        if result.get("year") is not None
        else kwargs.get("year")
    )
    if (
        not run_id
        or not governance_dir
        or not report_date
        or isinstance(year_raw, bool)
        or not isinstance(year_raw, (int, str))
    ):
        logger.warning("page actor completed without a durable receipt identity")
        return False
    try:
        target_year = int(year_raw)
    except ValueError:
        logger.warning("page actor completed without a durable receipt identity")
        return False
    record: dict[str, object] = {
        "run_id": run_id,
        "job_name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_key": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_version": PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
        "protocol_version": PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        "status": "completed",
        "target_year": target_year,
        "report_date": report_date,
        "generation": str(result.get("generation") or ""),
        "finished_at": datetime.now(UTC).isoformat(),
    }
    for key in (
        "manifest_sha256",
        "prepared_at",
        "publication_status",
        "recovered_after_commit",
        "resource_limits",
    ):
        if result.get(key) is not None:
            record[key] = result[key]
    with _page_receipt_lock(governance_dir):
        governance_repo = GovernanceRepository(base_dir=Path(governance_dir))
        if _latest_page_run_status(governance_repo, run_id=run_id) == "completed":
            return False
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            record,
        )
    return True


def persist_pnl_by_business_page_terminal_failure(
    message: Any,
    exception: BaseException,
    *,
    broker: Any = None,
) -> bool:
    """Persist an actor failure only after Dramatiq marks it terminal."""
    if str(getattr(message, "actor_name", "") or "") != PNL_BY_BUSINESS_PAGE_ACTOR_NAME:
        return False
    if not bool(getattr(message, "failed", False)):
        return False
    kwargs = getattr(message, "kwargs", {})
    if not isinstance(kwargs, Mapping):
        kwargs = {}
    options = getattr(message, "options", {})
    if not isinstance(options, Mapping):
        options = {}
    actor_options: Mapping[str, object] = {}
    if broker is not None:
        try:
            resolved_options = broker.get_actor(message.actor_name).options
        except ActorNotFound:
            resolved_options = {}
        if isinstance(resolved_options, Mapping):
            actor_options = resolved_options
    run_id = str(kwargs.get("run_id") or "")
    governance_dir = str(kwargs.get("governance_dir") or "")
    report_date = str(kwargs.get("as_of_date") or "")
    year_raw = kwargs.get("year")
    if (
        not run_id
        or not governance_dir
        or not report_date
        or isinstance(year_raw, bool)
        or not isinstance(year_raw, (int, str))
    ):
        logger.warning("page actor failed without a durable receipt identity")
        return False
    try:
        target_year = int(year_raw)
    except ValueError:
        logger.warning("page actor failed without a durable receipt identity")
        return False
    retries = options.get("retries")
    max_retries = options.get("max_retries", actor_options.get("max_retries"))
    throws = options.get("throws", actor_options.get("throws"))
    retry_when = options.get("retry_when", actor_options.get("retry_when"))
    if throws and isinstance(exception, throws):
        terminal_reason = "declared_non_retryable"
    elif retry_when is not None:
        terminal_reason = "retry_policy_rejected"
    elif (
        isinstance(retries, int)
        and not isinstance(retries, bool)
        and isinstance(max_retries, int)
        and not isinstance(max_retries, bool)
        and retries > max_retries
    ):
        terminal_reason = "retries_exhausted"
    else:
        terminal_reason = "retry_policy_rejected"
    record: dict[str, object] = {
        "run_id": run_id,
        "job_name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_key": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_version": PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
        "protocol_version": PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        "status": "failed",
        "failure_category": "actor_terminal_failure",
        "terminal_reason": terminal_reason,
        "target_year": target_year,
        "report_date": report_date,
        "error_message": str(exception),
        "finished_at": datetime.now(UTC).isoformat(),
    }
    if retries is not None:
        record["retries"] = retries
    if max_retries is not None:
        record["max_retries"] = max_retries
    with _page_receipt_lock(governance_dir):
        governance_repo = GovernanceRepository(base_dir=Path(governance_dir))
        latest_status = _latest_page_run_status(governance_repo, run_id=run_id)
        if latest_status in {"completed", "failed"}:
            return False
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            record,
        )
    return True


class WorkerRecoveryMiddleware(Middleware):
    """Recover durable work after actors and worker threads are ready."""

    def __init__(
        self,
        *,
        recovery: Callable[[], int] = recover_durable_business_intents,
        ack_maintenance: Callable[[RedisBroker], dict[str, object]] = (
            run_expired_redis_ack_maintenance
        ),
        maintenance_grace_seconds: float = ACK_MAINTENANCE_GRACE_SECONDS,
        maintenance_retry_seconds: float = ACK_MAINTENANCE_RETRY_SECONDS,
        maintenance_max_retry_seconds: float = ACK_MAINTENANCE_MAX_RETRY_SECONDS,
    ) -> None:
        self._recovery = recovery
        self._ack_maintenance = ack_maintenance
        self._maintenance_grace_seconds = maintenance_grace_seconds
        self._maintenance_retry_seconds = maintenance_retry_seconds
        self._maintenance_max_retry_seconds = maintenance_max_retry_seconds
        self._shutdown = Event()
        self._start_lock = Lock()
        self._maintenance_thread: Thread | None = None

    def after_worker_boot(self, broker: Any, worker: Any) -> None:
        try:
            failures = self._recovery()
            if failures:
                logger.warning(
                    "worker startup business-intent recovery reported %s failure(s)",
                    failures,
                )
        except Exception:
            logger.exception("worker startup business-intent recovery failed")

        if not isinstance(broker, RedisBroker):
            return
        with self._start_lock:
            if (
                self._maintenance_thread is not None
                and self._maintenance_thread.is_alive()
            ):
                return
            self._shutdown.clear()
            delay_seconds = max(
                0.0,
                float(broker.heartbeat_timeout) / 1000
                + self._maintenance_grace_seconds,
            )
            self._maintenance_thread = Thread(
                target=self._maintain_after_heartbeat_timeout,
                args=(broker, delay_seconds),
                name="moss-worker-ack-recovery",
                daemon=True,
            )
            self._maintenance_thread.start()

    def before_worker_shutdown(self, broker: Any, worker: Any) -> None:
        self._shutdown.set()

    def after_process_message(
        self,
        broker: Any,
        message: Any,
        *,
        result: object = None,
        exception: BaseException | None = None,
    ) -> None:
        if exception is None:
            persist_pnl_by_business_page_completion(message, result)
        else:
            persist_pnl_by_business_page_terminal_failure(
                message,
                exception,
                broker=broker,
            )

    def _maintain_after_heartbeat_timeout(
        self,
        broker: RedisBroker,
        delay_seconds: float,
    ) -> None:
        try:
            if self._shutdown.wait(delay_seconds):
                return
            failure_count = 0
            while not self._shutdown.is_set():
                try:
                    result = self._ack_maintenance(broker)
                except Exception as exc:  # noqa: BLE001 -- retry the maintenance callback; throttled logs below retain the traceback.
                    failure_count += 1
                    retry_seconds = _ack_maintenance_retry_delay(
                        failure_count,
                        initial_seconds=self._maintenance_retry_seconds,
                        maximum_seconds=self._maintenance_max_retry_seconds,
                    )
                    log_failure = failure_count == 1 or failure_count & (failure_count - 1) == 0
                    log = logger.warning if log_failure else logger.debug
                    log(
                        "worker startup Redis ACK maintenance failed on attempt %s; "
                        "retrying in %.2f seconds: %s",
                        failure_count,
                        retry_seconds,
                        exc,
                        exc_info=log_failure,
                    )
                    if self._shutdown.wait(retry_seconds):
                        return
                    continue
                logger.info(
                    "worker startup Redis ACK maintenance completed for %s queue(s)",
                    result.get("queue_count", 0),
                )
                return
        finally:
            with self._start_lock:
                if self._maintenance_thread is current_thread():
                    self._maintenance_thread = None


def register_worker_recovery_middleware(broker: Any) -> WorkerRecoveryMiddleware:
    """Register startup recovery once on the active worker broker."""
    for middleware in broker.middleware:
        if isinstance(middleware, WorkerRecoveryMiddleware):
            return middleware
    middleware = WorkerRecoveryMiddleware()
    if any(isinstance(item, Retries) for item in broker.middleware):
        # ``after_*`` hooks run in reverse registration order.  Registering
        # before Retries lets Retries mark an exhausted message as failed
        # before this middleware decides whether to persist a terminal receipt.
        broker.add_middleware(middleware, before=Retries)
    else:
        broker.add_middleware(middleware)
    return middleware
