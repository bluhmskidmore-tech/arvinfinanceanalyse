import uuid

import logging
import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

EXECUTIVE_READ_HEADERS = {"X-User-Id": "executive-read-user", "X-User-Role": "viewer"}


def _configure_executive_scope_store(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "executive-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    return repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")


def _grant_executive_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> AuthContext:
    _configure_executive_scope_store(tmp_path, monkeypatch).grant_scope(
        user_id=user_id,
        role=None,
        resource="executive",
        action="read",
    )
    return AuthContext(user_id="executive-read-user", role="viewer", identity_source="header")


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


def _load_executive_routes_module():
    """Isolated routes module (avoids clobbering ``backend.app.api.routes.executive`` in sys.modules)."""
    return load_module(
        f"tests._exec_routes.executive_{uuid.uuid4().hex}",
        "backend/app/api/routes/executive.py",
    )


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


def _client_with_stubbed_executive_services(monkeypatch, tmp_path=None, *, grant_read: bool = True):
    module = _load_executive_routes_module()
    monkeypatch.setattr(module, "executive_overview", lambda report_date=None: _ok_payload("executive.overview"))
    monkeypatch.setattr(module, "executive_summary", lambda report_date=None: _ok_payload("executive.summary"))
    monkeypatch.setattr(
        module,
        "executive_pnl_attribution",
        lambda report_date=None: _ok_payload("executive.pnl-attribution"),
    )
    monkeypatch.setattr(module, "home_snapshot_envelope", lambda **_kwargs: _ok_payload("home.snapshot"))
    monkeypatch.setattr(module, "home_research_reports_envelope", lambda **_kwargs: _ok_payload("home.research_reports"))
    monkeypatch.setattr(module, "home_income_trend_envelope", lambda **_kwargs: _ok_payload("home.income_trend"))
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)
    if tmp_path is not None:
        _configure_executive_scope_store(tmp_path, monkeypatch)
    if grant_read:
        if tmp_path is None:
            raise AssertionError("tmp_path is required when granting executive read scope")
        _grant_executive_read_scope(tmp_path, monkeypatch)
        client.headers.update(EXECUTIVE_READ_HEADERS)
    return module, client


def test_home_snapshot_route_logs_api_perf(monkeypatch, tmp_path, caplog):
    _module, client = _client_with_stubbed_executive_services(monkeypatch, tmp_path)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get("/ui/home/snapshot", params={"report_date": "2025-11-20"})

    assert response.status_code == 200
    records = _perf_records(caplog, "/ui/home/snapshot")
    assert records
    record = records[-1]
    assert record.getMessage() == "moss_api_perf"
    assert getattr(record, "duration_ms") >= 0
    assert getattr(record, "result_kind") == "home.snapshot"


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


def test_executive_dashboard_endpoints_return_result_meta_envelopes(monkeypatch, tmp_path):
    module, _client = _client_with_stubbed_executive_services(monkeypatch, tmp_path)
    auth = _grant_executive_read_scope(tmp_path, monkeypatch)

    for name in ("overview", "summary", "pnl_attribution"):
        payload = getattr(module, name)(auth=auth)
        assert "result_meta" in payload
        assert "result" in payload
        assert payload["result_meta"]["result_kind"].startswith("executive.")

    for name in ("risk_overview", "alerts", "contribution"):
        with pytest.raises(HTTPException) as exc_info:
            getattr(module, name)(auth=auth)
        assert exc_info.value.status_code == 503


def test_executive_overview_read_surface_requires_explicit_read_scope(tmp_path, monkeypatch) -> None:
    _module, client = _client_with_stubbed_executive_services(monkeypatch, tmp_path, grant_read=False)

    response = client.get("/ui/home/overview", headers=EXECUTIVE_READ_HEADERS)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path,params",
    [
        ("/ui/risk/overview", {}),
        ("/ui/home/contribution", {}),
        ("/ui/home/alerts", {}),
        ("/ui/home/snapshot", {"report_date": "2025-11-20"}),
        ("/ui/home/research-reports", {"report_date": "2025-11-20"}),
        ("/ui/home/income-trend", {"report_date": "2025-11-20"}),
    ],
)
def test_executive_remaining_read_surfaces_require_explicit_read_scope(
    path, params, tmp_path, monkeypatch
) -> None:
    _module, client = _client_with_stubbed_executive_services(monkeypatch, tmp_path, grant_read=False)

    response = client.get(path, params=params or None, headers=EXECUTIVE_READ_HEADERS)

    assert response.status_code == 403


