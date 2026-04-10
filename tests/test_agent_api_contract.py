from fastapi.testclient import TestClient

from backend.app.main import app
from tests.helpers import load_module


def test_agent_request_schema_defines_phase1_contract():
    module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    request_model = getattr(module, "AgentQueryRequest", None)
    assert request_model is not None

    fields = set(request_model.model_fields)
    assert {
        "question",
        "basis",
        "filters",
        "position_scope",
        "currency_basis",
        "context",
    } <= fields


def test_agent_response_schema_exposes_target_state_and_disabled_contracts():
    module = load_module(
        "backend.app.agent.schemas.agent_response",
        "backend/app/agent/schemas/agent_response.py",
    )
    assert getattr(module, "AgentEnvelope", None) is not None
    assert getattr(module, "AgentResultMeta", None) is not None
    disabled = getattr(module, "AgentDisabledResponse", None)
    assert disabled is not None
    assert {"enabled", "phase", "detail"} <= set(disabled.model_fields)


def test_agent_query_endpoint_is_registered_but_disabled_in_phase1():
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "月均市值怎么查"})

    assert response.status_code == 503
    assert response.json() == {
        "enabled": False,
        "phase": "phase1",
        "detail": "Agent endpoint is planned but disabled in Phase 1.",
    }

