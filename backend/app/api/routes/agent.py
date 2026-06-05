from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.agent.schemas.agent_run import (
    AgentRunCreateResponse,
    AgentRunStatusResponse,
)
from backend.app.agent.tools.analysis_view_tool import (
    is_explicit_local_agent_intent,
    is_plain_analysis_chat_question,
)
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.agent_run_service import (
    create_agent_run,
    get_agent_run_owner,
    get_agent_run_status,
)
from backend.app.services.agent_service import (
    audit_disabled_agent_query,
    execute_agent_query,
    phase1_disabled_response,
)
from backend.app.services.dexter_agent_service import execute_dexter_agent_query
from backend.app.services.hermes_agent_service import execute_hermes_agent_query

router = APIRouter(prefix="/api/agent")


_MUTATING_ACTION_CONTEXT_KEYS = {
    "action",
    "action_type",
    "requested_action",
    "side_effect",
    "tool_action",
}
_MUTATING_ACTION_TOKENS = {
    "command",
    "delete",
    "export",
    "file_write",
    "import",
    "mutate",
    "refresh",
    "shell",
    "write",
    "删除",
    "刷新",
    "导入",
    "导出",
    "命令",
    "写入",
}
_READ_ONLY_AGENT_DETAIL = "Agent endpoints are read-only; mutating actions are not allowed."


def _provider_name(settings: object) -> str:
    return str(getattr(settings, "agent_provider", "local")).strip().lower() or "local"


def _run_executor_for_provider(settings: object):
    provider = _provider_name(settings)
    if provider == "hermes":
        return execute_hermes_agent_query
    if provider == "dexter":
        return execute_dexter_agent_query
    return None


def _provider_transport(settings: object) -> str:
    provider = _provider_name(settings)
    if provider == "dexter":
        return str(getattr(settings, "agent_dexter_transport", "cli") or "cli").strip().lower() or "cli"
    return str(getattr(settings, "agent_hermes_transport", "bridge") or "bridge").strip().lower() or "bridge"


def _should_execute_local_query(request: AgentQueryRequest) -> bool:
    explicit_intent = str(request.context.get("intent") or "").strip().lower()
    return is_explicit_local_agent_intent(explicit_intent) or is_plain_analysis_chat_question(request.question)


def _contains_mutating_action(value: object) -> bool:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return any(token in normalized for token in _MUTATING_ACTION_TOKENS)
    if isinstance(value, dict):
        return any(_contains_mutating_action(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_mutating_action(item) for item in value)
    return False


def _enforce_read_only_agent_request(request: AgentQueryRequest) -> None:
    for key, value in request.context.items():
        if key.strip().lower() in _MUTATING_ACTION_CONTEXT_KEYS and _contains_mutating_action(value):
            raise HTTPException(status_code=403, detail=_READ_ONLY_AGENT_DETAIL)


def _apply_auth_context(
    request: AgentQueryRequest,
    auth: AuthContext,
) -> AgentQueryRequest:
    return request.model_copy(
        update={
            "context": {
                **request.context,
                "user_id": auth.user_id,
                "user_role": auth.role,
                "identity_source": auth.identity_source,
            }
        }
    )


@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
    _enforce_read_only_agent_request(request)
    settings = get_settings()
    if not settings.agent_enabled:
        audit_disabled_agent_query(
            request=request,
            governance_dir=str(settings.governance_path),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=phase1_disabled_response().model_dump(mode="json"),
        )

    try:
        if _should_execute_local_query(request):
            return execute_agent_query(
                request=request,
                duckdb_path=str(settings.duckdb_path),
                governance_dir=str(settings.governance_path),
            )

        provider = _provider_name(settings)
        if provider == "hermes":
            return execute_hermes_agent_query(
                request=request,
                governance_dir=str(settings.governance_path),
                settings=settings,
            )
        if provider == "dexter":
            return execute_dexter_agent_query(
                request=request,
                governance_dir=str(settings.governance_path),
                settings=settings,
            )
        return execute_agent_query(
            request=request,
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/runs", response_model=AgentRunCreateResponse | AgentEnvelope | AgentDisabledResponse)
def create_agent_run_endpoint(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunCreateResponse | AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
    _enforce_read_only_agent_request(request)
    settings = get_settings()
    if not settings.agent_enabled:
        audit_disabled_agent_query(
            request=request,
            governance_dir=str(settings.governance_path),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=phase1_disabled_response().model_dump(mode="json"),
        )
    executor = _run_executor_for_provider(settings)
    if executor is None:
        raise HTTPException(status_code=400, detail="Agent runs require MOSS_AGENT_PROVIDER=hermes or dexter.")

    # CLI-backed providers are more stable as synchronous calls; returning the
    # final envelope lets the frontend use its existing sync-compat path.
    if _provider_transport(settings) == "cli":
        return executor(
            request,
            str(settings.governance_path),
            settings,
        )

    return create_agent_run(
        request=request,
        settings=settings,
        executor=executor,
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunStatusResponse,
    response_model_exclude_none=True,
)
def get_agent_run_endpoint(
    run_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunStatusResponse:
    settings = get_settings()
    try:
        owner = get_agent_run_owner(run_id=run_id, settings=settings)
        if owner is not None and owner != auth.user_id:
            raise HTTPException(status_code=403, detail="Agent run belongs to a different user.")
        return get_agent_run_status(run_id=run_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
