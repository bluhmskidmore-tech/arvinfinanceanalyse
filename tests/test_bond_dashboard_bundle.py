"""Narrow contract test for bond-dashboard bundle aggregation endpoint."""
from __future__ import annotations

import copy
from decimal import Decimal

from backend.app.governance.settings import get_settings
from tests.test_bond_dashboard_api_contract import (
    REPORT_DATE,
    _bond_dashboard_client_with_read_scope,
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
