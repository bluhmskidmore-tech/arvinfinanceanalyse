from __future__ import annotations

import json
import math
import uuid
from bisect import bisect_right
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import duckdb
from backend.app.core_finance.candidate_history_proxy_backtest import (
    CYCLE_PROXY_ENTRY_PRICE_WARNING,
    CYCLE_PROXY_FORMULA_VERSION,
    PORTFOLIO_PROXY_ENTRY_PRICE_WARNING,
    PORTFOLIO_PROXY_FORMULA_VERSION,
    build_candidate_history_portfolio_series,
    build_candidate_history_portfolio_summary,
    build_cycle_proxy_nav_series,
    build_cycle_proxy_summary,
    candidate_history_portfolio_price_field_stats,
    cycle_proxy_return_field_stats,
)
from backend.app.core_finance.field_normalization import (
    TRADING_STATUS_SQL_IN_LIST,
    is_trading_status,
)
from backend.app.core_finance.matched_baseline import (
    MATCHED_BASELINE_TABLE,
    matched_baseline_stats_from_rows,
)
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

if TYPE_CHECKING:
    from backend.app.tasks.choice_stock_materialize import ChoiceStockMaterializationCoverage


def load_choice_stock_materialization_coverage(**kwargs: Any) -> ChoiceStockMaterializationCoverage:
    """延迟导入 tasks 层的覆盖度读取：只读路径导入本模块时不得触发
    backend.app.tasks（dramatiq broker/actor 注册）初始化。保留模块级
    同名符号，测试仍可 monkeypatch 本模块属性。"""
    from backend.app.tasks.choice_stock_materialize import (
        load_choice_stock_materialization_coverage as _load_coverage,
    )

    return _load_coverage(**kwargs)


EMPTY_SOURCE_VERSION = "sv_livermore_candidate_history_empty"
EMPTY_VENDOR_VERSION = "vv_none"
RESULT_KIND = "market_data.livermore.candidate_history"
RULE_VERSION = "rv_livermore_candidate_history_v1"
CACHE_VERSION = "cv_livermore_candidate_history_v2"
STRATEGY_SCORE_RESULT_KIND = "market_data.livermore.strategy_score"
STRATEGY_SCORE_RULE_VERSION = "rv_livermore_strategy_score_v1"
STRATEGY_SCORE_CACHE_VERSION = "cv_livermore_strategy_score_v1"
STRATEGY_OPTIMIZATION_RESULT_KIND = "market_data.livermore.strategy_optimization"
STRATEGY_OPTIMIZATION_RULE_VERSION = "rv_livermore_strategy_optimization_v1"
STRATEGY_OPTIMIZATION_CACHE_VERSION = "cv_livermore_strategy_optimization_v1"
STRATEGY_FAMILY_READINESS_CONTRACT_VERSION = "rv_livermore_strategy_family_readiness_v1"
CYCLE_PROXY_BACKTEST_RESULT_KIND = "market_data.livermore.cycle_proxy_backtest"
CYCLE_PROXY_BACKTEST_RULE_VERSION = "rv_livermore_cycle_proxy_backtest_v1"
CYCLE_PROXY_BACKTEST_CACHE_VERSION = "cv_livermore_cycle_proxy_backtest_v1"
CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RESULT_KIND = "market_data.livermore.candidate_history_portfolio_backtest"
CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RULE_VERSION = "rv_livermore_candidate_history_portfolio_backtest_v1"
CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_CACHE_VERSION = "cv_livermore_candidate_history_portfolio_backtest_v1"
TABLE_HIST = "livermore_candidate_history"
TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
BENCHMARK_SERIES_ID = "CA.CSI300"
TABLE_BENCHMARK_DAILY = "fact_choice_macro_daily"
TABLE_BENCHMARK_SNAPSHOT = "choice_market_snapshot"
_DEFAULT_SIGNAL_KINDS = ["hybrid_fusion", "stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"]
_STRATEGY_LABELS = {
    "hybrid_fusion": "融合策略",
    "stock_candidate": "趋势突破",
    "factor_screen": "多因子",
    "theme_breakout": "题材突变",
    "mean_reversion": "超跌反弹",
}
STRATEGY_FAMILY_CONTRACT_VERSION = "rv_livermore_strategy_family_contract_v1"
_STRATEGY_SCORE_FAMILY_SIGNAL_KINDS = {
    "stock_candidate",
    "hybrid_fusion",
    "theme_breakout",
    "factor_screen",
    "mean_reversion",
}
_STRATEGY_FAMILY_BY_SIGNAL_KIND = {
    "stock_candidate": "trend_core",
    "hybrid_fusion": "hybrid_fusion",
    "theme_breakout": "theme_breakout",
    "factor_screen": "factor_screen",
    "mean_reversion": "mean_reversion",
    "fresh_trend_watchlist": "fresh_trend_watchlist",
    "uptrend_momentum": "uptrend_momentum_observation",
}
_STRATEGY_FAMILY_LABELS = {
    "trend_core": "Trend core",
    "hybrid_fusion": "Hybrid fusion",
    "theme_breakout": "Theme breakout",
    "factor_screen": "Factor screen",
    "mean_reversion": "Mean reversion",
    "fresh_trend_watchlist": "Fresh trend watchlist",
    "uptrend_momentum_observation": "Uptrend momentum observation",
}
_STRATEGY_FAMILY_FIELDS = (
    "family_key",
    "family_label",
    "family_contract_version",
    "primary_sample_size",
)
_HORIZON_LABELS = {
    "return_1d": "T+1",
    "return_5d": "T+5",
    "return_10d": "T+10",
    "return_20d": "T+20",
}
_STRATEGY_REVIEW_HORIZON = "return_5d"
_STRATEGY_REVIEW_LONG_HORIZON = "return_20d"
_STRATEGY_REVIEW_MIN_T5_SAMPLE = 30
_STRATEGY_REVIEW_MIN_T5_WIN_RATE = 0.5
_STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR = 0.012
_STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_TARGET = 0.024
_ENTRY_ALLOWED_STATES = POLICY.entry_observation_states
_COMPLETION_HORIZONS = ("return_1d", "return_5d", "return_20d")
_FORWARD_COVERAGE_COMPLETE = "complete"
_FORWARD_COVERAGE_PENDING = "pending"
_FORWARD_COVERAGE_MISSING_BAR = "missing_bar"
_FORWARD_COVERAGE_PARTIAL_HALT = "partial_halt"
_FORWARD_COVERAGE_STATUSES = (
    _FORWARD_COVERAGE_COMPLETE,
    _FORWARD_COVERAGE_PENDING,
    _FORWARD_COVERAGE_MISSING_BAR,
    _FORWARD_COVERAGE_PARTIAL_HALT,
)
_FORWARD_COVERAGE_MATURITY_FORWARD_BARS = 20
_FORWARD_MATURITY_HORIZONS = {"1d": 1, "5d": 5, "10d": 10, "20d": 20}
_FORWARD_MATURITY_STATUSES = (
    "natural_pending",
    "complete",
    "matured_missing_bar",
    "raw_matured_adjustment_missing",
    "partial_halt",
)
_FORWARD_RETURN_KEYS = ("return_1d", "return_5d", "return_10d", "return_20d")
_ADJUSTED_FORWARD_RETURN_KEYS = {
    "return_1d": "return_1d_adj",
    "return_5d": "return_5d_adj",
    "return_10d": "return_10d_adj",
    "return_20d": "return_20d_adj",
}
_EXECUTION_RETURN_KEYS = {
    "return_1d": "return_1d_net_adj",
    "return_5d": "return_5d_net_adj",
    "return_10d": "return_10d_net_adj",
    "return_20d": "return_20d_net_adj",
}
_EXECUTION_METRIC_BASIS = "net_next_open_adj"
_CYCLE_PROXY_SIGNAL_KIND = "stock_candidate"
_CYCLE_PROXY_MAX_RANK = 6
_CYCLE_PROXY_ALLOWED_MARKET_STATES = POLICY.entry_observation_states
_PORTFOLIO_BACKTEST_SIGNAL_KIND = "stock_candidate"
_PORTFOLIO_BACKTEST_MAX_RANK = 6
_PORTFOLIO_BACKTEST_ALLOWED_MARKET_STATES = POLICY.entry_observation_states
_CYCLE_PROXY_MISSING_FULL_STRATEGY_INPUTS = [
    "PMI",
    "credit_impulse",
    "price_spread",
    "industry_profit_cycle",
    "industry_revenue_cycle",
    "fund_flow",
    "turnover_persistence",
    "northbound_flow",
    "valuation_percentile_history",
    "earnings_revision",
]

_SELECT_COLUMNS = (
    "snapshot_as_of_date",
    "stock_code",
    "stock_name",
    "candidate_rank",
    "sector_code",
    "sector_name",
    "selection_close",
    "forward_trade_date_1d",
    "forward_trade_date_5d",
    "forward_trade_date_10d",
    "forward_trade_date_20d",
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "return_1d_adj",
    "return_5d_adj",
    "return_10d_adj",
    "return_20d_adj",
    "data_status",
    "formula_version",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
    "signal_kind",
    "theme_key",
    "theme_name",
    "theme_source_kind",
    "theme_rank",
    "stock_rank_in_theme",
    "sector_rank",
    "market_state",
    "abnormal_turnover",
    "gap_norm",
    "breakout_extension_norm",
    "breakout_level",
    "ema10",
    "ma20",
    "ma60",
    "ma120",
    "strength_pctchange",
    "strength_turn",
    "strength_amplitude",
    "close_strength",
    "closed_up_limit",
    "signal_evidence_json",
)
_EXECUTION_SELECT_COLUMNS = (
    "signal_date",
    "stock_code",
    "signal_kind",
    "market_state",
    "entry_executable",
    "entry_block_reason",
    "entry_date",
    "exit_date_5d",
    "return_1d_net_adj",
    "return_5d_gross_adj",
    "return_5d_net_adj",
    "return_10d_net_adj",
    "return_20d_net_adj",
)
_MATCHED_BASELINE_SELECT_COLUMNS = (
    "signal_date",
    "candidate_stock_code",
    "signal_kind",
    "control_stock_code",
    "control_group",
    "control_return_1d_net_adj",
    "control_return_5d_net_adj",
    "control_return_10d_net_adj",
    "control_return_20d_net_adj",
    "control_entry_executable",
    "seed",
    "formula_version",
    "run_id",
)


def livermore_candidate_history_envelope(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    limit: int,
    evaluation_as_of_date: str | None = None,
) -> dict[str, object]:
    """Read persisted candidate history slice; DuckDB SELECT only (API read-only)."""
    trimmed_code = stock_code.strip().upper() if stock_code else None
    trimmed_code = trimmed_code if trimmed_code else None
    normalized_snapshot_from = snapshot_from.strip() if snapshot_from else None
    normalized_snapshot_to = snapshot_to.strip() if snapshot_to else None
    requested_evaluation_date = _strict_optional_date(evaluation_as_of_date)
    empty_evaluation_date = requested_evaluation_date or _normalize_date_text(normalized_snapshot_to) or date.today().isoformat()
    empty_snapshot_to = _safe_optional_date(normalized_snapshot_to)
    empty_effective_snapshot_to = min(
        empty_evaluation_date,
        empty_snapshot_to or empty_evaluation_date,
    )

    def build_empty_payload() -> dict[str, object]:
        return {
            "items": [],
            "summary": _build_summary([], evaluation_as_of_date=empty_evaluation_date),
            "backtest_window_summary": livermore_candidate_history_backtest_window_summary(
                duckdb_path=duckdb_path,
                stock_code=trimmed_code,
                snapshot_from=normalized_snapshot_from,
                snapshot_to=empty_effective_snapshot_to,
                evaluation_as_of_date=empty_evaluation_date,
            ),
            "stock_code": trimmed_code,
            "snapshot_from": normalized_snapshot_from,
            "snapshot_to": normalized_snapshot_to,
            "effective_snapshot_to": empty_effective_snapshot_to,
            "limit": limit,
            "evaluation_as_of_date": empty_evaluation_date,
        }

    path = Path(duckdb_path)
    if not path.is_file():
        return _wrap_empty_envelope(payload=build_empty_payload())

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {r[0] for r in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            return _wrap_empty_envelope(payload=build_empty_payload())
        available_columns = _available_columns(conn)
        resolved_evaluation_date = _resolve_evaluation_as_of_date(
            conn,
            tables=tables,
            requested_evaluation_as_of_date=requested_evaluation_date,
            fallback_date=normalized_snapshot_to,
        )
        effective_snapshot_to = min(
            resolved_evaluation_date,
            _safe_optional_date(normalized_snapshot_to) or resolved_evaluation_date,
        )

        where_clauses: list[str] = []
        bindings: list[object] = []
        if trimmed_code:
            where_clauses.append("stock_code = ?")
            bindings.append(trimmed_code)
        if normalized_snapshot_from:
            where_clauses.append("snapshot_as_of_date >= ?")
            bindings.append(normalized_snapshot_from[:10])
        where_clauses.append("try_cast(snapshot_as_of_date as date) <= cast(? as date)")
        bindings.append(effective_snapshot_to)
        sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
        filter_bindings = list(bindings)

        rows = conn.execute(
            f"""
            select {_select_list(available_columns)}
            from {TABLE_HIST}
            {sql_where}
            order by snapshot_as_of_date desc, candidate_rank asc
            limit ?
            """,
            [*filter_bindings, limit],
        ).fetchall()
        items = [_normalize_row(row) for row in rows]
        _annotate_forward_maturity(
            conn,
            items=items,
            tables=tables,
            evaluation_as_of_date=resolved_evaluation_date,
            rewrite_legacy_status=requested_evaluation_date is not None,
        )
        all_filtered_maturity = _all_filtered_forward_maturity_summary(
            conn,
            tables=tables,
            available_columns=available_columns,
            sql_where=sql_where,
            filter_bindings=filter_bindings,
            evaluation_as_of_date=resolved_evaluation_date,
        )
        execution_rows = (
            _load_execution_window_rows(
                conn,
                stock_code=trimmed_code,
                snapshot_from=normalized_snapshot_from,
                snapshot_to=normalized_snapshot_to,
            )
            if TABLE_EXECUTION_HIST in tables
            else None
        )
        matched_baseline_rows = (
            _load_matched_baseline_window_rows(
                conn,
                stock_code=trimmed_code,
                snapshot_from=normalized_snapshot_from,
                snapshot_to=normalized_snapshot_to,
            )
            if MATCHED_BASELINE_TABLE in tables
            else None
        )
        if requested_evaluation_date is not None:
            execution_rows = None
            matched_baseline_rows = None
    finally:
        conn.close()

    lineage_src = _first_nonempty_source_version(items)
    lineage_vend = _first_nonempty_vendor_version(items)

    backtest_window_summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=duckdb_path,
        stock_code=trimmed_code,
        snapshot_from=normalized_snapshot_from,
        snapshot_to=effective_snapshot_to,
        evaluation_as_of_date=resolved_evaluation_date,
    )
    backtest_window_summary = dict(backtest_window_summary)
    backtest_window_summary["forward_coverage_row_counts"] = _forward_coverage_counts(items)
    backtest_window_summary["outcome_evaluation_as_of_date"] = resolved_evaluation_date
    summary = _build_summary(
        items,
        backtest_window_summary=backtest_window_summary,
        execution_rows=execution_rows,
        matched_baseline_rows=matched_baseline_rows,
        evaluation_as_of_date=resolved_evaluation_date,
    )
    returned_maturity = summary.get("forward_maturity")
    if isinstance(returned_maturity, dict):
        returned_maturity["scope"] = "returned_slice"
        returned_maturity["returned_slice_row_count"] = len(items)
        returned_maturity["all_filtered"] = all_filtered_maturity
    result_payload = {
        "items": items,
        "summary": summary,
        "backtest_window_summary": backtest_window_summary,
        "stock_code": trimmed_code,
        "snapshot_from": normalized_snapshot_from,
        "snapshot_to": normalized_snapshot_to,
        "effective_snapshot_to": effective_snapshot_to,
        "limit": limit,
        "returned_row_count": len(items),
        "all_filtered_row_count": all_filtered_maturity["row_count"],
        "evaluation_as_of_date": resolved_evaluation_date,
    }

    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=lineage_src,
        rule_version=RULE_VERSION,
        quality_flag=cast(
            QualityFlag,
            "warning"
            if not items or all_filtered_maturity.get("classification_available") is False
            else "ok",
        ),
        vendor_version=lineage_vend or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "stock_code": trimmed_code,
            "snapshot_from": result_payload["snapshot_from"],
            "snapshot_to": result_payload["snapshot_to"],
            "effective_snapshot_to": effective_snapshot_to,
            "limit": limit,
            "evaluation_as_of_date": resolved_evaluation_date,
        },
        tables_used=[TABLE_HIST]
        + ([TABLE_OBS] if TABLE_OBS in tables else [])
        + ([TABLE_EXECUTION_HIST] if execution_rows is not None else [])
        + ([MATCHED_BASELINE_TABLE] if matched_baseline_rows is not None else []),
        evidence_rows=len(items),
        result_payload=result_payload,
    )


def livermore_candidate_history_envelope_or_none(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    limit: int,
) -> dict[str, object] | None:
    try:
        return livermore_candidate_history_envelope(
            duckdb_path=duckdb_path,
            stock_code=stock_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            limit=limit,
        )
    except duckdb.Error:
        return None


