from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

FACTOR_COLUMNS: tuple[str, ...] = ("value", "quality", "momentum", "low_vol", "dividend")
REQUIRED_FACTOR_INPUTS: tuple[str, ...] = (
    "pe",
    "pb",
    "ps",
    "roe",
    "gross_margin",
    "three_month_return",
    "twelve_month_return",
    "volatility",
    "dividend_yield",
)
DEFAULT_FACTOR_WEIGHTS: Mapping[str, float] = {
    "value": 0.30,
    "quality": 0.25,
    "momentum": 0.15,
    "low_vol": 0.15,
    "dividend": 0.15,
}
DEFAULT_WINSOR_LIMITS: tuple[float, float] = (0.05, 0.95)
LOW_CROWDING_REGIME_TARGET_POSITIONS: Mapping[str, float] = {
    "liquidity_shock": 0.25,
    "crowded_quant": 0.35,
    "fast_down": 0.35,
    "range": 0.60,
    "weak_up": 0.70,
    "strong_up": 0.85,
}


def generate_random_prices(
    num_stocks: int = 5,
    num_days: int = 756,
    seed: int = 42,
    *,
    end_date: str | pd.Timestamp = "2026-05-06",
) -> pd.DataFrame:
    if num_stocks <= 0:
        raise ValueError("num_stocks must be positive")
    if num_days <= 0:
        raise ValueError("num_days must be positive")

    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=0.0005, scale=0.02, size=(num_days, num_stocks))
    prices = 100 * np.exp(np.cumsum(returns, axis=0))
    dates = pd.date_range(end=pd.Timestamp(end_date), periods=num_days, freq="D")
    return pd.DataFrame(prices, index=dates, columns=[f"Stock{i}" for i in range(num_stocks)])


def moving_average_strategy(
    prices: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
    max_drawdown: float = 0.15,
    stop_loss: float = 0.10,
) -> pd.Series:
    price_frame = _clean_price_frame(prices)
    _validate_windows(short_window, long_window)
    if max_drawdown < 0:
        raise ValueError("max_drawdown must be non-negative")
    if stop_loss < 0:
        raise ValueError("stop_loss must be non-negative")

    short_ma = price_frame.rolling(window=short_window).mean().to_numpy(dtype="float64")
    long_ma = price_frame.rolling(window=long_window).mean().to_numpy(dtype="float64")
    price_values = price_frame.to_numpy(dtype="float64")
    portfolio_value = np.ones(len(price_frame), dtype="float64")
    current_position = np.zeros(len(price_frame.columns), dtype="float64")
    entry_prices = np.full(len(price_frame.columns), np.nan, dtype="float64")
    cash = 1.0
    peak_value = 1.0

    for row_no in range(1, len(price_frame)):
        # 先用昨日收盘确定的持仓结算今日收益（避免用当日信号吃当日收益的前视偏差）。
        previous_position = current_position
        daily_returns = price_values[row_no] / price_values[row_no - 1] - 1.0
        cash *= 1 + _weighted_return_array(previous_position, daily_returns)
        portfolio_value[row_no] = cash

        if row_no < long_window:
            continue

        # 今日收盘信号只决定今日收盘后的持仓，影响的是次日及以后的收益。
        current_position = previous_position.copy()
        crossed_up = (short_ma[row_no - 1] <= long_ma[row_no - 1]) & (
            short_ma[row_no] > long_ma[row_no]
        )
        crossed_down = (
            (short_ma[row_no - 1] >= long_ma[row_no - 1])
            & (short_ma[row_no] < long_ma[row_no])
            & ~crossed_up
        )
        if crossed_up.any():
            current_position[crossed_up] = 1.0
            entry_prices[crossed_up] = price_values[row_no, crossed_up]
        if crossed_down.any():
            current_position[crossed_down] = 0.0
            entry_prices[crossed_down] = np.nan

        held = (current_position > 0) & ~np.isnan(entry_prices) & ~crossed_up
        stop_mask = np.zeros_like(held, dtype=bool)
        stop_mask[held] = price_values[row_no, held] / entry_prices[held] - 1.0 <= -stop_loss
        if stop_mask.any():
            current_position[stop_mask] = 0.0
            entry_prices[stop_mask] = np.nan

        peak_value = max(peak_value, cash)
        if peak_value > 0 and (peak_value - cash) / peak_value > max_drawdown:
            current_position.fill(0.0)
            entry_prices.fill(np.nan)

    return pd.Series(portfolio_value, index=price_frame.index, dtype="float64")


