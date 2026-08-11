from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pytest

from backend.app.core_finance.portfolio_backtest import (
    build_benchmark_comparison,
    filter_rows_by_liquidity_floor,
    liquidity_floor_summary,
    run_portfolio_backtest,
    summarize_equity_curve,
)
from backend.app.core_finance.portfolio_paths import position_path_key


EXPOSURE = {
    "OFF": (0.0,),
    "WARM": (0.5,),
    "HOT": (1.0,),
}


def _execution_row(
    *,
    signal_date: str,
    stock_code: str,
    rank: int,
    market_state: str,
    entry_date: str,
    exit_date_5d: str,
    return_5d_net_adj: float,
    entry_executable: bool = True,
    daily_amount: float | None = 300_000_000.0,
    ema10: float | None = None,
    signal_close: float | None = None,
) -> dict[str, object]:
    return {
        "signal_date": signal_date,
        "stock_code": stock_code,
        "stock_name": f"Stock {stock_code}",
        "signal_kind": "stock_candidate",
        "candidate_rank": rank,
        "market_state": market_state,
        "entry_date": entry_date,
        "entry_price": 10.0,
        "signal_close": signal_close,
        "entry_executable": entry_executable,
        "entry_block_reason": None if entry_executable else "entry_limit_up_or_one_line",
        "ema10": ema10,
        "exit_date_5d": exit_date_5d,
        "return_5d_net_adj": return_5d_net_adj,
        "daily_amount": daily_amount,
    }


def test_portfolio_backtest_applies_exposure_slots_and_entry_blocks() -> None:
    market_states = [
        {"trade_date": "2026-06-01", "market_state": "WARM"},
        {"trade_date": "2026-06-02", "market_state": "WARM"},
        {"trade_date": "2026-06-03", "market_state": "HOT"},
        {"trade_date": "2026-06-04", "market_state": "HOT"},
    ]
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.10,
            ),
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000002.SZ",
                rank=2,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=-0.20,
            ),
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000003.SZ",
                rank=3,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.50,
                entry_executable=False,
            ),
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000004.SZ",
                rank=4,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.50,
            ),
            _execution_row(
                signal_date="2026-06-02",
                stock_code="000005.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-03",
                exit_date_5d="2026-06-04",
                return_5d_net_adj=0.20,
            ),
        ],
        market_states,
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=2,
        exposure_by_market_state=EXPOSURE,
    )

    curve_by_date = {str(row["date"]): row for row in result.equity_curve}
    assert curve_by_date["2026-06-01"]["net_value"] == pytest.approx(100.0)
    assert curve_by_date["2026-06-01"]["buy_notional"] == pytest.approx(50.0)
    assert curve_by_date["2026-06-01"]["max_single_name_weight"] == pytest.approx(0.25)
    assert curve_by_date["2026-06-03"]["net_value"] == pytest.approx(97.5)
    # 敞口 T+1 生效（审计 MAC-01）：06-03 建仓使用 06-02 收盘的 WARM(0.5) 决策，
    # 而不是 06-03 当日的 HOT(1.0)：97.5 × 0.5 / 2 = 24.375。
    assert curve_by_date["2026-06-03"]["buy_notional"] == pytest.approx(24.375)
    assert curve_by_date["2026-06-04"]["net_value"] == pytest.approx(102.375)
    assert result.metrics["cumulative_return"] == pytest.approx(0.02375)
    assert result.skip_counts["entry_blocked"] == 1
    assert result.skip_counts["no_slot"] == 1
    assert [row["amount"] for row in result.trades if row["action"] == "buy"] == [
        pytest.approx(25.0),
        pytest.approx(25.0),
        pytest.approx(24.375),
    ]


def test_portfolio_backtest_prefers_daily_exposure_over_state_max() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.10,
            )
        ],
        [{"trade_date": "2026-06-01", "market_state": "WARM"}],
        exposure_rows=[
            {"trade_date": "2026-05-29", "exposure": 0.25},
            {"trade_date": "2026-06-01", "exposure": 0.25},
            {"trade_date": "2026-06-03", "exposure": 0.25},
        ],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.25, 0.5, 0.75)},
    )

    buy_trades = [row for row in result.trades if row["action"] == "buy"]
    assert buy_trades[0]["amount"] == pytest.approx(5.0)
    curve_by_date = {str(row["date"]): row for row in result.equity_curve}
    assert curve_by_date["2026-06-01"]["exposure"] == pytest.approx(0.25)
    assert result.metrics["exposure_basis"] == "per_date_actual"
    assert result.metrics["exposure_fallback_day_ratio"] == pytest.approx(0.0)


def test_portfolio_backtest_reports_daily_exposure_fallback_ratio() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-02",
                return_5d_net_adj=0.10,
            )
        ],
        [
            {"trade_date": "2026-06-01", "market_state": "WARM"},
            {"trade_date": "2026-06-02", "market_state": "WARM"},
        ],
        exposure_by_date={"2026-06-01": 0.25},
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.25, 0.5, 0.75)},
    )

    assert result.metrics["exposure_basis"] == "per_date_actual"
    assert result.metrics["exposure_actual_days"] == 1
    assert result.metrics["exposure_fallback_days"] == 1
    assert result.metrics["exposure_fallback_day_ratio"] == pytest.approx(0.5)


def test_portfolio_backtest_excludes_signal_only_dates_from_exposure_metrics() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.10,
            )
        ],
        [
            {"trade_date": "2026-05-29", "market_state": "WARM"},
            {"trade_date": "2026-06-01", "market_state": "WARM"},
            {"trade_date": "2026-06-03", "market_state": "WARM"},
        ],
        exposure_rows=[
            {"trade_date": "2026-06-01", "exposure": 0.25},
            {"trade_date": "2026-06-03", "exposure": 0.25},
        ],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.25, 0.5, 0.75)},
    )

    assert [row["date"] for row in result.equity_curve] == ["2026-06-01", "2026-06-03"]
    assert result.metrics["sample_days"] == 1
    assert result.metrics["exposure_fallback_day_ratio"] == pytest.approx(0.0)