def livermore_candidate_history_strategy_score_envelope(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
    macro_context_loader: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, object]:
    """Read persisted candidate history and score strategies by market state; DuckDB SELECT only."""
    normalized_horizon = primary_horizon if primary_horizon in _HORIZON_LABELS else "return_5d"
    path = Path(duckdb_path)
    if not path.is_file():
        resolved_to = _normalize_date_text(snapshot_to) or date.today().isoformat()
        resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
        payload = _build_strategy_score_payload(
            items=[],
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
            current_market_state=current_market_state,
            min_sample=min_sample,
            primary_horizon=normalized_horizon,
            backtest_window_summary=_empty_backtest_window_summary(
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
            ),
            macro_context=_load_strategy_macro_context(macro_context_loader, resolved_to),
        )
        return _wrap_strategy_score_envelope(
            payload=payload,
            source_version=EMPTY_SOURCE_VERSION,
            vendor_version=EMPTY_VENDOR_VERSION,
            evidence_rows=0,
            quality_flag="warning",
        )

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            resolved_to = _normalize_date_text(snapshot_to) or date.today().isoformat()
            resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
            payload = _build_strategy_score_payload(
                items=[],
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
                current_market_state=current_market_state,
                min_sample=min_sample,
                primary_horizon=normalized_horizon,
                backtest_window_summary=_empty_backtest_window_summary(
                    snapshot_from=resolved_from,
                    snapshot_to=resolved_to,
                ),
                macro_context=_load_strategy_macro_context(macro_context_loader, resolved_to),
            )
            return _wrap_strategy_score_envelope(
                payload=payload,
                source_version=EMPTY_SOURCE_VERSION,
                vendor_version=EMPTY_VENDOR_VERSION,
                evidence_rows=0,
                quality_flag="warning",
            )

        resolved_to = _normalize_date_text(snapshot_to) or _latest_history_snapshot_date(conn) or date.today().isoformat()
        resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
        items = _load_backtest_window_rows(
            conn,
            stock_code=None,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
        row_dates = _snapshot_row_dates(items)
        trade_dates = _resolve_replay_trade_dates(
            conn,
            tables=tables,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
            row_dates=row_dates,
        )
    finally:
        conn.close()

    backtest_window_summary = _build_backtest_window_summary_from_rows(
        duckdb_path=duckdb_path,
        rows=items,
        trade_dates=trade_dates,
        history_table_present=True,
        base_summary=_empty_backtest_window_summary(snapshot_from=resolved_from, snapshot_to=resolved_to),
    )
    if backtest_window_summary.get("status") in {"valid", "partial"}:
        scoring_items = _horizon_usable_items(items, backtest_window_summary=backtest_window_summary)
    else:
        scoring_items = items
    payload = _build_strategy_score_payload(
        items=scoring_items,
        snapshot_from=resolved_from,
        snapshot_to=resolved_to,
        current_market_state=current_market_state,
        min_sample=min_sample,
        primary_horizon=normalized_horizon,
        backtest_window_summary=backtest_window_summary,
        macro_context=_load_strategy_macro_context(macro_context_loader, resolved_to),
    )
    return _wrap_strategy_score_envelope(
        payload=payload,
        source_version=_first_nonempty_source_version(scoring_items or items),
        vendor_version=_first_nonempty_vendor_version(scoring_items or items) or EMPTY_VENDOR_VERSION,
        evidence_rows=len(scoring_items),
        quality_flag="ok" if scoring_items else "warning",
    )


def livermore_candidate_history_strategy_optimization_envelope(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
    macro_context_loader: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, object]:
    """Read candidate history and diagnose T+n strategy slices; DuckDB SELECT only."""
    normalized_horizon = primary_horizon if primary_horizon in _HORIZON_LABELS else "return_5d"
    path = Path(duckdb_path)
    if not path.is_file():
        resolved_to = _normalize_date_text(snapshot_to) or date.today().isoformat()
        resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
        payload = _build_strategy_optimization_payload(
            items=[],
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
            current_market_state=current_market_state,
            min_sample=min_sample,
            primary_horizon=normalized_horizon,
            backtest_window_summary=_empty_backtest_window_summary(
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
            ),
            macro_context=_load_strategy_macro_context(macro_context_loader, resolved_to),
        )
        return _wrap_strategy_optimization_envelope(
            payload=payload,
            source_version=EMPTY_SOURCE_VERSION,
            vendor_version=EMPTY_VENDOR_VERSION,
            evidence_rows=0,
            quality_flag="warning",
        )

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            resolved_to = _normalize_date_text(snapshot_to) or date.today().isoformat()
            resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
            payload = _build_strategy_optimization_payload(
                items=[],
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
                current_market_state=current_market_state,
                min_sample=min_sample,
                primary_horizon=normalized_horizon,
                backtest_window_summary=_empty_backtest_window_summary(
                    snapshot_from=resolved_from,
                    snapshot_to=resolved_to,
                ),
                macro_context=_load_strategy_macro_context(macro_context_loader, resolved_to),
            )
            return _wrap_strategy_optimization_envelope(
                payload=payload,
                source_version=EMPTY_SOURCE_VERSION,
                vendor_version=EMPTY_VENDOR_VERSION,
                evidence_rows=0,
                quality_flag="warning",
            )

        resolved_to = _normalize_date_text(snapshot_to) or _latest_history_snapshot_date(conn) or date.today().isoformat()
        resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
        items = _load_backtest_window_rows(
            conn,
            stock_code=None,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
        row_dates = _snapshot_row_dates(items)
        trade_dates = _resolve_replay_trade_dates(
            conn,
            tables=tables,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
            row_dates=row_dates,
        )
    finally:
        conn.close()

    backtest_window_summary = _build_backtest_window_summary_from_rows(
        duckdb_path=duckdb_path,
        rows=items,
        trade_dates=trade_dates,
        history_table_present=True,
        base_summary=_empty_backtest_window_summary(snapshot_from=resolved_from, snapshot_to=resolved_to),
    )
    if backtest_window_summary.get("status") in {"valid", "partial"}:
        optimizer_items = _horizon_usable_items(items, backtest_window_summary=backtest_window_summary)
    else:
        optimizer_items = items
    payload = _build_strategy_optimization_payload(
        items=optimizer_items,
        snapshot_from=resolved_from,
        snapshot_to=resolved_to,
        current_market_state=current_market_state,
        min_sample=min_sample,
        primary_horizon=normalized_horizon,
        backtest_window_summary=backtest_window_summary,
        macro_context=_load_strategy_macro_context(macro_context_loader, resolved_to),
    )
    return _wrap_strategy_optimization_envelope(
        payload=payload,
        source_version=_first_nonempty_source_version(optimizer_items or items),
        vendor_version=_first_nonempty_vendor_version(optimizer_items or items) or EMPTY_VENDOR_VERSION,
        evidence_rows=len(optimizer_items),
        quality_flag="ok" if optimizer_items else "warning",
    )


def livermore_candidate_history_cycle_proxy_backtest_envelope(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> dict[str, object]:
    """Build a point-in-time proxy NAV from completed stock-candidate rows; DuckDB SELECT only."""
    path = Path(duckdb_path)
    resolved_from = _normalize_date_text(snapshot_from)
    resolved_to = _normalize_date_text(snapshot_to)
    if not path.is_file():
        payload = _build_cycle_proxy_backtest_payload(
            items=[],
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
        return _wrap_cycle_proxy_backtest_envelope(
            payload=payload,
            source_version=EMPTY_SOURCE_VERSION,
            vendor_version=EMPTY_VENDOR_VERSION,
            evidence_rows=0,
            quality_flag="warning",
        )

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            payload = _build_cycle_proxy_backtest_payload(
                items=[],
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
            )
            return _wrap_cycle_proxy_backtest_envelope(
                payload=payload,
                source_version=EMPTY_SOURCE_VERSION,
                vendor_version=EMPTY_VENDOR_VERSION,
                evidence_rows=0,
                quality_flag="warning",
            )
        if resolved_to is None:
            resolved_to = _latest_history_snapshot_date(conn)
        rows = _load_backtest_window_rows(
            conn,
            stock_code=None,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
        execution_rows = (
            _load_execution_window_rows(
                conn,
                stock_code=None,
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
            )
            if TABLE_EXECUTION_HIST in tables
            else []
        )
        rows = _enrich_cycle_proxy_execution_returns(rows, execution_rows=execution_rows)
        proxy_nav = build_cycle_proxy_nav_series(_cycle_proxy_items(rows))
        benchmark_rows, benchmark_table = _load_benchmark_rows_for_nav_series(
            conn,
            tables=tables,
            nav_series=proxy_nav,
        )
    finally:
        conn.close()

    payload = _build_cycle_proxy_backtest_payload(
        items=rows,
        snapshot_from=resolved_from,
        snapshot_to=resolved_to,
        benchmark_rows=benchmark_rows,
    )
    proxy_items = _cycle_proxy_items(rows)
    return _wrap_cycle_proxy_backtest_envelope(
        payload=payload,
        source_version=_first_nonempty_source_version(proxy_items or rows),
        vendor_version=_first_nonempty_vendor_version(proxy_items or rows) or EMPTY_VENDOR_VERSION,
        evidence_rows=len(proxy_items),
        quality_flag="ok" if proxy_items else "warning",
        tables_used=_append_optional_table(
            _append_optional_table(
                [TABLE_HIST],
                TABLE_EXECUTION_HIST if execution_rows else None,
            ),
            benchmark_table,
        ),
    )


def livermore_candidate_history_portfolio_backtest_envelope(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> dict[str, object]:
    """Build a monthly candidate-history portfolio proxy from landed daily closes; DuckDB SELECT only."""
    path = Path(duckdb_path)
    resolved_from = _normalize_date_text(snapshot_from)
    resolved_to = _normalize_date_text(snapshot_to)
    if not path.is_file():
        payload = _build_candidate_history_portfolio_backtest_payload(
            items=[],
            close_rows=[],
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
        return _wrap_candidate_history_portfolio_backtest_envelope(
            payload=payload,
            source_version=EMPTY_SOURCE_VERSION,
            vendor_version=EMPTY_VENDOR_VERSION,
            evidence_rows=0,
            quality_flag="warning",
        )

    benchmark_rows: list[dict[str, Any]] = []
    benchmark_table: list[str] = []
    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables or TABLE_OBS not in tables:
            payload = _build_candidate_history_portfolio_backtest_payload(
                items=[],
                close_rows=[],
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
            )
            return _wrap_candidate_history_portfolio_backtest_envelope(
                payload=payload,
                source_version=EMPTY_SOURCE_VERSION,
                vendor_version=EMPTY_VENDOR_VERSION,
                evidence_rows=0,
                quality_flag="warning",
            )
        if resolved_to is None:
            resolved_to = _latest_history_snapshot_date(conn)
        rows = _load_backtest_window_rows(
            conn,
            stock_code=None,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
        monthly_rebalances = _candidate_history_portfolio_rebalance_rows(rows)
        has_adjustment_factor = _candidate_history_portfolio_has_adjustment_factor(conn, tables=tables)
        close_rows = _load_candidate_history_portfolio_close_rows(
            conn,
            rebalances=monthly_rebalances,
            snapshot_to=resolved_to,
            has_adjustment_factor=has_adjustment_factor,
        )
        portfolio_nav, _rebalance_log, _stale_price_codes = build_candidate_history_portfolio_series(
            rebalances=monthly_rebalances,
            close_rows=close_rows,
        )
        benchmark_rows, benchmark_table = _load_benchmark_rows_for_nav_series(
            conn,
            tables=tables,
            nav_series=portfolio_nav,
        )
    finally:
        conn.close()

    payload = _build_candidate_history_portfolio_backtest_payload(
        items=rows,
        close_rows=close_rows,
        snapshot_from=resolved_from,
        snapshot_to=resolved_to,
        benchmark_rows=benchmark_rows,
    )
    evidence_items = [row for rebalance in _candidate_history_portfolio_rebalance_rows(rows) for row in rebalance["items"]]
    return _wrap_candidate_history_portfolio_backtest_envelope(
        payload=payload,
        source_version=_first_nonempty_source_version(evidence_items or rows),
        vendor_version=_first_nonempty_vendor_version(evidence_items or rows) or EMPTY_VENDOR_VERSION,
        evidence_rows=len(evidence_items),
        quality_flag="ok" if payload["summary"] else "warning",
        tables_used=_append_optional_table(
            [TABLE_HIST, TABLE_OBS, *([TABLE_ADJ_FACTOR] if has_adjustment_factor else [])],
            benchmark_table,
        ),
    )


def _available_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_HIST}')").fetchall()}


def _available_execution_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_EXECUTION_HIST}')").fetchall()}


def _available_matched_baseline_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        str(row[1]).lower()
        for row in conn.execute(f"pragma table_info('{MATCHED_BASELINE_TABLE}')").fetchall()
    }


def livermore_candidate_history_backtest_window_summary(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    evaluation_as_of_date: str | None = None,
) -> dict[str, Any]:
    trimmed_code = stock_code.strip().upper() if stock_code else None
    trimmed_code = trimmed_code if trimmed_code else None
    normalized_from = _normalize_date_text(snapshot_from)
    normalized_to = _normalize_date_text(snapshot_to)
    normalized_evaluation_date = _strict_optional_date(evaluation_as_of_date)
    effective_snapshot_to = (
        min(normalized_to or normalized_evaluation_date, normalized_evaluation_date)
        if normalized_evaluation_date
        else normalized_to
    )
    base_summary = _empty_backtest_window_summary(
        snapshot_from=normalized_from,
        snapshot_to=effective_snapshot_to,
    )

    path = Path(duckdb_path)
    if not path.is_file():
        return base_summary

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables and TABLE_OBS not in tables:
            return base_summary
        history_table_present = TABLE_HIST in tables
        rows = _load_backtest_window_rows(
            conn,
            stock_code=trimmed_code,
            snapshot_from=normalized_from,
            snapshot_to=effective_snapshot_to,
            evaluation_as_of_date=normalized_evaluation_date,
        )
        if normalized_evaluation_date:
            _annotate_forward_maturity(
                conn,
                items=rows,
                tables=tables,
                evaluation_as_of_date=normalized_evaluation_date,
                rewrite_legacy_status=True,
            )
        row_dates = _snapshot_row_dates(rows)
        trade_dates = _resolve_replay_trade_dates(
            conn,
            tables=tables,
            snapshot_from=normalized_from,
            snapshot_to=effective_snapshot_to,
            row_dates=row_dates,
        )
    finally:
        conn.close()

    return _build_backtest_window_summary_from_rows(
        duckdb_path=duckdb_path,
        rows=rows,
        trade_dates=trade_dates,
        history_table_present=history_table_present,
        base_summary=base_summary,
    )


def _snapshot_row_dates(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            normalized
            for row in rows
            if (normalized := _safe_optional_date(str(row.get("snapshot_as_of_date") or "")))
        }
    )


def _build_backtest_window_summary_from_rows(
    *,
    duckdb_path: str,
    rows: list[dict[str, Any]],
    trade_dates: list[str],
    history_table_present: bool,
    base_summary: dict[str, Any],
) -> dict[str, Any]:
    if not trade_dates:
        return base_summary

    rows_by_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        trade_date = str(row.get("snapshot_as_of_date") or "")[:10]
        if not trade_date:
            continue
        rows_by_date.setdefault(trade_date, []).append(row)

    completed_dates = 0
    pending_dates = 0
    unsupported_dates = 0
    proxy_only_dates = 0
    completed_rows = 0
    pending_rows = 0
    unsupported_rows = 0
    proxy_only_rows = 0
    included_dates: list[str] = []
    excluded_dates: list[str] = []
    date_reasons: list[dict[str, Any]] = []

    for trade_date in trade_dates:
        coverage = load_choice_stock_materialization_coverage(duckdb_path=duckdb_path, as_of_date=trade_date)
        classification = _classify_replay_date(
            trade_date=trade_date,
            coverage=coverage,
            rows=rows_by_date.get(trade_date, []),
            history_table_present=history_table_present,
        )
        status = str(classification["status"])
        row_count = len(rows_by_date.get(trade_date, []))
        if status == "completed":
            completed_dates += 1
            completed_rows += row_count
        elif status == "pending":
            pending_dates += 1
            pending_rows += row_count
        elif status == "unsupported":
            unsupported_dates += 1
            unsupported_rows += row_count
        elif status == "proxy_only":
            proxy_only_dates += 1
            proxy_only_rows += row_count

        if bool(classification["affects_completed_stats"]):
            included_dates.append(trade_date)
        else:
            excluded_dates.append(trade_date)

        public_reason = cast(dict[str, Any] | None, classification.get("public_reason"))
        if public_reason is not None:
            date_reasons.append(public_reason)

    if completed_dates and not (pending_dates or unsupported_dates or proxy_only_dates):
        window_status = "valid"
    elif completed_dates:
        window_status = "partial"
    else:
        window_status = "unsupported"

    return {
        "status": window_status,
        "snapshot_from": trade_dates[0],
        "snapshot_to": trade_dates[-1],
        "replay_dates_total": len(trade_dates),
        "replay_dates_completed": completed_dates,
        "replay_dates_pending": pending_dates,
        "replay_dates_unsupported": unsupported_dates,
        "replay_dates_proxy_only": proxy_only_dates,
        "completed_rows": completed_rows,
        "pending_rows": pending_rows,
        "unsupported_rows": unsupported_rows,
        "proxy_only_rows": proxy_only_rows,
        "forward_coverage_row_counts": _forward_coverage_counts(rows),
        "included_completed_stats_dates": included_dates,
        "excluded_from_completed_stats_dates": excluded_dates,
        "date_reasons": date_reasons,
    }


def _select_list(available_columns: set[str]) -> str:
    parts: list[str] = []
    for column in _SELECT_COLUMNS:
        if column.lower() in available_columns:
            parts.append(column)
        elif column == "signal_kind":
            parts.append("'stock_candidate' as signal_kind")
        else:
            parts.append(f"null as {column}")
    return ", ".join(parts)


def _execution_select_list(available_columns: set[str]) -> str:
    parts: list[str] = []
    for column in _EXECUTION_SELECT_COLUMNS:
        if column.lower() in available_columns:
            parts.append(column)
        elif column == "signal_kind":
            parts.append("'stock_candidate' as signal_kind")
        else:
            parts.append(f"null as {column}")
    return ", ".join(parts)


def _matched_baseline_select_list(available_columns: set[str]) -> str:
    parts: list[str] = []
    for column in _MATCHED_BASELINE_SELECT_COLUMNS:
        if column.lower() in available_columns:
            parts.append(column)
        elif column == "signal_kind":
            parts.append("'stock_candidate' as signal_kind")
        else:
            parts.append(f"null as {column}")
    return ", ".join(parts)


def _load_backtest_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    evaluation_as_of_date: str | None = None,
) -> list[dict[str, Any]]:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if TABLE_HIST not in tables:
        return []
    available_columns = _available_columns(conn)
    where_clauses: list[str] = []
    bindings: list[object] = []
    if stock_code:
        where_clauses.append("stock_code = ?")
        bindings.append(stock_code)
    if snapshot_from:
        where_clauses.append("snapshot_as_of_date >= ?")
        bindings.append(snapshot_from)
    if snapshot_to:
        where_clauses.append("snapshot_as_of_date <= ?")
        bindings.append(snapshot_to)
    sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = conn.execute(
        f"""
        select {_select_list(available_columns)}
        from {TABLE_HIST}
        {sql_where}
        order by snapshot_as_of_date asc, candidate_rank asc
        """,
        bindings,
    ).fetchall()
    items = [_normalize_row(row) for row in rows]
    if evaluation_as_of_date:
        return items
    return _annotate_forward_coverage(
        items,
        observation_trade_dates=_load_observation_trade_dates(
            conn,
            tables=tables,
            min_snapshot_date=_min_snapshot_date(items),
        ),
    )


def _load_execution_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> list[dict[str, Any]]:
    available_columns = _available_execution_columns(conn)
    where_clauses: list[str] = []
    bindings: list[object] = []
    if stock_code:
        where_clauses.append("stock_code = ?")
        bindings.append(stock_code)
    if snapshot_from:
        where_clauses.append("signal_date >= ?")
        bindings.append(snapshot_from[:10])
    if snapshot_to:
        where_clauses.append("signal_date <= ?")
        bindings.append(snapshot_to[:10])
    sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = conn.execute(
        f"""
        select {_execution_select_list(available_columns)}
        from {TABLE_EXECUTION_HIST}
        {sql_where}
        order by signal_date asc, stock_code asc
        """,
        bindings,
    ).fetchall()
    return [_normalize_execution_row(row) for row in rows]


def _load_matched_baseline_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> list[dict[str, Any]]:
    available_columns = _available_matched_baseline_columns(conn)
    where_clauses: list[str] = []
    bindings: list[object] = []
    if stock_code:
        where_clauses.append("candidate_stock_code = ?")
        bindings.append(stock_code)
    if snapshot_from:
        where_clauses.append("signal_date >= ?")
        bindings.append(snapshot_from[:10])
    if snapshot_to:
        where_clauses.append("signal_date <= ?")
        bindings.append(snapshot_to[:10])
    sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = conn.execute(
        f"""
        select {_matched_baseline_select_list(available_columns)}
        from {MATCHED_BASELINE_TABLE}
        {sql_where}
        order by signal_date asc, candidate_stock_code asc, control_stock_code asc
        """,
        bindings,
    ).fetchall()
    return [_normalize_matched_baseline_row(row) for row in rows]


def _normalize_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_SELECT_COLUMNS[i]: row[i] for i in range(len(_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item


def _normalize_execution_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_EXECUTION_SELECT_COLUMNS[i]: row[i] for i in range(len(_EXECUTION_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item


def _normalize_matched_baseline_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_MATCHED_BASELINE_SELECT_COLUMNS[i]: row[i] for i in range(len(_MATCHED_BASELINE_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item


def _min_snapshot_date(items: list[dict[str, Any]]) -> str | None:
    dates = [text for item in items if (text := str(item.get("snapshot_as_of_date") or "").strip()[:10])]
    return min(dates) if dates else None


def _load_observation_trade_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    min_snapshot_date: str | None,
) -> list[str]:
    """Distinct observation trade dates after the earliest snapshot (maturity reference; SELECT only)."""
    if TABLE_OBS not in tables or not min_snapshot_date:
        return []
    columns = {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_OBS}')").fetchall()}
    if "close_value" not in columns:
        return []
    rows = conn.execute(
        f"""
        select distinct trade_date
        from {TABLE_OBS}
        where trade_date > ?
          and close_value is not null
        """,
        [min_snapshot_date],
    ).fetchall()
    return sorted({str(row[0])[:10] for row in rows if str(row[0] or "").strip()})


def _annotate_forward_coverage(
    items: list[dict[str, Any]],
    *,
    observation_trade_dates: list[str],
) -> list[dict[str, Any]]:
    for item in items:
        item["forward_coverage"] = _derive_forward_coverage(
            item,
            observation_trade_dates=observation_trade_dates,
        )
    return items


def _derive_forward_coverage(
    item: dict[str, Any],
    *,
    observation_trade_dates: list[str],
) -> str:
    """Read-time refinement of data_status: split 'pending' into pending vs missing_bar.

    A pending row becomes missing_bar when the observation calendar already provides at least
    _FORWARD_COVERAGE_MATURITY_FORWARD_BARS trade dates after the row's snapshot date, yet
    forward returns are still absent: the forward window has matured, so the missing bars point
    to a delisting / unresumed halt / ingestion gap rather than an immature window. The stored
    data_status vocabulary is never rewritten; this marker is derived per read.
    """
    status = str(item.get("data_status") or "").strip()
    if status and status != _FORWARD_COVERAGE_PENDING:
        return status
    if not status and all(item.get(horizon) is not None for horizon in _COMPLETION_HORIZONS):
        return _FORWARD_COVERAGE_COMPLETE
    if not any(item.get(key) is None for key in _FORWARD_RETURN_KEYS):
        return _FORWARD_COVERAGE_PENDING
    snapshot_date = str(item.get("snapshot_as_of_date") or "").strip()[:10]
    if not snapshot_date or not observation_trade_dates:
        return _FORWARD_COVERAGE_PENDING
    forward_bar_count = len(observation_trade_dates) - bisect_right(observation_trade_dates, snapshot_date)
    if forward_bar_count >= _FORWARD_COVERAGE_MATURITY_FORWARD_BARS:
        return _FORWARD_COVERAGE_MISSING_BAR
    return _FORWARD_COVERAGE_PENDING


def _forward_coverage_of(item: dict[str, Any]) -> str:
    value = str(item.get("forward_coverage") or "").strip()
    if value:
        return value
    return _derive_forward_coverage(item, observation_trade_dates=[])


def _forward_coverage_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in _FORWARD_COVERAGE_STATUSES}
    for item in items:
        key = _forward_coverage_of(item)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _missing_bar_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if _forward_coverage_of(item) == _FORWARD_COVERAGE_MISSING_BAR)


def _forward_coverage_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _forward_coverage_counts(items)
    return {
        "row_count": len(items),
        "counts": counts,
        "missing_bar_row_count": counts[_FORWARD_COVERAGE_MISSING_BAR],
        "maturity_forward_bars": _FORWARD_COVERAGE_MATURITY_FORWARD_BARS,
        "maturity_reference": f"distinct forward trade dates in {TABLE_OBS}",
    }


def _annotate_forward_maturity(
    conn: duckdb.DuckDBPyConnection,
    *,
    items: list[dict[str, Any]],
    tables: set[str],
    evaluation_as_of_date: str,
    rewrite_legacy_status: bool,
) -> list[dict[str, Any]]:
    stock_observations, market_dates, source_issue = _load_forward_maturity_observations(
        conn,
        tables=tables,
        min_snapshot_date=_min_snapshot_date(items),
        evaluation_as_of_date=evaluation_as_of_date,
        stock_codes={str(item.get("stock_code") or "").strip().upper() for item in items},
    )
    for item in items:
        maturity = _derive_forward_maturity(
            item,
            stock_observations=stock_observations,
            market_dates=market_dates,
            evaluation_as_of_date=evaluation_as_of_date,
            source_issue=source_issue,
        )
        item["forward_maturity"] = maturity
        _mask_unverified_forward_outcomes(
            item,
            maturity=maturity,
            rewrite_legacy_status=rewrite_legacy_status,
        )
    return items


def _mask_unverified_forward_outcomes(
    item: dict[str, Any],
    *,
    maturity: dict[str, Any],
    rewrite_legacy_status: bool,
) -> None:
    raw_horizons = maturity.get("horizons")
    horizons = raw_horizons if isinstance(raw_horizons, dict) else {}
    statuses: dict[str, str] = {}
    for horizon in _FORWARD_MATURITY_HORIZONS:
        raw_horizon = horizons.get(horizon)
        horizon_item = raw_horizon if isinstance(raw_horizon, dict) else {}
        status = str(horizon_item.get("status") or "natural_pending")
        statuses[horizon] = status
        target_verified = bool(horizon_item.get("target_observation_verified"))
        raw_return = _maturity_finite_float(item.get(f"return_{horizon}"))
        adjusted_return = _maturity_finite_float(item.get(f"return_{horizon}_adj"))
        if not target_verified:
            item[f"forward_trade_date_{horizon}"] = None
            item[f"return_{horizon}"] = None
            item[f"return_{horizon}_adj"] = None
        elif raw_return is None:
            item[f"return_{horizon}"] = None
            item[f"return_{horizon}_adj"] = None
        elif adjusted_return is None:
            item[f"return_{horizon}"] = raw_return
            item[f"return_{horizon}_adj"] = None
        else:
            item[f"return_{horizon}"] = raw_return
            item[f"return_{horizon}_adj"] = adjusted_return

    if not rewrite_legacy_status:
        stored_status = str(item.get("data_status") or "").strip()
        item["forward_coverage"] = (
            stored_status if stored_status in _FORWARD_COVERAGE_STATUSES else _FORWARD_COVERAGE_PENDING
        )
        return

    if statuses and all(status == "complete" for status in statuses.values()):
        item["data_status"] = "complete"
    elif "partial_halt" in statuses.values():
        item["data_status"] = "partial_halt"
    else:
        item["data_status"] = "pending"

    long_status = statuses.get("20d", "natural_pending")
    item["forward_coverage"] = {
        "complete": _FORWARD_COVERAGE_COMPLETE,
        "matured_missing_bar": _FORWARD_COVERAGE_MISSING_BAR,
        "partial_halt": _FORWARD_COVERAGE_PARTIAL_HALT,
    }.get(long_status, _FORWARD_COVERAGE_PENDING)


def _load_forward_maturity_observations(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    min_snapshot_date: str | None,
    evaluation_as_of_date: str,
    stock_codes: set[str],
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str], str | None]:
    stock_codes = {code for code in stock_codes if code}
    if TABLE_OBS not in tables:
        return {}, [], "observation_table_missing"
    columns = {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_OBS}')").fetchall()}
    missing_columns = sorted({"trade_date", "stock_code", "close_value"} - columns)
    if missing_columns:
        return {}, [], f"observation_required_columns_missing:{','.join(missing_columns)}"
    if not min_snapshot_date or not stock_codes:
        return {}, [], None
    has_trade_status = "tradestatus" in columns
    status_select = "tradestatus" if has_trade_status else "null as tradestatus"
    valid_status_sql = (
        f"and lower(trim(cast(tradestatus as varchar))) in {TRADING_STATUS_SQL_IN_LIST}"
        if has_trade_status
        else ""
    )
    code_placeholders = ", ".join("?" for _ in stock_codes)
    rows = conn.execute(
        f"""
        with latest_revisions as (
          select
            trade_date,
            stock_code,
            close_value,
            {status_select},
            row_number() over (
              partition by
                upper(trim(cast(stock_code as varchar))),
                try_cast(trade_date as date)
              order by rowid desc
            ) as revision_rank
          from {TABLE_OBS}
          where try_cast(trade_date as date) > cast(? as date)
            and try_cast(trade_date as date) <= cast(? as date)
            and upper(trim(cast(stock_code as varchar))) in ({code_placeholders})
        )
        select trade_date, stock_code, close_value, tradestatus
        from latest_revisions
        where revision_rank = 1
        order by trade_date, stock_code
        """,
        [min_snapshot_date, evaluation_as_of_date, *sorted(stock_codes)],
    ).fetchall()
    market_rows = conn.execute(
        f"""
        with latest_revisions as (
          select
            trade_date,
            stock_code,
            close_value,
            {status_select},
            row_number() over (
              partition by
                upper(trim(cast(stock_code as varchar))),
                try_cast(trade_date as date)
              order by rowid desc
            ) as revision_rank
          from {TABLE_OBS}
          where try_cast(trade_date as date) > cast(? as date)
            and try_cast(trade_date as date) <= cast(? as date)
        )
        select distinct try_cast(trade_date as date)
        from latest_revisions
        where revision_rank = 1
          and try_cast(close_value as double) > 0
          and isfinite(try_cast(close_value as double))
          {valid_status_sql}
        order by 1
        """,
        [min_snapshot_date, evaluation_as_of_date],
    ).fetchall()
    observations: dict[str, dict[str, dict[str, Any]]] = {}
    market_dates = {
        normalized
        for row in market_rows
        if (normalized := _safe_optional_date(str(row[0] or "")))
    }
    for trade_date_raw, stock_code_raw, close_raw, trade_status_raw in rows:
        trade_date = _safe_optional_date(str(trade_date_raw or ""))
        stock_code = str(stock_code_raw or "").strip().upper()
        close_value = _maturity_positive_float(close_raw)
        if not trade_date or not stock_code:
            continue
        trade_status = str(trade_status_raw or "").strip()
        valid_close = close_value is not None and (
            not has_trade_status or _maturity_is_trading_status(trade_status)
        )
        observations.setdefault(stock_code, {})[trade_date] = {
            "close": close_value,
            "trade_status": trade_status,
            "valid_close": valid_close,
        }
    return observations, sorted(market_dates), None


def _derive_forward_maturity(
    item: dict[str, Any],
    *,
    stock_observations: dict[str, dict[str, dict[str, Any]]],
    market_dates: list[str],
    evaluation_as_of_date: str,
    source_issue: str | None = None,
) -> dict[str, Any]:
    if source_issue:
        return {
            "evaluation_as_of_date": evaluation_as_of_date,
            "horizons": {
                horizon: {
                    "status": "matured_missing_bar",
                    "reason": "observation_source_unavailable",
                    "horizon_bars": bar_count,
                    "target_trade_date": None,
                    "stock_valid_bar_count": 0,
                    "market_trade_date_count": 0,
                    "target_observation_verified": False,
                }
                for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items()
            },
            "maturity_clock": "individual_stock_valid_close_bars",
            "diagnostic_clock": "market_trade_dates",
            "source_status": "unavailable",
            "source_issue": source_issue,
            "classification_available": False,
        }
    snapshot_date = _safe_optional_date(str(item.get("snapshot_as_of_date") or ""))
    stock_code = str(item.get("stock_code") or "").strip().upper()
    stock_rows = stock_observations.get(stock_code, {})
    valid_dates = [
        trade_date
        for trade_date, row in sorted(stock_rows.items())
        if snapshot_date
        and snapshot_date < trade_date <= evaluation_as_of_date
        and bool(row.get("valid_close"))
    ]
    market_after_snapshot = [
        trade_date
        for trade_date in market_dates
        if snapshot_date and snapshot_date < trade_date <= evaluation_as_of_date
    ]
    explicit_halt = any(
        snapshot_date
        and snapshot_date < trade_date <= evaluation_as_of_date
        and bool(str(row.get("trade_status") or "").strip())
        and not _maturity_is_trading_status(str(row.get("trade_status") or ""))
        for trade_date, row in stock_rows.items()
    )
    horizons: dict[str, dict[str, Any]] = {}
    for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items():
        expected_target_date = valid_dates[bar_count - 1] if len(valid_dates) >= bar_count else None
        stored_target_date = _safe_optional_date(str(item.get(f"forward_trade_date_{horizon}") or ""))
        target_is_actual = bool(
            stored_target_date
            and stored_target_date <= evaluation_as_of_date
            and stored_target_date == expected_target_date
        )
        raw_return = _maturity_finite_float(item.get(f"return_{horizon}"))
        adjusted_return = _maturity_finite_float(item.get(f"return_{horizon}_adj"))
        if target_is_actual and raw_return is not None:
            status = "complete" if adjusted_return is not None else "raw_matured_adjustment_missing"
        elif len(market_after_snapshot) < bar_count:
            status = "natural_pending"
        elif explicit_halt and len(valid_dates) < bar_count:
            status = "partial_halt"
        else:
            status = "matured_missing_bar"
        horizons[horizon] = {
            "status": status,
            "horizon_bars": bar_count,
            "target_trade_date": stored_target_date if target_is_actual else None,
            "stock_valid_bar_count": len(valid_dates),
            "market_trade_date_count": len(market_after_snapshot),
            "target_observation_verified": target_is_actual,
        }
    return {
        "evaluation_as_of_date": evaluation_as_of_date,
        "horizons": horizons,
        "maturity_clock": "individual_stock_valid_close_bars",
        "diagnostic_clock": "market_trade_dates",
        "source_status": "available",
        "classification_available": True,
    }


def _forward_maturity_summary(
    items: list[dict[str, Any]],
    *,
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    source_issues = sorted(
        {
            str(maturity.get("source_issue"))
            for item in items
            if isinstance((maturity := item.get("forward_maturity")), dict)
            and maturity.get("classification_available") is False
            and maturity.get("source_issue")
        }
    )
    classification_available = not source_issues
    horizons: dict[str, dict[str, Any]] = {}
    for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items():
        counts = {status: 0 for status in _FORWARD_MATURITY_STATUSES}
        mature_dates: list[str] = []
        pending_dates: list[str] = []
        for item in items:
            maturity = item.get("forward_maturity")
            maturity_horizons = maturity.get("horizons") if isinstance(maturity, dict) else None
            horizon_item = maturity_horizons.get(horizon) if isinstance(maturity_horizons, dict) else None
            status = str(horizon_item.get("status") if isinstance(horizon_item, dict) else "natural_pending")
            if status not in counts:
                status = "matured_missing_bar"
            counts[status] += 1
            snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
            if status == "natural_pending":
                pending_dates.append(snapshot_date)
            else:
                mature_dates.append(snapshot_date)
        horizons[horizon] = {
            "horizon_bars": bar_count,
            "row_count": len(items),
            "counts": counts,
            "window_matured_row_count": len(items) - counts["natural_pending"],
            "natural_pending_row_count": counts["natural_pending"],
            "latest_mature_snapshot_date": max(mature_dates) if mature_dates else None,
            "latest_pending_snapshot_date": max(pending_dates) if pending_dates else None,
            "counts_authoritative": classification_available,
        }
    return {
        "scope": "returned_slice",
        "row_count": len(items),
        "evaluation_as_of_date": evaluation_as_of_date,
        "horizons": horizons,
        "maturity_clock": "individual_stock_valid_close_bars",
        "diagnostic_clock": "market_trade_dates",
        "source_status": "available" if classification_available else "unavailable",
        "classification_available": classification_available,
        "counts_authoritative": classification_available,
        **({"source_issue": source_issues[0]} if source_issues else {}),
    }


def _all_filtered_forward_maturity_summary(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    available_columns: set[str],
    sql_where: str,
    filter_bindings: list[object],
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    def date_expr(column: str) -> str:
        return f"try_cast({column} as date)" if column in available_columns else "cast(null as date)"

    def number_expr(column: str) -> str:
        return f"try_cast({column} as double)" if column in available_columns else "cast(null as double)"

    stock_expr = (
        "upper(trim(cast(stock_code as varchar)))"
        if "stock_code" in available_columns
        else "cast(null as varchar)"
    )
    filtered_sql = f"""
        select
          rowid as candidate_rowid,
          {date_expr("snapshot_as_of_date")} as snapshot_date,
          {stock_expr} as stock_code,
          {date_expr("forward_trade_date_1d")} as stored_date_1d,
          {date_expr("forward_trade_date_5d")} as stored_date_5d,
          {date_expr("forward_trade_date_10d")} as stored_date_10d,
          {date_expr("forward_trade_date_20d")} as stored_date_20d,
          {number_expr("return_1d")} as raw_return_1d,
          {number_expr("return_5d")} as raw_return_5d,
          {number_expr("return_10d")} as raw_return_10d,
          {number_expr("return_20d")} as raw_return_20d,
          {number_expr("return_1d_adj")} as adjusted_return_1d,
          {number_expr("return_5d_adj")} as adjusted_return_5d,
          {number_expr("return_10d_adj")} as adjusted_return_10d,
          {number_expr("return_20d_adj")} as adjusted_return_20d
        from {TABLE_HIST}
        {sql_where}
    """
    observation_columns = _table_columns_for_service(conn, TABLE_OBS) if TABLE_OBS in tables else set()
    required_observation_columns = {"trade_date", "stock_code", "close_value"}
    if not required_observation_columns.issubset(observation_columns):
        row = conn.execute(
            f"with filtered as ({filtered_sql}) select count(*)::bigint, max(snapshot_date) from filtered",
            filter_bindings,
        ).fetchone()
        row_count = int(row[0] or 0) if row else 0
        latest_snapshot = _safe_optional_date(str(row[1] if row else ""))
        missing_observation_columns = sorted(required_observation_columns - observation_columns)
        source_issue = (
            "observation_table_missing"
            if TABLE_OBS not in tables
            else f"observation_required_columns_missing:{','.join(missing_observation_columns)}"
        )
        return _empty_all_filtered_maturity_summary(
            row_count=row_count,
            latest_snapshot_date=latest_snapshot,
            evaluation_as_of_date=evaluation_as_of_date,
            source_issue=source_issue,
        )

    has_trade_status = "tradestatus" in observation_columns
    latest_status_select = (
        "first(cast(o.tradestatus as varchar) order by o.rowid desc)"
        if has_trade_status
        else "cast(null as varchar)"
    )
    scoped_valid_status_sql = (
        f"lower(trim(coalesce(o.trade_status, ''))) in {TRADING_STATUS_SQL_IN_LIST}"
        if has_trade_status
        else "true"
    )
    market_status_sql = (
        f"and lower(trim(coalesce(trade_status, ''))) in {TRADING_STATUS_SQL_IN_LIST}"
        if has_trade_status
        else ""
    )
    explicit_halt_sql = (
        "trim(coalesce(o.trade_status, '')) <> '' "
        f"and lower(trim(o.trade_status)) not in {TRADING_STATUS_SQL_IN_LIST}"
        if has_trade_status
        else "false"
    )
    rows = conn.execute(
        f"""
        with filtered as materialized ({filtered_sql}),
        candidate_bounds as (
          select min(snapshot_date) as minimum_snapshot_date
          from filtered
          where snapshot_date is not null
        ),
        candidate_stocks as (
          select stock_code, min(snapshot_date) as minimum_snapshot_date
          from filtered
          where stock_code is not null and snapshot_date is not null
          group by stock_code
        ),
        market_latest_observations as materialized (
          select
            upper(trim(cast(o.stock_code as varchar))) as stock_code,
            try_cast(o.trade_date as date) as trade_date,
            first(try_cast(o.close_value as double) order by o.rowid desc) as close_value,
            {latest_status_select} as trade_status
          from {TABLE_OBS} o
          cross join candidate_bounds bounds
          where bounds.minimum_snapshot_date is not null
            and try_cast(o.trade_date as date) > bounds.minimum_snapshot_date
            and try_cast(o.trade_date as date) <= cast(? as date)
          group by 1, 2
        ),
        market_dates as (
          select distinct trade_date
          from market_latest_observations
          where close_value > 0
            and isfinite(close_value)
            {market_status_sql}
        ),
        market_counts as (
          select f.candidate_rowid, count(m.trade_date)::bigint as market_count
          from filtered f
          left join market_dates m
            on f.snapshot_date is not null and m.trade_date > f.snapshot_date
          group by f.candidate_rowid
        ),
        candidate_observation_revisions as materialized (
          select
            upper(trim(cast(o.stock_code as varchar))) as stock_code,
            try_cast(o.trade_date as date) as trade_date,
            first(try_cast(o.close_value as double) order by o.rowid desc) as close_value,
            {latest_status_select} as trade_status
          from {TABLE_OBS} o
          join candidate_stocks stocks
            on stocks.stock_code = upper(trim(cast(o.stock_code as varchar)))
           and try_cast(o.trade_date as date) > stocks.minimum_snapshot_date
          where try_cast(o.trade_date as date) is not null
            and try_cast(o.trade_date as date) <= cast(? as date)
          group by 1, 2
        ),
        candidate_observations as materialized (
          select
            o.stock_code,
            o.trade_date,
            (
              o.close_value > 0
              and isfinite(o.close_value)
              and {scoped_valid_status_sql}
            ) as valid_close,
            ({explicit_halt_sql}) as explicit_halt
          from candidate_observation_revisions o
        ),
        valid_observations as (
          select
            f.candidate_rowid,
            o.trade_date,
            row_number() over (
              partition by f.candidate_rowid
              order by o.trade_date
            ) as bar_number
          from filtered f
          join candidate_observations o
            on o.stock_code = f.stock_code
           and f.snapshot_date is not null
           and o.trade_date > f.snapshot_date
           and o.valid_close
          qualify bar_number <= 20
        ),
        targets as (
          select
            candidate_rowid,
            count(*)::bigint as stock_valid_bar_count,
            max(case when bar_number = 1 then trade_date end) as target_1d,
            max(case when bar_number = 5 then trade_date end) as target_5d,
            max(case when bar_number = 10 then trade_date end) as target_10d,
            max(case when bar_number = 20 then trade_date end) as target_20d
          from valid_observations
          group by candidate_rowid
        ),
        halt_flags as (
          select
            f.candidate_rowid,
             max(case when o.explicit_halt then 1 else 0 end)::integer as explicit_halt
          from filtered f
          left join candidate_observations o
            on o.stock_code = f.stock_code
           and f.snapshot_date is not null
           and o.trade_date > f.snapshot_date
          group by f.candidate_rowid
        ),
        horizon_rows as (
          select
            f.candidate_rowid,
            f.snapshot_date,
            h.horizon,
            h.bar_count,
            case h.horizon
              when '1d' then f.stored_date_1d when '5d' then f.stored_date_5d
              when '10d' then f.stored_date_10d else f.stored_date_20d end as stored_date,
            case h.horizon
              when '1d' then f.raw_return_1d when '5d' then f.raw_return_5d
              when '10d' then f.raw_return_10d else f.raw_return_20d end as raw_return,
            case h.horizon
              when '1d' then f.adjusted_return_1d when '5d' then f.adjusted_return_5d
              when '10d' then f.adjusted_return_10d else f.adjusted_return_20d end as adjusted_return,
            case h.horizon
              when '1d' then t.target_1d when '5d' then t.target_5d
              when '10d' then t.target_10d else t.target_20d end as expected_target,
            coalesce(t.stock_valid_bar_count, 0) as stock_valid_bar_count,
            coalesce(m.market_count, 0) as market_count,
            coalesce(hf.explicit_halt, 0) as explicit_halt
          from filtered f
          cross join (values ('1d', 1), ('5d', 5), ('10d', 10), ('20d', 20)) h(horizon, bar_count)
          left join targets t on t.candidate_rowid = f.candidate_rowid
          left join market_counts m on m.candidate_rowid = f.candidate_rowid
          left join halt_flags hf on hf.candidate_rowid = f.candidate_rowid
        ),
        classified as (
          select
            horizon,
            snapshot_date,
            case
              when stored_date is not null and stored_date = expected_target
                   and raw_return is not null and isfinite(raw_return)
                then case
                  when adjusted_return is not null and isfinite(adjusted_return) then 'complete'
                  else 'raw_matured_adjustment_missing' end
              when market_count < bar_count then 'natural_pending'
              when explicit_halt = 1 and stock_valid_bar_count < bar_count then 'partial_halt'
              else 'matured_missing_bar'
            end as status
          from horizon_rows
        )
        select horizon, status, count(*)::bigint, max(snapshot_date)
        from classified
        group by horizon, status
        order by horizon, status
        """,
        [*filter_bindings, evaluation_as_of_date, evaluation_as_of_date],
    ).fetchall()
    return _all_filtered_summary_from_rows(rows, evaluation_as_of_date=evaluation_as_of_date)


def _all_filtered_summary_from_rows(
    rows: list[tuple[Any, ...]],
    *,
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    horizons: dict[str, dict[str, Any]] = {}
    row_count = 0
    for horizon, bar_count in _FORWARD_MATURITY_HORIZONS.items():
        counts = {status: 0 for status in _FORWARD_MATURITY_STATUSES}
        latest_mature: str | None = None
        latest_pending: str | None = None
        for raw_horizon, raw_status, raw_count, raw_latest in rows:
            if str(raw_horizon) != horizon:
                continue
            status = str(raw_status)
            count = int(raw_count or 0)
            counts[status] = count
            latest = _safe_optional_date(str(raw_latest or ""))
            if status == "natural_pending":
                latest_pending = max(filter(None, [latest_pending, latest]), default=None)
            else:
                latest_mature = max(filter(None, [latest_mature, latest]), default=None)
        horizon_row_count = sum(counts.values())
        row_count = max(row_count, horizon_row_count)
        horizons[horizon] = {
            "horizon_bars": bar_count,
            "row_count": horizon_row_count,
            "counts": counts,
            "window_matured_row_count": horizon_row_count - counts["natural_pending"],
            "natural_pending_row_count": counts["natural_pending"],
            "latest_mature_snapshot_date": latest_mature,
            "latest_pending_snapshot_date": latest_pending,
            "counts_authoritative": True,
        }
    return {
        "scope": "all_filtered",
        "row_count": row_count,
        "evaluation_as_of_date": evaluation_as_of_date,
        "horizons": horizons,
        "maturity_clock": "individual_stock_valid_close_bars",
        "diagnostic_clock": "market_trade_dates",
        "source_status": "available",
        "classification_available": True,
        "counts_authoritative": True,
    }


def _empty_all_filtered_maturity_summary(
    *,
    row_count: int,
    latest_snapshot_date: str | None,
    evaluation_as_of_date: str,
    source_issue: str,
) -> dict[str, Any]:
    rows = [
        (horizon, "matured_missing_bar", row_count, latest_snapshot_date)
        for horizon in _FORWARD_MATURITY_HORIZONS
    ]
    summary = _all_filtered_summary_from_rows(rows, evaluation_as_of_date=evaluation_as_of_date)
    for horizon in summary["horizons"].values():
        horizon["counts_authoritative"] = False
    summary.update(
        {
            "source_status": "unavailable",
            "source_issue": source_issue,
            "classification_available": False,
            "counts_authoritative": False,
        }
    )
    return summary


def _table_columns_for_service(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _resolve_evaluation_as_of_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_evaluation_as_of_date: str | None,
    fallback_date: str | None,
) -> str:
    if requested_evaluation_as_of_date:
        return requested_evaluation_as_of_date
    if TABLE_OBS in tables:
        columns = {
            str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_OBS}')").fetchall()
        }
        if "trade_date" in columns:
            today = date.today().isoformat()
            row = conn.execute(
                f"""
                select max(try_cast(trade_date as date))
                from {TABLE_OBS}
                where try_cast(trade_date as date) <= cast(? as date)
                """,
                [today],
            ).fetchone()
            resolved = _safe_optional_date(str(row[0] if row else ""))
            if resolved:
                return resolved
    return _safe_optional_date(fallback_date) or date.today().isoformat()


def _strict_optional_date(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text[:10]).isoformat()


def _safe_optional_date(value: str | None) -> str | None:
    try:
        return _strict_optional_date(value)
    except ValueError:
        return None


def _maturity_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _maturity_positive_float(value: Any) -> float | None:
    number = _maturity_finite_float(value)
    return number if number is not None and number > 0 else None


def _maturity_is_trading_status(value: str) -> bool:
    return is_trading_status(value)


def _resolve_replay_trade_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    snapshot_from: str | None,
    snapshot_to: str | None,
    row_dates: list[str],
) -> list[str]:
    if TABLE_OBS not in tables:
        return row_dates
    if not snapshot_from and not snapshot_to:
        return row_dates

    where_clauses: list[str] = []
    bindings: list[object] = []
    if snapshot_from:
        where_clauses.append("trade_date >= ?")
        bindings.append(snapshot_from)
    if snapshot_to:
        where_clauses.append("trade_date <= ?")
        bindings.append(snapshot_to)
    sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
    observed = [
        str(row[0])[:10]
        for row in conn.execute(
            f"""
            select distinct trade_date
            from {TABLE_OBS}
            {sql_where}
            order by trade_date asc
            """,
            bindings,
        ).fetchall()
        if str(row[0] or "").strip()
    ]
    return observed or row_dates


def _build_summary(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any] | None = None,
    execution_rows: list[dict[str, Any]] | None = None,
    matched_baseline_rows: list[dict[str, Any]] | None = None,
    evaluation_as_of_date: str | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "row_count": len(items),
        "complete_count": _count_status(items, "complete"),
        "pending_count": _count_status(items, "pending"),
        "partial_halt_count": _count_status(items, "partial_halt"),
        "forward_coverage_counts": _forward_coverage_counts(items),
        "missing_forward_return_count": sum(
            1 for item in items if any(item.get(horizon) is None for horizon in _COMPLETION_HORIZONS)
        ),
        "avg_return_1d": _avg_present(items, "return_1d"),
        "avg_return_5d": _avg_present(items, "return_5d"),
        "avg_return_10d": _avg_present(items, "return_10d"),
        "avg_return_20d": _avg_present(items, "return_20d"),
        "horizon_stats": _build_horizon_stats(items),
        "by_signal_kind": _count_by_signal_kind(items),
        "by_signal_kind_horizon_stats": _build_signal_kind_horizon_stats(items),
    }
    if evaluation_as_of_date:
        summary["forward_maturity"] = _forward_maturity_summary(
            items,
            evaluation_as_of_date=evaluation_as_of_date,
        )
    if backtest_window_summary is not None and backtest_window_summary.get("status") in {"valid", "partial"}:
        horizon_usable_items = _horizon_usable_items(items, backtest_window_summary=backtest_window_summary)
        summary["decision_usable_stats"] = _build_decision_usable_stats(
            items,
            backtest_window_summary=backtest_window_summary,
        )
        summary["horizon_usable_stats"] = _build_horizon_stats(horizon_usable_items)
        summary["by_signal_kind_horizon_usable_stats"] = _build_signal_kind_horizon_stats(horizon_usable_items)
        summary["by_market_state_signal_kind_horizon_stats"] = _build_market_state_signal_kind_horizon_stats(
            horizon_usable_items
        )
        if execution_rows is not None:
            execution_usable_rows = _execution_rows_for_dates(
                execution_rows,
                _decision_usable_dates(backtest_window_summary),
            )
            summary["execution_usable_stats"] = _build_execution_usable_stats(execution_usable_rows)
            summary["entry_blocked_stats"] = _build_entry_blocked_stats(execution_usable_rows)
            summary["by_market_state_signal_kind_execution_stats"] = (
                _build_market_state_signal_kind_execution_stats(execution_usable_rows)
            )
            if matched_baseline_rows is not None:
                summary["matched_baseline_stats"] = matched_baseline_stats_from_rows(
                    execution_usable_rows,
                    matched_baseline_rows,
                    dimensions=("signal_kind",),
                )
    return summary


def _build_decision_usable_stats(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any],
) -> dict[str, Any]:
    included_dates = _decision_usable_dates(backtest_window_summary)
    completed_items = [
        item
        for item in items
        if str(item.get("snapshot_as_of_date") or "")[:10] in included_dates
        and str(item.get("data_status") or "").strip() == "complete"
    ]
    usable_items = [_decision_usable_adjusted_item(item) for item in completed_items]
    usable_items = [item for item in usable_items if item is not None]
    return {
        "metric_basis": "adjusted_close_return",
        "adj_coverage_count": len(usable_items),
        "adj_coverage_total": len(completed_items),
        "adj_coverage_ratio": round(len(usable_items) / len(completed_items), 6) if completed_items else None,
        "row_count": len(usable_items),
        "complete_row_count": _count_status(usable_items, "complete"),
        "pending_row_count": _count_status(usable_items, "pending"),
        "partial_halt_row_count": _count_status(usable_items, "partial_halt"),
        "missing_forward_return_count": sum(
            1 for item in usable_items if any(item.get(horizon) is None for horizon in _COMPLETION_HORIZONS)
        ),
        "avg_return_1d": _avg_present(usable_items, "return_1d"),
        "avg_return_5d": _avg_present(usable_items, "return_5d"),
        "avg_return_10d": _avg_present(usable_items, "return_10d"),
        "avg_return_20d": _avg_present(usable_items, "return_20d"),
        "win_rate_1d": _win_rate_present(usable_items, "return_1d"),
        "win_rate_5d": _win_rate_present(usable_items, "return_5d"),
        "win_rate_10d": _win_rate_present(usable_items, "return_10d"),
        "win_rate_20d": _win_rate_present(usable_items, "return_20d"),
        "by_signal_kind": _count_by_signal_kind(usable_items),
        "by_signal_kind_horizon_stats": _build_signal_kind_horizon_stats(usable_items),
        "included_snapshot_dates": sorted({str(item.get("snapshot_as_of_date") or "")[:10] for item in usable_items}),
        "excluded_snapshot_dates": _decision_excluded_dates(
            items,
            usable_items=usable_items,
            included_dates=included_dates,
        ),
    }


def _decision_usable_adjusted_item(item: dict[str, Any]) -> dict[str, Any] | None:
    adjusted_item = dict(item)
    has_adjusted_return = False
    for raw_key, adjusted_key in _ADJUSTED_FORWARD_RETURN_KEYS.items():
        adjusted_value = item.get(adjusted_key)
        adjusted_item[raw_key] = adjusted_value
        if adjusted_value is not None:
            has_adjusted_return = True
    if not has_adjusted_return:
        return None
    return adjusted_item


def _decision_usable_dates(backtest_window_summary: dict[str, Any]) -> set[str]:
    return {
        str(item)[:10]
        for item in backtest_window_summary.get("included_completed_stats_dates", [])
        if str(item or "").strip()
    }


def _horizon_usable_items(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    usable_dates = _decision_usable_dates(backtest_window_summary)
    for reason in backtest_window_summary.get("date_reasons", []):
        if not isinstance(reason, dict):
            continue
        if str(reason.get("status") or "").strip() not in {"completed", "pending"}:
            continue
        trade_date = str(reason.get("trade_date") or "").strip()[:10]
        if trade_date:
            usable_dates.add(trade_date)
    return [
        item
        for item in items
        if str(item.get("snapshot_as_of_date") or "").strip()[:10] in usable_dates
    ]


def _classify_replay_date(
    *,
    trade_date: str,
    coverage: Any,
    rows: list[dict[str, Any]],
    history_table_present: bool,
) -> dict[str, Any]:
    if not history_table_present:
        return _classification(
            trade_date=trade_date,
            status="unsupported",
            reason_code="missing_required_source_table",
            message=f"{TABLE_HIST} table absent; cannot distinguish no-signal dates from missing candidate-history materialization for {trade_date}.",
            affects_completed_stats=False,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )

    missing_items = {str(item) for item in getattr(coverage, "missing_request_items", [])}
    if not bool(getattr(coverage, "full_coverage", False)):
        if missing_items == {"limit_up_quality:daily_limit_flags"}:
            return _classification(
                trade_date=trade_date,
                status="unsupported",
                reason_code="missing_daily_limit_flags",
                message=f"daily_limit_flags absent; Livermore strategy replay unsupported for {trade_date}.",
                affects_completed_stats=False,
                signal_kinds=_DEFAULT_SIGNAL_KINDS,
            )
        missing_detail = ", ".join(sorted(missing_items)) or str(getattr(coverage, "status", "not_materialized"))
        return _classification(
            trade_date=trade_date,
            status="unsupported",
            reason_code="missing_required_source_table",
            message=f"Required source coverage is incomplete for {trade_date}: {missing_detail}.",
            affects_completed_stats=False,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )
    if not rows:
        return _classification(
            trade_date=trade_date,
            status="completed",
            reason_code="no_strategy_signals",
            message=f"Full replay coverage produced no Livermore strategy signal rows for {trade_date}.",
            affects_completed_stats=True,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )

    signal_kinds = _signal_kinds_for_rows(rows)
    if any(str(row.get("data_status") or "").strip() == "pending" for row in rows):
        return _classification(
            trade_date=trade_date,
            status="pending",
            reason_code="forward_returns_pending",
            message=f"Forward return bars are not available yet; exclude {trade_date} from completed forward-return statistics.",
            affects_completed_stats=False,
            signal_kinds=signal_kinds,
            missing_bar_row_count=_missing_bar_count(rows),
        )
    if any(
        str(row.get("signal_kind") or "").strip() == "theme_breakout"
        and str(row.get("theme_source_kind") or "").strip() == "proxy"
        for row in rows
    ):
        return _classification(
            trade_date=trade_date,
            status="proxy_only",
            reason_code="proxy_theme_only",
            message=f"Theme breakout replay for {trade_date} relies on proxy-only theme evidence.",
            affects_completed_stats=False,
            signal_kinds=signal_kinds,
        )
    return {
        "status": "completed",
        "affects_completed_stats": True,
        "public_reason": None,
    }


def _classification(
    *,
    trade_date: str,
    status: str,
    reason_code: str,
    message: str,
    affects_completed_stats: bool,
    signal_kinds: list[str],
    missing_bar_row_count: int | None = None,
) -> dict[str, Any]:
    public_reason: dict[str, Any] = {
        "trade_date": trade_date,
        "status": status,
        "reason_code": reason_code,
        "message": message,
        "affects_completed_stats": affects_completed_stats,
        "signal_kinds": signal_kinds,
    }
    if missing_bar_row_count is not None:
        public_reason["missing_bar_row_count"] = missing_bar_row_count
    return {
        "status": status,
        "affects_completed_stats": affects_completed_stats,
        "public_reason": public_reason,
    }


def _count_status(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if str(item.get("data_status") or "").strip() == status)


def _count_by_signal_kind(items: list[dict[str, Any]]) -> dict[str, int]:
    by_signal_kind: dict[str, int] = {}
    for item in items:
        signal_kind = _normalized_signal_kind(item)
        by_signal_kind[signal_kind] = by_signal_kind.get(signal_kind, 0) + 1
    return by_signal_kind


def _signal_kinds_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    signal_kinds = sorted({_normalized_signal_kind(row) for row in rows})
    return signal_kinds or list(_DEFAULT_SIGNAL_KINDS)


def _avg_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = _present_float_values(items, key)
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _win_rate_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = _present_float_values(items, key)
    if not values:
        return None
    return round(sum(1 for value in values if value > 0) / len(values), 6)


def _build_horizon_stats(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values_by_key: dict[str, list[float]] = {key: [] for key in _HORIZON_LABELS}
    for item in items:
        for key, raw in item.items():
            if key not in values_by_key:
                continue
            if raw is None:
                continue
            try:
                values_by_key[key].append(float(raw))
            except (TypeError, ValueError):
                continue
    return {
        key: _horizon_stat_from_values(values, item_count=len(items))
        for key, values in values_by_key.items()
    }


def _median_float(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return round(ordered[midpoint], 6)
    return round((ordered[midpoint - 1] + ordered[midpoint]) / 2, 6)


def _horizon_stat_from_values(values: list[float], *, item_count: int) -> dict[str, Any]:
    positive_count = sum(1 for value in values if value > 0)
    return {
        "available_count": len(values),
        "missing_count": item_count - len(values),
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": round(sum(values) / len(values), 6) if values else None,
        "median_return": _median_float(values),
        "win_rate": round(positive_count / len(values), 6) if values else None,
    }


def _build_signal_kind_horizon_stats(items: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(signal_kind, []).append(item)
    return {signal_kind: _build_horizon_stats(rows) for signal_kind, rows in sorted(grouped.items())}


def _execution_rows_for_dates(rows: list[dict[str, Any]], included_dates: set[str]) -> list[dict[str, Any]]:
    if not included_dates:
        return []
    return [row for row in rows if str(row.get("signal_date") or "").strip()[:10] in included_dates]


def _execution_executable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _bool_value(row.get("entry_executable")) is True]


def _build_execution_usable_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    executable_rows = _execution_executable_rows(rows)
    signal_kind_stats = _build_execution_signal_kind_horizon_stats(executable_rows)
    return {
        "metric_basis": _EXECUTION_METRIC_BASIS,
        "basis_label": "T+1\u5f00\u76d8\u6210\u4ea4\u00b7\u542b\u8d39\u00b7\u590d\u6743",
        "row_count": len(executable_rows),
        "execution_row_count": len(rows),
        "entry_executable_count": len(executable_rows),
        "horizon_usable_stats": _build_execution_horizon_stats(executable_rows),
        "by_signal_kind": _count_by_execution_signal_kind(executable_rows),
        "by_signal_kind_horizon_stats": signal_kind_stats,
        "by_signal_kind_horizon_usable_stats": signal_kind_stats,
        "included_signal_dates": sorted(
            {date_text for row in executable_rows if (date_text := str(row.get("signal_date") or "").strip()[:10])}
        ),
    }


def _build_execution_horizon_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        horizon: _execution_horizon_stat(rows, column)
        for horizon, column in _EXECUTION_RETURN_KEYS.items()
    }


def _execution_horizon_stat(rows: list[dict[str, Any]], column: str) -> dict[str, Any]:
    values = _present_float_values(rows, column)
    positive_count = sum(1 for value in values if value > 0)
    avg_return = round(sum(values) / len(values), 6) if values else None
    median_return = _median_float(values)
    win_rate = round(positive_count / len(values), 6) if values else None
    missing_count = len(rows) - len(values)
    return {
        "available_count": len(values),
        "missing_count": missing_count,
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": avg_return,
        "median_return": median_return,
        "win_rate": win_rate,
        "n": len(values),
        "adj_missing_n": missing_count,
        "win": win_rate,
        "avg": avg_return,
        "median": median_return,
        "p10": _percentile_float(values, 0.1),
        "p90": _percentile_float(values, 0.9),
    }


def _build_execution_signal_kind_horizon_stats(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        signal_kind = _execution_signal_kind(row)
        grouped.setdefault(signal_kind, []).append(row)
    return {signal_kind: _build_execution_horizon_stats(group_rows) for signal_kind, group_rows in sorted(grouped.items())}


def _build_market_state_signal_kind_execution_stats(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in _execution_executable_rows(rows):
        market_state = _execution_market_state(row)
        signal_kind = _execution_signal_kind(row)
        grouped.setdefault(market_state, {}).setdefault(signal_kind, []).append(row)
    return {
        market_state: {
            signal_kind: _build_execution_horizon_stats(group_rows)
            for signal_kind, group_rows in sorted(signal_groups.items())
        }
        for market_state, signal_groups in sorted(grouped.items())
    }


def _build_entry_blocked_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_rows = [row for row in rows if _bool_value(row.get("entry_executable")) is False]
    by_reason: dict[str, dict[str, Any]] = {}
    for row in blocked_rows:
        reason = str(row.get("entry_block_reason") or "unknown").strip() or "unknown"
        current = by_reason.setdefault(reason, {"count": 0, "share": None})
        current["count"] += 1
    for reason in sorted(by_reason):
        by_reason[reason]["share"] = round(by_reason[reason]["count"] / len(rows), 6) if rows else None
    executable_count = len(_execution_executable_rows(rows))
    return {
        "metric_basis": _EXECUTION_METRIC_BASIS,
        "total_row_count": len(rows),
        "entry_executable_count": executable_count,
        "blocked_row_count": len(blocked_rows),
        "blocked_ratio": round(len(blocked_rows) / len(rows), 6) if rows else None,
        "by_reason": dict(sorted(by_reason.items())),
    }


def _count_by_execution_signal_kind(rows: list[dict[str, Any]]) -> dict[str, int]:
    by_signal_kind: dict[str, int] = {}
    for row in rows:
        signal_kind = _execution_signal_kind(row)
        by_signal_kind[signal_kind] = by_signal_kind.get(signal_kind, 0) + 1
    return by_signal_kind


def _build_market_state_signal_kind_horizon_stats(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in items:
        market_state = _market_state_from_signal_evidence(item)
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(market_state, {}).setdefault(signal_kind, []).append(item)
    return {
        market_state: {
            signal_kind: _build_horizon_stats(rows)
            for signal_kind, rows in sorted(signal_groups.items())
        }
        for market_state, signal_groups in sorted(grouped.items())
    }


def _stock_candidate_state_scopes(items: list[dict[str, Any]]) -> dict[str, Any]:
    stock_items = [item for item in items if _normalized_signal_kind(item) == "stock_candidate"]
    entry_items: list[dict[str, Any]] = []
    overheat_count = 0
    unknown_count = 0
    missing_turnover_count = 0
    for item in stock_items:
        market_state = _market_state_from_signal_evidence(item)
        if market_state in _ENTRY_ALLOWED_STATES:
            entry_items.append(item)
        elif market_state == "OVERHEAT":
            overheat_count += 1
        elif market_state == "unknown":
            unknown_count += 1
        if _abnormal_turnover_value(item) is None:
            missing_turnover_count += 1
    total = len(stock_items)
    return {
        "stock_candidate_all_states": _build_horizon_stats(stock_items),
        "stock_candidate_entry_allowed_states_only": _build_horizon_stats(entry_items),
        "overheat_ratio": overheat_count / total if total else None,
        "unknown_market_state_ratio": unknown_count / total if total else None,
        "abnormal_turnover_missing_ratio": missing_turnover_count / total if total else None,
    }


def _build_strategy_score_payload(
    *,
    items: list[dict[str, Any]],
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
    backtest_window_summary: dict[str, Any],
    macro_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_min_sample = max(_STRATEGY_REVIEW_MIN_T5_SAMPLE, int(min_sample))
    normalized_macro_context = _strategy_macro_context(macro_context)
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in items:
        market_state = _market_state_from_signal_evidence(item)
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(market_state, {}).setdefault(signal_kind, []).append(item)

    rows: list[dict[str, Any]] = []
    for market_state, signal_groups in sorted(grouped.items()):
        for signal_kind, signal_items in sorted(signal_groups.items()):
            rows.append(
                _strategy_score_row(
                    market_state=market_state,
                    signal_kind=signal_kind,
                    items=signal_items,
                    min_sample=effective_min_sample,
                    primary_horizon=primary_horizon,
                    macro_context=normalized_macro_context,
                )
            )

    rows = _rank_strategy_score_rows(rows)
    normalized_current_state = _normalized_text(current_market_state) or None
    current_rows = _sort_strategy_score_rows(
        [row for row in rows if normalized_current_state and row["market_state"] == normalized_current_state]
    )
    if normalized_current_state and not current_rows:
        current_rows = [
            _empty_strategy_score_row(
                market_state=normalized_current_state,
                signal_kind=signal_kind,
                min_sample=effective_min_sample,
                primary_horizon=primary_horizon,
                macro_context=normalized_macro_context,
            )
            for signal_kind in _DEFAULT_SIGNAL_KINDS
        ]
    if normalized_current_state and not any(row["sample_status"] == "sufficient" for row in current_rows):
        current_rows = [
            {
                **row,
                "reason": _current_state_insufficient_reason(
                    row["stats"][_STRATEGY_REVIEW_HORIZON]["available_count"],
                    min_sample=effective_min_sample,
                    primary_horizon=_STRATEGY_REVIEW_HORIZON,
                ),
            }
            for row in current_rows
        ]

    return {
        "as_of_date": snapshot_to,
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "primary_horizon": primary_horizon,
        "min_sample": effective_min_sample,
        "review_thresholds": _strategy_review_thresholds(effective_min_sample),
        "current_market_state": normalized_current_state,
        "macro_context": normalized_macro_context,
        "backtest_window_summary": backtest_window_summary,
        "forward_coverage_summary": _forward_coverage_summary(items),
        "rows": _sort_strategy_score_rows(rows),
        "current_market_state_rows": current_rows,
        "stock_candidate_state_scopes": _stock_candidate_state_scopes(items),
    }


def _build_strategy_optimization_payload(
    *,
    items: list[dict[str, Any]],
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
    backtest_window_summary: dict[str, Any],
    macro_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_min_sample = max(_STRATEGY_REVIEW_MIN_T5_SAMPLE, int(min_sample))
    normalized_macro_context = _strategy_macro_context(macro_context)
    normalized_current_state = _normalized_text(current_market_state) or None
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(_normalized_signal_kind(item), []).append(item)

    signal_kinds = [
        *[kind for kind in _DEFAULT_SIGNAL_KINDS if kind in grouped],
        *sorted(kind for kind in grouped if kind not in _DEFAULT_SIGNAL_KINDS),
    ]
    if not signal_kinds:
        signal_kinds = list(_DEFAULT_SIGNAL_KINDS)

    strategy_summaries = _sort_strategy_optimization_summaries(
        [
            _strategy_optimization_summary(
                signal_kind=signal_kind,
                items=grouped.get(signal_kind, []),
                min_sample=effective_min_sample,
                primary_horizon=primary_horizon,
                macro_context=normalized_macro_context,
            )
            for signal_kind in signal_kinds
        ]
    )
    slices = _sort_strategy_optimization_slices(
        _build_strategy_optimization_slices(
            items,
            min_sample=effective_min_sample,
            primary_horizon=primary_horizon,
            macro_context=normalized_macro_context,
        )
    )
    recommendations = _strategy_optimization_recommendations(
        strategy_summaries=strategy_summaries,
        slices=slices,
    )

    return {
        "as_of_date": snapshot_to,
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "primary_horizon": primary_horizon,
        "min_sample": effective_min_sample,
        "review_thresholds": _strategy_review_thresholds(effective_min_sample),
        "current_market_state": normalized_current_state,
        "macro_context": normalized_macro_context,
        "backtest_window_summary": backtest_window_summary,
        "strategy_summaries": strategy_summaries,
        "slices": slices,
        "recommendations": recommendations,
        "pending_summary": _strategy_optimization_pending_summary(items, primary_horizon=primary_horizon),
        "sample_maturity": _strategy_optimization_sample_maturity(
            strategy_summaries=strategy_summaries,
            slices=slices,
            min_sample=effective_min_sample,
            primary_horizon=primary_horizon,
        ),
    }


def _build_cycle_proxy_backtest_payload(
    *,
    items: list[dict[str, Any]],
    snapshot_from: str | None,
    snapshot_to: str | None,
    benchmark_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    proxy_items = _cycle_proxy_items(items)
    nav_series = build_cycle_proxy_nav_series(proxy_items)
    summary = build_cycle_proxy_summary(
        nav_series,
        candidate_rows=len(proxy_items),
        benchmark_rows=benchmark_rows or [],
        benchmark_series_id=BENCHMARK_SERIES_ID,
        return_field_stats=cycle_proxy_return_field_stats(proxy_items),
    )
    return {
        "status": "proxy" if summary is not None else "unsupported",
        "full_strategy_status": "blocked_missing_inputs",
        "formula_version": CYCLE_PROXY_FORMULA_VERSION,
        "proxy_signal_kind": _CYCLE_PROXY_SIGNAL_KIND,
        "proxy_rule": (
            "Equal-weight non-overlapping T+5 baskets of completed rank<=6 stock_candidate rows in WARM/HOT states, "
            "excluding execution-blocked entries and re-entering only after the previous basket's latest realized "
            "T+5 exit date."
        ),
        "execution_blocked_rows_in_window": sum(
            1 for item in items if item.get("execution_entry_blocked") is True
        ),
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "missing_full_strategy_inputs": list(_CYCLE_PROXY_MISSING_FULL_STRATEGY_INPUTS),
        "warnings": [
            "This is a reduced proxy backtest, not the full A-share cycle-rotation strategy.",
            "It uses daily candidate rows already persisted by the existing Livermore replay pipeline.",
            "Executable next-open return_5d_net_adj is preferred and already includes formal transaction costs; when unavailable, the read side applies those costs to return_5d_adj (gross return_5d second fallback).",
            CYCLE_PROXY_ENTRY_PRICE_WARNING,
            "Proxy evidence only: cost and return conventions are aligned with the formal engine constants, but results are not produced by the formal path backtest engine.",
            "Full benchmark attribution and the report's monthly core cadence are still not modeled here.",
        ],
        "summary": summary,
        "nav_series": nav_series,
    }


def _build_candidate_history_portfolio_backtest_payload(
    *,
    items: list[dict[str, Any]],
    close_rows: list[dict[str, Any]],
    snapshot_from: str | None,
    snapshot_to: str | None,
    benchmark_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rebalances = _candidate_history_portfolio_rebalance_rows(items)
    nav_series, rebalance_log, stale_price_codes = build_candidate_history_portfolio_series(
        rebalances=rebalances,
        close_rows=close_rows,
    )
    price_field_stats = candidate_history_portfolio_price_field_stats(close_rows)
    summary = build_candidate_history_portfolio_summary(
        nav_series,
        rebalance_log=rebalance_log,
        benchmark_rows=benchmark_rows or [],
        benchmark_series_id=BENCHMARK_SERIES_ID,
        price_field_stats=price_field_stats,
    )
    return {
        "status": "portfolio_proxy" if summary is not None else "unsupported",
        "full_strategy_status": "blocked_missing_inputs",
        "formula_version": PORTFOLIO_PROXY_FORMULA_VERSION,
        "signal_kind": _PORTFOLIO_BACKTEST_SIGNAL_KIND,
        "rebalance_rule": "first_available_monthly_snapshot",
        "weighting_rule": "equal_weight_top_6",
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "missing_full_strategy_inputs": list(_CYCLE_PROXY_MISSING_FULL_STRATEGY_INPUTS),
        "warnings": [
            "This is a candidate-history portfolio proxy, not the full A-share cycle-rotation strategy.",
            "It uses first-available monthly stock_candidate snapshots, equal-weight top-6 replay rows, daily adjusted-close mark-to-market with raw-close fallback, and fixed transaction-cost assumptions.",
            PORTFOLIO_PROXY_ENTRY_PRICE_WARNING,
            "Proxy evidence only: transaction costs (buy/sell fees plus per-side slippage) are aligned with the formal engine constants, but results are not produced by the formal path backtest engine.",
            "It still lacks the report's macro, industry-cycle, fund-flow, valuation-history, and earnings-revision inputs.",
            *[
                f"Stock {code} had no fresh close for an entire rebalance period; its position was valued at the last known close (forward-fill)."
                for code in stale_price_codes
            ],
        ],
        "summary": summary,
        "nav_series": nav_series,
        "rebalance_log": rebalance_log,
    }


def _cycle_proxy_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proxy_items: list[dict[str, Any]] = []
    for item in items:
        if _normalized_signal_kind(item) != _CYCLE_PROXY_SIGNAL_KIND:
            continue
        if str(item.get("data_status") or "").strip() != "complete":
            continue
        if _candidate_rank(item) is None or _candidate_rank(item) > _CYCLE_PROXY_MAX_RANK:
            continue
        if _market_state_from_signal_evidence(item) not in _CYCLE_PROXY_ALLOWED_MARKET_STATES:
            continue
        if item.get("execution_entry_blocked") is True:
            continue
        if item.get("return_1d") is None:
            continue
        proxy_items.append(item)
    return proxy_items


def _enrich_cycle_proxy_execution_returns(
    items: list[dict[str, Any]],
    *,
    execution_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach point-in-time next-open returns by signal date and stock code."""
    execution_by_key = {
        (
            str(row.get("signal_date") or "")[:10],
            str(row.get("stock_code") or "").strip(),
        ): row
        for row in execution_rows
        if str(row.get("signal_date") or "").strip()
        and str(row.get("stock_code") or "").strip()
        and _normalized_signal_kind(row) == _CYCLE_PROXY_SIGNAL_KIND
    }
    enriched: list[dict[str, Any]] = []
    for item in items:
        key = (
            str(item.get("snapshot_as_of_date") or "")[:10],
            str(item.get("stock_code") or "").strip(),
        )
        if _normalized_signal_kind(item) != _CYCLE_PROXY_SIGNAL_KIND:
            enriched.append(item)
            continue
        execution = execution_by_key.get(key)
        if execution is None:
            enriched.append(item)
            continue
        enriched_item = dict(item)
        if execution.get("entry_executable") is False:
            enriched_item["execution_entry_blocked"] = True
            enriched.append(enriched_item)
            continue
        if execution.get("entry_executable") is True:
            enriched_item["execution_entry_date"] = execution.get("entry_date")
            enriched_item["execution_exit_date_5d"] = execution.get("exit_date_5d")
            enriched_item["return_5d_gross_adj"] = execution.get("return_5d_gross_adj")
            enriched_item["return_5d_net_adj"] = execution.get("return_5d_net_adj")
        enriched.append(enriched_item)
    return enriched


def _candidate_history_portfolio_rebalance_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_date: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if _normalized_signal_kind(item) != _PORTFOLIO_BACKTEST_SIGNAL_KIND:
            continue
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if snapshot_date:
            rows_by_date.setdefault(snapshot_date, []).append(item)

    first_dates_by_month: dict[str, str] = {}
    for snapshot_date in sorted(rows_by_date):
        month_key = snapshot_date[:7]
        first_dates_by_month.setdefault(month_key, snapshot_date)

    rebalances: list[dict[str, Any]] = []
    for month_key in sorted(first_dates_by_month):
        snapshot_date = first_dates_by_month[month_key]
        rows = sorted(
            rows_by_date[snapshot_date],
            key=lambda item: (_candidate_rank(item) or 999999, str(item.get("stock_code") or "")),
        )
        market_state = _market_state_from_signal_evidence(rows[0]) if rows else "unknown"
        eligible_items = [
            item
            for item in rows
            if _candidate_rank(item) is not None
            and _candidate_rank(item) <= _PORTFOLIO_BACKTEST_MAX_RANK
            and _market_state_from_signal_evidence(item) in _PORTFOLIO_BACKTEST_ALLOWED_MARKET_STATES
        ]
        rebalances.append(
            {
                "date": snapshot_date,
                "month": month_key,
                "market_state": market_state,
                "items": eligible_items[:_PORTFOLIO_BACKTEST_MAX_RANK],
            }
        )
    return rebalances


def _load_candidate_history_portfolio_close_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    rebalances: list[dict[str, Any]],
    snapshot_to: str | None,
    has_adjustment_factor: bool | None = None,
) -> list[dict[str, Any]]:
    stock_codes = sorted(
        {
            str(item.get("stock_code") or "").strip()
            for rebalance in rebalances
            for item in rebalance["items"]
            if str(item.get("stock_code") or "").strip()
        }
    )
    if not rebalances or not stock_codes:
        return []
    if has_adjustment_factor is None:
        has_adjustment_factor = _candidate_history_portfolio_has_adjustment_factor(conn)
    start_date = str(rebalances[0]["date"])
    placeholders = ", ".join("?" for _ in stock_codes)
    where_to = "and d.trade_date <= ?" if snapshot_to else ""
    adj_select = (
        """
          case
            when af.adj_factor is not null and af.adj_factor > 0
            then d.close_value * af.adj_factor
            else null
          end as adj_close_value,
          af.adj_factor
        """
        if has_adjustment_factor
        else """
          cast(null as double) as adj_close_value,
          cast(null as double) as adj_factor
        """
    )
    adj_join = (
        f"""
        left join {TABLE_ADJ_FACTOR} af
          on af.stock_code = d.stock_code
         and af.trade_date = d.trade_date
        """
        if has_adjustment_factor
        else ""
    )
    bindings: list[object] = [*stock_codes, start_date]
    if snapshot_to:
        bindings.append(snapshot_to)
    rows = conn.execute(
        f"""
        select
          d.trade_date,
          d.stock_code,
          d.close_value,
          {adj_select}
        from {TABLE_OBS} d
        {adj_join}
        where d.stock_code in ({placeholders})
          and d.trade_date >= ?
          {where_to}
        order by d.trade_date asc, d.stock_code asc
        """,
        bindings,
    ).fetchall()
    return [
        {
            "trade_date": str(trade_date)[:10],
            "stock_code": str(stock_code),
            "close_value": float(close_value),
            "adj_close_value": float(adj_close_value) if adj_close_value is not None else None,
            "adj_factor": float(adj_factor) if adj_factor is not None else None,
        }
        for trade_date, stock_code, close_value, adj_close_value, adj_factor in rows
        if close_value is not None
    ]


def _candidate_history_portfolio_has_adjustment_factor(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str] | None = None,
) -> bool:
    table_names = tables if tables is not None else {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if TABLE_ADJ_FACTOR not in table_names:
        return False
    columns = {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_ADJ_FACTOR}')").fetchall()}
    return {"stock_code", "trade_date", "adj_factor"}.issubset(columns)


def _load_benchmark_rows_for_nav_series(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    nav_series: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not nav_series:
        return [], []
    start_date = str(nav_series[0]["date"])[:10]
    end_date = str(nav_series[-1].get("exit_date") or nav_series[-1]["date"])[:10]
    return _load_benchmark_rows(conn, tables=tables, start_date=start_date, end_date=end_date)


def _load_benchmark_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_date: dict[str, dict[str, Any]] = {}
    tables_used: list[str] = []
    for table in (TABLE_BENCHMARK_SNAPSHOT, TABLE_BENCHMARK_DAILY):
        if table not in tables:
            continue
        rows = conn.execute(
            f"""
            select trade_date, value_numeric
            from {table}
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) >= ?
              and cast(trade_date as date) <= ?
            order by cast(trade_date as date) asc
            """,
            [BENCHMARK_SERIES_ID, start_date, end_date],
        ).fetchall()
        if not rows:
            continue
        tables_used.append(table)
        for trade_date, value in rows:
            if value is None:
                continue
            by_date[str(trade_date)[:10]] = {
                "trade_date": str(trade_date)[:10],
                "value": float(value),
            }
    return [by_date[key] for key in sorted(by_date)], sorted(tables_used, key=_benchmark_table_sort_key)


def _benchmark_table_sort_key(table: str) -> int:
    return (TABLE_BENCHMARK_DAILY, TABLE_BENCHMARK_SNAPSHOT).index(table)


def _append_optional_table(tables: list[str], table: str | list[str] | None) -> list[str]:
    if table is None:
        return tables
    optional_tables = table if isinstance(table, list) else [table]
    out = [*tables]
    for item in optional_tables:
        if item not in out:
            out.append(item)
    return out


def _strategy_primary_sample_size(
    *,
    stats: dict[str, dict[str, Any]],
    primary_horizon: str,
) -> int | None:
    primary_stats = stats.get(primary_horizon)
    if not isinstance(primary_stats, dict):
        return None
    available_count = primary_stats.get("available_count")
    if available_count is None:
        return None
    try:
        return int(available_count)
    except (TypeError, ValueError):
        return None


def _empty_strategy_family_metadata() -> dict[str, Any]:
    return {field: None for field in _STRATEGY_FAMILY_FIELDS}


def _strategy_family_metadata(
    *,
    signal_kind: str,
    stats: dict[str, dict[str, Any]],
    primary_horizon: str,
    score_priority_only: bool,
) -> dict[str, Any]:
    if score_priority_only and signal_kind not in _STRATEGY_SCORE_FAMILY_SIGNAL_KINDS:
        return _empty_strategy_family_metadata()
    family_key = _STRATEGY_FAMILY_BY_SIGNAL_KIND.get(signal_kind)
    if not family_key:
        return _empty_strategy_family_metadata()
    return {
        "family_key": family_key,
        "family_label": _STRATEGY_FAMILY_LABELS.get(family_key, family_key),
        "family_contract_version": STRATEGY_FAMILY_CONTRACT_VERSION,
        "primary_sample_size": _strategy_primary_sample_size(
            stats=stats,
            primary_horizon=primary_horizon,
        ),
    }


def _strategy_family_metadata_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in _STRATEGY_FAMILY_FIELDS}


def _strategy_family_metadata_index(
    *,
    rows: list[dict[str, Any]],
    key_field: str,
    target_type: str,
) -> dict[tuple[str, str], dict[str, Any] | None]:
    index: dict[tuple[str, str], dict[str, Any] | None] = {}
    duplicate_keys: set[str] = set()
    for row in rows:
        target_key = str(row.get(key_field) or "")
        if not target_key:
            continue
        index_key = (target_type, target_key)
        if index_key in index:
            duplicate_keys.add(target_key)
            continue
        index[index_key] = _strategy_family_metadata_from_row(row)
    for target_key in duplicate_keys:
        index[(target_type, target_key)] = None
    return index


def _strategy_family_metadata_for_recommendation_target(
    *,
    target_type: str,
    target_key: str,
    family_by_target: dict[tuple[str, str], dict[str, Any] | None],
) -> dict[str, Any]:
    source = family_by_target.get((target_type, target_key))
    if source is None:
        return _empty_strategy_family_metadata()
    return {field: source.get(field) for field in _STRATEGY_FAMILY_FIELDS}


def _load_strategy_macro_context(
    loader: Callable[[str], dict[str, Any] | None] | None,
    snapshot_to: str | None,
) -> dict[str, Any] | None:
    if loader is None or not snapshot_to:
        return None
    context = loader(snapshot_to)
    return _strategy_macro_context(context)


def _strategy_macro_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(context, dict) or not context:
        return None
    return dict(context)


def _strategy_family_sample_maturity(
    *,
    primary_sample_size: Any,
    min_sample: int,
) -> str:
    if primary_sample_size is None:
        return "unknown"
    try:
        sample_size = int(primary_sample_size)
    except (TypeError, ValueError):
        return "unknown"
    return "sufficient" if sample_size >= min_sample else "insufficient"


def _strategy_family_data_readiness(macro_context: dict[str, Any] | None) -> str:
    if not macro_context:
        return "missing"
    data_state = _normalized_text(macro_context.get("data_state")) or "missing"
    if data_state == "ready":
        return "ready"
    if data_state in {"degraded", "stale"}:
        return "degraded"
    return "missing"


def _strategy_family_macro_compatibility(data_readiness: str) -> str:
    if data_readiness == "ready":
        return "compatible"
    if data_readiness == "degraded":
        return "degraded"
    return "unknown"


def _strategy_family_readiness_reasons(
    *,
    macro_context: dict[str, Any] | None,
    sample_maturity: str,
) -> list[str]:
    reasons = ["OBSERVATION_ONLY_BOUNDARY"]
    if not macro_context:
        reasons.append("MACRO_CONTEXT_MISSING")
    else:
        raw_reasons = macro_context.get("readiness_reasons")
        if isinstance(raw_reasons, list):
            reasons.extend(str(reason) for reason in raw_reasons if str(reason or "").strip())
    if sample_maturity != "sufficient":
        reasons.append("SAMPLE_MATURITY_INSUFFICIENT")
    return _dedupe_preserve_order(reasons)


def _strategy_family_readiness(
    *,
    family_metadata: dict[str, Any],
    macro_context: dict[str, Any] | None,
    min_sample: int,
) -> dict[str, Any] | None:
    if not family_metadata.get("family_key"):
        return None
    sample_maturity = _strategy_family_sample_maturity(
        primary_sample_size=family_metadata.get("primary_sample_size"),
        min_sample=min_sample,
    )
    data_readiness = _strategy_family_data_readiness(macro_context)
    readiness_state = (
        "observation_ready"
        if data_readiness == "ready" and sample_maturity == "sufficient"
        else "degraded_observation"
    )
    return {
        "readiness_contract_version": STRATEGY_FAMILY_READINESS_CONTRACT_VERSION,
        "readiness_state": readiness_state,
        "macro_context_id": (macro_context or {}).get("macro_context_id"),
        "market_gate_context_id": None,
        "macro_compatibility": _strategy_family_macro_compatibility(data_readiness),
        "market_gate_compatibility": "unknown",
        "data_readiness": data_readiness,
        "sample_maturity": sample_maturity,
        "readiness_reasons": _strategy_family_readiness_reasons(
            macro_context=macro_context,
            sample_maturity=sample_maturity,
        ),
        "observational_only": True,
        "formal_use_allowed": False,
    }


def _strategy_family_contract_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **_strategy_family_metadata_from_row(row),
        "family_readiness": row.get("family_readiness"),
    }


def _strategy_family_contract_index(
    *,
    rows: list[dict[str, Any]],
    key_field: str,
    target_type: str,
) -> dict[tuple[str, str], dict[str, Any] | None]:
    index: dict[tuple[str, str], dict[str, Any] | None] = {}
    duplicate_keys: set[str] = set()
    for row in rows:
        target_key = str(row.get(key_field) or "")
        if not target_key:
            continue
        index_key = (target_type, target_key)
        if index_key in index:
            duplicate_keys.add(target_key)
            continue
        index[index_key] = _strategy_family_contract_from_row(row)
    for target_key in duplicate_keys:
        index[(target_type, target_key)] = None
    return index


def _strategy_family_contract_for_recommendation_target(
    *,
    target_type: str,
    target_key: str,
    family_by_target: dict[tuple[str, str], dict[str, Any] | None],
) -> dict[str, Any]:
    source = family_by_target.get((target_type, target_key))
    if source is None:
        return {**_empty_strategy_family_metadata(), "family_readiness": None}
    return {
        **{field: source.get(field) for field in _STRATEGY_FAMILY_FIELDS},
        "family_readiness": source.get("family_readiness"),
    }


def _strategy_optimization_summary(
    *,
    signal_kind: str,
    items: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = _build_horizon_stats(items)
    recommendation = _optimization_recommendation(
        stats=stats,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
    )
    family_metadata = _strategy_family_metadata(
        signal_kind=signal_kind,
        stats=stats,
        primary_horizon=primary_horizon,
        score_priority_only=False,
    )
    family_readiness = _strategy_family_readiness(
        family_metadata=family_metadata,
        macro_context=macro_context,
        min_sample=min_sample,
    )
    return {
        "summary_key": f"strategy:{signal_kind}",
        "signal_kind": signal_kind,
        "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
        **family_metadata,
        "family_readiness": family_readiness,
        "sample_status": "sufficient" if recommendation["action"] != "pending_more_history" else "insufficient",
        "stats": stats,
        "date_weighted_stats": _build_date_weighted_horizon_stats(items),
        "recommendation": recommendation,
    }


def _build_strategy_optimization_slices(
    items: list[dict[str, Any]],
    *,
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    evidence_by_item = _signal_evidence_by_item(items)
    factor_items = [item for item in items if _normalized_signal_kind(item) == "factor_screen"]
    trend_items = [item for item in items if _normalized_signal_kind(item) == "stock_candidate"]
    theme_items = [item for item in items if _normalized_signal_kind(item) == "theme_breakout"]

    slices: list[dict[str, Any]] = []
    slices.extend(
        _rank_optimization_slices(
            signal_kind="factor_screen",
            dimension="rank",
            items=factor_items,
            buckets=[(1, 10, "1-10"), (11, 20, "11-20"), (21, 30, "21-30")],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _rank_optimization_slices(
            signal_kind="stock_candidate",
            dimension="rank",
            items=trend_items,
            buckets=[(1, 10, "1-10"), (11, 20, "11-20"), (21, 30, "21-30")],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="stock_candidate",
            dimension="market_state",
            items=trend_items,
            label_prefix="market state",
            classifier=lambda item: _market_state_from_signal_evidence(item, evidence_by_item=evidence_by_item),
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="stock_candidate",
            dimension="fundamental_overlay",
            items=trend_items,
            label_prefix="基本面 overlay",
            classifier=lambda item: _fundamental_overlay_status(item, evidence_by_item=evidence_by_item),
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="stock_candidate",
            dimension="abnormal_turnover",
            items=trend_items,
            label_prefix="换手异动",
            classifier=lambda item: _abnormal_turnover_bucket(
                _number_from_item_or_evidence(item, "abnormal_turnover", evidence_by_item=evidence_by_item)
            ),
            ordered_labels=["<1", "1-2", "2-3.5", ">3.5", "unknown"],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="stock_candidate",
            dimension="gap_norm",
            items=trend_items,
            label_prefix="跳空",
            classifier=lambda item: _gap_norm_bucket(
                _number_from_item_or_evidence(item, "gap_norm", evidence_by_item=evidence_by_item)
            ),
            ordered_labels=["<=0", "0-0.2", "0.2-0.45", ">0.45", "unknown"],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="stock_candidate",
            dimension="breakout_extension_norm",
            items=trend_items,
            label_prefix="突破延展",
            classifier=lambda item: _breakout_extension_bucket(
                _number_from_item_or_evidence(item, "breakout_extension_norm", evidence_by_item=evidence_by_item)
            ),
            ordered_labels=["<=0.1", "0.1-0.25", "0.25-0.35", ">0.35", "unknown"],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _rank_value_optimization_slices(
            signal_kind="theme_breakout",
            dimension="theme_rank",
            items=theme_items,
            label_prefix="theme rank",
            value_key="theme_rank",
            buckets=[(1, 3, "1-3"), (4, 10, "4-10"), (11, None, "11+")],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _rank_value_optimization_slices(
            signal_kind="theme_breakout",
            dimension="stock_rank_in_theme",
            items=theme_items,
            label_prefix="stock rank",
            value_key="stock_rank_in_theme",
            buckets=[(1, 3, "1-3"), (4, 5, "4-5"), (6, None, "6+")],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="theme_breakout",
            dimension="movement_event_count",
            items=theme_items,
            label_prefix="题材异动事件",
            classifier=lambda item: _movement_event_bucket(
                _integer_from_item_or_evidence(item, "movement_event_count", evidence_by_item=evidence_by_item)
            ),
            ordered_labels=["0", "1-5", "6-10", ">10", "unknown"],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    slices.extend(
        _categorical_optimization_slices(
            signal_kind="theme_breakout",
            dimension="stock_movement_event_count",
            items=theme_items,
            label_prefix="个股异动事件",
            classifier=lambda item: _stock_movement_event_bucket(
                _integer_from_item_or_evidence(item, "stock_movement_event_count", evidence_by_item=evidence_by_item)
            ),
            ordered_labels=["0", "1", "2+", "unknown"],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
    )
    return slices


def _rank_optimization_slices(
    *,
    signal_kind: str,
    dimension: str,
    items: list[dict[str, Any]],
    buckets: list[tuple[int, int | None, str]],
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    return _rank_value_optimization_slices(
        signal_kind=signal_kind,
        dimension=dimension,
        items=items,
        label_prefix="rank",
        value_key="candidate_rank",
        buckets=buckets,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
        macro_context=macro_context,
    )


def _rank_value_optimization_slices(
    *,
    signal_kind: str,
    dimension: str,
    items: list[dict[str, Any]],
    label_prefix: str,
    value_key: str,
    buckets: list[tuple[int, int | None, str]],
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for rank_from, rank_to, label in buckets:
        bucket_items = [
            item
            for item in items
            if (rank := _integer_from_item_or_evidence(item, value_key)) is not None
            and rank >= rank_from
            and (rank_to is None or rank <= rank_to)
        ]
        if not bucket_items:
            continue
        slices.append(
            _strategy_optimization_slice(
                signal_kind=signal_kind,
                dimension=dimension,
                bucket_key=label,
                label=f"{label_prefix} {label}",
                items=bucket_items,
                min_sample=min_sample,
                primary_horizon=primary_horizon,
                macro_context=macro_context,
            )
        )
    return slices


def _categorical_optimization_slices(
    *,
    signal_kind: str,
    dimension: str,
    items: list[dict[str, Any]],
    label_prefix: str,
    classifier: Any,
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None,
    ordered_labels: list[str] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        label = _normalized_text(classifier(item)) or "unknown"
        grouped.setdefault(label, []).append(item)
    labels = ordered_labels or sorted(grouped)
    labels = [label for label in labels if label in grouped]
    labels.extend(sorted(label for label in grouped if label not in labels))
    return [
        _strategy_optimization_slice(
            signal_kind=signal_kind,
            dimension=dimension,
            bucket_key=label,
            label=f"{label_prefix} {label}",
            items=grouped[label],
            min_sample=min_sample,
            primary_horizon=primary_horizon,
            macro_context=macro_context,
        )
        for label in labels
    ]


def _strategy_optimization_slice(
    *,
    signal_kind: str,
    dimension: str,
    bucket_key: str,
    label: str,
    items: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None,
) -> dict[str, Any]:
    stats = _build_horizon_stats(items)
    recommendation = _optimization_recommendation(
        stats=stats,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
    )
    family_metadata = _strategy_family_metadata(
        signal_kind=signal_kind,
        stats=stats,
        primary_horizon=primary_horizon,
        score_priority_only=False,
    )
    family_readiness = _strategy_family_readiness(
        family_metadata=family_metadata,
        macro_context=macro_context,
        min_sample=min_sample,
    )
    return {
        "slice_key": f"{signal_kind}:{dimension}:{_slug_text(bucket_key)}",
        "signal_kind": signal_kind,
        "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
        **family_metadata,
        "family_readiness": family_readiness,
        "dimension": dimension,
        "bucket": bucket_key,
        "label": label,
        "sample_status": "sufficient" if recommendation["action"] != "pending_more_history" else "insufficient",
        "stats": stats,
        "date_weighted_stats": _build_date_weighted_horizon_stats(items),
        "recommendation": recommendation,
    }


def _optimization_recommendation(
    *,
    stats: dict[str, dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    review = _strategy_review_gate(stats=stats, min_sample=min_sample)
    return {
        "action": review["action"],
        "priority_label": review["priority_label"],
        "reason": review["reason"],
        "primary_horizon": primary_horizon,
        "review_horizon": _STRATEGY_REVIEW_HORIZON,
        "available_count": review["available_count"],
        "min_sample": review["min_sample"],
        "avg_return": review["avg_return"],
        "median_return": review["median_return"],
        "t20_median_return": review["t20_median_return"],
        "win_rate": review["win_rate"],
        "score": review["score"],
    }


def _optimization_score(*, avg_return: Any, win_rate: Any) -> float | None:
    if avg_return is None or win_rate is None:
        return None
    try:
        return round(float(win_rate) * 100 + float(avg_return) * 100, 4)
    except (TypeError, ValueError):
        return None


def _strategy_review_thresholds(min_sample: int) -> dict[str, Any]:
    return {
        "review_horizon": _STRATEGY_REVIEW_HORIZON,
        "mature_min_sample": max(_STRATEGY_REVIEW_MIN_T5_SAMPLE, int(min_sample)),
        "min_t5_win_rate": _STRATEGY_REVIEW_MIN_T5_WIN_RATE,
        "official_t5_avg_return_band": {
            "lower": _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR,
            "upper": _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_TARGET,
        },
        "long_horizon": _STRATEGY_REVIEW_LONG_HORIZON,
        "long_horizon_median_rule": "not_below_t5_median",
    }


def _strategy_review_gate(*, stats: dict[str, dict[str, Any]], min_sample: int) -> dict[str, Any]:
    required_sample = max(_STRATEGY_REVIEW_MIN_T5_SAMPLE, int(min_sample))
    t5_stats = stats.get(_STRATEGY_REVIEW_HORIZON) or {}
    t20_stats = stats.get(_STRATEGY_REVIEW_LONG_HORIZON) or {}
    available_count = int(t5_stats.get("available_count") or 0)
    avg_return = _float_value(t5_stats.get("avg_return"))
    win_rate = _float_value(t5_stats.get("win_rate"))
    median_return = _float_value(t5_stats.get("median_return"))
    t20_median_return = _float_value(t20_stats.get("median_return"))
    score = _optimization_score(avg_return=avg_return, win_rate=win_rate)

    if available_count < required_sample or avg_return is None or win_rate is None:
        return {
            "action": "pending_more_history",
            "priority_label": "样本不足",
            "sample_status": "insufficient",
            "reason": _sample_insufficient_reason(
                available_count,
                min_sample=required_sample,
                primary_horizon=_STRATEGY_REVIEW_HORIZON,
            ),
            "available_count": available_count,
            "min_sample": required_sample,
            "avg_return": avg_return,
            "median_return": median_return,
            "t20_median_return": t20_median_return,
            "win_rate": win_rate,
            "score": score,
            "passed": False,
        }

    issues: list[str] = []
    metric_failed = False
    if win_rate < _STRATEGY_REVIEW_MIN_T5_WIN_RATE:
        metric_failed = True
        issues.append(f"T+5 胜率低于 {_STRATEGY_REVIEW_MIN_T5_WIN_RATE * 100:.0f}%")
    if avg_return < _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR:
        metric_failed = True
        issues.append("T+5 均值低于 official 1.20%-2.40% 区间下沿")

    long_window_pending = t20_median_return is None
    long_window_worse = median_return is not None and t20_median_return is not None and t20_median_return < median_return
    if long_window_pending:
        issues.append("T+20 中位数待成熟")
    elif long_window_worse:
        issues.append("T+20 中位数低于 T+5 中位数")

    if metric_failed or long_window_worse:
        action = "downgrade"
        priority_label = "降权观察"
    elif long_window_pending:
        action = "observe"
        priority_label = "继续观察"
    else:
        action = "promote"
        priority_label = "优先复核"

    base_reason = (
        f"T+5 成熟样本 {available_count}/{required_sample}，胜率 {win_rate * 100:.1f}% ，"
        f"均值 {avg_return * 100:+.2f}%（official 1.20%-2.40%），"
        f"中位数 {_format_optional_percent(median_return)}，"
        f"T+20 中位数 {_format_optional_percent(t20_median_return)}，评分 {score:.2f}。"
    )
    if action == "promote":
        reason = base_reason + "通过 T+5 成熟样本、胜率、official 下沿和 T+20 中位数不恶化门槛，仅用于优先复核排序。"
    elif action == "observe":
        reason = base_reason + "；".join(issues) + "，继续观察。"
    else:
        reason = base_reason + "；".join(issues) + "，降权观察。"

    return {
        "action": action,
        "priority_label": priority_label,
        "sample_status": "sufficient",
        "reason": reason,
        "available_count": available_count,
        "min_sample": required_sample,
        "avg_return": avg_return,
        "median_return": median_return,
        "t20_median_return": t20_median_return,
        "win_rate": win_rate,
        "score": score,
        "passed": action == "promote",
    }


def _format_optional_percent(value: Any) -> str:
    numeric = _float_value(value)
    if numeric is None:
        return "待成熟"
    return f"{numeric * 100:+.2f}%"


def _build_date_weighted_horizon_stats(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_horizon_date: dict[str, dict[str, list[float]]] = {key: {} for key in _HORIZON_LABELS}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "").strip()[:10]
        if not snapshot_date:
            continue
        for key, by_date in by_horizon_date.items():
            value = _float_value(item.get(key))
            if value is None:
                continue
            by_date.setdefault(snapshot_date, []).append(value)
    return {
        key: _date_weighted_horizon_stat_from_daily(by_date)
        for key, by_date in by_horizon_date.items()
    }


def _date_weighted_horizon_stat(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    by_date: dict[str, list[float]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "").strip()[:10]
        if not snapshot_date:
            continue
        value = _float_value(item.get(key))
        if value is None:
            continue
        by_date.setdefault(snapshot_date, []).append(value)
    return _date_weighted_horizon_stat_from_daily(by_date)


def _date_weighted_horizon_stat_from_daily(by_date: dict[str, list[float]]) -> dict[str, Any]:
    daily_returns = [sum(values) / len(values) for values in by_date.values() if values]
    return {
        "available_day_count": len(daily_returns),
        "candidate_row_count": sum(len(values) for values in by_date.values()),
        "avg_return": round(sum(daily_returns) / len(daily_returns), 6) if daily_returns else None,
        "positive_day_rate": round(sum(1 for value in daily_returns if value > 0) / len(daily_returns), 6)
        if daily_returns
        else None,
        "worst_day_return": round(min(daily_returns), 6) if daily_returns else None,
        "best_day_return": round(max(daily_returns), 6) if daily_returns else None,
    }


def _strategy_optimization_pending_summary(items: list[dict[str, Any]], *, primary_horizon: str) -> dict[str, Any]:
    pending_items = [item for item in items if item.get(primary_horizon) is None]
    pending_dates = sorted(
        {
            str(item.get("snapshot_as_of_date") or "").strip()[:10]
            for item in pending_items
            if str(item.get("snapshot_as_of_date") or "").strip()
        }
    )
    latest_pending_date = pending_dates[-1] if pending_dates else None
    horizon_label = _HORIZON_LABELS[primary_horizon]
    if pending_items:
        message = (
            f"{horizon_label} 仍有 {len(pending_items)} 条收益待成熟"
            + (f"，最新 pending 日期 {latest_pending_date}" if latest_pending_date else "")
            + "。"
        )
    else:
        message = f"{horizon_label} 已成熟样本内暂无 pending 收益。"
    return {
        "primary_horizon": primary_horizon,
        "pending_rows": len(pending_items),
        "pending_dates": pending_dates,
        "latest_pending_date": latest_pending_date,
        "message": message,
    }


def _strategy_optimization_sample_maturity(
    *,
    strategy_summaries: list[dict[str, Any]],
    slices: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    all_items = [*strategy_summaries, *slices]
    sufficient_count = sum(1 for item in all_items if item.get("sample_status") == "sufficient")
    insufficient_count = sum(1 for item in all_items if item.get("sample_status") != "sufficient")
    return {
        "status": "sufficient" if sufficient_count else "insufficient",
        "primary_horizon": primary_horizon,
        "min_sample": min_sample,
        "sufficient_count": sufficient_count,
        "insufficient_count": insufficient_count,
    }


def _strategy_optimization_recommendations(
    *,
    strategy_summaries: list[dict[str, Any]],
    slices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    family_by_target = {
        **_strategy_family_contract_index(
            rows=strategy_summaries,
            key_field="summary_key",
            target_type="strategy",
        ),
        **_strategy_family_contract_index(
            rows=slices,
            key_field="slice_key",
            target_type="slice",
        ),
    }
    for row in strategy_summaries:
        target_type = "strategy"
        target_key = str(row["summary_key"])
        recommendations.append(
            {
                **cast(dict[str, Any], row["recommendation"]),
                "target_type": target_type,
                "target_key": target_key,
                "signal_kind": row["signal_kind"],
                "label": row["strategy_label"],
                **_strategy_family_contract_for_recommendation_target(
                    target_type=target_type,
                    target_key=target_key,
                    family_by_target=family_by_target,
                ),
            }
        )
    for row in slices:
        target_type = "slice"
        target_key = str(row["slice_key"])
        recommendations.append(
            {
                **cast(dict[str, Any], row["recommendation"]),
                "target_type": target_type,
                "target_key": target_key,
                "signal_kind": row["signal_kind"],
                "label": row["label"],
                **_strategy_family_contract_for_recommendation_target(
                    target_type=target_type,
                    target_key=target_key,
                    family_by_target=family_by_target,
                ),
            }
        )
    return sorted(recommendations, key=_strategy_optimization_recommendation_sort_key)


def _sort_strategy_optimization_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_strategy_optimization_row_sort_key)


def _sort_strategy_optimization_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_strategy_optimization_row_sort_key)


def _strategy_optimization_row_sort_key(row: dict[str, Any]) -> tuple[int, float, int, str]:
    recommendation = cast(dict[str, Any], row.get("recommendation") or {})
    score = recommendation.get("score")
    signal_kind = str(row.get("signal_kind") or "")
    return (
        0 if score is not None else 1,
        -(float(score) if score is not None else -1.0),
        _strategy_order_index(signal_kind),
        str(row.get("slice_key") or row.get("summary_key") or ""),
    )


def _strategy_optimization_recommendation_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    action_order = {
        "promote": 0,
        "downgrade": 1,
        "observe": 2,
        "pending_more_history": 3,
    }
    score = row.get("score")
    return (
        action_order.get(str(row.get("action") or ""), 9),
        -(float(score) if score is not None else -1.0),
        str(row.get("target_key") or ""),
    )


def _strategy_order_index(signal_kind: str) -> int:
    return _DEFAULT_SIGNAL_KINDS.index(signal_kind) if signal_kind in _DEFAULT_SIGNAL_KINDS else 999


def _fundamental_overlay_status(
    item: dict[str, Any],
    *,
    evidence_by_item: dict[int, dict[str, Any]] | None = None,
) -> str:
    evidence = _signal_evidence(item, evidence_by_item=evidence_by_item)
    value = _normalized_text(evidence.get("fundamental_overlay_status"))
    if value:
        return value
    overlay = evidence.get("fundamental_overlay")
    if isinstance(overlay, dict):
        value = _normalized_text(overlay.get("status"))
        if value:
            return value
    return "unknown"


def _number_from_item_or_evidence(
    item: dict[str, Any],
    key: str,
    *,
    evidence_by_item: dict[int, dict[str, Any]] | None = None,
) -> float | None:
    raw = item.get(key)
    if raw is None:
        raw = _signal_evidence(item, evidence_by_item=evidence_by_item).get(key)
    return _float_value(raw)


def _integer_from_item_or_evidence(
    item: dict[str, Any],
    key: str,
    *,
    evidence_by_item: dict[int, dict[str, Any]] | None = None,
) -> int | None:
    raw = item.get(key)
    if raw is None:
        raw = _signal_evidence(item, evidence_by_item=evidence_by_item).get(key)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _abnormal_turnover_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value < 1:
        return "<1"
    if value < 2:
        return "1-2"
    if value <= 3.5:
        return "2-3.5"
    return ">3.5"


def _gap_norm_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "<=0"
    if value <= 0.2:
        return "0-0.2"
    if value <= 0.45:
        return "0.2-0.45"
    return ">0.45"


def _breakout_extension_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0.1:
        return "<=0.1"
    if value <= 0.25:
        return "0.1-0.25"
    if value <= 0.35:
        return "0.25-0.35"
    return ">0.35"


def _movement_event_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "0"
    if value <= 5:
        return "1-5"
    if value <= 10:
        return "6-10"
    return ">10"


def _stock_movement_event_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    return "2+"


def _slug_text(value: str) -> str:
    return (
        str(value or "unknown")
        .strip()
        .replace(" ", "_")
        .replace("<=", "lte")
        .replace(">=", "gte")
        .replace("<", "lt")
        .replace(">", "gt")
        .replace("+", "plus")
    )


def _strategy_score_row(
    *,
    market_state: str,
    signal_kind: str,
    items: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = _build_horizon_stats(items)
    diagnostics = _strategy_score_diagnostics(
        market_state=market_state,
        signal_kind=signal_kind,
        items=items,
        stats=stats,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
    )
    family_metadata = _strategy_family_metadata(
        signal_kind=signal_kind,
        stats=stats,
        primary_horizon=primary_horizon,
        score_priority_only=True,
    )
    family_readiness = _strategy_family_readiness(
        family_metadata=family_metadata,
        macro_context=macro_context,
        min_sample=min_sample,
    )
    review = _strategy_review_gate(stats=stats, min_sample=min_sample)
    missing_bar_count = _missing_bar_count(items)
    if review["sample_status"] == "insufficient":
        return {
            "market_state": market_state,
            "signal_kind": signal_kind,
            "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
            **family_metadata,
            "family_readiness": family_readiness,
            "sample_status": "insufficient",
            "priority_score": None,
            "priority_rank": None,
            "priority_label": "样本不足",
            "reason": review["reason"],
            "stats": stats,
            "missing_bar_count": missing_bar_count,
            "diagnostics": diagnostics,
        }

    return {
        "market_state": market_state,
        "signal_kind": signal_kind,
        "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
        **family_metadata,
        "family_readiness": family_readiness,
        "sample_status": "sufficient",
        "priority_score": review["score"],
        "priority_rank": None,
        "priority_label": review["priority_label"],
        "reason": review["reason"],
        "stats": stats,
        "missing_bar_count": missing_bar_count,
        "diagnostics": diagnostics,
    }


def _empty_strategy_score_row(
    *,
    market_state: str,
    signal_kind: str,
    min_sample: int,
    primary_horizon: str,
    macro_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = _empty_horizon_stats_by_key()
    family_metadata = _strategy_family_metadata(
        signal_kind=signal_kind,
        stats=stats,
        primary_horizon=primary_horizon,
        score_priority_only=True,
    )
    family_readiness = _strategy_family_readiness(
        family_metadata=family_metadata,
        macro_context=macro_context,
        min_sample=min_sample,
    )
    return {
        "market_state": market_state,
        "signal_kind": signal_kind,
        "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
        **family_metadata,
        "family_readiness": family_readiness,
        "sample_status": "insufficient",
        "priority_score": None,
        "priority_rank": None,
        "priority_label": "样本不足",
        "reason": _sample_insufficient_reason(0, min_sample=min_sample, primary_horizon=_STRATEGY_REVIEW_HORIZON),
        "stats": stats,
        "missing_bar_count": 0,
        "diagnostics": _empty_strategy_score_diagnostics(),
    }


def _rank_strategy_score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_state: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_state.setdefault(str(row["market_state"]), []).append(row)
    ranked_rows: list[dict[str, Any]] = []
    for state_rows in rows_by_state.values():
        rank = 1
        for row in _sort_strategy_score_rows(state_rows):
            if row["sample_status"] == "sufficient" and row.get("priority_label") == "优先复核":
                row = {**row, "priority_rank": rank}
                rank += 1
            ranked_rows.append(row)
    return ranked_rows


def _sort_strategy_score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[str, int, float, int, str]:
        score = row.get("priority_score")
        signal_kind = str(row.get("signal_kind") or "")
        strategy_order = _DEFAULT_SIGNAL_KINDS.index(signal_kind) if signal_kind in _DEFAULT_SIGNAL_KINDS else 999
        return (
            str(row.get("market_state") or ""),
            0 if score is not None else 1,
            -(float(score) if score is not None else -1.0),
            strategy_order,
            signal_kind,
        )

    return sorted(rows, key=sort_key)


def _empty_strategy_score_diagnostics() -> dict[str, Any]:
    return {
        "priority_scope": None,
        "priority_scope_label": None,
        "priority_scope_stats": None,
        "maturity": _empty_maturity_diagnostics(),
        "rank_buckets": [],
        "risk_flags": [],
    }


def _strategy_score_diagnostics(
    *,
    market_state: str,
    signal_kind: str,
    items: list[dict[str, Any]],
    stats: dict[str, dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    diagnostics = _empty_strategy_score_diagnostics()
    rank_buckets = _rank_bucket_diagnostics(
        market_state=market_state,
        signal_kind=signal_kind,
        items=items,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
    )
    diagnostics["rank_buckets"] = rank_buckets
    if market_state == "OVERHEAT" and signal_kind == "factor_screen" and any(
        int(bucket["rank_from"]) > 10 for bucket in rank_buckets
    ):
        priority_scope_items = [
            item for item in items if (rank := _candidate_rank(item)) is not None and rank <= 10
        ]
        diagnostics["priority_scope"] = "rank<=10"
        diagnostics["priority_scope_label"] = "前10名优先复核"
        diagnostics["priority_scope_stats"] = _build_horizon_stats(priority_scope_items)
        diagnostics["maturity"] = _maturity_diagnostics(priority_scope_items, primary_horizon=_STRATEGY_REVIEW_HORIZON)
    else:
        diagnostics["maturity"] = _maturity_diagnostics(items, primary_horizon=_STRATEGY_REVIEW_HORIZON)
    diagnostics["risk_flags"] = _strategy_score_risk_flags(
        market_state=market_state,
        signal_kind=signal_kind,
        stats=stats,
        min_sample=min_sample,
    )
    return diagnostics


def _rank_bucket_diagnostics(
    *,
    market_state: str,
    signal_kind: str,
    items: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for rank_from, rank_to, label in _rank_bucket_ranges(signal_kind):
        bucket_items = [
            item
            for item in items
            if (rank := _candidate_rank(item)) is not None and rank >= rank_from and (rank_to is None or rank <= rank_to)
        ]
        if not bucket_items:
            continue
        bucket_stats = _build_horizon_stats(bucket_items)
        review = _strategy_review_gate(stats=bucket_stats, min_sample=min_sample)
        priority_label, included_in_priority, reason = _rank_bucket_priority(
            market_state=market_state,
            signal_kind=signal_kind,
            rank_from=rank_from,
            review=review,
        )
        buckets.append(
            {
                "label": label,
                "rank_from": rank_from,
                "rank_to": rank_to,
                "sample_status": review["sample_status"],
                "priority_label": priority_label,
                "included_in_priority": included_in_priority,
                "reason": reason,
                "stats": bucket_stats,
            }
        )
    return buckets


def _rank_bucket_ranges(signal_kind: str) -> list[tuple[int, int | None, str]]:
    if signal_kind == "factor_screen":
        return [(1, 5, "1-5"), (6, 10, "6-10"), (11, 20, "11-20"), (21, None, "21+")]
    if signal_kind == "stock_candidate":
        return [(1, 3, "1-3"), (4, 6, "4-6"), (7, 10, "7-10"), (11, None, "11+")]
    return []


def _rank_bucket_priority(
    *,
    market_state: str,
    signal_kind: str,
    rank_from: int,
    review: dict[str, Any],
) -> tuple[str, bool, str]:
    if review["sample_status"] == "insufficient":
        return (str(review["priority_label"]), False, str(review["reason"]))
    if market_state == "OVERHEAT" and signal_kind == "factor_screen" and rank_from > 10:
        return (
            "降权观察",
            False,
            "OVERHEAT 状态下 rank > 10 的多因子候选降权观察；优先复核仅覆盖前10名。",
        )
    if review["action"] != "promote":
        return (str(review["priority_label"]), False, str(review["reason"]))
    return (
        "优先复核",
        True,
        str(review["reason"]),
    )


def _strategy_score_risk_flags(
    *,
    market_state: str,
    signal_kind: str,
    stats: dict[str, dict[str, Any]],
    min_sample: int,
) -> list[dict[str, Any]]:
    if market_state != "OVERHEAT" or signal_kind != "stock_candidate":
        return []
    t5_stats = stats[_STRATEGY_REVIEW_HORIZON]
    t20_stats = stats[_STRATEGY_REVIEW_LONG_HORIZON]
    available_count = int(t20_stats["available_count"])
    if available_count < min_sample:
        return []
    t5_median = _float_value(t5_stats.get("median_return"))
    t20_median = _float_value(t20_stats.get("median_return"))
    if t5_median is None or t20_median is None or t20_median >= t5_median:
        return []
    return [
        {
            "kind": "long_window_median_worse",
            "label": "长窗口中位数恶化",
            "horizon": _STRATEGY_REVIEW_LONG_HORIZON,
            "reason": (
                f"T+20 样本 {available_count}，中位数 {t20_median * 100:+.2f}% "
                f"低于 T+5 中位数 {t5_median * 100:+.2f}%，仅按短窗口复核。"
            ),
            "stats": t20_stats,
        }
    ]


def _empty_maturity_diagnostics() -> dict[str, Any]:
    return {
        "status": "narrow",
        "label": "样本偏窄",
        "reason": "T+5 已成熟快照 0/4，等待更多成熟日。",
        "min_mature_snapshot_count": 4,
        "mature_snapshot_count": 0,
        "snapshot_stats": [],
        "tracked_snapshots": [],
        "worst_snapshot": None,
    }


def _maturity_diagnostics(
    items: list[dict[str, Any]],
    *,
    primary_horizon: str,
    min_mature_snapshot_count: int = 4,
) -> dict[str, Any]:
    snapshot_groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date:
            continue
        snapshot_groups.setdefault(snapshot_date, []).append(item)

    snapshot_stats = [
        _snapshot_maturity_stat(snapshot_date, snapshot_items, primary_horizon=primary_horizon)
        for snapshot_date, snapshot_items in sorted(snapshot_groups.items())
        if any(item.get(primary_horizon) is not None for item in snapshot_items)
    ]
    mature_count = len(snapshot_stats)
    status = "sufficient" if mature_count >= min_mature_snapshot_count else "narrow"
    label = "成熟快照充足" if status == "sufficient" else "样本偏窄"
    horizon_label = _HORIZON_LABELS[primary_horizon]
    reason = (
        f"{horizon_label} 已成熟快照 {mature_count}/{min_mature_snapshot_count}，"
        + ("可作为强优先复核。" if status == "sufficient" else "等待更多成熟日。")
    )
    return {
        "status": status,
        "label": label,
        "reason": reason,
        "min_mature_snapshot_count": min_mature_snapshot_count,
        "mature_snapshot_count": mature_count,
        "snapshot_stats": snapshot_stats,
        "tracked_snapshots": _tracked_snapshot_stats_from_groups(snapshot_groups),
        "worst_snapshot": _worst_snapshot_stat(snapshot_stats),
    }


def _tracked_snapshot_stats(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshot_groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date:
            continue
        snapshot_groups.setdefault(snapshot_date, []).append(item)
    return _tracked_snapshot_stats_from_groups(snapshot_groups)


def _tracked_snapshot_stats_from_groups(
    snapshot_groups: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [
        _tracked_snapshot_stat(snapshot_date, snapshot_items)
        for snapshot_date, snapshot_items in sorted(snapshot_groups.items())
    ]


def _tracked_snapshot_stat(snapshot_date: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_count = len(items)
    horizons: dict[str, dict[str, Any]] = {}
    horizon_stats = _build_horizon_stats(items)
    for horizon, stat in horizon_stats.items():
        available_count = int(stat["available_count"])
        if available_count >= candidate_count and candidate_count > 0:
            status = "complete"
        elif available_count > 0:
            status = "partial"
        else:
            status = "pending"
        horizons[horizon] = {**stat, "status": status}
    return {
        "snapshot_as_of_date": snapshot_date,
        "candidate_count": candidate_count,
        "horizons": horizons,
    }


def _snapshot_maturity_stat(
    snapshot_date: str,
    items: list[dict[str, Any]],
    *,
    primary_horizon: str,
) -> dict[str, Any]:
    stat = _horizon_stat(items, primary_horizon)
    return {
        "snapshot_as_of_date": snapshot_date,
        "available_count": stat["available_count"],
        "positive_count": stat["positive_count"],
        "non_positive_count": stat["non_positive_count"],
        "avg_return": stat["avg_return"],
        "median_return": stat["median_return"],
        "win_rate": stat["win_rate"],
    }


def _worst_snapshot_stat(snapshot_stats: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not snapshot_stats:
        return None
    return min(
        snapshot_stats,
        key=lambda stat: (
            float(stat["win_rate"]) if stat.get("win_rate") is not None else -1.0,
            float(stat["avg_return"]) if stat.get("avg_return") is not None else -1.0,
            str(stat.get("snapshot_as_of_date") or ""),
        ),
    )


def _candidate_rank(item: dict[str, Any]) -> int | None:
    try:
        return int(item.get("candidate_rank"))
    except (TypeError, ValueError):
        return None


def _empty_horizon_stats_by_key() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "available_count": 0,
            "missing_count": 0,
            "positive_count": 0,
            "non_positive_count": 0,
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
        }
        for key in _HORIZON_LABELS
    }


def _sample_insufficient_reason(available_count: int, *, min_sample: int, primary_horizon: str) -> str:
    return f"{_HORIZON_LABELS[primary_horizon]} 可用样本 {available_count}/{min_sample}，样本不足，仅作观察。"


def _current_state_insufficient_reason(available_count: int, *, min_sample: int, primary_horizon: str) -> str:
    return f"当前状态样本不足：{_HORIZON_LABELS[primary_horizon]} 可用样本 {available_count}/{min_sample}，仅作观察。"


def _score_reason(
    *,
    available_count: int,
    win_rate: float,
    avg_return: float,
    priority_score: float,
    priority_label: str,
    primary_horizon: str,
) -> str:
    horizon_label = _HORIZON_LABELS[primary_horizon]
    base = (
        f"{horizon_label} 样本 {available_count}，胜率 {win_rate * 100:.1f}%，"
        f"均值 {avg_return * 100:+.2f}%，评分 {priority_score:.2f}。"
    )
    if priority_label == "降权观察":
        return base + "胜率低于 50% 或均值不为正，降权观察。"
    return base + "仅用于优先复核排序。"


def _horizon_stat(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = _present_float_values(items, key)
    positive_count = sum(1 for value in values if value > 0)
    return {
        "available_count": len(values),
        "missing_count": len(items) - len(values),
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": round(sum(values) / len(values), 6) if values else None,
        "median_return": _median_float(values),
        "win_rate": round(positive_count / len(values), 6) if values else None,
    }


def _present_float_values(items: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for item in items:
        raw = item.get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _percentile_float(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    bounded = min(max(float(percentile), 0.0), 1.0)
    position = bounded * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index
    return round(ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight, 6)


def _normalized_signal_kind(item: dict[str, Any]) -> str:
    return str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"


def _execution_signal_kind(row: dict[str, Any]) -> str:
    return str(row.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"


def _execution_market_state(row: dict[str, Any]) -> str:
    return _normalized_text(row.get("market_state")) or "unknown"


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"true", "t", "1", "yes", "y"}:
        return True
    if text in {"false", "f", "0", "no", "n"}:
        return False
    return None


def _market_state_from_signal_evidence(
    item: dict[str, Any],
    *,
    evidence_by_item: dict[int, dict[str, Any]] | None = None,
) -> str:
    direct = _normalized_text(item.get("market_state"))
    if direct:
        return direct
    evidence = _signal_evidence(item, evidence_by_item=evidence_by_item)
    for key in ("market_state", "market_state_kind", "market_gate_state"):
        value = _normalized_text(evidence.get(key))
        if value:
            return value
    market_gate = evidence.get("market_gate")
    if isinstance(market_gate, dict):
        value = _normalized_text(market_gate.get("state"))
        if value:
            return value
    return "unknown"


def _abnormal_turnover_value(
    item: dict[str, Any],
    *,
    evidence_by_item: dict[int, dict[str, Any]] | None = None,
) -> float | None:
    raw = item.get("abnormal_turnover")
    if raw is None:
        raw = _signal_evidence(item, evidence_by_item=evidence_by_item).get("abnormal_turnover")
    if raw is None:
        raw = item.get("strength_turn")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _signal_evidence(
    item: dict[str, Any],
    *,
    evidence_by_item: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if evidence_by_item is not None:
        return evidence_by_item.get(id(item), {})
    return _parse_signal_evidence_json(item.get("signal_evidence_json"))


def _signal_evidence_by_item(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {id(item): _parse_signal_evidence_json(item.get("signal_evidence_json")) for item in items}


def _parse_signal_evidence_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _decision_excluded_dates(
    items: list[dict[str, Any]],
    *,
    usable_items: list[dict[str, Any]],
    included_dates: set[str],
) -> list[str]:
    usable_keys = {
        (
            str(item.get("snapshot_as_of_date") or "")[:10],
            str(item.get("stock_code") or "").strip(),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        for item in usable_items
    }
    excluded_dates: set[str] = set()
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date:
            continue
        row_key = (
            snapshot_date,
            str(item.get("stock_code") or "").strip(),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        if snapshot_date not in included_dates or row_key not in usable_keys:
            excluded_dates.add(snapshot_date)
    return sorted(excluded_dates)


def _empty_backtest_window_summary(
    *,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> dict[str, Any]:
    return {
        "status": "unsupported",
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "replay_dates_total": 0,
        "replay_dates_completed": 0,
        "replay_dates_pending": 0,
        "replay_dates_unsupported": 0,
        "replay_dates_proxy_only": 0,
        "completed_rows": 0,
        "pending_rows": 0,
        "unsupported_rows": 0,
        "proxy_only_rows": 0,
        "forward_coverage_row_counts": {status: 0 for status in _FORWARD_COVERAGE_STATUSES},
        "included_completed_stats_dates": [],
        "excluded_from_completed_stats_dates": [],
        "date_reasons": [],
    }


def _first_nonempty_source_version(items: list[dict[str, Any]]) -> str:
    for row in items:
        text = str(row.get("source_version") or "").strip()
        if text:
            return text
    return EMPTY_SOURCE_VERSION


def _normalize_date_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:10]


def _default_snapshot_from(snapshot_to: str) -> str:
    try:
        parsed = date.fromisoformat(snapshot_to[:10])
    except ValueError:
        parsed = date.today()
    return (parsed - timedelta(days=180)).isoformat()


def _latest_history_snapshot_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    row = conn.execute(f"select max(snapshot_as_of_date) from {TABLE_HIST}").fetchone()
    if not row:
        return None
    return _normalize_date_text(row[0])


def _first_nonempty_vendor_version(items: list[dict[str, Any]]) -> str | None:
    for row in items:
        text = str(row.get("vendor_version") or "").strip()
        if text:
            return text
    return None


def _wrap_empty_envelope(*, payload: dict[str, object]) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "stock_code": payload.get("stock_code"),
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "limit": payload.get("limit"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=0,
        result_payload=payload,
    )


def _wrap_strategy_score_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_strategy_score_{uuid.uuid4().hex[:12]}",
        result_kind=STRATEGY_SCORE_RESULT_KIND,
        cache_version=STRATEGY_SCORE_CACHE_VERSION,
        source_version=source_version,
        rule_version=STRATEGY_SCORE_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "current_market_state": payload.get("current_market_state"),
            "min_sample": payload.get("min_sample"),
            "primary_horizon": payload.get("primary_horizon"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )


def _wrap_strategy_optimization_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_strategy_optimization_{uuid.uuid4().hex[:12]}",
        result_kind=STRATEGY_OPTIMIZATION_RESULT_KIND,
        cache_version=STRATEGY_OPTIMIZATION_CACHE_VERSION,
        source_version=source_version,
        rule_version=STRATEGY_OPTIMIZATION_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "current_market_state": payload.get("current_market_state"),
            "min_sample": payload.get("min_sample"),
            "primary_horizon": payload.get("primary_horizon"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )


def _wrap_cycle_proxy_backtest_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
    tables_used: list[str] | None = None,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_cycle_proxy_backtest_{uuid.uuid4().hex[:12]}",
        result_kind=CYCLE_PROXY_BACKTEST_RESULT_KIND,
        cache_version=CYCLE_PROXY_BACKTEST_CACHE_VERSION,
        source_version=source_version,
        rule_version=CYCLE_PROXY_BACKTEST_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "proxy_signal_kind": payload.get("proxy_signal_kind"),
        },
        tables_used=tables_used or [TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )


def _wrap_candidate_history_portfolio_backtest_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
    tables_used: list[str] | None = None,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_portfolio_backtest_{uuid.uuid4().hex[:12]}",
        result_kind=CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RESULT_KIND,
        cache_version=CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_CACHE_VERSION,
        source_version=source_version,
        rule_version=CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "signal_kind": payload.get("signal_kind"),
            "rebalance_rule": payload.get("rebalance_rule"),
        },
        tables_used=tables_used or [TABLE_HIST, TABLE_OBS],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )
