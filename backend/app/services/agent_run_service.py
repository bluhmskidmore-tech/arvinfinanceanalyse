from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.agent.runtime.toolset_policy import normalize_read_only_toolsets
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.agent.schemas.agent_run import (
    AgentRunCreateResponse,
    AgentRunListResponse,
    AgentRunRecord,
    AgentRunStatusResponse,
)
from backend.app.governance.agent_audit import AGENT_AUDIT_STREAM, AgentAuditPayload
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import GovernanceRepository

AGENT_RUN_STREAM = "agent_run"
AGENT_RUN_DISPATCH_STREAM = "agent_run_dispatch"
AGENT_RUN_JOB_NAME = "agent_run"
AGENT_RUN_STATE_LOCK = threading.Lock()
AGENT_RUN_TRANSITION_LOCK = threading.RLock()
AGENT_RUN_TRANSITION_FILE_LOCK = LockDefinition(
    key="lock:agent-run:transition",
    ttl_seconds=300,
)
MAX_AGENT_RUN_CACHE_SIZE = 200
AGENT_RUN_STALE_GRACE_SECONDS = 30.0
AGENT_RUN_QUEUED_STALE_SECONDS = 600.0
# local provider 没有单次调用超时设置，但同样经 Dramatiq worker 异步执行；
# worker 崩溃后 running 记录必须能收敛，否则 SSE 永不发 terminal 帧。
# 可通过治理 setting agent_run_local_timeout_seconds 覆盖。
AGENT_RUN_LOCAL_STALE_SECONDS = 1800.0
AGENT_RUN_DISPATCH_WAIT_SECONDS = 5.0
AGENT_RUN_DISPATCH_POLL_SECONDS = 0.01
AGENT_RUN_CANCEL_POLL_SECONDS = 0.5
AGENT_RUN_HEARTBEAT_SECONDS = 15.0
_AGENT_RUN_LATEST_RECORDS: dict[str, dict[str, object]] = {}
_ACTIVE_AGENT_RUN_STATUSES = frozenset({"queued", "starting", "running"})
_TERMINAL_AGENT_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
_DISPATCH_FAILURE_CODE = "AGENT_RUN_DISPATCH_FAILED"
_EXECUTION_FAILURE_CODE = "AGENT_RUN_EXECUTION_FAILED"
_PREPARATION_FAILURE_CODE = "AGENT_RUN_PREPARATION_FAILED"
# 与 AgentQueryRequest.question 的 min_length=1 / max_length=8000 约束对齐：
# 该约束晚于部分历史 run 记录引入，重建历史 request（stale 对账 audit、
# 失败回退）时必须截断/兜底，否则状态读取会抛 ValidationError。
_RECONSTRUCTED_QUESTION_MAX_LENGTH = 8000
_LOGGER = logging.getLogger(__name__)

# Indirection so tests can control heartbeat timing deterministically.
_monotonic = time.monotonic

AgentExecutor = Callable[[AgentQueryRequest, str, Any], AgentEnvelope]


class AgentRunStateConflict(RuntimeError):
    """Raised when a requested run lifecycle transition is not allowed."""


class AgentRunDispatchError(RuntimeError):
    """Raised after a broker dispatch failure is persisted as terminal."""


class _ExecuteAgentRunTaskProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.agent_run import execute_agent_run_task as _actor

        return _actor.send(**kwargs)


execute_agent_run_task = _ExecuteAgentRunTaskProxy()


async def iter_agent_run_events(
    *,
    run_id: str,
    settings: Any,
    initial_status: AgentRunStatusResponse | None = None,
    poll_interval_seconds: float = 0.5,
    heartbeat_interval_seconds: float = AGENT_RUN_HEARTBEAT_SECONDS,
):
    """Yield distinct run snapshots as SSE frames until the run is terminal.

    While the snapshot is unchanged, an SSE comment frame (``: keepalive``) is
    emitted every ``heartbeat_interval_seconds`` so idle proxies do not drop the
    connection. Comment frames are ignored natively by EventSource-style
    parsers and carry no event shape.
    """
    current_status = initial_status or get_agent_run_status(run_id=run_id, settings=settings)
    last_frame: str | None = None
    last_emit = _monotonic()

    while True:
        frame = (
            "event: run_update\n"
            f"data: {current_status.model_dump_json(exclude_none=True)}\n\n"
        )
        if frame != last_frame:
            yield frame
            last_frame = frame
            last_emit = _monotonic()
        if current_status.status in _TERMINAL_AGENT_RUN_STATUSES:
            return
        if (
            heartbeat_interval_seconds > 0
            and _monotonic() - last_emit >= heartbeat_interval_seconds
        ):
            yield ": keepalive\n\n"
            last_emit = _monotonic()

        await asyncio.sleep(max(0.0, poll_interval_seconds))
        current_status = await asyncio.to_thread(
            get_agent_run_status,
            run_id=run_id,
            settings=settings,
        )


def _provider_runtime_fields(settings: Any, provider: str | None = None) -> tuple[str, str, str, str]:
    normalized_provider = str(provider or getattr(settings, "agent_provider", "hermes") or "hermes").strip().lower()
    if normalized_provider == "local":
        return (
            "local",
            "default",
            "inline",
            normalize_read_only_toolsets(""),
        )
    if normalized_provider == "dexter":
        return (
            "dexter",
            str(getattr(settings, "agent_dexter_model", "") or "default"),
            str(getattr(settings, "agent_dexter_transport", "cli") or "cli"),
            normalize_read_only_toolsets(str(getattr(settings, "agent_dexter_toolsets", "") or "")),
        )
    return (
        "hermes",
        str(getattr(settings, "agent_hermes_model", "") or "default"),
        str(getattr(settings, "agent_hermes_transport", "bridge") or "bridge"),
        normalize_read_only_toolsets(str(getattr(settings, "agent_hermes_toolsets", "") or "")),
    )


