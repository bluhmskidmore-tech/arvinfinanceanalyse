from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Literal, SupportsFloat, SupportsIndex, SupportsInt, cast

import duckdb
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    StockAnalysisThemeOverlayReader,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.livermore_candidate_history_envelope_support import (
    _default_snapshot_from,
)
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_backtest_window_summary,
    livermore_candidate_history_envelope_or_none,
)
from backend.app.services.macro_bond_linkage_service import get_macro_environment_context
from backend.app.services.market_data_livermore_service import (
    livermore_attested_strategy_envelope_from_catalog,
    livermore_strategy_envelope_from_catalog,
    livermore_strategy_envelope_from_catalog_from_connection,
)
from backend.app.services.pretrade_qualification import STRATEGY_CALCULATION_MODE

DISCLAIMER = "Observation-only output. This service does not generate trading instructions."
LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND = "market_data.livermore.signal_confluence"
LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION = "rv_livermore_signal_confluence_v3_authoritative_macro_lineage"
LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION = "cv_livermore_signal_confluence_v3_authoritative_macro_lineage"
ENTRY_OBSERVATION_STATES = POLICY.entry_observation_states
REPLAY_READY_COMPLETED_DATES = 20
REPLAY_READY_MATCHED_ENTRIES = 100
REPLAY_PARTIAL_COMPLETED_DATES = 5
REPLAY_PARTIAL_MATCHED_ENTRIES = 30
REPLAY_REQUIRED_HORIZONS = ("return_5d", "return_20d")
REPLAY_EVIDENCE_LIMIT = 500
AUTHORITATIVE_MACRO_REQUIRED_INPUTS = ("PMI", "credit_impulse")
MACRO_MULTIPLIERS = POLICY.macro_multipliers
MACRO_CROSS_ASSET_REUSE_DISCLOSURES = (
    "Legacy bond-side macro_bond_linkage composite score is retained for degraded disclosure only; "
    "it never authorizes equity entry observations.",
    "Legacy bond macro thresholds of +/-0.3 are empirical and have no independent equity-side contract source.",
)