def mean_reversion_momentum_strategy(
    prices: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
    z_threshold: float = 1.5,
    max_drawdown: float = 0.12,
    stop_loss: float = 0.08,
    take_profit: float = 0.20,
) -> pd.Series:
    price_frame = _clean_price_frame(prices)
    _validate_windows(short_window, long_window)
    if z_threshold <= 0:
        raise ValueError("z_threshold must be positive")
    if max_drawdown < 0 or stop_loss < 0 or take_profit < 0:
        raise ValueError("risk thresholds must be non-negative")

    rolling_mean = price_frame.rolling(short_window).mean()
    rolling_std = price_frame.rolling(short_window).std(ddof=0).replace(0, np.nan)
    z_scores = ((price_frame - rolling_mean) / rolling_std).to_numpy(dtype="float64")
    trend_ma = price_frame.rolling(long_window).mean().to_numpy(dtype="float64")
    price_values = price_frame.to_numpy(dtype="float64")
    warmup = max(short_window, long_window)

    portfolio_value = np.ones(len(price_frame), dtype="float64")
    current_position = np.zeros(len(price_frame.columns), dtype="float64")
    entry_prices = np.full(len(price_frame.columns), np.nan, dtype="float64")
    cash = 1.0
    peak_value = 1.0

    for row_no in range(1, len(price_frame)):
        # 先用昨日收盘确定的持仓结算今日收益（避免用当日信号吃当日收益的前视偏差）。
        previous_position = current_position
        daily_returns = price_values[row_no] / price_values[row_no - 1] - 1.0
        cash *= 1 + _weighted_return_array(previous_position, daily_returns)
        portfolio_value[row_no] = cash

        if row_no < warmup:
            continue

        # 今日收盘信号只决定今日收盘后的持仓，影响的是次日及以后的收益。
        current_position = previous_position.copy()
        price_row = price_values[row_no]
        z_row = z_scores[row_no]
        trend_row = trend_ma[row_no]
        held = current_position > 0
        entry_signal = (~held) & np.isfinite(z_row) & np.isfinite(trend_row) & (z_row < -z_threshold) & (price_row > trend_row)
        if entry_signal.any():
            current_position[entry_signal] = 1.0
            entry_prices[entry_signal] = price_row[entry_signal]

        held_with_entry = held & ~np.isnan(entry_prices)
        exit_mask = np.zeros_like(held_with_entry, dtype=bool)
        if held_with_entry.any():
            changes = price_row[held_with_entry] / entry_prices[held_with_entry] - 1.0
            held_trend = trend_row[held_with_entry]
            held_z = z_row[held_with_entry]
            exit_mask[held_with_entry] = (
                (changes <= -stop_loss)
                | (changes >= take_profit)
                | (np.isfinite(held_trend) & (price_row[held_with_entry] < held_trend))
                | (np.isfinite(held_z) & (held_z > z_threshold))
            )
        if exit_mask.any():
            current_position[exit_mask] = 0.0
            entry_prices[exit_mask] = np.nan

        peak_value = max(peak_value, cash)
        if peak_value > 0 and (peak_value - cash) / peak_value > max_drawdown:
            current_position.fill(0.0)
            entry_prices.fill(np.nan)

    return pd.Series(portfolio_value, index=price_frame.index, dtype="float64")


def compute_factors(
    financial_df: pd.DataFrame,
    *,
    winsor_limits: tuple[float, float] | None = DEFAULT_WINSOR_LIMITS,
) -> pd.DataFrame:
    missing = [column for column in REQUIRED_FACTOR_INPUTS if column not in financial_df.columns]
    if missing:
        raise ValueError(f"missing factor input columns: {', '.join(missing)}")

    numeric = financial_df.loc[:, REQUIRED_FACTOR_INPUTS].apply(pd.to_numeric, errors="coerce").astype("float64")
    numeric = _winsorize_frame(numeric, winsor_limits)
    raw_factors = np.column_stack(
        [
            _row_nanmean(
                _safe_inverse_array(numeric["pe"].to_numpy(dtype="float64")),
                _safe_inverse_array(numeric["pb"].to_numpy(dtype="float64")),
                _safe_inverse_array(numeric["ps"].to_numpy(dtype="float64")),
            ),
            _row_nanmean(
                numeric["roe"].to_numpy(dtype="float64"),
                numeric["gross_margin"].to_numpy(dtype="float64"),
            ),
            _row_nanmean(
                numeric["three_month_return"].to_numpy(dtype="float64"),
                numeric["twelve_month_return"].to_numpy(dtype="float64"),
            ),
            _safe_inverse_array(numeric["volatility"].to_numpy(dtype="float64")),
            numeric["dividend_yield"].to_numpy(dtype="float64"),
        ]
    )
    return pd.DataFrame(
        _zscore_array(raw_factors),
        index=financial_df.index,
        columns=FACTOR_COLUMNS,
    )


