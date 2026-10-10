from __future__ import annotations

import duckdb
import pytest

from backend.app.core_finance.portfolio_backtest import run_portfolio_backtest
from backend.app.core_finance.portfolio_paths import position_path_key
from scripts.run_portfolio_backtest import _load_execution_rows

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]


def _row(**overrides):
    return dict(dict(signal_date="2026-05-29", stock_code="A", candidate_rank=1,
                     market_state="HOT", entry_date="2026-06-01", entry_price=10,
                     signal_close=10, entry_executable=True, exit_date_5d="2026-06-05",
                     return_5d_net_adj=0), **overrides)


@pytest.mark.parametrize("today", [0, 1])
def test_first_open_uses_prior_decision_outside_equity_window(today):
    result = run_portfolio_backtest([_row()], exposure_by_date={"2026-05-29": 0, "2026-06-01": today},
                                   max_positions=1, exposure_by_market_state={"HOT": 1})
    assert result.equity_curve[0]["date"] == "2026-06-01"
    assert result.equity_curve[0]["buy_notional"] == 0
    assert result.equity_curve[0]["entry_exposure_date"] == "2026-05-29"


def test_newer_off_state_takes_precedence_over_older_actual_exposure():
    result = run_portfolio_backtest([
        _row(signal_date="2026-05-28", entry_date="2026-05-29", exit_date_5d="2026-05-29"),
        _row(stock_code="B", signal_date="2026-06-01", market_state="OFF",
             entry_date="2026-06-02", exit_date_5d="2026-06-08"),
    ], [{"trade_date": "2026-06-01", "market_state": "OFF"}],
        exposure_by_date={"2026-05-29": 1}, max_positions=1,
        exposure_by_market_state={"HOT": 1, "OFF": 0})
    assert [t["stock_code"] for t in result.trades if t["action"] == "buy"] == ["A"]
    opening = next(e for e in result.equity_curve if e["date"] == "2026-06-02")
    assert opening["entry_exposure_date"] == "2026-06-01"
    assert opening["entry_exposure"] == 0


@pytest.mark.parametrize("factor", [1, 2])
@pytest.mark.parametrize("raw_key", ["open", "open_value"])
@pytest.mark.parametrize("execution_price", [None, 0, -1])
def test_missing_execution_price_uses_raw_path_open_for_premium(factor, raw_key, execution_price):
    paths = {position_path_key("A", "2026-06-01"): [
        dict(trade_date=f"2026-06-0{d}", **{raw_key: 12}, close=12,
             adj_open=12 * factor, adj_close=12 * factor, adj_factor=factor)
        for d in range(1, 6)]}
    result = run_portfolio_backtest([_row(entry_price=execution_price)], mode="path", price_paths=paths,
                                   max_positions=1, max_entry_premium=.05,
                                   exposure_by_market_state={"HOT": 1})
    assert result.skip_counts["entry_premium_blocked"] == 1
    assert result.trades == []


def test_no_prior_decision_does_not_use_same_day_signal():
    result = run_portfolio_backtest([_row(signal_date="2026-06-01")],
                                   exposure_by_date={"2026-06-01": 1}, max_positions=1)
    assert result.trades == []
    assert result.equity_curve[0]["entry_exposure_date"] is None


def test_cli_loads_signal_day_exposure_before_first_entry(tmp_path, monkeypatch):
    from contextlib import closing
    from scripts import run_portfolio_backtest as script

    db = tmp_path / "synthetic.duckdb"
    with closing(duckdb.connect(str(db))) as conn:
        conn.execute("create table livermore_candidate_execution_history(stock_code varchar)")
    monkeypatch.setattr(script, "read_only_connection", lambda *_args, **_kwargs: closing(duckdb.connect(str(db), read_only=True)))
    monkeypatch.setattr(script, "_load_execution_rows", lambda *_args, **_kwargs: ([_row()], []))

    class WindowChecked(Exception):
        pass

    def check_window(_conn, *, tables, start_date, end_date):
        assert start_date == "2026-05-29"
        assert end_date == "2026-06-05"
        raise WindowChecked

    monkeypatch.setattr(script, "_load_daily_exposure_rows", check_window)
    with pytest.raises(WindowChecked):
        script.run_portfolio_backtest_from_duckdb(db_path=str(db), report_path=tmp_path / "report.md", output_dir=tmp_path / "output")