def load_macro_adversarial_signal_payload(
    *, output_dir: str | Path | None = None
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        from backend.app.services.macro_adversarial_signal_service import (
            load_macro_adversarial_signal_payload as loader,
        )
    except ModuleNotFoundError as exc:
        if exc.name != "backend.app.services.macro_adversarial_signal_service":
            raise
        return {}, {}

    payload, meta = loader(output_dir=output_dir)
    return _dict_payload(payload), _dict_payload(meta)


def livermore_signal_confluence_envelope(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    choice_stock_catalog_file: object,
    theme_overlay_reader: StockAnalysisThemeOverlayReader | None = None,
    _conn: duckdb.DuckDBPyConnection | None = None,
    _captured_external_inputs: Mapping[str, object] | None = None,
    _strategy_calculation_mode: str | None = None,
) -> dict[str, object]:
    if _strategy_calculation_mode not in {None, STRATEGY_CALCULATION_MODE}:
        raise ValueError("unsupported pretrade strategy calculation mode")
    if (
        _captured_external_inputs is not None
        and _conn is None
        and _strategy_calculation_mode != STRATEGY_CALCULATION_MODE
    ):
        raise ValueError("captured external inputs require attested strategy mode")
    catalog_file = cast(str | Path, choice_stock_catalog_file)
    if _conn is None:
        if _strategy_calculation_mode == STRATEGY_CALCULATION_MODE:
            livermore_envelope = livermore_attested_strategy_envelope_from_catalog(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                choice_stock_catalog_file=catalog_file,
                theme_overlay_reader=theme_overlay_reader,
                captured_external_inputs=_captured_external_inputs,
            )
        else:
            livermore_envelope = livermore_strategy_envelope_from_catalog(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                choice_stock_catalog_file=catalog_file,
                theme_overlay_reader=theme_overlay_reader,
            )
    else:
        livermore_envelope = livermore_strategy_envelope_from_catalog_from_connection(
            _conn,
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            choice_stock_catalog_file=catalog_file,
            theme_overlay_reader=theme_overlay_reader,
            backfill_mode=True,
            captured_external_inputs=_captured_external_inputs,
        )
    livermore_meta = _dict_payload(livermore_envelope.get("result_meta"))
    livermore_payload = _dict_payload(livermore_envelope.get("result"))
    resolved_as_of_date = _optional_text(livermore_payload.get("as_of_date")) or _optional_text(as_of_date)

    macro_meta: dict[str, object] = {}
    macro_payload: dict[str, object] = {}
    if resolved_as_of_date:
        if _conn is not None:
            macro_envelope = get_macro_environment_context(
                date.fromisoformat(resolved_as_of_date),
                _conn=_conn,
                _duckdb_path=duckdb_path,
            )
        else:
            macro_envelope = get_macro_environment_context(
                date.fromisoformat(resolved_as_of_date)
            )
        macro_meta = _dict_payload(macro_envelope.get("result_meta"))
        macro_payload = _dict_payload(macro_envelope.get("result"))
    if _captured_external_inputs is None:
        adversarial_payload, adversarial_meta = load_macro_adversarial_signal_payload(
            output_dir=None
        )
    else:
        adversarial_payload = _dict_payload(
            _captured_external_inputs.get("adversarial_payload")
        )
        adversarial_meta = _dict_payload(
            _captured_external_inputs.get("adversarial_meta")
        )
    adversarial_meta_for_envelope = (
        {}
        if adversarial_payload.get("status") == "missing"
        and not adversarial_payload.get("items")
        else adversarial_meta
    )
    replay_snapshot_to = resolved_as_of_date[:10] if resolved_as_of_date else None
    replay_snapshot_from = _default_snapshot_from(replay_snapshot_to) if replay_snapshot_to else None
    if replay_snapshot_to:
        replay_summary = dict(
            livermore_candidate_history_backtest_window_summary(
                duckdb_path=duckdb_path,
                stock_code=None,
                snapshot_from=replay_snapshot_from,
                snapshot_to=replay_snapshot_to,
                evaluation_as_of_date=replay_snapshot_to,
                _conn=_conn,
            )
        )
        replay_summary.setdefault("observed_snapshot_from", replay_summary.get("snapshot_from"))
        replay_summary.setdefault("observed_snapshot_to", replay_summary.get("snapshot_to"))
        replay_summary["requested_snapshot_from"] = replay_snapshot_from
        replay_summary["requested_snapshot_to"] = replay_snapshot_to
        # Keep the confluence compatibility aliases on the requested boundary;
        # explicit observed_* fields disclose the actually covered trade dates.
        replay_summary["snapshot_from"] = replay_snapshot_from
        replay_summary["snapshot_to"] = replay_snapshot_to
    else:
        replay_summary = {}

    result_payload = build_livermore_signal_confluence(
        as_of_date=resolved_as_of_date or "",
        livermore_payload=livermore_payload,
        strategy_meta=livermore_meta,
        macro_payload=macro_payload,
        adversarial_payload=adversarial_payload,
        backtest_window_summary=replay_summary,
    )
    _attach_legacy_bond_lineage(result_payload, macro_meta=macro_meta)
    _attach_replay_evidence(
        result_payload,
        duckdb_path=duckdb_path,
        as_of_date=resolved_as_of_date,
        conn=_conn,
    )
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_signal_confluence_{date.today().strftime('%Y%m%d')}",
        result_kind=LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND,
        cache_version=LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION,
        source_version=_combine_lineage(
            [
                _meta_source_version(livermore_meta),
                _meta_source_version(adversarial_meta_for_envelope),
            ],
            empty_value="sv_livermore_signal_confluence_empty",
        ),
        rule_version=LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        quality_flag=_merge_quality_flag(
            _meta_quality_flag(livermore_meta),
            _meta_quality_flag(adversarial_meta_for_envelope),
        ),
        vendor_version=_combine_lineage(
            [
                _meta_vendor_version(livermore_meta),
                _meta_vendor_version(adversarial_meta_for_envelope),
            ],
            empty_value="vv_none",
        ),
        vendor_status=_merge_vendor_status(
            _meta_vendor_status(livermore_meta),
            _meta_vendor_status(adversarial_meta_for_envelope),
        ),
        fallback_mode=_merge_fallback_mode(
            _meta_fallback_mode(livermore_meta),
            _meta_fallback_mode(adversarial_meta_for_envelope),
        ),
        filters_applied={
            "requested_as_of_date": _optional_text(as_of_date),
            "as_of_date": resolved_as_of_date,
            "replay_snapshot_from": replay_snapshot_from,
            "replay_snapshot_to": replay_snapshot_to,
        },
        tables_used=_combine_tables(
            _meta_tables_used(livermore_meta),
            _meta_tables_used(adversarial_meta_for_envelope),
            replay_summary.get("tables_used"),
        ),
        evidence_rows=(
            _safe_int(_meta_evidence_rows(livermore_meta))
            + _safe_int(_meta_evidence_rows(adversarial_meta_for_envelope))
        ),
        result_payload=result_payload,
    )


def build_livermore_replay_status(backtest_window_summary: dict[str, object] | None = None) -> dict[str, object]:
    return _build_replay_status(backtest_window_summary)


