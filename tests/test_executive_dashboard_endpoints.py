from fastapi.testclient import TestClient

from tests.helpers import load_module


def test_fastapi_application_exposes_executive_dashboard_routes():
    module = load_module("backend.app.main", "backend/app/main.py")
    app = getattr(module, "app", None)

    paths = {route.path for route in app.routes}
    assert "/ui/home/overview" in paths
    assert "/ui/home/summary" in paths
    assert "/ui/pnl/attribution" in paths
    assert "/ui/risk/overview" in paths
    assert "/ui/home/contribution" in paths
    assert "/ui/home/alerts" in paths


def test_executive_dashboard_endpoints_return_result_meta_envelopes():
    module = load_module(
        "backend.app.api.routes.executive",
        "backend/app/api/routes/executive.py",
    )

    for name in (
        "overview",
        "summary",
        "pnl_attribution",
        "risk_overview",
        "contribution",
        "alerts",
    ):
        payload = getattr(module, name)()
        assert "result_meta" in payload
        assert "result" in payload
        assert payload["result_meta"]["result_kind"].startswith("executive.")


def test_executive_dashboard_http_routes_return_200_with_result_envelope():
    main = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main.app)
    paths = [
        "/ui/home/overview",
        "/ui/home/summary",
        "/ui/pnl/attribution",
        "/ui/risk/overview",
        "/ui/home/contribution",
        "/ui/home/alerts",
    ]
    kinds: list[str] = []
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.json()
        assert "result_meta" in body and "result" in body
        meta = body["result_meta"]
        assert meta.get("basis") == "analytical"
        assert meta.get("formal_use_allowed") is False
        assert meta.get("scenario_flag") is False
        kinds.append(str(meta.get("result_kind", "")))
    assert "executive.overview" in kinds
    assert "executive.summary" in kinds
    assert "executive.pnl-attribution" in kinds
    assert "executive.risk-overview" in kinds
    assert "executive.contribution" in kinds
    assert "executive.alerts" in kinds
