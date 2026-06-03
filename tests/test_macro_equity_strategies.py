from __future__ import annotations

import pandas as pd
from backend.app.core_finance.macro import equity_strategies as equity_strategies_module
from backend.app.core_finance.macro.equity_strategies import (
    classify_low_crowding_market_regime,
    compute_factors,
    compute_low_crowding_scores,
    generate_random_prices,
    low_crowding_multifactor_selection,
    mean_reversion_momentum_strategy,
    moving_average_strategy,
    multi_factor_selection,
    _industry_neutralize_factors,
)
from backend.app.core_finance.macro.toolkit import get_toolkit_script, run_toolkit_script


def test_equity_strategies_are_exported_from_macro_package() -> None:
    from backend.app.core_finance import macro
    from backend.app.core_finance.macro import equity_strategies

    assert macro.generate_random_prices is equity_strategies.generate_random_prices
    assert macro.moving_average_strategy is equity_strategies.moving_average_strategy
    assert macro.mean_reversion_momentum_strategy is equity_strategies.mean_reversion_momentum_strategy
    assert macro.compute_factors is equity_strategies.compute_factors
    assert macro.multi_factor_selection is equity_strategies.multi_factor_selection
    assert macro.compute_low_crowding_scores is equity_strategies.compute_low_crowding_scores
    assert macro.classify_low_crowding_market_regime is equity_strategies.classify_low_crowding_market_regime
    assert macro.low_crowding_multifactor_selection is equity_strategies.low_crowding_multifactor_selection


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


def test_moving_average_strategy_does_not_capture_signal_day_return() -> None:
    # 金叉在第 4 天（row_no=4）才确认，且当天价格从 10 跳到 13。
    # 正确做法：信号当天收盘后才建仓，次日起才计收益，因此吃不到这 30% 跳涨。
    # 若存在前视偏差（用当天信号吃当天收益），净值会变成约 1.30。
    prices = pd.DataFrame(
        {"x": [10, 10, 10, 10, 13, 13, 13, 13]},
        index=pd.date_range("2026-01-01", periods=8, freq="D"),
    )

    portfolio = moving_average_strategy(prices, short_window=2, long_window=3)

    assert abs(float(portfolio.iloc[-1]) - 1.0) < 1e-9


def test_mean_reversion_momentum_strategy_does_not_capture_signal_day_return() -> None:
    # 第 3 天（row_no=3）触发入场（跌破短期均值但仍在长期均线上方），入场日是下跌日。
    # 第 4 天反弹 +22% 并触发止盈。正确做法应吃到第 4 天的反弹（净值≈1.22）。
    # 若存在前视偏差，入场日先吃到 -10%、止盈日又吃不到反弹，净值会低于 1.0。
    prices = pd.DataFrame(
        {"x": [10, 10, 20, 18, 22, 22, 22]},
        index=pd.date_range("2026-01-01", periods=7, freq="D"),
    )

    portfolio = mean_reversion_momentum_strategy(
        prices,
        short_window=2,
        long_window=3,
        z_threshold=0.5,
    )

    assert float(portfolio.iloc[-1]) > 1.1


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


def test_equity_strategy_portfolio_paths_are_stable_for_multistock_sample() -> None:
    prices = generate_random_prices(num_stocks=6, num_days=120, seed=20260602)

    moving_average = moving_average_strategy(prices)
    mean_reversion = mean_reversion_momentum_strategy(prices, z_threshold=0.8)

    assert round(float(moving_average.iloc[-1]), 12) == 1.111509676331
    assert round(float(moving_average.min()), 12) == 0.96551648441
    assert round(float(moving_average.max()), 12) == 1.138880452146
    assert round(float(mean_reversion.iloc[-1]), 12) == 1.01663166321
    assert round(float(mean_reversion.min()), 12) == 0.978534131903
    assert round(float(mean_reversion.max()), 12) == 1.076100455866


