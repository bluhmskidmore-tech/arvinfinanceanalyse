from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_agent_query_is_reserved_without_governed_result_meta() -> None:
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    payload = response.json()
    assert "reserved" in payload["detail"].lower()
    assert "result_meta" not in payload
