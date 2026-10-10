from __future__ import annotations

import pytest

from backend.app.core_finance.portfolio_backtest import run_portfolio_backtest, write_equity_curve_csv
from backend.app.core_finance.portfolio_paths import position_path_key
from backend.app.core_finance.vol_target_overlay import build_vol_target_index_comparison
from scripts.run_portfolio_backtest import _run_portfolio_result_set

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]

DATES = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-08"]
STATES = [{"trade_date": day, "market_state": "HOT"} for day in DATES]


def _row(code: str, entry_index: int) -> dict[str, object]:
    return {
        "stock_code": code,
        "signal_date": DATES[entry_index - 1] if entry_index else "2026-05-29",
        "entry_date": DATES[entry_index],
        "entry_price": 10.0,
        "entry_executable": True,
        "candidate_rank": 1,
        "market_state": "HOT",
        "exit_date_5d": DATES[-1],
        "return_5d_net_adj": 0.0,
        "exit_date_20d": DATES[-1],
        "return_20d_net_adj": 0.0,
    }


def _paths(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    return {
        position_path_key(row["stock_code"], row["entry_date"]): [
            {"trade_date": day, "adj_open": 10.0, "adj_close": 10.0}
            for day in DATES if day >= str(row["entry_date"])
        ]
        for row in rows
    }


@pytest.mark.parametrize("sizing", ["equal_weight", "risk_budget"])
@pytest.mark.parametrize("mark_kind", ["adjusted_open", "raw_open", "previous_close", "missing_day"])
def test_open_orders_ignore_same_day_close_and_keep_close_valuation(sizing: str, mark_kind: str) -> None:
    rows = [_row("A", 0), _row("B", 1)]
    results = []
    for close in (10.0, 11.0):
        paths = _paths(rows)
        bars = paths[position_path_key("A", DATES[0])]
        bars[1]["adj_close"] = close
        if mark_kind == "raw_open":
            for bar in bars:
                bar.update(path_price_basis="raw_fallback_missing_adj_factor", open=10.0, close=bar["adj_close"])
                bar["adj_open"] = 90.0
        elif mark_kind == "previous_close":
            bars[1]["adj_open"] = None
            bars[1]["tradestatus"] = "停牌"
        elif mark_kind == "missing_day":
            del bars[1]
        results.append(run_portfolio_backtest(
            rows, STATES, mode="path", price_paths=paths, initial_capital=100.0,
            max_positions=4, exposure_by_date={"2026-05-29": 1.0, **{day: 1.0 for day in DATES}},
            sizing=sizing, risk_per_trade=0.025, fallback_stop_distance_pct=0.1, single_name_cap=0.25,
        ))
    assert [next(t["amount"] for t in r.trades if t["action"] == "buy" and t["stock_code"] == "B")
            for r in results] == [25.0, 25.0]
    if mark_kind != "missing_day":
        assert [r.equity_curve[1]["net_value"] for r in results] == [100.0, 102.5]
    assert results[0].metrics["opening_previous_close_fallback_position_days"] == (
        1 if mark_kind in {"previous_close", "missing_day"} else 0
    )


def test_open_equity_uses_today_open_when_it_differs_from_previous_close() -> None:
    rows = [_row("A", 0), _row("B", 1)]
    paths = _paths(rows)
    paths[position_path_key("A", DATES[0])][1].update(adj_open=12.0, adj_close=90.0)
    result = run_portfolio_backtest(rows, STATES, mode="path", price_paths=paths,
                                    initial_capital=100.0, max_positions=4,
                                    exposure_by_market_state={"HOT": 1.0})
    assert next(t["amount"] for t in result.trades if t["action"] == "buy" and t["stock_code"] == "B") == 26.25


def test_missing_open_and_prior_close_skips_new_orders_without_future_close() -> None:
    rows = [_row("A", 0), _row("B", 1)]
    paths = _paths(rows)
    paths[position_path_key("A", DATES[0])][0]["adj_close"] = None
    paths[position_path_key("A", DATES[0])][1].update(adj_open=None, adj_close=90.0)
    result = run_portfolio_backtest(rows, STATES, mode="path", price_paths=paths,
                                    initial_capital=100.0, max_positions=4,
                                    exposure_by_market_state={"HOT": 1.0})
    assert [t["stock_code"] for t in result.trades if t["action"] == "buy"] == ["A"]
    assert result.metrics["opening_missing_price_position_days"] == 1
    assert result.skip_counts["missing_opening_valuation"] == 1


def test_path_open_price_gain_cannot_supply_cash_for_another_order() -> None:
    rows = [_row("A", 0), _row("B", 1)]
    paths = _paths(rows)
    paths[position_path_key("A", DATES[0])][1].update(adj_open=100.0, adj_close=100.0)
    result = run_portfolio_backtest(rows, STATES, mode="path", price_paths=paths,
                                    initial_capital=100.0, max_positions=2,
                                    exposure_by_market_state={"HOT": 1.0})
    assert [t["stock_code"] for t in result.trades if t["action"] == "buy"] == ["A"]
    assert result.skip_counts["insufficient_cash"] == 1


@pytest.mark.parametrize("mode", ["horizon", "path"])
def test_script_overlay_keeps_effective_dates_for_reduction_and_recovery(mode: str) -> None:
    rows = [_row("A", 0), _row("B", 2), _row("C", 5)]
    gate = [{"date": day, "exposure": 1.0 if i in (0, 4, 5) else 0.0} for i, day in enumerate(DATES)]
    # A non-trading-day decision must not introduce a calendar-day shift.
    gate.append({"date": "2026-06-06", "exposure": 0.0})
    overlay = build_vol_target_index_comparison(
        [{"date": day, "daily_return": 0.0} for day in DATES],
        exposure_rows=gate, exposure_by_market_state={"HOT": 1.0, "OFF": 0.0}, target_vol=0.15, window=2,
    )
    results = _run_portfolio_result_set(
        rows, STATES, exposure_rows=gate, initial_capital=100.0, max_positions=4,
        mode=mode, price_paths=_paths(rows),
        vol_target_exposure_by_target={0.15: overlay["vol_target_exposure_by_date"]},
    )
    result = results["fixed_20d_vol_target_0p15"]
    assert [t["stock_code"] for t in result.trades if t["action"] == "buy"] == ["A", "C"]
    assert result.metrics["exposure_date_basis"] == "effective_date_with_prior_decision_fallback"
    assert result.metrics["vol_target_warning"] is None
    assert overlay["exposure_date_basis"] == "effective_date"
    assert result.metrics["formal_use_allowed"] is False
    assert result.equity_curve[2]["exposure"] == 0.0
    assert result.equity_curve[2]["entry_exposure"] == 0.0
    assert result.equity_curve[2]["entry_exposure_date"] == DATES[2]


@pytest.mark.parametrize("mode", ["horizon", "path"])
def test_missing_effective_date_falls_back_to_prior_gate_decision(mode: str) -> None:
    rows = [_row("A", 0), _row("B", 2)]
    result = run_portfolio_backtest(
        rows, STATES, mode=mode, price_paths=_paths(rows), initial_capital=100.0, max_positions=4,
        exposure_by_date={DATES[0]: 1.0, DATES[1]: 0.0, DATES[2]: 1.0},
        effective_exposure_by_date={DATES[0]: 0.5, DATES[3]: 1.0},
    )
    buys = [t for t in result.trades if t["action"] == "buy"]
    assert [(t["stock_code"], t["amount"]) for t in buys] == [("A", 12.5)]
    assert result.equity_curve[2]["entry_exposure_basis"] == "prior_decision_fallback"


@pytest.mark.parametrize("mode", ["horizon", "path"])
def test_raw_gate_still_has_exactly_one_trading_day_lag(mode: str) -> None:
    rows = [_row("A", 0), _row("B", 1), _row("C", 2)]
    result = run_portfolio_backtest(
        rows, STATES, mode=mode, price_paths=_paths(rows), initial_capital=100.0, max_positions=4,
        exposure_by_date={DATES[0]: 1.0, DATES[1]: 0.0, DATES[2]: 1.0},
    )
    assert [t["stock_code"] for t in result.trades if t["action"] == "buy"] == ["A", "B"]


@pytest.mark.parametrize("mode", ["horizon", "path"])
def test_first_day_effective_zero_overrides_raw_gate_without_prior_value(mode: str) -> None:
    rows = [_row("A", 0)]
    result = run_portfolio_backtest(
        rows, STATES, mode=mode, price_paths=_paths(rows), exposure_by_date={DATES[0]: 1.0},
        effective_exposure_by_date={DATES[0]: 0.0},
    )
    assert result.trades == []
    assert result.equity_curve[0]["entry_exposure"] == 0.0


def test_equity_csv_retains_effective_date_and_missing_price_disclosure(tmp_path) -> None:
    import csv

    rows = [_row("A", 0)]
    result = run_portfolio_backtest(rows, STATES, effective_exposure_by_date={DATES[0]: 0.0})
    output = tmp_path / "equity.csv"
    write_equity_curve_csv(output, result.equity_curve)
    with output.open(encoding="utf-8", newline="") as handle:
        first = next(csv.DictReader(handle))
    assert first["entry_exposure_basis"] == "effective_date"
    assert first["entry_exposure_date"] == DATES[0]
    assert first["entry_exposure"] == "0.0"
    assert first["opening_missing_price_positions"] == "0"
