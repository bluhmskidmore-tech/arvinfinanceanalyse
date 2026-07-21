from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.agent.runtime.toolset_policy import normalize_read_only_toolsets
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.agent.schemas.agent_run import (
    AgentRunCreateResponse,
    AgentRunRecord,
    AgentRunStatusResponse,
)
from backend.app.governance.agent_audit import AGENT_AUDIT_STREAM, AgentAuditPayload
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import GovernanceRepository

AGENT_RUN_STREAM = "agent_run"
AGENT_RUN_JOB_NAME = "agent_run"
AGENT_RUN_LOCK = threading.Lock()
AGENT_RUN_STATE_LOCK = threading.Lock()
AGENT_RUN_TRANSITION_LOCK = threading.RLock()
AGENT_RUN_TRANSITION_FILE_LOCK = LockDefinition(
    key="lock:agent-run:transition",
    ttl_seconds=300,
)
MAX_AGENT_RUN_CACHE_SIZE = 200
AGENT_RUN_STALE_GRACE_SECONDS = 30.0
_AGENT_RUN_LATEST_RECORDS: dict[str, dict[str, object]] = {}

AgentExecutor = Callable[[AgentQueryRequest, str, Any], AgentEnvelope]


async def iter_agent_run_events(
    *,
    run_id: str,
    settings: Any,
    initial_status: AgentRunStatusResponse | None = None,
    poll_interval_seconds: float = 0.5,
):
    """Yield distinct run snapshots as SSE frames until the run is terminal."""
    current_status = initial_status or get_agent_run_status(run_id=run_id, settings=settings)
    last_frame: str | None = None

    while True:
        frame = (
            "event: run_update\n"
            f"data: {current_status.model_dump_json(exclude_none=True)}\n\n"
        )
        if frame != last_frame:
            yield frame
            last_frame = frame
        if current_status.status in {"completed", "failed"}:
            return

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


def create_agent_run(
    *,
    request: AgentQueryRequest,
    settings: Any,
    executor: AgentExecutor,
    provider: str | None = None,
) -> AgentRunCreateResponse:
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
    provider, model, transport, toolsets = _provider_runtime_fields(settings, provider)
    record = AgentRunRecord(
        run_id=run_id,
        status="queued",
        question=run_request.question,
        request=run_request.model_dump(mode="json"),
        provider=provider,
        model=model,
        transport=transport,
        toolsets=toolsets,
        queued_at=queued_at,
    )
    _append_record(settings, record)

    thread = threading.Thread(
        target=_execute_agent_run,
        kwargs={
            "run_id": run_id,
            "request": run_request,
            "settings": settings,
            "executor": executor,
        },
        daemon=True,
        name=f"moss-agent-run-{run_id.split(':')[-1]}",
    )
    thread.start()

    return AgentRunCreateResponse(
        run_id=run_id,
        status="queued",
        provider=record.provider,
        model=record.model,
        transport=record.transport,
        toolsets=record.toolsets,
        queued_at=queued_at,
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
    if str(record.get("status") or "") not in {"starting", "running"}:
        return record

    started_at = _parse_utc_datetime(record.get("started_at"))
    finished_at_text = _utc_now()
    finished_at = _parse_utc_datetime(finished_at_text)
    if started_at is None or finished_at is None:
        return record

    elapsed_seconds = max((finished_at - started_at).total_seconds(), 0.0)
    stale_after_seconds = _agent_run_stale_after_seconds(record=record, settings=settings)
    if elapsed_seconds <= stale_after_seconds:
        return record

    request = record.get("request")
    failed_record = AgentRunRecord(
        run_id=str(record.get("run_id") or ""),
        status="failed",
        question=str(record.get("question") or ""),
        request=dict(request) if isinstance(request, dict) else {},
        provider=str(record.get("provider") or "hermes"),
        model=str(record.get("model") or "default"),
        transport=str(record.get("transport") or "bridge"),
        toolsets=str(record.get("toolsets") or "default"),
        queued_at=_optional_text(record.get("queued_at")),
        started_at=_optional_text(record.get("started_at")),
        finished_at=finished_at_text,
        elapsed_seconds=round(elapsed_seconds, 3),
        error_message=(
            "Agent run 未在运行超时后进入终态"
            f"（{stale_after_seconds:g}s），可能因进程重启或运行中断。"
        ),
    )
    try:
        audit_request = AgentQueryRequest.model_validate(
            request if isinstance(request, dict) else {"question": failed_record.question}
        )
    except (TypeError, ValueError):
        audit_request = AgentQueryRequest(question=failed_record.question)
    appended = _append_record_if_latest_status(
        settings=settings,
        record=failed_record,
        allowed_statuses={"starting", "running"},
        audit_payload=_build_failed_run_audit_payload(
            run_id=failed_record.run_id,
            request=audit_request,
            provider=failed_record.provider,
            error_type="StaleAgentRun",
        ),
    )
    if not appended:
        return _latest_run_record(run_id=failed_record.run_id, settings=settings) or record
    return failed_record.model_dump(mode="json", exclude_none=True)


def _agent_run_stale_after_seconds(
    *,
    record: dict[str, object],
    settings: Any,
) -> float:
    provider = str(record.get("provider") or "hermes").strip().lower()
    if provider == "local":
        return float("inf")
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


def _execute_agent_run(
    *,
    run_id: str,
    request: AgentQueryRequest,
    settings: Any,
    executor: AgentExecutor,
) -> None:
    with AGENT_RUN_LOCK:
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
        try:
            envelope = executor(
                request,
                str(getattr(settings, "governance_path", "")),
                settings,
            )
        except Exception as exc:
            finished_at = _utc_now()
            error_message = str(exc) or exc.__class__.__name__
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
                    error_type=exc.__class__.__name__,
                ),
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


def _build_failed_run_audit_payload(
    *,
    run_id: str,
    request: AgentQueryRequest,
    provider: str,
    error_type: str,
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
            "scenario_flag": request.basis == "scenario",
            "provider": provider,
            "error_type": error_type,
        },
    )


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
        status=status,  # type: ignore[arg-type]
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
        status=str(record.get("status") or "failed"),  # type: ignore[arg-type]
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
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