def test_industry_neutralize_factors_preserves_peer_group_semantics() -> None:
    factors = pd.DataFrame(
        {
            "value": [1.0, 3.0, 10.0, 2.0, 2.0],
            "quality": [2.0, 4.0, 20.0, 6.0, 6.0],
            "momentum": [3.0, 5.0, 30.0, 7.0, 7.0],
            "low_vol": [4.0, 6.0, 40.0, 8.0, 8.0],
            "dividend": [5.0, 7.0, 50.0, 9.0, 9.0],
        },
        index=["a", "b", "single", "flat_1", "flat_2"],
    )
    industries = pd.Series(
        ["tech", "tech", "solo", "flat", "flat"],
        index=factors.index,
    )

    neutralized = _industry_neutralize_factors(factors, industries)

    assert neutralized.loc["a"].to_dict() == {
        "value": -1.0,
        "quality": -1.0,
        "momentum": -1.0,
        "low_vol": -1.0,
        "dividend": -1.0,
    }
    assert neutralized.loc["b"].to_dict() == {
        "value": 1.0,
        "quality": 1.0,
        "momentum": 1.0,
        "low_vol": 1.0,
        "dividend": 1.0,
    }
    assert neutralized.loc["single"].to_dict() == factors.loc["single"].to_dict()
    assert neutralized.loc[["flat_1", "flat_2"]].eq(0.0).all().all()


def test_industry_neutralize_factors_uses_group_std_without_extra_squared_pass(monkeypatch) -> None:
    factors = pd.DataFrame(
        {
            "value": [1.0, 3.0, 10.0],
            "quality": [2.0, 4.0, 20.0],
            "momentum": [3.0, 5.0, 30.0],
            "low_vol": [4.0, 6.0, 40.0],
            "dividend": [5.0, 7.0, 50.0],
        },
        index=["a", "b", "single"],
    )
    industries = pd.Series(["tech", "tech", "solo"], index=factors.index)

    def fail_pow(*args: object, **kwargs: object) -> pd.DataFrame:
        raise AssertionError("industry neutralization should use grouped standard deviation directly")

    monkeypatch.setattr(pd.DataFrame, "pow", fail_pow)

    neutralized = _industry_neutralize_factors(factors, industries)

    assert neutralized.loc["a", "value"] == -1.0
    assert neutralized.loc["b", "value"] == 1.0
    assert neutralized.loc["single"].to_dict() == factors.loc["single"].to_dict()


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


def test_compute_factors_winsorizes_without_per_column_series_quantiles(monkeypatch) -> None:
    financials = pd.DataFrame(
        {
            "pe": [8.0, 12.0, 20.0, 120.0],
            "pb": [0.8, 1.1, 2.0, 8.0],
            "ps": [1.0, 1.4, 2.5, 12.0],
            "roe": [0.22, 0.18, 0.11, -0.03],
            "gross_margin": [0.45, 0.38, 0.30, 0.08],
            "three_month_return": [0.18, 0.08, -0.04, -0.20],
            "twelve_month_return": [0.42, 0.18, -0.12, -0.50],
            "volatility": [0.16, 0.20, 0.28, 0.60],
            "dividend_yield": [0.06, 0.04, 0.02, 0.00],
            "industry": ["technology", "consumer", "industrial", "energy"],
        },
        index=["AAA", "BBB", "CCC", "DDD"],
    )

    def fail_series_quantile(*args: object, **kwargs: object) -> float:
        raise AssertionError("compute_factors should winsorize the whole frame at once")

    monkeypatch.setattr(pd.Series, "quantile", fail_series_quantile)

    factors = compute_factors(financials)

    assert factors.index.tolist() == financials.index.tolist()
    assert factors.columns.tolist() == list(equity_strategies_module.FACTOR_COLUMNS)


def test_multi_factor_selection_caps_extreme_value_outlier() -> None:
    financials = pd.DataFrame(
        {
            "pe": [22.0, 18.0, 20.0, 24.0, 26.0],
            "pb": [1.8, 1.7, 1.9, 2.0, 1.6],
            "ps": [0.001, 2.0, 2.2, 2.4, 2.6],
            "roe": [0.01, 0.18, 0.20, 0.16, 0.19],
            "gross_margin": [0.02, 0.40, 0.42, 0.38, 0.41],
            "three_month_return": [-0.20, 0.08, 0.06, 0.07, 0.09],
            "twelve_month_return": [-0.15, 0.20, 0.18, 0.19, 0.21],
            "volatility": [0.25, 0.22, 0.24, 0.23, 0.21],
            "dividend_yield": [0.01, 0.03, 0.025, 0.028, 0.032],
            "industry": ["logistics", "technology", "technology", "consumer", "consumer"],
        },
        index=["deep_value_outlier", "tech_a", "tech_b", "consumer_a", "consumer_b"],
    )

    selected = multi_factor_selection(financials, top_pct=0.4, max_per_industry=2)

    assert "deep_value_outlier" not in selected.index.tolist()


