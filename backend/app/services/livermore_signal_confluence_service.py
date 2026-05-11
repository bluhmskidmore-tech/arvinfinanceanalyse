from __future__ import annotations

import math
from collections.abc import Mapping

DISCLAIMER = "Observation-only output. This service does not generate trading instructions."
ENTRY_OBSERVATION_STATES = {"WARM", "HOT", "OVERHEAT"}
MACRO_MULTIPLIERS = {
    "supportive": 1.0,
    "neutral": 0.5,
    "restrictive": 0.0,
    "unknown": 0.0,
}


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
    return {
        "window_status": _optional_text(summary.get("status")) or "unsupported",
        "has_decision_usable_completed_stats": bool(included_completed_stats_dates or completed_dates > 0),
        "completed_dates": completed_dates,
        "pending_dates": _safe_int(summary.get("replay_dates_pending")),
        "unsupported_dates": _safe_int(summary.get("replay_dates_unsupported")),
        "proxy_only_dates": _safe_int(summary.get("replay_dates_proxy_only")),
        "completed_candidate_rows": completed_rows,
        "pending_candidate_rows": _safe_int(summary.get("pending_rows")),
        "unsupported_candidate_rows": _safe_int(summary.get("unsupported_rows")),
        "proxy_only_candidate_rows": _safe_int(summary.get("proxy_only_rows")),
        "included_completed_stats_dates": included_completed_stats_dates,
        "blocked_dates": _replay_blocked_dates(summary.get("date_reasons")),
        "completed_zero_signal_dates": _completed_zero_signal_dates(summary.get("date_reasons")),
    }


def _empty_replay_status() -> dict[str, object]:
    return {
        "window_status": "unsupported",
        "has_decision_usable_completed_stats": False,
        "completed_dates": 0,
        "pending_dates": 0,
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "completed_candidate_rows": 0,
        "pending_candidate_rows": 0,
        "unsupported_candidate_rows": 0,
        "proxy_only_candidate_rows": 0,
        "included_completed_stats_dates": [],
        "blocked_dates": [],
        "completed_zero_signal_dates": [],
    }


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
    if composite_score <= -0.3:
        return "supportive"
    if composite_score >= 0.3:
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