def test_portfolio_backtest_entry_exposure_uses_prior_day_decision() -> None:
    """建仓敞口 T+1 生效（审计 MAC-01）：当日收盘才产生的敞口决策不得用于当日建仓。

    与 gate_timing_csi300 基准和 vol_target_overlay 的既有 T+1 规则
    （2026-07-19 审计 宏观 H-1）同一口径；序列首日退回当日决策。
    """
    rows = [
        _execution_row(
            signal_date="2026-05-29",
            stock_code="000001.SZ",
            rank=1,
            market_state="HOT",
            entry_date="2026-06-01",
            exit_date_5d="2026-06-05",
            return_5d_net_adj=0.10,
        ),
        _execution_row(
            signal_date="2026-06-01",
            stock_code="000002.SZ",
            rank=1,
            market_state="HOT",
            entry_date="2026-06-02",
            exit_date_5d="2026-06-05",
            return_5d_net_adj=0.10,
        ),
    ]
    market_states = [
        {"trade_date": "2026-06-01", "market_state": "HOT"},
        {"trade_date": "2026-06-02", "market_state": "HOT"},
        {"trade_date": "2026-06-05", "market_state": "HOT"},
    ]
    result = run_portfolio_backtest(
        rows,
        market_states,
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state=EXPOSURE,
        # T 日收盘决定的敞口：06-01 决定 1.0，06-02 决定 0.0。
        exposure_by_date={"2026-06-01": 1.0, "2026-06-02": 0.0},
    )

    buys = [trade for trade in result.trades if trade["action"] == "buy"]
    buy_codes_by_date = {(trade["date"], trade["stock_code"]) for trade in buys}
    # 首日无 T-1 决策，退回当日决策（1.0）→ 可建仓。
    assert ("2026-06-01", "000001.SZ") in buy_codes_by_date
    # 06-02 建仓使用 06-01 收盘的决策（1.0），而不是 06-02 当日的 0.0。
    assert ("2026-06-02", "000002.SZ") in buy_codes_by_date


def test_summarize_equity_curve_annualizes_by_calendar_span_not_row_count() -> None:
    """稀疏 equity 曲线按日历跨度年化（审计 MAC-02），不得按记录条数套 252。"""
    curve = [
        {"date": "2026-01-02", "net_value": 100.0, "open_positions": 0},
        {"date": "2026-06-30", "net_value": 105.0, "open_positions": 1},
        {"date": "2026-12-28", "net_value": 110.0, "open_positions": 0},
    ]
    trades = [{"action": "buy", "amount": 100.0}]

    metrics = summarize_equity_curve(
        curve,
        initial_capital=100.0,
        max_positions=5,
        trades=trades,
    )

    span_days = (date(2026, 12, 28) - date(2026, 1, 2)).days
    assert metrics["sample_days"] == 2
    assert metrics["cagr"] == pytest.approx(1.10 ** (365 / span_days) - 1.0, abs=1e-6)
    assert metrics["annual_turnover"] == pytest.approx(1.0 * 365 / span_days, abs=1e-6)
    # 旧口径 (1.10)**(252/2)-1 是天文数字；日历口径应接近 10%。
    assert metrics["cagr"] < 0.2


def test_summarize_equity_curve_returns_none_when_span_cannot_annualize() -> None:
    """同日/单点曲线无法年化：返回 None 而不是编造年化数字（审计 MAC-02）。"""
    curve = [
        {"date": "2026-06-01", "net_value": 100.0, "open_positions": 0},
        {"date": "2026-06-01", "net_value": 101.0, "open_positions": 0},
    ]
    metrics = summarize_equity_curve(
        curve,
        initial_capital=100.0,
        max_positions=5,
        trades=[],
    )

    assert metrics["cagr"] is None
    assert metrics["annual_turnover"] is None
    assert metrics["daily_sharpe"] is None


def test_portfolio_path_mode_fixed_horizon_matches_horizon_mode_daily_values() -> None:
    rows = [
        _execution_row(
            signal_date="2026-05-29",
            stock_code="000001.SZ",
            rank=1,
            market_state="WARM",
            entry_date="2026-06-01",
            exit_date_5d="2026-06-03",
            return_5d_net_adj=-0.0041,
        )
    ]
    market_states = [
        {"trade_date": "2026-06-01", "market_state": "WARM"},
        {"trade_date": "2026-06-02", "market_state": "WARM"},
        {"trade_date": "2026-06-03", "market_state": "WARM"},
    ]
    price_paths = {
        position_path_key("000001.SZ", "2026-06-01"): [
            {"trade_date": "2026-06-01", "adj_open": 10.0, "adj_close": 10.0},
            {"trade_date": "2026-06-02", "adj_open": 10.0, "adj_close": 10.0},
            {"trade_date": "2026-06-03", "adj_open": 10.0, "adj_close": 10.0},
        ]
    }

    horizon = run_portfolio_backtest(
        rows,
        market_states,
        exposure_rows=[{"trade_date": day["trade_date"], "exposure": 0.5} for day in market_states],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )
    path = run_portfolio_backtest(
        rows,
        market_states,
        mode="path",
        price_paths=price_paths,
        exposure_rows=[{"trade_date": day["trade_date"], "exposure": 0.5} for day in market_states],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )

    assert [row["net_value"] for row in path.equity_curve] == [
        row["net_value"] for row in horizon.equity_curve
    ]
    assert path.metrics["cumulative_return"] == horizon.metrics["cumulative_return"]