def test_multi_factor_selection_limits_industry_concentration() -> None:
    rows = []
    index = []
    for i in range(6):
        rows.append(
            {
                "pe": 5.0 + i,
                "pb": 0.45 + i * 0.02,
                "ps": 0.01 + i * 0.001,
                "roe": 0.08,
                "gross_margin": 0.12,
                "three_month_return": -0.05,
                "twelve_month_return": -0.08,
                "volatility": 0.18,
                "dividend_yield": 0.04,
                "industry": "construction",
            }
        )
        index.append(f"construction_{i}")
    for i, industry in enumerate(["technology", "medicine", "consumer"]):
        rows.append(
            {
                "pe": 18.0,
                "pb": 1.8,
                "ps": 2.0,
                "roe": 0.22 - i * 0.01,
                "gross_margin": 0.42 - i * 0.02,
                "three_month_return": 0.12 - i * 0.01,
                "twelve_month_return": 0.28 - i * 0.02,
                "volatility": 0.24 + i * 0.01,
                "dividend_yield": 0.025,
                "industry": industry,
            }
        )
        index.append(industry)
    financials = pd.DataFrame(rows, index=index)

    selected = multi_factor_selection(financials, top_pct=1.0, max_per_industry=2)

    assert selected["industry"].value_counts().max() <= 2
    assert len(selected) == 5


def test_multi_factor_selection_keeps_singleton_industries_ranked_by_factors() -> None:
    financials = pd.DataFrame(
        {
            "pe": [8.0, 18.0, 35.0],
            "pb": [0.8, 2.2, 4.0],
            "ps": [1.0, 3.0, 8.0],
            "roe": [0.22, 0.12, 0.03],
            "gross_margin": [0.45, 0.30, 0.08],
            "three_month_return": [0.18, 0.08, -0.12],
            "twelve_month_return": [0.42, 0.10, -0.30],
            "volatility": [0.16, 0.25, 0.45],
            "dividend_yield": [0.06, 0.03, 0.00],
            "industry": ["technology", "consumer", "financial"],
        },
        index=["strong", "middle", "weak"],
    )

    selected = multi_factor_selection(financials, top_pct=1.0)

    assert selected["score"].nunique() > 1
    assert selected.index.tolist()[0] == "strong"


def test_low_crowding_scores_rank_less_crowded_names_higher() -> None:
    observations = _low_crowding_observations(
        {
            "quiet": [10, 10.1, 10.2, 10.25, 10.3, 10.35],
            "hot": [10, 10.8, 11.6, 12.8, 14.0, 15.5],
        },
        turn={"quiet": 1.0, "hot": 5.0},
        amount={"quiet": 100.0, "hot": 800.0},
        amplitude={"quiet": 1.0, "hot": 9.0},
    )

    scores = compute_low_crowding_scores(observations)

    assert scores.index.tolist()[0] == "quiet"
    assert scores.loc["quiet", "low_crowding_score"] > scores.loc["hot", "low_crowding_score"]


