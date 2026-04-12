from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.governance.settings import get_settings
from backend.app.services.agent_service import (
    audit_disabled_agent_query,
    execute_agent_query,
    phase1_disabled_response,
)

router = APIRouter(prefix="/api/agent")

@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(request: AgentQueryRequest) -> AgentEnvelope | JSONResponse:
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
        return execute_agent_query(
            request=request,
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
