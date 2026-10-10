"""Narrow contract test for bond-dashboard bundle aggregation endpoint."""
from __future__ import annotations


import copy
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
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


def _home_summary_refresh_fixture(monkeypatch):
    service = load_module(
        "tests._bond_dashboard_home_summary_refresh",
        "backend/app/services/bond_dashboard_service.py",
    )
    state = {"database": 1, "physical": 1, "scope": 1, "terminal": 1, "builds": 0, "hook": None}
    monkeypatch.setattr(service, "_duckdb_cache_version_token", lambda: ("test-db", state["database"]))
    monkeypatch.setattr(service, "_bond_analytics_rows_cache_version_token", lambda: ("selected-db", state["physical"]), raising=False)
    monkeypatch.setattr(service, "resolve_completed_formal_build_lineage", lambda **_kwargs: {
        "run_id": str(state["terminal"]), "source_version": "sv_home",
        "rule_version": "rv_home", "cache_version": "cv_home",
    }, raising=False)
    from backend.app.services import runtime_cache

    def identity(key):
        return ("test-scope", state["scope"], key)

    monkeypatch.setattr(runtime_cache, "system_read_cache_identity", identity)
    monkeypatch.setattr(service, "system_read_cache_identity", identity, raising=False)

    def build(rd):
        state["builds"] += 1
        result = ({"report_date": rd, "build": state["builds"]},
                  {"source_version": "sv_home", "rule_version": "rv_home", "cache_version": "cv_home"}, 1)
        if state["hook"]:
            state["hook"]()
        return result

    monkeypatch.setattr(service, "_build_bond_dashboard_home_summary_components", build)
    monkeypatch.setattr(service, "_analytical_envelope_from_lineage", lambda **kwargs: {
        "result": kwargs["result_payload"], "result_meta": kwargs["lineage"],
    })
    return service, state


def test_home_summary_force_refresh_keeps_valid_hit_until_new_result_is_ready(monkeypatch):
    service, state = _home_summary_refresh_fixture(monkeypatch)
    rd = date.fromisoformat(REPORT_DATE)
    first = service.get_bond_dashboard_home_summary(rd)
    assert service.get_bond_dashboard_home_summary(rd)["result"] == first["result"]
    assert state["builds"] == 1
    state["hook"] = lambda: service.get_bond_dashboard_home_summary(rd)
    refreshed = service.get_bond_dashboard_home_summary(rd, force_refresh=True)
    assert refreshed["result"]["build"] == 2
    assert service.get_bond_dashboard_home_summary(rd)["result"] == refreshed["result"]
    assert state["builds"] == 2
    state["hook"] = lambda: (_ for _ in ()).throw(RuntimeError("refresh failed"))
    with pytest.raises(RuntimeError, match="refresh failed"):
        service.get_bond_dashboard_home_summary(rd, force_refresh=True)
    assert service.get_bond_dashboard_home_summary(rd)["result"] == refreshed["result"]


@pytest.mark.parametrize("change", ["generation", "database", "physical", "scope", "terminal"])
def test_home_summary_force_refresh_does_not_store_changed_read_inputs(monkeypatch, change):
    service, state = _home_summary_refresh_fixture(monkeypatch)
    rd = date.fromisoformat(REPORT_DATE)
    first = service.get_bond_dashboard_home_summary(rd)
    cache = service._home_summary_cache
    original_key = next(iter(cache._store))

    def invalidate():
        if change == "generation":
            service.clear_bond_dashboard_runtime_cache()
        else:
            state[change] += 1

    state["hook"] = invalidate
    refreshed = service.get_bond_dashboard_home_summary(rd, force_refresh=True)
    assert refreshed["result"]["build"] == 2
    state["hook"] = None
    if change == "generation":
        assert cache._store == {}
        assert service.get_bond_dashboard_home_summary(rd)["result"]["build"] == 3
    else:
        assert cache._store[original_key][1][0] == first["result"]
        assert all(entry[1][0] != refreshed["result"] for entry in cache._store.values())
    if change in {"database", "scope"}:
        assert service.get_bond_dashboard_home_summary(rd)["result"]["build"] == 3


def _live_bond_dashboard_service():
    """Return the bond_dashboard_service module fresh routes and patches must share.

    ``tests.helpers.load_module`` replaces ``sys.modules`` entries without
    refreshing parent package attributes, so ``import backend.app.services.
    bond_dashboard_service as service_mod`` can return a stale module object while
    a freshly built app resolves the current one; patches on the stale module (or
    on a class the stale module no longer binds) would then silently miss.
    """
    import backend.app.services.bond_dashboard_service  # noqa: F401

    return sys.modules["backend.app.services.bond_dashboard_service"]


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


