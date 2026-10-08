"""Synthetic macro risk availability and scenario contract, never bank data."""
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from backend.app.core_finance.macro_bond_linkage import MacroEnvironmentScore, estimate_macro_impact_on_portfolio
from backend.app.repositories.macro_bond_linkage_repo import MacroBondLinkageRepository
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_data]
DAY = date(2026, 10, 6)


def environment():
    return MacroEnvironmentScore(DAY, "rising", .5, .25, 0, 0, 0, "synthetic", [], [])


def create_table(conn, filename, table):
    conn.execute(next(sql for sql in parse_registry_sql_text((REGISTRY_DIR / filename).read_text(encoding="utf-8"))
                      if sql.startswith(f"create table if not exists {table} (")))


def test_zero_market_value_is_unknown_ratio_not_zero():
    value = estimate_macro_impact_on_portfolio(environment(), Decimal(100), Decimal(40), Decimal(0))
    assert value["total_estimated_impact"] == Decimal(-1300)
    assert value["impact_ratio_to_market_value"] is None


def test_missing_risk_does_not_become_a_zero_scenario(tmp_path):
    path = tmp_path / "missing.duckdb"
    with duckdb.connect(str(path)):
        pass
    risk = MacroBondLinkageRepository(path).load_portfolio_metrics(DAY)
    assert risk["portfolio_dv01"] is None
    assert risk["portfolio_cs01"] is None
    assert risk["portfolio_market_value"] is None


def test_null_risk_leg_keeps_other_leg_but_total_unknown():
    result = estimate_macro_impact_on_portfolio(environment(), None, Decimal(40), Decimal(100000))
    assert result["estimated_rate_pnl_impact"] is None
    assert result["estimated_spread_pnl_impact"] == Decimal(200)
    assert result["total_estimated_impact"] is None
    assert result["impact_ratio_to_market_value"] is None


def test_valid_and_true_zero_keep_existing_linear_contract():
    result = estimate_macro_impact_on_portfolio(environment(), Decimal(100), Decimal(40), Decimal(100000))
    assert result["total_estimated_impact"] == Decimal(-1300)
    assert result["impact_ratio_to_market_value"] == Decimal("-.013")
    zero = estimate_macro_impact_on_portfolio(environment(), Decimal(0), Decimal(0), Decimal(100000))
    assert zero["total_estimated_impact"] == 0
    assert zero["impact_ratio_to_market_value"] == 0


def test_partial_bond_analytics_does_not_publish_subset_as_portfolio(tmp_path):
    path = tmp_path / "partial.duckdb"
    with duckdb.connect(str(path)) as conn:
        create_table(conn, "02_bond_analytics.sql", "fact_formal_bond_analytics_daily")
        conn.execute("""insert into fact_formal_bond_analytics_daily
          (report_date,instrument_code,portfolio_name,cost_center,currency_code,dv01,is_credit,spread_dv01,market_value,source_version,rule_version)
          values ('2026-10-05','SYN001','P1','C1','CNY',100,true,40,100000,'sv_synthetic','rv_synthetic'),
                 ('2026-10-05','SYN001','P2','C2','USD',null,true,null,50000,'sv_synthetic','rv_synthetic')""")
    risk = MacroBondLinkageRepository(path).load_portfolio_metrics(DAY)
    assert risk["portfolio_dv01"] is None
    assert risk["portfolio_cs01"] is None
    assert risk["portfolio_market_value"] == Decimal(150000)
    assert risk["risk_report_date"] == "2026-10-05"
    assert risk["coverage"]["dv01_observed_count"] == 1
    assert risk["coverage"]["row_count"] == 2
    assert len(risk["entities"]) == 2
    assert len({r["entity_id"] for r in risk["entities"]}) == 2


def test_empty_analytics_table_keeps_missing(tmp_path):
    path = tmp_path / "empty.duckdb"
    with duckdb.connect(str(path)) as conn:
        create_table(conn, "02_bond_analytics.sql", "fact_formal_bond_analytics_daily")
    assert MacroBondLinkageRepository(path).load_portfolio_metrics(DAY)["portfolio_dv01"] is None


