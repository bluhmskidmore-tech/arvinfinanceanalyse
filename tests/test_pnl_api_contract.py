from __future__ import annotations

import json
import logging
import sys
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.pnl import PnlByBusinessYtdPayload
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import ROOT, load_module

PNL_READ_HEADERS = {"X-User-Id": "pnl-read-user", "X-User-Role": "viewer"}


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


def _force_pnl_ytd_refresh_bundle_contract(monkeypatch) -> None:
    """契约测试用 FakeRefreshInput 时关闭 formal 优先，避免与已物化的 DuckDB 行混用。"""
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "false")
    get_settings.cache_clear()


def _setup_route_scope_store(tmp_path, monkeypatch) -> UserScopeRepository:
    sqlite_path = tmp_path / "auth-scope-contract.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")


def _grant_pnl_read_scope(repo: UserScopeRepository, *, user_id: str = "*") -> None:
    repo.grant_scope(
        user_id=user_id,
        role=None,
        resource="pnl",
        action="read",
    )


def _exact_cutoff_pnl_repository(_path):
    return SimpleNamespace(
        max_formal_or_nonstd_report_date_in_year=lambda **kwargs: kwargs["as_of_cap"]
    )


def _grant_liability_analytics_read_scope(repo: UserScopeRepository, *, user_id: str = "*") -> None:
    repo.grant_scope(
        user_id=user_id,
        role=None,
        resource="liability_analytics",
        action="read",
    )


@pytest.fixture(autouse=True)
def seed_pnl_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "pnl-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    _grant_pnl_read_scope(UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}"))
    yield
    get_settings.cache_clear()


def test_fastapi_application_registers_pnl_routes():
    from backend.app.main import app

    paths = {route.path for route in app.routes}

    assert "/api/pnl/dates" in paths
    assert "/api/pnl/data" in paths
    assert "/api/pnl/bridge" in paths
    assert "/api/pnl/overview" in paths
    assert "/api/pnl/v1-data" in paths
    assert "/api/pnl/by-business" in paths
    assert "/api/pnl/by-business-ytd" in paths
    assert "/api/pnl/by-business-monthly" in paths
    assert "/api/pnl/by-business-analysis" in paths
    assert "/api/pnl/by-business/precompute-status" in paths
    assert "/api/pnl/by-business/precompute-rebuild" in paths
    assert "/api/pnl/by-business/manual-adjustments" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/edit" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/approve" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/revoke" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/restore" in paths
    assert "/api/pnl/yearly-summary" in paths
    assert "/api/data/refresh_pnl" in paths
    assert "/api/data/import_status/pnl" in paths


def test_pnl_formal_read_routes_declare_result_envelope_response_model():
    from fastapi.routing import APIRoute

    route_module = load_module("backend.app.api.routes.pnl", "backend/app/api/routes/pnl.py")
    from backend.app.schemas.result_meta import ResultEnvelope

    routes = {
        route.path: route
        for route in route_module.router.routes
        if isinstance(route, APIRoute) and "GET" in route.methods
    }

    expected_paths = {
        "/api/pnl/dates",
        "/api/pnl/data",
        "/api/pnl/bridge",
        "/api/pnl/overview",
        "/api/pnl/v1-data",
        "/api/pnl/by-business",
        "/api/pnl/by-business-ytd",
        "/api/pnl/by-business-monthly",
        "/api/pnl/by-business-analysis",
        "/api/pnl/yearly-summary",
    }

    missing_model = [
        path
        for path in sorted(expected_paths)
        if routes[path].response_model is not ResultEnvelope
    ]

    assert missing_model == []


def test_pnl_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch):
    route_module = load_module("backend.app.api.routes.pnl", "backend/app/api/routes/pnl.py")

    class FakePnlService:
        @staticmethod
        def pnl_dates_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.dates"}, "result": {"report_dates": []}}

        @staticmethod
        def pnl_data_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.data"}, "result": {}}

        @staticmethod
        def pnl_overview_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.overview"}, "result": {}}

        @staticmethod
        def pnl_v1_data_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.v1_data"}, "result": {}}

        @staticmethod
        def pnl_by_business_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.by_business"}, "result": {}}

        @staticmethod
        def pnl_by_business_ytd_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.by_business_ytd"}, "result": {}}

        @staticmethod
        def pnl_by_business_monthly_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.by_business_monthly"}, "result": {}}

        @staticmethod
        def pnl_by_business_analysis_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.by_business_analysis"}, "result": {}}

        @staticmethod
        def list_pnl_by_business_manual_adjustments(*_args, **_kwargs):
            return {"items": []}

        @staticmethod
        def pnl_yearly_summary_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.yearly_summary"}, "result": {}}

        @staticmethod
        def pnl_import_status(*_args, **_kwargs):
            return {"status": "idle"}

    class FakePnlBridgeService:
        @staticmethod
        def pnl_bridge_envelope(**_kwargs):
            return {"result_meta": {"result_kind": "pnl.bridge"}, "result": {}}

    def fake_import_module(module_name: str):
        if module_name == "backend.app.services.pnl_bridge_service":
            return FakePnlBridgeService
        return FakePnlService

    monkeypatch.setattr(route_module, "import_module", fake_import_module)
    sqlite_path = tmp_path / "pnl-read-denied.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    cases = [
        ("/api/pnl/dates", {}),
        ("/api/pnl/data", {"date": "2026-02-28"}),
        ("/api/pnl/bridge", {"report_date": "2026-02-28"}),
        ("/api/pnl/overview", {"report_date": "2026-02-28"}),
        ("/api/pnl/v1-data", {"date": "2026-02-28"}),
        ("/api/pnl/by-business", {"report_date": "2026-02-28"}),
        ("/api/pnl/by-business-ytd", {"year": 2026}),
        ("/api/pnl/by-business-monthly", {"year": 2026}),
        ("/api/pnl/by-business-analysis", {"year": 2026}),
        ("/api/pnl/by-business/manual-adjustments", {"report_date": "2026-02-28"}),
        ("/api/pnl/yearly-summary", {"year": 2026}),
        ("/api/data/import_status/pnl", {}),
    ]

    for path, params in cases:
        response = client.get(path, params=params, headers=PNL_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_pnl_by_business_analysis_logs_api_perf(monkeypatch, caplog):
    from fastapi import FastAPI

    route_module = load_module(
        f"tests._pnl_routes.pnl_{id(monkeypatch)}",
        "backend/app/api/routes/pnl.py",
    )

    class FakePnlService:
        @staticmethod
        def pnl_by_business_analysis_envelope(**_kwargs):
            return {
                "result_meta": {
                    "trace_id": "tr_pnl_analysis_perf",
                    "result_kind": "pnl.by_business_analysis",
                },
                "result": {"rows": []},
            }

    monkeypatch.setattr(route_module, "_pnl_service", lambda: FakePnlService)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get(
            "/api/pnl/by-business-analysis",
            params={"year": 2026, "dimension": "bond_bucket"},
        )

    assert response.status_code == 200
    records = _perf_records(caplog, "/api/pnl/by-business-analysis")
    assert records
    record = records[-1]
    assert record.getMessage() == (
        f'moss_api_perf endpoint="{record.endpoint}" duration_ms={record.duration_ms} '
        f'trace_id="{record.trace_id}" result_kind="{record.result_kind}" '
        "duckdb_statement_count=null"
    )
    assert getattr(record, "duration_ms") >= 0
    assert getattr(record, "result_kind") == "pnl.by_business_analysis"


@pytest.mark.parametrize(
    "path",
    [
        "/api/pnl/by-business-ytd",
        "/api/pnl/by-business-monthly",
        "/api/pnl/by-business-analysis",
    ],
)
def test_pnl_by_business_analytical_routes_reject_invalid_calendar_date_before_service(path, monkeypatch):
    route_module = load_module(
        f"tests._pnl_routes.invalid_date_{path.rsplit('/', 1)[-1]}_{id(monkeypatch)}",
        "backend/app/api/routes/pnl.py",
    )
    calls: list[dict[str, object]] = []

    class FakePnlService:
        @staticmethod
        def pnl_by_business_ytd_envelope(**kwargs):
            calls.append(kwargs)
            return {"result_meta": {}, "result": {}}

        @staticmethod
        def pnl_by_business_monthly_envelope(**kwargs):
            calls.append(kwargs)
            return {"result_meta": {}, "result": {}}

        @staticmethod
        def pnl_by_business_analysis_envelope(**kwargs):
            calls.append(kwargs)
            return {"result_meta": {}, "result": {}}

    monkeypatch.setattr(route_module, "_pnl_service", lambda: FakePnlService)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.get(
        path,
        params={"year": 2026, "as_of_date": "2026-02-30"},
        headers=PNL_READ_HEADERS,
    )

    assert response.status_code == 422
    assert calls == []


def test_pnl_by_business_analysis_reuses_inputs_for_same_period(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    class FakePnlRepository:
        pnl_fetch_count = 0
        balance_fetch_count = 0

        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2026
            assert as_of_cap in {None, "2026-04-30"}
            return "2026-04-30"

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2026, "2026-04-30")

        def list_union_report_dates(self):
            return ["2026-01-31", "2026-04-30"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert year == 2026
            assert as_of_date == "2026-04-30"
            type(self).pnl_fetch_count += 1
            return [
                {
                    "source_kind": "formal_fi",
                    "report_date": "2026-04-30",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": "政策性金融债",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("100.00"),
                }
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert start_date == "2026-01-01"
            assert end_date == "2026-04-30"
            type(self).balance_fetch_count += 1
            return [
                {
                    "report_date": "2026-04-30",
                    "instrument_code": "P001",
                    "instrument_name": "policy bond",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "account_category": "asset",
                    "asset_class": "政策性金融债",
                    "bond_type": "政策性金融债",
                    "sub_type": "政策性金融债",
                    "business_type_primary": "政策性金融债",
                    "business_type_final": "政策性金融债",
                    "invest_type_std": "T",
                    "accounting_basis": "FVTPL",
                    "position_scope": "asset",
                    "currency_basis": "CNY",
                    "currency_code": "CNY",
                    "avg_amount": Decimal("1000.00"),
                    "current_amount": Decimal("1000.00"),
                }
            ]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result": kwargs["result_payload"]},
    )

    first = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2026,
        as_of_date="2026-04-30",
        dimension="bond_bucket",
    )
    second = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2026,
        as_of_date="2026-04-30",
        dimension="bond_bucket_monthly",
    )

    assert first["result"]["rows"][0]["dimension_label"] == "利率债"
    assert second["result"]["dimension"] == "bond_bucket_monthly"
    assert FakePnlRepository.pnl_fetch_count == 1
    assert FakePnlRepository.balance_fetch_count == 1
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()


def test_pnl_business_classification_uses_prior_daily_balance_for_closed_positions():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    policy_type = str(row_defs["asset_zqtz_policy_financial_bond"]["match_keywords"][0])
    balance_rows = [
        {
            "report_date": "2026-04-12",
            "instrument_code": "250001.IB",
            "instrument_name": "prior balance policy bond",
            "portfolio_name": "FI Desk",
            "cost_center": "CC100",
            "account_category": "asset",
            "asset_class": policy_type,
            "bond_type": policy_type,
            "sub_type": policy_type,
            "business_type_primary": policy_type,
            "business_type_final": policy_type,
            "invest_type_std": "A",
            "accounting_basis": "FVOCI",
            "currency_basis": "CNY",
            "currency_code": "CNY",
        }
    ]

    classification = pnl_service._analysis_classification_for_pnl_row(
        pnl_row={
            "source_kind": "formal_fi",
            "report_date": "2026-04-30",
            "instrument_code": "250001.IB",
            "portfolio_name": "FI Desk",
            "cost_center": "CC100",
            "currency_basis": "CNY",
            "accounting_basis": "FVOCI",
            "invest_type_std": "A",
        },
        balance_lookup=pnl_service._analysis_balance_lookup(balance_rows),
        historical_balance_lookup=pnl_service._analysis_historical_balance_lookup(balance_rows),
        sub_type_by_date_code=pnl_service._analysis_sub_type_by_date_code(balance_rows),
        fallback_date="2026-04-30",
    )

    matched_keys = {str(row["row_key"]) for row in pnl_service.match_zqtz_asset_bond_rows(classification)}
    assert classification["business_type_primary"] == policy_type
    assert "asset_zqtz_policy_financial_bond" in matched_keys


def test_pnl_by_business_monthly_prefers_precomputed_payload(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    cached_payload = {
        "year": 2025,
        "as_of_date": "2025-12-31",
        "source_tables": ["fact_pnl_by_business_precompute"],
        "months": [
            {
                "month_key": "2025-12",
                "coverage_days": 31,
                "expected_days": 31,
                "sample_filled": False,
                "sample_fill_method": None,
                "period_start_date": "2025-12-01",
                "period_end_date": "2025-12-31",
                "calendar_days": 31,
                "source_total_pnl": "0.00",
                "classified_parent_total_pnl": "0.00",
                "unallocated_pnl": "0.00",
                "unallocated_abs_pnl": "0.00",
                "unallocated_row_count": 0,
                "reconciliation_delta": "0.00",
                "unallocated_breakdown": [],
                "unallocated_items": [],
                "unallocated_evidence_complete": True,
                "summary": {
                    "interest_income": "0.00",
                    "fair_value_change": "0.00",
                    "capital_gain": "0.00",
                    "manual_adjustment": "0.00",
                    "total_pnl": "0.00",
                    "avg_balance": "0.00",
                    "current_balance": "0.00",
                    "annualized_yield_pct": None,
                    "ftp_rate_pct": "0.00",
                    "ftp_cost": None,
                    "ftp_net_pnl": None,
                    "ftp_net_annualized_yield_pct": None,
                    "asset_count": 0,
                },
                "items": [],
            }
        ],
    }

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-12-31")

        def fetch_pnl_by_business_precompute(
            self,
            *,
            year,
            as_of_date,
            result_kind,
            dimension,
            business_key,
            expected_rule_version,
            supplemental_source_version,
        ):
            assert (year, as_of_date, result_kind, dimension, business_key) == (
                2025,
                "2025-12-31",
                "monthly",
                "",
                "",
            )
            assert expected_rule_version == PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
            assert supplemental_source_version
            return cached_payload

        def list_union_report_dates(self):  # pragma: no cover - proves cache avoids live build
            raise AssertionError("monthly endpoint should not rebuild when precompute exists")

        def fetch_by_business_analysis_pnl_rows(self, **_kwargs):  # pragma: no cover
            raise AssertionError("monthly endpoint should not fetch analysis rows when precompute exists")

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_monthly_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        as_of_date="2025-12-31",
    )

    assert payload["result_meta"]["result_kind"] == "pnl.by_business_monthly"
    assert payload["result"] == {
        **cached_payload,
        "management_change": {
            "comparison_basis": "latest_month_vs_previous_calendar_month",
            "comparison_scope": "requested_year",
            "comparison_status": "previous_month_missing",
            "comparison_available": False,
            "current_month_key": "2025-12",
            "previous_month_key": "2025-11",
            "coverage_warning_months": [],
            "reconciliation_warning_months": [],
            "incomplete_months": [],
            "summary": None,
            "rows": [],
        },
    }


def test_pnl_by_business_analysis_prefers_precomputed_payload(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    cached_payload = {
        "year": 2025,
        "as_of_date": "2025-12-31",
        "business_key": "asset_zqtz_policy_financial_bond",
        "dimension": "instrument",
        "period_start_date": "2025-01-01",
        "period_end_date": "2025-12-31",
        "coverage_days": 365,
        "expected_days": 365,
        "sample_filled": False,
        "sample_fill_method": None,
        "source_tables": ["fact_pnl_by_business_precompute"],
        "rows": [],
    }

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-12-31")

        def fetch_pnl_by_business_precompute(
            self,
            *,
            year,
            as_of_date,
            result_kind,
            dimension,
            business_key,
            expected_rule_version,
            supplemental_source_version,
        ):
            assert (year, as_of_date, result_kind, dimension, business_key) == (
                2025,
                "2025-12-31",
                "analysis",
                "instrument",
                "asset_zqtz_policy_financial_bond",
            )
            assert expected_rule_version == PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
            assert supplemental_source_version
            return cached_payload

        def list_union_report_dates(self):  # pragma: no cover - proves cache avoids live build
            raise AssertionError("analysis endpoint should not rebuild when precompute exists")

        def fetch_by_business_analysis_pnl_rows(self, **_kwargs):  # pragma: no cover
            raise AssertionError("analysis endpoint should not fetch rows when precompute exists")

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        as_of_date="2025-12-31",
        business_key="asset_zqtz_policy_financial_bond",
        dimension="instrument",
    )

    assert payload["result_meta"]["result_kind"] == "pnl.by_business_analysis"
    assert payload["result"] == {**cached_payload, "merged_bucket_rows": []}


def test_pnl_by_business_ytd_prefers_precomputed_payload(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    pnl_service.clear_pnl_by_business_ytd_cache()
    cached_payload = {
        "year": 2025,
        "period_type": "yearly",
        "period_label": "2025 YTD",
        "period_start_date": "2025-01-01",
        "period_end_date": "2025-12-31",
        "total_pnl": "100.00",
        "coverage_days": 365,
        "expected_days": 365,
        "sample_filled": False,
        "sample_fill_method": None,
        "classified_parent_total_pnl": "100.00",
        "summary": {
            "interest_income": "100.00",
            "fair_value_change": "0.00",
            "capital_gain": "0.00",
            "manual_adjustment": "0.00",
            "total_pnl": "100.00",
            "avg_balance": "1000.00",
            "current_balance": "1000.00",
            "annualized_yield_pct": "10.00",
            "ftp_rate_pct": "1.60",
            "ftp_cost": "16.00",
            "ftp_net_pnl": "84.00",
            "ftp_net_annualized_yield_pct": "8.40",
            "proportion": "1.00",
            "assets_count": 1,
        },
        "unallocated_pnl": "0.00",
        "unallocated_abs_pnl": "0.00",
        "unallocated_row_count": 0,
        "reconciliation_delta": "0.00",
        "unallocated_breakdown": [],
        "unallocated_items": [],
        "source_tables": ["fact_pnl_by_business_precompute"],
        "items": [],
    }

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def formal_pnl_ytd_has_rows(self, *, year, as_of_date):
            return (year, as_of_date) == (2025, "2025-12-31")

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-12-31")

    fetches: list[dict[str, object]] = []
    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "get_settings",
        lambda: SimpleNamespace(pnl_by_business_ytd_prefer_formal_facts=True),
    )
    monkeypatch.setattr(
        pnl_service,
        "_fetch_pnl_by_business_precompute",
        lambda _repo, **kwargs: fetches.append(kwargs) or cached_payload,
    )
    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_from_formal_facts",
        lambda **_kwargs: pytest.fail("YTD endpoint should not rebuild when precompute exists"),
    )
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"trace_id": kwargs["trace_id"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        as_of_date="2025-12-31",
    )

    assert fetches == [
        {
            "governance_dir": str(tmp_path / "governance"),
            "year": 2025,
            "as_of_date": "2025-12-31",
            "result_kind": "ytd",
            "dimension": "",
            "business_key": "",
        }
    ]
    assert payload["result"] == cached_payload
    assert payload["result_meta"]["trace_id"].endswith("_precomputed")


def test_pnl_by_business_precompute_requires_coverage_diagnostics_before_use():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    required = {
        "coverage_days": 365,
        "expected_days": 365,
        "sample_filled": False,
        "sample_fill_method": None,
    }
    monthly_required = {
        **required,
        "source_total_pnl": "1.00",
        "classified_parent_total_pnl": "1.00",
        "unallocated_pnl": "0.00",
        "unallocated_abs_pnl": "0.00",
        "unallocated_row_count": 0,
        "reconciliation_delta": "0.00",
        "unallocated_breakdown": [],
        "unallocated_items": [],
        "unallocated_evidence_complete": True,
    }

    assert pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        {"rows": [], **required},
        result_kind="analysis",
    )
    assert not pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        {"rows": []},
        result_kind="analysis",
    )
    assert pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        {"months": [{"month_key": "2025-12", **monthly_required}]},
        result_kind="monthly",
    )
    assert not pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        {
            "months": [
                {
                    "month_key": "2025-12",
                    **{key: value for key, value in monthly_required.items() if key != "unallocated_items"},
                }
            ]
        },
        result_kind="monthly",
    )
    assert not pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        {"months": []},
        result_kind="monthly",
    )
    ytd_payload = {
        **required,
        "total_pnl": "1.00",
        "classified_parent_total_pnl": "1.00",
        "unallocated_pnl": "0.00",
        "unallocated_abs_pnl": "0.00",
        "unallocated_row_count": 0,
        "reconciliation_delta": "0.00",
        "unallocated_breakdown": [],
        "unallocated_items": [],
        "summary": {},
        "items": [],
    }
    assert pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        ytd_payload,
        result_kind="ytd",
    )
    assert not pnl_service._pnl_by_business_precompute_has_required_diagnostics(
        {key: value for key, value in ytd_payload.items() if key != "unallocated_items"},
        result_kind="ytd",
    )


def test_pnl_by_business_monthly_manual_adjustment_uses_declared_row_definition():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    manual_row = pnl_service._pnl_by_business_adjustment_record(
        report_date="2025-12-31",
        row_key="asset_zqtz_foreign_bond",
        business_type="Foreign bond manual adjustment",
        manual_adjustment="25.00",
        source_note="pnl_by_business_adjustments:foreign-1",
    )

    month = pnl_service._build_pnl_by_business_monthly_buckets(
        pnl_rows=(manual_row,),
        balance_rows=(),
        loaded_dates=["2025-12-31"],
        ftp_rate_pct=Decimal("0"),
    )[0]
    by_key = {item.row_key: item for item in month.items}

    assert by_key["asset_zqtz_foreign_bond"].manual_adjustment == Decimal("25.00")
    assert month.source_total_pnl == Decimal("25.00")
    assert month.classified_parent_total_pnl == Decimal("25.00")
    assert month.unallocated_pnl == Decimal("0.00")
    assert month.unallocated_row_count == 0
    assert month.reconciliation_delta == Decimal("0.00")


def test_pnl_by_business_monthly_aggregates_unallocated_before_rounding():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    rows = tuple(
        {
            "source_kind": "formal_fi",
            "report_date": "2025-12-31",
            "instrument_code": f"UNALLOCATED-{index}",
            "portfolio_name": "Unmapped Desk",
            "cost_center": "CC-UNMAPPED",
            "currency_basis": "CNY",
            "invest_type_std": "",
            "accounting_basis": "",
            "interest_income_514": Decimal("0.004"),
            "fair_value_change_516": Decimal("0"),
            "capital_gain_517": Decimal("0"),
            "manual_adjustment": Decimal("0"),
            "total_pnl": Decimal("0.004"),
        }
        for index in range(2)
    )

    month = pnl_service._build_pnl_by_business_monthly_buckets(
        pnl_rows=rows,
        balance_rows=(),
        loaded_dates=["2025-12-31"],
        ftp_rate_pct=Decimal("0"),
    )[0]

    assert month.source_total_pnl == Decimal("0.01")
    assert month.unallocated_pnl == Decimal("0.01")
    assert month.unallocated_abs_pnl == Decimal("0.01")
    assert month.reconciliation_delta == Decimal("0.00")


def test_pnl_by_business_monthly_reconciles_precise_aggregates_before_rounding():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    parent_row = pnl_service._pnl_by_business_adjustment_record(
        report_date="2025-12-31",
        row_key="asset_zqtz_foreign_bond",
        business_type="Foreign bond manual adjustment",
        manual_adjustment="0.004",
        source_note="pnl_by_business_adjustments:precision-parent",
    )
    unallocated_row = {
        "source_kind": "formal_fi",
        "report_date": "2025-12-31",
        "instrument_code": "UNALLOCATED-PRECISION",
        "portfolio_name": "Unmapped Desk",
        "cost_center": "CC-UNMAPPED",
        "currency_basis": "CNY",
        "invest_type_std": "",
        "accounting_basis": "",
        "interest_income_514": Decimal("0.004"),
        "fair_value_change_516": Decimal("0"),
        "capital_gain_517": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0.004"),
    }

    month = pnl_service._build_pnl_by_business_monthly_buckets(
        pnl_rows=(parent_row, unallocated_row),
        balance_rows=(),
        loaded_dates=["2025-12-31"],
        ftp_rate_pct=Decimal("0"),
    )[0]

    assert month.source_total_pnl == Decimal("0.01")
    assert month.classified_parent_total_pnl == Decimal("0.00")
    assert month.unallocated_pnl == Decimal("0.00")
    assert month.reconciliation_delta == Decimal("0.00")


def test_pnl_by_business_monthly_and_analysis_fall_back_when_adjustment_precompute_is_missing(
    tmp_path,
    monkeypatch,
):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    GovernanceRepository(base_dir=governance_dir).append(
        "pnl_by_business_adjustments",
        {
            "adjustment_id": "pba-precompute-bypass-1",
            "event_type": "created",
            "created_at": "2026-04-12T08:00:00+00:00",
            "stream": "pnl_by_business_adjustments",
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "Policy Financial Bond",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "25.00",
            "reason": "manual override should bypass stale precompute",
        },
    )

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-12-31")

        def fetch_pnl_by_business_precompute(
            self,
            *,
            year,
            as_of_date,
            result_kind,
            dimension,
            business_key,
            expected_rule_version,
            supplemental_source_version,
        ):
            assert supplemental_source_version
            return None

        def list_union_report_dates(self):
            return ["2025-12-31"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-12-31")
            return [
                {
                    "report_date": "2025-12-31",
                    "source_kind": "formal_fi",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": "T",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("25.50"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("125.50"),
                },
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert (start_date, end_date) == ("2025-12-01", "2025-12-31")
            return [
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "P001",
                    "instrument_name": "policy financial bond",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "account_category": "asset",
                    "asset_class": "政策性金融债",
                    "bond_type": "政策性金融债",
                    "sub_type": "政策性金融债",
                    "business_type_primary": "政策性金融债",
                    "business_type_final": "政策性金融债",
                    "invest_type_std": "T",
                    "accounting_basis": "FVTPL",
                    "currency_code": "CNY",
                    "avg_amount": Decimal("1000.00"),
                    "current_amount": Decimal("1000.00"),
                },
            ]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_monthly_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
    )

    assert payload["result_meta"]["result_kind"] == "pnl.by_business_monthly"
    assert payload["result"]["source_tables"][-1] == "pnl_by_business_adjustments"
    by_key = {item["row_key"]: item for item in payload["result"]["months"][0]["items"]}
    assert by_key["asset_zqtz_policy_financial_bond"]["manual_adjustment"] == "25.00"
    assert by_key["asset_zqtz_policy_financial_bond"]["total_pnl"] == "150.50"

    analysis_payload = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
        business_key="asset_zqtz_policy_financial_bond",
        dimension="currency",
    )

    assert analysis_payload["result_meta"]["result_kind"] == "pnl.by_business_analysis"
    assert analysis_payload["result"]["source_tables"][-1] == "pnl_by_business_adjustments"
    assert analysis_payload["result"]["rows"][0]["manual_adjustment"] == "25.00"
    assert analysis_payload["result"]["rows"][0]["total_pnl"] == "150.50"
    get_settings.cache_clear()


