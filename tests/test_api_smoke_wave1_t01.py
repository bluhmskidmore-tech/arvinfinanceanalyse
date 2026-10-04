"""Smoke tests for Wave 1 T01 missing API routes."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

@pytest.fixture
def auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    sqlite_path = tmp_path / "smoke-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")

    duckdb_path = tmp_path / "empty-smoke.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))

    # Do not set WALK_FORWARD_REPORT_PATH_ENV so it triggers 404 for strategy_reports

    get_settings.cache_clear()

    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo = repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")

    for resource in ["dashboard", "strategy_reports", "team_performance"]:
        repo.grant_scope(
            user_id="*",
            role=None,
            resource=resource,
            action="read",
        )

    app_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(app_module.app)
    client.headers.update({"X-User-Id": "smoke-test-user", "X-User-Role": "viewer"})

    return client


def test_dashboard_api_smoke(auth_client: TestClient) -> None:
    # 1. core_metrics
    resp_core = auth_client.get("/api/dashboard/core_metrics")
    assert resp_core.status_code == 200
    payload_core = resp_core.json()
    assert "result_meta" in payload_core
    assert "result" in payload_core

    # 2. daily-changes
    resp_daily = auth_client.get("/api/dashboard/daily-changes")
    assert resp_daily.status_code == 200
    payload_daily = resp_daily.json()
    assert "result_meta" in payload_daily
    assert "result" in payload_daily


def test_strategy_reports_api_smoke(auth_client: TestClient) -> None:
    # walk-forward relies on a JSON file, which exists in the workspace
    resp = auth_client.get("/api/strategy-reports/walk-forward")
    assert resp.status_code == 200
    payload = resp.json()
    assert "result_meta" in payload
    assert "result" in payload


def test_team_performance_api_smoke(auth_client: TestClient) -> None:
    # assessment-workbook returns static data, should be 200
    resp = auth_client.get("/api/team-performance/assessment-workbook")
    assert resp.status_code == 200
    payload = resp.json()
    assert "result_meta" in payload
    assert "result" in payload
    assert "centers" in payload["result"]
