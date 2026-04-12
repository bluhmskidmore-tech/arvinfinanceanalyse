import uuid

from fastapi.testclient import TestClient

from tests.helpers import load_module


def _load_executive_routes_module():
    """Isolated routes module (avoids clobbering ``backend.app.api.routes.executive`` in sys.modules)."""
    return load_module(
        f"tests._exec_routes.executive_{uuid.uuid4().hex}",
        "backend/app/api/routes/executive.py",
    )


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
    module = _load_executive_routes_module()

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


def test_executive_dashboard_routes_forward_report_date_query(monkeypatch):
    module = _load_executive_routes_module()

    calls: list[tuple[str, str | None]] = []

    def _stub(name: str):
        def _inner(report_date: str | None = None):
            calls.append((name, report_date))
            return {"result_meta": {"result_kind": f"executive.{name}"}, "result": {}}

        return _inner

    monkeypatch.setattr(module, "executive_overview", _stub("overview"))
    monkeypatch.setattr(module, "executive_pnl_attribution", _stub("pnl-attribution"))
    monkeypatch.setattr(module, "executive_risk_overview", _stub("risk-overview"))
    monkeypatch.setattr(module, "executive_contribution", _stub("contribution"))
    monkeypatch.setattr(module, "executive_alerts", _stub("alerts"))

    assert module.overview(report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.overview"
    assert module.pnl_attribution(report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.pnl-attribution"
    assert module.risk_overview(report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.risk-overview"
    assert module.contribution(report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.contribution"
    assert module.alerts(report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.alerts"

    assert calls == [
        ("overview", "2025-11-20"),
        ("pnl-attribution", "2025-11-20"),
        ("risk-overview", "2025-11-20"),
        ("contribution", "2025-11-20"),
        ("alerts", "2025-11-20"),
    ]


def test_executive_dashboard_http_routes_reject_invalid_report_date():
    main = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main.app)
    for path in (
        "/ui/home/overview",
        "/ui/pnl/attribution",
        "/ui/risk/overview",
        "/ui/home/contribution",
        "/ui/home/alerts",
    ):
        response = client.get(path, params={"report_date": "2025-99-99"})
        assert response.status_code == 422, path
