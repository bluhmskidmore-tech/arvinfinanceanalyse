"""Verify write-route auth contracts, including scoped refresh exceptions."""
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
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    get_settings.cache_clear()

    from backend.app.repositories.user_scope_repo import UserScopeRepository

    repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    if grant:
        repo.grant_scope(user_id="*", role=None, resource="*", action="*")
    return sqlite_path


MUTATION_ROUTES = [
    ("POST", "/api/kpi/metrics", {"metric_code": "T", "metric_name": "Test", "major_category": "A", "owner_id": 1, "year": 2026, "score_weight": "1.0", "data_source_type": "MANUAL", "scoring_rule_type": "LINEAR"}),
    ("PUT", "/api/kpi/metrics/99999", {"metric_code": "T", "metric_name": "Test", "major_category": "A", "owner_id": 1, "year": 2026, "score_weight": "1.0", "data_source_type": "MANUAL", "scoring_rule_type": "LINEAR"}),
    ("DELETE", "/api/kpi/metrics/99999", None),
    ("POST", "/api/kpi/values", {"metric_id": 99999, "as_of_date": "2026-01-01"}),
    ("PUT", "/api/kpi/values/99999", {}),
    ("POST", "/api/kpi/values/batch", {"as_of_date": "2026-01-01", "items": []}),
    ("POST", "/api/kpi/fetch_and_recalc?owner_id=1&as_of_date=2026-01-01", {"metric_ids": []}),
    (
        "POST",
        "/api/pnl/by-business/manual-adjustments",
        {
            "report_date": "2026-01-01",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "100",
        },
    ),
    (
        "POST",
        "/api/pnl/by-business/manual-adjustments/test-id/edit",
        {
            "report_date": "2026-01-01",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "50",
        },
    ),
    ("POST", "/api/pnl/by-business/manual-adjustments/test-id/revoke", None),
    ("POST", "/api/pnl/by-business/manual-adjustments/test-id/restore", None),
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
    ("POST", "/ui/macro/toolkit/cffex-member-rank/refresh", {"trade_date": "2026-04-10", "contracts": ["T.CFE"], "sources": ["choice"]}),
    ("POST", "/ui/macro/toolkit/scripts/debug_wind/run", {"timeout_seconds": 30}),
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


def _patch_formal_pnl_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.pnl as route_module

    class FakePnlService:
        PnlRefreshConflictError = type("PnlRefreshConflictError", (Exception,), {})

        def refresh_pnl(self, _settings, *, report_date=None):
            calls.append("called")
            return {"status": "queued", "run_id": "formal-pnl-refresh-test", "report_date": report_date}

    monkeypatch.setattr(route_module, "_pnl_service", lambda: FakePnlService())
    return "formal-pnl-refresh-test"


def _patch_bond_analytics_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.bond_analytics as route_module

    def fake_refresh(_settings, *, report_date: str):
        calls.append("called")
        return {"status": "queued", "run_id": "bond-analytics-refresh-test", "report_date": report_date}

    monkeypatch.setattr(route_module, "refresh_bond_analytics", fake_refresh)
    return "bond-analytics-refresh-test"


def _patch_balance_analysis_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.balance_analysis as route_module

    def fake_refresh(_settings, *, report_date: str):
        calls.append("called")
        return {"status": "queued", "run_id": "balance-analysis-refresh-test", "report_date": report_date}

    monkeypatch.setattr(route_module, "refresh_balance_analysis", fake_refresh)
    return "balance-analysis-refresh-test"


def _patch_accounting_asset_movement_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.accounting_asset_movement as route_module

    def fake_refresh(_settings, *, report_date: str, currency_basis: str):
        calls.append("called")
        return {
            "status": "queued",
            "run_id": "accounting-asset-movement-refresh-test",
            "report_date": report_date,
            "currency_basis": currency_basis,
        }

    monkeypatch.setattr(route_module, "refresh_accounting_asset_movement", fake_refresh)
    return "accounting-asset-movement-refresh-test"


def _patch_source_preview_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.source_preview as route_module

    monkeypatch.setenv("MOSS_SOURCE_PREVIEW_HTTP_ENABLED", "1")

    def fake_refresh(_settings):
        calls.append("called")
        return {"status": "queued", "run_id": "source-preview-refresh-test"}

    monkeypatch.setattr(route_module, "refresh_source_preview", fake_refresh)
    return "source-preview-refresh-test"


def _patch_choice_stock_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.macro_toolkit as route_module
    from backend.app.services import macro_toolkit_service

    def fake_refresh(**_kwargs):
        calls.append("called")
        return macro_toolkit_service.MacroToolkitActionResult(
            payload={"status": "queued", "run_id": "choice-stock-refresh-test"},
            quality_flag="ok",
            fallback_mode="none",
            as_of_date="2026-04-30",
        )

    monkeypatch.setattr(macro_toolkit_service, "queue_choice_stock_refresh", fake_refresh)
    monkeypatch.setattr(route_module, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {"status": "queued"})
    return "choice-stock-refresh-test"


def _patch_product_category_refresh(monkeypatch, calls: list[str]) -> str:
    import backend.app.api.routes.product_category_pnl as route_module

    def fake_refresh(_settings):
        calls.append("called")
        return {"status": "queued", "run_id": "product-category-refresh-test"}

    monkeypatch.setattr(route_module, "refresh_product_category_pnl", fake_refresh)
    return "product-category-refresh-test"


SCOPED_REFRESH_ROUTES = [
    ("/api/data/refresh_pnl", None, "formal_pnl", _patch_formal_pnl_refresh),
    ("/api/bond-analytics/refresh?report_date=2026-01-01", None, "bond_analytics", _patch_bond_analytics_refresh),
    ("/ui/balance-analysis/refresh?report_date=2026-01-01", None, "balance_analysis", _patch_balance_analysis_refresh),
    (
        "/ui/balance-movement-analysis/refresh?report_date=2026-01-01",
        None,
        "accounting_asset_movement",
        _patch_accounting_asset_movement_refresh,
    ),
    ("/ui/preview/source-foundation/refresh", None, "source_preview.source_foundation", _patch_source_preview_refresh),
    (
        "/ui/macro/toolkit/choice-stock/refresh",
        {"as_of_date": "2026-04-30", "refresh_history": True, "refresh_factors": False},
        "macro_toolkit.choice_stock",
        _patch_choice_stock_refresh,
    ),
    ("/ui/pnl/product-category/refresh", None, "product_category_pnl", _patch_product_category_refresh),
]


@pytest.mark.parametrize(
    "path,body,resource,patch_refresh",
    SCOPED_REFRESH_ROUTES,
    ids=[path.split("?")[0] for path, _, _, _ in SCOPED_REFRESH_ROUTES],
)
def test_refresh_route_requires_explicit_scope_grant(path, body, resource, patch_refresh, tmp_path, monkeypatch):
    sqlite_path = _setup_scope_store(tmp_path, monkeypatch, grant=False)

    from backend.app.repositories.user_scope_repo import UserScopeRepository

    calls: list[str] = []
    expected_run_id = patch_refresh(monkeypatch, calls)
    client = TestClient(_load_app(), raise_server_exceptions=False)

    denied = client.post(
        path,
        json=body,
        headers={"X-User-Id": "refresh-user"},
    )
    assert denied.status_code == 403, denied.text
    assert calls == []

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="refresh-user",
        role=None,
        resource=resource,
        action="refresh",
    )
    allowed = client.post(
        path,
        json=body,
        headers={"X-User-Id": "refresh-user"},
    )
    assert allowed.status_code == 200, allowed.text
    assert expected_run_id in allowed.text
    assert calls == ["called"]


