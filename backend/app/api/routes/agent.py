from fastapi import APIRouter, status

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse
from backend.app.services.agent_service import phase1_disabled_response

router = APIRouter(prefix="/api/agent")


@router.post(
    "/query",
    response_model=AgentDisabledResponse,
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
)
def query_agent(_: AgentQueryRequest) -> AgentDisabledResponse:
    return phase1_disabled_response()

