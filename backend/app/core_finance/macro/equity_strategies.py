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

    short_ma = price_frame.rolling(window=short_window).mean()
    long_ma = price_frame.rolling(window=long_window).mean()
    positions = pd.DataFrame(0.0, index=price_frame.index, columns=price_frame.columns)
    portfolio_value = pd.Series(1.0, index=price_frame.index, dtype="float64")
    cash = 1.0
    peak_value = 1.0
    entry_prices: dict[str, float | None] = {column: None for column in price_frame.columns}

    for row_no in range(1, len(price_frame)):
        if row_no < long_window:
            portfolio_value.iat[row_no] = cash
            continue

        current_position = positions.iloc[row_no - 1].copy()
        for column in price_frame.columns:
            crossed_up = (
                short_ma[column].iat[row_no - 1] <= long_ma[column].iat[row_no - 1]
                and short_ma[column].iat[row_no] > long_ma[column].iat[row_no]
            )
            crossed_down = (
                short_ma[column].iat[row_no - 1] >= long_ma[column].iat[row_no - 1]
                and short_ma[column].iat[row_no] < long_ma[column].iat[row_no]
            )
            if crossed_up:
                current_position[column] = 1.0
                entry_prices[column] = float(price_frame[column].iat[row_no])
            elif crossed_down:
                current_position[column] = 0.0
                entry_prices[column] = None
            elif current_position[column] > 0 and entry_prices[column] is not None:
                drawdown_from_entry = price_frame[column].iat[row_no] / entry_prices[column] - 1
                if drawdown_from_entry <= -stop_loss:
                    current_position[column] = 0.0
                    entry_prices[column] = None

        positions.iloc[row_no] = current_position
        daily_returns = _safe_daily_returns(price_frame, row_no)
        cash *= 1 + _weighted_return(current_position, daily_returns)
        portfolio_value.iat[row_no] = cash

        peak_value = max(peak_value, cash)
        if peak_value > 0 and (peak_value - cash) / peak_value > max_drawdown:
            positions.iloc[row_no] = 0.0
            for column in entry_prices:
                entry_prices[column] = None

    return portfolio_value


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
    z_scores = (price_frame - rolling_mean) / rolling_std
    trend_ma = price_frame.rolling(long_window).mean()
    warmup = max(short_window, long_window)

    positions = pd.DataFrame(0.0, index=price_frame.index, columns=price_frame.columns)
    portfolio_value = pd.Series(1.0, index=price_frame.index, dtype="float64")
    entry_prices: dict[str, float | None] = {column: None for column in price_frame.columns}
    cash = 1.0
    peak_value = 1.0

    for row_no in range(1, len(price_frame)):
        if row_no < warmup:
            portfolio_value.iat[row_no] = cash
            continue

        current_position = positions.iloc[row_no - 1].copy()
        for column in price_frame.columns:
            price = float(price_frame[column].iat[row_no])
            z_score = z_scores[column].iat[row_no]
            trend = trend_ma[column].iat[row_no]
            held = current_position[column] > 0

            if not held and pd.notna(z_score) and pd.notna(trend) and z_score < -z_threshold and price > trend:
                current_position[column] = 1.0
                entry_prices[column] = price
            elif held and entry_prices[column] is not None:
                change = price / entry_prices[column] - 1
                exit_signal = (
                    change <= -stop_loss
                    or change >= take_profit
                    or (pd.notna(trend) and price < trend)
                    or (pd.notna(z_score) and z_score > z_threshold)
                )
                if exit_signal:
                    current_position[column] = 0.0
                    entry_prices[column] = None

        positions.iloc[row_no] = current_position
        daily_returns = _safe_daily_returns(price_frame, row_no)
        cash *= 1 + _weighted_return(current_position, daily_returns)
        portfolio_value.iat[row_no] = cash

        peak_value = max(peak_value, cash)
        if peak_value > 0 and (peak_value - cash) / peak_value > max_drawdown:
            positions.iloc[row_no] = 0.0
            for column in entry_prices:
                entry_prices[column] = None

    return portfolio_value


def compute_factors(financial_df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_FACTOR_INPUTS if column not in financial_df.columns]
    if missing:
        raise ValueError(f"missing factor input columns: {', '.join(missing)}")

    numeric = financial_df.loc[:, REQUIRED_FACTOR_INPUTS].apply(pd.to_numeric, errors="coerce")
    value = pd.concat(
        [
            _safe_inverse(numeric["pe"]),
            _safe_inverse(numeric["pb"]),
            _safe_inverse(numeric["ps"]),
        ],
        axis=1,
    ).mean(axis=1)
    quality = numeric[["roe", "gross_margin"]].mean(axis=1)
    momentum = numeric[["three_month_return", "twelve_month_return"]].mean(axis=1)
    low_vol = _safe_inverse(numeric["volatility"])
    dividend = numeric["dividend_yield"]

    return pd.DataFrame(
        {
            "value": _zscore(value),
            "quality": _zscore(quality),
            "momentum": _zscore(momentum),
            "low_vol": _zscore(low_vol),
            "dividend": _zscore(dividend),
        },
        index=financial_df.index,
    )


def multi_factor_selection(
    financial_df: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
    top_pct: float = 0.1,
    industries_focus: Sequence[str] | None = None,
) -> pd.DataFrame:
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct must be in the (0, 1] range")
    if "industry" not in financial_df.columns:
        raise ValueError("missing factor input columns: industry")

    factors = compute_factors(financial_df)
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
    return scored.sort_values("score", ascending=False).head(cutoff)


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


def _safe_inverse(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    return pd.Series(np.where(clean > 0, 1 / clean, np.nan), index=series.index, dtype="float64")


def _zscore(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    mean = clean.mean()
    std = clean.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index, dtype="float64")
    return ((clean - mean) / std).fillna(0.0)
