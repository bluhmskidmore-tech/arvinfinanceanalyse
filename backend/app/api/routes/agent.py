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
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.agent_run_service import (
    create_agent_run,
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


def _provider_name(settings: object) -> str:
    return str(getattr(settings, "agent_provider", "local")).strip().lower() or "local"


def _run_executor_for_provider(settings: object):
    provider = _provider_name(settings)
    if provider == "hermes":
        return execute_hermes_agent_query
    if provider == "dexter":
        return execute_dexter_agent_query
    return None


def _apply_auth_context(
    request: AgentQueryRequest,
    auth: AuthContext,
) -> AgentQueryRequest:
    return request.model_copy(
        update={
            "context": {
                **request.context,
                "user_id": request.context.get("user_id") or auth.user_id,
                "user_role": request.context.get("user_role") or auth.role,
                "identity_source": request.context.get("identity_source") or auth.identity_source,
            }
        }
    )


@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
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


@router.post("/runs", response_model=AgentRunCreateResponse)
def create_agent_run_endpoint(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunCreateResponse | JSONResponse:
    request = _apply_auth_context(request, auth)
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
def get_agent_run_endpoint(run_id: str) -> AgentRunStatusResponse:
    try:
        return get_agent_run_status(run_id=run_id, settings=get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