def test_low_crowding_scores_are_stable_for_multistock_sample() -> None:
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    rows: list[dict[str, object]] = []
    for stock_code in ["quiet", "hot", "fade", "spike"]:
        for row_no, trade_date in enumerate(dates):
            if stock_code == "quiet":
                close_value = 10.0 + row_no * 0.02
            elif stock_code == "hot":
                close_value = 10.0 * (1.018**row_no)
            elif stock_code == "fade":
                close_value = 12.0 - row_no * 0.03
            else:
                close_value = 9.5 + (0.01 * row_no if row_no < 24 else 1.2)
            rows.append(
                {
                    "trade_date": trade_date,
                    "stock_code": stock_code,
                    "close_value": round(close_value, 6),
                    "turn": 1.0 + (0.05 * row_no if stock_code in {"hot", "spike"} else 0.01 * row_no),
                    "amount": 100.0 + (20.0 * row_no if stock_code == "hot" else 5.0 * row_no if stock_code == "spike" else row_no),
                    "pctchange": 0.0,
                    "amplitude": 1.0 + (0.4 * row_no if stock_code == "hot" else 0.2 * row_no if stock_code == "spike" else 0.03 * row_no),
                    "lowlimit": 1.0,
                }
            )

    scores = compute_low_crowding_scores(pd.DataFrame(rows))

    assert scores.index.tolist() == ["fade", "quiet", "spike", "hot"]
    assert round(float(scores.loc["fade", "low_crowding_score"]), 12) == 4.752506014842
    assert round(float(scores.loc["quiet", "low_crowding_score"]), 12) == 4.312700430439
    assert round(float(scores.loc["spike", "low_crowding_score"]), 12) == -2.444403126732
    assert round(float(scores.loc["hot", "low_crowding_score"]), 12) == -6.620803318549
    assert round(float(scores.loc["hot", "low_crowding_rank_pct"]), 12) == 0.25


def test_low_crowding_regime_uses_observation_breadth_and_limit_down() -> None:
    prices = pd.DataFrame(
        {
            "a": [10.0] * 60 + [9.0],
            "b": [10.0] * 60 + [9.0],
            "c": [10.0] * 60 + [9.0],
            "d": [10.0] * 60 + [9.0],
            "e": [10.0] * 60 + [9.0],
        },
        index=pd.date_range("2026-01-01", periods=61, freq="D"),
    )
    observations = _low_crowding_observations(
        {column: prices[column].tolist() for column in prices.columns},
        pctchange={column: -10.0 for column in prices.columns},
        lowlimit={column: 9.0 for column in prices.columns},
    )

    regime = classify_low_crowding_market_regime(prices, observations)

    assert regime["regime"] == "crowded_quant"
    assert regime["limit_down_count"] == 5
    assert regime["breadth_score"] == -1.0


def test_low_crowding_regime_reuses_cleaned_observations(monkeypatch) -> None:
    prices = pd.DataFrame(
        {
            "a": [10.0] * 60 + [9.0],
            "b": [10.0] * 60 + [9.0],
            "c": [10.0] * 60 + [9.0],
            "d": [10.0] * 60 + [9.0],
            "e": [10.0] * 60 + [9.0],
        },
        index=pd.date_range("2026-01-01", periods=61, freq="D"),
    )
    observations = _low_crowding_observations(
        {column: prices[column].tolist() for column in prices.columns},
        pctchange={column: -10.0 for column in prices.columns},
        lowlimit={column: 9.0 for column in prices.columns},
    )
    clean_calls = 0
    original_clean = equity_strategies_module._clean_observation_frame

    def counted_clean(frame: pd.DataFrame) -> pd.DataFrame:
        nonlocal clean_calls
        clean_calls += 1
        return original_clean(frame)

    monkeypatch.setattr(equity_strategies_module, "_clean_observation_frame", counted_clean)

    regime = classify_low_crowding_market_regime(prices, observations)

    assert regime["regime"] == "crowded_quant"
    assert clean_calls == 1


