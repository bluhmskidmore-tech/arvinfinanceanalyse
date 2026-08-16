from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.governance.settings import get_settings
from backend.app.services import agent_run_service
from backend.app.services.agent_service import execute_agent_query
from backend.app.services.dexter_agent_service import execute_dexter_agent_query
from backend.app.services.hermes_agent_service import (
    execute_hermes_agent_query as _execute_hermes_agent_query_direct,
)
from backend.app.tasks.broker import register_actor_once

AGENT_RUN_TIME_LIMIT_MS = 3_600_000
_TERMINAL_AGENT_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
_AGENT_LAB_STREAM_PROTOCOL = "run_delta_v1"
_AGENT_LAB_STREAM_SURFACE = "lab"

AgentExecutor = Callable[[AgentQueryRequest, str, Any], AgentEnvelope]


def _execute_local_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope:
    return execute_agent_query(
        request=request,
        duckdb_path=str(getattr(settings, "duckdb_path", "")),
        governance_dir=governance_dir,
    )


def execute_hermes_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope:
    if (
        str(request.context.get("agent_stream_protocol") or "").strip()
        != _AGENT_LAB_STREAM_PROTOCOL
        or str(request.context.get("agent_stream_surface") or "").strip()
        != _AGENT_LAB_STREAM_SURFACE
    ):
        return _execute_hermes_agent_query_direct(request, governance_dir, settings)
    run_id = str(request.context.get("run_id") or "").strip()
    if not run_id:
        return _execute_hermes_agent_query_direct(request, governance_dir, settings)
    publisher = agent_run_service.build_agent_run_delta_publisher(
        run_id=run_id,
        settings=settings,
    )
    return _execute_hermes_agent_query_direct(
        request,
        governance_dir,
        settings,
        stream_delta_callback=publisher.publish,
        stream_should_continue=publisher.is_active,
    )


def _executor_for_provider(provider: object) -> AgentExecutor:
    normalized_provider = str(provider or "").strip().lower()
    executors: dict[str, AgentExecutor] = {
        "local": _execute_local_agent_query,
        "hermes": execute_hermes_agent_query,
        "dexter": execute_dexter_agent_query,
    }
    try:
        return executors[normalized_provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported agent run provider: {normalized_provider or '<empty>'}") from exc


def _execute_agent_run_task(*, run_id: str) -> None:
    settings = get_settings()
    current_status = agent_run_service.get_agent_run_status(
        run_id=run_id,
        settings=settings,
    )
    if str(current_status.status) in _TERMINAL_AGENT_RUN_STATUSES:
        return None

    try:
        executor = _executor_for_provider(current_status.provider)
        agent_run_service.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=executor,
        )
    except Exception as exc:
        # The actor has max_retries=0: without this the run would stay queued
        # forever after a preparation failure (e.g. unsupported provider or an
        # unrecoverable persisted request payload).
        agent_run_service.fail_agent_run(
            run_id=run_id,
            settings=settings,
            error=exc,
        )
    except BaseException as exc:
        # Dramatiq's time_limit interrupt (TimeLimitExceeded) subclasses
        # BaseException, so it bypasses the branch above. Converge the run to
        # failed first, then re-raise to preserve the worker interrupt
        # semantics (shutdown, time-limit accounting).
        agent_run_service.fail_agent_run(
            run_id=run_id,
            settings=settings,
            error=exc,
        )
        raise
    return None


execute_agent_run_task = register_actor_once(
    "execute_agent_run",
    _execute_agent_run_task,
    max_retries=0,
    time_limit_ms=AGENT_RUN_TIME_LIMIT_MS,
)