@pytest.mark.parametrize("dv01,cs01,expected", [(None, 0, None), (0, 0, Decimal(0))])
def test_published_tensor_preserves_null_and_zero_and_actual_date(tmp_path, dv01, cs01, expected):
    path = tmp_path / "tensor.duckdb"
    with duckdb.connect(str(path)) as conn:
        create_table(conn, "04_risk_tensor.sql", "fact_formal_risk_tensor_daily")
        conn.execute("""insert into fact_formal_risk_tensor_daily
          (report_date,portfolio_dv01,cs01,total_market_value,bond_count,duration_excluded_count,
           source_version,rule_version,quality_flag,warnings_json)
          values ('2026-10-05',?,?,100000,2,1,'sv_tensor_synthetic','rv_tensor_synthetic','warning','["synthetic published warning"]')""", [dv01, cs01])
    risk = MacroBondLinkageRepository(path).load_portfolio_metrics(DAY)
    assert risk["portfolio_dv01"] == expected
    assert risk["risk_report_date"] == "2026-10-05"
    assert risk["coverage"]["duration_excluded_count"] == 1
    assert "synthetic published warning" in risk["warnings"]


def test_empty_published_tensor_scope_does_not_masquerade_as_observed_zero(tmp_path):
    path = tmp_path / "empty-tensor.duckdb"
    with duckdb.connect(str(path)) as conn:
        create_table(conn, "04_risk_tensor.sql", "fact_formal_risk_tensor_daily")
        conn.execute("""insert into fact_formal_risk_tensor_daily
          (report_date,portfolio_dv01,cs01,total_market_value,bond_count,quality_flag,warnings_json)
          values ('2026-10-06',0,0,0,0,'warning','["No bond analytics rows available for risk tensor materialization."]')""")
    risk = MacroBondLinkageRepository(path).load_portfolio_metrics(DAY)
    assert risk["portfolio_dv01"] is None
    assert risk["portfolio_cs01"] is None
    assert risk["coverage"]["row_count"] == 0
    assert estimate_macro_impact_on_portfolio(environment(), risk["portfolio_dv01"],
                                            risk["portfolio_cs01"], risk["portfolio_market_value"])["total_estimated_impact"] is None


