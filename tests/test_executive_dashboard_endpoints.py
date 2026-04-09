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