def test_portfolio_path_mode_marks_open_positions_to_market_daily() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=-0.0041,
            )
        ],
        [
            {"trade_date": "2026-06-01", "market_state": "WARM"},
            {"trade_date": "2026-06-02", "market_state": "WARM"},
            {"trade_date": "2026-06-03", "market_state": "WARM"},
        ],
        mode="path",
        price_paths={
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_open": 10.0, "adj_close": 10.0},
                {"trade_date": "2026-06-02", "adj_open": 11.0, "adj_close": 11.0},
                {"trade_date": "2026-06-03", "adj_open": 10.0, "adj_close": 10.0},
            ]
        },
        exposure_rows=[
            {"trade_date": "2026-06-01", "exposure": 0.5},
            {"trade_date": "2026-06-02", "exposure": 0.5},
            {"trade_date": "2026-06-03", "exposure": 0.5},
        ],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )

    curve_by_date = {row["date"]: row for row in result.equity_curve}
    assert curve_by_date["2026-06-02"]["net_value"] == pytest.approx(105.0)
    assert curve_by_date["2026-06-03"]["net_value"] == pytest.approx(99.795)


def test_portfolio_path_mode_extends_timeline_for_delayed_limit_down_exit() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
            )
        ],
        [
            {"trade_date": "2026-06-01", "market_state": "WARM"},
            {"trade_date": "2026-06-02", "market_state": "WARM"},
            {"trade_date": "2026-06-03", "market_state": "WARM"},
            {"trade_date": "2026-06-04", "market_state": "WARM"},
            {"trade_date": "2026-06-05", "market_state": "WARM"},
        ],
        mode="path",
        price_paths={
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_open": 10.0, "adj_close": 10.0},
                {"trade_date": "2026-06-02", "adj_open": 10.0, "adj_close": 10.0},
                {
                    "trade_date": "2026-06-03",
                    "adj_open": 10.0,
                    "adj_close": 9.0,
                    "lowlimit": 9.0,
                    "limit_down": True,
                },
                {
                    "trade_date": "2026-06-04",
                    "adj_open": 9.0,
                    "adj_close": 8.1,
                    "lowlimit": 8.1,
                    "limit_down": True,
                },
                {"trade_date": "2026-06-05", "adj_open": 8.2, "adj_close": 8.5, "lowlimit": 7.3},
            ]
        },
        exposure_rows=[{"trade_date": f"2026-06-0{day}", "exposure": 0.5} for day in range(1, 6)],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )

    assert [row["date"] for row in result.equity_curve] == [
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-06-05",
    ]
    assert [row for row in result.trades if row["action"] == "sell"][0]["date"] == "2026-06-05"


def test_portfolio_path_mode_does_not_fund_open_with_same_day_close_exit() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
            ),
            _execution_row(
                signal_date="2026-06-02",
                stock_code="000002.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-03",
                exit_date_5d="2026-06-05",
                return_5d_net_adj=0.0,
            ),
        ],
        [
            {"trade_date": "2026-06-01", "market_state": "HOT"},
            {"trade_date": "2026-06-02", "market_state": "HOT"},
            {"trade_date": "2026-06-03", "market_state": "HOT"},
            {"trade_date": "2026-06-05", "market_state": "HOT"},
        ],
        mode="path",
        price_paths={
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_open": 10.0, "adj_close": 10.0},
                {"trade_date": "2026-06-02", "adj_open": 10.0, "adj_close": 10.0},
                {"trade_date": "2026-06-03", "adj_open": 10.0, "adj_close": 10.0},
            ],
            position_path_key("000002.SZ", "2026-06-03"): [
                {"trade_date": "2026-06-03", "adj_open": 10.0, "adj_close": 10.0},
                {"trade_date": "2026-06-04", "adj_open": 10.0, "adj_close": 10.0},
                {"trade_date": "2026-06-05", "adj_open": 10.0, "adj_close": 10.0},
            ],
        },
        exposure_rows=[
            {"trade_date": "2026-06-01", "exposure": 1.0},
            {"trade_date": "2026-06-02", "exposure": 1.0},
            {"trade_date": "2026-06-03", "exposure": 1.0},
            {"trade_date": "2026-06-04", "exposure": 1.0},
            {"trade_date": "2026-06-05", "exposure": 1.0},
        ],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )

    buys = [row for row in result.trades if row["action"] == "buy"]
    assert [row["stock_code"] for row in buys] == ["000001.SZ"]
    assert result.skip_counts["no_slot"] == 1


def test_portfolio_horizon_mode_exits_same_day_entry_date_equals_exit_date() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-01",
                return_5d_net_adj=0.05,
            )
        ],
        [{"trade_date": "2026-06-01", "market_state": "HOT"}],
        exposure_by_date={"2026-06-01": 1.0},
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )

    sells = [row for row in result.trades if row["action"] == "sell"]
    assert sells and sells[0]["date"] == "2026-06-01"
    curve_by_date = {row["date"]: row for row in result.equity_curve}
    assert curve_by_date["2026-06-01"]["open_positions"] == 0
    assert curve_by_date["2026-06-01"]["net_value"] == pytest.approx(105.0)


def test_portfolio_risk_budget_sizing_weights_by_stop_distance() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                ema10=9.6,
            ),
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000002.SZ",
                rank=2,
                market_state="HOT",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                ema10=9.2,
            ),
        ],
        [{"trade_date": "2026-06-02", "market_state": "HOT"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state=EXPOSURE,
        sizing="risk_budget",
        risk_per_trade=0.01,
        single_name_cap=0.25,
    )

    buy_trades = [row for row in result.trades if row["action"] == "buy"]
    assert [row["amount"] for row in buy_trades] == [pytest.approx(25.0), pytest.approx(12.5)]
    assert [row["stop_distance_pct"] for row in buy_trades] == [pytest.approx(0.04), pytest.approx(0.08)]
    assert result.metrics["sizing"] == "risk_budget"
    assert result.metrics["risk_per_trade"] == pytest.approx(0.01)


def test_portfolio_risk_budget_exposure_cap_skips_later_ranks() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code=f"00000{rank}.SZ",
                rank=rank,
                market_state="WARM",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                ema10=9.6,
            )
            for rank in (1, 2, 3)
        ],
        [{"trade_date": "2026-06-02", "market_state": "WARM"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.5,)},
        sizing="risk_budget",
        risk_per_trade=0.01,
        single_name_cap=0.25,
    )

    assert [row["stock_code"] for row in result.trades if row["action"] == "buy"] == [
        "000001.SZ",
        "000002.SZ",
    ]
    assert result.skip_counts["exposure_cap_skip"] == 1


