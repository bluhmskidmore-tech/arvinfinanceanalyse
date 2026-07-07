"""Macro-cycle overlay for the Livermore market gate.

Additive-disclosure, behavior-conservative design:

- ``apply_macro_gate_overlay`` never mutates the input gate and never changes
  the meaning of existing gate fields (``state``, ``passed_conditions``,
  ``conditions`` ...). It only adds ``macro_context`` / ``macro_overlay`` /
  ``exposure_raw`` / ``formula_version`` and, when a deteriorating macro cycle
  is confirmed, lowers ``exposure`` via ``min(exposure_raw, cap)``.
- The macro score used for a gate dated T must be built from inputs with
  business_date <= T (enforced upstream by ``build_cycle_macro_snapshot``);
  this module re-checks for look-ahead dates and refuses to adjust on any
  violation.
- If macro data is missing, expired, or look-ahead dated, the gate exposure is
  byte-identical to the raw gate (hard regression safety line).

Formula (rv_market_gate_macro_overlay_v1):

    cycle_state = recession    if macro_score <  0.25
                  contraction  if 0.25 <= macro_score < 0.40
                  neutral      if 0.40 <= macro_score < 0.60
                  expansion    if macro_score >= 0.60
    exposure_cap = {recession: 0.25, contraction: 0.50}[cycle_state]  (else no cap)
    exposure     = min(exposure_raw, exposure_cap)                    (never raises)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.app.core_finance.data_freshness import (
    FRESHNESS_TIER_EXPIRED,
    assess_freshness,
)

GATE_MACRO_OVERLAY_FORMULA_VERSION = "rv_market_gate_macro_overlay_v1"

MACRO_CYCLE_STATE_RECESSION = "recession"
MACRO_CYCLE_STATE_CONTRACTION = "contraction"
MACRO_CYCLE_STATE_NEUTRAL = "neutral"
MACRO_CYCLE_STATE_EXPANSION = "expansion"

# Thresholds on the cycle macro score (cycle_macro_score.compute_macro_score, range [0, 1]).
MACRO_SCORE_CONTRACTION_MIN = 0.25
MACRO_SCORE_NEUTRAL_MIN = 0.40
MACRO_SCORE_EXPANSION_MIN = 0.60

# Exposure caps applied only in confirmed deteriorating states; other states never adjust.
MACRO_EXPOSURE_CAP_BY_STATE: dict[str, float] = {
    MACRO_CYCLE_STATE_RECESSION: 0.25,
    MACRO_CYCLE_STATE_CONTRACTION: 0.50,
}

MACRO_OVERLAY_RULE_TEXT = (
    "exposure = min(exposure_raw, cap[cycle_state]) with cap recession=0.25, contraction=0.50; "
    "cycle_state from macro_score: <0.25 recession, [0.25,0.40) contraction, "
    "[0.40,0.60) neutral, >=0.60 expansion; no adjustment when macro is "
    "missing/expired/look-ahead or in neutral/expansion states."
)

MACRO_CONTEXT_STATUS_READY = "ready"
MACRO_CONTEXT_STATUS_MISSING = "missing"
MACRO_CONTEXT_STATUS_EXPIRED = "expired"
MACRO_CONTEXT_STATUS_LOOK_AHEAD = "look_ahead"


@dataclass(frozen=True)
class MacroCycleObservation:
    """Macro-cycle inputs as of the gate trade date T (all business dates must be <= T).

    ``component_dates`` rows are ``(input_family, input_label, cadence, business_date)``
    matching the service-side cycle-input evidence shape.
    """

    macro_score: float | None
    component_dates: tuple[tuple[str, str, str, str], ...] = ()
    evidence: str = ""


def classify_macro_cycle_state(macro_score: float) -> str:
    if macro_score < MACRO_SCORE_CONTRACTION_MIN:
        return MACRO_CYCLE_STATE_RECESSION
    if macro_score < MACRO_SCORE_NEUTRAL_MIN:
        return MACRO_CYCLE_STATE_CONTRACTION
    if macro_score < MACRO_SCORE_EXPANSION_MIN:
        return MACRO_CYCLE_STATE_NEUTRAL
    return MACRO_CYCLE_STATE_EXPANSION


def apply_macro_gate_overlay(
    gate: dict[str, object],
    *,
    gate_as_of_date: str | None,
    macro: MacroCycleObservation | None,
) -> dict[str, object]:
    """Return a copy of the gate payload with additive macro disclosure and a conservative cap.

    Existing keys keep their exact values except ``exposure``, which is lowered
    (never raised) only when a deteriorating macro cycle is confirmed with
    usable, non-expired, non-look-ahead macro inputs.
    """
    result = dict(gate)
    exposure_raw = _safe_float(gate.get("exposure")) or 0.0

    components: list[dict[str, object]] = []
    if macro is not None and gate_as_of_date:
        for input_family, input_label, cadence, business_date in macro.component_dates:
            assessment = assess_freshness(business_date, gate_as_of_date, cadence=cadence)
            components.append(
                {
                    "input_family": input_family,
                    "input": input_label,
                    "cadence": cadence,
                    "business_date": business_date,
                    "age_days": assessment.age_days,
                    "tier": assessment.tier,
                }
            )

    status = _macro_context_status(
        gate_as_of_date=gate_as_of_date,
        macro=macro,
        components=components,
    )

    macro_score = macro.macro_score if macro is not None else None
    cycle_state = (
        classify_macro_cycle_state(macro_score)
        if status == MACRO_CONTEXT_STATUS_READY and macro_score is not None
        else None
    )
    data_date, lag_days, max_component_lag_days = _lag_disclosure(
        gate_as_of_date=gate_as_of_date,
        components=components,
    )

    cap = MACRO_EXPOSURE_CAP_BY_STATE.get(cycle_state) if cycle_state is not None else None
    applied = cap is not None and exposure_raw > cap
    exposure_adjusted = round(min(exposure_raw, cap), 4) if applied and cap is not None else exposure_raw

    result["exposure"] = exposure_adjusted
    result["exposure_raw"] = exposure_raw
    result["formula_version"] = GATE_MACRO_OVERLAY_FORMULA_VERSION
    result["macro_context"] = {
        "status": status,
        "cycle_state": cycle_state,
        "macro_score": macro_score,
        "gate_as_of_date": gate_as_of_date,
        "data_date": data_date,
        "lag_days": lag_days,
        "max_component_lag_days": max_component_lag_days,
        "components": components,
        "evidence": macro.evidence if macro is not None else "",
        "formula_version": GATE_MACRO_OVERLAY_FORMULA_VERSION,
    }
    result["macro_overlay"] = {
        "applied": applied,
        "exposure_cap": cap,
        "exposure_raw": exposure_raw,
        "exposure_adjusted": exposure_adjusted,
        "rule": MACRO_OVERLAY_RULE_TEXT,
        "formula_version": GATE_MACRO_OVERLAY_FORMULA_VERSION,
    }
    return result


def _macro_context_status(
    *,
    gate_as_of_date: str | None,
    macro: MacroCycleObservation | None,
    components: list[dict[str, object]],
) -> str:
    if (
        macro is None
        or macro.macro_score is None
        or not gate_as_of_date
        or not components
    ):
        return MACRO_CONTEXT_STATUS_MISSING
    ages = [row["age_days"] for row in components]
    if any(age is None for age in ages):
        return MACRO_CONTEXT_STATUS_MISSING
    if any(isinstance(age, int) and age < 0 for age in ages):
        return MACRO_CONTEXT_STATUS_LOOK_AHEAD
    if any(row["tier"] == FRESHNESS_TIER_EXPIRED for row in components):
        return MACRO_CONTEXT_STATUS_EXPIRED
    return MACRO_CONTEXT_STATUS_READY


def _lag_disclosure(
    *,
    gate_as_of_date: str | None,
    components: list[dict[str, object]],
) -> tuple[str | None, int | None, int | None]:
    gate_date = _parse_date(gate_as_of_date)
    dates = [
        parsed
        for row in components
        if (parsed := _parse_date(str(row.get("business_date") or ""))) is not None
    ]
    if gate_date is None or not dates:
        return None, None, None
    data_date = max(dates)
    return (
        data_date.isoformat(),
        (gate_date - data_date).days,
        (gate_date - min(dates)).days,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
