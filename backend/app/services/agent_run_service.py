from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.agent.schemas.agent_run import (
    AgentRunCreateResponse,
    AgentRunRecord,
    AgentRunStatusResponse,
)
from backend.app.repositories.governance_repo import GovernanceRepository

AGENT_RUN_STREAM = "agent_run"
AGENT_RUN_JOB_NAME = "agent_run"
AGENT_RUN_LOCK = threading.Lock()
AGENT_RUN_STATE_LOCK = threading.Lock()
MAX_AGENT_RUN_CACHE_SIZE = 200
_AGENT_RUN_LATEST_RECORDS: dict[str, dict[str, object]] = {}

AgentExecutor = Callable[[AgentQueryRequest, str, Any], AgentEnvelope]


def _provider_runtime_fields(settings: Any, provider: str | None = None) -> tuple[str, str, str, str]:
    normalized_provider = str(provider or getattr(settings, "agent_provider", "hermes") or "hermes").strip().lower()
    if normalized_provider == "dexter":
        return (
            "dexter",
            str(getattr(settings, "agent_dexter_model", "") or "default"),
            str(getattr(settings, "agent_dexter_transport", "cli") or "cli"),
            str(getattr(settings, "agent_dexter_toolsets", "") or "default"),
        )
    return (
        "hermes",
        str(getattr(settings, "agent_hermes_model", "") or "default"),
        str(getattr(settings, "agent_hermes_transport", "bridge") or "bridge"),
        str(getattr(settings, "agent_hermes_toolsets", "") or "default"),
    )


def create_agent_run(
    *,
    request: AgentQueryRequest,
    settings: Any,
    executor: AgentExecutor,
) -> AgentRunCreateResponse:
    run_id = _build_run_id()
    queued_at = _utc_now()
    provider, model, transport, toolsets = _provider_runtime_fields(settings)
    record = AgentRunRecord(
        run_id=run_id,
        status="queued",
        question=request.question,
        request=request.model_dump(mode="json"),
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
            "request": request,
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
    records = _load_run_records(settings, run_id=run_id)
    if records:
        latest_record = records[-1]
        _remember_run_record(latest_record)
        return _status_from_record(latest_record)

    cached_record = _load_cached_run_record(run_id)
    if cached_record is not None:
        return _status_from_record(cached_record)
    raise ValueError(f"Unknown agent run_id={run_id}")


def _execute_agent_run(
    *,
    run_id: str,
    request: AgentQueryRequest,
    settings: Any,
    executor: AgentExecutor,
) -> None:
    with AGENT_RUN_LOCK:
        started_at = _utc_now()
        _append_record(
            settings,
            _transition_record(
                settings=settings,
                run_id=run_id,
                request=request,
                status="starting",
                started_at=started_at,
            ),
        )
        _append_record(
            settings,
            _transition_record(
                settings=settings,
                run_id=run_id,
                request=request,
                status="running",
                started_at=started_at,
            ),
        )
        started = datetime.now(timezone.utc)
        try:
            envelope = executor(
                request,
                str(getattr(settings, "governance_path", "")),
                settings,
            )
        except Exception as exc:
            finished_at = _utc_now()
            _append_record(
                settings,
                _transition_record(
                    settings=settings,
                    run_id=run_id,
                    request=request,
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    elapsed_seconds=_elapsed_seconds(started),
                    error_message=str(exc) or exc.__class__.__name__,
                ),
            )
            return

        finished_at = _utc_now()
        _append_record(
            settings,
            _transition_record(
                settings=settings,
                run_id=run_id,
                request=request,
                status="completed",
                started_at=started_at,
                finished_at=finished_at,
                elapsed_seconds=_elapsed_seconds(started),
                result=envelope.model_dump(mode="json"),
            ),
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


def _append_record(settings: Any, record: AgentRunRecord) -> None:
    GovernanceRepository(base_dir=getattr(settings, "governance_path")).append(
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
        for record in GovernanceRepository(base_dir=getattr(settings, "governance_path")).read_all(AGENT_RUN_STREAM)
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
        result=AgentEnvelope.model_validate(result) if isinstance(result, dict) else None,
    )


def _build_run_id() -> str:
    return f"agent_run:{datetime.now(timezone.utc).isoformat()}:{uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_seconds(started: datetime) -> float:
    return round((datetime.now(timezone.utc) - started).total_seconds(), 3)


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