class StagedAgentRunCreation:
    """Outcome of the fast, lock-guarded first half of run creation.

    Exactly one of the three shapes is populated:

    - ``existing``: an idempotent duplicate short-circuits to this record;
    - ``pending_idempotency_scope``: a duplicate must wait for the first
      dispatcher to resolve (acceptance or terminal failure);
    - ``queued_record`` + ``run_request``: a fresh run was persisted as
      ``queued`` and still needs broker dispatch.
    """

    __slots__ = ("existing", "pending_idempotency_scope", "queued_record", "run_request")

    def __init__(
        self,
        *,
        existing: dict[str, object] | None = None,
        pending_idempotency_scope: tuple[str, str | None, str] | None = None,
        queued_record: AgentRunRecord | None = None,
        run_request: AgentQueryRequest | None = None,
    ) -> None:
        self.existing = existing
        self.pending_idempotency_scope = pending_idempotency_scope
        self.queued_record = queued_record
        self.run_request = run_request


def create_agent_run(
    *,
    request: AgentQueryRequest,
    settings: Any,
    provider: str | None = None,
) -> AgentRunCreateResponse:
    staged = stage_agent_run_creation(
        request=request,
        settings=settings,
        provider=provider,
    )
    return complete_agent_run_creation(staged=staged, settings=settings)


def stage_agent_run_creation(
    *,
    request: AgentQueryRequest,
    settings: Any,
    provider: str | None = None,
) -> StagedAgentRunCreation:
    """Idempotency check plus queued-record persistence, nothing slower.

    This half is safe to call while holding coarser locks (e.g. the agent
    workspace lifecycle lock): it never waits on dispatch resolution and never
    touches the broker. Callers must pass the result to
    `complete_agent_run_creation` outside such locks.
    """
    repo = GovernanceRepository(base_dir=settings.governance_path)

    with AGENT_RUN_TRANSITION_LOCK:
        with acquire_lock(
            AGENT_RUN_TRANSITION_FILE_LOCK,
            base_dir=repo.base_dir,
            timeout_seconds=5.0,
        ):
            idempotency_scope = _create_idempotency_scope(request)
            if idempotency_scope is not None:
                existing = _find_existing_idempotent_run_record(
                    repo=repo,
                    owner_user_id=idempotency_scope[0],
                    conversation_id=idempotency_scope[1],
                    client_request_id=idempotency_scope[2],
                )
                if existing is not None:
                    if _is_dispatch_pending_record(repo=repo, record=existing):
                        return StagedAgentRunCreation(
                            pending_idempotency_scope=idempotency_scope,
                        )
                    if str(existing.get("status") or "") not in {"failed", "cancelled"}:
                        return StagedAgentRunCreation(existing=existing)
                    # 该 scope 下的所有 run 均已终态 failed/cancelled：
                    # 幂等键不再短路（否则 retry 只会拿回上一次失败记录），
                    # 允许落一条新的 queued 记录。

            run_id = _build_run_id()
            queued_at = _utc_now()
            run_request = request.model_copy(
                update={
                    "context": {
                        **request.context,
                        "run_id": run_id,
                    }
                }
            )
            provider, model, transport, toolsets = _provider_runtime_fields(
                settings,
                provider,
            )
            conversation_id = _context_identifier(
                run_request.context,
                "conversation_id",
            )
            retry_of_run_id = _context_identifier(
                run_request.context,
                "retry_of_run_id",
            )
            queued_record = AgentRunRecord(
                run_id=run_id,
                status="queued",
                conversation_id=conversation_id,
                retry_of_run_id=retry_of_run_id,
                question=run_request.question,
                request=run_request.model_dump(mode="json"),
                provider=provider,
                model=model,
                transport=transport,
                toolsets=toolsets,
                queued_at=queued_at,
            )
            _append_record(settings, queued_record)
            return StagedAgentRunCreation(
                queued_record=queued_record,
                run_request=run_request,
            )


def complete_agent_run_creation(
    *,
    staged: StagedAgentRunCreation,
    settings: Any,
) -> AgentRunCreateResponse:
    """Dispatch-side second half: duplicate waits and broker send live here."""
    repo = GovernanceRepository(base_dir=settings.governance_path)
    if staged.existing is not None:
        return _create_response_for_existing_record(staged.existing)

    if staged.pending_idempotency_scope is not None:
        resolved = _wait_for_idempotent_dispatch_resolution(
            repo=repo,
            owner_user_id=staged.pending_idempotency_scope[0],
            conversation_id=staged.pending_idempotency_scope[1],
            client_request_id=staged.pending_idempotency_scope[2],
        )
        if resolved is None:
            raise AgentRunDispatchError(
                "Agent run dispatch acceptance is unresolved for the repeated "
                "client request."
            )
        return _create_response_for_existing_record(resolved)

    queued_record = staged.queued_record
    run_request = staged.run_request
    assert queued_record is not None
    assert run_request is not None

    try:
        execute_agent_run_task.send(run_id=queued_record.run_id)
    except Exception as exc:
        finished_at = _utc_now()
        error_message = _safe_run_error_message(
            _DISPATCH_FAILURE_CODE,
            provider=queued_record.provider,
        )
        _LOGGER.error(
            "Agent run dispatch failed run_id=%s provider=%s error_type=%s error_code=%s",
            queued_record.run_id,
            queued_record.provider,
            exc.__class__.__name__,
            _DISPATCH_FAILURE_CODE,
        )
        failed_record = _transition_record(
            settings=settings,
            run_id=queued_record.run_id,
            request=run_request,
            status="failed",
            finished_at=finished_at,
            error_message=error_message,
        )
        _append_record_if_latest_status(
            settings=settings,
            record=failed_record,
            allowed_statuses=set(_ACTIVE_AGENT_RUN_STATUSES),
            audit_payload=_build_failed_run_audit_payload(
                run_id=queued_record.run_id,
                request=run_request,
                provider=failed_record.provider,
                error_type=AgentRunDispatchError.__name__,
                error_code=_DISPATCH_FAILURE_CODE,
            ),
        )
        raise AgentRunDispatchError(error_message) from None
    _append_dispatch_acceptance(repo=repo, run_id=queued_record.run_id)

    return AgentRunCreateResponse(
        run_id=queued_record.run_id,
        status="queued",
        conversation_id=queued_record.conversation_id,
        retry_of_run_id=queued_record.retry_of_run_id,
        artifact_refs=queued_record.artifact_refs,
        provider=queued_record.provider,
        model=queued_record.model,
        transport=queued_record.transport,
        toolsets=queued_record.toolsets,
        queued_at=queued_record.queued_at or _utc_now(),
    )


