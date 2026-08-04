from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.governance.settings import get_settings
from backend.app.services import agent_run_service
from backend.app.services.agent_service import execute_agent_query
from backend.app.services.dexter_agent_service import execute_dexter_agent_query
from backend.app.services.hermes_agent_service import execute_hermes_agent_query
from backend.app.tasks.broker import register_actor_once

AGENT_RUN_TIME_LIMIT_MS = 3_600_000
_TERMINAL_AGENT_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})

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

    agent_run_service.execute_agent_run_by_id(
        run_id=run_id,
        settings=settings,
        executor=_executor_for_provider(current_status.provider),
    )
    return None


execute_agent_run_task = register_actor_once(
    "execute_agent_run",
    _execute_agent_run_task,
    max_retries=0,
    time_limit_ms=AGENT_RUN_TIME_LIMIT_MS,
)