def build_livermore_signal_confluence(
    *,
    as_of_date: str,
    livermore_payload: dict[str, object],
    macro_payload: dict[str, object],
    strategy_meta: dict[str, object] | None = None,
    adversarial_payload: dict[str, object] | None = None,
    backtest_window_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    diagnostics: list[str] = []

    composite_score = _extract_composite_score(macro_payload)
    legacy_macro_status = _macro_status(composite_score)
    if composite_score is None:
        diagnostics.append("Legacy bond macro composite score is missing; it cannot authorize entry observations.")
    else:
        diagnostics.extend(MACRO_CROSS_ASSET_REUSE_DISCLOSURES)

    market_gate = _mapping(livermore_payload.get("market_gate"))
    if market_gate is None:
        diagnostics.append("Missing Livermore market gate; entry observations are blocked.")
    market_gate_state = str((market_gate or {}).get("state") or "UNKNOWN").upper()
    market_gate_exposure = _float_or_none((market_gate or {}).get("exposure"))
    if market_gate_exposure is None:
        diagnostics.append(
            "Missing Livermore market gate exposure; position size hint is unavailable."
        )

    macro_context = _authoritative_macro_context(
        as_of_date=as_of_date,
        market_gate=market_gate,
        strategy_meta=strategy_meta,
        legacy_composite_score=composite_score,
        legacy_macro_status=legacy_macro_status,
    )
    macro_status = str(macro_context["status"])
    macro_multiplier = MACRO_MULTIPLIERS[macro_status]
    allows_new_entry_observations = (
        market_gate is not None
        and market_gate_state in ENTRY_OBSERVATION_STATES
        and macro_context["authority_status"] == "ready"
        and macro_status in {"supportive", "neutral"}
    )
    if macro_context["authority_status"] != "ready":
        diagnostics.append(
            "Authoritative PMI/credit-expansion-proxy (social-financing-stock YoY delta proxy) "
            "market-gate context is not ready; entry observations fail closed."
        )
    position_size_hint = (
        None if market_gate_exposure is None else round(market_gate_exposure * macro_multiplier, 4)
    )
    adversarial_context = _build_adversarial_context(
        adversarial_payload=adversarial_payload,
        allows_new_entry_observations=allows_new_entry_observations,
        diagnostics=diagnostics,
    )
    entry_observation_action = (
        "observe_only"
        if bool(adversarial_context.get("blocks_new_entry_observations"))
        else ("observe_entry_setup" if allows_new_entry_observations else "observe_only")
    )

    entry_observations = _build_entry_observations(
        livermore_payload=livermore_payload,
        entry_observation_action=entry_observation_action,
        diagnostics=diagnostics,
    )
    exit_observations = _build_exit_observations(
        livermore_payload=livermore_payload,
        diagnostics=diagnostics,
    )

    diagnostics.append(DISCLAIMER)
    return {
        "as_of_date": as_of_date,
        "macro_context": {**macro_context, "multiplier": macro_multiplier},
        "adversarial_context": adversarial_context,
        "strategy_context": {
            "market_gate_state": market_gate_state,
            "market_gate_exposure": market_gate_exposure,
            "allows_new_entry_observations": allows_new_entry_observations,
            "new_entry_observation_allowed": allows_new_entry_observations,
            "position_size_hint": position_size_hint,
        },
        "closed_loop_state": _build_closed_loop_state(
            allows_new_entry_observations=allows_new_entry_observations,
            adversarial_context=adversarial_context,
            entry_observation_action=entry_observation_action,
            exit_observations=exit_observations,
            backtest_window_summary=backtest_window_summary,
        ),
        "position_size_hint": position_size_hint,
        "entry_observations": entry_observations,
        "exit_observations": exit_observations,
        "diagnostics": diagnostics,
        "disclaimer": DISCLAIMER,
    }


def _build_entry_observations(
    *,
    livermore_payload: Mapping[str, object],
    entry_observation_action: str,
    diagnostics: list[str],
) -> list[dict[str, object]]:
    stock_candidates = _mapping(livermore_payload.get("stock_candidates"))
    items = _list_of_mappings((stock_candidates or {}).get("items"))
    if not items:
        diagnostics.append("No stock candidates available for observation.")
        return []

    return [
        {
            "stock_code": item.get("stock_code"),
            "stock_name": item.get("stock_name"),
            "action": entry_observation_action,
            "trigger_price": item.get("breakout_level"),
            "current_price": item.get("close"),
            "invalidation_reference_price": item.get("ema10"),
            "evidence": _entry_evidence(item, diagnostics),
        }
        for item in items
    ]


def _build_adversarial_context(
    *,
    adversarial_payload: Mapping[str, object] | None,
    allows_new_entry_observations: bool,
    diagnostics: list[str],
) -> dict[str, object]:
    payload = adversarial_payload if isinstance(adversarial_payload, Mapping) else None
    status = _adversarial_status(payload)
    risk_gate = _adversarial_risk_gate(payload, status=status)
    payload_diagnostics = _adversarial_diagnostics(payload)
    blocks_new_entry_observations = allows_new_entry_observations and risk_gate == "block"

    if status == "missing":
        diagnostics.append("Macro adversarial signal is missing; no adversarial gate is applied.")
    elif status == "degraded":
        diagnostics.append("Macro adversarial signal is degraded; no adversarial gate is applied.")

    if blocks_new_entry_observations:
        diagnostics.append(
            "Adversarial risk gate is blocking new entry observations; candidate entries stay observe_only."
        )

    diagnostics.extend(payload_diagnostics)
    return {
        "status": status,
        "mode": _optional_text((payload or {}).get("mode")) or (
            "missing" if status == "missing" else "macro_adversarial_crowding"
        ),
        "risk_gate": risk_gate,
        "position_scale": _float_or_none((payload or {}).get("position_scale")),
        "strongest_block_reason": _optional_text((payload or {}).get("strongest_block_reason")),
        "blocks_new_entry_observations": blocks_new_entry_observations,
        "diagnostics": payload_diagnostics,
    }


def _build_closed_loop_state(
    *,
    allows_new_entry_observations: bool,
    adversarial_context: Mapping[str, object],
    entry_observation_action: str,
    exit_observations: list[dict[str, object]],
    backtest_window_summary: Mapping[str, object] | None,
) -> dict[str, object]:
    adversarial_status = _normalize_adversarial_status(adversarial_context.get("status"))
    if bool(adversarial_context.get("blocks_new_entry_observations")):
        status = "blocked_by_adversarial"
        entry_gate = "blocked"
    elif adversarial_status in {"missing", "degraded"}:
        status = f"degraded_{adversarial_status}_adversarial"
        entry_gate = "open" if entry_observation_action == "observe_entry_setup" else entry_observation_action
    elif allows_new_entry_observations:
        status = "open"
        entry_gate = "open"
    else:
        status = "observe_only"
        entry_gate = "observe_only"
    lineage_status = "complete"
    if adversarial_status == "missing":
        lineage_status = "missing"
    elif adversarial_status == "degraded":
        lineage_status = "degraded"
    return {
        "status": status,
        "entry_gate": entry_gate,
        "exit_gate": _exit_gate(exit_observations),
        "replay_status": _build_replay_status(backtest_window_summary),
        "lineage_status": lineage_status,
        "market_macro_allows_observation": allows_new_entry_observations,
        "adversarial_status": adversarial_status,
        "adversarial_risk_gate": _optional_text(adversarial_context.get("risk_gate")) or "unknown",
        "entry_observation_action": entry_observation_action,
    }


def _build_replay_status(summary: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(summary, Mapping):
        return _empty_replay_status()

    included_completed_stats_dates = _string_list(
        summary.get("_included_completed_stats_dates") or summary.get("included_completed_stats_dates")
    )
    completed_dates = _safe_int(summary.get("replay_dates_completed"))
    completed_rows = _safe_int(summary.get("completed_rows"))
    pending_dates = _safe_int(summary.get("replay_dates_pending"))
    pending_tail_dates = _string_list(summary.get("pending_tail_dates"))
    blocking_pending_dates = _string_list(summary.get("blocking_pending_dates"))
    pending_tail_count = _safe_int(summary.get("replay_dates_pending_tail"))
    blocking_pending_count = _safe_int(summary.get("replay_dates_pending_blocking"))
    if pending_tail_dates:
        pending_tail_count = len(pending_tail_dates)
    if blocking_pending_dates:
        blocking_pending_count = len(blocking_pending_dates)
    if "blocking_pending_dates" not in summary and "replay_dates_pending_blocking" not in summary:
        # Older summaries did not distinguish a natural T+20 tail.  Preserve
        # fail-closed behavior rather than silently treating all pending dates
        # as non-blocking.
        blocking_pending_count = pending_dates
    unsupported_dates = _safe_int(summary.get("replay_dates_unsupported"))
    proxy_only_dates = _safe_int(summary.get("replay_dates_proxy_only"))
    matched_entry_count, has_required_horizon_stats = _replay_matched_entry_count(summary)
    maturity_status = _replay_maturity_status(
        completed_dates=completed_dates,
        blocking_pending_dates=blocking_pending_count,
        unsupported_dates=unsupported_dates,
        proxy_only_dates=proxy_only_dates,
        matched_entry_count=matched_entry_count,
        has_required_horizon_stats=has_required_horizon_stats,
    )
    return {
        "window_status": _optional_text(summary.get("status")) or "unsupported",
        "snapshot_from": _optional_text(summary.get("snapshot_from")),
        "snapshot_to": _optional_text(summary.get("snapshot_to")),
        "requested_snapshot_from": _optional_text(summary.get("requested_snapshot_from")),
        "requested_snapshot_to": _optional_text(summary.get("requested_snapshot_to")),
        "observed_snapshot_from": _optional_text(summary.get("observed_snapshot_from")),
        "observed_snapshot_to": _optional_text(summary.get("observed_snapshot_to")),
        "metric_basis": _replay_decision_metric_basis(summary),
        "research_metric_basis": _optional_text(summary.get("research_metric_basis")),
        "maturity_status": maturity_status,
        "has_decision_usable_completed_stats": maturity_status == "ready",
        "completed_dates": completed_dates,
        "pending_dates": pending_dates,
        "pending_tail_date_count": pending_tail_count,
        "pending_tail_dates": pending_tail_dates,
        "blocking_pending_date_count": blocking_pending_count,
        "blocking_pending_dates": blocking_pending_dates,
        "unsupported_dates": unsupported_dates,
        "proxy_only_dates": proxy_only_dates,
        "completed_candidate_rows": completed_rows,
        "pending_candidate_rows": _safe_int(summary.get("pending_rows")),
        "unsupported_candidate_rows": _safe_int(summary.get("unsupported_rows")),
        "proxy_only_candidate_rows": _safe_int(summary.get("proxy_only_rows")),
        "matched_entry_count": matched_entry_count,
        "has_required_horizon_stats": has_required_horizon_stats,
        "included_completed_stats_dates": included_completed_stats_dates,
        "blocked_dates": _replay_blocked_dates(summary.get("date_reasons")),
        "completed_zero_signal_dates": _completed_zero_signal_dates(summary.get("date_reasons")),
    }


def _empty_replay_status() -> dict[str, object]:
    return {
        "window_status": "unsupported",
        "snapshot_from": None,
        "snapshot_to": None,
        "requested_snapshot_from": None,
        "requested_snapshot_to": None,
        "observed_snapshot_from": None,
        "observed_snapshot_to": None,
        "metric_basis": None,
        "research_metric_basis": None,
        "maturity_status": "missing",
        "has_decision_usable_completed_stats": False,
        "completed_dates": 0,
        "pending_dates": 0,
        "pending_tail_date_count": 0,
        "pending_tail_dates": [],
        "blocking_pending_date_count": 0,
        "blocking_pending_dates": [],
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "completed_candidate_rows": 0,
        "pending_candidate_rows": 0,
        "unsupported_candidate_rows": 0,
        "proxy_only_candidate_rows": 0,
        "matched_entry_count": 0,
        "has_required_horizon_stats": False,
        "included_completed_stats_dates": [],
        "blocked_dates": [],
        "completed_zero_signal_dates": [],
    }


def _replay_maturity_status(
    *,
    completed_dates: int,
    blocking_pending_dates: int,
    unsupported_dates: int,
    proxy_only_dates: int,
    matched_entry_count: int,
    has_required_horizon_stats: bool,
) -> str:
    if (
        completed_dates >= REPLAY_READY_COMPLETED_DATES
        and blocking_pending_dates == 0
        and unsupported_dates == 0
        and proxy_only_dates == 0
        and matched_entry_count >= REPLAY_READY_MATCHED_ENTRIES
        and has_required_horizon_stats
    ):
        return "ready"
    if completed_dates >= REPLAY_PARTIAL_COMPLETED_DATES or matched_entry_count >= REPLAY_PARTIAL_MATCHED_ENTRIES:
        return "partial"
    if completed_dates > 0 or matched_entry_count > 0:
        return "insufficient"
    if blocking_pending_dates > 0:
        return "pending"
    if unsupported_dates > 0:
        return "unsupported"
    if proxy_only_dates > 0:
        return "proxy_only"
    return "missing"


def _replay_matched_entry_count(summary: Mapping[str, object]) -> tuple[int, bool]:
    execution_stats = _mapping(summary.get("execution_usable_stats"))
    decision_metric_basis = _replay_decision_metric_basis(summary)
    if decision_metric_basis != "net_next_open_adj" or execution_stats is None:
        return 0, False
    stats = _mapping(execution_stats.get("by_signal_kind_horizon_usable_stats"))
    if stats is None:
        return 0, False
    stock_candidate_stats = _mapping(stats.get("stock_candidate"))
    if stock_candidate_stats is None:
        return 0, False
    horizon_counts: list[int] = []
    for horizon in REPLAY_REQUIRED_HORIZONS:
        horizon_stats = _mapping(stock_candidate_stats.get(horizon))
        if horizon_stats is None:
            return 0, False
        horizon_counts.append(_safe_int(horizon_stats.get("available_count")))
    return min(horizon_counts), True


def _replay_decision_metric_basis(summary: Mapping[str, object]) -> str | None:
    declared = _optional_text(summary.get("decision_metric_basis"))
    execution_stats = _mapping(summary.get("execution_usable_stats"))
    nested = _optional_text(execution_stats.get("metric_basis")) if execution_stats else None
    if declared and nested and declared != nested:
        return None
    return declared or nested


def _replay_blocked_dates(value: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in _list_of_mappings(value):
        status = _optional_text(item.get("status"))
        if status == "completed":
            continue
        trade_date = _optional_text(item.get("trade_date"))
        reason_code = _optional_text(item.get("reason_code"))
        if not trade_date or not status or not reason_code:
            continue
        rows.append(
            {
                "trade_date": trade_date,
                "status": status,
                "reason_code": reason_code,
                "signal_kinds": _string_list(item.get("signal_kinds")),
            }
        )
    return rows


def _completed_zero_signal_dates(value: object) -> list[str]:
    dates = []
    for item in _list_of_mappings(value):
        if (
            _optional_text(item.get("status")) == "completed"
            and _optional_text(item.get("reason_code")) == "no_strategy_signals"
            and item.get("affects_completed_stats") is True
        ):
            trade_date = _optional_text(item.get("trade_date"))
            if trade_date:
                dates.append(trade_date)
    return dates


def _exit_gate(exit_observations: list[dict[str, object]]) -> str:
    if any(item.get("triggered") is True or item.get("action") == "exit_triggered" for item in exit_observations):
        return "triggered"
    if exit_observations:
        return "watch"
    return "missing"


def _build_exit_observations(
    *,
    livermore_payload: Mapping[str, object],
    diagnostics: list[str],
) -> list[dict[str, object]]:
    risk_exit = _mapping(livermore_payload.get("risk_exit"))
    watch_items = _list_of_mappings((risk_exit or {}).get("watch_items"))
    if watch_items:
        observations: list[dict[str, object]] = []
        for item in watch_items:
            triggered = bool(item.get("triggered"))
            observations.append(
                {
                    "stock_code": item.get("stock_code"),
                    "stock_name": item.get("stock_name"),
                    "action": "exit_triggered" if triggered else "observe_exit_watch",
                    "current_price": item.get("latest_close"),
                    "exit_watch_price": _exit_watch_price(item),
                    "triggered": triggered,
                    "evidence": _exit_evidence(item, diagnostics),
                }
            )
        return observations

    triggered_items = _list_of_mappings((risk_exit or {}).get("items"))
    if triggered_items:
        return [
            {
                "stock_code": item.get("stock_code"),
                "stock_name": item.get("stock_name"),
                "action": "exit_triggered",
                "current_price": item.get("latest_close"),
                "exit_watch_price": item.get("latest_ema10"),
                "triggered": True,
                "evidence": _exit_evidence(item, diagnostics),
            }
            for item in triggered_items
        ]

    diagnostics.append("No risk exit watch items or triggered exit items available.")
    return []


def _entry_evidence(item: Mapping[str, object], diagnostics: list[str]) -> list[str]:
    evidence: list[str] = []
    label = _security_label(item)
    if item.get("breakout_level") is None:
        diagnostics.append(f"{label} is missing breakout_level; entry trigger price is unavailable.")
    else:
        evidence.append("候选触发价来自 Livermore breakout_level。")

    if item.get("ema10") is None:
        diagnostics.append(f"{label} is missing EMA10; invalidation reference price is unavailable.")
    else:
        evidence.append("失效参考价来自候选股 EMA10。")
    return evidence


def _exit_watch_price(item: Mapping[str, object]) -> object:
    if item.get("exit_watch_price") is not None:
        return item.get("exit_watch_price")
    return item.get("latest_ema10")


def _exit_evidence(item: Mapping[str, object], diagnostics: list[str]) -> list[str]:
    if _exit_watch_price(item) is not None:
        return ["退出观察价来自 Livermore EMA10。"]
    diagnostics.append(f"{_security_label(item)} is missing EMA10; exit watch price is unavailable.")
    return []


def _security_label(item: Mapping[str, object]) -> str:
    stock_code = str(item.get("stock_code") or "").strip()
    if stock_code:
        return f"Stock {stock_code}"
    return "A Livermore row"


def _extract_composite_score(payload: Mapping[str, object]) -> float | None:
    direct_score = _float_or_none(payload.get("composite_score"))
    if direct_score is not None:
        return direct_score

    for key in ("environment_score", "macro_environment"):
        macro_environment = _mapping(payload.get(key))
        if macro_environment is None:
            continue
        score = _float_or_none(macro_environment.get("composite_score"))
        if score is not None:
            return score
    return None


def _authoritative_macro_context(
    *,
    as_of_date: str,
    market_gate: Mapping[str, object] | None,
    strategy_meta: Mapping[str, object] | None,
    legacy_composite_score: float | None,
    legacy_macro_status: str,
) -> dict[str, object]:
    raw_context = _mapping((market_gate or {}).get("macro_context")) or {}
    components = [dict(item) for item in _list_of_mappings(raw_context.get("components"))]
    gate_as_of_date = _optional_text(raw_context.get("gate_as_of_date"))
    expected_as_of_date = as_of_date[:10] if as_of_date else None
    component_by_family = {
        str(item.get("input_family") or "").strip(): item
        for item in components
        if str(item.get("input_family") or "").strip()
    }
    required_inputs = list(AUTHORITATIVE_MACRO_REQUIRED_INPUTS)
    missing_inputs = [name for name in required_inputs if name not in component_by_family]
    authority_reasons: list[str] = []

    if _optional_text(raw_context.get("status")) != "ready":
        authority_reasons.append("market_gate_macro_status_not_ready")
    if not gate_as_of_date or gate_as_of_date != expected_as_of_date:
        authority_reasons.append("gate_as_of_date_mismatch")

    strategy_quality = _optional_text((strategy_meta or {}).get("quality_flag"))
    strategy_vendor = _optional_text((strategy_meta or {}).get("vendor_status"))
    strategy_fallback = _optional_text((strategy_meta or {}).get("fallback_mode"))
    if strategy_quality != "ok":
        authority_reasons.append("strategy_quality_not_ok")
    if strategy_vendor != "ok":
        authority_reasons.append("strategy_vendor_not_ok")
    if strategy_fallback != "none":
        authority_reasons.append("strategy_fallback_active")

    pmi_component = component_by_family.get("PMI")
    credit_component = component_by_family.get("credit_impulse")
    if pmi_component is not None and _optional_text(pmi_component.get("input")) != "M0017126":
        authority_reasons.append("pmi_series_not_authoritative")
    if credit_component is not None and _optional_text(credit_component.get("input")) not in {
        "M5525763",
        "M0001385",
    }:
        authority_reasons.append("credit_impulse_series_not_authoritative")

    for family in required_inputs:
        component = component_by_family.get(family)
        if component is None:
            continue
        business_date = _optional_text(component.get("business_date"))
        age_days = component.get("age_days")
        tier = _optional_text(component.get("tier"))
        if tier != "fresh":
            authority_reasons.append(f"{family}_tier_not_fresh")
        if not isinstance(age_days, int) or age_days < 0:
            authority_reasons.append(f"{family}_age_not_usable")
        if not business_date or not gate_as_of_date or business_date > gate_as_of_date:
            authority_reasons.append(f"{family}_business_date_look_ahead")

    if missing_inputs:
        authority_reasons.append("required_macro_inputs_missing")
    cycle_state = _optional_text(raw_context.get("cycle_state"))
    if cycle_state not in {"expansion", "neutral", "contraction", "recession"}:
        authority_reasons.append("cycle_state_not_supported")
    if _float_or_none(raw_context.get("macro_score")) is None:
        authority_reasons.append("macro_score_not_usable")

    authority_status = "ready" if not authority_reasons else "blocked"
    cycle_status = {
        "expansion": "supportive",
        "neutral": "neutral",
        "contraction": "restrictive",
        "recession": "restrictive",
    }
    status = cycle_status.get(cycle_state, "unknown") if cycle_state is not None else "unknown"
    if authority_status != "ready":
        status = "unknown"
    return {
        "status": status,
        "composite_score": _float_or_none(raw_context.get("macro_score")),
        "source_metric": "market_gate.macro_context.macro_score",
        "authority_status": authority_status,
        "authority_reasons": authority_reasons,
        "cycle_state": cycle_state,
        "gate_as_of_date": gate_as_of_date,
        "data_date": _optional_text(raw_context.get("data_date")),
        "lag_days": raw_context.get("lag_days"),
        "max_component_lag_days": raw_context.get("max_component_lag_days"),
        "components": components,
        "formula_version": _optional_text(raw_context.get("formula_version")),
        "evidence": _optional_text(raw_context.get("evidence")) or "",
        "required_inputs": required_inputs,
        "missing_inputs": missing_inputs,
        "legacy_bond_context": {
            "authority_status": "legacy_degraded_only",
            "status": legacy_macro_status,
            "composite_score": legacy_composite_score,
            "lineage": {},
        },
    }


def _macro_status(composite_score: float | None) -> str:
    if composite_score is None:
        return "unknown"
    if composite_score < -0.3:
        return "supportive"
    if composite_score > 0.3:
        return "restrictive"
    return "neutral"


def _adversarial_status(payload: Mapping[str, object] | None) -> str:
    if payload is None or not payload:
        return "missing"
    direct_status = _normalize_adversarial_status(
        payload.get("status")
        or payload.get("lineage_status")
        or (_mapping(payload.get("lineage")) or {}).get("status")
        or (_mapping(payload.get("source")) or {}).get("status")
    )
    if direct_status != "unknown":
        return direct_status
    if _adversarial_risk_gate(payload, status="unknown") in {"allow", "pass", "block"}:
        return "ok"
    return "unknown"


def _adversarial_risk_gate(payload: Mapping[str, object] | None, *, status: str) -> str:
    if status == "missing":
        return "missing"
    direct_gate = _optional_text(
        (payload or {}).get("risk_gate")
        or (_mapping((payload or {}).get("gate")) or {}).get("risk_gate")
        or (_mapping((payload or {}).get("summary")) or {}).get("risk_gate")
    )
    normalized = str(direct_gate or "").strip().lower()
    if normalized in {"allow", "pass", "block", "degraded", "missing", "error"}:
        return normalized
    return "unknown"


def _adversarial_diagnostics(payload: Mapping[str, object] | None) -> list[str]:
    if payload is None:
        return []
    for key in ("diagnostics", "warnings", "messages"):
        values = payload.get(key)
        if isinstance(values, list):
            return [text for item in values if (text := _optional_text(item))]
    return []


def _normalize_adversarial_status(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"ok", "ready", "allow", "pass", "complete"}:
        return "ok"
    if normalized in {"degraded", "warning", "stale", "error"}:
        return "degraded"
    if normalized in {"missing", "absent", "unavailable"}:
        return "missing"
    return "unknown"


def _mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _optional_text(item))]


def _safe_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return max(int(value), 0) if isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)) else 0
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value) if isinstance(value, (str, bytes, bytearray, SupportsFloat, SupportsIndex)) else None
    except (TypeError, ValueError):
        return None
    if parsed is None or not math.isfinite(parsed):
        return None
    return parsed