def get_agent_run_status(*, run_id: str, settings: Any) -> AgentRunStatusResponse:
    return _status_from_run_record(run_id=run_id, settings=settings)


def get_agent_run_owner(*, run_id: str, settings: Any) -> str | None:
    record = _latest_run_record(run_id=run_id, settings=settings)
    if record is None:
        raise ValueError(f"Unknown agent run_id={run_id}")
    request = record.get("request")
    if not isinstance(request, dict):
        return None
    context = request.get("context")
    if not isinstance(context, dict):
        return None
    user_id = str(context.get("user_id") or "").strip()
    return user_id or None


def execute_agent_run_by_id(
    *,
    run_id: str,
    settings: Any,
    executor: AgentExecutor,
) -> AgentRunStatusResponse:
    record = _latest_run_record(run_id=run_id, settings=settings)
    if record is None:
        raise ValueError(f"Unknown agent run_id={run_id}")
    status = str(record.get("status") or "")
    if status in _TERMINAL_AGENT_RUN_STATUSES:
        return _status_from_record(record)
    if status not in _ACTIVE_AGENT_RUN_STATUSES:
        raise AgentRunStateConflict(
            f"Agent run {run_id} has unsupported lifecycle status={status or '<empty>'}."
        )

    request = _request_from_run_record(record=record, run_id=run_id)
    _execute_agent_run(
        run_id=run_id,
        request=request,
        settings=settings,
        executor=executor,
    )
    return _status_from_run_record(run_id=run_id, settings=settings)


def list_agent_runs(
    *,
    settings: Any,
    owner_user_id: str,
    limit: int = 20,
    conversation_id: str | None = None,
) -> AgentRunListResponse:
    normalized_owner = str(owner_user_id or "").strip()
    normalized_limit = max(int(limit), 0)
    normalized_conversation_id = str(conversation_id or "").strip() or None
    if not normalized_owner or normalized_limit == 0:
        return AgentRunListResponse(items=[])

    latest_by_run_id: dict[str, dict[str, object]] = {}
    records = GovernanceRepository(base_dir=settings.governance_path).read_all(
        AGENT_RUN_STREAM
    )
    for record in records:
        run_id = str(record.get("run_id") or "").strip()
        if run_id:
            latest_by_run_id[run_id] = record

    owned_records = [
        record
        for record in latest_by_run_id.values()
        if _owner_from_run_record(record) == normalized_owner
        and (
            normalized_conversation_id is None
            or _conversation_id_from_run_record(record)
            == normalized_conversation_id
        )
    ]
    owned_records.sort(key=_run_record_sort_time, reverse=True)
    selected = owned_records[:normalized_limit]
    for record in selected:
        _remember_run_record(record)
    # 列表与单条状态端点共用同一 stale 判定，避免同一 run 两端点状态矛盾。
    # 这里只调整展示视图，不写回：收敛落盘仍由单条状态读取路径完成。
    return AgentRunListResponse(
        items=[
            _status_from_record(
                _stale_adjusted_record_view(record=record, settings=settings)
            )
            for record in selected
        ]
    )


def cancel_agent_run(*, run_id: str, settings: Any) -> AgentRunStatusResponse:
    record = _latest_run_record(run_id=run_id, settings=settings)
    if record is None:
        raise ValueError(f"Unknown agent run_id={run_id}")
    status = str(record.get("status") or "")
    if status == "cancelled":
        return _status_from_record(record)
    if status not in _ACTIVE_AGENT_RUN_STATUSES:
        raise AgentRunStateConflict(
            f"Agent run {run_id} cannot be cancelled from status={status or '<empty>'}."
        )

    request = _request_from_run_record(record=record, run_id=run_id)
    finished_at = _utc_now()
    cancelled_record = _transition_record(
        settings=settings,
        run_id=run_id,
        request=request,
        status="cancelled",
        started_at=_optional_text(record.get("started_at")),
        finished_at=finished_at,
        elapsed_seconds=_elapsed_between(
            record.get("started_at"),
            finished_at,
        ),
    )
    appended = _append_record_if_latest_status(
        settings=settings,
        record=cancelled_record,
        allowed_statuses=set(_ACTIVE_AGENT_RUN_STATUSES),
    )
    if appended:
        return _status_from_record(
            cancelled_record.model_dump(mode="json", exclude_none=True)
        )

    latest = _latest_run_record(run_id=run_id, settings=settings)
    if latest is None:
        raise ValueError(f"Unknown agent run_id={run_id}")
    latest_status = str(latest.get("status") or "")
    if latest_status == "cancelled":
        return _status_from_record(latest)
    raise AgentRunStateConflict(
        f"Agent run {run_id} cannot be cancelled from status={latest_status or '<empty>'}."
    )


def retry_agent_run(*, run_id: str, settings: Any) -> AgentRunCreateResponse:
    staged = stage_agent_run_retry(run_id=run_id, settings=settings)
    return complete_agent_run_creation(staged=staged, settings=settings)


def stage_agent_run_retry(*, run_id: str, settings: Any) -> StagedAgentRunCreation:
    """Lock-friendly first half of a retry: validate source run and stage.

    Mirrors `stage_agent_run_creation`'s contract: safe to call under the
    agent workspace lifecycle lock (no dispatch waits, no broker send); pass
    the result to `complete_agent_run_creation` outside such locks.
    """
    record = _latest_run_record(run_id=run_id, settings=settings)
    if record is None:
        raise ValueError(f"Unknown agent run_id={run_id}")
    status = str(record.get("status") or "")
    if status not in {"failed", "cancelled"}:
        raise AgentRunStateConflict(
            f"Agent run {run_id} cannot be retried from status={status or '<empty>'}."
        )

    request = _request_from_run_record(record=record, run_id=run_id)
    retry_request = request.model_copy(
        update={
            "context": {
                **request.context,
                "retry_of_run_id": run_id,
                "client_request_id": f"retry:{run_id}",
            }
        }
    )
    return stage_agent_run_creation(
        request=retry_request,
        settings=settings,
        provider=_optional_text(record.get("provider")),
    )