def test_product_category_refresh_returns_503_when_scope_store_unavailable(tmp_path, monkeypatch):
    _setup_scope_store(tmp_path, monkeypatch, grant=False)

    from backend.app.repositories.user_scope_repo import UserScopeRepository

    calls: list[str] = []
    _patch_product_category_refresh(monkeypatch, calls)
    monkeypatch.setattr(
        UserScopeRepository,
        "has_permission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("scope store down")),
    )
    client = TestClient(_load_app(), raise_server_exceptions=False)

    response = client.post(
        "/ui/pnl/product-category/refresh",
        headers={"X-User-Id": "product-category-user"},
    )

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "User scope store is unavailable."
    assert calls == []


def test_macro_choice_series_refresh_requires_explicit_refresh_grant(tmp_path, monkeypatch):
    sqlite_path = _setup_scope_store(tmp_path, monkeypatch, grant=False)

    from backend.app.repositories.user_scope_repo import UserScopeRepository
    import backend.app.api.routes.macro_vendor as route_module

    calls: list[int] = []

    def fake_choice_refresh(*, backfill_days: int):
        calls.append(backfill_days)
        return {"status": "completed", "warnings": []}

    monkeypatch.setattr(route_module.refresh_choice_macro_snapshot, "fn", fake_choice_refresh, raising=False)
    monkeypatch.setattr(
        route_module,
        "_run_public_cross_asset_headline_refresh",
        lambda: {"status": "completed", "warnings": []},
    )
    client = TestClient(_load_app(), raise_server_exceptions=False)

    denied = client.post(
        "/ui/macro/choice-series/refresh?backfill_days=2",
        headers={"X-User-Id": "macro-user"},
    )
    assert denied.status_code == 403
    assert calls == []

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="macro-user",
        role=None,
        resource="macro_vendor.choice_series",
        action="refresh",
    )
    allowed = client.post(
        "/ui/macro/choice-series/refresh?backfill_days=2",
        headers={"X-User-Id": "macro-user"},
    )
    assert allowed.status_code == 200, allowed.text
    assert calls == [2]