def test_pnl_by_business_precompute_writes_page_payloads(tmp_path, monkeypatch):
    precompute_module = load_module(
        "backend.app.tasks.pnl_by_business_precompute",
        "backend/app/tasks/pnl_by_business_precompute.py",
    )

    row_defs = (
        {
            "row_key": "asset_zqtz_policy_financial_bond",
            "row_label": "Policy Financial Bond",
            "sort_order": 66,
            "source_note": "test",
        },
    )
    governance_dir = tmp_path / "governance"
    GovernanceRepository(base_dir=governance_dir).append(
        "pnl_by_business_adjustments",
        {
            "adjustment_id": "adj-precompute-approved",
            "event_type": "approved",
            "created_at": "2026-04-12T08:00:00+00:00",
            "stream": "pnl_by_business_adjustments",
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "Policy Financial Bond",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "25.00",
            "reason": "approved adjustment must be materialized",
        },
    )

    class FakePnlRepository:
        written_records: list[dict[str, object]] = []
        supplemental_source_version = ""
        pnl_fetch_count = 0
        precompute_fetch_count = 0

        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-12-31")

        def list_union_report_dates(self):
            return ["2025-12-31"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert year == 2025
            assert as_of_date == "2025-12-31"
            type(self).pnl_fetch_count += 1
            return [
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-12-31",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": "Policy Financial Bond",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("100.00"),
                }
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert start_date == "2025-12-01"
            assert end_date == "2025-12-31"
            return [
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "P001",
                    "instrument_name": "policy bond",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "account_category": "asset",
                    "asset_class": "Policy Financial Bond",
                    "bond_type": "Policy Financial Bond",
                    "sub_type": "Policy Financial Bond",
                    "business_type_primary": "Policy Financial Bond",
                    "business_type_final": "Policy Financial Bond",
                    "invest_type_std": "Policy Financial Bond",
                    "accounting_basis": "FVTPL",
                    "position_scope": "asset",
                    "currency_basis": "CNY",
                    "currency_code": "CNY",
                    "avg_amount": Decimal("10000.00"),
                    "current_amount": Decimal("11000.00"),
                }
            ]

        def pnl_by_business_precompute_source_version(
            self, *, year, as_of_date, supplemental_source_version=""
        ):
            assert (year, as_of_date) == (2025, "2025-12-31")
            type(self).supplemental_source_version = supplemental_source_version
            return f"source::{supplemental_source_version}"

        def fetch_pnl_by_business_precompute(
            self,
            *,
            year,
            as_of_date,
            result_kind,
            dimension,
            business_key,
            expected_rule_version,
            supplemental_source_version,
        ):
            type(self).precompute_fetch_count += 1
            expected_source_version = self.pnl_by_business_precompute_source_version(
                year=year,
                as_of_date=as_of_date,
                supplemental_source_version=supplemental_source_version,
            )
            for record in type(self).written_records:
                if (
                    record["year"] == year
                    and record["as_of_date"] == as_of_date
                    and record["result_kind"] == result_kind
                    and record["dimension"] == dimension
                    and record["business_key"] == business_key
                    and record["rule_version"] == expected_rule_version
                    and record["source_version"] == expected_source_version
                ):
                    return json.loads(str(record["payload_json"]))
            return None

        def replace_pnl_by_business_precompute(self, *, year, as_of_date, records):
            assert year == 2025
            assert as_of_date == "2025-12-31"
            type(self).written_records = records

    monkeypatch.setattr(precompute_module, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(precompute_module, "ZQTZ_ASSET_BOND_ROWS", row_defs)
    monkeypatch.setattr(precompute_module, "match_zqtz_asset_bond_rows", lambda _classification: row_defs)
    expected_ytd_payload = PnlByBusinessYtdPayload.model_validate(
        {
            "year": 2025,
            "period_type": "yearly",
            "period_label": "2025 YTD",
            "period_start_date": "2025-12-01",
            "period_end_date": "2025-12-31",
            "total_pnl": "125.00",
            "coverage_days": 1,
            "expected_days": 31,
            "sample_filled": True,
            "sample_fill_method": "observed_days_scaled_to_calendar",
            "classified_parent_total_pnl": "125.00",
            "summary": {
                "interest_income": "100.00",
                "fair_value_change": "0.00",
                "capital_gain": "0.00",
                "manual_adjustment": "25.00",
                "total_pnl": "125.00",
                "avg_balance": "10000.00",
                "current_balance": "11000.00",
                "annualized_yield_pct": "0.00",
                "ftp_rate_pct": "1.60",
                "ftp_cost": "0.00",
                "ftp_net_pnl": "125.00",
                "ftp_net_annualized_yield_pct": "0.00",
                "proportion": "1.00",
                "assets_count": 1,
            },
            "unallocated_pnl": "0.00",
            "unallocated_abs_pnl": "0.00",
            "unallocated_row_count": 0,
            "reconciliation_delta": "0.00",
            "unallocated_breakdown": [],
            "unallocated_items": [],
            "source_tables": ["fact_formal_pnl_fi", "pnl_by_business_adjustments"],
            "items": [],
        }
    )
    monkeypatch.setattr(
        precompute_module,
        "_build_pnl_by_business_ytd_payload_for_precompute",
        lambda **_kwargs: expected_ytd_payload,
        raising=False,
    )

    summary = precompute_module.precompute_pnl_by_business_payloads(
        duckdb_path="fake.duckdb",
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
    )

    record_keys = {
        (str(record["result_kind"]), str(record["dimension"]), str(record["business_key"]))
        for record in FakePnlRepository.written_records
    }
    assert ("monthly", "", "") in record_keys
    assert ("ytd", "", "") in record_keys
    assert ("analysis", "bond_bucket", "") in record_keys
    assert ("analysis", "currency", "asset_zqtz_policy_financial_bond") in record_keys
    assert ("analysis", "instrument", "asset_zqtz_policy_financial_bond") in record_keys
    assert summary["records"] == len(FakePnlRepository.written_records)
    assert summary["ytd_records"] == 1

    monthly_record = next(record for record in FakePnlRepository.written_records if record["result_kind"] == "monthly")
    monthly_payload = json.loads(str(monthly_record["payload_json"]))
    assert monthly_payload["as_of_date"] == "2025-12-31"
    assert monthly_payload["months"][0]["month_key"] == "2025-12"
    assert monthly_payload["source_tables"][-1] == "pnl_by_business_adjustments"
    monthly_by_key = {
        item["row_key"]: item for item in monthly_payload["months"][0]["items"]
    }
    assert monthly_by_key["asset_zqtz_policy_financial_bond"]["manual_adjustment"] == "25.00"
    assert monthly_by_key["asset_zqtz_policy_financial_bond"]["total_pnl"] == "125.00"
    assert FakePnlRepository.supplemental_source_version
    assert monthly_record["source_version"] == f"source::{FakePnlRepository.supplemental_source_version}"

    currency_record = next(
        record
        for record in FakePnlRepository.written_records
        if record["result_kind"] == "analysis"
        and record["dimension"] == "currency"
        and record["business_key"] == "asset_zqtz_policy_financial_bond"
    )
    currency_payload = json.loads(str(currency_record["payload_json"]))
    assert currency_payload["coverage_days"] == 1
    assert currency_payload["expected_days"] == 31
    assert currency_payload["sample_filled"] is True
    assert currency_payload["sample_fill_method"] == "observed_days_scaled_to_calendar"
    assert [
        (row["dimension_key"], row["dimension_label"], row["total_pnl"])
        for row in currency_payload["rows"]
    ] == [("CNY", "人民币", "125.00")]

    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"trace_id": kwargs["trace_id"]}, "result": kwargs["result_payload"]},
    )
    monthly_envelope = pnl_service.pnl_by_business_monthly_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
    )
    analysis_envelope = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
        business_key="asset_zqtz_policy_financial_bond",
        dimension="currency",
    )

    assert monthly_envelope["result_meta"]["trace_id"].endswith("_precomputed")
    assert analysis_envelope["result_meta"]["trace_id"].endswith("_precomputed")
    assert FakePnlRepository.pnl_fetch_count == 1
    assert FakePnlRepository.precompute_fetch_count == 2


def test_pnl_by_business_ytd_precompute_reuses_payload_builder_without_lineage(monkeypatch):
    precompute_module = load_module(
        "backend.app.tasks.pnl_by_business_precompute",
        "backend/app/tasks/pnl_by_business_precompute.py",
    )
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    expected_payload = object()
    payload_builder_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_payload_from_formal_facts",
        lambda **kwargs: payload_builder_calls.append(kwargs) or (expected_payload, "2025-12-31"),
        raising=False,
    )
    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_from_formal_facts",
        lambda **_kwargs: pytest.fail("precompute must not require the formal lineage envelope"),
    )

    payload = precompute_module._build_pnl_by_business_ytd_payload_for_precompute(
        duckdb_path="fake.duckdb",
        governance_dir="unused",
        year=2025,
        as_of_date="2025-12-31",
    )

    assert payload is expected_payload
    assert payload_builder_calls == [
        {
            "duckdb_path": "fake.duckdb",
            "governance_dir": "unused",
            "year": 2025,
            "as_of_date": "2025-12-31",
        }
    ]


def test_pnl_by_business_precompute_invalidates_after_source_change(tmp_path, monkeypatch):
    task_module = load_module("backend.app.tasks.pnl_materialize", "backend/app/tasks/pnl_materialize.py")
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "P001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "10.00",
                "fair_value_change_516": "0.00",
                "capital_gain_517": "0.00",
                "manual_adjustment": "0.00",
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-fi",
                "trace_id": "trace-fi",
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P002', 'FI Desk', 'CC100', 'T', 'FVTPL', 'CNY',
              5.00, 0.00, 0.00, 0.00, 5.00,
              'src-v2', 'rv_pnl_phase2_materialize_v1', 'batch-fi-2', 'trace-fi-2'
            )
            """
        )
    finally:
        conn.close()

    payload = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
        dimension="bond_bucket",
    )

    total_pnl = sum(Decimal(str(row["total_pnl"])) for row in payload["result"]["rows"])
    assert total_pnl == Decimal("15.00")


def test_pnl_by_business_monthly_contract_returns_independent_month_buckets(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    policy_type = str(row_defs["asset_zqtz_policy_financial_bond"]["match_keywords"][0])
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-02-28"}
            return "2025-02-28"

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-02-28")

        def list_union_report_dates(self):
            return ["2025-01-31", "2025-02-28"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert year == 2025
            assert as_of_date == "2025-02-28"
            return [
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-01-31",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": policy_type,
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("100.00"),
                },
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-02-28",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": policy_type,
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("200.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("200.00"),
                },
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-02-28",
                    "instrument_code": "UNALLOCATED-A",
                    "portfolio_name": "Unmapped Desk",
                    "cost_center": "CC-UNMAPPED",
                    "currency_basis": "CNY",
                    "invest_type_std": "A",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("7.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("7.00"),
                },
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-02-28",
                    "instrument_code": "UNALLOCATED-A-NEG",
                    "portfolio_name": "Unmapped Desk",
                    "cost_center": "CC-UNMAPPED",
                    "currency_basis": "CNY",
                    "invest_type_std": "A",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("-2.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("-2.00"),
                },
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert start_date == "2025-01-01"
            assert end_date == "2025-02-28"
            base = {
                "instrument_code": "P001",
                "instrument_name": "policy bond",
                "portfolio_name": "Rate Desk",
                "cost_center": "CC-RATE",
                "account_category": "asset",
                "asset_class": policy_type,
                "bond_type": policy_type,
                "sub_type": policy_type,
                "business_type_primary": policy_type,
                "business_type_final": policy_type,
                "invest_type_std": "T",
                "accounting_basis": "FVTPL",
                "position_scope": "asset",
                "currency_basis": "CNY",
                "currency_code": "CNY",
            }
            return [
                {
                    **base,
                    "report_date": "2025-01-31",
                    "avg_amount": Decimal("1000.00"),
                    "current_amount": Decimal("1100.00"),
                },
                {
                    **base,
                    "report_date": "2025-02-28",
                    "avg_amount": Decimal("2000.00"),
                    "current_amount": Decimal("2200.00"),
                },
            ]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business-monthly", params={"year": 2025, "as_of_date": "2025-02-28"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_monthly"
    result = payload["result"]
    assert result["year"] == 2025
    assert result["as_of_date"] == "2025-02-28"
    assert [month["month_key"] for month in result["months"]] == ["2025-01", "2025-02"]

    jan, feb = result["months"]
    assert jan["period_start_date"] == "2025-01-01"
    assert jan["period_end_date"] == "2025-01-31"
    assert jan["calendar_days"] == 31
    assert jan["coverage_days"] == 1
    assert jan["expected_days"] == 31
    assert jan["sample_filled"] is True
    assert jan["sample_fill_method"] == "observed_days_scaled_to_calendar"
    assert jan["summary"]["total_pnl"] == "100.00"
    assert jan["summary"]["avg_balance"] == "1000.00"
    assert jan["summary"]["current_balance"] == "1100.00"
    assert jan["summary"]["ftp_cost"] == "1.49"
    assert jan["summary"]["ftp_net_pnl"] == "98.51"
    jan_item = next(item for item in jan["items"] if item["row_key"] == "asset_zqtz_policy_financial_bond")
    assert set(jan_item) == {
        "row_key",
        "sort_order",
        "business_type",
        "interest_income",
        "fair_value_change",
        "capital_gain",
        "manual_adjustment",
        "total_pnl",
        "avg_balance",
        "current_balance",
        "annualized_yield_pct",
        "ftp_rate_pct",
        "ftp_cost",
        "ftp_net_pnl",
        "ftp_net_annualized_yield_pct",
        "proportion",
        "asset_count",
        "source_note",
    }
    assert jan_item["total_pnl"] == "100.00"
    assert jan_item["avg_balance"] == "1000.00"
    assert jan_item["current_balance"] == "1100.00"
    assert jan_item["annualized_yield_pct"] == "117.741935"
    assert jan_item["ftp_rate_pct"] == "1.750000"
    assert jan_item["ftp_cost"] == "1.49"
    assert jan_item["ftp_net_pnl"] == "98.51"
    assert jan_item["ftp_net_annualized_yield_pct"] == "115.991935"
    assert jan_item["proportion"] == "1.000000"
    assert jan_item["asset_count"] == 1
    assert feb["summary"]["total_pnl"] == "200.00"
    assert feb["summary"]["avg_balance"] == "2000.00"
    assert feb["coverage_days"] == 1
    assert feb["expected_days"] == 28
    assert feb["sample_filled"] is True
    assert feb["sample_fill_method"] == "observed_days_scaled_to_calendar"
    assert feb["source_total_pnl"] == "205.00"
    assert feb["classified_parent_total_pnl"] == "200.00"
    assert feb["unallocated_pnl"] == "5.00"
    assert feb["unallocated_abs_pnl"] == "9.00"
    assert feb["unallocated_row_count"] == 2
    assert feb["reconciliation_delta"] == "0.00"
    assert feb["unallocated_breakdown"] == [
        {
            "reason_code": "no_business_rule_match",
            "source_kind": "formal_fi",
            "invest_type_std": "A",
            "accounting_basis": "FVTPL",
            "portfolio_name": "Unmapped Desk",
            "cost_center": "CC-UNMAPPED",
            "pnl_row_count": 2,
            "total_pnl": "5.00",
            "abs_pnl": "9.00",
            "sample_instrument_codes": ["UNALLOCATED-A", "UNALLOCATED-A-NEG"],
        }
    ]
    assert [item["instrument_code"] for item in feb["unallocated_items"]] == [
        "UNALLOCATED-A",
        "UNALLOCATED-A-NEG",
    ]
    assert [item["total_pnl"] for item in feb["unallocated_items"]] == ["7.00", "-2.00"]
    assert feb["items"][0]["total_pnl"] != "300.00"
    management_change = result["management_change"]
    assert management_change["comparison_basis"] == "latest_month_vs_previous_calendar_month"
    assert management_change["comparison_scope"] == "requested_year"
    assert management_change["comparison_status"] == "data_quality_warning"
    assert management_change["comparison_available"] is True
    assert management_change["current_month_key"] == "2025-02"
    assert management_change["previous_month_key"] == "2025-01"
    assert management_change["coverage_warning_months"] == ["2025-01", "2025-02"]
    assert management_change["reconciliation_warning_months"] == ["2025-02"]
    assert management_change["incomplete_months"] == []
    assert management_change["summary"] == {
        "interest_income_delta": "100.00",
        "fair_value_change_delta": "0.00",
        "capital_gain_delta": "0.00",
        "manual_adjustment_delta": "0.00",
        "total_pnl_delta": "100.00",
        "avg_balance_delta": "1000.00",
        "current_balance_delta": "1100.00",
        "annualized_yield_delta_bp": "1261.5208",
        "ftp_cost_delta": "1.19",
        "ftp_net_pnl_delta": "98.81",
        "ftp_net_annualized_yield_delta_bp": "1261.5208",
    }
    policy_change = next(
        row
        for row in management_change["rows"]
        if row["row_key"] == "asset_zqtz_policy_financial_bond"
    )
    assert policy_change["comparison_available"] is True
    assert policy_change["comparison_reason"] == "available"
    assert policy_change["total_pnl_delta"] == "100.00"
    assert policy_change["avg_balance_delta"] == "1000.00"
    assert policy_change["ftp_net_pnl_delta"] == "98.81"
    assert policy_change["ftp_net_annualized_yield_delta_bp"] == "1261.5208"
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()


def _monthly_management_change_bucket(
    pnl_service,
    *,
    month_key: str,
    period_end_date: str,
    calendar_days: int,
    coverage_days: int,
    expected_days: int,
    total_pnl: str,
    avg_balance: str,
    current_balance: str,
):
    has_balance = coverage_days > 0
    item = pnl_service.PnlByBusinessMonthlyItem(
        row_key="asset_zqtz_policy_financial_bond",
        sort_order=66,
        business_type="政策性金融债",
        interest_income=Decimal(total_pnl),
        fair_value_change=Decimal("0"),
        capital_gain=Decimal("0"),
        manual_adjustment=Decimal("0"),
        total_pnl=Decimal(total_pnl),
        avg_balance=Decimal(avg_balance),
        current_balance=Decimal(current_balance),
        annualized_yield_pct=Decimal("2.000000") if has_balance else None,
        ftp_rate_pct=Decimal("1.600000"),
        ftp_cost=Decimal("10.00") if has_balance else None,
        ftp_net_pnl=Decimal(total_pnl) - Decimal("10.00") if has_balance else None,
        ftp_net_annualized_yield_pct=Decimal("0.400000") if has_balance else None,
        proportion=Decimal("1.000000"),
        asset_count=1,
        source_note="ZQTZ_ASSET_BOND_ROWS",
    )
    summary = pnl_service.PnlByBusinessMonthlySummary(
        interest_income=item.interest_income,
        fair_value_change=item.fair_value_change,
        capital_gain=item.capital_gain,
        manual_adjustment=item.manual_adjustment,
        total_pnl=item.total_pnl,
        avg_balance=item.avg_balance,
        current_balance=item.current_balance,
        annualized_yield_pct=item.annualized_yield_pct,
        ftp_rate_pct=item.ftp_rate_pct,
        ftp_cost=item.ftp_cost,
        ftp_net_pnl=item.ftp_net_pnl,
        ftp_net_annualized_yield_pct=item.ftp_net_annualized_yield_pct,
        asset_count=1,
    )
    return pnl_service.PnlByBusinessMonthlyBucket(
        month_key=month_key,
        period_start_date=f"{month_key}-01",
        period_end_date=period_end_date,
        calendar_days=calendar_days,
        coverage_days=coverage_days,
        expected_days=expected_days,
        sample_filled=0 < coverage_days < expected_days,
        sample_fill_method=(
            "observed_days_scaled_to_calendar" if 0 < coverage_days < expected_days else None
        ),
        source_total_pnl=Decimal(total_pnl),
        classified_parent_total_pnl=Decimal(total_pnl),
        unallocated_pnl=Decimal("0"),
        unallocated_abs_pnl=Decimal("0"),
        unallocated_row_count=0,
        reconciliation_delta=Decimal("0"),
        unallocated_breakdown=[],
        unallocated_items=[],
        unallocated_evidence_complete=True,
        summary=summary,
        items=[item],
    )


def test_pnl_by_business_monthly_change_does_not_treat_zero_coverage_as_zero_balance():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    january = _monthly_management_change_bucket(
        pnl_service,
        month_key="2025-01",
        period_end_date="2025-01-31",
        calendar_days=31,
        coverage_days=31,
        expected_days=31,
        total_pnl="100.00",
        avg_balance="1000.00",
        current_balance="1100.00",
    )
    february = _monthly_management_change_bucket(
        pnl_service,
        month_key="2025-02",
        period_end_date="2025-02-28",
        calendar_days=28,
        coverage_days=0,
        expected_days=28,
        total_pnl="200.00",
        avg_balance="0.00",
        current_balance="0.00",
    )
    payload = pnl_service.PnlByBusinessMonthlyPayload(
        year=2025,
        as_of_date="2025-02-28",
        source_tables=["test"],
        months=[january, february],
    )

    change = pnl_service._pnl_by_business_monthly_with_management_change(payload).management_change

    assert change is not None
    assert change.comparison_status == "data_quality_warning"
    assert change.summary is not None
    assert change.summary.total_pnl_delta == Decimal("100.00")
    assert change.summary.avg_balance_delta is None
    assert change.summary.current_balance_delta is None
    assert change.summary.annualized_yield_delta_bp is None
    assert change.summary.ftp_cost_delta is None
    assert change.summary.ftp_net_pnl_delta is None
    assert change.summary.ftp_net_annualized_yield_delta_bp is None
    assert change.rows[0].avg_balance_delta is None
    assert change.rows[0].current_balance_delta is None


def test_pnl_by_business_monthly_change_fails_closed_for_incomplete_current_month():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    january = _monthly_management_change_bucket(
        pnl_service,
        month_key="2025-01",
        period_end_date="2025-01-31",
        calendar_days=31,
        coverage_days=31,
        expected_days=31,
        total_pnl="100.00",
        avg_balance="1000.00",
        current_balance="1100.00",
    )
    partial_february = _monthly_management_change_bucket(
        pnl_service,
        month_key="2025-02",
        period_end_date="2025-02-15",
        calendar_days=15,
        coverage_days=15,
        expected_days=15,
        total_pnl="120.00",
        avg_balance="1200.00",
        current_balance="1250.00",
    )
    payload = pnl_service.PnlByBusinessMonthlyPayload(
        year=2025,
        as_of_date="2025-02-15",
        source_tables=["test"],
        months=[january, partial_february],
    )

    change = pnl_service._pnl_by_business_monthly_with_management_change(payload).management_change

    assert change is not None
    assert change.comparison_status == "period_incomplete"
    assert change.comparison_available is False
    assert change.incomplete_months == ["2025-02"]
    assert change.summary is None
    assert change.rows == []


def test_pnl_by_business_monthly_change_marks_previous_month_outside_year_scope():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    january = _monthly_management_change_bucket(
        pnl_service,
        month_key="2026-01",
        period_end_date="2026-01-31",
        calendar_days=31,
        coverage_days=31,
        expected_days=31,
        total_pnl="100.00",
        avg_balance="1000.00",
        current_balance="1100.00",
    )
    payload = pnl_service.PnlByBusinessMonthlyPayload(
        year=2026,
        as_of_date="2026-01-31",
        source_tables=["test"],
        months=[january],
    )

    change = pnl_service._pnl_by_business_monthly_with_management_change(payload).management_change

    assert change is not None
    assert change.comparison_status == "previous_month_outside_request_scope"
    assert change.comparison_available is False
    assert change.previous_month_key == "2025-12"
    assert change.summary is None


def test_pnl_by_business_monthly_reconciliation_delta_is_independently_derived(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    forced_item = pnl_service.PnlByBusinessYtdUnallocatedItem(
        report_date="2025-01-31",
        reason_code="no_business_rule_match",
        source_kind="formal_fi",
        instrument_code="UNALLOCATED-A",
        portfolio_name="Unmapped Desk",
        cost_center="CC-UNMAPPED",
        invest_type_std="A",
        accounting_basis="FVTPL",
        currency_basis="CNY",
        interest_income_514=Decimal("5.00"),
        fair_value_change_516=Decimal("0.00"),
        capital_gain_517=Decimal("0.00"),
        manual_adjustment=Decimal("0.00"),
        total_pnl=Decimal("5.00"),
        abs_pnl=Decimal("5.00"),
    )
    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_unallocated_item",
        lambda **_kwargs: forced_item,
    )

    buckets = pnl_service._build_pnl_by_business_monthly_buckets(
        pnl_rows=(
            {
                "source_kind": "formal_fi",
                "report_date": "2025-01-31",
                "instrument_code": "UNALLOCATED-A",
                "portfolio_name": "Unmapped Desk",
                "cost_center": "CC-UNMAPPED",
                "currency_basis": "CNY",
                "invest_type_std": "A",
                "accounting_basis": "FVTPL",
                "interest_income_514": Decimal("7.00"),
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "manual_adjustment": Decimal("0.00"),
                "total_pnl": Decimal("7.00"),
            },
        ),
        balance_rows=(),
        loaded_dates=["2025-01-31"],
        ftp_rate_pct=Decimal("0"),
    )

    assert len(buckets) == 1
    assert buckets[0].source_total_pnl == Decimal("7.00")
    assert buckets[0].classified_parent_total_pnl == Decimal("0.00")
    assert buckets[0].unallocated_pnl == Decimal("5.00")
    assert buckets[0].reconciliation_delta == Decimal("2.00")


def test_pnl_by_business_quality_flags_unallocated_rows_even_when_net_is_zero():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    ytd_payload = pnl_service.PnlByBusinessYtdPayload.model_construct(
        coverage_days=1,
        expected_days=1,
        unallocated_pnl=Decimal("0"),
        unallocated_row_count=2,
        reconciliation_delta=Decimal("0"),
    )
    month = pnl_service.PnlByBusinessMonthlyBucket.model_construct(
        coverage_days=1,
        expected_days=1,
        unallocated_pnl=Decimal("0"),
        unallocated_row_count=2,
        reconciliation_delta=Decimal("0"),
    )
    monthly_payload = pnl_service.PnlByBusinessMonthlyPayload.model_construct(months=[month])

    assert pnl_service._pnl_by_business_ytd_quality_flag(ytd_payload) == "warning"
    assert pnl_service._pnl_by_business_monthly_quality_flag(monthly_payload) == "warning"


def test_pnl_service_uses_shared_formal_lineage_and_result_meta_helpers():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "pnl_service.py"
    src = path.read_text(encoding="utf-8")

    assert "resolve_formal_manifest_lineage" in src
    assert "build_formal_result_envelope_from_lineage" in src
    assert "def _resolve_pnl_manifest_lineage" not in src


def test_pnl_service_keeps_intentional_local_cache_version_wrapper():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "pnl_service.py"
    src = path.read_text(encoding="utf-8")

    assert "def _build_pnl_formal_result_envelope_from_lineage" in src
    assert "use_lineage_cache_version=False" in src
    assert "default_cache_version=PNL_CACHE_VERSION" in src


def test_pnl_by_business_analytical_envelope_exposes_requested_resolved_fallback_dates(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {
            "result_meta": {
                "result_kind": kwargs["result_kind"],
                "basis": "formal",
                "formal_use_allowed": True,
                "quality_flag": kwargs.get("quality_flag") or "ok",
                "fallback_mode": "none",
            },
            "result": kwargs["result_payload"],
        },
    )

    payload = pnl_service._build_pnl_by_business_analytical_result_envelope(
        governance_dir=str(tmp_path / "governance"),
        requested_report_date="2026-06-15",
        resolved_report_date="2026-05-31",
        trace_id="tr_pnl_by_business_dates",
        result_kind="pnl.by_business_ytd",
        result_payload={"source_tables": ["fact_formal_pnl_fi"]},
        quality_flag="warning",
        filters_applied={"year": 2026},
    )

    meta = payload["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["requested_report_date"] == "2026-06-15"
    assert meta["resolved_report_date"] == "2026-05-31"
    assert meta["as_of_date"] == "2026-05-31"
    assert meta["fallback_date"] == "2026-05-31"
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["date_basis"] == "formal_report_date_cutoff"
    assert meta["filters_applied"] == {"year": 2026}
    assert meta["tables_used"] == ["fact_formal_pnl_fi"]
    assert meta["source_surface"] == "formal_pnl"


def test_pnl_by_business_ytd_rechecks_precompute_before_each_request(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    pnl_service.clear_pnl_by_business_ytd_cache()
    calls: list[dict[str, object]] = []
    fetches: list[dict[str, object]] = []

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            return "2025-12-31"

        def formal_pnl_ytd_has_rows(self, *, year, as_of_date):
            return True

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            pass

    def fake_uncached(**kwargs):
        calls.append(kwargs)
        return {"result": {"call_count": len(calls)}}

    monkeypatch.setattr(pnl_service, "_pnl_by_business_ytd_from_formal_facts", fake_uncached)
    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "get_settings",
        lambda: SimpleNamespace(pnl_by_business_ytd_prefer_formal_facts=True),
    )
    monkeypatch.setattr(
        pnl_service,
        "_fetch_pnl_by_business_precompute",
        lambda _repo, **kwargs: fetches.append(kwargs) or None,
    )

    first = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        as_of_date="2025-12-31",
    )
    second = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        as_of_date="2025-12-31",
    )

    assert first["result"]["call_count"] == 1
    assert second["result"]["call_count"] == 2
    assert len(fetches) == 2
    assert len(calls) == 2
    pnl_service.clear_pnl_by_business_ytd_cache()


def test_adb_comparison_runtime_cache_reuses_same_arguments(monkeypatch):
    adb_service = load_module("backend.app.services.adb_analysis_service", "backend/app/services/adb_analysis_service.py")
    adb_service.clear_adb_comparison_cache()
    calls: list[tuple[str, str, int]] = []

    def fake_uncached(start_date, end_date, top_n=20):
        calls.append((start_date, end_date, top_n))
        return {"result": {"call_count": len(calls)}}

    monkeypatch.setattr(adb_service, "_adb_comparison_envelope_uncached", fake_uncached)

    first = adb_service.adb_comparison_envelope("2025-01-01", "2025-12-31", top_n=200)
    second = adb_service.adb_comparison_envelope("2025-01-01", "2025-12-31", top_n=200)

    assert first == second
    assert first["result"]["call_count"] == 1
    assert calls == [("2025-01-01", "2025-12-31", 200)]
    adb_service.clear_adb_comparison_cache()


def test_pnl_refresh_serializes_decimal_rows_before_queue_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    source_service = load_module(
        "backend.app.services.pnl_source_service",
        "backend/app/services/pnl_source_service.py",
    )

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: source_service.PnlRefreshInput(
            report_date="2026-02-28",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2026-02-28",
                    "instrument_code": "240001.IB",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "invest_type_raw": "交易性金融资产",
                    "interest_income_514": Decimal("12.34"),
                    "fair_value_change_516": Decimal("-5.67"),
                    "capital_gain_517": Decimal("1.00"),
                    "manual_adjustment": Decimal("0"),
                    "currency_basis": "CNY",
                    "source_version": "sv_decimal",
                    "rule_version": "rv_decimal",
                    "ingest_batch_id": "ib_decimal",
                    "trace_id": "trace-decimal",
                }
            ],
            nonstd_rows_by_type={
                "516": [
                    {
                        "voucher_date": "2026-02-28",
                        "account_code": "51601010004",
                        "asset_code": "240001.IB",
                        "portfolio_name": "FI Desk",
                        "cost_center": "CC100",
                        "dc_flag": "credit",
                        "event_type": "mtm",
                        "raw_amount": Decimal("8.90"),
                        "source_file": "nonstd-516.xlsx",
                        "source_version": "sv_decimal_nonstd",
                        "rule_version": "rv_decimal",
                        "ingest_batch_id": "ib_decimal",
                        "trace_id": "trace-decimal-nonstd",
                    }
                ]
            },
        ),
    )
    dispatched: list[dict[str, object]] = []

    def fake_send(**kwargs):
        json.dumps(kwargs)
        dispatched.append(kwargs)

    monkeypatch.setattr(pnl_service.materialize_pnl_facts, "send", fake_send)

    payload = pnl_service.refresh_pnl(get_settings())

    assert payload["status"] == "queued"
    assert dispatched[0]["fi_rows"][0]["interest_income_514"] == "12.34"
    assert dispatched[0]["nonstd_rows_by_type"]["516"][0]["raw_amount"] == "8.90"
    get_settings.cache_clear()


def test_pnl_overview_service_consumes_pnl_vs_ledger_reconciliation_check():
    service_module = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    check = service_module._pnl_overview_reconciliation_check(
        {
            "interest_income_514": Decimal("10"),
            "fair_value_change_516": Decimal("-2"),
            "capital_gain_517": Decimal("3"),
            "manual_adjustment": Decimal("1"),
            "total_pnl": Decimal("12"),
        }
    )

    assert check == {
        "pnl_total": 12.0,
        "ledger_pnl_total": 12.0,
        "diff": 0.0,
        "breached": False,
        "missing_keys": [],
    }


def test_pnl_overview_reconciliation_check_flags_inconsistent_total():
    service_module = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    check = service_module._pnl_overview_reconciliation_check(
        {
            "interest_income_514": Decimal("10"),
            "fair_value_change_516": Decimal("-2"),
            "capital_gain_517": Decimal("3"),
            "manual_adjustment": Decimal("1"),
            "total_pnl": Decimal("11"),
        }
    )

    assert check["breached"] is True
    assert check["diff"] == -1.0


def test_pnl_by_business_traces_formal_fi_to_zqtz_business_type_primary(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business"
    result = payload["result"]
    assert result["report_date"] == "2025-12-31"
    assert result["source_tables"] == [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
    ]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert by_business["bond-trading"]["total_pnl"] == "111.50"
    assert by_business["bond-trading"]["capital_gain_517"] == "1.75"
    assert by_business["bond-trading"]["scale_amount"] == "1099.00"
    assert by_business["bond-trading"]["yield_pct"] == "10.145587"
    assert by_business["bond-trading"]["pnl_row_count"] == 2
    assert by_business["bond-allocation"]["total_pnl"] == "10.00"
    assert by_business["bond-allocation"]["scale_amount"] == "300.00"
    assert by_business["H"]["total_pnl"] == "4.00"
    assert by_business["H"]["scale_amount"] == "0.00"
    assert by_business["H"]["yield_pct"] is None
    assert result["summary"]["total_pnl"] == "125.50"
    assert result["summary"]["traced_pnl_row_count"] == 3
    assert result["summary"]["untraced_pnl_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_summary_column_totals_match_detail_rows(tmp_path, monkeypatch):
    """summary 的 514/516/517 分列合计必须与同一批明细行逐列求和一致（同源，无独立口径）。"""
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        # 514/516/517 归并边界样例：负的 516、非零手工调整，且该行未被余额追溯。
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'MERGE-EDGE.IB', 'FI Desk', 'CC998', 'A', 'FVTPL', 'CNY',
              6.00, -9.25, 0.50, 1.75, -1.00,
              'fi-merge-edge-v1', 'rv_pnl_phase2_materialize_v1', 'ib-merge-edge', 'trace-fi-merge-edge'
            )
            """
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    rows = result["rows"]
    summary = result["summary"]
    assert len(rows) >= 2
    for summary_field, row_field in [
        ("interest_income_514", "interest_income_514"),
        ("fair_value_change_516", "fair_value_change_516"),
        ("capital_gain_517", "capital_gain_517"),
        ("manual_adjustment", "manual_adjustment"),
        ("total_pnl", "total_pnl"),
        ("total_scale_amount", "scale_amount"),
    ]:
        assert Decimal(summary[summary_field]) == sum(
            (Decimal(row[row_field]) for row in rows), Decimal("0")
        ), summary_field
    assert summary["pnl_row_count"] == sum(row["pnl_row_count"] for row in rows)
    # 分列合计求和后应回收敛到 total_pnl（514 + 516 + 517 + 手工调整 = 合计损益）。
    assert Decimal(summary["total_pnl"]) == (
        Decimal(summary["interest_income_514"])
        + Decimal(summary["fair_value_change_516"])
        + Decimal(summary["capital_gain_517"])
        + Decimal(summary["manual_adjustment"])
    )
    # 边界样例行确实进入了明细与合计（负 516 / 非零手工调整未被吞掉）。
    assert any(Decimal(row["fair_value_change_516"]) < 0 for row in rows)
    assert any(Decimal(row["manual_adjustment"]) != 0 for row in rows)
    get_settings.cache_clear()