def fail_agent_run(*, run_id: str, settings: Any, error: BaseException) -> None:
    """Persist a still-active run as failed after a worker-side preparation error.

    Used by the run worker when execution cannot even start (for example an
    unsupported provider or an unrecoverable persisted request payload), so the
    run does not stay queued forever. Also accepts ``BaseException`` interrupts
    (e.g. Dramatiq ``TimeLimitExceeded``) so a time-limited worker converges the
    run before re-raising. Terminal runs are left untouched and the raw error
    detail is never disclosed in run records or audit rows.
    """
    record = _latest_run_record(run_id=run_id, settings=settings)
    if record is None:
        return
    if str(record.get("status") or "") in _TERMINAL_AGENT_RUN_STATUSES:
        return

    try:
        request = _request_from_run_record(record=record, run_id=run_id)
    except RuntimeError:
        request = AgentQueryRequest(
            question=_reconstructed_question(record.get("question")),
            context={"run_id": run_id},
        )
    provider = str(record.get("provider") or "hermes")
    error_message = _safe_run_error_message(
        _PREPARATION_FAILURE_CODE,
        provider=provider,
    )
    _LOGGER.error(
        "Agent run preparation failed run_id=%s provider=%s error_type=%s error_code=%s",
        run_id,
        provider,
        error.__class__.__name__,
        _PREPARATION_FAILURE_CODE,
    )
    finished_at = _utc_now()
    failed_record = _transition_record(
        settings=settings,
        run_id=run_id,
        request=request,
        status="failed",
        started_at=_optional_text(record.get("started_at")),
        finished_at=finished_at,
        elapsed_seconds=_elapsed_between(record.get("started_at"), finished_at),
        error_message=error_message,
    )
    _append_record_if_latest_status(
        settings=settings,
        record=failed_record,
        allowed_statuses=set(_ACTIVE_AGENT_RUN_STATUSES),
        audit_payload=_build_failed_run_audit_payload(
            run_id=run_id,
            request=request,
            provider=failed_record.provider,
            error_type=error.__class__.__name__,
            error_code=_PREPARATION_FAILURE_CODE,
        ),
    )


def _status_from_run_record(*, run_id: str, settings: Any) -> AgentRunStatusResponse:
    record = _latest_run_record(run_id=run_id, settings=settings)
    if record is None:
        raise ValueError(f"Unknown agent run_id={run_id}")
    record = _reconcile_stale_run_record(record=record, settings=settings)
    return _status_from_record(record)


def _reconcile_stale_run_record(
    *,
    record: dict[str, object],
    settings: Any,
) -> dict[str, object]:
    reconciliation = _stale_run_reconciliation(record=record, settings=settings)
    if reconciliation is None:
        return record
    failed_record, allowed_statuses, error_type = reconciliation

    request = record.get("request")
    try:
        audit_request = AgentQueryRequest.model_validate(
            request if isinstance(request, dict) else {"question": failed_record.question}
        )
    except (TypeError, ValueError):
        audit_request = AgentQueryRequest(
            question=_reconstructed_question(failed_record.question)
        )
    appended = _append_record_if_latest_status(
        settings=settings,
        record=failed_record,
        allowed_statuses=allowed_statuses,
        audit_payload=_build_failed_run_audit_payload(
            run_id=failed_record.run_id,
            request=audit_request,
            provider=failed_record.provider,
            error_type=error_type,
        ),
    )
    if not appended:
        return _latest_run_record(run_id=failed_record.run_id, settings=settings) or record
    return failed_record.model_dump(mode="json", exclude_none=True)


def _stale_run_reconciliation(
    *,
    record: dict[str, object],
    settings: Any,
) -> tuple[AgentRunRecord, set[str], str] | None:
    """Compute the stale-failure view for an active record without persisting it.

    Returns ``(failed_record, allowed_statuses, error_type)`` when the record
    exceeded its stale deadline, or ``None`` when it is not stale. Shared by the
    persisting reconciliation (`_reconcile_stale_run_record`) and the read-only
    list path so both endpoints report the same status for the same run.
    """
    status = str(record.get("status") or "")
    if status not in _ACTIVE_AGENT_RUN_STATUSES:
        return None

    finished_at_text = _utc_now()
    finished_at = _parse_utc_datetime(finished_at_text)
    if status == "queued":
        anchor = _parse_utc_datetime(record.get("queued_at"))
        stale_after_seconds = _agent_run_queued_stale_after_seconds(settings)
        allowed_statuses = {"queued"}
        error_type = "StaleQueuedAgentRun"
    else:
        anchor = _parse_utc_datetime(record.get("started_at"))
        stale_after_seconds = _agent_run_stale_after_seconds(record=record, settings=settings)
        allowed_statuses = {"starting", "running"}
        error_type = "StaleAgentRun"
    if anchor is None or finished_at is None:
        return None

    elapsed_seconds = max((finished_at - anchor).total_seconds(), 0.0)
    if elapsed_seconds <= stale_after_seconds:
        return None

    if status == "queued":
        error_message = (
            f"Agent run 排队超过 {stale_after_seconds:g}s 仍未开始执行，"
            "可能因任务派发丢失或 worker 中断。"
        )
        reconciled_elapsed_seconds = None
    else:
        error_message = (
            "Agent run 未在运行超时后进入终态"
            f"（{stale_after_seconds:g}s），可能因进程重启或运行中断。"
        )
        reconciled_elapsed_seconds = round(elapsed_seconds, 3)

    request = record.get("request")
    failed_record = AgentRunRecord(
        run_id=str(record.get("run_id") or ""),
        status="failed",
        conversation_id=_conversation_id_from_run_record(record),
        retry_of_run_id=_retry_of_run_id_from_record(record),
        artifact_refs=_artifact_refs_from_run_record(record),
        question=str(record.get("question") or ""),
        request=dict(request) if isinstance(request, dict) else {},
        provider=str(record.get("provider") or "hermes"),
        model=str(record.get("model") or "default"),
        transport=str(record.get("transport") or "bridge"),
        toolsets=str(record.get("toolsets") or "default"),
        queued_at=_optional_text(record.get("queued_at")),
        started_at=_optional_text(record.get("started_at")),
        finished_at=finished_at_text,
        elapsed_seconds=reconciled_elapsed_seconds,
        error_message=error_message,
    )
    return failed_record, allowed_statuses, error_type


