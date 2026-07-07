from __future__ import annotations

from backend.app.core_finance.candidate_history_proxy_backtest import (
    CYCLE_PROXY_FORMULA_VERSION,
    PORTFOLIO_PROXY_FORMULA_VERSION,
    build_candidate_history_portfolio_series,
    build_candidate_history_portfolio_summary,
    build_cycle_proxy_nav_series,
    candidate_history_portfolio_price_field_stats,
    cycle_proxy_return_field_stats,
    cycle_proxy_row_return,
    max_drawdown_interval,
    max_gain_interval,
    proxy_cost_basis,
)


def test_formula_versions_are_stable_identifiers() -> None:
    assert CYCLE_PROXY_FORMULA_VERSION == "fv_livermore_cycle_proxy_backtest_adj_first_v2"
    assert PORTFOLIO_PROXY_FORMULA_VERSION == "fv_livermore_candidate_history_portfolio_adj_mtm_v2"


def test_cycle_proxy_row_return_prefers_adjusted_over_gross() -> None:
    assert cycle_proxy_row_return({"return_5d_adj": 0.10, "return_5d": 0.12}) == (0.10, "return_5d_adj")
    assert cycle_proxy_row_return({"return_5d_adj": None, "return_5d": 0.12}) == (0.12, "return_5d")
    assert cycle_proxy_row_return({"return_5d_adj": None, "return_5d": None}) is None
    assert cycle_proxy_row_return({"return_5d_adj": float("nan"), "return_5d": 0.12}) == (0.12, "return_5d")


def test_cycle_proxy_return_field_stats_counts_fallback_rows() -> None:
    stats = cycle_proxy_return_field_stats(
        [
            {"return_5d_adj": 0.10, "return_5d": 0.12},
            {"return_5d_adj": None, "return_5d": 0.12},
            {"return_5d_adj": None, "return_5d": None},
        ]
    )
    assert stats == {"return_rows_adjusted": 1, "return_rows_gross_fallback": 1}


def test_cycle_proxy_nav_series_nets_policy_costs_and_skips_overlapping_baskets() -> None:
    series = build_cycle_proxy_nav_series(
        [
            {
                "snapshot_as_of_date": "2026-05-01",
                "return_5d_adj": 0.10,
                "forward_trade_date_5d": "2026-05-08",
            },
            # overlaps the first basket's exit window, must be skipped
            {
                "snapshot_as_of_date": "2026-05-05",
                "return_5d": 0.50,
                "forward_trade_date_5d": "2026-05-12",
            },
        ]
    )
    assert len(series) == 1
    # 0.10 - (0.0008 + 0.0013 + 2 * 0.0010) = 0.0959
    assert series[0]["period_return"] == 0.0959
    assert series[0]["period_return_gross"] == 0.1
    assert series[0]["nav"] == 1.0959


def test_portfolio_series_marks_to_market_with_forward_fill_and_costs() -> None:
    nav_series, rebalance_log, stale_codes = build_candidate_history_portfolio_series(
        rebalances=[
            {
                "date": "2026-05-01",
                "market_state": "WARM",
                "items": [{"stock_code": "000001.SZ"}, {"stock_code": "000002.SZ"}],
            }
        ],
        close_rows=[
            {"trade_date": "2026-05-01", "stock_code": "000001.SZ", "close_value": 100.0},
            {"trade_date": "2026-05-01", "stock_code": "000002.SZ", "close_value": 100.0},
            # 000001.SZ never reprices: forward-filled and reported as stale
            {"trade_date": "2026-05-02", "stock_code": "000002.SZ", "close_value": 110.0},
        ],
    )
    # entry cost: buy 1.0 notional * (0.0008 + 0.0010) = 0.0018
    assert [row["nav"] for row in nav_series] == [0.9982, 1.04811]
    assert rebalance_log[0]["transaction_cost"] == 0.0018
    assert rebalance_log[0]["buy_turnover"] == 1.0
    assert stale_codes == ["000001.SZ"]


