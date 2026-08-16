from __future__ import annotations

import json
import logging
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
from backend.app.core_finance.field_normalization import is_tradestatus_tradable
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_CURRENT_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    MATCHED_BASELINE_TABLE,
    matched_baseline_stats_from_rows,
)
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.repositories.livermore_candidate_history_repo import (
    CANDIDATE_EXECUTION_SELECT_COLUMNS,
    CANDIDATE_HISTORY_SELECT_COLUMNS,
    MATCHED_BASELINE_SELECT_COLUMNS,
    RELATION_CHOICE_MARKET_SNAPSHOT,
    RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
    RELATION_FACT_CHOICE_MACRO_DAILY,
    RELATION_LIVERMORE_CANDIDATE_EXECUTION_HISTORY,
    RELATION_LIVERMORE_CANDIDATE_HISTORY,
    RELATION_STOCK_ADJUSTMENT_FACTOR,
    LivermoreCandidateHistoryRepository,
)
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

# 门面拆分：以下名字已按行为等价逐字迁移到同级子模块，
# 此处显式逐名重导出，保证既有调用方与测试的属性访问不变。
from backend.app.services.livermore_candidate_history_read_support import (
    BENCHMARK_SERIES_ID,
    TABLE_BENCHMARK_DAILY,
    TABLE_BENCHMARK_SNAPSHOT,
    TABLE_EXECUTION_HIST,
    TABLE_HIST,
    TABLE_OBS,
    _COMPLETION_HORIZONS,
    _EXECUTION_SELECT_COLUMNS,
    _FORWARD_COVERAGE_COMPLETE,
    _FORWARD_COVERAGE_MATURITY_FORWARD_BARS,
    _FORWARD_COVERAGE_MISSING_BAR,
    _FORWARD_COVERAGE_PARTIAL_HALT,
    _FORWARD_COVERAGE_PENDING,
    _FORWARD_COVERAGE_STATUSES,
    _FORWARD_MATURITY_HORIZONS,
    _FORWARD_MATURITY_STATUSES,
    _FORWARD_RETURN_KEYS,
    _MATCHED_BASELINE_SELECT_COLUMNS,
    _SELECT_COLUMNS,
    _all_filtered_forward_maturity_summary,
    _all_filtered_summary_from_rows,
    _annotate_forward_coverage,
    _annotate_forward_maturity,
    _available_columns,
    _available_execution_columns,
    _available_matched_baseline_columns,
    _benchmark_table_sort_key,
    _candidate_history_portfolio_has_adjustment_factor,
    _candidate_history_repository_for_connection,
    _derive_forward_coverage,
    _derive_forward_maturity,
    _empty_all_filtered_maturity_summary,
    _execution_select_list,
    _forward_coverage_counts,
    _forward_coverage_of,
    _forward_coverage_summary,
    _forward_maturity_summary,
    _latest_history_snapshot_date,
    _load_benchmark_rows,
    _load_benchmark_rows_for_nav_series,
    _load_candidate_history_portfolio_close_rows,
    _load_execution_window_rows,
    _load_forward_maturity_observations,
    _load_matched_baseline_window_rows,
    _mask_unverified_forward_outcomes,
    _matched_baseline_select_list,
    _maturity_finite_float,
    _maturity_positive_float,
    _min_snapshot_date,
    _missing_bar_count,
    _normalize_date_text,
    _normalize_execution_row,
    _normalize_matched_baseline_row,
    _normalize_row,
    _resolve_evaluation_as_of_date,
    _resolve_replay_trade_dates,
    _safe_optional_date,
    _select_list,
    _strict_optional_date,
    _table_columns_for_service,
)
from backend.app.services.livermore_candidate_history_window_stats import (
    CHOICE_NATIVE_ERA_START,
    _ADJUSTED_FORWARD_RETURN_KEYS,
    _CYCLE_PROXY_SIGNAL_KIND,
    _DEFAULT_SIGNAL_KINDS,
    _EXECUTION_METRIC_BASIS,
    _EXECUTION_RETURN_KEYS,
    _HORIZON_LABELS,
    _append_optional_table,
    _avg_present,
    _bool_value,
    _build_entry_blocked_stats,
    _build_execution_horizon_stats,
    _build_execution_signal_kind_horizon_stats,
    _build_execution_usable_stats,
    _build_market_state_signal_kind_execution_stats,
    _classification,
    _classify_replay_date,
    _count_by_execution_signal_kind,
    _count_by_signal_kind,
    _count_status,
    _decision_excluded_dates,
    _decision_usable_adjusted_item,
    _decision_usable_dates,
    _enrich_cycle_proxy_execution_returns,
    _era_sample_generation,
    _execution_executable_rows,
    _execution_horizon_stat,
    _execution_market_state,
    _execution_rows_for_dates,
    _execution_signal_kind,
    _horizon_stat_from_values,
    _horizon_usable_items,
    _median_float,
    _normalized_signal_kind,
    _normalized_text,
    _percentile_float,
    _present_float_values,
    _signal_kinds_for_rows,
    _snapshot_row_dates,
    _win_rate_present,
)
from backend.app.services.livermore_candidate_history_strategy_support import (
    STRATEGY_FAMILY_READINESS_CONTRACT_VERSION,
    _STRATEGY_FAMILY_FIELDS,
    _STRATEGY_REVIEW_HORIZON,
    _STRATEGY_REVIEW_LONG_HORIZON,
    _STRATEGY_REVIEW_MIN_T5_SAMPLE,
    _STRATEGY_REVIEW_MIN_T5_WIN_RATE,
    _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR,
    _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_TARGET,
    _abnormal_turnover_bucket,
    _breakout_extension_bucket,
    _candidate_rank,
    _current_state_insufficient_reason,
    _date_weighted_horizon_stat,
    _date_weighted_horizon_stat_from_daily,
    _dedupe_preserve_order,
    _empty_horizon_stats_by_key,
    _empty_maturity_diagnostics,
    _empty_strategy_family_metadata,
    _empty_strategy_score_diagnostics,
    _float_value,
    _format_optional_percent,
    _gap_norm_bucket,
    _horizon_stat,
    _load_strategy_macro_context,
    _movement_event_bucket,
    _optimization_recommendation,
    _optimization_score,
    _rank_bucket_priority,
    _rank_bucket_ranges,
    _rank_strategy_score_rows,
    _sample_insufficient_reason,
    _score_reason,
    _slug_text,
    _snapshot_maturity_stat,
    _sort_strategy_optimization_slices,
    _sort_strategy_optimization_summaries,
    _sort_strategy_score_rows,
    _stock_movement_event_bucket,
    _strategy_family_contract_for_recommendation_target,
    _strategy_family_contract_from_row,
    _strategy_family_contract_index,
    _strategy_family_data_readiness,
    _strategy_family_macro_compatibility,
    _strategy_family_metadata_from_row,
    _strategy_family_metadata_index,
    _strategy_family_readiness,
    _strategy_family_readiness_reasons,
    _strategy_family_sample_maturity,
    _strategy_macro_context,
    _strategy_optimization_pending_summary,
    _strategy_optimization_recommendation_sort_key,
    _strategy_optimization_row_sort_key,
    _strategy_optimization_sample_maturity,
    _strategy_order_index,
    _strategy_review_gate,
    _strategy_review_thresholds,
    _strategy_score_risk_flags,
    _worst_snapshot_stat,
)
from backend.app.services.livermore_candidate_history_envelope_support import (
    CACHE_VERSION,
    CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_CACHE_VERSION,
    CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RESULT_KIND,
    CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RULE_VERSION,
    CYCLE_PROXY_BACKTEST_CACHE_VERSION,
    CYCLE_PROXY_BACKTEST_RESULT_KIND,
    CYCLE_PROXY_BACKTEST_RULE_VERSION,
    EMPTY_SOURCE_VERSION,
    EMPTY_VENDOR_VERSION,
    RESULT_KIND,
    RULE_VERSION,
    STRATEGY_OPTIMIZATION_CACHE_VERSION,
    STRATEGY_OPTIMIZATION_RESULT_KIND,
    STRATEGY_OPTIMIZATION_RULE_VERSION,
    STRATEGY_SCORE_CACHE_VERSION,
    STRATEGY_SCORE_RESULT_KIND,
    STRATEGY_SCORE_RULE_VERSION,
    _default_snapshot_from,
    _first_nonempty_source_version,
    _first_nonempty_vendor_version,
    _wrap_candidate_history_portfolio_backtest_envelope,
    _wrap_cycle_proxy_backtest_envelope,
    _wrap_empty_envelope,
    _wrap_strategy_optimization_envelope,
    _wrap_strategy_score_envelope,
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


TABLE_ADJ_FACTOR = RELATION_STOCK_ADJUSTMENT_FACTOR
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
_ENTRY_ALLOWED_STATES = POLICY.entry_observation_states
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
_CYCLE_PROXY_RETURN_PREFERENCE_NOTE = (
    "Executable next-open return_5d_net_adj is preferred and already includes formal transaction costs; "
    "when unavailable, the read side applies those costs to return_5d_adj (gross return_5d second fallback)."
)
_PORTFOLIO_PROXY_BASIS_NOTE = (
    "It uses first-available monthly stock_candidate snapshots, equal-weight top-6 replay rows, "
    "daily adjusted-close mark-to-market with raw-close fallback, and fixed transaction-cost assumptions."
)
_SAMPLE_GENERATION_ERA_NOTE = (
    "sample_generation splits replay rows by signal date at the 2026-01-05 Choice-native era boundary "
    "(earlier rows come from the tushare-era ingestion, later rows from the Choice-native ingestion), "
    "matching CHOICE_NATIVE_ERA_START in scripts/run_portfolio_backtest.py."
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

    repository = LivermoreCandidateHistoryRepository(str(path))
    with repository.scoped_connection() as conn:
        assert conn is not None
        tables = repository.list_table_names(conn=conn)
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

        sql_where, filter_bindings = repository.candidate_history_filter(
            stock_code=trimmed_code,
            snapshot_from=normalized_snapshot_from,
            snapshot_to=effective_snapshot_to,
        )
        rows = repository.fetch_history_slice_rows(
            available_columns=available_columns,
            sql_where=sql_where,
            filter_bindings=filter_bindings,
            limit=limit,
            conn=conn,
        )
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


logger = logging.getLogger(__name__)

DUCKDB_QUERY_FAILED_PREFIX = "DuckDB query failed"


def _warn_duckdb_query_failed(
    stage: str,
    *,
    exc: BaseException,
    tables: object = None,
    as_of_date: str | None = None,
) -> str:
    if isinstance(tables, (list, tuple, set, frozenset)):
        table_text = ",".join(str(item) for item in tables) or "-"
    elif tables:
        table_text = str(tables)
    else:
        table_text = "-"
    date_text = str(as_of_date) if as_of_date else "-"
    summary = str(exc).strip().replace("\n", " ")[:300] or exc.__class__.__name__
    logger.warning(
        "livermore_duckdb_query_failed stage=%s tables=%s as_of_date=%s error=%s",
        stage,
        table_text,
        date_text,
        summary,
    )
    return (
        f"{DUCKDB_QUERY_FAILED_PREFIX} stage={stage} tables={table_text} "
        f"as_of_date={date_text} error={summary}"
    )


def livermore_candidate_history_envelope_or_none(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    limit: int,
    query_failures: list[str] | None = None,
) -> dict[str, object] | None:
    try:
        return livermore_candidate_history_envelope(
            duckdb_path=duckdb_path,
            stock_code=stock_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
            limit=limit,
        )
    except duckdb.Error as exc:
        reason = _warn_duckdb_query_failed(
            "candidate_history_envelope",
            exc=exc,
            tables=[
                RELATION_LIVERMORE_CANDIDATE_HISTORY,
                RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
            ],
            as_of_date=snapshot_to or snapshot_from,
        )
        if query_failures is not None:
            query_failures.append(reason)
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

    repository = LivermoreCandidateHistoryRepository(str(path))
    with repository.scoped_connection() as conn:
        assert conn is not None
        tables = repository.list_table_names(conn=conn)
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

    repository = LivermoreCandidateHistoryRepository(str(path))
    with repository.scoped_connection() as conn:
        assert conn is not None
        tables = repository.list_table_names(conn=conn)
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

    repository = LivermoreCandidateHistoryRepository(str(path))
    with repository.scoped_connection() as conn:
        assert conn is not None
        tables = repository.list_table_names(conn=conn)
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
    repository = LivermoreCandidateHistoryRepository(str(path))
    with repository.scoped_connection() as conn:
        assert conn is not None
        tables = repository.list_table_names(conn=conn)
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

    repository = LivermoreCandidateHistoryRepository(str(path))
    with repository.scoped_connection() as conn:
        assert conn is not None
        tables = repository.list_table_names(conn=conn)
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

    return _build_backtest_window_summary_from_rows(
        duckdb_path=duckdb_path,
        rows=rows,
        trade_dates=trade_dates,
        history_table_present=history_table_present,
        base_summary=base_summary,
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


def _load_backtest_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    evaluation_as_of_date: str | None = None,
) -> list[dict[str, Any]]:
    repository = _candidate_history_repository_for_connection()
    tables = repository.list_table_names(conn=conn)
    if TABLE_HIST not in tables:
        return []
    available_columns = _available_columns(conn)
    rows = repository.fetch_history_window_rows(
        stock_code=stock_code,
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
        available_columns=available_columns,
        conn=conn,
    )
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


def _load_observation_trade_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    min_snapshot_date: str | None,
) -> list[str]:
    """Distinct observation trade dates after the earliest snapshot (maturity reference; SELECT only)."""
    if TABLE_OBS not in tables or not min_snapshot_date:
        return []
    repository = _candidate_history_repository_for_connection()
    columns = repository.table_columns(TABLE_OBS, conn=conn)
    if "close_value" not in columns:
        return []
    rows = repository.fetch_observation_trade_dates_after(
        min_snapshot_date=min_snapshot_date,
        conn=conn,
    )
    return sorted({str(row[0])[:10] for row in rows if str(row[0] or "").strip()})


_UNKNOWN_FORMULA_VERSION_KEY = "unknown"


def _current_execution_formula_version() -> str:
    """延迟导入 tasks 层常量：只读路径导入本模块时不得触发
    backend.app.tasks 初始化（与 load_choice_stock_materialization_coverage
    同一约束）。"""
    from backend.app.tasks.livermore_candidate_history_materialize import (
        EXECUTION_FORMULA_VERSION,
    )

    return EXECUTION_FORMULA_VERSION


def _formula_version_disclosure(
    rows: list[dict[str, Any]],
    *,
    current_formula_version: str,
) -> dict[str, Any]:
    """窗口行按 formula_version 的行数分布与 stale 计数（纯披露，不过滤不改数）。

    缺失/空白版本归入 "unknown"；stale = 非当前版本行数（unknown 计入：
    旧 schema 无版本列的存量同样不是当前版本口径）。
    """
    version_counts: dict[str, int] = {}
    stale_count = 0
    for row in rows:
        version = str(row.get("formula_version") or "").strip()
        version_counts[version or _UNKNOWN_FORMULA_VERSION_KEY] = (
            version_counts.get(version or _UNKNOWN_FORMULA_VERSION_KEY, 0) + 1
        )
        if version != current_formula_version:
            stale_count += 1
    return {
        "current_formula_version": current_formula_version,
        "formula_version_row_counts": dict(sorted(version_counts.items())),
        "stale_formula_row_count": stale_count,
    }


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
    # 治理披露（纯加法）：execution / matched_baseline 窗口存量按
    # formula_version 的行数分布与非当前版本行计数，让消费端在重物化完成
    # 前能看到窗口内 stale 版本存量；不过滤不改任何统计口径。
    if execution_rows is not None:
        summary["execution_formula_version_disclosure"] = _formula_version_disclosure(
            execution_rows,
            current_formula_version=_current_execution_formula_version(),
        )
    if matched_baseline_rows is not None:
        summary["matched_baseline_formula_version_disclosure"] = _formula_version_disclosure(
            matched_baseline_rows,
            current_formula_version=MATCHED_BASELINE_CURRENT_FORMULA_VERSION,
        )
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


def _build_signal_kind_horizon_stats(items: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(signal_kind, []).append(item)
    return {signal_kind: _build_horizon_stats(rows) for signal_kind, rows in sorted(grouped.items())}


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
    return_field_stats = cycle_proxy_return_field_stats(proxy_items)
    summary = build_cycle_proxy_summary(
        nav_series,
        candidate_rows=len(proxy_items),
        benchmark_rows=benchmark_rows or [],
        benchmark_series_id=BENCHMARK_SERIES_ID,
        return_field_stats=return_field_stats,
    )
    caliber_disclosure: dict[str, Any] | None = None
    if summary is not None:
        caliber_disclosure = {
            "entry_price_warning": CYCLE_PROXY_ENTRY_PRICE_WARNING,
            "return_field_stats": return_field_stats,
            "sample_generation": _era_sample_generation(proxy_items),
            "basis_notes": [
                CYCLE_PROXY_ENTRY_PRICE_WARNING,
                _CYCLE_PROXY_RETURN_PREFERENCE_NOTE,
                _SAMPLE_GENERATION_ERA_NOTE,
            ],
        }
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
            _CYCLE_PROXY_RETURN_PREFERENCE_NOTE,
            CYCLE_PROXY_ENTRY_PRICE_WARNING,
            "Proxy evidence only: cost and return conventions are aligned with the formal engine constants, but results are not produced by the formal path backtest engine.",
            "Full benchmark attribution and the report's monthly core cadence are still not modeled here.",
        ],
        "caliber_disclosure": caliber_disclosure,
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
    caliber_disclosure: dict[str, Any] | None = None
    if summary is not None:
        rebalance_items = [row for rebalance in rebalances for row in rebalance["items"]]
        caliber_disclosure = {
            "entry_price_warning": PORTFOLIO_PROXY_ENTRY_PRICE_WARNING,
            # The monthly portfolio proxy has no per-row return-field selection;
            # its return caliber is the mark-to-market price-source split.
            "return_field_stats": price_field_stats,
            "sample_generation": _era_sample_generation(rebalance_items),
            "basis_notes": [
                PORTFOLIO_PROXY_ENTRY_PRICE_WARNING,
                _PORTFOLIO_PROXY_BASIS_NOTE,
                _SAMPLE_GENERATION_ERA_NOTE,
            ],
        }
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
            _PORTFOLIO_PROXY_BASIS_NOTE,
            PORTFOLIO_PROXY_ENTRY_PRICE_WARNING,
            "Proxy evidence only: transaction costs (buy/sell fees plus per-side slippage) are aligned with the formal engine constants, but results are not produced by the formal path backtest engine.",
            "It still lacks the report's macro, industry-cycle, fund-flow, valuation-history, and earnings-revision inputs.",
            *[
                f"Stock {code} had no fresh close for an entire rebalance period; its position was valued at the last known close (forward-fill)."
                for code in stale_price_codes
            ],
        ],
        "caliber_disclosure": caliber_disclosure,
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