def _stale_adjusted_record_view(
    *,
    record: dict[str, object],
    settings: Any,
) -> dict[str, object]:
    """Read-only stale view: same judgment as reconciliation, no write-back."""
    reconciliation = _stale_run_reconciliation(record=record, settings=settings)
    if reconciliation is None:
        return record
    return reconciliation[0].model_dump(mode="json", exclude_none=True)


def _agent_run_queued_stale_after_seconds(settings: Any) -> float:
    try:
        timeout = float(
            getattr(
                settings,
                "agent_run_queued_timeout_seconds",
                AGENT_RUN_QUEUED_STALE_SECONDS,
            )
            or AGENT_RUN_QUEUED_STALE_SECONDS
        )
    except (TypeError, ValueError):
        timeout = AGENT_RUN_QUEUED_STALE_SECONDS
    return max(timeout, 1.0)


def _agent_run_stale_after_seconds(
    *,
    record: dict[str, object],
    settings: Any,
) -> float:
    provider = str(record.get("provider") or "hermes").strip().lower()
    if provider == "local":
        try:
            local_timeout = float(
                getattr(
                    settings,
                    "agent_run_local_timeout_seconds",
                    AGENT_RUN_LOCAL_STALE_SECONDS,
                )
                or AGENT_RUN_LOCAL_STALE_SECONDS
            )
        except (TypeError, ValueError):
            local_timeout = AGENT_RUN_LOCAL_STALE_SECONDS
        return max(local_timeout, 1.0) + AGENT_RUN_STALE_GRACE_SECONDS
    setting_name = (
        "agent_dexter_timeout_seconds"
        if provider == "dexter"
        else "agent_hermes_timeout_seconds"
    )
    try:
        provider_timeout = float(getattr(settings, setting_name, 180.0) or 180.0)
    except (TypeError, ValueError):
        provider_timeout = 180.0
    return max(provider_timeout, 1.0) + AGENT_RUN_STALE_GRACE_SECONDS


def _parse_utc_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _latest_run_record(*, run_id: str, settings: Any) -> dict[str, object] | None:
    records = _load_run_records(settings, run_id=run_id)
    if records:
        latest_record = records[-1]
        _remember_run_record(latest_record)
        return latest_record

    cached_record = _load_cached_run_record(run_id)
    if cached_record is not None:
        return cached_record
    return None


def _request_from_run_record(
    *,
    record: dict[str, object],
    run_id: str,
) -> AgentQueryRequest:
    request_payload = record.get("request")
    if not isinstance(request_payload, dict):
        raise RuntimeError(f"Agent run {run_id} has no recoverable request payload.")
    question = request_payload.get("question")
    if isinstance(question, str):
        # 早于 question min/max_length 约束落地的历史 run 可能带超长/空 question；
        # execute/cancel/retry 的重建路径不得因此抛错。复用 _reconstructed_question
        # 收敛到当前边界（run 记录与状态响应保留原文，仅重建的请求视图被截断）。
        request_payload = {
            **request_payload,
            "question": _reconstructed_question(question),
        }
    try:
        request = AgentQueryRequest.model_validate(request_payload)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Agent run {run_id} has an invalid persisted request payload."
        ) from exc
    return request.model_copy(
        update={
            "context": {
                **request.context,
                "run_id": run_id,
            }
        }
    )


def _owner_from_run_record(record: dict[str, object]) -> str | None:
    request = record.get("request")
    if not isinstance(request, dict):
        return None
    context = request.get("context")
    if not isinstance(context, dict):
        return None
    owner = str(context.get("user_id") or "").strip()
    return owner or None


def _conversation_id_from_run_record(record: dict[str, object]) -> str | None:
    conversation_id = _optional_text(record.get("conversation_id"))
    if conversation_id is not None:
        return conversation_id
    return _context_identifier_from_run_record(record, "conversation_id")


def _retry_of_run_id_from_record(record: dict[str, object]) -> str | None:
    retry_of_run_id = _optional_text(record.get("retry_of_run_id"))
    if retry_of_run_id is not None:
        return retry_of_run_id
    return _context_identifier_from_run_record(record, "retry_of_run_id")


def _client_request_id_from_run_record(record: dict[str, object]) -> str | None:
    return _context_identifier_from_run_record(record, "client_request_id")


def _create_idempotency_scope(
    request: AgentQueryRequest,
) -> tuple[str, str | None, str] | None:
    """Idempotency scope for run creation.

    ``conversation_id`` is optional: conversationless runs (including retries
    of conversationless runs, whose ``client_request_id`` is deterministic)
    degrade to a ``(user_id, client_request_id)`` scope instead of losing
    duplicate protection entirely. A ``None`` conversation only matches
    records that also have no conversation.
    """
    owner_user_id = _context_identifier(request.context, "user_id")
    conversation_id = _context_identifier(request.context, "conversation_id")
    client_request_id = _context_identifier(request.context, "client_request_id")
    if owner_user_id is None or client_request_id is None:
        return None
    return owner_user_id, conversation_id, client_request_id


