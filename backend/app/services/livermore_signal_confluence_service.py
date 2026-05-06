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


def build_livermore_signal_confluence(
    *,
    as_of_date: str,
    livermore_payload: dict[str, object],
    macro_payload: dict[str, object],
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

    entry_observations = _build_entry_observations(
        livermore_payload=livermore_payload,
        allows_new_entry_observations=allows_new_entry_observations,
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
        "strategy_context": {
            "market_gate_state": market_gate_state,
            "market_gate_exposure": market_gate_exposure,
            "allows_new_entry_observations": allows_new_entry_observations,
        },
        "position_size_hint": position_size_hint,
        "entry_observations": entry_observations,
        "exit_observations": exit_observations,
        "diagnostics": diagnostics,
        "disclaimer": DISCLAIMER,
    }


def _build_entry_observations(
    *,
    livermore_payload: Mapping[str, object],
    allows_new_entry_observations: bool,
    diagnostics: list[str],
) -> list[dict[str, object]]:
    stock_candidates = _mapping(livermore_payload.get("stock_candidates"))
    items = _list_of_mappings((stock_candidates or {}).get("items"))
    if not items:
        diagnostics.append("No stock candidates available for observation.")
        return []

    action = "observe_entry_setup" if allows_new_entry_observations else "observe_only"
    return [
        {
            "stock_code": item.get("stock_code"),
            "stock_name": item.get("stock_name"),
            "action": action,
            "trigger_price": item.get("breakout_level"),
            "current_price": item.get("close"),
            "invalidation_reference_price": item.get("ema10"),
            "evidence": _entry_evidence(item, diagnostics),
        }
        for item in items
    ]


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


def _mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


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
