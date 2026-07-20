"""Formal-side calculations for the candidate-history proxy backtests.

These functions implement the reduced cycle-rotation proxy (non-overlapping
T+5 baskets) and the monthly candidate-history portfolio proxy (equal-weight
top-6, daily adjusted-close mark-to-market with raw-close fallback). They are not the full path backtest
engine in ``portfolio_backtest.py`` — the proxy simulation structures
(non-overlapping baskets, monthly target-weight rebalances) are not
expressible in the signal-driven slot model — but all return, cost, and
risk conventions are aligned with the formal engine constants:

- transaction costs and slippage come from ``strategy_policy.POLICY``
- basket returns prefer execution-history ``return_5d_net_adj`` (next-open,
  already net of policy costs); when unavailable they use
  ``adjusted_returns.net_return_after_costs`` on dividend/split-adjusted
  ``return_5d_adj`` and finally gross ``return_5d``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from backend.app.core_finance.adjusted_returns import net_return_after_costs
from backend.app.core_finance.strategy_policy import POLICY

# v2: basket returns prefer return_5d_adj over gross return_5d.
# v3: per-basket net returns now use multiplicative cost netting
# ((1+r)*(1-c)-1) via adjusted_returns.net_return_after_costs.
# v4: service-enriched next-open return_5d_net_adj is preferred and is not
# charged again; candidate-history close-based returns remain explicit fallbacks.
CYCLE_PROXY_FORMULA_VERSION = "fv_livermore_cycle_proxy_backtest_execution_first_v4"
# v2: portfolio proxy marks to market on adjustment-factor adjusted closes,
# falling back to raw closes only when the adjusted price is missing.
PORTFOLIO_PROXY_FORMULA_VERSION = "fv_livermore_candidate_history_portfolio_adj_mtm_v2"

CYCLE_PROXY_ENTRY_PRICE_WARNING = (
    "Executable next-open return_5d_net_adj from livermore_candidate_execution_history is preferred. "
    "When that row is unavailable, the fallback uses signal-day close returns, embedding a "
    "same-day execution assumption that is not replicable live and may be systematically optimistic."
)
PORTFOLIO_PROXY_ENTRY_PRICE_WARNING = (
    "The monthly portfolio proxy remains priced at the snapshot-day close, embedding a same-day "
    "execution assumption that is not replicable live, so returns may be systematically optimistic. "
    "livermore_candidate_execution_history tracks next-open entries and limit-up blocking, but its "
    "fixed-horizon rows cannot directly replace this proxy's monthly daily-mark-to-market path."
)

CYCLE_PROXY_EXECUTION_RETURN_FIELD = "return_5d_net_adj"
CYCLE_PROXY_EXECUTION_GROSS_FIELD = "return_5d_gross_adj"
CYCLE_PROXY_EXECUTION_ENTRY_DATE_FIELD = "execution_entry_date"
CYCLE_PROXY_EXECUTION_EXIT_DATE_FIELD = "execution_exit_date_5d"
CYCLE_PROXY_RETURN_FIELD = "return_5d_adj"
CYCLE_PROXY_RETURN_FALLBACK_FIELD = "return_5d"
PORTFOLIO_PROXY_PRICE_FIELD = "adj_close_value"
PORTFOLIO_PROXY_PRICE_FALLBACK_FIELD = "close_value"
PROXY_ANNUALIZATION_DAYS_PER_YEAR = 365.0
PROXY_ANNUALIZATION_MIN_BASKETS = 2
TRADING_DAYS_PER_YEAR = 252


def proxy_cost_basis() -> dict[str, Any]:
    return {
        "source": "core_finance.strategy_policy.POLICY",
        "buy_cost_rate": POLICY.buy_cost_rate,
        "sell_cost_rate": POLICY.sell_cost_rate,
        "slippage_rate": POLICY.slippage_rate,
        "round_trip_cost_rate": round(
            POLICY.buy_cost_rate + POLICY.sell_cost_rate + 2 * POLICY.slippage_rate,
            6,
        ),
    }


def cycle_proxy_row_return(row: Mapping[str, Any]) -> tuple[float, str] | None:
    """Return the preferred basket return and the field it came from."""
    execution_net = _safe_float(row.get(CYCLE_PROXY_EXECUTION_RETURN_FIELD))
    if execution_net is not None:
        return execution_net, CYCLE_PROXY_EXECUTION_RETURN_FIELD
    adjusted = _safe_float(row.get(CYCLE_PROXY_RETURN_FIELD))
    if adjusted is not None:
        return adjusted, CYCLE_PROXY_RETURN_FIELD
    fallback = _safe_float(row.get(CYCLE_PROXY_RETURN_FALLBACK_FIELD))
    if fallback is not None:
        return fallback, CYCLE_PROXY_RETURN_FALLBACK_FIELD
    return None


def cycle_proxy_return_field_stats(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    execution_rows = 0
    adjusted_rows = 0
    fallback_rows = 0
    for row in items:
        selected = cycle_proxy_row_return(row)
        if selected is None:
            continue
        if selected[1] == CYCLE_PROXY_EXECUTION_RETURN_FIELD:
            execution_rows += 1
        elif selected[1] == CYCLE_PROXY_RETURN_FIELD:
            adjusted_rows += 1
        else:
            fallback_rows += 1
    return {
        "return_rows_execution_net_adjusted": execution_rows,
        # Keep the legacy key while exposing that it is now a fallback.
        "return_rows_adjusted": adjusted_rows,
        "return_rows_adjusted_fallback": adjusted_rows,
        "return_rows_gross_fallback": fallback_rows,
    }


def candidate_history_portfolio_price(row: Mapping[str, Any]) -> tuple[float, str] | None:
    """Return the mark-to-market price and source field for a close row."""
    adjusted = _safe_float(row.get(PORTFOLIO_PROXY_PRICE_FIELD))
    if adjusted is not None:
        return adjusted, PORTFOLIO_PROXY_PRICE_FIELD
    fallback = _safe_float(row.get(PORTFOLIO_PROXY_PRICE_FALLBACK_FIELD))
    if fallback is not None:
        return fallback, PORTFOLIO_PROXY_PRICE_FALLBACK_FIELD
    return None


def candidate_history_portfolio_price_field_stats(
    close_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    adjusted_rows = 0
    fallback_rows = 0
    for row in close_rows:
        selected = candidate_history_portfolio_price(row)
        if selected is None:
            continue
        if selected[1] == PORTFOLIO_PROXY_PRICE_FIELD:
            adjusted_rows += 1
        else:
            fallback_rows += 1
    return {
        "price_rows_adjusted": adjusted_rows,
        "price_rows_raw_fallback": fallback_rows,
    }


def build_cycle_proxy_nav_series(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows_by_date: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if snapshot_date:
            rows_by_date.setdefault(snapshot_date, []).append(item)

    nav = 1.0
    next_entry_after: str | None = None
    series: list[dict[str, Any]] = []
    for snapshot_date, rows in sorted(rows_by_date.items()):
        selected_rows = [
            (row, selected)
            for row in rows
            if (selected := cycle_proxy_row_return(row)) is not None
        ]
        if not selected_rows:
            continue
        values: list[float] = []
        gross_values: list[float] = []
        entry_dates: list[str] = []
        exit_dates: list[str] = []
        for row, (value, field_name) in selected_rows:
            if field_name == CYCLE_PROXY_EXECUTION_RETURN_FIELD:
                entry_date = str(
                    row.get(CYCLE_PROXY_EXECUTION_ENTRY_DATE_FIELD) or snapshot_date
                ).strip()[:10]
                exit_date = str(
                    row.get(CYCLE_PROXY_EXECUTION_EXIT_DATE_FIELD)
                    or row.get("forward_trade_date_5d")
                    or ""
                ).strip()[:10]
                if not exit_date:
                    continue
                # Execution history is already net of the formal round-trip costs.
                values.append(value)
                execution_gross = _safe_float(row.get(CYCLE_PROXY_EXECUTION_GROSS_FIELD))
                gross_values.append(value if execution_gross is None else execution_gross)
                entry_dates.append(entry_date)
                exit_dates.append(exit_date)
                continue
            exit_date = str(row.get("forward_trade_date_5d") or "").strip()[:10]
            if not exit_date:
                continue
            net_value = net_return_after_costs(
                value,
                buy_cost_rate=POLICY.buy_cost_rate,
                sell_cost_rate=POLICY.sell_cost_rate,
                slippage_rate=POLICY.slippage_rate,
            )
            if net_value is not None:
                values.append(net_value)
                gross_values.append(value)
                entry_dates.append(snapshot_date)
                exit_dates.append(exit_date)
        if not values:
            continue
        entry_date = max(entry_dates)
        if next_entry_after is not None and entry_date <= next_entry_after:
            continue
        period_return = sum(values) / len(values)
        exit_date = max(exit_dates)
        nav *= 1 + period_return
        series.append(
            {
                "date": entry_date,
                "exit_date": exit_date,
                "period_return": round(period_return, 6),
                "period_return_gross": round(sum(gross_values) / len(gross_values), 6),
                "nav": round(nav, 6),
                "candidate_count": len(values),
            }
        )
        next_entry_after = exit_date
    return series


def build_cycle_proxy_summary(
    nav_series: Sequence[Mapping[str, Any]],
    *,
    candidate_rows: int,
    benchmark_rows: Sequence[Mapping[str, Any]],
    benchmark_series_id: str,
    return_field_stats: Mapping[str, int] | None = None,
) -> dict[str, Any] | None:
    if not nav_series:
        return None

    terminal_nav = float(nav_series[-1]["nav"])
    cumulative_return = terminal_nav - 1
    sample_days = len(nav_series)
    span_days = cycle_proxy_span_calendar_days(nav_series)
    if (
        sample_days >= PROXY_ANNUALIZATION_MIN_BASKETS
        and span_days is not None
        and span_days > 0
        and terminal_nav > 0
    ):
        annualized_return: float | None = terminal_nav ** (PROXY_ANNUALIZATION_DAYS_PER_YEAR / span_days) - 1
        annualization_status = "ok"
    else:
        annualized_return = None
        annualization_status = "insufficient_sample"
    summary = {
        "sample_days": sample_days,
        "candidate_rows": candidate_rows,
        "return_field_used": CYCLE_PROXY_EXECUTION_RETURN_FIELD,
        "return_field_fallback": CYCLE_PROXY_RETURN_FIELD,
        "return_field_second_fallback": CYCLE_PROXY_RETURN_FALLBACK_FIELD,
        "execution_return_costs_already_applied": True,
        **dict(return_field_stats or {}),
        "cost_basis": proxy_cost_basis(),
        "cumulative_return": round(cumulative_return, 6),
        "annualized_return": round(annualized_return, 6) if annualized_return is not None else None,
        "annualization_status": annualization_status,
        "annualization_span_calendar_days": span_days,
        "max_gain": max_gain_interval(nav_series),
        "max_drawdown": max_drawdown_interval(nav_series),
    }
    benchmark = build_benchmark_window_summary(
        nav_series=nav_series,
        benchmark_rows=benchmark_rows,
        strategy_cumulative_return=cumulative_return,
        series_id=benchmark_series_id,
    )
    if benchmark is not None:
        summary["benchmark"] = benchmark
    return summary


def cycle_proxy_span_calendar_days(nav_series: Sequence[Mapping[str, Any]]) -> int | None:
    """Calendar days from the first basket entry to the last realized exit date."""
    try:
        first_entry = date.fromisoformat(str(nav_series[0]["date"])[:10])
        last_exit = date.fromisoformat(str(nav_series[-1].get("exit_date") or nav_series[-1]["date"])[:10])
    except ValueError:
        return None
    return (last_exit - first_entry).days


def build_candidate_history_portfolio_series(
    *,
    rebalances: Sequence[Mapping[str, Any]],
    close_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if not rebalances or not close_rows:
        return [], [], []

    closes_by_date: dict[str, dict[str, float]] = {}
    for row in close_rows:
        selected = candidate_history_portfolio_price(row)
        if selected is None:
            continue
        date_key = str(row["trade_date"])
        closes_by_date.setdefault(date_key, {})[str(row["stock_code"])] = selected[0]

    rebalance_by_date = {str(rebalance["date"]): rebalance for rebalance in rebalances}
    positions: dict[str, float] = {}
    cash = 1.0
    nav = 1.0
    nav_series: list[dict[str, Any]] = []
    rebalance_log: list[dict[str, Any]] = []
    # Missing closes are valued at the last known close (forward-fill) instead
    # of zero; stocks that never reprice within a rebalance period are reported.
    last_close: dict[str, float] = {}
    codes_seen_since_rebalance: set[str] = set()
    stale_price_codes: set[str] = set()
    dates_after_last_rebalance = 0

    for trade_date in sorted(closes_by_date):
        closes = closes_by_date[trade_date]
        # After this update, last_close holds today's close when fresh and the
        # forward-filled previous close otherwise.
        last_close.update(closes)
        codes_seen_since_rebalance.update(closes)
        market_value_before = sum(shares * last_close.get(code, 0.0) for code, shares in positions.items())
        nav_before_rebalance = cash + market_value_before
        rebalance = rebalance_by_date.get(trade_date)
        if rebalance is not None:
            stale_price_codes.update(code for code in positions if code not in codes_seen_since_rebalance)
            target_codes = [
                str(item.get("stock_code") or "").strip()
                for item in rebalance["items"]
                if str(item.get("stock_code") or "").strip() in closes
            ]
            target_weight = 1.0 / len(target_codes) if target_codes else 0.0
            current_values = {
                code: positions.get(code, 0.0) * last_close.get(code, 0.0)
                for code in set(positions) | set(target_codes)
            }
            target_values = {code: nav_before_rebalance * target_weight for code in target_codes}
            buy_value = sum(
                max(target_values.get(code, 0.0) - current_values.get(code, 0.0), 0.0)
                for code in set(current_values) | set(target_values)
            )
            sell_value = sum(
                max(current_values.get(code, 0.0) - target_values.get(code, 0.0), 0.0)
                for code in set(current_values) | set(target_values)
            )
            buy_turnover = buy_value / nav_before_rebalance if nav_before_rebalance > 0 else 0.0
            sell_turnover = sell_value / nav_before_rebalance if nav_before_rebalance > 0 else 0.0
            cost = buy_value * (POLICY.buy_cost_rate + POLICY.slippage_rate) + sell_value * (
                POLICY.sell_cost_rate + POLICY.slippage_rate
            )
            investable_nav = max(nav_before_rebalance - cost, 0.0)
            if target_codes:
                target_value_after_cost = investable_nav / len(target_codes)
                positions = {code: target_value_after_cost / closes[code] for code in target_codes if closes[code] > 0}
                cash = 0.0
            else:
                positions = {}
                cash = investable_nav
            nav = cash + sum(shares * last_close.get(code, 0.0) for code, shares in positions.items())
            rebalance_log.append(
                {
                    "date": trade_date,
                    "market_state": rebalance["market_state"],
                    "target_count": len(target_codes),
                    "buy_turnover": round(buy_turnover, 6),
                    "sell_turnover": round(sell_turnover, 6),
                    "transaction_cost": round(cost, 6),
                }
            )
            codes_seen_since_rebalance = set()
            dates_after_last_rebalance = 0
        else:
            nav = cash + market_value_before
            dates_after_last_rebalance += 1
        nav_series.append(
            {
                "date": trade_date,
                "nav": round(nav, 6),
                "cash_weight": round(cash / nav, 6) if nav > 0 else 0.0,
                "holding_count": len(positions),
            }
        )
    if dates_after_last_rebalance > 0:
        stale_price_codes.update(code for code in positions if code not in codes_seen_since_rebalance)
    return nav_series, rebalance_log, sorted(stale_price_codes)


def build_candidate_history_portfolio_summary(
    nav_series: Sequence[Mapping[str, Any]],
    *,
    rebalance_log: Sequence[Mapping[str, Any]],
    benchmark_rows: Sequence[Mapping[str, Any]],
    benchmark_series_id: str,
    price_field_stats: Mapping[str, int] | None = None,
) -> dict[str, Any] | None:
    if not nav_series or not rebalance_log:
        return None
    terminal_nav = float(nav_series[-1]["nav"])
    cumulative_return = terminal_nav - 1.0
    sample_days = max(len(nav_series) - 1, 0)
    annualized_return = (
        terminal_nav ** (TRADING_DAYS_PER_YEAR / sample_days) - 1
        if sample_days > 0 and terminal_nav > 0
        else None
    )
    buy_turnover = sum(float(row["buy_turnover"]) for row in rebalance_log)
    sell_turnover = sum(float(row["sell_turnover"]) for row in rebalance_log)
    transaction_cost = sum(float(row["transaction_cost"]) for row in rebalance_log)
    summary = {
        "sample_days": sample_days,
        "candidate_rows": sum(int(row["target_count"]) for row in rebalance_log),
        "rebalance_count": len(rebalance_log),
        "invested_rebalance_count": sum(1 for row in rebalance_log if int(row["target_count"]) > 0),
        "cash_rebalance_count": sum(1 for row in rebalance_log if int(row["target_count"]) == 0),
        "price_field_used": PORTFOLIO_PROXY_PRICE_FIELD,
        "price_field_fallback": PORTFOLIO_PROXY_PRICE_FALLBACK_FIELD,
        **dict(price_field_stats or {}),
        "gross_turnover": round(buy_turnover + sell_turnover, 6),
        "cost_basis": proxy_cost_basis(),
        "cost_drag": round(transaction_cost, 6),
        "cumulative_return": round(cumulative_return, 6),
        "annualized_return": round(annualized_return, 6) if annualized_return is not None else None,
        "max_gain": max_gain_interval(nav_series),
        "max_drawdown": max_drawdown_interval(nav_series),
    }
    benchmark = build_benchmark_window_summary(
        nav_series=nav_series,
        benchmark_rows=benchmark_rows,
        strategy_cumulative_return=cumulative_return,
        series_id=benchmark_series_id,
    )
    if benchmark is not None:
        summary["benchmark"] = benchmark
    return summary


def build_benchmark_window_summary(
    *,
    nav_series: Sequence[Mapping[str, Any]],
    benchmark_rows: Sequence[Mapping[str, Any]],
    strategy_cumulative_return: float,
    series_id: str,
) -> dict[str, Any] | None:
    """Endpoint-ratio benchmark return over the strategy window.

    The start/end ratio equals compounding the benchmark's own full daily
    calendar over the same window, so sparse strategy anchor dates cannot
    skip intermediate benchmark trading days (same convention as the formal
    engine's ``build_benchmark_comparison``).
    """
    if not nav_series or len(benchmark_rows) < 2:
        return None
    requested_start_date = str(nav_series[0]["date"])[:10]
    requested_end_date = str(nav_series[-1].get("exit_date") or nav_series[-1]["date"])[:10]
    start_row = benchmark_rows[0]
    end_row = benchmark_rows[-1]
    start_value = float(start_row["value"])
    end_value = float(end_row["value"])
    if start_value <= 0:
        return None
    benchmark_return = end_value / start_value - 1
    start_date = str(start_row["trade_date"])[:10]
    end_date = str(end_row["trade_date"])[:10]
    return {
        "series_id": series_id,
        "coverage_status": "complete"
        if start_date <= requested_start_date and end_date >= requested_end_date
        else "partial",
        "requested_start_date": requested_start_date,
        "requested_end_date": requested_end_date,
        "start_date": start_date,
        "end_date": end_date,
        "cumulative_return": round(benchmark_return, 6),
        "relative_cumulative_return": round(strategy_cumulative_return - benchmark_return, 6),
    }


def max_gain_interval(nav_series: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    best_return = float("-inf")
    trough_nav = 1.0
    trough_date = str(nav_series[0]["date"])
    best_start = trough_date
    best_end = str(nav_series[0].get("exit_date") or trough_date)
    for row in nav_series:
        nav = float(row["nav"])
        current_date = str(row.get("exit_date") or row["date"])
        gain = nav / trough_nav - 1 if trough_nav > 0 else 0.0
        if gain > best_return:
            best_return = gain
            best_start = trough_date
            best_end = current_date
        if nav < trough_nav:
            trough_nav = nav
            trough_date = current_date
    return {
        "return": round(max(best_return, 0.0), 6),
        "start_date": best_start,
        "end_date": best_end,
    }


def max_drawdown_interval(nav_series: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    peak_nav = 1.0
    peak_date = str(nav_series[0]["date"])
    worst_return = 0.0
    worst_peak_date = peak_date
    worst_trough_date = peak_date
    for row in nav_series:
        nav = float(row["nav"])
        current_date = str(row.get("exit_date") or row["date"])
        if nav > peak_nav:
            peak_nav = nav
            peak_date = current_date
        drawdown = nav / peak_nav - 1 if peak_nav > 0 else 0.0
        if drawdown < worst_return:
            worst_return = drawdown
            worst_peak_date = peak_date
            worst_trough_date = current_date
    return {
        "return": round(worst_return, 6),
        "peak_date": worst_peak_date,
        "trough_date": worst_trough_date,
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number