def _find_existing_idempotent_run_record(
    *,
    repo: GovernanceRepository,
    owner_user_id: str,
    conversation_id: str | None,
    client_request_id: str,
) -> dict[str, object] | None:
    """Pick the record a duplicate create should observe for this scope.

    Active or completed runs win (earliest, deterministic under concurrency)
    so duplicates short-circuit to them. Only when every run under the scope
    is terminal ``failed``/``cancelled`` does the earliest terminal record
    surface — the create path then allows a fresh run, while the dispatch
    waiter still sees a dispatch-failure record to propagate.
    """
    latest_by_run_id: dict[str, dict[str, object]] = {}
    for record in repo.read_all(AGENT_RUN_STREAM):
        run_id = str(record.get("run_id") or "").strip()
        if not run_id:
            continue
        if _owner_from_run_record(record) != owner_user_id:
            continue
        if _conversation_id_from_run_record(record) != conversation_id:
            continue
        if _client_request_id_from_run_record(record) != client_request_id:
            continue
        latest_by_run_id[run_id] = record
    if not latest_by_run_id:
        return None

    def _sort_key(record: dict[str, object]) -> tuple[datetime, str]:
        return (
            _run_record_sort_time(record),
            str(record.get("run_id") or ""),
        )

    reusable = [
        record
        for record in latest_by_run_id.values()
        if str(record.get("status") or "") not in {"failed", "cancelled"}
    ]
    if reusable:
        return min(reusable, key=_sort_key)
    return min(latest_by_run_id.values(), key=_sort_key)


def _create_response_for_existing_record(
    record: dict[str, object],
) -> AgentRunCreateResponse:
    error_message = _optional_text(record.get("error_message"))
    if (
        str(record.get("status") or "") == "failed"
        and error_message is not None
        and error_message
        == _safe_run_error_message(
            _DISPATCH_FAILURE_CODE,
            provider=_optional_text(record.get("provider")),
        )
    ):
        raise AgentRunDispatchError(error_message)
    _remember_run_record(record)
    return _create_response_from_record(record)


def _is_dispatch_pending_record(
    *,
    repo: GovernanceRepository,
    record: dict[str, object],
) -> bool:
    if str(record.get("status") or "") != "queued":
        return False
    run_id = str(record.get("run_id") or "").strip()
    if not run_id:
        return False
    return not _is_dispatch_accepted(repo=repo, run_id=run_id)


def _is_dispatch_accepted(*, repo: GovernanceRepository, run_id: str) -> bool:
    return any(
        str(record.get("run_id") or "").strip() == run_id
        for record in repo.read_all(AGENT_RUN_DISPATCH_STREAM)
    )


def _append_dispatch_acceptance(
    *,
    repo: GovernanceRepository,
    run_id: str,
) -> None:
    repo.append(
        AGENT_RUN_DISPATCH_STREAM,
        {
            "run_id": run_id,
            "accepted_at": _utc_now(),
        },
    )


def _wait_for_idempotent_dispatch_resolution(
    *,
    repo: GovernanceRepository,
    owner_user_id: str,
    conversation_id: str | None,
    client_request_id: str,
) -> dict[str, object] | None:
    deadline = time.monotonic() + AGENT_RUN_DISPATCH_WAIT_SECONDS
    while time.monotonic() < deadline:
        existing = _find_existing_idempotent_run_record(
            repo=repo,
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            client_request_id=client_request_id,
        )
        if existing is not None and not _is_dispatch_pending_record(
            repo=repo,
            record=existing,
        ):
            return existing
        time.sleep(AGENT_RUN_DISPATCH_POLL_SECONDS)
    return None


def _context_identifier_from_run_record(
    record: dict[str, object],
    key: str,
) -> str | None:
    request = record.get("request")
    if not isinstance(request, dict):
        return None
    context = request.get("context")
    if not isinstance(context, dict):
        return None
    return _context_identifier(context, key)


def _reconstructed_question(value: object) -> str:
    """Coerce a historical question into the current AgentQueryRequest bounds.

    Records persisted before the ``min_length=1`` / ``max_length=8000``
    constraint may carry over-long or empty questions; reconstruction paths
    must not raise on them. Run records and status responses keep the original
    text — only the rebuilt request/audit view is truncated.
    """
    text = str(value or "")[:_RECONSTRUCTED_QUESTION_MAX_LENGTH]
    return text or "(question unavailable)"


def _context_identifier(
    context: dict[str, object],
    key: str,
) -> str | None:
    value = context.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _artifact_refs_from_run_record(
    record: dict[str, object],
) -> list[str] | None:
    artifact_refs = _artifact_refs_from_value(record.get("artifact_refs"))
    if artifact_refs is not None:
        return artifact_refs

    result = record.get("result")
    if isinstance(result, dict):
        artifact_refs = _artifact_refs_from_value(result.get("artifact_refs"))
        if artifact_refs is not None:
            return artifact_refs
        run_id = _optional_text(record.get("run_id"))
        if run_id is not None and _conversation_id_from_run_record(record) is not None:
            return [f"artifact:{run_id}"]
    return None


