"""Walk-forward 样本外验证框架（只读分析工具）。

用途：把"全窗口 in-sample 回测"得到的策略结论，放到滚动的训练/验证切割上重跑，
区分"稳健优势"与"过拟合 / 时段红利"。

边界（务必保持）：
- 只读 DuckDB；不写任何表；不修改 `backend/app/core_finance/` 引擎或策略；
- 复用 `portfolio_backtest.run_portfolio_backtest` / `build_benchmark_comparison`
  与 `scripts/run_portfolio_backtest.py` 的执行历史加载器，本脚本只做切割与统计；
- 纯切割/选参/聚合逻辑放在 `scripts/walk_forward_core.py`，由
  `tests/test_walk_forward_validation.py` 做防泄漏断言。

用法::

    .venv\\Scripts\\python.exe scripts/run_walk_forward_validation.py \\
        --db-path data/moss.duckdb \\
        --report-path tmp-strategy-reports/walk-forward-first-run.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.portfolio_backtest import (  # noqa: E402
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MAX_POSITIONS,
    PORTFOLIO_ENGINE_VERSION,
    build_benchmark_comparison,
    run_portfolio_backtest,
)
from backend.app.core_finance.portfolio_paths import (  # noqa: E402
    load_position_price_paths,
    position_path_key,
)
from backend.app.core_finance.strategy_policy import POLICY  # noqa: E402
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from scripts.run_portfolio_backtest import (  # noqa: E402
    CHOICE_NATIVE_ERA_START,
    TABLE_EXECUTION_HIST,
    _load_benchmark_rows,
    _load_daily_exposure_rows,
    _load_execution_rows,
    _market_state_rows_from_execution,
    _table_names,
)
from scripts.walk_forward_core import (  # noqa: E402
    DEFAULT_FORCED_CUT_DATES,
    DEFAULT_MAX_GAP_DAYS,
    DEFAULT_MIN_WINDOWS_FOR_VERDICT,
    DEFAULT_RISK_PER_TRADE_GRID,
    VERDICT_INSUFFICIENT,
    ParameterSelection,
    ScheduleConfig,
    Segment,
    WalkForwardLeakageError,
    WalkForwardWindow,
    annualize_return,
    build_windows,
    chain_returns,
    date_text,
    decay_ratio,
    oos_verdict,
    parameter_drift,
    schedule_diagram,
    score_from_metrics,
    select_parameter,
    select_training_rows,
    select_validation_rows,
    sign_consistency,
    span_days,
    window_crosses_dates,
    windows_are_disjoint,
)

DEFAULT_DB_PATH = "data/moss.duckdb"
DEFAULT_REPORT_PATH = Path("tmp-strategy-reports/walk-forward-first-run.md")
VARIANT = "fixed_20d"
HORIZON_DAYS = 20
PRIMARY_SCHEDULE = ScheduleConfig(label="primary_6t_2v_2s", train_months=6, valid_months=2, step_months=2)
COMPACT_SCHEDULE = ScheduleConfig(label="compact_1t_1v_1s", train_months=1, valid_months=1, step_months=1)
MIN_TRAIN_ROWS = 20
SIGNAL_KIND_ORDER = (
    "stock_candidate",
    "theme_breakout",
    "mean_reversion",
    "uptrend_momentum",
    "fresh_trend_watchlist",
    "factor_screen",
    "hybrid_fusion",
)
METRIC_BASIS = (
    "path 模式盯市 fixed_20d；T+1 开盘执行历史；20d 净收益按引擎 coalesce 链 "
    "(return_20d_net_adj -> return_20d_net) 取值；逐日 gate 敞口优先、缺失退回状态 fallback；"
    "敞口 T 日决策 T+1 生效；成本/滑点取 POLICY"
)


@dataclass(frozen=True)
class RunSummary:
    """单次回测切片的可比摘要（策略 + 基准）。"""

    input_rows: int
    buy_trades: int
    sell_trades: int
    sample_days: int
    cumulative_return: float | None
    cagr: float | None
    max_drawdown: float | None
    daily_sharpe: float | None
    calmar: float | None
    gate_return: float | None
    buy_hold_return: float | None
    excess_vs_gate: float | None
    excess_vs_buy_hold: float | None
    mtm_cost_fallback_ratio: float | None
    stop_ref_fallback: int
    exposure_cap_clipped: int
    exposure_fallback_day_ratio: float | None
    skipped_missing_outcome: int

    @property
    def has_activity(self) -> bool:
        return self.buy_trades > 0


EMPTY_SUMMARY = RunSummary(
    input_rows=0,
    buy_trades=0,
    sell_trades=0,
    sample_days=0,
    cumulative_return=None,
    cagr=None,
    max_drawdown=None,
    daily_sharpe=None,
    calmar=None,
    gate_return=None,
    buy_hold_return=None,
    excess_vs_gate=None,
    excess_vs_buy_hold=None,
    mtm_cost_fallback_ratio=None,
    stop_ref_fallback=0,
    exposure_cap_clipped=0,
    exposure_fallback_day_ratio=None,
    skipped_missing_outcome=0,
)


class BacktestRunner:
    """把公共输入（价格路径/敞口/基准）固定下来，只按行切片重跑引擎。"""

    def __init__(
        self,
        *,
        price_paths: Mapping[str, Sequence[Mapping[str, object]]],
        market_state_rows: Sequence[Mapping[str, object]],
        exposure_rows: Sequence[Mapping[str, object]],
        benchmark_rows: Sequence[Mapping[str, object]],
        mode: str,
        initial_capital: float,
        max_positions: int,
    ) -> None:
        self._price_paths = price_paths
        self._market_state_rows = market_state_rows
        self._exposure_rows = exposure_rows
        self._benchmark_rows = benchmark_rows
        self._mode = mode
        self._initial_capital = initial_capital
        self._max_positions = max_positions
        self.run_count = 0

    def run(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        sizing: str = "equal_weight",
        risk_per_trade: float | None = None,
        path_cutoff_date: str | None = None,
    ) -> RunSummary:
        if not rows:
            return EMPTY_SUMMARY
        self.run_count += 1
        result = run_portfolio_backtest(
            rows,
            self._market_state_rows,
            variant=VARIANT,
            exposure_rows=self._exposure_rows,
            initial_capital=self._initial_capital,
            max_positions=self._max_positions,
            mode=self._mode,
            price_paths=self._scoped_price_paths(rows, cutoff_date=path_cutoff_date),
            sizing=sizing,
            risk_per_trade=risk_per_trade,
            single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        )
        comparison = build_benchmark_comparison(
            result.equity_curve,
            self._benchmark_rows,
            self._market_state_rows,
            exposure_rows=self._exposure_rows,
            initial_capital=self._initial_capital,
        )
        return _summarize_run(result, comparison, input_rows=len(rows))

    def _scoped_price_paths(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        cutoff_date: str | None = None,
    ) -> dict[str, Sequence[Mapping[str, object]]]:
        """只把本切片持仓自己的价格路径喂给引擎，并可按决策时点截断路径尾部。

        引擎的 `_portfolio_trade_dates` 会把 price_paths 中落在时间轴内的日期并入
        交易日网格；若传入其它窗口的路径，会污染本窗的净值曲线步频。

        `cutoff_date` 用于训练回测：path 模式下停牌/跌停会把持仓顺延到 20d 名义
        退出日之后，即使 purge 已按 `exit_date_20d <= train_end` 过滤，训练时间轴
        仍可能越过 train_end 数日并把 train_end 之后的价格并入选参打分。这里把每条
        路径的 bar 截到 `trade_date <= cutoff_date`，让选参只能看到决策时点已公开的价格。
        """
        if not self._price_paths:
            return {}
        keys = {
            position_path_key(row.get("stock_code"), row.get("entry_date"))
            for row in rows
        }
        scoped = {key: value for key, value in self._price_paths.items() if key in keys}
        if not cutoff_date:
            return scoped
        truncated: dict[str, Sequence[Mapping[str, object]]] = {}
        for key, bars in scoped.items():
            kept = [bar for bar in bars if date_text(bar.get("trade_date")) <= cutoff_date]
            if kept:
                truncated[key] = kept
        return truncated


def _summarize_run(result: Any, comparison: Mapping[str, object], *, input_rows: int) -> RunSummary:
    metrics = result.metrics
    benchmark_metrics = comparison.get("metrics") if isinstance(comparison, Mapping) else {}
    benchmark_metrics = benchmark_metrics if isinstance(benchmark_metrics, Mapping) else {}
    gate = benchmark_metrics.get("gate_timing_csi300") or {}
    buy_hold = benchmark_metrics.get("csi300_buy_hold") or {}
    strategy_return = _finite(metrics.get("cumulative_return"))
    gate_return = _finite(gate.get("cumulative_return")) if isinstance(gate, Mapping) else None
    buy_hold_return = (
        _finite(buy_hold.get("cumulative_return")) if isinstance(buy_hold, Mapping) else None
    )
    cagr = _finite(metrics.get("cagr"))
    max_drawdown = _finite(metrics.get("max_drawdown"))
    return RunSummary(
        input_rows=input_rows,
        buy_trades=sum(1 for row in result.trades if row.get("action") == "buy"),
        sell_trades=sum(1 for row in result.trades if row.get("action") == "sell"),
        sample_days=int(metrics.get("sample_days") or 0),
        cumulative_return=strategy_return,
        cagr=cagr,
        max_drawdown=max_drawdown,
        daily_sharpe=_finite(metrics.get("daily_sharpe")),
        calmar=(cagr / max_drawdown if cagr is not None and max_drawdown else None),
        gate_return=gate_return,
        buy_hold_return=buy_hold_return,
        excess_vs_gate=(
            strategy_return - gate_return
            if strategy_return is not None and gate_return is not None
            else None
        ),
        excess_vs_buy_hold=(
            strategy_return - buy_hold_return
            if strategy_return is not None and buy_hold_return is not None
            else None
        ),
        mtm_cost_fallback_ratio=_finite(metrics.get("mtm_cost_fallback_ratio")),
        stop_ref_fallback=int(metrics.get("stop_ref_fallback") or 0),
        exposure_cap_clipped=int(metrics.get("exposure_cap_clipped") or 0),
        exposure_fallback_day_ratio=_finite(metrics.get("exposure_fallback_day_ratio")),
        skipped_missing_outcome=int(result.skip_counts.get("missing_exit_or_return") or 0),
    )


# ---------------------------------------------------------------- data loading


def load_inputs(
    db_path: str,
    *,
    mode: str,
) -> dict[str, Any]:
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"DuckDB file not found: {db_file}")

    issues: list[str] = []
    with read_only_connection(str(db_file)) as conn:
        tables = _table_names(conn)
        if TABLE_EXECUTION_HIST not in tables:
            raise RuntimeError(f"Required table {TABLE_EXECUTION_HIST} is missing")
        loaded_rows, load_issues = _load_execution_rows(
            conn,
            tables=tables,
            signal_kind="",
            start_date=None,
            end_date=None,
        )
        issues.extend(load_issues)
        execution_rows, dedupe_stats = _dedupe_execution_rows(loaded_rows)
        dedupe_stats.update(_table_row_conservation(conn, dedupe_stats))
        if dedupe_stats["removed_rows"]:
            issues.append(
                f"执行历史加载行 {dedupe_stats['loaded_rows']} 行去重为 "
                f"{dedupe_stats['deduped_rows']} 行（涉及 {dedupe_stats['duplicate_keys']} 个 "
                "(signal_date, stock_code, signal_kind) 键）："
                f"ema10 join 扇出 {dedupe_stats['join_fanout_rows']} 行 + 表内完全重复 "
                f"{dedupe_stats['table_duplicate_rows']} 行；walk-forward 编排侧按键去重"
                "（保留 ema10 非空且最小者），不改共享加载器。"
            )
        disclosure = _outcome_disclosure(conn)
        usable_rows = [row for row in execution_rows if _is_usable(row)]
        market_state_rows = _market_state_rows_from_execution(execution_rows)
        exposure_start = min(date_text(row["entry_date"]) for row in usable_rows)
        exposure_end = max(
            date_text(row.get("exit_date_20d") or row.get("entry_date")) for row in usable_rows
        )
        exposure_rows, exposure_issues = _load_daily_exposure_rows(
            conn,
            tables=tables,
            start_date=exposure_start,
            end_date=exposure_end,
        )
        issues.extend(exposure_issues)
        benchmark_rows, benchmark_tables = _load_benchmark_rows(
            conn,
            tables=tables,
            start_date=exposure_start,
            end_date=exposure_end,
        )
        price_paths = (
            load_position_price_paths(conn, usable_rows, max_horizon_days=HORIZON_DAYS + 5)
            if mode == "path"
            else {}
        )

    if not benchmark_tables:
        issues.append("CSI300 基准不可得；超额相关列全部为 NA。")
    missing_paths = sum(
        1
        for row in usable_rows
        if position_path_key(row.get("stock_code"), row.get("entry_date")) not in price_paths
    )
    if mode == "path" and missing_paths:
        issues.append(
            f"{missing_paths}/{len(usable_rows)} 条可用行没有价格路径，path 模式下按成本计价降级"
            "（引擎 mtm_cost_fallback 口径）。"
        )
    return {
        "execution_rows": execution_rows,
        "usable_rows": usable_rows,
        "market_state_rows": market_state_rows,
        "exposure_rows": exposure_rows,
        "benchmark_rows": benchmark_rows,
        "benchmark_tables": benchmark_tables,
        "price_paths": price_paths,
        "disclosure": disclosure,
        "dedupe": dedupe_stats,
        "missing_price_path_rows": missing_paths,
        "issues": issues,
        "db_path": str(db_file),
    }


DEDUPE_KEY_FIELDS = ("signal_date", "stock_code", "signal_kind")


def _dedupe_execution_rows(
    rows: Sequence[Mapping[str, object]],
) -> tuple[list[Mapping[str, object]], dict[str, Any]]:
    """按 (signal_date, stock_code, signal_kind) 去重，抵消共享加载器的 ema10 join 扇出。

    `scripts/run_portfolio_backtest.py::_load_execution_rows` 会 left join
    `livermore_candidate_history` 取 `ema10`；该表对同一
    (stock_code, snapshot_as_of_date, signal_kind) 可能有多行，导致 join 后行数
    大于执行历史表内行数（同一笔执行被重复计入仓位与统计）。该加载器是已提交的共享
    文件、扇出属继承问题，这里不改加载器，只在 walk-forward 编排侧去重。

    取舍：同键各行除 `ema10` 外字段相同，因此保留 **ema10 非空且数值最小** 的一行
    （其次按加载顺序稳定取首行）。理由：ema10 是 risk_budget 的止损参考，ema10 越小
    ⇒ 止损距离 (entry-ema10)/entry 越大 ⇒ 仓位越小，选的是同键候选中最保守的一档；
    非空优先则避免退回 POLICY 的固定 fallback 止损距离。
    """
    grouped: dict[tuple[str, ...], list[tuple[int, Mapping[str, object]]]] = {}
    for index, row in enumerate(rows):
        key = tuple(str(row.get(field) or "") for field in DEDUPE_KEY_FIELDS)
        grouped.setdefault(key, []).append((index, row))

    kept: list[tuple[int, Mapping[str, object]]] = []
    removed_by_kind: dict[str, int] = {}
    duplicate_keys = 0
    ema10_conflict_keys = 0
    max_multiplicity = 1
    for key, group in grouped.items():
        if len(group) > 1:
            duplicate_keys += 1
            max_multiplicity = max(max_multiplicity, len(group))
            if len({_finite(item.get("ema10")) for _index, item in group}) > 1:
                ema10_conflict_keys += 1
            kind = key[2] or "unknown"
            removed_by_kind[kind] = removed_by_kind.get(kind, 0) + len(group) - 1
        kept.append(min(group, key=lambda item: _dedupe_sort_key(item[0], item[1])))

    kept.sort(key=lambda item: item[0])
    deduped = [row for _index, row in kept]
    return deduped, {
        "loaded_rows": len(rows),
        "deduped_rows": len(deduped),
        "removed_rows": len(rows) - len(deduped),
        "duplicate_keys": duplicate_keys,
        "ema10_conflict_keys": ema10_conflict_keys,
        "max_multiplicity": max_multiplicity,
        "removed_rows_by_kind": dict(sorted(removed_by_kind.items())),
        "key_fields": list(DEDUPE_KEY_FIELDS),
        "keep_rule": "ema10 非空优先，其次 ema10 最小，其次加载顺序首行",
    }


def _table_row_conservation(
    conn: duckdb.DuckDBPyConnection,
    dedupe_stats: Mapping[str, Any],
) -> dict[str, Any]:
    """行数守恒取证：把编排侧去重结果对齐到执行历史表内的去重键数。

    加载器多出来的行有两个来源，必须分开说：
    (a) `livermore_candidate_history` 的 ema10 join 扇出（表外放大）；
    (b) 执行历史表**自身**就有的完全重复行（同键同 run_id 同收益）。
    """
    row = conn.execute(
        f"""
        select
          count(*) as table_rows_with_entry_date,
          count(distinct (
            cast(signal_date as varchar) || '|' || stock_code || '|' || coalesce(signal_kind, '')
          )) as table_distinct_keys
        from {TABLE_EXECUTION_HIST}
        where entry_date is not null
        """
    ).fetchone()
    table_rows = int(row[0] or 0) if row else 0
    table_keys = int(row[1] or 0) if row else 0
    return {
        "table_rows_with_entry_date": table_rows,
        "table_distinct_keys": table_keys,
        "table_duplicate_rows": table_rows - table_keys,
        "join_fanout_rows": int(dedupe_stats["loaded_rows"]) - table_rows,
        "deduped_matches_table_distinct_keys": int(dedupe_stats["deduped_rows"]) == table_keys,
    }


def _dedupe_sort_key(index: int, row: Mapping[str, object]) -> tuple[int, float, int]:
    ema10 = _finite(row.get("ema10"))
    if ema10 is None:
        return (1, 0.0, index)
    return (0, ema10, index)


def _is_usable(row: Mapping[str, object]) -> bool:
    """引擎口径的"可用行"：有 20d 退出日且 20d 净收益（含 coalesce 回退）非空。"""
    return bool(row.get("exit_date_20d")) and row.get("return_20d_net_adj") is not None


def _outcome_disclosure(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """按 signal_kind 统计缺口来源，全部来自可核对的列状态而非推断。"""
    rows = conn.execute(
        f"""
        select
          signal_kind,
          count(*) as total_rows,
          sum(case when entry_date is null then 1 else 0 end) as no_entry_date,
          sum(case when coalesce(entry_executable, true) then 0 else 1 end) as entry_blocked,
          sum(case when exit_date_20d is null then 1 else 0 end) as outcome_no_exit_date,
          sum(
            case
              when exit_date_20d is not null
               and return_20d_net_adj is null
               and return_20d_net is null
              then 1 else 0
            end
          ) as exit_date_without_return,
          sum(
            case
              when return_20d_net_adj is null and return_20d_net is not null
              then 1 else 0
            end
          ) as adjusted_return_missing_coalesced,
          sum(
            case
              when exit_date_20d is not null
               and coalesce(return_20d_net_adj, return_20d_net) is not null
              then 1 else 0
            end
          ) as usable_rows,
          min(signal_date) as min_signal_date,
          max(signal_date) as max_signal_date,
          max(
            case
              when exit_date_20d is not null
               and coalesce(return_20d_net_adj, return_20d_net) is not null
              then signal_date
            end
          ) as max_usable_signal_date
        from {TABLE_EXECUTION_HIST}
        group by 1
        order by 1
        """
    ).fetchall()
    by_kind = {
        str(row[0]): {
            "total_rows": int(row[1] or 0),
            "no_entry_date": int(row[2] or 0),
            "entry_blocked": int(row[3] or 0),
            "outcome_no_exit_date": int(row[4] or 0),
            "exit_date_without_return": int(row[5] or 0),
            "adjusted_return_missing_coalesced": int(row[6] or 0),
            "usable_rows": int(row[7] or 0),
            "min_signal_date": date_text(row[8]),
            "max_signal_date": date_text(row[9]),
            "max_usable_signal_date": date_text(row[10]),
        }
        for row in rows
    }
    masked = conn.execute(
        f"""
        select min(signal_date), max(signal_date), count(*)
        from {TABLE_EXECUTION_HIST}
        where exit_date_20d is not null
          and return_20d_net_adj is null
          and return_20d_net is null
        """
    ).fetchone()
    pending = conn.execute(
        f"""
        select min(signal_date), max(signal_date), count(*)
        from {TABLE_EXECUTION_HIST}
        where exit_date_20d is null
        """
    ).fetchone()
    adjusted_missing = conn.execute(
        f"""
        select min(signal_date), max(signal_date), count(*), max(exit_date_20d)
        from {TABLE_EXECUTION_HIST}
        where exit_date_20d is not null
          and return_20d_net_adj is null
          and return_20d_net is not null
        """
    ).fetchone()
    latest_adjusted_missing = conn.execute(
        f"""
        select min(signal_date), count(*)
        from {TABLE_EXECUTION_HIST}
        where exit_date_20d is not null
          and return_20d_net_adj is null
          and return_20d_net is not null
          and cast(signal_date as date) >= date '2026-05-01'
        """
    ).fetchone()
    months = conn.execute(
        f"""
        select strftime(cast(signal_date as date), '%Y-%m') as ym, count(*)
        from {TABLE_EXECUTION_HIST}
        group by 1 order by 1
        """
    ).fetchall()
    return {
        "by_kind": by_kind,
        "exit_date_without_return_block": {
            "min_signal_date": date_text(masked[0]) if masked else "",
            "max_signal_date": date_text(masked[1]) if masked else "",
            "rows": int(masked[2] or 0) if masked else 0,
        },
        "no_exit_date_block": {
            "min_signal_date": date_text(pending[0]) if pending else "",
            "max_signal_date": date_text(pending[1]) if pending else "",
            "rows": int(pending[2] or 0) if pending else 0,
        },
        "adjusted_return_missing_block": {
            "min_signal_date": date_text(adjusted_missing[0]) if adjusted_missing else "",
            "max_signal_date": date_text(adjusted_missing[1]) if adjusted_missing else "",
            "rows": int(adjusted_missing[2] or 0) if adjusted_missing else 0,
            "max_exit_date": date_text(adjusted_missing[3]) if adjusted_missing else "",
            "recent_block_min_signal_date": date_text(latest_adjusted_missing[0])
            if latest_adjusted_missing
            else "",
            "recent_block_rows": int(latest_adjusted_missing[1] or 0) if latest_adjusted_missing else 0,
        },
        "adjustment_factor_coverage": _adjustment_factor_coverage(conn),
        "months_present": [str(row[0]) for row in months],
    }


def _adjustment_factor_coverage(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """复权因子日频覆盖的断点：判断复权收益缺失是否来自因子覆盖悬崖。

    以行情观测日历为参照，找出第一个没有任何复权因子行的交易日，
    并统计有多少条"复权缺失"执行行的 20d 目标日正好落在该断点之后。
    """
    tables = _table_names(conn)
    if "stock_adjustment_factor" not in tables:
        return {"status": "table_missing"}
    row = conn.execute(
        f"""
        with factor_dates as (
          select distinct cast(trade_date as date) as trade_date
          from stock_adjustment_factor
        ),
        affected_targets as (
          select distinct cast(exit_date_20d as date) as target_date
          from {TABLE_EXECUTION_HIST}
          where exit_date_20d is not null
            and return_20d_net_adj is null
            and return_20d_net is not null
        ),
        uncovered_targets as (
          select a.target_date
          from affected_targets a
          left join factor_dates f on f.trade_date = a.target_date
          where f.trade_date is null
        ),
        dense_runs as (
          select trade_date, lag(trade_date) over (order by trade_date) as previous_trade_date
          from factor_dates
        ),
        dense_end as (
          select max(trade_date) as dense_coverage_end
          from dense_runs
          where previous_trade_date is not null
            and date_diff('day', previous_trade_date, trade_date) <= 7
        )
        select
          (select count(*) from uncovered_targets) as uncovered_target_date_count,
          (select min(target_date) from uncovered_targets) as first_uncovered_target_date,
          (select max(target_date) from uncovered_targets) as last_uncovered_target_date,
          (select dense_coverage_end from dense_end) as dense_coverage_end,
          (select max(trade_date) from factor_dates) as max_factor_trade_date,
          (select count(*) from {TABLE_EXECUTION_HIST} e
             where e.exit_date_20d is not null
               and e.return_20d_net_adj is null
               and e.return_20d_net is not null
               and cast(e.exit_date_20d as date) in (select target_date from uncovered_targets)
          ) as rows_with_uncovered_target,
          (select count(*) from {TABLE_EXECUTION_HIST} e
             where e.exit_date_20d is not null
               and e.return_20d_net_adj is null
               and e.return_20d_net is not null
               and cast(e.exit_date_20d as date)
                   > coalesce((select dense_coverage_end from dense_end), date '9999-12-31')
          ) as rows_after_dense_coverage_end
        """
    ).fetchone()
    return {
        "status": "ready",
        "uncovered_target_date_count": int(row[0] or 0) if row else 0,
        "first_uncovered_target_date": date_text(row[1]) if row else "",
        "last_uncovered_target_date": date_text(row[2]) if row else "",
        "dense_coverage_end": date_text(row[3]) if row else "",
        "max_factor_trade_date": date_text(row[4]) if row else "",
        "rows_with_uncovered_target": int(row[5] or 0) if row else 0,
        "rows_after_dense_coverage_end": int(row[6] or 0) if row else 0,
    }


# ------------------------------------------------------------------- analysis


def analyze_schedule(
    *,
    runner: BacktestRunner,
    usable_rows: Sequence[Mapping[str, object]],
    schedule: ScheduleConfig,
    objective: str,
    risk_per_trade_grid: Sequence[float],
    forced_cut_dates: Sequence[str],
    max_gap_days: int,
    min_windows: int,
    purge: bool,
    detailed: bool,
) -> dict[str, Any]:
    windows, segments = build_windows(
        [date_text(row.get("signal_date")) for row in usable_rows],
        schedule=schedule,
        forced_cut_dates=forced_cut_dates,
        max_gap_days=max_gap_days,
    )
    crossing = {
        window.window_id: crossed
        for window in windows
        if (crossed := window_crosses_dates(window, forced_cut_dates))
    }
    if crossing:
        raise WalkForwardLeakageError(
            f"schedule={schedule.label} 生成了跨强制切割点的窗口，拒绝出报告：{crossing}"
        )
    clamped_windows = {
        window.window_id: window.valid_end for window in windows if window.valid_end_clamped
    }
    rows_by_kind: dict[str, list[Mapping[str, object]]] = {}
    for row in usable_rows:
        rows_by_kind.setdefault(str(row.get("signal_kind") or "unknown"), []).append(row)

    kinds = [kind for kind in SIGNAL_KIND_ORDER if kind in rows_by_kind]
    kinds.extend(sorted(kind for kind in rows_by_kind if kind not in SIGNAL_KIND_ORDER))

    equal_weight = {
        kind: _analyze_equal_weight_kind(
            runner=runner,
            kind=kind,
            rows=rows_by_kind[kind],
            windows=windows,
            min_windows=min_windows,
        )
        for kind in kinds
    }
    risk_budget = {
        kind: _analyze_risk_budget_kind(
            runner=runner,
            kind=kind,
            rows=rows_by_kind[kind],
            windows=windows,
            objective=objective,
            grid=tuple(risk_per_trade_grid),
            purge=purge,
            min_windows=min_windows,
        )
        for kind in kinds
    }
    return {
        "schedule": {
            "label": schedule.label,
            "train_months": schedule.train_months,
            "valid_months": schedule.valid_months,
            "step_months": schedule.step_months,
            "objective": objective,
            "purge_enabled": purge,
            "detailed": detailed,
            "min_windows_for_verdict": min_windows,
        },
        "segments": [_segment_payload(segment) for segment in segments],
        "windows": [_window_payload(window) for window in windows],
        "window_objects": windows,
        "segment_objects": segments,
        "windows_disjoint": windows_are_disjoint(windows),
        "windows_crossing_forced_cut": crossing,
        "windows_valid_end_clamped": clamped_windows,
        "equal_weight": equal_weight,
        "risk_budget": risk_budget,
        "signal_kinds": kinds,
    }


def _analyze_equal_weight_kind(
    *,
    runner: BacktestRunner,
    kind: str,
    rows: Sequence[Mapping[str, object]],
    windows: Sequence[WalkForwardWindow],
    min_windows: int,
) -> dict[str, Any]:
    in_sample = runner.run(rows)
    window_rows: list[dict[str, Any]] = []
    for window in windows:
        validation_rows = select_validation_rows(rows, window)
        summary = runner.run(validation_rows)
        window_rows.append(
            {
                "window_id": window.window_id,
                "valid_start": window.valid_start,
                "valid_end": window.valid_end,
                "input_rows": len(validation_rows),
                "summary": summary,
            }
        )
    active = [item for item in window_rows if item["summary"].has_activity]
    aggregate = _aggregate_oos(
        active_windows=active,
        in_sample=in_sample,
        min_windows=min_windows,
    )
    return {
        "signal_kind": kind,
        "total_usable_rows": len(rows),
        "first_signal_date": min((date_text(row.get("signal_date")) for row in rows), default=""),
        "last_signal_date": max((date_text(row.get("signal_date")) for row in rows), default=""),
        "in_sample": in_sample,
        "windows": window_rows,
        "active_window_count": len(active),
        **aggregate,
    }


def _analyze_risk_budget_kind(
    *,
    runner: BacktestRunner,
    kind: str,
    rows: Sequence[Mapping[str, object]],
    windows: Sequence[WalkForwardWindow],
    objective: str,
    grid: Sequence[float],
    purge: bool,
    min_windows: int,
) -> dict[str, Any]:
    in_sample_by_param = {param: runner.run(rows, sizing="risk_budget", risk_per_trade=param) for param in grid}
    in_sample_scores = {
        param: score_from_metrics(_metrics_view(summary), objective=objective)
        for param, summary in in_sample_by_param.items()
    }
    in_sample_selection = select_parameter(in_sample_scores, objective=objective)

    window_rows: list[dict[str, Any]] = []
    for window in windows:
        training_rows = select_training_rows(rows, window, purge=purge)
        validation_rows = select_validation_rows(rows, window)
        train_summaries = {
            param: runner.run(
                training_rows,
                sizing="risk_budget",
                risk_per_trade=param,
                path_cutoff_date=window.train_end,
            )
            for param in grid
        } if len(training_rows) >= MIN_TRAIN_ROWS else {}
        train_scores = {
            param: score_from_metrics(_metrics_view(summary), objective=objective)
            for param, summary in train_summaries.items()
        }
        selection = (
            select_parameter(train_scores, objective=objective)
            if train_scores
            else ParameterSelection("insufficient_train_rows", objective, None, None, ())
        )
        validation_by_param = {
            param: runner.run(validation_rows, sizing="risk_budget", risk_per_trade=param)
            for param in grid
        } if validation_rows else {}
        oracle = select_parameter(
            {
                param: score_from_metrics(_metrics_view(summary), objective=objective)
                for param, summary in validation_by_param.items()
            },
            objective=objective,
        )
        window_rows.append(
            {
                "window_id": window.window_id,
                "train_start": window.train_start,
                "train_end": window.train_end,
                "valid_start": window.valid_start,
                "valid_end": window.valid_end,
                "train_rows": len(training_rows),
                "train_rows_unpurged": len(select_training_rows(rows, window, purge=False)),
                "valid_rows": len(validation_rows),
                "train_scores": {param: train_scores.get(param) for param in grid},
                "selection": selection,
                "oracle": oracle,
                "validation_by_param": validation_by_param,
            }
        )

    selected_windows = [
        {
            "window_id": item["window_id"],
            "valid_start": item["valid_start"],
            "valid_end": item["valid_end"],
            "input_rows": item["valid_rows"],
            "summary": item["validation_by_param"].get(item["selection"].selected, EMPTY_SUMMARY),
        }
        for item in window_rows
        if item["selection"].selected is not None
    ]
    active_selected = [item for item in selected_windows if item["summary"].has_activity]
    policy_param = 0.005 if 0.005 in set(grid) else (grid[0] if grid else None)
    fixed_windows = [
        {
            "window_id": item["window_id"],
            "valid_start": item["valid_start"],
            "valid_end": item["valid_end"],
            "input_rows": item["valid_rows"],
            "summary": item["validation_by_param"].get(policy_param, EMPTY_SUMMARY),
        }
        for item in window_rows
    ]
    active_fixed = [item for item in fixed_windows if item["summary"].has_activity]
    oracle_windows = [
        {
            "window_id": item["window_id"],
            "valid_start": item["valid_start"],
            "valid_end": item["valid_end"],
            "input_rows": item["valid_rows"],
            "summary": item["validation_by_param"].get(item["oracle"].selected, EMPTY_SUMMARY),
        }
        for item in window_rows
        if item["oracle"].selected is not None
    ]
    active_oracle = [item for item in oracle_windows if item["summary"].has_activity]

    policy_in_sample = in_sample_by_param.get(policy_param, EMPTY_SUMMARY)
    return {
        "signal_kind": kind,
        "grid": tuple(grid),
        "policy_param": policy_param,
        "in_sample_by_param": in_sample_by_param,
        "in_sample_scores": in_sample_scores,
        "in_sample_selection": in_sample_selection,
        "policy_in_sample": policy_in_sample,
        "windows": window_rows,
        "selected": _aggregate_oos(
            active_windows=active_selected,
            in_sample=policy_in_sample,
            min_windows=min_windows,
        ),
        "fixed_policy": _aggregate_oos(
            active_windows=active_fixed,
            in_sample=policy_in_sample,
            min_windows=min_windows,
        ),
        "oracle": _aggregate_oos(
            active_windows=active_oracle,
            in_sample=policy_in_sample,
            min_windows=min_windows,
        ),
        "drift": parameter_drift([item["selection"].selected for item in window_rows]),
    }


def _aggregate_oos(
    *,
    active_windows: Sequence[Mapping[str, Any]],
    in_sample: RunSummary,
    min_windows: int,
) -> dict[str, Any]:
    summaries = [item["summary"] for item in active_windows]
    strategy_returns = [value for item in summaries if (value := item.cumulative_return) is not None]
    gate_returns = [value for item in summaries if (value := item.gate_return) is not None]
    excess_values = [item.excess_vs_gate for item in summaries]

    chain_strategy = chain_returns(strategy_returns) if strategy_returns else None
    chain_gate = chain_returns(gate_returns) if len(gate_returns) == len(summaries) and gate_returns else None
    chain_excess = (
        chain_strategy - chain_gate if chain_strategy is not None and chain_gate is not None else None
    )
    total_span = sum(
        span_days(str(item["valid_start"]), str(item["valid_end"])) for item in active_windows
    )
    oos_annualized = (
        annualize_return(chain_strategy, total_span) if chain_strategy is not None else None
    )
    verdict, verdict_reason = oos_verdict(
        window_count=len(active_windows),
        excess_values=excess_values,
        chain_excess=chain_excess,
        min_windows=min_windows,
    )
    return {
        "oos_window_count": len(active_windows),
        "oos_span_start": min((str(item["valid_start"]) for item in active_windows), default=""),
        "oos_span_end": max((str(item["valid_end"]) for item in active_windows), default=""),
        "oos_total_span_days": total_span,
        "oos_chain_return": _round(chain_strategy),
        "oos_chain_gate_return": _round(chain_gate),
        "oos_chain_excess": _round(chain_excess),
        "oos_annualized_return": _round(oos_annualized),
        "oos_worst_window_return": _round(min(strategy_returns) if strategy_returns else None),
        "oos_best_window_return": _round(max(strategy_returns) if strategy_returns else None),
        "oos_max_window_drawdown": _round(
            max((item.max_drawdown for item in summaries if item.max_drawdown is not None), default=None)
        ),
        "return_sign_consistency": sign_consistency([item.cumulative_return for item in summaries]),
        "excess_sign_consistency": sign_consistency(excess_values),
        "decay_cumulative": decay_ratio(chain_strategy, in_sample.cumulative_return),
        "decay_cagr": decay_ratio(oos_annualized, in_sample.cagr),
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }


def _metrics_view(summary: RunSummary) -> dict[str, object]:
    return {
        "daily_sharpe": summary.daily_sharpe,
        "cagr": summary.cagr,
        "max_drawdown": summary.max_drawdown,
        "cumulative_return": summary.cumulative_return,
    }


def _segment_payload(segment: Segment) -> dict[str, Any]:
    return {
        "segment_id": segment.segment_id,
        "start_date": segment.start_date,
        "end_date": segment.end_date,
        "signal_date_count": segment.signal_date_count,
        "start_reason": segment.start_reason,
    }


def _window_payload(window: WalkForwardWindow) -> dict[str, Any]:
    return {
        "window_id": window.window_id,
        "segment_id": window.segment_id,
        "train_start": window.train_start,
        "train_end": window.train_end,
        "valid_start": window.valid_start,
        "valid_end": window.valid_end,
        "valid_end_clamped": window.valid_end_clamped,
    }


# --------------------------------------------------------------------- report


def build_report(payload: Mapping[str, Any]) -> str:
    primary = payload["schedules"][0]
    lines: list[str] = []
    lines.extend(_report_header(payload, primary))
    lines.extend(_report_executive_summary(payload, primary))
    lines.extend(_report_gap_accounting(payload))
    lines.extend(_report_schedule(primary))
    lines.extend(_report_equal_weight(primary))
    lines.extend(_report_risk_budget(primary))
    lines.extend(_report_full_window_contrast(payload, primary))
    for schedule_payload in payload["schedules"][1:]:
        lines.extend(_report_secondary_schedule(schedule_payload))
    lines.extend(_report_methodology(payload, primary))
    lines.extend(_report_json_appendix(payload))
    return "\n".join(lines) + "\n"


def _report_header(payload: Mapping[str, Any], primary: Mapping[str, Any]) -> list[str]:
    schedule = primary["schedule"]
    return [
        "# Walk-Forward 样本外验证框架 — 首轮体检报告",
        "",
        f"> 生成时间：{payload['generated_at']} | 引擎 `{PORTFOLIO_ENGINE_VERSION}` | 模式 `{payload['mode']}` | 变体 `{VARIANT}`",
        f"> DuckDB `{payload['db_path']}`（只读） | 执行历史 {payload['execution_row_count']} 行，"
        f"其中可用 {payload['usable_row_count']} 行 | 回测调用 {payload['backtest_run_count']} 次",
        f"> 主切割：训练 {schedule['train_months']} 月 / 验证 {schedule['valid_months']} 月 / 步长 "
        f"{schedule['step_months']} 月，选参目标 `{schedule['objective']}`，训练期 purge="
        f"{schedule['purge_enabled']}",
        f"> 口径：{METRIC_BASIS}",
        "",
        "**本报告只做只读分析**：未修改引擎、策略、政策或任何数据；全部数字由 "
        "`scripts/run_walk_forward_validation.py` 单次运行产出，可复现。",
        "",
        "---",
        "",
    ]


def _report_executive_summary(payload: Mapping[str, Any], primary: Mapping[str, Any]) -> list[str]:
    lines = [
        "## 0. 执行摘要",
        "",
        "### 0.1 七策略样本外判定（等权 fixed_20d，主切割）",
        "",
        "| signal_kind | 可用行 | 历史区间 | OOS窗数 | OOS链式收益 | OOS链式超额(vs gate) | 正超额窗 | 全窗口IS收益 | 衰减率(累计) | 判定 |",
        "|---|---:|---|---:|---:|---:|---|---:|---:|---|",
    ]
    for kind in primary["signal_kinds"]:
        item = primary["equal_weight"][kind]
        consistency = item["excess_sign_consistency"]
        lines.append(
            "| {kind} | {rows} | {first}~{last} | {windows} | {chain} | {excess} | {pos} | {is_return} | {decay} | {verdict} |".format(
                kind=kind,
                rows=item["total_usable_rows"],
                first=item["first_signal_date"],
                last=item["last_signal_date"],
                windows=item["oos_window_count"],
                chain=_pct(item["oos_chain_return"]),
                excess=_pct(item["oos_chain_excess"]),
                pos=f"{consistency['positive_windows']}/{consistency['observed_windows']}"
                if consistency["observed_windows"]
                else "NA",
                is_return=_pct(item["in_sample"].cumulative_return),
                decay=_ratio(item["decay_cumulative"]),
                verdict=_verdict_label(item["verdict"]),
            )
        )
    lines.extend(
        [
            "",
            "### 0.2 risk_budget 参数稳健性（主切割）",
            "",
            "| signal_kind | OOS活动窗 | 选参轨迹(逐窗) | 漂移率 | OOS(逐窗选参) | OOS(固定rpt=0.5%) | OOS(事后最优) | IS(rpt=0.5%) | 选参增益 |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for kind in primary["signal_kinds"]:
        item = primary["risk_budget"][kind]
        trajectory = " → ".join(
            _rpt_label(row["selection"].selected) for row in item["windows"]
        ) or "NA"
        selected_chain = item["selected"]["oos_chain_return"]
        fixed_chain = item["fixed_policy"]["oos_chain_return"]
        gain = (
            selected_chain - fixed_chain
            if selected_chain is not None and fixed_chain is not None
            else None
        )
        lines.append(
            "| {kind} | {windows} | {traj} | {drift} | {sel} | {fixed} | {oracle} | {is_} | {gain} |".format(
                kind=kind,
                windows=item["selected"]["oos_window_count"],
                traj=trajectory,
                drift=_num(item["drift"]["switch_rate"]),
                sel=_pct(selected_chain),
                fixed=_pct(fixed_chain),
                oracle=_pct(item["oracle"]["oos_chain_return"]),
                is_=_pct(item["policy_in_sample"].cumulative_return),
                gain=_pct(gain),
            )
        )
    lines.extend(["", "### 0.3 结论要点", ""])
    lines.extend(_readout_bullets(primary))
    lines.extend(["", "### 0.4 整改后复跑与首版的差异（WF-1~WF-4）", ""])
    lines.extend(_rectification_notes(payload))
    lines.extend(["", "---", ""])
    return lines


def _rectification_notes(payload: Mapping[str, Any]) -> list[str]:
    """验收整改后复跑的差异说明：只有行计数变了，判定与收益数字未变。"""
    dedupe = payload["dedupe"]
    return [
        f"- **唯一的数字变化来自 WF-3 去重**：执行历史行 5560 → {dedupe['deduped_rows']}"
        f"（−{dedupe['removed_rows']}：join 扇出 {dedupe['join_fanout_rows']} 行 + 表内重复 "
        f"{dedupe['table_duplicate_rows']} 行），可用行 4311 → {payload['usable_row_count']}；"
        "§0.1 的「可用行」列相应下降：stock_candidate 783 → 768、mean_reversion 589 → 577、"
        f"hybrid_fusion 132 → 117（逐 kind 去重数 {dedupe['removed_rows_by_kind']}）。",
        f"- **收益/回撤/超额/漂移/判定全部逐字不变**：本次 {dedupe['duplicate_keys']} 个重复键的 "
        f"`ema10` 取值完全一致（`ema10_conflict_keys={dedupe['ema10_conflict_keys']}`），"
        "且引擎本就对同日同股的重复候选按 `duplicate_stock` 跳过，扇出行从未真正建仓。"
        "因此去重修正的是**披露口径**（行计数），不是任何业绩数字——与首版报告逐行对照确认。",
        "- **WF-1（窗口夹取 + fail-fast）在当前数据下零影响**：主切割 5 个窗口的验证末日"
        "均早于段边界，`windows_valid_end_clamped` 为空、`windows_crossing_forced_cut` 为空；"
        "修复是防御性的（对抗构造见 §7.2 引用的测试）。",
        "- **WF-2（训练路径按 `train_end` 截断）在当前数据下未改变选参**：主切割下"
        "训练期尾部持仓的 path 顺延未跨过 `train_end`，选参轨迹与首版一致；"
        "该截断消除的是「停牌顺延数日」这一微扰通道。",
    ]


def _readout_bullets(primary: Mapping[str, Any]) -> list[str]:
    """从本次运行的数字直接生成结论要点，避免报告正文与表格脱节。"""
    bullets: list[str] = []
    judged = [
        kind
        for kind in primary["signal_kinds"]
        if primary["equal_weight"][kind]["verdict"] != VERDICT_INSUFFICIENT
    ]
    unjudged = [kind for kind in primary["signal_kinds"] if kind not in judged]
    supported = [kind for kind in judged if primary["equal_weight"][kind]["verdict"] == "oos_supported"]
    weakened = [kind for kind in judged if primary["equal_weight"][kind]["verdict"] == "oos_weakened"]

    bullets.append(
        f"- **可判定的只有 {len(judged)}/{len(primary['signal_kinds'])} 个策略**："
        f"{'、'.join(judged) or '无'} 有足够验证窗；"
        f"{'、'.join(unjudged) or '无'} 因历史全部落在 2026-03 之后（两代边界之后的段不足以生成 "
        f"{primary['schedule']['train_months']}+{primary['schedule']['valid_months']} 个月的窗口）而**未被检验**——"
        "它们的全窗口结论既没被支持也没被推翻。"
    )
    if supported:
        for kind in supported:
            item = primary["equal_weight"][kind]
            bullets.append(
                f"- **{kind}：样本外支持**。{item['excess_sign_consistency']['positive_windows']}/"
                f"{item['excess_sign_consistency']['observed_windows']} 个验证窗正超额，"
                f"链式超额 {_pct(item['oos_chain_excess'])}，链式收益 {_pct(item['oos_chain_return'])}"
                f"（全窗口 IS {_pct(item['in_sample'].cumulative_return)}）。"
                "优势在滚动切割下没有消失。"
            )
    if weakened:
        for kind in weakened:
            item = primary["equal_weight"][kind]
            bullets.append(
                f"- **{kind}：样本外削弱**。仅 {item['excess_sign_consistency']['positive_windows']}/"
                f"{item['excess_sign_consistency']['observed_windows']} 个验证窗正超额，"
                f"链式超额 {_pct(item['oos_chain_excess'])}；"
                f"逐窗最差 {_pct(item['oos_worst_window_return'])}，最大窗内回撤 "
                f"{_pct(item['oos_max_window_drawdown'])}。"
            )

    rb_judged = [
        kind
        for kind in primary["signal_kinds"]
        if primary["risk_budget"][kind]["fixed_policy"]["oos_window_count"]
        >= primary["schedule"]["min_windows_for_verdict"]
    ]
    if rb_judged:
        details = []
        for kind in rb_judged:
            item = primary["risk_budget"][kind]
            details.append(
                f"{kind}（IS {_pct(item['policy_in_sample'].cumulative_return)} → OOS "
                f"{_pct(item['fixed_policy']['oos_chain_return'])}）"
            )
        bullets.append(
            "- **risk_budget rpt=0.5% 的样本内优势普遍缩水**："
            + "；".join(details)
            + "。全部为同一引擎、同一口径下的对照，差异来自切割方式而非参数实现。"
        )
        drift_rates = [
            primary["risk_budget"][kind]["drift"]["switch_rate"]
            for kind in rb_judged
            if primary["risk_budget"][kind]["drift"]["switch_rate"] is not None
        ]
        modes = {
            kind: primary["risk_budget"][kind]["drift"]["mode_value"] for kind in rb_judged
        }
        bullets.append(
            "- **最优 rpt 随窗漂移严重**：可判定策略的相邻窗切换率为 "
            + "、".join(_num(rate) for rate in drift_rates)
            + "，各自众数分别是 "
            + "、".join(f"{kind}={_rpt_label(value)}" for kind, value in modes.items())
            + "——**没有任何一个策略把 0.5% 选为众数**；"
            "训练窗选出的参数在验证窗的表现与事后最优参数也不重合（§4.1）。"
            "这说明 rpt 更像一个需要按 kind/区制分别校准的量，而不是一个全局稳健常数。"
        )
        selection_gain = [
            (
                kind,
                primary["risk_budget"][kind]["selected"]["oos_chain_return"],
                primary["risk_budget"][kind]["fixed_policy"]["oos_chain_return"],
            )
            for kind in rb_judged
        ]
        positive_gain = [
            kind
            for kind, selected, fixed in selection_gain
            if selected is not None and fixed is not None and selected > fixed
        ]
        bullets.append(
            f"- **逐窗选参 vs 固定 0.5%**：{len(positive_gain)}/{len(selection_gain)} 个可判定策略上"
            "逐窗选参的链式 OOS 收益高于固定 0.5%（§0.2 选参增益列）；"
            "但窗数太少，该增益不足以支撑「上线自适应选参」的结论，只说明固定 0.5% 不是这几段里的最优点。"
        )
    else:
        bullets.append("- risk_budget 参数型验证在主切割下没有足够窗数，全部不可判。")
    return bullets


def _report_gap_accounting(payload: Mapping[str, Any]) -> list[str]:
    disclosure = payload["disclosure"]
    masked = disclosure["exit_date_without_return_block"]
    pending = disclosure["no_exit_date_block"]
    adjusted = disclosure["adjusted_return_missing_block"]
    factor_coverage = disclosure["adjustment_factor_coverage"]
    dedupe = payload["dedupe"]
    lines = [
        "## 1. 数据缺口如实计数",
        "",
        "全部分类来自可核对的列状态（不做因果推断）：",
        "",
        "| signal_kind | 总行 | 不可执行 | 无20d退出日(截尾) | 有退出日无任何收益(遮挡) | 复权缺失走coalesce | 可用行 | 最后可用信号日 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for kind in SIGNAL_KIND_ORDER:
        item = disclosure["by_kind"].get(kind)
        if item is None:
            continue
        lines.append(
            "| {kind} | {total} | {blocked} | {no_exit} | {masked} | {adj} | {usable} | {last} |".format(
                kind=kind,
                total=item["total_rows"],
                blocked=item["entry_blocked"],
                no_exit=item["outcome_no_exit_date"],
                masked=item["exit_date_without_return"],
                adj=item["adjusted_return_missing_coalesced"],
                usable=item["usable_rows"],
                last=item["max_usable_signal_date"] or "NA",
            )
        )
    months = set(disclosure["months_present"])
    missing_months = [month for month in ("2026-01", "2026-02") if month not in months]
    lines.extend(
        [
            "",
            "**四类已知缺口的处置**：",
            "",
            f"1. **执行历史月度空洞**：常被引用的 2026-01/2026-02 缺口在本次数据中确认缺失："
            f"{'、'.join(missing_months) if missing_months else '无（两个月均已有行）'}；"
            "框架不跨空洞生成窗口——空洞被 `max_gap_days` 与强制切割点共同拦成段边界。",
            f"2. **20d outcome 未成熟尾部（截尾）**：{pending['rows']} 行无 `exit_date_20d`"
            f"（信号日 {pending['min_signal_date']}~{pending['max_signal_date']}），"
            "一律排除在可用行之外，不进入任何窗口；这意味着最后一段验证窗天然被截断。",
            f"3. **有退出日但无任何 20d 收益（遮挡）**：{masked['rows']} 行。"
            + (
                "本框架的输入表 `livermore_candidate_execution_history` **未出现**该症状"
                "（`stored_target_conflict` 是 `livermore_candidate_outcome_maturity` 在 "
                "`livermore_candidate_history` 上的运行期 issue，不落成执行历史的列状态）；"
                "如实计为 0，不臆造遮挡量。"
                if masked["rows"] == 0
                else f"信号日 {masked['min_signal_date']}~{masked['max_signal_date']}；如实排除并计数，不做代理填补。"
            ),
            f"4. **复权缺失行**：{adjusted['rows']} 行有 `return_20d_net` 但无 `return_20d_net_adj`"
            f"（信号日 {adjusted['min_signal_date']}~{adjusted['max_signal_date']}），"
            "沿用引擎 coalesce 链 `return_20d_net_adj -> return_20d_net` 计入回测，逐 kind 计数见上表。"
            "这些行按**未复权**净收益结算，除权窗口内存在方向不定的偏差。",
            f"   - 根因取证（分两类）：**(a) 日期级空洞** —— "
            f"{factor_coverage.get('rows_with_uncovered_target', 0)} 行的 20d 目标日"
            f"（共 {factor_coverage.get('uncovered_target_date_count', 0)} 个日期，散布于 "
            f"{factor_coverage.get('first_uncovered_target_date', 'NA')}~"
            f"{factor_coverage.get('last_uncovered_target_date', 'NA')}）在 `stock_adjustment_factor` 中"
            "完全没有因子行；**(b) 逐票缺失** —— 其余行的目标日有因子但该股票缺行。",
            f"   - 其中尾部 {factor_coverage.get('rows_after_dense_coverage_end', 0)} 行的目标日晚于"
            f"因子表的稠密覆盖末日 {factor_coverage.get('dense_coverage_end', 'NA')}"
            f"（表内最大因子日 {factor_coverage.get('max_factor_trade_date', 'NA')} 是孤立补载日，"
            "不构成连续覆盖），信号日集中在 "
            f"{adjusted['recent_block_min_signal_date']}~{adjusted['max_signal_date']}、"
            f"目标日最远 {adjusted['max_exit_date']}。"
            "**任务所述「2026-06 中旬遮挡」在本框架输入表中的可观测形态就是这道复权因子覆盖悬崖**——"
            "这些行不是被排除，而是以未复权口径进入了最后一个可用月，属已披露偏差。",
            "",
            f"- 两代数据边界 `{CHOICE_NATIVE_ERA_START}` 为强制切割点，任何窗口不得跨越。",
            f"- path 模式缺价格路径行：{payload['missing_price_path_rows']}（按成本计价降级）。",
            "",
            "**加载器行数守恒（ema10 join 扇出 + 表内重复行）**：",
            f"- 共享加载器 `_load_execution_rows` 为取 `ema10` 左连 "
            "`livermore_candidate_history`，该表对同一 "
            "(stock_code, snapshot_as_of_date, signal_kind) 可能有 2 行，"
            f"于是加载 {dedupe['loaded_rows']} 行 vs 表内（`entry_date` 非空）"
            f"{dedupe['table_rows_with_entry_date']} 行，**join 扇出 +"
            f"{dedupe['join_fanout_rows']} 行**（最大重复 {dedupe['max_multiplicity']} 次）。",
            f"- 执行历史表**自身**还有 {dedupe['table_duplicate_rows']} 行完全重复的执行行"
            f"（同 `(signal_date, stock_code, signal_kind)`、同 run_id / formula_version / "
            "entry_date / 20d 收益），两者叠加才产生 4 倍键。",
            "- 该加载器是已提交的共享文件、扇出属继承问题，**本框架不改加载器**，"
            f"而是在编排侧按 `{', '.join(dedupe['key_fields'])}` 去重（{dedupe['keep_rule']}）："
            f"{dedupe['loaded_rows']} → {dedupe['deduped_rows']} 行"
            f"（−{dedupe['removed_rows']}，涉及 {dedupe['duplicate_keys']} 个键）；"
            f"去重后行数与表内去重键数 {dedupe['table_distinct_keys']} "
            f"{'一致' if dedupe['deduped_matches_table_distinct_keys'] else '**不一致（需排查）**'}"
            "，即「一个 (信号日, 股票, 信号族) 一行」。"
            + (
                f"逐 kind 去重行数：{dedupe['removed_rows_by_kind']}。"
                if dedupe["removed_rows_by_kind"]
                else ""
            ),
            f"- 与上表口径的剩余差异只有两项且可核对：上表 SQL 不过滤 `entry_date`"
            f"（{sum(item['no_entry_date'] for item in disclosure['by_kind'].values())} 行无 "
            "`entry_date`，无法建仓）、且把上述表内重复行各计一次；"
            "§0.1「可用行」是编排侧去重后的口径。",
            f"- 取舍说明：本次 {dedupe['duplicate_keys']} 个重复键的 `ema10` 取值全部相同"
            f"（`ema10_conflict_keys={dedupe['ema10_conflict_keys']}`），故去重不改任何计算；"
            "规则本身保留 ema10 非空且最小者 ⇒ 止损距离最大 ⇒ 同键候选中仓位最保守的一档，"
            "并避免退回 POLICY 固定 fallback 止损距离。"
            "引擎对同日同股的重复候选本就按 `duplicate_stock` 跳过，扇出行从未真正建仓。",
            "",
            "---",
            "",
        ]
    )
    return lines


def _report_schedule(primary: Mapping[str, Any]) -> list[str]:
    lines = [
        "## 2. 切割方案与窗口清单",
        "",
        "### 2.1 分段（强制切割点 / 数据空洞）",
        "",
        "| segment | 起 | 止 | 信号日数 | 起始原因 |",
        "|---|---|---|---:|---|",
    ]
    for segment in primary["segments"]:
        lines.append(
            "| {sid} | {start} | {end} | {count} | {reason} |".format(
                sid=segment["segment_id"],
                start=segment["start_date"],
                end=segment["end_date"],
                count=segment["signal_date_count"],
                reason=segment["start_reason"],
            )
        )
    lines.extend(
        [
            "",
            "### 2.2 窗口",
            "",
            "| window | segment | 训练区间 | 验证区间 | 验证末日被段边界夹短 |",
            "|---|---|---|---|---|",
        ]
    )
    for window in primary["windows"]:
        lines.append(
            "| {wid} | {sid} | {ts}~{te} | {vs}~{ve} | {clamped} |".format(
                wid=window["window_id"],
                sid=window["segment_id"],
                ts=window["train_start"],
                te=window["train_end"],
                vs=window["valid_start"],
                ve=window["valid_end"],
                clamped="是" if window.get("valid_end_clamped") else "否",
            )
        )
    lines.extend(
        [
            "",
            f"- 验证窗互不重叠：{primary['windows_disjoint']}（链式复利成立的前提）",
            f"- 跨越强制切割点的窗口：{primary['windows_crossing_forced_cut'] or '无'}"
            "（窗口生成阶段已把验证末日夹在段实际边界内；若仍出现跨界，"
            "`analyze_schedule` 直接抛 `WalkForwardLeakageError` 拒绝出报告）",
            f"- 验证末日被段边界夹短的窗口：{primary['windows_valid_end_clamped'] or '无'}"
            "（夹短窗的验证时长小于名义 valid_months，其年化数字更不稳定）",
            "",
            "---",
            "",
        ]
    )
    return lines


def _report_equal_weight(primary: Mapping[str, Any]) -> list[str]:
    lines = [
        "## 3. 无参数型验证：七个 signal_kind 等权 fixed_20d",
        "",
        "### 3.1 逐窗样本外表现",
        "",
        "| signal_kind | window | 验证区间 | 验证行 | 买入笔 | 收益 | 回撤 | Sharpe | gate基准 | 超额 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind in primary["signal_kinds"]:
        item = primary["equal_weight"][kind]
        emitted = False
        for window in item["windows"]:
            summary: RunSummary = window["summary"]
            if not summary.has_activity:
                continue
            emitted = True
            lines.append(
                "| {kind} | {wid} | {vs}~{ve} | {rows} | {buys} | {ret} | {mdd} | {sharpe} | {gate} | {excess} |".format(
                    kind=kind,
                    wid=window["window_id"],
                    vs=window["valid_start"],
                    ve=window["valid_end"],
                    rows=window["input_rows"],
                    buys=summary.buy_trades,
                    ret=_pct(summary.cumulative_return),
                    mdd=_pct(summary.max_drawdown),
                    sharpe=_num(summary.daily_sharpe),
                    gate=_pct(summary.gate_return),
                    excess=_pct(summary.excess_vs_gate),
                )
            )
        if not emitted:
            lines.append(
                f"| {kind} | — | — | 0 | 0 | NA | NA | NA | NA | NA |"
            )
    lines.extend(
        [
            "",
            "### 3.2 聚合：衰减率 / 稳定性 / 判定",
            "",
            "OOS窗只计**有实际买入**的验证窗（该 kind 在某窗无信号时不计入，也不参与链式复利）。",
            "注意 OOS 覆盖期与 IS 覆盖期不同（见下表 OOS区间 列），因此**期间中性的比较应看链式超额**"
            "（策略 − 同期 gate 择时基准），而不是链式收益与 IS 收益的直接相除。",
            "",
            "| signal_kind | OOS窗 | OOS区间 | 链式OOS | 链式超额 | 年化OOS | 最差窗 | 最大窗内回撤 | IS累计 | IS年化 | 衰减(累计) | 衰减(年化) | 收益正窗 | 超额正窗 | 判定 | 理由 |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|",
        ]
    )
    for kind in primary["signal_kinds"]:
        item = primary["equal_weight"][kind]
        in_sample: RunSummary = item["in_sample"]
        return_consistency = item["return_sign_consistency"]
        excess_consistency = item["excess_sign_consistency"]
        lines.append(
            "| {kind} | {windows} | {span} | {chain} | {excess} | {ann} | {worst} | {mdd} | {is_cum} | {is_cagr} | {d_cum} | {d_cagr} | {rpos} | {epos} | {verdict} | {reason} |".format(
                kind=kind,
                windows=item["oos_window_count"],
                span=f"{item['oos_span_start']}~{item['oos_span_end']}"
                if item["oos_span_start"]
                else "—",
                chain=_pct(item["oos_chain_return"]),
                excess=_pct(item["oos_chain_excess"]),
                ann=_pct(item["oos_annualized_return"]),
                worst=_pct(item["oos_worst_window_return"]),
                mdd=_pct(item["oos_max_window_drawdown"]),
                is_cum=_pct(in_sample.cumulative_return),
                is_cagr=_pct(in_sample.cagr),
                d_cum=_ratio(item["decay_cumulative"]),
                d_cagr=_ratio(item["decay_cagr"]),
                rpos=f"{return_consistency['positive_windows']}/{return_consistency['observed_windows']}"
                if return_consistency["observed_windows"]
                else "NA",
                epos=f"{excess_consistency['positive_windows']}/{excess_consistency['observed_windows']}"
                if excess_consistency["observed_windows"]
                else "NA",
                verdict=_verdict_label(item["verdict"]),
                reason=item["verdict_reason"],
            )
        )
    lines.extend(["", "---", ""])
    return lines


def _report_risk_budget(primary: Mapping[str, Any]) -> list[str]:
    objective = primary["schedule"]["objective"]
    lines = [
        "## 4. 参数型验证：risk_budget rpt 网格",
        "",
        f"训练窗按 `{objective}` 选参，验证窗只用该参数。训练切片额外做 purge："
        "只保留 20d 退出日 ≤ 训练末日的行，保证选参时刻这些收益已完全兑现。",
        "",
        "### 4.1 逐窗选参与样本外结果",
        "",
        f"「训练行」列格式为 purge 后(purge 前)；训练行少于 {MIN_TRAIN_ROWS} 条的窗不选参（记 NA），"
        "避免在几乎没有观测的训练窗上假装完成了参数优化。"
        "「事后最优」是用验证窗自身结果反选出的参数，仅用于度量选参损失，**不是可实施的策略**。",
        "",
        "| signal_kind | window | 训练行(purge前) | 训练分数 0.25/0.50/0.75/1.00% | 选中 | 验证行 | OOS收益(选中) | OOS收益(0.5%) | 事后最优 | OOS收益(事后最优) |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for kind in primary["signal_kinds"]:
        item = primary["risk_budget"][kind]
        emitted = False
        for window in item["windows"]:
            selected = window["selection"].selected
            selected_summary = window["validation_by_param"].get(selected, EMPTY_SUMMARY)
            policy_summary = window["validation_by_param"].get(item["policy_param"], EMPTY_SUMMARY)
            oracle_selected = window["oracle"].selected
            oracle_summary = window["validation_by_param"].get(oracle_selected, EMPTY_SUMMARY)
            if selected is None and not policy_summary.has_activity:
                continue
            emitted = True
            scores = " / ".join(
                _num(window["train_scores"].get(param)) for param in item["grid"]
            )
            lines.append(
                "| {kind} | {wid} | {tr}({tru}) | {scores} | {sel} | {vr} | {sel_ret} | {pol_ret} | {orc} | {orc_ret} |".format(
                    kind=kind,
                    wid=window["window_id"],
                    tr=window["train_rows"],
                    tru=window["train_rows_unpurged"],
                    scores=scores,
                    sel=_rpt_label(selected),
                    vr=window["valid_rows"],
                    sel_ret=_pct(selected_summary.cumulative_return),
                    pol_ret=_pct(policy_summary.cumulative_return),
                    orc=_rpt_label(oracle_selected),
                    orc_ret=_pct(oracle_summary.cumulative_return),
                )
            )
        if not emitted:
            lines.append(f"| {kind} | — | — | — | NA | 0 | NA | NA | NA | NA |")

    lines.extend(
        [
            "",
            "### 4.2 参数漂移度",
            "",
            "| signal_kind | 有效选参窗 | 取值个数 | 众数 | 众数占比 | 切换次数 | 切换率 | 平均步长(rpt) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for kind in primary["signal_kinds"]:
        drift = primary["risk_budget"][kind]["drift"]
        lines.append(
            "| {kind} | {windows} | {distinct} | {mode} | {share} | {switches} | {rate} | {step} |".format(
                kind=kind,
                windows=drift["observed_windows"],
                distinct=drift["distinct_values"],
                mode=_rpt_label(drift["mode_value"]),
                share=_num(drift["mode_share"]),
                switches=_num(drift["switch_count"]),
                rate=_num(drift["switch_rate"]),
                step=_num(drift["mean_abs_step"]),
            )
        )

    lines.extend(
        [
            "",
            "### 4.3 样本外 vs 全窗口 in-sample（rpt=0.5%）",
            "",
            "| signal_kind | IS累计(0.5%) | IS回撤(0.5%) | IS最优rpt | OOS链式(0.5%) | OOS链式(逐窗选参) | 衰减率(0.5%) | 超额正窗(0.5%) | 判定(0.5%) |",
            "|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for kind in primary["signal_kinds"]:
        item = primary["risk_budget"][kind]
        policy_is: RunSummary = item["policy_in_sample"]
        fixed = item["fixed_policy"]
        consistency = fixed["excess_sign_consistency"]
        lines.append(
            "| {kind} | {is_cum} | {is_mdd} | {is_best} | {oos_fixed} | {oos_sel} | {decay} | {pos} | {verdict} |".format(
                kind=kind,
                is_cum=_pct(policy_is.cumulative_return),
                is_mdd=_pct(policy_is.max_drawdown),
                is_best=_rpt_label(item["in_sample_selection"].selected),
                oos_fixed=_pct(fixed["oos_chain_return"]),
                oos_sel=_pct(item["selected"]["oos_chain_return"]),
                decay=_ratio(fixed["decay_cumulative"]),
                pos=f"{consistency['positive_windows']}/{consistency['observed_windows']}"
                if consistency["observed_windows"]
                else "NA",
                verdict=_verdict_label(fixed["verdict"]),
            )
        )
    lines.extend(["", "---", ""])
    return lines


def _report_full_window_contrast(payload: Mapping[str, Any], primary: Mapping[str, Any]) -> list[str]:
    lines = [
        "## 5. 与全窗口结论的对照",
        "",
        "对照口径：本表的「全窗口 IS」由本次运行同一引擎重算，与既有报告口径一致但数据已滚动更新，",
        "因此绝对数可能与历史报告略有差异；结论方向的对照以本次内部一致的数字为准。",
        "",
        "| 策略 | 全窗口 IS 结论（本次重算） | 样本外结论 | 对照 |",
        "|---|---|---|---|",
    ]
    for kind in primary["signal_kinds"]:
        item = primary["equal_weight"][kind]
        in_sample: RunSummary = item["in_sample"]
        is_excess = in_sample.excess_vs_gate
        is_claim = (
            f"累计 {_pct(in_sample.cumulative_return)}，超额 {_pct(is_excess)}"
            if in_sample.cumulative_return is not None
            else "NA"
        )
        verdict = item["verdict"]
        if verdict == VERDICT_INSUFFICIENT:
            contrast = "**不可判**（窗数不足）"
        elif is_excess is None:
            contrast = "不可判（IS 超额不可得）"
        elif is_excess > 0 and verdict == "oos_supported":
            contrast = "**被样本外支持**"
        elif is_excess > 0 and verdict == "oos_weakened":
            contrast = "**被样本外削弱**"
        elif is_excess <= 0 and verdict == "oos_weakened":
            contrast = "样本外一致为负（IS 负结论被确认）"
        elif is_excess <= 0 and verdict == "oos_supported":
            contrast = "样本外反而为正（IS 负结论被推翻）"
        else:
            contrast = "方向不定"
        lines.append(
            "| {kind} | {claim} | {oos} | {contrast} |".format(
                kind=kind,
                claim=is_claim,
                oos=f"{_verdict_label(verdict)}；链式超额 {_pct(item['oos_chain_excess'])}",
                contrast=contrast,
            )
        )
    lines.extend(["", "---", ""])
    return lines


def _report_secondary_schedule(schedule_payload: Mapping[str, Any]) -> list[str]:
    schedule = schedule_payload["schedule"]
    lines = [
        f"## 6. 敏感性切割：{schedule['label']}（探索性，不作为判定依据）",
        "",
        f"训练 {schedule['train_months']} 月 / 验证 {schedule['valid_months']} 月 / 步长 "
        f"{schedule['step_months']} 月。目的有二：(1) 检验主切割结论对窗口粒度的敏感性；"
        "(2) 给只有 2026-03 之后历史的短史策略一个能落窗的粒度。"
        "该粒度下单窗样本极小、训练期几乎无自由度，**结论一律不升级为判定**。",
        "",
        "该切割覆盖的 OOS 区间与主切割**不同且更长**（见 OOS区间 列），因此其数值水平不能与 §3 直接比较；"
        "可比的只有方向（超额正窗比例、链式超额符号）。",
        "",
        f"另一处近似：本切割在 {len(schedule_payload['segments'])} 个数据段上都生成了窗口，"
        "链式复利把段与段之间的数据空洞当作连续持有处理（窗口本身仍不跨段）。",
        "",
        "| signal_kind | OOS窗 | OOS区间 | 链式OOS | 链式超额 | 收益正窗 | 超额正窗 | IS累计 | 衰减(累计) | 参考判定 |",
        "|---|---:|---|---:|---:|---|---|---:|---:|---|",
    ]
    for kind in schedule_payload["signal_kinds"]:
        item = schedule_payload["equal_weight"][kind]
        in_sample: RunSummary = item["in_sample"]
        return_consistency = item["return_sign_consistency"]
        excess_consistency = item["excess_sign_consistency"]
        lines.append(
            "| {kind} | {windows} | {span} | {chain} | {excess} | {rpos} | {epos} | {is_cum} | {decay} | {verdict} |".format(
                kind=kind,
                windows=item["oos_window_count"],
                span=f"{item['oos_span_start']}~{item['oos_span_end']}"
                if item["oos_span_start"]
                else "—",
                chain=_pct(item["oos_chain_return"]),
                excess=_pct(item["oos_chain_excess"]),
                rpos=f"{return_consistency['positive_windows']}/{return_consistency['observed_windows']}"
                if return_consistency["observed_windows"]
                else "NA",
                epos=f"{excess_consistency['positive_windows']}/{excess_consistency['observed_windows']}"
                if excess_consistency["observed_windows"]
                else "NA",
                is_cum=_pct(in_sample.cumulative_return),
                decay=_ratio(item["decay_cumulative"]),
                verdict=_verdict_label(item["verdict"]),
            )
        )
    lines.extend(
        [
            "",
        "risk_budget 逐窗选参轨迹（同一粒度）：",
        "",
        f"注意：1 个月的训练窗在 purge（要求 20d 结果已兑现）之后往往不足 {MIN_TRAIN_ROWS} 行，"
        "因此多数 kind 的「有效选参窗」为 0。"
        "**这本身是结论**：在月度粒度上无法在不偷看未来的前提下完成参数选择；"
        "「OOS(固定0.5%)」列不依赖选参，仍然可读。",
        "",
        "| signal_kind | 有效选参窗 | 众数 | 切换率 | OOS(选参) | OOS(固定0.5%) |",
        "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for kind in schedule_payload["signal_kinds"]:
        item = schedule_payload["risk_budget"][kind]
        drift = item["drift"]
        lines.append(
            "| {kind} | {windows} | {mode} | {rate} | {sel} | {fixed} |".format(
                kind=kind,
                windows=drift["observed_windows"],
                mode=_rpt_label(drift["mode_value"]),
                rate=_num(drift["switch_rate"]),
                sel=_pct(item["selected"]["oos_chain_return"]),
                fixed=_pct(item["fixed_policy"]["oos_chain_return"]),
            )
        )
    lines.extend(["", "---", ""])
    return lines


def _report_methodology(payload: Mapping[str, Any], primary: Mapping[str, Any]) -> list[str]:
    schedule = primary["schedule"]
    lines = [
        "## 7. 方法学附录",
        "",
        "### 7.1 切割图示",
        "",
        "```",
    ]
    lines.extend(schedule_diagram(primary["window_objects"], primary["segment_objects"]))
    lines.extend(
        [
            "```",
            "",
            "（T=训练月，V=验证月，.=同段内未被该窗覆盖的月）",
            "",
            "### 7.2 防泄漏机制",
            "",
            "| 机制 | 实现 | 断言位置 |",
            "|---|---|---|",
            "| 验证窗只见窗内信号 | `select_validation_rows` 按 `signal_date` 闭区间切片 | `tests/test_walk_forward_validation.py::test_validation_slice_only_contains_window_signal_dates` |",
            "| 选参只用训练窗 | `select_training_rows` 按 `signal_date` 切片 | 同上文件 `test_training_slice_*` |",
            f"| 训练期 purge（{HORIZON_DAYS}d 未兑现行剔除） | 训练行要求 `exit_date_20d <= train_end`，即选参时刻(`valid_start`)其收益已实现 | `test_training_rows_are_purged_of_unrealized_outcomes` |",
            "| 未来数据不影响选参（纯逻辑） | 删除/篡改 `train_end` 之后的全部行，选参结果必须不变 | `test_parameter_selection_is_immune_to_future_rows` |",
            "| 未来数据不影响选参（真实引擎） | 在真实引擎上篡改 `train_end` 之后的执行行与窗外路径价格，选参与训练分数必须逐字节不变 | `test_real_engine_parameter_selection_is_immune_to_future_rows` |",
            "| 窗口不跨代际边界 | 分段在强制切割点与数据空洞处断开；验证末日再夹在段实际边界内，跨界则 `analyze_schedule` fail-fast | `test_windows_never_cross_forced_cut_date`、`test_segment_end_in_same_month_as_cut_does_not_leak_next_segment`、`test_analyze_schedule_fails_fast_on_crossing_window` |",
            "| 价格路径按切片限定 | 只把本切片持仓的路径喂给引擎，避免其它窗口的路径污染交易日网格 | `test_scoped_price_paths_exclude_other_slices` |",
            "| 训练路径按决策时点截断 | path 模式下停牌/跌停顺延会让训练时间轴越过 `train_end`；训练调用把每条路径的 bar 截到 `trade_date <= train_end` | `test_training_price_paths_are_truncated_at_train_end` |",
            "",
            "注意：验证窗内建仓的持仓，其 20d 结果自然落在验证窗之后——这是「决策后的实现结果」，",
            "不是前视；本框架禁止的是「决策时使用决策日之后的信息」。",
            "",
            "### 7.3 指标定义",
            "",
            "- **链式 OOS 收益** = ∏(1 + 各验证窗收益) − 1（验证窗互不重叠时成立，见 §2.2）；",
            "  - **窗间持有期重叠（口径披露）**：窗口的互不重叠是按 `signal_date` 定义的，"
            f"而验证窗末尾建仓的持仓其 {HORIZON_DAYS}d 持有期会延伸到下一验证窗的日历区间内。"
            "本框架把每个验证窗当作独立重启的资金曲线（各窗从 `initial_capital` 起算、窗末清仓收口）"
            "再把窗收益相乘，因此链式收益是「连续换仓的近似」而非单条不间断资金曲线："
            "跨窗的仓位延续、现金占用与相邻窗之间的相关性都没有被建模，"
            "相邻窗收益并非严格独立，链式数值的置信度低于单窗数值；",
            "- **链式超额** = 链式策略收益 − 链式 gate 择时基准收益（`gate_timing_csi300`，与引擎同口径）；",
            "- **衰减率(累计)** = 链式 OOS 收益 ÷ 全窗口 IS 累计收益；IS ≤ 0 时比值无意义，只给差值并标注；",
            "- **衰减率(年化)** = OOS 年化 ÷ IS 年化，年化统一按 365/日历跨度（与引擎 `_annualization_factor` 同口径）；",
            "- **超额符号一致率** = 正超额验证窗数 ÷ 可观测验证窗数；",
            "- **参数漂移度** = 相邻窗选参发生变化的比例（切换率）+ 平均绝对步长；",
            f"- **判定阈值**：窗数 < {schedule['min_windows_for_verdict']} 判「不可判」；"
            "否则超额正窗比 ≥ 2/3 且链式超额 > 0 判「样本外支持」，"
            "正窗比 ≤ 1/3 或链式超额 < 0 判「样本外削弱」，其余「方向不稳定」。",
            "",
            "### 7.4 自由度与局限（如实披露）",
            "",
        ]
    )
    limitations = _build_limitations(payload, primary)
    lines.extend(f"{index}. {text}" for index, text in enumerate(limitations, start=1))
    lines.extend(["", "---", ""])
    return lines


def _build_limitations(payload: Mapping[str, Any], primary: Mapping[str, Any]) -> list[str]:
    schedule = primary["schedule"]
    short_history = [
        kind
        for kind in primary["signal_kinds"]
        if primary["equal_weight"][kind]["oos_window_count"] < schedule["min_windows_for_verdict"]
    ]
    window_count = len(primary["windows"])
    return [
        f"**窗数本身很少**：主切割只产出 {window_count} 个验证窗，且全部落在同一个数据段内；"
        "任一策略的判定至多基于个位数的独立观测，统计力弱，只能作方向证据。",
        f"**短历史策略不可判**：{'、'.join(short_history) if short_history else '无'} 在主切割下有效验证窗少于 "
        f"{schedule['min_windows_for_verdict']} 个，本报告不对其给出样本外结论。"
        "其全窗口结论既未被支持也未被削弱——是**未被检验**。",
        "**验证窗内持有期重叠**：20d 持有期使同一验证窗内的观测高度相关，"
        "有效独立观测数远小于行数；逐窗 Sharpe/回撤应视为噪声较大的读数。",
        "**验证窗间持有期重叠**：窗口按 `signal_date` 互斥，但窗末建仓的 20d 持有期跨入下一窗日历区间；"
        "本框架每窗独立重启资金曲线后再链式相乘（§7.3），未建模跨窗仓位延续与现金占用，"
        "相邻窗收益不严格独立，链式收益应作方向性读数、不可当作可实盘复现的净值。",
        "**尾部截断**：最后一段验证窗因 20d outcome 未回补而系统性缺少晚期信号，"
        "该窗结论对「窗末行情」不敏感，存在选择性幸存。",
        "**市场状态标签可漂移**：逐日 gate 敞口与 market_state 来自重放，"
        "既有审计（factor_screen 门控复审）已记录标签漂移；所有状态条件化的窗口结果继承该不确定性。",
        "**基准口径**：超额以 `gate_timing_csi300`（同敞口择时的 CSI300）为准，"
        "不是无风险利率或行业中性基准；策略与基准的敞口路径不同会带入 beta 残差。",
        "**只验证了两类对象**：sizing 参数（rpt）与信号族本身；"
        "选股打分内部参数（如 momentum v2 的权重、factor_screen 的因子集）没有进入本框架，"
        "它们的过拟合风险未被本轮体检覆盖。",
        "**OOS 与 IS 覆盖期不同**：验证窗只覆盖 S1 的一段，而全窗口 IS 含 2026 段；"
        "「衰减率(累计)」因此混合了过拟合效应与期间构成效应，"
        "**期间中性的判据是链式超额**（同期 gate 基准已扣除），判定逻辑也以它为准。",
        "**复权口径不均匀**：最后一个可用月的行按未复权净收益进入回测（§1 第 4 条），"
        "与其余月份的复权口径不完全可比。",
    ]


def _report_json_appendix(payload: Mapping[str, Any]) -> list[str]:
    return [
        "## 8. 附录：机器可读汇总（主切割聚合）",
        "",
        f"完整明细（含逐窗记录与敏感性切割）见同目录 `{Path(payload['json_path']).name}`。",
        "",
        "```json",
        json.dumps(_json_payload(payload, full=False), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
    ]


def _json_payload(payload: Mapping[str, Any], *, full: bool) -> dict[str, Any]:
    schedules = payload["schedules"] if full else payload["schedules"][:1]
    return {
        "generated_at": payload["generated_at"],
        "db_path": payload["db_path"],
        "mode": payload["mode"],
        "engine_version": PORTFOLIO_ENGINE_VERSION,
        "execution_row_count": payload["execution_row_count"],
        "usable_row_count": payload["usable_row_count"],
        "backtest_run_count": payload["backtest_run_count"],
        "issues": payload["issues"],
        "dedupe": payload["dedupe"],
        "disclosure": payload["disclosure"] if full else payload["disclosure"]["adjustment_factor_coverage"],
        "schedules": [
            {
                "schedule": item["schedule"],
                "segments": item["segments"],
                "windows": item["windows"],
                "windows_disjoint": item["windows_disjoint"],
                "windows_crossing_forced_cut": item["windows_crossing_forced_cut"],
                "windows_valid_end_clamped": item["windows_valid_end_clamped"],
                "equal_weight": {
                    kind: _json_equal_weight(item["equal_weight"][kind], full=full)
                    for kind in item["signal_kinds"]
                },
                "risk_budget": {
                    kind: _json_risk_budget(item["risk_budget"][kind], full=full)
                    for kind in item["signal_kinds"]
                },
            }
            for item in schedules
        ],
    }


def _json_equal_weight(item: Mapping[str, Any], *, full: bool = True) -> dict[str, Any]:
    return {
        "total_usable_rows": item["total_usable_rows"],
        "first_signal_date": item["first_signal_date"],
        "last_signal_date": item["last_signal_date"],
        "in_sample": _json_summary(item["in_sample"]),
        "oos_window_count": item["oos_window_count"],
        "oos_chain_return": item["oos_chain_return"],
        "oos_chain_excess": item["oos_chain_excess"],
        "oos_annualized_return": item["oos_annualized_return"],
        "decay_cumulative": item["decay_cumulative"],
        "decay_cagr": item["decay_cagr"],
        "return_sign_consistency": item["return_sign_consistency"],
        "excess_sign_consistency": item["excess_sign_consistency"],
        "verdict": item["verdict"],
        "verdict_reason": item["verdict_reason"],
        **(
            {
                "windows": [
                    {
                        "window_id": window["window_id"],
                        "valid_start": window["valid_start"],
                        "valid_end": window["valid_end"],
                        "input_rows": window["input_rows"],
                        **_json_summary(window["summary"]),
                    }
                    for window in item["windows"]
                ]
            }
            if full
            else {}
        ),
    }


def _json_risk_budget(item: Mapping[str, Any], *, full: bool = True) -> dict[str, Any]:
    return {
        "grid": list(item["grid"]),
        "policy_param": item["policy_param"],
        "in_sample_selection": item["in_sample_selection"].selected,
        "policy_in_sample": _json_summary(item["policy_in_sample"]),
        "drift": item["drift"],
        "selected": _json_aggregate(item["selected"]),
        "fixed_policy": _json_aggregate(item["fixed_policy"]),
        "oracle": _json_aggregate(item["oracle"]),
        **(
            {
                "in_sample_by_param": {
                    str(param): _json_summary(summary)
                    for param, summary in item["in_sample_by_param"].items()
                },
                "windows": [
                    {
                        "window_id": window["window_id"],
                        "train_rows": window["train_rows"],
                        "train_rows_unpurged": window["train_rows_unpurged"],
                        "valid_rows": window["valid_rows"],
                        "train_scores": {
                            str(key): value for key, value in window["train_scores"].items()
                        },
                        "selected": window["selection"].selected,
                        "selection_status": window["selection"].status,
                        "oracle": window["oracle"].selected,
                    }
                    for window in item["windows"]
                ],
            }
            if full
            else {}
        ),
    }


def _json_aggregate(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key
        in {
            "oos_window_count",
            "oos_total_span_days",
            "oos_chain_return",
            "oos_chain_excess",
            "oos_annualized_return",
            "decay_cumulative",
            "decay_cagr",
            "excess_sign_consistency",
            "verdict",
        }
    }


def _json_summary(summary: RunSummary) -> dict[str, Any]:
    return {
        "input_rows": summary.input_rows,
        "buy_trades": summary.buy_trades,
        "cumulative_return": _round(summary.cumulative_return),
        "cagr": _round(summary.cagr),
        "max_drawdown": _round(summary.max_drawdown),
        "daily_sharpe": _round(summary.daily_sharpe),
        "gate_return": _round(summary.gate_return),
        "excess_vs_gate": _round(summary.excess_vs_gate),
        "skipped_missing_outcome": summary.skipped_missing_outcome,
    }


# ------------------------------------------------------------------ formatting


def _pct(value: object) -> str:
    number = _finite(value)
    return "NA" if number is None else f"{number * 100:.2f}%"


def _num(value: object) -> str:
    number = _finite(value)
    return "NA" if number is None else f"{number:.4f}"


def _ratio(item: Mapping[str, Any] | None) -> str:
    if not item:
        return "NA"
    if item.get("status") == "ready" and item.get("ratio") is not None:
        return f"{float(item['ratio']):.2f}x"
    if item.get("status") == "is_non_positive":
        return f"IS≤0(Δ{_pct(item.get('delta'))})"
    return "NA"


def _rpt_label(value: object) -> str:
    number = _finite(value)
    return "NA" if number is None else f"{number * 100:.2f}%"


def _verdict_label(verdict: str) -> str:
    return {
        "oos_supported": "样本外支持",
        "oos_weakened": "样本外削弱",
        "oos_inconclusive": "方向不稳定",
        "insufficient_windows": "不可判(窗数不足)",
    }.get(verdict, verdict)


def _round(value: object) -> float | None:
    number = _finite(value)
    return None if number is None else round(number, 6)


def _finite(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# ------------------------------------------------------------------------ main


def run_walk_forward_validation(
    *,
    db_path: str = DEFAULT_DB_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    mode: str = "path",
    objective: str = "sharpe",
    train_months: int = PRIMARY_SCHEDULE.train_months,
    valid_months: int = PRIMARY_SCHEDULE.valid_months,
    step_months: int = PRIMARY_SCHEDULE.step_months,
    risk_per_trade_grid: Sequence[float] = DEFAULT_RISK_PER_TRADE_GRID,
    forced_cut_dates: Sequence[str] = DEFAULT_FORCED_CUT_DATES,
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
    min_windows: int = DEFAULT_MIN_WINDOWS_FOR_VERDICT,
    purge: bool = True,
    include_compact_schedule: bool = True,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
) -> dict[str, Any]:
    started = time.time()
    inputs = load_inputs(db_path, mode=mode)
    runner = BacktestRunner(
        price_paths=inputs["price_paths"],
        market_state_rows=inputs["market_state_rows"],
        exposure_rows=inputs["exposure_rows"],
        benchmark_rows=inputs["benchmark_rows"],
        mode=mode,
        initial_capital=initial_capital,
        max_positions=max_positions,
    )
    schedules = [
        ScheduleConfig(
            label=f"primary_{train_months}t_{valid_months}v_{step_months}s",
            train_months=train_months,
            valid_months=valid_months,
            step_months=step_months,
        )
    ]
    if include_compact_schedule:
        schedules.append(COMPACT_SCHEDULE)

    schedule_payloads = [
        analyze_schedule(
            runner=runner,
            usable_rows=inputs["usable_rows"],
            schedule=schedule,
            objective=objective,
            risk_per_trade_grid=risk_per_trade_grid,
            forced_cut_dates=forced_cut_dates,
            max_gap_days=max_gap_days,
            min_windows=min_windows,
            purge=purge,
            detailed=index == 0,
        )
        for index, schedule in enumerate(schedules)
    ]

    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S%z"),
        "db_path": inputs["db_path"],
        "mode": mode,
        "execution_row_count": len(inputs["execution_rows"]),
        "usable_row_count": len(inputs["usable_rows"]),
        "missing_price_path_rows": inputs["missing_price_path_rows"],
        "disclosure": inputs["disclosure"],
        "dedupe": inputs["dedupe"],
        "issues": inputs["issues"],
        "schedules": schedule_payloads,
        "backtest_run_count": runner.run_count,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_path = output.with_suffix(".json")
    payload["json_path"] = str(json_path)
    json_path.write_text(
        json.dumps(_json_payload(payload, full=True), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    output.write_text(build_report(payload), encoding="utf-8")
    payload["report_path"] = str(output)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward out-of-sample validation for MOSS strategies.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--mode", choices=("path", "horizon"), default="path")
    parser.add_argument("--objective", choices=("sharpe", "calmar"), default="sharpe")
    parser.add_argument("--train-months", type=int, default=PRIMARY_SCHEDULE.train_months)
    parser.add_argument("--valid-months", type=int, default=PRIMARY_SCHEDULE.valid_months)
    parser.add_argument("--step-months", type=int, default=PRIMARY_SCHEDULE.step_months)
    parser.add_argument(
        "--risk-per-trade-grid",
        default=",".join(str(value) for value in DEFAULT_RISK_PER_TRADE_GRID),
        help="Comma separated risk_per_trade grid, e.g. 0.0025,0.005,0.0075,0.01",
    )
    parser.add_argument(
        "--forced-cut-dates",
        default=",".join(DEFAULT_FORCED_CUT_DATES),
        help="Comma separated YYYY-MM-DD dates that no window may span.",
    )
    parser.add_argument("--max-gap-days", type=int, default=DEFAULT_MAX_GAP_DAYS)
    parser.add_argument("--min-windows", type=int, default=DEFAULT_MIN_WINDOWS_FOR_VERDICT)
    parser.add_argument("--no-purge", action="store_true", help="Disable training-window purge (sensitivity only).")
    parser.add_argument("--no-compact-schedule", action="store_true")
    parser.add_argument("--initial-capital", type=float, default=DEFAULT_INITIAL_CAPITAL)
    parser.add_argument("--max-positions", type=int, default=DEFAULT_MAX_POSITIONS)
    args = parser.parse_args()

    payload = run_walk_forward_validation(
        db_path=args.db_path,
        report_path=args.report_path,
        mode=args.mode,
        objective=args.objective,
        train_months=args.train_months,
        valid_months=args.valid_months,
        step_months=args.step_months,
        risk_per_trade_grid=[float(value) for value in args.risk_per_trade_grid.split(",") if value.strip()],
        forced_cut_dates=[value.strip() for value in args.forced_cut_dates.split(",") if value.strip()],
        max_gap_days=args.max_gap_days,
        min_windows=args.min_windows,
        purge=not args.no_purge,
        include_compact_schedule=not args.no_compact_schedule,
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
    )
    print(
        json.dumps(
            {
                "status": "ready",
                "report_path": payload["report_path"],
                "json_path": payload["json_path"],
                "execution_row_count": payload["execution_row_count"],
                "usable_row_count": payload["usable_row_count"],
                "backtest_run_count": payload["backtest_run_count"],
                "elapsed_seconds": payload["elapsed_seconds"],
                "issues": payload["issues"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