def _attach_replay_evidence(
    payload: dict[str, object],
    *,
    duckdb_path: str,
    as_of_date: str | None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> None:
    replay_evidence = _candidate_history_replay_evidence(
        payload=payload,
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        conn=conn,
    )
    payload["replay_evidence"] = replay_evidence


def _candidate_history_replay_evidence(
    *,
    payload: dict[str, object],
    duckdb_path: str,
    as_of_date: str | None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, object]:
    snapshot_as_of_date = as_of_date[:10] if as_of_date else None
    if not as_of_date:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    path = Path(duckdb_path)
    if not path.is_file():
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    envelope = livermore_candidate_history_envelope_or_none(
        duckdb_path=duckdb_path,
        stock_code=None,
        snapshot_from=snapshot_as_of_date,
        snapshot_to=snapshot_as_of_date,
        limit=REPLAY_EVIDENCE_LIMIT,
        _conn=conn,
    )
    if envelope is None:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)

    result = _dict_payload(envelope.get("result"))
    all_items = _list_of_dict_mappings(result.get("items"))
    row_count = _non_negative_int(result.get("all_filtered_row_count"), default=len(all_items))
    if row_count <= 0:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)

    replay_stock_codes = {_normalized_stock_code(item.get("stock_code")) for item in all_items}
    replay_stock_codes.discard("")
    entry_stock_codes = {
        _normalized_stock_code(item.get("stock_code"))
        for item in _list_of_dict_mappings(payload.get("entry_observations"))
    }
    entry_stock_codes.discard("")

    return {
        "status": "available",
        "snapshot_as_of_date": snapshot_as_of_date,
        "row_count": row_count,
        "matched_entry_count": len(entry_stock_codes & replay_stock_codes),
        "sample_items": [_replay_sample_item(item) for item in all_items[:5]],
    }