@pytest.mark.parametrize("close_return", [0, 1])
def test_horizon_close_sale_cannot_fund_same_day_open(close_return):
    result = run_portfolio_backtest([
        _row(return_5d_net_adj=close_return),
        _row(stock_code="B", signal_date="2026-06-04", entry_date="2026-06-05", exit_date_5d="2026-06-11"),
    ], max_positions=1, exposure_by_market_state={"HOT": 1})
    assert [t["stock_code"] for t in result.trades if t["action"] == "buy"] == ["A"]
    assert result.equity_curve[-1]["cash"] == 100 * (1 + close_return)


@pytest.mark.parametrize("close_return", [0, 1])
def test_horizon_open_sizing_excludes_todays_close_gain_with_free_slot(close_return):
    result = run_portfolio_backtest([
        _row(return_5d_net_adj=close_return),
        _row(stock_code="B", signal_date="2026-06-04", entry_date="2026-06-05", exit_date_5d="2026-06-11"),
    ], max_positions=2, exposure_by_market_state={"HOT": 1})
    assert [t["amount"] for t in result.trades if t["action"] == "buy"] == [50, 50]


@pytest.mark.parametrize("execution_close", [True, False])
@pytest.mark.parametrize("factor", [1, 2])
def test_real_loader_price_basis_is_invariant_to_constant_adjustment(execution_close, factor):
    conn = duckdb.connect(":memory:")
    try:
        close_column = ", signal_close double" if execution_close else ""
        conn.execute(f"""create table livermore_candidate_execution_history (
          signal_date varchar, stock_code varchar, stock_name varchar, signal_kind varchar,
          candidate_rank integer, market_state varchar, entry_date varchar, entry_price double,
          entry_executable boolean, entry_block_reason varchar, exit_date_5d varchar,
          return_5d_net_adj double, exit_date_20d varchar, return_20d_net_adj double{close_column})""")
        conn.execute("insert into livermore_candidate_execution_history values ('2026-05-29', 'A', 'A', 'stock_candidate', 1, 'HOT', '2026-06-01', 10, true, null, '2026-06-05', 0, '2026-06-05', 0" + (", 10" if execution_close else "") + ")")
        conn.execute("create table choice_stock_daily_observation(trade_date varchar, stock_code varchar, close_value double)")
        conn.execute("insert into choice_stock_daily_observation values ('2026-05-29', 'A', 10)")
        conn.execute("create table stock_adjustment_factor(trade_date varchar, stock_code varchar, adj_factor double)")
        conn.execute("insert into stock_adjustment_factor values ('2026-05-29', 'A', ?)", [factor])
        rows, _ = _load_execution_rows(conn, tables={r[0] for r in conn.execute('show tables').fetchall()},
                                       signal_kind="stock_candidate", start_date=None, end_date=None)
    finally:
        conn.close()
    paths = {position_path_key("A", "2026-06-01"): [
        dict(trade_date=f"2026-06-0{d}", open=10, close=10, adj_open=10 * factor,
             adj_close=10 * factor, adj_factor=factor) for d in range(1, 6)]}
    result = run_portfolio_backtest(rows, mode="path", price_paths=paths, max_positions=1,
                                   max_entry_premium=.05, exposure_by_market_state={"HOT": 1})
    assert rows[0]["signal_close"] == 10
    assert sum(t["action"] == "buy" for t in result.trades) == 1
    assert next(t for t in result.trades if t["action"] == "buy")["entry_premium"] == 0