def test_pnl_by_business_allows_cost_center_relaxed_trace_after_strict_miss(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'CCRELAX.IB', 'FI Desk', 'CC-PNL', 'A', 'FVOCI', 'CNY',
              15.00, 0.00, 0.00, 0.00, 15.00,
              'fi-relaxed-v1', 'rv_pnl_phase2_materialize_v1', 'ib-relaxed', 'trace-fi-relaxed'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'CCRELAX.IB', 'FI Desk', 'CC-BAL', 'bond-relaxed',
              'A', 'FVOCI', 'asset', 'CNY', 'CNY',
              150.00000000, 150.00000000, 0.00000000, false,
              'sv-z-relaxed', 'rv-z-relaxed', 'ib-z-relaxed', 'trace-z-relaxed'
            )
            """
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert by_business["bond-relaxed"]["total_pnl"] == "15.00"
    assert by_business["bond-relaxed"]["scale_amount"] == "150.00"
    assert by_business["bond-relaxed"]["balance_row_count"] == 1
    assert result["summary"]["untraced_pnl_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_uses_relaxed_balance_amount_when_strict_business_type_is_blank(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'CCBLANK.IB', 'FI Desk', 'CC-PNL', 'A', 'FVOCI', 'CNY',
              20.00, 0.00, 0.00, 0.00, 20.00,
              'fi-relaxed-blank-v1', 'rv_pnl_phase2_materialize_v1', 'ib-relaxed-blank', 'trace-fi-relaxed-blank'
            )
            """
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "CCBLANK.IB",
                    "FI Desk",
                    "CC-PNL",
                    "",
                    "A",
                    "FVOCI",
                    "asset",
                    "CNY",
                    "CNY",
                    "999.00000000",
                    "999.00000000",
                    "0.00000000",
                    False,
                    "sv-z-strict-blank",
                    "rv-z-strict-blank",
                    "ib-z-strict-blank",
                    "trace-z-strict-blank",
                ),
                (
                    "2025-12-31",
                    "CCBLANK.IB",
                    "FI Desk",
                    "CC-BAL",
                    "bond-relaxed-blank",
                    "A",
                    "FVOCI",
                    "asset",
                    "CNY",
                    "CNY",
                    "250.00000000",
                    "250.00000000",
                    "0.00000000",
                    False,
                    "sv-z-relaxed-blank",
                    "rv-z-relaxed-blank",
                    "ib-z-relaxed-blank",
                    "trace-z-relaxed-blank",
                ),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert by_business["bond-relaxed-blank"]["total_pnl"] == "20.00"
    assert by_business["bond-relaxed-blank"]["scale_amount"] == "250.00"
    assert by_business["bond-relaxed-blank"]["balance_row_count"] == 1
    assert result["summary"]["untraced_pnl_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_keeps_ambiguous_relaxed_trace_untraced(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'CCAMBIG.IB', 'FI Desk', 'CC-PNL', 'A', 'FVOCI', 'CNY',
              30.00, 0.00, 0.00, 0.00, 30.00,
              'fi-relaxed-ambiguous-v1', 'rv_pnl_phase2_materialize_v1', 'ib-relaxed-ambiguous',
              'trace-fi-relaxed-ambiguous'
            )
            """
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "CCAMBIG.IB",
                    "FI Desk",
                    "CC-BAL-A",
                    "bond-relaxed-ambiguous-a",
                    "A",
                    "FVOCI",
                    "asset",
                    "CNY",
                    "CNY",
                    "100.00000000",
                    "100.00000000",
                    "0.00000000",
                    False,
                    "sv-z-relaxed-ambiguous-a",
                    "rv-z-relaxed-ambiguous-a",
                    "ib-z-relaxed-ambiguous-a",
                    "trace-z-relaxed-ambiguous-a",
                ),
                (
                    "2025-12-31",
                    "CCAMBIG.IB",
                    "FI Desk",
                    "CC-BAL-B",
                    "bond-relaxed-ambiguous-b",
                    "A",
                    "FVOCI",
                    "asset",
                    "CNY",
                    "CNY",
                    "900.00000000",
                    "900.00000000",
                    "0.00000000",
                    False,
                    "sv-z-relaxed-ambiguous-b",
                    "rv-z-relaxed-ambiguous-b",
                    "ib-z-relaxed-ambiguous-b",
                    "trace-z-relaxed-ambiguous-b",
                ),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert "bond-relaxed-ambiguous-a" not in by_business
    assert "bond-relaxed-ambiguous-b" not in by_business
    assert by_business["A"]["total_pnl"] == "30.00"
    assert by_business["A"]["scale_amount"] == "0.00"
    assert by_business["A"]["balance_row_count"] == 0
    assert result["summary"]["traced_pnl_row_count"] == 3
    assert result["summary"]["untraced_pnl_row_count"] == 2
    breakdown = {
        (row["reason_code"], row["invest_type_std"]): row
        for row in result["summary"]["untraced_breakdown"]
    }
    assert breakdown[("same_day_balance_multiple_primary_types", "A")]["pnl_row_count"] == 1
    assert breakdown[("same_day_balance_multiple_primary_types", "A")]["total_pnl"] == "30.00"
    get_settings.cache_clear()


def test_pnl_by_business_summarizes_untraced_balance_evidence(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', ?, 'FI Desk', ?, ?, 'FVOCI', 'CNY',
              ?, ?, 0.00, 0.00, ?,
              'fi-untraced-evidence-v1', 'rv_pnl_phase2_materialize_v1', 'ib-untraced-evidence', ?
            )
            """,
            [
                ("HIST-FUT.IB", "CC-HIST", "A", "30.00", "0.00", "30.00", "trace-fi-hist-future"),
                ("HIST-MATURED.IB", "CC-MATURED", "T", "0.00", "-5.00", "-5.00", "trace-fi-hist-matured"),
                ("NEVER-ZQTZ.IB", "CC-NEVER", "A", "7.00", "0.00", "7.00", "trace-fi-never"),
            ],
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, maturity_date, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, 'FI Desk', ?, ?, ?, 'FVOCI', 'asset', 'CNY', 'CNY',
              ?, ?, 0.00000000, ?, false,
              'sv-z-historical', 'rv-z-historical', 'ib-z-historical', ?
            )
            """,
            [
                (
                    "2025-11-30",
                    "HIST-FUT.IB",
                    "CC-HIST",
                    "bond-historical",
                    "A",
                    "300.00000000",
                    "300.00000000",
                    "2026-06-30",
                    "trace-z-hist-future",
                ),
                (
                    "2025-11-30",
                    "HIST-MATURED.IB",
                    "CC-MATURED",
                    "bond-matured",
                    "T",
                    "200.00000000",
                    "200.00000000",
                    "2025-12-01",
                    "trace-z-hist-matured",
                ),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["summary"]["untraced_pnl_row_count"] == 4
    breakdown = {
        (row["reason_code"], row["invest_type_std"]): row
        for row in result["summary"]["untraced_breakdown"]
    }
    assert breakdown[("position_absent_before_maturity", "A")]["pnl_row_count"] == 1
    assert breakdown[("position_absent_before_maturity", "A")]["total_pnl"] == "30.00"
    assert breakdown[("matured_before_or_on_report_date", "T")]["pnl_row_count"] == 1
    assert breakdown[("matured_before_or_on_report_date", "T")]["total_pnl"] == "-5.00"
    assert breakdown[("matured_before_or_on_report_date", "T")]["abs_pnl"] == "5.00"
    assert breakdown[("never_seen_in_zqtz_asset_balance", "A")]["pnl_row_count"] == 1
    assert breakdown[("never_seen_in_zqtz_asset_balance", "A")]["total_pnl"] == "7.00"
    assert breakdown[("never_seen_in_zqtz_asset_balance", "H")]["total_pnl"] == "4.00"
    get_settings.cache_clear()


def test_pnl_by_business_ytd_total_matches_formal_fact_rollups(tmp_path, monkeypatch):
    """默认 formal 路径：YTD 总损益应等于 FI + nonstd 桥接在 as_of 前的累计（与物化口径一致）。"""
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    result = payload["result"]
    repo_mod = load_module("backend.app.repositories.pnl_repo", "backend/app/repositories/pnl_repo.py")
    repo = repo_mod.PnlRepository(str(duckdb_path))
    expected = repo.sum_formal_total_pnl_through_report_date("2025-12-31") + repo.sum_nonstd_bridge_total_pnl_through_report_date(
        "2025-12-31"
    )
    assert Decimal(str(result["total_pnl"])) == expected.quantize(Decimal("0.01"))
    assert result["period_start_date"] == "2025-12-01"
    assert result["period_end_date"] == "2025-12-31"
    assert "fact_formal_pnl_fi" in result["source_tables"]
    get_settings.cache_clear()


def test_analysis_classification_uses_formal_source_metadata_when_position_is_absent() -> None:
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    classification = pnl_service._analysis_classification_for_pnl_row(
        pnl_row={
            "source_kind": "formal_fi",
            "report_date": "2026-03-31",
            "instrument_code": "2605287",
            "instrument_name": "26山东债19",
            "asset_class": "地方政府债券",
            "portfolio_name": "FIOA",
            "cost_center": "50101002",
            "currency_basis": "CNY",
            "invest_type_std": "A",
            "accounting_basis": "FVOCI",
        },
        balance_lookup={},
        historical_balance_lookup={},
        sub_type_by_date_code={},
        fallback_date="2026-03-31",
    )
    matched_keys = {
        str(row["row_key"])
        for row in pnl_service.match_zqtz_asset_bond_rows(classification)
    }

    assert "asset_zqtz_local_government_bond" in matched_keys


def test_pnl_by_business_ytd_returns_backend_owned_yield_and_ftp_fields(monkeypatch, tmp_path):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    policy_type = str(row_defs["asset_zqtz_policy_financial_bond"]["match_keywords"][0])
    if hasattr(pnl_service, "clear_pnl_by_business_ytd_cache"):
        pnl_service.clear_pnl_by_business_ytd_cache()

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-02-28"}
            return "2025-02-28"

        def formal_pnl_ytd_has_rows(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-02-28")
            return True

        def require_current_formal_pnl_rule_version(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-02-28")

        def list_union_report_dates(self):
            return ["2025-01-31", "2025-02-28"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-02-28")
            base = {
                "source_kind": "formal_fi",
                "instrument_code": "P001",
                "portfolio_name": "Rate Desk",
                "cost_center": "CC-RATE",
                "currency_basis": "CNY",
                "invest_type_std": policy_type,
                "accounting_basis": "FVTPL",
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "manual_adjustment": Decimal("0.00"),
            }
            return [
                {
                    **base,
                    "report_date": "2025-01-31",
                    "interest_income_514": Decimal("100.00"),
                    "total_pnl": Decimal("100.00"),
                },
                {
                    **base,
                    "report_date": "2025-02-28",
                    "interest_income_514": Decimal("200.00"),
                    "total_pnl": Decimal("200.00"),
                },
                {
                    **base,
                    "report_date": "2025-02-28",
                    "instrument_code": "UNALLOCATED-A",
                    "portfolio_name": "Unmapped Desk",
                    "cost_center": "CC-UNMAPPED",
                    "invest_type_std": "A",
                    "interest_income_514": Decimal("7.00"),
                    "total_pnl": Decimal("7.00"),
                },
                {
                    **base,
                    "report_date": "2025-02-28",
                    "instrument_code": "UNALLOCATED-A-NEG",
                    "portfolio_name": "Unmapped Desk",
                    "cost_center": "CC-UNMAPPED",
                    "invest_type_std": "A",
                    "interest_income_514": Decimal("-2.00"),
                    "total_pnl": Decimal("-2.00"),
                },
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert (start_date, end_date) == ("2025-01-01", "2025-02-28")
            base = {
                "instrument_code": "P001",
                "instrument_name": "policy bond",
                "portfolio_name": "Rate Desk",
                "cost_center": "CC-RATE",
                "account_category": "asset",
                "asset_class": policy_type,
                "bond_type": policy_type,
                "sub_type": policy_type,
                "business_type_primary": policy_type,
                "business_type_final": policy_type,
                "invest_type_std": "T",
                "accounting_basis": "FVTPL",
                "position_scope": "asset",
                "currency_basis": "CNY",
                "currency_code": "CNY",
            }
            return [
                {
                    **base,
                    "report_date": "2025-01-31",
                    "avg_amount": Decimal("1000.00"),
                    "current_amount": Decimal("1100.00"),
                },
                {
                    **base,
                    "report_date": "2025-02-28",
                    "avg_amount": Decimal("2000.00"),
                    "current_amount": Decimal("2200.00"),
                },
            ]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path="fake.duckdb",
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        as_of_date="2025-02-28",
    )

    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    by_key = {item["row_key"]: item for item in payload["result"]["items"]}
    row = by_key["asset_zqtz_policy_financial_bond"]
    assert set(row) >= {
        "avg_balance",
        "annualized_yield_pct",
        "ftp_rate_pct",
        "ftp_cost",
        "ftp_net_pnl",
        "ftp_net_annualized_yield_pct",
    }
    assert row["total_pnl"] == "300.00"
    assert row["avg_balance"] == "1500.00"
    assert row["current_balance"] == "2200.00"
    assert row["annualized_yield_pct"] == "123.728814"
    assert row["ftp_rate_pct"] == "1.750000"
    assert row["ftp_cost"] == "4.24"
    assert row["ftp_net_pnl"] == "295.76"
    result = payload["result"]
    assert result["total_pnl"] == "305.00"
    assert result["coverage_days"] == 2
    assert result["expected_days"] == 59
    assert result["sample_filled"] is True
    assert result["sample_fill_method"] == "observed_days_scaled_to_calendar"
    assert result["classified_parent_total_pnl"] == "300.00"
    assert result["summary"] == {
        "interest_income": "300.00",
        "fair_value_change": "0.00",
        "capital_gain": "0.00",
        "manual_adjustment": "0.00",
        "total_pnl": "300.00",
        "avg_balance": "1500.00",
        "current_balance": "2200.00",
        "annualized_yield_pct": "123.728814",
        "ftp_rate_pct": "1.750000",
        "ftp_cost": "4.24",
        "ftp_net_pnl": "295.76",
        "ftp_net_annualized_yield_pct": "121.978814",
        "proportion": "0.983607",
        "assets_count": 1,
    }
    assert result["unallocated_pnl"] == "5.00"
    assert result["unallocated_abs_pnl"] == "9.00"
    assert result["unallocated_row_count"] == 2
    assert result["reconciliation_delta"] == "0.00"
    assert result["unallocated_breakdown"] == [
        {
            "reason_code": "no_business_rule_match",
            "source_kind": "formal_fi",
            "invest_type_std": "A",
            "accounting_basis": "FVTPL",
            "portfolio_name": "Unmapped Desk",
            "cost_center": "CC-UNMAPPED",
            "pnl_row_count": 2,
            "total_pnl": "5.00",
            "abs_pnl": "9.00",
            "sample_instrument_codes": ["UNALLOCATED-A", "UNALLOCATED-A-NEG"],
        }
    ]
    assert result["unallocated_items"] == [
        {
            "report_date": "2025-02-28",
            "reason_code": "no_business_rule_match",
            "source_kind": "formal_fi",
            "instrument_code": "UNALLOCATED-A",
            "portfolio_name": "Unmapped Desk",
            "cost_center": "CC-UNMAPPED",
            "invest_type_std": "A",
            "accounting_basis": "FVTPL",
            "currency_basis": "CNY",
            "interest_income_514": "7.00",
            "fair_value_change_516": "0.00",
            "capital_gain_517": "0.00",
            "manual_adjustment": "0.00",
            "total_pnl": "7.00",
            "abs_pnl": "7.00",
        },
        {
            "report_date": "2025-02-28",
            "reason_code": "no_business_rule_match",
            "source_kind": "formal_fi",
            "instrument_code": "UNALLOCATED-A-NEG",
            "portfolio_name": "Unmapped Desk",
            "cost_center": "CC-UNMAPPED",
            "invest_type_std": "A",
            "accounting_basis": "FVTPL",
            "currency_basis": "CNY",
            "interest_income_514": "-2.00",
            "fair_value_change_516": "0.00",
            "capital_gain_517": "0.00",
            "manual_adjustment": "0.00",
            "total_pnl": "-2.00",
            "abs_pnl": "2.00",
        },
    ]
    assert row["ftp_net_annualized_yield_pct"] == "121.978814"
    if hasattr(pnl_service, "clear_pnl_by_business_ytd_cache"):
        pnl_service.clear_pnl_by_business_ytd_cache()


def test_pnl_by_business_ytd_reconciliation_delta_is_independently_derived():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_def = next(
        row
        for row in category_module.ZQTZ_ASSET_BOND_ROWS
        if str(row["row_key"]) == "asset_zqtz_policy_financial_bond"
    )
    group = pnl_service._new_balance_movement_pnl_group(row_def)
    pnl_service._merge_balance_movement_business_record(
        {str(row_def["row_key"]): group},
        row_def,
        {
            "bond_code": "PARENT-1",
            "interest_income": Decimal("4.00"),
            "fair_value_change": Decimal("0"),
            "capital_gain": Decimal("0"),
            "manual_adjustment": Decimal("0"),
            "total_pnl": Decimal("4.00"),
        },
    )

    payload = pnl_service._build_pnl_by_business_ytd_payload_from_groups(
        year=2025,
        loaded_dates=["2025-01-31"],
        total_pnl=Decimal("10.00"),
        groups={str(row_def["row_key"]): group},
        duckdb_path="unused.duckdb",
        source_tables=["test_source"],
        ftp_rate_pct=Decimal("0"),
        balance_rows=[],
        unallocated_items=[
            {
                "report_date": "2025-01-31",
                "reason_code": "no_business_rule_match",
                "source_kind": "formal_fi",
                "instrument_code": "UNALLOCATED-1",
                "portfolio_name": "Unmapped Desk",
                "cost_center": "CC-UNMAPPED",
                "invest_type_std": "A",
                "accounting_basis": "FVTPL",
                "currency_basis": "CNY",
                "interest_income_514": Decimal("5.00"),
                "fair_value_change_516": Decimal("0"),
                "capital_gain_517": Decimal("0"),
                "manual_adjustment": Decimal("0"),
                "total_pnl": Decimal("5.00"),
                "abs_pnl": Decimal("5.00"),
            }
        ],
    )

    assert payload.classified_parent_total_pnl == Decimal("4.00")
    assert payload.unallocated_pnl == Decimal("5.00")
    assert payload.reconciliation_delta == Decimal("1.00")


def test_pnl_by_business_ytd_aggregates_unallocated_before_rounding():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    precise_items = [
        {
            "report_date": "2025-01-31",
            "reason_code": "no_business_rule_match",
            "source_kind": "formal_fi",
            "instrument_code": f"UNALLOCATED-{index}",
            "portfolio_name": "Unmapped Desk",
            "cost_center": "CC-UNMAPPED",
            "invest_type_std": "",
            "accounting_basis": "",
            "currency_basis": "CNY",
            "interest_income_514": Decimal("0.004"),
            "fair_value_change_516": Decimal("0"),
            "capital_gain_517": Decimal("0"),
            "manual_adjustment": Decimal("0"),
            "total_pnl": Decimal("0.004"),
            "abs_pnl": Decimal("0.004"),
        }
        for index in range(2)
    ]

    payload = pnl_service._build_pnl_by_business_ytd_payload_from_groups(
        year=2025,
        loaded_dates=["2025-01-31"],
        total_pnl=Decimal("0.008"),
        groups={},
        duckdb_path="unused.duckdb",
        source_tables=["test_source"],
        ftp_rate_pct=Decimal("0"),
        balance_rows=[],
        unallocated_items=precise_items,
    )

    assert payload.total_pnl == Decimal("0.01")
    assert payload.unallocated_pnl == Decimal("0.01")
    assert payload.unallocated_abs_pnl == Decimal("0.01")
    assert payload.reconciliation_delta == Decimal("0.00")


def test_pnl_by_business_ytd_reconciles_precise_aggregates_before_rounding():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_def = next(
        row for row in category_module.ZQTZ_ASSET_BOND_ROWS if str(row["row_key"]) == "asset_zqtz_foreign_bond"
    )
    group = pnl_service._new_balance_movement_pnl_group(row_def)
    pnl_service._merge_balance_movement_business_record(
        {str(row_def["row_key"]): group},
        row_def,
        {
            "bond_code": "PARENT-PRECISION",
            "interest_income": Decimal("0"),
            "fair_value_change": Decimal("0"),
            "capital_gain": Decimal("0"),
            "manual_adjustment": Decimal("0.004"),
            "total_pnl": Decimal("0.004"),
        },
    )
    unallocated_item = {
        "report_date": "2025-01-31",
        "reason_code": "no_business_rule_match",
        "source_kind": "formal_fi",
        "instrument_code": "UNALLOCATED-PRECISION",
        "portfolio_name": "Unmapped Desk",
        "cost_center": "CC-UNMAPPED",
        "invest_type_std": "",
        "accounting_basis": "",
        "currency_basis": "CNY",
        "interest_income_514": Decimal("0.004"),
        "fair_value_change_516": Decimal("0"),
        "capital_gain_517": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0.004"),
        "abs_pnl": Decimal("0.004"),
    }

    payload = pnl_service._build_pnl_by_business_ytd_payload_from_groups(
        year=2025,
        loaded_dates=["2025-01-31"],
        total_pnl=Decimal("0.008"),
        groups={str(row_def["row_key"]): group},
        duckdb_path="unused.duckdb",
        source_tables=["test_source"],
        ftp_rate_pct=Decimal("0"),
        balance_rows=[],
        unallocated_items=[unallocated_item],
    )

    assert payload.total_pnl == Decimal("0.01")
    assert payload.classified_parent_total_pnl == Decimal("0.00")
    assert payload.unallocated_pnl == Decimal("0.00")
    assert payload.reconciliation_delta == Decimal("0.00")


def test_pnl_by_business_ytd_summary_aggregates_parent_amounts_before_rounding():
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = [
        row
        for row in category_module.ZQTZ_ASSET_BOND_ROWS
        if category_module.is_parent_zqtz_business_row(
            str(row["row_key"]),
            str(row["row_label"]),
            row.get("source_note"),
        )
    ][:2]
    groups = {}
    for index, row_def in enumerate(row_defs):
        group = pnl_service._new_balance_movement_pnl_group(row_def)
        groups[str(row_def["row_key"])] = group
        pnl_service._merge_balance_movement_business_record(
            groups,
            row_def,
            {
                "bond_code": f"PARENT-PRECISION-{index}",
                "interest_income": Decimal("0.006"),
                "fair_value_change": Decimal("0"),
                "capital_gain": Decimal("0"),
                "manual_adjustment": Decimal("0"),
                "total_pnl": Decimal("0.006"),
            },
        )

    payload = pnl_service._build_pnl_by_business_ytd_payload_from_groups(
        year=2025,
        loaded_dates=["2025-01-31"],
        total_pnl=Decimal("0.012"),
        groups=groups,
        duckdb_path="unused.duckdb",
        source_tables=["test_source"],
        ftp_rate_pct=Decimal("0"),
        balance_rows=[],
        unallocated_items=[],
    )

    assert payload.classified_parent_total_pnl == Decimal("0.01")
    assert payload.summary.interest_income == Decimal("0.01")
    assert payload.summary.total_pnl == Decimal("0.01")


def test_pnl_by_business_ytd_classifies_each_report_month_before_accumulating(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    commercial_type = classification["commercial_type"]
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fact_formal_pnl_fi where substr(cast(report_date as varchar), 1, 4) = '2025'")
        conn.execute("delete from fact_nonstd_pnl_bridge where substr(cast(report_date as varchar), 1, 4) = '2025'")
        conn.execute(
            "delete from fact_formal_zqtz_balance_daily where substr(cast(report_date as varchar), 1, 4) = '2025'"
        )
        conn.executemany(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, 'SWITCH001', 'Financial Desk', 'CC-SWITCH', 'T', 'FVTPL', 'CNY',
              ?, 0.00, 0.00, 0.00, ?,
              'fi-switch-v1', 'rv_pnl_phase2_materialize_v1', 'ib-switch', ?
            )
            """,
            [
                ("2025-01-31", "100.00", "100.00", "trace-switch-jan"),
                ("2025-02-28", "200.00", "200.00", "trace-switch-feb"),
            ],
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-01-31', 'FUTURE001', 'Future Desk', 'CC-FUTURE', 'T', 'FVTPL', 'CNY',
              0.07, 0.00, 0.00, 0.00, 0.07,
              'fi-future-v1', 'rv_pnl_phase2_materialize_v1', 'ib-future', 'trace-future-jan'
            )
            """
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, 'SWITCH001', 'switching instrument', 'Financial Desk', 'CC-SWITCH',
              'asset', ?, ?, ?, ?,
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              ?, ?, 0.00000000, false,
              'sv-switch-zqtz', 'rv-switch-zqtz', 'ib-switch-zqtz', ?
            )
            """,
            [
                (
                    "2025-01-31",
                    commercial_type,
                    commercial_type,
                    commercial_type,
                    commercial_type,
                    "1000.00000000",
                    "1000.00000000",
                    "trace-switch-zqtz-jan",
                ),
                (
                    "2025-02-28",
                    "同业存单",
                    "同业存单",
                    "同业存单",
                    "同业存单",
                    "2000.00000000",
                    "2000.00000000",
                    "trace-switch-zqtz-feb",
                ),
            ],
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-02-28', 'FUTURE001', 'future-only classification', 'Future Desk', 'CC-FUTURE',
              'asset', ?, ?, ?, ?,
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              3000.00000000, 3000.00000000, 0.00000000, false,
              'sv-future-zqtz', 'rv-future-zqtz', 'ib-future-zqtz', 'trace-future-zqtz-feb'
            )
            """,
            [commercial_type, commercial_type, commercial_type, commercial_type],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-02-28"})
    monthly_response = client.get("/api/pnl/by-business-monthly", params={"year": 2025, "as_of_date": "2025-02-28"})

    assert ytd_response.status_code == 200
    assert monthly_response.status_code == 200
    ytd_by_key = {item["row_key"]: item for item in ytd_response.json()["result"]["items"]}
    ytd_result = ytd_response.json()["result"]
    monthly_result = monthly_response.json()["result"]
    monthly_totals: dict[str, Decimal] = {}
    for month in monthly_response.json()["result"]["months"]:
        for item in month["items"]:
            monthly_totals[item["row_key"]] = monthly_totals.get(item["row_key"], Decimal("0")) + Decimal(
                item["total_pnl"]
            )

    assert ytd_by_key["asset_zqtz_commercial_financial_bond"]["total_pnl"] == "100.00"
    assert ytd_by_key["asset_zqtz_interbank_cd"]["total_pnl"] == "200.00"
    assert Decimal(ytd_by_key["asset_zqtz_commercial_financial_bond"]["total_pnl"]) == monthly_totals[
        "asset_zqtz_commercial_financial_bond"
    ]
    assert Decimal(ytd_by_key["asset_zqtz_interbank_cd"]["total_pnl"]) == monthly_totals["asset_zqtz_interbank_cd"]
    monthly_unallocated_items = [
        item for month in monthly_result["months"] for item in month["unallocated_items"]
    ]
    assert [item["instrument_code"] for item in ytd_result["unallocated_items"]] == [
        item["instrument_code"] for item in monthly_unallocated_items
    ]
    assert ytd_result["unallocated_pnl"] == "0.07"
    assert ytd_result["unallocated_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_ytd_rejects_stale_2026_h1_formal_facts(monkeypatch) -> None:
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2026
            return "2026-06-30"

        def formal_pnl_ytd_has_rows(self, *, year, as_of_date):
            assert (year, as_of_date) == (2026, "2026-06-30")
            return True

        def require_current_formal_pnl_rule_version(self, **_kwargs):
            raise RuntimeError(
                "Formal pnl facts contain stale rule versions: rv_pnl_phase2_materialize_v1"
            )

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(pnl_service, "_ensure_formal_pnl_storage_available", lambda _path: None)
    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_from_formal_facts",
        lambda **_kwargs: {"stale": True},
    )

    with pytest.raises(RuntimeError, match="stale rule versions"):
        pnl_service._pnl_by_business_ytd_envelope_uncached(
            duckdb_path="unused.duckdb",
            governance_dir="unused-governance",
            year=2026,
            as_of_date="2026-06-30",
        )


def test_pnl_by_business_ytd_formal_path_classifies_nonstd_prefix_rows(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = [
            ("SA001", "20.00", "0.00", "0.00", "20.00"),
            ("G0001", "7.00", "0.00", "0.00", "7.00"),
            ("J4001", "11.00", "0.00", "0.00", "11.00"),
            ("J1001", "14.00", "0.00", "0.00", "14.00"),
            ("J02205260102", "0.00", "9.00", "0.00", "9.00"),
            ("J09999990102", "0.00", "0.00", "4.00", "4.00"),
            ("JM001", "10.00", "0.00", "0.00", "10.00"),
        ]
        conn.executemany(
            """
            insert into fact_nonstd_pnl_bridge values (
              '2025-12-31', ?, 'NonStd Desk', 'CC-PREFIX',
              ?, ?, ?, 0.00, ?,
              'sv-nonstd-prefix', 'rv_pnl_phase2_materialize_v1', 'ib-nonstd-prefix', 'tr-nonstd-prefix'
            )
            """,
            rows,
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})

    assert response.status_code == 200
    by_key = {item["row_key"]: item for item in response.json()["result"]["items"]}
    assert by_key["asset_zqtz_public_fund"]["total_pnl"] == "20.00"
    assert by_key["asset_zqtz_non_bottom_investment"]["total_pnl"] == "45.00"
    assert by_key["asset_zqtz_detail_trust_plan"]["total_pnl"] == "7.00"
    assert by_key["asset_zqtz_detail_securities_asset_management_plan"]["total_pnl"] == "38.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["total_pnl"] == "11.00"
    assert by_key["asset_zqtz_detail_foreign_currency_delegated"]["total_pnl"] == "14.00"
    assert by_key["asset_zqtz_detail_local_currency_delegated_market_value"]["total_pnl"] == "9.00"
    assert by_key["asset_zqtz_detail_local_currency_special_account_cost"]["total_pnl"] == "4.00"
    assert by_key["asset_zqtz_other_debt_financing"]["total_pnl"] == "10.00"
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_audit_tracks_current_and_events(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _grant_pnl_read_scope(UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "125.50",
            "reason": "补录估值调整",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    adjustment_id = created["adjustment_id"]
    assert created["event_type"] == "created"
    assert created["manual_adjustment"] == "125.50"
    assert created["stream"] == "pnl_by_business_adjustments"

    edit_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/edit",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "150.00",
            "reason": "复核后修正",
        },
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["event_type"] == "edited"

    list_response = client.get(
        "/api/pnl/by-business/manual-adjustments",
        params={"report_date": "2025-12-31"},
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["report_date"] == "2025-12-31"
    assert payload["adjustment_count"] == 1
    assert payload["event_total"] == 2
    assert payload["adjustments"][0]["adjustment_id"] == adjustment_id
    assert payload["adjustments"][0]["event_type"] == "edited"
    assert payload["adjustments"][0]["manual_adjustment"] == "150.00"
    assert [event["event_type"] for event in payload["events"]] == ["edited", "created"]
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_active_state_changes_enqueue_precompute_refresh(
    tmp_path,
    monkeypatch,
):
    from backend.app.schemas.pnl import PnlByBusinessManualAdjustmentRequest
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    conn = duckdb.connect(settings.duckdb_path, read_only=False)
    try:
        conn.execute("create table fact_formal_pnl_fi (report_date varchar)")
        conn.execute("insert into fact_formal_pnl_fi values ('2025-12-31')")
    finally:
        conn.close()
    dispatched: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        lambda **kwargs: dispatched.append(kwargs),
    )
    payload = PnlByBusinessManualAdjustmentRequest(
        report_date="2025-12-31",
        row_key="asset_zqtz_policy_financial_bond",
        business_type="Policy Financial Bond",
        operator="DELTA",
        approval_status="approved",
        manual_adjustment="25.00",
        reason="rebuild precompute after approval state changes",
    )

    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        payload,
        created_by="maker",
    )
    adjustment_id = str(created["adjustment_id"])
    assert dispatched == []

    pnl_service.approve_pnl_by_business_manual_adjustment(
        settings,
        adjustment_id=adjustment_id,
        approved_by="checker",
    )
    assert len(dispatched) == 1
    assert dispatched[0]["duckdb_path"] == str(settings.duckdb_path)
    assert dispatched[0]["governance_dir"] == str(settings.governance_path)
    assert dispatched[0]["year"] == 2025
    assert dispatched[0]["trigger_reason"] == "manual_adjustment_state_change"
    assert str(dispatched[0]["run_id"]).startswith("pnl_by_business_precompute:")
    assert dispatched[0]["queued_at"]

    pnl_service.approve_pnl_by_business_manual_adjustment(
        settings,
        adjustment_id=adjustment_id,
        approved_by="checker",
    )
    assert len(dispatched) == 1

    pnl_service.update_pnl_by_business_manual_adjustment(
        settings,
        adjustment_id=adjustment_id,
        payload=payload.model_copy(update={"manual_adjustment": Decimal("30.00")}),
    )
    assert len(dispatched) == 1

    pnl_service.approve_pnl_by_business_manual_adjustment(
        settings,
        adjustment_id=adjustment_id,
        approved_by="checker",
    )
    assert len(dispatched) == 1

    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    first_run_id = str(dispatched[0]["run_id"])
    first_record = next(
        record
        for record in governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
        if record["run_id"] == first_run_id
    )
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **first_record,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    pnl_service.revoke_pnl_by_business_manual_adjustment(settings, adjustment_id=adjustment_id)
    assert len(dispatched) == 2

    pnl_service.revoke_pnl_by_business_manual_adjustment(settings, adjustment_id=adjustment_id)
    pnl_service.restore_pnl_by_business_manual_adjustment(settings, adjustment_id=adjustment_id)
    assert len(dispatched) == 2

    for message in dispatched:
        run_id = str(message["run_id"])
        latest_record = next(
            record
            for record in reversed(governance_repo.read_all(CACHE_BUILD_RUN_STREAM))
            if record["run_id"] == run_id
        )
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **latest_record,
                "status": "completed",
                "report_date": "2025-12-31",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def fail_dispatch(**_kwargs):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(pnl_service.rebuild_pnl_by_business_precompute, "send", fail_dispatch)
    approved_after_dispatch_failure = pnl_service.approve_pnl_by_business_manual_adjustment(
        settings,
        adjustment_id=adjustment_id,
        approved_by="checker",
    )
    assert approved_after_dispatch_failure["approval_status"] == "approved"
    current = pnl_service.list_pnl_by_business_manual_adjustments(
        settings,
        report_date="2025-12-31",
    )["adjustments"][0]
    assert current["approval_status"] == "approved"
    get_settings.cache_clear()


def test_rebuild_pnl_by_business_precompute_task_uses_latest_year_cutoff(
    tmp_path,
    monkeypatch,
):
    from backend.app.tasks import pnl_materialize

    calls: list[dict[str, object]] = []
    cache_clears: list[bool] = []

    def fake_precompute(**kwargs):
        calls.append(kwargs)
        return {
            "year": 2025,
            "as_of_date": "2025-12-31",
            "records": 118,
            "source_version": "sv-pnl-by-business-ready",
            "generated_at": "2026-07-15T12:00:00+00:00",
        }

    monkeypatch.setattr(pnl_materialize, "precompute_pnl_by_business_payloads", fake_precompute)
    monkeypatch.setattr(
        pnl_materialize,
        "_clear_pnl_page_runtime_caches",
        lambda: cache_clears.append(True),
    )

    result = pnl_materialize.run_pnl_by_business_precompute_sync(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        year=2025,
        run_id="pnl-by-business-precompute:test-ready",
        trigger_reason="manual_retry",
    )

    assert calls == [
        {
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_dir": str(tmp_path / "governance"),
                "year": 2025,
                "as_of_date": None,
            }
    ]
    assert cache_clears == [True]
    assert result == {
        "year": 2025,
        "as_of_date": "2025-12-31",
        "records": 118,
        "source_version": "sv-pnl-by-business-ready",
        "generated_at": "2026-07-15T12:00:00+00:00",
    }
    run_records = [
        record
        for record in GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
        if record["run_id"] == "pnl-by-business-precompute:test-ready"
    ]
    assert [record["status"] for record in run_records] == ["running", "completed"]
    assert run_records[-1]["report_date"] == "2025-12-31"
    assert run_records[-1]["record_count"] == 118
    assert run_records[-1]["trigger_reason"] == "manual_retry"
    assert run_records[-1]["source_version"] == "sv-pnl-by-business-ready"


def test_rebuild_pnl_by_business_precompute_task_records_failure(
    tmp_path,
    monkeypatch,
):
    from backend.app.tasks import pnl_materialize

    calls: list[str] = []
    lock_state = {"active": False, "entries": 0, "exits": 0}
    cache_clears: list[bool] = []

    class FakeLockContext:
        def __enter__(self):
            lock_state.update(active=True, entries=lock_state["entries"] + 1)
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            lock_state.update(active=False, exits=lock_state["exits"] + 1)
            return False

    def fail_precompute(**kwargs):
        assert lock_state["active"] is True
        cutoff = str(kwargs["as_of_date"])
        calls.append(cutoff)
        if cutoff == "2025-02-28":
            raise RuntimeError("precompute fixture failed")
        return {"as_of_date": cutoff, "records": 1}

    monkeypatch.setattr(pnl_materialize, "PnlRepository", _exact_cutoff_pnl_repository)
    monkeypatch.setattr(pnl_materialize, "precompute_pnl_by_business_payloads", fail_precompute)
    monkeypatch.setattr(pnl_materialize, "acquire_lock", lambda *_args, **_kwargs: FakeLockContext())
    monkeypatch.setattr(
        pnl_materialize,
        "_clear_pnl_page_runtime_caches",
        lambda: cache_clears.append(True),
    )

    with pytest.raises(RuntimeError, match="precompute fixture failed"):
        pnl_materialize.run_pnl_by_business_precompute_sync(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
            year=2025,
            as_of_dates=["2025-01-31", "2025-02-28", "2025-03-31"],
            run_id="pnl-by-business-precompute:test-failed",
            trigger_reason="manual_retry",
        )

    run_records = [
        record
        for record in GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
        if record["run_id"] == "pnl-by-business-precompute:test-failed"
    ]
    assert calls == ["2025-01-31", "2025-02-28"]
    assert lock_state == {"active": False, "entries": 1, "exits": 1}
    assert cache_clears == []
    assert [record["status"] for record in run_records] == ["running", "failed"]
    assert run_records[-1]["error_message"] == "precompute fixture failed"
    assert run_records[-1]["failure_category"] == "materialize_failure"


def test_request_pnl_by_business_precompute_rebuild_is_observable_and_deduplicated(
    tmp_path,
    monkeypatch,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    dispatched: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        lambda **kwargs: dispatched.append(kwargs),
    )

    queued = pnl_service.request_pnl_by_business_precompute_rebuild(settings, year=2025)

    assert queued["status"] == "queued"
    assert queued["serving_mode"] == "live_fallback"
    assert queued["trigger_reason"] == "manual_retry"
    assert queued["retry_policy"] == {"max_retries": 3, "min_backoff_seconds": 15}
    assert len(dispatched) == 1
    assert dispatched[0]["run_id"] == queued["run_id"]
    run_records = GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
    assert run_records[-1]["status"] == "queued"
    assert run_records[-1]["target_year"] == 2025

    with pytest.raises(pnl_service.PnlByBusinessPrecomputeConflictError):
        pnl_service.request_pnl_by_business_precompute_rebuild(settings, year=2025)
    assert len(dispatched) == 1
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("available_dates", "expected_cutoffs"),
    [
        pytest.param(
            [
                "2026-06-30",
                "2026-02-28",
                "2026-01-31",
                "2026-05-31",
                "2026-03-31",
                "2026-04-30",
                "2026-03-31",
            ],
            [
                "2026-01-31",
                "2026-02-28",
                "2026-03-31",
                "2026-04-30",
                "2026-05-31",
                "2026-06-30",
            ],
            id="current-2026-cutoffs",
        ),
        pytest.param(
            [
                "2026-06-30",
                "2026-03-31",
                "2026-03-15",
                "20260430",
                "2026-W22-7",
                "not-a-date",
                "2025-12-31",
                "2026-01-31",
                "2026-03-31",
            ],
            [
                "2026-01-31",
                "2026-03-31",
                "2026-06-30",
            ],
            id="sparse-cutoffs-ignore-invalid-values",
        ),
    ],
)
def test_request_pnl_by_business_precompute_rebuild_all_available_dispatches_exact_month_end_cutoffs(
    tmp_path,
    monkeypatch,
    available_dates,
    expected_cutoffs,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    dispatched: list[dict[str, object]] = []

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def list_union_report_dates(self):
            return available_dates

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        lambda **kwargs: dispatched.append(kwargs),
    )

    queued = pnl_service.request_pnl_by_business_precompute_rebuild(
        settings,
        year=2026,
        scope="all_available",
    )

    assert queued["scope"] == "all_available"
    assert queued["target_as_of_dates"] == expected_cutoffs
    assert queued["target_count"] == len(expected_cutoffs)
    assert len(dispatched) == 1
    assert dispatched[0]["as_of_date"] is None
    assert dispatched[0]["as_of_dates"] == expected_cutoffs
    run_records = GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
    assert run_records[-1]["target_as_of_dates"] == expected_cutoffs
    assert run_records[-1]["target_count"] == len(expected_cutoffs)
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "available_dates",
    [
        [],
        ["not-a-date", "2026-02-15", "2025-12-31"],
    ],
)
def test_request_pnl_by_business_precompute_rebuild_all_available_rejects_empty_valid_target_set(
    monkeypatch,
    available_dates,
):
    from backend.app.services import pnl_service

    settings = get_settings()

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def list_union_report_dates(self):
            return available_dates

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_queue_pnl_by_business_precompute_refresh",
        lambda *_args, **_kwargs: pytest.fail("invalid targets must not queue"),
    )

    with pytest.raises(ValueError, match="No available month-end cutoffs"):
        pnl_service.request_pnl_by_business_precompute_rebuild(
            settings,
            year=2026,
            scope="all_available",
        )


@pytest.mark.parametrize(
    ("year", "as_of_date"),
    [
        (2026, "20260630"),
        (2026, "2026-W27-2"),
        (1999, None),
        (2101, None),
    ],
)
def test_request_pnl_by_business_precompute_rebuild_rejects_noncanonical_dates_and_out_of_range_years(
    monkeypatch,
    year,
    as_of_date,
):
    from backend.app.services import pnl_service

    settings = get_settings()
    monkeypatch.setattr(
        pnl_service,
        "_queue_pnl_by_business_precompute_refresh",
        lambda *_args, **_kwargs: pytest.fail("invalid targets must not queue"),
    )

    with pytest.raises(ValueError):
        pnl_service.request_pnl_by_business_precompute_rebuild(
            settings,
            year=year,
            as_of_date=as_of_date,
        )


@pytest.mark.parametrize(
    ("year", "as_of_dates"),
    [
        (2026, ["20260630"]),
        (2026, ["2026-W27-2"]),
        (2026, ["2026-06-15"]),
        (2026, ["2025-12-31"]),
        (2026, []),
        (1999, ["1999-12-31"]),
        (2101, ["2101-12-31"]),
    ],
)
def test_rebuild_pnl_by_business_precompute_batch_rejects_invalid_date_contract(
    tmp_path,
    monkeypatch,
    year,
    as_of_dates,
):
    from backend.app.tasks import pnl_materialize

    monkeypatch.setattr(
        pnl_materialize,
        "precompute_pnl_by_business_payloads",
        lambda **_kwargs: pytest.fail("invalid targets must not precompute"),
    )

    with pytest.raises(ValueError):
        pnl_materialize.run_pnl_by_business_precompute_sync(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
            year=year,
            as_of_dates=as_of_dates,
        )


def test_rebuild_pnl_by_business_precompute_batch_accepts_leap_year_month_end():
    from backend.app.tasks import pnl_materialize

    assert pnl_materialize._normalize_pnl_by_business_precompute_target_dates(
        year=2024,
        as_of_dates=["2024-02-29"],
    ) == ["2024-02-29"]


def test_rebuild_pnl_by_business_precompute_exact_cutoff_batch_uses_one_writer_lock(
    tmp_path,
    monkeypatch,
):
    from backend.app.tasks import pnl_materialize

    calls: list[dict[str, object]] = []
    lock_state = {"active": False, "entries": 0, "exits": 0}

    class FakeLockContext:
        def __enter__(self):
            assert lock_state["active"] is False
            lock_state["active"] = True
            lock_state["entries"] += 1
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            assert lock_state["active"] is True
            lock_state["active"] = False
            lock_state["exits"] += 1
            return False

    def fake_precompute(**kwargs):
        assert lock_state["active"] is True
        calls.append(kwargs)
        as_of_date = str(kwargs["as_of_date"])
        record_count = 100 + len(calls)
        return {
            "year": 2026,
            "as_of_date": as_of_date,
            "records": record_count,
            "source_version": f"source::{as_of_date}",
            "generated_at": f"2026-07-15T12:00:0{len(calls)}+00:00",
        }

    monkeypatch.setattr(pnl_materialize, "PnlRepository", _exact_cutoff_pnl_repository)
    monkeypatch.setattr(pnl_materialize, "precompute_pnl_by_business_payloads", fake_precompute)
    monkeypatch.setattr(pnl_materialize, "acquire_lock", lambda *_args, **_kwargs: FakeLockContext())
    monkeypatch.setattr(pnl_materialize, "_clear_pnl_page_runtime_caches", lambda: None)

    result = pnl_materialize.run_pnl_by_business_precompute_sync(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        year=2026,
        as_of_dates=["2026-06-30", "2026-01-31", "2026-06-30"],
        run_id="pnl-by-business-precompute:test-exact-cutoff-batch",
        trigger_reason="manual_retry_all_available",
    )

    assert lock_state == {"active": False, "entries": 1, "exits": 1}
    assert [call["as_of_date"] for call in calls] == ["2026-01-31", "2026-06-30"]
    assert result["as_of_dates"] == ["2026-01-31", "2026-06-30"]
    assert result["cutoff_count"] == 2
    assert result["records"] == 203
    assert [item["as_of_date"] for item in result["results"]] == ["2026-01-31", "2026-06-30"]
    run_records = [
        record
        for record in GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
        if record["run_id"] == "pnl-by-business-precompute:test-exact-cutoff-batch"
    ]
    assert [record["status"] for record in run_records] == ["running", "completed"]
    assert run_records[-1]["target_as_of_dates"] == ["2026-01-31", "2026-06-30"]
    assert run_records[-1]["cutoff_count"] == 2
    assert run_records[-1]["record_count"] == 203


def test_pnl_by_business_precompute_exact_cutoff_partitions_replace_idempotently_and_stay_isolated(
    tmp_path,
):
    from backend.app.tasks.pnl_by_business_precompute import persist_pnl_by_business_precompute

    duckdb_path = tmp_path / "moss.duckdb"

    def row(cutoff, kind, marker):
        return {
            "year": 2026,
            "as_of_date": cutoff,
            "result_kind": kind,
            "dimension": "currency" if kind == "analysis" else "",
            "business_key": "",
            "payload_json": json.dumps({"marker": marker}),
            "source_version": f"source::{cutoff}::{marker}",
            "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
            "generated_at": "2026-07-16T12:00:00+00:00",
        }

    def persist(cutoff, rows):
        persist_pnl_by_business_precompute(
            duckdb_path=str(duckdb_path),
            year=2026,
            as_of_date=cutoff,
            records=rows,
        )

    def snapshot():
        with duckdb.connect(str(duckdb_path), read_only=True) as conn:
            return conn.execute(
                "select as_of_date, result_kind, payload_json "
                "from fact_pnl_by_business_precompute "
                "order by as_of_date, result_kind"
            ).fetchall()

    persist("2026-01-31", [row("2026-01-31", "monthly", "initial")])
    persist("2026-02-28", [row("2026-02-28", "monthly", "sentinel")])
    replacement = [
        row("2026-01-31", "monthly", "current"),
        row("2026-01-31", "analysis", "current"),
    ]
    persist("2026-01-31", replacement)
    first_rebuild = snapshot()
    persist("2026-01-31", replacement)
    second_rebuild = snapshot()

    assert second_rebuild == first_rebuild
    assert [(item[0], item[1], json.loads(str(item[2]))["marker"]) for item in second_rebuild] == [
        ("2026-01-31", "analysis", "current"),
        ("2026-01-31", "monthly", "current"),
        ("2026-02-28", "monthly", "sentinel"),
    ]


def test_rebuild_pnl_by_business_precompute_exact_cutoff_batch_rejects_resolved_cutoff_drift(
    tmp_path,
    monkeypatch,
):
    from backend.app.tasks import pnl_materialize

    duckdb_path = tmp_path / "moss.duckdb"
    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute("create table preflight_guard (marker varchar)")
        conn.execute("insert into preflight_guard values ('original')")
    precompute_calls: list[bool] = []

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert (year, as_of_cap) == (2026, "2026-06-30")
            return "2026-05-31"

    def fake_precompute(**kwargs):
        precompute_calls.append(True)
        with duckdb.connect(str(duckdb_path)) as conn:
            conn.execute("update preflight_guard set marker = 'mutated'")
        return {"as_of_date": kwargs["as_of_date"], "records": 1}

    monkeypatch.setattr(pnl_materialize, "PnlRepository", FakePnlRepository, raising=False)
    monkeypatch.setattr(
        pnl_materialize,
        "precompute_pnl_by_business_payloads",
        fake_precompute,
    )
    monkeypatch.setattr(pnl_materialize, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(pnl_materialize, "_clear_pnl_page_runtime_caches", lambda: None)

    with pytest.raises(RuntimeError, match="resolved source cutoff=2026-05-31.*requested cutoff=2026-06-30"):
        pnl_materialize.run_pnl_by_business_precompute_sync(
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
            year=2026,
            as_of_dates=["2026-06-30"],
        )

    assert precompute_calls == []
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert conn.execute("select marker from preflight_guard").fetchone() == ("original",)


def test_rebuild_pnl_by_business_precompute_exact_cutoff_batch_rejects_returned_cutoff_drift(
    tmp_path,
    monkeypatch,
):
    from backend.app.tasks import pnl_materialize

    run_id = "pnl-by-business-precompute:test-returned-cutoff-drift"
    preflight_calls: list[tuple[int, str]] = []
    precompute_calls: list[str] = []
    cache_clear_calls: list[bool] = []

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            preflight_calls.append((year, as_of_cap))
            return "2026-06-30"

    def fake_precompute(**kwargs):
        precompute_calls.append(str(kwargs["as_of_date"]))
        return {"as_of_date": "2026-05-31", "records": 1}

    monkeypatch.setattr(pnl_materialize, "PnlRepository", FakePnlRepository, raising=False)
    monkeypatch.setattr(
        pnl_materialize,
        "precompute_pnl_by_business_payloads",
        fake_precompute,
    )
    monkeypatch.setattr(pnl_materialize, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(
        pnl_materialize,
        "_clear_pnl_page_runtime_caches",
        lambda: cache_clear_calls.append(True),
    )

    with pytest.raises(
        RuntimeError,
        match="returned as_of_date=2026-05-31.*requested cutoff=2026-06-30",
    ):
        pnl_materialize.run_pnl_by_business_precompute_sync(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
            year=2026,
            as_of_dates=["2026-06-30"],
            run_id=run_id,
        )

    run_records = [
        record
        for record in GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
        if record["run_id"] == run_id
    ]
    assert preflight_calls == [(2026, "2026-06-30")]
    assert precompute_calls == ["2026-06-30"]
    assert [record["status"] for record in run_records] == ["running", "failed"]
    assert cache_clear_calls == []


def test_pnl_by_business_precompute_batch_status_uses_selected_cutoff(
    tmp_path,
    monkeypatch,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    target_cutoffs = ["2026-01-31", "2026-03-31"]
    queued_record = CacheBuildRunRecord(
        run_id="pnl_by_business_precompute:all-available",
        job_name=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        status="queued",
        cache_key=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
        cache_version=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
        lock="lock:duckdb:materialize:test",
        source_version=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION,
        vendor_version="vv_none",
        rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        queued_at=datetime.now(timezone.utc).isoformat(),
    ).model_dump()
    queued_record["target_year"] = 2026
    queued_record["trigger_reason"] = "manual_retry_all_available"
    queued_record["target_as_of_dates"] = target_cutoffs
    GovernanceRepository(base_dir=settings.governance_path).append(CACHE_BUILD_RUN_STREAM, queued_record)

    class FakePnlRepository:
        verify_current_calls: list[bool] = []

        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2026
            return "2026-06-30" if as_of_cap is None else str(as_of_cap)

        def fetch_pnl_by_business_precompute_metadata(self, **kwargs):
            assert kwargs["as_of_date"] in {"2026-03-31", "2026-06-30"}
            type(self).verify_current_calls.append(bool(kwargs["verify_current"]))
            return None

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)

    status = pnl_service.pnl_by_business_precompute_status(
        settings,
        year=2026,
        as_of_date="2026-03-31",
    )

    assert status["status"] == "queued"
    assert status["run_id"] == "pnl_by_business_precompute:all-available"
    assert status["report_date"] == "2026-03-31"
    assert status["serving_mode"] == "live_fallback"

    unlisted = pnl_service.pnl_by_business_precompute_status(
        settings,
        year=2026,
        as_of_date="2026-06-30",
    )
    assert unlisted["status"] == "idle"
    assert unlisted["run_id"] is None

    completed_record = {
        **queued_record,
        "status": "completed",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "source_version": "source::2026-06-30",
        "record_count": 708,
        "cutoff_results": [
            {
                "as_of_date": cutoff,
                "records": 118,
                "source_version": f"source::{cutoff}",
                "generated_at": f"generated::{cutoff}",
            }
            for cutoff in target_cutoffs
        ],
    }
    GovernanceRepository(base_dir=settings.governance_path).append(CACHE_BUILD_RUN_STREAM, completed_record)

    completed = pnl_service.pnl_by_business_precompute_status(
        settings,
        year=2026,
        as_of_date="2026-03-31",
    )

    assert FakePnlRepository.verify_current_calls == [False, True, True]
    assert completed["status"] == "completed"
    assert completed["report_date"] == "2026-03-31"
    assert completed["source_version"] == "source::2026-03-31"
    assert completed["generated_at"] == "generated::2026-03-31"
    assert completed["record_count"] == 118
    get_settings.cache_clear()


def test_pnl_by_business_precompute_rebuild_openapi_exposes_all_available_scope():
    from backend.app.main import app

    operation = app.openapi()["paths"]["/api/pnl/by-business/precompute-rebuild"]["post"]
    scope_parameter = next(parameter for parameter in operation["parameters"] if parameter["name"] == "scope")

    assert scope_parameter["schema"]["default"] == "selected"
    assert scope_parameter["schema"]["enum"] == ["selected", "all_available"]


def test_pnl_by_business_precompute_routes_enforce_scopes_before_wiring_requests(
    tmp_path,
    monkeypatch,
):
    route_module = load_module(
        f"tests._pnl_routes.precompute_route_contract_{id(monkeypatch)}",
        "backend/app/api/routes/pnl.py",
    )
    service_lookups: list[bool] = []
    status_calls: list[dict[str, object]] = []
    rebuild_calls: list[dict[str, object]] = []

    class FakePnlService:
        class PnlByBusinessPrecomputeConflictError(RuntimeError):
            pass

        class PnlByBusinessPrecomputeDispatchError(RuntimeError):
            pass

        @staticmethod
        def pnl_by_business_precompute_status(_settings, **kwargs):
            status_calls.append(kwargs)
            return {"year": kwargs["year"], "status": "idle"}

        @staticmethod
        def request_pnl_by_business_precompute_rebuild(_settings, **kwargs):
            rebuild_calls.append(kwargs)
            return {"status": "queued", **kwargs}

    def load_service():
        service_lookups.append(True)
        return FakePnlService

    monkeypatch.setattr(route_module, "_pnl_service", load_service)
    scope_repo = _setup_route_scope_store(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    headers = {"X-User-Id": "precompute-operator", "X-User-Role": "viewer"}
    status_path = "/api/pnl/by-business/precompute-status"
    rebuild_path = "/api/pnl/by-business/precompute-rebuild"

    assert client.get(status_path, params={"year": 2026}, headers=headers).status_code == 403
    assert (
        client.post(
            rebuild_path,
            params={"year": 2026, "scope": "all_available"},
            headers=headers,
        ).status_code
        == 403
    )
    assert service_lookups == status_calls == rebuild_calls == []

    _grant_pnl_read_scope(scope_repo, user_id="precompute-operator")
    allowed_status = client.get(
        status_path,
        params={"year": 2026, "as_of_date": "2026-03-31"},
        headers=headers,
    )
    assert allowed_status.status_code == 200

    scope_repo.grant_scope(
        user_id="precompute-operator",
        role=None,
        resource="pnl_by_business.adjustment",
        action="write",
    )

    selected = client.post(
        rebuild_path,
        params={"year": 2026, "as_of_date": "2026-03-31"},
        headers=headers,
    )
    all_available = client.post(
        rebuild_path,
        params={"year": 2026, "scope": "all_available"},
        headers=headers,
    )

    assert selected.status_code == 200
    assert all_available.status_code == 200
    assert status_calls == [{"year": 2026, "as_of_date": "2026-03-31"}]
    assert rebuild_calls == [
        {"year": 2026, "as_of_date": "2026-03-31", "scope": "selected"},
        {"year": 2026, "as_of_date": None, "scope": "all_available"},
    ]


def test_pnl_by_business_precompute_status_distinguishes_current_cache_and_live_fallback(
    tmp_path,
    monkeypatch,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()

    class FakeCurrentPnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap is None
            return "2025-12-31"

        def fetch_pnl_by_business_precompute_metadata(self, **_kwargs):
            return {
                "year": 2025,
                "as_of_date": "2025-12-31",
                "source_version": "sv-current",
                "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                "generated_at": "2026-07-15T12:00:00+00:00",
                "record_count": 118,
                "is_current": True,
            }

    monkeypatch.setattr(pnl_service, "PnlRepository", FakeCurrentPnlRepository)
    current = pnl_service.pnl_by_business_precompute_status(settings, year=2025)
    assert current["status"] == "completed"
    assert current["serving_mode"] == "precomputed"
    assert current["is_current"] is True
    assert current["report_date"] == "2025-12-31"
    assert current["record_count"] == 118

    failed_record = CacheBuildRunRecord(
        run_id="pnl_by_business_precompute:failed-status",
        job_name=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        status="failed",
        cache_key=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
        cache_version=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
        lock="lock:duckdb:materialize:test",
        source_version="sv-failed",
        vendor_version="vv_none",
        rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        finished_at=datetime.now(timezone.utc).isoformat(),
        error_message="worker failed",
        failure_category="materialize_failure",
    ).model_dump()
    failed_record["target_year"] = 2025
    failed_record["trigger_reason"] = "manual_retry"
    GovernanceRepository(base_dir=settings.governance_path).append(CACHE_BUILD_RUN_STREAM, failed_record)

    class FakeStalePnlRepository(FakeCurrentPnlRepository):
        def fetch_pnl_by_business_precompute_metadata(self, **_kwargs):
            return None

    monkeypatch.setattr(pnl_service, "PnlRepository", FakeStalePnlRepository)
    retrying = pnl_service.pnl_by_business_precompute_status(settings, year=2025)
    assert retrying["status"] == "queued"
    assert retrying["failure_category"] == "automatic_retry_pending"
    assert retrying["error_message"] == "上一次预计算未完成，后台正在按策略自动重试。"

    for _attempt in range(3):
        GovernanceRepository(base_dir=settings.governance_path).append(
            CACHE_BUILD_RUN_STREAM,
            {**failed_record, "finished_at": datetime.now(timezone.utc).isoformat()},
        )
    failed = pnl_service.pnl_by_business_precompute_status(settings, year=2025)
    assert failed["status"] == "failed"
    assert failed["serving_mode"] == "live_fallback"
    assert failed["is_current"] is False
    assert failed["error_message"] == "预计算执行失败，自动重试已结束，请查看后台运行日志。"
    assert failed["retry_attempt"] == 4
    get_settings.cache_clear()


def test_pnl_by_business_precompute_status_uses_selected_cutoff(
    tmp_path,
    monkeypatch,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    metadata_calls: list[dict[str, object]] = []

    class FakeHistoricalPnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            return "2025-06-30" if as_of_cap == "2025-06-30" else "2025-12-31"

        def fetch_pnl_by_business_precompute_metadata(self, **kwargs):
            metadata_calls.append(kwargs)
            return {
                "year": 2025,
                "as_of_date": "2025-06-30",
                "source_version": "sv-historical-current",
                "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                "generated_at": "2026-07-15T12:00:00+00:00",
                "record_count": 117,
                "is_current": True,
            }

    latest_record = CacheBuildRunRecord(
        run_id="pnl_by_business_precompute:latest-cutoff",
        job_name=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        status="completed",
        cache_key=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
        cache_version=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
        lock="lock:duckdb:materialize:test",
        source_version="sv-latest",
        vendor_version="vv_none",
        rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        report_date="2025-12-31",
        finished_at=datetime.now(timezone.utc).isoformat(),
    ).model_dump()
    latest_record["target_year"] = 2025
    GovernanceRepository(base_dir=settings.governance_path).append(CACHE_BUILD_RUN_STREAM, latest_record)
    monkeypatch.setattr(pnl_service, "PnlRepository", FakeHistoricalPnlRepository)

    status = pnl_service.pnl_by_business_precompute_status(
        settings,
        year=2025,
        as_of_date="2025-06-30",
    )

    assert status["status"] == "completed"
    assert status["report_date"] == "2025-06-30"
    assert status["run_id"] is None
    assert status["serving_mode"] == "precomputed"
    assert len(metadata_calls) == 1
    assert metadata_calls[0]["year"] == 2025
    assert metadata_calls[0]["as_of_date"] == "2025-06-30"
    assert str(metadata_calls[0]["supplemental_source_version"]).startswith(
        "sv_pnl_by_business_adjustments_v1:"
    )
    assert metadata_calls[0]["verify_current"] is True
    get_settings.cache_clear()


def test_pnl_by_business_precompute_status_marks_stale_inflight_and_allows_rebuild(
    tmp_path,
    monkeypatch,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    stale_record = CacheBuildRunRecord(
        run_id="pnl_by_business_precompute:stale",
        job_name=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        status="queued",
        cache_key=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
        cache_version=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
        lock="lock:duckdb:materialize:test",
        source_version="sv-pending",
        vendor_version="vv_none",
        rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        report_date="2025-12-31",
        queued_at=(datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    ).model_dump()
    stale_record["target_year"] = 2025
    GovernanceRepository(base_dir=settings.governance_path).append(CACHE_BUILD_RUN_STREAM, stale_record)

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            return "2025-12-31"

        def fetch_pnl_by_business_precompute_metadata(self, **_kwargs):
            return None

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    dispatched: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        lambda **kwargs: dispatched.append(kwargs),
    )

    stale = pnl_service.pnl_by_business_precompute_status(
        settings,
        year=2025,
        as_of_date="2025-12-31",
    )
    assert stale["status"] == "failed"
    assert stale["failure_category"] == "stale_inflight"
    assert stale["error_message"] == "预计算任务长时间未更新，已解除占用，可重新生成。"

    queued = pnl_service.request_pnl_by_business_precompute_rebuild(
        settings,
        year=2025,
        as_of_date="2025-12-31",
    )
    assert queued["status"] == "queued"
    assert len(dispatched) == 1
    assert dispatched[0]["as_of_date"] == "2025-12-31"
    get_settings.cache_clear()


def test_pnl_by_business_precompute_status_prioritizes_inflight_run_over_later_terminal_event(
    tmp_path,
    monkeypatch,
):
    from backend.app.services import pnl_service

    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    settings = get_settings()
    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    now = datetime.now(timezone.utc).isoformat()

    def append_run(run_id: str, status: str) -> None:
        record = CacheBuildRunRecord(
            run_id=run_id,
            job_name=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
            status=status,
            cache_key=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
            cache_version=pnl_service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
            lock="lock:duckdb:materialize:test",
            source_version="sv-pending",
            vendor_version="vv_none",
            rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
            report_date="2025-12-31",
            queued_at=now,
            started_at=now if status in {"running", "completed"} else None,
            finished_at=now if status == "completed" else None,
        ).model_dump()
        record["target_year"] = 2025
        governance_repo.append(CACHE_BUILD_RUN_STREAM, record)

    append_run("pnl_by_business_precompute:run-a", "running")
    append_run("pnl_by_business_precompute:run-b", "queued")
    append_run("pnl_by_business_precompute:run-a", "completed")

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            return "2025-12-31"

        def fetch_pnl_by_business_precompute_metadata(self, **kwargs):
            assert kwargs["verify_current"] is False
            return None

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)

    status = pnl_service.pnl_by_business_precompute_status(
        settings,
        year=2025,
        as_of_date="2025-12-31",
    )
    assert status["status"] == "queued"
    assert status["run_id"] == "pnl_by_business_precompute:run-b"
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_feeds_ytd_monthly_and_analysis(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    scope_repo = UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn)
    _grant_pnl_read_scope(scope_repo)
    scope_repo.grant_scope(user_id="*", role=None, resource="pnl_by_business.adjustment", action="approve")
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P001', 'Rate Desk', 'CC-RATE', 'T', 'FVTPL', 'CNY',
              100.00, 0.00, 25.50, 0.00, 125.50,
              'fi-policy-adjust-base', 'rv_pnl_phase2_materialize_v1', 'ib-policy-adjust-base', 'trace-policy-adjust-base'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P001', 'policy financial bond', 'Rate Desk', 'CC-RATE',
              'asset', '政策性金融债', '政策性金融债', '政策性金融债', '政策性金融债',
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              1000.00000000, 1000.00000000, 0.00000000, false,
              'sv-policy-adjust-balance', 'rv-policy-adjust-balance', 'ib-policy-adjust-balance', 'trace-policy-adjust-balance'
            )
            """
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "25.00",
            "reason": "补录政策性金融债调整",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["approval_status"] == "pending"
    adjustment_id = create_response.json()["adjustment_id"]

    approve_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/approve",
        headers={"X-User-Id": "checker", "X-User-Role": "reviewer"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approval_status"] == "approved"

    detail_create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_detail_structured_finance_broker",
            "business_type": "Structured finance detail manual adjustment",
            "operator": "DELTA",
            "approval_status": "pending",
            "manual_adjustment": "5.00",
            "reason": "Detail-row reconciliation regression",
        },
    )
    assert detail_create_response.status_code == 200
    detail_adjustment_id = detail_create_response.json()["adjustment_id"]
    detail_approve_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{detail_adjustment_id}/approve",
        headers={"X-User-Id": "detail-checker", "X-User-Role": "reviewer"},
    )
    assert detail_approve_response.status_code == 200
    assert detail_approve_response.json()["approval_status"] == "approved"

    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    ytd_result = ytd_response.json()["result"]
    ytd_by_key = {item["row_key"]: item for item in ytd_result["items"]}
    adjusted_ytd = ytd_by_key["asset_zqtz_policy_financial_bond"]
    assert adjusted_ytd["manual_adjustment"] == "25.00"
    assert adjusted_ytd["total_pnl"] == "150.50"
    assert ytd_by_key["asset_zqtz_detail_structured_finance_broker"]["manual_adjustment"] == "5.00"
    assert ytd_result["total_pnl"] == "267.00"
    ytd_detail_unallocated = next(
        item
        for item in ytd_result["unallocated_items"]
        if item["source_kind"] == "manual_adjustment"
        and item["instrument_code"] == "manual::asset_zqtz_detail_structured_finance_broker"
    )
    assert ytd_detail_unallocated["total_pnl"] == "5.00"
    assert ytd_result["reconciliation_delta"] == "0.00"
    assert "pnl_by_business_adjustments" in ytd_result["source_tables"]

    monthly_response = client.get(
        "/api/pnl/by-business-monthly",
        params={"year": 2025, "as_of_date": "2025-12-31"},
    )
    assert monthly_response.status_code == 200
    month = monthly_response.json()["result"]["months"][0]
    monthly_by_key = {item["row_key"]: item for item in month["items"]}
    assert monthly_by_key["asset_zqtz_policy_financial_bond"]["manual_adjustment"] == "25.00"
    assert monthly_by_key["asset_zqtz_policy_financial_bond"]["total_pnl"] == "150.50"
    assert monthly_by_key["asset_zqtz_detail_structured_finance_broker"]["manual_adjustment"] == "5.00"
    assert month["summary"]["manual_adjustment"] == "25.00"
    assert month["reconciliation_delta"] == "0.00"
    assert ytd_result["unallocated_pnl"] == month["unallocated_pnl"]
    assert ytd_result["unallocated_row_count"] == month["unallocated_row_count"]

    analysis_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_policy_financial_bond",
            "dimension": "monthly",
        },
    )
    assert analysis_response.status_code == 200
    analysis_row = analysis_response.json()["result"]["rows"][0]
    assert analysis_row["manual_adjustment"] == "25.00"
    assert analysis_row["total_pnl"] == "150.50"

    accounting_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_policy_financial_bond",
            "dimension": "accounting",
        },
    )
    assert accounting_response.status_code == 200
    accounting_rows = {
        row["dimension_key"]: row for row in accounting_response.json()["result"]["rows"]
    }
    manual_row = accounting_rows["manual_adjustment"]
    assert manual_row["dimension_label"] == "手工调整"
    assert manual_row["manual_adjustment"] == "25.00"
    assert manual_row["total_pnl"] == "25.00"
    assert manual_row["avg_balance"] == "0.00"
    assert manual_row["ftp_cost"] == "0.00"
    assert manual_row["ftp_net_pnl"] == "25.00"
    assert manual_row["ftp_net_annualized_yield_pct"] is None
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_request_approved_is_forced_pending(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _grant_pnl_read_scope(UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn))
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    policy_type = str(row_defs["asset_zqtz_policy_financial_bond"]["match_keywords"][0])
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P001', 'Rate Desk', 'CC-RATE', 'T', 'FVTPL', 'CNY',
              100.00, 0.00, 25.50, 0.00, 125.50,
              'fi-policy-pending-base', 'rv_pnl_phase2_materialize_v1', 'ib-policy-pending-base', 'trace-policy-pending-base'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P001', 'policy financial bond', 'Rate Desk', 'CC-RATE',
              'asset', ?, ?, ?, ?,
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              1000.00000000, 1000.00000000, 0.00000000, false,
              'sv-policy-pending-balance', 'rv-policy-pending-balance', 'ib-policy-pending-balance', 'trace-policy-pending-balance'
            )
            """,
            [policy_type, policy_type, policy_type, policy_type],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": policy_type,
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "25.00",
            "reason": "request cannot self-approve",
        },
    )
    assert create_response.status_code == 200
    adjustment_id = create_response.json()["adjustment_id"]
    assert create_response.json()["approval_status"] == "pending"

    edit_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/edit",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": policy_type,
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "30.00",
            "reason": "edit cannot self-approve",
        },
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["approval_status"] == "pending"

    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    ytd_result = ytd_response.json()["result"]
    ytd_by_key = {item["row_key"]: item for item in ytd_result["items"]}
    policy_item = ytd_by_key["asset_zqtz_policy_financial_bond"]
    assert policy_item["manual_adjustment"] == "0.00"
    assert policy_item["total_pnl"] == "125.50"
    assert "pnl_by_business_adjustments" not in ytd_result["source_tables"]
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_approval_requires_checker(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    scope_repo = UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn)
    _grant_pnl_read_scope(scope_repo)
    scope_repo.grant_scope(user_id="*", role=None, resource="pnl_by_business.adjustment", action="approve")
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        headers={"X-User-Id": "maker", "X-User-Role": "analyst"},
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "Policy Financial Bond",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "25.00",
            "reason": "maker cannot self approve",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["approval_status"] == "pending"
    assert created["created_by"] == "maker"
    adjustment_id = created["adjustment_id"]

    self_approve_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/approve",
        headers={"X-User-Id": "maker", "X-User-Role": "analyst"},
    )
    assert self_approve_response.status_code == 403

    checker_approve_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/approve",
        headers={"X-User-Id": "checker", "X-User-Role": "reviewer"},
    )
    assert checker_approve_response.status_code == 200
    approved = checker_approve_response.json()
    assert approved["approval_status"] == "approved"
    assert approved["approved_by"] == "checker"
    assert approved["created_by"] == "maker"
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_restore_returns_to_pending(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _grant_pnl_read_scope(UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "Policy Financial Bond",
            "operator": "DELTA",
            "manual_adjustment": "25.00",
            "reason": "restore should need approval again",
        },
    )
    assert create_response.status_code == 200
    adjustment_id = create_response.json()["adjustment_id"]

    revoke_response = client.post(f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/revoke")
    assert revoke_response.status_code == 200
    assert revoke_response.json()["approval_status"] == "rejected"

    restore_response = client.post(f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/restore")
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["event_type"] == "restored"
    assert restored["approval_status"] == "pending"
    assert restored["approved_by"] == ""
    get_settings.cache_clear()


def test_pnl_by_business_analysis_contract_reconciles_selected_business(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    other_type = classification["other_type"]
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = [
            ("SA001", "20.00", "0.00", "0.00", "20.00"),
            ("G0001", "7.00", "0.00", "0.00", "7.00"),
            ("J4001", "11.00", "0.00", "0.00", "11.00"),
            ("J1001", "14.00", "0.00", "0.00", "14.00"),
            ("J02205260102", "0.00", "9.00", "0.00", "9.00"),
            ("J09999990102", "0.00", "0.00", "4.00", "4.00"),
            ("JM001", "10.00", "0.00", "0.00", "10.00"),
        ]
        conn.executemany(
            """
            insert into fact_nonstd_pnl_bridge values (
              '2025-12-31', ?, 'NonStd Desk', 'CC-PREFIX',
              ?, ?, ?, 0.00, ?,
              'sv-nonstd-analysis', 'rv_pnl_phase2_materialize_v1', 'ib-nonstd-analysis', 'tr-nonstd-analysis'
            )
            """,
            rows,
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-01",
                    "J4001",
                    "J4 structured",
                    "NonStd Desk",
                    "CC-J4",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "500.00000000",
                    "500.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j4-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j4-prior",
                ),
                (
                    "2025-12-01",
                    "J1001",
                    "J1 delegated",
                    "NonStd Desk",
                    "CC-J1",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "1000.00000000",
                    "1000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j1-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j1-prior",
                ),
                (
                    "2025-12-01",
                    "J02205260102",
                    "J0 market",
                    "NonStd Desk",
                    "CC-J0-M",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "1500.00000000",
                    "1500.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j0-market-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-market-prior",
                ),
                (
                    "2025-12-01",
                    "J09999990102",
                    "J0 cost",
                    "NonStd Desk",
                    "CC-J0-C",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "2000.00000000",
                    "2000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j0-cost-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-cost-prior",
                ),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    ytd_by_key = {item["row_key"]: item for item in ytd_response.json()["result"]["items"]}

    response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_detail_securities_asset_management_plan",
            "dimension": "portfolio",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_analysis"
    result = payload["result"]
    assert result["dimension"] == "portfolio"
    assert result["business_key"] == "asset_zqtz_detail_securities_asset_management_plan"
    assert result["period_start_date"] == "2025-12-01"
    assert result["period_end_date"] == "2025-12-31"
    assert "ZQTZ_ASSET_BOND_ROWS" in result["source_tables"]
    assert set(result["rows"][0]) == {
        "dimension_key",
        "dimension_label",
        "interest_income",
        "fair_value_change",
        "capital_gain",
        "manual_adjustment",
        "total_pnl",
        "avg_balance",
        "current_balance",
        "annualized_yield_pct",
        "ftp_rate_pct",
        "ftp_cost",
        "ftp_net_pnl",
        "ftp_net_annualized_yield_pct",
        "asset_count",
    }
    row = result["rows"][0]
    assert row["dimension_key"] == "NonStd Desk"
    assert row["total_pnl"] == ytd_by_key["asset_zqtz_detail_securities_asset_management_plan"]["total_pnl"]
    assert row["total_pnl"] == "38.00"
    assert row["avg_balance"] == "7500.00"
    assert row["current_balance"] == "10012.00"
    assert row["avg_balance"] != row["current_balance"]
    assert row["annualized_yield_pct"] == "5.965591"
    assert row["ftp_rate_pct"] == "1.750000"
    assert row["ftp_cost"] == "11.15"
    assert row["ftp_net_pnl"] == "26.85"
    assert row["ftp_net_annualized_yield_pct"] == "4.215591"
    assert row["asset_count"] == 4

    currency_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_detail_securities_asset_management_plan",
            "dimension": "currency",
        },
    )
    assert currency_response.status_code == 200
    currency_result = currency_response.json()["result"]
    assert currency_result["dimension"] == "currency"
    currency_rows = {item["dimension_key"]: item for item in currency_result["rows"]}
    assert set(currency_rows) == {"CNY", "USD"}
    assert currency_rows["CNY"]["dimension_label"] == "人民币"
    assert currency_rows["CNY"]["total_pnl"] == "24.00"
    assert currency_rows["CNY"]["avg_balance"] == "6000.00"
    assert currency_rows["CNY"]["current_balance"] == "8012.00"
    assert currency_rows["CNY"]["ftp_cost"] == "8.92"
    assert currency_rows["CNY"]["ftp_net_pnl"] == "15.08"
    assert currency_rows["CNY"]["asset_count"] == 3
    assert currency_rows["USD"]["dimension_label"] == "美元（折人民币）"
    assert currency_rows["USD"]["total_pnl"] == "14.00"
    assert currency_rows["USD"]["avg_balance"] == "1500.00"
    assert currency_rows["USD"]["current_balance"] == "2000.00"
    assert currency_rows["USD"]["ftp_cost"] == "2.23"
    assert currency_rows["USD"]["ftp_net_pnl"] == "11.77"
    assert currency_rows["USD"]["asset_count"] == 1
    assert sum(Decimal(item["total_pnl"]) for item in currency_result["rows"]) == Decimal("38.00")
    assert sum(Decimal(item["avg_balance"]) for item in currency_result["rows"]) == Decimal("7500.00")
    assert sum(Decimal(item["current_balance"]) for item in currency_result["rows"]) == Decimal("10012.00")
    assert sum(Decimal(item["ftp_cost"]) for item in currency_result["rows"]) == Decimal("11.15")
    assert sum(Decimal(item["ftp_net_pnl"]) for item in currency_result["rows"]) == Decimal("26.85")

    jm_currency_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_other_debt_financing",
            "dimension": "currency",
        },
    )
    assert jm_currency_response.status_code == 200
    assert [
        (item["dimension_key"], item["dimension_label"], item["total_pnl"])
        for item in jm_currency_response.json()["result"]["rows"]
    ] == [("CNY", "人民币", "10.00")]

    empty_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "missing-business-key",
            "dimension": "portfolio",
        },
    )
    assert empty_response.status_code == 200
    assert empty_response.json()["result"]["rows"] == []

    invalid_response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "bad"},
    )
    assert invalid_response.status_code == 422
    get_settings.cache_clear()


def test_pnl_by_business_analysis_bond_bucket_and_ftp_contract(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    other_type = classification["other_type"]
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fact_formal_pnl_fi where substr(cast(report_date as varchar), 1, 4) = '2025'")
        conn.execute("delete from fact_nonstd_pnl_bridge where substr(cast(report_date as varchar), 1, 4) = '2025'")
        conn.execute(
            "delete from fact_formal_zqtz_balance_daily where substr(cast(report_date as varchar), 1, 4) = '2025'"
        )
        conn.executemany(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', ?, ?, ?, 'T', 'FVTPL', 'CNY',
              ?, 0.00, 0.00, 0.00, ?,
              'fi-bucket-v1', 'rv_pnl_phase2_materialize_v1', 'ib-bucket', 'trace-fi-bucket'
            )
            """,
            [
                ("P001", "Rate Desk", "CC-RATE", "100.00", "100.00"),
                ("E001", "Credit Desk", "CC-ENT", "30.00", "30.00"),
                ("ABS001", "Credit Desk", "CC-ABS", "50.00", "50.00"),
                ("C001", "Financial Desk", "CC-COM", "40.00", "40.00"),
                ("NCD001", "Financial Desk", "CC-NCD", "60.00", "60.00"),
                ("J0001", "Other Desk", "CC-J", "70.00", "70.00"),
                ("U001", "No Balance", "CC-U", "10.00", "10.00"),
            ],
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', ?, ?, ?, ?, 'asset', ?, ?, ?, ?,
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              ?, ?, 0.00000000, false,
              'sv-z-bucket', 'rv-z-bucket', 'ib-z-bucket', 'trace-z-bucket'
            )
            """,
            [
                ("P001", "policy financial bond", "Rate Desk", "CC-RATE", "政策性金融债", "政策性金融债", "政策性金融债", "政策性金融债", "1000.00000000", "1000.00000000"),
                ("E001", "enterprise bond", "Credit Desk", "CC-ENT", "企业债", "企业债", "企业债", "企业债", "2000.00000000", "2000.00000000"),
                ("ABS001", "asset backed security", "Credit Desk", "CC-ABS", "资产支持证券", "资产支持证券", "资产支持证券", "资产支持证券", "3000.00000000", "3000.00000000"),
                ("C001", "commercial financial bond", "Financial Desk", "CC-COM", "商业性金融债", "商业性金融债", "商业性金融债", "商业性金融债", "4000.00000000", "4000.00000000"),
                ("NCD001", "interbank cd", "Financial Desk", "CC-NCD", "同业存单", "同业存单", "同业存单", "同业存单", "5000.00000000", "5000.00000000"),
                ("J0001", "non bottom asset", "Other Desk", "CC-J", other_type, other_type, other_type, other_type, "6000.00000000", "6000.00000000"),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    assert ytd_response.json()["result"]["total_pnl"] == "360.00"

    response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "bond_bucket"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["dimension"] == "bond_bucket"
    by_label = {row["dimension_label"]: row for row in result["rows"]}
    assert list(by_label) == ["利率债", "信用债", "金融债", "其它债券"]
    assert by_label["利率债"]["total_pnl"] == "100.00"
    assert by_label["信用债"]["total_pnl"] == "80.00"
    assert by_label["金融债"]["total_pnl"] == "100.00"
    assert by_label["其它债券"]["total_pnl"] == "80.00"
    assert sum(Decimal(row["total_pnl"]) for row in result["rows"]) == Decimal("360.00")
    assert by_label["利率债"]["avg_balance"] == "1000.00"
    assert by_label["利率债"]["current_balance"] == "1000.00"
    assert by_label["利率债"]["annualized_yield_pct"] == "117.741935"
    assert by_label["利率债"]["ftp_rate_pct"] == "1.750000"
    assert by_label["利率债"]["ftp_cost"] == "1.49"
    assert by_label["利率债"]["ftp_net_pnl"] == "98.51"
    assert by_label["利率债"]["ftp_net_annualized_yield_pct"] == "115.991935"

    merged_rows = result["merged_bucket_rows"]
    assert [(row["dimension_key"], row["dimension_label"]) for row in merged_rows] == [("other_merged", "其他")]
    merged = merged_rows[0]
    assert merged["total_pnl"] == "180.00"
    assert merged["avg_balance"] == "15000.00"
    # Backend口径: (180 / 15000) * 365/31 * 100, not a per-row yield weighting.
    assert merged["annualized_yield_pct"] == "14.129032"
    assert merged["ftp_cost"] == "22.29"
    assert merged["ftp_net_pnl"] == "157.71"
    assert merged["ftp_net_annualized_yield_pct"] == "12.379032"

    trend_response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "bond_bucket_monthly"},
    )
    assert trend_response.status_code == 200
    trend_result = trend_response.json()["result"]
    assert trend_result["dimension"] == "bond_bucket_monthly"
    trend_by_key = {row["dimension_key"]: row for row in trend_result["rows"]}
    assert list(trend_by_key) == [
        "2025-12-31::rate_bond",
        "2025-12-31::credit_bond",
        "2025-12-31::financial_bond",
        "2025-12-31::other_bond",
    ]
    assert trend_by_key["2025-12-31::rate_bond"]["dimension_label"] == "2025-12-31 利率债"
    assert trend_by_key["2025-12-31::rate_bond"]["total_pnl"] == "100.00"
    assert trend_by_key["2025-12-31::rate_bond"]["avg_balance"] == "1000.00"
    assert trend_by_key["2025-12-31::rate_bond"]["ftp_net_pnl"] == "98.51"

    no_avg_response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "portfolio"},
    )
    assert no_avg_response.status_code == 200
    by_portfolio = {row["dimension_label"]: row for row in no_avg_response.json()["result"]["rows"]}
    assert by_portfolio["No Balance"]["avg_balance"] == "0.00"
    assert by_portfolio["No Balance"]["current_balance"] == "0.00"
    assert by_portfolio["No Balance"]["annualized_yield_pct"] is None
    assert by_portfolio["No Balance"]["ftp_cost"] is None
    assert by_portfolio["No Balance"]["ftp_net_pnl"] is None
    assert by_portfolio["No Balance"]["ftp_net_annualized_yield_pct"] is None
    get_settings.cache_clear()


def test_pnl_by_business_keeps_same_instrument_positions_separate(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', '240001.IB', 'Other Desk', 'CC300', 'T', 'FVTPL', 'CNY',
              20.00, 0.00, 0.00, 0.00, 20.00,
              'fi-same-instrument-v1', 'rv_pnl_phase2_materialize_v1', 'ib-same-instrument', 'trace-fi-same-instrument'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', '240001.IB', 'Other Desk', 'CC300', 'bond-hedging',
              'T', 'FVTPL', 'asset', 'CNY', 'CNY', 200.00, 200.00, 0.00, false,
              'sv-z-hedge', 'rv-z-biz', 'ib-z-hedge', 'trace-z-hedge'
            )
            """
        )
    finally:
        conn.close()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert by_business["bond-trading"]["total_pnl"] == "111.50"
    assert by_business["bond-trading"]["scale_amount"] == "1099.00"
    assert by_business["bond-hedging"]["total_pnl"] == "20.00"
    assert by_business["bond-hedging"]["scale_amount"] == "200.00"
    assert by_business["bond-hedging"]["pnl_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_daily_uses_formal_facts_not_refresh_source_override(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    pnl_repo_module = load_module("backend.app.repositories.pnl_repo", "backend/app/repositories/pnl_repo.py")
    source_service = load_module(
        "backend.app.services.pnl_source_service",
        "backend/app/services/pnl_source_service.py",
    )

    class AlwaysDefaultPath:
        def __init__(self, *_args):
            pass

        def resolve(self):
            return "data/moss.duckdb"

    class FakeRefreshInput:
        fi_rows = [
            {
                "instrument_code": "250002.IB",
                "currency_basis": "CNY",
                "invest_type_raw": "source-only",
                "interest_income_514": Decimal("999.00"),
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "manual_adjustment": Decimal("0.00"),
            }
        ]

    monkeypatch.setattr(pnl_repo_module, "Path", AlwaysDefaultPath, raising=False)
    monkeypatch.setattr(
        source_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    rows = repo.fetch_by_business_rows("2025-12-31")
    total = sum((Decimal(str(row["total_pnl"])) for row in rows), Decimal("0"))
    by_business = {str(row["business_type_primary"]): row for row in rows}

    assert total == Decimal("125.50000000")
    assert Decimal(str(by_business["bond-trading"]["scale_amount"])) == Decimal("1099.00000000")
    assert "source-only" not in by_business


def test_pnl_by_business_balance_lookup_stays_on_requested_report_date(tmp_path):
    pnl_repo_module = load_module(
        "backend.app.repositories.pnl_repo_date_scoped_business_lookup",
        "backend/app/repositories/pnl_repo.py",
    )
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              currency_basis varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_nonstd_pnl_bridge (
              report_date varchar,
              bond_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              currency_basis varchar,
              business_type_primary varchar,
              sub_type varchar,
              asset_class varchar,
              position_scope varchar,
              market_value_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values
            ('2026-04-30', 'BOND-001', 'FIOA', 'CC', 'A', 'FVOCI', 'CNY', 10, 0, 0, 0, 10, 'sv', 'rv', 'batch', 'tr')
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2026-03-31', 'BOND-001', 'FIOA', 'CC', 'CNY', 'old-month-credit', '', '', 'asset', 900),
            ('2026-04-30', 'BOND-001', 'FIOA', 'CC', 'CNY', '', '', '', 'asset', 100)
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    rows = repo.fetch_by_business_rows("2026-04-30")

    assert len(rows) == 1
    assert rows[0]["business_type_primary"] == "A"
    assert Decimal(str(rows[0]["scale_amount"])) == Decimal("0E-8")
    assert rows[0]["balance_row_count"] == 0


def test_pnl_by_business_balance_query_filters_balance_dates_to_pnl_dates(monkeypatch):
    pnl_repo_module = load_module(
        "backend.app.repositories.pnl_repo_balance_date_filter_contract",
        "backend/app/repositories/pnl_repo.py",
    )
    captured_sql: list[str] = []

    class FakeCursor:
        def fetchall(self):
            return []

    class FakeConnection:
        def execute(self, sql, _params=None):
            captured_sql.append(sql)
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(
        pnl_repo_module.duckdb,
        "connect",
        lambda *_args, **_kwargs: FakeConnection(),
    )

    pnl_repo_module.PnlRepository("unused.duckdb").fetch_by_business_rows("2026-04-30")

    query = "\n".join(captured_sql).lower()
    assert "from fact_formal_zqtz_balance_daily" in query
    assert "select distinct report_date from pnl_rows" in query


def test_pnl_by_business_summary_rows_stay_on_requested_report_date(tmp_path):
    pnl_repo_module = load_module(
        "backend.app.repositories.pnl_repo_date_scoped_business_summary",
        "backend/app/repositories/pnl_repo.py",
    )
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              currency_basis varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_nonstd_pnl_bridge (
              report_date varchar,
              bond_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              currency_basis varchar,
              business_type_primary varchar,
              sub_type varchar,
              asset_class varchar,
              position_scope varchar,
              market_value_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values
            ('2026-04-30', 'BOND-001', 'FIOA', 'CC', 'A', 'FVOCI', 'CNY', 10, 0, 0, 0, 10, 'sv', 'rv', 'batch', 'tr')
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2026-03-31', 'BOND-001', 'FIOA', 'CC', 'CNY', 'old-month-credit', '', '', 'asset', 900),
            ('2026-04-30', 'BOND-001', 'FIOA', 'CC', 'CNY', '', '', '', 'asset', 100)
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    rows = repo.fetch_by_business_summary_rows("2026-04-30")

    assert len(rows) == 1
    assert rows[0]["business_type_primary"] == "A"
    assert Decimal(str(rows[0]["scale_amount"])) == Decimal("0E-8")
    assert rows[0]["balance_row_count"] == 0


def test_pnl_by_business_summary_rows_batch_groups_by_report_date(tmp_path):
    pnl_repo_module = load_module(
        "backend.app.repositories.pnl_repo_date_scoped_business_summary_batch",
        "backend/app/repositories/pnl_repo.py",
    )
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              currency_basis varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_nonstd_pnl_bridge (
              report_date varchar,
              bond_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              currency_basis varchar,
              business_type_primary varchar,
              sub_type varchar,
              asset_class varchar,
              position_scope varchar,
              market_value_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values
            ('2026-04-30', 'BOND-001', 'FIOA', 'CC', 'A', 'FVOCI', 'CNY', 10, 0, 0, 0, 10, 'sv', 'rv', 'batch', 'tr'),
            ('2026-03-31', 'BOND-002', 'FIOA', 'CC', 'H', 'FVOCI', 'CNY', 20, 0, 0, 0, 20, 'sv', 'rv', 'batch', 'tr')
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2026-04-30', 'BOND-001', 'FIOA', 'CC', 'CNY', 'A', '', '', 'asset', 100),
            ('2026-03-31', 'BOND-002', 'FIOA', 'CC', 'CNY', 'H', '', '', 'asset', 200),
            ('2026-02-28', 'BOND-001', 'FIOA', 'CC', 'CNY', 'old-month-credit', '', '', 'asset', 900)
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    by_date = repo.fetch_by_business_summary_rows_by_report_date(["2026-04-30", "2026-03-31", "2026-02-28"])

    assert [row["business_type_primary"] for row in by_date["2026-04-30"]] == ["A"]
    assert Decimal(str(by_date["2026-04-30"][0]["scale_amount"])) == Decimal("100.00000000")
    assert [row["business_type_primary"] for row in by_date["2026-03-31"]] == ["H"]
    assert Decimal(str(by_date["2026-03-31"][0]["scale_amount"])) == Decimal("200.00000000")
    assert by_date["2026-02-28"] == []


def test_tpl_pnl_summary_batch_keeps_report_date_grain(tmp_path):
    pnl_repo_module = load_module(
        "backend.app.repositories.pnl_repo_tpl_summary_batch",
        "backend/app/repositories/pnl_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              accounting_basis varchar,
              fair_value_change_516 decimal(24, 8),
              total_pnl decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, accounting_basis, fair_value_change_516, total_pnl
            ) values
            ('2026-04-30', 'FVTPL', 10, 12),
            ('2026-04-30', 'FVOCI', 99, 99),
            ('2026-03-31', 'TPL', 1, 2)
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    summaries = repo.fetch_tpl_pnl_summary_by_report_date(["2026-04-30", "2026-03-31", "2026-02-28"])

    assert Decimal(str(summaries["2026-04-30"]["tpl_fair_value_change"])) == Decimal("10.00000000")
    assert Decimal(str(summaries["2026-04-30"]["tpl_total_pnl"])) == Decimal("12.00000000")
    assert summaries["2026-04-30"]["row_count"] == 1
    assert Decimal(str(summaries["2026-03-31"]["tpl_total_pnl"])) == Decimal("2.00000000")
    assert summaries["2026-02-28"]["tpl_total_pnl"] == 0
    assert summaries["2026-02-28"]["row_count"] == 0


def test_pnl_by_business_ytd_uses_v1_formula_and_balance_movement_rows(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)

    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    enterprise_type = classification["enterprise_type"]
    commercial_type = classification["commercial_type"]

    class FakeRefreshInput:
        report_date = "2025-12-31"
        is_month_end = True

        def __init__(self):
            self.fi_rows = [
                {
                    "instrument_code": "E001",
                    "asset_class": enterprise_type,
                    "interest_income_514": Decimal("106.00"),
                    "fair_value_change_516": Decimal("3.00"),
                    "capital_gain_517": Decimal("10.00"),
                    "source_version": "sv-fi-enterprise",
                },
                {
                    "instrument_code": "C001",
                    "asset_class": commercial_type,
                    "interest_income_514": Decimal("40.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "source_version": "sv-fi-commercial",
                },
                {
                    "instrument_code": "U001",
                    "asset_class": "UNMAPPED_TEST",
                    "interest_income_514": Decimal("5.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "source_version": "sv-fi-unmapped",
                },
            ]
            self.nonstd_rows_by_type = {
                "514": [
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J4001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("11.00"),
                        "source_version": "sv-nonstd-j4",
                    },
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J1001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("2.00"),
                        "source_version": "sv-nonstd-j1",
                    },
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "JM001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("10.60"),
                        "source_version": "sv-nonstd-jm",
                    },
                ],
                "516": [
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J02205260102",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("9.00"),
                        "source_version": "sv-nonstd-j0-market",
                    }
                ],
                "517": [
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J09999990102",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("4.00"),
                        "source_version": "sv-nonstd-j0-cost",
                    },
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "SA001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("20.00"),
                        "source_version": "sv-nonstd-sa",
                    },
                ],
            }

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2025-12-31"],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    result = payload["result"]
    assert result["year"] == 2025
    assert result["period_label"].startswith("2025")
    assert "fact_formal_zqtz_balance_daily" in result["source_tables"]
    assert "ZQTZ_ASSET_BOND_ROWS" in result["source_tables"]
    assert [item["sort_order"] for item in result["items"]] == sorted(item["sort_order"] for item in result["items"])

    by_key = {item["row_key"]: item for item in result["items"]}
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["interest_income"] == "106.00"
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["fair_value_change"] == "3.00"
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["capital_gain"] == "-9.43"
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["total_pnl"] == "99.57"
    assert by_key["asset_zqtz_commercial_financial_bond"]["total_pnl"] == "40.00"
    assert by_key["asset_zqtz_public_fund"]["total_pnl"] == "20.00"
    assert by_key["asset_zqtz_other_debt_financing"]["total_pnl"] == "10.60"

    assert by_key["asset_zqtz_non_bottom_investment"]["total_pnl"] == "38.00"
    assert by_key["asset_zqtz_detail_securities_asset_management_plan"]["total_pnl"] == "38.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["total_pnl"] == "11.00"
    assert by_key["asset_zqtz_detail_foreign_currency_delegated"]["total_pnl"] == "14.00"
    assert by_key["asset_zqtz_detail_local_currency_delegated_market_value"]["total_pnl"] == "9.00"
    assert by_key["asset_zqtz_detail_local_currency_special_account_cost"]["total_pnl"] == "4.00"

    assert by_key["asset_zqtz_non_bottom_investment"]["current_balance"] == "10012.00"
    assert by_key["asset_zqtz_detail_securities_asset_management_plan"]["current_balance"] == "10012.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["current_balance"] == "1005.00"
    assert by_key["asset_zqtz_detail_foreign_currency_delegated"]["current_balance"] == "2000.00"
    assert by_key["asset_zqtz_detail_local_currency_delegated_market_value"]["current_balance"] == "3007.00"
    assert by_key["asset_zqtz_detail_local_currency_special_account_cost"]["current_balance"] == "4000.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["balance_yield_pct"] == "1.094527"
    assert by_key["asset_zqtz_central_bank_bill"]["balance_yield_pct"] is None
    assert result["total_pnl"] == "213.17"
    assert result["unallocated_pnl"] == "5.00"
    assert result["unallocated_abs_pnl"] == "5.00"
    assert result["unallocated_row_count"] == 1
    assert result["reconciliation_delta"] == "0.00"
    assert result["unallocated_breakdown"] == [
        {
            "reason_code": "no_business_rule_match",
            "source_kind": "refresh_bundle",
            "invest_type_std": "",
            "accounting_basis": "",
            "portfolio_name": "",
            "cost_center": "",
            "pnl_row_count": 1,
            "total_pnl": "5.00",
            "abs_pnl": "5.00",
            "sample_instrument_codes": ["U001"],
        }
    ]
    assert result["unallocated_items"][0]["instrument_code"] == "U001"
    assert result["unallocated_items"][0]["source_kind"] == "refresh_bundle"
    assert result["unallocated_items"][0]["total_pnl"] == "5.00"

    # 不变量：payload.total_pnl = 各条 V1 记录 total_pnl 之和（每条资产/凭证一条）；因 ZQTZ 多行命中，
    # items 各行 total_pnl 之和可大于该值（父级+其中重复分摊）。
    repo_mod = load_module("backend.app.repositories.pnl_repo", "backend/app/repositories/pnl_repo.py")
    repo = repo_mod.PnlRepository(str(duckdb_path))
    sub_map = repo.fetch_zqtz_sub_type_map(["2025-12-31"])
    fx_rates = repo.fetch_latest_fx_rates("2025-12-31", {"USD"})
    fake_in = FakeRefreshInput()
    v1_record_total = sum(
        Decimal(str(record["total_pnl"]))
        for record in pnl_service._iter_v1_compatible_pnl_records(
            report_date="2025-12-31",
            refresh_input=fake_in,
            sub_type_map=sub_map,
            fx_rates=fx_rates,
        )
    )
    assert v1_record_total.quantize(Decimal("0.01")) == Decimal(result["total_pnl"])
    items_total = sum(Decimal(item["total_pnl"]) for item in result["items"])
    assert items_total > v1_record_total.quantize(Decimal("0.01"))

    get_settings.cache_clear()


def test_pnl_by_business_ytd_refresh_bundle_rejects_prior_day_fx_locs(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    _replace_pnl_refresh_fx_rows(
        duckdb_path,
        rows=[
            ("2025-12-30", "USD", "CNY", "7.00000000", True, False, "sv_fx_prior_only", "2025-12-30"),
        ],
    )
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)

    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    enterprise_type = classification["enterprise_type"]

    class FakeRefreshInput:
        report_date = "2025-12-31"
        is_month_end = True

        def __init__(self):
            self.fi_rows = [
                {
                    "instrument_code": "E001",
                    "asset_class": enterprise_type,
                    "interest_income_514": Decimal("10.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "fx_base_currency": "USD",
                    "source_version": "sv-fi-usd",
                }
            ]
            self.nonstd_rows_by_type = {}

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2025-12-31"],
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025})

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Missing formal fx rate" in detail
    assert "base_currency=USD" in detail
    assert "report_date=2025-12-31" in detail
    get_settings.cache_clear()