def test_portfolio_risk_budget_partial_fill_uses_remaining_exposure_budget() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                ema10=9.6,
            ),
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000002.SZ",
                rank=2,
                market_state="WARM",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                ema10=9.6,
            ),
        ],
        [{"trade_date": "2026-06-02", "market_state": "WARM"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.3,)},
        sizing="risk_budget",
        risk_per_trade=0.01,
        single_name_cap=0.25,
    )

    buy_trades = [row for row in result.trades if row["action"] == "buy"]
    assert [row["amount"] for row in buy_trades] == [pytest.approx(25.0), pytest.approx(5.0)]
    assert buy_trades[1]["exposure_cap_clipped"] is True
    assert result.skip_counts["exposure_cap_skip"] == 0
    assert result.metrics["exposure_cap_clipped"] == 1


def test_portfolio_risk_budget_hit_rate_uses_filled_position_budget() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000001.SZ",
                rank=1,
                market_state="WARM",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=-0.07,
                ema10=9.6,
            )
        ],
        [
            {"trade_date": "2026-06-02", "market_state": "WARM"},
            {"trade_date": "2026-06-03", "market_state": "WARM"},
        ],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.1,)},
        sizing="risk_budget",
        risk_per_trade=0.01,
        single_name_cap=0.25,
    )

    buy_trade = [row for row in result.trades if row["action"] == "buy"][0]
    sell_trade = [row for row in result.trades if row["action"] == "sell"][0]
    assert buy_trade["amount"] == pytest.approx(10.0)
    assert buy_trade["risk_budget_planned"] == pytest.approx(0.004)
    assert sell_trade["risk_budget_loss"] == pytest.approx(0.007)
    assert sell_trade["risk_budget_hit"] is False
    assert result.metrics["risk_budget_hit_rate"] == pytest.approx(0.0)


def test_portfolio_risk_budget_fallback_stop_distance_is_counted() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                ema10=None,
            )
        ],
        [{"trade_date": "2026-06-02", "market_state": "HOT"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state=EXPOSURE,
        sizing="risk_budget",
        risk_per_trade=0.01,
        single_name_cap=0.25,
    )

    buy_trades = [row for row in result.trades if row["action"] == "buy"]
    assert buy_trades[0]["amount"] == pytest.approx(12.5)
    assert buy_trades[0]["stop_ref_fallback"] is True
    assert result.metrics["stop_ref_fallback"] == 1


def test_portfolio_max_entry_premium_blocks_without_consuming_slot() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                signal_close=10.0,
            )
            | {"entry_price": 10.6},
            _execution_row(
                signal_date="2026-06-01",
                stock_code="000002.SZ",
                rank=2,
                market_state="HOT",
                entry_date="2026-06-02",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
                signal_close=10.0,
            )
            | {"entry_price": 10.1},
        ],
        [{"trade_date": "2026-06-02", "market_state": "HOT"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
        max_entry_premium=0.03,
    )

    buy_trades = [row for row in result.trades if row["action"] == "buy"]
    assert [row["stock_code"] for row in buy_trades] == ["000002.SZ"]
    assert buy_trades[0]["entry_premium"] == pytest.approx(0.01)
    assert result.skip_counts["entry_premium_blocked"] == 1
    assert result.skip_counts["no_slot"] == 0
    assert result.metrics["entry_premium_blocked"] == 1
    assert result.metrics["max_entry_premium"] == pytest.approx(0.03)


def test_portfolio_vol_target_emits_warning_when_not_wired_to_exposure() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
            )
        ],
        [{"trade_date": "2026-06-01", "market_state": "HOT"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
        vol_target=0.15,
    )

    assert result.metrics["vol_target"] == pytest.approx(0.15)
    assert result.metrics["vol_target_warning"] is not None
    assert "exposure_by_date" in result.metrics["vol_target_warning"]


def test_portfolio_vol_target_none_emits_no_warning() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-03",
                return_5d_net_adj=0.0,
            )
        ],
        [{"trade_date": "2026-06-01", "market_state": "HOT"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
    )

    assert result.metrics["vol_target"] is None
    assert result.metrics["vol_target_warning"] is None


def test_portfolio_probe_pyramid_confirms_and_adds_next_open() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-05",
                return_5d_net_adj=0.0,
            )
            | {"signal_high": 10.5}
        ],
        [{"trade_date": f"2026-06-0{day}", "market_state": "HOT"} for day in range(1, 6)],
        mode="path",
        price_paths={
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_open": 10.0, "adj_close": 10.2},
                {"trade_date": "2026-06-02", "adj_open": 10.2, "adj_close": 10.6},
                {"trade_date": "2026-06-03", "adj_open": 10.7, "adj_close": 10.8},
                {"trade_date": "2026-06-04", "adj_open": 10.8, "adj_close": 10.9},
                {"trade_date": "2026-06-05", "adj_open": 10.9, "adj_close": 11.0},
            ]
        },
        exposure_rows=[{"trade_date": f"2026-06-0{day}", "exposure": 1.0} for day in range(1, 6)],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
        entry_style="probe_pyramid",
        probe_fraction=0.5,
        confirm_days=3,
    )

    buys = [row for row in result.trades if row["action"] == "buy"]
    assert [(row["date"], row["entry_stage"], row["amount"]) for row in buys] == [
        ("2026-06-01", "probe", pytest.approx(50.0)),
        ("2026-06-03", "pyramid_add", pytest.approx(50.0)),
    ]
    assert result.metrics["probe_confirm_rate"] == pytest.approx(1.0)
    assert result.metrics["probe_failed_exit"] == 0
    assert result.metrics["probe_confirmed_avg_return"] is not None
    assert result.metrics["probe_confirmed_win_rate"] == pytest.approx(1.0)


