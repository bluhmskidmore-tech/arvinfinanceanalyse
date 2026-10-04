from __future__ import annotations

import duckdb
import pytest

from backend.app.core_finance import matched_baseline
from backend.app.core_finance.strategy_policy import POLICY

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_livermore]


@pytest.mark.parametrize("batch", [False, True])
def test_control_exit_uses_dedicated_limit_price_and_waits_until_sellable(batch):
    with duckdb.connect(":memory:") as conn:
        conn.execute("create table choice_stock_daily_observation(trade_date varchar, stock_code varchar, open_value double, close_value double, tradestatus varchar, highlimit varchar, lowlimit varchar)")
        conn.execute("create table stock_adjustment_factor(stock_code varchar, trade_date varchar, adj_factor double, source_version varchar, run_id varchar)")
        conn.execute("create table stock_limit_price_daily(trade_date varchar, stock_code varchar, up_limit double, down_limit double)")
        for day in range(1, 7):
            date = f"2026-06-{day:02d}"
            close = 9.0 if day == 5 else 10.0
            conn.execute("insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)", [date, "A", 10, close, "Trading", "0", "1" if day == 5 else "0"])
            conn.execute("insert into stock_adjustment_factor values (?, ?, ?, ?, ?)", ["A", date, 1, "test", "test"])
            conn.execute("insert into stock_limit_price_daily values (?, ?, ?, ?)", [date, "A", 11, 9])
        if batch:
            result = matched_baseline._load_control_execution_returns_for_date(conn, stock_codes=["A"], signal_date="2026-05-31")["A"]
        else:
            result = matched_baseline._control_execution_returns(conn, stock_code="A", signal_date="2026-05-31")
    # Day five cannot sell at 9. Day six can sell at 10, preserving gross wealth.
    expected = -(POLICY.buy_cost_rate + POLICY.sell_cost_rate + 2 * POLICY.slippage_rate)
    assert result["return_5d_net_adj"] == pytest.approx(expected)


def test_native_limit_flag_is_not_a_one_yuan_price():
    assert matched_baseline._is_limit_down({"lowlimit": "1", "highlimit": "0", "close_value": 9.0})
    assert matched_baseline._entry_block_reason({"highlimit": "0", "lowlimit": "1"}, entry_price=10) == ""


@pytest.mark.parametrize("available_at, expected_source", [("2026-06-01", "stk_limit"), ("2026-07-01", "observation_cast"), (None, "observation_cast")])
def test_pit_limit_price_requires_pre_evaluation_availability(available_at, expected_source):
    with duckdb.connect(":memory:") as conn:
        conn.execute("create table stock_limit_price_daily(stock_code varchar, trade_date varchar, up_limit double, down_limit double, source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar)")
        conn.execute("insert into stock_limit_price_daily values ('A', '2026-06-05', 11, 9, 'sv', 'vv', 'rv', 'run')")
        bars = {"A": [dict(trade_date="2026-06-05", open_value=10, close_value=9, highlimit=12, lowlimit=8)]}
        source_index = {("stock_limit_price_daily", "sv", "vv", "rv", "run"): available_at} if available_at else {}
        matched_baseline._attach_limit_prices(conn, bars, source_availability_index=source_index, evaluation_as_of_date="2026-06-06")
    bar = bars["A"][0]
    assert bar["limit_price_source"] == expected_source
    assert matched_baseline._is_limit_down(bar) is (expected_source == "stk_limit")


