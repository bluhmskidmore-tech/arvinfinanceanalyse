from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def test_agent_query_is_not_published_without_governed_result_meta(monkeypatch) -> None:
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "false")
    monkeypatch.setenv("MOSS_AGENT_PROVIDER", "local")
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 404
    get_settings.cache_clear()
