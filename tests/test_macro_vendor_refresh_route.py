from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module


def _build_app():
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    app = FastAPI()
    app.include_router(route_module.router)
    return app, route_module


def test_choice_series_refresh_route_delegates_to_service(monkeypatch):
    app, route_module = _build_app()
    called: dict[str, object] = {}

    monkeypatch.setattr(route_module, "get_settings", lambda: object())
    monkeypatch.setattr(
        route_module,
        "queue_choice_macro_refresh",
        lambda settings, backfill_days: (
            called.update({"settings": settings, "backfill_days": backfill_days})
            or {
                "status": "queued",
                "run_id": "choice_macro_refresh:test-run",
                "job_name": "choice_macro_refresh",
                "trigger_mode": "async",
                "cache_key": "choice_macro.latest",
            }
        ),
    )

    response = TestClient(app).post(
        "/ui/macro/choice-series/refresh",
        params={"backfill_days": 5},
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == "choice_macro_refresh:test-run"
    assert called["backfill_days"] == 5


def test_choice_series_refresh_route_maps_service_error_to_503(monkeypatch):
    app, route_module = _build_app()

    monkeypatch.setattr(route_module, "get_settings", lambda: object())
    monkeypatch.setattr(
        route_module,
        "queue_choice_macro_refresh",
        lambda settings, backfill_days: (_ for _ in ()).throw(
            route_module.ChoiceMacroRefreshServiceError(
                "Choice-macro refresh queue dispatch failed."
            )
        ),
    )

    response = TestClient(app).post("/ui/macro/choice-series/refresh")

    assert response.status_code == 503
    assert response.json() == {"detail": "Choice-macro refresh queue dispatch failed."}


def test_choice_series_refresh_status_route_delegates_to_service(monkeypatch):
    app, route_module = _build_app()
    called: dict[str, object] = {}

    monkeypatch.setattr(route_module, "get_settings", lambda: object())
    monkeypatch.setattr(
        route_module,
        "choice_macro_refresh_status",
        lambda settings, run_id="": (
            called.update({"settings": settings, "run_id": run_id})
            or {
                "status": "queued",
                "run_id": run_id,
                "job_name": "choice_macro_refresh",
                "trigger_mode": "async",
                "cache_key": "choice_macro.latest",
                "error_message": None,
            }
        ),
    )

    response = TestClient(app).get(
        "/ui/macro/choice-series/refresh-status",
        params={"run_id": "choice_macro_refresh:test-run"},
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == "choice_macro_refresh:test-run"
    assert called["run_id"] == "choice_macro_refresh:test-run"