def _empty_replay_evidence(*, snapshot_as_of_date: str | None) -> dict[str, object]:
    return {
        "status": "missing",
        "snapshot_as_of_date": snapshot_as_of_date,
        "row_count": 0,
        "matched_entry_count": 0,
        "sample_items": [],
    }


def _replay_window_candidate_row_count(summary: dict[str, object]) -> int:
    return (
        _non_negative_int(summary.get("completed_rows"))
        + _non_negative_int(summary.get("pending_rows"))
        + _non_negative_int(summary.get("unsupported_rows"))
        + _non_negative_int(summary.get("proxy_only_rows"))
    )


def _replay_sample_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "stock_code": item.get("stock_code"),
        "stock_name": item.get("stock_name"),
        "candidate_rank": item.get("candidate_rank"),
        "signal_kind": item.get("signal_kind"),
        "data_status": item.get("data_status"),
    }


def _normalized_stock_code(value: object) -> str:
    return str(value or "").strip().upper()


def _dict_payload(value: object) -> dict[str, object]:
    mapping = _mapping(value)
    if mapping is None:
        return {}
    return dict(mapping)


def _list_of_dict_mappings(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in _list_of_mappings(value)]


def _non_negative_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value) if isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)) else default
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _attach_legacy_bond_lineage(
    payload: dict[str, object],
    *,
    macro_meta: dict[str, object],
) -> None:
    macro_context = payload.get("macro_context")
    if not isinstance(macro_context, dict):
        return
    legacy_context = macro_context.get("legacy_bond_context")
    if not isinstance(legacy_context, dict):
        return
    legacy_context["lineage"] = {
        "source_version": _optional_text(_meta_source_version(macro_meta)),
        "vendor_version": _optional_text(_meta_vendor_version(macro_meta)),
        "rule_version": _optional_text(macro_meta.get("rule_version")),
        "cache_version": _optional_text(macro_meta.get("cache_version")),
        "quality_flag": _optional_text(_meta_quality_flag(macro_meta)),
        "vendor_status": _optional_text(_meta_vendor_status(macro_meta)),
        "fallback_mode": _optional_text(_meta_fallback_mode(macro_meta)),
        "tables_used": _combine_tables(_meta_tables_used(macro_meta)),
        "evidence_rows": _safe_int(_meta_evidence_rows(macro_meta)),
    }


