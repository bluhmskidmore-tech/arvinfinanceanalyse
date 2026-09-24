"""Route-support helpers for `/ui/market-data` livermore endpoints.

This module owns the non-endpoint assembly logic that previously lived in
`backend.app.api.routes.market_data_livermore`: cache-key builders, the
position-snapshot CSV path guard, the macro-context loader, and the
workbench-summary payload builders. The route module re-imports every helper
into its own namespace so existing monkeypatch/import contracts keep working.

Intentionally not moved here (their internals must resolve through the route
module globals for existing tests): `_livermore_strategy_cache_key`,
`_stock_analysis_workbench_cache_key`, `_livermore_signal_confluence_cache_key`,
`_choice_stock_catalog_fingerprint`, and `_cached_stock_analysis_workbench`.

This module must not import the route module (no circular imports).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app.services.macro_bond_linkage_service import get_macro_context_v1
from backend.app.services.market_data_livermore_service import livermore_data_version


def _resolve_livermore_position_csv_path(*, data_input_root: Path, csv_path: str) -> Path:
    base_root = Path(data_input_root).resolve()
    allowed_root = (base_root / "livermore").resolve()
    raw_path = Path(csv_path).expanduser()
    candidate = raw_path.resolve() if raw_path.is_absolute() else (base_root / raw_path).resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("Livermore position snapshot CSV must be under data_input/livermore.") from exc
    return candidate


def _invalidate_livermore_response_cache() -> None:
    from backend.app.api.response_cache import market_home_response_cache

    market_home_response_cache.invalidate()


def _livermore_stock_detail_cache_key(
    *, duckdb_path: str, stock_code: str, as_of_date: str | None, lookback: int
) -> str:
    return (
        f"livermore/stock-detail::stock={stock_code}::as_of={as_of_date or ''}"
        f"::lookback={lookback}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _stock_kline_analysis_cache_key(*, duckdb_path: str, stock_code: str, as_of_date: str | None, lookback: int) -> str:
    return f"stock-analysis/kline::stock={stock_code}::as_of={as_of_date or ''}::lookback={lookback}::{duckdb_path}"


def _stock_heavyweight_trends_cache_key(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    window_days: int,
    sector_limit: int,
    stocks_per_sector: int,
) -> str:
    return (
        f"stock-analysis/heavyweight-trends::as_of={as_of_date or ''}::window_days={window_days}"
        f"::sector_limit={sector_limit}::stocks_per_sector={stocks_per_sector}"
        f"::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_candidate_history_cache_key(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    evaluation_as_of_date: str | None,
    limit: int,
) -> str:
    return (
        f"livermore/candidate-history::stock={stock_code or ''}"
        f"::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::evaluation={evaluation_as_of_date or ''}::limit={limit}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_strategy_score_cache_key(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> str:
    return (
        f"livermore/strategy-score::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::market_state={current_market_state or ''}::min_sample={min_sample}"
        f"::primary_horizon={primary_horizon}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_strategy_optimization_cache_key(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> str:
    return (
        f"livermore/strategy-optimization::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::market_state={current_market_state or ''}::min_sample={min_sample}"
        f"::primary_horizon={primary_horizon}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_cycle_proxy_backtest_cache_key(
    *, duckdb_path: str, snapshot_from: str | None, snapshot_to: str | None
) -> str:
    return f"livermore/cycle-proxy-backtest::from={snapshot_from or ''}::to={snapshot_to or ''}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"


def _livermore_portfolio_backtest_cache_key(
    *, duckdb_path: str, snapshot_from: str | None, snapshot_to: str | None
) -> str:
    return (
        f"livermore/candidate-history-portfolio-backtest::from={snapshot_from or ''}"
        f"::to={snapshot_to or ''}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_sector_rank_series_cache_key(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    window_days: int,
    sector_code: str | None,
    top_k: int,
) -> str:
    return (
        f"livermore/sector-rank-series::as_of={as_of_date or ''}::window_days={window_days}"
        f"::sector={sector_code or ''}::top_k={top_k}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_macro_context_v1_for_date(as_of_date: str) -> dict[str, object] | None:
    as_of_text = _optional_text(as_of_date)
    if not as_of_text:
        return None
    return get_macro_context_v1(
        date.fromisoformat(as_of_text[:10]),
        as_of_date=as_of_text[:10],
    )


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _count_array(value: object) -> int | None:
    if isinstance(value, list):
        return len(value)
    return None


def _count_mapping(value: object) -> int | None:
    if isinstance(value, dict):
        return len(value)
    return None


def _count_array_or_mapping(value: object) -> int | None:
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def _present(value: object) -> bool:
    return value not in (None, "", [], {})


def _optional_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        parsed = int(value)
    elif isinstance(value, (int, float, str)):
        try:
            parsed = int(value)
        except ValueError:
            return None
    else:
        return None
    return max(parsed, 0)


def _item_count(value: object) -> int | None:
    mapping = _mapping(value)
    if "items" in mapping:
        return _count_array(mapping.get("items"))
    return _count_array_or_mapping(value)


def _active_data_gap_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(1 for item in value if not (isinstance(item, dict) and str(item.get("status") or "").lower() == "ready"))


def _active_diagnostic_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(
        1 for item in value if not (isinstance(item, dict) and str(item.get("severity") or "").lower() == "info")
    )


def _actionable_unsupported_output_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(
        1 for item in value if not (isinstance(item, dict) and _is_known_livermore_policy_pause(item.get("reason")))
    )


def _is_known_livermore_policy_pause(reason: object) -> bool:
    lower = str(reason or "").strip().lower()
    return (
        ("stock candidate policy" in lower and "inactive in overheat" in lower)
        or "mean reversion watchlist is paused" in lower
        or ("theme breakout execution is paused" in lower and "overheat" in lower)
        or ("hybrid fusion is observation-only" in lower and "warm/hot" in lower)
        or ("uptrend momentum watchlist is paused" in lower and "warm or hot" in lower)
    )


def _sum_optional_counts(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _livermore_workbench_strategy_summary(result: dict[str, object]) -> dict[str, object]:
    data_gap_count = _active_data_gap_count(result.get("data_gaps"))
    diagnostic_count = _active_diagnostic_count(result.get("diagnostics"))
    unsupported_output_count = _actionable_unsupported_output_count(result.get("unsupported_outputs"))
    return {
        "kind": "strategy",
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "requested_as_of_date": (
            result.get("requested_as_of_date") if _present(result.get("requested_as_of_date")) else None
        ),
        "strategy_name": result.get("strategy_name") if _present(result.get("strategy_name")) else None,
        "basis": result.get("basis") if _present(result.get("basis")) else None,
        "market_gate_present": _present(result.get("market_gate")),
        "rule_readiness_count": _count_array(result.get("rule_readiness")),
        "module_state_count": _count_array(result.get("module_states")),
        "factor_screen_candidate_count": _item_count(result.get("factor_screen_candidates")),
        "hybrid_fusion_candidate_count": _item_count(result.get("hybrid_fusion_candidates")),
        "sector_rank_count": _item_count(result.get("sector_rank")),
        "data_gap_count": data_gap_count,
        "diagnostic_count": diagnostic_count,
        "supported_output_count": _count_array(result.get("supported_outputs")),
        "unsupported_output_count": unsupported_output_count,
        "actionable_boundary_count": _sum_optional_counts(data_gap_count, diagnostic_count, unsupported_output_count),
        "total_data_gap_count": _count_array(result.get("data_gaps")),
        "total_diagnostic_count": _count_array(result.get("diagnostics")),
        "total_unsupported_output_count": _count_array(result.get("unsupported_outputs")),
        "risk_exit_present": _present(result.get("risk_exit")),
    }


def _livermore_workbench_signal_summary(result: dict[str, object]) -> dict[str, object]:
    replay = _mapping(result.get("replay_evidence"))
    return {
        "kind": "signal_confluence",
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "macro_context_present": _present(result.get("macro_context")),
        "adversarial_context_present": _present(result.get("adversarial_context")),
        "strategy_context_present": _present(result.get("strategy_context")),
        "closed_loop_state_present": _present(result.get("closed_loop_state")),
        "entry_observation_count": _count_array(result.get("entry_observations")),
        "exit_observation_count": _count_array(result.get("exit_observations")),
        "replay_evidence_present": _present(result.get("replay_evidence")),
        "replay_evidence_row_count": _optional_count(replay.get("row_count")) if replay else None,
        "replay_evidence_sample_count": _count_array(replay.get("sample_items")) if replay else None,
        "diagnostic_count": _count_array(result.get("diagnostics")),
        "position_size_hint_present": _present(result.get("position_size_hint")),
    }


def _livermore_workbench_candidate_history_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "candidate_history",
        "item_count": _count_array(result.get("items")),
        "summary_present": _present(result.get("summary")),
        "backtest_window_summary_present": _present(result.get("backtest_window_summary")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
        "stock_code_present": _present(result.get("stock_code")),
        "limit": _optional_count(result.get("limit")),
    }


def _livermore_workbench_strategy_score_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "strategy_score",
        "row_count": _count_array(result.get("rows")),
        "current_market_state_row_count": _count_array(result.get("current_market_state_rows")),
        "scope_count": _count_array_or_mapping(result.get("stock_candidate_state_scopes")),
        "review_thresholds_present": _present(result.get("review_thresholds")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
        "primary_horizon": result.get("primary_horizon") if _present(result.get("primary_horizon")) else None,
        "min_sample": _optional_count(result.get("min_sample")),
        "backtest_window_summary_present": _present(result.get("backtest_window_summary")),
    }


def _livermore_workbench_strategy_optimization_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "strategy_optimization",
        "strategy_summary_count": _count_array(result.get("strategy_summaries")),
        "slice_count": _count_array(result.get("slices")),
        "optimization_review_item_count": _count_array(result.get("recommendations")),
        "pending_summary_present": _present(result.get("pending_summary")),
        "sample_maturity_present": _present(result.get("sample_maturity")),
        "review_thresholds_present": _present(result.get("review_thresholds")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_cycle_proxy_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "cycle_proxy_backtest",
        "status": result.get("status") if _present(result.get("status")) else None,
        "full_strategy_status": (
            result.get("full_strategy_status") if _present(result.get("full_strategy_status")) else None
        ),
        "proxy_signal_kind": result.get("proxy_signal_kind") if _present(result.get("proxy_signal_kind")) else None,
        "proxy_rule_present": _present(result.get("proxy_rule")),
        "summary_present": _present(result.get("summary")),
        "nav_series_count": _count_array(result.get("nav_series")),
        "warning_count": _count_array(result.get("warnings")),
        "missing_input_count": _count_array(result.get("missing_full_strategy_inputs")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_portfolio_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "candidate_history_portfolio_backtest",
        "status": result.get("status") if _present(result.get("status")) else None,
        "full_strategy_status": (
            result.get("full_strategy_status") if _present(result.get("full_strategy_status")) else None
        ),
        "signal_kind": result.get("signal_kind") if _present(result.get("signal_kind")) else None,
        "rebalance_rule_present": _present(result.get("rebalance_rule")),
        "weighting_rule_present": _present(result.get("weighting_rule")),
        "summary_present": _present(result.get("summary")),
        "nav_series_count": _count_array(result.get("nav_series")),
        "rebalance_log_count": _count_array(result.get("rebalance_log")),
        "warning_count": _count_array(result.get("warnings")),
        "missing_input_count": _count_array(result.get("missing_full_strategy_inputs")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_sector_series_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "sector_rank_series",
        "state": result.get("state") if _present(result.get("state")) else None,
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "series_count": _count_array(result.get("series")),
        "top_k": _optional_count(result.get("top_k")),
        "window_days": _optional_count(result.get("window_days")),
        "formula_version": result.get("formula_version") if _present(result.get("formula_version")) else None,
        "unsupported_note_count": _count_array(result.get("unsupported_notes")),
    }


def _livermore_workbench_summary(result: dict[str, object], *, summary_kind: str) -> dict[str, object]:
    if summary_kind == "strategy":
        return _livermore_workbench_strategy_summary(result)
    if summary_kind == "signal_confluence":
        return _livermore_workbench_signal_summary(result)
    if summary_kind == "candidate_history":
        return _livermore_workbench_candidate_history_summary(result)
    if summary_kind == "strategy_score":
        return _livermore_workbench_strategy_score_summary(result)
    if summary_kind == "strategy_optimization":
        return _livermore_workbench_strategy_optimization_summary(result)
    if summary_kind == "cycle_proxy_backtest":
        return _livermore_workbench_cycle_proxy_summary(result)
    if summary_kind == "candidate_history_portfolio_backtest":
        return _livermore_workbench_portfolio_summary(result)
    if summary_kind == "sector_rank_series":
        return _livermore_workbench_sector_series_summary(result)
    return {
        "kind": summary_kind,
        "field_count": _count_mapping(result),
    }


def _with_livermore_workbench_summary(
    envelope: dict[str, object],
    *,
    summary_kind: str,
) -> dict[str, object]:
    result_value = envelope.get("result")
    if not isinstance(result_value, dict):
        return envelope
    result_value["workbench_summary"] = _livermore_workbench_summary(result_value, summary_kind=summary_kind)
    return envelope


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