def test_portfolio_series_uses_adjusted_prices_through_ex_dividend_gap() -> None:
    rebalances = [
        {
            "date": "2026-05-01",
            "market_state": "WARM",
            "items": [{"stock_code": "000001.SZ"}],
        }
    ]
    raw_gap_rows = [
        {"trade_date": "2026-05-01", "stock_code": "000001.SZ", "close_value": 100.0},
        {"trade_date": "2026-05-02", "stock_code": "000001.SZ", "close_value": 50.0},
    ]
    raw_nav, _raw_rebalance_log, _raw_stale_codes = build_candidate_history_portfolio_series(
        rebalances=rebalances,
        close_rows=raw_gap_rows,
    )
    assert [row["nav"] for row in raw_nav] == [0.9982, 0.4991]

    adjusted_nav, _rebalance_log, _stale_codes = build_candidate_history_portfolio_series(
        rebalances=rebalances,
        close_rows=[
            {**raw_gap_rows[0], "adj_close_value": 100.0},
            {**raw_gap_rows[1], "adj_close_value": 100.0},
        ],
    )

    assert [row["nav"] for row in adjusted_nav] == [0.9982, 0.9982]
    assert adjusted_nav[-1]["nav"] > raw_nav[-1]["nav"]


def test_portfolio_price_field_stats_counts_raw_fallback_rows() -> None:
    stats = candidate_history_portfolio_price_field_stats(
        [
            {"adj_close_value": 100.0, "close_value": 50.0},
            {"adj_close_value": None, "close_value": 51.0},
            {"adj_close_value": float("nan"), "close_value": 52.0},
            {"adj_close_value": None, "close_value": None},
        ]
    )
    assert stats == {"price_rows_adjusted": 1, "price_rows_raw_fallback": 2}


def test_portfolio_summary_discloses_price_basis_and_fallback_rows() -> None:
    summary = build_candidate_history_portfolio_summary(
        [{"date": "2026-05-01", "nav": 0.9982}],
        rebalance_log=[
            {
                "date": "2026-05-01",
                "market_state": "WARM",
                "target_count": 1,
                "buy_turnover": 1.0,
                "sell_turnover": 0.0,
                "transaction_cost": 0.0018,
            }
        ],
        benchmark_rows=[],
        benchmark_series_id="CA.CSI300",
        price_field_stats={"price_rows_adjusted": 2, "price_rows_raw_fallback": 1},
    )

    assert summary is not None
    assert summary["price_field_used"] == "adj_close_value"
    assert summary["price_field_fallback"] == "close_value"
    assert summary["price_rows_adjusted"] == 2
    assert summary["price_rows_raw_fallback"] == 1


def test_interval_metrics_report_dates_and_signs() -> None:
    nav_series = [
        {"date": "2026-05-01", "nav": 1.1},
        {"date": "2026-05-02", "nav": 0.9},
        {"date": "2026-05-03", "nav": 1.2},
    ]
    gain = max_gain_interval(nav_series)
    assert gain["return"] == round(1.2 / 0.9 - 1, 6)
    assert gain["start_date"] == "2026-05-02"
    assert gain["end_date"] == "2026-05-03"
    drawdown = max_drawdown_interval(nav_series)
    assert drawdown["return"] == round(0.9 / 1.1 - 1, 6)
    assert drawdown["peak_date"] == "2026-05-01"
    assert drawdown["trough_date"] == "2026-05-02"


def test_proxy_cost_basis_matches_policy_constants() -> None:
    basis = proxy_cost_basis()
    assert basis["source"] == "core_finance.strategy_policy.POLICY"
    assert basis["round_trip_cost_rate"] == round(
        basis["buy_cost_rate"] + basis["sell_cost_rate"] + 2 * basis["slippage_rate"], 6
    )