@pytest.mark.parametrize("signal_available", [True, False, "neutral"])
def test_real_http_serializes_risk_availability_and_lineage(tmp_path, monkeypatch, signal_available):
    from datetime import timedelta
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import macro_bond_linkage as routes
    from backend.app.services import macro_bond_linkage_service as service
    from backend.app.core_finance.macro_bond_linkage import RATE_INDICATORS, LIQUIDITY_INDICATORS, GROWTH_INDICATORS, INFLATION_INDICATORS
    from backend.app.repositories.user_scope_repo import UserScopeRepository
    from backend.app.security.auth_context import AuthContext, get_auth_context

    path = tmp_path / "http.duckdb"
    with duckdb.connect(str(path)) as conn:
        create_table(conn, "11_choice_macro.sql", "fact_choice_macro_daily")
        create_table(conn, "03_yield_curve.sql", "fact_formal_yield_curve_daily")
        create_table(conn, "02_bond_analytics.sql", "fact_formal_bond_analytics_daily")
        for n in range(40):
            day = str(DAY - timedelta(days=39-n))
            codes = {**RATE_INDICATORS, **LIQUIDITY_INDICATORS, **GROWTH_INDICATORS, **INFLATION_INDICATORS} if signal_available else {"SYN_UNRELATED": "unrelated"}
            for code in codes:
                conn.execute("""insert into fact_choice_macro_daily
                  (series_id,series_name,trade_date,value_numeric,source_version,vendor_version,rule_version)
                  values (?,?,?,?,'sv_macro_synthetic','vv_synthetic','rv_synthetic')""", [code, code, day, 2 if signal_available == "neutral" else 2+n*.01])
            conn.execute("""insert into fact_formal_yield_curve_daily
              (trade_date,curve_type,tenor,rate_pct,source_version,vendor_version,rule_version)
              values (?,'treasury','10Y',?,'sv_curve_synthetic','vv_synthetic','rv_synthetic')""", [day, 2+n*.01])
        conn.execute("""insert into fact_formal_bond_analytics_daily
          (report_date,instrument_code,instrument_name,portfolio_name,cost_center,accounting_class,currency_code,
           dv01,is_credit,spread_dv01,market_value,source_version,rule_version)
          values ('2026-10-05','SYN001','合成券','P1','C1','FVOCI','CNY',100,true,40,100000,'sv_synthetic','rv_synthetic'),
                 ('2026-10-05','SYN001','合成券','P2','C2','AC','USD',null,true,null,50000,'sv_synthetic','rv_synthetic')""")
        if signal_available is not True:
            conn.execute("update fact_formal_bond_analytics_daily set dv01=100,spread_dv01=40")
    settings = SimpleNamespace(duckdb_path=str(path), governance_sql_dsn=f"sqlite:///{tmp_path / 'scopes.sqlite'}")
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    scopes.grant_scope(user_id="synthetic-reader", role="viewer", resource="macro_bond_linkage", action="read",
                       operator="synthetic-test", reason="Isolated synthetic risk read")
    scopes.engine.dispose()
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext("synthetic-reader", "viewer", "synthetic-test")
    with TestClient(app) as client:
        response = client.get("/api/macro-bond-linkage/analysis?report_date=2026-10-06")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    impact = payload["result"]["portfolio_impact"]
    if signal_available == "neutral":
        assert impact["status"] == "available"
        assert Decimal(impact["total_estimated_impact"]) == 0
        assert Decimal(impact["impact_ratio_to_market_value"]) == 0
        assert impact["availability_reason"] is None
    else:
        assert impact["status"] == "unavailable"
        assert impact["total_estimated_impact"] is None
    assert impact["risk_report_date"] == "2026-10-05"
    assert impact["entity_link_status"] == "aggregation_inputs"
    assert impact["coverage"]["dv01_observed_count"] == (1 if signal_available is True else 2)
    assert impact["entities"][1]["currency_code"] == "USD"
    if not signal_available:
        assert payload["result"]["environment_score"]["signal_status"] == "unavailable"
        assert impact["estimated_rate_change_bps"] is None
        assert impact["estimated_spread_widening_bps"] is None
        assert impact["availability_reason"] == "macro_signal_unavailable"
    output = os.environ.get("MOSS_MARKET_HTTP_FIXTURE_OUTPUT")
    if output and signal_available is True:
        Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.parametrize("scenario", [
    "inflation_only", "rate_only", "liquidity_only", "observed_neutral_axes",
    "neutral_missing_rate_risk", "neutral_missing_all_risk",
])
def test_real_http_requires_each_scenario_axis_evidence(tmp_path, monkeypatch, scenario):
    """Actual synthetic tables, repository and HTTP distinguish missing axes from neutral."""
    from datetime import timedelta
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import macro_bond_linkage as routes
    from backend.app.services import macro_bond_linkage_service as service
    from backend.app.core_finance.macro_bond_linkage import RATE_INDICATORS, LIQUIDITY_INDICATORS, INFLATION_INDICATORS
    from backend.app.repositories.user_scope_repo import UserScopeRepository
    from backend.app.security.auth_context import AuthContext, get_auth_context

    neutral = scenario.startswith("neutral_") or scenario == "observed_neutral_axes"
    codes = (INFLATION_INDICATORS if scenario == "inflation_only" else
             RATE_INDICATORS if scenario == "rate_only" else
             LIQUIDITY_INDICATORS if scenario == "liquidity_only" else
             {**RATE_INDICATORS, **LIQUIDITY_INDICATORS})
    path = tmp_path / "scenario-axis.duckdb"
    with duckdb.connect(str(path)) as conn:
        create_table(conn, "11_choice_macro.sql", "fact_choice_macro_daily")
        create_table(conn, "03_yield_curve.sql", "fact_formal_yield_curve_daily")
        create_table(conn, "02_bond_analytics.sql", "fact_formal_bond_analytics_daily")
        for n in range(40):
            day = str(DAY - timedelta(days=39-n))
            for code in codes:
                conn.execute("""insert into fact_choice_macro_daily
                  (series_id,series_name,trade_date,value_numeric,source_version,vendor_version,rule_version)
                  values (?,?,?,?,'sv_axis_synthetic','vv_axis_synthetic','rv_axis_synthetic')""",
                  [code, code, day, 2 if neutral else 2+n*.01])
            conn.execute("""insert into fact_formal_yield_curve_daily
              (trade_date,curve_type,tenor,rate_pct,source_version,vendor_version,rule_version)
              values (?,'treasury','10Y',?,'sv_curve_synthetic','vv_curve_synthetic','rv_curve_synthetic')""",
              [day, 2+n*.01])
        conn.execute("""insert into fact_formal_bond_analytics_daily
          (report_date,instrument_code,instrument_name,portfolio_name,cost_center,accounting_class,currency_code,
           dv01,is_credit,spread_dv01,market_value,source_version,rule_version)
          values ('2026-10-05','SYN-AXIS','合成情景券','SYN-P','SYN-C','FVOCI','CNY',
                  ?,true,?,100000,'sv_axis_risk_synthetic','rv_axis_risk_synthetic')""",
          [None if scenario.startswith("neutral_missing_") else 100,
           None if scenario == "neutral_missing_all_risk" else 40])
    settings = SimpleNamespace(duckdb_path=str(path), governance_sql_dsn=f"sqlite:///{tmp_path / 'scopes.sqlite'}")
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    scopes.grant_scope(user_id="axis-reader", role="viewer", resource="macro_bond_linkage", action="read",
                       operator="synthetic-test", reason="Synthetic scenario coverage regression")
    scopes.engine.dispose()
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext("axis-reader", "viewer", "synthetic-test")
    with TestClient(app) as client:
        response = client.get("/api/macro-bond-linkage/analysis?report_date=2026-10-06")
    assert response.status_code == 200, response.text
    payload = response.json()
    output = os.environ.get("MOSS_MACRO_AXIS_HTTP_OUTPUT_DIR")
    if output:
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"{scenario}-http.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    environment = payload["result"]["environment_score"]
    impact = payload["result"]["portfolio_impact"]
    assert environment["signal_status"] == "partial"
    assert impact["risk_report_date"] == "2026-10-05"
    covered = environment["signal_evidence_categories"]
    for axis, shock, pnl, sensitivity, multiplier in [
        ("rate", "estimated_rate_change_bps", "estimated_rate_pnl_impact", "portfolio_dv01", 30),
        ("liquidity", "estimated_spread_widening_bps", "estimated_spread_pnl_impact", "portfolio_cs01", -20),
    ]:
        if axis not in covered:
            assert impact[shock] is None
            assert impact[pnl] is None
        else:
            score_key = "rate_direction_score" if axis == "rate" else "liquidity_score"
            assert Decimal(impact[shock]) == Decimal(str(round(environment[score_key] * multiplier, 4)))
            if impact[sensitivity] is None:
                assert impact[pnl] is None
            else:
                assert Decimal(impact[pnl]) == -Decimal(impact[sensitivity]) * Decimal(impact[shock])
    if scenario == "observed_neutral_axes":
        assert impact["status"] == "available"
        assert Decimal(impact["total_estimated_impact"]) == 0
        assert Decimal(impact["impact_ratio_to_market_value"]) == 0
        assert impact["availability_reason"] is None
    else:
        assert impact["total_estimated_impact"] is None
        assert impact["impact_ratio_to_market_value"] is None
        assert impact["status"] == ("unavailable" if scenario in {"inflation_only", "neutral_missing_all_risk"} else "partial")
        assert impact["availability_reason"] == (
            "macro_signal_unavailable" if scenario == "inflation_only" else
            "risk_inputs_unavailable" if scenario == "neutral_missing_all_risk" else
            "risk_inputs_partial" if scenario == "neutral_missing_rate_risk" else "macro_signal_partial"
        )
        assert impact["ratio_unavailable_reason"] == (
            "impact_unavailable" if scenario.startswith("neutral_missing_") else impact["availability_reason"]
        )
