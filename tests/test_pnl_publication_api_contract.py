from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.security.auth_context import AuthContext
from tests.helpers import load_module


@pytest.fixture
def route_context(monkeypatch):
    route = load_module(
        f"tests._pnl_routes.publication_{id(monkeypatch)}",
        "backend/app/api/routes/pnl.py",
    )
    settings = SimpleNamespace(
        financial_publication_enabled=True,
        duckdb_path="unused-active.duckdb",
        governance_path="unused-governance",
    )
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    permissions = {"read": True, "write": False}

    def authorize(*, auth, settings, resource, action):
        if not permissions[action]:
            raise PermissionError("test permission denied")

    monkeypatch.setattr(route, "ensure_user_allowed", authorize)
    app = FastAPI()
    app.dependency_overrides[route.get_auth_context] = lambda: AuthContext(
        user_id="publication-reader", role="viewer", identity_source="header"
    )
    app.include_router(route.router)
    return route, settings, permissions, TestClient(app)


def test_page_prepare_permissions_and_exact_scope(route_context, monkeypatch):
    route, settings, permissions, client = route_context
    calls = []

    class Service:
        PnlByBusinessPrecomputeConflictError = type("Conflict", (RuntimeError,), {})
        PnlByBusinessPrecomputeDispatchError = type("Dispatch", (RuntimeError,), {})

        @staticmethod
        def pnl_by_business_precompute_status(_settings, **kwargs):
            return {"readiness": "pending", "generation": None, **kwargs}

        @staticmethod
        def request_pnl_by_business_page_rebuild(_settings, **kwargs):
            assert _settings is settings
            calls.append(kwargs)
            return {"readiness": "pending", "generation": None, **kwargs}

    monkeypatch.setattr(route, "_pnl_service", lambda: Service)
    params = {"year": 2026, "as_of_date": "2026-03-31"}
    status = client.get("/api/pnl/by-business/precompute-status", params=params)
    assert status.status_code == 200
    assert status.json()["permissions"]["can_rebuild"] is False
    page_params = {**params, "include_page_dependencies": True}
    assert client.post("/api/pnl/by-business/precompute-rebuild", params=page_params).status_code == 403
    assert calls == []

    permissions["write"] = True
    prepared = client.post("/api/pnl/by-business/precompute-rebuild", params=page_params)
    assert prepared.status_code == 200
    assert prepared.json()["permissions"] == {"can_rebuild": True, "reason": None}
    assert calls == [params]
    for invalid in (
        {"year": 2026, "include_page_dependencies": True},
        {**page_params, "scope": "all_available"},
    ):
        assert client.post("/api/pnl/by-business/precompute-rebuild", params=invalid).status_code == 422
    assert calls == [params]


def test_published_insights_pins_generation_without_legacy_fallback(route_context, monkeypatch):
    route, settings, _permissions, client = route_context
    reads = []

    class GenerationConflict(RuntimeError):
        pass

    def published(_settings, **kwargs):
        assert _settings is settings
        reads.append(kwargs)
        if kwargs["generation"] == "revoked":
            raise GenerationConflict("Requested generation has been revoked")
        if kwargs["generation"] == "io-error":
            raise RuntimeError("Published result could not be read")
        return {"result_meta": {}, "result": {"generation": kwargs["generation"]}}

    def resolve(name):
        assert name == "backend.app.services.pnl_by_business_publication_service"
        return SimpleNamespace(
            read_published_pnl_by_business_insights=published,
            PnlPublishedGenerationConflictError=GenerationConflict,
        )

    monkeypatch.setattr(route, "import_module", resolve)
    params = {"year": 2026, "as_of_date": "2026-03-31", "generation": "sealed-001"}
    result = client.get("/api/pnl/by-business-insights", params=params)
    assert result.status_code == 200
    assert result.json()["result"]["generation"] == "sealed-001"
    assert reads == [params]
    revoked = client.get("/api/pnl/by-business-insights", params={**params, "generation": "revoked"})
    assert revoked.status_code == 409
    assert "revoked" in revoked.json()["detail"]
    assert len(reads) == 2
    io_error = client.get("/api/pnl/by-business-insights", params={**params, "generation": "io-error"})
    assert io_error.status_code == 503
    assert len(reads) == 3

    settings.financial_publication_enabled = False
    disabled = client.get("/api/pnl/by-business-insights", params=params)
    assert disabled.status_code == 409
    assert len(reads) == 3


def test_read_permission_checked_before_publication_lookup(route_context, monkeypatch):
    route, _settings, permissions, client = route_context
    permissions["read"] = False

    def forbidden_lookup(_name):
        pytest.fail("Publication service was loaded before read authorization")

    monkeypatch.setattr(route, "import_module", forbidden_lookup)
    result = client.get(
        "/api/pnl/by-business-insights",
        params={"year": 2026, "as_of_date": "2026-03-31", "generation": "sealed-001"},
    )
    assert result.status_code == 403


def test_page_dates_catalog_uses_committed_receipts_without_active_database(
    route_context, tmp_path, monkeypatch
):
    from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
    from backend.app.services.pnl_task_dispatch import CACHE_KEY

    route, settings, _permissions, client = route_context
    settings.duckdb_path = str(tmp_path / "does-not-exist-active.duckdb")
    settings.governance_path = str(tmp_path / "governance")
    settings.financial_publication_root = str(tmp_path / "publication")
    repository = GovernanceRepository(base_dir=settings.governance_path)
    for run_id, report_date, status in (
        ("ready-source", "2026-03-31", "completed"),
        ("failed-source", "2026-04-30", "failed"),
        ("replaced-state", "2026-05-31", "completed"),
        ("replaced-state", "2026-05-31", "failed"),
    ):
        repository.append(CACHE_BUILD_RUN_STREAM, {
            "run_id": run_id, "report_date": report_date, "status": status,
            "job_name": "pnl_materialize", "cache_key": CACHE_KEY,
            "source_version": "synthetic-source-v1", "rule_version": "synthetic-rule-v1",
        })
    response = client.get("/api/pnl/dates", params={"page": "by_business_insights"})
    assert response.status_code == 200
    assert response.json()["result"]["report_dates"] == ["2026-03-31"]
    assert response.json()["result_meta"]["formal_use_allowed"] is False
    assert response.json()["result_meta"]["filters_applied"]["page_readiness_required"] is True
    assert not (tmp_path / "does-not-exist-active.duckdb").exists()

    legacy_calls = []

    def legacy_dates(**kwargs):
        legacy_calls.append(kwargs)
        return {"result_meta": {}, "result": {"report_dates": ["2020-01-31"]}}

    monkeypatch.setattr(route, "_pnl_service", lambda: SimpleNamespace(pnl_dates_envelope=legacy_dates))
    legacy = client.get("/api/pnl/dates")
    assert legacy.status_code == 200
    assert legacy.json()["result"]["report_dates"] == ["2020-01-31"]
    assert len(legacy_calls) == 1