def test_executive_dashboard_http_routes_expose_only_landed_executive_surfaces_as_200(monkeypatch, tmp_path):
    _module, client = _client_with_stubbed_executive_services(monkeypatch, tmp_path)
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
    auth = AuthContext(user_id="executive-read-user", role="viewer", identity_source="header")
    monkeypatch.setattr(module, "_ensure_executive_read_allowed", lambda _auth: None)

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
            getattr(module, name)(auth=auth)
        assert exc_info.value.status_code == 503


def test_excluded_executive_routes_stay_503_even_when_service_returns_ok(monkeypatch):
    module = _load_executive_routes_module()
    auth = AuthContext(user_id="executive-read-user", role="viewer", identity_source="header")
    monkeypatch.setattr(module, "_ensure_executive_read_allowed", lambda _auth: None)

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
            getattr(module, name)(auth=auth)
        assert exc_info.value.status_code == 503


def test_executive_dashboard_routes_forward_report_date_query(monkeypatch, tmp_path):
    module = _load_executive_routes_module()
    auth = _grant_executive_read_scope(tmp_path, monkeypatch)

    calls: list[tuple[str, str | None]] = []

    def _stub(name: str):
        def _inner(report_date: str | None = None):
            calls.append((name, report_date))
            return {"result_meta": {"result_kind": f"executive.{name}"}, "result": {}}

        return _inner

    monkeypatch.setattr(module, "executive_overview", _stub("overview"))
    monkeypatch.setattr(module, "executive_summary", _stub("summary"))
    monkeypatch.setattr(module, "executive_pnl_attribution", _stub("pnl-attribution"))
    monkeypatch.setattr(module, "executive_risk_overview", _stub("risk-overview"))
    monkeypatch.setattr(module, "executive_contribution", _stub("contribution"))
    monkeypatch.setattr(module, "executive_alerts", _stub("alerts"))

    assert module.overview(auth=auth, report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.overview"
    assert module.summary(auth=auth, report_date="2025-11-20")["result_meta"]["result_kind"] == "executive.summary"
    assert (
        module.pnl_attribution(auth=auth, report_date="2025-11-20")["result_meta"]["result_kind"]
        == "executive.pnl-attribution"
    )

    for name in ("risk_overview", "contribution", "alerts"):
        with pytest.raises(HTTPException) as exc_info:
            getattr(module, name)(auth=auth, report_date="2025-11-20")
        assert exc_info.value.status_code == 503

    assert calls == [
        ("overview", "2025-11-20"),
        ("summary", "2025-11-20"),
        ("pnl-attribution", "2025-11-20"),
    ]


def test_executive_dashboard_http_routes_reject_invalid_report_date(tmp_path, monkeypatch):
    _grant_executive_read_scope(tmp_path, monkeypatch)
    main = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main.app)
    for path in (
        "/ui/home/overview",
        "/ui/home/summary",
        "/ui/pnl/attribution",
    ):
        response = client.get(path, params={"report_date": "2025-99-99"}, headers=EXECUTIVE_READ_HEADERS)
        assert response.status_code == 422, path

    response = client.get("/ui/home/snapshot", params={"report_date": "2025-99-99"})
    assert response.status_code == 422, "/ui/home/snapshot"

    for path in (
        "/ui/risk/overview",
        "/ui/home/contribution",
        "/ui/home/alerts",
    ):
        response = client.get(path, params={"report_date": "2025-99-99"})
        assert response.status_code == 503, path
        assert "reserved" in response.text.lower()
