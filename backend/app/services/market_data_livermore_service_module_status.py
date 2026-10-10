"""从 market_data_livermore_service 拆出的 Choice 股票输出容器、模块状态与不可用原因口径。

门面模块逐名 re-export；行为与拆分前完全一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, cast

from backend.app.core_finance.fresh_trend_watchlist_candidates import (
    FreshTrendWatchlistSnapshot,
)
from backend.app.core_finance.livermore_risk_exit import MVP_RULE_LABEL
from backend.app.core_finance.livermore_stock_candidates import (
    stock_candidate_policy_active_market_states,
)
from backend.app.core_finance.livermore_strategy import BroadIndexObservation
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness
from backend.app.services.market_data_livermore_service_support import (
    _unique_preserving_order,
)

if TYPE_CHECKING:
    from backend.app.tasks.choice_stock_materialize import ChoiceStockMaterializationCoverage


STOCK_CANDIDATE_POLICY_INACTIVE_INPUT_FAMILY = "stock_candidate_policy"
STOCK_CANDIDATE_POLICY_INACTIVE_REASON_PREFIX = "Stock candidate policy "


STOCK_MODULE_FRESHNESS_THRESHOLD_DAYS = 3
STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD = 0.8
STOCK_MODULE_PARTIAL_COVERAGE_THRESHOLD = 0.5


class _LoadedObservation(BroadIndexObservation):
    pass


@dataclass(frozen=True)
class _ChoiceStockOutputs:
    sector_coverage: ChoiceStockMaterializationCoverage | None
    stock_coverage: ChoiceStockMaterializationCoverage | None
    sector_rank_payload: dict[str, object] | None
    stock_candidates_payload: dict[str, object] | None
    uptrend_momentum_payload: dict[str, object] | None
    fresh_trend_watchlist_payload: dict[str, object] | None
    mean_reversion_payload: dict[str, object] | None
    factor_screen_payload: dict[str, object] | None
    factor_screen_block_reason: str
    theme_breakout_payload: dict[str, object] | None
    hybrid_fusion_payload: dict[str, object] | None
    hybrid_fusion_block_reason: str
    risk_exit_payload: dict[str, object] | None
    risk_exit_block_reason: str
    stock_candidate_block_reason: str
    tables_used: list[str]
    source_versions: list[str]
    vendor_versions: list[str]
    evidence_rows: int
    query_failed_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _FreshTrendWatchlistLoadResult:
    snapshots: list[FreshTrendWatchlistSnapshot]
    tables_used: list[str]
    query_failed_reason: str = ""


@dataclass(frozen=True)
class _DualStockHistoryInputs:
    candidate_history_by_code: dict[str, dict[str, list[float]]]
    trading_history_by_code: dict[str, dict[str, list[object]]]


def _choice_stock_dependency_summary(
    *,
    stock_readiness: ChoiceStockReadiness,
    families: list[str],
    ready_summary: str,
) -> str:
    if stock_readiness.ready:
        return ready_summary

    relevant = [family for family in families if family in stock_readiness.missing_input_families]
    if not relevant:
        relevant = list(stock_readiness.missing_input_families)
    formatted = ", ".join(relevant) if relevant else "stock input families"
    status_text = "missing" if stock_readiness.status == "missing_catalog" else "incomplete"
    return f"Choice stock catalog is {status_text}; missing or unconfirmed required input families: {formatted}."


def _choice_stock_missing_inputs(*, stock_readiness: ChoiceStockReadiness, families: list[str]) -> list[str]:
    relevant = [family for family in families if family in stock_readiness.missing_input_families]
    return [str(family) for family in relevant] or list(families)


def _theme_breakout_evidence_entry(
    *,
    input_family: str,
    catalog_status: str,
    table_name: str,
    tables_used: list[str],
    date_row_count: int,
    matched_row_count: int,
    fallback_row_count: int = 0,
) -> dict[str, object]:
    if catalog_status == "catalog_unconfirmed" and fallback_row_count <= 0:
        state = "catalog_unconfirmed"
    elif table_name not in tables_used:
        state = "table_missing"
    elif matched_row_count > 0:
        state = "matched_rows"
    else:
        state = "landed_no_rows"
    return {
        "input_family": input_family,
        "status": state,
        "state": state,
        "table": table_name,
        "table_name": table_name,
        "row_count": date_row_count,
        "date_row_count": date_row_count,
        "matched_row_count": matched_row_count,
        "fallback_row_count": fallback_row_count,
        "message": _theme_breakout_evidence_message(
            input_family=input_family,
            state=state,
            table_name=table_name,
            date_row_count=date_row_count,
            matched_row_count=matched_row_count,
        ),
    }


def _theme_breakout_evidence_message(
    *,
    input_family: str,
    state: str,
    table_name: str,
    date_row_count: int,
    matched_row_count: int,
) -> str:
    if state == "catalog_unconfirmed":
        return f"{input_family} is optional and not confirmed in the Choice stock catalog."
    if state == "table_missing":
        return f"{input_family} is confirmed, but {table_name} is not landed in DuckDB."
    if state == "matched_rows":
        return f"{input_family} has {matched_row_count} date-matched rows from {table_name}."
    return f"{input_family} table {table_name} is landed with {date_row_count} date rows but no matched usable rows."


def _movement_for_concept(
    *,
    movement_by_key: dict[tuple[str, str, str], dict[str, object]],
    stock_code: str,
    concept_code: str,
    concept_name: str,
) -> dict[str, object]:
    empty = {
        "count": 0,
        "latest_event_time": "",
        "latest_event_title": "",
    }
    if not movement_by_key:
        return empty
    candidates = [
        value
        for (code, row_concept_code, row_concept_name), value in movement_by_key.items()
        if code == stock_code and row_concept_code == concept_code and row_concept_name == concept_name
    ]
    if not candidates:
        return empty
    latest = max(candidates, key=lambda row: str(row["latest_event_time"]))
    return {
        "count": sum(int(row["count"]) for row in candidates),
        "latest_event_time": latest["latest_event_time"],
        "latest_event_title": latest["latest_event_title"],
    }


def _mean_reversion_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if market_state in {"HOT", "OVERHEAT"}:
        return (
            "Mean reversion watchlist is paused when the market gate is HOT or OVERHEAT "
            "because the defended-trend candidate bundle already covers overheated tape."
        )
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but mean reversion daily inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    return (
        "Mean reversion inputs are landed, but no Trading-status A-share rows produced "
        "watchlist snapshots for this as_of_date."
    )


def _uptrend_momentum_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if market_state not in {"WARM", "HOT"}:
        return "Uptrend momentum watchlist is paused unless the market gate is WARM or HOT."
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but uptrend momentum daily inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    return (
        "Uptrend momentum inputs are landed, but no Trading-status A-share rows produced "
        "watchlist snapshots for this as_of_date."
    )


def _fresh_trend_watchlist_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if market_state not in {"WARM", "HOT", "OVERHEAT"}:
        return "Fresh trend watchlist is observation-only and runs only when the market gate is WARM, HOT, or OVERHEAT."
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status", "sector_membership"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but fresh trend daily inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    return (
        "Fresh trend inputs are landed, but no growth-board Trading rows passed "
        "the new-trend and old-economy exclusion filters for this as_of_date."
    )


def _module_payload(*, key: str, stock_outputs: _ChoiceStockOutputs) -> dict[str, object] | None:
    if key == "sector_rank":
        return stock_outputs.sector_rank_payload
    if key == "stock_candidates":
        return stock_outputs.stock_candidates_payload
    if key == "uptrend_momentum_candidates":
        return stock_outputs.uptrend_momentum_payload
    if key == "fresh_trend_watchlist":
        return stock_outputs.fresh_trend_watchlist_payload
    if key == "mean_reversion_candidates":
        return stock_outputs.mean_reversion_payload
    if key == "factor_screen_candidates":
        return stock_outputs.factor_screen_payload
    if key == "theme_breakout":
        return stock_outputs.theme_breakout_payload
    if key == "hybrid_fusion":
        return stock_outputs.hybrid_fusion_payload
    if key == "risk_exit":
        return stock_outputs.risk_exit_payload
    return None


def _module_source_date(
    *,
    key: str,
    payload: dict[str, object] | None,
    stock_outputs: _ChoiceStockOutputs,
    page_as_of_date: str | None,
) -> str | None:
    if key == "market_gate":
        return page_as_of_date
    if key == "factor_screen_candidates":
        return _payload_text(payload, "factor_snapshot_as_of_date") or _payload_text(payload, "as_of_date")
    if key == "hybrid_fusion" and _hybrid_fusion_is_factor_only(payload):
        return _module_source_date(
            key="factor_screen_candidates",
            payload=stock_outputs.factor_screen_payload,
            stock_outputs=stock_outputs,
            page_as_of_date=page_as_of_date,
        )
    return _payload_text(payload, "as_of_date")


def _payload_text(payload: dict[str, object] | None, key: str) -> str | None:
    value = payload.get(key) if isinstance(payload, dict) else None
    text = str(value).strip() if value is not None else ""
    return text or None


def _module_threshold_days(key: str) -> int | None:
    if key in {"factor_screen_candidates", "hybrid_fusion", "risk_exit"}:
        return STOCK_MODULE_FRESHNESS_THRESHOLD_DAYS
    return None


def _module_lag_days(*, page_as_of_date: str | None, source_date: str | None, market_dates: list[date]) -> int | None:
    if not page_as_of_date or not source_date:
        return None
    try:
        page_date = date.fromisoformat(page_as_of_date)
        source = date.fromisoformat(source_date)
    except ValueError:
        return None
    if page_date <= source:
        return 0
    trading_dates = {market_date for market_date in market_dates if source < market_date <= page_date}
    if trading_dates:
        return len(trading_dates)
    return max(0, (page_date - source).days)


def _coverage_ratio(count: int | None, denominator: int | None) -> float | None:
    if count is None or denominator is None or denominator <= 0:
        return None
    return round(count / denominator, 6)


def _coverage_state(*, coverage_denominator: int | None, coverage_ratio: float | None) -> str | None:
    if coverage_denominator is None or coverage_denominator <= 0 or coverage_ratio is None:
        return "blocked"
    if coverage_ratio < STOCK_MODULE_PARTIAL_COVERAGE_THRESHOLD:
        return "blocked"
    if coverage_ratio < STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD:
        return "partial"
    return None


def _coverage_degradation_reason(
    *,
    label: str,
    coverage_count: int | None,
    coverage_denominator: int | None,
    coverage_ratio: float | None,
) -> str | None:
    if coverage_denominator is None or coverage_denominator <= 0 or coverage_ratio is None:
        count_text = "unknown" if coverage_count is None else str(coverage_count)
        return (
            f"{label} active A-share universe denominator is unavailable; "
            f"coverage count is {count_text}, so primary eligibility cannot be certified."
        )
    if coverage_ratio < STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD:
        percent = coverage_ratio * 100
        threshold = STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD * 100
        return (
            f"{label} covers {coverage_count}/{coverage_denominator} active A-share stocks "
            f"({percent:.1f}%); primary threshold is {threshold:.0f}%."
        )
    return None


def _factor_screen_payload_is_inactive(payload: dict[str, object] | None) -> bool:
    market_state = _payload_text(payload, "market_state")
    return bool(market_state and market_state not in POLICY.factor_screen_active_states)


def _hybrid_fusion_is_factor_only(payload: dict[str, object] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return False
    source_kinds: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            continue
        raw_kinds = evidence.get("source_kinds")
        if isinstance(raw_kinds, list):
            source_kinds.update(str(kind) for kind in raw_kinds if kind)
    return source_kinds == {"factor_screen"}


def _lifecourt_available_inputs(stock_outputs: _ChoiceStockOutputs) -> list[str]:
    available: list[str] = []
    if stock_outputs.stock_candidates_payload is not None:
        available.append("stock_candidates")
    if stock_outputs.theme_breakout_payload is not None:
        available.append("theme_breakout")
    if stock_outputs.factor_screen_payload is not None:
        available.append("factor_screen_candidates")
    if stock_outputs.hybrid_fusion_payload is not None:
        available.append("hybrid_fusion")
    return available


def _lifecourt_missing_inputs(stock_outputs: _ChoiceStockOutputs) -> list[str]:
    missing = [
        "social_text_raw",
        "ocr_asr_pipeline",
        "bot_spam_detection",
        "margin_balance",
        "unlock_event_panel",
    ]
    if stock_outputs.sector_rank_payload is None:
        missing.append("sector_rank_for_regime")
    return missing


def _query_failure_reason_for_stage(stock_outputs: _ChoiceStockOutputs, stage: str) -> str:
    prefix = f"stage={stage}"
    for reason in stock_outputs.query_failed_reasons:
        if prefix in reason:
            return reason
    return ""


def _sector_unavailable_reason(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    query_failure = _query_failure_reason_for_stage(stock_outputs, "sector_rank_inputs")
    if query_failure:
        return query_failure
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["sector_membership", "sector_strength"],
            ready_summary="",
        )
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but sector ranking inputs are not materialized yet."
    if not stock_outputs.sector_coverage.full_coverage:
        return stock_outputs.sector_coverage.message
    return "Choice sector inputs are landed, but fewer than three rankable sectors are available."


def _stock_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.stock_candidate_block_reason:
        return stock_outputs.stock_candidate_block_reason
    query_failure = _query_failure_reason_for_stage(stock_outputs, "stock_candidate_snapshots")
    if query_failure:
        return query_failure
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status", "limit_up_quality"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but stock candidate inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    if stock_outputs.sector_rank_payload is None:
        return "Sector rank is unavailable, so stock candidates remain blocked."
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "Market gate is unavailable or stale, so stock candidates cannot be evaluated."
    return ""


def _stock_candidate_policy_inactive_reason(*, policy_name: str, market_state: str) -> str:
    active_states = "/".join(sorted(stock_candidate_policy_active_market_states(policy_name)))
    return (
        f"{STOCK_CANDIDATE_POLICY_INACTIVE_REASON_PREFIX}{policy_name} is inactive in {market_state}; "
        f"active market states are {active_states}."
    )


def _is_stock_candidate_policy_inactive_reason(reason: str) -> bool:
    return reason.startswith(STOCK_CANDIDATE_POLICY_INACTIVE_REASON_PREFIX)


def _theme_breakout_evidence_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    evidence_state = payload.get("evidence_state")
    if not isinstance(evidence_state, dict):
        return []
    entries: list[dict[str, object]] = []
    for input_family in ("concept_membership", "intraday_movement"):
        entry = evidence_state.get(input_family)
        if isinstance(entry, dict):
            entries.append(cast(dict[str, object], entry))
    return entries


def _theme_breakout_evidence_ready(payload: dict[str, object]) -> bool:
    entries = _theme_breakout_evidence_entries(payload)
    return bool(entries) and all(str(entry.get("status") or entry.get("state")) == "matched_rows" for entry in entries)


def _theme_breakout_uses_current_overlay(payload: dict[str, object]) -> bool:
    raw_themes = payload.get("items")
    if isinstance(raw_themes, list) and any(
        isinstance(theme, dict) and theme.get("source_kind") == "tushare_current_overlay" for theme in raw_themes
    ):
        return True
    evidence_state = payload.get("evidence_state")
    if not isinstance(evidence_state, dict):
        return False
    concept_evidence = evidence_state.get("concept_membership")
    return isinstance(concept_evidence, dict) and (
        concept_evidence.get("status") == "current_overlay"
        or concept_evidence.get("concept_source_kind") == "tushare_current_overlay"
    )


def _theme_breakout_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "sector_membership", "sector_strength", "stock_ohlcv", "stock_status"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but theme breakout inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    if stock_outputs.sector_rank_payload is None:
        return "Sector rank is unavailable, so the theme breakout proxy is blocked."
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "Market gate is unavailable or stale, so theme breakout observations cannot be evaluated."
    if market_state == "OVERHEAT":
        return "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy."
    return "Theme breakout proxy produced no payload for the resolved inputs."


def _has_hybrid_fusion_candidate_source(
    *,
    stock_candidates_payload: dict[str, object] | None,
    factor_screen_payload: dict[str, object] | None,
    theme_breakout_payload: dict[str, object] | None,
) -> bool:
    return any(
        (
            _payload_item_count(stock_candidates_payload) > 0,
            _payload_item_count(factor_screen_payload) > 0,
            _theme_breakout_stock_item_count(theme_breakout_payload) > 0,
        )
    )


def _hybrid_fusion_unavailable_reason_from_payloads(
    *,
    market_state: str,
    stock_candidates_payload: dict[str, object] | None,
    factor_screen_payload: dict[str, object] | None,
    theme_breakout_payload: dict[str, object] | None,
) -> str:
    missing_sources: list[str] = []
    if _payload_item_count(stock_candidates_payload) <= 0:
        missing_sources.append("stock_candidates")
    if _payload_item_count(factor_screen_payload) <= 0:
        missing_sources.append("factor_screen_candidates")
    if _theme_breakout_stock_item_count(theme_breakout_payload) <= 0:
        missing_sources.append("theme_breakout")
    if len(missing_sources) == 3:
        return (
            "Hybrid fusion requires at least one landed candidate source: "
            "stock_candidates, factor_screen_candidates, or theme_breakout. "
            f"Missing candidate source rows: {', '.join(missing_sources)}."
        )
    if market_state not in {"WARM", "HOT"}:
        return f"Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is {market_state}."
    return ""


def _payload_item_count(payload: dict[str, object] | None) -> int:
    raw = payload.get("items") if isinstance(payload, dict) else None
    return len(raw) if isinstance(raw, list) else 0


def _theme_breakout_stock_item_count(payload: dict[str, object] | None) -> int:
    raw_themes = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_themes, list):
        return 0
    count = 0
    for raw_theme in raw_themes:
        if not isinstance(raw_theme, dict):
            continue
        raw_items = raw_theme.get("items")
        if isinstance(raw_items, list):
            count += sum(1 for raw_item in raw_items if isinstance(raw_item, dict))
    return count


def _stock_unavailable_input_family(stock_outputs: _ChoiceStockOutputs) -> str:
    if stock_outputs.stock_candidate_block_reason:
        if _is_stock_candidate_policy_inactive_reason(stock_outputs.stock_candidate_block_reason):
            return STOCK_CANDIDATE_POLICY_INACTIVE_INPUT_FAMILY
        return "limit_up_quality"
    return "stock_universe"


def _risk_unavailable_reason(specific_reason: str = "") -> str:
    reason = (
        f"The defended-bundle {MVP_RULE_LABEL} MVP remains blocked. Existing formal ledger "
        "position_snapshot/position_snapshot_agg are not accepted for Livermore A-share risk_exit "
        "because their governed schema is bond/ledger-shaped and lacks proven stock_code, "
        "Livermore entry_cost, and bars_since_entry semantics. Current accepted stock holding "
        "fact source remains livermore_position_snapshot plus choice_stock_daily_observation close_history."
    )
    if specific_reason:
        return f"{reason} Current blocker: {specific_reason}"
    return reason


def _coverage_gap_status(coverage: ChoiceStockMaterializationCoverage | None) -> str:
    if coverage is None:
        return "missing"
    if coverage.status == "partial":
        return "partial"
    return "missing"


def _sector_status(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.sector_rank_payload is not None:
        return "ready"
    if not stock_readiness.ready:
        return "missing"
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.status == "not_materialized":
        return "missing"
    if not stock_outputs.sector_coverage.full_coverage:
        return "partial"
    return "blocked"


def _stock_status(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.stock_candidates_payload is not None:
        return "ready"
    if not stock_readiness.ready:
        return "blocked"
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "blocked"
    if not stock_outputs.stock_coverage.full_coverage:
        return "partial"
    if stock_outputs.sector_rank_payload is None or market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "blocked"
    return "blocked"


def _sector_missing_inputs(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> list[str]:
    if stock_outputs.sector_rank_payload is not None:
        return []
    if not stock_readiness.ready:
        return _choice_stock_missing_inputs(
            stock_readiness=stock_readiness,
            families=["sector_membership", "sector_strength"],
        )
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.full_coverage:
        return []
    return _missing_families_from_request_items(stock_outputs.sector_coverage.missing_request_items)


def _missing_families_from_request_items(items: list[str]) -> list[str]:
    families = [str(item).split(":", 1)[0] for item in items if item]
    return _unique_preserving_order(families)