def legacy_pnl_by_business_ytd_uses_v1_import_formula_and_sub_type_mapping(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)
    _seed_pnl_by_business_rows(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set sub_type = business_type_primary
            where report_date = '2025-12-31'
            """
        )
    finally:
        conn.close()

    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        fi_rows = [
            {
                "instrument_code": "240001.IB",
                "asset_class": "企业债",
                "interest_income_514": Decimal("106.00"),
                "fair_value_change_516": Decimal("3.00"),
                "capital_gain_517": Decimal("10.00"),
                "source_version": "sv-fi",
            },
            {
                "instrument_code": "NO-ZQTZ.IB",
                "asset_class": "大额存单",
                "interest_income_514": Decimal("106.00"),
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "source_version": "sv-fi",
            },
        ]
        nonstd_rows_by_type = {
            "514": [
                {
                    "voucher_date": "2025-12-15",
                    "asset_code": "JM001",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("106.00"),
                    "source_version": "sv-nonstd-514",
                },
                {
                    "voucher_date": "2025-12-15",
                    "asset_code": "G0001",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("7.00"),
                    "source_version": "sv-nonstd-514",
                },
            ],
            "517": [
                {
                    "voucher_date": "2025-12-16",
                    "asset_code": "SA001",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("20.00"),
                    "source_version": "sv-nonstd-517",
                }
            ],
        }

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2025-12-31"],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    result = payload["result"]
    assert result["year"] == 2025
    assert result["period_label"] == "2025年12月累计"
    by_business = {item["business_type"]: item for item in result["items"]}
    assert by_business["bond-trading"]["interest_income"] == "100.00"
    assert by_business["bond-trading"]["fair_value_change"] == "3.00"
    assert by_business["bond-trading"]["capital_gain"] == "-9.43"
    assert by_business["bond-trading"]["total_pnl"] == "93.57"
    assert by_business["同业存单"]["total_pnl"] == "100.00"
    assert by_business["债权投资"]["total_pnl"] == "100.00"
    assert by_business["信托结构化产品"]["total_pnl"] == "7.00"
    assert by_business["公募基金"]["total_pnl"] == "20.00"
    assert result["total_pnl"] == "320.57"
    get_settings.cache_clear()


def test_pnl_by_business_ytd_respects_as_of_date_cutoff(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        nonstd_rows_by_type: dict[str, list[dict[str, object]]] = {}

        def __init__(self, report_date: str):
            amount = Decimal("10.00") if report_date == "2026-01-31" else Decimal("20.00")
            self.report_date = report_date
            self.is_month_end = True
            self.fi_rows = [
                {
                    "instrument_code": "250001.IB",
                    "asset_class": "政策性金融债",
                    "interest_income_514": amount,
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "source_version": f"sv-{report_date}",
                }
            ]

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **kwargs: FakeRefreshInput(str(kwargs["report_date"])),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2026-02-28", "2026-01-31"],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cutoff_response = client.get(
        "/api/pnl/by-business-ytd",
        params={"year": 2026, "as_of_date": "2026-01-31"},
    )
    full_response = client.get("/api/pnl/by-business-ytd", params={"year": 2026})

    assert cutoff_response.status_code == 200
    assert full_response.status_code == 200
    cutoff_result = cutoff_response.json()["result"]
    full_result = full_response.json()["result"]
    assert cutoff_result["period_label"] == "2026年01月累计"
    assert cutoff_result["period_start_date"] == "2026-01-01"
    assert cutoff_result["period_end_date"] == "2026-01-31"
    assert cutoff_result["total_pnl"] == "10.00"
    assert full_result["period_label"] == "2026年01-02月累计"
    assert full_result["period_start_date"] == "2026-01-01"
    assert full_result["period_end_date"] == "2026-02-28"
    assert full_result["total_pnl"] == "30.00"
    get_settings.cache_clear()


def test_pnl_v1_data_returns_v1_detail_formula_rows(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        report_date = "2025-12-31"
        is_month_end = True
        fi_rows = [
            {
                "instrument_code": "240001.IB",
                "instrument_name": "Test FI",
                "portfolio_name": "FI Desk",
                "asset_class": "企业债",
                "interest_income_514": Decimal("106.00"),
                "fair_value_change_516": Decimal("3.00"),
                "capital_gain_517": Decimal("10.00"),
                "source_version": "sv-fi",
                "trace_id": "tr-fi",
            }
        ]
        nonstd_rows_by_type = {
            "514": [
                {
                    "voucher_date": "2025-12-15",
                    "asset_code": "JM001",
                    "portfolio_name": "NonStd Desk",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("106.00"),
                    "source_version": "sv-nonstd-514",
                    "trace_id": "tr-nonstd-514",
                }
            ],
            "517": [
                {
                    "voucher_date": "2025-12-16",
                    "asset_code": "JM001",
                    "portfolio_name": "NonStd Desk",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("20.00"),
                    "source_version": "sv-nonstd-517",
                    "trace_id": "tr-nonstd-517",
                }
            ],
        }

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/v1-data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.v1_data"
    rows = payload["result"]["rows"]
    by_code = {row["asset_code"]: row for row in rows}
    assert Decimal(by_code["240001.IB"]["interest_income"]).quantize(Decimal("0.01")) == Decimal("106.00")
    assert Decimal(by_code["240001.IB"]["fair_value_change"]).quantize(Decimal("0.01")) == Decimal("3.00")
    assert Decimal(by_code["240001.IB"]["capital_gain"]).quantize(Decimal("0.01")) == Decimal("-9.43")
    assert Decimal(by_code["240001.IB"]["total_pnl"]).quantize(Decimal("0.01")) == Decimal("99.57")
    assert Decimal(by_code["JM001"]["interest_income"]).quantize(Decimal("0.01")) == Decimal("106.00")
    assert Decimal(by_code["JM001"]["capital_gain"]).quantize(Decimal("0.01")) == Decimal("20.00")
    assert Decimal(by_code["JM001"]["total_pnl"]).quantize(Decimal("0.01")) == Decimal("126.00")
    get_settings.cache_clear()


def test_pnl_v1_data_rejects_prior_day_fx_locs_for_report_date(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _replace_pnl_refresh_fx_rows(
        duckdb_path,
        rows=[
            ("2025-12-30", "USD", "CNY", "7.00000000", True, False, "sv_fx_prior_only", "2025-12-30"),
        ],
    )
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        report_date = "2025-12-31"
        is_month_end = True
        fi_rows = [
            {
                "instrument_code": "USD-FI",
                "instrument_name": "USD FI",
                "portfolio_name": "FI Desk",
                "asset_class": "test-bond",
                "interest_income_514": Decimal("10.00"),
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "fx_base_currency": "USD",
                "source_version": "sv-fi-usd",
                "trace_id": "tr-fi-usd",
            }
        ]
        nonstd_rows_by_type = {}

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/v1-data", params={"date": "2025-12-31"})

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Missing formal fx rate" in detail
    assert "base_currency=USD" in detail
    assert "report_date=2025-12-31" in detail
    get_settings.cache_clear()


def test_pnl_yearly_summary_groups_months_by_zqtz_business_type_primary(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    _seed_pnl_by_business_month(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/yearly-summary", params={"year": 2025})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.yearly_summary"
    rows = payload["result"]["rows"]
    assert [row["report_month"] for row in rows] == ["2025-11", "2025-12", "2025-12", "2025-12"]
    by_key = {(row["report_month"], row["business_type_primary"]): row for row in rows}
    assert by_key[("2025-11", "bond-trading")]["total_pnl"] == "6.00"
    assert by_key[("2025-12", "bond-trading")]["total_pnl"] == "111.50"
    assert by_key[("2025-12", "bond-allocation")]["total_pnl"] == "10.00"
    assert by_key[("2025-12", "H")]["total_pnl"] == "4.00"
    get_settings.cache_clear()


def test_yield_by_period_monthly_and_quarterly_rollups_from_formal_pnl(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _grant_liability_analytics_read_scope(
        UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn)
    )
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    _seed_pnl_by_business_month(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    monthly = client.get("/api/analysis/yield-by-period", params={"year": 2025, "period_type": "monthly"})
    assert monthly.status_code == 200
    mbody = monthly.json()
    assert mbody["result_meta"]["result_kind"] == "liability_analytics.yield_by_period"
    mperiods = {p["period"]: p for p in mbody["result"]["periods"]}
    assert mperiods["2025-11"]["num_days"] == 30
    assert abs(float(mperiods["2025-11"]["total_pnl"]) - 6.0) < 1e-6
    assert mperiods["2025-12"]["num_days"] == 31
    assert abs(float(mperiods["2025-12"]["total_pnl"]) - 125.5) < 1e-6

    quarterly = client.get("/api/analysis/yield-by-period", params={"year": 2025, "period_type": "quarterly"})
    assert quarterly.status_code == 200
    qperiods = {p["period"]: p for p in quarterly.json()["result"]["periods"]}
    q4 = qperiods["2025-Q4"]
    assert q4["start_date"] == "2025-10-01"
    assert abs(float(q4["total_pnl"]) - 131.5) < 1e-6

    yearly = client.get("/api/analysis/yield-by-period", params={"year": 2025, "period_type": "yearly"})
    assert yearly.status_code == 200
    yrows = yearly.json()["result"]["periods"]
    assert len(yrows) == 1
    assert yrows[0]["period"] == "2025"
    assert abs(float(yrows[0]["total_pnl"]) - 131.5) < 1e-6
    get_settings.cache_clear()


def test_pnl_dates_returns_union_and_constituent_lists(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.dates"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    assert payload["result"] == {
        "report_dates": ["2026-02-28", "2026-01-31", "2025-12-31"],
        "formal_fi_report_dates": ["2026-01-31", "2025-12-31"],
        "nonstd_bridge_report_dates": ["2026-02-28", "2025-12-31"],
    }
    get_settings.cache_clear()


def test_pnl_data_returns_shared_date_with_two_explicit_lists_and_report_date_build_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(governance_dir, source_version="sv_override", vendor_version="vv_override", rule_version="rv_override")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.data"
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v3"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    assert payload["result"]["report_date"] == "2025-12-31"
    assert len(payload["result"]["formal_fi_rows"]) == 1
    assert len(payload["result"]["nonstd_bridge_rows"]) == 1
    assert payload["result"]["formal_fi_rows"][0]["instrument_code"] == "240001.IB"
    assert payload["result"]["nonstd_bridge_rows"][0]["bond_code"] == "BOND-001"
    get_settings.cache_clear()


def test_pnl_data_returns_one_sided_dates_with_empty_other_list(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    fi_only = client.get("/api/pnl/data", params={"date": "2026-01-31"})
    assert fi_only.status_code == 200
    fi_payload = fi_only.json()["result"]
    assert len(fi_payload["formal_fi_rows"]) == 1
    assert fi_payload["nonstd_bridge_rows"] == []

    nonstd_only = client.get("/api/pnl/data", params={"date": "2026-02-28"})
    assert nonstd_only.status_code == 200
    nonstd_payload = nonstd_only.json()["result"]
    assert nonstd_payload["formal_fi_rows"] == []
    assert len(nonstd_payload["nonstd_bridge_rows"]) == 1
    get_settings.cache_clear()


def test_pnl_data_returns_404_for_absent_union_date(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/data", params={"date": "2027-01-31"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No pnl data found for report_date=2027-01-31 in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
    get_settings.cache_clear()


def test_pnl_overview_returns_backend_owned_aggregation_and_report_date_build_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(governance_dir, source_version="sv_overview", vendor_version="vv_overview", rule_version="rv_overview")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.overview"
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v3"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    assert payload["result"] == {
        "report_date": "2025-12-31",
        "formal_fi_row_count": 1,
        "nonstd_bridge_row_count": 1,
        "interest_income_514": "12.50",
        "fair_value_change_516": "96.75",
        "capital_gain_517": "1.75",
        "manual_adjustment": "0.50",
        "total_pnl": "111.50",
    }
    get_settings.cache_clear()


def test_pnl_overview_keeps_fixed_cache_version_even_if_manifest_contains_cache_version(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_overview_cache",
        vendor_version="vv_overview_cache",
        rule_version="rv_overview_cache",
        cache_version="cv_manifest_override_should_not_apply",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v3"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    get_settings.cache_clear()


def test_pnl_data_prefers_report_date_specific_build_lineage_over_latest_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_manifest_latest",
        vendor_version="vv_manifest_latest",
        rule_version="rv_manifest_latest",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2025-12",
        status="completed",
        source_version="sv_build_2025_12",
        vendor_version="vv_build_2025_12",
        rule_version="rv_build_2025_12",
        report_date="2025-12-31",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2026-01",
        status="completed",
        source_version="sv_build_2026_01",
        vendor_version="vv_build_2026_01",
        rule_version="rv_build_2026_01",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_build_2025_12"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    get_settings.cache_clear()


def test_pnl_data_uses_report_date_specific_build_lineage_without_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2025-12",
        status="completed",
        source_version="sv_build_2025_12",
        vendor_version="vv_build_2025_12",
        rule_version="rv_build_2025_12",
        report_date="2025-12-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_build_2025_12"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    get_settings.cache_clear()


def test_pnl_overview_prefers_report_date_specific_build_lineage_over_latest_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_manifest_latest",
        vendor_version="vv_manifest_latest",
        rule_version="rv_manifest_latest",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2025-12",
        status="completed",
        source_version="sv_build_2025_12",
        vendor_version="vv_build_2025_12",
        rule_version="rv_build_2025_12",
        report_date="2025-12-31",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2026-01",
        status="completed",
        source_version="sv_build_2026_01",
        vendor_version="vv_build_2026_01",
        rule_version="rv_build_2026_01",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_build_2025_12"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
    get_settings.cache_clear()


def test_pnl_bridge_returns_rows_and_phase3_warning_when_balance_rows_are_unavailable(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge",
        vendor_version="vv_bridge",
        rule_version="rv_bridge",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.bridge"
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v3"
    assert "start_pack" not in payload["result_meta"]["cache_version"]
    assert payload["result_meta"]["cache_version"] == (
        "cv_pnl_bridge_formal_v1__cv_pnl_formal__rv_pnl_phase2_materialize_v3__"
        "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1__"
        "cv_yield_curve_formal__rv_yield_curve_formal_materialize_v1"
    )
    assert payload["result"]["report_date"] == "2025-12-31"
    assert len(payload["result"]["rows"]) == 1
    assert payload["result"]["rows"][0]["instrument_code"] == "240001.IB"
    assert payload["result"]["rows"][0]["carry"]["raw"] == 12.5
    assert payload["result"]["rows"][0]["carry"]["unit"] == "yuan"
    assert payload["result"]["rows"][0]["beginning_dirty_mv"]["raw"] == 0.0
    assert payload["result"]["rows"][0]["beginning_dirty_mv"]["sign_aware"] is False
    assert payload["result"]["rows"][0]["ending_dirty_mv"]["raw"] == 0.0
    assert payload["result"]["rows"][0]["ending_dirty_mv"]["sign_aware"] is False
    assert payload["result"]["rows"][0]["current_balance_found"] is False
    assert payload["result"]["rows"][0]["prior_balance_found"] is False
    assert payload["result"]["rows"][0]["balance_diagnostics"] == [
        "Missing current balance row; ending_dirty_mv defaults to 0.",
        "Missing prior balance row; beginning_dirty_mv defaults to 0.",
    ]
    assert payload["result"]["warnings"][0] == (
        "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
    )
    assert "Current balance rows unavailable" in payload["result"]["warnings"][1]
    assert "No prior balance report date found" in payload["result"]["warnings"][2]
    summary = payload["result"]["summary"]
    assert summary["row_count"] == 1
    assert summary["total_carry"]["raw"] == 12.5
    assert summary["total_roll_down"]["raw"] == 0.0
    assert summary["total_treasury_curve"]["raw"] == 0.0
    assert summary["total_credit_spread"]["raw"] == 0.0
    assert summary["total_fx_translation"]["raw"] == 0.0
    assert summary["total_realized_trading"]["raw"] == 1.75
    assert summary["total_unrealized_fv"]["raw"] == -3.25
    assert summary["total_manual_adjustment"]["raw"] == 0.5
    assert summary["total_explained_pnl"]["raw"] == 11.5
    assert summary["total_actual_pnl"]["raw"] == 11.5
    assert summary["total_residual"]["raw"] == 0.0
    get_settings.cache_clear()


def test_pnl_bridge_prefers_report_date_specific_pnl_build_lineage_over_latest_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_manifest_latest",
        vendor_version="vv_pnl_manifest_latest",
        rule_version="rv_pnl_manifest_latest",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="pnl-build-2025-12",
        status="completed",
        source_version="sv_pnl_build_2025_12",
        vendor_version="vv_pnl_build_2025_12",
        rule_version="rv_pnl_build_2025_12",
        report_date="2025-12-31",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="pnl-build-2026-01",
        status="completed",
        source_version="sv_pnl_build_2026_01",
        vendor_version="vv_pnl_build_2026_01",
        rule_version="rv_pnl_build_2026_01",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_pnl_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_pnl_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_build_2025_12"
    get_settings.cache_clear()


def test_pnl_bridge_uses_report_date_specific_pnl_build_lineage_without_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_pnl_build_run(
        governance_dir,
        run_id="pnl-build-2025-12",
        status="completed",
        source_version="sv_pnl_build_2025_12",
        vendor_version="vv_pnl_build_2025_12",
        rule_version="rv_pnl_build_2025_12",
        report_date="2025-12-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_pnl_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_pnl_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_build_2025_12"
    get_settings.cache_clear()


def test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_balance",
        vendor_version="vv_bridge_balance",
        rule_version="rv_bridge_balance",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=True,
        include_unusable_zqtz_intermediate_prior=True,
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1__sv-z-current__sv-z-prior"
    assert payload["result_meta"]["rule_version"] == "rv-z-current__rv-z-prior__rv_pnl_phase2_materialize_v3"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["cache_version"] == (
        "cv_pnl_bridge_formal_v1__cv_pnl_formal__rv_pnl_phase2_materialize_v3__"
        "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1__"
        "cv_yield_curve_formal__rv_yield_curve_formal_materialize_v1"
    )
    row = payload["result"]["rows"][0]
    assert row["instrument_code"] == "240001.IB"
    assert row["beginning_dirty_mv"]["raw"] == 91.0
    assert row["ending_dirty_mv"]["raw"] == 102.0
    assert row["current_balance_found"] is True
    assert row["prior_balance_found"] is True
    assert row["balance_diagnostics"] == []
    summary = payload["result"]["summary"]
    assert summary["total_beginning_dirty_mv"]["raw"] == 91.0
    assert summary["total_ending_dirty_mv"]["raw"] == 102.0
    assert summary["total_carry"]["raw"] == 12.5
    assert summary["total_roll_down"]["raw"] == 0.0
    assert summary["total_treasury_curve"]["raw"] == 0.0
    assert summary["total_credit_spread"]["raw"] == 0.0
    assert summary["total_fx_translation"]["raw"] == 0.0
    assert summary["total_realized_trading"]["raw"] == 1.75
    assert summary["total_unrealized_fv"]["raw"] == -3.25
    assert summary["total_manual_adjustment"]["raw"] == 0.5
    assert summary["total_explained_pnl"]["raw"] == 11.5
    assert summary["total_actual_pnl"]["raw"] == 11.5
    assert summary["total_residual"]["raw"] == 0.0
    assert payload["result"]["warnings"][0] == (
        "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
    )
    assert any(
        "Balance lineage fallback used for report_date=2025-12-31" in warning
        for warning in payload["result"]["warnings"]
    )
    assert any(
        "Balance lineage fallback used for prior_report_date=2025-10-31" in warning
        for warning in payload["result"]["warnings"]
    )
    assert any("No treasury curve available" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_returns_503_when_balance_query_fails(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge",
        vendor_version="vv_bridge",
        rule_version="rv_bridge",
    )
    bridge_service = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )

    def fail_balance_read(*_args, **_kwargs):
        raise RuntimeError("Formal balance query failed for pnl.bridge.")

    monkeypatch.setattr(
        bridge_service.BalanceAnalysisRepository,
        "fetch_pnl_bridge_zqtz_balance_rows",
        fail_balance_read,
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal balance query failed for pnl.bridge."
    get_settings.cache_clear()


def test_pnl_bridge_result_meta_merges_report_date_specific_balance_build_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_bridge_meta",
        vendor_version="vv_pnl_bridge_meta",
        rule_version="rv_pnl_bridge_meta",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current",
        report_date="2025-12-31",
        source_version="sv_balance_current",
        vendor_version="vv_balance",
        rule_version="rv_balance_current",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-newer-unrelated",
        report_date="2026-01-31",
        source_version="sv_balance_newer",
        vendor_version="vv_balance",
        rule_version="rv_balance_newer",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == (
        "fi-shared-v1__nonstd-shared-v1__sv_balance_current__sv_balance_prior"
    )
    assert payload["result_meta"]["rule_version"] == (
        "rv_balance_current__rv_balance_prior__rv_pnl_phase2_materialize_v3"
    )
    assert payload["result_meta"]["vendor_version"] == "vv_balance__vv_none"
    assert payload["result"]["warnings"][0] == (
        "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
    )
    assert any("No treasury curve available" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_prefers_latest_valid_balance_build_when_newer_completed_row_has_blank_source_version(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_bridge_meta",
        vendor_version="vv_pnl_bridge_meta",
        rule_version="rv_pnl_bridge_meta",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current-valid",
        report_date="2025-12-31",
        source_version="sv_balance_current_valid",
        vendor_version="vv_balance",
        rule_version="rv_balance_current_valid",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current-invalid-newer",
        report_date="2025-12-31",
        source_version="",
        vendor_version="vv_balance",
        rule_version="rv_balance_current_invalid",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == (
        "fi-shared-v1__nonstd-shared-v1__sv_balance_current_valid__sv_balance_prior"
    )
    assert payload["result_meta"]["rule_version"] == (
        "rv_balance_current_valid__rv_balance_prior__rv_pnl_phase2_materialize_v3"
    )
    assert not any(
        "Balance lineage fallback used for report_date=2025-12-31" in warning
        for warning in payload["result"]["warnings"]
    )
    get_settings.cache_clear()


def test_pnl_bridge_reads_fx_rates_from_duckdb_and_populates_fx_translation(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_fx",
        vendor_version="vv_bridge_fx",
        rule_version="rv_bridge_fx",
    )
    _seed_usd_pnl_bridge_balance_rows(duckdb_path)
    _seed_pnl_bridge_snapshot_face_values(duckdb_path)
    _seed_pnl_bridge_fx_rates(duckdb_path)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    row = payload["result"]["rows"][0]
    # dirty exposure = market 100 + accrued 2 = 102; 102 * (7.0827 - 7.04135) = 4.2177
    assert row["fx_translation"]["raw"] == 4.2177
    assert payload["result"]["summary"]["total_fx_translation"]["raw"] == 4.2177
    assert any("currency_basis mismatch" in warning for warning in payload["result"]["warnings"])
    assert any("currency_basis mismatch" in message for message in row["balance_diagnostics"])
    get_settings.cache_clear()


def test_pnl_bridge_rejects_prior_day_fx_locs_for_report_date(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_fx",
        vendor_version="vv_bridge_fx",
        rule_version="rv_bridge_fx",
    )
    _seed_usd_pnl_bridge_balance_rows(duckdb_path)
    _seed_pnl_bridge_snapshot_face_values(duckdb_path)
    _seed_pnl_bridge_fx_rates(
        duckdb_path,
        rows=[
            ("2025-12-30", "USD", "CNY", "7.08270000", True, False, "sv_fx_prior_day", "2025-12-30"),
            ("2025-10-31", "USD", "CNY", "7.04135000", True, False, "sv_fx_prior_exact", "2025-10-31"),
        ],
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Missing formal fx rate" in detail
    assert "base_currency=USD" in detail
    assert "report_date=2025-12-31" in detail
    get_settings.cache_clear()


def test_pnl_bridge_rejects_business_day_fx_carry_forward(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_fx",
        vendor_version="vv_bridge_fx",
        rule_version="rv_bridge_fx",
    )
    _seed_usd_pnl_bridge_balance_rows(duckdb_path)
    _seed_pnl_bridge_snapshot_face_values(duckdb_path)
    _seed_pnl_bridge_fx_rates(
        duckdb_path,
        rows=[
            ("2025-12-31", "USD", "CNY", "7.08270000", False, True, "sv_fx_current_carry", "2025-12-30"),
            ("2025-10-31", "USD", "CNY", "7.04135000", True, False, "sv_fx_prior_exact", "2025-10-31"),
        ],
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Invalid formal fx carry-forward metadata" in detail
    assert "carry-forward is only allowed" in detail
    get_settings.cache_clear()


def test_pnl_bridge_rejects_contradictory_fx_carry_forward_metadata(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_fx",
        vendor_version="vv_bridge_fx",
        rule_version="rv_bridge_fx",
    )
    _seed_usd_pnl_bridge_balance_rows(duckdb_path)
    _seed_pnl_bridge_snapshot_face_values(duckdb_path)
    _seed_pnl_bridge_fx_rates(
        duckdb_path,
        rows=[
            ("2025-12-31", "USD", "CNY", "7.08270000", False, True, "sv_fx_current_bad", "2025-12-31"),
            ("2025-10-31", "USD", "CNY", "7.04135000", True, False, "sv_fx_prior_exact", "2025-10-31"),
        ],
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 404
    assert "Invalid formal fx carry-forward metadata" in response.json()["detail"]
    get_settings.cache_clear()


def test_pnl_overview_returns_404_for_absent_union_date(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/overview", params={"report_date": "2027-01-31"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No pnl data found for report_date=2027-01-31 in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
    get_settings.cache_clear()


def test_pnl_refresh_queue_and_latest_import_status_flow(tmp_path, monkeypatch):
    duckdb_path, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    def fake_send(**kwargs):
        queued_messages.append(kwargs)
        return None

    monkeypatch.setattr(pnl_service.materialize_pnl_facts, "send", fake_send)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/api/data/refresh_pnl")

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "queued"
    assert refresh_payload["job_name"] == "pnl_materialize"
    assert refresh_payload["trigger_mode"] == "async"
    assert refresh_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert refresh_payload["report_date"] == "2026-02-28"
    assert queued_messages[0]["run_id"] == refresh_payload["run_id"]
    assert queued_messages[0]["report_date"] == "2026-02-28"
    assert queued_messages[0]["is_month_end"] is True
    assert len(queued_messages[0]["fi_rows"]) > 0
    assert len(queued_messages[0]["nonstd_rows_by_type"]["516"]) == 2

    queued_status = client.get("/api/data/import_status/pnl")
    assert queued_status.status_code == 200
    assert queued_status.json()["status"] == "queued"
    assert queued_status.json()["run_id"] == refresh_payload["run_id"]

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        CacheBuildRunRecord(
            run_id=refresh_payload["run_id"],
            job_name="pnl_materialize",
            status="completed",
            cache_key="pnl:phase2:materialize:formal",
            lock="lock:duckdb:formal:pnl:phase2:materialize",
            source_version="sv_pnl_test",
            vendor_version="vv_none",
        ).model_dump(),
    )

    completed_status = client.get("/api/data/import_status/pnl")
    assert completed_status.status_code == 200
    completed_payload = completed_status.json()
    assert completed_payload["status"] == "completed"
    assert completed_payload["run_id"] == refresh_payload["run_id"]
    assert completed_payload["trigger_mode"] == "terminal"
    assert completed_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert completed_payload["source_version"] == "sv_pnl_test"
    assert duckdb_path.exists() is False
    get_settings.cache_clear()


def test_pnl_refresh_reuses_run_for_same_idempotency_key(tmp_path, monkeypatch):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    headers = {"Idempotency-Key": "pnl-refresh-2026-02-28"}

    first_response = client.post("/api/data/refresh_pnl", headers=headers)
    second_response = client.post("/api/data/refresh_pnl", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert second_payload["run_id"] == first_payload["run_id"]
    assert second_payload["idempotency_key"] == "pnl-refresh-2026-02-28"
    assert second_payload["idempotency_replay"] is True
    assert len(queued_messages) == 1

    records = [
        record
        for record in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        if record.get("job_name") == "pnl_materialize"
        and record.get("run_id") == first_payload["run_id"]
    ]
    assert len(records) == 1
    get_settings.cache_clear()


def test_pnl_refresh_requeues_stale_inflight_run_for_same_idempotency_key(tmp_path, monkeypatch):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _append_pnl_build_run(
        governance_dir,
        run_id="run-stale-idempotent",
        status="running",
        source_version="sv_pending",
        report_date="2026-02-28",
        queued_at=stale_time,
        idempotency_key="pnl-refresh-2026-02-28",
    )

    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post(
        "/api/data/refresh_pnl",
        headers={"Idempotency-Key": "pnl-refresh-2026-02-28"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["idempotency_key"] == "pnl-refresh-2026-02-28"
    assert payload["idempotency_replay"] is False
    assert payload["run_id"] != "run-stale-idempotent"
    assert len(queued_messages) == 1
    assert queued_messages[0]["run_id"] == payload["run_id"]
    assert queued_messages[0]["report_date"] == "2026-02-28"

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    stale_records = [record for record in records if record.get("run_id") == "run-stale-idempotent"]
    assert stale_records[-1]["status"] == "failed"
    assert stale_records[-1]["error_message"] == "Marked stale pnl idempotent refresh run as failed."
    get_settings.cache_clear()


def test_pnl_refresh_requires_explicit_refresh_scope_grant(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    scope_repo = _setup_route_scope_store(tmp_path, monkeypatch)
    route_module = load_module("backend.app.api.routes.pnl", "backend/app/api/routes/pnl.py")
    calls: list[str | None] = []

    def fake_refresh(settings, *, report_date=None, **_kwargs):
        calls.append(report_date)
        return {"status": "queued", "run_id": "pnl-refresh-auth-test"}

    monkeypatch.setattr(route_module._pnl_service(), "refresh_pnl", fake_refresh)
    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )

    denied = client.post(
        "/api/data/refresh_pnl",
        headers={"X-User-Id": "pnl-refresh-user", "X-User-Role": "viewer"},
    )
    assert denied.status_code == 403, denied.text
    assert calls == []

    scope_repo.grant_scope(
        user_id="pnl-refresh-user",
        role=None,
        resource="formal_pnl",
        action="refresh",
    )
    allowed = client.post(
        "/api/data/refresh_pnl",
        headers={"X-User-Id": "pnl-refresh-user", "X-User-Role": "viewer"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["run_id"] == "pnl-refresh-auth-test"
    assert calls == [None]
    get_settings.cache_clear()


def test_pnl_refresh_sync_fallback_materializes_latest_sources(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/api/data/refresh_pnl")

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "completed"
    assert refresh_payload["job_name"] == "pnl_materialize"
    assert refresh_payload["trigger_mode"] == "sync-fallback"
    assert refresh_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert refresh_payload["report_date"] == "2026-02-28"
    assert refresh_payload["formal_fi_rows"] > 0
    assert refresh_payload["nonstd_bridge_rows"] == 1

    status_response = client.get("/api/data/import_status/pnl")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["run_id"] == refresh_payload["run_id"]
    assert status_payload["report_date"] == "2026-02-28"
    assert status_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert status_payload["job_name"] == "pnl_materialize"

    dates_response = client.get("/api/pnl/dates")
    assert dates_response.status_code == 200
    assert dates_response.json()["result"]["report_dates"] == ["2026-02-28"]

    data_response = client.get("/api/pnl/data", params={"date": "2026-02-28"})
    assert data_response.status_code == 200
    assert len(data_response.json()["result"]["formal_fi_rows"]) > 0
    assert len(data_response.json()["result"]["nonstd_bridge_rows"]) == 1
    get_settings.cache_clear()


def test_pnl_refresh_sync_fallback_uses_direct_sync_helper(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    sync_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )
    monkeypatch.setattr(
        pnl_service,
        "run_pnl_materialize_sync",
        lambda **kwargs: sync_calls.append(kwargs) or {
            "status": "completed",
            "cache_key": "pnl:phase2:materialize:formal",
            "run_id": kwargs["run_id"],
            "report_date": kwargs["report_date"],
            "formal_fi_rows": 1,
            "nonstd_bridge_rows": 1,
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "vendor_version": "vv_none",
            "lock": "lock:duckdb:formal:pnl:phase2:materialize",
        },
    )

    payload = pnl_service.refresh_pnl(get_settings())

    assert payload["status"] == "completed"
    assert payload["trigger_mode"] == "sync-fallback"
    assert sync_calls
    assert sync_calls[0]["report_date"] == "2026-02-28"


def test_pnl_refresh_returns_503_when_send_error_is_not_safe_for_sync_fallback(
    tmp_path,
    monkeypatch,
):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    fallback_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("unexpected broker failure")),
    )
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "fn",
        lambda **kwargs: fallback_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Pnl refresh queue dispatch failed: RuntimeError: unexpected broker failure"
    )
    assert fallback_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    latest = [record for record in records if record.get("job_name") == "pnl_materialize"][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == (
        "Pnl refresh queue dispatch failed: RuntimeError: unexpected broker failure"
    )
    assert latest["failure_category"] == "RuntimeError"
    assert latest["failure_reason"] == "unexpected broker failure"
    get_settings.cache_clear()


def test_pnl_refresh_returns_409_when_same_report_date_is_already_in_progress(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    governance_dir = tmp_path / "governance"
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-inflight",
                job_name="pnl_materialize",
                status="running",
                cache_key="pnl:phase2:materialize:formal",
                lock="lock:duckdb:formal:pnl:phase2:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2026-02-28",
            "queued_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: send_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 409
    assert response.json()["detail"] == "Pnl refresh already in progress for report_date=2026-02-28."
    assert send_calls == []
    get_settings.cache_clear()


def test_pnl_refresh_returns_409_when_legacy_inflight_has_no_timestamps(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    governance_dir = tmp_path / "governance"
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-legacy-inflight",
                job_name="pnl_materialize",
                status="running",
                cache_key="pnl:phase2:materialize:formal",
                lock="lock:duckdb:formal:pnl:phase2:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2026-02-28",
        },
    )

    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: send_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 409
    assert response.json()["detail"] == "Pnl refresh already in progress for report_date=2026-02-28."
    assert send_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    legacy = [record for record in records if record.get("run_id") == "run-legacy-inflight"]
    assert len(legacy) == 1
    assert legacy[0]["status"] == "running"
    get_settings.cache_clear()


def test_pnl_refresh_reconciles_stale_inflight_run_and_requeues_requested_month(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    governance_dir = tmp_path / "governance"
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-stale",
                job_name="pnl_materialize",
                status="running",
                cache_key="pnl:phase2:materialize:formal",
                lock="lock:duckdb:formal:pnl:phase2:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2026-02-28",
            "queued_at": stale_time,
        },
    )

    queued_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert queued_messages[0]["report_date"] == "2026-02-28"

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    stale_records = [record for record in records if record.get("run_id") == "run-stale"]
    assert stale_records[-1]["status"] == "failed"
    assert stale_records[-1]["error_message"] == "Marked stale pnl refresh run as failed."
    get_settings.cache_clear()


def test_pnl_refresh_report_date_queues_exact_requested_month(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["report_date"] == "2026-01-31"
    assert queued_messages[0]["report_date"] == "2026-01-31"
    assert queued_messages[0]["nonstd_rows_by_type"] == {}
    get_settings.cache_clear()


def test_pnl_refresh_report_date_sync_fallback_materializes_requested_month(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["report_date"] == "2026-01-31"
    assert payload["nonstd_bridge_rows"] == 0

    dates_response = client.get("/api/pnl/dates")
    assert dates_response.status_code == 200
    assert dates_response.json()["result"]["report_dates"] == ["2026-01-31"]
    get_settings.cache_clear()


def test_pnl_refresh_report_date_returns_404_when_requested_month_is_missing(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/data/refresh_pnl", params={"report_date": "2024-12-31"})

    assert response.status_code == 404
    assert "2024-12-31" in response.json()["detail"]
    get_settings.cache_clear()


def test_pnl_refresh_report_date_prefers_manifest_source_over_direct_source_for_same_family(
    tmp_path,
    monkeypatch,
):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    manifest_fi = _create_archived_copy(
        tmp_path,
        source_file=ROOT / "data_input" / "pnl" / "FI损益202601.xls",
        archive_name="manifest-fi-202601.xls",
    )
    _append_source_manifest_row(
        governance_dir,
        source_family="pnl",
        report_date="2026-01-31",
        source_file="FI损益202601.xls",
        archived_path=manifest_fi,
        source_version="sv_manifest_fi_202601",
        ingest_batch_id="ib_manifest_fi_202601",
    )

    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    assert response.json()["report_date"] == "2026-01-31"
    assert queued_messages
    assert queued_messages[0]["fi_rows"]
    assert {
        row["source_version"] for row in queued_messages[0]["fi_rows"]
    } == {"sv_manifest_fi_202601"}
    get_settings.cache_clear()


def test_pnl_refresh_report_date_mixes_manifest_and_direct_sources_by_family(
    tmp_path,
    monkeypatch,
):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    _write_nonstd_refresh_workbook(
        tmp_path / "data_input" / "pnl_516" / "非标516-20260101-0131.xlsx",
        row_dates=("2026-01-30", "2026-01-31"),
    )
    manifest_fi = _create_archived_copy(
        tmp_path,
        source_file=ROOT / "data_input" / "pnl" / "FI损益202601.xls",
        archive_name="manifest-fi-202601.xls",
    )
    _append_source_manifest_row(
        governance_dir,
        source_family="pnl",
        report_date="2026-01-31",
        source_file="FI损益202601.xls",
        archived_path=manifest_fi,
        source_version="sv_manifest_fi_202601",
        ingest_batch_id="ib_manifest_fi_202601",
    )

    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    assert queued_messages
    fi_rows = queued_messages[0]["fi_rows"]
    nonstd_rows = queued_messages[0]["nonstd_rows_by_type"]["516"]
    assert {row["source_version"] for row in fi_rows} == {"sv_manifest_fi_202601"}
    assert all(row["source_version"] != "sv_manifest_fi_202601" for row in nonstd_rows)
    assert all(str(row["source_version"]).startswith("sv_pnl_") for row in nonstd_rows)
    get_settings.cache_clear()


def test_pnl_refresh_report_date_uses_covering_nonstd_range_when_exact_month_end_missing(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    _write_nonstd_refresh_workbook(
        tmp_path / "data_input" / "pnl_516" / "非标516-20260101-0228.xlsx",
        row_dates=("2026-01-30", "2026-02-28"),
    )

    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    assert queued_messages
    nonstd_rows = queued_messages[0]["nonstd_rows_by_type"]["516"]
    assert [row["voucher_date"] for row in nonstd_rows] == ["2026-01-30"]
    assert nonstd_rows[0]["source_file"] == "非标516-20260101-0228.xlsx"
    get_settings.cache_clear()


def test_pnl_refresh_ignores_nonstd_rows_outside_target_report_month(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    nonstd_path = next((tmp_path / "data_input" / "pnl_516").glob("*.xlsx"))
    _write_nonstd_refresh_workbook(
        nonstd_path,
        include_prior_month_row=True,
    )
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/api/data/refresh_pnl")

    assert refresh_response.status_code == 200
    assert refresh_response.json()["status"] == "completed"

    data_response = client.get("/api/pnl/data", params={"date": "2026-02-28"})

    assert data_response.status_code == 200
    bridge_row = data_response.json()["result"]["nonstd_bridge_rows"][0]
    assert Decimal(bridge_row["fair_value_change_516"]) == Decimal("100.00")
    assert Decimal(bridge_row["total_pnl"]) == Decimal("100.00")
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_exact_queued_record(tmp_path, monkeypatch):
    governance_dir = _configure_import_status_env(tmp_path, monkeypatch)
    _append_pnl_build_run(governance_dir, run_id="run-queued", status="queued", source_version="sv_queued")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-queued"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-queued"
    assert payload["status"] == "queued"
    assert payload["source_version"] == "sv_queued"
    assert payload["trigger_mode"] == "async"
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_latest_matching_completed_record_without_unrelated_fallback(tmp_path, monkeypatch):
    governance_dir = _configure_import_status_env(tmp_path, monkeypatch)
    _append_pnl_build_run(governance_dir, run_id="run-target", status="queued", source_version="sv_q")
    _append_pnl_build_run(governance_dir, run_id="run-target", status="running", source_version="sv_r")
    _append_pnl_build_run(governance_dir, run_id="run-target", status="completed", source_version="sv_done")
    _append_pnl_build_run(governance_dir, run_id="run-newer", status="queued", source_version="sv_other")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-target"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-target"
    assert payload["status"] == "completed"
    assert payload["source_version"] == "sv_done"
    assert payload["trigger_mode"] == "terminal"
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_failed_terminal_record(tmp_path, monkeypatch):
    governance_dir = _configure_import_status_env(tmp_path, monkeypatch)
    _append_pnl_build_run(governance_dir, run_id="run-failed", status="queued", source_version="sv_q")
    _append_pnl_build_run(
        governance_dir,
        run_id="run-failed",
        status="failed",
        source_version="sv_failed",
        error_message="duckdb transaction rolled back",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-failed"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-failed"
    assert payload["status"] == "failed"
    assert payload["source_version"] == "sv_failed"
    assert payload["trigger_mode"] == "terminal"
    assert payload["error_message"] == "duckdb transaction rolled back"
    assert payload["report_date"] == "2026-01-31"
    assert payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert payload["job_name"] == "pnl_materialize"
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_404_for_unknown_run_id(tmp_path, monkeypatch):
    _configure_import_status_env(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown pnl refresh run_id=run-missing"
    get_settings.cache_clear()


def test_pnl_import_status_returns_503_when_status_backend_fails(tmp_path, monkeypatch):
    _configure_import_status_env(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service.GovernanceRepository,
        "read_all",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("status backend unavailable")),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-any"})

    assert response.status_code == 503
    assert response.json()["detail"] == "status backend unavailable"
    get_settings.cache_clear()


def test_pnl_dates_returns_503_when_storage_is_unavailable(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/dates")

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal pnl storage is unavailable."
    get_settings.cache_clear()


def test_pnl_overview_returns_503_when_storage_is_unavailable(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal pnl storage is unavailable."
    get_settings.cache_clear()


def test_pnl_dates_returns_503_when_required_tables_are_missing(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")
    duckdb_path = tmp_path / "empty-schema.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/dates")

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal pnl storage is unavailable."
    get_settings.cache_clear()


def test_pnl_dates_accepts_single_available_fact_table(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")
    duckdb_path = tmp_path / "formal-fi-only.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              currency_basis varchar,
              interest_income_514 decimal(24, 8),
              fair_value_change_516 decimal(24, 8),
              capital_gain_517 decimal(24, 8),
              manual_adjustment decimal(24, 8),
              total_pnl decimal(24, 8),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P001', 'Rate Desk', 'CC-RATE', 'T', 'FVTPL', 'CNY',
              100.00, 0.00, 25.50, 0.00, 125.50,
              'fi-only-v1', 'rv_pnl_phase2_materialize_v1', 'ib-fi-only', 'trace-fi-only'
            )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/dates")

    assert response.status_code == 200
    assert response.json()["result"]["report_dates"] == ["2025-12-31"]
    assert response.json()["result"]["formal_fi_report_dates"] == ["2025-12-31"]
    assert response.json()["result"]["nonstd_bridge_report_dates"] == []
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/pnl/data", {"date": "2025-12-31"}),
        ("/api/pnl/v1-data", {"date": "2025-12-31"}),
        ("/api/pnl/by-business", {"report_date": "2025-12-31"}),
        ("/api/pnl/by-business-ytd", {"year": 2025, "as_of_date": "2025-12-31"}),
        ("/api/pnl/by-business-monthly", {"year": 2025, "as_of_date": "2025-12-31"}),
        ("/api/pnl/by-business-analysis", {"year": 2025, "as_of_date": "2025-12-31"}),
        ("/api/pnl/yearly-summary", {"year": 2025}),
    ],
)
def test_pnl_finance_read_surfaces_return_503_when_storage_is_unavailable(
    path,
    params,
    tmp_path,
    monkeypatch,
):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(path, params=params)

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal pnl storage is unavailable."
    get_settings.cache_clear()


def _materialize_three_pnl_dates(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", '["*"]')
    get_settings.cache_clear()

    shared = {
        "report_date": "2025-12-31",
        "is_month_end": True,
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
    }
    task_module.materialize_pnl_facts.fn(
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "12.50",
                "fair_value_change_516": "-3.25",
                "capital_gain_517": "1.75",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "source_version": "fi-shared-v1",
                "rule_version": "src-rule-fi-shared",
                "ingest_batch_id": "batch-fi-shared",
                "trace_id": "trace-fi-shared",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={
            "516": [
                {
                    "voucher_date": "2025-12-30",
                    "account_code": "51601010004",
                    "asset_code": "BOND-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "credit",
                    "event_type": "mtm",
                    "raw_amount": "40.00",
                    "source_file": "nonstd-516.xlsx",
                    "source_version": "nonstd-shared-v1",
                    "rule_version": "src-rule-nonstd-shared",
                    "ingest_batch_id": "batch-bridge-shared",
                    "trace_id": "trace-001",
                },
                {
                    "voucher_date": "2025-12-31",
                    "account_code": "51601010004",
                    "asset_code": "BOND-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "credit",
                    "event_type": "mtm",
                    "raw_amount": "60.00",
                    "source_file": "nonstd-516.xlsx",
                    "source_version": "nonstd-shared-v1",
                    "rule_version": "src-rule-nonstd-shared",
                    "ingest_batch_id": "batch-bridge-shared",
                    "trace_id": "trace-002",
                },
            ]
        },
        **shared,
    )

    task_module.materialize_pnl_facts.fn(
        fi_rows=[
            {
                "report_date": "2026-01-31",
                "instrument_code": "250001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC200",
                "invest_type_raw": "持有至到期",
                "interest_income_514": "20.00",
                "fair_value_change_516": "0.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0.00",
                "currency_basis": "CNY",
                "source_version": "fi-only-v1",
                "rule_version": "src-rule-fi-only",
                "ingest_batch_id": "batch-fi-only",
                "trace_id": "trace-fi-only",
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        report_date="2026-01-31",
        is_month_end=True,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    task_module.materialize_pnl_facts.fn(
        fi_rows=[],
        nonstd_rows_by_type={
            "514": [
                {
                    "voucher_date": "2026-02-28",
                    "account_code": "51401000004",
                    "asset_code": None,
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC300",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "15.00",
                    "source_file": "nonstd-514.xlsx",
                    "source_version": "nonstd-only-v1",
                    "rule_version": "src-rule-nonstd-only",
                    "ingest_batch_id": "batch-bridge-only",
                    "trace_id": "trace-514",
                }
            ]
        },
        report_date="2026-02-28",
        is_month_end=True,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    return governance_dir


def _append_manifest_override(
    governance_dir,
    *,
    source_version: str,
    vendor_version: str,
    rule_version: str,
    cache_version: str | None = None,
):
    manifest_path = governance_dir / "cache_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "cache_key": "pnl:phase2:materialize:formal",
                    "cache_version": cache_version,
                    "source_version": source_version,
                    "vendor_version": vendor_version,
                    "rule_version": rule_version,
                },
                ensure_ascii=False,
        )
            + "\n"
        )


def _seed_pnl_bridge_balance_rows(
    duckdb_path: Path,
    *,
    include_tyw_only_intermediate_prior: bool,
    include_unusable_zqtz_intermediate_prior: bool = False,
) -> None:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "240001.IB",
                "FI Desk",
                "CC100",
                "T",
                "FVTPL",
                "asset",
                "CNY",
                "CNY",
                "100.00000000",
                "99.00000000",
                "2.00000000",
                False,
                "sv-z-current",
                "rv-z-current",
                "ib-z-current",
                "trace-z-current",
            ],
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-10-31",
                "240001.IB",
                "FI Desk",
                "CC100",
                "T",
                "FVTPL",
                "asset",
                "CNY",
                "CNY",
                "90.00000000",
                "89.00000000",
                "1.00000000",
                False,
                "sv-z-prior",
                "rv-z-prior",
                "ib-z-prior",
                "trace-z-prior",
            ],
        )
        if include_tyw_only_intermediate_prior:
            conn.execute(
                """
                insert into fact_formal_tyw_balance_daily (
                  report_date, position_id, product_type, position_side, counterparty_name,
                  invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
                  principal_amount, accrued_interest_amount, source_version, rule_version,
                  ingest_batch_id, trace_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "2025-11-30",
                    "tyw-only-prior",
                    "Interbank",
                    "liability",
                    "Bank A",
                    "H",
                    "AC",
                    "liability",
                    "CNY",
                    "CNY",
                    "50.00000000",
                    "5.00000000",
                    "sv-tyw-prior",
                    "rv-tyw-prior",
                    "ib-tyw-prior",
                    "trace-tyw-prior",
                ],
            )
        if include_unusable_zqtz_intermediate_prior:
            conn.execute(
                """
                insert into fact_formal_zqtz_balance_daily (
                  report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
                  accounting_basis, position_scope, currency_basis, currency_code,
                  market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
                  source_version, rule_version, ingest_batch_id, trace_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "2025-11-30",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "T",
                    "FVTPL",
                    "liability",
                    "native",
                    "CNY",
                    "999.00000000",
                    "999.00000000",
                    "9.00000000",
                    True,
                    "sv-z-unusable",
                    "rv-z-unusable",
                    "ib-z-unusable",
                    "trace-z-unusable",
                ],
            )
    finally:
        conn.close()


def _seed_pnl_by_business_rows(duckdb_path: Path) -> None:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute("delete from fact_formal_zqtz_balance_daily where report_date = '2025-12-31'")
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "001",
                    "FI Desk",
                    "CC100",
                    "bond-trading",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "100.00000000",
                    "99.00000000",
                    "2.00000000",
                    False,
                    "sv-z-biz",
                    "rv-z-biz",
                    "ib-z-biz",
                    "trace-z-biz-1",
                ),
                (
                    "2025-12-31",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "bond-trading",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "999.00000000",
                    "998.00000000",
                    "9.00000000",
                    False,
                    "sv-z-biz-dup",
                    "rv-z-biz",
                    "ib-z-biz-dup",
                    "trace-z-biz-dup",
                ),
                (
                    "2025-12-31",
                    "250002.IB",
                    "FI Desk",
                    "CC200",
                    "bond-allocation",
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "300.00000000",
                    "300.00000000",
                    "3.00000000",
                    False,
                    "sv-z-biz",
                    "rv-z-biz",
                    "ib-z-biz",
                    "trace-z-biz-2",
                ),
            ],
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', '250002.IB', 'FI Desk', 'CC200', 'H', 'AC', 'CNY',
              8.00, 0.00, 2.00, 0.00, 10.00,
              'fi-extra-v1', 'rv_pnl_phase2_materialize_v1', 'ib-extra', 'trace-fi-extra'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'NO-ZQTZ.IB', 'FI Desk', 'CC999', 'H', 'AC', 'CNY',
              4.00, 0.00, 0.00, 0.00, 4.00,
              'fi-unmatched-v1', 'rv_pnl_phase2_materialize_v1', 'ib-unmatched', 'trace-fi-unmatched'
            )
            """
        )
    finally:
        conn.close()


