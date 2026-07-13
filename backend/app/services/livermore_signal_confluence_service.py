from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from backend.app.core_finance.strategy_policy import POLICY
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    StockAnalysisThemeOverlayReader,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_backtest_window_summary,
    livermore_candidate_history_envelope_or_none,
)
from backend.app.services.macro_bond_linkage_service import get_macro_environment_context
from backend.app.services.market_data_livermore_service import livermore_strategy_envelope_from_catalog

DISCLAIMER = "Observation-only output. This service does not generate trading instructions."
LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND = "market_data.livermore.signal_confluence"
LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION = "rv_livermore_signal_confluence_v1"
LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION = "cv_livermore_signal_confluence_v1"
ENTRY_OBSERVATION_STATES = POLICY.entry_observation_states
REPLAY_READY_COMPLETED_DATES = 20
REPLAY_READY_MATCHED_ENTRIES = 100
REPLAY_PARTIAL_COMPLETED_DATES = 5
REPLAY_PARTIAL_MATCHED_ENTRIES = 30
REPLAY_REQUIRED_HORIZONS = ("return_5d", "return_20d")
MACRO_MULTIPLIERS = POLICY.macro_multipliers


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
) -> dict[str, object]:
    strategy_kwargs: dict[str, object] = {
        "duckdb_path": duckdb_path,
        "as_of_date": as_of_date,
        "choice_stock_catalog_file": choice_stock_catalog_file,
    }
    if theme_overlay_reader is not None:
        strategy_kwargs["theme_overlay_reader"] = theme_overlay_reader
    livermore_envelope = livermore_strategy_envelope_from_catalog(**strategy_kwargs)
    livermore_meta = _dict_payload(livermore_envelope.get("result_meta"))
    livermore_payload = _dict_payload(livermore_envelope.get("result"))
    resolved_as_of_date = _optional_text(livermore_payload.get("as_of_date")) or _optional_text(as_of_date)

    macro_meta: dict[str, object] = {}
    macro_payload: dict[str, object] = {}
    if resolved_as_of_date:
        macro_envelope = get_macro_environment_context(date.fromisoformat(resolved_as_of_date))
        macro_meta = _dict_payload(macro_envelope.get("result_meta"))
        macro_payload = _dict_payload(macro_envelope.get("result"))
    adversarial_payload, adversarial_meta = load_macro_adversarial_signal_payload(output_dir=None)
    adversarial_meta_for_envelope = (
        {}
        if adversarial_payload.get("status") == "missing"
        and not adversarial_payload.get("items")
        else adversarial_meta
    )
    replay_summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=duckdb_path,
        stock_code=None,
        snapshot_from=resolved_as_of_date[:10] if resolved_as_of_date else None,
        snapshot_to=resolved_as_of_date[:10] if resolved_as_of_date else None,
    )

    result_payload = build_livermore_signal_confluence(
        as_of_date=resolved_as_of_date or "",
        livermore_payload=livermore_payload,
        macro_payload=macro_payload,
        adversarial_payload=adversarial_payload,
        backtest_window_summary=replay_summary,
    )
    _attach_replay_evidence(
        result_payload,
        duckdb_path=duckdb_path,
        as_of_date=resolved_as_of_date,
        replay_summary=replay_summary,
    )
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_signal_confluence_{date.today().strftime('%Y%m%d')}",
        result_kind=LIVERMORE_SIGNAL_CONFLUENCE_RESULT_KIND,
        cache_version=LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION,
        source_version=_combine_lineage(
            [
                _meta_source_version(livermore_meta),
                _meta_source_version(macro_meta),
                _meta_source_version(adversarial_meta_for_envelope),
            ],
            empty_value="sv_livermore_signal_confluence_empty",
        ),
        rule_version=LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        quality_flag=_merge_quality_flag(
            _meta_quality_flag(livermore_meta),
            _meta_quality_flag(macro_meta),
            _meta_quality_flag(adversarial_meta_for_envelope),
        ),
        vendor_version=_combine_lineage(
            [
                _meta_vendor_version(livermore_meta),
                _meta_vendor_version(macro_meta),
                _meta_vendor_version(adversarial_meta_for_envelope),
            ],
            empty_value="vv_none",
        ),
        vendor_status=_merge_vendor_status(
            _meta_vendor_status(livermore_meta),
            _meta_vendor_status(macro_meta),
            _meta_vendor_status(adversarial_meta_for_envelope),
        ),
        fallback_mode=_merge_fallback_mode(
            _meta_fallback_mode(livermore_meta),
            _meta_fallback_mode(macro_meta),
            _meta_fallback_mode(adversarial_meta_for_envelope),
        ),
        filters_applied={
            "requested_as_of_date": _optional_text(as_of_date),
            "as_of_date": resolved_as_of_date,
        },
        tables_used=_combine_tables(
            _meta_tables_used(livermore_meta),
            _meta_tables_used(macro_meta),
            _meta_tables_used(adversarial_meta_for_envelope),
        ),
        evidence_rows=(
            _safe_int(_meta_evidence_rows(livermore_meta))
            + _safe_int(_meta_evidence_rows(macro_meta))
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
    adversarial_payload: dict[str, object] | None = None,
    backtest_window_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    diagnostics: list[str] = []

    composite_score = _extract_composite_score(macro_payload)
    macro_status = _macro_status(composite_score)
    if composite_score is None:
        diagnostics.append("Missing macro composite score; macro context is unknown.")

    market_gate = _mapping(livermore_payload.get("market_gate"))
    if market_gate is None:
        diagnostics.append("Missing Livermore market gate; entry observations are blocked.")
    market_gate_state = str((market_gate or {}).get("state") or "UNKNOWN").upper()
    market_gate_exposure = _safe_float((market_gate or {}).get("exposure"))

    macro_multiplier = MACRO_MULTIPLIERS[macro_status]
    allows_new_entry_observations = (
        market_gate is not None
        and market_gate_state in ENTRY_OBSERVATION_STATES
        and macro_status in {"supportive", "neutral"}
    )
    position_size_hint = round(market_gate_exposure * macro_multiplier, 4)
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
        "macro_context": {
            "status": macro_status,
            "composite_score": composite_score,
            "multiplier": macro_multiplier,
        },
        "adversarial_context": adversarial_context,
        "strategy_context": {
            "market_gate_state": market_gate_state,
            "market_gate_exposure": market_gate_exposure,
            "allows_new_entry_observations": allows_new_entry_observations,
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
        "position_scale": _safe_optional_float((payload or {}).get("position_scale")),
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
    unsupported_dates = _safe_int(summary.get("replay_dates_unsupported"))
    proxy_only_dates = _safe_int(summary.get("replay_dates_proxy_only"))
    matched_entry_count, has_required_horizon_stats = _replay_matched_entry_count(summary)
    maturity_status = _replay_maturity_status(
        completed_dates=completed_dates,
        pending_dates=pending_dates,
        unsupported_dates=unsupported_dates,
        proxy_only_dates=proxy_only_dates,
        matched_entry_count=matched_entry_count,
        has_required_horizon_stats=has_required_horizon_stats,
    )
    return {
        "window_status": _optional_text(summary.get("status")) or "unsupported",
        "maturity_status": maturity_status,
        "has_decision_usable_completed_stats": maturity_status == "ready",
        "completed_dates": completed_dates,
        "pending_dates": pending_dates,
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
        "maturity_status": "missing",
        "has_decision_usable_completed_stats": False,
        "completed_dates": 0,
        "pending_dates": 0,
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
    pending_dates: int,
    unsupported_dates: int,
    proxy_only_dates: int,
    matched_entry_count: int,
    has_required_horizon_stats: bool,
) -> str:
    if (
        completed_dates >= REPLAY_READY_COMPLETED_DATES
        and pending_dates == 0
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
    if pending_dates > 0:
        return "pending"
    if unsupported_dates > 0:
        return "unsupported"
    if proxy_only_dates > 0:
        return "proxy_only"
    return "missing"


def _replay_matched_entry_count(summary: Mapping[str, object]) -> tuple[int, bool]:
    stats = _mapping(summary.get("by_signal_kind_horizon_usable_stats")) or _mapping(
        summary.get("by_signal_kind_horizon_stats")
    )
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


def _replay_blocked_dates(value: object) -> list[dict[str, object]]:
    rows = []
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
    direct_score = _safe_optional_float(payload.get("composite_score"))
    if direct_score is not None:
        return direct_score

    for key in ("environment_score", "macro_environment"):
        macro_environment = _mapping(payload.get(key))
        if macro_environment is None:
            continue
        score = _safe_optional_float(macro_environment.get("composite_score"))
        if score is not None:
            return score
    return None


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
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _safe_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _safe_float(value: object) -> float:
    parsed = _safe_optional_float(value)
    if parsed is None:
        return 0.0
    return parsed


def _attach_replay_evidence(
    payload: dict[str, object],
    *,
    duckdb_path: str,
    as_of_date: str | None,
    replay_summary: dict[str, object],
) -> None:
    replay_evidence = _candidate_history_replay_evidence(
        payload=payload,
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        replay_summary=replay_summary,
    )
    payload["replay_evidence"] = replay_evidence


def _candidate_history_replay_evidence(
    *,
    payload: dict[str, object],
    duckdb_path: str,
    as_of_date: str | None,
    replay_summary: dict[str, object],
) -> dict[str, object]:
    snapshot_as_of_date = as_of_date[:10] if as_of_date else None
    if not as_of_date:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    path = Path(duckdb_path)
    if not path.is_file():
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    row_count = _replay_window_candidate_row_count(replay_summary)
    if row_count <= 0:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)
    envelope = livermore_candidate_history_envelope_or_none(
        duckdb_path=duckdb_path,
        stock_code=None,
        snapshot_from=snapshot_as_of_date,
        snapshot_to=snapshot_as_of_date,
        limit=max(row_count, 5),
    )
    if envelope is None:
        return _empty_replay_evidence(snapshot_as_of_date=snapshot_as_of_date)

    result = _dict_payload(envelope.get("result"))
    all_items = _list_of_dict_mappings(result.get("items"))

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
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


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


def _merge_quality_flag(*values: object) -> str:
    normalized = {str(value or "").strip() for value in values if str(value or "").strip()}
    if "error" in normalized:
        return "error"
    if "stale" in normalized:
        return "stale"
    if "warning" in normalized:
        return "warning"
    return "ok"


def _merge_vendor_status(*values: object) -> str:
    normalized = {str(value or "").strip() for value in values if str(value or "").strip()}
    if "vendor_unavailable" in normalized:
        return "vendor_unavailable"
    if "vendor_stale" in normalized:
        return "vendor_stale"
    return "ok"


def _merge_fallback_mode(*values: object) -> str:
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
