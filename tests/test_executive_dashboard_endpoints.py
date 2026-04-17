import uuid

import pytest
from fastapi import HTTPException
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

    for name in ("overview", "summary", "pnl_attribution"):
        payload = getattr(module, name)()
        assert "result_meta" in payload
        assert "result" in payload
        assert payload["result_meta"]["result_kind"].startswith("executive.")

    for name in ("risk_overview", "alerts", "contribution"):
        with pytest.raises(HTTPException) as exc_info:
            getattr(module, name)()
        assert exc_info.value.status_code == 503


def test_executive_dashboard_http_routes_expose_only_landed_executive_surfaces_as_200():
    main = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main.app)
    ok_paths = [
        "/ui/home/overview",
        "/ui/home/summary",
        "/ui/pnl/attribution",
    ]
    kinds: list[str] = []
    for path in ok_paths:
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

    for path in (
        "/ui/risk/overview",
        "/ui/home/alerts",
        "/ui/home/contribution",
    ):
        response = client.get(path)
        assert response.status_code == 503, path


def test_partial_executive_routes_raise_503_when_service_marks_vendor_unavailable(monkeypatch):
    module = _load_executive_routes_module()

    def _vendor_unavailable_payload(result_kind: str) -> dict[str, object]:
        return {
            "result_meta": {
                "result_kind": result_kind,
                "vendor_status": "vendor_unavailable",
            },
            "result": {},
        }

    monkeypatch.setattr(
        module,
        "executive_risk_overview",
        lambda report_date=None: _vendor_unavailable_payload("executive.risk-overview"),
    )
    monkeypatch.setattr(
        module,
        "executive_contribution",
        lambda report_date=None: _vendor_unavailable_payload("executive.contribution"),
    )
    monkeypatch.setattr(
        module,
        "executive_alerts",
        lambda report_date=None: _vendor_unavailable_payload("executive.alerts"),
    )

    for name in ("risk_overview", "contribution", "alerts"):
        with pytest.raises(HTTPException) as exc_info:
            getattr(module, name)()
        assert exc_info.value.status_code == 503


def test_excluded_executive_routes_stay_503_even_when_service_returns_ok(monkeypatch):
    module = _load_executive_routes_module()

    def _ok_payload(result_kind: str) -> dict[str, object]:
        return {
            "result_meta": {
                "result_kind": result_kind,
                "basis": "analytical",
                "formal_use_allowed": False,
                "scenario_flag": False,
                "vendor_status": "ok",
            },
            "result": {},
        }

    monkeypatch.setattr(
        module,
        "executive_risk_overview",
        lambda report_date=None: _ok_payload("executive.risk-overview"),
    )
    monkeypatch.setattr(
        module,
        "executive_contribution",
        lambda report_date=None: _ok_payload("executive.contribution"),
    )
    monkeypatch.setattr(
        module,
        "executive_alerts",
        lambda report_date=None: _ok_payload("executive.alerts"),
    )

    for name in ("risk_overview", "contribution", "alerts"):
        with pytest.raises(HTTPException) as exc_info:
            getattr(module, name)()
        assert exc_info.value.status_code == 503


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

    for name in ("risk_overview", "contribution", "alerts"):
        with pytest.raises(HTTPException) as exc_info:
            getattr(module, name)(report_date="2025-11-20")
        assert exc_info.value.status_code == 503

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