def _seed_pnl_by_business_ytd_balance_rows(duckdb_path: Path) -> dict[str, str]:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    other_type = str(row_defs["asset_zqtz_non_bottom_investment"]["bond_types"][0])
    enterprise_type = str(row_defs["asset_zqtz_nonfinancial_enterprise_bond"]["match_keywords"][1])
    commercial_type = str(row_defs["asset_zqtz_commercial_financial_bond"]["match_keywords"][2])
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute("delete from fact_formal_zqtz_balance_daily where report_date = '2025-12-31'")
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              observed_trade_date varchar,
              source_version varchar
            )
            """
        )
        conn.execute("alter table fx_daily_mid add column if not exists source_name varchar")
        conn.execute("alter table fx_daily_mid add column if not exists is_business_day boolean")
        conn.execute("alter table fx_daily_mid add column if not exists is_carry_forward boolean")
        conn.execute("alter table fx_daily_mid add column if not exists observed_trade_date varchar")
        conn.execute("delete from fx_daily_mid where trade_date = '2025-12-31'")
        conn.execute(
            """
            insert into fx_daily_mid (
              trade_date, base_currency, quote_currency, mid_rate, source_name,
              is_business_day, is_carry_forward, observed_trade_date, source_version
            )
            values ('2025-12-31', 'USD', 'CNY', 7.00000000, 'CFETS', true, false, '2025-12-31', 'sv_fx_ytd_balance')
            """
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "J4001",
                    "J4 structured",
                    "NonStd Desk",
                    "CC-J4",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "1000.00000000",
                    "1000.00000000",
                    "5.00000000",
                    False,
                    "sv-z-j4",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j4",
                ),
                (
                    "2025-12-31",
                    "J1001",
                    "J1 delegated",
                    "NonStd Desk",
                    "CC-J1",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "2000.00000000",
                    "2000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j1",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j1",
                ),
                (
                    "2025-12-31",
                    "J02205260102",
                    "J0 market",
                    "NonStd Desk",
                    "CC-J0-M",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "3000.00000000",
                    "3000.00000000",
                    "7.00000000",
                    False,
                    "sv-z-j0-market",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-market",
                ),
                (
                    "2025-12-31",
                    "J09999990102",
                    "J0 cost",
                    "NonStd Desk",
                    "CC-J0-C",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "4000.00000000",
                    "4000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j0-cost",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-cost",
                ),
                (
                    "2025-12-31",
                    "JM001",
                    "JM debt",
                    "NonStd Desk",
                    "CC-JM",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "5000.00000000",
                    "5000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-jm",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-jm",
                ),
                (
                    "2025-12-31",
                    "SA001",
                    "SA fund",
                    "NonStd Desk",
                    "CC-SA",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "6000.00000000",
                    "6000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-sa",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-sa",
                ),
                (
                    "2025-12-31",
                    "E001",
                    "enterprise bond",
                    "FI Desk",
                    "CC-E",
                    "asset",
                    enterprise_type,
                    enterprise_type,
                    enterprise_type,
                    enterprise_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "7000.00000000",
                    "7000.00000000",
                    "70.00000000",
                    False,
                    "sv-z-enterprise",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-enterprise",
                ),
                (
                    "2025-12-31",
                    "C001",
                    "commercial bank bond",
                    "FI Desk",
                    "CC-C",
                    "asset",
                    commercial_type,
                    commercial_type,
                    commercial_type,
                    commercial_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "8000.00000000",
                    "8000.00000000",
                    "80.00000000",
                    False,
                    "sv-z-commercial",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-commercial",
                ),
            ],
        )
    finally:
        conn.close()
    return {
        "enterprise_type": enterprise_type,
        "commercial_type": commercial_type,
        "other_type": other_type,
    }


def _replace_pnl_refresh_fx_rows(
    duckdb_path: Path,
    *,
    rows: list[tuple[str, str, str, str, bool, bool, str, str]],
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute("delete from fx_daily_mid")
        conn.executemany(
            """
            insert into fx_daily_mid (
              trade_date, base_currency, quote_currency, mid_rate,
              source_name, is_business_day, is_carry_forward, source_version,
              observed_trade_date
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    trade_date,
                    base_currency,
                    quote_currency,
                    mid_rate,
                    "CFETS",
                    is_business_day,
                    is_carry_forward,
                    source_version,
                    observed_trade_date,
                )
                for trade_date, base_currency, quote_currency, mid_rate, is_business_day, is_carry_forward, source_version, observed_trade_date in rows
            ],
        )
    finally:
        conn.close()


