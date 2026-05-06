from __future__ import annotations

import pandas as pd

from backend.app.core_finance.macro.equity_strategies import (
    compute_factors,
    generate_random_prices,
    mean_reversion_momentum_strategy,
    moving_average_strategy,
    multi_factor_selection,
)
from backend.app.core_finance.macro.toolkit import get_toolkit_script, run_toolkit_script


def test_equity_strategies_are_exported_from_macro_package() -> None:
    from backend.app.core_finance import macro

    assert macro.generate_random_prices is generate_random_prices
    assert macro.moving_average_strategy is moving_average_strategy
    assert macro.mean_reversion_momentum_strategy is mean_reversion_momentum_strategy
    assert macro.compute_factors is compute_factors
    assert macro.multi_factor_selection is multi_factor_selection


def test_generate_random_prices_is_seeded_and_named() -> None:
    first = generate_random_prices(num_stocks=2, num_days=5, seed=7)
    second = generate_random_prices(num_stocks=2, num_days=5, seed=7)

    assert first.shape == (5, 2)
    assert first.columns.tolist() == ["Stock0", "Stock1"]
    assert first.equals(second)


def test_moving_average_strategy_returns_clean_portfolio_path() -> None:
    prices = pd.DataFrame(
        {
            "winner": [10, 10, 10, 11, 12, 13, 14, 15],
            "laggard": [10, 10, 10, 9, 8, 7, 6, 5],
        },
        index=pd.date_range("2026-01-01", periods=8, freq="D"),
    )

    portfolio = moving_average_strategy(prices, short_window=2, long_window=3)

    assert portfolio.index.equals(prices.index)
    assert portfolio.isna().sum() == 0
    assert portfolio.iloc[0] == 1.0
    assert portfolio.iloc[-1] > 1.0


def test_mean_reversion_momentum_strategy_returns_clean_portfolio_path() -> None:
    prices = pd.DataFrame(
        {
            "rebound": [10, 10, 10, 10, 8, 9, 10, 11, 12, 13],
            "flat": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        },
        index=pd.date_range("2026-01-01", periods=10, freq="D"),
    )

    portfolio = mean_reversion_momentum_strategy(
        prices,
        short_window=2,
        long_window=3,
        z_threshold=0.5,
    )

    assert portfolio.index.equals(prices.index)
    assert portfolio.isna().sum() == 0
    assert portfolio.iloc[0] == 1.0
    assert portfolio.iloc[-1] >= 1.0


def test_multi_factor_selection_ranks_and_filters_industry() -> None:
    financials = pd.DataFrame(
        {
            "pe": [8.0, 18.0, 35.0, 12.0],
            "pb": [0.8, 2.2, 4.0, 1.5],
            "ps": [1.0, 3.0, 8.0, 2.0],
            "roe": [0.22, 0.12, 0.03, 0.18],
            "gross_margin": [0.45, 0.30, 0.08, 0.38],
            "three_month_return": [0.18, 0.08, -0.12, 0.12],
            "twelve_month_return": [0.42, 0.10, -0.30, 0.24],
            "volatility": [0.16, 0.25, 0.45, 0.20],
            "dividend_yield": [0.06, 0.03, 0.00, 0.04],
            "industry": ["technology", "consumer", "technology", "financial"],
        },
        index=["AAA", "BBB", "CCC", "DDD"],
    )

    factors = compute_factors(financials)
    selected = multi_factor_selection(financials, top_pct=0.5, industries_focus=["technology"])

    assert set(factors.columns) == {"value", "quality", "momentum", "low_vol", "dividend"}
    assert selected.index.tolist() == ["AAA"]
    assert selected["score"].iloc[0] == financials.assign(score=selected["score"]).loc["AAA", "score"]


def test_macro_toolkit_registers_equity_strategies_script(capsys) -> None:
    script = get_toolkit_script("equity_strategies")

    assert script.filename == "equity_strategies.py"
    assert script.group == "allocation"
    assert script.default_data_sources == ("choice", "tushare")

    result = run_toolkit_script("equity_strategies")
    output = capsys.readouterr().out

    assert result.path.name == "equity_strategies.py"
    assert "moving_average_final_value" in output
    assert "multi_factor_selected_count" in output