def _artifact_refs_from_value(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    refs = list(
        dict.fromkeys(
            text
            for item in value
            if (text := str(item or "").strip())
        )
    )
    return refs or None


def _run_record_sort_time(record: dict[str, object]) -> datetime:
    for field in ("queued_at", "started_at", "finished_at"):
        parsed = _parse_utc_datetime(record.get(field))
        if parsed is not None:
            return parsed
    return datetime.min.replace(tzinfo=UTC)


def _elapsed_between(started_at: object, finished_at: object) -> float | None:
    started = _parse_utc_datetime(started_at)
    finished = _parse_utc_datetime(finished_at)
    if started is None or finished is None:
        return None
    return round(max((finished - started).total_seconds(), 0.0), 3)


def _execute_agent_run(
    *,
    run_id: str,
    request: AgentQueryRequest,
    settings: Any,
    executor: AgentExecutor,
) -> None:
    started_at = _utc_now()
    starting_record = _transition_record(
        settings=settings,
        run_id=run_id,
        request=request,
        status="starting",
        started_at=started_at,
    )
    if not _append_record_if_latest_status(
        settings=settings,
        record=starting_record,
        allowed_statuses={"queued"},
    ):
        return
    running_record = _transition_record(
        settings=settings,
        run_id=run_id,
        request=request,
        status="running",
        started_at=started_at,
    )
    if not _append_record_if_latest_status(
        settings=settings,
        record=running_record,
        allowed_statuses={"starting"},
    ):
        return
    started = datetime.now(UTC)
    outcome = _run_executor_until_run_is_terminal(
        run_id=run_id,
        request=request,
        settings=settings,
        executor=executor,
    )
    if outcome is None:
        _LOGGER.info(
            "Agent run execution abandoned after external terminal transition run_id=%s",
            run_id,
        )
        return

    error = outcome.get("error")
    if isinstance(error, Exception):
        finished_at = _utc_now()
        provider = str(running_record.provider or "hermes")
        error_message = str(error) or error.__class__.__name__
        error_code: str | None = None
        if provider != "local":
            error_message = _safe_run_error_message(
                _EXECUTION_FAILURE_CODE,
                provider=provider,
            )
            error_code = _EXECUTION_FAILURE_CODE
        _LOGGER.error(
            "Agent run execution failed run_id=%s provider=%s error_type=%s error_code=%s",
            run_id,
            provider,
            error.__class__.__name__,
            _EXECUTION_FAILURE_CODE,
        )
        failed_record = _transition_record(
            settings=settings,
            run_id=run_id,
            request=request,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=_elapsed_seconds(started),
            error_message=error_message,
        )
        _append_record_if_latest_status(
            settings=settings,
            record=failed_record,
            allowed_statuses={"starting", "running"},
            audit_payload=_build_failed_run_audit_payload(
                run_id=run_id,
                request=request,
                provider=failed_record.provider,
                error_type=error.__class__.__name__,
                error_code=error_code,
            ),
        )
        return

    envelope = outcome.get("envelope")
    if not isinstance(envelope, AgentEnvelope):
        # Class identity may rotate when the schemas module is reloaded (e.g.
        # module fresh-loads in tests or hot reload); accept any same-shaped
        # envelope by re-validating it instead of dropping the result.
        try:
            envelope = AgentEnvelope.model_validate(envelope.model_dump(mode="python"))
        except Exception:
            # The executor thread ended without a usable result (e.g.
            # interrupted by a BaseException); the run converges later via
            # stale reconciliation. Log loudly: a dropped result must stay
            # observable.
            _LOGGER.warning(
                "Agent run executor ended without a usable envelope run_id=%s outcome_type=%s outcome_type_module=%s",
                run_id,
                type(envelope).__name__,
                getattr(type(envelope), "__module__", "<unknown>"),
            )
            return
    finished_at = _utc_now()
    completed_record = _transition_record(
        settings=settings,
        run_id=run_id,
        request=request,
        status="completed",
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=_elapsed_seconds(started),
        result=envelope.model_dump(mode="json"),
    )
    _append_record_if_latest_status(
        settings=settings,
        record=completed_record,
        allowed_statuses={"starting", "running"},
    )


def _run_executor_until_run_is_terminal(
    *,
    run_id: str,
    request: AgentQueryRequest,
    settings: Any,
    executor: AgentExecutor,
) -> dict[str, object] | None:
    """Invoke the executor on a side thread until it finishes or the run is terminal.

    Returns the executor outcome (``envelope`` or ``error``), or ``None`` when
    the run reached a terminal state externally (cancel or stale reconciliation)
    while the provider call was still in flight. In that case the worker slot is
    released immediately; the abandoned provider result is discarded later by
    the status-guarded append.
    """
    outcome: dict[str, object] = {}
    done = threading.Event()

    def _invoke() -> None:
        try:
            outcome["envelope"] = executor(
                request,
                str(getattr(settings, "governance_path", "")),
                settings,
            )
        except Exception as exc:
            outcome["error"] = exc
        finally:
            done.set()

    threading.Thread(
        target=_invoke,
        name=f"agent-run-executor-{run_id}",
        daemon=True,
    ).start()

    consecutive_poll_failures = 0
    while not done.wait(timeout=AGENT_RUN_CANCEL_POLL_SECONDS):
        try:
            latest = _latest_run_record(run_id=run_id, settings=settings)
        except Exception as exc:
            # A transient governance read failure (e.g. lock contention) must not
            # abort supervision of an in-flight provider call, but while it lasts
            # the run cannot observe an external cancel. Report the start of each
            # failure streak so a broken governance store is distinguishable from
            # a cancel that was simply never requested.
            consecutive_poll_failures += 1
            if consecutive_poll_failures == 1:
                _LOGGER.warning(
                    "Agent run cancellation poll failed run_id=%s error_type=%s",
                    run_id,
                    exc.__class__.__name__,
                )
            continue
        consecutive_poll_failures = 0
        if (
            latest is not None
            and str(latest.get("status") or "") in _TERMINAL_AGENT_RUN_STATUSES
        ):
            return None
    return outcome


def _build_failed_run_audit_payload(
    *,
    run_id: str,
    request: AgentQueryRequest,
    provider: str,
    error_type: str,
    error_code: str | None = None,
) -> AgentAuditPayload:
    trace_id = f"tr_agent_run_failed_{uuid4().hex[:12]}"
    return AgentAuditPayload(
        user_id=str(request.context.get("user_id") or "agent_user"),
        query_text=request.question,
        tools_used=["agent_run", f"provider:{provider}", "status:failed"],
        tables_used=[],
        filters_applied={
            key: value
            for key, value in request.filters.items()
            if value not in (None, "", False)
        },
        trace_id=trace_id,
        run_id=run_id,
        result_meta={
            "trace_id": trace_id,
            "basis": request.basis,
            "result_kind": "agent.run_failed",
            "formal_use_allowed": False,
            "quality_flag": "error",
            # Human: caliber-formal_scenario_gate-justified -- this only discloses
            # the already-selected request basis in failed-run metadata; it cannot
            # authorize formal or scenario use.
            "scenario_flag": request.basis == "scenario",
            "provider": provider,
            "error_type": error_type,
            **({"error_code": error_code} if error_code is not None else {}),
        },
    )


def _safe_run_error_message(
    error_code: str,
    *,
    provider: str | None = None,
) -> str:
    normalized_provider = str(provider or "").strip().lower()
    if error_code == _DISPATCH_FAILURE_CODE:
        return "Agent run dispatch failed."
    if error_code == _PREPARATION_FAILURE_CODE:
        return "Agent run preparation failed."
    if error_code == _EXECUTION_FAILURE_CODE and normalized_provider != "local":
        return "Agent provider execution failed."
    return "Agent run failed."


def _transition_record(
    *,
    settings: Any,
    run_id: str,
    request: AgentQueryRequest,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    elapsed_seconds: float | None = None,
    error_message: str | None = None,
    result: dict[str, object] | None = None,
) -> AgentRunRecord:
    initial = _load_cached_run_record(run_id) or _load_run_records(settings, run_id=run_id)[0]
    provider, model, transport, toolsets = _provider_runtime_fields(
        settings,
        str(initial.get("provider") or getattr(settings, "agent_provider", "hermes") or "hermes"),
    )
    return AgentRunRecord(
        run_id=run_id,
        status=status,
        conversation_id=(
            _optional_text(initial.get("conversation_id"))
            or _context_identifier(request.context, "conversation_id")
        ),
        retry_of_run_id=(
            _optional_text(initial.get("retry_of_run_id"))
            or _context_identifier(request.context, "retry_of_run_id")
        ),
        artifact_refs=(
            _artifact_refs_from_value(initial.get("artifact_refs"))
            or (
                [f"artifact:{run_id}"]
                if status == "completed"
                and _context_identifier(request.context, "conversation_id")
                and result is not None
                else None
            )
        ),
        question=request.question,
        request=request.model_dump(mode="json"),
        provider=str(initial.get("provider") or provider),
        model=str(initial.get("model") or model),
        transport=str(initial.get("transport") or transport),
        toolsets=str(initial.get("toolsets") or toolsets),
        queued_at=str(initial.get("queued_at") or ""),
        started_at=started_at or _optional_text(initial.get("started_at")),
        finished_at=finished_at,
        elapsed_seconds=elapsed_seconds,
        error_message=error_message,
        result=result,
    )


def _append_record_if_latest_status(
    *,
    settings: Any,
    record: AgentRunRecord,
    allowed_statuses: set[str],
    audit_payload: AgentAuditPayload | None = None,
) -> bool:
    repo = GovernanceRepository(base_dir=settings.governance_path)
    with AGENT_RUN_TRANSITION_LOCK:
        with acquire_lock(
            AGENT_RUN_TRANSITION_FILE_LOCK,
            base_dir=repo.base_dir,
            timeout_seconds=5.0,
        ):
            matching = [
                item
                for item in repo.read_all(AGENT_RUN_STREAM)
                if str(item.get("run_id") or "") == record.run_id
            ]
            if not matching:
                return False
            latest = matching[-1]
            if str(latest.get("status") or "") not in allowed_statuses:
                _remember_run_record(latest)
                return False

            record_payload: dict[str, object] = {
                "job_name": AGENT_RUN_JOB_NAME,
                **record.model_dump(mode="json", exclude_none=True),
            }
            entries = [(AGENT_RUN_STREAM, record_payload)]
            if audit_payload is not None:
                entries.append(
                    (
                        AGENT_AUDIT_STREAM,
                        audit_payload.model_dump(mode="json", exclude_none=True),
                    )
                )
            repo.append_many_atomic(entries)
            _remember_run_record(record.model_dump(mode="json", exclude_none=True))
            return True


def _append_record(settings: Any, record: AgentRunRecord) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        AGENT_RUN_STREAM,
        {
            "job_name": AGENT_RUN_JOB_NAME,
            **record.model_dump(mode="json", exclude_none=True),
        },
    )
    _remember_run_record(record.model_dump(mode="json", exclude_none=True))