def multi_factor_selection(
    financial_df: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
    top_pct: float = 0.1,
    industries_focus: Sequence[str] | None = None,
    max_per_industry: int | None = None,
    industry_neutral: bool = True,
    winsor_limits: tuple[float, float] | None = DEFAULT_WINSOR_LIMITS,
) -> pd.DataFrame:
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct must be in the (0, 1] range")
    if "industry" not in financial_df.columns:
        raise ValueError("missing factor input columns: industry")

    factors = compute_factors(financial_df, winsor_limits=winsor_limits)
    if industry_neutral:
        factors = _industry_neutralize_factors(factors, financial_df["industry"])
    active_weights = weights or DEFAULT_FACTOR_WEIGHTS
    unknown = [column for column in active_weights if column not in factors.columns]
    if unknown:
        raise ValueError(f"unknown factor weight columns: {', '.join(unknown)}")

    score = pd.Series(0.0, index=financial_df.index, dtype="float64")
    for column, weight in active_weights.items():
        score += factors[column] * float(weight)

    scored = financial_df.copy()
    scored["score"] = score
    if industries_focus is not None:
        scored = scored[scored["industry"].isin(industries_focus)]
    if scored.empty:
        return scored.sort_values("score", ascending=False)

    cutoff = max(int(len(scored) * top_pct), 1)
    selected = scored.sort_values("score", ascending=False).head(cutoff)
    if max_per_industry is None:
        return selected
    return _limit_per_industry(selected, max_per_industry=max_per_industry)


def classify_low_crowding_market_regime(
    prices: pd.DataFrame,
    observations: pd.DataFrame | None = None,
) -> dict[str, float | int | str | None]:
    price_frame = _clean_price_frame(prices)
    clean_observations = _clean_observation_frame(observations) if observations is not None and not observations.empty else None
    market_index = price_frame.div(price_frame.iloc[0]).mean(axis=1) * 100.0
    latest_index = float(market_index.iloc[-1])
    ma_fast = float(market_index.rolling(20, min_periods=min(5, len(market_index))).mean().iloc[-1])
    ma_slow = float(market_index.rolling(60, min_periods=min(10, len(market_index))).mean().iloc[-1])
    idx_ret_20d = _window_return(market_index, 20)
    amount_change_20 = _market_amount_change_20_from_clean(clean_observations)
    breadth_score = _latest_breadth_score_from_clean(price_frame, clean_observations)
    limit_down_count, sample_count = _latest_limit_down_count_from_clean(clean_observations)

    if amount_change_20 <= -0.30 and idx_ret_20d < 0:
        regime = "liquidity_shock"
    elif limit_down_count >= max(5, int(sample_count * 0.10)) and idx_ret_20d < 0:
        regime = "crowded_quant"
    elif idx_ret_20d <= -0.08 or latest_index < ma_slow * 0.97:
        regime = "fast_down"
    elif latest_index > ma_fast > ma_slow and breadth_score > 0:
        regime = "strong_up"
    elif latest_index > ma_fast or idx_ret_20d > 0:
        regime = "weak_up"
    else:
        regime = "range"

    target_position = float(LOW_CROWDING_REGIME_TARGET_POSITIONS[regime])
    return {
        "regime": regime,
        "target_position": target_position,
        "regime_score": round(float(breadth_score + idx_ret_20d + amount_change_20 * 0.2), 6),
        "breadth_score": round(float(breadth_score), 6),
        "limit_down_count": int(limit_down_count),
        "sample_count": int(sample_count),
        "amount_change_20": round(float(amount_change_20), 6),
        "idx_ret_20d": round(float(idx_ret_20d), 6),
        "latest_date": str(price_frame.index[-1])[:10],
    }


