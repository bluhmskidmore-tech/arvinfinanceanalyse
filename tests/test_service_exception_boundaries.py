from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.api.routes import adb_analysis as adb_routes
from backend.app.governance import settings as governance_settings


_ADB_ROUTE_CASES = (
    ("get_adb", "adb_envelope_for_dates"),
    ("adb_comparison", "adb_comparison_envelope"),
    ("adb_insights", "adb_insights_envelope"),
    ("adb_monthly", "adb_monthly_envelope"),
    ("adb_coverage", "adb_coverage_diagnostics"),
    ("adb_backfill", "dispatch_adb_backfill"),
)


class _UnexpectedServiceError(Exception):
    pass


def _call_adb_route(route_name: str) -> object:
    auth = SimpleNamespace(user_id="exception-boundary-test")
    if route_name == "adb_monthly":
        return adb_routes.adb_monthly(auth=auth, year=2026)
    kwargs = {
        "auth": auth,
        "start_date": "2026-01-01",
        "end_date": "2026-01-02",
    }
    if route_name == "adb_comparison":
        kwargs["top_n"] = 20
    return getattr(adb_routes, route_name)(**kwargs)


def _prepare_adb_route(monkeypatch: pytest.MonkeyPatch, service_name: str, exc: BaseException) -> None:
    monkeypatch.setattr(governance_settings, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(adb_routes, "_ensure_adb_analysis_read_allowed", lambda *_args: None)
    monkeypatch.setattr(adb_routes, "ensure_user_allowed", lambda **_kwargs: None)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise exc

    monkeypatch.setattr(adb_routes.adb_analysis_service, service_name, _raise)


@pytest.mark.parametrize(("route_name", "service_name"), _ADB_ROUTE_CASES)
def test_adb_routes_sanitize_unexpected_service_errors(
    monkeypatch: pytest.MonkeyPatch,
    route_name: str,
    service_name: str,
) -> None:
    _prepare_adb_route(
        monkeypatch,
        service_name,
        _UnexpectedServiceError("secret_table at C:\\private\\moss.duckdb"),
    )

    with pytest.raises(HTTPException) as exc_info:
        _call_adb_route(route_name)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {
        "code": "ADB_INTERNAL_ERROR",
        "message": "ADB 分析请求处理失败。",
    }
    assert "secret_table" not in str(exc_info.value.detail)
