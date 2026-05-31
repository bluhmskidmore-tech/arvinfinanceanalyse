from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from backend.app.core_finance.factor_screen_candidates import (
    MAX_CANDIDATES,
    MAX_CANDIDATES_PER_INDUSTRY,
    TOP_PCT,
    _filter_factor_screen_universe,
)
from backend.app.core_finance.macro.equity_strategies import (
    DEFAULT_FACTOR_WEIGHTS,
    REQUIRED_FACTOR_INPUTS,
    _industry_neutralize_factors,
    compute_factors,
)

RULE_VERSION = "rv_macro_toolkit_shadow_portfolio_v1"
TABLES_USED = ["choice_stock_daily_observation", "choice_stock_factor_snapshot"]
COST_BPS = [0, 10, 20, 50]
FACTOR_INPUT_COLUMNS = [*REQUIRED_FACTOR_INPUTS, "industry"]
DEEP_VALUE_QUALITY_WEIGHTS = {
    "value": 0.45,
    "quality": 0.25,
    "momentum": 0.05,
    "low_vol": 0.10,
    "dividend": 0.15,
}
DUCKDB_BUSY_MARKERS = (
    "already open",
    "another program",
    "being used",
    "file is locked",
    "locked",
    "另一个程序",
    "正在使用",
)


@dataclass(frozen=True)
class PortfolioSpec:
    key: str
    label: str
    role: str
    weights: dict[str, float]
    pe_max: float | None = None
    pb_max: float | None = None
    turnover_cap: float | None = None


PORTFOLIOS = (
    PortfolioSpec(
        key="current_baseline",
        label="当前正式规则",
        role="production_reference",
        weights=dict(DEFAULT_FACTOR_WEIGHTS),
    ),
    PortfolioSpec(
        key="deep_value_quality_pe80",
        label="深度价值质量影子组合",
        role="shadow_candidate",
        weights=DEEP_VALUE_QUALITY_WEIGHTS,
        pe_max=80,
    ),
)


def compute_equity_shadow_portfolio_report(duckdb_path: str | Path) -> dict[str, object]:
    path = Path(duckdb_path)
    if not path.exists():
        return _unavailable_report(["DUCKDB_NOT_FOUND"])

    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        return _unavailable_report(_duckdb_open_warnings(exc))

    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        missing_tables = [table for table in TABLES_USED if table not in tables]
        if missing_tables:
            return _unavailable_report([f"MISSING_TABLES: {', '.join(missing_tables)}"])

        factor_dates = _factor_dates(conn)
        if len(factor_dates) < 2:
            return _insufficient_report(factor_dates, ["FACTOR_HISTORY_TOO_SHORT"])

        periods = list(zip(factor_dates[:-1], factor_dates[1:]))
        factors_by_date = {sample_date: _load_factor_snapshot(conn, sample_date) for sample_date in factor_dates}
        benchmark = _benchmark_result(conn, periods, factors_by_date)
        portfolio_payloads: list[dict[str, object]] = []
        period_payloads: list[dict[str, object]] = []
        for spec in PORTFOLIOS:
            portfolio, rows = _portfolio_result(conn, periods, factors_by_date, benchmark["period_returns"], spec)
            portfolio_payloads.append(portfolio)
            period_payloads.extend(rows)
        latest_date = factor_dates[-1]
        warnings = ["READ_ONLY_SHADOW_NOT_PRODUCTION"]
        if len(periods) < 12:
            warnings.append("SHORT_HISTORY")
        return {
            "status": "complete",
            "basis": "read_only_shadow",
            "label": "影子组合报告",
            "as_of_date": latest_date,
            "factor_dates": factor_dates,
            "completed_periods": len(periods),
            "rule_version": RULE_VERSION,
            "tables_used": list(TABLES_USED),
            "warnings": warnings,
            "cost_model": {
                "cost_bps": list(COST_BPS),
                "initial_build_included": True,
                "final_liquidation_included": False,
                "method": "cost_bps_applied_to_abs_weight_delta",
            },
            "benchmark": benchmark["payload"],
            "portfolios": portfolio_payloads,
            "period_returns": period_payloads,
        }
    except duckdb.Error as exc:
        return _unavailable_report([f"DUCKDB_QUERY_FAILED: {type(exc).__name__}"])
    finally:
        conn.close()