def test_portfolio_probe_pyramid_exits_unconfirmed_probe_next_open() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row(
                signal_date="2026-05-29",
                stock_code="000001.SZ",
                rank=1,
                market_state="HOT",
                entry_date="2026-06-01",
                exit_date_5d="2026-06-05",
                return_5d_net_adj=0.0,
            )
            | {"signal_high": 11.5}
        ],
        [{"trade_date": f"2026-06-0{day}", "market_state": "HOT"} for day in range(1, 6)],
        mode="path",
        price_paths={
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_open": 10.0, "adj_close": 10.2},
                {"trade_date": "2026-06-02", "adj_open": 10.2, "adj_close": 10.4},
                {"trade_date": "2026-06-03", "adj_open": 10.4, "adj_close": 10.6},
                {"trade_date": "2026-06-04", "adj_open": 9.6, "adj_close": 9.7},
                {"trade_date": "2026-06-05", "adj_open": 9.7, "adj_close": 9.8},
            ]
        },
        exposure_rows=[{"trade_date": f"2026-06-0{day}", "exposure": 1.0} for day in range(1, 6)],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=1,
        exposure_by_market_state=EXPOSURE,
        entry_style="probe_pyramid",
        probe_fraction=0.5,
        confirm_days=3,
    )

    buys = [row for row in result.trades if row["action"] == "buy"]
    sells = [row for row in result.trades if row["action"] == "sell"]
    assert [(row["date"], row["entry_stage"], row["amount"]) for row in buys] == [
        ("2026-06-01", "probe", pytest.approx(50.0))
    ]
    assert sells[0]["date"] == "2026-06-04"
    assert sells[0]["exit_stage"] == "probe_failed_exit"
    assert result.metrics["probe_failed_exit"] == 1
    assert result.metrics["probe_confirm_rate"] == pytest.approx(0.0)
    assert result.metrics["probe_failed_avg_return"] < 0
    assert result.metrics["probe_failed_avg_loss"] > 0


def test_portfolio_probe_pyramid_requires_path_mode() -> None:
    with pytest.raises(ValueError, match="probe_pyramid requires path mode"):
        run_portfolio_backtest(
            [
                _execution_row(
                    signal_date="2026-06-01",
                    stock_code="000001.SZ",
                    rank=1,
                    market_state="HOT",
                    entry_date="2026-06-02",
                    exit_date_5d="2026-06-03",
                    return_5d_net_adj=0.0,
                )
            ],
            [{"trade_date": "2026-06-02", "market_state": "HOT"}],
            variant="fixed_5d",
            exposure_by_market_state=EXPOSURE,
            entry_style="probe_pyramid",
        )


def test_portfolio_hold_progress_matrix_groups_k_day_progress_by_t20_return() -> None:
    from scripts.run_portfolio_backtest import _build_hold_progress_matrix

    payload = _build_hold_progress_matrix(
        [
            {
                "stock_code": "000001.SZ",
                "entry_date": "2026-06-01",
                "entry_price": 10.0,
                "return_20d_net_adj": None,
            }
        ],
        {
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_close": 9.6},
                {"trade_date": "2026-06-02", "adj_close": 10.1},
                {"trade_date": "2026-06-03", "adj_close": 10.3},
                {"trade_date": "2026-06-04", "adj_close": 10.4},
                {"trade_date": "2026-06-05", "adj_close": 10.6},
                {"trade_date": "2026-06-08", "adj_close": 10.7},
                {"trade_date": "2026-06-09", "adj_close": 10.8},
                {"trade_date": "2026-06-10", "adj_close": 10.9},
                {"trade_date": "2026-06-11", "adj_close": 11.0},
                {"trade_date": "2026-06-12", "adj_close": 11.1},
                {"trade_date": "2026-06-15", "adj_close": 11.2},
                {"trade_date": "2026-06-16", "adj_close": 11.3},
                {"trade_date": "2026-06-17", "adj_close": 11.4},
                {"trade_date": "2026-06-18", "adj_close": 11.5},
                {"trade_date": "2026-06-19", "adj_close": 11.6},
                {"trade_date": "2026-06-22", "adj_close": 11.7},
                {"trade_date": "2026-06-23", "adj_close": 11.8},
                {"trade_date": "2026-06-24", "adj_close": 11.9},
                {"trade_date": "2026-06-25", "adj_close": 12.0},
                {"trade_date": "2026-06-26", "adj_close": 12.1},
            ]
        },
    )

    assert payload["status"] == "ready"
    rows = {(row["day"], row["progress_bucket"]): row for row in payload["rows"]}
    assert rows[(1, "lt_-3pct")]["sample_count"] == 1
    # gross 0.21 netted multiplicatively: (1 + 0.21) * (1 - 0.0041) - 1 = 0.205039
    assert rows[(1, "lt_-3pct")]["avg_t20_net_return"] == pytest.approx(0.205039)
    assert rows[(8, "gt_+5pct")]["win_rate"] == pytest.approx(1.0)


def test_portfolio_hold_progress_matrix_uses_adjusted_entry_denominator() -> None:
    from scripts.run_portfolio_backtest import _build_hold_progress_matrix

    payload = _build_hold_progress_matrix(
        [
            {
                "stock_code": "000001.SZ",
                "entry_date": "2026-06-01",
                "entry_price": 10.0,
                "return_20d_net_adj": 0.10,
            }
        ],
        {
            position_path_key("000001.SZ", "2026-06-01"): [
                {"trade_date": "2026-06-01", "adj_open": 20.0, "adj_close": 19.0},
            ]
        },
    )

    rows = {(row["day"], row["progress_bucket"]): row for row in payload["rows"]}
    assert rows[(1, "lt_-3pct")]["sample_count"] == 1


