"""MS006 preserves raw price analysis but never labels it verified NAV."""
from datetime import date, timedelta

import duckdb
import pandas as pd
import pytest

from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.services import macro_toolkit_route_support as support

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_toolkit]


def _seed_strategy_prices(path):
    """Raw split-like prices and existing factor inputs, only in the caller's temp DB."""
    day, code = date(2026, 10, 6), "SYN001.SZ"
    with duckdb.connect(str(path)) as conn:
        for filename, table in (
            ("21_choice_stock.sql", "choice_stock_daily_observation"),
            ("27_choice_stock_factor_snapshot.sql", "choice_stock_factor_snapshot"),
        ):
            statements = parse_registry_sql_text((REGISTRY_DIR / filename).read_text(encoding="utf-8"))
            conn.execute(next(sql for sql in statements if sql.startswith(f"create table if not exists {table} (")))
        conn.execute("""insert into choice_stock_factor_snapshot
            (as_of_date, stock_code, pe, pb, ps, roe, gross_margin,
             three_month_return, twelve_month_return, volatility, dividend_yield,
             industry, source_version, vendor_version, rule_version, run_id)
            values (?, ?, 10, 1, 2, .15, .30, .1, .2, .15, .03,
                    'synthetic-industry', 'sv_synthetic_factor', 'vv_synthetic_factor', ?, 'synthetic-factor')
        """, [str(day - timedelta(days=1)), code, "synthetic-factor-rule"])
        days = [day - timedelta(days=79 - index) for index in range(80)]
        conn.executemany("""insert into choice_stock_daily_observation
            (stock_code, trade_date, close_value, turn, amount, volume,
             tradestatus, source_version, vendor_version, run_id)
            values (?, ?, ?, 2, 1000000, 1000000, '1',
                    'sv_synthetic_raw_price', 'vv_choice_tushare_stock_20261006_aaaaaaaaaaaa', 'synthetic-price')
        """, [(code, str(item), 50.0 if item == day else 100.0) for item in days])
    return path


def test_unavailable_results_are_not_described_as_absent_summaries():
    summaries = [{"status": "unavailable", "result": {"data_status": "unavailable"}} for _ in range(4)]
    status = support._equity_strategy_payload_data_status(summaries)
    assert status == {"status": "unavailable", "summary_count": 4, "reason": "all_strategies_unavailable"}
    warnings = support._equity_strategy_payload_warnings(status)
    assert warnings == ["已返回策略说明，当前各策略均无可用结果；请查看对应策略的缺失证据。"]
    empty = support._equity_strategy_payload_data_status([])
    assert empty["reason"] == "no_strategy_summaries"


def test_existing_research_strategies_still_use_previous_close_positions():
    from backend.app.core_finance.macro.equity_strategies import moving_average_strategy, mean_reversion_momentum_strategy
    ma = moving_average_strategy(pd.DataFrame({"SYN": [100., 100., 100., 90., 95., 110., 220.]}),
                                 short_window=2, long_window=3)
    assert ma.iloc[5] == 1.0  # Entry close cannot capture its own price jump.
    assert ma.iloc[6] == 2.0
    mr = mean_reversion_momentum_strategy(pd.DataFrame({"SYN": [50., 50., 100., 90., 99.]}),
                                          short_window=2, long_window=3, z_threshold=.5)
    assert mr.iloc[3] == 1.0
    assert mr.iloc[4] == pytest.approx(1.1)


def test_unverified_raw_prices_do_not_publish_nav(monkeypatch):
    # The split is economically neutral; raw prices alone cannot establish its return.
    prices = pd.DataFrame({"SYN001": [100.] * 79 + [50.]}, index=pd.date_range("2026-01-01", periods=80))
    context = {"prices": prices, "as_of_date": "2026-03-21", "tables_used": ["choice_stock_daily_observation"],
               "source_versions": ["sv_synthetic"], "vendor_versions": ["vv_synthetic"]}
    monkeypatch.setattr(support, "_real_multi_factor_summary", lambda *a, **kw: {"key": "multi_factor_selection", "preserved": True})
    monkeypatch.setattr(support, "_real_low_crowding_regime_multifactor_summary", lambda *a, **kw: {"key": "low_crowding", "preserved": True})
    summaries = support._real_equity_strategy_summaries(context)
    for summary in summaries[:2]:
        assert summary["status"] == "unavailable"
        assert summary["primary_metric"] is None
        assert summary["result"]["final_value"] is None
        assert summary["result"]["return_basis_status"] == "unverified"
        assert summary["result"]["benchmark_status"] == "not_configured"
        assert summary["result"]["position_timing"] == "previous_close_position"
    assert summaries[2]["preserved"] is True
    assert summaries[3]["preserved"] is True


def test_real_strategy_http_keeps_raw_context_without_publishing_nav(tmp_path, monkeypatch):
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import macro_toolkit as routes
    from backend.app.services import macro_toolkit_read_service as read_service
    from backend.app.repositories.user_scope_repo import UserScopeRepository
    from backend.app.security.auth_context import AuthContext, get_auth_context
    path = _seed_strategy_prices(tmp_path / "strategy.duckdb")
    settings = SimpleNamespace(duckdb_path=str(path), governance_path=str(tmp_path / "governance"),
                               governance_sql_dsn=f"sqlite:///{tmp_path / 'scopes.sqlite'}")
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    scopes.grant_scope(user_id="synthetic-reader", role="viewer", resource="macro_toolkit", action="read",
                       operator="synthetic-test", reason="Isolated synthetic MS006 read")
    scopes.engine.dispose()
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(read_service, "get_settings", lambda: settings)
    # These independent capabilities are outside MS006; SQL/price loader, strategy
    # summaries, aggregation, schema, registered GET route and read guard are real.
    monkeypatch.setattr(support, "compute_equity_shadow_portfolio_report", lambda *a, **kw: {})
    monkeypatch.setattr(support, "_macro_etf_strategy_snapshot_for_toolkit", lambda *a, **kw: {})
    monkeypatch.setattr(support, "_choice_stock_refresh_overview", lambda *a, **kw: {})
    monkeypatch.setattr(routes, "_choice_stock_refresh_overview", lambda *a, **kw: {})
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext("synthetic-reader", "viewer", "synthetic-test")
    with TestClient(app) as client:
        response = client.get("/ui/macro/toolkit/analysis/strategy-summaries")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    summaries = payload["result"]["strategy_summaries"]
    assert len(summaries) == 4
    for summary in summaries[:2]:
        assert summary["primary_metric"] is None
        assert summary["result"]["final_value"] is None
        assert summary["result"]["stock_count"] == 1
        assert summary["result"]["observation_count"] == 80
        assert summary["result"]["return_basis_status"] == "unverified"
        assert summary["result"]["benchmark_status"] == "not_configured"
    assert summaries[2]["key"] == "multi_factor_selection"
    assert summaries[2]["status"] == "complete"
    assert payload["result"]["strategy_data_status"]["status"] == "degraded"
    output = os.environ.get("MOSS_STRATEGY_HTTP_FIXTURE_OUTPUT")
    if output:
        Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