def _unavailable_report(warnings: list[str]) -> dict[str, object]:
    return {
        "status": "unavailable",
        "basis": "read_only_shadow",
        "label": "影子组合报告",
        "as_of_date": None,
        "factor_dates": [],
        "completed_periods": 0,
        "rule_version": RULE_VERSION,
        "tables_used": list(TABLES_USED),
        "warnings": ["READ_ONLY_SHADOW_NOT_PRODUCTION", *warnings],
        "cost_model": {
            "cost_bps": list(COST_BPS),
            "initial_build_included": True,
            "final_liquidation_included": False,
            "method": "cost_bps_applied_to_abs_weight_delta",
        },
        "benchmark": None,
        "portfolios": [],
        "period_returns": [],
    }


def _duckdb_open_warnings(exc: duckdb.Error) -> list[str]:
    warnings: list[str] = []
    message = str(exc).casefold()
    if any(marker.casefold() in message for marker in DUCKDB_BUSY_MARKERS):
        warnings.append("DUCKDB_BUSY")
    warnings.append(f"DUCKDB_OPEN_FAILED: {type(exc).__name__}")
    return warnings


def _insufficient_report(factor_dates: list[str], warnings: list[str]) -> dict[str, object]:
    report = _unavailable_report(warnings)
    report["status"] = "insufficient_history"
    report["factor_dates"] = factor_dates
    report["as_of_date"] = factor_dates[-1] if factor_dates else None
    return report


def _factor_dates(conn: duckdb.DuckDBPyConnection) -> list[str]:
    return [
        str(row[0])[:10]
        for row in conn.execute(
            """
            select distinct as_of_date
            from choice_stock_factor_snapshot
            where as_of_date is not null
            order by as_of_date
            """
        ).fetchall()
    ]


def _load_factor_snapshot(conn: duckdb.DuckDBPyConnection, as_of_date: str) -> pd.DataFrame:
    columns = ["stock_code", *FACTOR_INPUT_COLUMNS]
    frame = conn.execute(
        f"""
        select {", ".join(columns)}
        from choice_stock_factor_snapshot
        where as_of_date = ?
        """,
        [as_of_date],
    ).df()
    if frame.empty:
        return pd.DataFrame(columns=columns).set_index("stock_code")
    frame["stock_name"] = ""
    frame = frame.set_index("stock_code")
    numeric_columns = list(REQUIRED_FACTOR_INPUTS)
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    frame["industry"] = frame["industry"].astype(str).str.strip()
    frame = frame.dropna(subset=FACTOR_INPUT_COLUMNS)
    frame = frame[frame["industry"] != ""]
    return _filter_factor_screen_universe(frame)


def _benchmark_result(
    conn: duckdb.DuckDBPyConnection,
    periods: list[tuple[str, str]],
    factors_by_date: dict[str, pd.DataFrame],
) -> dict[str, object]:
    nav = 1.0
    max_nav = 1.0
    max_drawdown = 0.0
    period_returns: dict[tuple[str, str], float] = {}
    for start_date, end_date in periods:
        universe = factors_by_date[start_date]
        returns = _simple_returns(conn, start_date, end_date, list(universe.index))
        period_return = float(returns.mean()) if not returns.empty else 0.0
        period_returns[(start_date, end_date)] = period_return
        nav *= 1.0 + period_return
        max_nav = max(max_nav, nav)
        max_drawdown = min(max_drawdown, nav / max_nav - 1.0)
    return {
        "period_returns": period_returns,
        "payload": {
            "key": "equal_weight_factor_universe",
            "label": "因子池等权基准",
            "total_return": _round(nav - 1.0),
            "max_drawdown": _round(max_drawdown),
        },
    }


