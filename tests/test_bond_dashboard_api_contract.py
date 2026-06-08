"""Contract tests for bond-dashboard HTTP API (envelope + empty DB behavior)."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

REPORT_DATE = "2026-03-31"
BOND_DASHBOARD_READ_HEADERS = {"X-User-Id": "bond-dashboard-read-user", "X-User-Role": "viewer"}


def _grant_bond_dashboard_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    sqlite_path = tmp_path / "bond-dashboard-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id=user_id,
        role=None,
        resource="bond_dashboard",
        action="read",
    )


def _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch) -> TestClient:
    _grant_bond_dashboard_read_scope(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update(BOND_DASHBOARD_READ_HEADERS)
    return client


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


def _replace_bond_dashboard_rows(repo: Any, *, report_date: str, rows: list[Any]) -> None:
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    with repository_task_write_scope("backend.app.tasks.bond_dashboard_api_contract_test"):
        repo.replace_bond_analytics_rows(report_date=report_date, rows=rows)

_BOND_DASHBOARD_CASES: list[tuple[str, dict[str, str | int]]] = [
    ("/api/bond-dashboard/dates", {}),
    ("/api/bond-dashboard/home-summary", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/headline-kpis", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/asset-structure", {"report_date": REPORT_DATE, "group_by": "bond_type"}),
    ("/api/bond-dashboard/yield-distribution", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/portfolio-comparison", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/spread-analysis", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/maturity-structure", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/industry-distribution", {"report_date": REPORT_DATE, "top_n": 10}),
    ("/api/bond-dashboard/risk-indicators", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/business-type-metrics", {"report_date": REPORT_DATE}),
]


def _make_bond_analytics_row(
    *,
    report_date: str,
    instrument_code: str,
    portfolio_name: str,
    asset_class_std: str,
    market_value: Decimal,
    ytm: Decimal,
    modified_duration: Decimal,
    bond_type_label: str | None = None,
    maturity_date: date | None = date(2030, 1, 1),
) -> Any:
    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow

    macaulay_duration = modified_duration * Decimal("1.02")
    face_value = Decimal("1000")
    return BondAnalyticsRow(
        report_date=date.fromisoformat(report_date),
        instrument_code=instrument_code,
        instrument_name=instrument_code,
        portfolio_name=portfolio_name,
        cost_center="C1",
        asset_class_raw=asset_class_std,
        asset_class_std=asset_class_std,
        bond_type=bond_type_label if bond_type_label is not None else asset_class_std,
        issuer_name="I",
        industry_name="bank",
        rating="AAA",
        accounting_class="AC",
        accounting_rule_id="r1",
        currency_code="CNY",
        face_value=face_value,
        market_value_native=market_value,
        market_value=market_value,
        amortized_cost=market_value,
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.025"),
        interest_mode="fixed",
        interest_payment_frequency="annual",
        interest_rate_style="fixed",
        ytm=ytm,
        maturity_date=maturity_date,
        next_call_date=None,
        years_to_maturity=Decimal("2.5"),
        tenor_bucket="1-3Y",
        macaulay_duration=macaulay_duration,
        modified_duration=modified_duration,
        convexity=Decimal("0.01"),
        dv01=face_value * modified_duration / Decimal("10000"),
        is_credit=asset_class_std == "credit",
        spread_dv01=face_value * modified_duration / Decimal("10000") if asset_class_std == "credit" else Decimal("0"),
        source_version="sv",
        rule_version="rv",
        ingest_batch_id="ib",
        trace_id="tr",
    )


def _metric_raw(value: Any) -> Decimal:
    if isinstance(value, dict):
        return Decimal(str(value["raw"]))
    return Decimal(str(value))


def _assert_numeric(value: Any, *, unit: str, raw: Decimal | str | int | None = None) -> None:
    assert isinstance(value, dict)
    assert {"raw", "unit", "display", "precision", "sign_aware"} <= set(value)
    assert value["unit"] == unit
    assert isinstance(value["display"], str)
    assert isinstance(value["precision"], int)
    assert isinstance(value["sign_aware"], bool)
    if raw is not None:
        assert Decimal(str(value["raw"])) == Decimal(str(raw))


def _assert_result_envelope(
    payload: dict[str, Any],
    *,
    basis: str = "formal",
    formal_use_allowed: bool = True,
) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    assert payload.get("data_source") == "bond_analytics_facts"
    meta = payload["result_meta"]
    assert meta.get("basis") == basis
    assert meta.get("formal_use_allowed") is formal_use_allowed
    for key in ("trace_id", "source_version", "rule_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"


def _assert_formal_envelope(payload: dict[str, Any]) -> None:
    _assert_result_envelope(payload)


def _assert_bond_dashboard_headline_candidate_envelope(payload: dict[str, Any]) -> None:
    _assert_result_envelope(payload, basis="analytical", formal_use_allowed=False)
    meta = payload["result_meta"]
    assert meta["result_kind"] == "bond_dashboard.headline_kpis"
    assert meta["source_surface"] == "bond_analytics"
    assert meta["quality_flag"] == "warning"
    assert meta["scenario_flag"] is False
    assert meta["requested_report_date"] == REPORT_DATE
    assert meta["resolved_report_date"] == REPORT_DATE
    assert meta["as_of_date"] == REPORT_DATE
    assert meta["date_basis"] == "bond_dashboard_report_date"
    assert meta["filters_applied"] == {"report_date": REPORT_DATE}
    assert meta["tables_used"] == ["fact_formal_bond_analytics_daily"]


def _assert_bond_dashboard_home_summary_candidate_envelope(payload: dict[str, Any]) -> None:
    _assert_result_envelope(payload, basis="analytical", formal_use_allowed=False)
    meta = payload["result_meta"]
    assert meta["result_kind"] == "bond_dashboard.home_summary"
    assert meta["source_surface"] == "bond_analytics"
    assert meta["quality_flag"] == "warning"
    assert meta["scenario_flag"] is False
    assert meta["requested_report_date"] == REPORT_DATE
    assert meta["resolved_report_date"] == REPORT_DATE
    assert meta["as_of_date"] == REPORT_DATE
    assert meta["date_basis"] == "bond_dashboard_report_date"
    assert meta["filters_applied"] == {"report_date": REPORT_DATE}
    assert meta["tables_used"] == ["fact_formal_bond_analytics_daily"]


def _check_all_on_empty_db(tmp_path, monkeypatch) -> None:
    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    for path, params in _BOND_DASHBOARD_CASES:
        response = client.get(path, params=params)
        assert response.status_code == 200, (
            f"{path} {params} -> {response.status_code}: {response.text}"
        )
        payload = response.json()
        if path.endswith("/headline-kpis"):
            _assert_bond_dashboard_headline_candidate_envelope(payload)
        elif path.endswith("/home-summary"):
            _assert_bond_dashboard_home_summary_candidate_envelope(payload)
        else:
            _assert_formal_envelope(payload)
        result = payload["result"]
        if path.endswith("/dates"):
            assert result.get("report_dates") == []
        elif path.endswith("/home-summary"):
            assert result.get("report_date") == REPORT_DATE
            assert result["headline"].get("report_date") == REPORT_DATE
            assert result["risk"].get("report_date") == REPORT_DATE
            assert result["asset_type"].get("items") == []
            assert result["asset_rating"].get("items") == []
            assert result["maturity"].get("items") == []
            assert result["industry"].get("items") == []
            assert result["yield_distribution"].get("items") == []
            assert result["portfolio_comparison"].get("items") == []
            assert result["spread"].get("items") == []
            assert result["business_type"].get("items") == []
            cur = result["headline"]["kpis"]
            _assert_numeric(cur["total_market_value"], unit="yuan", raw=0)
            _assert_numeric(result["risk"]["credit_ratio"], unit="ratio", raw=0)
        elif path.endswith("/headline-kpis"):
            assert result.get("report_date") == REPORT_DATE
            assert result.get("kpis") is not None
            cur = result["kpis"]
            assert cur["bond_count"] == 0
            _assert_numeric(cur["total_market_value"], unit="yuan", raw=0)
            _assert_numeric(cur["weighted_ytm"], unit="pct", raw=0)
            _assert_numeric(cur["weighted_duration"], unit="ratio", raw=0)
            _assert_numeric(cur["total_dv01"], unit="dv01", raw=0)
            assert result.get("prev_report_date") is None
            assert result.get("prev_kpis") is None
        elif path.endswith("/asset-structure"):
            assert result.get("items") == []
            _assert_numeric(result["total_market_value"], unit="yuan", raw=0)
        elif path.endswith("/yield-distribution"):
            assert result.get("items") == []
            _assert_numeric(result["weighted_ytm"], unit="pct", raw=0)
        elif path.endswith("/maturity-structure"):
            assert result.get("items") == []
            _assert_numeric(result["total_market_value"], unit="yuan", raw=0)
        elif path.endswith("/industry-distribution"):
            assert result.get("items") == []
        elif path.endswith("/risk-indicators"):
            _assert_numeric(result["total_market_value"], unit="yuan", raw=0)
            _assert_numeric(result["total_dv01"], unit="dv01", raw=0)
            _assert_numeric(result["weighted_duration"], unit="ratio", raw=0)
            _assert_numeric(result["credit_ratio"], unit="ratio", raw=0)
            _assert_numeric(result["total_spread_dv01"], unit="dv01", raw=0)
        elif path.endswith("/business-type-metrics"):
            assert result.get("report_date") == REPORT_DATE
            assert result.get("items") == []
        else:
            assert result.get("items") == []


def test_bond_dashboard_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    route_module = load_module(
        "tests._bond_dashboard_routes_auth",
        "backend/app/api/routes/bond_dashboard.py",
    )
    app = FastAPI()
    app.include_router(route_module.router)
    sqlite_path = tmp_path / "bond-dashboard-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    client = TestClient(app)

    for path, params in _BOND_DASHBOARD_CASES:
        response = client.get(path, params=params, headers=BOND_DASHBOARD_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_bond_dashboard_endpoints_envelope_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _check_all_on_empty_db(tmp_path, monkeypatch)
    get_settings.cache_clear()


def test_bond_dashboard_service_uses_shared_lineage_and_meta_helpers() -> None:
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "bond_dashboard_service.py"
    src = path.read_text(encoding="utf-8")

    assert "resolve_formal_facts_lineage" in src
    assert "build_formal_result_meta_from_lineage" in src
    assert "build_formal_result_envelope_from_lineage" in src


def test_bond_dashboard_service_reuses_formal_fact_rows_for_same_report_date(monkeypatch) -> None:
    service_mod = load_module(
        "tests._bond_dashboard_service_fact_cache",
        "backend/app/services/bond_dashboard_service.py",
    )
    service_mod.clear_bond_dashboard_runtime_cache()

    class FakeBondDashboardRepo:
        fetch_fact_calls = 0

        def list_report_dates(self):
            return [REPORT_DATE]

        def fetch_bond_analytics_rows(self, *, report_date):
            assert report_date == REPORT_DATE
            type(self).fetch_fact_calls += 1
            return [
                {
                    "source_version": "sv_cached_fact",
                    "rule_version": "rv_cached_fact",
                }
            ]

        def fetch_dashboard_headline_kpis(self, report_date, prev_report_date=None):
            assert report_date == REPORT_DATE
            assert prev_report_date is None
            row = {
                "total_market_value": Decimal("1000"),
                "unrealized_pnl": Decimal("0"),
                "weighted_ytm": Decimal("0.03"),
                "weighted_duration": Decimal("3"),
                "weighted_coupon": Decimal("0.025"),
                "credit_spread_median": Decimal("0.001"),
                "total_dv01": Decimal("1"),
                "bond_count": 1,
            }
            return {"current": row, "previous": None}

        def fetch_dashboard_risk_indicators(self, report_date):
            assert report_date == REPORT_DATE
            return {
                "total_market_value": Decimal("1000"),
                "total_dv01": Decimal("1"),
                "weighted_duration": Decimal("3"),
                "credit_ratio": Decimal("0.2"),
                "weighted_convexity": Decimal("0.1"),
                "total_spread_dv01": Decimal("0.2"),
                "reinvestment_ratio_1y": Decimal("0.1"),
            }

        def fetch_dashboard_portfolio_comparison(self, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "portfolio_name": "P1",
                    "total_market_value": Decimal("1000"),
                    "weighted_ytm": Decimal("0.03"),
                    "weighted_duration": Decimal("3"),
                    "total_dv01": Decimal("1"),
                    "bond_count": 1,
                }
            ]

    monkeypatch.setattr(service_mod, "_repo", FakeBondDashboardRepo)
    monkeypatch.setattr(
        service_mod,
        "_duckdb_cache_version_token",
        lambda: ("fake.duckdb", 1),
    )

    service_mod.get_bond_dashboard_headline_kpis(date.fromisoformat(REPORT_DATE))
    service_mod.get_bond_dashboard_risk_indicators(date.fromisoformat(REPORT_DATE))
    service_mod.get_bond_dashboard_portfolio_comparison(date.fromisoformat(REPORT_DATE))

    assert FakeBondDashboardRepo.fetch_fact_calls == 1


def test_bond_dashboard_home_summary_builds_child_payloads_without_child_envelopes(monkeypatch) -> None:
    service_mod = load_module(
        "tests._bond_dashboard_home_summary_payload_builders",
        "backend/app/services/bond_dashboard_service.py",
    )
    service_mod.clear_bond_dashboard_runtime_cache()

    class FakeBondDashboardRepo:
        fetch_headline_calls = 0

        def list_report_dates(self):
            return [REPORT_DATE]

        def fetch_bond_analytics_rows(self, *, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "source_version": "sv_home_summary",
                    "rule_version": "rv_home_summary",
                }
            ]

        def fetch_dashboard_headline_kpis(self, report_date, prev_report_date=None):
            assert report_date == REPORT_DATE
            assert prev_report_date is None
            type(self).fetch_headline_calls += 1
            row = {
                "total_market_value": Decimal("1000"),
                "unrealized_pnl": Decimal("10"),
                "weighted_ytm": Decimal("0.03"),
                "weighted_duration": Decimal("3"),
                "weighted_coupon": Decimal("0.025"),
                "credit_spread_median": Decimal("0.001"),
                "total_dv01": Decimal("1"),
                "bond_count": 1,
            }
            return {"current": row, "previous": None}

        def fetch_dashboard_risk_indicators(self, report_date):
            assert report_date == REPORT_DATE
            return {
                "total_market_value": Decimal("1000"),
                "total_dv01": Decimal("1"),
                "weighted_duration": Decimal("3"),
                "credit_ratio": Decimal("0.2"),
                "weighted_convexity": Decimal("0.1"),
                "total_spread_dv01": Decimal("0.2"),
                "reinvestment_ratio_1y": Decimal("0.1"),
            }

        def fetch_dashboard_asset_structure(self, report_date, group_by):
            assert report_date == REPORT_DATE
            return [
                {
                    "category": group_by,
                    "total_market_value": Decimal("1000"),
                    "bond_count": 1,
                }
            ]

        def fetch_dashboard_maturity_structure(self, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "maturity_bucket": "1-3Y",
                    "total_market_value": Decimal("1000"),
                    "bond_count": 1,
                }
            ]

        def fetch_dashboard_industry_distribution(self, report_date, top_n=10):
            assert report_date == REPORT_DATE
            assert top_n == 10
            return [
                {
                    "industry_name": "Industry",
                    "total_market_value": Decimal("1000"),
                    "bond_count": 1,
                }
            ]

        def fetch_dashboard_yield_distribution(self, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "yield_bucket": "2.0%-2.5%",
                    "total_market_value": Decimal("1000"),
                    "bond_count": 1,
                }
            ]

        def fetch_dashboard_portfolio_comparison(self, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "portfolio_name": "P1",
                    "total_market_value": Decimal("1000"),
                    "weighted_ytm": Decimal("0.03"),
                    "weighted_duration": Decimal("3"),
                    "total_dv01": Decimal("1"),
                    "bond_count": 1,
                }
            ]

        def fetch_dashboard_spread_by_bond_type(self, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "bond_type": "Bond",
                    "median_yield": Decimal("0.03"),
                    "bond_count": 1,
                    "total_market_value": Decimal("1000"),
                }
            ]

        def fetch_business_type_metrics(self, report_date):
            assert report_date == REPORT_DATE
            return [
                {
                    "name": "Bond",
                    "market_value": Decimal("1000"),
                    "weighted_avg_ytm": Decimal("0.03"),
                    "weighted_avg_duration": Decimal("3"),
                }
            ]

    def fail_child_envelope(*args, **kwargs):
        raise AssertionError("home-summary should not build child envelopes")

    monkeypatch.setattr(service_mod, "_repo", FakeBondDashboardRepo)
    monkeypatch.setattr(
        service_mod,
        "_duckdb_cache_version_token",
        lambda: ("fake.duckdb", 1),
    )
    monkeypatch.setattr(service_mod, "build_formal_result_envelope", fail_child_envelope)
    monkeypatch.setattr(service_mod, "build_formal_result_meta_from_lineage", fail_child_envelope)

    payload = service_mod.get_bond_dashboard_home_summary(date.fromisoformat(REPORT_DATE))
    cached_payload = service_mod.get_bond_dashboard_home_summary(date.fromisoformat(REPORT_DATE))

    assert payload["result_meta"]["result_kind"] == "bond_dashboard.home_summary"
    result = payload["result"]
    assert result["headline"]["kpis"]["total_market_value"]["raw"] == 1000.0
    assert result["asset_type"]["group_by"] == "bond_type"
    assert result["asset_rating"]["group_by"] == "rating"
    assert result["business_type"]["items"][0]["name"] == "Bond"
    assert FakeBondDashboardRepo.fetch_headline_calls == 1
    assert cached_payload["result"] == payload["result"]
    assert cached_payload["result_meta"]["trace_id"] != payload["result_meta"]["trace_id"]


def test_bond_dashboard_dates_falls_back_to_facts_lineage_when_manifest_missing(tmp_path, monkeypatch) -> None:
    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-fallback.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    _replace_bond_dashboard_rows(
        repo,
        report_date=REPORT_DATE,
        rows=[
            BondAnalyticsRow(
                report_date=date.fromisoformat(REPORT_DATE),
                instrument_code="B1",
                instrument_name="B1",
                portfolio_name="P1",
                cost_center="C1",
                asset_class_raw="x",
                asset_class_std="rate",
                bond_type="国债",
                issuer_name="I",
                industry_name="银行",
                rating="AAA",
                accounting_class="AC",
                accounting_rule_id="r1",
                currency_code="CNY",
                face_value=Decimal("1000000"),
                market_value_native=Decimal("1000000"),
                market_value=Decimal("1000000"),
                amortized_cost=Decimal("1000000"),
                accrued_interest=Decimal("0"),
                coupon_rate=Decimal("0.025"),
                interest_mode="fixed",
                interest_payment_frequency="annual",
                interest_rate_style="fixed",
                ytm=Decimal("0.03"),
                maturity_date=date(2030, 1, 1),
                next_call_date=None,
                years_to_maturity=Decimal("2.5"),
                tenor_bucket="1-3年",
                macaulay_duration=Decimal("2"),
                modified_duration=Decimal("1.9"),
                convexity=Decimal("0.01"),
                dv01=Decimal("100"),
                is_credit=False,
                spread_dv01=Decimal("0"),
                source_version="sv_dash_row",
                rule_version="rv_dash_row",
                ingest_batch_id="ib",
                trace_id="tr",
            )
        ],
    )

    payload = load_module(
        "backend.app.services.bond_dashboard_service",
        "backend/app/services/bond_dashboard_service.py",
    ).get_bond_dashboard_dates()

    assert payload["result_meta"]["source_version"] == "sv_dash_row"
    assert payload["result_meta"]["rule_version"] == "rv_bond_analytics_formal_materialize_v1"
    assert payload["result_meta"]["cache_version"] == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1"
    assert payload["result"]["report_dates"] == [REPORT_DATE]
    assert payload["data_source"] == "bond_analytics_facts"
    get_settings.cache_clear()


def test_bond_dashboard_group_by_validation_422(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    response = client.get(
        "/api/bond-dashboard/asset-structure",
        params={"report_date": REPORT_DATE, "group_by": "not_a_column"},
    )
    assert response.status_code == 422
    get_settings.cache_clear()


def test_bond_dashboard_headline_logs_api_perf(tmp_path, monkeypatch, caplog) -> None:
    duckdb_path = tmp_path / "empty-perf.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get(
            "/api/bond-dashboard/headline-kpis",
            params={"report_date": REPORT_DATE},
        )

    assert response.status_code == 200
    records = _perf_records(caplog, "/api/bond-dashboard/headline-kpis")
    assert records
    record = records[-1]
    assert record.getMessage() == "moss_api_perf"
    assert getattr(record, "duration_ms") >= 0
    assert getattr(record, "result_kind") == "bond_dashboard.headline_kpis"
    assert getattr(record, "trace_id")
    assert getattr(record, "duckdb_statement_count") is None
    get_settings.cache_clear()


def test_bond_dashboard_headline_kpis_metadata_preserves_candidate_boundary(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "headline-candidate.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)

    response = client.get(
        "/api/bond-dashboard/headline-kpis",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    meta = payload["result_meta"]
    assert meta["result_kind"] == "bond_dashboard.headline_kpis"
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["source_surface"] == "bond_analytics"
    assert meta["requested_report_date"] == REPORT_DATE
    assert meta["resolved_report_date"] == REPORT_DATE
    assert meta["as_of_date"] == REPORT_DATE
    assert meta["date_basis"] == "bond_dashboard_report_date"
    assert meta["filters_applied"] == {"report_date": REPORT_DATE}
    assert meta["tables_used"] == ["fact_formal_bond_analytics_daily"]
    assert meta["evidence_rows"] == 0
    get_settings.cache_clear()


def test_bond_dashboard_headline_kpis_shape_with_seeded_facts(tmp_path, monkeypatch) -> None:
    from decimal import Decimal

    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    d1 = "2026-03-30"
    d2 = "2026-03-31"
    for rd, mv, ytm in [
        (d1, Decimal("1000000"), Decimal("0.03")),
        (d2, Decimal("1100000"), Decimal("0.032")),
    ]:
        row = BondAnalyticsRow(
            report_date=date.fromisoformat(rd),
            instrument_code="B1",
            instrument_name="B1",
            portfolio_name="P1",
            cost_center="C1",
            asset_class_raw="x",
            asset_class_std="rate",
            bond_type="国债",
            issuer_name="I",
            industry_name="银行",
            rating="AAA",
            accounting_class="AC",
            accounting_rule_id="r1",
            currency_code="CNY",
            face_value=Decimal("1000000"),
            market_value_native=mv,
            market_value=mv,
            amortized_cost=mv,
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.025"),
            interest_mode="fixed",
            interest_payment_frequency="annual",
            interest_rate_style="fixed",
            ytm=ytm,
            maturity_date=date(2030, 1, 1),
            next_call_date=None,
            years_to_maturity=Decimal("2.5"),
            tenor_bucket="1-3年",
            macaulay_duration=Decimal("2"),
            modified_duration=Decimal("1.9"),
            convexity=Decimal("0.01"),
            dv01=Decimal("100"),
            is_credit=False,
            spread_dv01=Decimal("0"),
            source_version="sv",
            rule_version="rv",
            ingest_batch_id="ib",
            trace_id="tr",
        )
        _replace_bond_dashboard_rows(repo, report_date=rd, rows=[row])

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    response = client.get("/api/bond-dashboard/headline-kpis", params={"report_date": d2})
    assert response.status_code == 200
    payload = response.json()
    _assert_bond_dashboard_headline_candidate_envelope(payload)
    res = payload["result"]
    assert res["prev_report_date"] == d1
    assert res["kpis"]["bond_count"] == 1
    assert res["prev_kpis"] is not None
    assert res["prev_kpis"]["bond_count"] == 1
    _assert_numeric(res["kpis"]["total_market_value"], unit="yuan", raw=Decimal("1100000"))
    _assert_numeric(res["kpis"]["weighted_ytm"], unit="pct", raw=Decimal("0.032"))
    _assert_numeric(res["kpis"]["weighted_duration"], unit="ratio", raw=Decimal("1.9"))
    _assert_numeric(res["kpis"]["total_dv01"], unit="dv01", raw=Decimal("100"))
    _assert_numeric(res["prev_kpis"]["total_market_value"], unit="yuan", raw=Decimal("1000000"))
    assert res["kpis"]["total_market_value"] != res["prev_kpis"]["total_market_value"]
    get_settings.cache_clear()


def test_bond_dashboard_main_endpoints_return_numeric_payloads_with_seeded_facts(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-numeric-contract.duckdb"
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
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="OTHER",
            portfolio_name="P2",
            asset_class_std="other",
            market_value=Decimal("600"),
            ytm=Decimal("0"),
            modified_duration=Decimal("0"),
            bond_type_label="Other",
        ),
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)

    headline = client.get("/api/bond-dashboard/headline-kpis", params={"report_date": REPORT_DATE})
    assert headline.status_code == 200, headline.text
    headline_kpis = headline.json()["result"]["kpis"]
    _assert_numeric(headline_kpis["total_market_value"], unit="yuan", raw=Decimal("1000"))
    _assert_numeric(headline_kpis["weighted_ytm"], unit="pct", raw=Decimal("0.035"))
    _assert_numeric(headline_kpis["weighted_duration"], unit="ratio", raw=Decimal("5"))
    _assert_numeric(headline_kpis["total_dv01"], unit="dv01", raw=Decimal("0.8"))

    asset = client.get(
        "/api/bond-dashboard/asset-structure",
        params={"report_date": REPORT_DATE, "group_by": "bond_type"},
    )
    assert asset.status_code == 200, asset.text
    asset_result = asset.json()["result"]
    _assert_numeric(asset_result["total_market_value"], unit="yuan", raw=Decimal("1000"))
    asset_item = asset_result["items"][0]
    _assert_numeric(asset_item["total_market_value"], unit="yuan", raw=Decimal("600"))
    _assert_numeric(asset_item["percentage"], unit="pct", raw=Decimal("0.6"))

    yield_distribution = client.get("/api/bond-dashboard/yield-distribution", params={"report_date": REPORT_DATE})
    assert yield_distribution.status_code == 200, yield_distribution.text
    yield_result = yield_distribution.json()["result"]
    _assert_numeric(yield_result["weighted_ytm"], unit="pct", raw=Decimal("0.035"))
    _assert_numeric(yield_result["items"][0]["total_market_value"], unit="yuan")

    portfolio = client.get("/api/bond-dashboard/portfolio-comparison", params={"report_date": REPORT_DATE})
    assert portfolio.status_code == 200, portfolio.text
    portfolio_item = portfolio.json()["result"]["items"][0]
    _assert_numeric(portfolio_item["total_market_value"], unit="yuan")
    _assert_numeric(portfolio_item["weighted_ytm"], unit="pct")
    _assert_numeric(portfolio_item["weighted_duration"], unit="ratio")
    _assert_numeric(portfolio_item["total_dv01"], unit="dv01")

    spread = client.get("/api/bond-dashboard/spread-analysis", params={"report_date": REPORT_DATE})
    assert spread.status_code == 200, spread.text
    spread_item = spread.json()["result"]["items"][0]
    _assert_numeric(spread_item["median_yield"], unit="pct")
    _assert_numeric(spread_item["total_market_value"], unit="yuan")

    maturity = client.get("/api/bond-dashboard/maturity-structure", params={"report_date": REPORT_DATE})
    assert maturity.status_code == 200, maturity.text
    maturity_result = maturity.json()["result"]
    _assert_numeric(maturity_result["total_market_value"], unit="yuan", raw=Decimal("1000"))
    _assert_numeric(maturity_result["items"][0]["total_market_value"], unit="yuan")
    _assert_numeric(maturity_result["items"][0]["percentage"], unit="pct", raw=Decimal("1"))

    industry = client.get(
        "/api/bond-dashboard/industry-distribution",
        params={"report_date": REPORT_DATE, "top_n": 10},
    )
    assert industry.status_code == 200, industry.text
    industry_item = industry.json()["result"]["items"][0]
    _assert_numeric(industry_item["total_market_value"], unit="yuan", raw=Decimal("1000"))
    _assert_numeric(industry_item["percentage"], unit="pct", raw=Decimal("1"))

    risk = client.get("/api/bond-dashboard/risk-indicators", params={"report_date": REPORT_DATE})
    assert risk.status_code == 200, risk.text
    risk_result = risk.json()["result"]
    _assert_numeric(risk_result["total_market_value"], unit="yuan", raw=Decimal("1000"))
    _assert_numeric(risk_result["total_dv01"], unit="dv01", raw=Decimal("0.8"))
    _assert_numeric(risk_result["weighted_duration"], unit="ratio", raw=Decimal("5"))
    _assert_numeric(risk_result["credit_ratio"], unit="ratio", raw=Decimal("0.3"))
    _assert_numeric(risk_result["total_spread_dv01"], unit="dv01", raw=Decimal("0.6"))

    business_type = client.get("/api/bond-dashboard/business-type-metrics", params={"report_date": REPORT_DATE})
    assert business_type.status_code == 200, business_type.text
    business_item = business_type.json()["result"]["items"][0]
    assert isinstance(business_item["market_value"], str)
    assert isinstance(business_item["weighted_avg_ytm_pct"], str)
    get_settings.cache_clear()


def test_bond_dashboard_weighted_yield_and_duration_exclude_other_or_no_maturity_assets(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-eligible.duckdb"
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
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="CREDIT",
            portfolio_name="P1",
            asset_class_std="credit",
            market_value=Decimal("300"),
            ytm=Decimal("0.04"),
            modified_duration=Decimal("6"),
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="OTHER",
            portfolio_name="P1",
            asset_class_std="other",
            market_value=Decimal("600"),
            ytm=Decimal("0"),
            modified_duration=Decimal("0"),
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="NO-MATURITY",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("1000"),
            ytm=Decimal("0.99"),
            modified_duration=Decimal("0"),
            maturity_date=None,
        ),
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)

    headline = client.get("/api/bond-dashboard/headline-kpis", params={"report_date": REPORT_DATE})
    assert headline.status_code == 200, headline.text
    headline_result = headline.json()["result"]
    assert headline_result["kpis"]["bond_count"] == 4
    assert _metric_raw(headline_result["kpis"]["weighted_ytm"]) == Decimal("0.035")
    assert _metric_raw(headline_result["kpis"]["weighted_duration"]) == Decimal("5")

    yield_distribution = client.get("/api/bond-dashboard/yield-distribution", params={"report_date": REPORT_DATE})
    assert yield_distribution.status_code == 200, yield_distribution.text
    assert _metric_raw(yield_distribution.json()["result"]["weighted_ytm"]) == Decimal("0.035")

    portfolio = client.get("/api/bond-dashboard/portfolio-comparison", params={"report_date": REPORT_DATE})
    assert portfolio.status_code == 200, portfolio.text
    item = portfolio.json()["result"]["items"][0]
    assert _metric_raw(item["weighted_ytm"]) == Decimal("0.035")
    assert _metric_raw(item["weighted_duration"]) == Decimal("5")

    risk = client.get("/api/bond-dashboard/risk-indicators", params={"report_date": REPORT_DATE})
    assert risk.status_code == 200, risk.text
    assert _metric_raw(risk.json()["result"]["weighted_duration"]) == Decimal("5")
    get_settings.cache_clear()


def test_bond_dashboard_distribution_percentage_keeps_sub_one_percent_ratio(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-small-percentage.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    rows = [
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="LARGE",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("199"),
            ytm=Decimal("0.02"),
            modified_duration=Decimal("2"),
            bond_type_label="Large",
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="SMALL",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("1"),
            ytm=Decimal("0.02"),
            modified_duration=Decimal("2"),
            bond_type_label="Small",
        ),
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    response = client.get(
        "/api/bond-dashboard/asset-structure",
        params={"report_date": REPORT_DATE, "group_by": "bond_type"},
    )
    assert response.status_code == 200, response.text

    by_category = {item["category"]: item for item in response.json()["result"]["items"]}
    _assert_numeric(by_category["Large"]["percentage"], unit="pct", raw=Decimal("0.995"))
    _assert_numeric(by_category["Small"]["percentage"], unit="pct", raw=Decimal("0.005"))
    assert by_category["Small"]["percentage"]["display"] == "0.50%"
    get_settings.cache_clear()


def test_business_type_metrics_returns_envelope(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-btm.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    rows = [
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="B1",
            portfolio_name="P1",
            asset_class_std="rate",
            market_value=Decimal("100"),
            ytm=Decimal("0.02"),
            modified_duration=Decimal("2"),
            bond_type_label="国债",
        ),
        _make_bond_analytics_row(
            report_date=REPORT_DATE,
            instrument_code="B2",
            portfolio_name="P1",
            asset_class_std="credit",
            market_value=Decimal("300"),
            ytm=Decimal("0.04"),
            modified_duration=Decimal("6"),
            bond_type_label="政金债",
        ),
    ]
    _replace_bond_dashboard_rows(repo, report_date=REPORT_DATE, rows=rows)

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)
    rsp = client.get("/api/bond-dashboard/business-type-metrics", params={"report_date": REPORT_DATE})
    assert rsp.status_code == 200, rsp.text
    payload = rsp.json()
    _assert_formal_envelope(payload)
    items = payload["result"]["items"]
    assert len(items) >= 2
    names = {it["name"] for it in items}
    assert "国债" in names and "政金债" in names
    assert all("weighted_avg_ytm_pct" in it for it in items)
    assert all("market_value" in it for it in items)
    get_settings.cache_clear()
