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


def _raise_agent_reserved_surface() -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Agent surface is reserved by the current boundary and is not available in this wave.",
    )

@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentEnvelope | JSONResponse:
    _raise_agent_reserved_surface()
