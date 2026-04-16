from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.agent_service import (
    audit_disabled_agent_query,
    execute_agent_query,
    phase1_disabled_response,
)

router = APIRouter(prefix="/api/agent")

@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentEnvelope | JSONResponse:
    request = request.model_copy(
        update={
            "context": {
                **request.context,
                "user_id": request.context.get("user_id") or auth.user_id,
                "user_role": request.context.get("user_role") or auth.role,
                "identity_source": request.context.get("identity_source") or auth.identity_source,
            }
        }
    )
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