def test_macro_toolkit_script_run_requires_matching_scope_grant(tmp_path, monkeypatch):
    sqlite_path = _setup_scope_store(tmp_path, monkeypatch, grant=False)

    from backend.app.repositories.user_scope_repo import UserScopeRepository
    from backend.app.services import macro_toolkit_service

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="script-user",
        role=None,
        resource="macro_toolkit.script",
        action="execute",
        scope_key="script",
        scope_value="debug_wind",
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "run_macro_toolkit_script",
        lambda **_kwargs: {"status": "completed", "exit_code": 0, "stdout": "", "stderr": "", "output_files": []},
    )
    client = TestClient(_load_app(), raise_server_exceptions=False)

    allowed = client.post(
        "/ui/macro/toolkit/scripts/debug_wind/run",
        json={"timeout_seconds": 30},
        headers={"X-User-Id": "script-user"},
    )
    denied = client.post(
        "/ui/macro/toolkit/scripts/signal-aggregator/run",
        json={"timeout_seconds": 30},
        headers={"X-User-Id": "script-user"},
    )

    assert allowed.status_code == 200, allowed.text
    assert denied.status_code == 403, denied.text


def test_macro_toolkit_script_run_rejects_argv_even_with_matching_scope_grant(tmp_path, monkeypatch):
    sqlite_path = _setup_scope_store(tmp_path, monkeypatch, grant=False)

    from backend.app.repositories.user_scope_repo import UserScopeRepository
    from backend.app.services import macro_toolkit_service

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="script-user",
        role=None,
        resource="macro_toolkit.script",
        action="execute",
        scope_key="script",
        scope_value="debug_wind",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        macro_toolkit_service,
        "run_macro_toolkit_script",
        lambda **kwargs: calls.append(kwargs)
        or {"status": "completed", "exit_code": 0, "stdout": "", "stderr": "", "output_files": []},
    )
    client = TestClient(_load_app(), raise_server_exceptions=False)

    response = client.post(
        "/ui/macro/toolkit/scripts/debug_wind/run",
        json={"argv": ["--output", "tmp/out.json"], "timeout_seconds": 30},
        headers={"X-User-Id": "script-user"},
    )

    assert response.status_code == 400, response.text
    assert "arguments" in response.text
    assert calls == []


def test_macro_toolkit_cffex_refresh_accepts_explicit_refresh_grant(tmp_path, monkeypatch):
    sqlite_path = _setup_scope_store(tmp_path, monkeypatch, grant=False)

    from backend.app.repositories.user_scope_repo import UserScopeRepository
    import backend.app.api.routes.macro_toolkit as route_module
    from backend.app.services import macro_toolkit_service

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="cffex-user",
        role=None,
        resource="macro_toolkit.cffex_member_rank",
        action="refresh",
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "refresh_cffex_member_rank",
        lambda **_kwargs: macro_toolkit_service.MacroToolkitActionResult(
            payload={"trade_date": "2026-04-10", "row_count": 2},
            quality_flag="ok",
            fallback_mode="none",
            as_of_date="2026-04-10",
        ),
    )
    monkeypatch.setattr(
        route_module,
        "_cffex_member_rank_status",
        lambda *_args, **_kwargs: {"status": "ok", "latest_trade_date": "2026-04-10"},
    )
    client = TestClient(_load_app(), raise_server_exceptions=False)

    response = client.post(
        "/ui/macro/toolkit/cffex-member-rank/refresh",
        json={"trade_date": "2026-04-10", "contracts": ["T.CFE"], "sources": ["choice"]},
        headers={"X-User-Id": "cffex-user"},
    )

    assert response.status_code == 200, response.text