def compute_low_crowding_scores(observations: pd.DataFrame) -> pd.DataFrame:
    obs = _clean_observation_frame(observations)
    recent = obs.groupby("stock_code", sort=False).tail(21).copy()
    if recent.empty:
        return pd.DataFrame(
            columns=[
                "stock_code",
                "latest_date",
                "crowding_score",
                "low_crowding_score",
                "low_crowding_rank_pct",
            ]
        )

    recent_grouped = recent.groupby("stock_code", sort=False)
    latest = recent_grouped.tail(1).set_index("stock_code")
    recent20 = recent_grouped.tail(20)
    recent20_grouped = recent20.groupby("stock_code", sort=False)

    first_close = recent_grouped["close_value"].first()
    last_close = recent_grouped["close_value"].last()
    ret_5 = _grouped_window_return(recent, last_close, first_close, window=5)
    ret_20 = _grouped_window_return(recent, last_close, first_close, window=20)

    turn_median = recent20_grouped["turn"].median().reindex(latest.index)
    amount_mean = recent20_grouped["amount"].mean().reindex(latest.index)
    latest_turn = pd.to_numeric(latest["turn"], errors="coerce")
    latest_amount = pd.to_numeric(latest["amount"], errors="coerce")
    turn_accel = (latest_turn / turn_median - 1).where(turn_median.notna() & (turn_median > 0), 0.0)
    amount_accel = (latest_amount / amount_mean - 1).where(amount_mean.notna() & (amount_mean > 0), 0.0)

    amplitude_any = recent["amplitude"].notna().groupby(recent["stock_code"], sort=False).any()
    amplitude_mean = recent20_grouped["amplitude"].mean().reindex(latest.index)
    amplitude_20 = amplitude_mean.where(amplitude_any.reindex(latest.index).fillna(False), 0.0)

    out = pd.DataFrame(
        {
            "latest_date": latest["trade_date"].astype(str).str[:10],
            "ret_5": ret_5.reindex(latest.index),
            "ret_20": ret_20.reindex(latest.index),
            "turn_accel": turn_accel,
            "amount_accel": amount_accel,
            "amplitude_20": amplitude_20,
        },
        index=latest.index,
    )
    components = pd.DataFrame(
        {
            "ret_5_hot": out["ret_5"].clip(lower=0),
            "ret_20_hot": out["ret_20"].clip(lower=0),
            "turn_accel_hot": out["turn_accel"].clip(lower=0),
            "amount_accel_hot": out["amount_accel"].clip(lower=0),
            "amplitude_20": out["amplitude_20"].clip(lower=0),
        },
        index=out.index,
    )
    out["crowding_score"] = components.apply(_zscore).sum(axis=1)
    out["low_crowding_score"] = -out["crowding_score"]
    out["low_crowding_rank_pct"] = out["low_crowding_score"].rank(pct=True)
    return out.sort_values("low_crowding_score", ascending=False)


def _grouped_window_return(
    recent: pd.DataFrame,
    last_close: pd.Series,
    first_close: pd.Series,
    *,
    window: int,
) -> pd.Series:
    shifted_start = recent.groupby("stock_code", sort=False)["close_value"].shift(window)
    start_close = shifted_start.groupby(recent["stock_code"], sort=False).last()
    start_close = start_close.reindex(last_close.index).where(start_close.notna(), first_close)
    valid_start = start_close > 0
    return (last_close / start_close - 1).where(valid_start, 0.0).fillna(0.0)


