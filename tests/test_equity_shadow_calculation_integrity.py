from __future__ import annotations

import math

import duckdb
import pandas as pd
import pytest

from backend.app.core_finance.macro import equity_shadow_portfolio as shadow

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_macro_toolkit]


@pytest.mark.parametrize("end_factor, expected", [(2.0, 0.0), (None, None), (0.0, None), (-1.0, None), (float("nan"), None), (math.inf, None)])
def test_shadow_split_uses_wealth_and_requires_valid_factors(end_factor, expected):
    with duckdb.connect(":memory:") as conn:
        conn.execute("create table choice_stock_daily_observation(stock_code varchar, trade_date varchar, close_value double)")
        conn.execute("create table stock_adjustment_factor(stock_code varchar, trade_date varchar, adj_factor double)")
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?)", [("A", "2026-01-01", 100), ("A", "2026-02-01", 50)])
        conn.executemany("insert into stock_adjustment_factor values (?, ?, ?)", [("A", "2026-01-01", 1), ("A", "2026-02-01", end_factor)])
        returns = shadow._simple_returns(conn, "2026-01-01", "2026-02-01", ["A"])
    # A two-for-one split preserves 1 * 100 == 2 * 50 of wealth.
    assert list(returns.index) == ["A"]
    if expected is None:
        assert pd.isna(returns.loc["A"])
    else:
        assert returns.loc["A"] == pytest.approx(expected)


@pytest.mark.parametrize("observed", [{"A": 0.08}, {}])
def test_shadow_missing_holding_return_is_not_reweighted_or_zero(observed):
    values = {("a", "b"): pd.Series(observed, dtype="float64")}
    assert shadow._selection_return(values, "a", "b", ["A", "B"]) is None


def _portfolio(monkeypatch, first_returns):
    frame = pd.DataFrame({"pe": [10.0, 10.0], "pb": [1.0, 1.0], "industry": ["I", "J"], "score": [1, 1]}, index=["A", "B"])
    monkeypatch.setattr(shadow, "_ranked_frame", lambda frame, *args, **kwargs: frame)
    monkeypatch.setattr(shadow, "_select_with_caps", lambda frame, **kwargs: frame)
    periods = [("a", "b"), ("b", "c")]
    returns = {periods[0]: pd.Series(first_returns, dtype="float64"), periods[1]: pd.Series({"A": 0.0, "B": 0.0})}
    return shadow._portfolio_result(periods, {key: frame for key in "abc"}, returns, dict.fromkeys(periods, 0.0), shadow.PORTFOLIOS[0])


def test_shadow_rebalance_pays_for_drift_even_when_names_do_not_change(monkeypatch):
    _, periods = _portfolio(monkeypatch, {"A": 0.5, "B": 0.0})
    # Start with 50 / 50; values become 75 / 50, weights 60 / 40.
    # Restoring 50 / 50 trades 10% sold plus 10% bought.
    assert periods[1]["traded_notional"] == pytest.approx(0.2)
    cost = next(row for row in periods[1]["cost_results"] if row["cost_bps"] == 50)
    assert cost["cost"] == pytest.approx(0.001)
    assert cost["net_return"] == pytest.approx(-0.001)


def test_shadow_missing_period_invalidates_cumulative_and_next_cost(monkeypatch):
    portfolio, periods = _portfolio(monkeypatch, {"A": 0.08})
    assert periods[0]["gross_return"] is None
    assert periods[1]["traded_notional"] is None
    assert portfolio["total_return"] is None
    assert portfolio["max_drawdown"] is None
    assert portfolio["win_rate"] is None
    assert all(row["total_return"] is None for row in portfolio["cost_results"])


def test_shadow_benchmark_requires_full_universe_coverage():
    report = shadow._benchmark_result([("a", "b")], {("a", "b"): pd.Series({"A": 0.08, "B": math.nan})})
    assert report["period_returns"][("a", "b")] is None
    assert report["payload"]["total_return"] is None


@pytest.mark.parametrize("factor_rows", [[], [("A", "b", 2.0), ("A", "b", 3.0)]])
def test_shadow_missing_or_ambiguous_factor_cannot_fall_back_to_raw(factor_rows):
    with duckdb.connect(":memory:") as conn:
        conn.execute("create table choice_stock_daily_observation(stock_code varchar, trade_date varchar, close_value double)")
        conn.execute("create table stock_adjustment_factor(stock_code varchar, trade_date varchar, adj_factor double)")
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?)", [("A", "a", 100), ("A", "b", 50)])
        conn.execute("insert into stock_adjustment_factor values ('A', 'a', 1)")
        if factor_rows:
            conn.executemany("insert into stock_adjustment_factor values (?, ?, ?)", factor_rows)
        returns = shadow._simple_returns(conn, "a", "b", ["A"])
    assert pd.isna(returns.loc["A"])


def test_shadow_partial_report_keeps_null_totals_and_blocks_admission(tmp_path):
    import json

    from tests.test_macro_toolkit_shadow_portfolio_report import _seed_shadow_report_db

    path = tmp_path / "shadow.duckdb"
    _seed_shadow_report_db(path)
    with duckdb.connect(str(path)) as conn:
        conn.execute("delete from stock_adjustment_factor where trade_date = '2026-05-02'")
    result = shadow.compute_equity_shadow_portfolio_report(path)
    assert result["status"] == "partial"
    assert "INCOMPLETE_ADJUSTED_RETURN_COVERAGE" in result["warnings"]
    assert result["benchmark"]["total_return"] is None
    for portfolio in result["portfolios"]:
        assert portfolio["total_return"] is None
        assert portfolio["excess_return"] is None
        assert portfolio["win_rate"] is None
        if portfolio["role"] == "shadow_candidate":
            assert portfolio["admission"]["status"] == "needs_review"
    json.dumps(result, allow_nan=False)