def _portfolio_result(
    conn: duckdb.DuckDBPyConnection,
    periods: list[tuple[str, str]],
    factors_by_date: dict[str, pd.DataFrame],
    benchmark_returns: dict[tuple[str, str], float],
    spec: PortfolioSpec,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    nav_by_cost = {cost_bps: 1.0 for cost_bps in COST_BPS}
    max_nav_by_cost = {cost_bps: 1.0 for cost_bps in COST_BPS}
    mdd_by_cost = {cost_bps: 0.0 for cost_bps in COST_BPS}
    wins_by_cost = {cost_bps: 0 for cost_bps in COST_BPS}
    previous_codes: set[str] | None = None
    previous_weights_by_cost: dict[int, dict[str, float]] = {cost_bps: {} for cost_bps in COST_BPS}
    name_turnovers: list[float] = []
    traded_notional: list[float] = []
    counts: list[int] = []
    pe_values: list[float] = []
    pb_values: list[float] = []
    period_payloads: list[dict[str, object]] = []

    for start_date, end_date in periods:
        universe = factors_by_date[start_date]
        ranked = _ranked_frame(_apply_constraints(universe, spec), spec.weights)
        selected = _select_with_caps(ranked, previous_codes=previous_codes, turnover_cap=spec.turnover_cap)
        selected_codes = list(selected.index)
        gross_return = _selection_return(conn, start_date, end_date, selected_codes)
        benchmark_return = benchmark_returns.get((start_date, end_date), 0.0)
        new_weights = _equal_weights(selected_codes)
        period_costs: list[dict[str, object]] = []
        if previous_codes is not None:
            name_turnovers.append(1.0 - len(previous_codes & set(selected_codes)) / max(len(previous_codes), 1))
        for cost_bps in COST_BPS:
            previous_weights = previous_weights_by_cost[cost_bps]
            traded = _traded_notional(previous_weights, new_weights)
            if cost_bps == 0:
                traded_notional.append(traded)
            cost = traded * cost_bps / 10_000.0
            net_return = (1.0 - cost) * (1.0 + gross_return) - 1.0
            nav_by_cost[cost_bps] *= 1.0 + net_return
            max_nav_by_cost[cost_bps] = max(max_nav_by_cost[cost_bps], nav_by_cost[cost_bps])
            mdd_by_cost[cost_bps] = min(
                mdd_by_cost[cost_bps],
                nav_by_cost[cost_bps] / max_nav_by_cost[cost_bps] - 1.0,
            )
            wins_by_cost[cost_bps] += int(net_return > benchmark_return)
            previous_weights_by_cost[cost_bps] = new_weights
            period_costs.append(
                {
                    "cost_bps": cost_bps,
                    "net_return": _round(net_return),
                    "cost": _round(cost),
                }
            )
        if not selected.empty:
            pe_values.append(float(pd.to_numeric(selected["pe"], errors="coerce").mean()))
            pb_values.append(float(pd.to_numeric(selected["pb"], errors="coerce").mean()))
        counts.append(len(selected_codes))
        period_payloads.append(
            {
                "portfolio_key": spec.key,
                "start_date": start_date,
                "end_date": end_date,
                "gross_return": _round(gross_return),
                "benchmark_return": _round(benchmark_return),
                "excess_return": _round(gross_return - benchmark_return),
                "selected_count": len(selected_codes),
                "name_turnover": _round(name_turnovers[-1]) if name_turnovers and previous_codes is not None else None,
                "traded_notional": _round(traded_notional[-1]) if traded_notional else None,
                "cost_results": period_costs,
            }
        )
        previous_codes = set(selected_codes)

    benchmark_nav = math.prod(1.0 + benchmark_returns[period] for period in periods) if periods else 1.0
    cost_results = [
        {
            "cost_bps": cost_bps,
            "total_return": _round(nav_by_cost[cost_bps] - 1.0),
            "excess_return": _round(nav_by_cost[cost_bps] / benchmark_nav - 1.0 if benchmark_nav else 0.0),
            "max_drawdown": _round(mdd_by_cost[cost_bps]),
            "win_rate": _round(wins_by_cost[cost_bps] / len(periods) if periods else 0.0),
        }
        for cost_bps in COST_BPS
    ]
    latest_ranked = _ranked_frame(_apply_constraints(factors_by_date[periods[-1][1]], spec), spec.weights) if periods else pd.DataFrame()
    latest_selected = _select_with_caps(latest_ranked, previous_codes=None, turnover_cap=None)
    return (
        {
            "key": spec.key,
            "label": spec.label,
            "role": spec.role,
            "total_return": cost_results[0]["total_return"],
            "excess_return": cost_results[0]["excess_return"],
            "max_drawdown": cost_results[0]["max_drawdown"],
            "win_rate": cost_results[0]["win_rate"],
            "average_turnover": _round(sum(name_turnovers) / len(name_turnovers)) if name_turnovers else None,
            "average_traded_notional": _round(sum(traded_notional) / len(traded_notional)) if traded_notional else None,
            "average_count": _round(sum(counts) / len(counts)) if counts else 0,
            "average_pe": _round(sum(pe_values) / len(pe_values)) if pe_values else None,
            "average_pb": _round(sum(pb_values) / len(pb_values)) if pb_values else None,
            "weights": {key: _round(value) for key, value in spec.weights.items()},
            "constraints": {
                "pe_max": spec.pe_max,
                "pb_max": spec.pb_max,
                "turnover_cap": spec.turnover_cap,
                "top_pct": TOP_PCT,
                "max_candidates": MAX_CANDIDATES,
                "max_per_industry": MAX_CANDIDATES_PER_INDUSTRY,
            },
            "cost_results": cost_results,
            "latest_holdings": _latest_holdings(latest_selected),
        },
        period_payloads,
    )


def _ranked_frame(frame: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    if frame.empty:
        result = frame.copy()
        result["score"] = pd.Series(dtype="float64")
        return result
    factors = compute_factors(frame)
    factors = _industry_neutralize_factors(factors, frame["industry"])
    score = pd.Series(0.0, index=factors.index, dtype="float64")
    for column, weight in weights.items():
        score = score.add(factors[column] * float(weight), fill_value=0.0)
    ranked = frame.copy()
    ranked["score"] = score
    return ranked.sort_values("score", ascending=False)


def _apply_constraints(frame: pd.DataFrame, spec: PortfolioSpec) -> pd.DataFrame:
    constrained = frame
    if spec.pe_max is not None:
        constrained = constrained[pd.to_numeric(constrained["pe"], errors="coerce") <= spec.pe_max]
    if spec.pb_max is not None:
        constrained = constrained[pd.to_numeric(constrained["pb"], errors="coerce") <= spec.pb_max]
    return constrained


def _select_with_caps(
    ranked: pd.DataFrame,
    *,
    previous_codes: set[str] | None,
    turnover_cap: float | None,
) -> pd.DataFrame:
    if ranked.empty:
        return ranked.head(0)
    top_pool_size = max(int(len(ranked) * TOP_PCT), 1)
    selected_codes: list[str] = []
    industry_counts: Counter[str] = Counter()
    if previous_codes and turnover_cap is not None:
        max_replace = int(math.floor(len(previous_codes) * turnover_cap))
        min_keep = max(len(previous_codes) - max_replace, 0)
        for stock_code in [code for code in ranked.index if code in previous_codes]:
            _add_candidate(selected_codes, industry_counts, ranked, str(stock_code))
            if len(selected_codes) >= min_keep:
                break
    for stock_code in ranked.head(top_pool_size).index:
        _add_candidate(selected_codes, industry_counts, ranked, str(stock_code))
        if len(selected_codes) >= MAX_CANDIDATES:
            break
    return ranked.loc[selected_codes]


def _add_candidate(
    selected_codes: list[str],
    industry_counts: Counter[str],
    ranked: pd.DataFrame,
    stock_code: str,
) -> None:
    if stock_code in selected_codes or stock_code not in ranked.index:
        return
    industry = str(ranked.loc[stock_code, "industry"])
    if industry_counts[industry] >= MAX_CANDIDATES_PER_INDUSTRY:
        return
    selected_codes.append(stock_code)
    industry_counts[industry] += 1


def _selection_return(
    conn: duckdb.DuckDBPyConnection,
    start_date: str,
    end_date: str,
    stock_codes: list[str],
) -> float:
    returns = _simple_returns(conn, start_date, end_date, stock_codes)
    return float(returns.mean()) if not returns.empty else 0.0


def _simple_returns(
    conn: duckdb.DuckDBPyConnection,
    start_date: str,
    end_date: str,
    stock_codes: list[str],
) -> pd.Series:
    if not stock_codes:
        return pd.Series(dtype="float64")
    frame = conn.execute(
        """
        select stock_code, trade_date, close_value
        from choice_stock_daily_observation
        where trade_date in (?, ?)
          and stock_code = any(?)
        """,
        [start_date, end_date, stock_codes],
    ).df()
    if frame.empty:
        return pd.Series(dtype="float64")
    pivot = frame.pivot(index="stock_code", columns="trade_date", values="close_value")
    pivot.columns = [str(column)[:10] for column in pivot.columns]
    if start_date not in pivot.columns or end_date not in pivot.columns:
        return pd.Series(dtype="float64")
    returns = pivot[end_date] / pivot[start_date] - 1.0
    return pd.to_numeric(returns, errors="coerce").replace([math.inf, -math.inf], pd.NA).dropna()


def _equal_weights(stock_codes: list[str]) -> dict[str, float]:
    if not stock_codes:
        return {}
    weight = 1.0 / len(stock_codes)
    return {stock_code: weight for stock_code in stock_codes}


def _traded_notional(previous_weights: dict[str, float], new_weights: dict[str, float]) -> float:
    return sum(
        abs(new_weights.get(stock_code, 0.0) - previous_weights.get(stock_code, 0.0))
        for stock_code in set(previous_weights) | set(new_weights)
    )


def _latest_holdings(selected: pd.DataFrame) -> list[dict[str, Any]]:
    holdings: list[dict[str, Any]] = []
    for rank, (stock_code, row) in enumerate(selected.head(10).iterrows(), start=1):
        holdings.append(
            {
                "rank": rank,
                "stock_code": str(stock_code),
                "industry": str(row.get("industry") or ""),
                "score": _round(row.get("score")),
                "pe": _round(row.get("pe")),
                "pb": _round(row.get("pb")),
                "three_month_return": _round(row.get("three_month_return")),
            }
        )
    return holdings


def _round(value: object, digits: int = 6) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return round(number, digits)
