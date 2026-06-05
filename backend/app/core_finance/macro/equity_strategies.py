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

    short_ma = price_frame.rolling(window=short_window).mean()
    long_ma = price_frame.rolling(window=long_window).mean()
    positions = pd.DataFrame(0.0, index=price_frame.index, columns=price_frame.columns)
    portfolio_value = pd.Series(1.0, index=price_frame.index, dtype="float64")
    cash = 1.0
    peak_value = 1.0
    entry_prices: dict[str, float | None] = {column: None for column in price_frame.columns}

    for row_no in range(1, len(price_frame)):
        # 先用昨日收盘确定的持仓结算今日收益（避免用当日信号吃当日收益的前视偏差）。
        previous_position = positions.iloc[row_no - 1]
        daily_returns = _safe_daily_returns(price_frame, row_no)
        cash *= 1 + _weighted_return(previous_position, daily_returns)
        portfolio_value.iat[row_no] = cash

        if row_no < long_window:
            positions.iloc[row_no] = previous_position
            continue

        # 今日收盘信号只决定今日收盘后的持仓，影响的是次日及以后的收益。
        current_position = previous_position.copy()
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
        # 先用昨日收盘确定的持仓结算今日收益（避免用当日信号吃当日收益的前视偏差）。
        previous_position = positions.iloc[row_no - 1]
        daily_returns = _safe_daily_returns(price_frame, row_no)
        cash *= 1 + _weighted_return(previous_position, daily_returns)
        portfolio_value.iat[row_no] = cash

        if row_no < warmup:
            positions.iloc[row_no] = previous_position
            continue

        # 今日收盘信号只决定今日收盘后的持仓，影响的是次日及以后的收益。
        current_position = previous_position.copy()
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

        peak_value = max(peak_value, cash)
        if peak_value > 0 and (peak_value - cash) / peak_value > max_drawdown:
            positions.iloc[row_no] = 0.0
            for column in entry_prices:
                entry_prices[column] = None

    return portfolio_value


def compute_factors(
    financial_df: pd.DataFrame,
    *,
    winsor_limits: tuple[float, float] | None = DEFAULT_WINSOR_LIMITS,
) -> pd.DataFrame:
    missing = [column for column in REQUIRED_FACTOR_INPUTS if column not in financial_df.columns]
    if missing:
        raise ValueError(f"missing factor input columns: {', '.join(missing)}")

    numeric = financial_df.loc[:, REQUIRED_FACTOR_INPUTS].apply(pd.to_numeric, errors="coerce")
    numeric = _winsorize_frame(numeric, winsor_limits)
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
    market_index = price_frame.div(price_frame.iloc[0]).mean(axis=1) * 100.0
    latest_index = float(market_index.iloc[-1])
    ma_fast = float(market_index.rolling(20, min_periods=min(5, len(market_index))).mean().iloc[-1])
    ma_slow = float(market_index.rolling(60, min_periods=min(10, len(market_index))).mean().iloc[-1])
    idx_ret_20d = _window_return(market_index, 20)
    amount_change_20 = _market_amount_change_20(observations)
    breadth_score = _latest_breadth_score(price_frame, observations)
    limit_down_count, sample_count = _latest_limit_down_count(observations)

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
    records: list[dict[str, float | str]] = []
    for stock_code, group in obs.groupby("stock_code", sort=False):
        ordered = group.sort_values("trade_date").tail(21)
        if ordered.empty:
            continue
        latest = ordered.iloc[-1]
        close = ordered["close_value"]
        ret_5 = _window_return(close, 5)
        ret_20 = _window_return(close, 20)
        turn_median = ordered["turn"].tail(20).median()
        amount_mean = ordered["amount"].tail(20).mean()
        latest_turn = float(latest.get("turn", 0.0) or 0.0)
        latest_amount = float(latest.get("amount", 0.0) or 0.0)
        turn_accel = latest_turn / turn_median - 1 if pd.notna(turn_median) and turn_median > 0 else 0.0
        amount_accel = latest_amount / amount_mean - 1 if pd.notna(amount_mean) and amount_mean > 0 else 0.0
        amplitude_20 = float(ordered["amplitude"].tail(20).mean()) if ordered["amplitude"].notna().any() else 0.0
        records.append(
            {
                "stock_code": str(stock_code),
                "latest_date": str(latest["trade_date"])[:10],
                "ret_5": float(ret_5),
                "ret_20": float(ret_20),
                "turn_accel": float(turn_accel),
                "amount_accel": float(amount_accel),
                "amplitude_20": float(amplitude_20),
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "stock_code",
                "latest_date",
                "crowding_score",
                "low_crowding_score",
                "low_crowding_rank_pct",
            ]
        )

    out = pd.DataFrame(records).set_index("stock_code")
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


def low_crowding_multifactor_selection(
    financial_df: pd.DataFrame,
    observations: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
    top_pct: float = 0.1,
    min_names_for_exclusion: int = 5,
) -> pd.DataFrame:
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct must be in the (0, 1] range")
    scored = multi_factor_selection(financial_df, weights=weights, top_pct=1.0)
    crowding = compute_low_crowding_scores(observations)
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


def _safe_inverse(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    return pd.Series(np.where(clean > 0, 1 / clean, np.nan), index=series.index, dtype="float64")


def _winsorize_frame(frame: pd.DataFrame, limits: tuple[float, float] | None) -> pd.DataFrame:
    if limits is None:
        return frame
    lower, upper = limits
    if not 0 <= lower < upper <= 1:
        raise ValueError("winsor_limits must satisfy 0 <= lower < upper <= 1")
    clipped = frame.copy()
    for column in clipped.columns:
        series = pd.to_numeric(clipped[column], errors="coerce")
        lo = series.quantile(lower)
        hi = series.quantile(upper)
        if pd.notna(lo) and pd.notna(hi):
            clipped[column] = series.clip(lower=lo, upper=hi)
    return clipped


def _industry_neutralize_factors(factors: pd.DataFrame, industries: pd.Series) -> pd.DataFrame:
    out = factors.copy()
    industry_labels = industries.reindex(out.index).fillna("").astype(str)
    for column in FACTOR_COLUMNS:
        out[column] = out.groupby(industry_labels, group_keys=False)[column].transform(_zscore_if_group_has_peers)
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
        obs = _clean_observation_frame(observations)
        latest_date = obs["trade_date"].max()
        latest = obs[obs["trade_date"] == latest_date]
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
    obs = _clean_observation_frame(observations)
    daily_amount = obs.groupby("trade_date")["amount"].sum(min_count=1).dropna().sort_index()
    if daily_amount.empty:
        return 0.0
    baseline = daily_amount.tail(20).mean()
    if pd.isna(baseline) or baseline <= 0:
        return 0.0
    return float(daily_amount.iloc[-1] / baseline - 1)


def _latest_limit_down_count(observations: pd.DataFrame | None) -> tuple[int, int]:
    if observations is None or observations.empty:
        return 0, 0
    obs = _clean_observation_frame(observations)
    latest_date = obs["trade_date"].max()
    latest = obs[obs["trade_date"] == latest_date]
    lowlimit = pd.to_numeric(latest["lowlimit"], errors="coerce")
    close = pd.to_numeric(latest["close_value"], errors="coerce")
    is_limit_down = lowlimit.notna() & close.notna() & (close <= lowlimit * 1.001)
    return int(is_limit_down.sum()), int(len(latest))