def test_bond_dashboard_fact_rows_cache_collapses_concurrent_fetches(tmp_path, monkeypatch) -> None:
    import backend.app.services.bond_dashboard_service as service_mod

    duckdb_path = tmp_path / "dash-bundle-fact-cache.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    service_mod.clear_bond_dashboard_runtime_cache()
    calls = 0

    class FakeBondAnalyticsRepository:
        def fetch_bond_analytics_rows(self, *, report_date: str):
            nonlocal calls
            calls += 1
            time.sleep(0.05)
            return [{"report_date": report_date, "source_version": "sv_test"}]

    fake_repo = FakeBondAnalyticsRepository()
    monkeypatch.setattr(service_mod, "_repo", lambda: fake_repo)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _index: service_mod._fact_rows(REPORT_DATE), range(4)))

    assert calls == 1
    assert all(result == results[0] for result in results)
    get_settings.cache_clear()


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
        "dates",
        "headline-kpis",
        "home-summary",
        "risk-indicators",
        "yield-distribution",
        "portfolio-comparison",
        "spread-analysis",
        "maturity-structure",
        "industry-distribution",
        "business-type-metrics",
        "asset-structure",
        "asset-structure-rating",
        "asset-structure-portfolio-name",
        "asset-structure-tenor-bucket",
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
    assert bundle_result["failed_sections"] == []
    assert {
        section: envelope["result_meta"]["quality_flag"]
        for section, envelope in bundle_result["sections"].items()
    } == {section: "ok" for section in requested_sections}

    single_endpoints = {
        "dates": ("/api/bond-dashboard/dates", {}),
        "headline-kpis": ("/api/bond-dashboard/headline-kpis", {"report_date": REPORT_DATE}),
        "home-summary": ("/api/bond-dashboard/home-summary", {"report_date": REPORT_DATE}),
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
        "asset-structure-portfolio-name": (
            "/api/bond-dashboard/asset-structure",
            {"report_date": REPORT_DATE, "group_by": "portfolio_name"},
        ),
        "asset-structure-tenor-bucket": (
            "/api/bond-dashboard/asset-structure",
            {"report_date": REPORT_DATE, "group_by": "tenor_bucket"},
        ),
    }

    for section, (path, params) in single_endpoints.items():
        single_response = client.get(path, params=params)
        assert single_response.status_code == 200, single_response.text
        assert _strip_volatile_envelope_fields(bundle_result["sections"][section]) == _strip_volatile_envelope_fields(
            single_response.json()
        ), section

    get_settings.cache_clear()