def _meta_source_version(meta: dict[str, object]) -> object:
    source = _dict_payload(meta.get("source"))
    return meta.get("source_version") or source.get("source_version") or source.get("version")


def _meta_quality_flag(meta: dict[str, object]) -> object:
    source = _dict_payload(meta.get("source"))
    return meta.get("quality_flag") or source.get("quality_flag") or source.get("status")


def _meta_vendor_version(meta: dict[str, object]) -> object:
    vendor = _dict_payload(meta.get("vendor"))
    return meta.get("vendor_version") or vendor.get("vendor_version") or vendor.get("version")


def _meta_vendor_status(meta: dict[str, object]) -> object:
    vendor = _dict_payload(meta.get("vendor"))
    return meta.get("vendor_status") or vendor.get("vendor_status") or vendor.get("status")


def _meta_fallback_mode(meta: dict[str, object]) -> object:
    source = _dict_payload(meta.get("source"))
    return meta.get("fallback_mode") or source.get("fallback_mode")


def _meta_tables_used(meta: dict[str, object]) -> object:
    return meta.get("tables_used") or meta.get("tables")


def _meta_evidence_rows(meta: dict[str, object]) -> object:
    evidence = _dict_payload(meta.get("evidence"))
    return meta.get("evidence_rows") or evidence.get("evidence_rows") or evidence.get("rows")


