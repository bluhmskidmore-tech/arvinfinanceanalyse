from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence

TRADING_DAYS_PER_YEAR = 252


def calculate_vol_target_multipliers(
    return_rows: Sequence[Mapping[str, object]],
    *,
    target_vol: float,
    window: int = 20,
) -> list[dict[str, object]]:
    if target_vol <= 0:
        raise ValueError("target_vol must be positive")
    if window <= 1:
        raise ValueError("window must be greater than 1")

    history: list[float] = []
    points: list[dict[str, object]] = []
    for row in sorted(return_rows, key=lambda item: _date_text(item.get("trade_date") or item.get("date"))):
        date_key = _date_text(row.get("trade_date") or row.get("date"))
        daily_return = _first_float(row.get("return"), row.get("daily_return"))
        if not date_key or daily_return is None:
            continue
        insufficient_history = len(history) < window
        realized_vol: float | None = None
        multiplier = 1.0
        if not insufficient_history:
            realized_vol = statistics.stdev(history[-window:]) * math.sqrt(TRADING_DAYS_PER_YEAR)
            if realized_vol > 0:
                multiplier = min(1.0, target_vol / realized_vol)
        points.append(
            {
                "date": date_key,
                "daily_return": daily_return,
                "realized_vol": _round_optional(realized_vol),
                "multiplier": round(multiplier, 6),
                "insufficient_history": insufficient_history,
            }
        )
        history.append(daily_return)
    return points


def benchmark_daily_returns(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    direct: list[dict[str, object]] = []
    values: list[tuple[str, float]] = []
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date"))
        if not date_key:
            continue
        daily_return = _first_float(row.get("return"), row.get("daily_return"))
        if daily_return is not None:
            direct.append({"date": date_key, "daily_return": daily_return})
            continue
        value = _first_float(row.get("value"), row.get("close"), row.get("value_numeric"))
        if value is not None and value > 0:
            values.append((date_key, value))
    if direct:
        return sorted(direct, key=lambda row: str(row["date"]))

    returns: list[dict[str, object]] = []
    previous_value: float | None = None
    for date_key, value in sorted(values):
        daily_return = 0.0 if previous_value is None else value / previous_value - 1.0
        returns.append({"date": date_key, "daily_return": daily_return})
        previous_value = value
    return returns


def build_vol_target_index_comparison(
    benchmark_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]] = (),
    market_state_rows: Sequence[Mapping[str, object]] = (),
    exposure_by_market_state: Mapping[str, object],
    target_vol: float,
    window: int = 20,
    initial_capital: float = 100.0,
) -> dict[str, object]:
    return_rows = benchmark_daily_returns(benchmark_rows)
    if not return_rows:
        return {"status": "benchmark_unavailable", "target_vol": target_vol, "window": window, "curves": [], "metrics": {}}

    multipliers = {
        str(row["date"]): row
        for row in calculate_vol_target_multipliers(return_rows, target_vol=target_vol, window=window)
    }
    exposure_by_date = _exposure_by_date(exposure_rows)
    state_by_date = _market_state_by_date(market_state_rows)
    gate_value = float(initial_capital)
    vol_target_value = float(initial_capital)
    curves: list[dict[str, object]] = []
    gate_exposures: list[float] = []
    vol_target_exposures: list[float] = []
    multiplier_values: list[float] = []
    insufficient_days = 0
    prev_exposure: float | None = None
    for row in return_rows:
        date_key = str(row["date"])
        daily_return = float(row["daily_return"])
        decided_exposure = exposure_by_date.get(
            date_key,
            _exposure_for_state(state_by_date.get(date_key, "OFF"), exposure_by_market_state),
        )
        # 敞口由 T 日收盘决定、T+1 日生效（与 equity_strategies 口径一致），
        # 避免"当日收盘决定的敞口吃当日收益"的前视偏差（2026-07-19 审计 宏观 H-1）。
        # 序列首日没有 T-1 决策可用，退回当日决策（仅首日）。
        exposure = prev_exposure if prev_exposure is not None else decided_exposure
        prev_exposure = decided_exposure
        multiplier_row = multipliers[date_key]
        multiplier = float(multiplier_row["multiplier"])
        if bool(multiplier_row["insufficient_history"]):
            insufficient_days += 1
        vol_target_exposure = exposure * multiplier
        gate_value *= 1.0 + daily_return * exposure
        vol_target_value *= 1.0 + daily_return * vol_target_exposure
        gate_exposures.append(exposure)
        vol_target_exposures.append(vol_target_exposure)
        multiplier_values.append(multiplier)
        curves.append(
            {
                "date": date_key,
                "daily_return": round(daily_return, 6),
                "gate_exposure": round(exposure, 6),
                "realized_vol": multiplier_row["realized_vol"],
                "vol_multiplier": round(multiplier, 6),
                "vol_target_exposure": round(vol_target_exposure, 6),
                "gate_index": round(gate_value, 6),
                "gate_voltarget_index": round(vol_target_value, 6),
            }
        )

    return {
        "status": "ready",
        "target_vol": target_vol,
        "window": window,
        "curves": curves,
        "vol_target_exposure_by_date": {
            str(row["date"]): float(row["vol_target_exposure"])
            for row in curves
        },
        "metrics": {
            "gate_index": {
                **_metrics_from_values([float(row["gate_index"]) for row in curves], initial_capital=initial_capital),
                "avg_exposure": _round_optional(statistics.fmean(gate_exposures) if gate_exposures else None),
            },
            "gate_voltarget_index": {
                **_metrics_from_values(
                    [float(row["gate_voltarget_index"]) for row in curves],
                    initial_capital=initial_capital,
                ),
                "avg_exposure": _round_optional(
                    statistics.fmean(vol_target_exposures) if vol_target_exposures else None
                ),
                "avg_multiplier": _round_optional(statistics.fmean(multiplier_values) if multiplier_values else None),
                "insufficient_history_days": insufficient_days,
            },
        },
    }