def test_low_crowding_multifactor_selection_combines_factor_and_crowding_scores() -> None:
    financials = pd.DataFrame(
        {
            "pe": [8.0, 5.0, 20.0],
            "pb": [0.8, 0.5, 2.0],
            "ps": [1.0, 0.6, 3.0],
            "roe": [0.22, 0.30, 0.08],
            "gross_margin": [0.45, 0.55, 0.20],
            "three_month_return": [0.18, 0.50, 0.03],
            "twelve_month_return": [0.42, 0.90, 0.08],
            "volatility": [0.16, 0.40, 0.25],
            "dividend_yield": [0.06, 0.02, 0.03],
            "industry": ["technology", "technology", "consumer"],
        },
        index=["quiet", "hot", "middle"],
    )
    observations = _low_crowding_observations(
        {
            "quiet": [10, 10.1, 10.2, 10.3, 10.4, 10.5],
            "hot": [10, 11, 12, 13, 14, 16],
            "middle": [10, 10.2, 10.3, 10.4, 10.5, 10.6],
        },
        turn={"quiet": 1.0, "hot": 7.0, "middle": 2.0},
        amount={"quiet": 100.0, "hot": 900.0, "middle": 180.0},
        amplitude={"quiet": 1.0, "hot": 12.0, "middle": 2.0},
    )

    selected = low_crowding_multifactor_selection(
        financials,
        observations,
        top_pct=1 / 3,
        min_names_for_exclusion=3,
    )

    assert selected.index.tolist() == ["quiet"]
    assert "combined_score" in selected.columns
    assert int(selected["crowding_excluded_count"].iloc[0]) == 1


def test_low_crowding_multifactor_selection_reuses_precomputed_crowding_scores(monkeypatch) -> None:
    financials = pd.DataFrame(
        {
            "pe": [8.0, 5.0, 20.0],
            "pb": [0.8, 0.5, 2.0],
            "ps": [1.0, 0.6, 3.0],
            "roe": [0.22, 0.30, 0.08],
            "gross_margin": [0.45, 0.55, 0.20],
            "three_month_return": [0.18, 0.50, 0.03],
            "twelve_month_return": [0.42, 0.90, 0.08],
            "volatility": [0.16, 0.40, 0.25],
            "dividend_yield": [0.06, 0.02, 0.03],
            "industry": ["technology", "technology", "consumer"],
        },
        index=["quiet", "hot", "middle"],
    )
    observations = _low_crowding_observations(
        {
            "quiet": [10, 10.1, 10.2, 10.3, 10.4, 10.5],
            "hot": [10, 11, 12, 13, 14, 16],
            "middle": [10, 10.2, 10.3, 10.4, 10.5, 10.6],
        },
        turn={"quiet": 1.0, "hot": 7.0, "middle": 2.0},
        amount={"quiet": 100.0, "hot": 900.0, "middle": 180.0},
        amplitude={"quiet": 1.0, "hot": 12.0, "middle": 2.0},
    )
    expected = low_crowding_multifactor_selection(
        financials,
        observations,
        top_pct=1 / 3,
        min_names_for_exclusion=3,
    )
    crowding_scores = compute_low_crowding_scores(observations)

    def fail_compute_low_crowding_scores(_observations: pd.DataFrame) -> pd.DataFrame:
        raise AssertionError("precomputed crowding scores should be reused")

    monkeypatch.setattr(
        equity_strategies_module,
        "compute_low_crowding_scores",
        fail_compute_low_crowding_scores,
    )

    selected = low_crowding_multifactor_selection(
        financials,
        observations,
        top_pct=1 / 3,
        min_names_for_exclusion=3,
        crowding_scores=crowding_scores,
    )

    pd.testing.assert_frame_equal(selected, expected)


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


def _low_crowding_observations(
    close_by_stock: dict[str, list[float]],
    *,
    turn: dict[str, float] | None = None,
    amount: dict[str, float] | None = None,
    amplitude: dict[str, float] | None = None,
    pctchange: dict[str, float] | None = None,
    lowlimit: dict[str, float] | None = None,
) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(next(iter(close_by_stock.values()))), freq="D")
    rows: list[dict[str, object]] = []
    for stock_code, closes in close_by_stock.items():
        for row_no, close in enumerate(closes):
            previous = closes[row_no - 1] if row_no > 0 else close
            derived_pctchange = (close / previous - 1) * 100 if previous else 0.0
            rows.append(
                {
                    "trade_date": dates[row_no],
                    "stock_code": stock_code,
                    "close_value": close,
                    "amount": (amount or {}).get(stock_code, 100.0),
                    "pctchange": (pctchange or {}).get(stock_code, derived_pctchange),
                    "turn": (turn or {}).get(stock_code, 1.0),
                    "amplitude": (amplitude or {}).get(stock_code, 1.0),
                    "lowlimit": (lowlimit or {}).get(stock_code, close * 0.9),
                }
            )
    return pd.DataFrame(rows)