def _remember_run_record(record: dict[str, object]) -> None:
    run_id = str(record.get("run_id") or "").strip()
    if not run_id:
        return
    with AGENT_RUN_STATE_LOCK:
        _AGENT_RUN_LATEST_RECORDS[run_id] = dict(record)
        while len(_AGENT_RUN_LATEST_RECORDS) > MAX_AGENT_RUN_CACHE_SIZE:
            _AGENT_RUN_LATEST_RECORDS.pop(next(iter(_AGENT_RUN_LATEST_RECORDS)))


def _load_cached_run_record(run_id: str) -> dict[str, object] | None:
    with AGENT_RUN_STATE_LOCK:
        record = _AGENT_RUN_LATEST_RECORDS.get(run_id)
        return dict(record) if record is not None else None


def _load_run_records(settings: Any, *, run_id: str) -> list[dict[str, object]]:
    records = [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(AGENT_RUN_STREAM)
        if str(record.get("run_id") or "") == run_id
    ]
    return records


def _status_from_record(record: dict[str, object]) -> AgentRunStatusResponse:
    result = record.get("result")
    return AgentRunStatusResponse(
        run_id=str(record.get("run_id") or ""),
        status=str(record.get("status") or "failed"),
        conversation_id=_conversation_id_from_run_record(record),
        retry_of_run_id=_retry_of_run_id_from_record(record),
        artifact_refs=_artifact_refs_from_run_record(record),
        question=_optional_text(record.get("question")),
        provider=str(record.get("provider") or "hermes"),
        model=str(record.get("model") or "default"),
        transport=str(record.get("transport") or "bridge"),
        toolsets=str(record.get("toolsets") or "default"),
        queued_at=_optional_text(record.get("queued_at")),
        started_at=_optional_text(record.get("started_at")),
        finished_at=_optional_text(record.get("finished_at")),
        elapsed_seconds=_optional_float(record.get("elapsed_seconds")),
        error_message=_optional_text(record.get("error_message")),
        result=result if isinstance(result, dict) else None,
    )


def _create_response_from_record(record: dict[str, object]) -> AgentRunCreateResponse:
    return AgentRunCreateResponse(
        run_id=str(record.get("run_id") or ""),
        status=str(record.get("status") or "queued"),
        conversation_id=_conversation_id_from_run_record(record),
        retry_of_run_id=_retry_of_run_id_from_record(record),
        artifact_refs=_artifact_refs_from_run_record(record),
        provider=str(record.get("provider") or "hermes"),
        model=str(record.get("model") or "default"),
        transport=str(record.get("transport") or "bridge"),
        toolsets=str(record.get("toolsets") or "default"),
        queued_at=_optional_text(record.get("queued_at")) or _utc_now(),
    )


def _build_run_id() -> str:
    return f"agent_run:{datetime.now(UTC).isoformat()}:{uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _elapsed_seconds(started: datetime) -> float:
    return round((datetime.now(UTC) - started).total_seconds(), 3)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