@pytest.mark.parametrize("open_price, executable", [(10.0, True), (11.0, False)])
def test_batch_control_universe_matches_single_stock_numeric_entry_limit(open_price, executable):
    with duckdb.connect(":memory:") as conn:
        conn.execute("create table choice_stock_daily_observation(trade_date varchar, stock_code varchar, open_value double, close_value double, tradestatus varchar, highlimit varchar, lowlimit varchar)")
        conn.execute("create table stock_limit_price_daily(trade_date varchar, stock_code varchar, up_limit double, down_limit double)")
        conn.execute("insert into choice_stock_daily_observation values ('2026-05-31', 'A', 10, 10, 'Trading', '0', '0')")
        conn.execute("insert into choice_stock_daily_observation values ('2026-06-01', 'A', ?, 11, 'Trading', '1', '0')", [open_price])
        conn.execute("insert into stock_limit_price_daily values ('2026-06-01', 'A', 11, 9)")
        batch = matched_baseline._load_control_universes_for_dates(conn, ["2026-05-31"])["2026-05-31"]
        single = matched_baseline._load_control_universe_for_date(conn, "2026-05-31")
    # A closing limit-up flag cannot block an opening purchase below the numeric cap.
    assert batch[0]["entry_executable"] is executable
    assert batch == single
    candidate = {"stock_code": "C", "signal_date": "2026-05-31", "run_id": "test"}
    assert len(matched_baseline.select_matched_controls(candidate, batch)) == int(executable)


@pytest.mark.parametrize(
    "decision_available_at, failure_reason",
    [
        ("2026-06-05", None),
        (None, "exit_decision_observation_source_availability_unproven"),
        ("2026-06-21", "exit_decision_observation_source_available_after_evaluation"),
    ],
)
def test_pit_receipt_contains_limit_source_that_delayed_the_exit(decision_available_at, failure_reason):
    with duckdb.connect(":memory:") as conn:
        conn.execute("create table choice_stock_daily_observation(trade_date varchar, stock_code varchar, open_value double, close_value double, tradestatus varchar, highlimit varchar, lowlimit varchar, source_version varchar, run_id varchar)")
        conn.execute("create table stock_adjustment_factor(stock_code varchar, trade_date varchar, adj_factor double, source_version varchar, run_id varchar)")
        conn.execute("create table stock_limit_price_daily(stock_code varchar, trade_date varchar, up_limit double, down_limit double, source_version varchar, run_id varchar)")
        for day in range(1, 21):
            date = f"2026-06-{day:02d}"
            conn.execute("insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?)", [date, "A", 10, 9 if day == 5 else 10, "Trading", "12", "8", "decision_observation" if day == 5 else "observation", "obs_run"])
            conn.execute("insert into stock_adjustment_factor values (?, ?, ?, ?, ?)", ["A", date, 1, "factor", "factor_run"])
        conn.execute("insert into stock_limit_price_daily values ('A', '2026-06-05', 11, 9, 'limit_day_5_only', 'limit_run_5_only')")
        index = {
            (matched_baseline.TABLE_OBS, "observation", None, None, "obs_run"): "2026-06-01",
            (matched_baseline.STOCK_ADJUSTMENT_FACTOR_TABLE, "factor", None, None, "factor_run"): "2026-06-01",
            (matched_baseline.TABLE_LIMIT_PRICE, "limit_day_5_only", None, None, "limit_run_5_only"): "2026-06-05",
        }
        if decision_available_at:
            index[(matched_baseline.TABLE_OBS, "decision_observation", None, None, "obs_run")] = decision_available_at
        proof = matched_baseline._control_execution_pit_proof(conn, stock_code="A", signal_date="2026-05-31", evaluation_as_of_date="2026-06-20", source_availability_index=index)
    assert proof["horizons"]["5d"]["trade_date"] == "2026-06-06"
    assert proof["horizons"]["5d"]["failure_reason"] == failure_reason
    assert proof["horizons"]["5d"]["usable"] is (failure_reason is None)
    if failure_reason is None:
        assert proof["horizons"]["5d"]["net_adj_return"] == pytest.approx(-0.0041)
    else:
        assert proof["horizons"]["5d"]["net_adj_return"] is None
    decisions = proof["source_evidence"]["limit_price"].get("exit_5d_decisions", [])
    assert [decision["trade_date"] for decision in decisions] == ["2026-06-05", "2026-06-06"]
    skipped = decisions[0]
    assert skipped["decision"] == "limit_down"
    assert skipped["close_value"] == 9
    assert skipped["down_limit"] == 9
    assert skipped["source"]["source_version"] == "limit_day_5_only"
    assert skipped["source"]["run_id"] == "limit_run_5_only"
    assert skipped["source"]["available_at"] == "2026-06-05"
    assert decisions[1]["decision"] == "sellable"
