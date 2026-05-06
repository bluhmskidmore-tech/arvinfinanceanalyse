"""Verify all mutation routes enforce auth and refresh routes accept identity-only."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _load_app():
    import importlib
    mod = importlib.import_module("backend.app.main")
    return mod.app


def _setup_scope_store(tmp_path, monkeypatch, *, grant: bool):
    """Set up SQLite-backed scope store. If grant=False, no permissions are seeded."""
    from backend.app.governance.settings import get_settings

    sqlite_path = tmp_path / "auth-scope-contract.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()

    from backend.app.repositories.user_scope_repo import UserScopeRepository

    repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    if grant:
        repo.grant_scope(user_id="*", role=None, resource="*", action="*")


MUTATION_ROUTES = [
    ("POST", "/api/kpi/metrics", {"metric_code": "T", "metric_name": "Test", "major_category": "A", "owner_id": 1, "year": 2026, "score_weight": "1.0", "data_source_type": "MANUAL", "scoring_rule_type": "LINEAR"}),
    ("PUT", "/api/kpi/metrics/99999", {"metric_code": "T", "metric_name": "Test", "major_category": "A", "owner_id": 1, "year": 2026, "score_weight": "1.0", "data_source_type": "MANUAL", "scoring_rule_type": "LINEAR"}),
    ("DELETE", "/api/kpi/metrics/99999", None),
    ("POST", "/api/kpi/values", {"metric_id": 99999, "as_of_date": "2026-01-01"}),
    ("PUT", "/api/kpi/values/99999", {}),
    ("POST", "/api/kpi/values/batch", {"as_of_date": "2026-01-01", "items": []}),
    ("POST", "/api/kpi/fetch_and_recalc?owner_id=1&as_of_date=2026-01-01", {"metric_ids": []}),
    ("POST", "/ui/pnl/product-category/manual-adjustments", {"report_date": "2026-01-01", "account_code": "X", "currency": "CNY", "operator": "DELTA", "monthly_pnl": "100"}),
    ("POST", "/ui/pnl/product-category/manual-adjustments/test-id/revoke", None),
    ("POST", "/ui/pnl/product-category/manual-adjustments/test-id/edit", {"report_date": "2026-01-01", "account_code": "X", "currency": "CNY", "operator": "DELTA", "monthly_pnl": "50"}),
    ("POST", "/ui/pnl/product-category/manual-adjustments/test-id/restore", None),
    ("POST", "/ui/qdb-gl-monthly-analysis/manual-adjustments", {"report_month": "202601", "adjustment_class": "mapping_adjustment", "target": {"account_code": "123", "field": "account_name"}, "operator": "OVERRIDE", "value": "manual", "approval_status": "approved"}),
    ("POST", "/ui/qdb-gl-monthly-analysis/manual-adjustments/test-id/edit", {"report_month": "202601", "adjustment_class": "mapping_adjustment", "target": {"account_code": "123", "field": "account_name"}, "operator": "OVERRIDE", "value": "manual", "approval_status": "approved"}),
    ("POST", "/ui/qdb-gl-monthly-analysis/manual-adjustments/test-id/revoke", None),
    ("POST", "/ui/qdb-gl-monthly-analysis/manual-adjustments/test-id/restore", None),
    ("POST", "/ui/news/tushare-npr/ingest", None),
    ("POST", "/api/news/tushare-npr/ingest", None),
    ("POST", "/ui/market-data/livermore/position-snapshot", {"as_of_date": "2026-04-30", "csv_path": "livermore/positions.csv"}),
    ("POST", "/ui/market-data/livermore/position-snapshot/manual", {"as_of_date": "2026-04-30", "positions": [{"stock_code": "000001.SZ", "stock_name": "Alpha", "entry_cost": 10.5, "bars_since_entry": 6}]}),
]

RESERVED_MUTATION_PATHS = {
    "/ui/news/tushare-npr/ingest",
    "/api/news/tushare-npr/ingest",
}


@pytest.mark.parametrize("method,path,body", MUTATION_ROUTES, ids=[f"{m} {p}" for m, p, _ in MUTATION_ROUTES])
def test_mutation_route_returns_403_without_scope_grant(method, path, body, tmp_path, monkeypatch):
    _setup_scope_store(tmp_path, monkeypatch, grant=False)
    client = TestClient(_load_app(), raise_server_exceptions=False)
    headers = {"X-User-Id": "test-no-perms", "X-User-Role": "viewer"}
    if method == "POST":
        response = client.post(path, json=body, headers=headers)
    elif method == "PUT":
        response = client.put(path, json=body, headers=headers)
    elif method == "DELETE":
        response = client.delete(path, headers=headers)
    else:
        raise ValueError(f"Unexpected method: {method}")
    expected_status = 503 if path in RESERVED_MUTATION_PATHS else 403
    assert response.status_code == expected_status, (
        f"Expected {expected_status} for {method} {path}, got {response.status_code}: {response.text}"
    )
    if path in RESERVED_MUTATION_PATHS:
        assert "reserved" in response.text.lower()


REFRESH_ROUTES = [
    ("POST", "/api/data/refresh_pnl", None),
    ("POST", "/ui/pnl/product-category/refresh", None),
    ("POST", "/api/bond-analytics/refresh?report_date=2026-01-01", None),
    ("POST", "/ui/balance-analysis/refresh?report_date=2026-01-01", None),
    ("POST", "/ui/balance-movement-analysis/refresh?report_date=2026-01-01", None),
    ("POST", "/ui/preview/source-foundation/refresh", None),
]


@pytest.mark.parametrize("method,path,body", REFRESH_ROUTES, ids=[f"{m} {p.split('?')[0]}" for m, p, _ in REFRESH_ROUTES])
def test_refresh_route_does_not_require_scope_grant(method, path, body, tmp_path, monkeypatch):
    """Refresh routes should NOT return 403 even without scope grants (identity-only)."""
    _setup_scope_store(tmp_path, monkeypatch, grant=False)
    client = TestClient(_load_app(), raise_server_exceptions=False)
    headers = {"X-User-Id": "test-refresh-user"}
    response = client.post(path, json=body, headers=headers)
    assert response.status_code != 403, f"Refresh route {path} should not require permissions, got 403"
