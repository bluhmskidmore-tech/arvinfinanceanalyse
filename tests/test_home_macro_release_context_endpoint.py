from __future__ import annotations

import logging
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.schemas.home_macro_release_context import HomeMacroReleaseContextEnvelope
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

READ_HEADERS = {"X-User-Id": "macro-home-user", "X-User-Role": "viewer"}


def _payload(status: str = "ready") -> dict[str, Any]:
    counts = {name: 0 for name in ("ready", "partial", "stale", "fallback", "source_pending", "error")}
    counts[status] = 1
    return {
        "result_meta": {
            "trace_id": "tr_home_macro_release_context",
            "basis": "analytical",
            "result_kind": "home.macro_release_context",
            "formal_use_allowed": False,
            "source_surface": "market_data",
            "source_version": "sv_test",
            "vendor_version": "vv_test",
            "rule_version": "rv_home_macro_release_context_v1",
            "cache_version": "cv_home_macro_release_context_v1",
            "quality_flag": "warning",
            "vendor_status": "ok",
            "fallback_mode": "none",
        },
        "result": {
            "window_start_date": "2026-07-16",
            "window_end_date": "2026-08-30",
            "history_items": [
                {
                    "indicator_key": "test_indicator",
                    "title": "Test indicator",
                    "region": "CN",
                    "category": "activity",
                    "importance": "high",
                    "source_status": status,
                    "metrics": [
                        {
                            "metric_key": "test_metric",
                            "label": "Test metric",
                            "actual_value": 0.0 if status == "ready" else None,
                            "previous_value": None,
                            "change_value": None,
                            "display_unit": "index",
                            "change_unit": "index_point",
                            "precision": 1,
                            "direction": "unavailable",
                        }
                    ],
                }
            ],
            "coverage": {
                "configured_count": 1,
                "ready_count": counts["ready"],
                "partial_count": counts["partial"],
                "stale_count": counts["stale"],
                "fallback_count": counts["fallback"],
                "source_pending_count": counts["source_pending"],
                "error_count": counts["error"],
            },
        },
    }


def _grant_scope(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "home-macro-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="executive",
        action="read",
    )


def _client(monkeypatch, tmp_path, *, grant_scope: bool, status: str = "ready"):
    module = load_module(
        f"tests._home_macro_endpoint_{uuid.uuid4().hex}",
        "backend/app/api/routes/executive.py",
    )
    calls: list[dict[str, object]] = []

    class _Service:
        def __init__(self, **kwargs: object) -> None:
            calls.append({"constructor": kwargs})

        def build_envelope(self, **kwargs: object) -> HomeMacroReleaseContextEnvelope:
            calls.append({"build": kwargs})
            return HomeMacroReleaseContextEnvelope.model_validate(_payload(status))

    monkeypatch.setattr(module, "HomeMacroReleaseContextService", _Service)
    if grant_scope:
        _grant_scope(tmp_path, monkeypatch)
    else:
        sqlite_path = tmp_path / "home-macro-scope.db"
        monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
        monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
        get_settings.cache_clear()
        load_module(
            "backend.app.repositories.user_scope_repo",
            "backend/app/repositories/user_scope_repo.py",
        ).UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    app = FastAPI()
    app.include_router(module.router)
    return module, TestClient(app), calls


def test_route_is_strictly_typed_and_calls_service_through_perf_wrapper(
    monkeypatch,
    tmp_path,
    caplog,
) -> None:
    _module, client, calls = _client(monkeypatch, tmp_path, grant_scope=True)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get(
            "/ui/home/macro-release-context",
            params={"start_date": "2026-07-16", "end_date": "2026-08-30", "history_limit": 8},
            headers=READ_HEADERS,
        )

    assert response.status_code == 200
    assert calls[-1]["build"] == {
        "window_start_date": __import__("datetime").date(2026, 7, 16),
        "window_end_date": __import__("datetime").date(2026, 8, 30),
        "history_limit": 8,
    }
    route = next(route for route in client.app.routes if route.path == "/ui/home/macro-release-context")
    assert route.response_model is HomeMacroReleaseContextEnvelope
    assert any(
        record.name == "backend.app.api.perf"
        and getattr(record, "endpoint", None) == "/ui/home/macro-release-context"
        for record in caplog.records
    )
    assert response.json()["result_meta"]["basis"] == "analytical"
    assert response.json()["result_meta"]["formal_use_allowed"] is False


def test_route_checks_executive_read_before_constructing_service(monkeypatch, tmp_path) -> None:
    _module, client, calls = _client(monkeypatch, tmp_path, grant_scope=False)

    response = client.get(
        "/ui/home/macro-release-context",
        params={"start_date": "2026-07-16", "end_date": "2026-08-30"},
        headers=READ_HEADERS,
    )

    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "not-a-date", "end_date": "2026-08-30"},
        {"start_date": "2026-07-16", "end_date": "not-a-date"},
        {"start_date": "2026-08-30", "end_date": "2026-07-16"},
        {"start_date": "2026-07-16", "end_date": "2026-08-30", "history_limit": 0},
        {"start_date": "2026-07-16", "end_date": "2026-08-30", "history_limit": 21},
    ],
)
def test_route_rejects_invalid_windows_and_limits(monkeypatch, tmp_path, params) -> None:
    _module, client, _calls = _client(monkeypatch, tmp_path, grant_scope=True)

    response = client.get("/ui/home/macro-release-context", params=params, headers=READ_HEADERS)

    assert response.status_code == 422


@pytest.mark.parametrize("status", ["partial", "stale", "source_pending", "error"])
def test_route_returns_explicit_non_ready_states_as_200(monkeypatch, tmp_path, status) -> None:
    _module, client, _calls = _client(monkeypatch, tmp_path, grant_scope=True, status=status)

    response = client.get(
        "/ui/home/macro-release-context",
        params={"start_date": "2026-07-16", "end_date": "2026-08-30"},
        headers=READ_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["result"]["history_items"][0]["source_status"] == status
