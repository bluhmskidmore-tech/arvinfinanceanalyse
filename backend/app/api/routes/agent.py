from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.governance.agent_audit import AgentAuditPayload, append_agent_audit
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.agent_service import execute_agent_query, phase1_disabled_response

router = APIRouter(prefix="/api/agent")


@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(request: AgentQueryRequest) -> AgentEnvelope | JSONResponse:
    settings = get_settings()
    if not settings.agent_enabled:
        disabled = phase1_disabled_response()
        append_agent_audit(
            GovernanceRepository(base_dir=settings.governance_path),
            AgentAuditPayload(
                user_id=str(request.context.get("user_id") or "agent_user"),
                query_text=request.question,
                tools_used=["agent_disabled"],
                tables_used=[],
                filters_applied={},
                trace_id="tr_agent_disabled",
                result_meta={
                    "result_kind": "agent.disabled",
                    "phase": disabled.phase,
                    "enabled": disabled.enabled,
                },
            ),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=disabled.model_dump(mode="json"),
        )

    return execute_agent_query(
        request=request,
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
    )