def test_portfolio_hold_progress_matrix_uses_raw_fallback_price_basis() -> None:
    from scripts.run_portfolio_backtest import _build_hold_progress_matrix

    payload = _build_hold_progress_matrix(
        [
            {
                "stock_code": "000001.SZ",
                "entry_date": "2026-06-01",
                "entry_price": 10.0,
                "return_20d_net_adj": 0.10,
            }
        ],
        {
            position_path_key("000001.SZ", "2026-06-01"): [
                {
                    "trade_date": "2026-06-01",
                    "path_price_basis": "raw_fallback_missing_adj_factor",
                    "open": 10.0,
                    "close": 10.4,
                    "adj_open": 200.0,
                    "adj_close": 190.0,
                },
            ]
        },
    )

    rows = {(row["day"], row["progress_bucket"]): row for row in payload["rows"]}
    assert rows[(1, "+2pct_to_+5pct")]["sample_count"] == 1
    assert (1, "lt_-3pct") not in rows


def test_portfolio_script_reports_adjustment_factor_fill_and_raw_fallback_counts() -> None:
    from scripts.run_portfolio_backtest import (
        _price_path_forward_filled_adj_factor_rows,
        _price_path_missing_adj_factor_rows,
        _price_path_raw_fallback_paths,
    )

    paths = {
        "filled": [
            {
                "adj_factor_missing": True,
                "adj_factor_forward_filled": True,
                "path_price_basis": "adjusted",
            }
        ],
        "raw": [
            {
                "adj_factor_missing": True,
                "adj_factor_forward_filled": False,
                "path_price_basis": "raw_fallback_missing_adj_factor",
            }
        ],
    }

    assert _price_path_missing_adj_factor_rows(paths) == 2
    assert _price_path_forward_filled_adj_factor_rows(paths) == 1
    assert _price_path_raw_fallback_paths(paths) == 1


def test_portfolio_benchmark_comparison_quantifies_gate_timing_increment() -> None:
    market_states = [
        {"trade_date": "2026-06-01", "market_state": "WARM"},
        {"trade_date": "2026-06-02", "market_state": "WARM"},
        {"trade_date": "2026-06-03", "market_state": "HOT"},
        {"trade_date": "2026-06-04", "market_state": "HOT"},
    ]
    strategy_curve = [
        {"date": "2026-06-01", "net_value": 100.0},
        {"date": "2026-06-02", "net_value": 100.0},
        {"date": "2026-06-03", "net_value": 97.5},
        {"date": "2026-06-04", "net_value": 107.25},
    ]
    comparison = build_benchmark_comparison(
        strategy_curve,
        [
            {"trade_date": "2026-06-01", "value": 100.0},
            {"trade_date": "2026-06-02", "value": 110.0},
            {"trade_date": "2026-06-03", "value": 99.0},
            {"trade_date": "2026-06-04", "value": 108.9},
        ],
        market_states,
        exposure_by_market_state=EXPOSURE,
        initial_capital=100.0,
    )

    assert comparison["status"] == "ready"
    metrics = comparison["metrics"]
    assert metrics["csi300_buy_hold"]["cumulative_return"] == pytest.approx(0.089)
    # 敞口 T+1 生效（前视偏差修复，2026-07-19 审计 宏观 H-1）：
    # 6/2 收益按 6/1 决策 WARM(0.5)，6/3 按 6/2 决策 WARM(0.5)，6/4 按 6/3 决策 HOT(1.0)
    # -> 1.05 * 0.95 * 1.10 - 1 = 0.09725
    assert metrics["gate_timing_csi300"]["cumulative_return"] == pytest.approx(0.09725)
    assert metrics["stock_selection_increment"]["cumulative_return"] == pytest.approx(-0.02475)


def test_benchmark_comparison_prefers_daily_exposure() -> None:
    comparison = build_benchmark_comparison(
        [
            {"date": "2026-06-01", "net_value": 100.0},
            {"date": "2026-06-02", "net_value": 100.0},
        ],
        [
            {"trade_date": "2026-06-01", "value": 100.0},
            {"trade_date": "2026-06-02", "value": 110.0},
        ],
        # 敞口 T+1 生效：6/2 的收益使用 6/1 收盘的决策。
        [{"trade_date": "2026-06-01", "market_state": "WARM"}],
        exposure_rows=[{"trade_date": "2026-06-01", "exposure": 0.25}],
        exposure_by_market_state={"WARM": (0.25, 0.5, 0.75)},
        initial_capital=100.0,
    )

    metrics = comparison["metrics"]
    assert metrics["gate_timing_csi300"]["cumulative_return"] == pytest.approx(0.025)


def test_benchmark_comparison_gate_exposure_applies_with_one_day_lag() -> None:
    """T 日收盘决定的敞口不得吃 T 日收益（2026-07-19 审计 宏观 H-1 回归锁定）。"""
    comparison = build_benchmark_comparison(
        [
            {"date": "2026-06-01", "net_value": 100.0},
            {"date": "2026-06-03", "net_value": 100.0},
        ],
        [
            {"trade_date": "2026-06-01", "return": 0.0},
            {"trade_date": "2026-06-02", "return": 0.10},
            {"trade_date": "2026-06-03", "return": 0.10},
        ],
        [],
        # 6/2 收盘才决定满仓：6/2 的 10% 不得吃到，6/3 的 10% 才吃到。
        exposure_rows=[
            {"trade_date": "2026-06-01", "exposure": 0.0},
            {"trade_date": "2026-06-02", "exposure": 1.0},
            {"trade_date": "2026-06-03", "exposure": 1.0},
        ],
        exposure_by_market_state=EXPOSURE,
        initial_capital=100.0,
    )

    metrics = comparison["metrics"]
    assert metrics["gate_timing_csi300"]["cumulative_return"] == pytest.approx(0.10)


