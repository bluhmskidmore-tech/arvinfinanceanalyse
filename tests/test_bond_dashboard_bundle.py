"""Narrow contract test for bond-dashboard bundle aggregation endpoint."""
from __future__ import annotations

import copy
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_dashboard_api_contract import (
    BOND_DASHBOARD_READ_HEADERS,
    REPORT_DATE,
    _bond_dashboard_client_with_read_scope,
    _grant_bond_dashboard_read_scope,
    _make_bond_analytics_row,
    _replace_bond_dashboard_rows,
)


def _strip_volatile_envelope_fields(envelope: dict) -> dict:
    out = copy.deepcopy(envelope)
    meta = out.get("result_meta")
    if isinstance(meta, dict):
        meta.pop("trace_id", None)
        meta.pop("generated_at", None)
    return out


def _bond_dashboard_client_with_bundle_scopes(tmp_path, monkeypatch) -> TestClient:
    _grant_bond_dashboard_read_scope(tmp_path, monkeypatch)
    sqlite_path = tmp_path / "bond-dashboard-read-scope.db"
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="bond_analytics",
        action="read",
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update(BOND_DASHBOARD_READ_HEADERS)
    return client


def test_bond_dashboard_bundle_matches_individual_section_envelopes(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-bundle.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    rows = [
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="RATE",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("100"),
            ytm=Decimal("0.02"),
            modified_duration=Decimal("2"),
            bond_type_label="Rate",
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="CREDIT",
            portfolio_name="P1",
            asset_class_std="credit",
            market_value=Decimal("300"),
            ytm=Decimal("0.04"),
            modified_duration=Decimal("6"),
            bond_type_label="Credit",
        ),
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    requested_sections = [
        "headline-kpis",
        "risk-indicators",
        "yield-distribution",
        "portfolio-comparison",
        "spread-analysis",
        "maturity-structure",
        "industry-distribution",
        "business-type-metrics",
        "asset-structure",
        "asset-structure-rating",
    ]
    bundle_response = client.get(
        "/api/bond-dashboard/bundle",
        params={
            "report_date": REPORT_DATE,
            "sections": ",".join(requested_sections),
            "industry_top_n": 10,
        },
    )
    assert bundle_response.status_code == 200, bundle_response.text
    bundle_payload = bundle_response.json()

    assert bundle_payload.get("data_source") == "bond_analytics_facts"
    bundle_meta = bundle_payload["result_meta"]
    assert bundle_meta["result_kind"] == "bond_dashboard.bundle"
    assert bundle_meta["basis"] == "analytical"
    assert bundle_meta["requested_report_date"] == REPORT_DATE
    assert bundle_meta["filters_applied"]["sections"] == requested_sections

    bundle_result = bundle_payload["result"]
    assert bundle_result["report_date"] == REPORT_DATE
    assert bundle_result["requested_sections"] == requested_sections
    assert set(bundle_result["sections"]) == set(requested_sections)

    single_endpoints = {
        "headline-kpis": ("/api/bond-dashboard/headline-kpis", {"report_date": REPORT_DATE}),
        "risk-indicators": ("/api/bond-dashboard/risk-indicators", {"report_date": REPORT_DATE}),
        "yield-distribution": ("/api/bond-dashboard/yield-distribution", {"report_date": REPORT_DATE}),
        "portfolio-comparison": ("/api/bond-dashboard/portfolio-comparison", {"report_date": REPORT_DATE}),
        "spread-analysis": ("/api/bond-dashboard/spread-analysis", {"report_date": REPORT_DATE}),
        "maturity-structure": ("/api/bond-dashboard/maturity-structure", {"report_date": REPORT_DATE}),
        "industry-distribution": (
            "/api/bond-dashboard/industry-distribution",
            {"report_date": REPORT_DATE, "top_n": 10},
        ),
        "business-type-metrics": (
            "/api/bond-dashboard/business-type-metrics",
            {"report_date": REPORT_DATE},
        ),
        "asset-structure": (
            "/api/bond-dashboard/asset-structure",
            {"report_date": REPORT_DATE, "group_by": "bond_type"},
        ),
        "asset-structure-rating": (
            "/api/bond-dashboard/asset-structure",
            {"report_date": REPORT_DATE, "group_by": "rating"},
        ),
    }

    for section, (path, params) in single_endpoints.items():
        single_response = client.get(path, params=params)
        assert single_response.status_code == 200, single_response.text
        assert _strip_volatile_envelope_fields(bundle_result["sections"][section]) == _strip_volatile_envelope_fields(
            single_response.json()
        ), section

    get_settings.cache_clear()


def test_bond_dashboard_bundle_includes_cockpit_analytics_sections(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-bundle-cockpit.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    rows = [
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="AC_RATE",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("100"),
            ytm=Decimal("0.02"),
            modified_duration=Decimal("2"),
            bond_type_label="Rate",
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="AC_CREDIT",
            portfolio_name="P1",
            asset_class_std="credit",
            market_value=Decimal("300"),
            ytm=Decimal("0.04"),
            modified_duration=Decimal("6"),
            bond_type_label="Credit",
        ),
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    client = _bond_dashboard_client_with_bundle_scopes(tmp_path, monkeypatch)
    requested_sections = [
        "top-holdings",
        "portfolio-headlines",
        "dv01-risk-ac",
        "dv01-risk-oci",
        "dv01-risk-tpl",
        "dv01-risk-all",
        "yield-curve-term-structure",
    ]
    response = client.get(
        "/api/bond-dashboard/bundle",
        params={
            "report_date": REPORT_DATE,
            "sections": ",".join(requested_sections),
            "analytics_top_n": 5,
            "dv01_top_n": 1,
            "dv01_shock_bps": "1",
            "curve_types": "treasury,cdb",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]

    assert result["requested_sections"] == requested_sections
    assert result["failed_sections"] == []
    assert set(result["sections"]) == set(requested_sections)
    assert {k: v["status"] for k, v in result["section_statuses"].items()} == {
        section: "ok" for section in requested_sections
    }
    assert result["sections"]["top-holdings"]["result"]["top_n"] == 5
    assert result["sections"]["portfolio-headlines"]["result_meta"]["result_kind"] == "bond_analytics.portfolio_headlines"
    assert result["sections"]["dv01-risk-ac"]["result"]["accounting_class"] == "AC"
    assert result["sections"]["dv01-risk-all"]["result"]["accounting_class"] == "all"
    assert (
        result["sections"]["yield-curve-term-structure"]["result_meta"]["result_kind"]
        == "bond_analytics.yield_curve_term_structure"
    )
    get_settings.cache_clear()


def test_bond_dashboard_bundle_isolates_section_failure(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    import backend.app.services.bond_dashboard_service as service_mod

    duckdb_path = tmp_path / "dash-bundle-isolation.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    rows = [
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="AC_RATE",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("100"),
            ytm=Decimal("0.02"),
            modified_duration=Decimal("2"),
            bond_type_label="Rate",
        )
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    def broken_top_holdings(*args, **kwargs):
        raise RuntimeError("top holdings unavailable")

    monkeypatch.setattr(service_mod, "get_top_holdings", broken_top_holdings)

    client = _bond_dashboard_client_with_bundle_scopes(tmp_path, monkeypatch)
    response = client.get(
        "/api/bond-dashboard/bundle",
        params={
            "report_date": REPORT_DATE,
            "sections": "headline-kpis,top-holdings",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    result = payload["result"]

    assert payload["result_meta"]["quality_flag"] == "warning"
    assert "headline-kpis" in result["sections"]
    assert "top-holdings" not in result["sections"]
    assert result["failed_sections"] == ["top-holdings"]
    assert result["section_statuses"]["headline-kpis"]["status"] == "ok"
    assert result["section_statuses"]["top-holdings"]["status"] == "error"
    assert result["section_statuses"]["top-holdings"]["message"] == "top holdings unavailable"
    get_settings.cache_clear()


def test_bond_dashboard_bundle_rejects_unknown_sections(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "dash-bundle-invalid.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    response = client.get(
        "/api/bond-dashboard/bundle",
        params={"report_date": REPORT_DATE, "sections": "headline-kpis,not-real"},
    )
    assert response.status_code == 422
    assert "unsupported bond-dashboard bundle sections" in response.json()["detail"]
    get_settings.cache_clear()


def test_bond_dashboard_bundle_dates_only_without_report_date(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "dash-bundle-dates.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    bundle_response = client.get(
        "/api/bond-dashboard/bundle",
        params={"sections": "dates"},
    )
    assert bundle_response.status_code == 200, bundle_response.text
    dates_response = client.get("/api/bond-dashboard/dates")
    assert dates_response.status_code == 200, dates_response.text

    bundle_payload = bundle_response.json()
    assert bundle_payload["result_meta"]["result_kind"] == "bond_dashboard.bundle"
    assert bundle_payload["result_meta"]["basis"] == "formal"
    assert bundle_payload["result"]["report_date"] is None
    assert _strip_volatile_envelope_fields(bundle_payload["result"]["sections"]["dates"]) == _strip_volatile_envelope_fields(
        dates_response.json()
    )
    get_settings.cache_clear()