def _combine_lineage(values: list[object], *, empty_value: str) -> str:
    unique_values: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in unique_values:
            unique_values.append(text)
    if not unique_values:
        return empty_value
    if len(unique_values) == 1:
        return unique_values[0]
    return "__".join(unique_values)


def _merge_quality_flag(*values: object) -> Literal["ok", "warning", "error", "stale"]:
    normalized = {str(value or "").strip() for value in values if str(value or "").strip()}
    if "error" in normalized:
        return "error"
    if "stale" in normalized:
        return "stale"
    if "warning" in normalized:
        return "warning"
    return "ok"


def _merge_vendor_status(*values: object) -> Literal["ok", "vendor_stale", "vendor_unavailable"]:
    normalized = {str(value or "").strip() for value in values if str(value or "").strip()}
    if "vendor_unavailable" in normalized:
        return "vendor_unavailable"
    if "vendor_stale" in normalized:
        return "vendor_stale"
    return "ok"


def _merge_fallback_mode(*values: object) -> Literal["none", "latest_snapshot"]:
    if any(str(value or "").strip() == "latest_snapshot" for value in values):
        return "latest_snapshot"
    return "none"


def _combine_tables(*values: object) -> list[str]:
    combined: list[str] = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            text = str(item or "").strip()
            if text and text not in combined:
                combined.append(text)
    return combined
