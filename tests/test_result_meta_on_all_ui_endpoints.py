from fastapi.testclient import TestClient

from tests.helpers import load_module


def test_all_ui_placeholder_endpoints_return_result_meta():
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    for path in (
        "/ui/home/overview",
        "/ui/home/summary",
        "/ui/home/contribution",
        "/ui/home/alerts",
        "/ui/pnl/attribution",
        "/ui/risk/overview",
    ):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert "result_meta" in payload
        assert "result" in payload
