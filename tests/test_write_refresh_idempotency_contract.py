"""System contract for write-refresh Idempotency-Key behavior.

The endpoints covered here intentionally keep endpoint-specific target identity
and payload shapes. This suite asserts only the shared write-refresh invariants.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_bond_analytics_api import REPORT_DATE as BOND_REPORT_DATE
from tests.test_bond_analytics_materialize_flow import (
    _seed_bond_snapshot_rows,
    seed_yield_curves_for_bond_analytics_tests,
)
from tests.test_product_category_pnl_flow import _write_month_pair as _write_product_category_month_pair
from tests.test_qdb_gl_monthly_analysis_core import _write_month_pair as _write_qdb_month_pair


Request = dict[str, Any]


@dataclass(frozen=True)
class RefreshEndpointAdapter:
    family: str
    name: str
    path: str
    idempotency_key: str
    same_target: Request
    different_target: Request | None
    setup: Callable[[Path, Any], tuple[TestClient, list[object]]]
    refresh_payload: Callable[[dict[str, Any]], dict[str, Any]]
    side_effect_count: Callable[[list[object]], int] = len


def _post(client: TestClient, adapter: RefreshEndpointAdapter, request: Request, *, key: str | None):
    headers = dict(request.get("headers") or {})
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(
        adapter.path,
        params=request.get("params"),
        json=request.get("json"),
        headers=headers,
    )


def _top_level_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _macro_choice_stock_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload["result"]["refresh"]


def _assert_different_target_identity(
    adapter: RefreshEndpointAdapter,
    first_refresh: dict[str, Any],
    second_refresh: dict[str, Any],
) -> None:
    request = adapter.different_target or {}
    params = request.get("params") or {}

    if "report_date" in params:
        assert second_refresh["report_date"] == params["report_date"]
        assert first_refresh.get("report_date") != second_refresh["report_date"]

    if "report_month" in params:
        assert second_refresh["status"] == "completed"
        assert second_refresh["report_month"] == params["report_month"]
        assert second_refresh["report_date"] == params["report_month"]
        assert first_refresh.get("report_month") != second_refresh["report_month"]


def _scope_repo(tmp_path: Path, monkeypatch: Any, filename: str) -> UserScopeRepository:
    sqlite_path = tmp_path / filename
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(dsn)


def _main_client() -> TestClient:
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def _setup_product_category(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    data_root = tmp_path / "product-category" / "data_input"
    source_dir = data_root / "pnl_contract_source"
    source_dir.mkdir(parents=True)
    _write_product_category_month_pair(source_dir, "202601", january=True)
    duckdb_path = tmp_path / "product-category" / "moss.duckdb"
    governance_dir = tmp_path / "product-category" / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    repo = _scope_repo(tmp_path, monkeypatch, "product-category-auth.db")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl", action="read")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl", action="refresh")
    get_settings.cache_clear()

    calls: list[object] = []
    service_mod = load_module(
        "backend.app.services.product_category_pnl_service",
        "backend/app/services/product_category_pnl_service.py",
    )
    monkeypatch.setattr(service_mod.materialize_product_category_pnl, "send", lambda **kwargs: calls.append(kwargs))
    return _main_client(), calls


def _setup_source_preview(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    duckdb_path = tmp_path / "source-preview" / "moss.duckdb"
    governance_dir = tmp_path / "source-preview" / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_SOURCE_PREVIEW_HTTP_ENABLED", "1")
    repo = _scope_repo(tmp_path, monkeypatch, "source-preview-auth.db")
    repo.grant_scope(user_id="*", role=None, resource="source_preview.source_foundation", action="read")
    repo.grant_scope(user_id="*", role=None, resource="source_preview.source_foundation", action="refresh")
    get_settings.cache_clear()

    calls: list[object] = []
    service_mod = load_module(
        "backend.app.services.source_preview_refresh_service",
        "backend/app/services/source_preview_refresh_service.py",
    )
    monkeypatch.setattr(service_mod.refresh_source_preview_cache, "send", lambda **kwargs: calls.append(kwargs))
    return _main_client(), calls


def _setup_balance_analysis(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    duckdb_path = tmp_path / "balance-analysis" / "moss.duckdb"
    governance_dir = tmp_path / "balance-analysis" / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    repo = _scope_repo(tmp_path, monkeypatch, "balance-analysis-auth.db")
    repo.grant_scope(user_id="*", role=None, resource="balance_analysis", action="read")
    repo.grant_scope(user_id="*", role=None, resource="balance_analysis", action="refresh")
    get_settings.cache_clear()

    calls: list[object] = []
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    monkeypatch.setattr(service_mod.materialize_balance_analysis_facts, "send", lambda **kwargs: calls.append(kwargs))
    return _main_client(), calls


def _setup_bond_analytics(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    duckdb_path = tmp_path / "bond-analytics" / "moss.duckdb"
    governance_dir = tmp_path / "bond-analytics" / "governance"
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    repo = _scope_repo(tmp_path, monkeypatch, "bond-analytics-auth.db")
    repo.grant_scope(user_id="*", role=None, resource="bond_analytics", action="read")
    repo.grant_scope(user_id="*", role=None, resource="bond_analytics", action="refresh")
    _seed_bond_snapshot_rows(str(duckdb_path))
    seed_yield_curves_for_bond_analytics_tests(str(duckdb_path))
    get_settings.cache_clear()

    calls: list[object] = []
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    monkeypatch.setattr(service_mod, "_prepare_yield_curve_inputs_for_refresh", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(service_mod.materialize_bond_analytics_facts, "send", lambda **kwargs: calls.append(kwargs))
    return _main_client(), calls


def _setup_pnl(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    duckdb_path = tmp_path / "pnl" / "moss.duckdb"
    governance_dir = tmp_path / "pnl" / "governance"
    source_dir = tmp_path / "pnl" / "source"
    source_dir.mkdir(parents=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_PNL_SOURCE_DIR", str(source_dir))
    repo = _scope_repo(tmp_path, monkeypatch, "pnl-auth.db")
    repo.grant_scope(user_id="*", role=None, resource="formal_pnl", action="read")
    repo.grant_scope(user_id="*", role=None, resource="formal_pnl", action="refresh")
    get_settings.cache_clear()

    calls: list[object] = []
    service_mod = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(service_mod.materialize_pnl_facts, "send", lambda **kwargs: calls.append(kwargs))
    return _main_client(), calls


def _setup_qdb_gl(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    source_dir = tmp_path / "qdb-gl" / "data_input" / "pnl_contract_source"
    source_dir.mkdir(parents=True)
    _write_qdb_month_pair(source_dir, "202602")
    _write_qdb_month_pair(source_dir, "202603")
    governance_dir = tmp_path / "qdb-gl" / "governance"
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    repo = _scope_repo(tmp_path, monkeypatch, "qdb-gl-auth.db")
    repo.grant_scope(user_id="*", role=None, resource="qdb_gl_monthly_analysis", action="read")
    repo.grant_scope(user_id="*", role=None, resource="qdb_gl_monthly_analysis", action="refresh")
    get_settings.cache_clear()

    calls: list[object] = []
    service_mod = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    original_rebuild = service_mod._rebuild_workbook_payload

    def counted_rebuild(*args: object, **kwargs: object) -> tuple[object, object, object, object, object]:
        calls.append(kwargs)
        return original_rebuild(*args, **kwargs)

    monkeypatch.setattr(service_mod, "_rebuild_workbook_payload", counted_rebuild)
    return _main_client(), calls


def _setup_macro_choice_stock(tmp_path: Path, monkeypatch: Any) -> tuple[TestClient, list[object]]:
    duckdb_path = tmp_path / "macro-choice-stock" / "moss.duckdb"
    governance_path = tmp_path / "macro-choice-stock" / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    repo = _scope_repo(tmp_path, monkeypatch, "macro-choice-stock-auth.db")
    repo.grant_scope(user_id="stock-refresh-user", role=None, resource="macro_toolkit", action="read")
    repo.grant_scope(
        user_id="stock-refresh-user",
        role=None,
        resource="macro_toolkit.choice_stock",
        action="refresh",
    )
    get_settings.cache_clear()

    calls: list[object] = []
    route_mod = load_module("backend.app.api.routes.macro_toolkit", "backend/app/api/routes/macro_toolkit.py")
    service_mod = route_mod.macro_toolkit_service
    monkeypatch.setattr(
        service_mod,
        "materialize_choice_stock_inputs",
        lambda **kwargs: calls.append(("history", kwargs))
        or {"status": "completed", "row_count": 111, "source_version": "sv_history"},
    )
    monkeypatch.setattr(
        service_mod,
        "materialize_choice_stock_factor_snapshot",
        lambda **kwargs: calls.append(("factor", kwargs))
        or {"status": "completed", "row_count": 222, "source_version": "sv_factor"},
    )

    app = FastAPI()
    app.include_router(route_mod.router)
    return TestClient(app), calls


def _macro_headers() -> dict[str, str]:
    return {"X-User-Id": "stock-refresh-user", "X-User-Role": "viewer"}


ENDPOINTS = (
    RefreshEndpointAdapter(
        family="key-only",
        name="product-category",
        path="/ui/pnl/product-category/refresh",
        idempotency_key=" product-category-refresh-contract ",
        same_target={},
        different_target=None,
        setup=_setup_product_category,
        refresh_payload=_top_level_payload,
    ),
    RefreshEndpointAdapter(
        family="key-only",
        name="source-preview",
        path="/ui/preview/source-foundation/refresh",
        idempotency_key=" source-preview-refresh-contract ",
        same_target={},
        different_target=None,
        setup=_setup_source_preview,
        refresh_payload=_top_level_payload,
    ),
    RefreshEndpointAdapter(
        family="key-date",
        name="balance-analysis",
        path="/ui/balance-analysis/refresh",
        idempotency_key=" balance-analysis-refresh-contract ",
        same_target={"params": {"report_date": "2025-12-31"}},
        different_target={"params": {"report_date": "2025-11-30"}},
        setup=_setup_balance_analysis,
        refresh_payload=_top_level_payload,
    ),
    RefreshEndpointAdapter(
        family="key-date",
        name="bond-analytics",
        path="/api/bond-analytics/refresh",
        idempotency_key=" bond-analytics-refresh-contract ",
        same_target={"params": {"report_date": BOND_REPORT_DATE}},
        different_target={"params": {"report_date": "2026-03-30"}},
        setup=_setup_bond_analytics,
        refresh_payload=_top_level_payload,
        side_effect_count=lambda calls: len(calls) // 2,
    ),
    RefreshEndpointAdapter(
        family="key-date",
        name="pnl",
        path="/api/data/refresh_pnl",
        idempotency_key=" pnl-refresh-contract ",
        same_target={},
        different_target={"params": {"report_date": "2026-02-27"}},
        setup=_setup_pnl,
        refresh_payload=_top_level_payload,
    ),
    RefreshEndpointAdapter(
        family="key-month",
        name="qdb-gl-monthly-analysis",
        path="/ui/qdb-gl-monthly-analysis/refresh",
        idempotency_key=" qdb-gl-refresh-contract ",
        same_target={"params": {"report_month": "202602"}},
        different_target={"params": {"report_month": "202603"}},
        setup=_setup_qdb_gl,
        refresh_payload=_top_level_payload,
    ),
    RefreshEndpointAdapter(
        family="composite",
        name="macro-toolkit-choice-stock",
        path="/ui/macro/toolkit/choice-stock/refresh",
        idempotency_key=" choice-stock-refresh-contract ",
        same_target={
            "json": {
                "as_of_date": "2026-04-30",
                "refresh_history": True,
                "refresh_factors": True,
                "factor_max_stock_count": None,
            },
            "headers": _macro_headers(),
        },
        different_target={
            "json": {
                "as_of_date": "2026-04-29",
                "refresh_history": True,
                "refresh_factors": True,
                "factor_max_stock_count": None,
            },
            "headers": _macro_headers(),
        },
        setup=_setup_macro_choice_stock,
        refresh_payload=_macro_choice_stock_payload,
        side_effect_count=lambda calls: len(calls) // 2,
    ),
)


def _ids(adapter: RefreshEndpointAdapter) -> str:
    return adapter.name


@pytest.mark.parametrize("adapter", ENDPOINTS, ids=_ids)
def test_refresh_idempotency_key_is_optional(adapter: RefreshEndpointAdapter, tmp_path: Path, monkeypatch: Any) -> None:
    client, calls = adapter.setup(tmp_path, monkeypatch)

    try:
        response = _post(client, adapter, adapter.same_target, key=None)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200, response.text
    refresh = adapter.refresh_payload(response.json())
    assert refresh.get("idempotency_replay") in (None, False)
    assert adapter.side_effect_count(calls) == 1


@pytest.mark.parametrize("adapter", ENDPOINTS, ids=_ids)
def test_refresh_replays_same_normalized_idempotency_key(
    adapter: RefreshEndpointAdapter,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    client, calls = adapter.setup(tmp_path, monkeypatch)

    try:
        first_response = _post(client, adapter, adapter.same_target, key=adapter.idempotency_key)
        second_response = _post(client, adapter, adapter.same_target, key=adapter.idempotency_key)
    finally:
        get_settings.cache_clear()

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    first_refresh = adapter.refresh_payload(first_response.json())
    second_refresh = adapter.refresh_payload(second_response.json())
    assert second_refresh["run_id"] == first_refresh["run_id"]
    assert second_refresh["idempotency_key"] == adapter.idempotency_key.strip()
    assert second_refresh["idempotency_replay"] is True
    assert adapter.side_effect_count(calls) == 1


@pytest.mark.parametrize(
    "adapter",
    [adapter for adapter in ENDPOINTS if adapter.different_target is not None],
    ids=_ids,
)
def test_refresh_does_not_replay_same_key_for_different_target(
    adapter: RefreshEndpointAdapter,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    client, calls = adapter.setup(tmp_path, monkeypatch)

    try:
        first_response = _post(client, adapter, adapter.same_target, key=adapter.idempotency_key)
        second_response = _post(client, adapter, adapter.different_target or {}, key=adapter.idempotency_key)
    finally:
        get_settings.cache_clear()

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    first_refresh = adapter.refresh_payload(first_response.json())
    second_refresh = adapter.refresh_payload(second_response.json())
    assert second_refresh["run_id"] != first_refresh["run_id"]
    assert second_refresh["idempotency_replay"] is False
    _assert_different_target_identity(adapter, first_refresh, second_refresh)
    assert adapter.side_effect_count(calls) == 2
