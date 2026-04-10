from fastapi.testclient import TestClient

from backend.app.main import app


def test_all_ui_placeholder_endpoints_return_result_meta():
    client = TestClient(app)
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