def low_crowding_multifactor_selection(
    financial_df: pd.DataFrame,
    observations: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
    top_pct: float = 0.1,
    min_names_for_exclusion: int = 5,
    crowding_scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct must be in the (0, 1] range")
    scored = multi_factor_selection(financial_df, weights=weights, top_pct=1.0)
    crowding = crowding_scores if crowding_scores is not None else compute_low_crowding_scores(observations)
    joined = scored.join(crowding, how="inner")
    if joined.empty:
        return joined

    filtered = joined.copy()
    filtered["excluded_by_crowding"] = False
    excluded_count = 0
    if len(filtered) >= min_names_for_exclusion:
        crowding_cutoff = filtered["crowding_score"].quantile(0.80)
        filtered["excluded_by_crowding"] = filtered["crowding_score"] > crowding_cutoff
        excluded_count = int(filtered["excluded_by_crowding"].sum())
        filtered = filtered[~filtered["excluded_by_crowding"]].copy()
    if filtered.empty:
        filtered["crowding_excluded_count"] = excluded_count
        return filtered

    filtered["combined_score"] = filtered["score"] + 0.25 * _zscore(filtered["low_crowding_score"])
    filtered["crowding_excluded_count"] = excluded_count
    cutoff = max(int(len(filtered) * top_pct), 1)
    return filtered.sort_values("combined_score", ascending=False).head(cutoff)


def _clean_price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        raise ValueError("prices must not be empty")
    frame = prices.apply(pd.to_numeric, errors="coerce")
    if frame.isna().any().any():
        raise ValueError("prices must contain only numeric, non-null values")
    if (frame <= 0).any().any():
        raise ValueError("prices must be positive")
    return frame.astype("float64")


def _validate_windows(short_window: int, long_window: int) -> None:
    if short_window <= 0 or long_window <= 0:
        raise ValueError("windows must be positive")
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window")


def _safe_daily_returns(prices: pd.DataFrame, row_no: int) -> pd.Series:
    returns = prices.iloc[row_no] / prices.iloc[row_no - 1] - 1
    return returns.replace([np.inf, -np.inf], 0).fillna(0)


def _weighted_return(position: pd.Series, daily_returns: pd.Series) -> float:
    active_count = float(position.sum())
    if active_count <= 0:
        return 0.0
    weights = position / active_count
    return float((weights * daily_returns).sum())


def _weighted_return_array(position: np.ndarray, daily_returns: np.ndarray) -> float:
    active_count = float(position.sum())
    if active_count <= 0:
        return 0.0
    clean_returns = np.nan_to_num(daily_returns, nan=0.0, posinf=0.0, neginf=0.0)
    return float(np.dot(position / active_count, clean_returns))


def _safe_inverse(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    return pd.Series(np.where(clean > 0, 1 / clean, np.nan), index=series.index, dtype="float64")


def _safe_inverse_array(values: np.ndarray) -> np.ndarray:
    return np.divide(1.0, values, out=np.full_like(values, np.nan, dtype="float64"), where=values > 0)


def _row_nanmean(*columns: np.ndarray) -> np.ndarray:
    values = np.column_stack(columns)
    finite = np.isfinite(values)
    counts = finite.sum(axis=1)
    sums = np.where(finite, values, 0.0).sum(axis=1)
    return np.divide(sums, counts, out=np.full(len(counts), np.nan, dtype="float64"), where=counts > 0)


def _zscore_array(values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    counts = finite.sum(axis=0)
    sums = np.where(finite, values, 0.0).sum(axis=0)
    means = np.divide(sums, counts, out=np.full(values.shape[1], np.nan, dtype="float64"), where=counts > 0)
    centered = values - means
    variances = np.divide(
        np.where(finite, centered * centered, 0.0).sum(axis=0),
        counts,
        out=np.full(values.shape[1], np.nan, dtype="float64"),
        where=counts > 0,
    )
    stds = np.sqrt(variances)
    valid_columns = np.isfinite(stds) & (stds != 0)
    return np.divide(
        centered,
        stds,
        out=np.zeros_like(values, dtype="float64"),
        where=finite & valid_columns.reshape(1, -1),
    )


def _winsorize_frame(frame: pd.DataFrame, limits: tuple[float, float] | None) -> pd.DataFrame:
    if limits is None:
        return frame
    lower, upper = limits
    if not 0 <= lower < upper <= 1:
        raise ValueError("winsor_limits must satisfy 0 <= lower < upper <= 1")
    values = frame.to_numpy(dtype="float64", copy=True)
    bounds = np.nanquantile(values, [lower, upper], axis=0)
    valid_bounds = np.isfinite(bounds[0]) & np.isfinite(bounds[1])
    values[:, valid_bounds] = np.clip(values[:, valid_bounds], bounds[0, valid_bounds], bounds[1, valid_bounds])
    return pd.DataFrame(values, index=frame.index, columns=frame.columns)


def _industry_neutralize_factors(factors: pd.DataFrame, industries: pd.Series) -> pd.DataFrame:
    out = factors.copy()
    if out.empty:
        return out
    industry_labels = industries.reindex(out.index).fillna("").astype(str)
    clean = out.loc[:, FACTOR_COLUMNS].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    grouped = clean.groupby(industry_labels, sort=False)
    counts = grouped.transform("count")
    means = grouped.transform("mean")
    stds = grouped.transform("std", ddof=0)
    zscores = ((clean - means) / stds.replace(0.0, np.nan)).fillna(0.0)
    out.loc[:, FACTOR_COLUMNS] = zscores.where(counts >= 2, clean)
    return out


def _zscore_if_group_has_peers(series: pd.Series) -> pd.Series:
    if len(series.dropna()) < 2:
        return series
    return _zscore(series)


def _limit_per_industry(scored: pd.DataFrame, *, max_per_industry: int) -> pd.DataFrame:
    if max_per_industry <= 0:
        raise ValueError("max_per_industry must be positive")
    if "industry" not in scored.columns:
        return scored
    kept = scored.groupby("industry", group_keys=False, sort=False).head(max_per_industry)
    return kept.sort_values("score", ascending=False)


def _zscore(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    mean = clean.mean()
    std = clean.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index, dtype="float64")
    return ((clean - mean) / std).fillna(0.0)


def _window_return(series: pd.Series, window: int) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 2:
        return 0.0
    start_idx = max(0, len(clean) - window - 1)
    start = float(clean.iloc[start_idx])
    end = float(clean.iloc[-1])
    if start <= 0:
        return 0.0
    return end / start - 1


def _clean_observation_frame(observations: pd.DataFrame) -> pd.DataFrame:
    required = ["trade_date", "stock_code", "close_value"]
    missing = [column for column in required if column not in observations.columns]
    if missing:
        raise ValueError(f"missing observation columns: {', '.join(missing)}")
    out = observations.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    out["stock_code"] = out["stock_code"].astype(str)
    for column in ["close_value", "amount", "pctchange", "turn", "amplitude", "lowlimit"]:
        if column not in out.columns:
            out[column] = np.nan
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["trade_date", "stock_code", "close_value"])
    out = out[out["close_value"] > 0]
    if out.empty:
        raise ValueError("observations must contain positive close values")
    return out.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)


def _latest_breadth_score(prices: pd.DataFrame, observations: pd.DataFrame | None) -> float:
    if observations is not None and not observations.empty and "pctchange" in observations.columns:
        return _latest_breadth_score_from_clean(prices, _clean_observation_frame(observations))
    return _latest_breadth_score_from_clean(prices, None)


def _latest_breadth_score_from_clean(prices: pd.DataFrame, observations: pd.DataFrame | None) -> float:
    if observations is not None and not observations.empty and "pctchange" in observations.columns:
        latest_date = observations["trade_date"].max()
        latest = observations[observations["trade_date"] == latest_date]
        pctchange = pd.to_numeric(latest["pctchange"], errors="coerce").dropna()
        if not pctchange.empty:
            up_count = int((pctchange > 0).sum())
            down_count = int((pctchange < 0).sum())
            denom = up_count + down_count
            return (up_count - down_count) / denom if denom else 0.0
    latest_returns = prices.iloc[-1] / prices.iloc[-2] - 1 if len(prices) >= 2 else pd.Series(dtype=float)
    up_count = int((latest_returns > 0).sum())
    down_count = int((latest_returns < 0).sum())
    denom = up_count + down_count
    return (up_count - down_count) / denom if denom else 0.0


def _market_amount_change_20(observations: pd.DataFrame | None) -> float:
    if observations is None or observations.empty or "amount" not in observations.columns:
        return 0.0
    return _market_amount_change_20_from_clean(_clean_observation_frame(observations))


def _market_amount_change_20_from_clean(observations: pd.DataFrame | None) -> float:
    if observations is None or observations.empty or "amount" not in observations.columns:
        return 0.0
    daily_amount = observations.groupby("trade_date")["amount"].sum(min_count=1).dropna().sort_index()
    if daily_amount.empty:
        return 0.0
    baseline = daily_amount.tail(20).mean()
    if pd.isna(baseline) or baseline <= 0:
        return 0.0
    return float(daily_amount.iloc[-1] / baseline - 1)


def _latest_limit_down_count(observations: pd.DataFrame | None) -> tuple[int, int]:
    if observations is None or observations.empty:
        return 0, 0
    return _latest_limit_down_count_from_clean(_clean_observation_frame(observations))


def _latest_limit_down_count_from_clean(observations: pd.DataFrame | None) -> tuple[int, int]:
    if observations is None or observations.empty:
        return 0, 0
    latest_date = observations["trade_date"].max()
    latest = observations[observations["trade_date"] == latest_date]
    lowlimit = pd.to_numeric(latest["lowlimit"], errors="coerce")
    close = pd.to_numeric(latest["close_value"], errors="coerce")
    is_limit_down = lowlimit.notna() & close.notna() & (close <= lowlimit * 1.001)
    return int(is_limit_down.sum()), int(len(latest))