def test_benchmark_comparison_compounds_intermediate_days_for_sparse_strategy_curve() -> None:
    strategy_curve = [
        {"date": "2026-06-01", "net_value": 100.0},
        {"date": "2026-06-05", "net_value": 100.0},
    ]
    benchmark_rows = [
        {"trade_date": "2026-06-01", "return": 0.0},
        {"trade_date": "2026-06-02", "return": 0.01},
        {"trade_date": "2026-06-03", "return": 0.01},
        {"trade_date": "2026-06-04", "return": 0.01},
        {"trade_date": "2026-06-05", "return": 0.01},
    ]

    comparison = build_benchmark_comparison(
        strategy_curve,
        benchmark_rows,
        [],
        exposure_by_market_state=EXPOSURE,
        initial_capital=100.0,
    )

    assert comparison["status"] == "ready"
    curve_by_date = {row["date"]: row for row in comparison["curves"]}
    assert curve_by_date["2026-06-01"]["csi300_buy_hold"] == pytest.approx(100.0)
    # 100 * 1.01^4 compounded over the benchmark's own 06-02..06-05 trading
    # days, not just the single 06-05 return the old code used to apply.
    assert curve_by_date["2026-06-05"]["csi300_buy_hold"] == pytest.approx(104.060401)


def test_liquidity_floor_keeps_missing_amounts_and_removes_known_fails() -> None:
    rows = [
        {"stock_code": "000001.SZ", "daily_amount": 300_000_000.0},
        {"stock_code": "000002.SZ", "daily_amount": 120_000_000.0},
        {"stock_code": "000003.SZ", "daily_amount": None},
    ]

    assert liquidity_floor_summary(rows, min_daily_amount=200_000_000.0) == {
        "min_daily_amount": 200_000_000.0,
        "total_rows": 3,
        "known_pass_rows": 1,
        "known_fail_rows": 1,
        "missing_amount_rows": 1,
    }
    assert [row["stock_code"] for row in filter_rows_by_liquidity_floor(rows)] == [
        "000001.SZ",
        "000003.SZ",
    ]


def test_portfolio_script_loads_daily_exposure_from_candidate_evidence(tmp_path) -> None:
    from scripts.run_portfolio_backtest import _load_daily_exposure_rows

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?)",
            [
                ("2026-06-01", '{"market_state":"WARM","market_gate_exposure":0.25}'),
                ("2026-06-01", '{"market_state":"WARM","market_gate_exposure":0.25}'),
                ("2026-06-02", '{"market_state":"WARM"}'),
            ],
        )
        rows, issues = _load_daily_exposure_rows(
            conn,
            tables={"livermore_candidate_history"},
            start_date="2026-06-01",
            end_date="2026-06-02",
        )
    finally:
        conn.close()

    assert rows == [
        {
            "trade_date": "2026-06-01",
            "exposure": 0.25,
            "market_state": "WARM",
            "source": "persisted:livermore_candidate_history",
        }
    ]
    assert any("missing=1" in issue for issue in issues)


def test_portfolio_script_reconstructs_daily_exposure_from_gate_inputs(tmp_path) -> None:
    from scripts.run_portfolio_backtest import _load_daily_exposure_rows

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_livermore_gate_supplement_daily (
              trade_date varchar,
              breadth_5d double,
              limit_up_quality_ok boolean,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(65)]
        macro_rows = [
            (
                "CA.CSI300",
                "CSI300",
                trade_date,
                3000.0 + index * 10,
                "daily",
                "index",
                "sv",
                "vv",
                "rv",
                "ok",
                "run",
            )
            for index, trade_date in enumerate(dates, start=1)
        ]
        conn.executemany("insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", macro_rows)
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values (?, 0.2, false, 'sv', 'vv', 'rv', 'run')",
            [dates[-1]],
        )
        rows, issues = _load_daily_exposure_rows(
            conn,
            tables={"fact_choice_macro_daily", "fact_livermore_gate_supplement_daily"},
            start_date=dates[-1],
            end_date=dates[-1],
        )
    finally:
        conn.close()

    assert rows == [{"trade_date": dates[-1], "exposure": 0.75, "market_state": "HOT", "source": "replayed"}]
    assert any("replayed=1" in issue for issue in issues)


def test_portfolio_script_loads_adjusted_signal_high_for_probe_variants(tmp_path) -> None:
    from scripts.run_portfolio_backtest import _load_execution_rows

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              entry_block_reason varchar,
              exit_date_5d varchar,
              return_5d_net_adj double,
              exit_date_20d varchar,
              return_20d_net_adj double
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              high_value double
            )
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              trade_date varchar,
              stock_code varchar,
              adj_factor double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-01', '000001.SZ', 'Stock 1', 'stock_candidate', 1, 'HOT',
             '2026-06-02', 10.0, true, null, '2026-06-03', 0.01, '2026-06-25', 0.02)
            """
        )
        conn.execute("insert into choice_stock_daily_observation values ('2026-06-01', '000001.SZ', 300000000, 10.5)")
        conn.execute("insert into stock_adjustment_factor values ('2026-06-01', '000001.SZ', 2.0)")
        rows, issues = _load_execution_rows(
            conn,
            tables={"livermore_candidate_execution_history", "choice_stock_daily_observation", "stock_adjustment_factor"},
            signal_kind="stock_candidate",
            start_date=None,
            end_date=None,
        )
    finally:
        conn.close()

    assert rows[0]["daily_amount"] == pytest.approx(300_000_000.0)
    assert rows[0]["signal_high"] == pytest.approx(21.0)
    assert not any("high_value unavailable" in issue for issue in issues)


def test_portfolio_script_loads_history_ema10_without_signal_kind_column(tmp_path) -> None:
    from scripts.run_portfolio_backtest import _load_execution_rows

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              signal_close double,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              entry_block_reason varchar,
              exit_date_5d varchar,
              return_5d_net_adj double,
              exit_date_20d varchar,
              return_20d_net_adj double
            )
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              ema10 double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-01', '000001.SZ', 'Stock 1', 'stock_candidate', 1, 'HOT',
             10.0, '2026-06-02', 10.2, true, null, '2026-06-03', 0.01, '2026-06-25', 0.02)
            """
        )
        conn.execute("insert into livermore_candidate_history values ('2026-06-01', '000001.SZ', 9.8)")
        rows, issues = _load_execution_rows(
            conn,
            tables={"livermore_candidate_execution_history", "livermore_candidate_history"},
            signal_kind="stock_candidate",
            start_date=None,
            end_date=None,
        )
    finally:
        conn.close()

    assert rows[0]["ema10"] == pytest.approx(9.8)
    assert not any("signal_kind" in issue for issue in issues)


