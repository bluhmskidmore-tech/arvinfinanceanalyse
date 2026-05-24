from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def test_agent_query_is_disabled_without_governed_result_meta(monkeypatch) -> None:
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "false")
    monkeypatch.setenv("MOSS_AGENT_PROVIDER", "local")
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    payload = response.json()
    assert payload["enabled"] is False
    assert "disabled" in payload["detail"].lower()
    assert "result_meta" not in payload
    get_settings.cache_clear()