def test_bond_dashboard_bundle_page_sections_warn_on_empty_facts(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "dash-bundle-empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    requested_sections = [
        "dates",
        "headline-kpis",
        "home-summary",
        "risk-indicators",
        "asset-structure",
        "asset-structure-rating",
        "asset-structure-portfolio-name",
        "asset-structure-tenor-bucket",
        "yield-distribution",
        "portfolio-comparison",
        "spread-analysis",
        "maturity-structure",
        "industry-distribution",
        "business-type-metrics",
    ]
    response = client.get(
        "/api/bond-dashboard/bundle",
        params={
            "report_date": REPORT_DATE,
            "sections": ",".join(requested_sections),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    result = payload["result"]
    assert result["failed_sections"] == []
    assert set(result["sections"]) == set(requested_sections)
    assert {
        section: envelope["result_meta"]["quality_flag"]
        for section, envelope in result["sections"].items()
    } == {section: "warning" for section in requested_sections}
    assert {
        section: status["status"]
        for section, status in result["section_statuses"].items()
    } == {section: "ok" for section in requested_sections}
    risk_result = result["sections"]["risk-indicators"]["result"]
    assert risk_result["weighted_convexity"]["raw"] is None
    assert risk_result["weighted_convexity_coverage_ratio"]["raw"] == 0
    assert result["sections"]["business-type-metrics"]["result"]["items"] == []
    get_settings.cache_clear()


def test_bond_dashboard_bundle_reuses_headline_snapshot_for_yield_distribution(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    service_mod = _live_bond_dashboard_service()

    duckdb_path = tmp_path / "dash-bundle-shared-headline.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    service_mod.clear_bond_dashboard_runtime_cache()

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

    # Count fetches on the repository class the service module actually binds;
    # the class imported at the top of this test can be a forked instance after
    # tests.helpers.load_module replaced bond_analytics_repo in sys.modules.
    original_fetch = service_mod.BondAnalyticsRepository.fetch_dashboard_headline_kpis
    calls = 0

    def counting_fetch(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original_fetch(self, *args, **kwargs)

    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_dashboard_headline_kpis",
        counting_fetch,
    )

    payload = service_mod.get_bond_dashboard_bundle(
        sections=["headline-kpis", "yield-distribution"],
        report_date=date.fromisoformat(REPORT_DATE),
    )

    assert payload["result"]["failed_sections"] == []
    assert calls == 1
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
        "dv01-risk",
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
    assert all(
        isinstance(status["duration_ms"], (int, float)) and status["duration_ms"] >= 0
        for status in result["section_statuses"].values()
    )
    assert result["sections"]["top-holdings"]["result"]["top_n"] == 5
    assert result["sections"]["portfolio-headlines"]["result_meta"]["result_kind"] == "bond_analytics.portfolio_headlines"
    assert result["sections"]["dv01-risk"]["result"]["accounting_class"] == "all"
    assert result["sections"]["dv01-risk-ac"]["result"]["accounting_class"] == "AC"
    assert result["sections"]["dv01-risk-all"]["result"]["accounting_class"] == "all"
    assert (
        result["sections"]["yield-curve-term-structure"]["result_meta"]["result_kind"]
        == "bond_analytics.yield_curve_term_structure"
    )
    get_settings.cache_clear()


def test_bond_dashboard_bundle_isolates_section_failure(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    service_mod = _live_bond_dashboard_service()

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
    assert result["section_statuses"]["headline-kpis"]["duration_ms"] >= 0
    assert result["section_statuses"]["top-holdings"]["duration_ms"] >= 0
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
    assert bundle_payload["result_meta"]["quality_flag"] == "warning"
    assert bundle_payload["result"]["report_date"] is None
    assert (
        bundle_payload["result"]["sections"]["dates"]["result_meta"]["quality_flag"]
        == "warning"
    )
    assert _strip_volatile_envelope_fields(bundle_payload["result"]["sections"]["dates"]) == _strip_volatile_envelope_fields(
        dates_response.json()
    )
    get_settings.cache_clear()


def test_dashboard_cache_capacity_and_expiry_are_bounded():
    from backend.app.services import bond_dashboard_service as service

    now = [0.0]
    cache = service._TTLCache(ttl_seconds=30, clock=lambda: now[0], max_entries=32, sweep_budget=4)
    for version in range(10000):
        cache.set(("database-version", version), bytes(1024))
        assert len(cache._store) <= 32
        assert len(cache._expiry_scan) <= 32
    now[0] = 86400.0
    for _ in range(8):
        cache.get(("unused",))
    assert len(cache._store) == len(cache._expiry_scan) == 0


def test_dashboard_fetch_lock_retained_for_waiters_and_reclaimed_after_exit():
    import threading
    import time
    from backend.app.services import bond_dashboard_service as service

    key = ("synthetic-lock-test",)
    entered, release, waiter_entered = (threading.Event() for _ in range(3))

    def holder():
        with service._fact_rows_fetch_lock(key):
            entered.set()
            assert release.wait(2)

    def waiter():
        with service._fact_rows_fetch_lock(key):
            waiter_entered.set()

    first, second = threading.Thread(target=holder), threading.Thread(target=waiter)
    first.start()
    assert entered.wait(1)
    second.start()
    try:
        for _ in range(200):
            with service._fact_rows_fetch_locks_guard:
                entry = service._fact_rows_fetch_locks[key]
                if entry[1] == 2:
                    break
            time.sleep(0.001)
        assert entry[1] == 2
        lock = entry[0]
        service.clear_bond_dashboard_runtime_cache()
        assert service._fact_rows_fetch_locks[key][0] is lock
        assert not waiter_entered.is_set()
    finally:
        release.set()
        first.join(2)
        second.join(2)
    assert waiter_entered.is_set()
    assert key not in service._fact_rows_fetch_locks
    for version in range(10000):
        with service._fact_rows_fetch_lock(("synthetic-version", version)):
            pass
    assert not service._fact_rows_fetch_locks


def test_dashboard_clear_drops_report_dates_build_started_before_clear(monkeypatch):
    from types import SimpleNamespace
    from backend.app.services import bond_dashboard_service as service

    service.clear_bond_dashboard_runtime_cache()
    monkeypatch.setattr(service, "_duckdb_cache_version_token", lambda: ("synthetic", 1))

    def build():
        service.clear_bond_dashboard_runtime_cache()
        return ["old-date"]

    monkeypatch.setattr(service, "_repo", lambda: SimpleNamespace(list_report_dates=build))
    assert service._report_dates() == ["old-date"]
    monkeypatch.setattr(service, "_repo", lambda: SimpleNamespace(list_report_dates=lambda: ["new-date"]))
    assert service._report_dates() == ["new-date"]