def _metrics_from_values(values: Sequence[float], *, initial_capital: float) -> dict[str, object]:
    if not values:
        return {
            "sample_days": 0,
            "terminal_value": None,
            "cumulative_return": None,
            "cagr": None,
            "max_drawdown": None,
            "daily_sharpe": None,
        }
    sample_days = max(len(values) - 1, 0)
    terminal_value = values[-1]
    returns = [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
        if values[index - 1] > 0
    ]
    cagr = (
        (terminal_value / initial_capital) ** (TRADING_DAYS_PER_YEAR / sample_days) - 1.0
        if sample_days > 0 and terminal_value > 0 and initial_capital > 0
        else None
    )
    return {
        "sample_days": sample_days,
        "terminal_value": _round_optional(terminal_value),
        "cumulative_return": _round_optional(terminal_value / initial_capital - 1.0 if initial_capital > 0 else None),
        "cagr": _round_optional(cagr),
        "max_drawdown": _round_optional(_max_drawdown(values)),
        "daily_sharpe": _round_optional(_sharpe(returns)),
    }


def _exposure_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date"))
        exposure = _first_float(row.get("exposure"), row.get("market_gate_exposure"), row.get("value"))
        if date_key and exposure is not None:
            out[date_key] = min(max(exposure, 0.0), 1.0)
    return out


def _market_state_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date"))
        state = _text(row.get("market_state") or row.get("state"))
        if date_key and state:
            out[date_key] = state
    return out


def _exposure_for_state(state: str | None, exposure_by_market_state: Mapping[str, object]) -> float:
    raw = exposure_by_market_state.get(str(state or "OFF"), 0.0)
    if isinstance(raw, (tuple, list)):
        values = [_safe_float(value) for value in raw]
        exposure = max((value for value in values if value is not None), default=0.0)
    else:
        exposure = _safe_float(raw) or 0.0
    return min(max(exposure, 0.0), 1.0)


def _max_drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, 1.0 - value / peak)
    return max_drawdown


def _sharpe(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return statistics.fmean(returns) / stdev * math.sqrt(TRADING_DAYS_PER_YEAR)


def _first_float(*values: object) -> float | None:
    for value in values:
        coerced = _safe_float(value)
        if coerced is not None:
            return coerced
    return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round_optional(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def _date_text(value: object) -> str:
    return "" if value is None else str(value).strip()[:10]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