def test_portfolio_script_nulls_signal_high_when_signal_adjustment_factor_missing(tmp_path) -> None:
    from scripts.run_portfolio_backtest import _load_execution_rows

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              entry_block_reason varchar,
              exit_date_5d varchar,
              return_5d_net_adj double,
              exit_date_20d varchar,
              return_20d_net_adj double
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              high_value double,
              close_value double
            )
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              trade_date varchar,
              stock_code varchar,
              adj_factor double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-01', '000001.SZ', 'Stock 1', 'stock_candidate', 1, 'HOT',
             '2026-06-02', 10.0, true, null, '2026-06-03', 0.01, '2026-06-25', 0.02)
            """
        )
        conn.execute(
            "insert into choice_stock_daily_observation values ('2026-06-01', '000001.SZ', 300000000, 10.5, 10.0)"
        )
        rows, issues = _load_execution_rows(
            conn,
            tables={
                "livermore_candidate_execution_history",
                "choice_stock_daily_observation",
                "stock_adjustment_factor",
            },
            signal_kind="stock_candidate",
            start_date=None,
            end_date=None,
        )
    finally:
        conn.close()

    assert rows[0]["signal_high"] is None
    assert rows[0]["signal_close"] is None
    assert any("lacked signal-day adjustment factors" in issue for issue in issues)


def test_portfolio_script_path_mode_includes_probe_pyramid_variants() -> None:
    from scripts.run_portfolio_backtest import _run_portfolio_result_set

    start = date(2026, 6, 1)
    path_rows = [
        {
            "trade_date": (start + timedelta(days=index)).isoformat(),
            "adj_open": 10.0 + index * 0.1,
            "adj_close": 10.2 + index * 0.1,
        }
        for index in range(24)
    ]
    path_rows[1]["adj_close"] = 10.8
    execution_rows = [
        _execution_row(
            signal_date="2026-05-29",
            stock_code="000001.SZ",
            rank=1,
            market_state="HOT",
            entry_date="2026-06-01",
            exit_date_5d="2026-06-05",
            return_5d_net_adj=0.01,
        )
        | {
            "signal_high": 10.5,
            "exit_date_20d": "2026-06-20",
            "return_20d_net_adj": 0.02,
        }
    ]

    results = _run_portfolio_result_set(
        execution_rows,
        [{"trade_date": row["trade_date"], "market_state": "HOT"} for row in path_rows],
        exposure_rows=[{"trade_date": row["trade_date"], "exposure": 1.0} for row in path_rows],
        initial_capital=100.0,
        max_positions=1,
        mode="path",
        price_paths={position_path_key("000001.SZ", "2026-06-01"): path_rows},
        vol_target_exposure_by_target={
            0.15: {str(row["trade_date"]): 0.5 for row in path_rows},
        },
    )

    assert "fixed_20d_probe_pyramid_cd_3" in results
    assert "fixed_20d_probe_pyramid_cd_5" in results
    assert "fixed_20d_max_entry_premium_0p02" in results
    assert "fixed_20d_max_entry_premium_0p03" in results
    assert "fixed_20d_max_entry_premium_none" in results
    assert "fixed_20d_vol_target_0p15" in results
    assert results["fixed_20d_probe_pyramid_cd_3"].metrics["probe_confirm_rate"] == pytest.approx(1.0)
    assert results["fixed_20d_vol_target_0p15"].metrics["vol_target"] == pytest.approx(0.15)


def test_portfolio_script_reports_state_fallback_when_daily_exposure_unavailable(tmp_path) -> None:
    from scripts.run_portfolio_backtest import run_portfolio_backtest_from_duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              entry_block_reason varchar,
              exit_date_5d varchar,
              return_5d_net_adj double,
              exit_date_20d varchar,
              return_20d_net_adj double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-01', '000001.SZ', 'Stock 1', 'stock_candidate', 1, 'WARM',
             '2026-06-02', 10.0, true, null, '2026-06-03', 0.01, '2026-06-04', 0.02)
            """
        )
    finally:
        conn.close()

    payload = run_portfolio_backtest_from_duckdb(
        db_path=str(db_path),
        report_path=tmp_path / "report.md",
        output_dir=tmp_path,
    )

    assert payload["status"] == "ready"
    assert payload["daily_exposure_rows"] == 0
    assert payload["exposure_basis"] == "state_max_fallback"
    assert "fixed_20d_risk_budget_rpt_0p005" in payload["results"]
    assert "fixed_20d_risk_budget_rpt_0p010" in payload["results"]


def test_portfolio_script_loads_legacy_net_return_columns(tmp_path) -> None:
    from scripts.run_portfolio_backtest import run_portfolio_backtest_from_duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              entry_block_reason varchar,
              exit_date_5d varchar,
              return_5d_net double,
              exit_date_20d varchar,
              return_20d_net double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-01', '000001.SZ', 'Stock 1', 'stock_candidate', 1, 'WARM',
             '2026-06-02', 10.0, true, null, '2026-06-03', 0.01, '2026-06-04', 0.02)
            """
        )
    finally:
        conn.close()

    payload = run_portfolio_backtest_from_duckdb(
        db_path=str(db_path),
        report_path=tmp_path / "report.md",
        output_dir=tmp_path,
    )

    assert payload["status"] == "ready"
    assert payload["results"]["fixed_5d"]["metrics"]["cumulative_return"] is not None