def _seed_pnl_by_business_month(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi (
              report_date, instrument_code, portfolio_name, cost_center,
              invest_type_std, accounting_basis, currency_basis,
              interest_income_514, fair_value_change_516, capital_gain_517,
              manual_adjustment, total_pnl, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-11-30', '240001.IB', 'FI Desk', 'CC100', 'T', 'FVTPL', 'CNY',
              5.00, 1.00, 0.00, 0.00, 6.00,
              'fi-nov-v1', 'rv_pnl_phase2_materialize_v1', 'ib-nov', 'trace-fi-nov'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-11-30', '240001.IB', 'FI Desk', 'CC100', 'bond-trading',
              'T', 'FVTPL', 'asset', 'CNY', 'CNY', 80.00, 80.00, 1.00, false,
              'sv-z-nov', 'rv-z-nov', 'ib-z-nov', 'trace-z-nov'
            )
            """
        )
    finally:
        conn.close()


def _seed_usd_pnl_bridge_balance_rows(duckdb_path: Path) -> None:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute(
            "update fact_formal_pnl_fi set currency_basis = 'USD' where report_date = '2025-12-31' and instrument_code = '240001.IB'"
        )
        conn.execute("delete from fact_formal_zqtz_balance_daily")
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "100.00000000",
                    "99.00000000",
                    "2.00000000",
                    False,
                    "sv-z-current-usd",
                    "rv-z-current-usd",
                    "ib-z-current-usd",
                    "trace-z-current-usd",
                ),
                (
                    "2025-10-31",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "90.00000000",
                    "89.00000000",
                    "1.00000000",
                    False,
                    "sv-z-prior-usd",
                    "rv-z-prior-usd",
                    "ib-z-prior-usd",
                    "trace-z-prior-usd",
                ),
            ],
        )
    finally:
        conn.close()


def _seed_pnl_bridge_snapshot_face_values(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists zqtz_bond_daily_snapshot (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              currency_code varchar,
              face_value_native decimal(24, 8)
            )
            """
        )
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.executemany(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, portfolio_name, cost_center, currency_code, face_value_native
            ) values (?, ?, ?, ?, ?, ?)
            """,
            [
                ("2025-12-31", "240001.IB", "FI Desk", "CC100", "USD", "1000.00000000"),
                ("2025-10-31", "240001.IB", "FI Desk", "CC100", "USD", "1000.00000000"),
            ],
        )
    finally:
        conn.close()


def _seed_pnl_bridge_fx_rates(
    duckdb_path: Path,
    *,
    rows: list[tuple[str, str, str, str, bool, bool, str, str]] | None = None,
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              observed_trade_date varchar
            )
            """
        )
        conn.execute("delete from fx_daily_mid")
        conn.executemany(
            """
            insert into fx_daily_mid (
              trade_date, base_currency, quote_currency, mid_rate,
              source_name, is_business_day, is_carry_forward, source_version,
              observed_trade_date
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (trade_date, base_currency, quote_currency, mid_rate, "CFETS", is_business_day, is_carry_forward, source_version, observed_trade_date)
                for trade_date, base_currency, quote_currency, mid_rate, is_business_day, is_carry_forward, source_version, observed_trade_date in (
                    rows
                    or [
                        ("2025-12-31", "USD", "CNY", "7.08270000", True, False, "sv_fx_daily_mid_test", "2025-12-31"),
                        ("2025-10-31", "USD", "CNY", "7.04135000", True, False, "sv_fx_daily_mid_test", "2025-10-31"),
                    ]
                )
            ],
        )
    finally:
        conn.close()


def _configure_refresh_sources(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_root = tmp_path / "data_input"
    (data_root / "pnl").mkdir(parents=True)
    (data_root / "pnl_516").mkdir(parents=True)

    _write_fi_refresh_marker(data_root, month_key="202602")
    _write_nonstd_refresh_workbook(data_root / "pnl_516" / "非标516-20260101-0228.xlsx")
    source_service = load_module(
        "backend.app.services.pnl_source_service",
        "backend/app/services/pnl_source_service.py",
    )
    monkeypatch.setattr(source_service, "_parse_fi_rows", _fake_parse_fi_refresh_rows)

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", '["*"]')
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{(tmp_path / 'auth-scope.db').as_posix()}")
    get_settings.cache_clear()
    scope_repo = UserScopeRepository(get_settings().governance_sql_dsn or get_settings().postgres_dsn)
    _grant_pnl_read_scope(scope_repo)
    scope_repo.grant_scope(
        user_id="*",
        role=None,
        resource="formal_pnl",
        action="refresh",
    )
    return duckdb_path, governance_dir


def _copy_fi_refresh_source(tmp_path, *, month_key: str):
    _write_fi_refresh_marker(tmp_path / "data_input", month_key=month_key)


def _write_fi_refresh_marker(data_root: Path, *, month_key: str) -> Path:
    path = data_root / "pnl" / f"FI损益{month_key}.xls"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test-only FI refresh marker; parser is monkeypatched\n", encoding="utf-8")
    return path


def _fake_parse_fi_refresh_rows(snapshot) -> list[dict[str, object]]:
    return [
        {
            "report_date": snapshot.report_date,
            "instrument_code": "240001.IB",
            "portfolio_name": "FI Desk",
            "cost_center": "CC100",
            "invest_type_raw": "交易性金融资产",
            "interest_income_514": Decimal("12.50"),
            "fair_value_change_516": Decimal("-3.25"),
            "capital_gain_517": Decimal("1.75"),
            "manual_adjustment": Decimal("0"),
            "currency_basis": "CNY",
            "source_version": snapshot.source_version,
            "rule_version": "rv_test_fi_refresh_parser",
            "ingest_batch_id": snapshot.ingest_batch_id,
            "trace_id": f"{snapshot.path.name}:fi:1",
            "approval_status": "approved",
            "event_semantics": "realized_incremental",
            "realized_flag": True,
        }
    ]


def _configure_import_status_env(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    return governance_dir


def _append_source_manifest_row(
    governance_dir,
    *,
    source_family: str,
    report_date: str,
    source_file: str,
    archived_path: Path,
    source_version: str,
    ingest_batch_id: str,
):
    GovernanceRepository(base_dir=governance_dir).append(
        SOURCE_MANIFEST_STREAM,
        {
            "source_family": source_family,
            "report_date": report_date,
            "source_file": source_file,
            "archived_path": str(archived_path),
            "source_version": source_version,
            "ingest_batch_id": ingest_batch_id,
            "status": "completed",
            "created_at": "2026-04-11T00:00:00+00:00",
        },
    )


def _create_archived_copy(tmp_path, *, source_file: Path, archive_name: str) -> Path:
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / archive_name
    target.write_text(
        f"test-only archived marker for {source_file.name}\n",
        encoding="utf-8",
    )
    return target


def _append_pnl_build_run(
    governance_dir,
    *,
    run_id: str,
    status: str,
    source_version: str,
    **extra: object,
):
    record = CacheBuildRunRecord(
        run_id=run_id,
        job_name="pnl_materialize",
        status=status,
        cache_key="pnl:phase2:materialize:formal",
        lock="lock:duckdb:formal:pnl:phase2:materialize",
        source_version=source_version,
        vendor_version="vv_none",
    ).model_dump()
    for key, value in extra.items():
        if value is not None:
            record[key] = value
    GovernanceRepository(base_dir=governance_dir).append(CACHE_BUILD_RUN_STREAM, record)


def _append_balance_build_run(
    governance_dir,
    *,
    run_id: str,
    report_date: str,
    source_version: str,
    vendor_version: str,
    rule_version: str,
):
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=run_id,
                job_name="balance_analysis_materialize",
                status="completed",
                cache_key="balance_analysis:materialize:formal",
                cache_version="cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version=source_version,
                vendor_version=vendor_version,
                rule_version=rule_version,
            ).model_dump(),
            "report_date": report_date,
        },
    )


def _write_nonstd_refresh_workbook(
    path: Path,
    *,
    include_prior_month_row: bool = False,
    row_dates: tuple[str, str] = ("2026-02-27", "2026-02-28"),
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["会计分录详情表"])
    worksheet.append(
        [
            "账务流水号",
            "序号",
            "所属账套",
            "账务日期",
            "交易流水号",
            "内部账户号",
            "产品类型",
            "客户名称",
            "会计分类",
            "成本中心",
            "投资组合",
            "资产代码",
            "交易机构",
            "会计事件",
            "币种",
            "借贷标识",
            "科目号",
            "科目名称",
            "金额",
            "备注",
        ]
    )
    if include_prior_month_row:
        worksheet.append(
            [
                "1411967",
                "0",
                "默认账套",
                "2026-01-31",
                "TRD000",
                "",
                "证券投资基金",
                "测试产品Z",
                "FVTPL",
                "5010",
                "FIOA",
                "BOND-001",
                "80002",
                "月初遗留估值",
                "人民币",
                "贷",
                "51601010004",
                "公允价值变动损益",
                "30.00",
                "carryover_val|",
            ]
        )
    worksheet.append(
        [
            "1411968",
            "1",
            "默认账套",
            row_dates[0],
            "TRD001",
            "",
            "证券投资基金",
            "测试产品A",
            "FVTPL",
            "5010",
            "FIOA",
            "BOND-001",
            "80002",
            "冲销前一日估值",
            "人民币",
            "贷",
            "51601010004",
            "公允价值变动损益",
            "40.00",
            "revmtm_val|",
        ]
    )
    worksheet.append(
        [
            "1411969",
            "2",
            "默认账套",
            row_dates[1],
            "TRD002",
            "",
            "证券投资基金",
            "测试产品B",
            "FVTPL",
            "5010",
            "FIOA",
            "BOND-001",
            "80002",
            "估值入账",
            "人民币",
            "贷",
            "51601010004",
            "公允价值变动损益",
            "60.00",
            "mtm_val|",
        ]
    )
    workbook.save(path)
