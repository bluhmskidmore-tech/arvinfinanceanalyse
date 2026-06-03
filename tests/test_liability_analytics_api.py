from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


LIABILITY_ANALYTICS_READ_HEADERS = {"X-User-Id": "liability-read-user", "X-User-Role": "viewer"}

_LIABILITY_ANALYTICS_READ_CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("/api/risk/buckets", {"report_date": "2026-01-31"}),
    ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
    ("/api/analysis/yield-by-period", {"year": "2026", "period_type": "monthly"}),
    ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
    ("/api/liabilities/monthly", {"year": "2026"}),
    ("/ui/liability/business-context", {}),
    ("/api/analysis/liabilities/cockpit-warnings", {"report_date": "2026-01-31"}),
    ("/api/analysis/liabilities/contribution-split", {"report_date": "2026-01-31"}),
)


def _configure_liability_scope_store(tmp_path: Path, monkeypatch, *, grant_read_scope: bool) -> None:
    sqlite_path = tmp_path / "liability-analytics-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    if grant_read_scope:
        UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
            user_id="*",
            role=None,
            resource="liability_analytics",
            action="read",
        )


def _build_client(tmp_path: Path, monkeypatch, *, grant_read_scope: bool = True) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "liability.duckdb"))
    _configure_liability_scope_store(tmp_path, monkeypatch, grant_read_scope=grant_read_scope)
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)
    client.headers.update(LIABILITY_ANALYTICS_READ_HEADERS)
    return client


def test_liability_analytics_read_surfaces_require_explicit_read_scope(tmp_path: Path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch, grant_read_scope=False)

    for path, params in _LIABILITY_ANALYTICS_READ_CASES:
        response = client.get(path, params=params or None)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_liability_analytics_routes_fail_closed_while_surface_remains_reserved(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path, params in (
        ("/api/risk/buckets", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield-by-period", {"year": "2026", "period_type": "monthly"}),
        ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
        ("/api/liabilities/monthly", {"year": "2026"}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        body = response.json()
        assert "result_meta" in body, path
        assert "result" in body, path
        assert body["result_meta"].get("basis") == "analytical", path


def test_liability_analytics_routes_still_validate_invalid_report_date(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path in (
        "/api/risk/buckets",
        "/api/analysis/yield_metrics",
        "/api/analysis/liabilities/counterparty",
    ):
        response = client.get(path, params={"report_date": "2026-99-99"})
        assert response.status_code == 422, path
        assert "invalid report_date" in response.json()["detail"].lower(), path


def test_liability_analytics_monthly_route_still_validates_year_bounds(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/liabilities/monthly", params={"year": "1999"})
    assert response.status_code == 422


def test_yield_by_period_returns_envelope_with_empty_periods_on_empty_db(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/analysis/yield-by-period", params={"year": "2026", "period_type": "monthly"})
    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["result_kind"] == "liability_analytics.yield_by_period"
    assert body["result"]["year"] == 2026
    assert body["result"]["period_type"] == "monthly"
    assert body["result"]["periods"] == []
